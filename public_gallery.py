#!/usr/bin/env python3
"""Crawl the public Buildweek project gallery once Devpost publishes it.

This is the no-login path. It deliberately fails closed while the gallery is
unpublished rather than attempting to bypass the participant-list gate.
"""
import datetime
import json
import os
import re
import sys
import time
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(ROOT, "data", "hackathons.json")
OUT = os.path.join(ROOT, "data", "openai-build-week.json")
STATE = os.path.join(ROOT, "data", ".scrape_state_public_gallery.json")
BASE = "https://openai.devpost.com"
PROJECT_BASE = "https://devpost.com"
HACKATHON_NAME = "OpenAI Build Week"
DELAY = float(os.environ.get("PAGE_DELAY", "0.35"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "0"))

SLUG_RE = re.compile(r"^/software/([a-z0-9][a-z0-9-]+[a-z0-9])/?$", re.I)
USER_RE = re.compile(r"^https?://devpost\.com/([a-z0-9][a-z0-9_-]{1,30})/?$", re.I)
NON_USER = {
    "software", "hackathons", "portfolio", "settings", "assets", "users",
    "submit-to", "forum_topics", "challenges", "search", "resources",
    "rules", "updates", "participants", "project-gallery", "details",
    "faqs", "organize", "about", "careers", "contact", "help", "legal",
    "blog", "guides", "product", "info",
}


def get(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def project_slugs(html):
    soup = BeautifulSoup(html, "html.parser")
    slugs = set()
    for anchor in soup.find_all("a", href=True):
        href = urlparse(urljoin(BASE + "/", str(anchor["href"])))
        match = SLUG_RE.match(href.path)
        if match and href.netloc in {"openai.devpost.com", "devpost.com"}:
            slugs.add(match.group(1).lower())
    return slugs


def gallery_pages(html):
    soup = BeautifulSoup(html, "html.parser")
    pages = {1}
    for anchor in soup.find_all("a", href=True):
        query = parse_qs(urlparse(urljoin(BASE + "/", str(anchor["href"]))).query)
        for value in query.get("page", []):
            if value.isdigit():
                pages.add(int(value))
    return pages


def is_unpublished(html):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    return "haven't published this gallery yet" in text or "hasn't published this gallery yet" in text


def parse_project(html, slug, categories):
    soup = BeautifulSoup(html, "html.parser")
    def meta(name):
        tag = soup.find("meta", property=name)
        return str(tag.get("content", "")).strip() if tag else ""

    title = meta("og:title") or slug
    description = meta("og:description")
    image = meta("og:image")
    text = soup.get_text(" ", strip=True)

    members = []
    seen_members = set()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(PROJECT_BASE + "/", str(anchor["href"]))
        match = USER_RE.match(href)
        if not match:
            continue
        handle = match.group(1)
        key = handle.lower()
        if key in NON_USER or key in seen_members:
            continue
        seen_members.add(key)
        members.append({
            "handle": handle,
            "name": anchor.get_text(" ", strip=True) or handle,
            "url": f"{PROJECT_BASE}/{handle}",
        })

    repo_url = demo_url = None
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        low = href.lower()
        if not repo_url and any(host in low for host in ("github.com", "gitlab.com", "bitbucket.org")):
            repo_url = href
        if not demo_url and any(token in low for token in ("youtu.be", "youtube.com", "demo")):
            demo_url = href

    category = next((c for c in categories if re.search(r"\b" + re.escape(c) + r"\b", text, re.I)), None)
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "image": image,
        "category": category,
        "members": members,
        "url": f"{PROJECT_BASE}/software/{slug}",
        "repo_url": repo_url,
        "demo_url": demo_url,
    }


def load_state():
    if not os.path.exists(STATE):
        return {"pages": [], "slugs": []}
    with open(STATE) as handle:
        state = json.load(handle)
    if not isinstance(state.get("pages"), list) or not isinstance(state.get("slugs"), list):
        raise ValueError("invalid public-gallery checkpoint")
    return state


def save_state(state):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(state, handle, indent=2)
    os.replace(tmp, STATE)


def update_manifest(count, generated_at):
    with open(MANIFEST) as handle:
        manifest = json.load(handle)
    for entry in manifest.get("hackathons", []):
        if entry.get("slug") == "openai-build-week":
            entry["count"] = count
            entry["generated_at"] = generated_at
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, MANIFEST)


def main():
    with open(OUT) as handle:
        data = json.load(handle)
    categories = data.get("categories", [])
    projects = {project["slug"].lower(): project for project in data.get("projects", [])}
    state = load_state()
    completed_pages = set(state["pages"])
    discovered = set(state["slugs"]) | set(projects)

    session = requests.Session()
    session.headers.update({"User-Agent": "BuildweekCommunityGallery/1.0"})
    first = get(session, f"{BASE}/project-gallery")
    if is_unpublished(first):
        print("The official Buildweek project gallery is not published yet.")
        return 2

    pending_pages = sorted(gallery_pages(first) - completed_pages)
    if not pending_pages:
        pending_pages = [1]

    for page in pending_pages:
        if MAX_PAGES and page > MAX_PAGES:
            break
        html = first if page == 1 else get(session, f"{BASE}/project-gallery?page={page}")
        slugs = project_slugs(html)
        if not slugs:
            raise RuntimeError(f"page {page} contained no project links; refusing to mark it complete")
        print(f"page {page}: {len(slugs)} projects", flush=True)
        for slug in sorted(slugs - discovered):
            project_html = get(session, f"{PROJECT_BASE}/software/{slug}")
            projects[slug] = parse_project(project_html, slug, categories)
            discovered.add(slug)
            time.sleep(DELAY)
        completed_pages.add(page)
        state = {"pages": sorted(completed_pages), "slugs": sorted(discovered)}
        save_state(state)

    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    output = {**data, "projects": list(projects.values()), "count": len(projects), "generated_at": generated_at}
    tmp = OUT + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, OUT)
    update_manifest(len(projects), generated_at)
    print(f"DONE: {len(projects)} projects written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

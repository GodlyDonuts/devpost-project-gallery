#!/usr/bin/env python3
"""
OpenAI Build Week — community project gallery scraper.

WHY THIS EXISTS
  Devpost doesn't publish the Build Week project gallery until a couple weeks
  after the deadline. This scraper walks the participant list, checks each
  participant's public projects, keeps only those *submitted to OpenAI Build
  Week*, and classifies them into one of the four official tracks.

  Output: data/projects.json  (consumed by the GitHub Pages UI in app.js)

IMPORTANT — TWO THINGS ARE REQUIRED (evidence-based):
  1. DEVP0ST_SESSION_COOKIE  — the participant list is login-gated
                                ("Please log in to browse this hackathon's
                                participants."). A session cookie is mandatory.
  2. PROXY_URL (optional)    — 46k+ participants => 100k+ requests. Use a proxy
                                pool to avoid IP bans / rate limits.

The script is fully RESUMABLE: it checkpoints processed handles and found
projects, so you can run it in chunks / across CI jobs.

USAGE
  export DEVP0ST_SESSION_COOKIE="session=...; _devpost=..."
  export PROXY_URL="http://user:pass@host:port"      # or comma-separated list
  python3 scrape.py

  Optional env:
    HACKATHON_NAME="OpenAI Build Week"   (what we match in "Submitted to")
    HACKATHON_ID="30223"
    OUTPUT="data/projects.json"
    CHECKPOINT="data/.scrape_state.json"
    START_PAGE="1"
    MAX_PAGES="0"            # 0 = no limit
    PAGE_DELAY="0.25"        # seconds between requests (jitter added)
"""

import os
import re
import sys
import json
import time
import random
import datetime
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing deps. Install with: pip install requests beautifulsoup4")

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
HACKATHON_NAME = os.getenv("HACKATHON_NAME", "OpenAI Build Week")
HACKATHON_ID = os.getenv("HACKATHON_ID", "30223")
OUTPUT = os.getenv("OUTPUT", "data/projects.json")
CHECKPOINT = os.getenv("CHECKPOINT", "data/.scrape_state.json")
BASE = "https://openai.devpost.com"
PROFILE_BASE = "https://devpost.com"
COOKIE = os.getenv("DEVP0ST_SESSION_COOKIE", "")
PROXIES_RAW = os.getenv("PROXY_URL", "")
START_PAGE = int(os.getenv("START_PAGE", "1"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "0"))
PAGE_DELAY = float(os.getenv("PAGE_DELAY", "0.25"))

CATEGORIES = [
    "Apps for Your Life",
    "Work & Productivity",
    "Developer Tools",
    "Education",
]

# Paths that are NOT user profiles — used to filter participant links.
NON_USER = {
    "software", "hackathons", "portfolio", "settings", "assets",
    "users", "submit-to", "forum_topics", "challenges", "search",
    "resources", "rules", "updates", "participants", "project-gallery",
    "details", "faqs", "organize", "about", "careers", "contact",
    "help", "legal", "blog", "guides", "webinar-events", "customer-stories",
    "product", "info", "devpost.team", "discord.com", "twitter.com",
    "linkedin.com", "facebook.com", "google.com", "youtube.com",
}

# --------------------------------------------------------------------------- #
# Session / proxy
# --------------------------------------------------------------------------- #
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
})
if COOKIE:
    session.headers["Cookie"] = COOKIE

PROXIES = [p.strip() for p in PROXIES_RAW.split(",") if p.strip()]


def proxy_for():
    if not PROXIES:
        return None
    url = random.choice(PROXIES)
    return {"http": url, "https": url}


def get(url, retries=4):
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, proxies=proxy_for(), timeout=25)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  429 on {url} — sleeping {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code in (503, 502, 504):
                time.sleep(3 * (attempt + 1))
                continue
            return r
        except Exception as e:  # network / proxy errors
            last = e
            time.sleep(2 * (attempt + 1))
    print(f"  FAILED after {retries} tries: {url} ({last})", flush=True)
    return None


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
SOFTWARE_RE = re.compile(r"/software/([a-z0-9][a-z0-9\-]+[a-z0-9])", re.I)
USER_RE = re.compile(r"^https?://devpost\.com/([a-z0-9][a-z0-9_\-]{1,30})$", re.I)


def extract_handles_from_participants(html):
    """Return unique participant handles from a /participants?page=N page."""
    soup = BeautifulSoup(html, "html.parser")
    handles = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        m = USER_RE.match(urljoin(BASE + "/", href))
        if not m:
            continue
        h = m.group(1)
        if h.lower() in NON_USER:
            continue
        # skip handles that are clearly not user pages (e.g. contain a dot/tld)
        if "." in h or "/" in h:
            continue
        handles.add(h)
    return handles


def extract_profile_projects(html):
    """Return set of software slugs listed on a user profile page."""
    slugs = set()
    for m in SOFTWARE_RE.finditer(html):
        slug = m.group(1)
        # 'new' is the "create project" link, not a real project
        if slug in ("new", "search"):
            continue
        slugs.add(slug)
    return slugs


def parse_project(html, slug):
    soup = BeautifulSoup(html, "html.parser")
    # title
    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    if not title:
        t = soup.find("title")
        if t:
            title = t.get_text(strip=True).replace(" | Devpost", "")

    # description
    desc = ""
    ogd = soup.find("meta", property="og:description")
    if ogd and ogd.get("content"):
        desc = ogd["content"].strip()

    # members (authors) — links to /<handle> inside the project
    members = []
    seen = set()
    for a in soup.find_all("a", href=True):
        m = USER_RE.match(a["href"])
        if not m:
            continue
        h = m.group(1)
        if h.lower() in NON_USER or h in seen:
            continue
        seen.add(h)
        name = a.get_text(strip=True) or h
        members.append({"handle": h, "name": name, "url": f"{PROFILE_BASE}/{h}"})

    # submitted to — look for the hackathon name near "Submitted to"
    text = soup.get_text(" ", strip=True)
    submitted_here = HACKATHON_NAME.lower() in text.lower()

    # category — match any of the four official tracks present on the page
    category = "Uncategorized"
    for c in CATEGORIES:
        if re.search(r"\b" + re.escape(c) + r"\b", text, re.I):
            category = c
            break

    # repo / demo links (best effort)
    repo_url = demo_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        low = href.lower()
        if any(k in low for k in ("github.com", "gitlab.com", "bitbucket.org")):
            repo_url = href
        if any(k in low for k in ("demo", "youtu.be", "youtube.com")) and not demo_url:
            demo_url = href

    return {
        "slug": slug,
        "title": title,
        "description": desc,
        "category": category if submitted_here else None,
        "members": members,
        "submitted_to_build_week": submitted_here,
        "url": f"{PROFILE_BASE}/software/{slug}",
        "repo_url": repo_url,
        "demo_url": demo_url,
    }


# --------------------------------------------------------------------------- #
# State / checkpoint
# --------------------------------------------------------------------------- #
def load_state():
    if os.path.exists(CHECKPOINT):
        try:
            with open(CHECKPOINT) as f:
                return json.load(f)
        except Exception:
            pass
    return {"processed": [], "projects": []}


def save_state(state):
    os.makedirs(os.path.dirname(CHECKPOINT) or ".", exist_ok=True)
    tmp = CHECKPOINT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, CHECKPOINT)


def write_output(projects):
    os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
    seen = {}
    for p in projects:
        seen[p["slug"]] = p
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hackathon": HACKATHON_NAME,
        "count": len(seen),
        "projects": list(seen.values()),
    }
    tmp = OUTPUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    os.replace(tmp, OUTPUT)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    if not COOKIE:
        sys.exit("ERROR: DEVP0ST_SESSION_COOKIE is required (participant list is login-gated).")

    state = load_state()
    processed = set(state["processed"])
    projects = state["projects"]

    print(f"Scraping participants for '{HACKATHON_NAME}' (id={HACKATHON_ID})")
    print(f"Already processed: {len(processed)} handles · found: {len(projects)} projects")
    print(f"Proxy pool size: {len(PROXIES)} · page delay: {PAGE_DELAY}s")

    page = START_PAGE
    stall = 0  # pages with no new handles before we give up
    while True:
        if MAX_PAGES and page >= START_PAGE + MAX_PAGES:
            print(f"Reached MAX_PAGES limit ({MAX_PAGES}). Stopping.")
            break

        url = f"{BASE}/participants?page={page}"
        r = get(url)
        if not r or r.status_code != 200:
            print(f"Stop: participants page {page} returned {r.status_code if r else 'ERR'}")
            break

        handles = extract_handles_from_participants(r.text)
        new = handles - processed
        print(f"page {page}: {len(handles)} handles, {len(new)} new", flush=True)

        if not handles:
            stall += 1
            if stall >= 3:
                print("No handles found on 3 consecutive pages — done enumerating.")
                break
        else:
            stall = 0

        for h in sorted(new):
            processed.add(h)
            pr = get(f"{PROFILE_BASE}/{h}")
            if not pr or pr.status_code != 200:
                continue
            slugs = extract_profile_projects(pr.text)
            for slug in slugs:
                # skip if already collected
                if any(p["slug"] == slug for p in projects):
                    continue
                pj = get(f"{PROFILE_BASE}/software/{slug}")
                if not pj or pj.status_code != 200:
                    continue
                info = parse_project(pj.text, slug)
                if info["submitted_to_build_week"]:
                    projects.append({
                        "slug": info["slug"],
                        "title": info["title"],
                        "description": info["description"],
                        "category": info["category"],
                        "members": info["members"],
                        "url": info["url"],
                        "repo_url": info["repo_url"],
                        "demo_url": info["demo_url"],
                    })
                    print(f"  + [{info['category']}] {info['title']}  (by {h})", flush=True)
            time.sleep(PAGE_DELAY * random.uniform(0.6, 1.4))

        # checkpoint every page
        state["processed"] = sorted(processed)
        state["projects"] = projects
        save_state(state)
        write_output(projects)

        page += 1
        time.sleep(PAGE_DELAY * random.uniform(0.6, 1.4))

    # final flush
    state["processed"] = sorted(processed)
    state["projects"] = projects
    save_state(state)
    write_output(projects)
    print(f"\nDONE. {len(processed)} handles processed, {len(projects)} Build Week projects saved to {OUTPUT}")


if __name__ == "__main__":
    main()

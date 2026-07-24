#!/usr/bin/env python3
"""
Devpost hackathon project gallery scraper  (multi-hackathon aware).

Each hackathon is described in data/hackathons.json and gets its own
data/<slug>.json file. The landing page (index.html) lists them; the
per-hackathon page (gallery.html?h=<slug>) renders that file.

WHY THIS EXISTS
  Devpost doesn't publish a hackathon's gallery until a couple weeks after the
  deadline. This walks the participant list, keeps only projects *submitted to*
  the target hackathon, and classifies them into that hackathon's tracks.

REQUIRED (evidence-based)
  1. DEVP0ST_SESSION_COOKIE  — the participant list is login-gated.
  2. PROXY_URL (optional)    — 46k+ participants => 100k+ requests; use a proxy.

RESUMABLE: per-hackathon checkpoint (data/.scrape_state_<slug>.json) so you can
run in chunks / across CI jobs.

USAGE
  export DEVP0ST_SESSION_COOKIE="session=...; _devpost=..."
  export PROXY_URL="http://user:pass@host:port"        # optional but recommended
  python3 scrape.py                 # scrapes every hackathon in the manifest
  HACKATHON_SLUG=openai-build-week python3 scrape.py   # just one
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
# Paths / config
# --------------------------------------------------------------------------- #
ROOT = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(ROOT, "data", "hackathons.json")
DATA_DIR = os.path.join(ROOT, "data")
BASE = "https://openai.devpost.com"
PROFILE_BASE = "https://devpost.com"

COOKIE = os.getenv("DEVP0ST_SESSION_COOKIE", "")
PROXIES_RAW = os.getenv("PROXY_URL", "")
HACKATHON_SLUG = os.getenv("HACKATHON_SLUG", "")
START_PAGE = int(os.getenv("START_PAGE", "1"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "0"))
PAGE_DELAY = float(os.getenv("PAGE_DELAY", "0.25"))

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
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    print(f"  FAILED after {retries} tries: {url} ({last})", flush=True)
    return None


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
SOFTWARE_RE = re.compile(r"/software/([a-z0-9][a-z0-9\-]+[a-z0-9])", re.I)
USER_RE = re.compile(r"^https?://devpost\.com/([a-z0-9][a-z0-9_\-]{1,30})$", re.I)


def extract_handles_from_participants(html):
    soup = BeautifulSoup(html, "html.parser")
    handles = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        m = USER_RE.match(urljoin(BASE + "/", href))
        if not m:
            continue
        h = m.group(1)
        if h.lower() in NON_USER or "." in h or "/" in h:
            continue
        handles.add(h)
    return handles


def extract_profile_projects(html):
    return {
        m.group(1)
        for m in SOFTWARE_RE.finditer(html)
        if m.group(1) not in ("new", "search")
    }


def parse_project(html, slug, categories, hackathon_name):
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = str(og["content"]).strip()
    if not title:
        t = soup.find("title")
        if t:
            title = t.get_text(strip=True).replace(" | Devpost", "")

    desc = ""
    ogd = soup.find("meta", property="og:description")
    if ogd and ogd.get("content"):
        desc = str(ogd["content"]).strip()

    image = ""
    ogi = soup.find("meta", property="og:image")
    if ogi and ogi.get("content"):
        image = str(ogi["content"]).strip()

    members = []
    seen = set()
    for a in soup.find_all("a", href=True):
        m = USER_RE.match(str(a["href"]))
        if not m:
            continue
        h = m.group(1)
        if h.lower() in NON_USER or h.lower() in seen:
            continue
        seen.add(h.lower())
        members.append({"handle": h, "name": a.get_text(strip=True) or h, "url": f"{PROFILE_BASE}/{h}"})

    text = soup.get_text(" ", strip=True)
    submitted_here = hackathon_name.lower() in text.lower()

    category = None  # track labels aren't on public pages; filled in manually later
    for c in categories:
        if re.search(r"\b" + re.escape(c) + r"\b", text, re.I):
            category = c
            break

    repo_url = demo_url = None
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        low = href.lower()
        if any(k in low for k in ("github.com", "gitlab.com", "bitbucket.org")):
            repo_url = href
        elif any(k in low for k in ("demo", "youtu.be", "youtube.com")) and not demo_url:
            demo_url = href

    return {
        "slug": slug,
        "title": title,
        "description": desc,
        "image": image,
        "category": category if submitted_here else None,
        "submitted_to_hackathon": submitted_here,
        "members": members,
        "url": f"{PROFILE_BASE}/software/{slug}",
        "repo_url": repo_url,
        "demo_url": demo_url,
    }


# --------------------------------------------------------------------------- #
# State / manifest
# --------------------------------------------------------------------------- #
def load_manifest():
    with open(MANIFEST) as f:
        return json.load(f)


def save_manifest(manifest):
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, MANIFEST)


def state_path(slug):
    return os.path.join(DATA_DIR, f".scrape_state_{slug}.json")


def out_path(slug):
    return os.path.join(DATA_DIR, f"{slug}.json")


def load_state(slug):
    p = state_path(slug)
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            pass
    return {"processed": [], "projects": []}


def save_state(slug, state):
    tmp = state_path(slug) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, state_path(slug))


def write_output(slug, cfg, projects):
    out = {
        "slug": slug,
        "name": cfg.get("name", slug),
        "hackathon_id": cfg.get("hackathon_id"),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "categories": cfg.get("categories", []),
        "count": len(projects),
        "projects": projects,
    }
    tmp = out_path(slug) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    os.replace(tmp, out_path(slug))
    return out


# --------------------------------------------------------------------------- #
# Crawl one hackathon
# --------------------------------------------------------------------------- #
def process_hackathon(cfg):
    slug = cfg["slug"]
    name = cfg.get("name", slug)
    hid = cfg.get("hackathon_id", "")
    categories = cfg.get("categories", [])
    print(f"\n=== {name} (slug={slug}, id={hid}) ===")

    state = load_state(slug)
    processed = set(state["processed"])
    projects = state["projects"]

    page = START_PAGE
    stall = 0
    while True:
        if MAX_PAGES and page >= START_PAGE + MAX_PAGES:
            print(f"  Reached MAX_PAGES limit ({MAX_PAGES}).")
            break
        url = f"{BASE}/participants?page={page}"
        r = get(url)
        if not r or r.status_code != 200:
            print(f"  Stop: participants page {page} returned {r.status_code if r else 'ERR'}")
            break
        handles = extract_handles_from_participants(r.text)
        new = handles - processed
        print(f"  page {page}: {len(handles)} handles, {len(new)} new", flush=True)
        if not handles:
            stall += 1
            if stall >= 3:
                print("  No handles on 3 consecutive pages — done enumerating.")
                break
        else:
            stall = 0

        for h in sorted(new):
            processed.add(h)
            pr = get(f"{PROFILE_BASE}/{h}")
            if not pr or pr.status_code != 200:
                continue
            for pslug in extract_profile_projects(pr.text):
                if any(p["slug"] == pslug for p in projects):
                    continue
                pj = get(f"{PROFILE_BASE}/software/{pslug}")
                if not pj or pj.status_code != 200:
                    continue
                info = parse_project(pj.text, pslug, categories, name)
                if info["submitted_to_hackathon"]:
                    projects.append({
                        "slug": info["slug"],
                        "title": info["title"],
                        "description": info["description"],
                        "image": info["image"],
                        "category": info["category"],
                        "members": info["members"],
                        "url": info["url"],
                        "repo_url": info["repo_url"],
                        "demo_url": info["demo_url"],
                    })
                    print(f"    + [{info['category']}] {info['title']}  (by {h})", flush=True)
            time.sleep(PAGE_DELAY * random.uniform(0.6, 1.4))

        state["processed"] = sorted(processed)
        state["projects"] = projects
        save_state(slug, state)
        write_output(slug, cfg, projects)
        page += 1
        time.sleep(PAGE_DELAY * random.uniform(0.6, 1.4))

    state["processed"] = sorted(processed)
    state["projects"] = projects
    save_state(slug, state)
    out = write_output(slug, cfg, projects)
    print(f"  DONE {name}: {len(processed)} handles, {len(projects)} projects.")
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    if not COOKIE:
        sys.exit("ERROR: DEVP0ST_SESSION_COOKIE is required (participant list is login-gated).")

    manifest = load_manifest()
    hacks = manifest.get("hackathons", [])
    if not hacks:
        sys.exit("ERROR: no hackathons in data/hackathons.json")

    targets = [h for h in hacks if h["slug"] == HACKATHON_SLUG] if HACKATHON_SLUG else hacks
    if HACKATHON_SLUG and not targets:
        sys.exit(f"ERROR: no hackathon with slug '{HACKATHON_SLUG}' in manifest.")

    print(f"Scraping {len(targets)} hackathon(s). Proxy pool size: {len(PROXIES)}.")
    for cfg in targets:
        out = process_hackathon(cfg)
        # update manifest entry
        for i, h in enumerate(manifest["hackathons"]):
            if h["slug"] == cfg["slug"]:
                manifest["hackathons"][i]["count"] = out["count"]
                manifest["hackathons"][i]["generated_at"] = out["generated_at"]
        save_manifest(manifest)
        print(f"  manifest updated: {cfg['slug']} -> {out['count']} projects")


if __name__ == "__main__":
    main()

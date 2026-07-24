#!/usr/bin/env python3
"""Snowball crawler: expand Build Week coverage WITHOUT a login cookie.

Strategy: every project page lists its members (devpost.com/<handle>); every
member profile lists all their /software/<slug> projects. We BFS from the seeds
(the projects already in the data file) across this public social graph, and
keep any project that literally mentions "OpenAI Build Week" on its page.

Everything is public. No participant list, no cookie, no personal-data storage
(only the public submission + author-handle credit). Resumable: visited handles
persist to data/.scrape_state_snowball.json so interrupted runs pick up.

Usage:
    python3 snowball.py            # bounded run (limits below)
    MAX_HANDLES=600 python3 snowball.py
"""
import json, re, os, time, urllib.request, sys

ROOT = "/Users/sairamen/projects/devpost-project-gallery"
OUT = f"{ROOT}/data/openai-build-week.json"
STATE = f"{ROOT}/data/.scrape_state_snowball.json"  # matches data/.scrape_state_*.json (gitignored)
HACK = "OpenAI Build Week"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
MAX_HANDLES = int(os.environ.get("MAX_HANDLES", "300"))
MAX_NEW = int(os.environ.get("MAX_NEW", "500"))
DELAY = float(os.environ.get("PAGE_DELAY", "0.12"))

SLUG_RE = re.compile(r"/software/([a-z0-9][a-z0-9\-]+[a-z0-9])", re.I)
USER_RE = re.compile(r"^https?://devpost\.com/([a-z0-9][a-z0-9_\-]{1,30})$", re.I)


def fetch(url, tries=2):
    for _ in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=25).read().decode("utf-8", "ignore")
        except Exception:
            time.sleep(0.5)
    return ""


def member_handles(html):
    out = set()
    for a in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        um = USER_RE.match(a.group(1))
        if um and "." not in um.group(1):
            out.add(um.group(1).lower())
    return out


def software_slugs(html):
    return {m.group(1).lower() for m in SLUG_RE.finditer(html)}


def parse_project(html, slug):
    m = re.search(r'<meta property="og:title" content="([^"]*)"', html, re.I)
    title = m.group(1).strip() if m else slug
    m = re.search(r'<meta property="og:description" content="([^"]*)"', html, re.I)
    desc = m.group(1).strip() if m else ""
    repo = demo = None
    for a in re.finditer(r'href="([^"]+)"', html, re.I):
        low = a.group(1).lower()
        if any(k in low for k in ("github.com", "gitlab.com", "bitbucket.org")) and not repo:
            repo = a.group(1)
        elif any(k in low for k in ("youtu.be", "youtube.com", "demo")) and not demo:
            demo = a.group(1)
    return {
        "slug": slug, "title": title, "description": desc, "category": None,
        "members": [{"handle": h, "name": h, "url": f"https://devpost.com/{h}"} for h in member_handles(html)],
        "url": f"https://devpost.com/software/{slug}", "repo_url": repo, "demo_url": demo,
    }


# --- load state ---
data = json.load(open(OUT))
projects = data["projects"]
bw_slugs = {p["slug"].lower() for p in projects}
state = json.load(open(STATE)) if os.path.exists(STATE) else {"visited": []}
visited = set(state.get("visited", []))

# seed: handles from current projects' members
queue = []
for p in projects:
    for m in p.get("members", []):
        h = m.get("handle")
        if h and h.lower() not in visited:
            queue.append(h.lower())
# also re-seed from any handle we've seen on BW project pages (members of known)
queue = list(dict.fromkeys(queue))
print(f"start: {len(projects)} BW projects, {len(visited)} handles visited, {len(queue)} handles queued")

processed = 0
added = 0
t0 = time.time()
while queue and processed < MAX_HANDLES and added < MAX_NEW:
    h = queue.pop(0)
    if h in visited:
        continue
    visited.add(h)
    processed += 1
    prof = fetch(f"https://devpost.com/{h}")
    if not prof:
        continue
    for slug in software_slugs(prof):
        if slug in bw_slugs or slug in ("new", "search"):
            continue
        ph = fetch(f"https://devpost.com/software/{slug}")
        if not ph:
            continue
        if HACK.lower() not in ph.lower():   # strict: must mention the hackathon
            continue
        proj = parse_project(ph, slug)
        projects.append(proj)
        bw_slugs.add(slug)
        added += 1
        # new members become future handles
        for m in proj["members"]:
            hh = m.get("handle")
            if hh and hh.lower() not in visited:
                queue.append(hh.lower())
    # persist progress continuously
    json.dump({"visited": sorted(visited)}, open(STATE, "w"))
    json.dump({**data, "projects": projects, "count": len(projects),
               "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},
              open(OUT, "w"), indent=2, ensure_ascii=False)
    if DELAY:
        time.sleep(DELAY)

print(f"done run: processed {processed} handles, added {added} new BW projects -> total {len(projects)}")

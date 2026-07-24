#!/usr/bin/env python3
"""
One-off backfill: add the `image` (Devpost og:image thumbnail) field to every
project in a data/<slug>.json file by re-reading the public project page.

These URLs are public (no session cookie required), so this runs without auth.
Idempotent: skips projects that already have an `image`.
"""
import json
import os
import sys
import time
import random
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing deps. Install with: pip install requests beautifulsoup4")

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")

slug = sys.argv[1] if len(sys.argv) > 1 else "openai-build-week"
path = os.path.join(DATA_DIR, f"{slug}.json")
if not os.path.exists(path):
    sys.exit(f"No such file: {path}")

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
})


def fetch_image(pslug):
    url = f"https://devpost.com/software/{pslug}"
    try:
        r = session.get(url, timeout=25)
    except Exception as e:
        print(f"  ERR {pslug}: {e}")
        return None
    if r.status_code != 200:
        print(f"  {r.status_code} {pslug}")
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return str(og["content"]).strip()
    return None


with open(path) as f:
    data = json.load(f)

projects = data.get("projects", [])
print(f"Backfilling {len(projects)} projects in {slug}.json")
changed = 0
for p in projects:
    if p.get("image"):
        continue
    img = fetch_image(p["slug"])
    if img:
        p["image"] = img
        changed += 1
        print(f"  + {p['title'][:48]!r}: {img.split('/')[-1]}")
    else:
        print(f"  - no image for {p['slug']}")
    time.sleep(random.uniform(0.4, 1.0))

data["projects"] = projects
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
os.replace(tmp, path)
print(f"Done. Added images to {changed} project(s).")

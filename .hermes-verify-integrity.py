#!/usr/bin/env python3
"""FRESH ad-hoc verification (NOT a suite). DATA INTEGRITY (user's hard rule):
every project in data/openai-build-week.json MUST have a real, resolvable Devpost
link that is an actual OpenAI Build Week submission. LIVE-fetch each url to prove
it (not assumed). Also confirm code category=None still holds."""
import importlib.util, json, time, urllib.request
ROOT = "/Users/sairamen/projects/devpost-project-gallery"
fails = []
def check(n, c, d=""):
    print(f"[{'PASS' if c else 'FAIL'}] {n}" + (f"  -- {d}" if d else ""))
    if not c: fails.append(n)

# code check
spec = importlib.util.spec_from_file_location("scrape", f"{ROOT}/scrape.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cats = ["Apps for Your Life", "Work & Productivity", "Developer Tools", "Education"]
html = urllib.request.urlopen("https://devpost.com/software/wyrd-ai", timeout=25).read().decode("utf-8","ignore")
i = m.parse_project(html, "wyrd-ai", cats, "OpenAI Build Week")
check("code.category_none", i["category"] is None, f"got {i['category']!r}")
check("code.submitted_true", bool(i["submitted_to_hackathon"]))

# data integrity: LIVE verify every project link
data = json.load(open(f"{ROOT}/data/openai-build-week.json"))
projs = data.get("projects", [])
print(f"\nProjects in file: {len(projs)}")
all_url = all(p.get("url","").startswith("https://devpost.com/software/") for p in projs)
check("data.every_has_devpost_url", all_url)
check("data.all_category_none", all(p.get("category") is None for p in projs))
ua = {"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
for p in projs:
    slug = p.get("slug","?"); url = p.get("url","")
    try:
        body = urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=25).read().decode("utf-8","ignore")
        is_bw = "openai build week" in body.lower()
        has_title = bool(p.get("title"))
        check(f"live.{slug}", is_bw and has_title, f"BW={is_bw} title={has_title}")
    except Exception as e:
        check(f"live.{slug}", False, f"FETCH FAILED: {e}")
    time.sleep(0.3)
print()
print(("FRESH AD-HOC VERIFICATION: all passed — every project is a live, resolvable, "
       "real OpenAI Build Week submission with a working link."
       if not fails else f"FRESH AD-HOC VERIFICATION: {len(fails)} FAIL — failing live.<slug> = NOT a verified real submission."))
raise SystemExit(1 if fails else 0)

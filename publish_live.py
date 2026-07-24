#!/usr/bin/env python3
"""Publish incremental gallery snapshots without exposing crawler internals."""

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PUBLIC_PATHS = (
    "index.js",
    "gallery.js",
    "scrape.py",
    "classify_projects.py",
    "publish_live.py",
    "data/hackathons.json",
    "data/openai-build-week.json",
    "data/openai-build-week-classifications.json",
    "data/openai-build-week-overrides.json",
    "data/openai-build-week-supplemental-projects.json",
)


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, check=check, capture_output=True)


def publish_once():
    paths = [path for path in PUBLIC_PATHS if (ROOT / path).exists()]
    changed = git("diff", "--quiet", "--", *paths, check=False).returncode != 0
    untracked = [path for path in paths if git("ls-files", "--error-unmatch", path, check=False).returncode != 0]
    if not changed and not untracked:
        print("No public gallery changes to publish.", flush=True)
        return False
    git("add", "--", *paths)
    # Nothing to commit can still occur when only an ignored/untracked path was
    # considered; leave the worktree untouched in that case.
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("No stageable public gallery changes.", flush=True)
        return False
    git("commit", "-m", "Publish gallery update")
    git("push", "origin", "HEAD:main")
    print("Published live gallery update.", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=120)
    args = parser.parse_args()
    while True:
        try:
            publish_once()
        except subprocess.CalledProcessError as error:
            print(error.stderr.strip() or f"git command failed: {error.cmd}", file=sys.stderr, flush=True)
        if not args.watch:
            return
        time.sleep(max(args.interval, 30))


if __name__ == "__main__":
    main()

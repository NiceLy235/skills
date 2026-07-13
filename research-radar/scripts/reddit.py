#!/usr/bin/env python3
"""Reddit source — top posts by keyword, per-subreddit or site-wide.

CLI:
  python3 reddit.py --query llm --since 30d --top 15 --subreddits MachineLearning,deeplearning

REQUIRES a descriptive User-Agent or Reddit returns 429. We set one below.
Stdout: standard JSON envelope (see _common.emit). kind = "discuss".
"""
import argparse
import os
import sys
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_json, emit, utcnow  # noqa: E402

UA = "research-radar/1.0 (research digest tool; python-urllib)"


def window_for(since_dt):
    """Map a cutoff to Reddit's t= window (day/week/month/year/all)."""
    days = (utcnow() - since_dt).days
    if days <= 1:
        return "day"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    if days <= 366:
        return "year"
    return "all"


def _iso(epoch):
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser(description="Reddit source for research-radar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--subreddits", default="",
                    help="comma-separated subs, e.g. MachineLearning,deeplearning")
    args = ap.parse_args()

    t = window_for(parse_since(args.since))
    subs = [s.strip() for s in args.subreddits.split(",") if s.strip()]
    targets = subs if subs else [""]
    headers = {"User-Agent": UA}

    hits = []
    errors = []
    for sub in targets:
        if sub:
            base = f"https://www.reddit.com/r/{sub}/search.json"
            extra = {"restrict_sr": "1"}
        else:
            base = "https://www.reddit.com/search.json"
            extra = {}
        params = {"q": args.query, "sort": "top", "t": t,
                  "limit": str(max(1, min(args.top, 100)))}
        params.update(extra)
        url = base + "?" + urllib.parse.urlencode(params)
        try:
            data = get_json(url, headers=headers)
        except Exception as e:
            errors.append(f"{sub or 'all'}: {e}")
            continue
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {}) or {}
            name = d.get("name") or d.get("id") or ""
            permalink = d.get("permalink") or ""
            selftext = (d.get("selftext") or "").strip()
            created = d.get("created_utc")
            hits.append({
                "id": f"reddit:{name}",
                "title": d.get("title") or "(no title)",
                "url": f"https://www.reddit.com{permalink}" if permalink else (d.get("url") or ""),
                "kind": "discuss",
                "date": _iso(created) if created else "",
                "summary_raw": (selftext[:300] + "…") if len(selftext) > 300 else selftext,
                "metrics": {
                    "score": d.get("score") or 0,
                    "comments": d.get("num_comments") or 0,
                },
                "extra": {"subreddit": d.get("subreddit") or sub, "name": name},
            })
    hits = hits[: args.top]
    emit("reddit", hits, error="; ".join(errors) if errors else None)


if __name__ == "__main__":
    main()

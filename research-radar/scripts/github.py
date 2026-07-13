#!/usr/bin/env python3
"""GitHub source — recent, star-ranked repositories by keyword.

CLI:
  python3 github.py --query mamba --since 30d --top 15 --min-stars 50 --language python

GITHUB_TOKEN env (optional) raises the rate limit from 60 to 5000 req/hr.
Stdout: standard JSON envelope (see _common.emit). kind = "code".
"""
import argparse
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_json, emit  # noqa: E402

ENDPOINT = "https://api.github.com/search/repositories"


def main():
    ap = argparse.ArgumentParser(description="GitHub source for research-radar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-stars", type=int, default=0)
    ap.add_argument("--language", default="")
    args = ap.parse_args()

    cutoff = parse_since(args.since).strftime("%Y-%m-%d")
    q_parts = [args.query.strip()]
    if args.language.strip():
        q_parts.append(f"language:{args.language.strip()}")
    q_parts.append(f"pushed:>={cutoff}")

    params = {
        "q": " ".join(q_parts),
        "sort": "stars",
        "order": "desc",
        "per_page": str(max(1, min(args.top, 100))),
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)

    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        data = get_json(url, headers=headers)
    except Exception as e:
        emit("github", [], error=f"fetch failed: {e}")
        return

    hits = []
    for item in data.get("items", []):
        stars = item.get("stargazers_count", 0) or 0
        if stars < args.min_stars:
            continue
        full = (item.get("full_name") or "").lower()
        lic = item.get("license") or {}
        hits.append({
            "id": f"github:{full}",
            "title": item.get("full_name") or full,
            "url": item.get("html_url") or f"https://github.com/{full}",
            "kind": "code",
            "date": item.get("pushed_at") or item.get("updated_at") or "",
            "summary_raw": item.get("description") or "",
            "metrics": {
                "stars": stars,
                "forks": item.get("forks_count", 0) or 0,
                "issues": item.get("open_issues_count", 0) or 0,
            },
            "extra": {
                "full_name": item.get("full_name"),
                "language": item.get("language"),
                "license": lic.get("spdx_id") if lic else None,
                "topics": item.get("topics", []) or [],
            },
        })
    emit("github", hits)


if __name__ == "__main__":
    main()

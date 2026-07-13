#!/usr/bin/env python3
"""Hacker News source — recent stories by keyword (Algolia API).

CLI:
  python3 hn.py --query llm --since 7d --top 15

Stdout: standard JSON envelope (see _common.emit). kind = "discuss".
"""
import argparse
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_json, emit  # noqa: E402

ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"


def main():
    ap = argparse.ArgumentParser(description="Hacker News source for research-radar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    cutoff_unix = int(parse_since(args.since).timestamp())
    params = {
        "query": args.query,
        "tags": "story",
        "numericFilters": f"created_at_i>{cutoff_unix}",
        "hitsPerPage": str(max(1, min(args.top, 1000))),
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)

    try:
        data = get_json(url)
    except Exception as e:
        emit("hackernews", [], error=f"fetch failed: {e}")
        return

    hits = []
    for h in data.get("hits", []):
        obj_id = h.get("objectID") or ""
        link = h.get("url") or f"https://news.ycombinator.com/item?id={obj_id}"
        hits.append({
            "id": f"hn:{obj_id}",
            "title": h.get("title") or "(no title)",
            "url": link,
            "kind": "discuss",
            "date": h.get("created_at") or "",
            "summary_raw": "",
            "metrics": {
                "points": h.get("points") or 0,
                "comments": h.get("num_comments") or 0,
            },
            "extra": {"hn_id": obj_id, "author": h.get("author")},
        })
    emit("hackernews", hits)


if __name__ == "__main__":
    main()

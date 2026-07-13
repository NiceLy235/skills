#!/usr/bin/env python3
"""Lobsters source — recent stories mentioning a keyword.

CLI:
  python3 lobsters.py --query mamba --since 30d --top 15

Lobsters has no JSON keyword search, so we page through newest.json and filter
client-side (title/tags/description contains any query term AND within window).
Stdout: standard JSON envelope (see _common.emit). kind = "discuss".
"""
import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_json, emit  # noqa: E402


def _parse_dt(s):
    """Lobsters created_at '2026-07-11T00:24:30.000-05:00' -> aware datetime."""
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Lobsters source for research-radar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--pages", type=int, default=3,
                    help="newest pages to scan (~40 stories each)")
    args = ap.parse_args()

    cutoff = parse_since(args.since)
    qterms = [t.lower() for t in args.query.split() if t.strip()]

    hits = []
    fetch_err = None
    for page in range(1, args.pages + 1):
        url = "https://lobste.rs/newest.json" if page == 1 else f"https://lobste.rs/newest/page/{page}.json"
        try:
            stories = get_json(url)
        except Exception as e:
            fetch_err = f"page {page}: {e}"
            break  # later pages missing -> stop paging, keep what we have
        if not isinstance(stories, list) or not stories:
            break
        for s in stories:
            blob = " ".join([
                s.get("title", ""),
                " ".join(s.get("tags", []) or []),
                s.get("description", "") or "",
            ]).lower()
            if qterms and not any(t in blob for t in qterms):
                continue
            dt = _parse_dt(s.get("created_at", ""))
            if dt is None or dt < cutoff:
                continue
            hits.append({
                "id": f"lobsters:{s.get('short_id')}",
                "title": s.get("title") or "(no title)",
                "url": s.get("short_id_url") or s.get("url") or "",
                "kind": "discuss",
                "date": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "summary_raw": s.get("description") or "",
                "metrics": {
                    "points": s.get("score") or 0,
                    "comments": s.get("comment_count") or 0,
                },
                "extra": {"tags": s.get("tags") or [], "lobsters_id": s.get("short_id")},
            })
            if len(hits) >= args.top:
                break
        if len(hits) >= args.top:
            break
    emit("lobsters", hits, error=(fetch_err if not hits and fetch_err else None))


if __name__ == "__main__":
    main()

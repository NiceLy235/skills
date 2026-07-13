#!/usr/bin/env python3
"""DBLP source — CS publication index by keyword (JSON API).

CLI:
  python3 dblp.py --query mamba --since 30d --top 15

Stdout: standard JSON envelope (see _common.emit). kind = "paper".

Date note: DBLP only exposes a publication *year*, so --since is honored at
year granularity (keeps year >= since-year). Treats DBLP as the
"formally-published CS papers this year" angle; it complements arXiv (preprints).
When a DOI is present the hit id is `doi:<doi>` so the same paper dedupes across
DBLP + Crossref.
"""
import argparse
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_json, emit, truncate  # noqa: E402

ENDPOINT = "https://dblp.org/search/publ/api"


def _norm_authors(a):
    if isinstance(a, list):
        return [x.get("text", x) if isinstance(x, dict) else str(x) for x in a]
    if isinstance(a, dict):
        return [a.get("text", str(a))]
    if isinstance(a, str):
        return [a]
    return []


def _as_str(v):
    """DBLP fields (venue, ee, ...) can be a list or a string depending on the
    record — coerce to a single string so the contract/truncate never breaks."""
    if isinstance(v, list):
        if not v:
            return ""
        return v[0] if isinstance(v[0], str) else str(v[0])
    if isinstance(v, str):
        return v
    return "" if v is None else str(v)


def main():
    ap = argparse.ArgumentParser(description="DBLP source for research-radar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--max-fetch", type=int, default=100,
                    help="DBLP results to pull before client-side year filtering")
    args = ap.parse_args()

    min_year = parse_since(args.since).year
    params = {"q": args.query, "format": "json", "h": str(max(1, min(args.max_fetch, 1000)))}
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)

    try:
        data = get_json(url)
    except Exception as e:
        emit("dblp", [], error=f"fetch failed: {e}")
        return

    try:
        hit_list = data["result"]["hits"]["hit"]
    except (KeyError, TypeError):
        hit_list = []
    # DBLP returns a bare object (not a list) when there is exactly one hit.
    if isinstance(hit_list, dict):
        hit_list = [hit_list]

    hits = []
    for h in hit_list:
        info = h.get("info", {}) or {}
        try:
            year = int(str(info.get("year") or ""))
        except (ValueError, TypeError):
            year = None
        if year is not None and year < min_year:
            continue
        title = (info.get("title") or "").strip().rstrip(".")
        doi = (info.get("doi") or "").strip()
        venue = _as_str(info.get("venue"))
        ee = _as_str(info.get("ee")) or _as_str(info.get("url"))
        authors = _norm_authors((info.get("authors") or {}).get("author"))
        hid = f"doi:{doi.lower()}" if doi else f"dblp:{info.get('key') or h.get('@id') or title}"
        hits.append({
            "id": hid,
            "title": title or "(untitled)",
            "url": ee,
            "kind": "paper",
            "date": f"{year}-01-01" if year else "",
            "summary_raw": truncate(venue, 300),
            "metrics": {},
            "extra": {
                "year": year, "venue": venue,
                "type": info.get("type"), "doi": doi, "authors": authors,
            },
        })
        if len(hits) >= args.top:
            break
    emit("dblp", hits)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Crossref source — broad academic works by keyword, with citation counts.

CLI:
  python3 crossref.py --query "mamba selective state space" --since 30d --top 15

Stdout: standard JSON envelope (see _common.emit). kind = "paper".

popularity metric = is-referenced-by-count (citations), the thing arXiv can't
give us. Set CROSSREF_MAILTO env to join the polite pool (faster rate limits).
When a DOI is present the hit id is `doi:<doi>` so the same paper dedupes across
Crossref + DBLP. Date is year-granular (Crossref issued date-parts -> year).
"""
import argparse
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_json, emit, truncate  # noqa: E402

ENDPOINT = "https://api.crossref.org/works"
_TAG = re.compile(r"<[^>]+>")


def main():
    ap = argparse.ArgumentParser(description="Crossref source for research-radar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--mailto", default=os.environ.get("CROSSREF_MAILTO", "research-radar@local"))
    args = ap.parse_args()

    min_year = parse_since(args.since).year
    # over-fetch then client-filter by year (Crossref relevance ≠ recency)
    params = {
        "query": args.query,
        "rows": str(max(1, min(args.top * 4, 100))),
        "select": "DOI,URL,title,issued,container-title,is-referenced-by-count,type,abstract,author",
        "mailto": args.mailto,
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": f"research-radar/1.0 (mailto:{args.mailto})"}

    try:
        data = get_json(url, headers=headers)
    except Exception as e:
        emit("crossref", [], error=f"fetch failed: {e}")
        return

    items = data.get("message", {}).get("items", []) or []
    kept = []
    for it in items:
        year = None
        try:
            year = (it.get("issued") or {}).get("date-parts", [[None]])[0][0]
        except (IndexError, TypeError):
            pass
        if year and year < min_year:
            continue
        title = (it.get("title") or [""])[0] or "(untitled)"
        doi = (it.get("DOI") or "").strip()
        link = it.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        cited = it.get("is-referenced-by-count") or 0
        venue = (it.get("container-title") or [""])[0] or ""
        authors = []
        for a in (it.get("author") or []):
            name = " ".join(filter(None, [a.get("given"), a.get("family")]))
            if name:
                authors.append(name)
        abstract = _TAG.sub("", it.get("abstract") or "")
        hid = f"doi:{doi.lower()}" if doi else f"crossref:{title}"
        kept.append({
            "id": hid,
            "title": title,
            "url": link,
            "kind": "paper",
            "date": f"{year}-01-01" if year else "",
            "summary_raw": truncate(f"{venue}. {abstract}".strip(" ."), 600),
            "metrics": {"citations": cited},
            "extra": {
                "doi": doi, "year": year, "venue": venue,
                "type": it.get("type"), "authors": authors,
            },
        })
        if len(kept) >= args.top:
            break
    emit("crossref", kept)


if __name__ == "__main__":
    main()

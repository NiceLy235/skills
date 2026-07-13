#!/usr/bin/env python3
"""arXiv source — recent papers by keyword + arXiv category filter.

CLI:
  python3 arxiv.py --query "mamba state space" --since 30d --top 15 --categories cs.AI,cs.CL

Stdout: standard JSON envelope (see _common.emit). kind = "paper".

Responses are cached to disk (--cache-dir, default
~/.cache/research-radar/arxiv) for CACHE_TTL seconds so repeated runs of the
same query in a session don't re-hit arXiv (and its ~1 req/3s/IP rate limit).
Use --no-cache to bypass. Cache hits are logged to stderr; stdout stays pure
JSON for the orchestrator.
"""
import argparse
import hashlib
import os
import shlex
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_text, emit, utcnow, truncate  # noqa: E402

ATOM = "{http://www.w3.org/2005/Atom}"
# https directly: the http endpoint 301-redirects to https, and following that
# redirect doubles our requests to arXiv (which rate-limits ~1 req/3s per IP).
ENDPOINT = "https://export.arxiv.org/api/query"

CACHE_DIR_DEFAULT = Path.home() / ".cache" / "research-radar" / "arxiv"
CACHE_TTL = 6 * 3600  # 6h: arXiv's index doesn't move fast; avoids repeat 429s


def build_search_query(query, categories):
    """Turn a free-text query into an arXiv search_query.

    Each whitespace token becomes all:<token> joined by AND (precision-first).
    Categories become a (cat:X OR cat:Y) clause. shlex keeps quoted phrases.
    """
    terms = [f"all:{t}" for t in shlex.split(query)]
    parts = []
    if categories:
        parts.append("(" + " OR ".join(f"cat:{c}" for c in categories) + ")")
    core = " AND ".join(terms) if terms else ""
    if core:
        parts.append("(" + core + ")")
    return " AND ".join(parts)


def _cache_key(args):
    """Stable key for the on-disk cache: the exact arguments that shape the feed."""
    raw = f"{args.query}|{args.since}|{args.top}|{args.categories}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser(description="arXiv source for research-radar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--categories", default="",
                    help="comma-separated arXiv categories, e.g. cs.AI,cs.CL")
    ap.add_argument("--cache-dir", default=str(CACHE_DIR_DEFAULT),
                    help="response cache dir (set with --no-cache to disable)")
    ap.add_argument("--no-cache", action="store_true",
                    help="bypass the response cache")
    args = ap.parse_args()

    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    cutoff = parse_since(args.since)
    begin = cutoff.strftime("%Y%m%d%H%M")
    end = utcnow().strftime("%Y%m%d%H%M")

    base = build_search_query(args.query, cats)
    date_filter = f"submittedDate:[{begin} TO {end}]"
    search_query = f"{base} AND {date_filter}" if base else date_filter

    params = {
        "search_query": search_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max(1, args.top)),
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)

    text = _load_feed(url, args)

    try:
        hits = parse_feed(text)
    except Exception as e:
        emit("arxiv", [], error=f"parse failed: {e}")
        return
    emit("arxiv", hits)


def _load_feed(url, args):
    """Return the Atom feed text, served from cache when fresh, else fetched.

    On a fetch failure we emit the error envelope and exit (stdout already
    holds valid JSON). A stale/corrupt cache entry is silently ignored and
    re-fetched; a cache write failure is ignored (cache is best-effort).
    """
    cache_path = None
    if not args.no_cache:
        cache_path = Path(args.cache_dir) / f"{_cache_key(args)}.xml"

    if cache_path is not None:
        try:
            if cache_path.exists() and (time.time() - cache_path.stat().st_mtime) < CACHE_TTL:
                print(f"[arxiv] cache hit {cache_path.name}", file=sys.stderr)
                return cache_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass  # unreadable/corrupt → fall through to a live fetch

    try:
        text = get_text(url, timeout=40, retries=3)
    except Exception as e:
        emit("arxiv", [], error=f"fetch failed: {e}")
        sys.exit(0)

    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(text, encoding="utf-8")
        except OSError:
            pass
    return text


def parse_feed(text):
    """Parse an arXiv Atom response into a list of contract hits.

    Separated from fetch so the XML contract can be unit-tested offline.
    Strips version suffixes (2401.17775v1 -> 2401.17775) for stable dedupe ids.
    """
    root = ET.fromstring(text)
    hits = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = (entry.findtext(f"{ATOM}id") or "").strip()
        arxiv_id = raw_id.split("/abs/")[-1]
        head, _, tail = arxiv_id.rpartition("v")
        if tail.isdigit():
            arxiv_id = head
        title = " ".join((entry.findtext(f"{ATOM}title") or "").split())
        summary = " ".join((entry.findtext(f"{ATOM}summary") or "").split())
        published = (entry.findtext(f"{ATOM}published") or "").strip()
        authors = [a for a in (e.findtext(f"{ATOM}name") for e in entry.findall(f"{ATOM}author")) if a]
        categories = [c.get("term") for c in entry.findall(f"{ATOM}category") if c.get("term")]
        hits.append({
            "id": f"arxiv:{arxiv_id}",
            "title": title or arxiv_id,
            "url": f"http://arxiv.org/abs/{arxiv_id}",
            "kind": "paper",
            "date": published,
            "summary_raw": truncate(summary),
            "metrics": {},
            "extra": {"arxiv_id": arxiv_id, "authors": authors, "categories": categories},
        })
    return hits


if __name__ == "__main__":
    main()

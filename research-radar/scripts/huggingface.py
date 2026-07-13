#!/usr/bin/env python3
"""Hugging Face source — popular models by keyword.

CLI:
  python3 huggingface.py --query mamba --since 30d --top 15

Stdout: standard JSON envelope (see _common.emit). kind = "model".

Note: the HF public API has no server-side date filter for /api/models, so the
--since window is applied client-side against lastModified. That means very old
but famous models are excluded when the window is short — expected for a
"what moved recently" radar.

If huggingface.co is unreachable (firewall TCP-drop in some sandboxes), the
fetch transparently retries once against the hf-mirror.com mirror. Hit URLs
always point at the official site regardless of where the data came from. Set
HF_ENDPOINT to force a specific base (disables the mirror fallback).
"""
import argparse
import os
import sys
import urllib.error
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_json, emit  # noqa: E402

OFFICIAL = "https://huggingface.co/api/models"
MIRROR = "https://hf-mirror.com/api/models"
# HF_ENDPOINT overrides the base; when unset we use official + mirror fallback.
BASE = (os.environ.get("HF_ENDPOINT") or OFFICIAL).rstrip("/")
# The official endpoint is probed once with a short timeout so a firewalled
# host (TCP SYN dropped → connect hangs) gives up in seconds and the mirror
# takes over, instead of burning 20s × retries before falling back.
_PRIMARY_TIMEOUT = 6
_PRIMARY_RETRIES = 0


def _is_connection_error(e):
    """True when the failure is transport-level (no server response reached).

    urllib.error.HTTPError is a subclass of URLError but means the server *did*
    respond (4xx/5xx) — that's not a connection failure, so the mirror won't help
    and we don't fall back. DNS errors / refused / TCP-drop / timeout are.
    """
    if isinstance(e, urllib.error.HTTPError):
        return False
    return isinstance(e, (urllib.error.URLError, TimeoutError, OSError))


def _fetch_with_fallback(primary, mirror, qs):
    """Fetch `primary?qs`; on a connection error retry once at `mirror?qs`.

    Mirror fallback only kicks in when the primary is the official endpoint
    (i.e. the caller hasn't overridden HF_ENDPOINT) and the failure is
    transport-level. Returns parsed JSON. Raises if both fail (or if the
    primary failure isn't a connection error) — the caller emits the envelope.
    """
    use_mirror = primary.rstrip("/") == OFFICIAL
    try:
        return get_json(primary + "?" + qs,
                        timeout=_PRIMARY_TIMEOUT, retries=_PRIMARY_RETRIES)
    except Exception as primary_err:
        if not (use_mirror and _is_connection_error(primary_err)):
            raise
        try:
            return get_json(mirror + "?" + qs)
        except Exception as mirror_err:
            raise Exception(
                f"official ({primary_err}) and mirror ({mirror_err}) both failed"
            ) from mirror_err


def main():
    ap = argparse.ArgumentParser(description="Hugging Face source for research-radar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    cutoff_iso = parse_since(args.since).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    params = {
        "search": args.query,
        "sort": "downloads",
        "direction": "-1",
        "limit": str(max(1, min(args.top, 100))),
    }
    qs = urllib.parse.urlencode(params)
    try:
        data = _fetch_with_fallback(BASE, MIRROR, qs)
    except Exception as e:
        emit("huggingface", [], error=f"fetch failed: {e}")
        return

    hits = []
    for m in data:
        mid = m.get("id") or m.get("modelId") or ""
        last = m.get("lastModified") or ""
        if last and last < cutoff_iso:
            continue
        tags = m.get("tags") or []
        pipe = m.get("pipeline_tag") or ""
        hits.append({
            "id": f"hf:{mid}",
            "title": mid,
            "url": f"https://huggingface.co/{mid}",
            "kind": "model",
            "date": last,
            "summary_raw": pipe,
            "metrics": {
                "downloads": m.get("downloads") or 0,
                "likes": m.get("likes") or 0,
            },
            "extra": {
                "pipeline_tag": pipe,
                "tags": tags[:10],
                "author": m.get("author"),
            },
        })
    emit("huggingface", hits)


if __name__ == "__main__":
    main()

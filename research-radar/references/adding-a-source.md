# Adding / removing / wiring a source

> 中文版见 `adding-a-source.zh.md`。

`sources.yaml` is the single source of truth. There are three source types.
Adding one is always "add one row to `sources.yaml`" — the only question is
whether you also need to write a fetcher.

## Remove (soft-delete) a source

Set `enabled: false` on its row. It's skipped at runtime but the config is kept
for later. (Deleting the row works too.)

## Type 1 — `script`: a new API source

For any source with a public HTTP API (JSON or XML), add a tiny pure-stdlib
fetcher and one yaml row.

### Step 1 — write `scripts/<name>.py`

Use this contract template. It must:
- take `--query`, `--since`, `--top` (plus any source-specific flags),
- fetch via `_common.get_json` / `get_text` (they retry transient errors),
- emit ONE JSON object on stdout via `_common.emit`,
- **never** crash on fetch/parse failure — emit the error envelope instead.

```python
#!/usr/bin/env python3
import argparse, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import parse_since, get_json, emit  # noqa: E402

ENDPOINT = "https://example.com/api/search"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", default="30d")
    ap.add_argument("--top", type=int, default=15)
    # add source-specific flags here, e.g. --categories
    args = ap.parse_args()

    cutoff = parse_since(args.since)
    params = {"q": args.query, "limit": str(args.top)}   # add date filter
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    try:
        data = get_json(url)
    except Exception as e:
        emit("<name>", [], error=f"fetch failed: {e}")
        return

    hits = []
    for item in data.get("items", []):
        hits.append({
            "id":          f"<name>:<stable-key>",   # dedupe key
            "title":       item.get("title", ""),
            "url":         item.get("url", ""),
            "kind":        "discuss",                 # paper|code|discuss|model
            "date":        item.get("date", ""),      # ISO 8601
            "summary_raw": item.get("summary", ""),
            "metrics":     {"score": item.get("score", 0)},
            "extra":       {},                        # anything else
        })
    emit("<name>", hits)

if __name__ == "__main__":
    main()
```

Required hit keys (all of them): `id, title, url, kind, date, summary_raw,
metrics, extra`. Empty values are fine; missing keys break the contract.

### Step 2 — add the yaml row

```yaml
- name: <name>
  type: script
  enabled: true
  script: <name>            # basename of scripts/<name>.py; omit if == name
  weight: 0.8               # 0..1 trust weight
  # source-specific config goes here, e.g.:
  categories: [cs.AI]
```

### Step 3 — teach the orchestrator the flag mapping

If your source has config keys beyond query/since/top, add a row to the
"config key → CLI flag" table in SKILL.md so the orchestrator passes them.
(Or just hard-code sensible defaults inside the script.)

### Step 4 — verify

```bash
python3 scripts/<name>.py --query "<test>" --since 30d --top 5 | jq '.hits[0]'
```
Confirm `.hits[0]` has all contract keys.

## Type 2 — `web`: a crawl / social source (no API)

For sites with no usable public API (知乎, X/Twitter, blogs, …) we don't write a
script — the orchestrator does `WebSearch "<query> site:<site>"` then fetches the
top results with `mcp__web_reader__webReader` and extracts fields by reading.

Add one row:

```yaml
- name: zhihu
  type: web
  enabled: true
  site: zhihu.com
  weight: 0.5
```

That's it. The orchestrator handles search + fetch + extraction for `web`
sources. If a site blocks crawling (common for X), the run marks it degraded in
the digest footer and continues — no code change needed.

## Type 3 — `skill`: wire another skill as a deep source

Any other skill becomes a source — most usefully `deep-research` for verified,
cited deep-dives. Add one row:

```yaml
- name: deep_research
  type: skill
  enabled: false          # opt-in per run via the `deep` argument
  skill: deep-research    # the Skill name to invoke
  weight: 0.9
```

At runtime (only when `deep` is requested AND the source is enabled), the
orchestrator:
1. distills the top hits into a focused research question,
2. calls the skill via the Skill tool,
3. appends the returned cited markdown under "🔬 深度报告".

The `skill:` value must match a skill available in your runtime. The interface
is intentionally simple: text question in, markdown report out — so most
research-style skills plug in with no glue code.

## Worked examples: gotchas from the built-in sources

Three real sources, three different non-obvious traps. Read the named script for
a working reference.

**Cross-source dedupe tip:** when two sources expose a DOI for the same paper,
use `doi:<doi>` as the `id` in *both* so they merge on dedupe (`dblp.py` and
`crossref.py` both do this — without it the same paper shows up twice).

### DBLP — one match comes back as an object, not a list
`result.hits.hit` is a **list** when there are many matches, but a **bare
object** when there is exactly one. Iterating a dict yields its string keys,
not hits:

```python
hit_list = data["result"]["hits"]["hit"]
if isinstance(hit_list, dict):      # exactly one match -> dict, not [dict]
    hit_list = [hit_list]
```

DBLP also exposes only a publication **year**, so honor `--since` at year
granularity and set `date` to `"{year}-01-01"`.

**`venue` / `ee` can be a list, not just a string** — some records return
`"venue": ["Neurocomputing", "..."]`. Passing that straight to `truncate()`
crashes (`'list' object has no attribute 'strip'`). Coerce with a helper
(`dblp.py::_as_str`) or rely on the hardened `_common.truncate`.

### Crossref — JATS abstracts, uppercase field names, year-granular dates
- **Casing is non-standard:** `.DOI`, `.URL`, `.["is-referenced-by-count"]`,
  `.issued."date-parts"[0][0]`. Lowercase `.doi` / `.url` silently return `null`.
- **Abstracts arrive as JATS XML** (`<jats:p>…</jats:p>`); strip tags:
  `re.sub(r"<[^>]+>", "", abstract)`.
- **Relevance ≠ recency:** over-fetch (`rows = top * 4`) then client-filter by
  year — Crossref's top results are often old.
- Set `mailto` (query param or `CROSSREF_MAILTO` env) to join the polite pool
  (higher rate limits).

### Lobsters — no JSON keyword search, so page + filter client-side
There is no `search.json?q=` endpoint (it returns `400 Unpermitted query`).
Page through `newest.json` and `/newest/page/{n}.json` (~40 stories each) and
filter client-side: any query term in title/tags/description **and** `created_at`
within the window. The timestamp is tz-aware (`2026-07-11T00:24:30.000-05:00`) —
parse with `datetime.fromisoformat`. Stop paging at `top` or on an empty page;
treat a later-page 404 as **end-of-data, not an error** (don't poison the run).

## Checklist after any change

- [ ] `sources.yaml` parses: `python3 -c "import yaml; yaml.safe_load(open('sources.yaml'))"`
  (or any YAML linter).
- [ ] script sources: `--query ... | jq '.hits[0]'` has all 8 contract keys.
- [ ] `name` is unique across all sources (it's the dedupe/footing identity).

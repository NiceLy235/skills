# Scoring

> 中文版见 `scoring.zh.md`。

Every normalized hit gets a single `score` in `[0, 1]`. The composite blends four
signals, each normalized to `[0, 1]` first:

```
score = 0.30 * recency      (how fresh within the window)
      + 0.30 * popularity   (how much attention it's getting)
      + 0.25 * relevance    (does it actually match the keywords)
      + 0.15 * source_weight(trust weight from sources.yaml)
```

These weights are the defaults; the orchestrator (you, Claude) applies them when
ranking. Tweak the blend here if a signal matters more for a run.

## Component definitions

### recency — 0.30
Freshness relative to the query window. Let `cutoff = parse_since(since)` and
`window = now - cutoff` (in days). For a hit dated `d`:

- `age = (now - d).days`
- `recency = clamp(1 - age / window, 0, 1)` when `window > 0`, else `1.0`.

So something published *today* scores 1.0; something at the very edge of the
window scores ~0. Hits older than the window (a few APIs leak them) score 0 and
should be dropped. If `date` is missing/unknown, use `0.5` (neutral) — do not
punish for a missing date.

### popularity — 0.30
Source-specific attention metric, log-scaled so one viral repo doesn't dominate:

| kind / source | raw metric                   |
|---------------|------------------------------|
| code (github) | `stargazers_count`           |
| discuss (hn)  | `points` (fall back to `comments`) |
| discuss (reddit) | `score` (fall back to `comments`) |
| model (hf)    | `downloads` (fall back to `likes`) |
| paper (arxiv) | none from API → `0.5` neutral |

```
popularity = log10(raw + 10) / log10(BUCKET + 10)
```
`BUCKET` is a per-kind scale ceiling that maps "a lot" to ~1.0. Defaults:

| kind   | BUCKET |
|--------|--------|
| code   | 10_000 (stars)  |
| model  | 1_000_000 (downloads) |
| discuss| 1_000 (points/score) |
| paper  | n/a (neutral 0.5) |

Clamp to `[0, 1]`. The point is rank order, not absolute values.

### relevance — 0.25
Keyword match against `title + summary_raw` (case-insensitive). Using the
*expanded* keyword set (synonyms + translations from pipeline step 3):

- All original keywords present → `1.0`
- Partial: `fraction_of_keywords_present` (count present / count total).
- Exclude terms present → cap relevance at `0.1` (effectively sinks it).

This is a cheap signal (we already have the text); the real semantic judgment
happens in the Summarize step's `值得看` verdict.

### source_weight — 0.15
Directly the `weight` field from `sources.yaml` (already 0..1). Reflects how
much you trust the source: arxiv/github 1.0, hn 0.7, hf 0.8, reddit 0.6,
social/crawl 0.5, deep-research 0.9.

## How it's used

1. Compute `score` for every deduped hit.
2. Sort the combined list descending by `score`.
3. Take the top `top_per_source * 1.5` (rounded) as the digest's ranked list,
   capped by a global token budget (see SKILL.md "Error handling & budget").
4. Render the "📊 综合榜单" table from this ranked list, then split into
   kind-sections (📄 论文 / 💻 代码 / 📣 社区讨论) for the detail view.

The `★ <score>` shown next to each item is `round(score, 2)`.

# Arguments

> 中文版见 `arguments.zh.md`。

`research-radar` is driven by keyword arguments on the slash invocation:

```
/research-radar keywords="..." since=30d sources=all top=15 exclude="..." deep
```

All arguments are optional except `keywords`.

## `keywords` (required)
The topic to track. One or more terms, space-separated. Quote phrases.

- `keywords="mamba state space"` — three terms (AND-matched inside each source).
- `keywords="状态空间模型 Mamba"` — mixed language; the pipeline auto-expands
  both directions (see pipeline step 3) so English-heavy sources (arxiv, github)
  and Chinese-heavy sources (zhihu) both get good queries.

Used as the seed for keyword expansion, relevance scoring, and the digest title.

## `since` (default: `30d`)
Time window. The cutoff is computed from "now" backwards. Accepted forms:

| Value        | Meaning                              |
|--------------|--------------------------------------|
| `Nd`         | last N days (`7d`, `30d`, `90d`)      |
| `YYYY-MM`    | since the first day of that month    |
| `YYYY-MM-DD` | since that exact date                 |

Examples: `since=7d`, `since=2024-06`, `since=2024-06-11`.
Per-source behavior of the window:

- **arxiv** — `submittedDate:[BEGIN TO END]` server-side.
- **github** — `pushed:>=YYYY-MM-DD` server-side.
- **hackernews** — `created_at_i > <unix>` server-side.
- **reddit** — mapped to the closest `t=` window (day/week/month/year/all).
- **huggingface** — applied client-side against `lastModified`.
- **web / skill** — passed through as context; WebSearch itself is not strictly
  date-bounded, so very recent intent is best expressed with `Nd`.

## `sources` (default: `all`)
Comma-separated list of source `name`s to **override** the enabled set. With
`all` (or omitted), every `enabled: true` source in `sources.yaml` runs.

- `sources=arxiv,github` — just those two.
- `sources=all` — everything enabled.
- A name not in `sources.yaml` → reported as skipped in the footer.

## `top` (default: from `sources.yaml` `top_per_source`)
Max hits to take **per source** before dedupe/score. Raising it widens recall at
the cost of tokens and time. After scoring, the digest keeps roughly
`top * 1.5` items total (see "Error handling & budget" in SKILL.md).

## `exclude` (default: none)
Comma-separated terms to demote. Any hit whose title/summary contains an exclude
term gets its relevance capped at 0.1 (sinks it in the ranked list). Use to cut
noise: `exclude="survey,reading list,awesome"`.

## `deep` (flag, default: off)
Enables `skill`-type sources (typically `deep_research`). Adds a "🔬 深度报告"
section to the digest with a cited deep-dive. Costs significant time/tokens —
leave off for quick scans.

## Examples

```
# quick scan, last week, code + papers only
/research-radar keywords="Mamba SSM" since=7d sources=arxiv,github top=10

# full radar, 30 days, drop listicles
/research-radar keywords="状态空间模型 Mamba" since=30d top=10 exclude="awesome,survey"

# one topic, deep verified report appended
/research-radar keywords="retrieval augmented generation 2024" since=2024-01 deep
```

---
name: research-radar
description: Use when the user wants a frontier scan of a topic — latest papers, trending repos/code, new models, and community discussion (Hacker News, Reddit, 知乎, X) filtered by keyword and time window, delivered as ONE deduped, scored, summarized Markdown digest. Triggers 前沿论文, 最新研究, 调研, 跟踪/追踪课题, paper/arxiv survey, github 调研, track a topic, what's new in <X>. Sources are add/removable in sources.yaml; other skills (e.g. deep-research) can be wired in as deep dig sources.
argument-hint: 'keywords="..." since=30d sources=all top=15 exclude="..." deep'
allowed-tools: Bash, WebSearch, mcp__web_reader__webReader, Read, Write, Edit, Skill, Task
---

# research-radar

> 中文版见 `SKILL.zh.md`（README 与 references 同样有 `.zh.md`）。

Produce a single Markdown **digest** surveying a topic across many sources:
papers, code, models, and community talk — deduped, scored, and summarized.

## When to use
- "帮我调研 / track 一下 <topic> 最近有什么进展"
- "最新论文 / 前沿研究 on <X>", "github 上有什么新项目"
- "what's new in <X> this month", "survey the frontier of <X>"
- Want a **cross-source** overview (not just one site, not just one deep-dive).

Do NOT use for: a single deep fact-checked report on one question (that's
`deep-research`), or a one-off web lookup (just WebSearch).

## Arguments
See `references/arguments.md` for full detail.

| arg | default | meaning |
|-----|---------|---------|
| `keywords` | required | topic terms (space-separated; quote phrases) |
| `since` | `30d` | `Nd` / `YYYY-MM` / `YYYY-MM-DD` |
| `sources` | `all` | comma list to override enabled set, or `all` |
| `top` | `top_per_source` (yaml) | max hits **per source** before dedupe |
| `exclude` | none | terms to demote (relevance→0.1) |
| `deep` | off | enable `skill`-type sources (deep-research) |

## Pipeline (execute in order)

**1. Parse args.** Resolve `keywords, since, sources, top, exclude, deep`. Pull
`top` default and `since` default from `sources.yaml` `defaults:` when unset.

**2. Read `sources.yaml`.** Select the run set: if `sources != all`, keep only
named + enabled sources; else all `enabled: true`. Note each source's `type`
(`script` / `web` / `skill`) and `weight`.

**3. Expand keywords.** Generate a small expanded set: synonyms + EN⇄ZH
translation (papers/repos are mostly English; zhihu/社区 mostly Chinese). Keep
the original as the primary query. This expanded set is used for (a) source
queries — English form for arxiv/github/hn/hf, original/mixed for reddit/web —
and (b) relevance scoring.

**4. Fetch each source** (see "Source types" below). Sources are independent —
for large runs, fetch them concurrently with `superpowers:dispatching-parallel-agents`
or several Bash calls in one message. **Proxy:** if `sources.yaml` sets a
non-empty `defaults.proxy` (e.g. `http://127.0.0.1:7897`), prefix each `script`
invocation with `http_proxy=<p> https_proxy=<p>` — urllib's default opener honors
those lowercase env vars, so this is how a non-interactive Claude Code Bash reaches
arxiv/reddit/HF through a proxy without depending on a shell alias. Leave `proxy`
blank/unset for direct connections.

**5. Normalize** every hit to the contract:
`{id, title, url, kind(paper|code|discuss|model), date(ISO), summary_raw, metrics{}, extra{}}`.

**6. Dedupe** by canonical key:
- paper → arxiv id (version-stripped) / DOI
- code → `owner/repo` lowercased
- model → HF model id
- discuss / web → normalized URL (drop query string + fragment, strip trailing
  slash, lowercase host)
On collision: keep the higher-scored hit, union `metrics`/`sources` into `extra`.

**7. Score** each hit (`references/scoring.md`):
`0.30·recency + 0.30·popularity + 0.25·relevance + 0.15·source_weight`.
Apply `exclude`: any hit whose title/summary contains an exclude term → cap
relevance at 0.1. Drop hits dated before the window.

**8. Summarize** the top-ranked items: read `summary_raw` (abstract / readme /
selftext) and produce, per item:
- 1–2 sentence **Chinese** summary (honor `summary_lang`).
- `值得看: yes / maybe / no` + one-sentence reason.
- For code: also judge 维护中? 有文档? 有测试? license?
- For models: note downloads/likes and `pipeline_tag` if useful.

**9. Render** the digest (see "Digest output") and Write it to
`/home/nice/ly/research/digests/YYYY-MM-DD-<topic-slug>.md`
(create the dir if missing; `<topic-slug>` = lowercase, non-alnum → `-`,
truncated ~40 chars). Return the path to the user.

## Source types — how to run each

### `script` (built-in fetcher)
Run `python3 scripts/<script>.py --query "<q>" --since <since> --top <top> <extra>`.
It prints one JSON object: `{"source", "count", "hits":[...], "error"?}`.
Parse stdout with `jq` (e.g. `... | jq '.hits'`). An `error` field or `count:0`
means the source yielded nothing — record it for the footer, keep going.
**With a proxy**, run `http_proxy=<p> https_proxy=<p> python3 scripts/<script>.py …`
(see "Unlocking blocked sources" below for the three ways to enable it).

Config key → CLI flag map (yaml key becomes the flag):

| source (`name`) | `script` | extra flags from yaml |
|-----------------|----------|-----------------------|
| arxiv | `arxiv` | `categories` → `--categories <csv>` |
| github | `github` | `min_stars` → `--min-stars <n>`, `language` → `--language <x>` |
| hackernews | `hn` | (none) |
| reddit | `reddit` | `subreddits` → `--subreddits <csv>` |
| huggingface | `huggingface` | (none) |
| dblp | `dblp` | `max_fetch` → `--max-fetch <n>` |
| crossref | `crossref` | `mailto` → `--mailto <email>` (optional; or `CROSSREF_MAILTO` env) |
| lobsters | `lobsters` | `pages` → `--pages <n>` |

Intrinsic script flags (not yaml-driven): arxiv caches responses for ~6h
(`--cache-dir`, default `~/.cache/research-radar/arxiv`; `--no-cache` to bypass).
GitHub honors `GITHUB_TOKEN` env (raises rate limit 60→5000/hr).

### `web` (crawl / social, no API — zhihu, X)
For each enabled `web` source:
1. `WebSearch "<expanded query> site:<site>"` → take the top `top` result URLs.
2. For each URL, `mcp__web_reader__webReader` and read item `[0]`. It returns
   **structured fields alongside the body** — map them into the contract rather
   than relying on raw text:
   - `title`        ← `headline` / `og:title` / `title`
   - `date`         ← `publishedTime` / `datePublished` (ISO; day-precise → feeds recency)
   - `metrics`      ← `{comments: commentCount}` (add `likes`/`votes` if present)
   - `summary_raw`  ← `description` + first 1–2 paragraphs of `content`
   - `extra`        ← `{author: name, site}`
3. Build the contract hit: `kind: discuss`, `id` = normalized URL (lowercase host
   + path, drop query/fragment/trailing slash). Missing fields stay empty — don't
   guess (empty `date` → neutral recency 0.5, not a penalty).
If a site blocks crawling (X often does) or webReader returns nothing usable,
mark the source **degraded** — note it in the footer, emit zero hits, do not fail.

### `skill` (delegate — only when `deep` set)
For each enabled `skill` source:
1. Distill the run's top hits + keywords into ONE focused research question.
2. Invoke via the **Skill** tool (`skill: <name>`, e.g. `deep-research`).
3. Take the returned cited markdown → append under "🔬 深度报告".

## Digest output

```markdown
# 前沿调研：<topic>  (YYYY-MM-DD · 最近 N 天)
> 关键词 … | 源: arxiv, github, … | 命中 <N> → 去重 <M>

## 📊 综合榜单
| # | 类型 | 标题 | 源 | 日期 | 热度 | 值得看 | 一句话 |
|---|------|------|----|------|------|--------|--------|
| 1 | …    | [..](url) | github | … | ★4.7k | yes | … |

## 📄 论文
### [标题](url)  ★<score>
- arxiv:<id> · 类别 · <date>
- 摘要(中): …
- 判断: 值得看 — <reason>

## 💻 代码
### [owner/repo](url)  ★<stars>  ⚡<updated>
- 中文简介 …
- 维护? 文档? 测试? license?

## 📣 社区讨论   (Hacker News / Reddit / 知乎 / X)
### [标题](url) — 源 · <date> · ▲<points> 💬<comments>
- 中文要点 …

## 🔬 深度报告   (仅 --deep)
<deep-research cited markdown>

> ⚠️ 跳过/降级的源: x_twitter (抓取受限), reddit (网络不可达) …
```

The ranked table is the headline; the kind-sections give the detail. Footer
**always** lists skipped/degraded sources with the reason.

## Config: managing sources
All add/remove happens in **`sources.yaml`** (see `references/adding-a-source.md`):
- Add an API source → write `scripts/<x>.py` (contract template in the ref) + one
  `type: script` row.
- Add a crawl/social source → one `type: web` row with `site:`.
- Wire any skill as a deep source → one `type: skill` row with `skill:`.
- Remove → `enabled: false` (or delete the row).

## Error handling & budget
- **One source failing never aborts the run.** A `script` that errors emits an
  error envelope; a `web`/`skill` source that's blocked is marked degraded. All
  such sources appear in the digest footer with a reason.
- **Token budget:** `top` caps per-source volume; after scoring keep ~`top*1.5`
  items total and never more than ~50. Summarize only the kept items.
- **Network limits:** GitHub works with no token (≤60 req/hr). Hugging Face
  auto-falls back to `hf-mirror.com` if the official site is unreachable.
  arXiv retries 429s gently (honors `Retry-After`) and caches responses ~6h.
  Reddit needs a proxy here AND may still TLS-block the proxy's IP. The error
  envelope + footer make any remaining block visible, not fatal.

## Unlocking blocked sources (arxiv / reddit / huggingface)
Some sandboxes block or rate-limit these. They're handled with zero new deps:
- **Hugging Face — mirror (automatic, zero config):** if `huggingface.co` is
  unreachable, `huggingface.py` retries once against `hf-mirror.com`. Hit URLs
  still point at the official site. Override with the `HF_ENDPOINT` env var.
- **arxiv / reddit — proxy (optional):** set `defaults.proxy` in `sources.yaml`
  (e.g. `http://127.0.0.1:7897`) and the orchestrator prefixes each script run
  with `http_proxy=<p> https_proxy=<p>`. urllib honors those, so no code change.
  Three equivalent ways to enable a proxy:
  1. `sources.yaml` `defaults.proxy` — recommended; per-run, only `script` sources.
  2. Claude Code `settings.json` `env` block — global, every command.
  3. `export http_proxy=… https_proxy=…` in the terminal before starting Claude Code.
- **Reddit IP-block fallback:** Reddit aggressively blocks proxy/VPN IPs. If
  `reddit.py` still errors *through* a proxy — `HTTP 403: Blocked` or
  `SSL unexpected eof` (Reddit alternates between a 403 block page and killing
  the TLS handshake) — that proxy's IP is reddit-blacklisted. Options: a
  **residential proxy**, Reddit's **OAuth API** (set credentials in env), or
  enable the **`reddit_web`** source — it routes `<q> site:reddit.com` through
  WebSearch (the search engine's own infra), returning post titles + snippets
  without ever connecting to Reddit.

## References
- `references/arguments.md` — full argument docs + examples
- `references/scoring.md` — score formula & component definitions
- `references/adding-a-source.md` — add/remove/wire a source, script contract template
- `sources.yaml` — the source registry (edit this)

# research-radar

> 中文版见 `README.zh.md`（SKILL 与 references 同样有 `.zh.md`）。

A skill that surveys the frontier of a topic across many sources and returns one
deduped, scored, summarized Markdown **digest**.

Point it at a topic + time window; it pulls from papers (arXiv), code (GitHub),
models (Hugging Face), and community discussion (Hacker News, Reddit, 知乎, X),
merges duplicates, ranks by a blended score, summarizes each item in Chinese, and
writes a digest you can skim in a minute.

```
/research-radar keywords="状态空间模型 Mamba" since=30d top=10
```

## Install (make `/research-radar` callable)

Claude Code auto-discovers skills only from `~/.claude/skills/` (user, global)
or `<project>/.claude/skills/` (project-scoped). This repo isn't in those paths
by default, so register `research-radar` with a **symlink** — the source stays
in your clone, so `git pull` updates flow straight through with no re-register:

```bash
# 1. clone anywhere you keep repos
git clone https://github.com/NiceLy235/skills.git ~/skills
# 2. symlink the skill into Claude Code's discovery path
mkdir -p ~/.claude/skills
ln -s ~/skills/research-radar ~/.claude/skills/research-radar
# 3. restart Claude Code (skills are indexed at session start)
```

> If you already have the source checked out somewhere else (you're the author,
> or cloned to a different path), replace `~/skills/research-radar` above with
> that absolute path — same mechanism.

Then **restart Claude Code** (a running session often picks up the new symlink
on rescan, but a restart is reliable). After that:

- `/research-radar keywords="..." since=30d top=10` — explicit call, or
- a matching request ("帮我调研一下 Mamba 最近有什么进展" / "survey what's new in Mamba") auto-triggers it.

Verify it's loaded: it shows up in `/help` of a fresh session. Editing files
under the cloned `research-radar/` takes effect immediately via the symlink —
**no re-register needed**; `git pull` to get updates.

## Docs & language / 文档与语言

All docs exist in **English** and **中文** (`.zh.md`). Sources are managed in
[`sources.yaml`](sources.yaml).

| 文档 Doc | English | 中文 |
|----------|---------|------|
| Skill (orchestration) | [SKILL.md](SKILL.md) | [SKILL.zh.md](SKILL.zh.md) |
| README (this file) | [README.md](README.md) | [README.zh.md](README.zh.md) |
| Arguments | [arguments.md](references/arguments.md) | [arguments.zh.md](references/arguments.zh.md) |
| Scoring | [scoring.md](references/scoring.md) | [scoring.zh.md](references/scoring.zh.md) |
| Adding a source | [adding-a-source.md](references/adding-a-source.md) | [adding-a-source.zh.md](references/adding-a-source.zh.md) |

## Layout

```
research-radar/
  SKILL.md                 # orchestration recipe Claude follows
  sources.yaml             # ★ the source registry — add/remove/wire sources here
  scripts/
    _common.py             # shared helpers: parse_since, emit, fetch+retry, contract
    arxiv.py  github.py  hn.py  reddit.py  huggingface.py   # one per script source
  references/
    arguments.md           # full arg docs + examples
    scoring.md             # score formula & components
    adding-a-source.md     # how to add/remove/wire a source (+ script template)
```

## Use

| goal | command |
|------|---------|
| quick code+paper scan | `/research-radar keywords="Mamba SSM" since=7d sources=arxiv,github top=10` |
| full radar | `/research-radar keywords="状态空间模型 Mamba" since=30d top=10` |
| drop noise | add `exclude="awesome,survey,reading list"` |
| add a verified deep-dive | add `deep` (enables the deep-research source) |

Digests land in `$RESEARCH_RADAR_DIGEST_DIR` (default `~/research/digests/`)
as `YYYY-MM-DD-<topic>.md`.

## Manage sources

Everything lives in **`sources.yaml`** — one row per source. Three types:

```yaml
- name: arxiv        # type 1: built-in API fetcher
  type: script
  enabled: true
  categories: [cs.AI, cs.CL, cs.LG]
  weight: 1.0

- name: zhihu        # type 2: crawl/social source (WebSearch site: + webReader)
  type: web
  enabled: true
  site: zhihu.com
  weight: 0.5

- name: deep_research   # type 3: delegate to another skill as a deep source
  type: skill
  enabled: false
  skill: deep-research
  weight: 0.9
```

- **Add an API source** → write `scripts/<x>.py` (template in
  `references/adding-a-source.md`) + one `type: script` row.
- **Add a social/crawl source** → one `type: web` row with `site:`.
- **Wire any skill** as a deep source → one `type: skill` row with `skill:`.
- **Remove** → `enabled: false`.

See `references/adding-a-source.md` for the full walkthrough + script contract.

## Dependencies

**Zero pip dependencies.** Sources are pure Python 3 stdlib
(`urllib.request`, `xml.etree`, `json`). Needs `python3`, `curl`, and `jq` for
parsing script output.

Optional:
- `GITHUB_TOKEN` env — raises GitHub rate limit from 60 to 5000 req/hr.
- The `deep-research` skill (or any research skill) — only if you enable a
  `type: skill` source.

## Notes / limits

- A failing source is recorded in the digest footer and skipped — it **never
  aborts** the run, even if half the sources are unreachable.
- `web` sources (X especially) may block crawling; they degrade gracefully too.
- Scoring weights and per-kind popularity ceilings live in `references/scoring.md`.

### Per-source reachability in THIS environment (verified 2026-07-13)

Which sources actually return data depends on your network egress. Status in the
current sandbox:

| source | type | here | note |
|--------|------|:----:|------|
| github | script | ✅ | works with no token (60 req/hr) |
| dblp | script | ✅ | CS papers; year-granular date |
| crossref | script | ✅ | brings citation counts |
| lobsters | script | ✅ | low volume; niche terms often 0 |
| hackernews | script | ✅ | keyword match is loose (expect noise) |
| huggingface | script | ✅ | official site firewalled → **auto-falls back to hf-mirror.com** (zero config) |
| arxiv | script | ⚠️ | reachable but shared-IP rate-limited → 429; cached ~6h + gentler retry; **✅ via proxy** |
| reddit | script | ❌ | DNS sinkhole + firewall; needs a proxy AND that proxy's IP not reddit-blocked |
| reddit_web | web | 🔁 | opt-in fallback: `<q> site:reddit.com` via WebSearch (no direct Reddit connection) |
| zhihu | web | ✅ | WebSearch returns rich results; network reachable |
| x_twitter | web | ❌ | firewall drops x.com:443 (DNS ok) + X anti-bot |
| deep_research | skill | ❓ | opt-in via `deep`; not a network source |

Legend: ✅ works, ⚠️ rate-limited/degraded but usable (✅ via proxy), ❌ hard
network block, 🔁 opt-in fallback source, ❓ not a network fetch (skill). All are
environment-specific — on a normal network every ❌/⚠️ goes green. HF is now
usable out of the box via the mirror; arxiv/reddit unlock with a proxy (see below).
Re-check a script source directly: `python3 scripts/<x>.py --query … --top 3 | jq '.count'`.
Probed but **not** registered: Semantic Scholar (429 without a key), Papers with
Code (redirect loop here).

## Unlocking blocked sources (arxiv / reddit / huggingface)

Some sandboxes block or rate-limit these three. They're handled with **zero new
dependencies** (pure stdlib):

- **Hugging Face — mirror, automatic (zero config).** If `huggingface.co:443` is
  firewalled, `huggingface.py` retries once against `hf-mirror.com`, which is
  reachable here. Hit URLs still point at the official site. Override either way
  with the `HF_ENDPOINT` env var. This is why HF shows ✅ above with no setup.
- **arxiv / reddit — proxy, optional.** Set `defaults.proxy` in `sources.yaml`
  (e.g. `http://127.0.0.1:7897`) and the orchestrator prefixes each script run
  with `http_proxy=<p> https_proxy=<p>`; urllib honors those, so arxiv/reddit
  route through your proxy with no code change. Three equivalent ways to enable:
  1. `sources.yaml` `defaults.proxy` — **recommended**; per-run, only `script` sources.
  2. Claude Code `settings.json` `env` block — global, every command.
  3. `export http_proxy=… https_proxy=…` in the terminal before starting Claude Code.
- **Reddit IP-block fallback.** Reddit blocks proxy/VPN IPs most aggressively.
  If `reddit.py` *through a proxy* still errors — `HTTP 403: Blocked` or
  `SSL unexpected eof` (Reddit alternates between a 403 block page and killing
  the TLS handshake) — that proxy's egress IP is reddit-blacklisted. Options:
  - a **residential proxy** (datacenter IPs are the ones Reddit blocks);
  - Reddit's **OAuth API** (set credentials via env);
  - enable the **`reddit_web`** source (`reddit_web.enabled: true`) — it routes
    `<q> site:reddit.com` through WebSearch, returning post titles + snippets via
    the search engine's own infra, with no direct connection to Reddit. webReader
    on a reddit URL may still fail (same TLS block), but the search snippets alone
    are enough as "community discussion" entries.

## Roadmap (v2, not built)

- **Subscription tracking**: pair with the `loop` skill to re-run on a schedule,
  keep a "last-seen keys" state file, and emit only the delta (new items since
  last run). Deliberately out of scope for v1 (single manual runs).

---
name: research-radar
description: （中文对照版，非加载入口；实际加载的是 SKILL.md）按 关键词+时间窗口 跨多源（论文/代码/模型/社区）调研前沿，去重打分摘要后输出一份 Markdown digest。
argument-hint: 'keywords="..." since=30d sources=all top=15 exclude="..." deep'
allowed-tools: Bash, WebSearch, mcp__web_reader__webReader, Read, Write, Edit, Skill, Task
---

# research-radar（中文版）

跨多个信息源调研一个主题，输出**一份**去重、打分、摘要后的 Markdown
**digest**（调研简报）：论文、代码、模型、社区讨论一网打尽。

## 何时使用
- "帮我调研 / track 一下 <主题> 最近有什么进展"
- "最新论文 / 前沿研究 on <X>"、"github 上有什么新项目"
- "what's new in <X> this month"、"survey the frontier of <X>"
- 需要**跨源**总览（不是单个站点，也不是单次深挖）。

不要用于：单一问题的深度事实核查报告（那是 `deep-research`）；或一次性
网页查询（直接 WebSearch 即可）。

## 参数
完整说明见 `references/arguments.zh.md`。

| 参数 | 默认 | 含义 |
|-----|------|------|
| `keywords` | 必填 | 主题词，空格分隔多个，短语加引号 |
| `since` | `30d` | `Nd` / `YYYY-MM` / `YYYY-MM-DD` |
| `sources` | `all` | 逗号分隔覆盖指定源，或 `all` |
| `top` | `top_per_source`（yaml） | **每源**去重前的最大命中数 |
| `exclude` | 无 | 排除词（命中则相关性压到 0.1） |
| `deep` | 关闭 | 启用 `skill` 类源（如 deep-research） |

## 流水线（按顺序执行）

**1. 解析参数。** 确定 `keywords, since, sources, top, exclude, deep`。`top`/`since`
未指定时取 `sources.yaml` 的 `defaults:`。

**2. 读 `sources.yaml`。** 选定本次运行源：若 `sources != all`，只保留指定且
`enabled` 的源；否则取全部 `enabled: true`。记录每个源的 `type`
（`script` / `web` / `skill`）与 `weight`。

**3. 关键词扩展。** 生成小规模扩展集：同义词 + 中英互译（论文/仓库偏英文；
知乎/社区偏中文）。原始词作为主查询。扩展集用于 (a) 各源查询——arxiv/github/hn/hf
用英文形，reddit/web 用原始/混合形；(b) 相关性打分。

**4. 逐源取数**（见下"源类型"）。源之间互相独立——大查询时可用
`superpowers:dispatching-parallel-agents` 或在一条消息里并发多个 Bash 取数。
**代理：** 若 `sources.yaml` 设了非空 `defaults.proxy`（如
`http://127.0.0.1:7897`），给每个 `script` 调用前缀
`http_proxy=<p> https_proxy=<p>`——urllib 默认 opener 认这俩小写环境变量，让 Claude
Code 的非交互 Bash 也能走代理访问 arxiv/reddit/HF，不依赖交互式 shell 别名。留空则直连。

**5. 归一化**所有 hit 到统一契约：
`{id, title, url, kind(paper|code|discuss|model), date(ISO), summary_raw, metrics{}, extra{}}`。

**6. 去重**，按规范 key：
- 论文 → arxiv id（去版本号）/ DOI
- 代码 → `owner/repo`（小写）
- 模型 → HF model id
- 讨论 / web → 归一化 URL（去 query 与 fragment、去尾斜杠、host 小写）
冲突时：保留分数高的，把 `metrics`/`sources` 合并进 `extra`。

**7. 打分**（`references/scoring.zh.md`）：
`0.30·新鲜度 + 0.30·热度 + 0.25·相关性 + 0.15·源权重`。
应用 `exclude`：标题/摘要含排除词的 hit → 相关性压到 0.1。丢弃窗口外的旧 hit。

**8. 摘要**（仅对排名靠前者）：读 `summary_raw`（摘要/readme/selftext），逐条产出：
- 1–2 句**中文**摘要（遵循 `summary_lang`）。
- `值得看: yes / maybe / no` + 一句理由。
- 代码额外判断：维护中？有文档？有测试？license？
- 模型额外注明 downloads/likes 与 `pipeline_tag`（有用时）。

**9. 渲染** digest（见"输出格式"），Write 到
`<digest-dir>/YYYY-MM-DD-<topic-slug>.md`，其中 `<digest-dir>` 取环境变量
`RESEARCH_RADAR_DIGEST_DIR`，未设则用 `~/research/digests/`
（目录不存在则创建；`<topic-slug>` = 小写、非字母数字→`-`、截断约 40 字符）。
把路径返回给用户。

## 源类型 —— 各自怎么跑

### `script`（内置抓取器）
执行 `python3 scripts/<script>.py --query "<q>" --since <since> --top <top> <extra>`。
脚本吐一个 JSON 对象：`{"source", "count", "hits":[...], "error"?}`。
用 `jq` 解析 stdout（如 `... | jq '.hits'`）。出现 `error` 或 `count:0` 表示该源无结果——记入页脚，继续。
**走代理时** 用 `http_proxy=<p> https_proxy=<p> python3 scripts/<script>.py …`
（启用代理的三种方式见下方"解锁受阻源"）。

yaml 配置键 → CLI 参数 映射表：

| 源（`name`） | `script` | 来自 yaml 的额外参数 |
|--------------|----------|----------------------|
| arxiv | `arxiv` | `categories` → `--categories <csv>` |
| github | `github` | `min_stars` → `--min-stars <n>`，`language` → `--language <x>` |
| hackernews | `hn` | （无） |
| reddit | `reddit` | `subreddits` → `--subreddits <csv>` |
| huggingface | `huggingface` | （无） |
| dblp | `dblp` | `max_fetch` → `--max-fetch <n>` |
| crossref | `crossref` | `mailto` → `--mailto <email>`（可选；或 `CROSSREF_MAILTO` 环境变量） |
| lobsters | `lobsters` | `pages` → `--pages <n>` |

脚本固有参数（非 yaml 驱动）：arxiv 会把响应缓存约 6h（`--cache-dir`，默认
`~/.cache/research-radar/arxiv`；`--no-cache` 跳过缓存）。
GitHub 支持 `GITHUB_TOKEN` 环境变量（限频 60→5000/小时）。

### `web`（抓取/社媒，无 API —— 知乎、X）
对每个启用的 `web` 源：
1. `WebSearch "<扩展 query> site:<site>"` → 取前 `top` 条结果 URL。
2. 对每个 URL 调 `mcp__web_reader__webReader`，读返回数组的 `[0]`。它**正文之外还带结构化字段**，
   要主动抽进契约，而不是只用正文：
   - `title`        ← `headline` / `og:title` / `title`
   - `date`         ← `publishedTime` / `datePublished`（ISO；精确到天 → 喂给新鲜度）
   - `metrics`      ← `{comments: commentCount}`（有 `likes`/`votes` 也加）
   - `summary_raw`  ← `description` + `content` 前 1–2 段
   - `extra`        ← `{author: name, site}`
3. 构造契约 hit：`kind: discuss`，`id` = 归一化 URL（host+path 小写，去 query/fragment/尾斜杠）。
   字段缺失就留空——别猜（`date` 空 → 新鲜度中性 0.5，不惩罚）。
若站点屏蔽抓取（X 常见）或 webReader 取不到可用内容，把该源标记为**降级**——记入页脚、产出 0 命中、不中断运行。

### `skill`（委托 —— 仅当设置了 `deep`）
对每个启用的 `skill` 源：
1. 把本次命中的高分项 + 关键词提炼成**一个**聚焦的研究问题。
2. 经 **Skill** 工具调用（`skill: <name>`，如 `deep-research`）。
3. 取回的带引用 markdown → 追加到"🔬 深度报告"段。

## 输出格式

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
<deep-research 带引用 markdown>

> ⚠️ 跳过/降级的源: x_twitter (抓取受限), reddit (网络不可达) …
```

榜单是门面；分类小节给细节。页脚**始终**列出跳过/降级的源及原因。

## 配置：管理信息源
所有增删都在 **`sources.yaml`**（详见 `references/adding-a-source.zh.md`）：
- 加 API 源 → 写 `scripts/<x>.py`（契约模板见该参考）+ 一行 `type: script`。
- 加抓取/社媒源 → 一行 `type: web` 带 `site:`。
- 接任意 skill 做深挖源 → 一行 `type: skill` 带 `skill:`。
- 删源 → `enabled: false`（或删行）。

## 错误处理与预算
- **单源失败绝不中断整体运行。** `script` 报错会吐错误信封；`web`/`skill` 被屏蔽则标记降级。这些源都会带原因出现在 digest 页脚。
- **token 预算：** `top` 限制每源体量；打分后总数保留约 `top*1.5` 条、不超过约 50 条。只对保留项做摘要。
- **网络限制：** GitHub 无 token 也能跑（≤60 req/小时）。Hugging Face 在官网不可达时自动回退到
  `hf-mirror.com`。arXiv 对 429 温和重试（尊重 `Retry-After`）并把响应缓存约 6h。Reddit 在本环境需代理，
  且代理出口 IP 可能仍被 reddit 在 TLS 层封。错误信封 + 页脚让剩余封锁可见而非致命。

## 解锁受阻源（arxiv / reddit / huggingface）
部分沙箱会封锁或限频这三个。均以零新增依赖处理：
- **Hugging Face —— 镜像（自动，零配置）：** `huggingface.co` 不可达时，`huggingface.py`
  自动回退到 `hf-mirror.com` 重试一次；hit 链接仍指向官网。可用 `HF_ENDPOINT` 环境变量覆盖。
- **arxiv / reddit —— 代理（可选）：** 在 `sources.yaml` 设 `defaults.proxy`（如
  `http://127.0.0.1:7897`），编排器给每次脚本运行前缀 `http_proxy=<p> https_proxy=<p>`，
  urllib 自动认，无需改代码。启用代理的三种等价方式：
  1. `sources.yaml` 的 `defaults.proxy` —— 推荐；按需、只影响 `script` 源。
  2. Claude Code `settings.json` 的 `env` 块 —— 全局，影响所有命令。
  3. 启动 Claude Code 前在终端 `export http_proxy=… https_proxy=…`。
- **Reddit IP 封锁兜底：** Reddit 对代理/VPN IP 反爬最强。若**经代理** `reddit.py` 仍报错——
  `HTTP 403: Blocked` 或 `SSL unexpected eof`（Reddit 时而返回 403 封锁页、时而直接掐 TLS 握手）——
  说明该代理出口 IP 被 reddit 拉黑。可选：换**住宅代理**、用 Reddit
  **OAuth API**（在环境变量里设凭证）、或启用 **`reddit_web`** 源——它把
  `<q> site:reddit.com` 走 WebSearch（搜索引擎自己的基础设施），返回帖子标题+摘要片段，全程不直连 Reddit。

## 参考
- `references/arguments.zh.md` — 参数完整说明 + 示例
- `references/scoring.zh.md` — 打分公式与各分量定义
- `references/adding-a-source.zh.md` — 增删/接入源、脚本契约模板
- `sources.yaml` — 源注册表（改这里）

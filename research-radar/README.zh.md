# research-radar（中文）

一个 skill：跨多源调研某个主题的前沿，返回一份**去重、打分、摘要**后的 Markdown
**digest**（调研简报）。

给它一个主题 + 时间窗口，它从论文（arXiv）、代码（GitHub）、模型（Hugging Face）、
社区讨论（Hacker News、Reddit、知乎、X）取数，合并重复项、按综合分排序、逐条中文
摘要，最后产出一份你一分钟就能扫完的简报。

```
/research-radar keywords="状态空间模型 Mamba" since=30d top=10
```

## 安装（让 `/research-radar` 能被调用）

Claude Code 只从 `~/.claude/skills/`（用户级，全局）或 `<项目>/.claude/skills/`（项目级）
自动发现 skill。本仓库默认不在这些路径下，所以用**软链**注册 `research-radar`——
真身留在你的 clone 里，`git pull` 拉到的更新会直接生效，无需重新注册：

```bash
# 1. clone 到你存放仓库的任意位置
git clone https://github.com/NiceLy235/skills.git ~/skills
# 2. 把 skill 软链进 Claude Code 的发现路径
mkdir -p ~/.claude/skills
ln -s ~/skills/research-radar ~/.claude/skills/research-radar
# 3. 重启 Claude Code（skill 在会话启动时索引）
```

> 如果你已经把源码放在别处（你是作者，或 clone 到了其他路径），把上面的
> `~/skills/research-radar` 换成那个绝对路径即可——机制一样。

然后**重启 Claude Code**（运行中的会话常常会在重扫时发现新软链，但重启更稳妥）。之后：

- `/research-radar keywords="..." since=30d top=10` 直接调用，或
- 匹配的请求（"帮我调研一下 Mamba 最近有什么进展"）自动触发。

验证：新会话的 `/help` 里能看到它。在 clone 的 `research-radar/` 下改文件经软链即时生效，
**无需重新注册**；`git pull` 获取更新。

## 文档与语言 / Docs & language

所有文档都有**英文**与**中文**（`.zh.md`）两版。源在 [`sources.yaml`](sources.yaml) 管理。

| 文档 | English | 中文 |
|------|---------|------|
| Skill（编排流程） | [SKILL.md](SKILL.md) | [SKILL.zh.md](SKILL.zh.md) |
| README（本文件） | [README.md](README.md) | [README.zh.md](README.zh.md) |
| 参数说明 | [arguments.md](references/arguments.md) | [arguments.zh.md](references/arguments.zh.md) |
| 打分 | [scoring.md](references/scoring.md) | [scoring.zh.md](references/scoring.zh.md) |
| 增删/接入源 | [adding-a-source.md](references/adding-a-source.md) | [adding-a-source.zh.md](references/adding-a-source.zh.md) |

## 目录结构

```
research-radar/
  SKILL.md                 # Claude 执行的编排流程（英文；中文对照见 SKILL.zh.md）
  sources.yaml             # ★ 源注册表 —— 增删/接入源都改这里
  scripts/
    _common.py             # 共享工具：parse_since、emit、抓取+重试、hit 契约
    arxiv.py  github.py  hn.py  reddit.py  huggingface.py   # 每个 script 源一个
  references/
    arguments.md           # 参数完整文档 + 示例
    scoring.md             # 打分公式与分量
    adding-a-source.md     # 如何增删/接入源（含脚本模板）
```

> 中文文档：`SKILL.zh.md`、`README.zh.md`、`references/*.zh.md`。

## 用法

| 目标 | 命令 |
|------|------|
| 快扫代码+论文 | `/research-radar keywords="Mamba SSM" since=7d sources=arxiv,github top=10` |
| 全源雷达 | `/research-radar keywords="状态空间模型 Mamba" since=30d top=10` |
| 去噪 | 加 `exclude="awesome,survey,reading list"` |
| 附带深度验证报告 | 加 `deep`（启用 deep-research 源） |

digest 存到 `$RESEARCH_RADAR_DIGEST_DIR`（默认 `~/research/digests/`），文件名 `YYYY-MM-DD-<topic>.md`。

## 管理信息源

一切都在 **`sources.yaml`**——一行一个源，三种类型：

```yaml
- name: arxiv        # 类型一：内置 API 抓取器
  type: script
  enabled: true
  categories: [cs.AI, cs.CL, cs.LG]
  weight: 1.0

- name: zhihu        # 类型二：抓取/社媒源（WebSearch site: + webReader）
  type: web
  enabled: true
  site: zhihu.com
  weight: 0.5

- name: deep_research   # 类型三：把别的 skill 当深挖源接入
  type: skill
  enabled: false
  skill: deep-research
  weight: 0.9
```

- **加 API 源** → 写 `scripts/<x>.py`（模板见 `references/adding-a-source.md`）+ 一行 `type: script`。
- **加社媒/抓取源** → 一行 `type: web` 带 `site:`。
- **接任意 skill** 做深挖源 → 一行 `type: skill` 带 `skill:`。
- **删源** → `enabled: false`。

完整流程 + 脚本契约见 `references/adding-a-source.md`。

## 依赖

**零 pip 依赖。** 各源都是纯 Python 3 标准库（`urllib.request`、`xml.etree`、
`json`）。需要 `python3`、`curl`、`jq`（解析脚本输出）。

可选：
- `GITHUB_TOKEN` 环境变量 —— GitHub 限频从 60 提到 5000 req/小时。
- `deep-research` skill（或任意研究类 skill）—— 仅当你启用 `type: skill` 源时需要。

## 注意 / 限制

- 任何源失败都会记入 digest 页脚并跳过——**绝不中断**整体运行，哪怕一半源不可达。
- `web` 源（尤其 X）可能屏蔽抓取；同样会优雅降级。
- 打分权重与各类型热度上限见 `references/scoring.md`。

### 本环境各源可达性（2026-07-13 实测）

哪些源真能取到数据，取决于你的出口网络。当前沙箱实测：

| 源 | 类型 | 本环境 | 说明 |
|----|------|:------:|------|
| github | script | ✅ | 无 token 可用（60 req/小时） |
| dblp | script | ✅ | CS 论文；按年过滤 |
| crossref | script | ✅ | 带被引次数 |
| lobsters | script | ✅ | 体量小；冷门词常 0 命中 |
| hackernews | script | ✅ | 关键词匹配宽松（会有噪音） |
| huggingface | script | ✅ | 官网被封 → **自动回退 hf-mirror.com**（零配置） |
| arxiv | script | ⚠️ | 可达但共享 IP 限频 → 429；缓存约 6h + 温和重试；**经代理 ✅** |
| reddit | script | ❌ | DNS 黑洞 + 防火墙；需代理且该代理 IP 未被 reddit 封 |
| reddit_web | web | 🔁 | 按需兜底：`<q> site:reddit.com` 走 WebSearch（不直连 Reddit） |
| zhihu | web | ✅ | WebSearch 返回丰富结果；网络可达 |
| x_twitter | web | ❌ | 防火墙丢包 x.com:443（DNS 正常）+ X 反爬 |
| deep_research | skill | ❓ | 经 `deep` 按需启用；非网络取数源 |

图例：✅ 可用，⚠️ 限频/降级但可用（经代理 ✅），❌ 硬封锁，🔁 按需兜底源，❓ 非网络抓取（skill）。
均随环境而变——正常网络下 ❌/⚠️ 都会转绿。HF 现已靠镜像开箱即用；arxiv/reddit 经代理解锁（见下）。
脚本源可直接复核：`python3 scripts/<x>.py --query … --top 3 | jq '.count'`。
探测过但**未**注册：Semantic Scholar（无 key 持续 429）、Papers with Code（本环境重定向异常）。

## 解锁受阻源（arxiv / reddit / huggingface）

部分沙箱会封锁或限频这三个。均以**零新增依赖**（纯标准库）处理：

- **Hugging Face —— 镜像，自动（零配置）。** `huggingface.co:443` 被防火墙封时，
  `huggingface.py` 自动回退到本机可达的 `hf-mirror.com` 重试一次；hit 链接仍指向官网。
  可用 `HF_ENDPOINT` 环境变量覆盖任一端点。所以上面 HF 无需任何配置就是 ✅。
- **arxiv / reddit —— 代理，可选。** 在 `sources.yaml` 设 `defaults.proxy`（如
  `http://127.0.0.1:7897`），编排器给每次脚本运行前缀 `http_proxy=<p> https_proxy=<p>`，
  urllib 自动认，arxiv/reddit 即走代理，无需改代码。启用代理的三种等价方式：
  1. `sources.yaml` 的 `defaults.proxy` —— **推荐**；按需、只影响 `script` 源。
  2. Claude Code `settings.json` 的 `env` 块 —— 全局，影响所有命令。
  3. 启动 Claude Code 前在终端 `export http_proxy=… https_proxy=…`。
- **Reddit IP 封锁兜底。** Reddit 对代理/VPN IP 反爬最强。若**经代理**
  `reddit.py` 仍报错——`HTTP 403: Blocked` 或 `SSL unexpected eof`（Reddit 时而返回 403 封锁页、
  时而直接掐 TLS 握手）——说明该代理出口 IP 被 reddit 拉黑（封的多是机房 IP）。可选：
  - 换**住宅代理**；
  - 用 Reddit **OAuth API**（在环境变量里设凭证）；
  - 启用 **`reddit_web`** 源（`reddit_web.enabled: true`）——把
    `<q> site:reddit.com` 走 WebSearch，经搜索引擎自己的基础设施返回帖子标题+摘要片段，
    全程不直连 Reddit。对 reddit URL 调 webReader 仍可能失败（同样的 TLS 封），但搜索片段本身
    已足以当作"社区讨论"条目。

## 路线图（v2，暂未做）

- **订阅追踪**：配合 `loop` skill 定时重跑，用一个"上次见过的 key"状态文件，只输出增量 delta（自上次以来的新增项）。v1 仅做单次手动运行，订阅明确列为 v2。

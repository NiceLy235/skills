# 参数说明（中文）

`research-radar` 通过斜杠调用的关键字参数驱动：

```
/research-radar keywords="..." since=30d sources=all top=15 exclude="..." deep
```

除 `keywords` 外均可省略。

## `keywords`（必填）
要追踪的主题。一个或多个词，空格分隔；短语加引号。

- `keywords="mamba state space"` —— 三个词（每源内 AND 匹配）。
- `keywords="状态空间模型 Mamba"` —— 中英混合；流水线会双向扩展（见流水线第 3 步），让英文为主的源（arxiv、github）和中文为主的源（知乎）都拿到好查询。

它是关键词扩展、相关性打分、digest 标题的种子。

## `since`（默认 `30d`）
时间窗口。cutoff 由"当前"向前计算。接受的形式：

| 值           | 含义                              |
|--------------|--------------------------------------|
| `Nd`         | 最近 N 天（`7d`、`30d`、`90d`）      |
| `YYYY-MM`    | 自该月第一天起                        |
| `YYYY-MM-DD` | 自该具体日期起                       |

示例：`since=7d`、`since=2024-06`、`since=2024-06-11`。
窗口在各源的处理：

- **arxiv** —— `submittedDate:[BEGIN TO END]`，服务端。
- **github** —— `pushed:>=YYYY-MM-DD`，服务端。
- **hackernews** —— `created_at_i > <unix>`，服务端。
- **reddit** —— 映射到最近的 `t=` 窗口（day/week/month/year/all）。
- **huggingface** —— 对 `lastModified` 客户端过滤。
- **web / skill** —— 作为上下文透传；WebSearch 本身不严格按日期过滤，所以"最近"意图最好用 `Nd` 表达。

## `sources`（默认 `all`）
逗号分隔的源 `name` 列表，**覆盖**默认启用集。设为 `all`（或省略）则运行 `sources.yaml` 中所有 `enabled: true` 的源。

- `sources=arxiv,github` —— 只跑这两个。
- `sources=all` —— 所有启用的源。
- 列了 `sources.yaml` 里没有的名字 → 在页脚记为跳过。

## `top`（默认取 `sources.yaml` 的 `top_per_source`）
去重/打分前**每源**取的最大命中数。调大提升召回，代价是 token 与时间。打分后 digest 大致保留 `top * 1.5` 条（见 SKILL.md"错误处理与预算"）。

## `exclude`（默认无）
逗号分隔的排除词。标题/摘要含排除词的 hit，相关性被压到 0.1（在榜单里沉底）。用来去噪：`exclude="survey,reading list,awesome"`。

## `deep`（开关，默认关）
启用 `skill` 类源（通常是 `deep_research`）。会在 digest 里加"🔬 深度报告"段，附带引用的深挖。耗时与 token 都较高——快速扫描时关掉。

## 示例

```
# 快扫，最近一周，只看代码+论文
/research-radar keywords="Mamba SSM" since=7d sources=arxiv,github top=10

# 全源雷达，30 天，去掉合集类噪音
/research-radar keywords="状态空间模型 Mamba" since=30d top=10 exclude="awesome,survey"

# 单主题，附深度验证报告
/research-radar keywords="retrieval augmented generation 2024" since=2024-01 deep
```

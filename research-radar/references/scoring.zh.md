# 打分（中文）

每个归一化后的 hit 得到一个 `[0, 1]` 的 `score`。综合分由四个信号混合而成，
每个信号先各自归一化到 `[0, 1]`：

```
score = 0.30 * 新鲜度(recency)   (窗口内的时效)
      + 0.30 * 热度(popularity)  (受关注度)
      + 0.25 * 相关性(relevance) (是否真匹配关键词)
      + 0.15 * 源权重(source_weight) (sources.yaml 的信任权重)
```

这些是默认权重；编排时（你，Claude）按此排序。若某次运行某个信号更重要，可在此微调配比。

## 各分量定义

### 新鲜度(recency) —— 0.30
相对查询窗口的时效。令 `cutoff = parse_since(since)`、`window = now - cutoff`（天）。
对日期为 `d` 的 hit：

- `age = (now - d).days`
- `window > 0` 时 `recency = clamp(1 - age / window, 0, 1)`，否则 `1.0`。

即：今天发布的 = 1.0；窗口最边缘的 ≈ 0。窗口外的旧 hit（个别 API 会泄漏）= 0，应丢弃。
`date` 缺失/未知时用 `0.5`（中性）——不要因缺日期惩罚。

### 热度(popularity) —— 0.30
按源取的关注度指标，log 缩放，避免一个爆款仓库压垮全场：

| kind / 源     | 原始指标                       |
|---------------|------------------------------|
| code (github) | `stargazers_count`           |
| discuss (hn)  | `points`（回退 `comments`）    |
| discuss (reddit) | `score`（回退 `comments`） |
| model (hf)    | `downloads`（回退 `likes`）    |
| paper (arxiv) | API 无 → 中性 `0.5`           |

```
popularity = log10(raw + 10) / log10(BUCKET + 10)
```
`BUCKET` 是各类型"算多"的上限，把"很多"映射到约 1.0。默认值：

| kind   | BUCKET |
|--------|--------|
| code   | 10_000（star） |
| model  | 1_000_000（下载） |
| discuss| 1_000（points/score） |
| paper  | 无（中性 0.5） |

夹紧到 `[0, 1]`。目的是**排序**，不是绝对值。

### 相关性(relevance) —— 0.25
对 `title + summary_raw` 做关键词匹配（不区分大小写）。用**扩展后**的关键词集
（流水线第 3 步的同义词 + 翻译）：

- 全部原始关键词都在 → `1.0`
- 部分：`fraction = 命中词数 / 总词数`
- 含排除词 → 相关性上限压到 `0.1`（基本沉底）

这是个廉价信号（文本已在手）；真正的语义判断在摘要步骤的 `值得看` 结论里。

### 源权重(source_weight) —— 0.15
直接取 `sources.yaml` 的 `weight`（已是 0..1）。反映对源的信任度：arxiv/github 1.0、hn 0.7、hf 0.8、reddit 0.6、社媒/抓取 0.5、deep-research 0.9。

## 怎么用

1. 给每个去重后的 hit 算 `score`。
2. 按 `score` 降序排合并列表。
3. 取前 `top_per_source * 1.5`（取整）作为 digest 的榜单，受全局 token 预算约束（见 SKILL.md"错误处理与预算"）。
4. 由榜单渲染"📊 综合榜单"表格，再按 kind 分小节（📄 论文 / 💻 代码 / 📣 社区讨论）给细节。

每条旁边显示的 `★ <score>` 是 `round(score, 2)`。

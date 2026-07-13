# 增删 / 接入信息源（中文）

`sources.yaml` 是唯一事实来源。源分三种类型。加一个源永远是"往 `sources.yaml`
加一行"——唯一要考虑的是是否需要写抓取器。

## 删除（软删除）一个源

把它的行的 `enabled` 设为 `false`。运行时跳过，但配置保留备用。（直接删行也行。）

## 类型一 —— `script`：新的 API 源

任何有公开 HTTP API（JSON 或 XML）的源，加一个纯标准库的小抓取器 + 一行 yaml。

### 第 1 步 —— 写 `scripts/<name>.py`

用下面的契约模板。要求：
- 接受 `--query`、`--since`、`--top`（外加任何源专属参数），
- 经 `_common.get_json` / `get_text` 取数（内置重试），
- 经 `_common.emit` 在 stdout 吐**一个** JSON 对象，
- **绝不**因取数/解析失败而崩溃——改吐错误信封。

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
    # 在此加源专属参数，如 --categories
    args = ap.parse_args()

    cutoff = parse_since(args.since)
    params = {"q": args.query, "limit": str(args.top)}   # 加日期过滤
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    try:
        data = get_json(url)
    except Exception as e:
        emit("<name>", [], error=f"fetch failed: {e}")
        return

    hits = []
    for item in data.get("items", []):
        hits.append({
            "id":          f"<name>:<稳定key>",   # 去重 key
            "title":       item.get("title", ""),
            "url":         item.get("url", ""),
            "kind":        "discuss",                 # paper|code|discuss|model
            "date":        item.get("date", ""),      # ISO 8601
            "summary_raw": item.get("summary", ""),
            "metrics":     {"score": item.get("score", 0)},
            "extra":       {},                        # 其他想带的字段
        })
    emit("<name>", hits)

if __name__ == "__main__":
    main()
```

必需的 hit 键（全都要）：`id, title, url, kind, date, summary_raw, metrics,
extra`。值可以为空；缺键会破坏契约。

### 第 2 步 —— 加 yaml 行

```yaml
- name: <name>
  type: script
  enabled: true
  script: <name>            # scripts/<name>.py 的 basename；与 name 相同可省略
  weight: 0.8               # 0..1 信任权重
  # 源专属配置写这里，如：
  categories: [cs.AI]
```

### 第 3 步 —— 告诉编排器参数映射

如果你的源除了 query/since/top 还有配置键，在 SKILL.md 的"配置键 → CLI 参数"表里加一行，
让编排器把它们传进去。（或者干脆在脚本里硬编码合理默认值。）

### 第 4 步 —— 验证

```bash
python3 scripts/<name>.py --query "<测试词>" --since 30d --top 5 | jq '.hits[0]'
```
确认 `.hits[0]` 含全部契约键。

## 类型二 —— `web`：抓取 / 社媒源（无 API）

对没有可用公开 API 的站点（知乎、X/Twitter、博客…）不写脚本——由编排器做
`WebSearch "<query> site:<site>"`，再用 `mcp__web_reader__webReader` 抓取前几条，
读取后提取字段。

加一行：

```yaml
- name: zhihu
  type: web
  enabled: true
  site: zhihu.com
  weight: 0.5
```

仅此而已。`web` 源的搜索 + 抓取 + 提取都由编排器处理。若站点屏蔽抓取（X 常见），
运行会把该源标记为降级并记入页脚后继续——无需改代码。

## 类型三 —— `skill`：把别的 skill 当深挖源接入

任意其他 skill 都能成为源——最常见的是用 `deep-research` 做带引用的深度验证。
加一行：

```yaml
- name: deep_research
  type: skill
  enabled: false          # 运行时经 `deep` 参数按需启用
  skill: deep-research    # 要调用的 Skill 名
  weight: 0.9
```

运行时（仅当请求了 `deep` **且**该源 enabled），编排器：
1. 把高分命中提炼成一个聚焦的研究问题，
2. 经 Skill 工具调用该 skill，
3. 把返回的带引用 markdown 追加到"🔬 深度报告"段。

`skill:` 的值必须是运行时里可用的 skill 名。接口刻意简单：文本问题进、markdown
报告出——所以多数研究类 skill 无需胶水代码即可接入。

## 实战示例：内置源踩过的坑

三个真实源，三种不同的隐蔽陷阱。对应脚本可作参考。

**跨源去重小技巧：** 当两个源对同一篇论文都给出 DOI 时，两边都用 `doi:<doi>` 作
`id`，去重时自动合并（`dblp.py` 与 `crossref.py` 都这么做——否则同一篇论文会出现两次）。

### DBLP —— 只有一条命中时会退化成 object，不是 list
`result.hits.hit` 在多条命中时是**列表**，但只有一条命中时是**裸 object**。
直接迭代 dict 得到的是它的字符串 key，不是命中：

```python
hit_list = data["result"]["hits"]["hit"]
if isinstance(hit_list, dict):      # 恰好一条命中 -> dict，不是 [dict]
    hit_list = [hit_list]
```

DBLP 还只给发表**年份**，所以 `--since` 只能按年粒度过滤，`date` 设成 `"{year}-01-01"`。

**`venue` / `ee` 有时是列表、不只是字符串**——某些记录返回 `"venue": ["Neurocomputing", "..."]`。直接喂给 `truncate()` 会崩（`'list' object has no attribute 'strip'`）。用 helper 归一化（`dblp.py::_as_str`）或依赖已加固的 `_common.truncate`。

### Crossref —— JATS 摘要、大写字段名、年粒度日期
- **字段大小写非标准：** `.DOI`、`.URL`、`.["is-referenced-by-count"]`、
  `.issued."date-parts"[0][0]`。小写 `.doi` / `.url` 会静默返回 `null`。
- **摘要是 JATS XML**（`<jats:p>…</jats:p>`），去标签：
  `re.sub(r"<[^>]+>", "", abstract)`。
- **相关性 ≠ 时效：** 多取（`rows = top * 4`）再按年客户端过滤——Crossref 靠前的结果常是旧的。
- 设 `mailto`（查询参数或 `CROSSREF_MAILTO` 环境变量）进入 polite pool（更高限频）。

### Lobsters —— 没有 JSON 关键词搜索，只能翻页 + 客户端过滤
没有 `search.json?q=` 端点（会返回 `400 Unpermitted query`）。改为翻 `newest.json`
与 `/newest/page/{n}.json`（每页约 40 条），客户端过滤：标题/tags/description 含任一
关键词 **且** `created_at` 在窗口内。时间戳带时区（`2026-07-11T00:24:30.000-05:00`），
用 `datetime.fromisoformat` 解析。凑够 `top` 或读到空页就停；后续页 404 当作
**"数据到头"，不要当错误**（别污染整次运行）。

## 改完的检查清单

- [ ] `sources.yaml` 能解析：`python3 -c "import yaml; yaml.safe_load(open('sources.yaml'))"`
  （或任意 YAML linter）。
- [ ] script 源：`--query ... | jq '.hits[0]'` 含全部 8 个契约键。
- [ ] 各源 `name` 全局唯一（它是去重/页脚的身份标识）。

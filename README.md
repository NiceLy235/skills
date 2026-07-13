# skills

> 中文说明见下方 [中文](#中文)。

A collection of [Claude Code](https://www.claude.com/claude-code) skills —
self-contained, zero-dependency tools you register into your own Claude Code
agent and call via `/skill-name` or natural-language triggers.

| skill | what it does | docs |
|-------|--------------|------|
| **research-radar** | Cross-source frontier-research digest: papers (arXiv), code (GitHub), models (Hugging Face), community (HN / Reddit / 知乎 / X) → one deduped, scored, summarized Markdown report. | [README](research-radar/README.md) · [中文](research-radar/README.zh.md) |

## Install a skill into your Claude Code

Claude Code auto-discovers skills from `~/.claude/skills/` (user / global) or
`<project>/.claude/skills/` (project-scoped). Register a skill with a **symlink**
so your clone stays the source of truth and `git pull` updates flow straight
through — no re-register needed.

```bash
# 1. clone the repo
git clone https://github.com/NiceLy235/skills.git ~/skills

# 2. symlink each skill you want into Claude Code's discovery path
mkdir -p ~/.claude/skills
ln -s ~/skills/research-radar ~/.claude/skills/research-radar

# 3. RESTART Claude Code (skills are indexed at session start)
```

After restart, verify the skill is loaded — it shows up in `/help` of a fresh
session — then invoke it:

```
/research-radar keywords="状态空间模型 Mamba" since=30d top=10
```

…or just describe the task in plain language and Claude Code triggers it.

### Requirements & notes

- **Claude Code** (CLI / desktop / web / IDE extension).
- **`python3`** on `PATH`. The script sources are pure Python 3 stdlib
  (`urllib`, `json`, `xml.etree`) — **no `pip install` needed**. (`curl` / `jq`
  are handy for manual probing but not required by the orchestration.)
- Per-skill env knobs are documented in each skill's README (e.g. optional
  `GITHUB_TOKEN`, proxy settings, `HF_ENDPOINT`).
- Project-scoped install: drop the symlink into `<repo>/.claude/skills/` instead
  of `~/.claude/skills/` to enable a skill for one project only.

### Update

```bash
cd ~/skills && git pull      # updates flow through the symlinks immediately
```

### Uninstall

```bash
rm ~/.claude/skills/research-radar     # remove the symlink; source clone untouched
```

---

## 中文

一套 [Claude Code](https://www.claude.com/claude-code) skill 合集——自包含、零依赖，
注册到你自己的 Claude Code 后即可用 `/skill名` 或自然语言触发。

| skill | 作用 | 文档 |
|-------|------|------|
| **research-radar** | 跨源前沿调研：论文（arXiv）、代码（GitHub）、模型（Hugging Face）、社区（HN / Reddit / 知乎 / X）→ 一份去重、打分、中文摘要的 Markdown 简报。 | [README](research-radar/README.md) · [中文](research-radar/README.zh.md) |

### 安装到你的 Claude Code

Claude Code 只从 `~/.claude/skills/`（用户级 / 全局）或 `<项目>/.claude/skills/`（项目级）
自动发现 skill。用**软链**注册，clone 作为真身，`git pull` 更新直接生效，无需重新注册：

```bash
# 1. clone 仓库
git clone https://github.com/NiceLy235/skills.git ~/skills

# 2. 把要用的 skill 软链进 Claude Code 的发现路径
mkdir -p ~/.claude/skills
ln -s ~/skills/research-radar ~/.claude/skills/research-radar

# 3. 「重启」Claude Code（skill 在会话启动时索引）
```

重启后用 `/help` 验证（新会话里能看到），然后：

```
/research-radar keywords="状态空间模型 Mamba" since=30d top=10
```

或直接用自然语言描述需求，Claude Code 会自动触发。

**依赖与说明**：
- **Claude Code**（CLI / 桌面 / 网页 / IDE 插件）。
- **`python3`**：脚本均为纯 Python 3 标准库（`urllib` / `json` / `xml.etree`），**无需 pip 安装**。
  （`curl` / `jq` 仅手动探测时方便，编排本身不依赖。）
- 各 skill 的环境变量开关见各自 README（如可选 `GITHUB_TOKEN`、代理设置、`HF_ENDPOINT`）。
- 项目级安装：把软链放到 `<项目>/.claude/skills/` 而非 `~/.claude/skills/`，即可只对单个项目启用。

**更新**：`cd ~/skills && git pull`，软链即时生效。
**卸载**：`rm ~/.claude/skills/research-radar`（仅删软链，不动源码 clone）。

## License

MIT — see [LICENSE](LICENSE). © 2026 NiceLy235.
本仓库所有 skill 均按 MIT 协议授权。

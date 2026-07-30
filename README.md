<div align="center">

# Codex Jingle

**让 Codex 任务完成时先响起状态音效，再用本机语音告诉你哪个任务结束了。**

[![macOS](https://img.shields.io/badge/macOS-13%2B-000000?logo=apple)](https://www.apple.com/macos/)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![SwiftUI](https://img.shields.io/badge/UI-SwiftUI-F05138?logo=swift&logoColor=white)](https://developer.apple.com/xcode/swiftui/)
[![License](https://img.shields.io/badge/code-MIT-green.svg)](LICENSE)
[![Sounds](https://img.shields.io/badge/sounds-CC0-blue.svg)](assets/sounds/LICENSE-CC0.txt)

</div>

---

```text
in   Codex agent-turn-complete event + thread title + final status
out  completion/attention sound → local task-name speech

fail missing or invalid event ID → ignore safely; do not risk duplicate speech
fail enhanced macOS voice unavailable → fall back to Tingting
fail multiple tasks finish together → serialize playback instead of overlapping
fail subagent/internal turn completes → stay silent; notify the parent task only
fail existing Codex notify config → back it up, then install the Jingle callback
```

Codex Jingle 是一个免费的 macOS companion widget。它不调用云端 TTS，不需要
API Key，也不常驻一个语音模型。设置窗口可以关掉；Codex 完成任务时，回调仍会
自动播放音效和播报。

## 示例输出

![Codex Jingle widget](./screenshots/codex-jingle-widget.png)

默认通知流程：

```text
快速完成音效
    ↓
“交易系统。任务已完成。”
```

需要确认时：

```text
平静提醒音效
    ↓
“交易系统。任务已结束，但还有事项需要确认。”
```

## 为什么是这个形态

- **零费用**：使用 macOS 本机语音和本地音效，没有 API 账单。
- **轻量**：设置页是原生 SwiftUI 小窗口，通知引擎是单文件 Python callback。
- **可辨认**：先用音效区分状态，再播报 Codex 任务名。
- **只报主任务**：subagent 与内部 code-review turn 静默，不朗读派发指令。
- **不打架**：多任务同时完成时排队播放，不让几段语音重叠。
- **可关闭**：设置 App 不需要一直运行，Codex callback 独立工作。
- **本地优先**：设置、缓存和事件记录只保存在 `~/.codex/spoken-notify/`。

## 架构

```text
┌──────────────────────┐
│ Codex task completes │
└──────────┬───────────┘
           ▼
┌────────────────────────────┐
│ codex_spoken_notify.py     │
│ classify · dedupe · queue  │
└──────────┬─────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐  ┌──────────────────┐
│ afplay   │  │ macOS `say`      │
│ 状态音效  │  │ 本机语音 + 缓存   │
└──────────┘  └──────────────────┘

┌────────────────────────────┐
│ Codex Jingle SwiftUI App   │
│ 选择 · 试听 · 保存设置       │
└────────────────────────────┘
```

## 快速开始

### 要求

- macOS 13 或更高版本
- Codex Desktop 或支持 `notify` callback 的 Codex CLI
- Xcode Command Line Tools：`xcode-select --install`
- 系统可用的 `python3`

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/zinan92/codex-jingle.git
cd codex-jingle

# 2. 安装 callback、音效和设置 App
./scripts/install.sh

# 3. 重启一次 Codex
```

安装器会：

1. 把通知引擎安装到 `~/.codex/hooks/codex_spoken_notify.py`。
2. 把 CC0 音效安装到 `~/.codex/hooks/sounds/`。
3. 在本机编译并签名 `~/Applications/Codex 通知设置.app`。
4. 备份现有 `~/.codex/config.toml`，再写入 Codex `notify` callback。

打开设置：

```bash
open "$HOME/Applications/Codex 通知设置.app"
```

也可以从命令行打开：

```bash
python3 "$HOME/.codex/hooks/codex_spoken_notify.py" --setup
```

## 功能一览

| 功能 | 说明 | 状态 |
|---|---|---|
| 双状态音效 | 完成与需确认使用独立音效 | 已完成 |
| 音效下拉菜单 | 每种状态提供 8 个 Kenney CC0 音效 | 已完成 |
| 独立试听 | 音效和语音分别试听 | 已完成 |
| 任务名播报 | 播报 Codex thread title 与状态 | 已完成 |
| 内容模式 | `任务名 + 状态` / `只播报状态` | 已完成 |
| 本机音色 | Sandy、Flo、Reed、Tingting | 已完成 |
| 本地缓存 | 相同播报复用 AIFF，最多保留 96 条 | 已完成 |
| 并发排队 | 多任务完成时串行播放 | 已完成 |
| 去重 | 相同 turn ID 跨重启只通知一次 | 已完成 |
| 主任务过滤 | subagent completion 静默，只播报用户可见任务 | 已完成 |

## 状态判断

通知引擎是确定性的，不使用 LLM。以下结果会进入“需确认”状态：

- 测试、验证或构建失败
- 缺少证据或无法验证
- 任务被 blocked
- 仍需用户决定或确认
- Codex final message 缺失

没有匹配到这些信号时，结果按完成处理。这个规则有意保持简单、可审计。

## 配置与本地数据

| 路径 | 用途 | 权限 |
|---|---|---|
| `~/.codex/spoken-notify/settings.json` | 当前音效、音色和播报设置 | `0600` |
| `~/.codex/spoken-notify/speech-cache/` | 本地 AIFF 语音缓存 | `0700` 目录 / `0600` 文件 |
| `~/.codex/spoken-notify/state.json` | 已处理 turn ID，防止重复 | `0600` |
| `~/.codex/spoken-notify/events.jsonl` | 状态与时序记录 | 本机用户可读 |

事件日志不会保存完整 prompt 或 final response。任务标题会用于本机播报和诊断记录。

## CLI 参考

查看生效设置：

```bash
python3 "$HOME/.codex/hooks/codex_spoken_notify.py" --show-settings
```

打开设置 App：

```bash
python3 "$HOME/.codex/hooks/codex_spoken_notify.py" --setup
```

手动测试成功通知：

```bash
python3 "$HOME/.codex/hooks/codex_spoken_notify.py" \
  --test-title "交易系统任务" \
  --status success
```

手动测试需确认通知：

```bash
python3 "$HOME/.codex/hooks/codex_spoken_notify.py" \
  --test-title "电商系统任务" \
  --status attention
```

## 测试

```bash
python3 tests/test_codex_spoken_notify.py
swiftc -parse src/CodexNotificationSettings.swift
```

测试覆盖设置迁移、声音目录、状态分类、语音文案、缓存复用、权限、超时、
fallback、通知顺序、跨进程串行化和重复抑制。

## 卸载

```bash
./scripts/uninstall.sh
```

默认保留本地设置与缓存。如果也要删除：

```bash
./scripts/uninstall.sh --purge-settings
```

卸载后重启一次 Codex。安装前生成的 `config.toml.codex-jingle.*.bak` 备份会保留，
方便手动恢复此前的 callback。

## 项目结构

```text
codex-jingle/
├── assets/sounds/                    # Kenney CC0 音效与 provenance
├── screenshots/                      # README 视觉证据
├── scripts/
│   ├── install.sh                    # 本机编译并安装
│   └── uninstall.sh                  # 安全卸载
├── src/
│   ├── codex_spoken_notify.py        # Codex callback 与通知引擎
│   ├── CodexNotificationSettings.swift
│   └── CodexNotificationSettings-Info.plist
├── tests/test_codex_spoken_notify.py
├── LICENSE                           # 代码：MIT
└── README.md
```

## For AI Agents

本节面向需要自动安装、检查或调用 Codex Jingle 的 AI Agent。

### Capability Contract

```yaml
name: codex-jingle
version: 0.7.1
capability:
  summary: Play a local status sound and announce which Codex task completed.
  in: Codex agent-turn-complete JSON event
  out: serialized local sound followed by cached macOS speech
  fail:
    - "invalid or missing turn ID → ignore without speaking"
    - "enhanced voice unavailable → use Tingting fallback"
    - "concurrent completions → serialize under a local file lock"
    - "subagent completion → ignore and wait for the parent task"
    - "sound playback fails → continue to speech and record the result"
  adapters: [afplay, macOS-say]
install_command: ./scripts/install.sh
settings_command: python3 ~/.codex/hooks/codex_spoken_notify.py --show-settings
test_command: python3 tests/test_codex_spoken_notify.py
runtime_state: ~/.codex/spoken-notify/
```

### Agent 调用示例

```python
import json
import subprocess
from pathlib import Path

payload = {
    "type": "agent-turn-complete",
    "turn-id": "example-turn-001",
    "thread-id": "example-thread",
    "cwd": "/path/to/project",
    "last-assistant-message": "All tests passed.",
}

result = subprocess.run(
    [
        str(Path.home() / ".codex/hooks/codex_spoken_notify.py"),
        "--dry-run",
        json.dumps(payload),
    ],
    capture_output=True,
    text=True,
    check=True,
)
print(result.stdout)
```

Agent 在修改 `~/.codex/config.toml` 前，应保留原文件并提示用户：Codex 当前只会调用
配置中的 `notify` command，安装器因此会替换已有 callback，而不是静默并行执行两个。

## License

代码使用 [MIT License](./LICENSE)。`assets/sounds/` 中的 Kenney 音效使用
[CC0 1.0](./assets/sounds/LICENSE-CC0.txt)，来源、原始文件名与 SHA-256 保存在
[`manifest.json`](./assets/sounds/manifest.json)。

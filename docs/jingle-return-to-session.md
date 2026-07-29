# 回到会话

Jingle 的主按钮只读取 Work Unit 已保存的 `provider`、`session_id` 和 `cwd`，
不读取 prompt 或摘要原文。

- Codex：当前 CLI（0.146）支持 `codex resume <SESSION_ID>`。Jingle 在 Terminal
  中以 Work Unit 的 cwd 启动该命令；若 Terminal/CLI 启动失败，会打开 ChatGPT 的
  Codex 项目作为降级路径，并在卡片内说明。
- Claude：先通过 macOS Accessibility 查找窗口标题含 session id 或项目目录名的
  Terminal、iTerm2、Warp 窗口并置前。查找不到（包括未授予辅助功能权限）时，会把
  `claude --resume <SESSION_ID>` 放进剪贴板，并明确提示用户粘贴执行。若复制失败，
  卡片显示失败提示。

这两个路径都不会悄悄吞掉失败。终端焦点匹配是 best-effort：Jingle 不保存或扫描会话
正文，只匹配短暂的窗口元数据。

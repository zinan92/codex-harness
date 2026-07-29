# 回到会话

Jingle 的主按钮只读取 Work Unit 已保存的 `provider`、`session_id`、`cwd` 和短暂的
终端定位器（terminal app / TTY / session id / parent pid），不读取 prompt 或摘要原文。

- Codex：只在启动时保存的 Terminal TTY 仍存在时聚焦原终端；不能验证原窗口时，
  打开 ChatGPT 的 Codex 项目，并明确显示「已打开 Codex 项目（未定位原会话）」。它不再
  新开一个 `codex resume` Terminal 后把它误报成原会话。
- Claude：只按启动时保存的 Terminal TTY 置前，绝不按 cwd 或窗口标题猜测。查找不到
  （包括旧 Work Unit 没有定位器、未授予自动化权限或原窗口已关闭）时，把
  `claude --resume <SESSION_ID>` 放进剪贴板，并明确提示用户粘贴执行。若复制失败，卡片
  显示失败提示。

这两个路径都不会悄悄吞掉失败。旧 Work Unit 因为没有启动时的定位器会安全降级；新的
Work Unit 会沿父进程链记录终端 TTY，再以同一个 TTY 验证原窗口。Jingle 不保存或扫描
会话正文。

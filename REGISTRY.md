# Codex Jingle Registry

## 现在在哪里

Codex Jingle 已有原生 macOS 菜单栏 app 和本地通知回调。Codex 的 `UserPromptSubmit` 与 `Stop` hook 可将主任务落为本地 `running` / `blocked` / `done` Work Unit，且子 agent 不会单独入队。结束时会单次读取 Codex 历史 session，按累计快照起止差写入不可变 token 账本；运行态只有时长、没有 token。Claude 已从运行路径移除：历史账本保留，但不会影响菜单栏、声音、语音或呼叫卡。卡片先同步显示裸首行/“处理中…”，再由后台 DeepSeek worker patch 摘要；摘要失败保留弱标记，绝不影响状态判断。

菜单栏数字按实际渲染的项目卡计数：普通独立任务完成会入队、轻响且显示「已完成：」，卡住会入队、自动弹一张卡并语音显示「需要决定：」。`/go` workflow 内部完成与 `blocked_only` 项目完成保持静默；完成不会自动弹卡。项目别名合并、同 session 新状态覆盖旧状态和主任务/子 agent 抑制均已生效。面板为实色且只显示“该我了”的项目；每个项目只保留当前最高优先级的一张卡，因此菜单栏数字与面板项目卡数一致。回到会话只尝试精确聚焦原 Terminal TTY，未验证时明确失败，不创建项目、会话、终端或 resume 命令。状态文件与事件日志不保存 prompt 或 assistant 正文。

`projects.json` 同时是交互项目白名单：未映射 cwd 的完成只留账本、不计数字也不发声，未映射项目卡住仍会呼叫；空 cwd、根目录和相对路径不会创建可见 Work Unit。

可比较的 mockup：

- A. 极简监控条：最短路径查看所有运行中任务。
- B. 双员工桌面：用 Codex 与 Claude 的角色感强化完成汇报。
- C. 验收收件箱：把尚未检查的结果放在第一优先级。

## 下一步

注意力队列已按「含 blocked 优先，其余按等待最久优先」排序。呼叫卡与清算面板已共享 mockup 测量出的材质、圆角、颜色和项目人格；终态条目显示等待时间和本轮账，清算面板还会安静显示经 Codex thread 元数据确认的运行时长，既不计数也不主动弹出。同一 thread 的遗留 running 只显示一次；无最近 Codex 活动、已归档或元数据不可读的记录不显示，避免旧 `UserPromptSubmit` 永远冒充 running。共享 cwd 的未映射 thread 使用 session-index 的短名称（不读取 SQLite 原始 prompt title）。未映射的完成项在 UI 与账本迁移中均 fail-closed；历史记录未删除，只被标记为不参与 attention。菜单栏 App 现由用户 LaunchAgent 在登录与异常退出后恢复。

继续用真实 Codex hook 回合观察项目别名覆盖率、thread 活动窗口和 workflow marker 使用率；若需要让未映射项目的完成可见，先由用户显式加入别名表。只有在用户明确反馈需要时，才重新调整「完成轻响 / 卡住语音」的双声音默认。

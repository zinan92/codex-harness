# Codex Jingle Registry

## 现在在哪里

Codex Jingle 已有原生 macOS 菜单栏 app 和本地通知回调。Codex 的 `UserPromptSubmit` 与 `Stop` hook 可将主任务落为本地 `running` / `blocked` / `done` Work Unit，且子 agent 不会单独入队。结束时会单次读取 Codex 历史 session，按累计快照起止差写入不可变 token 账本；运行态只有时长、没有 token。Claude 已从运行路径移除：历史账本保留，但不会影响菜单栏、声音、语音或呼叫卡。卡片先同步显示裸首行/“处理中…”，再由后台 DeepSeek worker patch 摘要；摘要失败保留弱标记，绝不影响状态判断。

菜单栏数字按实际渲染的项目卡计数：普通独立任务完成会入队、轻响且显示「已完成：」，卡住会入队、自动弹一张卡并语音显示「需要决定：」。`/go` workflow 内部完成与 `blocked_only` 项目完成保持静默；完成不会自动弹卡。项目别名合并、同 session 新状态覆盖旧状态和主任务/子 agent 抑制均已生效。结算面板已按 A 式极简监控条重构为实色深色面板，所有数值都由同一份项目级投影计算：只纳入显式映射项目；任一 live session 存在时，项目只显示最新的「工作中」session 并压制其他 session 的旧 attention；没有 live session 时才可显示最高优先级检查卡。今日 token 只汇总这一范围内的已结算账本，运行中的 session 不估算 token。回到会话只尝试精确聚焦原 Terminal TTY，未验证时明确失败，不创建项目、会话、终端或 resume 命令。状态文件与事件日志不保存 prompt 或 assistant 正文。

`projects.json` 同时是菜单栏项目白名单：未映射 cwd 的完成与卡住均只留账本，不计数字、不进运行区、不进检查区、不参与 token 汇总，也不会触发活动探测；空 cwd、根目录和相对路径不会创建可见 Work Unit。

可比较的 mockup：

- A. 极简监控条：最短路径查看所有运行中任务。
- B. 双员工桌面：用 Codex 与 Claude 的角色感强化完成汇报。
- C. 验收收件箱：把尚未检查的结果放在第一优先级。

## 下一步

注意力队列已按「含 blocked 优先，其余按等待最久优先」排序，展示单位是 Codex 项目而非单条 session：只要同项目任一未归档 session 的 running Work Unit 尚未出现 transcript `task_complete`，该项目的所有旧 `done` / `blocked` 回合一律退出队列、呼叫和菜单栏数字，且运行区只保留最新的一条；被后续 `task_complete` 覆盖的旧回合也不会复活成待办。终态条目只会在项目没有 live session、且尚未被 session 级完成事件覆盖时显示等待时间和本轮账，因此不会把“本轮耗时”和“已等待”误呈为同一个正在跑的项目；SQLite UI 更新时间不用于结束长任务判断。`ignored_prefixes` 显式排除 Jingle 自身等不应监控的 cwd；未映射历史记录未删除，只被排除在用户可见投影之外。菜单栏 App 现由用户 LaunchAgent 在登录与异常退出后恢复。

继续用真实 Codex hook 回合观察 A 式监控条是否只显示用户正在工作的项目，尤其核对项目别名覆盖率、thread 活动窗口和 workflow marker 使用率；若需要让未映射项目的完成可见，先由用户显式加入别名表。只有在用户明确反馈需要时，才重新调整「完成轻响 / 卡住语音」的双声音默认。

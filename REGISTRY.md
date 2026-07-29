# Codex Jingle Registry

## 现在在哪里

Codex Jingle 已有原生 macOS 菜单栏 app 和本地通知回调。方向 D 的前四阶段已完成：Codex/Claude 的 `UserPromptSubmit` 与结束 hook 可将主任务落为本地 `running` / `blocked` / `done` Work Unit，且子 agent 不会单独入队。结束时会单次读取历史 session，按 provider 正确公式写入不可变 token 账本；运行态只有时长、没有 token。卡片先同步显示裸首行/“处理中…”，再由后台 DeepSeek worker patch 摘要；摘要失败保留弱标记，绝不影响状态判断。菜单栏在零待办时仅显示灰点，完成项静默入队，卡住项只呼叫一张卡；清算视图按「卡住了 / 做完了 / 还在跑」展示，项目人格用本地 cwd 前缀映射并保留 CX/CL 徽章。状态文件与事件日志不保存 prompt 或 assistant 正文；实际启用全局 hook 仍须用户按文档显式配置并信任。

可比较的 mockup：

- A. 极简监控条：最短路径查看所有运行中任务。
- B. 双员工桌面：用 Codex 与 Claude 的角色感强化完成汇报。
- C. 验收收件箱：把尚未检查的结果放在第一优先级。

## 下一步

真实 Codex/Claude hook 回合已验证并已恢复临时配置：两边的 `session_id` / `cwd` / `transcript_path` 都与适配器一致，Codex 另有 `turn_id`、Claude 没有。下一阶段实现并验证「回到会话」：Codex 指定 session 的 resume/项目 fallback，Claude 原终端聚焦/复制 resume 命令 fallback 与失败提示。

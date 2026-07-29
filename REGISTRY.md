# Codex Jingle Registry

## 现在在哪里

Codex Jingle 已有原生 macOS 设置 Widget 和本地通知回调。方向 D 的前两阶段已完成：Codex/Claude 的 `UserPromptSubmit` 与结束 hook 可将主任务落为本地 `running` / `blocked` / `done` Work Unit，且子 agent 不会单独入队。结束时会单次读取历史 session，按 provider 正确公式写入不可变 token 账本；运行态只有时长、没有 token。状态文件与事件日志不保存 prompt 或 assistant 正文；实际启用全局 hook 仍须用户按文档显式配置并信任。

可比较的 mockup：

- A. 极简监控条：最短路径查看所有运行中任务。
- B. 双员工桌面：用 Codex 与 Claude 的角色感强化完成汇报。
- C. 验收收件箱：把尚未检查的结果放在第一优先级。

## 下一步

下一阶段是卡片摘要：结束事件先用裸首行或“处理中…”立即出卡，再异步请求 DeepSeek 生成 ≤24 字摘要并 patch；摘要失败弱标记兜底，状态判定、声音与呼叫绝不能等待它。

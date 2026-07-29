# Codex Jingle Registry

## 现在在哪里

Codex Jingle 已有原生 macOS 设置 Widget 和本地通知回调。方向 D 的第 1 阶段已完成：Codex/Claude 的 `UserPromptSubmit` 与结束 hook 可将主任务落为本地 `running` / `blocked` / `done` Work Unit，且子 agent 不会单独入队。状态文件与事件日志不保存 prompt 或 assistant 正文；实际启用全局 hook 仍须用户按文档显式配置并信任。

可比较的 mockup：

- A. 极简监控条：最短路径查看所有运行中任务。
- B. 双员工桌面：用 Codex 与 Claude 的角色感强化完成汇报。
- C. 验收收件箱：把尚未检查的结果放在第一优先级。

## 下一步

方向 D 已获确认，下一阶段是 Work Unit 账本：只在结束时读取一次历史 session 数据，分别验证 Codex 的累计差值与 Claude 的增量求和；运行态继续只显示时长，不读取或展示 token。

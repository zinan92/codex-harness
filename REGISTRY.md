# Codex Jingle Registry

## 现在在哪里

Codex Jingle 已有原生 macOS 菜单栏 app 和本地通知回调。方向 D 的前四阶段已完成：Codex/Claude 的 `UserPromptSubmit` 与结束 hook 可将主任务落为本地 `running` / `blocked` / `done` Work Unit，且子 agent 不会单独入队。结束时会单次读取历史 session，按 provider 正确公式写入不可变 token 账本；运行态只有时长、没有 token。卡片先同步显示裸首行/“处理中…”，再由后台 DeepSeek worker patch 摘要；摘要失败保留弱标记，绝不影响状态判断。菜单栏在零待办时仅显示灰点，完成项静默入队，卡住项只呼叫一张卡；清算视图按「卡住了 / 做完了 / 还在跑」展示，项目人格用本地 cwd 前缀映射并保留 CX/CL 徽章。状态文件与事件日志不保存 prompt 或 assistant 正文；实际启用全局 hook 仍须用户按文档显式配置并信任。

可比较的 mockup：

- A. 极简监控条：最短路径查看所有运行中任务。
- B. 双员工桌面：用 Codex 与 Claude 的角色感强化完成汇报。
- C. 验收收件箱：把尚未检查的结果放在第一优先级。

## 下一步

方向 D 已完成：真实 Codex/Claude hook 回合验证过两边的 `session_id` / `cwd` / `transcript_path` 与适配器一致（Codex 另有 `turn_id`、Claude 没有）。Story 1 已将呼叫/清算呈现改为屏幕内 clamp 的临时 panel，并以真实桌面 fixture 验收。Story 2 将会话返回改为启动时记录的终端 TTY 精确匹配：Terminal 会话只能命中原 TTY；没有该定位器的桌面会话安全降级为「未定位原会话」，Codex 打开项目、Claude 复制 resume 命令，绝不再把新 Terminal 或同 cwd 窗口误称为原会话。生命周期结束后两边都复用同一把本地 at-most-once 声音锁：做完只轻响，卡住才轻响并说话。Park 已批准 V2 项目级注意力路由；接下来按 `docs/jingle-v2-stories.md` 的 Story 3–6 继续逐项替换 turn 级队列，每项独立验证、PR 与合并。

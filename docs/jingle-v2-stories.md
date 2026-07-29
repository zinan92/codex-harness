# Jingle V2 · 项目级注意力路由合同

> 状态：待 Park 审核。本文只定义行为合同，不改变现有 hook、队列或 UI。

## 北极星

Jingle 的数字等于 **Park 现在需要回去处理的项目组数**，不等于模型完成过的
turn 数、token 账本行数或 session 历史数。每一项都必须把 Park 带回一个正确的
会话；不能做到，就不能把它显示成“已跳转”。

## 术语与不变量

| 术语 | 定义 |
|---|---|
| 项目（Project） | 用户认知的工作对象，例如「网格交易」；由本地别名表映射，不从 provider 或 cwd basename 猜。 |
| 会话（Thread） | 一个 provider + session_id；它是可跳转目标。 |
| 任务边界（Task envelope） | 一个独立任务，或一个 `/go` 这类 workflow 的整体；不是每一个模型 turn。 |
| 项目组（Attention group） | 同一 Project 的一个或多个 Thread 的当前摘要；它是菜单栏计数单位。 |

不变量：

1. 每个 Thread 同时至多有一个当前任务边界；新边界的终态覆盖它的旧终态。
2. 每个 Project 同时至多显示一个项目组；provider 只作为该组里的 CX/CL 子会话标识。
3. 账本保留所有 Work Unit，注意力队列只保留当前可行动状态；二者绝不能再混用。
4. 未映射 cwd 不自动与其它项目合并；宁可单列「未映射项目」，不能错并。
5. 任何降级跳转必须显式标为降级，不能显示“已跳转”。

## Story 1 · 屏幕安全的呈现层

作为 Park，我无论菜单栏项位于哪一块屏幕、哪一个边缘，都能完整看到 Jingle 卡片，
不会出现一半在屏幕外的 popover。

实现边界：呼叫卡和清算卡不再依赖 AppKit 对 `NSPopover` 边缘的猜测。它们由一个
临时、无 Dock 图标的 `NSPanel` 承载；位置以状态栏项所在屏幕的 `visibleFrame` 为
边界计算并 clamp。零待办时 panel 不存在；呼叫结束、已看或切换其它 app 后关闭。

成功标准：

- 在主屏幕和外接屏、状态栏项靠左/中/右的 fixture 中，卡片 frame 100% 位于
  `visibleFrame` 内，四条边均无裁切。
- 没有空间放完整高度时，卡片改为受限高度并内部滚动，而不是改到屏幕外。
- 自动呼叫与手动清算共用同一定位器；测试不能只覆盖其中一个。
- 0 待办时没有 panel、Dock 图标或常驻窗口。

## Story 2 · 可验证地回到正确会话

作为 Park，点击“回到会话”后，我要么进入原来的那个 Codex/Claude 会话窗口，要么看到
真实的降级动作和原因；不能新开一个无关的终端后却提示成功。

实现边界：在任务边界开始时捕获可验证的会话定位 metadata（provider、session_id、
cwd、启动它的 terminal process/window identity）。返回动作按下列顺序执行：

1. 发现并前置仍存在的原窗口，验证窗口/进程与保存 identity 一致；
2. provider 的指定-session 官方入口；
3. 明确降级：Claude 复制精确 resume 命令，Codex 打开项目并标明“未定位到原会话”。

成功标准：

- 对两个同时运行、同 cwd 的 Claude 会话，点击 A 只能前置 A，不得前置 B。
- 对 Codex/Claude 各一条真实会话，验收证据同时含 session id、被前置窗口 identity、
  可见前台窗口截图；不能仅以 Process 成功启动为证据。
- 原窗口已关闭时，UI 显示 `已复制 resume 命令` / `已打开项目（未定位原会话）`，
  不能显示“已跳转”。
- 所有 provider 的 fallback 都可单测；窗口定位失败不能吞掉错误。

## Story 3 · 项目别名与跨 provider 聚合

作为 Park，我看到的是「网格交易」「TokenRouter」等项目，而不是 `tokenrouter`、
`token router`、`产品网格交互`、`网格交易` 被拆成互不相干的卡片。

本地 `projects.json` 升级为显式表：`project_id`、展示名、颜色、每个 provider 的 cwd
前缀/别名。一个 Project 可包含多个 Codex/Claude Thread；组内保留子状态和各自的
“回到会话”入口。未配置别名的项目不参与跨 provider 合并。

成功标准：

- 映射表可将 `tokenrouter` 与 `token router` 合并为一个项目组，并同时显示 CX/CL
  子会话状态。
- 两个未映射但 basename 相同的 cwd 不会被错误合并。
- 项目组标题永远是配置展示名；provider 永远只是 badge，不是项目身份。
- 菜单栏数字等于可行动项目组数，而不是 Work Unit 数；同一项目的 CX/CL 两条会话
  最多算一个组。

## Story 4 · 新状态覆盖旧状态

作为 Park，同一会话开始第二个任务后，我只看到该会话最新、仍需处理的结果；旧完成项
仍在账本里，但不再占用我的通知队列。

成功标准：

- 同一 provider + session 连续完成 5 个独立 turn，账本保留 5 条 Work Unit，
  注意力队列最多保留该 session 的 1 条当前状态。
- 第 2 个任务开始后，第 1 个任务若未看自动被 supersede；菜单栏计数不增加。
- `已看` 只确认当前项目组/当前会话摘要，不删除账本或 token 数据。
- 项目组里有多个 provider 时，某一 provider 的新状态只覆盖该 provider 子会话，
  不覆盖另一 provider 的进行中任务。

## Story 5 · `/go` 与独立任务的通知边界

作为 Park，我希望一个独立任务结束时得到一次结果；但 `/go` 多步骤 workflow 的子步骤
完成不能逐个打断我，只在 workflow 整体完成或真正卡住时出现。

实现边界：任务边界必须有确定性来源，不能让 LLM 猜。先抓一次真实 `/go` 的生命周期
事件与 session transcript shape；若 CLI 不提供 workflow-finished 语义，则由 `/go` wrapper
显式写入本地 `workflow_started` / `workflow_finished` marker。普通任务默认是独立边界。

成功标准：

- 一次真实或录制的 `/go` 产生 N 个内部 turn 时，菜单栏不产生 N 个完成项；整条
  workflow 最多产生一个最终 `done` 或一个 `blocked` 项。
- workflow 中途需要 Park 决定时，立即产生一个 blocked 项并指出当前问题；其余子步骤
  保持静默。
- 普通独立任务完成后仍产生一次结果，不能因为聚合而丢失。
- 子 agent、teammate、内部工作流子步骤均不直接入队、不直接发声。

## Story 6 · 明确的通知策略表

作为 Park，我可以为每个项目/任务边界声明“什么时候值得打断我”，而不是让所有完成
事件平等地抢注意力。

初始策略只有三种，禁止新增第四种状态或第三种声音：

| 策略 | done | blocked | 适用 |
|---|---|---|---|
| `task_terminal` | 静默入项目组 | 呼叫 + 语音 | 普通独立任务（默认） |
| `workflow_terminal` | 仅 workflow 终态入组 | workflow 中途 blocked 立即呼叫 | `/go` 等多步骤流程 |
| `blocked_only` | 不入组 | 呼叫 + 语音 | 只关心人工决策的后台项目 |

成功标准：

- `workflow_terminal` 的 N 个子完成不会改变菜单栏数字；最终完成只加一。
- `blocked_only` 的完成没有数字、没有声音、没有卡片；blocked 仍按既有两声音规则呼叫。
- 默认策略、项目覆盖策略、未映射项目的 fail-closed 策略都有 fixture 测试。
- 策略命中原因写入元数据事件日志，但不写 prompt、assistant 正文或 DeepSeek 输入。

## 非目标

- 不把 token 账本变成实时监控或跑飞告警。
- 不用 LLM 判断 done/blocked 或猜 `/go` 是否结束。
- 不强行把未映射的 Codex/Claude 项目合并。
- 不让 provider 名称取代项目身份。
- 不删除历史 Work Unit、token 账本或既有 session。

## 交付顺序与验收闸门

1. **Story 1**：屏幕安全 panel，先以真实多屏截图验收。
2. **Story 2**：会话定位元数据与真实窗口跳转证据；未通过前不把 fallback 文案称为跳转。
3. **Story 3–4**：项目别名、项目组、会话最新状态覆盖；用当前 21 条历史状态回放，
   验证计数收敛到当前项目组数。
4. **Story 5–6**：先录制 `/go`，再接显式 workflow marker 与策略表；真实 `/go` 只允许
   一个最终通知。

每一项独立 issue / branch / PR / 合并。下一项必须以本项的真实验收证据为起点，不允许
把多个故事打成一个大 PR。

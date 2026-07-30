# Jingle 菜单栏

安装后的 `Codex 通知设置.app` 是菜单栏常驻 app：它不创建 Dock 图标或常驻
窗口。菜单栏数字是当前可行动的**项目组**数量，而非 Work Unit 数；只有可呼叫的
「卡住了」会自动展开单张卡片。

项目人格从 `~/.codex/jingle/projects.json` 读取。每个项目必须有显式 `project_id`
和 Codex cwd aliases。文件首次安装时由
`assets/jingle-projects.json` 初始化、之后绝不覆盖。未匹配 cwd 使用完整路径作为
内部 identity，只显示 basename，因此两个同名目录绝不会被自动合并。示例：

```json
{"projects":[{"project_id":"research","name":"投研面板","color":"blue","aliases":[{"provider":"codex","prefix":"/Users/me/work/research"}]}]}
```

`color` 可选值为 `blue`、`orange`、`green`、`red`。同一 provider + session 的新任务
开始时会 supersede 它尚未看的旧终态；账本、时长、token 均保留。菜单栏的「已看」
保留账本，只从当前清算队列移除；「10 分钟后再喊我」只压住该一张呼叫卡，到点重新呼叫。

Jingle 的展示单位是 Codex session，而不是单个 Work Unit。若本机 metadata 证明某 session 未归档且最近两分钟仍有活动，它只会安静地显示一次「工作中」：同 session 所有旧 `done` / `blocked` 记录都会退出清算队列、自动呼叫和菜单数字。只有 session 已不活动且元数据读取成功时，最后一个终态才可能进入「等你」。因此不会把一个长任务同时显示成“仍在跑”和“等你决定”。同一 thread 的多条遗留 running 记录只显示一次。若 cwd 是共享目录且没有显式项目 alias，Jingle 只使用 Codex session-index 的短名称作临时标签，绝不读取或持久化 SQLite 中常为原始 prompt 的 `title`。`ignored_prefixes` 可显式排除 Jingle 自身等不应监控的 cwd。

开发时可用 `JINGLE_STATE_PATH` 和 `JINGLE_PROJECTS_PATH` 指向 fixture，不会读写
真实的 `~/.codex/jingle/` 状态。

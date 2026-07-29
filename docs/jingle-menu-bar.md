# Jingle 菜单栏

安装后的 `Codex 通知设置.app` 是菜单栏常驻 app：它不创建 Dock 图标或常驻
窗口。菜单栏数字是未清算的「卡住了」和「做完了」数量；只有可呼叫的「卡住了」
会自动展开单张卡片。

项目人格从 `~/.codex/jingle/projects.json` 读取，最长前缀优先。文件可选；没
有匹配时使用 Work Unit 的 `cwd` 目录名。示例：

```json
{"projects":[{"prefix":"/Users/me/work/research","name":"投研面板","color":"blue"}]}
```

`color` 可选值为 `blue`、`orange`、`green`、`red`。菜单栏的「已看」保留账本，
只从清算队列移除；「10 分钟后再喊我」只压住该一张呼叫卡，到点重新呼叫。

开发时可用 `JINGLE_STATE_PATH` 和 `JINGLE_PROJECTS_PATH` 指向 fixture，不会读写
真实的 `~/.codex/jingle/` 状态。

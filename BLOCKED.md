# Blocked · 待你拍板

本文件只放**需要人判断**的事。能自动验证的缺陷一律直接修，不进这里。

## 本轮（2026-07-29 · Story 提交边界 + workspace 机器闸自动发现）

无。

## 待决

## 需要你动手的事（不是阻塞，是权限所在）

- **TradingView Advanced Charts 申请**（内容制作项目）：表单要求签署 License Agreement PDF
  并填写公司邮箱／电话／注册地——只能你本人完成。见 `status/内容制作.json`。
（原「旧仓库是否删除」已于 2026-07-29 处理：核验为本仓超集后删除，
桌面留有 `tokenrouter-old-repo-backup-20260729.tar.gz` 备份。）

## 已解决

- ~~B3 complex 的 story 提交边界失败（2026-07-29）~~：原真实失败收据
  `run-20260729T030604Z-86ed3383` 保留不改写。新增真实 complex 收据
  `run-20260729T052338Z-c4cb166e` 已以四条独立提交成功验证硬提交边界：`8e608a1`、`6caa6d0`、
  `0ec5edc`、`2ca2f59` 分别只包含各自 story 的源文件和测试文件，四次机器闸及 Opus 审核均通过。

- ~~Task 0 质量闸无法全绿（2026-07-29）~~：本次动工前及最终均已实际运行
  `bash scripts/check.sh`，退出码 0；`snapshots/` 未被此任务修改。

- ~~裸命令 `tr "..."` 的安装位置（2026-07-29）~~：不安装；系统命令冲突已按任务决定处理完毕。

- ~~受保护文件核验：仓库根不存在 `ARCHITECTURE.md` 与 `workbench.html`，
  `git diff --exit-code ARCHITECTURE.md workbench.html` 报 `fatal: ambiguous argument`。~~
  **已解决（2026-07-28）**：根因是账本最初建在 `~/Documents/tokenrouter`（另一个空仓库），
  而这两份文件在 `~/tokenrouter`。两仓已合并，现同处一仓，
  `git diff --exit-code -- ARCHITECTURE.md workbench.html` 正常返回 0。

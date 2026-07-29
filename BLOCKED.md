# Blocked · 待你拍板

本文件只放**需要人判断**的事。能自动验证的缺陷一律直接修，不进这里。

## 待决

- **Task 0 质量闸无法全绿（2026-07-29）**：开始执行前，工作树已有
  `snapshots/2026-07-29.json` 未提交改动，导致 `bash scripts/check.sh` 的「工作树干净」项失败。
  `snapshots/` 是本任务明令禁止修改的路径；未清理、未提交、未改写该文件。需要拥有该改动的人处理后再重跑全闸。

- **裸命令 `tr "..."` 的安装位置（2026-07-29）**：仓库写入边界只允许 `router/` 和三份根文档；将
  `tr` 安装到 PATH（例如 `~/bin`）需要写仓外文件，且会与系统的文本转换命令 `tr` 同名。本轮只能交付
  `./router/tr "..."` / `python3 -m router "..."`；如需裸命令，需你指定一个安全的 PATH 安装方案。

## 需要你动手的事（不是阻塞，是权限所在）

- **TradingView Advanced Charts 申请**（内容制作项目）：表单要求签署 License Agreement PDF
  并填写公司邮箱／电话／注册地——只能你本人完成。见 `status/内容制作.json`。
（原「旧仓库是否删除」已于 2026-07-29 处理：核验为本仓超集后删除，
桌面留有 `tokenrouter-old-repo-backup-20260729.tar.gz` 备份。）

## 已解决

- ~~受保护文件核验：仓库根不存在 `ARCHITECTURE.md` 与 `workbench.html`，
  `git diff --exit-code ARCHITECTURE.md workbench.html` 报 `fatal: ambiguous argument`。~~
  **已解决（2026-07-28）**：根因是账本最初建在 `~/Documents/tokenrouter`（另一个空仓库），
  而这两份文件在 `~/tokenrouter`。两仓已合并，现同处一仓，
  `git diff --exit-code -- ARCHITECTURE.md workbench.html` 正常返回 0。

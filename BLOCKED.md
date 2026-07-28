# Blocked · 待你拍板

本文件只放**需要人判断**的事。能自动验证的缺陷一律直接修，不进这里。

## 待决

（无）

## 需要你动手的事（不是阻塞，是权限所在）

- **TradingView Advanced Charts 申请**（内容制作项目）：表单要求签署 License Agreement PDF
  并填写公司邮箱／电话／注册地——只能你本人完成。见 `status/内容制作.json`。
- **`~/Documents/tokenrouter` 旧仓库**：内容已全部迁入本仓，是否删除等你确认。

## 已解决

- ~~受保护文件核验：仓库根不存在 `ARCHITECTURE.md` 与 `workbench.html`，
  `git diff --exit-code ARCHITECTURE.md workbench.html` 报 `fatal: ambiguous argument`。~~
  **已解决（2026-07-28）**：根因是账本最初建在 `~/Documents/tokenrouter`（另一个空仓库），
  而这两份文件在 `~/tokenrouter`。两仓已合并，现同处一仓，
  `git diff --exit-code -- ARCHITECTURE.md workbench.html` 正常返回 0。

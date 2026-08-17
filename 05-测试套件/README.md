# 05-测试套件 — 说明（重要）

> ⚠️ **本目录不是自动化回归测试套件**，请勿与仓库根的 `tests/` 混淆。

## 这是什么
- 这里是 **After Effects 手工验证夹具**：一组 `.jsx`（需在已打开的 AE 内运行）+ `.js`（Node 辅助脚本，多为提示文本）+ 报告 `.md` / `.json`。
- 用于人工验证 MCP 桥接操作（建合成、导入素材等），**无法在 CI / headless 环境自动执行**，依赖人工在 AE 面板点选运行。
- 多份报告已自注为"历史文档 / 当前走 pytest 体系"。

## 真实的自动化测试在哪里
- **Python 回归测试**：仓库根 `tests/` + `puppet-automation/tests/`（pytest，由 `.github/workflows/ci.yml` 自动运行）。
- **代码质量门禁**：`.github/workflows/ci.yml`（flake8 / 覆盖率 / 秘密扫描 / JSX 语法门）+ 本地 `.pre-commit-config.yaml`。
- 审查标准与流程：`02-开发文档/代码审查标准与流程.md`。

## 为什么保留原位（不归档）
- `phase7-media-tools/README.md` 与 `QUICKSTART.md` 仍引用本目录的 `Phase7_Test_Import.jsx` 等夹具，用于 AE 内手动验证。
- `.gitignore` 已将 `archive/` 整体忽略，移动会使文件脱离版本控制。
- 故本目录**保留**，仅作澄清。

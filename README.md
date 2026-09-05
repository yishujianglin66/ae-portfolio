# MasterCut · 母版工坊

> 原名 **AE-Knowledge-Vault**。磁盘目录名保持 `AE-Knowledge-Vault` 不变（数百处配置/脚本/文档硬编码绝对路径依赖），品牌口径以 MasterCut 为准。

## 定位

一条 **"母版精修 → 规则蒸馏 → 管线记忆"** 的风格化剪辑工作台：

1. **母版精修** —— 把一部作品当母版，用"统一编排入口 + AE 镜头级精修"打磨到大师级；
2. **规则蒸馏** —— 每轮验收通过的剪辑规则（铁律变速分档、kick/snare 鼓点→运镜映射、切点可见性标准、速度曲线锚、效果剂量）当场固化回编排决策；
3. **管线记忆** —— 规则沉淀于 `data/evolution/render_history.jsonl` 与配方卡，走向"母版生规则、规则生自动出片"。

## 当前状态（2026-09-05）

- **主线**：母版 run53（30s 洛天依燃向 AMV），`unified_edit.py` 出片 + AE 精修已迭代 v2→v7，质量闸门 7/7，等用户验收速度曲线版后向全部变速镜头推广。
- **工程平台**：五层架构（感知→理解→规划→执行→反馈）真实运转，历史 53 次 unified run 全链报告在 `output/`；测试套件 5,305 passed / 0 failed / 0 errors（08-27）。
- **量化对标**：`scripts/score_reference_gap.py` 将成片与 `data/reference_top/` 13 条顶尖 AMV 参照做同口径评分（切点踩拍 81%±80ms、beat_hit_rate 0.77）。

## 文档导航

| 入口 | 内容 |
|------|------|
| [01-项目概览/📋-项目概览-MOC.md](01-项目概览/📋-项目概览-MOC.md) | 项目总览、主线与工程平台层结构 |
| [🏠-AE知识中心.md](🏠-AE知识中心.md) | 知识体系全景（10-15 号知识库，891 篇 md / 约 1700 万字符） |
| [TASK_STATUS.md](TASK_STATUS.md) | 工程平台任务看板（08-31 后冻结，视频主线见下） |
| [docs/handoff-2026-09-05-sync.md](docs/handoff-2026-09-05-sync.md) | 最新交接文档（视频主线权威进度，系列含 09-01~09-05） |
| [00-每日记录/](00-每日记录/) | 2026-07-20 起的开发日志 |
| [02-开发文档/](02-开发文档/) | 开发手册、用户手册、编码规范 |

## 核心入口

- 出片：`python scripts/unified_edit.py --bgm <BGM> --duration 30 --tag <tag>`
- 精修：`scripts/build_master_polish.py`（AE 镜头级 MASTER 合成）
- 评分：`scripts/score_reference_gap.py`（参照集同口径评分）
- 经验采集：`scripts/harvest_experience.py` → `data/evolution/render_history.jsonl`
- 工程平台：`ae_agent_pipeline.py`（pyproject 注册入口）、`api_server.py`（FastAPI）

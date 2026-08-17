# 八轮审计升级累计状态（2026-08-14）

> 从最初"重新审核和评估 + 全网调研 + 迭代升级"请求起，共 9 轮（审计 1 轮 +
> 移交清单推进 8 轮）。本文件为最终累计状态，供后续会话与人类决策使用。

## 一、分报告索引（全部落盘 docs/research/）

| 文件 | 内容 |
|---|---|
| 2026-08-14-audit-summary-report.md | 总审计 + 升级实施（第 1 轮） |
| 2026-08-14-audit-{core-code,tests,knowledge}.md | 3 路本地深审 |
| 2026-08-14-audit-web-{datasets,tools,knowledge}.md | 3 路全网调研 |
| 2026-08-14-round{2..8}-progress.md | 移交清单推进报告 ×7 |
| 2026-08-14-cep-uxp-migration.md | CEP→UXP 迁移评估 |

## 二、能力升级全景

### 感知层
- **GPU 全线激活**：torch 2.13.0+cu126（RTX 4060 首次可用，此前全 CPU）
- **VideoMAE 运镜级联**：kandinsky-large（18 类，高精度）→ gullalc base（5 类）
  → 光流规则；A/B 实证 base 版 68% 素材误标 pan_left；帧补齐修复张量失配
- **W6 氛围闭环**：ToriiGate-2B（Apache-2.0）标注 65 素材（41+7 有效），
  质量门/纠错重试/英文词表；接入 production 报告 attribution
- **BeatNet 三层信号**：节拍/下拍/拍号 + rhythm_fusion 双网格调和
  （真实 BGM tempo 差 0.6% 互证）；use_beatnet 旗标端到端验证
- **素材三源画像**：content(deepghs) + atmosphere(ToriiGate) + camera
  统一画像 64 素材，驱动选材（教程录屏排除 + 燃向主题氛围排序）

### 决策层
- **运镜反锁死**：suggest_camera_for_shot 反锁死窗口 + 导演 recent 跟踪 +
  visual_variance≥7 池轮转；真机 build 段 23/23 pan_left → 7-8 种均衡
- **8 卡风格谱系**：amv/cyberpunk/hardcore/cinematic/ambient/emotional/
  vintage/high_key 全部真机或决策级验证，旋钮→运镜传导单调成立，
  反默认违规全零；26 用例 0.4s CI 冒烟
- **品味契约去误报**：反默认检查器限定"可变化转场"范围（爆发硬切/
  变速硬切为设计约束）
- **KB 效果白名单**：1026 条 KB 映射丢弃 862 条垃圾，199 条干净保留

### 工程层
- **4 个上帝文件拆分**：kb_scanner 2691→744、llm_gateway 4607→4028、
  unified_pipeline 5824→5140、全部 A/B 语义等价验证
- **registry 双体系统一**：sync_from_inventory 桥接 + 稳定默认路径 +
  3 训练脚本接线
- **D-13/15/24 修复**：轮询全局名唯一化、PS/PR/AU 脱离废弃继承链、
  10 个 JSX 入口四级路径解析
- **测试工程**：覆盖率 77.58% 实测（fail_under=60 从纸面变真实）、
  68 伪测试迁移（收集 170s→68s）、error_diagnostician/flagship/trainer/
  fusion/taxonomy 等 100+ 新用例

### 环境/数据
- python 入 PATH；transformers/safetensors/accelerate 补齐；
  Dockerfile 静态校验通过（Docker 未安装，环境级阻塞）
- model_registry 修正（13 条、smoke 伪值置 null、VideoMAE/ToriiGate 登记）

## 三、与并发会话的协作

仓库有另一 AI 会话并行工作（Step4 动漫数据集、抠像、LLM 路由等）。
期间发生 2 次仓库重置/rebase（我方未提交文件曾丢失并已全部重建），
此后双方提交节奏稳定互补；我方修复（KB 注入/tool_executor import）经
多轮核验持续幸存。对方已提交"多 Agent 协作隔离约定"文档。

## 四、剩余项（需人工/外部依赖/大工程）

| 项 | 性质 |
|---|---|
| UnifiedPipeline 主类继续分区（_run_execute_real_mix 545 行等） | 可按 _run_verify 模式继续 |
| 画像驱动选材深化（content 标签进 IP 匹配/叙事角色） | 中等工程 |
| UXP 面板骨架 | 需 UXP Developer Tool |
| Docker 容器化验证 | 需 Docker Desktop + WSL2 |
| 前端剩余组件 mock 收敛（已大部分完成） | 小 |
| capability_registry 冷启动清理 | 并发会话维护中，暂缓 |

## 五、回归基线（2026-08-14 round-10 更新）

- **全量回归：4952 passed / 0 failed / 9 skipped**（5 分 20 秒，默认 marker
  排除 148 个真实执行/慢测试）——标记债务已修复，全量绿跑达成 ✅
- **定向套件（9 轮累计 400+ 用例全绿）**：gateway 83 / pipeline 84 /
  KB 96 / camera+taste 87 / fusion+taxonomy+registry 22 / 风格矩阵 26 /
  诊断器 12 / flagship 10 等。
- **核心模块覆盖率**：77.58%（taste 97% / style_card 92% /
  camera_decision 86% / error_diagnostician 78%）。
- **真实管线**：v23 多次跑通，quality 79.6 → 81.3，风格卡全谱系零违规。
- **标记修复内容**：17 个真实执行文件补 real_e2e/integration 模块标记、
  4 个自管理文件撤销误标、2 个纯单元测试文件撤销误标、
  诊断器测试 asyncio.run 修复。

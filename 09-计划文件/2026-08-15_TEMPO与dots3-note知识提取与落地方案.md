# TEMPO / dots3-note 知识提取与落地方案

> 来源：小红书 dots 实验室开源项目 dots3-note preview（2026-08-14 发布）及配套技术文章
> 仓库：github.com/studio-dots-ai/dots3-note-prev（Apache 2.0）
> 权重：HuggingFace `dots-studio/dots3-note-prev` / ModelScope 同名
> 整理日期：2026-08-15
> 目的：系统性提取对 AE-Knowledge-Vault 项目有帮助的理念、机制与工程方法，并给出可落地映射
> 扩展：本方案的 P0/P1 任务已并入《2026-08-15_开源生态调研与实验室级推进集成方案.md》的 Lab Phase 0~2 路线图，并叠加 Kimi K3 / OpenHands / Argus 等 12 项机制增强

---

## 一、核心能力与关键技术点

### 1.1 模型本体（dots3-note preview）

| 属性 | 值 | 对本项目的意义 |
|------|------|------|
| 架构 | 多模态 MoE，280B 总参 / 16B 激活 | 轻量旗舰，API 调用成本可控 |
| 上下文 | 512K tokens | 可一次装入完整管线 manifest + 知识库上下文 |
| 输入 | 文本/图像/视频/音频（视频含音轨） | **可直接输入渲染产物视频做质量自评** |
| 视觉编码器 | MoE ViT 7B / 激活 1.2B | 帧级视觉理解能力 |
| 注意力 | 13 DSA + 33 SWA（~1:3 混合） | 长上下文效率设计，可作架构知识条目 |
| 推理开关 | `enable_thinking` 参数 | 快答/深推理双模式，自评调用可按需切换 |
| 工具调用 | `--tool-call-parser dots`（OpenAI 兼容） | 可无缝接入现有 llm_gateway |

### 1.2 TEMPO 训练方法（核心贡献）

**全称**：Test-time-scaled Value Estimation with Macro-step Policy Optimization

解决的问题：长轨迹强化学习中「**评价跟不上行动**」——传统 GRPO 只能等轨迹结束拿终局奖励，信号来得太晚，导致任务后半程得分停滞。

机制拆解（四个可迁移要素）：

1. **Macro-step 切分**：把几十小时的长轨迹切成多个宏步，每个宏步含多轮模型-环境交互
2. **Actor/Critic 角色切换**：宏步结束时同一模型从执行者切换为评价者
3. **Test-time scaling 估值**：critic 通过推理 + 工具调用 + 多次采样，估计当前状态的**预期剩余回报**
4. **未完成轨迹的训练信号**：中途估值变成尚未走完轨迹的学习信号——**失败/中断的轨迹也能产出训练价值**

实测效果：任务前半程 TEMPO 与 GRPO 无差异，**进入深水区后 GRPO 停滞、TEMPO 持续提升**。

### 1.3 Self-Critiquing（自我评价）

- **训练侧**：为长 rollout 中间状态提供密集的过程奖励信号
- **推理侧**：形成「观察 → 评价 → 重规划 → 行动 → 再评价」的持续循环（类 Harness 循环）
- **关键涌现能力**：即使任务未解出，也能从两个表面相似的中间状态中判断**哪个更有希望突破**（IMO 满分即靠"边生成证明、边工具检查、边修改"实现）
- **未来方向**：递归自我评价（recursive self-critiquing）——在无清晰外部奖励的开放任务中自我判断进展、调整记忆与规划

### 1.4 主动记忆与长程适应

- 构建**数千个不依赖先验知识的超长程新颖环境**做 RL 训练
- 任务长度超过上下文窗口时，模型学会**主动保留对后续有用的信息**（ARC-AGI 3 验证）

### 1.5 评测方法论（VibeBench 双基准）

| 基准 | 考察问题 | 设计要点 |
|------|------|------|
| VibeSearchBench | 需求没说清时，Agent 能否弄明白用户要什么 | 20 领域 200 任务，模拟真实用户多轮逐步补充需求与约束 |
| VibeLifeBench | 外部条件变化后，Agent 能否跟得住 | 10 领域 20 任务，每任务 20-30 阶段，**1247 项 atomic checks**（状态一致性/工具正确执行/最终交付物） |

关键结论：**Claude Opus 5 / GPT-5.5 均未达及格线**——单点能力强 ≠ 长程稳定执行。

---

## 二、对本项目有直接帮助的理念与机制

### 2.1 「中途自评」理念 → 直击本项目最大缺口

本项目现状：质量评价集中在**末端**——
- QG-1~QG-5 只在 S7 执行（`core/quality_gate.py`）
- parameter_optimizer 只在管线成功后的 `_post_execution_hook` 写反馈
- 数据回流（FlagshipManifestParser）也只解析已完成 run 的 manifest

这与 TEMPO 批判的「等终局反馈」模式完全同构。后果：S3 黑帧、帧亮度方差为 0 等问题，要跑完 S4/S5/S6 全部昂贵阶段后才在 S7 暴露——**浪费的是真实渲染时间**。

### 2.2 「未完成轨迹也有训练价值」→ 失败 run 的数据回流

当前失败即停（flagship_runner 设计原则），失败 run 的中间产物信息基本不进 ExperienceRecord。TEMPO 证明：**中途估值本身就可作为学习信号**。本项目已有数字孪生 Beta 分布校正机制（ExecutionObservation → StagePredictor alpha/beta 更新），只缺「中途观测」的写入点。

### 2.3 「哪个中间状态更有希望」→ 质量迭代候选比较

`PipelineConfig.max_quality_iterations=3` 已有迭代框架，但当前是串行重试。可借鉴 Self-Critiquing 的比较判断能力：**生成多个候选 → 轻量自评排序 → 只把最有希望的推进到昂贵阶段**。

### 2.4 atomic checks 评测方法 → 质量门粒度升级

VibeLifeBench 的 1247 项 atomic checks 思路：把"通过/不通过"的粗粒度验收，拆成**可独立判定、可定位、可统计**的原子检查项。本项目 QG-1~QG-5 是 5 个粗粒度门，拆分后能精确定位"哪个原子项失败、在哪个阶段引入"。

### 2.5 模糊需求评测 → 剪辑需求本质就是模糊需求

用户说"做个高燃混剪"正是 VibeSearchBench 考察的场景（多轮逐步补充约束）。所有头部模型在此不及格，说明**短期内靠外部知识约束比指望模型自己想清楚更可靠**——本项目 10-风格化剪辑知识库 / 11-大师知识库恰好是现成的约束注入源。

### 2.6 工程部署知识（参考价值）

- FP8 权重 + SGLang/vLLM 单节点 8 卡部署配方、MTP 投机解码（NEXTN，TPOT 降 50%+）
- DSA+SWA 混合注意力、top-8 路由 256 专家等架构细节
- 本机无多卡 GPU，暂不自部署；**走 ModelScope/百炼 API 接入**（与现有 llm_gateway 兼容，OpenAI 协议）

---

## 三、映射到项目现有能力

| TEMPO/dots3 机制 | 本项目对应物 | 现状 | 差距 |
|------|------|------|------|
| Macro-step 切分 | 旗舰管线 S0→S7 八阶段 | ✅ 已有，天然就是宏步 | 无（结构已具备） |
| 宏步间 critic 估值 | （无） | ❌ 缺失 | **核心缺口：阶段边界无自评节点** |
| 终局奖励 | S7 QG-1~QG-5 | ✅ 已有 | 粒度粗（5 门），应原子化 |
| 未完成轨迹训练信号 | ExperienceRecord / 数字孪生校正 | ⚠️ 仅成功 run 回流 | 失败 run 中间观测不写入 |
| Actor/Critic 角色切换 | flagship_runner 单一执行流 | ❌ 缺失 | 执行与评价未分离 |
| Test-time scaling 估值 | video_quality_assessor（YAVG/temporal_std 等） | ⚠️ 有指标但只在末端用 | 需把轻量指标前移到阶段边界 |
| 候选状态比较判断 | max_quality_iterations=3 串行重试 | ⚠️ 框架在，无候选并行比较 | 可增加候选采样+排序 |
| 主动记忆（超窗口保留） | persistent-learning-loop.ts / 知识库 | ✅ 已有持久学习通道 | 可补充"阶段性摘要写入"策略 |
| 模糊需求多轮评测 | （无） | ❌ 缺失 | 可建项目自有评测集 |
| 环境状态一致性检查 | Bridge 状态文件（bridge_ready.txt 等） | ⚠️ 零散存在 | 未纳入统一 atomic check 体系 |

---

## 四、优先级分层

### P0 —— 立即纳入（1-2 周，复用现有组件即可）

1. **中途自评节点（StageCritic）**：在 S2→S3、S3→S4、S5→S6 三个昂贵边界插入轻量 critic 门
2. **失败 run 中途观测回流**：critic 报告写入 manifest，FlagshipManifestParser 扩展解析，失败轨迹也喂数字孪生
3. **质量门原子化**：QG-1~QG-5 拆为 atomic checks 清单（含状态一致性项），报告结构化到项级

### P1 —— 近期扩展（2-4 周）

4. **候选比较自评**：S3 渲染产出 2-3 个低成本候选（降分辨率/抽样帧），critic 排序后再选优全量渲染
5. **模糊需求评测集**：建 `tests/vibe_search_bench/`，收录 20+ 条真实模糊剪辑需求 + 逐步追加约束的多轮脚本，回归验证需求理解
6. **dots3-note API 接入 llm_gateway**：作为视觉自评模型候选（输入渲染抽样帧/视频片段，输出结构化评价），与现有 ModelScope 通道并列

### P2 —— 研究参考（择机）

7. **递归自我评价**：开放任务（无明确质量指标的创意类任务）中让 Agent 自判进展——等官方后续论文
8. **TEMPO 训练方法**：若未来微调领域模型（如风格分类器），macro-step + 中途估值是可复用的 RL 配方
9. **自部署配方**：FP8/SGLang/MTP 细节存档于 `13-素材获取与搜索` 同级新建 `16-模型部署参考/`（待有硬件时启用）

---

## 五、可落地方案

### 5.1 新模块：`pipeline/midstep_critic.py`（P0-1 核心）

```python
"""阶段边界中途自评节点 —— 借鉴 TEMPO macro-step critic 思想。

设计原则：
- 轻量：只做 ffprobe/抽帧/指标采样，秒级完成，不触发真实渲染
- 三态裁决：continue / retry（回退本阶段重跑）/ abort（止损终止）
- 评价即信号：每次裁决写入 critic_report，供数字孪生校正
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class CriticVerdict:
    stage: str                          # 被评价的阶段（如 "S3"）
    value_estimate: float               # 预期剩余回报 0~1（能否通过最终 QG 的估计）
    decision: str                       # continue / retry / abort
    atomic_checks: Dict[str, bool] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


class StageCritic:
    """单个阶段边界的 critic。

    value_estimate 的构成（加权）：
    - 先验：数字孪生 StagePredictor.predict_success_rate（后续阶段链式乘积）
    - 后验：当前产物的原子检查通过率
    二者加权（建议先验 0.3 / 后验 0.7，随孪生数据积累逐步提高先验权重）
    """

    def __init__(self, digital_twin=None, threshold_continue=0.6,
                 threshold_abort=0.3, max_retry=1):
        ...

    def evaluate(self, stage: str, artifacts: Dict[str, Path],
                 context: dict) -> CriticVerdict:
        """执行原子检查并给出裁决。"""
        ...
```

**各边界的具体原子检查项（初版）**：

| 边界 | 原子检查项 | 失败裁决 |
|------|------|------|
| S2→S3 前 | 节拍文件非空、onset 数量 ≥ 预期下限、音频时长与素材总时长匹配 | retry S2 |
| S3→S4 前 | 渲染产物存在且 >100KB、ffprobe 时长达标、抽 5 帧 YAVG>15、帧间 temporal_std>3.0（防黑帧/静帧——历史 QG-1 失败的根因前移） | retry S3 |
| S5→S6 前 | 调色产物时长与粗剪一致、无色彩溢出（抽样帧 max<255 占比>99%）、音画同步偏差<40ms | retry S5 |

**接入点**：`flagship_runner.py` 各 `stage_sN()` 返回后调用；裁决为 abort 时立即停止并写 `critic_abort_report.json`。

### 5.2 manifest 扩展 + 失败回流（P0-2）

manifest.json 新增字段：

```json
{
  "critic_reports": [
    {"stage": "S3", "value_estimate": 0.82, "decision": "continue",
     "atomic_checks": {"size_ok": true, "yavg_ok": true, "temporal_std_ok": true}}
  ],
  "termination": "success | critic_abort | stage_error"
}
```

- `core/experience_harvester.py` 的 `FlagshipManifestParser` 扩展：解析 `critic_reports`，将**每个中途裁决**转成 ExperienceRecord（含 value_estimate 与实际终局结果的偏差）
- 数字孪生收益：Beta 分布校正从"每 run 一个终点观测"升级为"每 run 多个中途观测"，预期收敛速度显著提升（上次回流已验证成功率预测 0.14→0.31，中途观测密度提升后应进一步改善）

### 5.3 质量门原子化（P0-3）

`core/quality_gate.py` 重构方向：

```python
ATOMIC_CHECKS = {
    "QG-1": ["luminance_mean_in_range", "luminance_variance_above_min",
             "no_black_frame_stretch", "fade_transition_present"],
    "QG-2": ["duration_matches_plan", "clip_count_matches", "cut_on_beat_ratio"],
    "QG-3": ["resolution_spec", "fps_spec", "codec_spec"],
    "QG-4": ["audio_peak_in_range", "no_clipping", "audio_sync_offset"],
    "QG-5": ["color_no_overflow", "scene_change_count", "visual_variety_score"],
}
```

`quality_gate_report.json` 从 `{passed: bool}` 升级为逐项 `{check: bool, value: float, threshold: str}`，并标注每项的**引入阶段**（由 critic_reports 回溯定位）。

### 5.4 模糊需求评测集（P1-5）

新建 `tests/vibe_search_bench/`：

```
tests/vibe_search_bench/
├── cases.json          # 20+ 条用例：初始模糊需求 + 每轮追加的约束
├── runner.py           # 多轮模拟：逐轮喂需求，检查 Agent 是否正确追问/收敛
└── scoring.py          # 评分：约束召回率（最终方案覆盖了用户陆续提出的多少约束）
```

用例示例：初始"帮我做个高燃的" → 第 2 轮"素材是动漫的" → 第 3 轮"要踩点" → 第 4 轮"不要转场太花"。评分看最终 plan 是否吸收了全部约束、是否在正确的轮次追问。

### 5.5 知识库条目（写入 `04-设计模式与反模式/`）

新增文档 `04-设计模式与反模式/中途自评模式（TEMPO思想）.md`，收录：

1. **模式**：长流程中在每个昂贵阶段边界插入轻量评价节点，评价者用「先验预测 × 后验检查」估值，三态裁决
2. **反模式**：终局质量门——失败要跑完全程才暴露（本项目 QG-1 帧亮度方差=0 案例为实证）
3. **反模式**：失败即弃——失败 run 的中间观测不含训练/校正价值
4. **经验数字**：TEMPO 在任务后半程与 GRPO 拉开差距；本项目 S3→S6 占总耗时约 80%，是自评收益最大区间

---

## 六、验收标准（P0 完成后）

1. 构造黑帧注入故障（S3 产出全黑帧），管线在 **S3→S4 边界被 critic 拦截**，不再浪费 PR/DaVinci/AME 时间
2. 失败 run 的 `output/flagship_*/manifest.json` 含完整 `critic_reports`，且 ExperienceHarvester 能解析入库
3. `quality_gate_report.json` 输出原子项级结果，任一失败项可回溯到引入阶段
4. 数字孪生校正样本数 ≥ 原方案的 3 倍（中途观测密度提升的直接证据）

---

## 七、后续跟踪

- dots3-note 正式版开源后重新评估（preview 版体验与细节仍有优化空间）
- dots3 系列后续 jazz / aria 两档发布时，评估 aria 是否适合作为本项目视觉自评的旗舰模型
- 官方 Full Report 发布后补充 TEMPO 超参与消融实验细节
- 小红书"智谱安全披露账本"式的**公开进展披露机制**，可借鉴为本项目 changelog/阶段报告的运营方式（低优先级）

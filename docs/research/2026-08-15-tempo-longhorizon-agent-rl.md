# TEMPO/dots3 长程 Agent 技术调研与 AE-Knowledge-Vault 集成方案

> 日期：2026-08-15 · 来源：小红书 dots 实验室 TEMPO 技术博客、dots3-note 开源仓库、
> AgenticQwen (阿里, ACL 2026 Industry)、LongTraceRL (清华 THU-KEG)、VibeBench 评测基准
>
> 定位：不是泛泛的技术新闻总结，而是"哪些机制能直接搬进本项目"的工程调研。

## 一、技术全景：国产模型长程 Agent 的主战场（2026-08 当周）

| 方案 | 机构 | 核心机制 | 与本项目的关系 |
|---|---|---|---|
| **TEMPO** | 小红书 dots 实验室 | macro-step 切分长轨迹 + 阶段末 test-time scaled 自评（actor→critic 切换）+ 自评作未完轨迹训练信号 | **直接对标**（渲染管线天然是 macro-step 结构） |
| **dots3-note** | 小红书 | 280B/512K 上下文、主动记忆（边干边记）、自我批评（self-critiquing）、开放任务递归自评 | 记忆与自评机制可学 |
| **AgenticQwen** | 阿里 | dual-flywheel 数据合成 + GRPO 训练工业级工具调用小模型 | 数据飞轮思路 → 项目的数据回流 |
| **LongTraceRL** | 清华 | rubric rewards（量规奖励）从搜索轨迹学长上下文推理；4B/8B/30B 开源 | rubric 化奖励 → 项目质量门控 |
| **VibeSearchBench / VibeLifeBench** | 小红书 dots | 20 领域 200 任务 / 10 领域 20 任务×20-30 阶段 + 1247 atomic checks；头部模型全部不及格 | atomic checks 理念 → 项目渲染质量检查表 |

共同结论：**单点能力已够强（IMO 满分），长程稳定性是共同短板**——恰好也是本项目渲染管线"跑 10 分钟没问题、跑 2 小时就崩/漂"的同构问题。

## 二、五个可复用机制（提炼 + 映射）

### 机制 1：阶段中途自评（TEMPO 核心，最值得抄）

- **原做法**：长轨迹切 macro-step → 每阶段结束 actor 切 critic → 推理+工具调用估计"当前状态未来回报" → 变成未完轨迹的训练信号。
- **本项目映射**：渲染管线已有明确阶段（1.1 素材分析 → 1.3b 时间分析 → 1.4 选材 → 2 分镜 → 3 渲染 → 4 复核）。每个阶段结束加一次 LLM 自评：
  ```
  StageCritic(阶段产物摘要, 阶段决策日志, 目标) → {value: 0-10, rationale, risks[]}
  ```
- **成本**：用刚配好的 deepseek-v4-flash（高频档），单次调用 <1 分钱，7 阶段 <1 毛。
- **收益**：① 渲染崩溃后可按"阶段价值"判断断点恢复；② 自进化数据多一个维度（阶段分序列，而非仅最终分）；③ 与 TEMPO 论文同构——若未来做 RL 微调，这批数据就是现成的训练集。

### 机制 2：Rubric 奖励（LongTraceRL）

- **原做法**：用"量规"（rubric，多维度打分表）给搜索轨迹逐项评分，替代单一成败信号。
- **本项目映射**：现有 quality_gate / rhythm_reward 是单维度 rubric。扩展为**渲染五维量规**：
  1. 踩拍对齐（已有 rhythm_reward）
  2. 叙事一致性（已有 narrative_verification，可量化）
  3. 素材-叙事匹配度（semantic windows 命中率）
  4. 成片技术完整性（已有 video_quality_assessor 的 atomic checks：有音轨/无黑场/时长/分辨率/码率）
  5. 运镜多样性（camera_inventory 标签分布熵）
- 五项加权 = 最终 quality 分。比现在的"阶段成功计数"（D1 根因：四维全常数分）强一个量级。

### 机制 3：主动记忆 / 边干边记（dots3-note）

- **原做法**：模型在长任务中主动写笔记（notes），供后续步骤检索。
- **本项目映射**：渲染已有 decision_log（被动记录决策）。升级为**结构化阶段笔记**：
  ```
  run_notes.jsonl = [{stage, decision, critique_value, key_insight, for_next_stage[]}]
  ```
  下一阶段 prompt 里注入上一阶段 note 的 `for_next_stage` 提示。本质是把"模型写给自己的便签"作为跨阶段上下文通道。
- **落地关键**：notes 必须结构化（JSONL append-only），不能是自由文本——否则检索不起来。

### 机制 4：Atomic Checks（VibeLifeBench 评测方法论）

- **原做法**：1247 项原子检查，每项只回答"是/否"（状态一致？工具执行对？交付了什么？），避免主观打分。
- **本项目映射**：把成片验收从"VLM 主观复核"升级为"主观 + 原子检查"双轨：
  ```
  atomic_checks = [
    has_audio, duration_within_budget, resolution==1920x1080, fps==24,
    no_black_frames>2s, shot_count>=plan*0.8, bgm_aligned(踩拍率>=阈值) ...
  ]
  ```
  原子检查由本地工具完成（ffprobe/OpenCV，零 LLM 成本），主观维度才走 VLM。这直接解决"内容复核偶发失败"和"质量分数不可信"两个老问题。

### 机制 5：双数据飞轮（AgenticQwen）

- **原做法**：① 轨迹飞轮（真实交互轨迹回流训练）② 合成飞轮（拒绝采样 + 数据合成扩充）。
- **本项目映射**：项目已有飞轮①的雏形（processed_outputs.jsonl + evolution_knowledge），但**飞轮②是空的**。可补：
  - 用 deepseek-v4-flash 批量合成"阶段决策→价值评价"对（把真实 decision_log 喂给 LLM，让它产出多候选评价，保留与最终 quality 一致的）
  - 合成数据 + 真实数据合并 → 未来微调 RenderCritic 小模型

## 三、落地路线图（实验室级推进）

### P0 — 零训练成本，本周可做（纯 LLM 调用 + 结构化记录）

1. **StageCritic 中途自评**：`ai/stage_critic.py` 新增，production_director 每阶段结束调用，结果进 production_report.stage_self_critique + run_notes.jsonl。
2. **渲染五维 rubric**：`core/render_rubric.py`，整合现有 rhythm_reward / narrative_verification / video_quality_assessor 输出为统一分数。
3. **Atomic checks 验收表**：`core/atomic_checks.py`，渲染完成后跑 8-10 项本地检查，替代部分 VLM 复核。

验收标准：一次真实渲染产生完整的 `stage_critique + rubric + atomic_checks` 三件套，全部落盘。

### P1 — 数据积累 + 小模型微调（1-2 周，需云端算力）

4. **轨迹数据规范化**：每次渲染自动产出 RL 训练格式的轨迹 JSONL（stage state 摘要 + action + critic value + 最终 rubric 分）。积累 200+ 条渲染轨迹（约 2-4 周自然产出）。
5. **云端微调 RenderCritic**：
   - 底座：Qwen3-4B 或 LongTraceRL-4B（两者均有开源权重，云端 LoRA 微调 4B 级单卡 A10 即可）
   - 数据：真实轨迹 + 合成轨迹（机制 5）
   - 任务：输入（阶段状态摘要, 决策, 目标）→ 输出（value 0-10, rationale）
   - 部署：微调产物走火山方舟/硅基流动的模型托管，或本地 vLLM
6. **RenderCritic 替换 LLM critic**：P0 的 StageCritic 从"调 API"切换为"调本地/托管小模型"，单次自评成本趋近于零、延迟毫秒级。

### P2 — 研究级扩展（按需）

7. **TEMPO 式 RL 训练**：actor（渲染决策策略）+ critic（RenderCritic）联合 RL，macro-step 为训练单元。需要显著更大的轨迹库（1000+）和多卡训练，暂不启动。
8. **递归自我评价**：开放任务（无清晰外部奖励）中模型自评进展并据此调整记忆——待 dots3-note 正式版开源后评估借鉴。

## 四、云端训练任务建议（回答"能用到什么"）

| 云端资源 | 用途 | 优先级 |
|---|---|---|
| 火山方舟 GPU 实例（A10/单卡） | P1 的 RenderCritic LoRA 微调（4B 级，几小时） | 高 |
| 阿里云 PAI / 百炼 | 备选训练平台；百炼 Token Plan 仅限交互工具，训练走按量 | 中 |
| 硅基流动模型托管 | 微调产物托管 + API 化（项目已有 key，零新增账号） | 高 |
| deepseek-v4-flash（已配） | P0 阶段自评 + P1 合成数据飞轮（批量调用成本可忽略） | 立即 |
| ModelScope（已配） | 拉取 Qwen3-4B / LongTraceRL 权重 | 立即 |

**不建议**：自建训练机（电费+维护不划算）、用订阅套餐 Key 跑训练（百炼 Token Plan 明文禁止自动化，火山 Agent Plan 同理）。

## 五、知识条目建议（写入项目知识库）

1. `docs/research/2026-08-15-tempo-longhorizon-agent-rl.md`（本文档）
2. 知识库新增条目："渲染阶段自评协议"（StageCritic prompt 模板 + value 口径约定，与 style_cards 同构）
3. 知识库新增条目："渲染五维 rubric 权重表"（默认权重 + 各维度阈值，可被 taste_profile 覆盖——与品味契约联动）
4. `docs/plans/2026-08-15-render-critic-roadmap.md`：P0-P2 路线图 + 验收标准 + 数据格式规范（RL 轨迹 schema v1）

## 六、与现有体系的对齐检查（避免重复建设）

- 阶段自评 ≠ self_evolution_engine 的 post_execution_review（后者是终评；前者是中评）。两者共存：中评进轨迹，终评进经验蒸馏。
- rubric ≠ quality_gate 现状：quality_gate 是"门禁"（过/不过），rubric 是"打分表"（0-100 连续分）。保留门禁，新增打分。
- atomic_checks ≠ VRS：VRS 是渲染校验（视觉回归），atomic_checks 是成片技术验收。可合并到同一验证链。
- run_notes.jsonl ≠ decision_log：decision_log 是给人看的文档，notes 是给下一阶段模型看的结构化通道。前者归档，后者消费。

## 附：关键参考链接

- TEMPO 技术博客（中文）：小红书 dots 实验室官方博客
- dots3-note-prev：https://github.com/studio-dots-ai/dots3-note-prev
- AgenticQwen 复现：https://github.com/sontianye/AgenticQwen （arXiv:2604.21590, ACL 2026 Industry）
- LongTraceRL：https://github.com/THU-KEG/LongTraceRL （rubric rewards, 4B/8B/30B 权重开源）
- VibeBench：https://github.com/vibebench ；VibeSearchBench（arXiv:2605.27882）、VibeLifeBench（arXiv:2608.10875）

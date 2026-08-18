# 全项目能力增强总表（实测扫描版 V2，2026-08-18）

> 扫描方法：遍历 ai/ 80+ 任务脚本 docstring + 全代码外部模型引用 + models/ 目录
> + D:\AE-Data 数据集实测存在性。每一条都有落盘证据，非纸面推测。
> **V2 修订（同日）**：新增第五节「全网文献证据审计」——4 项选型依据 2025-2026
> 论文/基准实测证据修正，2 项原方案获证据支持。全部结论附来源链接。

---

## 一、扫描发现：你手里的三座未开发金矿

### 金矿 1：CameraBench 专业基准（D:\AE-Data\CameraBench，实测在位）
- 内容：`test.jsonl` + `videos.csv` —— 电影级运镜理解基准数据集
- 价值：① 运镜分类器训完可直接在**专业基准**上评测（不止自家 val 集）
  ② 其数据可反向扩充训练集（当前 6166 条 → 预计 +30-50%）
- 接入成本：低（同为视频→运镜标签范式，写个转换器即可）
- **V2 新增（证据支撑）**：CameraBench 官方已开源 SFT 微调模型
  `chancharikm/qwen2.5-vl-7b-cam-motion-preview`（15类运镜 SOTA）
  ——可直接下载作为 12069 条未标注 clips 的**专业标注器**，
  比通用 Qwen3-VL-8B 在运镜维度更准（来源：CameraBench GitHub，NeurIPS 2025 Spotlight）

### 金矿 2：ClipShots 镜头边界数据（D:\AE-Data\ClipShots，实测在位）
- 内容：`clipshots_ann.tar` 完整标注包（23K+ 真实镜头边界）
- 价值：当前切点靠 ffmpeg 场景检测（启发式），可训**深度镜头边界模型**替代
  ——直接强化卡点铁律链路的第一环（素材切片精度）
- 配套模型：TransNetV2（仅 6MB，SOTA 镜头边界检测，GitHub 开源）

### 金矿 3：AutoShot + MovieNet（实测在位）
- AutoShot：快手镜头检测数据 + 已有对比评测脚本
- MovieNet：电影理解数据集
- 价值：镜头边界模型的第二评测基准 + 电影级领域语料

## 二、已有能力矩阵（models/ 实测，避免重复建设）

| 模块 | 位置 | 状态 |
|---|---|---|
| 运镜分类 | models/camera/videomae_camera.py | 推理壳就位，训练中（48.3%→目标75%+） |
| 氛围标注 | models/atmosphere/torii_annotator.py | **壳已写好，等 ToriiGate 上 24GB 卡激活** |
| 节拍分析 | models/beat/beatnet_adapter.py + rhythm_fusion.py | BeatNet 已接入 |
| 素材标签 | models/tagging/material_tag_fusion.py | 已接入 |
| 抠像 | BiRefNet（844MB 已验证） | IoU 0.750，可续训 |
| 语义检索 | BGE-M3（镜像修复后可用） | 已接入 |
| VLM 标注 | Qwen3-VL 系列（t26* 管线） | 已验证 |
| 检测 | YOLOv8x | 已接入 |
| 分割 | SAM2.1（sam2.1_hiera_s.yaml） | 已引用 |

**结论：壳全都在，缺的是把模型训强 + 把金矿数据喂进去。**

## 三、增强途径总表（全部任务，按梯队排序）

### 第一梯队 · 数据已在手，直接可训（零下载）

| # | 任务 | 数据 | 动作 | 预期收益 | 算力 |
|---|---|---|---|---|---|
| 1 | **运镜分类大训练** | 6166条+shots | 三阶段方案（已 READY） | 48.3%→75-85% | 5090 8h |
| 2 | **CameraBench 扩充+评测** | D盘在手 | 转换器→扩充训练集→基准评测 | 精度+3-5pt，且有公信力分数 | 5090 2h |
| 3 | **BiRefNet 续训** | 云端 7.5G | +8ep 至收敛 | IoU 0.75→0.78 | AutoDL 3h |
| 4 | **IP 蒸馏换强 teacher** | 蒸馏管线全套 | DINOv2-strong 重蒸馏 | 0.751→0.78-0.80 | 5090 4h |

### 第二梯队 · 需下载模型，收益明确（小模型，几分钟下完）

| # | 任务 | 下载什么 | 解决什么 | 预期收益 |
|---|---|---|---|---|
| 5 | **镜头边界检测** | TransNetV2（6MB，GitHub） | 替代 ffmpeg 启发式切点，喂 ClipShots 23K 标注微调 | 切点精度质变，卡点链路第一环升级 |
| 6 | **视频质量评估** | DOVER 或 VSFA（HF） | 评分头从"手工特征"升级为"深度美学模型" | 因果引擎评分 82.3→85+ |
| 7 | **音乐情绪分类** | MER 模型（4类情绪，HF） | BGM 匹配从能量分析升级为情绪理解 | 音画匹配质量提升 |

### 第三梯队 · 有明确替代品或低收益（不建议现在做）

| # | 任务 | 为什么不做 |
|---|---|---|
| 8 | Whisper 字幕 | 本机已有 Intel 本地 ASR 技能（30语种+中文方言），替代品在位 |
| 9 | GroundingDINO 主体定位 | YOLOv8x 已在位，重叠度高 |
| 10 | 文生图/文生视频训练 | 走 API（网关已有），不值得自训 |

## 四、推荐总路线（一张 5090 全吃下）

```
第1晚: 任务1 运镜大训练 (8h)           ← 主战,已在 READY
第2晚: 任务2 CameraBench评测+扩充 (2h) + 任务4 IP蒸馏 (4h)
第3晚: 任务5 TransNetV2+ClipShots (3h) + 任务6 DOVER接入 (1h)
并行:  AutoDL 续训 BiRefNet (3h, 数据在云不用传)
顺带:  ToriiGate 全库氛围标注 (任何一次开机顺带 3h)
```

**全部完成后项目能力跃迁**：运镜 75%+（专业基准认证）、切点深度模型化、
抠像 0.78、评分 85+、氛围标注全库激活——六大模块全部换代。

## 五、朋友智能体交接物

见 `friend_trae_agent_taskfile_20260818.md`（任务书 V1，随第一包发出）。
每个后续任务的包各自带 RUN_*.bat + 验收标准，智能体按同流程执行。


---

## 五、全网文献证据审计（V2 新增，2026-08-18）

> 方法：针对本项目 6 个核心选型，检索 2025-2026 论文/基准/官方仓库实测数据。
> 每条结论附来源。**4 项修正、2 项确认**。

### 审计 1｜运镜分类训练方法 → 【修正：LoRA 上限不足，5090 应改全参微调】

**证据链**：
- MIT CSAIL《LoRA vs Full Fine-Tuning: An Illusion of Equivalence》(arXiv:2410.21228)：
  即使 LoRA rank=76 + rank stabilization，其**有效秩不到全参微调的一半**；
  LoRA 在更难的任务上难以追平全参微调
- CAPability 基准（OpenReview 2025 已接收，阿里 vilab）：独立证实
  「**所有模型都在动作识别、运镜识别、角色识别上挣扎**」——运镜分类是公认难任务
- CameraBench（NeurIPS 2025 Spotlight）：15 类运镜上 Qwen2.5-VL-7B SFT 仅 60.0% 平均准确率

**对本项目的影响**：
- v3c 用 LoRA r8 卡在 48.3% 有了理论解释（难任务 + 低秩瓶颈）
- 已升级的 r64+解冻2层方向正确，但**5090 上应直接改全参微调**：
  VideoMAE-base 仅 ~86M 参数，24GB 显存全参微调绰绰有余
  （对比：LLaMA-7B 全参需 78GB+，但我们的底模小两个数量级）
- 目标校准：6 类任务 + 动漫领域专精，75-80% 依然合理
  （CameraBench 15 类 SOTA=60%，类别少一半 + 领域专精会显著加分）

### 审计 2｜12069 条标注器 → 【修正：双标注器策略】

**证据链**：
- CameraBench 官方开源 SFT 模型 qwen2.5-vl-7b-cam-motion-preview（15 类运镜 SOTA）
- CamReasoner（arXiv:2602.00181，2026-04）：运镜理解 SOTA 又被推进，
  Qwen2.5-VL-7B 基座二分类 73.8%→78.4%
- Qwen3-VL 技术报告（arXiv:2511.21631）：Qwen3-VL-8B 视频理解 ≈ Qwen2.5-VL-72B，
  原生 256K 上下文 + 显式视频时间戳

**修正方案**：包2 标注改双标注器
- 运镜标签：CameraBench SFT 模型（专业）｜氛围/质量标签：Qwen3-VL-8B（通用强）
- 二者置信度分歧大的样本进人工复核队列（预计 <5%）

### 审计 3｜美学评分选型 → 【修正：DOVER 已过时，改 Q-Align / Peak-End-Net】

**证据链**（DIVIDE-3K 美学维度 SRCC 对比，数值来自 Peak-End-Net 论文表格）：
| 模型 | SRCC | PLCC |
|---|---|---|
| DOVER (ICCV 2023) | 0.3998 | 0.4308 |
| Q-Align (ICML 2024) | 0.4695 | 0.4842 |
| Peak-End-Net (2026-07, 阿里AMAP) | **0.5427** | **0.5773** |

- Peak-End-Net：冻结 ViT + 少量可训练参数（轻量，适合我们），
  代码开源 github.com/AMAP-ML/Peak-End-Net
- Q-Align 更强通用性但对算力要求高

**修正方案**：包4 美学评分模块改用 **Peak-End-Net**（轻量+SOTA+代码可得）
——此前 roadmap 写的 DOVER/VSFA 作废，那是 2023 年的 SOTA。

### 审计 4｜镜头边界检测 → 【部分修正：硬切够用，渐变转场需新模型】

**证据链**：
- TransVLM（arXiv:2604.27975，2026-04，HeyGen Research 已上生产）：
  VLM 范式全面超越专用网络（含 TransNetV2 类）
- OmniShotCut（arXiv:2604.24762，2026-05，UVA）实测点名：
  「TransNetV2 和 AutoShot 在 dissolve/fade 上失败——
  常把起始帧选在渐变中间」
- 但 TransNetV2 在**硬切**（卡点主场景）上依然稳固（F1 95%+，全流程工具链成熟）

**修正方案**：
- 卡点链路（硬切为主）：TransNetV2 维持原方案 ✓
- AMV 渐变转场检测（dissolve/wipe 常见）：包4 增加 OmniShotCut/TransVLM 评估项

### 审计 5｜BiRefNet 续训 → 【确认：选型正确，且发现升级路径】

**证据链**：
- BiRefNet 官方仓库活跃维护（2026-02 模型更新、2026-07 提交）
- RMBG-2.0（业界广泛使用的商业抠像模型）就是基于 BiRefNet 架构
- FCLM（arXiv:2601.12080，2026-01）仍以 BiRefNet 为对比基线
- **仓库 2025-10 升级了 DINOv3 backbone 兼容**——我们续训时可顺带评估换 backbone

**结论**：云盘续训方案不变；续训实验组可加一组 DINOv3-backbone 对照。

### 审计 6｜Qwen3-VL-8B 作通用标注器 → 【确认】

**证据链**：官方技术报告（arXiv:2511.21631）：
- Qwen3-VL-8B 性能接近上代 72B（等于白拿 9 倍参数量级的提升）
- 交错式 MRoPE + 显式视频时间戳——对视频时序标注是针对性增强
- 30 语种 OCR、动漫角色识别能力被官方点名为升级项

**结论**：t26* 管线继续用 Qwen3-VL-8B，无需更换。

### 审计总结论（一张表）

| 选型 | 审计结果 | 动作 |
|---|---|---|
| 运镜训练 LoRA r64 | ❌ 上限不足 | 5090 改**全参微调**（86M 模型无压力） |
| 12069 条标注器 | ⚠️ 单标注器 | 改**双标注器**（CameraBench SFT + Qwen3-VL-8B） |
| 美学评分 DOVER | ❌ 2023 过时 | 改 **Peak-End-Net**（2026 SOTA，轻量） |
| 切点 TransNetV2 | ⚠️ 硬切OK | 硬切维持；渐变转场加 OmniShotCut 评估 |
| BiRefNet 续训 | ✅ 正确 | 维持 + DINOv3 backbone 对照组 |
| Qwen3-VL 标注 | ✅ 正确 | 维持 |

**来源**：
- CameraBench: linzhiqiu.github.io/papers/camerabench/ (NeurIPS 2025 Spotlight)
- CamReasoner: arxiv.org/abs/2602.00181
- LoRA不等价性: arxiv.org/abs/2410.21228 (MIT CSAIL)
- CAPability: openreview.net/forum?id=w7CAtdP5XC
- Peak-End-Net: arxiv.org/abs/2607.13941 (Alibaba AMAP)
- TransVLM: arxiv.org/abs/2604.27975 (HeyGen)
- OmniShotCut: arxiv.org/abs/2604.24762 (UVA)
- BiRefNet: github.com/ZhengPeng7/BiRefNet
- Qwen3-VL: arxiv.org/abs/2511.21631

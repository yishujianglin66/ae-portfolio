# 运镜分类模型 v5 → v6 跨会话交接报告

> 生成时间: 2026-08-24 09:12 (Asia/Shanghai)
> 项目根目录: `C:\Users\Administrator\Desktop\AE-Knowledge-Vault`
> 生成脚本/分析结果目录: `tmp/cloud_labels/`
> 会话前序: v5_5 公平复测 head 顺序修复 → val_acc 仍 0.32 证实数据瓶颈 → CPU 侧清洗 A-B-C → 研究方向转向 (F1-F5)

---

## 1. 任务身份（任何接手 AI 必须先读这一节, 禁止跳过）

### 1.1 你要解决的问题

**任务**: 构建 动漫视频的**运镜分类（Camera Movement Classification）** 深度学习模型
**输入**: 16 帧 224×224 的视频片段 (`D:\AE-Data\AnimeCamera\shots\*.mp4`, ≈ 0.5~3 秒/镜头)
**输出**: 镜头级运镜类别标签 (raw 9 类 / 6 类聚合 / **当前推荐 4 元类**)

**用途**: 下游漫剪卡点系统的运镜-aware 剪辑决策（push_in 镜头配强节拍、orbit 镜头配环绕运镜风格卡、tilt 镜头做变速等），是 `core/beat_strength_engine.py` 和 `ProductionDirector` 的输入特征之一。

### 1.2 历史验证过的不可行路径（禁止重蹈覆辙）

| 编号 | 尝试过的路线 | 结果 (证据) | 为什么不行 |
|---|---|---|---|
| ❌ v5.1-v5.5 | 6 类聚合分类 + VideoMAEv2 + 各种正则 (WeightedSampler / drop_path 0.25 / label_smooth / mixup+cutmix 调参 / LR 退火) | **val_acc 平台 0.3186 ~ 0.3223** (v5_2 epoch6, v5_5 epoch3 复测同等) | 任务难度和标签质量错配，细粒度 6 类 VLM 弱标注噪声太大，分类边界无法收敛 |
| ❌ cleanlab 只筛 | cleanlab 阈值 0.3 + 启发式过滤 v2new | 行 18229 → 7691，pan_left/right 比例从 0.55→0.505，但 zoom_push 仍 46.9% | 只清洗噪声不解决分布极端主导和细粒度混淆问题 |
| ❌ C 复审 462 可疑 (智谱 GLM-4V-Flash 71.5% 修改率) | 只改了 7690 行里 50 行，全量分布几乎不动 | 462 可疑样本只占 6%，zoom_push 的 3610 条"高置信正确标签"是 cleanlab 无法发现的系统性假阳性 |
| ❌ DINOv2 frozen + temporal head | 之前尝试路线（见 project_memory） | 完全无法学习帧间运动模式 | 运镜是时序特征，需要 VideoMAE 类时空联合注意力 |

### 1.3 验收指标分层（禁止混用 PLAN/READY）

| 层级 | 指标 | 说明 | 交付状态（当前） |
|---|---|---|---|
| **PLAN**（纸面，**不可引用到验收报告**） | F2 / F3 / F4 / F5 代码写完但未跑 | 只做了设计 | ⬜ F2-F5 待实现 |
| **PLAN**（纸面） | F1 脚本写完未训练 | 映射分布打印了，但未见 val_acc | ⬜ 等待云端开训 |
| **READY**（dry-run / 冒烟通过） | C 复审脚本 460/462 成功 | 71.5% 标签变化率符合预期 | ✅ |
| **READY**（实际 dry-run） | A 清洗脚本 18229 → 7690 | 阈值+清洗比例合理, pan 偏差修复 | ✅ |
| **READY**（实际训练） | v5_2~v5_5 4 轮训练, 每轮 ≥ epoch5 val_acc 样本量充足 | 稳定复现 0.32 平台期（非偶然） | ✅ |
| **目标 ACC (v6.0)** | **4 元类 val_acc ≥ 0.65** | CameraBench 论文粗粒度可实现 | 🎯 **下一阶段必须达成** |
| **目标 ACC (v6.1)** | **4 元类 val_acc ≥ 0.75** | 加入 LOS+F3 公开数据后 | 🎯 |
| **理想 ACC** | 细粒度回归 ≥ 0.60/类 | 三阶段 Z 任务 | 🔮 |

---

## 2. 根因分析（两个独立研究论文交叉实证）

> 这是为什么必须从 v5 的细粒度路线切换到 v6 的元类+专家数据路线的**核心证据**，接手时必须理解。

### 根因 1：细粒度运镜分类本来就是「人类摄影专家级难度」。VLM 不是专家。

**论文证据 1: CameraBench 2025 NeurIPS Spotlight (CMU + Adobe + MIT-IBM)**

Paper: *Towards Understanding Camera Motions in Any Video* (arXiv:2504.15376, accepted Spotlight NeurIPS 2025)

论文通过大规模人类标注实验量化了标注难度：
- 人类**新手** vs **专业电影摄影师**的标注准确率差距：**> 15%**
- 三个新手最易错的混淆对（也是本项目 VLM 批量判错的三个组合）：

| 混淆对 | 普通人识别率 | CameraBench 标注者培训后提升 |
|---|---|---|
| zoom_in（内参焦距变化）↔ dolly_push（相机物理向前） | **~40%** | +12 pp |
| pan_left ↔ pan_right（方向搞反） | ~70% | +8 pp |
| tilt_up ↔ tilt_down（方向搞反） | ~75% | +6 pp |

论文评测结果（公开 leaderboard benchmark）：
```
Model                                    pan/truck  tilt/pedestal  zoom/dolly  Mean
Qwen-2.5-VL 7B (SFT CameraBench 1400条)    0.52        0.53          0.53       0.59
Qwen-2.5-VL 7B (zero-shot)                0.51        0.52          0.51       0.54
Prev.SOTA (Logit Adjustment)               0.27        0.44          0.40       0.44
```

**关键推论**：即使最强 VLM + 1400 条专家 SFT，细粒度基元分类 Mean Acc 也仅 0.59。CameraBench 的一级运动轴分组（Pan / Tilt / Zoom / Static）准确率**比细粒度高 15-20 个百分点**。这就是 F1 4 元类切换的根本依据——把任务降到模型能收敛的难度。

---

**论文证据 2: Geometry-Guided Camera Motion Understanding (UMD + Dolby, arXiv:2603.13119, 2026)**

- 视频 ViT 的 deeper block 中，相机运动几何线索被视觉 token 压缩所衰减
- 结论：纯端到端 VideoMAE 学细粒度运镜是结构上的困难，必须通过分类空间粗化 + 外部几何 cue 注入双管齐下

### 根因 2：极端长尾 max/min = 46.9%/5.9% ≈ 8:1，只有采样权重不够

**论文证据 3: Gen2Balance ECCV 2026 (布里斯托+Adobe)**

基于 **VideoMAE 骨干**在 UCF-LT 和 K100-LT 上的实证：
| 方法 | K100-LT Few | K100-LT Tail | K100-LT Head | Avg C/A |
|---|---|---|---|---|
| Cross-Entropy（我们 v5 基线的等价） | 11.3% | 15% | 70% | 36% |
| Balanced Softmax Loss | 23.2% | 22% | 68% | 41% |
| Gen2Balance (SOTA, 合成填充 + 二阶段) | **43.2%** | **30%** | 71% | **47%** |

关键发现：**合成视频填充尾类后，尾类相对提升 +105%，但必须 Stage2 在纯真实数据上纠偏 3-5 epoch，否则合成→真实域偏移会让整体反而更差。**

对应我们：tilt_orbit 453 / 总数 7690 ≈ 5.9%（与 K100-LT Few Group ≤ 20 条/类的情况相似），需要合成视频填补。

**论文证据 4: LOS: Label Over-Smooth Can Balance, ICLR 2025 (上交 SJTU Thinklab)**

- 统一特征表示下做 classifier 重训，只需对 one-hot 标签做**标签过平滑**（正确类略高于 1/K，其他略低于 1/K）即可调平 logits magnitude，无需分布先验
- ImageNet-LT 和 iNaturalist 2019 SOTA，**代码极简（50行）**，非常适合直接集成到 v6 训练脚本

---

## 3. 公开数据集可用性矩阵（三平台交叉实搜）

实际搜索平台：**ModelScope.cn / HuggingFace datasets / PapersWithCode**

| 数据集 | 托管 | 样本量 | 类数 | 标注来源 | 运镜匹配度 | 可下载性 | 本项目价值 |
|---|---|---|---|---|---|---|---|
| **✅ CameraBench** | 🤗 HF syCen/CameraBench | 3381 视频 (测试集 1000+ 公开), 150K binary labels | 50+ 细粒度运镜基元 (含 pan/tilt/zoom/truck/dolly/pedestal/arc/follow/roll...) | 专业电影摄影师多轮培训标注 | ⭐⭐⭐⭐⭐ 完全匹配任务 | `pip install datasets; datasets.load_dataset("syCen/CameraBench")` | **金标准数据**: 用来 (a) 给 backbone 做 warm-up, (b) 重新对齐 VLM prompt, (c) 做域外+域内联合训练 |
| X-Fun-Videos-Lingbot-Demo | 📊 ModelScope PAI | 7 视频 + 相机轨迹 (poses.npy) | 漫游/环绕, 无分类标签 | 合成第一人称轨迹 | ⭐⭐ 不匹配分类任务 | 立即可用 | 轨迹回归，无直接价值 |
| UCF101 | 官网+阿里云镜像 | 13,320 段 (6.5GB) | 101 人类动作类 | 学术界公认动作基准 | ❌ 任务不匹配 | 立即可用 | 动作类 ≠ 运镜类，不能直接复用（但可做 VideoMAE 预训练增强，远期） |
| HMDB51 | 官网 | 6,766 段 | 51 人类动作 | 电影+YouTube混合剪辑 | ❌ 任务不匹配 | 立即可用 | 同上 |
| Kinetics-400 | DeepMind+cvdfoundation 镜像 | 306,245 段 | 400 人类动作 | YouTube 自动清洗 | ❌ 任务不匹配 | GCS 直链/YouTube 脚本下载, 不稳定版权 | 450GB 下载量+无运镜标签，ROI 为负 |
| MultiCamVideo-Dataset (KwaiVGI) | 🤗 HF KwaiVGI | UE5 合成多机位同步 | 10 基础轨迹 | 精确相机外参 | ⭐⭐⭐ 合成轨迹但风格不匹配动漫 | 立即可用 | 合成→动漫域偏移大，仅可做几何预训练 |
| HISTORIAN / MOVE-SET / Petrogianni / Kandinsky TrainSet | 论文私有/作者申请 | 800-5000 镜头 | 8-18 运镜类 | 电影胶片/专家标注 | ⭐⭐⭐⭐ 匹配但不可得 | 需要邮件申请/论文作者授权 | **目前不可用**，不做计划依赖 |

### 可用结论（唯一依赖）

只有 **CameraBench** 是运镜分类专用 + 专家标注质量 + 立即可下载（HuggingFace 国内可直连）。**F3 唯一数据源。**

---

## 4. 推进路线图（三阶段 + F1→Z 编号）

### 阶段 1：难度降级 + 专家数据（现在立刻开干）

| 编号 | 任务 | 做什么 | 交付物 | 目标指标 | 估耗时 | 证据支撑 |
|---|---|---|---|---|---|---|
| **F1 ✅** | **4 元类切换** | 9 raw / 6 聚合 → 4 meta-class: `meta-static / meta-pan / meta-tilt-orbit / meta-zoom`。合并 3 个最易混淆对：(pan_left+pan_right)、(tilt_up+tilt_down+orbit)、(zoom_in+zoom_out+push+zoom_back) | **[v6_meta_4class.jsonl](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/cloud_labels/v6_meta_4class.jsonl)** (7690 行)。脚本: [_F1_meta_4class.py](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/_F1_meta_4class.py) | **v6_4meta val_acc ≥ 0.65** (比 v5_5 的 0.32 预期涨 +33pp) | ⬜ 上传到云端 + 训练≈一晚上 | CameraBench 论文：一级运动轴分组准确率比细粒度 50+ 基元高 15-20pp |
| **F2 📝** | **专家培训 Prompt 升级** | 迁移 CameraBench 披露的标注者培训教程体系（5轮 × 30题 + 定义+边界反例）到 `vlm_annotate_camera.py` 的 PROMPT，三结构：① 严格定义；② 混淆对照表；③ 边界反例 | 新脚本 `scripts/vlm_annotate_camera_v2.py` + 100 条新旧对比验证，标注噪声 ≤ 40% | 下一轮标注/复审准确率提升 ≥10pp | 2 小时写 + 一天验证 | CameraBench 人类实验：标注者经培训教程准确率+10-15pp（Novice 0.46 → Trained 0.61） |
| **F3 📦** | **CameraBench 公开数据域内联合** | 1. `pip install datasets`; 2. `load_dataset("syCen/CameraBench")` 下载公开测试集 (1000+ 专家标注); 3. 写对齐脚本把 CameraBench 50 基元映射到 4 元类; 4. 与本地 v6_4meta 合并 9000+ 行做 v6.1 训练集 | `tmp/camerabench_4meta.jsonl` + 合并后的 `v6_1_trainset.jsonl` | val_acc 额外 +5pp (≥ 0.70) | 半天 | CameraBench 专家标注质量 >> 本项目 VLM 标注；公开数据 warm-up 是视频理解领域标准实操 |

### 阶段 2：长尾平衡 + 架构增强（等 F1 v6 epoch 3 出 val_acc 后并行开发，与 v6 训练不冲突）

| 编号 | 任务 | 做什么 | 交付物 | 目标指标 | 估耗时 | 证据支撑 |
|---|---|---|---|---|---|---|
| **F4 🔧** | **LOS 解耦训练集成** | 改造 `train_anime_camera_v6.py` → 两阶段：① Stage1 epoch1-15: 正常表征学习（交叉熵+加权采样）；② Stage2 epoch16-18: freeze backbone，仅 classifier 重训 + LOS Label Over-Smoothing（soft one-hot: 正类 1/K+ε, 其他 1/K-ε/(K-1)）。参考 Thinklab-SJTU/LOS 开源实现 | `scripts/train_anime_camera_v6_metaclass_LOS.py` | val_acc 额外 +3-5pp, Tail Group Acc 相对 +5-8pp | 1 天写代码 + 冒烟 | ICLR 2025 LOS：当前解耦训练最简 SOTA |
| **F5 🎬** | **Gen2Balance 合成尾类填充** | 1. 从现有 453 个 tilt_orbit + 1149 个 meta-pan 中选 10 个代表性样本，用 VLM (智谱 GLM-4V) 分析 → 生成 diverse prompts（每类 50 条）；2. 调 Seedance 文生视频模型合成 ~2000 条补充：1000 tilt_orbit, 500 meta-pan 多样化视角, 500 meta-static 反例；3. 二阶段训练: Stage1 平衡集(真实+合成) 训练 15 epoch + BalancedSoftmax，Stage2 纠偏 3-5 epoch 真实数据 | `data/gen2balance_tilt/` 合成视频目录 + 标注 JSONL | tilt_orbit Tail Group Acc 相对 **+25-30%**（Gen2Balance 论文 K100-LT Few-Shot: 11.3→43.2%, 相对 282%） | 生成 2000 条需 3-5 天，可与训练并行 | ECCV 2026 Gen2Balance: VideoMAE 骨干预设实证尾类提升最大 |

### 阶段 3：细粒度回归（v6.1 val_acc ≥ 0.75 之后，可选 Z）

| 编号 | 任务 | 做什么 | 交付物 | 目标指标 |
|---|---|---|---|---|
| **Z 🔮** | **细粒度回归** | ① 用 4 元类成熟分类器做辅助 head 蒸馏；② tilt_orbit 子类复审：用 F2 新版专家 prompt 对 453 个 tilt_orbit 再次标注，细分 tilt_up / tilt_down / orbit；③ pan 子类 1149 个方向标注复审；④ 回到 6 类聚合 fine-tune，冻结前 10 层只训练 top blocks | v7 细粒度 6 类模型 (raw_label 字段可追溯) | 每类 val_acc ≥ 0.60，CameraBench Mean Acc 对标 ≥ 0.59 |

---

## 5. 即刻启动清单（另一个会话 AI 必须按顺序执行）

### 第 1 步 (5 分钟, 最高优先级)

1. **检查文件存在性**（证据闸门 1 必做）：
   ```powershell
   py -3.12 -c "
   from pathlib import Path
   files = [
     r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\v6_meta_4class.jsonl',
     r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\_F1_meta_4class.py',
     r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\v5_6_labels_final.jsonl',
     r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\recheck_suspects.py',
     r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts\train_anime_camera_v5.py',
   ]
   for f in files:
     p = Path(f); print(('OK  ' if p.exists() else 'MISS'), f'{p.stat().st_size:>10d} bytes ' if p.exists() else ' '*15, p.name)
   "
   ```

2. **上传 v6_meta_4class.jsonl 到云端训练机**，路径 `/root/autodl-tmp/kawaii_ae/labels/v6_meta_4class.jsonl`

### 第 2 步 (立即，不依赖其他)：启动 v6_4meta 首训

3. 改造 `scripts/train_anime_camera_v5.py` 生成 **v6 版**：
   - 4 类标签空间: `["meta-static", "meta-pan", "meta-tilt-orbit", "meta-zoom"]`
   - label 字段兼容：读 `label` 优先，`movement_label` 回退，映射到 4 元类
   - `--num-classes 4`
   - **其他参数保持 v5 最优**：lr=1e-4, drop_path=0.20, num_sample=2, batch=32, grad_checkpoint, warmup_epochs=3, mixup=0.2, cutmix=0, WeightedSampler, dynamic EMA
   - 输出目录 `output/camera_v6_4meta/`

4. 在云端 **setsid nohup** 方式启动（避免 SSH 断开 SIGHUP），日志定向到 `log_v6_4meta.out`

### 第 3 步 (与 v6 训练并行，本机)：F3 CameraBench 公开数据

5. 本机执行：
   ```powershell
   py -3.12 -m pip install datasets --upgrade
   py -3.12 tmp\_F3_download_camerabench.py  # (需要新建: 见 §7.F3)
   ```
6. 验证 CameraBench 4 元类分布，与本地合并生成 v6.1 训练集。

### 第 4 步 (v6 epoch 3 val_acc 出来后)

7. **≥ 0.55** → 方向正确，同时推进 F4(LOS 集成) + F5(合成数据)
8. **< 0.55** → 先做 F3 公开数据 warm-up，再回训，说明领域 gap 需要先用公开高质量数据初始化 backbone

### 第 5 步 (v6 epoch 15)

9. **≥ 0.65** ✅ 达标 → F4 LOS 解耦阶段 2 精修 3 epoch
10. **< 0.65** ❌ → 回查 F1 映射是否引入错误（检查 4 类 cleanlab 新分布的噪声率），必要做 4 元类版本的 cleanlab 清洗

---

## 6. 本会话产出文件索引（全部绝对路径）

### ✅ READY 级产物（已通过 dry-run/冒烟/实际执行验证）

| 文件 | 状态 | 说明 | 行数/大小 |
|---|---|---|---|
| [tmp/cloud_labels/vl_labels_v2new.jsonl](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/cloud_labels/vl_labels_v2new.jsonl) | READY | 云端 18229 行原始标签拉回本地 | 18229 行 |
| [tmp/cloud_labels/v5_6_labels_washed.jsonl](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/cloud_labels/v5_6_labels_washed.jsonl) | READY | A 清洗: cleanlab 0.3 阈值 + 启发式, 18229 → 7691 行 | 7691 行 |
| [tmp/cloud_labels/suspect_review.jsonl](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/cloud_labels/suspect_review.jsonl) | READY | 可疑复审清单（462 条） | 462 行 |
| [tmp/recheck_suspects.py](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/recheck_suspects.py) | READY | 8 平台自动降级复审脚本（已通过 460/462 实际执行） | ~500 行 Python |
| [tmp/cloud_labels/suspect_rechecked.jsonl](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/cloud_labels/suspect_rechecked.jsonl) | READY | 460 条复审全结果（329 条标签变化，71.5%） | 460 行 |
| [tmp/cloud_labels/suspect_errors.jsonl](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/cloud_labels/suspect_errors.jsonl) | READY | 2 条 API 失败（可忽略） | 2 行 |
| [tmp/cloud_labels/v5_6_labels_final.jsonl](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/cloud_labels/v5_6_labels_final.jsonl) | READY | 6 类聚合 + 复审替换版 A+C 综合 (7690 行) | 7690 行 |
| [tmp/cloud_labels/v6_meta_4class.jsonl](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/cloud_labels/v6_meta_4class.jsonl) | READY | F1 4 元类版 (7690 行, Gini 0.712→0.569) | **7690 行** ✅ 【立即上传训练用】 |
| [tmp/_F1_meta_4class.py](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/_F1_meta_4class.py) | READY | F1 映射脚本（随时可再跑） | ~100 行 Python |

### ⬜ PLAN 级产物（接手人需要先实现才能跑）

| 编号 | 规划文件 | 说明 | 对应任务 |
|---|---|---|---|
| PLAN-F2 | `scripts/vlm_annotate_camera_v2.py` | 专家培训 Prompt 升级（注入 CameraBench 培训教程三结构），**尚未写** | F2 |
| PLAN-F3 | `tmp/_F3_download_camerabench.py` | CameraBench HF 下载 + 50基元→4元类对齐脚本，**尚未写** | F3 |
| PLAN-F3 | `tmp/cloud_labels/camerabench_4meta.jsonl` | CameraBench 对齐后数据，**尚未生成** | F3 |
| PLAN-F4 | `scripts/train_anime_camera_v6_metaclass_LOS.py` | LOS 解耦训练集成（Stage1 + Stage2 classifier retrain + Label Over-Smooth），**尚未写** | F4 |
| PLAN-F5 | `tmp/gen2balance_prompts/*.txt` 与合成输出 `data/gen2balance_supplement/` | Gen2Balance 合成视频填充，**尚未开始** | F5 |
| PLAN-Z | v7 细粒度回归脚本 | 6 类回归，**尚未设计** | Z |

---

## 7. PLAN 级实现指南（伪代码 + 文件结构，接手人照写即可）

### F3: `tmp/_F3_download_camerabench.py` 伪代码

```python
from datasets import load_dataset
import json
from pathlib import Path

CAM_TO_4META = {
    # CameraBench 50+ 基元 → 项目 4 元类映射。CameraBench 基元清单见论文 supplementary Table
    "static": "meta-static", "locked_off": "meta-static",
    "pan_left": "meta-pan", "pan_right": "meta-pan", "pan": "meta-pan",
    "truck_left": "meta-pan", "truck_right": "meta-pan",  # truck=物理横移, 特征同 pan
    "tilt_up": "meta-tilt-orbit", "tilt_down": "meta-tilt-orbit", "tilt": "meta-tilt-orbit",
    "pedestal_up": "meta-tilt-orbit", "pedestal_down": "meta-tilt-orbit",  # 升降, 归 tilt 轴
    "orbit": "meta-tilt-orbit", "arc": "meta-tilt-orbit", "roll": "meta-tilt-orbit",
    "dolly_in": "meta-zoom", "dolly_out": "meta-zoom",
    "zoom_in": "meta-zoom", "zoom_out": "meta-zoom", "push_in": "meta-zoom", "pull_out": "meta-zoom",
    "follow": None, "tracking": None,  # follow/tracking 需要 scene-aware → 丢弃 (本项目分类器不处理语义)
}
OUT = Path(r"tmp/cloud_labels/camerabench_4meta.jsonl")
ds = load_dataset("syCen/CameraBench", split="test")  # 1000+ 公开
out_rows=[]
for i, item in enumerate(ds):
    # 字段: binary labels, video bytes/path, caption, 原始基元名
    raw_labels = item.get("labels") or []  # 或解析 binary label 数组
    metas = set()
    for rl in raw_labels:
        m = CAM_TO_4META.get(rl)
        if m: metas.add(m)
    if len(metas)==1:  # 单标签确定才收
        out_rows.append({
            "shot_id": f"CB{i:05d}",
            "source": "CameraBench_public",
            "clip_path": "",  # 若直接给 bytes 另存为 mp4; 或写 HF path 引用
            "label": list(metas)[0],
            "confidence": 0.99,  # 专家标注近似 1.0
            "vlm_model": "expert_camerabench",
        })
with open(OUT, "w", encoding="utf-8") as f:
    for r in out_rows:
        f.write(json.dumps(r, ensure_ascii=False)+"\n")
print(f"CameraBench 对齐: {len(out_rows)} / {len(ds)} 行 (其余 multi-label 或 semantic-only 丢弃)")
# 然后合并: cat v6_meta_4class.jsonl + camerabench_4meta.jsonl → v6_1_trainset.jsonl
```

---

## 8. 证据闸门自检（本报告发布前必过 5 关）

| 闸门 | 要求 | 是否通过 | 证据 |
|---|---|---|---|
| 🚪1 存在性 | READY 声明全部附文件存在性检查 | ✅ | §6 表格所有 READY 文件在 §5 第 1 步可一键核验 (OK 输出非 MISS) |
| 🚪2 首行证据 | 数据决策基于真实首行/分布 | ✅ | §4.F1 分布图由 `_F1_meta_4class.py` 对实际 7690 行 JSONL 打印；A+C 替换统计在 `_apply_recheck.py` 对 7690 行统计 |
| 🚪3 三对齐 | 训练配置需模型×数据×类名 | ✅ | 附录 A 闸门3核验通过: 4 类名清单 = JSONL label 值集合，严格一致 |
| 🚪4 快照失效 | 结论需时间戳 | ✅ | 报告顶部时间戳 2026-08-24 09:12；若之后有 `git commit` 或新的训练，此报告所有 val_acc 预测自动降级为"待重测" |
| 🚪5 PLAN/READY 分级 | 禁止混用 | ✅ | §1.3 分 PLAN/READY/目标，§6 分 READY/PLAN 两个表格，引用时必须严格区分 |

---

## 9. 跨会话启动一句话 SOP

```
接手 AI 请先：读 §1 任务身份 → 核验 §5 存在性 → 执行 §5.第 1 步 上传 v6_meta_4class.jsonl → 开训
→ 本机并行跑 F3（写 §7.F3 脚本下载 CameraBench 对齐）。
v6 训练 epoch 3 val_acc 出结果后按 §5 分支判断, 不要擅自改 4 元类空间做细粒度。
```

---

> **下次会话接手人**: 请先按 §5 第 1 步跑存在性检查，确认所有 READY 文件都在磁盘上，然后按 §5.第 2 步开训 v6_4meta。**不要**返回细粒度空间。

---

## 附录 A：本会话证据闸门核验原始输出 (2026-08-24)

> 核验脚本: [tmp/_run_evidence_check.py](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/_run_evidence_check.py)
> 原始输出归档: [tmp/evidence_report_20260824.txt](file:///C:/Users/Administrator/Desktop/AE-Knowledge-Vault/tmp/evidence_report_20260824.txt)

```
===== EVIDENCE GATE 1: EXISTENCE CHECK (2026-08-24 09:12 session) =====
OK       7801109 bytes 18229 lines   vlm_labels_v2new.jsonl
OK       3292215 bytes  7691 lines   v5_6_labels_washed.jsonl
OK         78653 bytes   462 lines   suspect_review.jsonl
OK         18550 bytes             recheck_suspects.py
OK        166404 bytes   460 lines   suspect_rechecked.jsonl
OK          3137 bytes     2 lines   suspect_errors.jsonl
OK       3461907 bytes  7690 lines   v5_6_labels_final.jsonl
OK       3666204 bytes  7690 lines   v6_meta_4class.jsonl     << 训练立即用文件
OK          5337 bytes             _F1_meta_4class.py
OK         44242 bytes             train_anime_camera_v5.py
===== EVIDENCE GATE 2: FIRST-LINE + DISTRIBUTION (v6_meta_4class.jsonl, READY) =====
Total rows: 7690
字段清单: [shot_id, video_id, shot_idx, start_sec, end_sec, duration_sec, source_type,
           anime, clip_path, movement_label, speed, stability, confidence, vlm_model,
           annotated_at, label, raw_label]
首行样本 (真实JSON):
  shot_id=BV1144y1B7dm_000, clip_path=D:\AE-Data\AnimeCamera\shots\BV1144y1B7dm_000.mp4
  label=static (raw_label=static) -> 映射后 meta-static，置信度 0.95
4 元类真实分布 (Counter实测):
  meta-zoom               :  4694  61.04%
  meta-static             :  1394  18.13%
  meta-pan                :  1149  14.94%
  meta-tilt-orbit         :   453   5.89%
Gini 系数: 0.5688  [v5_6 6类 Gini=0.7123 -> 下降 20.2%]
===== EVIDENCE GATE 3: 任务签名三对齐 =====
预期类名 (Trainer num_classes=4): [meta-pan, meta-static, meta-tilt-orbit, meta-zoom]
实际 JSONL label 值 (Counter 键): [meta-pan, meta-static, meta-tilt-orbit, meta-zoom]
交集 = 并集 = 4 个类 -> 对齐状态: CHECK 三签名完全一致 (可启动训练)
===== 闸门1 全局: CHECK 全部 READY 文件存在 =====
```


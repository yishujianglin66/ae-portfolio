# 包2 任务书 — ToriiGate 氛围标注 + v5 运镜重训

> **生成日期**: 2026-08-18
> **前置条件**: 包1 v4_5090 已回传验收通过 (val_acc=0.6047, MD5 C9A8DBC...)
> **本包目标**:
>   1. ToriiGate 全库氛围标注 (18235 镜头, mood/time/atmosphere 三维度)
>   2. v5 运镜分类重训 (扩数据集冲 val_acc >= 0.70)

---

## 一、包内容清单

| 文件/目录 | 大小 | 说明 |
|---|---|---|
| `models/ToriiGate-v0.4-2B/` | 4.6 GB | ToriiGate 模型 (Qwen2-VL 微调, 动漫 captioning 专家) |
| `scripts/torii_annotate_atmosphere.py` | 12 KB | 氛围标注脚本 (核心) |
| `scripts/train_anime_camera_v5.py` | 14 KB | v5 重训脚本 (核心) |
| `scripts/RUN_TORII_SMOKE.bat` | — | ToriiGate 冒烟 (20 镜头) |
| `scripts/RUN_TORII.bat` | — | ToriiGate 全量标注 |
| `scripts/RUN_V5_SMOKE.bat` | — | v5 冒烟 (200 样本) |
| `scripts/RUN_V5_TRAIN.bat` | — | v5 全量训练 |
| `data/vlm_labels_v3.jsonl` | ~8 MB | 扩充标签集 (本地 VLM 标注完成后打包) |
| `data/shots/` | 2.0 GB | 未标注镜头视频 (已包含在包内) |
| `models/VideoMAE-MovieShots/movement/` | 345 MB | 底座模型 (v5 从底模重训用) |
| `docs/friend_trae_agent_taskfile_pack2.md` | — | 本文件 |
| `requirements.txt` | — | 依赖列表 |

**总体积**: ~7 GB (主要来自 ToriiGate 模型 4.6 GB + shots 2 GB)

---

## 二、执行流程 (六阶段闸门)

### 阶段0: 装环境
```powershell
# 红线: torch>=2.7+cu128 (5090 Blackwell sm_120 专用)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install transformers qwen-vl-utils decord numpy pillow loguru
pip install safetensors
```

**闸门0**: `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` 输出 `True NVIDIA GeForce RTX 5090 Laptop GPU`

### 阶段1: 验包
```powershell
# 逐文件 exists 检查
python -c "from pathlib import Path; paths=['models/ToriiGate-v0.4-2B/model.safetensors','scripts/torii_annotate_atmosphere.py','scripts/train_anime_camera_v5.py','data/vlm_labels_v3.jsonl']; [print(('OK  ' if Path(p).exists() else 'MISS'), p) for p in paths]"
```

**闸门1**: 所有路径 `OK`, 任一 `MISS` 即停。

### 阶段2: ToriiGate 冒烟
```powershell
# 双击 RUN_TORII_SMOKE.bat 或手动:
py -3.12 scripts/torii_annotate_atmosphere.py --limit 20
```

**闸门2**:
- `data/torii_atmosphere_labels.jsonl` 至少 20 行
- 每行有 mood/time/atmosphere/caption 四字段
- mood ∈ {intense, serene, somber, mysterious, joyful, neutral}
- 无 CUDA OOM 错误 (显存占用应 < 6 GB)

### 阶段3: ToriiGate 全量标注
```powershell
# 双击 RUN_TORII.bat 或手动:
py -3.12 scripts/torii_annotate_atmosphere.py
```

**预计**: 1-2 小时, 支持断点续跑 (中断后重跑会跳过已标注)。

**闸门3**:
- `data/torii_atmosphere_labels.jsonl` 至少 18000 行
- mood/time/atmosphere 三个字段的类别分布合理 (无单一类别占比 > 60%)

### 阶段4: v5 冒烟
```powershell
# 双击 RUN_V5_SMOKE.bat 或手动:
py -3.12 scripts/train_anime_camera_v5.py --limit 200 --epochs 2 --amp --batch-size 8
```

**闸门4**:
- 训练能正常启动, 输出 `epoch 1 step ...` 日志
- epoch 2 后输出 `val_acc=0.xxxx` 非 NaN
- 无 CUDA OOM

### 阶段5: v5 全量训练
```powershell
# 双击 RUN_V5_TRAIN.bat 或手动:
py -3.12 scripts/train_anime_camera_v5.py --epochs 25 --early-stop 5 --amp --batch-size 16
```

**预计**: 4-6 小时 (24k 样本, 25 epochs, 配合早停可能 15-20 轮就停)。

**闸门5**: `models/output/anime_camera_lora_v5/meta.json` 的 `val_acc` 字段:
- `>= 0.70` 保底 ✅
- `>= 0.75` 达标 ✅
- `>= 0.80` 理想 ✅
- `< 0.70` 未达标 ⚠️ (但只要 > v4 的 0.6047 即视为进步)

### 阶段6: 打包回传

**回传文件** (放在同一目录):
1. `v5_result.zip` (约 330 MB)
   - `model.safetensors` (329 MB)
   - `config.json`
   - `meta.json` (含 val_acc, **禁止加工**)
   - `train_history.json` (训练曲线)
2. `torii_atmosphere_labels.jsonl` (~8 MB, 氛围标注产物)
3. `v5_handoff.html` (回传报告, 参考 v4_5090_handoff.html 格式)

**回传 SOP**:
- MD5 对照 (打包后计算 zip MD5 写入 handoff)
- val_acc 原样上报, 禁止修饰
- meta.json 里的字段为准

---

## 三、关键配置说明

### ToriiGate 标注脚本 (`torii_annotate_atmosphere.py`)
- **抽帧策略**: 镜头中点单帧 (氛围判断不需要多帧, 单帧足够)
- **Prompt**: JSON 模式输出 mood/time/atmosphere/caption 四字段
- **标签 schema**:
  - mood (6类): intense/serene/somber/mysterious/joyful/neutral
  - time (4类): day/night/dawn_dusk/unknown
  - atmosphere (6类): urban/nature/interior/battlefield/magical/abstract
- **解码**: 贪心解码 (temperature=0, 标签任务要确定性)
- **断点续跑**: 已标注的 shot_id 自动跳过

### v5 重训脚本 (`train_anime_camera_v5.py`)
- **双模式**:
  - 默认: 从底模重训 (推荐, 避免继承 v4 偏差)
  - `--resume-from <v4_5090路径>`: 从 v4 续训 (warm start, lr 自动降到 1e-5)
- **v5 改进点** (相对 v4):
  1. 数据扩充 2.5x: v4 用 10282 样本 → v5 用 ~24k
  2. label smoothing 0.1 (v4 在 60% 饱和, smoothing 防过拟合)
  3. mixup 0.2 (运镜类间语义重叠, mixup 提升泛化)
  4. early_stop 放宽到 5 (扩数据后波动更大)
  5. epochs 25 (扩数据需要更多轮次)
- **保留 v4 优点**: 全参微调, 六类 schema, 时间反转增强, 类权重

### 与 v4_5090 对比基线
| 维度 | v4_5090 | v5 |
|---|---|---|
| 训练样本 | 10282 | ~24000 (2.5x) |
| 训练模式 | full_ft | full_ft |
| epochs | 20 | 25 |
| early_stop | 4 | 5 |
| label_smoothing | 无 | 0.1 |
| mixup | 无 | 0.2 |
| val_acc | 0.6047 | 目标 >= 0.70 |
| best_epoch | 14 | 待测 |

---

## 四、故障排查

### CUDA OOM
```
RuntimeError: CUDA out of memory
```
- ToriiGate: 显存占用应 < 6 GB, 5090 24GB 不会 OOM。若发生, 检查是否有其他进程占用
- v5 训练: batch_size=16 约占 4-5 GB。若 OOM, 降到 `--batch-size 8`

### ToriiGate JSON 解析失败
- 脚本已容错 (正则提取 `{...}` 块), 失败的会跳过并记录 warning
- 若失败率 > 5%, 检查模型是否完整加载

### v5 数据加载失败
- `decord` 解码失败: 检查 `data/shots/` 下的 mp4 是否完整
- clip_path 不存在: 检查 `data/vlm_labels_v3.jsonl` 里的路径

### 断点续跑
- ToriiGate: 重跑 `RUN_TORII.bat` 会自动跳过已标注
- v5: 训练不支持断点续跑, 中断后需从头开始 (但 25 epochs 配早停通常 4-6 小时一次跑完)

---

## 五、预期产出

### ToriiGate 标注产物 (`data/torii_atmosphere_labels.jsonl`)
```json
{"shot_id":"BV1A1bfzZEcn_005","video_id":"BV1A1bfzZEcn","shot_idx":5,
 "anime":"一拳超人","source_type":"amv",
 "mood":"intense","time":"night","atmosphere":"battlefield",
 "caption":"A hero stands in a destroyed city under a dark sky, debris scattered around.",
 "annotated_at":"2026-08-19 10:23:45"}
```

### v5 训练产物 (`models/output/anime_camera_lora_v5/`)
```
model.safetensors     (329 MB, 全参完整模型)
config.json           (VideoMAEForVideoClassification, num_labels=6)
meta.json             (val_acc, best_epoch 等训练元数据)
train_history.json    (每轮 loss/val_acc/lr, 含进度曲线数据)
```

---

## 六、验收标准

| 产物 | 验收标准 |
|---|---|
| torii_atmosphere_labels.jsonl | 行数 >= 18000, 三维度类别分布合理 |
| v5 meta.json val_acc | >= 0.70 保底 / >= 0.75 达标 / >= 0.80 理想 |
| v5 model.safetensors | 198 keys, classifier.weight shape=(6,768) |

**回传三步校验** (本地 Owner 侧):
1. MD5 对照 (zip 包)
2. val_acc 对账 (meta.json 字段)
3. safetensors 加载测试 (198 keys 完整)

---

## 七、与包1的差异

| 维度 | 包1 | 包2 |
|---|---|---|
| 核心任务 | 运镜分类初训 (v4) | ToriiGate 标注 + v5 重训 |
| 模型体积 | 345 MB (底模) | 4.6 GB (ToriiGate) + 345 MB (底模) |
| 数据 | 6166 标注 | ~24k 标注 (本地扩充后) |
| 预计耗时 | 3h | 1-2h 标注 + 4-6h 训练 |
| 回传体积 | 305 MB | 330 MB (v5) + 8 MB (标注) |

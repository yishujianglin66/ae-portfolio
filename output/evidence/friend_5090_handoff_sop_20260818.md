# 交接 SOP：AE-Knowledge-Vault 模型训练包执行手册

> **本文件是给执行方 AI 智能体（或人类）的完整操作说明。**
> 目标：在本机（RTX 5090 Laptop 24GB）完成运镜分类器大权限训练，产出 adapter 权重。
> 版本 V1 · 2026-08-18 · 产出方: AE-Knowledge-Vault 主项目

---

## 0. 硬件与环境红线（先读，否则必踩坑）

| 项 | 要求 | 原因 |
|---|---|---|
| GPU | RTX 5090 24GB ✓ | Blackwell 架构 sm_120 |
| PyTorch | **≥ 2.7.0 且 cu128** | 旧版（cu121/cu124）在 5090 上报 `no kernel image is available`，网上旧教程全部不适用 |
| Python | 3.11 / 3.12 | 项目代码用了 `X | Y` 类型语法 |
| CUDA 驱动 | ≥ 550.x | 随 5090 出厂驱动即可 |

一键装环境（管理员 PowerShell，在包根目录）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

## 1. 包内清单（收到先核对）

```
train_pack_v1/
├─ RUN_SMOKE.bat            # 第一步：5分钟冒烟（200样本，验证环境OK）
├─ RUN_TRAIN.bat            # 第二步：正式训练（约6-9小时，可过夜）
├─ requirements.txt
├─ scripts/train_anime_camera_lora.py   # 训练脚本（已含云端大训练参数）
├─ base_model/videomae-movieshots/      # 底模 329MB（离线自带，无需下载）
├─ data/anime_camera/
│   ├─ vlm_labels_clean.jsonl           # 清洗后标签（如未清洗则用 vlm_labels.jsonl）
│   └─ shots/                           # 视频 clips（训练数据）
└─ docs/SOP_本文件.md
```

## 2. 执行步骤

### 第一步：冒烟（必须先跑，5 分钟）

```powershell
.\RUN_SMOKE.bat
# 等价命令:
# python scripts/train_anime_camera_lora.py --label-schema six --epochs 1 --limit 200 --batch-size 4 --lora-rank 64 --unfreeze 2 --amp --early-stop 3 --out models/output/smoke_test
```

**通过标准**：日志出现 `trainable params: ~19%` + 跑完输出 `best val_acc=`（数值多少无所谓，能跑完就是环境 OK）。

### 第二步：正式训练（约 6-9 小时，建议过夜）

```powershell
.\RUN_TRAIN.bat
# 等价命令:
# python scripts/train_anime_camera_lora.py --label-schema six --epochs 20 --batch-size 16 --lora-rank 64 --unfreeze 2 --amp --early-stop 4 --lr 3e-4 --out models/output/anime_camera_lora_v4_5090
```

**监控要点**：
- 每个 epoch 结束打印 `val acc`，最佳会自动保存
- 连续 4 轮不提升自动早停（正常现象，防过拟合）
- 中途断电/关机：重新跑同命令会从头开始（无断点续训），所以尽量一次跑完

### 第三步：验收 + 打包回传

训练完成后，把整个产物目录打包：

```powershell
# 确认产物存在且完整（应包含以下4个文件）
dir models\output\anime_camera_lora_v4_5090
# adapter_model.safetensors  (~10MB, r=64会比r=8大)
# adapter_config.json
# meta.json                  (内含 val_acc 最终成绩)
# README.md

# 打包
Compress-Archive -Path models\output\anime_camera_lora_v4_5090 -DestinationPath v4_5090_result.zip
# 顺带打包训练日志（如果重定向过输出）
```

**回传物只有这一两个 zip（约10MB），不用传数据集。**

## 3. 成功标准

| 等级 | val_acc | 含义 |
|---|---|---|
| 保底 | ≥ 0.70 | 超过当前 0.483，链路有效 |
| 达标 | ≥ 0.75 | 原定目标 |
| 理想 | ≥ 0.80 | 超预期 |

meta.json 里的 `val_acc` 字段为准，不需要人为加工任何数字。

## 4. 常见故障排查

| 症状 | 原因 | 解法 |
|---|---|---|
| `no kernel image is available` | PyTorch 版本旧，不支持 sm_120 | 重装 `torch>=2.7.0+cu128` |
| CUDA out of memory | 显存不足 | `--batch-size 16` 降到 `8`，加 `--grad-checkpoint` |
| 训练极慢（<1 it/s） | 落在核显/CPU 上 | 确认 `nvidia-smi` 里有 python 进程占显存 |
| labels 数量不匹配 | 用了旧 schema | 必须带 `--label-schema six` |

## 5. 数据安全承诺

- 本包数据仅用于本项目训练，训练完成后可整包删除
- 回传仅需产物 zip，训练数据无需回传

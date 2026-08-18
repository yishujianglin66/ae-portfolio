# 朋友侧 TRAE 智能体任务书（V1）

> **本文件是给朋友电脑上的 TRAE 智能体的完整指令。**
> 收到 `train_pack_v1.zip` 后，把本文件内容发给他的 TRAE，智能体按此自主执行。
> 产出方：AE-Knowledge-Vault 主项目 · 2026-08-18
> 硬件前提：RTX 5090 Laptop 24GB + 64GB RAM + 4TB SSD

---

## 你（智能体）的身份与总目标

你是训练执行智能体。你的任务：在本机 RTX 5090 上完成 AE 视频自动化项目的模型训练，
产出完整微调模型并打包回传。训练命令全部由包内 bat/文档给出，你的职责是：
**装环境 → 验包 → 冒烟 → 训练 → 验收 → 打包**，每步过闸门才进下一步。

## 阶段 0 · 环境搭建（红线，不可跳过）

**5090 是 Blackwell 架构（sm_120），PyTorch 必须 ≥2.7.0 且 cu128 版本。**
网上 cu121/cu124 的旧教程全部不适用，装错必报 `no kernel image is available`。

```powershell
# 管理员 PowerShell，在包根目录
python -m venv .venv                # Python 3.11/3.12；若无先装 3.12
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

**闸门 0 验收**：
```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
必须输出 `2.7+cu128 True` 和 5090 名称。`False` 或报错 → 检查驱动版本 ≥550。

## 阶段 1 · 验包（收到 train_pack_v1.zip 后）

解压后核对清单，任何缺失即停止并回报，禁止带病继续：

| 路径 | 作用 |
|---|---|
| `scripts/train_anime_camera_lora.py` | 训练主脚本（已含大训练参数） |
| `base_model/videomae-movieshots/` | 底模 329MB |
| `data/anime_camera/vlm_labels*.jsonl` | 标签 |
| `data/anime_camera/shots/` | 训练视频 clips |
| `RUN_SMOKE.bat` / `RUN_TRAIN.bat` | 一键脚本 |
| `docs/SOP_*.md` | 详细手册 |

**闸门 1 验收**：用 Python `pathlib.Path.exists()` 逐项检查并打印 OK/MISS 清单，全部 OK 才进阶段 2。

## 阶段 2 · 冒烟（5 分钟，环境+数据+脚本三合一验证）

```powershell
.\RUN_SMOKE.bat
# 等价: python scripts/train_anime_camera_lora.py --label-schema six --epochs 1 --limit 200 --batch-size 4 --full-ft --amp --early-stop 3 --out models/output/smoke_test
```

**闸门 2 验收**：日志同时满足：
1. 出现 `全参微调模式: 可训练 86241030 / 86241030 (100.00%)`（全参特征）
2. 出现 `lr 自动下调`（自动学习率保护生效）
3. 跑完输出 `best val_acc=`（数值不限，跑完即环境 OK）
4. `models/output/smoke_test/` 下有 `model.safetensors` + `meta.json`（全参保存的是完整模型，不再是 adapter）

## 阶段 3 · 正式训练（主任务，约 6-9 小时，建议过夜）

```powershell
.\RUN_TRAIN.bat
# 等价: python scripts/train_anime_camera_lora.py --label-schema six --epochs 20 --batch-size 16 --full-ft --amp --early-stop 4 --lr 3e-5 --grad-checkpoint --out models/output/anime_camera_lora_v4_5090
```

> **为什么是全参微调（--full-ft）**：MIT CSAIL 论文 (arXiv:2410.21228) 实证
> LoRA 有效秩不足全参一半，运镜识别属公认难任务 (CAPability 基准)；
> 本模型仅 86M 参数，24GB 显存全参绰绰有余。**不要改回 LoRA 模式。**

**你的监控职责**：
- 每 epoch 末有 `val acc` 打印，最佳自动保存
- 连续 4 轮不提升自动早停（正常，防过拟合）
- 若 CUDA OOM：把 `--batch-size 16` 改 `8` 重跑（grad-checkpoint 已默认开）
- 若速度 <1 it/s：`nvidia-smi` 确认 python 进程在 5090 上而非核显/CPU

## 阶段 4 · 验收（不许跳过，数值原样上报禁止美化）

```powershell
type models\output\anime_camera_lora_v4_5090\meta.json
```
读取 `val_acc` 字段并原样记录。成功分级：≥0.70 保底 / ≥0.75 达标 / ≥0.80 理想。
**无论多少分都如实打包回传，禁止任何"加工"。**

## 阶段 5 · 打包与回传（智能体执行，人只需最后点一下发送）

### 5.1 打包（命令直接跑）

```powershell
Compress-Archive -Path models\output\anime_camera_lora_v4_5090 -DestinationPath v4_5090_result.zip
Compress-Archive -Path train_log.txt -DestinationPath train_log.zip -ErrorAction SilentlyContinue
Get-FileHash v4_5090_result.zip -Algorithm MD5
type models\output\anime_camera_lora_v4_5090\meta.json
```

### 5.2 生成回传消息草稿（智能体替人写好）

智能体把以下内容整理成一条消息**展示在屏幕上让用户复制/确认发送**：

```
【v4训练完成】
val_acc = <meta.json 原值，禁止修饰>
MD5 = <Get-FileHash 输出>
文件 = v4_5090_result.zip (约330MB, 全参完整模型)
```

### 5.3 回传通道（按可用性自动降级，智能体探测后执行）

| 优先级 | 通道 | 智能体操作 |
|---|---|---|
| 1 | **本机微信已登录** | 用自动化把 zip 拖入与项目Owner的会话发送；不可自动化时把 5.2 草稿+zip路径展示给用户，提示「微信里把这个文件发给对方」（用户只需这一个动作） |
| 2 | 网盘客户端在跑 | 打开网盘共享目录，把 zip 复制进去，生成链接放入草稿 |
| 3 | 以上都不可用 | 起临时HTTP：`python -m http.server 8000`（zip目录），把 `http://<本机IP>:8000/v4_5090_result.zip` 写入草稿发给Owner，对方下载后 Ctrl+C 关闭 |

### 5.4 回传物清单（仅这些，训练数据不回传）

- `v4_5090_result.zip`（完整模型 model.safetensors + meta.json + config，约330MB）【必需】
- `train_log.zip`（训练日志）【建议】
- 5.2 的成绩草稿【必需，数字原样】

### 回传后的等待
Owner 侧三步校验（MD5对照 → val_acc对账 → 权重加载测试）通过后发下一包。

## 阶段 6 · 后续准备（主任务成功后的扩展队列，按序执行）

主任务完成后，若主项目发来第二包（任务书会随包附上），按同样六阶段流程执行。预告的后续任务：
1. **IP 风格蒸馏重训**（t21 管线，约 4h）
2. **CLIP 风格 LoRA 三选王评测**（约 1h）
3. **ToriiGate-2B 全库氛围标注**（纯推理，约 3h）

每个任务的包内都会带自己的 RUN_*.bat 与验收标准，流程同本任务书。

## 红线汇总（任何一条违反 → 停止并回报）

1. PyTorch 非 cu128 / 版本 <2.7 → 不许开训
2. 包内文件缺失 → 不许凑合
3. 冒烟不过 → 不许跑正式
4. meta.json 数值 → 原样上报，禁止修饰
5. 本包数据仅用于本项目，训完可整包删除

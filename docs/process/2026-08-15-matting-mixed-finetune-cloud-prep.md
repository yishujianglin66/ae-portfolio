# BiRefNet 混合微调 — 云端无卡模式准备清单（照做版）

> 日期：2026-08-15 · 目标：把「动漫1111对 + CelebA人像 + VOC/cityscapes/ADE 真实场景」的混合微调跑上云端
> 原理：AutoDL 先开「无卡模式」（约 0.1 元/时）把文件、数据、依赖、路径全部备好，确认无误后再切「有卡模式」真正训练——准备阶段几乎免费，GPU 只花在刀刃上。

---

## 0. 你要租的实例（有卡阶段）

| 项 | 值 |
|---|---|
| 显卡 | **RTX 4090 24GB**（按量计费，约 2 元/时） |
| 镜像 | **PyTorch 2.1+（CUDA 12.x）** |
| 数据盘 | ≥ 30GB |

## 1. 开无卡模式实例

AutoDL 控制台 → 租用新实例 → 选 4090 24GB → **勾选"无卡模式开机"**（不选 GPU，约 0.1 元/时）→ 镜像选 PyTorch 2.1+。

## 2. 上传文件（从本地 PowerShell 执行）

先打包需要传的 4 个脚本 + 动漫数据 + BiRefNet 模型：

```powershell
cd C:\Users\Administrator\Desktop\AE-Knowledge-Vault
tar -cf D:\AE-Data\matting_cloud.tar `
  scripts/build_matting_dataset.py `
  scripts/gen_celeba_pseudo_mask.py `
  scripts/finetune_birefnet.py `
  scripts/cloud_matting_pipeline.py `
  external\animeseg\imgs-masks.zip `
  external\birefnet
```

上传（替换成你的实例 SSH 端口/地址，AutoDL 控制台有「SSH 登录指令」）：

```powershell
scp -P <端口> D:\AE-Data\matting_cloud.tar root@<实例IP>:/root/autodl-tmp/
```

云端解压：

```bash
cd /root/autodl-tmp && tar -xf matting_cloud.tar
# 结果应出现: build_matting_dataset.py / gen_celeba_pseudo_mask.py /
#             finetune_birefnet.py / cloud_matting_pipeline.py /
#             imgs-masks.zip / birefnet/ (模型)
```

## 3. 装依赖（无卡模式 CPU 也能装）

```bash
cd /root/autodl-tmp
# BiRefNet remote code 需要 kornia/timm（管线自检只查 torch/transformers/cv2，这两个必须手动装）
pip install kornia timm einops accelerate -i https://pypi.tuna.tsinghua.edu.cn/simple
# 基础环境（镜像通常已有，缺什么补什么）
pip install transformers safetensors opencv-python-headless numpy -i https://pypi.tuna.tsinghua.edu.cn/simple
```

验证：`python -c "import torch, transformers, cv2, kornia, timm"` 无报错即 OK。

## 4. 数据准备（关键！管线路径约定必须吻合）

管线硬编码这些路径（见 `cloud_matting_pipeline.py`），务必照做：

| 云端路径 | 内容 | 来源 |
|---|---|---|
| `/root/autodl-tmp/datasets/VOC2012` | VOC2012（SegmentationClass + JPEGImages） | autodl-pub 挂载 |
| `/root/autodl-tmp/datasets/ADEChallengeData2016` | ADE（annotations + images） | autodl-pub 挂载 |
| `/root/autodl-tmp/datasets/cityscapes` | cityscapes（gtFine + leftImg8bit） | autodl-pub 挂载 |
| `/root/autodl-tmp/celeba/img_align_celeba/*.jpg` | CelebA 对齐人脸 | autodl-pub 挂载 |
| `/root/autodl-tmp/birefnet/model.safetensors` | BiRefNet 模型 | 已上传 |
| `/root/autodl-tmp/imgs-masks.zip` | animeseg 动漫数据 | 已上传 |

AutoDL 的 25 个公开数据集挂载在 `/root/autodl-pub/`，用**软链**把需要的指到约定路径（零拷贝零配额）：

```bash
cd /root/autodl-tmp
mkdir -p datasets celeba
# 先看看挂载里实际叫什么（不同批次实例目录名可能不同）
ls /root/autodl-pub/ | grep -iE "voc|city|ade|celeb"
# 按实际名字软链（以 ls 结果为准，这里是最常见的名字）
ln -s /root/autodl-pub/VOCdevkit/VOC2012       datasets/VOC2012
ln -s /root/autodl-pub/ADEChallengeData2016    datasets/ADEChallengeData2016
ln -s /root/autodl-pub/cityscapes              datasets/cityscapes
ln -s /root/autodl-pub/CelebA/img_align_celeba celeba/img_align_celeba
```

> 路径探测已内置：`build_matting_dataset.py` 会自动找 `VOC2012`、`cityscapes/gtFine`、`ADEChallengeData2016` 的常见嵌套位置，软链的父目录指对即可。

## 5. 建标记文件（管线自检靠它们）

```bash
cd /root/autodl-tmp
echo "EXTRACT_DONE" > datasets/.extract_done
echo "CELEBA_DONE"  > celeba/.done
```

## 6. 验证前置就绪（照搬管线的自检逻辑）

```bash
python -c "import torch, transformers, cv2, kornia, timm; print('deps OK')"
cat datasets/.extract_done 2>/dev/null
cat celeba/.done 2>/dev/null
ls -la birefnet/model.safetensors
ls -la imgs-masks.zip
ls datasets/VOC2012 2>/dev/null | head -3   # 应看到 SegmentationClass
ls datasets/ADEChallengeData2016 2>/dev/null | head -3
ls datasets/cityscapes/gtFine 2>/dev/null | head -3
ls celeba/img_align_celeba/*.jpg 2>/dev/null | head -3
```

全都有输出即就绪。**先跑一次 build 脚本验证数据可读（无卡模式即可）**：

```bash
cd /root/autodl-tmp
python build_matting_dataset.py --out /tmp/test_build \
  --anime /root/autodl-tmp/animeseg 2>/dev/null \
  --voc datasets/VOC2012 --cityscapes datasets --ade datasets/ADEChallengeData2016
# 预期看到: VOC2012 person: N / cityscapes person: N / ADE20k person: N / anime: N
rm -rf /tmp/test_build
```

## 7. 切有卡模式 → 一键训练

AutoDL 控制台 → 关机 → 重新开机选「有卡模式（4090）」→ 用 SSH 登录：

```bash
cd /root/autodl-tmp
# 本地 Windows 设 SSHPASS 后，在本地跑编排脚本（它会全自动：构建→CelebA伪mask→微调→回传）
# 本地 PowerShell:
#   $env:SSHPASS="你的实例密码"
#   python scripts/cloud_matting_pipeline.py
```

管线自动执行：
1. 解压 animeseg → 2. build 混合训练集 → 3. CelebA 4000 张伪 mask（GPU）→ 4. 混合微调 8 epochs → 5. 回传 `external/birefnet/finetuned_anime_mixed.pth`

## 8. 验收（本地）

回传完成后，本地验证：

```bash
python -c "
import torch
sd = torch.load('external/birefnet/finetuned_anime_mixed.pth', map_location='cpu')
print('权重参数数:', len(sd), '| 首个键:', list(sd.keys())[0])
"
```

然后跑 COCO 评估对比微调前后（需云上 COCO，或用 `scripts/eval_birefnet_coco.py`）。

## 9. 省钱提醒

- **训练完立即关机**（有卡按量计费，关机不扣 GPU 费，数据保留）
- 无卡模式下所有准备（2-6 步）成本不到 1 元
- 预算估算：CelebA 伪 mask 2-3h + 微调 3-5h ≈ **12-18 元**

## 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| `kornia` / `timm` ModuleNotFound | BiRefNet remote code 依赖 | `pip install kornia timm` |
| build 输出全 0 | 软链路径不对 | `ls` 核对 autodl-pub 实际目录名，重建软链 |
| `.extract_done` 检查失败 | 标记没建 | 重跑第 5 步 |
| `No matching distribution` | 网络代理 | 所有 pip 加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 显存不足 | batch 8 在 24GB 不够 | 训练命令加 `--batch 6`（脚本已参数化） |

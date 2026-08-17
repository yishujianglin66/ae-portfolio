# 双算力云并行任务分配（2026-08-15）

> 两台 AutoDL 实例并行推进 BiRefNet 微调与评估。任务按 GPU 依赖拆分：
> 实例 A = 训练（GPU 密集）；实例 B = 评估/预处理（与训练无依赖，可先跑基线）。

## 任务分配矩阵

| 任务 | 实例 A（已连接） | 实例 B（待凭据） | 依赖 |
|---|---|---|---|
| BiRefNet 动漫微调 8 epochs | ✅ 进行中（batch 4 续训 ep0） | — | — |
| COCO 微调后评估（A 组） | ✅ 训练完成后自动衔接 | — | A 训练回传 |
| **COCO 基线评估（原版 BiRefNet）** | — | ✅ **现在就能跑** | 无 |
| 检测器召回率（YOLO/Owlv2 on COCO person） | — | ✅ 无依赖 | 无 |
| Vimeo-90k 时序指标基准化 | — | ✅ 无依赖 | 无 |
| CelebA 数据预处理（混合微调备料） | — | ✅ 无依赖 | 无 |
| VOC 第二套评估 | — | 可与 COCO 并行 | 无 |

## 实例 B 操作流程（另一并行程序按此执行）

1. **连接**：SSH 凭据待用户提供（`cloud_ops.py` 已参数化，改 HOST/PORT/PASS 即可复用）
2. **环境**（复用 A 的坑位经验）：
   ```bash
   /root/miniconda3/bin/pip install -q -U transformers==5.14.1 safetensors opencv-python-headless einops kornia timm
   # torch 若 <2.6 需升级: pip install torch==2.6.0+cu118 --index-url https://download.pytorch.org/whl/cu118
   ```
3. **上传**：`eval_birefnet_coco.py` + `external/birefnet/`（config+birefnet.py+model.safetensors，~430MB）
4. **跑基线评估**：
   ```bash
   cd /root/autodl-tmp
   /root/miniconda3/bin/python eval_birefnet_coco.py --out eval_base.json   # 原版，不加 --weights
   ```
5. **产出回传**：`eval_base.json` 回传本地 `output/step2_locator/`，供与实例 A 的微调后结果做 A/B
6. **继续**：Vimeo-90k 基准化脚本（`eval_vimeo_temporal.py`，本会话稍后补）→ CelebA 预处理

## 协作协议（两程序/两实例协调）

- **互不 ssh 对方实例**：A 归本会话，B 归另一程序，凭据隔离
- **共享结论经本地 git**：两边的结果 JSON 都回传本地提交，A/B 对比在本地做
- **任务编号**：A1=微调训练 / B1=COCO基线 / B2=检测器召回 / B3=Vimeo / B4=CelebA，进度在本文打勾

## 进度跟踪

- [x] A1 微调训练（实例 A 进行中）
- [ ] A2 微调后 COCO 评估
- [ ] B1 COCO 基线评估（原版）
- [ ] B2 检测器召回率
- [ ] B3 Vimeo-90k 时序基准化
- [ ] B4 CelebA 预处理

---

> 实例 B 凭据到位后：另一程序直接跑 B1-B4；本会话跑 A1-A2 与最终 A/B 汇总。

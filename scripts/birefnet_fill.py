"""BiRefNet 补抠缺失帧：对 MatAnyone 链路缺失帧（面积<1%）用 BiRefNet 逐帧抠像补充
（BiRefNet 单帧主体抠像，不依赖时域，转身/模糊段可用）
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

from core.torch_runtime import get_device, infer_ctx

CUR = Path("output/step2_locator/matanyone_seg_final")   # v12 最终输出
VIDEO = "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"
OUT = Path("output/step2_locator/matanyone_seg_biref")
START = 100

print("loading BiRefNet...", file=sys.stderr)
model = AutoModelForImageSegmentation.from_pretrained(
    "external/birefnet", trust_remote_code=True, local_files_only=True).eval().cuda()
# 权重优先级: 混合微调(VOC IoU 0.75, 2026-08-16 A/B 实证) > 动漫微调 > 基座
_weight_chain = [
    Path("external/birefnet/finetuned_anime_mixed.pth"),
    Path("external/birefnet/finetuned_anime.pth"),
]
_loaded = False
for _finetuned in _weight_chain:
    if not _finetuned.exists() or _loaded:
        continue
    try:
        _sd = torch.load(_finetuned, map_location="cpu")
        if isinstance(_sd, dict) and "state_dict" in _sd:
            _sd = _sd["state_dict"]
        model.load_state_dict(_sd)
        print(f"[BiRefNet] 已加载微调权重 {_finetuned.name}", file=sys.stderr)
        _loaded = True
    except Exception as _e:
        print(f"[BiRefNet] {_finetuned.name} 加载失败, 试下一个: {_e}", file=sys.stderr)
if not _loaded:
    print("[BiRefNet] 无可用微调权重, 使用基座", file=sys.stderr)
model.eval().cuda()
tf = transforms.Compose([
    transforms.ToTensor(),
    transforms.Resize((1024, 1024)),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])
print("ready", file=sys.stderr)

# 找缺失帧
missing = []
for p in sorted(CUR.glob("mask_*.png")):
    gi = int(p.stem.split("_")[-1])
    m = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if m is None:
        continue
    if np.count_nonzero(m) / (m.shape[0] * m.shape[1]) < 0.01:
        missing.append(gi)
print(f"缺失帧: {missing}", file=sys.stderr)

cap = cv2.VideoCapture(VIDEO)
frames = {}
for gi in missing:
    cap.set(cv2.CAP_PROP_POS_FRAMES, gi)
    ret, frame = cap.read()
    if ret:
        frames[gi] = frame
cap.release()

OUT.mkdir(parents=True, exist_ok=True)
n_used = 0
t0 = time.time()
for p in sorted(CUR.glob("mask_*.png")):
    gi = int(p.stem.split("_")[-1])
    m = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if gi in frames:
        frame = frames[gi]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        inp = tf(rgb).unsqueeze(0).half().cuda()
        with infer_ctx(get_device()):
            pred = model(inp)[-1].sigmoid().cpu()[0].squeeze().float().numpy()
        h, w = frame.shape[:2]
        pred = cv2.resize(pred, (w, h), interpolation=cv2.INTER_LINEAR)
        alpha = (pred * 255).astype(np.uint8)
        # 最大连通域裁剪：BiRefNet 主体抠像可能带背景碎片，取最大连通域保主体
        binm = (alpha > 127).astype(np.uint8)
        n_cc, labels, stats, _ = cv2.connectedComponentsWithStats(binm, connectivity=8)
        if n_cc > 1:
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            alpha = np.where(labels == largest, alpha, 0).astype(np.uint8)
        area = np.count_nonzero(alpha > 127) / (h * w)
        if 0.01 <= area <= 0.40:
            # BiRefNet 输出面积合理 → 采用（并做软 alpha 二值化阈值 127）
            out = alpha
            n_used += 1
        else:
            out = m  # 保留原（填充）输出
        cv2.imencode(".png", out)[1].tofile(str(OUT / p.name))
    else:
        cv2.imencode(".png", m)[1].tofile(str(OUT / p.name))
print(f"BiRefNet 补抠 {n_used}/{len(frames)} 帧（面积合理者）in {time.time()-t0:.0f}s -> {OUT}", file=sys.stderr)

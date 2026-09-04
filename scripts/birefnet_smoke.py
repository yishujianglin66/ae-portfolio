"""BiRefNet 集成冒烟：单帧推理验证"""
import sys
import cv2
import numpy as np
import torch
from core.torch_runtime import infer_ctx
from torchvision import transforms

from transformers import AutoModelForImageSegmentation

print("loading BiRefNet...", file=sys.stderr)
model = AutoModelForImageSegmentation.from_pretrained(
    "external/birefnet", trust_remote_code=True, local_files_only=True)
model.eval()
device = "cuda"
model.to(device)
print("model ready", file=sys.stderr)

tf = transforms.Compose([
    transforms.ToTensor(),
    transforms.Resize((1024, 1024)),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

# 帧 170（转身中段，之前 MatAnyone 缺失）
cap = cv2.VideoCapture("data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4")
cap.set(cv2.CAP_PROP_POS_FRAMES, 170)
ret, frame = cap.read()
cap.release()
h, w = frame.shape[:2]
rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
pil = tf(rgb).unsqueeze(0).half().to(device)

import time
t0 = time.time()
with infer_ctx(device):
    preds = model(pil)[-1].sigmoid().cpu()
dt = time.time() - t0
pred = preds[0].squeeze().float().numpy()  # 1024x1024
pred = cv2.resize(pred, (w, h), interpolation=cv2.INTER_LINEAR)
alpha = (pred * 255).astype(np.uint8)
area = float(np.count_nonzero(alpha > 127)) / (h * w)
print(f"帧 170: 推理 {dt:.1f}s, alpha>127 面积 {area:.3f}")
cv2.imencode(".png", alpha)[1].tofile("output/step2_locator/_birefnet_170.png")
print("saved")

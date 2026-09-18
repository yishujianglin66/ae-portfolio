"""Owlv2 开放词汇检测冒烟：动漫人物检测锚定测试（替代 YOLO）"""
import sys
import time

import cv2
import numpy as np
import torch
from transformers import Owlv2ForObjectDetection, Owlv2Processor

from core.torch_runtime import get_device, infer_ctx

print("loading Owlv2...", file=sys.stderr)
model = Owlv2ForObjectDetection.from_pretrained(
    "external/owlv2", local_files_only=True).eval().cuda()
try:
    processor = Owlv2Processor.from_pretrained("external/owlv2", local_files_only=True)
except Exception as e:
    print(f"processor 加载失败: {e}", file=sys.stderr)
    sys.exit(2)
print("ready", file=sys.stderr)

cap = cv2.VideoCapture("data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4")
TEXTS = [["anime character"], ["person"]]
for gi in [170, 172, 176, 292, 300]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, gi)
    ret, frame = cap.read()
    if not ret:
        continue
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    t0 = time.time()
    with infer_ctx(get_device()):
        inputs = processor(text=TEXTS, images=rgb, return_tensors="pt").to("cuda")
        outputs = model(**inputs)
        results = processor.post_process_grounded_object_detection(
            outputs=outputs, target_sizes=torch.tensor([rgb.shape[:2]]), threshold=0.15)
    dt = time.time() - t0
    boxes = results[0]["boxes"].cpu().numpy()
    scores = results[0]["scores"].cpu().numpy()
    labels = results[0]["labels"].cpu().numpy()
    good = [(int(b[0]), int(b[1]), int(b[2]), int(b[3]), round(float(s), 2))
            for b, s in zip(boxes, scores) if s > 0.2]
    print(f"帧 {gi}: {dt:.2f}s, 检测 {len(good)} 个: {good[:4]}")
cap.release()

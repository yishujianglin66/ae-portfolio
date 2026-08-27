#!/usr/bin/env python3
"""生成 MG动画 + 手书动画演示产物"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.makedirs("output_production", exist_ok=True)

# 1. MG 数据图表动画 MP4
print("=" * 60)
print("[1/3] MG Template Engine → 数据图表动画 MP4")
from core.mg_template_engine import MGTemplateEngine
engine = MGTemplateEngine()

result = engine.render(
    {
        "type": "data_chart",
        "subtype": "bar",
        "data": [
            {"label": "Q1", "value": 42},
            {"label": "Q2", "value": 68},
            {"label": "Q3", "value": 55},
            {"label": "Q4", "value": 85},
        ],
        "style": {"bg": "#1a1a2e", "accent": "#4fc3f7", "secondary": "#e040fb", "text": "#ffffff"},
        "duration": 3.0,
        "fps": 24,
        "resolution": [1280, 720],
    },
    "output_production/mg_data_chart_demo.mp4",
    backend="pillow_ffmpeg",
)
print(f"  结果: {result}")

# 2. Lottie JSON 导出
print("\n[2/3] Lottie Exporter → MG 动画 JSON")
from core.lottie_exporter import LottieExporter
exporter = LottieExporter()
result2 = exporter.create_animation(
    layers=[
        {"type": "text", "text": "MG Animation Demo", "animation": "fade_in", "color": "#ffffff", "font_size": 60},
        {"type": "shape", "shape": "circle", "animation": "scale_up", "color": "#4fc3f7", "size": 150, "delay": 0.5},
        {"type": "shape", "shape": "rect", "animation": "slide_left", "color": "#e040fb", "size": 100, "delay": 1.0},
    ],
    output_path="output_production/mg_lottie_demo.json",
    duration_sec=3,
    fps=30,
    width=1280,
    height=720,
    bg_color="#1a1a2e",
)
print(f"  状态: {result2['status']}, 图层数: {result2['layer_count']}, 总帧数: {result2['total_frames']}")

# 验证 Lottie
validation = exporter.validate_lottie("output_production/mg_lottie_demo.json")
print(f"  验证: valid={validation['valid']}, 分辨率={validation['resolution']}")

# 3. 手绘风格化
print("\n[3/3] HanddrawnStyler → 手绘风格化图像")
from core.handdrawn_styler import HanddrawnStyler
import numpy as np
from PIL import Image

# 创建渐变测试图像
arr = np.zeros((512, 512, 3), dtype=np.uint8)
for y in range(512):
    for x in range(512):
        arr[y, x] = [int(255 * x / 512), int(255 * y / 512), 128]
img = Image.fromarray(arr)
img.save("output_production/test_input_gradient.png")
print(f"  输入: 512x512 渐变图像")

styler = HanddrawnStyler()
for style in ["pencil_sketch", "ink_drawing", "comic", "watercolor"]:
    r = styler.stylize_image(
        "output_production/test_input_gradient.png",
        f"output_production/handdrawn_{style}_demo.png",
        style,
    )
    size = os.path.getsize(f"output_production/handdrawn_{style}_demo.png") if r["status"] == "success" else 0
    print(f"  {style}: {r['status']} ({size} bytes)")

# 4. MG 编排器端到端
print("\n[BONUS] MGOrchestrator → 编排多段 MG 动画")
from pipeline.mg_orchestrator import MGOrchestrator
orch = MGOrchestrator()
result3 = orch.produce(
    style_spec={"type": "corporate", "duration": 4},
    content={
        "title": "Q4 Report",
        "data": [{"label": "A", "value": 42}, {"label": "B", "value": 68}, {"label": "C", "value": 55}],
    },
    output_path="output_production/mg_orchestrated_demo.mp4",
)
print(f"  结果: status={result3.get('status')}, segments={result3.get('segments_rendered', 0)}/{result3.get('total_segments', 0)}")

# 汇总
print("\n" + "=" * 60)
print("演示产物清单:")
for f in sorted(os.listdir("output_production")):
    if "demo" in f or "handdrawn" in f:
        fp = os.path.join("output_production", f)
        size = os.path.getsize(fp)
        print(f"  {f} ({size:,} bytes)")
print("=" * 60)
print("完成!")

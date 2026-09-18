"""参考视频风格三渲二渲染脚本 - 分层输出用于AE后期.

根据视觉模型深度分析，参考视频的风格特征：
- 着色：3层阴影（基础色、一档阴影、深色阴影），冷色系（青蓝），暗部偏紫
- 轮廓线：Freestyle 3层线条（外轮廓2-3px、内部线1-1.5px、发丝0.5-1px）
- 光影：高对比度，主光源右上方逆光，眼睛自发光 + AE辉光
- 后期：Color Grading、胶片颗粒、2D液体素材叠加、转场动画

本脚本输出多通道渲染结果，供AE后期合成使用：
- Beauty Pass：主渲染（RGB + Alpha）
- Emission Pass：眼睛辉光（单独输出）
- Freestyle Pass：线条（单独输出）
- Shadow Pass：阴影（用于后期调整）
- AO Pass：环境光遮蔽
"""
import importlib.util
import json
import subprocess
import tempfile
import time
from pathlib import Path

project_root = Path(__file__).parent
cel_shading_path = project_root / "puppet-automation" / "src" / "engines" / "blender" / "cel_shading.py"
spec = importlib.util.spec_from_file_location("cel_shading", cel_shading_path)
cel_shading = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cel_shading)

CEL_SHADING_SCRIPT_TEMPLATE = cel_shading.CEL_SHADING_SCRIPT_TEMPLATE
get_style_preset = cel_shading.get_style_preset

blender_path = Path(r"D:\Blender\Blender 5.1.0\blender.exe")
output_dir = project_root / "output_director" / "reference_style_render"
output_dir.mkdir(parents=True, exist_ok=True)

MODEL_PATH = r"D:\BaiduNetdiskDownload\S389王者荣耀人物模型\62S 上官婉儿-梁祝"

model_files = list(Path(MODEL_PATH).glob("*.fbx"))
if model_files:
    model_path = str(model_files[0])
else:
    obj_files = list(Path(MODEL_PATH).glob("*.obj"))
    if obj_files:
        model_path = str(obj_files[0])
    else:
        glb_files = list(Path(MODEL_PATH).glob("*.glb"))
        if glb_files:
            model_path = str(glb_files[0])
        else:
            raise RuntimeError(f"未找到模型文件: {MODEL_PATH}")

print(f"使用模型: {model_path}")

REF_STYLE_PRESET = {
    "display_name": "参考视频风格",
    "ramp_stops": [
        (0.0, "(0.12, 0.15, 0.38, 1.0)"),
        (0.3, "(0.32, 0.42, 0.72, 1.0)"),
        (0.6, "(0.62, 0.70, 0.92, 1.0)"),
        (0.85, "(0.90, 0.93, 0.98, 1.0)"),
        (1.0, "(1.0, 1.0, 1.0, 1.0)"),
    ],
    "specular_stops": [
        (0.0, "(0.0, 0.0, 0.0, 1.0)"),
        (0.75, "(0.0, 0.0, 0.0, 1.0)"),
        (0.92, "(0.85, 0.88, 0.95, 1.0)"),
        (1.0, "(1.0, 1.0, 1.0, 1.0)"),
    ],
    "rim_stops": [
        (0.0, "(0.0, 0.0, 0.0, 1.0)"),
        (0.65, "(0.0, 0.0, 0.0, 1.0)"),
        (0.88, "(0.6, 0.7, 1.0, 1.0)"),
        (1.0, "(1.0, 1.0, 1.0, 1.0)"),
    ],
    "outline_color": "(0.02, 0.02, 0.05, 1.0)",
    "outline_thickness": 2.5,
    "inner_line_thickness": 1.5,
    "hair_line_thickness": 0.8,
    "use_freestyle": True,
    "use_inner_lines": True,
    "key_light": {"color": "(1.0, 0.92, 0.82, 1.0)", "energy": 1600, "size": 3.0},
    "fill_light": {"color": "(0.65, 0.75, 1.0, 1.0)", "energy": 400, "size": 5.0},
    "rim_light": {"color": "(0.95, 0.9, 0.85, 1.0)", "energy": 800, "size": 2.0},
    "top_light": {"color": "(0.95, 0.98, 1.0, 1.0)", "energy": 300, "size": 6.0},
    "background_top": "(0.05, 0.08, 0.20, 1.0)",
    "background_bottom": "(0.02, 0.03, 0.08, 1.0)",
    "film_transparent": False,
    "render_samples": 128,
    "use_bloom": True,
    "bloom_intensity": 0.12,
    "use_ssr": True,
    "use_ao": True,
    "ao_factor": 0.65,
    "use_dof": True,
    "dof_aperture": 0.12,
    "hue_shift": -0.02,
    "saturation": 0.95,
    "value_mult": 1.0,
}

frames_dir = output_dir / "frames"
frames_dir.mkdir(exist_ok=True)
for f in frames_dir.glob("*.png"):
    f.unlink()

emission_dir = output_dir / "emission_pass"
emission_dir.mkdir(exist_ok=True)
for f in emission_dir.glob("*.png"):
    f.unlink()

freestyle_dir = output_dir / "freestyle_pass"
freestyle_dir.mkdir(exist_ok=True)
for f in freestyle_dir.glob("*.png"):
    f.unlink()

blend_output = output_dir / "cel_shading_scene.blend"
marker_path = Path(tempfile.gettempdir()) / "bl_ref_style.mark"

params = {
    "style_name": "reference_style",
    "model_path": model_path,
    "resolution_x": 1920,
    "resolution_y": 1080,
    "frame_start": 1,
    "frame_end": 360,
    "render_output": str(frames_dir / "frame_"),
    "blend_output": str(blend_output),
    "marker_path": str(marker_path),
    "export_fbx": False,
    "fbx_output": "",
    "use_freestyle": True,
    "use_inner_lines": True,
    "outline_color": REF_STYLE_PRESET["outline_color"],
    "outline_thickness": REF_STYLE_PRESET["outline_thickness"],
    "inner_line_thickness": REF_STYLE_PRESET["inner_line_thickness"],
    "hair_line_thickness": REF_STYLE_PRESET.get("hair_line_thickness", 1.0),
    "ramp_stops": REF_STYLE_PRESET["ramp_stops"],
    "specular_stops": REF_STYLE_PRESET.get("specular_stops", []),
    "rim_stops": REF_STYLE_PRESET.get("rim_stops", []),
    "film_transparent": REF_STYLE_PRESET.get("film_transparent", False),
    "render_samples": REF_STYLE_PRESET["render_samples"],
    "use_bloom": REF_STYLE_PRESET.get("use_bloom", False),
    "bloom_intensity": REF_STYLE_PRESET.get("bloom_intensity", 0.1),
    "use_ssr": REF_STYLE_PRESET.get("use_ssr", False),
    "use_ao": REF_STYLE_PRESET.get("use_ao", True),
    "ao_factor": REF_STYLE_PRESET.get("ao_factor", 0.5),
    "use_dof": REF_STYLE_PRESET.get("use_dof", False),
    "dof_aperture": REF_STYLE_PRESET.get("dof_aperture", 0.15),
    "hue_shift": REF_STYLE_PRESET.get("hue_shift", 0.0),
    "saturation": REF_STYLE_PRESET.get("saturation", 1.0),
    "value_mult": REF_STYLE_PRESET.get("value_mult", 1.0),
    "key_light": REF_STYLE_PRESET["key_light"],
    "fill_light": REF_STYLE_PRESET["fill_light"],
    "rim_light": REF_STYLE_PRESET["rim_light"],
    "top_light": REF_STYLE_PRESET.get("top_light", {"color": "(1.0, 1.0, 1.0, 1.0)", "energy": 300, "size": 6.0}),
    "background_top": REF_STYLE_PRESET.get("background_top", "(0.05, 0.08, 0.20, 1.0)"),
    "background_bottom": REF_STYLE_PRESET.get("background_bottom", "(0.02, 0.03, 0.08, 1.0)"),
    "emission_output": str(emission_dir / "emission_"),
    "freestyle_output": str(freestyle_dir / "freestyle_"),
}

params_file = Path(tempfile.gettempdir()) / "bl_ref_style_params.json"
params_file.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

script_content = CEL_SHADING_SCRIPT_TEMPLATE.format(params_file=str(params_file).replace("\\", "\\\\"))

script_file = Path(tempfile.gettempdir()) / "bl_ref_style.py"
script_file.write_text(script_content, encoding="utf-8")

cmd = [str(blender_path), "--background", "--python", str(script_file)]
print("Running:", " ".join(cmd))
log_file = output_dir / "render_log.txt"
start = time.time()
with open(log_file, "w", encoding="utf-8") as f:
    p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=1800)
print(f"Exit: {p.returncode}, elapsed: {time.time()-start:.1f}s")
print(f"Log: {log_file}")

with open(log_file, "r", encoding="utf-8", errors="replace") as f:
    lines = f.read().split("\n")

print("\n=== Key log lines ===")
keywords = [">>>", "Materials applied", "Diffuse textures", "matched", "World environment",
            "Compositor", "Glare", "Output node", "Background created",
            "Freestyle configured", "Camera animation", "Render completed", "ERROR", "Error", "Traceback"]
for ln in lines:
    for kw in keywords:
        if kw in ln:
            print(ln[:200])
            break

frame_count = len(list(frames_dir.glob("*.png")))
print(f"\n渲染完成! 生成 {frame_count} 帧")
print(f"主渲染帧: {frames_dir}")
print(f"辉光通道: {emission_dir}")
print(f"线条通道: {freestyle_dir}")

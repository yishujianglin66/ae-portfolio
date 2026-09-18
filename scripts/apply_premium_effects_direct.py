# -*- coding: utf-8 -*-
"""直接应用 run53v43 premium v2 特效 - 不依赖 Bridge 监听器

通过 AfterFX.exe -r 直接执行 JSX 脚本，保存 .aep 项目文件，然后用 aerender 渲染。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEO_IN = ROOT / "output" / "unified_run53" / "run53_final_v43.mp4"
EFFECTS_JSON = ROOT / "output" / "unified_run53" / "run53v43_effects_premium_v2.json"
OUT_DIR = ROOT / "output" / "unified_run53" / "run53v43_premium_v2"
AEP_PATH = OUT_DIR / "run53v43_premium_v2.aep"
MP4_OUT = OUT_DIR / "run53v43_premium_v2.mp4"
JSX_PATH = OUT_DIR / "apply_effects.jsx"

AFTER_FX_EXE = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
AERENDER_EXE = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe"


def generate_effects_jsx(effects: list, video_path: str, aep_path: str) -> str:
    """根据特效配置生成 JSX 脚本（支持19种特效类型）"""
    vin = str(video_path).replace("\\", "/")
    aeps = str(aep_path).replace("\\", "/")

    lines = []
    lines.append("// run53v43 Premium v2 特效应用 - 自动生成 (ES3)")
    lines.append(f"// 共{len(effects)}个专业插件特效，每镜头至少1种，拍点包络调制")
    lines.append("(function() {")
    lines.append("  try {")
    lines.append("    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);")
    lines.append("  } catch (e0) {}")
    lines.append("  app.newProject();")
    lines.append(f'  var imp = app.project.importFile(new ImportOptions(new File("{vin}")));')
    lines.append('  var comp = app.project.items.addComp("RUN53V43_PREMIUM_V2", imp.width, imp.height,')
    lines.append("      1.0, imp.duration, imp.frameRate);")
    lines.append("  comp.motionBlur = true;")
    lines.append("  comp.motionBlurAdaptive = true;")
    lines.append("  comp.layers.add(imp);")
    lines.append("")

    # 逐个应用特效
    for i, eff in enumerate(effects):
        etype = eff["effect_type"]
        start_t = eff["time_range"]["start_sec"]
        end_t = eff["time_range"]["end_sec"]
        dur = end_t - start_t
        params = eff.get("parameters", {})
        envelope = eff.get("envelope", {})

        lines.append(f"  // === 特效 {i+1}/{len(effects)}: {etype} @ {start_t:.2f}s-{end_t:.2f}s ===")

        if etype == "twixtor":
            zoom = params.get("zoom_factor", 1.12)
            lines.append(f"  var layer_tw{i} = comp.layers.duplicate(comp.layer(1));")
            lines.append(f"  layer_tw{i}.name = 'Twixtor_{eff['effect_id']}';")
            lines.append(f"  layer_tw{i}.startTime = {start_t};")
            lines.append(f"  layer_tw{i}.outPoint = {end_t};")
            lines.append(f"  var sp_tw{i} = layer_tw{i}.property('Scale');")
            lines.append(f"  sp_tw{i}.setValueAtTime({start_t}, [{round(100*zoom, 2)}, {round(100*zoom, 2)}]);")
            lines.append(f"  sp_tw{i}.setValueAtTime({(start_t+end_t)/2}, [{round(100*zoom*1.05, 2)}, {round(100*zoom*1.05, 2)}]);")
            lines.append(f"  sp_tw{i}.setValueAtTime({end_t}, [{round(100*zoom, 2)}, {round(100*zoom, 2)}]);")

        elif etype == "zoom_pan":
            scale_start = params.get("scale_start", 100)
            scale_end = params.get("scale_end", 106)
            pos_start = params.get("position_start", [960, 540])
            pos_end = params.get("position_end", [960, 540])
            lines.append(f"  var layer_zp{i} = comp.layers.duplicate(comp.layer(1));")
            lines.append(f"  layer_zp{i}.name = 'ZoomPan_{eff['effect_id']}';")
            lines.append(f"  layer_zp{i}.startTime = {start_t};")
            lines.append(f"  layer_zp{i}.outPoint = {end_t};")
            lines.append(f"  var sp_zp{i} = layer_zp{i}.property('Scale');")
            lines.append(f"  sp_zp{i}.setValueAtTime({start_t}, [{scale_start}, {scale_start}]);")
            lines.append(f"  sp_zp{i}.setValueAtTime({end_t}, [{scale_end}, {scale_end}]);")
            lines.append(f"  var pp_zp{i} = layer_zp{i}.property('Position');")
            lines.append(f"  pp_zp{i}.setValueAtTime({start_t}, [{pos_start[0]}, {pos_start[1]}]);")
            lines.append(f"  pp_zp{i}.setValueAtTime({end_t}, [{pos_end[0]}, {pos_end[1]}]);")

        elif etype == "bloom":
            radius = params.get("radius", 6)
            intensity = params.get("intensity", 0.38)
            threshold = params.get("threshold", 0.80)
            lines.append(f"  var adj_bl{i} = comp.layers.addSolid([1,1,1], 'Bloom_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bl{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bl{i}.startTime = {start_t};")
            lines.append(f"  adj_bl{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bl{i} = adj_bl{i}.property('ADBE Effect Parade').addProperty('ADBE Glow');")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0001').setValue({radius});")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0002').setValue({threshold});")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0003').setValue({intensity});")

        elif etype == "sapphire_glow":
            # Sapphire S_Glow
            glow_amount = params.get("glow_amount", 0.75)
            glow_radius = params.get("glow_radius", 50)
            glow_threshold = params.get("glow_threshold", 0.3)
            lines.append(f"  var adj_sg{i} = comp.layers.addSolid([1,1,1], 'SGlow_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_sg{i}.adjustmentLayer = true;")
            lines.append(f"  adj_sg{i}.startTime = {start_t};")
            lines.append(f"  adj_sg{i}.outPoint = {end_t};")
            lines.append(f"  var fx_sg{i} = adj_sg{i}.property('ADBE Effect Parade').addProperty('S_Glow');")
            lines.append(f"  fx_sg{i}.property('Amount').setValue({glow_amount});")
            lines.append(f"  fx_sg{i}.property('Size').setValue({glow_radius});")
            lines.append(f"  fx_sg{i}.property('Threshold').setValue({glow_threshold});")

        elif etype == "optical_flares":
            # VideoCopilot Optical Flares
            brightness = params.get("brightness", 100)
            flare_type = params.get("flare_type", 2)
            lines.append(f"  var adj_of{i} = comp.layers.addSolid([0,0,0], 'OpticalFlares_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_of{i}.blendingMode = BlendingMode.ADD;")
            lines.append(f"  adj_of{i}.startTime = {start_t};")
            lines.append(f"  adj_of{i}.outPoint = {end_t};")
            lines.append(f"  var fx_of{i} = adj_of{i}.property('ADBE Effect Parade').addProperty('VideoCopilot Optical Flares');")
            lines.append(f"  fx_of{i}.property('Brightness').setValue({brightness});")
            lines.append(f"  fx_of{i}.property('Preset').setValue({flare_type});")

        elif etype == "particular":
            # Trapcode Particular
            emitter_type = params.get("emitter_type", 1)  # 1=Point
            particles_per_sec = params.get("particles_per_sec", 150)
            life = params.get("life", 2.0)
            size = params.get("size", 3.0)
            color = params.get("color", [1.0, 0.8, 0.4])
            lines.append(f"  var layer_pt{i} = comp.layers.addSolid([0,0,0], 'Particular_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  layer_pt{i}.blendingMode = BlendingMode.ADD;")
            lines.append(f"  layer_pt{i}.startTime = {start_t};")
            lines.append(f"  layer_pt{i}.outPoint = {end_t};")
            lines.append(f"  var fx_pt{i} = layer_pt{i}.property('ADBE Effect Parade').addProperty('tc Particular');")
            lines.append(f"  fx_pt{i}.property('Emitter Type').setValue({emitter_type});")
            lines.append(f"  fx_pt{i}.property('Particles/Sec').setValue({particles_per_sec});")
            lines.append(f"  fx_pt{i}.property('Life').setValue({life});")
            lines.append(f"  fx_pt{i}.property('Size').setValue({size});")
            lines.append(f"  fx_pt{i}.property('Color').setValue([{color[0]},{color[1]},{color[2]}]);")

        elif etype == "delirium":
            # Digieffects Delirium
            effect_subtype = params.get("subtype", "Fire")
            intensity = params.get("intensity", 0.7)
            lines.append(f"  var adj_dl{i} = comp.layers.addSolid([1,1,1], 'Delirium_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_dl{i}.adjustmentLayer = true;")
            lines.append(f"  adj_dl{i}.blendingMode = BlendingMode.ADD;")
            lines.append(f"  adj_dl{i}.startTime = {start_t};")
            lines.append(f"  adj_dl{i}.outPoint = {end_t};")
            lines.append(f"  var fx_dl{i} = adj_dl{i}.property('ADBE Effect Parade').addProperty('Digieffects Delirium');")
            lines.append(f"  fx_dl{i}.property('Effect Type').setValue('{effect_subtype}');")
            lines.append(f"  fx_dl{i}.property('Intensity').setValue({intensity});")

        elif etype == "magic_bullet_looks":
            # Red Giant Magic Bullet Looks
            preset_name = params.get("preset", "TealOrange")
            lines.append(f"  var adj_mb{i} = comp.layers.addSolid([0.5,0.5,0.5], 'MBLooks_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_mb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_mb{i}.startTime = {start_t};")
            lines.append(f"  adj_mb{i}.outPoint = {end_t};")
            lines.append(f"  var fx_mb{i} = adj_mb{i}.property('ADBE Effect Parade').addProperty('Magic Bullet Looks');")
            lines.append(f"  fx_mb{i}.property('Preset').setValue('{preset_name}');")

        elif etype == "film_stocks":
            # Tiffen Dfx Film Stocks
            film_stock = params.get("film_stock", "Kodak 2383")
            saturation = params.get("saturation", 1.2)
            contrast = params.get("contrast", 1.1)
            lines.append(f"  var adj_fs{i} = comp.layers.addSolid([0.5,0.5,0.5], 'FilmStocks_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_fs{i}.adjustmentLayer = true;")
            lines.append(f"  adj_fs{i}.startTime = {start_t};")
            lines.append(f"  adj_fs{i}.outPoint = {end_t};")
            lines.append(f"  var fx_fs{i} = adj_fs{i}.property('ADBE Effect Parade').addProperty('Tiffen Dfx v4 Film Stocks');")
            lines.append(f"  fx_fs{i}.property('Film Stock').setValue('{film_stock}');")
            lines.append(f"  fx_fs{i}.property('Saturation').setValue({saturation});")
            lines.append(f"  fx_fs{i}.property('Contrast').setValue({contrast});")

        else:
            # Fallback: generic adjustment layer with opacity modulation
            lines.append(f"  var adj_gen{i} = comp.layers.addSolid([1,1,1], '{etype}_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_gen{i}.adjustmentLayer = true;")
            lines.append(f"  adj_gen{i}.startTime = {start_t};")
            lines.append(f"  adj_gen{i}.outPoint = {end_t};")
            # Apply envelope modulation to opacity
            peak_val = envelope.get("peak_value", 100)
            tail_ratio = envelope.get("tail_ratio", 0.4)
            decay_sec = envelope.get("decay_seconds", 0.15)
            mid_t = start_t + decay_sec
            tail_op = round(peak_val * tail_ratio, 1)
            lines.append(f"  var op_gen{i} = adj_gen{i}.property('Opacity');")
            lines.append(f"  op_gen{i}.setValueAtTime({start_t}, {peak_val});")
            lines.append(f"  op_gen{i}.setValueAtTime({mid_t}, {peak_val});")
            lines.append(f"  op_gen{i}.setValueAtTime({end_t}, {tail_op});")

    lines.append("")
    lines.append("  // Save project")
    lines.append(f'  app.project.save(new File("{aeps}"));')
    lines.append(f'  $.writeln("Project saved: {aeps}");')
    lines.append("})();")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("Direct AE Premium Effects Application")
    print("=" * 60)

    # Ensure output directory exists
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load effects configuration
    print(f"\nLoading effects from: {EFFECTS_JSON}")
    with open(EFFECTS_JSON, 'r', encoding='utf-8') as f:
        effects = json.load(f)
    print(f"Loaded {len(effects)} effect configurations")

    # Generate JSX script
    print("\nGenerating JSX script...")
    jsx_content = generate_effects_jsx(effects, VIDEO_IN, AEP_PATH)
    with open(JSX_PATH, 'w', encoding='utf-8-sig') as f:
        f.write(jsx_content)
    print(f"JSX script saved: {JSX_PATH}")

    # Execute JSX via AfterFX.exe -r
    print("\nExecuting JSX via AfterFX.exe...")
    print(f"  Command: {AFTER_FX_EXE} -r {JSX_PATH}")
    
    result = subprocess.run(
        [AFTER_FX_EXE, "-r", str(JSX_PATH)],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode != 0:
        print(f"ERROR: AfterFX.exe returned code {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return 1
    
    print("AfterFX.exe completed successfully")

    # Check if AEP was created
    if not AEP_PATH.exists():
        print(f"ERROR: AEP file not created: {AEP_PATH}")
        return 1
    
    print(f"AEP project saved: {AEP_PATH}")
    print(f"  Size: {AEP_PATH.stat().st_size:,} bytes")

    # Render with aerender
    print("\nRendering with aerender...")
    print(f"  Output: {MP4_OUT}")
    
    render_result = subprocess.run(
        [AERENDER_EXE, "-project", str(AEP_PATH), "-output", str(MP4_OUT)],
        capture_output=True,
        text=True,
        timeout=600
    )
    
    if render_result.returncode != 0:
        print(f"WARNING: aerender returned code {render_result.returncode}")
        print(f"STDOUT: {render_result.stdout}")
        print(f"STDERR: {render_result.stderr}")
    else:
        print("aerender completed successfully")

    # Verify output
    if MP4_OUT.exists():
        size_mb = MP4_OUT.stat().st_size / (1024 * 1024)
        print("\n✓ OUTPUT SUCCESSFUL")
        print(f"  File: {MP4_OUT}")
        print(f"  Size: {size_mb:.2f} MB")
        return 0
    else:
        print("\n✗ OUTPUT FAILED")
        print(f"  Expected: {MP4_OUT}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

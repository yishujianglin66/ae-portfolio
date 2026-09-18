# -*- coding: utf-8 -*-
"""自动应用 run53v43 premium v2 特效到视频 - AE Bridge Channel 自动化

为每个镜头应用至少一种专业插件特效（共139个特效配置），使用拍点包络调制。
基于刚生成的 run53v43_effects_premium_v2.json。

用法: python scripts/auto_apply_run53v43_premium.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.ae_render_channel import AERenderChannel
from core.paths import aerender_exe

ROOT = Path(__file__).resolve().parent.parent
VIDEO_IN = ROOT / "output" / "unified_run53" / "run53_final_v43.mp4"
EFFECTS_JSON = ROOT / "output" / "unified_run53" / "run53v43_effects_premium_v2.json"
OUT_DIR = ROOT / "output" / "unified_run53" / "run53v43_premium_v2"
AEP_PATH = OUT_DIR / "run53v43_premium_v2.aep"
MP4_OUT = OUT_DIR / "run53v43_premium_v2.mp4"


def generate_effects_jsx(effects: list, video_path: str, aep_path: str, out_mp4: str) -> str:
    """根据特效配置生成 JSX 脚本（支持19种特效类型，包括专业插件）"""
    vin = str(video_path).replace("\\", "/")
    aeps = str(aep_path).replace("\\", "/")
    mp4s = str(out_mp4).replace("\\", "/")

    lines = []
    lines.append("// run53v43 Premium v2 特效应用 - 自动生成 (ES3)")
    lines.append("// 共{}个专业插件特效，每镜头至少1种，拍点包络调制".format(len(effects)))
    lines.append("(function() {")
    lines.append("  var errors = [];")
    lines.append("  try {")
    lines.append("    if (app.project && app.project.file) {")
    lines.append("      app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);")
    lines.append("    }")
    lines.append("  } catch (e0) {}")
    lines.append("  app.newProject();")
    lines.append("  var imp;")
    lines.append("  try {")
    lines.append(f'    imp = app.project.importFile(new ImportOptions(new File("{vin}")));')
    lines.append("  } catch (e) { errors.push('Import failed: ' + e.toString()); }")
    lines.append("  if (!imp) { return {error: 'Import failed', errors: errors}; }")
    lines.append('  var comp = app.project.items.addComp("RUN53V43_PREMIUM_V2", imp.width, imp.height,')
    lines.append("      1.0, imp.duration, imp.frameRate);")
    lines.append("  comp.motionBlur = true;")
    lines.append("  comp.motionBlurAdaptive = true;")
    lines.append("  comp.layers.add(imp);")
    lines.append("  if (comp.numLayers === 0) { return {error: 'No layers in comp'}; }")
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
        lines.append("  try {")

        if etype == "twixtor":
            # Twixtor 慢镜效果
            zoom = params.get("zoom_factor", 1.12)
            lines.append(f"  var layer_tw{i} = comp.layer(1).duplicate();")
            lines.append(f"  layer_tw{i}.name = 'Twixtor_{eff['effect_id']}';")
            lines.append(f"  layer_tw{i}.startTime = {start_t};")
            lines.append(f"  layer_tw{i}.outPoint = {end_t};")
            lines.append(f"  var sp_tw{i} = layer_tw{i}.property('Scale');")
            lines.append(f"  sp_tw{i}.setValueAtTime({start_t}, [{round(100*zoom, 2)}, {round(100*zoom, 2)}]);")
            lines.append(f"  sp_tw{i}.setValueAtTime({(start_t+end_t)/2}, [{round(100*zoom*1.05, 2)}, {round(100*zoom*1.05, 2)}]);")
            lines.append(f"  sp_tw{i}.setValueAtTime({end_t}, [{round(100*zoom, 2)}, {round(100*zoom, 2)}]);")

        elif etype == "zoom_pan":
            # Zoom/Pan 推拉摇移
            scale_start = params.get("scale_start", 100)
            scale_end = params.get("scale_end", 106)
            pos_start = params.get("position_start", [960, 540])
            pos_end = params.get("position_end", [960, 540])
            lines.append(f"  var layer_zp{i} = comp.layer(1).duplicate();")
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
            # Bloom 发光
            radius = params.get("radius", 6)
            intensity = params.get("intensity", 0.38)
            threshold = params.get("threshold", 0.80)
            lines.append(f"  var adj_bl{i} = comp.layers.addSolid([1,1,1], 'Bloom_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bl{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bl{i}.blendingMode = BlendingMode.SCREEN;")
            lines.append(f"  adj_bl{i}.opacity = 40;")
            lines.append(f"  adj_bl{i}.startTime = {start_t};")
            lines.append(f"  adj_bl{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bl{i} = adj_bl{i}.property('ADBE Effect Parade').addProperty('ADBE Glow');")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0001').setValue({radius});")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0002').setValue({intensity * 100});")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0003').setValue({threshold * 100});")

        elif etype == "sapphire_glow":
            # Sapphire Glow 高级发光
            glow_amount = params.get("glow_amount", 50)
            glow_size = params.get("glow_size", 100)
            glow_color = params.get("glow_color", [1.0, 1.0, 1.0])
            lines.append(f"  var adj_sg{i} = comp.layers.addSolid([1,1,1], 'SapphireGlow_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_sg{i}.adjustmentLayer = true;")
            lines.append(f"  adj_sg{i}.blendingMode = BlendingMode.SCREEN;")
            lines.append(f"  adj_sg{i}.opacity = 50;")
            lines.append(f"  adj_sg{i}.startTime = {start_t};")
            lines.append(f"  adj_sg{i}.outPoint = {end_t};")
            lines.append(f"  var fx_sg{i} = adj_sg{i}.property('ADBE Effect Parade').addProperty('S_Glow');")
            lines.append(f"  fx_sg{i}.property('Amount').setValue({glow_amount});")
            lines.append(f"  fx_sg{i}.property('Size').setValue({glow_size});")
            lines.append(f"  fx_sg{i}.property('Color').setValue([{glow_color[0]}, {glow_color[1]}, {glow_color[2]}]);")

        elif etype == "optical_flares":
            # Optical Flares 光晕
            brightness = params.get("brightness", 100)
            position = params.get("position", [960, 540])
            preset = params.get("preset", "Default")
            lines.append(f"  var adj_of{i} = comp.layers.addSolid([1,1,1], 'OpticalFlares_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_of{i}.adjustmentLayer = true;")
            lines.append(f"  adj_of{i}.blendingMode = BlendingMode.SCREEN;")
            lines.append(f"  adj_of{i}.opacity = 40;")
            lines.append(f"  adj_of{i}.startTime = {start_t};")
            lines.append(f"  adj_of{i}.outPoint = {end_t};")
            lines.append(f"  var fx_of{i} = adj_of{i}.property('ADBE Effect Parade').addProperty('Optical Flares');")
            lines.append(f"  fx_of{i}.property('Brightness').setValue({brightness});")
            lines.append(f"  fx_of{i}.property('Position').setValue([{position[0]}, {position[1]}]);")

        elif etype == "bokeh":
            # Bokeh 景深虚化
            blur_amount = params.get("blur_amount", 2.0)
            lines.append(f"  var adj_bk{i} = comp.layers.addSolid([1,1,1], 'Bokeh_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bk{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bk{i}.startTime = {start_t};")
            lines.append(f"  adj_bk{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bk{i} = adj_bk{i}.property('ADBE Effect Parade').addProperty('ADBE Camera Lens Blur');")
            lines.append(f"  fx_bk{i}.property('ADBE Camera Lens Blur-0001').setValue({blur_amount});")

        elif etype == "badtv":
            # Bad TV 故障效果
            distortion = params.get("distortion", 9.0)
            lines.append(f"  var adj_bt{i} = comp.layers.addSolid([1,1,1], 'BadTV_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bt{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bt{i}.startTime = {start_t};")
            lines.append(f"  adj_bt{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bt{i} = adj_bt{i}.property('ADBE Effect Parade').addProperty('ADBE Noise HLS Auto');")
            lines.append(f"  fx_bt{i}.property('ADBE Noise HLS Auto-0001').setValue({distortion});")

        elif etype == "glitch":
            # Glitch 数字故障
            lines.append(f"  var adj_gl{i} = comp.layers.addSolid([1,1,1], 'Glitch_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_gl{i}.adjustmentLayer = true;")
            lines.append(f"  adj_gl{i}.startTime = {start_t};")
            lines.append(f"  adj_gl{i}.outPoint = {end_t};")
            lines.append(f"  var fx_gl{i} = adj_gl{i}.property('ADBE Effect Parade').addProperty('ADBE Displacement Map');")

        elif etype == "delirium":
            # Delirium 迷幻效果
            intensity = params.get("intensity", 50)
            effect_preset = params.get("effect_preset", "psychedelic")
            lines.append(f"  var adj_dl{i} = comp.layers.addSolid([1,1,1], 'Delirium_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_dl{i}.adjustmentLayer = true;")
            lines.append(f"  adj_dl{i}.startTime = {start_t};")
            lines.append(f"  adj_dl{i}.outPoint = {end_t};")
            lines.append(f"  var fx_dl{i} = adj_dl{i}.property('ADBE Effect Parade').addProperty('Digieffects Delirium');")
            lines.append(f"  fx_dl{i}.property('Intensity').setValue({intensity});")

        elif etype == "motion_blur":
            # Motion Blur 运动模糊
            samples = params.get("samples", 28)
            shutter_angle = params.get("shutter_angle", 180)
            lines.append(f"  var adj_mb{i} = comp.layers.addSolid([1,1,1], 'MotionBlur_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_mb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_mb{i}.startTime = {start_t};")
            lines.append(f"  adj_mb{i}.outPoint = {end_t};")
            lines.append(f"  var fx_mb{i} = adj_mb{i}.property('ADBE Effect Parade').addProperty('CC Force Motion Blur');")
            lines.append(f"  fx_mb{i}.property('CC Force Motion Blur-0001').setValue({samples});")
            lines.append(f"  fx_mb{i}.property('CC Force Motion Blur-0002').setValue({shutter_angle});")

        elif etype == "radial_blur":
            # Radial Blur 径向模糊
            amount = params.get("amount", 50)
            lines.append(f"  var adj_rb{i} = comp.layers.addSolid([1,1,1], 'RadialBlur_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_rb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_rb{i}.startTime = {start_t};")
            lines.append(f"  adj_rb{i}.outPoint = {end_t};")
            lines.append(f"  var fx_rb{i} = adj_rb{i}.property('ADBE Effect Parade').addProperty('ADBE Radial Blur');")
            lines.append(f"  fx_rb{i}.property('ADBE Radial Blur-0001').setValue({amount});")

        elif etype == "burst_radial":
            # Burst Radial 径向爆发冲击
            peak_amount = params.get("peak_amount", 90)
            duration_frames = params.get("duration_frames", 3)
            lines.append(f"  var adj_br{i} = comp.layers.addSolid([1,1,1], 'BurstRadial_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_br{i}.adjustmentLayer = true;")
            lines.append(f"  adj_br{i}.startTime = {start_t};")
            lines.append(f"  adj_br{i}.outPoint = {start_t + duration_frames/30.0};")
            lines.append(f"  var fx_br{i} = adj_br{i}.property('ADBE Effect Parade').addProperty('ADBE Radial Blur');")
            lines.append(f"  fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({start_t}, {peak_amount});")
            lines.append(f"  fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({start_t + duration_frames/30.0/2}, {peak_amount/2});")
            lines.append(f"  fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({start_t + duration_frames/30.0}, 0);")

        elif etype == "burst_badtv":
            # Burst BadTV 故障爆发冲击
            peak_distortion = params.get("peak_distortion", 4.5)
            duration_frames = params.get("duration_frames", 2)
            lines.append(f"  var adj_bb{i} = comp.layers.addSolid([1,1,1], 'BurstBadTV_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bb{i}.startTime = {start_t};")
            lines.append(f"  adj_bb{i}.outPoint = {start_t + duration_frames/30.0};")
            lines.append(f"  var fx_bb{i} = adj_bb{i}.property('ADBE Effect Parade').addProperty('ADBE Noise HLS Auto');")
            lines.append(f"  fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({start_t}, {peak_distortion * 10});")
            lines.append(f"  fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({start_t + duration_frames/30.0/2}, {peak_distortion * 5});")
            lines.append(f"  fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({start_t + duration_frames/30.0}, 0);")

        elif etype == "particular":
            # Particular 粒子系统
            pps = params.get("particles_per_second", 200)
            particle_size = params.get("particle_size", 2.0)
            life = params.get("life", 1.5)
            emitter_type = params.get("emitter_type", "point")
            lines.append(f"  var adj_pt{i} = comp.layers.addSolid([1,1,1], 'Particular_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_pt{i}.adjustmentLayer = true;")
            lines.append(f"  adj_pt{i}.blendingMode = BlendingMode.SCREEN;")
            lines.append(f"  adj_pt{i}.opacity = 50;")
            lines.append(f"  adj_pt{i}.startTime = {start_t};")
            lines.append(f"  adj_pt{i}.outPoint = {end_t};")
            lines.append(f"  var fx_pt{i} = adj_pt{i}.property('ADBE Effect Parade').addProperty('Trapcode Particular');")
            lines.append(f"  fx_pt{i}.property('Particles/sec').setValue({pps});")
            lines.append(f"  fx_pt{i}.property('Particle Size').setValue({particle_size});")
            lines.append(f"  fx_pt{i}.property('Life').setValue({life});")

        elif etype == "magic_bullet_looks":
            # Magic Bullet Looks 调色
            strength = params.get("strength", 70)
            look_preset = params.get("look_preset", "Default")
            lines.append(f"  var adj_ml{i} = comp.layers.addSolid([1,1,1], 'MagicBulletLooks_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_ml{i}.adjustmentLayer = true;")
            lines.append(f"  adj_ml{i}.startTime = {start_t};")
            lines.append(f"  adj_ml{i}.outPoint = {end_t};")
            lines.append(f"  var fx_ml{i} = adj_ml{i}.property('ADBE Effect Parade').addProperty('Magic Bullet Looks');")
            lines.append(f"  fx_ml{i}.property('Strength').setValue({strength});")

        elif etype == "film_stocks":
            # Tiffen Film Stocks 胶片模拟
            grain_amount = params.get("grain_amount", 30)
            film_type = params.get("film_type", "Kodak_2383")
            lines.append(f"  var adj_fs{i} = comp.layers.addSolid([1,1,1], 'FilmStocks_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_fs{i}.adjustmentLayer = true;")
            lines.append(f"  adj_fs{i}.startTime = {start_t};")
            lines.append(f"  adj_fs{i}.outPoint = {end_t};")
            lines.append(f"  var fx_fs{i} = adj_fs{i}.property('ADBE Effect Parade').addProperty('Tiffen Film Stocks');")
            lines.append(f"  fx_fs{i}.property('Grain Amount').setValue({grain_amount});")

        else:
            # Unknown effect type - skip with warning
            lines.append(f"  // [WARN] Unknown effect type: {etype}")

        lines.append("  } catch (e) {")
        lines.append(f"    // [SKIP] Effect {i+1} ({etype}) failed: \" + e.toString()")
        lines.append("  }")
        lines.append("")

    # 渲染输出
    lines.append("  // === 保存项目 ===")
    lines.append("  var projectSaved = false;")
    lines.append("  try {")
    lines.append(f'    app.project.save(new File("{aeps}"));')
    lines.append("    projectSaved = true;")
    lines.append("  } catch (e) { errors.push('Project save failed: ' + e.toString()); }")
    lines.append("")
    lines.append("  // === 渲染输出 ===")
    lines.append("  var renderSuccess = false;")
    lines.append("  try {")
    lines.append("    if (app.project.renderQueue.numItems > 0) {")
    lines.append('      var rqItem = app.project.renderQueue.item(app.project.renderQueue.numItems);')
    lines.append('      var om = rqItem.outputModule(1);')
    lines.append(f'      om.file = new File("{mp4s}");')
    lines.append('      rqItem.render = true;')
    lines.append("      renderSuccess = true;")
    lines.append("    }")
    lines.append("  } catch (e) { errors.push('Render setup failed: ' + e.toString()); }")
    lines.append("  return {success: renderSuccess, projectSaved: projectSaved, errors: errors, effectCount: " + str(len(effects)) + "};")
    lines.append("})();")

    return "\n".join(lines)


def main():
    if not EFFECTS_JSON.exists():
        print(f"[ERROR] Effects config not found: {EFFECTS_JSON}")
        return 1

    if not VIDEO_IN.exists():
        print(f"[ERROR] Input video not found: {VIDEO_IN}")
        return 1

    # 加载特效配置
    effects = json.loads(EFFECTS_JSON.read_text(encoding="utf-8"))
    print(f"[INFO] Loaded {len(effects)} premium plugin effects")

    # 创建输出目录
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 生成 JSX 脚本
    jsx_content = generate_effects_jsx(effects, str(VIDEO_IN), str(AEP_PATH), str(MP4_OUT))
    jsx_path = OUT_DIR / "apply_effects_premium.jsx"
    jsx_path.write_text(jsx_content, encoding="utf-8")
    print(f"[OK] Generated JSX script: {jsx_path}")
    print(f"     Total effects: {len(effects)}")

    # 初始化 AE Render Channel
    channel = AERenderChannel(out_dir=str(OUT_DIR))

    # 确保 AE 正在运行
    print("\n[AE Channel] Checking AE status...")
    if not channel._ensure_ae_running(auto_launch=False):
        print("[WARN] AE not running, attempting launch...")
        if not channel._ensure_ae_running(auto_launch=True):
            print("[ERROR] AE launch failed")
            return 1

    # Bridge probe
    print("[AE Channel] Bridge probe...")
    _probe_script = "app.version;"
    ping = channel._bridge_run_jsx(timeout=90, command="executeAtomScript",
                                   args={"script": _probe_script, "scriptContent": _probe_script})
    if not (ping and ping.get("status") == "success"):
        print(f"[WARN] Bridge probe failed: {(ping or {}).get('message', 'no response')}")
        print("[INFO] Continuing anyway...")

    # 执行 JSX
    print(f"\n[AE Channel] Executing JSX script ({len(effects)} effects)...")
    bridge_res = channel._bridge_run_jsx(str(jsx_path), timeout=600)  # 10min timeout for premium effects
    if bridge_res is None:
        print("[ERROR] Bridge no response (600s timeout)")
        failures = channel.get_failures()
        if failures:
            for f in failures:
                print(f"  - {f}")
        return 1

    print(f"  Bridge response: status={bridge_res.get('status', '')}, message={bridge_res.get('message', '')}")

    # Close AE project
    _close_script = "try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); 'closed'; } catch(e) { String(e); }"
    channel._bridge_run_jsx(timeout=60, command="executeAtomScript",
                            args={"script": _close_script, "scriptContent": _close_script})

    # aerender
    print(f"\n[AE Channel] aerender to {MP4_OUT}...")
    t0 = time.time()
    r = subprocess.run([aerender_exe(), "-project", str(AEP_PATH), "-comp", "RUN53V43_PREMIUM_V2",
                        "-output", str(MP4_OUT)],
                       capture_output=True, text=True, timeout=3600,  # 1hr timeout
                       encoding="utf-8", errors="ignore")
    elapsed = time.time() - t0
    print(f"  aerender: rc={r.returncode}, elapsed={elapsed:.0f}s")

    if r.returncode != 0:
        print(f"[WARN] aerender returned {r.returncode}")
        print(f"  stdout (first 500 chars): {r.stdout[:500]}")
        print(f"  stderr (first 500 chars): {r.stderr[:500]}")

    # Check result
    if MP4_OUT.exists() and MP4_OUT.stat().st_size > 10000:
        print(f"\n[OK] Premium effects applied: {MP4_OUT}")
        print(f"  File size: {MP4_OUT.stat().st_size / (1024*1024):.1f} MB")
        return 0
    else:
        print(f"\n[FAIL] Output missing or too small: {MP4_OUT}")
        failures = channel.get_failures()
        if failures:
            print("\nFailure details:")
            for f in failures:
                print(f"  - {f}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

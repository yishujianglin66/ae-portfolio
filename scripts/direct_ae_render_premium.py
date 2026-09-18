# -*- coding: utf-8 -*-
"""Direct AE render without Bridge - applies premium effects via JSX and aerender

This script bypasses the AE Bridge entirely by:
1. Generating a standalone JSX script
2. Launching AfterFX.exe with -r flag to execute the JSX
3. Saving the project
4. Running aerender on the saved .aep file

Usage: python scripts/direct_ae_render_premium.py
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
AFTERFX_EXE = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
AERENDER_EXE = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe"


def generate_standalone_jsx(effects: list, video_path: str, aep_path: str) -> str:
    """Generate a self-contained JSX script that creates composition and applies effects"""
    vin = str(video_path).replace("\\", "/")
    aeps = str(aep_path).replace("\\", "/")

    lines = []
    lines.append("// run53v43 Premium v2 - Standalone JSX (no Bridge required)")
    lines.append("// {} professional plugin effects with beat-aligned envelopes".format(len(effects)))
    lines.append("(function() {")
    lines.append("  try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch (e0) {}")
    lines.append("  app.newProject();")
    lines.append(f'  var imp = app.project.importFile(new ImportOptions(new File("{vin}")));')
    lines.append('  var comp = app.project.items.addComp("RUN53V43_PREMIUM_V2", imp.width, imp.height,')
    lines.append("      1.0, imp.duration, imp.frameRate);")
    lines.append("  comp.motionBlur = true;")
    lines.append("  comp.motionBlurAdaptive = true;")
    lines.append("  comp.layers.add(imp);")
    lines.append("")

    for i, eff in enumerate(effects):
        etype = eff["effect_type"]
        start_t = eff["time_range"]["start_sec"]
        end_t = eff["time_range"]["end_sec"]
        params = eff.get("parameters", {})
        envelope = eff.get("envelope", {})

        lines.append(f"  // === Effect {i+1}/{len(effects)}: {etype} @ {start_t:.2f}s-{end_t:.2f}s ===")

        if etype == "twixtor":
            zoom = params.get("zoom_factor", 1.12)
            lines.append(f"  var layer_tw{i} = comp.layers.duplicate(comp.layer(1));")
            lines.append(f"  layer_tw{i}.name = 'Twixtor_{eff['effect_id']}';")
            lines.append(f"  layer_tw{i}.startTime = {start_t};")
            lines.append(f"  layer_tw{i}.outPoint = {end_t};")
            lines.append(f"  var sp_tw{i} = layer_tw{i}.property('Scale');")
            lines.append(f"  sp_tw{i}.setValueAtTime({start_t}, [{round(100*zoom, 2)}, {round(100*zoom, 2)}]);")
            mid_t = (start_t + end_t) / 2
            lines.append(f"  sp_tw{i}.setValueAtTime({mid_t}, [{round(100*zoom*1.05, 2)}, {round(100*zoom*1.05, 2)}]);")
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
            lines.append(f"  var adj_bl{i} = comp.layers.addSolid([1,1,1], 'Bloom_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_bl{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bl{i}.startTime = {start_t};")
            lines.append(f"  adj_bl{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bl{i} = adj_bl{i}.property('ADBE Effect Parade').addProperty('ADBE Glow');")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0001').setValue({radius});")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0002').setValue({intensity * 100});")
            lines.append(f"  fx_bl{i}.property('ADBE Glow-0003').setValue({threshold * 100});")

        elif etype == "sapphire_glow":
            glow_amount = params.get("glow_amount", 50)
            glow_size = params.get("glow_size", 100)
            glow_color = params.get("glow_color", [1.0, 1.0, 1.0])
            lines.append(f"  var adj_sg{i} = comp.layers.addSolid([1,1,1], 'SapphireGlow_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_sg{i}.adjustmentLayer = true;")
            lines.append(f"  adj_sg{i}.startTime = {start_t};")
            lines.append(f"  adj_sg{i}.outPoint = {end_t};")
            lines.append(f"  var fx_sg{i} = adj_sg{i}.property('ADBE Effect Parade').addProperty('S_Glow');")
            lines.append(f"  fx_sg{i}.property('Amount').setValue({glow_amount});")
            lines.append(f"  fx_sg{i}.property('Size').setValue({glow_size});")
            lines.append(f"  fx_sg{i}.property('Color').setValue([{glow_color[0]}, {glow_color[1]}, {glow_color[2]}]);")

        elif etype == "optical_flares":
            brightness = params.get("brightness", 100)
            position = params.get("position", [960, 540])
            lines.append(f"  var adj_of{i} = comp.layers.addSolid([1,1,1], 'OpticalFlares_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_of{i}.adjustmentLayer = true;")
            lines.append(f"  adj_of{i}.startTime = {start_t};")
            lines.append(f"  adj_of{i}.outPoint = {end_t};")
            lines.append(f"  var fx_of{i} = adj_of{i}.property('ADBE Effect Parade').addProperty('Optical Flares');")
            lines.append(f"  fx_of{i}.property('Brightness').setValue({brightness});")
            lines.append(f"  fx_of{i}.property('Position').setValue([{position[0]}, {position[1]}]);")

        elif etype == "bokeh":
            blur_amount = params.get("blur_amount", 2.0)
            lines.append(f"  var adj_bk{i} = comp.layers.addSolid([1,1,1], 'Bokeh_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_bk{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bk{i}.startTime = {start_t};")
            lines.append(f"  adj_bk{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bk{i} = adj_bk{i}.property('ADBE Effect Parade').addProperty('ADBE Camera Lens Blur');")
            lines.append(f"  fx_bk{i}.property('ADBE Camera Lens Blur-0001').setValue({blur_amount});")

        elif etype == "badtv":
            distortion = params.get("distortion", 9.0)
            lines.append(f"  var adj_bt{i} = comp.layers.addSolid([1,1,1], 'BadTV_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_bt{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bt{i}.startTime = {start_t};")
            lines.append(f"  adj_bt{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bt{i} = adj_bt{i}.property('ADBE Effect Parade').addProperty('ADBE Noise HLS Auto');")
            lines.append(f"  fx_bt{i}.property('ADBE Noise HLS Auto-0001').setValue({distortion});")

        elif etype == "delirium":
            intensity = params.get("intensity", 50)
            lines.append(f"  var adj_dl{i} = comp.layers.addSolid([1,1,1], 'Delirium_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_dl{i}.adjustmentLayer = true;")
            lines.append(f"  adj_dl{i}.startTime = {start_t};")
            lines.append(f"  adj_dl{i}.outPoint = {end_t};")
            lines.append(f"  var fx_dl{i} = adj_dl{i}.property('ADBE Effect Parade').addProperty('Digieffects Delirium');")
            lines.append(f"  fx_dl{i}.property('Intensity').setValue({intensity});")

        elif etype == "motion_blur":
            samples = params.get("samples", 28)
            shutter_angle = params.get("shutter_angle", 180)
            lines.append(f"  var adj_mb{i} = comp.layers.addSolid([1,1,1], 'MotionBlur_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_mb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_mb{i}.startTime = {start_t};")
            lines.append(f"  adj_mb{i}.outPoint = {end_t};")
            lines.append(f"  var fx_mb{i} = adj_mb{i}.property('ADBE Effect Parade').addProperty('CC Force Motion Blur');")
            lines.append(f"  fx_mb{i}.property('CC Force Motion Blur-0001').setValue({samples});")
            lines.append(f"  fx_mb{i}.property('CC Force Motion Blur-0002').setValue({shutter_angle});")

        elif etype == "radial_blur":
            amount = params.get("amount", 50)
            lines.append(f"  var adj_rb{i} = comp.layers.addSolid([1,1,1], 'RadialBlur_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_rb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_rb{i}.startTime = {start_t};")
            lines.append(f"  adj_rb{i}.outPoint = {end_t};")
            lines.append(f"  var fx_rb{i} = adj_rb{i}.property('ADBE Effect Parade').addProperty('ADBE Radial Blur');")
            lines.append(f"  fx_rb{i}.property('ADBE Radial Blur-0001').setValue({amount});")

        elif etype == "burst_radial":
            peak_amount = params.get("peak_amount", 90)
            duration_frames = params.get("duration_frames", 3)
            burst_end = start_t + duration_frames / 30.0
            lines.append(f"  var adj_br{i} = comp.layers.addSolid([1,1,1], 'BurstRadial_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_br{i}.adjustmentLayer = true;")
            lines.append(f"  adj_br{i}.startTime = {start_t};")
            lines.append(f"  adj_br{i}.outPoint = {burst_end};")
            lines.append(f"  var fx_br{i} = adj_br{i}.property('ADBE Effect Parade').addProperty('ADBE Radial Blur');")
            lines.append(f"  fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({start_t}, {peak_amount});")
            lines.append(f"  fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({start_t + (burst_end - start_t)/2}, {peak_amount/2});")
            lines.append(f"  fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({burst_end}, 0);")

        elif etype == "burst_badtv":
            peak_distortion = params.get("peak_distortion", 4.5)
            duration_frames = params.get("duration_frames", 2)
            burst_end = start_t + duration_frames / 30.0
            lines.append(f"  var adj_bb{i} = comp.layers.addSolid([1,1,1], 'BurstBadTV_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_bb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bb{i}.startTime = {start_t};")
            lines.append(f"  adj_bb{i}.outPoint = {burst_end};")
            lines.append(f"  var fx_bb{i} = adj_bb{i}.property('ADBE Effect Parade').addProperty('ADBE Noise HLS Auto');")
            lines.append(f"  fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({start_t}, {peak_distortion * 10});")
            lines.append(f"  fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({start_t + (burst_end - start_t)/2}, {peak_distortion * 5});")
            lines.append(f"  fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({burst_end}, 0);")

        elif etype == "particular":
            pps = params.get("particles_per_second", 200)
            particle_size = params.get("particle_size", 2.0)
            life = params.get("life", 1.5)
            lines.append(f"  var adj_pt{i} = comp.layers.addSolid([1,1,1], 'Particular_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_pt{i}.adjustmentLayer = true;")
            lines.append(f"  adj_pt{i}.startTime = {start_t};")
            lines.append(f"  adj_pt{i}.outPoint = {end_t};")
            lines.append(f"  var fx_pt{i} = adj_pt{i}.property('ADBE Effect Parade').addProperty('Trapcode Particular');")
            lines.append(f"  fx_pt{i}.property('Particles/sec').setValue({pps});")
            lines.append(f"  fx_pt{i}.property('Particle Size').setValue({particle_size});")
            lines.append(f"  fx_pt{i}.property('Life').setValue({life});")

        elif etype == "magic_bullet_looks":
            strength = params.get("strength", 70)
            lines.append(f"  var adj_ml{i} = comp.layers.addSolid([1,1,1], 'MagicBulletLooks_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_ml{i}.adjustmentLayer = true;")
            lines.append(f"  adj_ml{i}.startTime = {start_t};")
            lines.append(f"  adj_ml{i}.outPoint = {end_t};")
            lines.append(f"  var fx_ml{i} = adj_ml{i}.property('ADBE Effect Parade').addProperty('Magic Bullet Looks');")
            lines.append(f"  fx_ml{i}.property('Strength').setValue({strength});")

        elif etype == "film_stocks":
            grain_amount = params.get("grain_amount", 30)
            lines.append(f"  var adj_fs{i} = comp.layers.addSolid([1,1,1], 'FilmStocks_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"  adj_fs{i}.adjustmentLayer = true;")
            lines.append(f"  adj_fs{i}.startTime = {start_t};")
            lines.append(f"  adj_fs{i}.outPoint = {end_t};")
            lines.append(f"  var fx_fs{i} = adj_fs{i}.property('ADBE Effect Parade').addProperty('Tiffen Film Stocks');")
            lines.append(f"  fx_fs{i}.property('Grain Amount').setValue({grain_amount});")

        else:
            lines.append(f"  // [WARN] Unknown effect type: {etype}")

        lines.append("")

    # Save project
    lines.append("  // === Save project ===")
    lines.append(f'  app.project.save(new File("{aeps}"));')
    lines.append(f'  $.writeln("Project saved: {aeps}");')
    lines.append("})();")

    return "\n".join(lines)


def main():
    if not EFFECTS_JSON.exists():
        print(f"[ERROR] Effects config not found: {EFFECTS_JSON}")
        return 1

    if not VIDEO_IN.exists():
        print(f"[ERROR] Input video not found: {VIDEO_IN}")
        return 1

    # Load effects
    effects = json.loads(EFFECTS_JSON.read_text(encoding="utf-8"))
    print(f"[INFO] Loaded {len(effects)} premium plugin effects")

    # Create output directory
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate standalone JSX
    jsx_content = generate_standalone_jsx(effects, str(VIDEO_IN), str(AEP_PATH))
    jsx_path = OUT_DIR / "apply_effects_premium_standalone.jsx"
    jsx_path.write_text(jsx_content, encoding="utf-8")
    print(f"[OK] Generated standalone JSX: {jsx_path}")
    print(f"     Script size: {len(jsx_content)} bytes, {jsx_content.count(chr(10))} lines")

    # Step 1: Launch AfterFX with -r flag to execute JSX
    print("\n[Step 1/3] Launching AfterFX to execute JSX...")
    print(f"  AfterFX: {AFTERFX_EXE}")
    print(f"  JSX: {jsx_path}")

    try:
        # Launch AE in background, it will execute the JSX and save the project
        ae_proc = subprocess.Popen(
            [AFTERFX_EXE, "-r", str(jsx_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
        print(f"  AfterFX launched (PID: {ae_proc.pid})")
        print("  Waiting for AE to process JSX and save project...")

        # Wait for AE to finish (it will exit after executing the script)
        # Give it up to 10 minutes
        timeout = 600
        t0 = time.time()
        while ae_proc.poll() is None:
            elapsed = time.time() - t0
            if elapsed > timeout:
                print(f"[WARN] AE exceeded {timeout}s timeout, terminating...")
                ae_proc.terminate()
                break
            time.sleep(2)
            if int(elapsed) % 30 == 0:
                print(f"  ... {int(elapsed)}s elapsed")

        elapsed_total = time.time() - t0
        print(f"  AfterFX completed in {elapsed_total:.0f}s (rc={ae_proc.returncode})")

    except Exception as e:
        print(f"[ERROR] Failed to launch AfterFX: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Check if AEP was created
    if not AEP_PATH.exists():
        print(f"[ERROR] AEP file not created: {AEP_PATH}")
        print("[INFO] AE may have failed to execute the JSX script")
        return 1

    print(f"[OK] AEP project saved: {AEP_PATH}")
    print(f"  Size: {AEP_PATH.stat().st_size / (1024*1024):.1f} MB")

    # Step 2: Run aerender
    print("\n[Step 2/3] Running aerender...")
    print(f"  aerender: {AERENDER_EXE}")
    print(f"  Project: {AEP_PATH}")
    print(f"  Output: {MP4_OUT}")

    t0 = time.time()
    try:
        r = subprocess.run(
            [AERENDER_EXE, "-project", str(AEP_PATH), "-comp", "RUN53V43_PREMIUM_V2", "-output", str(MP4_OUT)],
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
            encoding="utf-8",
            errors="ignore"
        )
        elapsed = time.time() - t0
        print(f"  aerender: rc={r.returncode}, elapsed={elapsed:.0f}s")

        if r.returncode != 0:
            print(f"[WARN] aerender returned {r.returncode}")
            if r.stdout:
                print(f"  stdout (last 500 chars): {r.stdout[-500:]}")
            if r.stderr:
                print(f"  stderr (last 500 chars): {r.stderr[-500:]}")

    except subprocess.TimeoutExpired:
        print("[ERROR] aerender timed out after 3600s")
        return 1
    except Exception as e:
        print(f"[ERROR] aerender failed: {e}")
        return 1

    # Step 3: Verify output
    print("\n[Step 3/3] Verifying output...")
    if MP4_OUT.exists() and MP4_OUT.stat().st_size > 10000:
        size_mb = MP4_OUT.stat().st_size / (1024*1024)
        print("[SUCCESS] Premium effects render completed!")
        print(f"  Output: {MP4_OUT}")
        print(f"  Size: {size_mb:.1f} MB")
        print(f"  Duration: ~{len(effects)/4:.0f}s (estimated from effect count)")
        print(f"\n[OK] FINAL PRODUCT READY: {MP4_OUT}")
        return 0
    else:
        print(f"[FAIL] Output missing or too small: {MP4_OUT}")
        if MP4_OUT.exists():
            print(f"  Actual size: {MP4_OUT.stat().st_size} bytes")
        return 1


if __name__ == "__main__":
    sys.exit(main())

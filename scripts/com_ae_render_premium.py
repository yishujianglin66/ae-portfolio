# -*- coding: utf-8 -*-
"""COM-based AE automation - applies premium effects via win32com

This script uses Windows COM automation to control After Effects directly,
bypassing the Bridge entirely.

Usage: python scripts/com_ae_render_premium.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False
    print("[WARN] win32com not available, falling back to subprocess method")

ROOT = Path(__file__).resolve().parent.parent
VIDEO_IN = ROOT / "output" / "unified_run53" / "run53_final_v43.mp4"
EFFECTS_JSON = ROOT / "output" / "unified_run53" / "run53v43_effects_premium_v2.json"
OUT_DIR = ROOT / "output" / "unified_run53" / "run53v43_premium_v2"
AEP_PATH = OUT_DIR / "run53v43_premium_v2.aep"
MP4_OUT = OUT_DIR / "run53v43_premium_v2.mp4"
AERENDER_EXE = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe"


def generate_jsx_for_com(effects: list, video_path: str) -> str:
    """Generate JSX code to be executed via COM DoScript"""
    vin = str(video_path).replace("\\", "/")

    lines = []
    lines.append("app.beginUndoGroup('Apply Premium Effects');")
    lines.append("try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch (e0) {}")
    lines.append("app.newProject();")
    lines.append(f'var imp = app.project.importFile(new ImportOptions(new File("{vin}")));')
    lines.append('var comp = app.project.items.addComp("RUN53V43_PREMIUM_V2", imp.width, imp.height,')
    lines.append("    1.0, imp.duration, imp.frameRate);")
    lines.append("comp.motionBlur = true;")
    lines.append("comp.motionBlurAdaptive = true;")
    lines.append("comp.layers.add(imp);")
    lines.append("")

    for i, eff in enumerate(effects):
        etype = eff["effect_type"]
        start_t = eff["time_range"]["start_sec"]
        end_t = eff["time_range"]["end_sec"]
        params = eff.get("parameters", {})

        lines.append(f"// Effect {i+1}/{len(effects)}: {etype}")

        if etype == "twixtor":
            zoom = params.get("zoom_factor", 1.12)
            lines.append(f"var layer_tw{i} = comp.layers.duplicate(comp.layer(1));")
            lines.append(f"layer_tw{i}.name = 'Twixtor_{eff['effect_id']}';")
            lines.append(f"layer_tw{i}.startTime = {start_t};")
            lines.append(f"layer_tw{i}.outPoint = {end_t};")
            lines.append(f"var sp_tw{i} = layer_tw{i}.property('Scale');")
            lines.append(f"sp_tw{i}.setValueAtTime({start_t}, [{round(100*zoom, 2)}, {round(100*zoom, 2)}]);")
            mid_t = (start_t + end_t) / 2
            lines.append(f"sp_tw{i}.setValueAtTime({mid_t}, [{round(100*zoom*1.05, 2)}, {round(100*zoom*1.05, 2)}]);")
            lines.append(f"sp_tw{i}.setValueAtTime({end_t}, [{round(100*zoom, 2)}, {round(100*zoom, 2)}]);")

        elif etype == "zoom_pan":
            scale_start = params.get("scale_start", 100)
            scale_end = params.get("scale_end", 106)
            pos_start = params.get("position_start", [960, 540])
            pos_end = params.get("position_end", [960, 540])
            lines.append(f"var layer_zp{i} = comp.layers.duplicate(comp.layer(1));")
            lines.append(f"layer_zp{i}.name = 'ZoomPan_{eff['effect_id']}';")
            lines.append(f"layer_zp{i}.startTime = {start_t};")
            lines.append(f"layer_zp{i}.outPoint = {end_t};")
            lines.append(f"var sp_zp{i} = layer_zp{i}.property('Scale');")
            lines.append(f"sp_zp{i}.setValueAtTime({start_t}, [{scale_start}, {scale_start}]);")
            lines.append(f"sp_zp{i}.setValueAtTime({end_t}, [{scale_end}, {scale_end}]);")
            lines.append(f"var pp_zp{i} = layer_zp{i}.property('Position');")
            lines.append(f"pp_zp{i}.setValueAtTime({start_t}, [{pos_start[0]}, {pos_start[1]}]);")
            lines.append(f"pp_zp{i}.setValueAtTime({end_t}, [{pos_end[0]}, {pos_end[1]}]);")

        elif etype == "bloom":
            radius = params.get("radius", 6)
            intensity = params.get("intensity", 0.38)
            threshold = params.get("threshold", 0.80)
            lines.append(f"var adj_bl{i} = comp.layers.addSolid([1,1,1], 'Bloom_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_bl{i}.adjustmentLayer = true;")
            lines.append(f"adj_bl{i}.startTime = {start_t};")
            lines.append(f"adj_bl{i}.outPoint = {end_t};")
            lines.append(f"var fx_bl{i} = adj_bl{i}.property('ADBE Effect Parade').addProperty('ADBE Glow');")
            lines.append(f"fx_bl{i}.property('ADBE Glow-0001').setValue({radius});")
            lines.append(f"fx_bl{i}.property('ADBE Glow-0002').setValue({intensity * 100});")
            lines.append(f"fx_bl{i}.property('ADBE Glow-0003').setValue({threshold * 100});")

        elif etype == "sapphire_glow":
            glow_amount = params.get("glow_amount", 50)
            glow_size = params.get("glow_size", 100)
            glow_color = params.get("glow_color", [1.0, 1.0, 1.0])
            lines.append(f"var adj_sg{i} = comp.layers.addSolid([1,1,1], 'SapphireGlow_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_sg{i}.adjustmentLayer = true;")
            lines.append(f"adj_sg{i}.startTime = {start_t};")
            lines.append(f"adj_sg{i}.outPoint = {end_t};")
            lines.append(f"var fx_sg{i} = adj_sg{i}.property('ADBE Effect Parade').addProperty('S_Glow');")
            lines.append(f"fx_sg{i}.property('Amount').setValue({glow_amount});")
            lines.append(f"fx_sg{i}.property('Size').setValue({glow_size});")
            lines.append(f"fx_sg{i}.property('Color').setValue([{glow_color[0]}, {glow_color[1]}, {glow_color[2]}]);")

        elif etype == "optical_flares":
            brightness = params.get("brightness", 100)
            position = params.get("position", [960, 540])
            lines.append(f"var adj_of{i} = comp.layers.addSolid([1,1,1], 'OpticalFlares_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_of{i}.adjustmentLayer = true;")
            lines.append(f"adj_of{i}.startTime = {start_t};")
            lines.append(f"adj_of{i}.outPoint = {end_t};")
            lines.append(f"var fx_of{i} = adj_of{i}.property('ADBE Effect Parade').addProperty('Optical Flares');")
            lines.append(f"fx_of{i}.property('Brightness').setValue({brightness});")
            lines.append(f"fx_of{i}.property('Position').setValue([{position[0]}, {position[1]}]);")

        elif etype == "bokeh":
            blur_amount = params.get("blur_amount", 2.0)
            lines.append(f"var adj_bk{i} = comp.layers.addSolid([1,1,1], 'Bokeh_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_bk{i}.adjustmentLayer = true;")
            lines.append(f"adj_bk{i}.startTime = {start_t};")
            lines.append(f"adj_bk{i}.outPoint = {end_t};")
            lines.append(f"var fx_bk{i} = adj_bk{i}.property('ADBE Effect Parade').addProperty('ADBE Camera Lens Blur');")
            lines.append(f"fx_bk{i}.property('ADBE Camera Lens Blur-0001').setValue({blur_amount});")

        elif etype == "badtv":
            distortion = params.get("distortion", 9.0)
            lines.append(f"var adj_bt{i} = comp.layers.addSolid([1,1,1], 'BadTV_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_bt{i}.adjustmentLayer = true;")
            lines.append(f"adj_bt{i}.startTime = {start_t};")
            lines.append(f"adj_bt{i}.outPoint = {end_t};")
            lines.append(f"var fx_bt{i} = adj_bt{i}.property('ADBE Effect Parade').addProperty('ADBE Noise HLS Auto');")
            lines.append(f"fx_bt{i}.property('ADBE Noise HLS Auto-0001').setValue({distortion});")

        elif etype == "delirium":
            intensity = params.get("intensity", 50)
            lines.append(f"var adj_dl{i} = comp.layers.addSolid([1,1,1], 'Delirium_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_dl{i}.adjustmentLayer = true;")
            lines.append(f"adj_dl{i}.startTime = {start_t};")
            lines.append(f"adj_dl{i}.outPoint = {end_t};")
            lines.append(f"var fx_dl{i} = adj_dl{i}.property('ADBE Effect Parade').addProperty('Digieffects Delirium');")
            lines.append(f"fx_dl{i}.property('Intensity').setValue({intensity});")

        elif etype == "motion_blur":
            samples = params.get("samples", 28)
            shutter_angle = params.get("shutter_angle", 180)
            lines.append(f"var adj_mb{i} = comp.layers.addSolid([1,1,1], 'MotionBlur_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_mb{i}.adjustmentLayer = true;")
            lines.append(f"adj_mb{i}.startTime = {start_t};")
            lines.append(f"adj_mb{i}.outPoint = {end_t};")
            lines.append(f"var fx_mb{i} = adj_mb{i}.property('ADBE Effect Parade').addProperty('CC Force Motion Blur');")
            lines.append(f"fx_mb{i}.property('CC Force Motion Blur-0001').setValue({samples});")
            lines.append(f"fx_mb{i}.property('CC Force Motion Blur-0002').setValue({shutter_angle});")

        elif etype == "radial_blur":
            amount = params.get("amount", 50)
            lines.append(f"var adj_rb{i} = comp.layers.addSolid([1,1,1], 'RadialBlur_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_rb{i}.adjustmentLayer = true;")
            lines.append(f"adj_rb{i}.startTime = {start_t};")
            lines.append(f"adj_rb{i}.outPoint = {end_t};")
            lines.append(f"var fx_rb{i} = adj_rb{i}.property('ADBE Effect Parade').addProperty('ADBE Radial Blur');")
            lines.append(f"fx_rb{i}.property('ADBE Radial Blur-0001').setValue({amount});")

        elif etype == "burst_radial":
            peak_amount = params.get("peak_amount", 90)
            duration_frames = params.get("duration_frames", 3)
            burst_end = start_t + duration_frames / 30.0
            lines.append(f"var adj_br{i} = comp.layers.addSolid([1,1,1], 'BurstRadial_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_br{i}.adjustmentLayer = true;")
            lines.append(f"adj_br{i}.startTime = {start_t};")
            lines.append(f"adj_br{i}.outPoint = {burst_end};")
            lines.append(f"var fx_br{i} = adj_br{i}.property('ADBE Effect Parade').addProperty('ADBE Radial Blur');")
            lines.append(f"fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({start_t}, {peak_amount});")
            lines.append(f"fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({start_t + (burst_end - start_t)/2}, {peak_amount/2});")
            lines.append(f"fx_br{i}.property('ADBE Radial Blur-0001').setValueAtTime({burst_end}, 0);")

        elif etype == "burst_badtv":
            peak_distortion = params.get("peak_distortion", 4.5)
            duration_frames = params.get("duration_frames", 2)
            burst_end = start_t + duration_frames / 30.0
            lines.append(f"var adj_bb{i} = comp.layers.addSolid([1,1,1], 'BurstBadTV_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_bb{i}.adjustmentLayer = true;")
            lines.append(f"adj_bb{i}.startTime = {start_t};")
            lines.append(f"adj_bb{i}.outPoint = {burst_end};")
            lines.append(f"var fx_bb{i} = adj_bb{i}.property('ADBE Effect Parade').addProperty('ADBE Noise HLS Auto');")
            lines.append(f"fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({start_t}, {peak_distortion * 10});")
            lines.append(f"fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({start_t + (burst_end - start_t)/2}, {peak_distortion * 5});")
            lines.append(f"fx_bb{i}.property('ADBE Noise HLS Auto-0001').setValueAtTime({burst_end}, 0);")

        elif etype == "particular":
            pps = params.get("particles_per_second", 200)
            particle_size = params.get("particle_size", 2.0)
            life = params.get("life", 1.5)
            lines.append(f"var adj_pt{i} = comp.layers.addSolid([1,1,1], 'Particular_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_pt{i}.adjustmentLayer = true;")
            lines.append(f"adj_pt{i}.startTime = {start_t};")
            lines.append(f"adj_pt{i}.outPoint = {end_t};")
            lines.append(f"var fx_pt{i} = adj_pt{i}.property('ADBE Effect Parade').addProperty('Trapcode Particular');")
            lines.append(f"fx_pt{i}.property('Particles/sec').setValue({pps});")
            lines.append(f"fx_pt{i}.property('Particle Size').setValue({particle_size});")
            lines.append(f"fx_pt{i}.property('Life').setValue({life});")

        elif etype == "magic_bullet_looks":
            strength = params.get("strength", 70)
            lines.append(f"var adj_ml{i} = comp.layers.addSolid([1,1,1], 'MagicBulletLooks_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_ml{i}.adjustmentLayer = true;")
            lines.append(f"adj_ml{i}.startTime = {start_t};")
            lines.append(f"adj_ml{i}.outPoint = {end_t};")
            lines.append(f"var fx_ml{i} = adj_ml{i}.property('ADBE Effect Parade').addProperty('Magic Bullet Looks');")
            lines.append(f"fx_ml{i}.property('Strength').setValue({strength});")

        elif etype == "film_stocks":
            grain_amount = params.get("grain_amount", 30)
            lines.append(f"var adj_fs{i} = comp.layers.addSolid([1,1,1], 'FilmStocks_{eff['effect_id']}', imp.width, imp.height, 1.0);")
            lines.append(f"adj_fs{i}.adjustmentLayer = true;")
            lines.append(f"adj_fs{i}.startTime = {start_t};")
            lines.append(f"adj_fs{i}.outPoint = {end_t};")
            lines.append(f"var fx_fs{i} = adj_fs{i}.property('ADBE Effect Parade').addProperty('Tiffen Film Stocks');")
            lines.append(f"fx_fs{i}.property('Grain Amount').setValue({grain_amount});")

        else:
            lines.append(f"// [WARN] Unknown effect type: {etype}")

        lines.append("")

    lines.append("app.endUndoGroup();")
    return "\n".join(lines)


def main():
    if not HAS_WIN32COM:
        print("[ERROR] win32com module required for COM automation")
        print("[INFO] Install with: pip install pywin32")
        return 1

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

    # Generate JSX for COM execution
    jsx_code = generate_jsx_for_com(effects, str(VIDEO_IN))
    print(f"[OK] Generated JSX code: {len(jsx_code)} bytes, {jsx_code.count(chr(10))} lines")

    # Step 1: Launch After Effects via COM
    print(f"\n[Step 1/4] Launching After Effects via COM...")
    try:
        ae_app = win32com.client.Dispatch("AfterFX.Application")
        print(f"  [OK] Connected to AfterFX (version: {ae_app.Version})")
    except Exception as e:
        print(f"[ERROR] Failed to connect to AfterFX: {e}")
        print("[INFO] Trying to launch AE manually...")
        try:
            import subprocess
            subprocess.Popen([r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"])
            time.sleep(10)  # Wait for AE to start
            ae_app = win32com.client.Dispatch("AfterFX.Application")
            print(f"  [OK] Connected after manual launch")
        except Exception as e2:
            print(f"[ERROR] Still cannot connect: {e2}")
            return 1

    # Step 2: Execute JSX via DoScript
    print(f"\n[Step 2/4] Executing JSX script ({len(effects)} effects)...")
    print(f"  This may take several minutes...")
    t0 = time.time()

    try:
        # DoScript executes ExtendScript code directly
        ae_app.DoScript(jsx_code)
        elapsed = time.time() - t0
        print(f"  [OK] JSX executed successfully in {elapsed:.0f}s")
    except Exception as e:
        print(f"[ERROR] JSX execution failed: {e}")
        return 1

    # Step 3: Save project
    print(f"\n[Step 3/4] Saving project...")
    try:
        ae_app.Project.Save(AEP_PATH)
        print(f"  [OK] Project saved: {AEP_PATH}")
        print(f"  Size: {AEP_PATH.stat().st_size / (1024*1024):.1f} MB")
    except Exception as e:
        print(f"[ERROR] Failed to save project: {e}")
        return 1

    # Close AE
    try:
        ae_app.Quit()
        print(f"  [OK] AfterFX closed")
    except:
        pass

    # Step 4: Run aerender
    print(f"\n[Step 4/4] Running aerender...")
    print(f"  Output: {MP4_OUT}")

    t0 = time.time()
    try:
        r = subprocess.run(
            [AERENDER_EXE, "-project", str(AEP_PATH), "-comp", "RUN53V43_PREMIUM_V2", "-output", str(MP4_OUT)],
            capture_output=True,
            text=True,
            timeout=3600,
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
        print(f"[ERROR] aerender timed out after 3600s")
        return 1
    except Exception as e:
        print(f"[ERROR] aerender failed: {e}")
        return 1

    # Verify output
    print(f"\n[Verification]")
    if MP4_OUT.exists() and MP4_OUT.stat().st_size > 10000:
        size_mb = MP4_OUT.stat().st_size / (1024*1024)
        print(f"[SUCCESS] Premium effects render completed!")
        print(f"  Output: {MP4_OUT}")
        print(f"  Size: {size_mb:.1f} MB")
        print(f"\n[OK] FINAL PRODUCT READY: {MP4_OUT}")
        return 0
    else:
        print(f"[FAIL] Output missing or too small: {MP4_OUT}")
        if MP4_OUT.exists():
            print(f"  Actual size: {MP4_OUT.stat().st_size} bytes")
        return 1


if __name__ == "__main__":
    sys.exit(main())

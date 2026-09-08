# -*- coding: utf-8 -*-
"""自动应用 run53v43 特效到视频 — AE Bridge Channel 自动化

使用刚集成的 visual effect schema 验证过的 8 个特效配置,
通过 AERenderChannel 自动生成 JSX + aerender 渲染。

用法: python scripts/auto_apply_run53v43_effects.py
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
EFFECTS_JSON = ROOT / "output" / "unified_run53" / "run53v43_effects.json"
OUT_DIR = ROOT / "output" / "unified_run53" / "run53v43_polished"
AEP_PATH = OUT_DIR / "run53v43_effects.aep"
MP4_OUT = OUT_DIR / "run53v43_polished.mp4"


def generate_effects_jsx(effects: list, video_path: str, aep_path: str, out_mp4: str) -> str:
    """根据特效配置生成 JSX 脚本"""
    vin = str(video_path).replace("\\", "/")
    aeps = str(aep_path).replace("\\", "/")
    mp4s = str(out_mp4).replace("\\", "/")

    lines = []
    lines.append("// run53v43 特效应用 - 自动生成 (ES3)")
    lines.append("(function() {")
    lines.append("  try {")
    lines.append("    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);")
    lines.append("  } catch (e0) {}")
    lines.append("  app.newProject();")
    lines.append(f'  var imp = app.project.importFile(new ImportOptions(new File("{vin}")));')
    lines.append('  var comp = app.project.items.addComp("RUN53V43_EFFECTS", imp.width, imp.height,')
    lines.append("      1.0, imp.duration, imp.frameRate);")
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

        lines.append(f"  // 特效 {i+1}: {etype} @ {start_t:.2f}s-{end_t:.2f}s")

        if etype == "twixtor":
            # Twixtor 慢镜效果 (需要插件, 用 stretch 模拟)
            zoom = params.get("zoom_factor", 1.12)
            speed_profile = params.get("speed_profile", [[0.0, 1.0], [1.0, 1.0]])
            lines.append(f"  var layer_tw{i} = comp.layers.duplicate(comp.layer(1));")
            lines.append(f"  layer_tw{i}.name = 'Twixtor_{eff['effect_id']}';")
            lines.append(f"  layer_tw{i}.startTime = 0;")
            lines.append(f"  layer_tw{i}.outPoint = {dur};")
            # 缩放关键帧
            lines.append(f"  var sp_tw = layer_tw{i}.property('Scale');")
            lines.append(f"  sp_tw.setValueAtTime(0, [{100*zoom}, {100*zoom}]);")
            lines.append(f"  sp_tw.setValueAtTime({dur/2}, [{100*zoom*1.05}, {100*zoom*1.05}]);")
            lines.append(f"  sp_tw.setValueAtTime({dur}, [{100*zoom}, {100*zoom}]);")

        elif etype == "bloom":
            # Bloom 发光
            radius = params.get("radius", 6)
            intensity = params.get("intensity", 0.38)
            threshold = params.get("threshold", 0.80)
            lines.append(f"  var adj_bl{i} = comp.layers.addSolid([1,1,1], 'Bloom_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bl{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bl{i}.startTime = {start_t};")
            lines.append(f"  adj_bl{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bl{i} = adj_bl{i}.property('Effects');")
            lines.append(f"  var gl_bl{i} = fx_bl{i}.addProperty('ADBE Glo2');")
            lines.append(f"  gl_bl{i}.property('ADBE Glo2-0003').setValue({radius});")  # Radius
            lines.append(f"  gl_bl{i}.property('ADBE Glo2-0004').setValue({intensity});")  # Intensity
            lines.append(f"  gl_bl{i}.property('ADBE Glo2-0002').setValue({threshold});")  # Threshold

        elif etype == "badtv":
            # BadTV 故障
            distortion = params.get("distortion", 9.0)
            lines.append(f"  var adj_bt{i} = comp.layers.addSolid([1,1,1], 'BadTV_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bt{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bt{i}.startTime = {start_t};")
            lines.append(f"  adj_bt{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bt{i} = adj_bt{i}.property('Effects');")
            lines.append(f"  var bt{i} = fx_bt{i}.addProperty('GUTS BadTV');")
            lines.append(f"  bt{i}.property('GUTS BadTV-0001').setValue({distortion});")  # Distortion
            # 包络衰减
            if envelope.get("enabled"):
                peak = envelope.get("peak_value", 1.0)
                decay = envelope.get("decay_seconds", 0.16)
                lines.append(f"  bt{i}.property('GUTS BadTV-0001').setValueAtTime({start_t}, {distortion * peak});")
                lines.append(f"  bt{i}.property('GUTS BadTV-0001').setValueAtTime({start_t + decay}, {distortion * 0.3});")

        elif etype == "burst_radial":
            # Radial Burst 径向冲击
            peak_amount = params.get("peak_amount", 90)
            lines.append(f"  var adj_rb{i} = comp.layers.addSolid([1,1,1], 'RadialBurst_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_rb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_rb{i}.startTime = {start_t};")
            lines.append(f"  adj_rb{i}.outPoint = {end_t};")
            lines.append(f"  var fx_rb{i} = adj_rb{i}.property('Effects');")
            lines.append(f"  var rb{i} = fx_rb{i}.addProperty('CC Radial Fast Blur');")
            lines.append(f"  rb{i}.property('CC Radial Fast Blur-0002').setValue({peak_amount});")  # Amount
            if envelope.get("enabled"):
                decay = envelope.get("decay_seconds", 0.08)
                lines.append(f"  rb{i}.property('CC Radial Fast Blur-0002').setValueAtTime({start_t}, {peak_amount});")
                lines.append(f"  rb{i}.property('CC Radial Fast Blur-0002').setValueAtTime({start_t + decay}, {peak_amount * 0.3});")

        elif etype == "bokeh":
            # Bokeh 景深虚化
            blur_amount = params.get("blur_amount", 2.0)
            lines.append(f"  var adj_bk{i} = comp.layers.addSolid([1,1,1], 'Bokeh_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bk{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bk{i}.startTime = {start_t};")
            lines.append(f"  adj_bk{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bk{i} = adj_bk{i}.property('Effects');")
            lines.append(f"  var bk{i} = fx_bk{i}.addProperty('RWB Fast Bokeh');")
            lines.append(f"  bk{i}.property('RWB Fast Bokeh-0001').setValue({blur_amount});")  # Blur Amount

        elif etype == "burst_badtv":
            # Burst BadTV 爆发
            peak_distortion = params.get("peak_distortion", 4.5)
            lines.append(f"  var adj_bbt{i} = comp.layers.addSolid([1,1,1], 'BurstBadTV_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_bbt{i}.adjustmentLayer = true;")
            lines.append(f"  adj_bbt{i}.startTime = {start_t};")
            lines.append(f"  adj_bbt{i}.outPoint = {end_t};")
            lines.append(f"  var fx_bbt{i} = adj_bbt{i}.property('Effects');")
            lines.append(f"  var bbt{i} = fx_bbt{i}.addProperty('GUTS BadTV');")
            lines.append(f"  bbt{i}.property('GUTS BadTV-0001').setValue({peak_distortion});")
            if envelope.get("enabled"):
                decay = envelope.get("decay_seconds", 0.08)
                lines.append(f"  bbt{i}.property('GUTS BadTV-0001').setValueAtTime({start_t}, {peak_distortion});")
                lines.append(f"  bbt{i}.property('GUTS BadTV-0001').setValueAtTime({start_t + decay}, {peak_distortion * 0.3});")

        elif etype == "motion_blur":
            # Motion Blur 运动模糊
            samples = params.get("samples", 28)
            lines.append(f"  var adj_mb{i} = comp.layers.addSolid([1,1,1], 'MotionBlur_{eff['effect_id']}', imp.width, imp.height, 1.0, imp.duration);")
            lines.append(f"  adj_mb{i}.adjustmentLayer = true;")
            lines.append(f"  adj_mb{i}.startTime = {start_t};")
            lines.append(f"  adj_mb{i}.outPoint = {end_t};")
            lines.append(f"  var fx_mb{i} = adj_mb{i}.property('Effects');")
            lines.append(f"  var mb{i} = fx_mb{i}.addProperty('CC Force Motion Blur');")
            lines.append(f"  mb{i}.property('CC Force Motion Blur-0001').setValue({samples});")  # Samples

        elif etype == "zoom_pan":
            # Zoom Pan 缩放平移
            scale_start = params.get("scale_start", 100)
            scale_end = params.get("scale_end", 106)
            pos_start = params.get("position_start", [960, 540])
            pos_end = params.get("position_end", [960, 540])
            lines.append(f"  var layer_zp{i} = comp.layers.duplicate(comp.layer(1));")
            lines.append(f"  layer_zp{i}.name = 'ZoomPan_{eff['effect_id']}';")
            lines.append(f"  layer_zp{i}.startTime = {start_t};")
            lines.append(f"  layer_zp{i}.outPoint = {end_t};")
            # Scale 关键帧
            lines.append(f"  var sp_zp = layer_zp{i}.property('Scale');")
            lines.append(f"  sp_zp.setValueAtTime({start_t}, [{scale_start}, {scale_start}]);")
            lines.append(f"  sp_zp.setValueAtTime({end_t}, [{scale_end}, {scale_end}]);")
            # Position 关键帧
            lines.append(f"  var pp_zp = layer_zp{i}.property('Position');")
            lines.append(f"  pp_zp.setValueAtTime({start_t}, [{pos_start[0]}, {pos_start[1]}]);")
            lines.append(f"  pp_zp.setValueAtTime({end_t}, [{pos_end[0]}, {pos_end[1]}]);")

        lines.append("")

    # 保存工程并渲染
    lines.append(f'  app.project.save(new File("{aeps}"));')
    lines.append('  "ok";')
    lines.append("  } catch(e) {")
    lines.append('    "ERR:" + e.toString();')
    lines.append("  }")
    lines.append("})")

    return "\ufeff" + "\n".join(lines)  # UTF-8 BOM


def main():
    if not VIDEO_IN.exists():
        print(f"[ERROR] 输入视频不存在: {VIDEO_IN}")
        return 1

    if not EFFECTS_JSON.exists():
        print(f"[ERROR] 特效配置不存在: {EFFECTS_JSON}")
        return 1

    # 加载已验证的特效配置
    effects = json.loads(EFFECTS_JSON.read_text(encoding="utf-8"))
    print(f"[INFO] 加载 {len(effects)} 个已验证特效:")
    for i, eff in enumerate(effects):
        print(f"  [{i+1}] {eff['effect_type']} @ {eff['time_range']['start_sec']:.2f}s-{eff['time_range']['end_sec']:.2f}s")

    # 创建输出目录
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 初始化 AE 渲染通道
    channel = AERenderChannel(out_dir=str(OUT_DIR))

    # 生成 JSX 脚本
    jsx_content = generate_effects_jsx(effects, str(VIDEO_IN), str(AEP_PATH), str(MP4_OUT))
    jsx_path = OUT_DIR / "apply_effects.jsx"
    jsx_path.write_text(jsx_content, encoding="utf-8")
    print(f"\n[INFO] JSX 脚本已生成: {jsx_path}")

    # 确保 AE 运行
    print("\n[AE通道] 检查 AE 状态...")
    if not channel._ensure_ae_running(auto_launch=False):
        print("[WARN] AE 未运行,尝试启动...")
        if not channel._ensure_ae_running(auto_launch=True):
            print("[ERROR] AE 启动失败")
            return 1

    # Bridge 探测
    print("[AE通道] Bridge 探测...")
    _probe_script = "app.version;"
    ping = channel._bridge_run_jsx(timeout=90, command="executeAtomScript",
                                   args={"script": _probe_script, "scriptContent": _probe_script})
    if not (ping and ping.get("status") == "success"):
        print(f"[WARN] Bridge 探测未成功: {(ping or {}).get('message', '无响应')}")
        print("[INFO] 仍尝试继续执行...")

    # 执行 JSX
    print("\n[AE通道] 执行 JSX 脚本应用特效...")
    bridge_res = channel._bridge_run_jsx(str(jsx_path), timeout=300)
    if bridge_res is None:
        print("[ERROR] Bridge 无响应 (300s 超时)")
        failures = channel.get_failures()
        if failures:
            for f in failures:
                print(f"  - {f}")
        return 1

    print(f"  Bridge 响应: status={bridge_res.get('status', '')}, message={bridge_res.get('message', '')}")

    # 关闭 AE 内工程
    _close_script = "try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); 'closed'; } catch(e) { String(e); }"
    channel._bridge_run_jsx(timeout=60, command="executeAtomScript",
                            args={"script": _close_script, "scriptContent": _close_script})

    # aerender 渲染
    print(f"\n[AE通道] aerender 渲染到 {MP4_OUT}...")
    t0 = time.time()
    r = subprocess.run([aerender_exe(), "-project", str(AEP_PATH), "-comp", "RUN53V43_EFFECTS",
                        "-output", str(MP4_OUT)],
                       capture_output=True, text=True, timeout=1800,
                       encoding="utf-8", errors="ignore")
    elapsed = time.time() - t0
    print(f"  aerender: rc={r.returncode}, 耗时{elapsed:.0f}s")

    if r.returncode != 0:
        print(f"[WARN] aerender 返回码 {r.returncode}")
        print(f"  stdout: {r.stdout[:500]}")
        print(f"  stderr: {r.stderr[:500]}")

    # 检查结果
    if MP4_OUT.exists() and MP4_OUT.stat().st_size > 10000:
        print(f"\n✅ [成功] 特效应用完成: {MP4_OUT}")
        print(f"  文件大小: {MP4_OUT.stat().st_size / (1024*1024):.1f} MB")
        return 0
    else:
        print(f"\n❌ [失败] 输出文件不存在或太小: {MP4_OUT}")
        failures = channel.get_failures()
        if failures:
            print("\n失败详情:")
            for f in failures:
                print(f"  - {f}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

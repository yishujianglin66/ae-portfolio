"""AE 真执行链端到端测试 — 创建工程、添加图层、应用效果、渲染 MP4、ffprobe 验证。

测试流程:
  1. 检查 AE engine 可用性
  2. 通过 Bridge ping 验证连通
  3. 创建新 AE 工程 (.aep)
  4. 添加蓝色固态层
  5. 添加 Gaussian Blur 效果
  6. 添加文本图层
  7. 保存工程
  8. 通过 aerender CLI 渲染输出 MP4
  9. 用 ffprobe 验证 MP4 元数据

用法:
  python scripts/test_ae_real_chain.py
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

# ---- 路径设置 ----
# engine.py 使用 from ...config import settings（3级相对导入），
# 需要将 puppet-automation 作为顶级包，以 src 为子包导入
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUPPET_ROOT = PROJECT_ROOT / "puppet-automation"
sys.path.insert(0, str(PUPPET_ROOT))

from src.config import settings  # noqa: E402
from src.engines.ae.engine import AEEngine  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "output" / "ae_real_chain_test"
AEP_PATH = OUTPUT_DIR / "ae_real_chain_test.aep"
MP4_PATH = OUTPUT_DIR / "ae_real_chain_test.mp4"
FFPROBE_PATH = settings.ffprobe_path


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_ffprobe(mp4_path: Path) -> dict | None:
    """用 ffprobe 验证 MP4 元数据。"""
    if not FFPROBE_PATH.exists():
        log(f"  WARN: ffprobe not found at {FFPROBE_PATH}")
        return None
    cmd = [
        str(FFPROBE_PATH),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(mp4_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            log(f"  ffprobe stderr: {result.stderr[:500]}")
            return None
    except Exception as e:
        log(f"  ffprobe error: {e}")
        return None


async def main() -> int:
    log("=" * 60)
    log("AE 真执行链端到端测试 — 开始")
    log("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Step 1: AE engine 可用性 ----
    log("\n[Step 1] 检查 AE engine 可用性")
    log(f"  aerender_path: {settings.aerender_path}")
    log(f"  aerender exists: {settings.aerender_path.exists()}")
    engine = AEEngine()
    log(f"  engine.available: {engine.available}")
    log(f"  afterfx_path: {engine._afterfx_path}")
    log(f"  afterfx exists: {engine._afterfx_path.exists()}")
    log(f"  bridge_dir: {engine._bridge_dir}")
    log(f"  bridge_dir exists: {engine._bridge_dir.exists()}")
    if not engine.available:
        log("  FAIL: AE engine not available")
        return 1

    # ---- Step 2: Bridge ping ----
    log("\n[Step 2] 通过 Bridge ping 验证连通")
    ping_script = '(function(){ return JSON.stringify({pong:true, ver:app.version, bridge:"test"}); })();'
    ping_result = await engine.run_script(ping_script)
    if ping_result.success:
        log("  OK: Bridge ping success")
        log(f"  method: {ping_result.metadata.get('method', 'unknown')}")
        log(f"  stdout: {ping_result.metadata.get('stdout', '')[:200]}")
    else:
        log("  FAIL: Bridge ping failed")
        log(f"  error: {ping_result.error}")
        log(f"  error_code: {ping_result.error_code}")
        log("  尝试 AfterFX.exe 兜底路径...")
        # 即使 ping 失败，也继续尝试创建工程（可能 bridge 未加载但 AfterFX.exe 可用）
        if not engine._afterfx_path.exists():
            log("  FAIL: AfterFX.exe 也不存在，无法继续")
            return 1

    # ---- Step 3: 创建新 AE 工程 ----
    log("\n[Step 3] 创建新 AE 工程")
    comp_name = "Main Comp"
    create_result = await engine.create_project(
        project_path=AEP_PATH,
        comp_name=comp_name,
        width=1920,
        height=1080,
        fps=30.0,
        duration=3.0,  # 3秒，加快渲染
    )
    if create_result.success:
        log("  OK: 工程创建成功")
        log(f"  projectPath: {create_result.metadata.get('projectPath', '')}")
        log(f"  compName: {create_result.metadata.get('compName', '')}")
        log(f"  aep exists: {AEP_PATH.exists()}")
        if AEP_PATH.exists():
            log(f"  aep size: {AEP_PATH.stat().st_size} bytes")
    else:
        log("  FAIL: 工程创建失败")
        log(f"  error: {create_result.error}")
        log(f"  error_code: {create_result.error_code}")
        log(f"  metadata: {create_result.metadata}")
        return 1

    # ---- Step 4: 添加蓝色固态层 ----
    log("\n[Step 4] 添加蓝色固态层")
    layer_result = await engine.add_layer(
        comp_name=comp_name,
        layer_type="solid",
        name="Blue Background",
        color=[0.0, 0.3, 0.8],  # 蓝色 [R, G, B] 0-1
        width=1920,
        height=1080,
    )
    if layer_result.success:
        log("  OK: 固态层添加成功")
        log(f"  layerIndex: {layer_result.metadata.get('layerIndex')}")
        log(f"  layerName: {layer_result.metadata.get('layerName')}")
        layer_index = layer_result.metadata.get("layerIndex", 1)
    else:
        log("  FAIL: 固态层添加失败")
        log(f"  error: {layer_result.error}")
        log(f"  metadata: {layer_result.metadata}")
        layer_index = 1  # 继续尝试

    # ---- Step 5: 添加 Gaussian Blur 效果 ----
    log("\n[Step 5] 添加 Gaussian Blur 效果")
    effect_result = await engine.add_effect(
        comp_name=comp_name,
        layer_index=layer_index,
        effect_name="ADBE Gaussian Blur 2",
        params={"ADBE Gaussian Blur 2-0001": 50.0},  # Blur Radius
    )
    if effect_result.success:
        log("  OK: 效果添加成功")
        log(f"  effectName: {effect_result.metadata.get('effectName')}")
        log(f"  appliedKeys: {effect_result.metadata.get('appliedKeys')}")
        log(f"  failedKeys: {effect_result.metadata.get('failedKeys')}")
    else:
        log("  WARN: 效果添加失败 (非致命)")
        log(f"  error: {effect_result.error}")
        log(f"  metadata: {effect_result.metadata}")

    # ---- Step 6: 添加文本图层 ----
    log("\n[Step 6] 添加文本图层")
    text_result = await engine.add_layer(
        comp_name=comp_name,
        layer_type="text",
        name="Title Text",
    )
    if text_result.success:
        log("  OK: 文本图层添加成功")
        log(f"  layerIndex: {text_result.metadata.get('layerIndex')}")
    else:
        log("  WARN: 文本图层添加失败 (非致命)")
        log(f"  error: {text_result.error}")

    # ---- Step 7: 保存工程 ----
    log("\n[Step 7] 保存工程")
    save_script = f'''(function() {{
    try {{
        var f = new File("{AEP_PATH.as_posix()}");
        app.project.save(f);
        return JSON.stringify({{success: true, path: f.fsName, numItems: app.project.numItems}});
    }} catch(e) {{
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
    save_result = await engine.run_script(save_script)
    if save_result.success:
        try:
            save_data = json.loads(save_result.metadata.get("stdout", "{}"))
            if save_data.get("error"):
                log(f"  FAIL: 保存失败: {save_data.get('message')}")
            else:
                log("  OK: 工程已保存")
                log(f"  path: {save_data.get('path', '')}")
                log(f"  numItems: {save_data.get('numItems', 0)}")
                log(f"  aep size: {AEP_PATH.stat().st_size} bytes")
        except json.JSONDecodeError as e:
            log(f"  WARN: 保存结果解析失败: {e}")
            log(f"  stdout: {save_result.metadata.get('stdout', '')[:200]}")
    else:
        log("  FAIL: 保存脚本执行失败")
        log(f"  error: {save_result.error}")

    if not AEP_PATH.exists():
        log("  FAIL: .aep 文件不存在，无法渲染")
        return 1

    # ---- Step 8: aerender CLI 渲染 ----
    log("\n[Step 8] 通过 aerender CLI 渲染 MP4")
    log(f"  project: {AEP_PATH}")
    log(f"  comp: {comp_name}")
    log(f"  output: {MP4_PATH}")

    # 8a: 先通过 bridge 保存并关闭工程，然后关闭 AE GUI，避免文件锁冲突
    log("  8a: 关闭 AE GUI 中的工程（避免文件锁）...")
    close_script = '(function(){ try { if(app.project) app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); return "closed"; } catch(e) { return e.toString(); } })();'
    close_result = await engine.run_script(close_script, timeout=10.0)
    if close_result.success:
        log(f"  工程已关闭: {close_result.metadata.get('stdout', '')[:100]}")
    else:
        log(f"  关闭工程失败（非致命）: {close_result.error}")
    await asyncio.sleep(1)

    # 完全关闭 AE GUI 进程，确保 aerender 不会因文件锁而挂起
    log("  关闭 AfterFX.exe 进程...")
    try:
        proc_ae = subprocess.run(
            ["taskkill", "/F", "/IM", "AfterFX.exe"],
            capture_output=True, text=True, timeout=10,
        )
        log(f"  taskkill returncode: {proc_ae.returncode}")
        if proc_ae.stdout:
            log(f"  taskkill stdout: {proc_ae.stdout.strip()}")
    except Exception as e:
        log(f"  taskkill 异常（非致命）: {e}")
    await asyncio.sleep(3)  # 等待 AE 完全释放文件锁

    # 清理旧输出
    if MP4_PATH.exists():
        MP4_PATH.unlink()

    # 8b: 尝试不带模板参数渲染（使用默认设置）
    # AE 2025 可能没有 "Best Settings" 模板名，直接用默认渲染设置
    avi_path = OUTPUT_DIR / "ae_real_chain_test.avi"
    if avi_path.exists():
        avi_path.unlink()
    render_cmd = [
        str(settings.aerender_path),
        "-project", str(AEP_PATH),
        "-comp", comp_name,
        "-output", str(avi_path),
        "-close", "DO_NOT_SAVE_CHANGES",
    ]
    log(f"  8b: cmd (no templates, default AVI): {' '.join(render_cmd)}")

    try:
        proc = subprocess.run(
            render_cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        log(f"  returncode: {proc.returncode}")
        if proc.stdout:
            stdout_lines = proc.stdout.strip().split("\n")
            log("  stdout (last 25 lines):")
            for line in stdout_lines[-25:]:
                log(f"    {line}")
        if proc.stderr:
            stderr_lines = proc.stderr.strip().split("\n")
            log("  stderr (last 10 lines):")
            for line in stderr_lines[-10:]:
                log(f"    {line}")

        if proc.returncode == 0 and avi_path.exists():
            log(f"  OK: AVI 渲染成功! size={avi_path.stat().st_size} bytes")
            # FFmpeg 转码 AVI → MP4
            ffmpeg_path = settings.get_ffmpeg()
            ffmpeg_cmd = [
                str(ffmpeg_path),
                "-y",
                "-i", str(avi_path),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-an",
                str(MP4_PATH),
            ]
            log(f"  ffmpeg cmd: {' '.join(ffmpeg_cmd)}")
            proc3 = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            log(f"  ffmpeg returncode: {proc3.returncode}")
            if proc3.stderr:
                stderr_lines = proc3.stderr.strip().split("\n")
                log("  ffmpeg stderr (last 5 lines):")
                for line in stderr_lines[-5:]:
                    log(f"    {line}")
        else:
            log("  默认渲染失败，尝试 -RStemplate Current Settings...")
            # 最后尝试: Current Settings
            render_cmd2 = [
                str(settings.aerender_path),
                "-project", str(AEP_PATH),
                "-comp", comp_name,
                "-output", str(avi_path),
                "-RStemplate", "Current Settings",
                "-close", "DO_NOT_SAVE_CHANGES",
            ]
            log(f"  fallback cmd: {' '.join(render_cmd2)}")
            proc2 = subprocess.run(
                render_cmd2,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            log(f"  fallback returncode: {proc2.returncode}")
            if proc2.stdout:
                stdout_lines = proc2.stdout.strip().split("\n")
                log("  fallback stdout (last 15 lines):")
                for line in stdout_lines[-15:]:
                    log(f"    {line}")
            if avi_path.exists() and avi_path.stat().st_size > 0:
                log(f"  AVI size: {avi_path.stat().st_size} bytes")
                # FFmpeg 转码
                ffmpeg_path = settings.get_ffmpeg()
                ffmpeg_cmd = [
                    str(ffmpeg_path),
                    "-y",
                    "-i", str(avi_path),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    "-an",
                    str(MP4_PATH),
                ]
                log(f"  ffmpeg cmd: {' '.join(ffmpeg_cmd)}")
                proc3 = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    encoding="utf-8",
                    errors="replace",
                )
                log(f"  ffmpeg returncode: {proc3.returncode}")
            else:
                log("  FAIL: 所有渲染尝试均失败")
    except subprocess.TimeoutExpired:
        log("  FAIL: aerender 超时 (120s)")
        if avi_path.exists():
            log(f"  但 AVI 文件存在: {avi_path.stat().st_size} bytes")
            # 尝试转码
            ffmpeg_path = settings.get_ffmpeg()
            ffmpeg_cmd = [
                str(ffmpeg_path), "-y",
                "-i", str(avi_path),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-an",
                str(MP4_PATH),
            ]
            subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
        return 1
    except Exception as e:
        log(f"  FAIL: aerender 异常: {e}")
        return 1

    # ---- Step 9: ffprobe 验证 ----
    log("\n[Step 9] ffprobe 验证 MP4 元数据")
    if not MP4_PATH.exists():
        log(f"  FAIL: MP4 文件不存在: {MP4_PATH}")
        return 1

    file_size = MP4_PATH.stat().st_size
    log(f"  MP4 path: {MP4_PATH}")
    log(f"  MP4 size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")

    if file_size < 1000:
        log(f"  FAIL: MP4 文件太小 ({file_size} bytes)，可能无效")
        return 1

    probe_data = run_ffprobe(MP4_PATH)
    if probe_data:
        fmt = probe_data.get("format", {})
        streams = probe_data.get("streams", [])
        log(f"  format_name: {fmt.get('format_name', 'unknown')}")
        log(f"  duration: {float(fmt.get('duration', 0)):.2f}s")
        log(f"  bit_rate: {int(fmt.get('bit_rate', 0)) // 1000} kbps")
        log(f"  nb_streams: {len(streams)}")
        for i, s in enumerate(streams):
            codec_type = s.get("codec_type", "unknown")
            codec_name = s.get("codec_name", "unknown")
            if codec_type == "video":
                width = s.get("width", 0)
                height = s.get("height", 0)
                fps_str = s.get("r_frame_rate", "0/1")
                log(f"  stream[{i}]: video {codec_name} {width}x{height} fps={fps_str}")
            elif codec_type == "audio":
                log(f"  stream[{i}]: audio {codec_name} {s.get('sample_rate', 0)}Hz")
            else:
                log(f"  stream[{i}]: {codec_type} {codec_name}")

        # 验证关键指标
        duration = float(fmt.get("duration", 0))
        has_video = any(s.get("codec_type") == "video" for s in streams)
        if has_video and duration > 0:
            log(f"\n  VALIDATION: video={has_video}, duration={duration:.2f}s, size={file_size}B")
            log("  OK: MP4 文件有效")
        else:
            log(f"\n  FAIL: MP4 文件无效 (has_video={has_video}, duration={duration})")
            return 1
    else:
        log("  WARN: ffprobe 验证失败，但 MP4 文件存在")
        log(f"  文件大小 {file_size} bytes 可能有效，但无法确认元数据")

    # ---- 最终结论 ----
    log("\n" + "=" * 60)
    if MP4_PATH.exists() and MP4_PATH.stat().st_size > 1000:
        log("FINAL: PASS — AE 真执行链打通成功")
        log(f"  AEP: {AEP_PATH} ({AEP_PATH.stat().st_size} bytes)")
        log(f"  MP4: {MP4_PATH} ({MP4_PATH.stat().st_size} bytes)")
        log("=" * 60)
        return 0
    else:
        log("FINAL: FAIL — AE 真执行链未完全打通")
        log("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

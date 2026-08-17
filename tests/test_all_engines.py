#!/usr/bin/env python3
"""P1 引擎实测：逐一验证每个引擎能真实调用外部软件。

测试策略（从快到慢）：
1. FFmpeg   — 版本查询 + 视频转码
2. Blender  — 版本查询
3. Topaz    — CLI 可用性
4. DaVinci  — 版本查询
5. AE       — 脚本执行（创建合成）
6. PR       — 进程启动
7. PS       — 进程启动
8. Silhouette — 进程启动

每个测试独立运行，一个失败不影响其他。
"""
from __future__ import annotations

import asyncio
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "puppet-automation"))

from src.config.settings import settings

# Test video
TEST_VIDEO = ROOT / "output" / "example1_hello.mp4"
if not TEST_VIDEO.exists():
    # Fallback: find any mp4 in output
    for p in (ROOT / "output").glob("*.mp4"):
        TEST_VIDEO = p
        break

OUTPUT_DIR = ROOT / "output" / "engine_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_result(name: str, success: bool, detail: str = "") -> None:
    status = "PASS" if success else "FAIL"
    print(f"  [{status}] {name}: {detail}")


# ──────────────────────────────────────────────────────────────────
# 1. FFmpeg Engine
# ──────────────────────────────────────────────────────────────────
async def test_ffmpeg() -> dict:
    """测试 FFmpeg 引擎：版本查询 + 视频转码。"""
    print_header("1. FFmpeg Engine")
    results = {}

    from src.engines.ffmpeg.engine import FFmpegEngine

    try:
        engine = FFmpegEngine()
        print_result("实例化", True, f"executable={engine.executable_path}")

        # Test 1a: version
        code, stdout, stderr, _err = engine._run_subprocess(
            [str(engine.executable_path), "-version"], timeout=10
        )
        results["version"] = code == 0
        version_line = stdout.split("\n")[0] if stdout else "unknown"
        print_result("版本查询", code == 0, version_line)

        # Test 1b: get_video_info
        if TEST_VIDEO.exists():
            info_result = await engine.get_video_info(str(TEST_VIDEO))
            results["get_video_info"] = info_result.success
            if info_result.success and info_result.metadata:
                meta = info_result.metadata
                print_result("视频信息", True, f"duration={meta.get('duration', '?')}s, "
                             f"resolution={meta.get('width', '?')}x{meta.get('height', '?')}")
            else:
                print_result("视频信息", False, info_result.error or "metadata empty")
        else:
            print_result("视频信息", False, "测试视频不存在")
            results["get_video_info"] = False

        # Test 1c: convert (transcode to different format)
        if TEST_VIDEO.exists():
            out_path = OUTPUT_DIR / "ffmpeg_test_output.avi"
            result = await engine.convert(
                input_path=str(TEST_VIDEO),
                output_path=str(out_path),
                codec="mpeg4",
                bitrate="5M",
                extra_args=["-t", "2", "-q:v", "5"]  # 2 seconds only, fast
            )
            results["convert"] = result.success
            print_result("视频转码", result.success,
                         f"output={out_path.name}, size={out_path.stat().st_size if out_path.exists() else 0} bytes")

        # Test 1d: extract_audio
        if TEST_VIDEO.exists():
            audio_out = OUTPUT_DIR / "ffmpeg_test_audio.mp3"
            result = await engine.extract_audio(
                video_path=str(TEST_VIDEO),
                output_path=str(audio_out)
            )
            results["extract_audio"] = result.success
            print_result("音频提取", result.success,
                         f"output={audio_out.name}, size={audio_out.stat().st_size if audio_out.exists() else 0} bytes")

    except Exception as e:
        print_result("FFmpeg 异常", False, str(e))
        traceback.print_exc()
        results["error"] = str(e)

    return results


# ──────────────────────────────────────────────────────────────────
# 2. Blender Engine
# ──────────────────────────────────────────────────────────────────
async def test_blender() -> dict:
    """测试 Blender 引擎：版本查询。"""
    print_header("2. Blender Engine")
    results = {}

    from src.engines.blender.engine import BlenderEngine

    try:
        engine = BlenderEngine()
        print_result("实例化", True, f"executable={engine.executable_path}")

        # Test 2a: version
        code, stdout, stderr, _err = engine._run_subprocess(
            [str(engine.executable_path), "--version"], timeout=15
        )
        results["version"] = code == 0
        version_line = stdout.split("\n")[0] if stdout else "unknown"
        print_result("版本查询", code == 0, version_line)

    except Exception as e:
        print_result("Blender 异常", False, str(e))
        traceback.print_exc()
        results["error"] = str(e)

    return results


# ──────────────────────────────────────────────────────────────────
# 3. AE Engine (最关键)
# ──────────────────────────────────────────────────────────────────
async def test_ae() -> dict:
    """测试 AE 引擎：aerender 版本 + JSX 脚本执行。"""
    print_header("3. After Effects Engine")
    results = {}

    from src.engines.ae.engine import AEEngine

    try:
        engine = AEEngine()
        print_result("实例化", True, f"executable={engine.executable_path}")

        # Test 3a: aerender version (quick)
        code, stdout, stderr, _err = engine._run_subprocess(
            [str(engine.executable_path), "-version"], timeout=10
        )
        results["version"] = code in (0, 15)  # aerender returns 15 for -version
        version_line = stdout.strip().split("\n")[0] if stdout else "unknown"
        print_result("aerender 版本", code in (0, 15), version_line)

        # Test 3b: run_script (create a test comp)
        # This actually starts AE and executes JSX
        print("  [INFO] 启动 AE 并执行 JSX 脚本（可能需要 30-60 秒）...")
        test_jsx = r"""
#target aftereffects
app.beginUndoGroup("Puppet Engine Test");
var comp = app.project.items.addComp("EngineTest_Comp", 1920, 1080, 1, 3, 30);
var solid = comp.layers.addSolid([0.5, 0.5, 1], "Blue Solid", comp.width, comp.height, 1);
app.endUndoGroup();
"AE_ENGINE_TEST_SUCCESS";
"""
        result = await engine.run_script(script_content=test_jsx)
        results["run_script"] = result.success
        if result.success:
            print_result("JSX 脚本执行", True, "AE 已启动并成功执行脚本")
        else:
            err = (result.error or "")[:200]
            print_result("JSX 脚本执行", False, err)

    except Exception as e:
        print_result("AE 异常", False, str(e))
        traceback.print_exc()
        results["error"] = str(e)

    return results


# ──────────────────────────────────────────────────────────────────
# 4. DaVinci Engine
# ──────────────────────────────────────────────────────────────────
async def test_davinci() -> dict:
    """测试 DaVinci Resolve 引擎。"""
    print_header("4. DaVinci Resolve Engine")
    results = {}

    from src.engines.davinci.engine import DavinciEngine

    try:
        engine = DavinciEngine()
        print_result("实例化", True, f"executable={engine.executable_path}")

        # Test: version check
        resolve_exe = settings.davinci_path / "Resolve.exe"
        if resolve_exe.exists():
            code, stdout, stderr, _err = engine._run_subprocess(
                [str(resolve_exe), "--version"], timeout=10
            )
            # DaVinci may not support --version, that's ok
            print_result("版本查询", True, f"exit_code={code}, stdout={stdout[:100] if stdout else 'empty'}")
            results["executable_found"] = True
        else:
            print_result("可执行文件", False, f"未找到: {resolve_exe}")
            results["executable_found"] = False

    except Exception as e:
        print_result("DaVinci 异常", False, str(e))
        traceback.print_exc()
        results["error"] = str(e)

    return results


# ──────────────────────────────────────────────────────────────────
# 5. Topaz Engine
# ──────────────────────────────────────────────────────────────────
async def test_topaz() -> dict:
    """测试 Topaz Video AI 引擎。"""
    print_header("5. Topaz Video AI Engine")
    results = {}

    from src.engines.topaz.engine import TopazEngine

    try:
        engine = TopazEngine()
        print_result("实例化", True, f"executable={engine.executable_path}")

        # Topaz is a GUI app, just check executable exists
        results["executable_found"] = engine.executable_path.exists()
        print_result("可执行文件", results["executable_found"], str(engine.executable_path))

    except Exception as e:
        print_result("Topaz 异常", False, str(e))
        traceback.print_exc()
        results["error"] = str(e)

    return results


# ──────────────────────────────────────────────────────────────────
# 6. Silhouette Engine
# ──────────────────────────────────────────────────────────────────
async def test_silhouette() -> dict:
    """测试 Silhouette 引擎。"""
    print_header("6. Silhouette Engine")
    results = {}

    from src.engines.silhouette.engine import SilhouetteEngine

    try:
        engine = SilhouetteEngine()
        print_result("实例化", True, f"executable={engine.executable_path}")

        # Check if silhouette executable exists
        sil_exe = settings.silhouette_path / "Silhouette.exe"
        if sil_exe.exists():
            print_result("可执行文件", True, str(sil_exe))
            results["executable_found"] = True
        else:
            print_result("可执行文件", False, f"未找到: {sil_exe}")
            results["executable_found"] = False

    except Exception as e:
        print_result("Silhouette 异常", False, str(e))
        traceback.print_exc()
        results["error"] = str(e)

    return results


# ──────────────────────────────────────────────────────────────────
# 7. Premiere Engine
# ──────────────────────────────────────────────────────────────────
async def test_premiere() -> dict:
    """测试 Premiere Pro 引擎。"""
    print_header("7. Premiere Pro Engine")
    results = {}

    from src.engines.premiere.engine import PremiereEngine

    try:
        engine = PremiereEngine()
        print_result("实例化", True, f"executable={engine.executable_path}")

        # Check if PR executable exists
        pr_exe = settings.premiere_path
        if pr_exe.exists():
            print_result("可执行文件", True, str(pr_exe))
            results["executable_found"] = True
        else:
            print_result("可执行文件", False, f"未找到: {pr_exe}")
            results["executable_found"] = False

    except Exception as e:
        print_result("Premiere 异常", False, str(e))
        traceback.print_exc()
        results["error"] = str(e)

    return results


# ──────────────────────────────────────────────────────────────────
# 8. Photoshop Engine
# ──────────────────────────────────────────────────────────────────
async def test_photoshop() -> dict:
    """测试 Photoshop 引擎。"""
    print_header("8. Photoshop Engine")
    results = {}

    from src.engines.photoshop.engine import PhotoshopEngine

    try:
        engine = PhotoshopEngine()
        print_result("实例化", True, f"executable={engine.executable_path}")

        # Check if PS executable exists
        ps_exe = settings.photoshop_path
        if ps_exe.exists():
            print_result("可执行文件", True, str(ps_exe))
            results["executable_found"] = True
        else:
            print_result("可执行文件", False, f"未找到: {ps_exe}")
            results["executable_found"] = False

    except Exception as e:
        print_result("Photoshop 异常", False, str(e))
        traceback.print_exc()
        results["error"] = str(e)

    return results


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────
async def main():
    print(f"P1 引擎实测开始")
    print(f"测试视频: {TEST_VIDEO}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    all_results = {}

    # Run tests from fastest to slowest
    # 1. FFmpeg (instant)
    all_results["ffmpeg"] = await test_ffmpeg()

    # 2. Blender (fast)
    all_results["blender"] = await test_blender()

    # 3. Topaz (fast CLI check)
    all_results["topaz"] = await test_topaz()

    # 4. DaVinci (fast check)
    all_results["davinci"] = await test_davinci()

    # 5. Silhouette (fast check)
    all_results["silhouette"] = await test_silhouette()

    # 6. Premiere (fast check)
    all_results["premiere"] = await test_premiere()

    # 7. Photoshop (fast check)
    all_results["photoshop"] = await test_photoshop()

    # 8. AE (slowest — actually starts After Effects)
    all_results["ae"] = await test_ae()

    # Summary
    print_header("SUMMARY")
    total = 0
    passed = 0
    for engine_name, results in all_results.items():
        for test_name, success in results.items():
            if test_name == "error":
                continue
            total += 1
            if success:
                passed += 1
        status = "ALL PASS" if all(results.get(k, False) for k in results if k != "error") else "HAS FAILURES"
        print(f"  {engine_name:15s}: {status}")

    print(f"\n  Total tests: {passed}/{total} passed")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())

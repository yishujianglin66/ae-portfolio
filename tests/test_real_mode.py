"""Adobe 全家桶真实模式集成测试

测试 PS/PR/ME 在真实环境下的功能：
1. Photoshop: 生成木质纹理
2. Premiere Pro: 时间线组装
3. Media Encoder: 批量渲染
4. Pipeline 集成验证
"""

import os
import sys
import time
import json
import tempfile
import subprocess
from pathlib import Path

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def create_test_video(output_path: str, duration: int = 3) -> bool:
    """使用 ffmpeg 创建测试视频"""
    ffmpeg = r"D:\app\FormatFactory\ffmpeg.exe"
    if not Path(ffmpeg).exists():
        print(f"[ERROR] ffmpeg 不存在: {ffmpeg}")
        return False

    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size=640x480:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    print(f"[ffmpeg] 创建测试视频: {output_path}")
    result = subprocess.run(cmd, capture_output=True, timeout=30)

    if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
        print(f"[ffmpeg] 测试视频创建成功: {Path(output_path).stat().st_size} bytes")
        return True
    else:
        print(f"[ffmpeg] 测试视频创建失败")
        if result.stderr:
            print(f"  stderr: {result.stderr.decode('gbk', errors='ignore')[:300]}")
        return False


def test_photoshop_real():
    """测试 Photoshop 真实模式 - 生成木质纹理"""
    print("\n" + "=" * 60)
    print("[测试 1] Photoshop 真实模式 - 生成木质纹理")
    print("=" * 60)

    from adobe_suite_integration import PhotoshopIntegrator, PhotoshopConfig

    ps = PhotoshopIntegrator(PhotoshopConfig(mode="real"))

    if not ps.is_available():
        print("  ✗ Photoshop 不可用")
        return False

    print(f"  PS 路径: {ps._exe_path}")

    output_dir = PROJECT_ROOT / "output" / "ps_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 测试生成木质纹理
    output_path = str(output_dir / "wood_texture.png")

    def progress_cb(progress, msg):
        print(f"  [{progress*100:.0f}%] {msg}")

    result = ps.generate_texture(
        material_type="wood",
        size=(1024, 1024),
        output_path=output_path,
        callback=progress_cb,
    )

    if result.success:
        print(f"\n  ✓ 纹理生成成功!")
        print(f"    材质: {result.material_type}")
        print(f"    模式: {result.mode}")
        print(f"    耗时: {result.duration:.2f}s")
        print(f"    输出: {result.output_files}")

        # 验证输出文件
        for f in result.output_files:
            if Path(f).exists():
                size = Path(f).stat().st_size
                print(f"    文件大小: {size} bytes")
            else:
                print(f"    ⚠ 文件不存在: {f}")
        return True
    else:
        print(f"\n  ✗ 纹理生成失败: {result.error}")
        print(f"    模式: {result.mode}")
        return False


def test_premiere_real():
    """测试 Premiere Pro 真实模式 - 时间线组装"""
    print("\n" + "=" * 60)
    print("[测试 2] Premiere Pro 真实模式 - 时间线组装")
    print("=" * 60)

    from adobe_suite_integration import PremiereIntegrator, PremiereConfig

    pr = PremiereIntegrator(PremiereConfig(mode="real"))

    if not pr.is_available():
        print("  ✗ Premiere Pro 不可用")
        return False

    print(f"  PR 路径: {pr._exe_path}")

    # 创建测试视频
    test_dir = PROJECT_ROOT / "output" / "pr_test"
    test_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    for i in range(3):
        clip_path = str(test_dir / f"clip_{i}.mp4")
        if create_test_video(clip_path, duration=3):
            clips.append(clip_path)

    if not clips:
        print("  ✗ 无法创建测试视频")
        return False

    output_project = str(test_dir / "puppet_timeline.prproj")

    def progress_cb(progress, msg):
        print(f"  [{progress*100:.0f}%] {msg}")

    result = pr.assemble_timeline(
        clips=clips,
        timeline_name="Puppet_Test_Timeline",
        transitions=True,
        transition_type="cross_dissolve",
        output_project=output_project,
        callback=progress_cb,
    )

    if result.success:
        print(f"\n  ✓ 时间线组装成功!")
        print(f"    片段数: {result.clips_assembled}")
        print(f"    转场数: {result.transitions_applied}")
        print(f"    模式: {result.mode}")
        print(f"    耗时: {result.duration:.2f}s")
        print(f"    项目: {result.output_project}")
        return True
    else:
        print(f"\n  ✗ 时间线组装失败: {result.error}")
        print(f"    模式: {result.mode}")
        return False


def test_media_encoder_real():
    """测试 Media Encoder 真实模式 - 批量渲染"""
    print("\n" + "=" * 60)
    print("[测试 3] Media Encoder 真实模式 - 批量渲染")
    print("=" * 60)

    from adobe_suite_integration import MediaEncoderIntegrator, MediaEncoderConfig

    me = MediaEncoderIntegrator(MediaEncoderConfig(mode="real"))

    if not me.is_available():
        print("  ✗ Media Encoder 不可用")
        return False

    print(f"  ME 路径: {me._exe_path}")

    # 使用之前创建的测试视频
    test_dir = PROJECT_ROOT / "output" / "pr_test"
    input_files = [str(f) for f in test_dir.glob("clip_*.mp4")]

    if not input_files:
        # 创建新的测试视频
        me_test_dir = PROJECT_ROOT / "output" / "me_test"
        me_test_dir.mkdir(parents=True, exist_ok=True)
        input_files = []
        for i in range(2):
            clip_path = str(me_test_dir / f"input_{i}.mp4")
            if create_test_video(clip_path, duration=2):
                input_files.append(clip_path)

    if not input_files:
        print("  ✗ 无可用测试视频")
        return False

    output_dir = str(PROJECT_ROOT / "output" / "me_test" / "rendered")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    def progress_cb(progress, msg):
        print(f"  [{progress*100:.0f}%] {msg}")

    result = me.batch_render(
        input_files=input_files,
        output_dir=output_dir,
        format_preset="mp4_h264",
        callback=progress_cb,
    )

    if result.success:
        print(f"\n  ✓ 批量渲染成功!")
        print(f"    处理文件数: {result.files_processed}")
        print(f"    模式: {result.mode}")
        print(f"    耗时: {result.total_duration:.2f}s")
        for f in result.output_files:
            if Path(f).exists():
                print(f"    输出: {f} ({Path(f).stat().st_size} bytes)")
        return True
    else:
        print(f"\n  ✗ 批量渲染失败: {result.error}")
        print(f"    模式: {result.mode}")
        return False


def test_pipeline_integration():
    """测试 Pipeline 中 AdobeSuiteIntegrator 集成"""
    print("\n" + "=" * 60)
    print("[测试 4] Pipeline 集成验证")
    print("=" * 60)

    try:
        from adobe_suite_integration import AdobeSuiteIntegrator

        suite = AdobeSuiteIntegrator(mode="auto")

        # 检查可用性
        availability = suite.is_available()
        print(f"  软件可用性: {availability}")

        all_available = all(availability.values())
        if all_available:
            print("  ✓ PS/PR/ME 全部可用")
        else:
            unavailable = [k for k, v in availability.items() if not v]
            print(f"  ⚠ 不可用: {unavailable}")

        # 测试统一入口 - 生成木偶材质包（simulate 模式，快速验证）
        print("\n  测试 generate_puppet_textures (simulate)...")
        textures = suite.generate_puppet_textures(
            materials=["wood", "ceramic"],
            output_dir=str(PROJECT_ROOT / "output" / "suite_test"),
            callback=lambda p, m: print(f"    [{p*100:.0f}%] {m}") if p % 0.5 < 0.01 else None,
        )

        success_count = sum(1 for r in textures.values() if r.success)
        print(f"  ✓ 材质包生成: {success_count}/{len(textures)} 成功")

        # 测试批量导出接口
        print("\n  测试 batch_export 接口...")
        test_dir = PROJECT_ROOT / "output" / "pr_test"
        input_files = [str(f) for f in test_dir.glob("clip_*.mp4")]

        if input_files:
            export_result = suite.batch_export(
                input_files=input_files[:2],
                output_dir=str(PROJECT_ROOT / "output" / "suite_export"),
                format_preset="mp4_h264",
            )
            print(f"  ✓ 批量导出: {export_result.files_processed} 文件, 模式={export_result.mode}")

        return True

    except Exception as e:
        print(f"  ✗ Pipeline 集成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ae_pipeline_adobe_loading():
    """测试 AE Pipeline 是否正确加载 AdobeSuiteIntegrator"""
    print("\n" + "=" * 60)
    print("[测试 5] AE Pipeline Adobe 加载验证")
    print("=" * 60)

    try:
        from ae_agent_pipeline import AEPipelineAgent

        pipeline = AEPipelineAgent()

        if hasattr(pipeline, 'adobe_suite') and pipeline.adobe_suite is not None:
            print("  ✓ AdobeSuiteIntegrator 已加载到 Pipeline")
            availability = pipeline.adobe_suite.is_available()
            print(f"    可用性: {availability}")
            return True
        elif hasattr(pipeline, 'adobe_enabled') and pipeline.adobe_enabled:
            print("  ✓ Adobe 集成已启用")
            return True
        else:
            print("  ⚠ AdobeSuiteIntegrator 未加载到 Pipeline")
            print(f"    adobe_suite: {getattr(pipeline, 'adobe_suite', 'N/A')}")
            print(f"    adobe_enabled: {getattr(pipeline, 'adobe_enabled', 'N/A')}")
            return False

    except Exception as e:
        print(f"  ✗ Pipeline 加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("Adobe 全家桶真实模式集成测试")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"项目: {PROJECT_ROOT}")
    print("=" * 60)

    results = {}

    # 测试 1: Photoshop 真实模式
    try:
        results["photoshop"] = test_photoshop_real()
    except Exception as e:
        print(f"  ✗ Photoshop 测试异常: {e}")
        results["photoshop"] = False

    # 测试 2: Premiere Pro 真实模式
    try:
        results["premiere"] = test_premiere_real()
    except Exception as e:
        print(f"  ✗ Premiere 测试异常: {e}")
        results["premiere"] = False

    # 测试 3: Media Encoder 真实模式
    try:
        results["media_encoder"] = test_media_encoder_real()
    except Exception as e:
        print(f"  ✗ Media Encoder 测试异常: {e}")
        results["media_encoder"] = False

    # 测试 4: Pipeline 集成
    try:
        results["pipeline"] = test_pipeline_integration()
    except Exception as e:
        print(f"  ✗ Pipeline 测试异常: {e}")
        results["pipeline"] = False

    # 测试 5: AE Pipeline 加载
    try:
        results["ae_pipeline"] = test_ae_pipeline_adobe_loading()
    except Exception as e:
        print(f"  ✗ AE Pipeline 测试异常: {e}")
        results["ae_pipeline"] = False

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = 0
    total = len(results)
    for name, ok in results.items():
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"  {status}  {name}")
        if ok:
            passed += 1

    print(f"\n总计: {passed}/{total} 通过")

    # 保存结果
    report = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "passed": passed,
        "total": total,
        "results": {k: v for k, v in results.items()},
    }

    report_path = PROJECT_ROOT / "output" / "real_mode_test_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n报告已保存: {report_path}")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

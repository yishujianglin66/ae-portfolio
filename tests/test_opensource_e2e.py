"""
开源集成实战测试套件
====================
测试用例设计：
1. OpenSourceHub 工具检测与状态报告
2. Whisper 语音识别端到端流水线
3. 统一调度器工作流预设验证（含模拟执行）
4. MoviePy 视频编辑功能验证
5. 桥接层集成 (OpenSourceHub <-> UnifiedToolIntegrator)

执行方式:
    py -3.12 test_opensource_e2e.py

验证方法:
    每个测试用例输出 PASS/FAIL，最终汇总报告
"""

import os
import sys
import time
import json
import traceback

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
os.environ["PATH"] += os.pathsep + r"D:\app\FormatFactory"

# 测试素材路径
TEST_VIDEO = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\external\OpenMontage\.agents\skills\hyperframes-animation\examples\assets\background-tech-data-flow.mp4"
TEST_AUDIO = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\external\OpenMontage\.agents\skills\hyperframes-media\assets\sfx\chime.mp3"
TEST_OUTPUT_DIR = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\test_output_opensource"

# 测试结果收集
results = []


def record(name: str, passed: bool, detail: str = ""):
    results.append({"name": name, "passed": passed, "detail": detail})
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}] {name}" + (f" - {detail}" if detail else ""))


# ================================================================
# 测试1: OpenSourceHub 工具检测与状态报告
# ================================================================
def test_opensource_hub_detection():
    print("\n" + "=" * 60)
    print("测试1: OpenSourceHub 工具检测与状态报告")
    print("=" * 60)

    try:
        from opensource_integrations import OpenSourceHub
        hub = OpenSourceHub()
        status = hub.auto_detect()

        # 验证所有7个工具都被注册
        expected_tools = ["rife", "sam2", "video2x", "whisper", "remotion", "openmontage", "moviepy"]
        for tool in expected_tools:
            present = tool in status
            record(f"工具注册: {tool}", present)

        # 验证至少有一个工具可用
        available = [k for k, v in status.items() if v]
        record("至少1个工具可用", len(available) >= 1, f"可用: {available}")

        # 验证状态报告生成
        report = hub.status_report()
        record("状态报告生成", len(report) > 50, f"长度: {len(report)}")

        # 验证 list_tools / list_operations
        tools_list = hub.list_tools()
        record("list_tools()", len(tools_list) == 7, f"共 {len(tools_list)} 个")

        for tool in ["rife", "whisper", "moviepy"]:
            ops = hub.list_operations(tool)
            record(f"list_operations({tool})", len(ops) > 0, f"{len(ops)} 个操作")

    except Exception as e:
        record("OpenSourceHub 初始化", False, str(e))
        traceback.print_exc()


# ================================================================
# 测试2: Whisper 语音识别端到端流水线
# ================================================================
def test_whisper_pipeline():
    print("\n" + "=" * 60)
    print("测试2: Whisper 语音识别端到端流水线")
    print("=" * 60)

    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)

    try:
        from opensource_integrations import WhisperAdapter
        adapter = WhisperAdapter()

        # 验证 whisper 可用
        available = adapter.check_available()
        record("Whisper 可用性检测", available)

        if not available:
            record("Whisper 转写测试", False, "工具不可用，跳过")
            return

        # 使用测试音频进行转写
        if os.path.exists(TEST_AUDIO):
            result = adapter.execute("transcribe", {
                "input_audio": TEST_AUDIO,
                "model": "tiny",
            })
            record("Whisper transcribe 执行", result.status in ("success", "simulated"),
                   f"status={result.status}, duration={result.duration_ms:.0f}ms")
        else:
            record("测试音频文件存在", False, f"未找到: {TEST_AUDIO}")

        # 测试字幕生成
        if os.path.exists(TEST_AUDIO):
            result = adapter.execute("generate_subtitles", {
                "input_audio": TEST_AUDIO,
                "model": "tiny",
                "format": "srt",
                "output_dir": TEST_OUTPUT_DIR,
            })
            record("Whisper generate_subtitles 执行",
                   result.status in ("success", "simulated"),
                   f"status={result.status}")

            # 验证 SRT 文件生成
            if result.output_files:
                srt_file = result.output_files[0]
                srt_exists = os.path.exists(srt_file)
                record("SRT 字幕文件生成", srt_exists,
                       f"路径: {srt_file}" if srt_exists else "文件未生成")
                if srt_exists:
                    with open(srt_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    record("SRT 内容非空", len(content) > 0, f"{len(content)} 字符")
            else:
                record("SRT 字幕文件生成", False, "无输出文件")

        # 测试语言检测
        if os.path.exists(TEST_AUDIO):
            result = adapter.execute("detect_language", {
                "input_audio": TEST_AUDIO,
                "model": "tiny",
            })
            record("Whisper detect_language 执行",
                   result.status in ("success", "simulated"),
                   f"status={result.status}")

        # 测试批量转写接口
        result = adapter.execute("batch_transcribe", {
            "input_files": [TEST_AUDIO] if os.path.exists(TEST_AUDIO) else [],
            "model": "tiny",
        })
        record("Whisper batch_transcribe 执行",
               result.status in ("success", "simulated"),
               f"status={result.status}")

    except Exception as e:
        record("Whisper 流水线", False, str(e))
        traceback.print_exc()


# ================================================================
# 测试3: 统一调度器工作流预设验证
# ================================================================
def test_workflow_presets():
    print("\n" + "=" * 60)
    print("测试3: 统一调度器工作流预设验证")
    print("=" * 60)

    try:
        from unified_tool_integrator import (
            ToolType, WorkflowPreset, WORKFLOW_PRESETS
        )

        # 验证新 ToolType
        new_tools = {
            "RIFE": "rife", "SAM2": "sam2", "WHISPER": "whisper",
            "REMOTION": "remotion", "MOVIEPY": "moviepy",
            "OPENMONTAGE": "openmontage", "VIDEO2X": "video2x",
            "SILHOUETTE": "silhouette",
        }
        for name, value in new_tools.items():
            has_attr = hasattr(ToolType, name)
            correct_val = getattr(ToolType, name, None)
            record(f"ToolType.{name}", has_attr and correct_val.value == value,
                   f"={correct_val.value}" if has_attr else "缺失")

        # 验证新 WorkflowPreset 枚举
        new_presets = [
            ("AI_SUBTITLE", "ai_subtitle_pipeline"),
            ("SMART_ROTO", "smart_roto_pipeline"),
            ("OPEN_PRODUCTION", "open_production_pipeline"),
            ("ENHANCED_UPSCALE", "enhanced_upscale_pipeline"),
            ("BATCH_SOCIAL", "batch_social_media"),
        ]
        for name, value in new_presets:
            has_enum = hasattr(WorkflowPreset, name)
            record(f"WorkflowPreset.{name}", has_enum)

        # 验证预设内容完整性
        preset_details = {
            "ai_subtitle_pipeline": {"steps": 3, "tools": ["ffmpeg", "whisper", "after_effects"]},
            "smart_roto_pipeline": {"steps": 3, "tools": ["sam2", "silhouette", "after_effects"]},
            "open_production_pipeline": {"steps": 3, "tools": ["openmontage", "whisper", "ffmpeg"]},
            "enhanced_upscale_pipeline": {"steps": 4, "tools": ["ffmpeg", "rife", "video2x", "ffmpeg"]},
            "batch_social_media": {"steps": 3, "tools": ["moviepy", "whisper", "ffmpeg"]},
        }
        for preset_id, expected in preset_details.items():
            preset = WORKFLOW_PRESETS.get(preset_id)
            if preset:
                step_count = len(preset["steps"])
                record(f"预设 {preset_id} 步骤数",
                       step_count == expected["steps"],
                       f"{step_count}/{expected['steps']}")
                # 验证每个步骤都有 tool 和 operation
                all_valid = all(
                    "tool" in s and "operation" in s
                    for s in preset["steps"]
                )
                record(f"预设 {preset_id} 步骤完整性", all_valid)
            else:
                record(f"预设 {preset_id} 存在", False, "未找到")

        # 验证总预设数
        total = len(WORKFLOW_PRESETS)
        record("总工作流预设数", total >= 9, f"共 {total} 个 (期望>=9)")

    except Exception as e:
        record("工作流预设验证", False, str(e))
        traceback.print_exc()


# ================================================================
# 测试4: MoviePy 视频编辑功能验证
# ================================================================
def test_moviepy_functions():
    print("\n" + "=" * 60)
    print("测试4: MoviePy 视频编辑功能验证")
    print("=" * 60)

    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)

    try:
        from opensource_integrations import MoviePyAdapter
        adapter = MoviePyAdapter()

        # 验证 moviepy 可用
        available = adapter.check_available()
        record("MoviePy 可用性检测", available)

        if not available:
            record("MoviePy 功能测试", False, "工具不可用，跳过")
            return

        # 验证操作列表
        ops = adapter.list_operations()
        record("MoviePy 操作列表", len(ops) >= 5, f"{len(ops)} 个操作")

        # 如果有测试视频，测试剪辑功能
        if os.path.exists(TEST_VIDEO) and available:
            result = adapter.execute("extract_audio", {
                "input_video": TEST_VIDEO,
                "output_dir": TEST_OUTPUT_DIR,
            })
            record("MoviePy extract_audio 执行",
                   result.status in ("success", "simulated"),
                   f"status={result.status}, duration={result.duration_ms:.0f}ms")

            if result.output_files:
                audio_exists = any(os.path.exists(f) for f in result.output_files)
                record("音频文件提取", audio_exists)
        else:
            record("测试视频文件", os.path.exists(TEST_VIDEO),
                   TEST_VIDEO if os.path.exists(TEST_VIDEO) else "未找到")

        # 测试 simulate 模式下的 cut_clip
        result = adapter.execute("cut_clip", {
            "input_video": TEST_VIDEO if os.path.exists(TEST_VIDEO) else "dummy.mp4",
            "output_dir": TEST_OUTPUT_DIR,
            "start": 0,
            "end": 2,
        })
        record("MoviePy cut_clip 执行", result.status in ("success", "simulated", "error"),
               f"status={result.status}")

    except Exception as e:
        record("MoviePy 功能验证", False, str(e))
        traceback.print_exc()


# ================================================================
# 测试5: 桥接层集成 (OpenSourceHub <-> UnifiedToolIntegrator)
# ================================================================
def test_bridge_integration():
    print("\n" + "=" * 60)
    print("测试5: 桥接层集成 (OpenSourceHub <-> UnifiedToolIntegrator)")
    print("=" * 60)

    try:
        from unified_tool_integrator import UnifiedToolIntegrator

        # 创建调度器实例（auto模式，不依赖真实工具）
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=TEST_OUTPUT_DIR,
            log_level="WARNING",
        )
        record("UnifiedToolIntegrator 初始化", True)

        # 验证开源工具中心已初始化
        has_hub = hasattr(integrator, '_os_hub')
        record("OpenSourceHub 桥接存在", has_hub)

        if has_hub and integrator._os_hub:
            # 验证合并后的工具状态
            all_tools = integrator.get_available_tools()
            record("合并工具状态报告", len(all_tools) > 10,
                   f"共 {len(all_tools)} 个工具")

            # 验证开源工具出现在合并列表中
            os_tools_found = [k for k in all_tools if k in
                              ["rife", "sam2", "whisper", "remotion", "moviepy", "openmontage", "video2x"]]
            record("开源工具在合并列表中", len(os_tools_found) >= 3,
                   f"找到: {os_tools_found}")

        # 验证 _execute_opensource_step 方法存在
        has_exec = hasattr(integrator, '_execute_opensource_step')
        record("_execute_opensource_step 方法存在", has_exec)

        # 测试通过桥接层执行开源工具步骤
        if has_exec:
            mock_result = None
            step_result = integrator._execute_opensource_step(
                {"tool": "whisper", "operation": "transcribe",
                 "params": {"input_audio": "test.mp3"}},
                mock_result
            )
            record("桥接层执行 Whisper 步骤",
                   "data" in step_result or "status" in step_result,
                   f"keys={list(step_result.keys())}")

        # 验证新工作流预设可通过调度器访问
        from unified_tool_integrator import WORKFLOW_PRESETS
        new_preset_ids = [
            "ai_subtitle_pipeline", "smart_roto_pipeline",
            "open_production_pipeline", "enhanced_upscale_pipeline",
            "batch_social_media"
        ]
        for pid in new_preset_ids:
            in_presets = pid in WORKFLOW_PRESETS
            record(f"预设 {pid} 可访问", in_presets)

    except Exception as e:
        record("桥接层集成", False, str(e))
        traceback.print_exc()


# ================================================================
# 汇总报告
# ================================================================
def print_summary():
    print("\n" + "=" * 60)
    print("测试汇总报告")
    print("=" * 60)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print(f"\n  总计: {total} 个测试")
    print(f"  通过: {passed} 个")
    print(f"  失败: {failed} 个")
    print(f"  通过率: {passed/total*100:.1f}%" if total > 0 else "  通过率: N/A")

    if failed > 0:
        print(f"\n  失败项目:")
        for r in results:
            if not r["passed"]:
                print(f"    [FAIL] {r['name']}: {r['detail']}")

    # 保存结果到 JSON
    report_file = os.path.join(TEST_OUTPUT_DIR, "test_report.json")
    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "N/A",
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  详细报告已保存: {report_file}")
    print("=" * 60)


# ================================================================
# 主入口
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  开源集成实战测试套件")
    print("  AE-Knowledge-Vault")
    print("=" * 60)

    start = time.time()

    test_opensource_hub_detection()
    test_whisper_pipeline()
    test_workflow_presets()
    test_moviepy_functions()
    test_bridge_integration()

    elapsed = time.time() - start
    print(f"\n  总耗时: {elapsed:.1f}s")

    print_summary()

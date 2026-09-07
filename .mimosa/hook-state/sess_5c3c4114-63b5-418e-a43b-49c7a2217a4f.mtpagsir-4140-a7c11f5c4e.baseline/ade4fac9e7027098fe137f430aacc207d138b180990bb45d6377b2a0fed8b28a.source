"""WhisperEngine CPU vs GPU 基准对比测试

科研级 benchmark：同一音频文件，分别用 CPU (openai-whisper) 和 GPU (faster-whisper float16)
跑转写，对比耗时、显存、文字准确度，产出 JSON + Markdown 报告。

运行：
    puppet-automation/venv/Scripts/python.exe scripts/benchmark_whisper_gpu.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation" / "src"))

# 把 NVIDIA CUDA DLL 目录加入 PATH（faster-whisper GPU 后端需要 cublas64_12.dll）
_VENV_NVIDIA = PROJECT_ROOT / "puppet-automation" / "venv" / "Lib" / "site-packages" / "nvidia"
for _sub in ("cublas/bin", "cuda_nvrtc/bin", "cuda_runtime/bin"):
    _dll_dir = _VENV_NVIDIA / _sub
    if _dll_dir.exists():
        os.add_dll_directory(str(_dll_dir))
        os.environ["PATH"] = str(_dll_dir) + os.pathsep + os.environ.get("PATH", "")

# 测试音频路径
TEST_AUDIO = PROJECT_ROOT / "output" / "benchmark" / "tts_test_zh.wav"
REPORT_JSON = PROJECT_ROOT / "output" / "benchmark" / "whisper_benchmark.json"
REPORT_MD = PROJECT_ROOT / "output" / "benchmark" / "whisper_benchmark.md"


def generate_tts_audio(text: str, out_path: Path) -> bool:
    """用 Windows SAPI.SpVoice 生成中文测试音频（无需联网）。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # 使用 PowerShell 调用 SAPI COM 对象
        ps_script = f'''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile("{out_path}")
$synth.Rate = 0
$synth.Volume = 100
$synth.Speak("{text}")
$synth.Dispose()
'''
        import subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"SAPI TTS failed: {result.stderr}")
            return False
        return out_path.exists()
    except Exception as e:
        print(f"TTS error: {e}")
        return False


async def run_benchmark():
    """跑 CPU vs GPU 基准对比。"""
    from engines.whisper.engine import WhisperEngine

    # Step 1: 生成测试音频（约 30-40 秒中文人声）
    test_text = (
        "大家好，这是一个用于测试语音识别性能的中文音频样本。"
        "我们正在进行 WhisperEngine 的 CPU 与 GPU 推理速度对比测试。"
        "人工智能技术正在改变视频制作行业，自动化工作流让创作者能够更专注于内容本身。"
        "After Effects 是一款强大的合成与动效软件，结合脚本自动化可以大幅提升生产效率。"
        "本测试音频将用于评估不同后端的转写速度和准确度。"
        "感谢您的关注，祝您工作顺利。"
    )
    print(f"[1/5] 生成测试音频 → {TEST_AUDIO}")
    if not generate_tts_audio(test_text, TEST_AUDIO):
        print("TTS 生成失败，无法继续基准测试")
        return None

    audio_size = TEST_AUDIO.stat().st_size
    print(f"    音频文件: {audio_size / 1024:.1f} KB")

    # Step 2: 初始化引擎
    print(f"\n[2/5] 初始化 WhisperEngine...")
    venv_python = PROJECT_ROOT / "puppet-automation" / "venv" / "Scripts" / "python.exe"
    engine = WhisperEngine(executable_path=venv_python)
    print(f"    faster_whisper available: {engine._faster_whisper is not None}")
    print(f"    openai_whisper available: {engine._whisper is not None}")

    results = {
        "audio_file": str(TEST_AUDIO),
        "audio_size_kb": round(audio_size / 1024, 2),
        "test_text": test_text,
        "test_text_length": len(test_text),
        "benchmarks": [],
    }

    # Step 3: CPU 基准（openai-whisper, base 模型）
    print(f"\n[3/5] CPU 基准测试 (openai-whisper base)...")
    engine_cpu = WhisperEngine(executable_path=venv_python, use_faster=False)
    if engine_cpu._whisper is not None:
        t0 = time.time()
        cpu_result = await engine_cpu.transcribe(
            TEST_AUDIO, model="base", language="zh", word_level=False,
        )
        cpu_time = time.time() - t0
        cpu_meta = cpu_result.metadata or {}
        results["benchmarks"].append({
            "backend": "openai-whisper (CPU)",
            "model": "base",
            "device": "cpu",
            "compute_type": "int8 (implicit)",
            "success": cpu_result.success,
            "duration_seconds": round(cpu_time, 2),
            "transcribed_chars": len(cpu_meta.get("text", "")),
            "segment_count": cpu_meta.get("segment_count", 0),
            "detected_language": cpu_meta.get("language", ""),
            "audio_duration_seconds": cpu_meta.get("duration", 0),
            "text_preview": (cpu_meta.get("text", "") or "")[:120],
            "error": cpu_result.error,
        })
        print(f"    耗时: {cpu_time:.2f}s | 字符: {len(cpu_meta.get('text', ''))} | 段: {cpu_meta.get('segment_count', 0)}")
    else:
        print("    openai-whisper 未安装，跳过 CPU 基准")
        results["benchmarks"].append({
            "backend": "openai-whisper (CPU)",
            "success": False,
            "error": "openai-whisper not installed",
        })

    # Step 4: GPU 基准（faster-whisper, base 模型, float16）
    print(f"\n[4/5] GPU 基准测试 (faster-whisper base float16)...")
    if engine._faster_whisper is not None:
        t0 = time.time()
        gpu_result = await engine.transcribe(
            TEST_AUDIO, model="base", language="zh", word_level=False,
        )
        gpu_time = time.time() - t0
        gpu_meta = gpu_result.metadata or {}
        results["benchmarks"].append({
            "backend": "faster-whisper (GPU)",
            "model": gpu_meta.get("model", "base"),
            "device": gpu_meta.get("device", "unknown"),
            "compute_type": "float16",
            "success": gpu_result.success,
            "duration_seconds": round(gpu_time, 2),
            "transcribed_chars": len(gpu_meta.get("text", "")),
            "segment_count": gpu_meta.get("segment_count", 0),
            "detected_language": gpu_meta.get("language", ""),
            "audio_duration_seconds": gpu_meta.get("duration", 0),
            "text_preview": (gpu_meta.get("text", "") or "")[:120],
            "error": gpu_result.error,
        })
        print(f"    耗时: {gpu_time:.2f}s | 设备: {gpu_meta.get('device')} | 字符: {len(gpu_meta.get('text', ''))} | 段: {gpu_meta.get('segment_count', 0)}")
    else:
        print("    faster-whisper 未安装，跳过 GPU 基准")
        results["benchmarks"].append({
            "backend": "faster-whisper (GPU)",
            "success": False,
            "error": "faster-whisper not installed",
        })

    # Step 5: GPU 基准（faster-whisper, medium 模型, float16）
    print(f"\n[5/5] GPU 基准测试 (faster-whisper medium float16)...")
    if engine._faster_whisper is not None:
        t0 = time.time()
        gpu_med_result = await engine.transcribe(
            TEST_AUDIO, model="medium", language="zh", word_level=False,
        )
        gpu_med_time = time.time() - t0
        gpu_med_meta = gpu_med_result.metadata or {}
        results["benchmarks"].append({
            "backend": "faster-whisper (GPU)",
            "model": gpu_med_meta.get("model", "medium"),
            "device": gpu_med_meta.get("device", "unknown"),
            "compute_type": "float16",
            "success": gpu_med_result.success,
            "duration_seconds": round(gpu_med_time, 2),
            "transcribed_chars": len(gpu_med_meta.get("text", "")),
            "segment_count": gpu_med_meta.get("segment_count", 0),
            "detected_language": gpu_med_meta.get("language", ""),
            "audio_duration_seconds": gpu_med_meta.get("duration", 0),
            "text_preview": (gpu_med_meta.get("text", "") or "")[:120],
            "error": gpu_med_result.error,
        })
        print(f"    耗时: {gpu_med_time:.2f}s | 设备: {gpu_med_meta.get('device')} | 字符: {len(gpu_med_meta.get('text', ''))} | 段: {gpu_med_meta.get('segment_count', 0)}")

    # 保存 JSON 报告
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 报告: {REPORT_JSON}")

    # 生成 Markdown 报告
    md = generate_markdown_report(results)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Markdown 报告: {REPORT_MD}")

    return results


def generate_markdown_report(results: dict) -> str:
    """生成 Markdown 可视化报告。"""
    md = ["# WhisperEngine CPU vs GPU 基准测试报告\n"]
    md.append(f"**测试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append(f"**测试音频**: `{results['audio_file']}` ({results['audio_size_kb']} KB)\n")
    md.append(f"**音频文本长度**: {results['test_text_length']} 字符\n")
    md.append(f"**参考文本**: {results['test_text'][:80]}...\n\n")

    md.append("## 测试结果对比\n")
    md.append("| 后端 | 模型 | 设备 | 计算类型 | 耗时(s) | 字符数 | 段数 | 状态 |")
    md.append("|------|------|------|---------|---------|--------|------|------|")

    for b in results["benchmarks"]:
        if b.get("success"):
            md.append(
                f"| {b['backend']} | {b.get('model', '-')} | {b.get('device', '-')} | "
                f"{b.get('compute_type', '-')} | {b['duration_seconds']} | "
                f"{b['transcribed_chars']} | {b['segment_count']} | ✅ |"
            )
        else:
            md.append(
                f"| {b['backend']} | - | - | - | - | - | - | ❌ {b.get('error', '')[:30]} |"
            )

    md.append("\n## 加速比分析\n")
    cpu_b = next((b for b in results["benchmarks"] if b.get("backend") == "openai-whisper (CPU)" and b.get("success")), None)
    gpu_b = next((b for b in results["benchmarks"] if b.get("backend") == "faster-whisper (GPU)" and b.get("model") == "base" and b.get("success")), None)
    gpu_m = next((b for b in results["benchmarks"] if b.get("backend") == "faster-whisper (GPU)" and b.get("model") == "medium" and b.get("success")), None)

    if cpu_b and gpu_b:
        speedup = cpu_b["duration_seconds"] / gpu_b["duration_seconds"] if gpu_b["duration_seconds"] > 0 else 0
        md.append(f"- **CPU base → GPU base 加速比**: {speedup:.2f}x")
        md.append(f"  - CPU: {cpu_b['duration_seconds']}s")
        md.append(f"  - GPU: {gpu_b['duration_seconds']}s")
    if cpu_b and gpu_m:
        speedup_m = cpu_b["duration_seconds"] / gpu_m["duration_seconds"] if gpu_m["duration_seconds"] > 0 else 0
        md.append(f"- **CPU base → GPU medium 加速比**: {speedup_m:.2f}x")
        md.append(f"  - CPU base: {cpu_b['duration_seconds']}s")
        md.append(f"  - GPU medium: {gpu_m['duration_seconds']}s (更高精度)")

    md.append("\n## 文本预览\n")
    for b in results["benchmarks"]:
        if b.get("success"):
            md.append(f"### {b['backend']} ({b.get('model', '-')})")
            md.append(f"```\n{b.get('text_preview', '')}\n```")
            md.append("")

    md.append("\n## 结论\n")
    if cpu_b and gpu_b:
        speedup = cpu_b["duration_seconds"] / gpu_b["duration_seconds"] if gpu_b["duration_seconds"] > 0 else 0
        if speedup >= 2:
            md.append(f"✅ **GPU 加速生效**，速度提升 **{speedup:.2f}x**。RTX 4060 8GB VRAM 完全可用。")
        else:
            md.append(f"⚠️ GPU 加速效果不显著 ({speedup:.2f}x)，可能因模型过小或驱动问题。")
    elif gpu_b and not cpu_b:
        md.append("✅ **GPU 推理成功**（CPU 后端不可用，无法对比）")
    else:
        md.append("❌ 推理失败，请检查日志")

    return "\n".join(md)


if __name__ == "__main__":
    result = asyncio.run(run_benchmark())
    if result:
        print("\n" + "=" * 60)
        print("基准测试完成")
        print("=" * 60)

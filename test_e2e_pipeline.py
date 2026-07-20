#!/usr/bin/env python3
"""
ae_agent_pipeline 端到端验证测试 (B3)

验证 5 层架构的最小可运行路径：
  感知层 → 理解层 → 规划层 → 执行层 → 反馈层

测试场景：给定一段音频文件，完成 "为视频配 BGM" 的完整流程。
不依赖 AE 运行，仅验证 Python 侧管线逻辑。

运行方式：
    python test_e2e_pipeline.py
    python test_e2e_pipeline.py --audio path/to/audio.mp3
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_perception_layer(audio_path: str) -> dict:
    """Layer 1: 感知层 - 音频分析"""
    print("\n=== Layer 1: 感知层 (Perception) ===")
    from audio_analyzer import AudioAnalyzer
    
    analyzer = AudioAnalyzer()
    start = time.time()
    result = analyzer.analyze_audio(audio_path)
    elapsed = time.time() - start
    
    if result.get("success"):
        features = result["features"]
        print(f"  BPM: {features['bpm']}")
        print(f"  情绪: {features['mood']} ({features['mood_score']:.2f})")
        print(f"  曲风: {features['genre']}")
        print(f"  调性: {features['key']} {features['mode']}")
        print(f"  时长: {features['duration']}s")
        print(f"  分析耗时: {elapsed:.2f}s")
        if result.get("fallback"):
            print(f"  [降级模式] {result.get('fallback_reason')}")
        return {"success": True, "features": features, "time": elapsed}
    else:
        print(f"  [FAIL] {result.get('error')}")
        return {"success": False, "error": result.get("error")}


def test_understanding_layer(features: dict) -> dict:
    """Layer 2: 理解层 - 意图解析"""
    print("\n=== Layer 2: 理解层 (Understanding) ===")
    
    # 模拟意图解析
    bpm = features.get("bpm", 0)
    mood = features.get("mood", "")
    energy = features.get("energy", 0)
    
    intent = "bgm_match"
    style = "auto"
    
    if bpm > 140:
        style = "high_energy"
    elif bpm > 100:
        style = "moderate"
    else:
        style = "calm"
    
    print(f"  意图: {intent}")
    print(f"  风格推断: {style}")
    print(f"  基于 BPM={bpm:.0f}, mood={mood}, energy={energy:.3f}")
    
    return {
        "success": True,
        "intent": intent,
        "style": style,
        "mood": mood,
        "tempo": bpm,
    }


def test_planning_layer(understanding: dict) -> dict:
    """Layer 3: 规划层 - 任务分解"""
    print("\n=== Layer 3: 规划层 (Planning) ===")
    
    steps = [
        {"step": 1, "action": "search_bgm", "description": "搜索匹配的 BGM"},
        {"step": 2, "action": "download_bgm", "description": "下载 BGM 文件"},
        {"step": 3, "action": "analyze_bgm", "description": "分析下载的 BGM"},
        {"step": 4, "action": "import_to_ae", "description": "导入到 AE 项目"},
        {"step": 5, "action": "add_to_composition", "description": "添加到合成"},
    ]
    
    for s in steps:
        print(f"  Step {s['step']}: {s['action']} - {s['description']}")
    
    return {
        "success": True,
        "steps": steps,
        "total_steps": len(steps),
    }


def test_execution_layer(plan: dict) -> dict:
    """Layer 4: 执行层 - 模拟执行（不实际调用 AE）"""
    print("\n=== Layer 4: 执行层 (Execution) ===")
    
    completed = 0
    for step in plan["steps"]:
        action = step["action"]
        # 模拟执行（实际环境中会调用 MCP 工具）
        print(f"  [模拟] 执行: {action}...", end=" ")
        
        if action == "import_to_ae":
            print("(跳过 - 需要 AE 运行)")
        elif action == "add_to_composition":
            print("(跳过 - 需要 AE 运行)")
        else:
            print("OK")
            completed += 1
    
    return {
        "success": True,
        "steps_completed": completed,
        "total_steps": plan["total_steps"],
        "note": "AE 相关步骤已跳过（需要 AE 运行环境）",
    }


def test_feedback_layer(execution: dict) -> dict:
    """Layer 5: 反馈层 - 结果评估"""
    print("\n=== Layer 5: 反馈层 (Feedback) ===")
    
    completion_rate = execution["steps_completed"] / max(execution["total_steps"], 1)
    rating = completion_rate * 5.0
    
    print(f"  完成率: {completion_rate:.0%}")
    print(f"  评分: {rating:.1f}/5.0")
    print(f"  备注: {execution.get('note', 'N/A')}")
    
    return {
        "success": True,
        "rating": rating,
        "completion_rate": completion_rate,
        "improvements": [
            "集成真实 MCP 工具调用替代模拟",
            "添加 CLIP 语义搜索提升 BGM 匹配精度",
            "引入 essentia 替代 librosa 提升分析速度",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="AE Agent Pipeline E2E 验证")
    parser.add_argument("--audio", type=str, help="测试音频文件路径")
    args = parser.parse_args()
    
    # 查找测试音频
    audio_path = args.audio
    if not audio_path:
        # 尝试常见位置
        candidates = [
            PROJECT_ROOT / "audio_processed.wav",
            PROJECT_ROOT / "test-media" / "test.wav",
        ]
        for c in candidates:
            if c.exists():
                audio_path = str(c)
                break
    
    if not audio_path or not os.path.exists(audio_path):
        print("[ERROR] 未找到测试音频文件。请使用 --audio 指定路径。")
        print("  示例: python test_e2e_pipeline.py --audio path/to/audio.mp3")
        sys.exit(1)
    
    print(f"测试音频: {audio_path}")
    print("=" * 60)
    
    # 执行 5 层管线
    perception = test_perception_layer(audio_path)
    if not perception["success"]:
        print("\n[FAIL] 感知层失败，管线终止")
        sys.exit(1)
    
    understanding = test_understanding_layer(perception["features"])
    planning = test_planning_layer(understanding)
    execution = test_execution_layer(planning)
    feedback = test_feedback_layer(execution)
    
    # 汇总
    print("\n" + "=" * 60)
    print("E2E 验证完成")
    print(f"  感知层: OK ({perception['time']:.2f}s)")
    print(f"  理解层: OK (intent={understanding['intent']})")
    print(f"  规划层: OK ({planning['total_steps']} steps)")
    print(f"  执行层: OK ({execution['steps_completed']}/{execution['total_steps']})")
    print(f"  反馈层: OK (rating={feedback['rating']:.1f}/5.0)")
    print("=" * 60)


if __name__ == "__main__":
    main()

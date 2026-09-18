#!/usr/bin/env python3
"""
端到端集成测试：验证 Silhouette + AE 混合任务的完整数据流。

测试场景：用户输入 "扣掉埼玉然后加发光"
预期流程：
  understand() → 识别为 hybrid 任务 (silhouette_task=roto, is_hybrid=True)
  plan()       → 生成 silhouette_operations + AE effects
  execute()    → 先执行 Silhouette roto，再执行 AE 效果

使用真实视频素材 D:/AE-Work/视频素材库/抖音_一拳超人_埼玉.mp4
mock SilhouetteExecutor 和 AECommandClient 以验证命令传递。
"""
import json
import logging
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VIDEO_PATH = r"D:\AE-Work\视频素材库\抖音_一拳超人_埼玉.mp4"
AUDIO_PATH = r"D:\AE-Work\音频素材库\BGM\抖音_BGM_世上无难事.mp3"


def main():
    print("=" * 70)
    print("端到端集成测试: Silhouette + AE 混合任务")
    print("=" * 70)

    # 检查素材
    print("\n[0] 检查测试素材...")
    if not os.path.exists(VIDEO_PATH):
        print(f"  [SKIP] 视频素材不存在: {VIDEO_PATH}")
        return 1
    if not os.path.exists(AUDIO_PATH):
        print(f"  [SKIP] 音频素材不存在: {AUDIO_PATH}")
        return 1
    print(f"  ✓ 视频: {VIDEO_PATH}")
    print(f"  ✓ 音频: {AUDIO_PATH}")

    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult, UnderstandingResult

    # 创建 pipeline（跳过重量级初始化）
    pipe = AEAgentPipeline.__new__(AEAgentPipeline)
    pipe._config = {"output": {"default_dir": r"D:\AE-Work\输出"}}
    pipe.silhouette_executor = None
    pipe._state_machine = None
    pipe._event_bus = None
    pipe._publish_pipeline_event = lambda *args, **kwargs: None
    pipe._observability = None
    pipe._orchestrator = None
    pipe._llm_gateway = None
    pipe._memory_store = None
    pipe._logger = logging.getLogger("test")

    passed = 0
    failed = 0

    # ------------------------------------------------------------------
    # Step 1: understand() - 识别混合任务
    # ------------------------------------------------------------------
    print("\n[Step 1] understand() - 识别混合任务")
    print("  输入: '扣掉埼玉然后加发光'")
    perception = PerceptionResult(
        video_analysis={"video_path": VIDEO_PATH},
        audio_analysis={"audio_path": AUDIO_PATH},
        clip_features=[{"source_path": VIDEO_PATH, "scene_analysis": {"dominant_scene_type": "character"}}],
        music_features={"mood": "epic", "mood_score": 0.8, "tempo": 120, "duration": 15.0},
    )
    understanding = pipe.understand(perception, "扣掉埼玉然后加发光")

    checks = [
        ("route_type == hybrid", understanding.route_type == "hybrid"),
        ("is_hybrid == True", understanding.is_hybrid is True),
        ("silhouette_task == roto", understanding.silhouette_task == "roto"),
        ("intent 非空", bool(understanding.intent)),
    ]
    for desc, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
        if ok:
            passed += 1
        else:
            failed += 1

    # ------------------------------------------------------------------
    # Step 2: plan() - 生成 Silhouette + AE 操作
    # ------------------------------------------------------------------
    print("\n[Step 2] plan() - 生成 Silhouette + AE 操作")
    planning = pipe.plan(understanding, perception)

    checks = [
        ("silhouette_operations 非空", len(planning.silhouette_operations) > 0),
        ("第 1 个命令 = silhouette_roto",
         planning.silhouette_operations[0].get("command") == "silhouette_roto"),
        ("source_path 指向真实视频",
         planning.silhouette_operations[0].get("params", {}).get("source_path") == VIDEO_PATH),
        ("shape_type == x-spline",
         planning.silhouette_operations[0].get("params", {}).get("shape_type") == "x-spline"),
        ("composition 非空", planning.composition is not None),
        ("layers 非空", len(planning.layers) > 0),
        ("effects 非空", len(planning.effects) > 0),
        ("execution_order 含 silhouette",
         "silhouette" in planning.execution_order or len(planning.silhouette_operations) > 0),
    ]
    for desc, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
        if ok:
            passed += 1
        else:
            failed += 1

    print("\n  Silhouette 操作详情:")
    print(f"  {json.dumps(planning.silhouette_operations, ensure_ascii=False, indent=2)}")

    # ------------------------------------------------------------------
    # Step 3: execute() - mock Silhouette + AE 执行
    # ------------------------------------------------------------------
    print("\n[Step 3] execute() - 模拟执行（mock Silhouette + AE）")

    # Mock SilhouetteExecutor
    mock_sil = MagicMock()
    mock_sil.execute.return_value = {
        "status": "success",
        "output_file": r"D:\AE-Work\silhouette_output\1.0000.exr",
        "operation": "roto",
        "shape_type": "x-spline",
    }
    pipe.silhouette_executor = mock_sil

    # Mock AE MCP Client 和 CommandGenerator
    mock_client = MagicMock()
    mock_client.send_command.return_value = {"success": True, "status": "success"}
    mock_generator = MagicMock()
    mock_generator.generate_from_planning_result.return_value = [
        {"op": "createComposition", "params": {"name": "test"}},
        {"op": "addEffect", "params": {"effectName": "glow"}},
    ]

    with patch("ae_mcp_client.AECommandClient", return_value=mock_client), \
         patch("ae_command_generator.AECommandGenerator", return_value=mock_generator):
        execution = pipe.execute(planning)

    checks = [
        ("Silhouette execute 被调用", mock_sil.execute.called),
        ("Silhouette 命令 = silhouette_roto",
         mock_sil.execute.call_args[0][0].get("command") == "silhouette_roto"),
        ("Silhouette 产出 artifacts", len(execution.silhouette_artifacts) > 0),
        ("Silhouette artifact 状态 = success",
         execution.silhouette_artifacts[0].get("status") == "success"),
        ("AE send_command 被调用", mock_client.send_command.called),
        ("AE 渲染命令被调用（最后一次）",
         mock_client.send_command.call_args_list[-1][0][0] == "renderComposition"),
    ]
    for desc, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
        if ok:
            passed += 1
        else:
            failed += 1

    # ------------------------------------------------------------------
    # Step 4: 完整数据流校验
    # ------------------------------------------------------------------
    print("\n[Step 4] 完整数据流校验")
    print("  用户输入: '扣掉埼玉然后加发光'")
    print(f"  → 路由: {understanding.route_type}")
    print(f"  → Silhouette 任务: {understanding.silhouette_task}")
    print(f"  → Silhouette 命令: {planning.silhouette_operations[0]['command']}")
    print(f"  → 源素材: {planning.silhouette_operations[0]['params']['source_path']}")
    print(f"  → Silhouette 输出: {execution.silhouette_artifacts[0].get('output_file', 'N/A')}")
    print(f"  → AE 效果数: {len(planning.effects)}")
    print(f"  → AE 命令数: {mock_generator.generate_from_planning_result.return_value.__len__()}")

    print("\n" + "=" * 70)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

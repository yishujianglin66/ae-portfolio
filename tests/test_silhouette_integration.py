#!/usr/bin/env python3
"""
Silhouette 集成测试：验证 ae_agent_pipeline.py 中的
IntentRouter 路由检测 + silhouette_operations 生成逻辑。
"""
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def make_pipeline():
    """创建 pipeline 实例（跳过重量级初始化）。"""
    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult, UnderstandingResult
    pipe = AEAgentPipeline.__new__(AEAgentPipeline)
    # 只初始化测试需要的字段
    return pipe


def test_route_detection():
    """测试路由类型检测。"""
    from ae_agent_pipeline import UnderstandingResult
    pipe = make_pipeline()

    cases = [
        # (prompt, expected_route, expected_task, expected_hybrid)
        ("加个模糊效果", "ae_only", "", False),
        ("扣个人像", "silhouette_only", "roto", False),
        ("跟踪这个物体", "silhouette_only", "track", False),
        ("修掉水印", "silhouette_only", "paint", False),
        ("扣个人像然后加发光", "hybrid", "roto", True),
        ("跟踪物体然后做文字动画", "hybrid", "track", True),
        ("修复画面然后加噪波", "hybrid", "paint", True),
        ("", "ae_only", "", False),
    ]

    for i, (prompt, exp_route, exp_task, exp_hybrid) in enumerate(cases, 1):
        u = UnderstandingResult()
        pipe._detect_silhouette_intent(u, prompt)
        assert u.route_type == exp_route, (
            f"Case {i} '{prompt}': route={u.route_type!r}, exp={exp_route!r}"
        )
        assert u.silhouette_task == exp_task, (
            f"Case {i} '{prompt}': task={u.silhouette_task!r}, exp={exp_task!r}"
        )
        assert u.is_hybrid == exp_hybrid, (
            f"Case {i} '{prompt}': hybrid={u.is_hybrid}, exp={exp_hybrid}"
        )


def test_operation_generation():
    """测试 silhouette_operations 生成。"""
    from ae_agent_pipeline import PerceptionResult, UnderstandingResult
    pipe = make_pipeline()

    # 模拟 perception 含一个视频片段
    perception = PerceptionResult(
        clip_features=[{"source_path": "D:/AE-Work/test.mp4"}]
    )

    cases = [
        ("roto", "silhouette_roto", {"shape_type", "tolerance", "output_format"}),
        ("track", "silhouette_track", {"track_type", "export_format", "search_area"}),
        ("paint", "silhouette_paint", {"brush_size", "brush_hardness", "mode"}),
        ("", "", set()),  # 无任务 → 空列表
    ]

    for i, (task, exp_cmd, required_keys) in enumerate(cases, 1):
        u = UnderstandingResult(silhouette_task=task)
        ops = pipe._generate_silhouette_operations(u, perception)

        if not task:
            assert len(ops) == 0, f"Case {i}: task='' 应无操作，实际 {len(ops)}"
            continue

        assert len(ops) == 1, f"Case {i}: task='{task}' 应 1 个操作，实际 {len(ops)}"
        op = ops[0]
        assert op["command"] == exp_cmd, (
            f"Case {i}: cmd={op['command']!r}, exp={exp_cmd!r}"
        )
        params = op.get("params", {})
        assert required_keys.issubset(set(params.keys())), (
            f"Case {i}: 缺少参数，需要 {required_keys}，实际 {set(params.keys())}"
        )
        assert params.get("source_path") == "D:/AE-Work/test.mp4", (
            f"Case {i}: source_path 不匹配"
        )


def main():
    print("=" * 60)
    print("Silhouette 集成测试 (ae_agent_pipeline.py)")
    print("=" * 60)

    print("\n[Test 1] 路由类型检测")
    try:
        test_route_detection()
        p1, f1 = 1, 0
        print("  PASSED")
    except AssertionError as e:
        p1, f1 = 0, 1
        print(f"  FAILED: {e}")

    print("\n[Test 2] silhouette_operations 生成")
    try:
        test_operation_generation()
        p2, f2 = 1, 0
        print("  PASSED")
    except AssertionError as e:
        p2, f2 = 0, 1
        print(f"  FAILED: {e}")

    total_p = p1 + p2
    total_f = f1 + f2
    print("\n" + "=" * 60)
    print(f"测试结果: {total_p} 通过, {total_f} 失败")
    print("=" * 60)
    sys.exit(0 if total_f == 0 else 1)


if __name__ == "__main__":
    main()

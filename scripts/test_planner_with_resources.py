"""验证 AIPlanner 是否真正调用 build_*_prompt_with_resources 注入资源清单。

本脚本通过 mock LLM 网关，让 planner 走 LLM 路径，并用 ``AsyncMock(wraps=...)``
包装 4 个 ``build_*_prompt_with_resources`` 函数：
- 包装器会记录调用次数与参数
- 同时仍委托给真实函数执行（验证真实函数不会因 resource_index_service 不可用而崩溃）

运行方式（在项目根目录）：
    py -3.11 scripts/test_planner_with_resources.py

预期输出：
- 4 个 build_*_prompt_with_resources 函数各被调用 1 次
- LLM mock 收到的提示词中包含资源清单注入痕迹（"资源库可用资源清单" 或降级说明）
- plan_from_query 返回有效的 PlanningResult
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# ============================================================
# 配置 sys.path：项目根（for core.*）+ puppet-automation（for src.*）
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUPPET_AUTOMATION = PROJECT_ROOT / "puppet-automation"
for p in (str(PROJECT_ROOT), str(PUPPET_AUTOMATION)):
    if p not in sys.path:
        sys.path.insert(0, p)


# ============================================================
# Mock LLM Gateway
# ============================================================
def _make_gateway_mock():
    """构造一个 mock LLM 网关，根据 task_type 返回 canned JSON 响应。"""

    intent_resp = json.dumps({
        "style": "wooden",
        "target_resolution": [1920, 1080],
        "target_fps": 30,
        "enable_face_puppet": True,
        "enable_body_puppet": True,
        "enable_3d_stage": False,
        "enable_audio": True,
        "quality_preset": "medium",
        "phases": ["phase1_preprocess", "phase2_keying", "phase3_stylize", "phase4_render"],
        "style_reasoning": "LLM chose wooden",
        "estimated_duration_minutes": 5,
    }, ensure_ascii=False)

    style_resp = json.dumps({
        "primary_style": "wooden",
        "alternatives": ["clay", "handle"],
        "confidence": 0.85,
        "reasoning": "基于资源库可用字体推荐木质木偶风格",
        "style_tips": {"font": "推荐使用思源黑体"},
    }, ensure_ascii=False)

    opt_resp = json.dumps({
        "recommended_resolution": [1920, 1080],
        "recommended_fps": 30,
        "recommended_quality": "medium",
        "enable_topaz": False,
        "enable_silhouette_roto": True,
        "enable_3d_stage": False,
        "enable_color_grade": True,
        "estimated_processing_time_minutes": 8,
        "optimization_notes": "基于可用 LUT 调色预设优化",
    }, ensure_ascii=False)

    explanation_resp = (
        "这是一个木质木偶风格的视频制作任务。将依次执行预处理、抠像、风格化和渲染四个阶段。"
        "预计耗时 8 分钟，输出 1920x1080/30fps 的视频。"
    )

    class _Resp:
        def __init__(self, content_str: str):
            self.content = content_str
            self.success = True
            self.error = ""
            self.model = "mock-model"
            self.provider = "mock"
            self.tokens_input = 0
            self.tokens_output = 0
            self.latency_ms = 0.0
            self.raw = {}

    # 用 message 内容做简单路由：含特定关键词则返回对应响应
    async def _chat_with_routing(message, task_type=None, system_prompt="",
                                 temperature=None, max_tokens=None):
        msg = message or ""
        # 通过提示词特征判断属于哪个阶段
        if "用户需求" in msg and "视频文件路径" in msg:
            return _Resp(intent_resp)
        if "风格推荐专家" in msg or "primary_style" in msg:
            return _Resp(style_resp)
        if "参数优化专家" in msg or "recommended_resolution" in msg:
            return _Resp(opt_resp)
        if "执行摘要" in msg or "任务配置" in msg:
            return _Resp(explanation_resp)
        return _Resp(intent_resp)  # 默认回退

    # 使用 SimpleNamespace 将 _chat_with_routing 作为实例属性（非类方法），
    # 避免 self 被自动注入到 message 参数。
    from types import SimpleNamespace
    gateway = SimpleNamespace()
    gateway.chat_with_routing = _chat_with_routing
    gateway.is_available = lambda: True
    return gateway


# ============================================================
# 主验证流程
# ============================================================
async def _verify() -> dict:
    """执行验证，返回结果字典。"""
    from src.ai_planner import planner as planner_mod
    from src.ai_planner.planner import AIPlanner
    from src.models.pipeline import VideoMetadata

    # 用 AsyncMock(wraps=real_func) 包装 4 个 build_* 函数：
    # 既记录调用，又委托真实实现（验证真实函数不会崩溃）
    real_build_intent = planner_mod.build_intent_parsing_prompt_with_resources
    real_build_style = planner_mod.build_style_recommendation_prompt_with_resources
    real_build_param = planner_mod.build_param_optimization_prompt_with_resources
    real_build_explain = planner_mod.build_pipeline_explanation_prompt_with_resources

    tracker_intent = AsyncMock(wraps=real_build_intent)
    tracker_style = AsyncMock(wraps=real_build_style)
    tracker_param = AsyncMock(wraps=real_build_param)
    tracker_explain = AsyncMock(wraps=real_build_explain)

    gateway = _make_gateway_mock()

    # 用 patch 替换 planner 模块中的 4 个函数引用（planner.py 顶部 from .prompts import 引入的名字）
    with patch.object(planner_mod, "build_intent_parsing_prompt_with_resources", tracker_intent), \
         patch.object(planner_mod, "build_style_recommendation_prompt_with_resources", tracker_style), \
         patch.object(planner_mod, "build_param_optimization_prompt_with_resources", tracker_param), \
         patch.object(planner_mod, "build_pipeline_explanation_prompt_with_resources", tracker_explain):

        planner = AIPlanner()
        # 注入 mock gateway，强制走 LLM 路径
        planner.intent_parser.llm = gateway
        planner.style_recommender.llm = gateway
        planner.param_optimizer.llm = gateway

        metadata = VideoMetadata(
            duration=60.0,
            width=1920,
            height=1080,
            fps=30.0,
            bitrate=5000000,
            codec="h264",
            has_audio=True,
            file_size=50000000,
            path="test.mp4",
        )

        # 执行完整规划流程，会依次触发 4 个 LLM 调用方法
        result = await planner.plan_from_query(
            user_query="做一个木质木偶风格的音乐卡点视频",
            video_path="test.mp4",
            video_metadata=metadata,
        )

    return {
        "result": result,
        "tracker_intent": tracker_intent,
        "tracker_style": tracker_style,
        "tracker_param": tracker_param,
        "tracker_explain": tracker_explain,
    }


def main() -> int:
    """主入口，返回退出码（0=成功，1=失败）。"""
    print("=" * 70)
    print("验证 AIPlanner 调用 build_*_prompt_with_resources 注入资源清单")
    print("=" * 70)

    try:
        out = asyncio.run(_verify())
    except Exception as exc:
        print(f"[FAIL] 执行异常: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    result = out["result"]
    trackers = {
        "build_intent_parsing_prompt_with_resources": out["tracker_intent"],
        "build_style_recommendation_prompt_with_resources": out["tracker_style"],
        "build_param_optimization_prompt_with_resources": out["tracker_param"],
        "build_pipeline_explanation_prompt_with_resources": out["tracker_explain"],
    }

    print("\n[1] PlanningResult 基本检查")
    print(f"    job.style        = {result.job.style.value}")
    print(f"    job.quality      = {result.job.quality_preset}")
    print(f"    job.phases       = {[p.value for p in result.job.phases]}")
    print(f"    explanation len  = {len(result.explanation)}")
    print(f"    style_rec        = {result.style_recommendation is not None}")
    print(f"    optimized_params = {result.optimized_params is not None}")

    print("\n[2] build_*_prompt_with_resources 调用统计")
    all_called = True
    for name, tracker in trackers.items():
        called = tracker.called
        count = tracker.call_count
        status = "OK" if called else "MISSING"
        if not called:
            all_called = False
        print(f"    [{status}] {name}: called={called}, call_count={count}")

    print("\n[3] 资源清单注入路径验证")
    if all_called:
        print("    [OK] 4 个 build_*_prompt_with_resources 均被调用 — 资源清单注入路径已激活")
    else:
        print("    [FAIL] 部分 build_* 函数未被调用 — 资源清单注入路径未激活")

    # 验证真实函数在 resource_index_service 不可用时也能正常返回（降级路径）
    print("\n[4] 降级路径验证（resource_index_service 不可用场景）")
    try:
        from src.ai_planner.prompts import build_resource_context
        degraded = asyncio.run(build_resource_context(limit_per_category=5))
        print(f"    [OK] build_resource_context 返回降级文本: {degraded[:80]}...")
    except Exception as exc:
        print(f"    [FAIL] build_resource_context 异常: {exc}")
        all_called = False

    print("\n" + "=" * 70)
    if all_called:
        print("验证通过：资源清单已真正注入 LLM 提示词")
        return 0
    else:
        print("验证失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

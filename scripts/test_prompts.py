"""快速测试 ai_planner.prompts 中的 build_resource_context 与异步包装函数。

运行方式（项目根目录）：
    py -3.11 scripts/test_prompts.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 将 puppet-automation/ 加入 sys.path，使得 `from src.ai_planner.prompts import ...` 可用
project_root = Path(__file__).resolve().parent.parent
puppet_root = project_root / "puppet-automation"
sys.path.insert(0, str(puppet_root))


async def main() -> None:
    from src.ai_planner.prompts import (
        build_intent_parsing_prompt_with_resources,
        build_param_optimization_prompt_with_resources,
        build_pipeline_explanation_prompt_with_resources,
        build_resource_context,
        build_style_recommendation_prompt_with_resources,
    )

    print("=" * 70)
    print("Test 1: build_resource_context() — 资源清单构建器")
    print("=" * 70)
    context = await build_resource_context(limit_per_category=30)
    print(context[:2000])
    print(f"\n[资源清单总长度: {len(context)} 字符]")

    print("\n" + "=" * 70)
    print("Test 2: build_intent_parsing_prompt_with_resources()")
    print("=" * 70)
    p1 = await build_intent_parsing_prompt_with_resources(
        user_query="做一个木质木偶风格的短视频，温暖童话感",
        video_path="D:/input/test.mp4",
        limit_per_category=10,
    )
    # 只打印末尾 1500 字符（前面是原模板）
    print("... (省略前部) ...\n" + p1[-1500:])

    print("\n" + "=" * 70)
    print("Test 3: build_style_recommendation_prompt_with_resources()")
    print("=" * 70)
    p2 = await build_style_recommendation_prompt_with_resources(
        duration=60,
        width=1920,
        height=1080,
        scene_count=3,
        face_count=1,
        content_type="fairy tale",
        motion_level="medium",
        user_preferences="童话故事",
        limit_per_category=10,
    )
    print("... (省略前部) ...\n" + p2[-1200:])

    print("\n" + "=" * 70)
    print("Test 4: build_param_optimization_prompt_with_resources()")
    print("=" * 70)
    p3 = await build_param_optimization_prompt_with_resources(
        duration=60,
        width=1920,
        height=1080,
        fps=30.0,
        bitrate=5000000,
        scene_count=3,
        motion_level="medium",
        face_count=1,
        has_people=True,
        style="wooden",
        quality_preset="high",
        limit_per_category=10,
    )
    print("... (省略前部) ...\n" + p3[-1200:])

    print("\n" + "=" * 70)
    print("Test 5: build_pipeline_explanation_prompt_with_resources()")
    print("=" * 70)
    p4 = await build_pipeline_explanation_prompt_with_resources(
        job_config='{"style": "wooden", "quality": "high"}',
        limit_per_category=10,
    )
    print("... (省略前部) ...\n" + p4[-1200:])

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

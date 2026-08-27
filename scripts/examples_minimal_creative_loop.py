#!/usr/bin/env python3
"""最小端到端创意闭环 — 使用示例。

===================================

展示 6+ 个典型场景：

1. 文字动画 - 一行式生成
2. 文字动画 - 自定义风格/时长
3. 动态图形 - 极简风格
4. 歌词视频 - 霓虹风格
5. 产品展示 - 极简品牌片
6. 转场效果 - 电影感
7. 完整注入 - 完整进度回调 + Mock 依赖
8. 失败回退 - 演示 LLM 失败时的 fallback 规划

运行方式::

    python examples_minimal_creative_loop.py --example 1
    python examples_minimal_creative_loop.py --example all

本示例默认开启**模拟模式**（``MOCK_MODE=1``），无需真实 AE/DaVinci 即可跑通。
需要真实执行时，将 ``MOCK_MODE`` 置为 ``0``。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

# 让脚本可直接 ``python examples_minimal_creative_loop.py`` 运行
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from pipeline.minimal_creative_loop import (  # noqa: E402
    ContentType,
    CreativeRequest,
    CreativeResult,
    MinimalCreativeLoop,
    StylePreset,
    quick_generate,
)


# 是否启用模拟模式（不调用真实 AE/DaVinci/LLM）
MOCK_MODE = True


# ============================================================================
# Mock 客户端（仅在 MOCK_MODE 时启用）
# ============================================================================

class MockUnifiedAEClient:
    """模拟 AE 客户端：所有方法返回成功响应，并记录调用历史。"""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._layer_counter = 0

    def _record(self, method: str, **kwargs: Any) -> Dict[str, Any]:
        self._layer_counter += 1
        self.calls.append({"method": method, "args": kwargs})
        return {
            "success": True,
            "data": {"layer_index": self._layer_counter},
        }

    def create_composition(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("create_composition", **kwargs)

    def create_text_layer(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("create_text_layer", **kwargs)

    def create_solid_layer(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("create_solid_layer", **kwargs)

    def create_shape_layer(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("create_shape_layer", **kwargs)

    def add_adjustment_layer(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("add_adjustment_layer", **kwargs)

    def set_layer_keyframe(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("set_layer_keyframe", **kwargs)

    def apply_effect(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("apply_effect", **kwargs)

    def get_layer_info(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("get_layer_info", **kwargs)

    def render(self, **kwargs: Any) -> Dict[str, Any]:
        out = Path(kwargs.get("output_path", "output/mock.mp4"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"MOCK_MOV" * 1024)
        return self._record("render", **kwargs)


class MockAEToDavinciPipeline:
    """模拟 AE→DaVinci 链路：返回成功的 PipelineResult。"""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def run_with_preset(
        self,
        comp_name: str,
        output_path: str,
        preset_name: str,
        duration: float = 10.0,
    ) -> Any:
        self.calls.append({
            "comp_name": comp_name,
            "output_path": output_path,
            "preset_name": preset_name,
            "duration": duration,
        })
        # 模拟：写一个假文件
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"MOCK_PIPELINE_MP4" * 2048)

        result = MagicMock()
        result.success = True
        result.errors = []
        result.warnings = []
        result.final_output_path = str(out)
        result.metrics = {"total_sec": 1.0}
        return result


class MockLLMGateway:
    """模拟 LLM 网关：返回一个固定的 CreativePlan JSON。"""

    def __init__(self, plan_json: Dict[str, Any] | None = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._plan_json = plan_json or self._default_plan()

    def _default_plan(self) -> Dict[str, Any]:
        return {
            "comp_name": "MockCinema",
            "duration": 10.0,
            "fps": 30.0,
            "resolution": [1920, 1080],
            "background": {"type": "solid", "color": [0.05, 0.05, 0.10]},
            "layers": [
                {
                    "type": "text",
                    "name": "HeroText",
                    "properties": {
                        "text": "探索未来",
                        "font_size": 96.0,
                        "color": [1.0, 0.95, 0.85],
                        "font_family": "Arial",
                        "position": [960.0, 540.0],
                    },
                }
            ],
            "keyframes": [
                {"layer_name": "HeroText", "property": "Opacity", "time": 0.0, "value": [0.0]},
                {"layer_name": "HeroText", "property": "Opacity", "time": 1.0, "value": [100.0]},
                {"layer_name": "HeroText", "property": "Scale", "time": 0.0, "value": [80.0, 80.0]},
                {"layer_name": "HeroText", "property": "Scale", "time": 1.5, "value": [100.0, 100.0]},
            ],
            "effects": [
                {"layer_name": "HeroText", "effect_name": "Glow", "settings": {"Glow Radius": 0.5}},
            ],
            "text_content": "探索未来",
            "text_style": {
                "font_size": 96.0,
                "color": [1.0, 0.95, 0.85],
                "font_family": "Arial",
                "alignment": "center",
            },
            "color_grading": {
                "preset_name": "cinematic_teal_orange",
                "style_description": "电影感青橙调色",
            },
            "estimated_complexity": 0.5,
        }

    async def chat(self, **kwargs: Any) -> Any:
        self.calls.append({"method": "chat", "args": kwargs})
        resp = MagicMock()
        resp.success = True
        resp.content = json.dumps(self._plan_json, ensure_ascii=False)
        resp.error = ""
        return resp

    async def chat_with_routing(self, **kwargs: Any) -> Any:
        self.calls.append({"method": "chat_with_routing", "args": kwargs})
        resp = MagicMock()
        resp.success = True
        resp.content = json.dumps(self._plan_json, ensure_ascii=False)
        resp.error = ""
        return resp


class FailingLLMGateway:
    """模拟 LLM 失败：用于演示 fallback 规划。"""

    async def chat(self, **kwargs: Any) -> Any:
        resp = MagicMock()
        resp.success = False
        resp.content = ""
        resp.error = "Simulated LLM failure"
        return resp

    async def chat_with_routing(self, **kwargs: Any) -> Any:
        return await self.chat(**kwargs)


def build_mock_loop(plan_json: Dict[str, Any] | None = None) -> MinimalCreativeLoop:
    """构造一个使用 Mock 依赖的 MinimalCreativeLoop。"""
    if not MOCK_MODE:
        return MinimalCreativeLoop()
    return MinimalCreativeLoop(
        ae_client=MockUnifiedAEClient(),
        ae_to_davinci=MockAEToDavinciPipeline(),
        llm_gateway=MockLLMGateway(plan_json=plan_json),
    )


# ============================================================================
# 进度展示工具
# ============================================================================

def make_progress_logger(prefix: str = "") -> Any:
    """构造一个打印进度的 callback。"""
    def callback(stage: str, percent: float) -> None:
        bar_len = 30
        filled = int(bar_len * percent)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"{prefix}[{bar}] {percent * 100:5.1f}% {stage}")
    return callback


def print_result(label: str, result: CreativeResult) -> None:
    """格式化输出执行结果。"""
    print(f"\n=== {label} ===")
    print(f"成功：{result.success}")
    print(f"输出：{result.output_path}")
    print(f"总耗时：{result.total_duration_sec:.2f}s")
    if result.plan:
        print(f"合成名：{result.plan.comp_name}")
        print(f"复杂度：{result.plan.estimated_complexity:.2f}")
        print(f"图层数：{len(result.plan.layers)}")
        print(f"关键帧：{len(result.plan.keyframes)}")
        print(f"效果数：{len(result.plan.effects)}")
    if result.warnings:
        print(f"警告（{len(result.warnings)}）:")
        for w in result.warnings:
            print(f"  - {w}")
    if result.errors:
        print(f"错误（{len(result.errors)}）:")
        for e in result.errors:
            print(f"  - {e}")
    if result.metrics:
        print(f"指标：{result.metrics}")


# ============================================================================
# 示例
# ============================================================================

def example_1_text_animation_quick() -> None:
    """示例 1：一行式文字动画。"""
    print("\n" + "=" * 60)
    print("示例 1：一行式文字动画（quick_generate）")
    print("=" * 60)

    loop = build_mock_loop()
    # 直接替换 llm 为带正确 comp_name 的版本
    loop.llm = MockLLMGateway(plan_json={
        "comp_name": "HelloWorld_Anim",
        "duration": 5.0,
        "fps": 30.0,
        "resolution": [1280, 720],
        "background": {"type": "solid", "color": [0.1, 0.1, 0.2]},
        "layers": [
            {
                "type": "text",
                "name": "Hello",
                "properties": {
                    "text": "Hello, World!",
                    "font_size": 80.0,
                    "color": [1.0, 1.0, 1.0],
                    "font_family": "Arial",
                },
            }
        ],
        "keyframes": [],
        "effects": [],
        "text_content": "Hello, World!",
        "text_style": {"font_size": 80.0, "color": [1.0, 1.0, 1.0], "font_family": "Arial", "alignment": "center"},
        "color_grading": {"preset_name": "cinematic_teal_orange", "style_description": "电影感"},
        "estimated_complexity": 0.3,
    })

    result = loop.text_animation(
        text="Hello, World!",
        style="cinematic",
        duration=5.0,
        output_path="output/example1_hello.mp4",
    )
    print_result("示例 1 结果", result)


def example_2_text_animation_custom() -> None:
    """示例 2：自定义文字动画（霓虹风格、长时长）。"""
    print("\n" + "=" * 60)
    print("示例 2：自定义霓虹风格文字动画")
    print("=" * 60)

    loop = build_mock_loop()
    loop.llm = MockLLMGateway(plan_json={
        "comp_name": "Neon_Anim",
        "duration": 15.0,
        "fps": 60.0,
        "resolution": [1920, 1080],
        "background": {"type": "solid", "color": [0.02, 0.0, 0.05]},
        "layers": [
            {
                "type": "text",
                "name": "NeonText",
                "properties": {
                    "text": "NEON VIBES",
                    "font_size": 120.0,
                    "color": [1.0, 0.0, 0.8],
                    "font_family": "Arial",
                },
            }
        ],
        "keyframes": [
            {"layer_name": "NeonText", "property": "Opacity", "time": 0.0, "value": [0.0]},
            {"layer_name": "NeonText", "property": "Opacity", "time": 0.8, "value": [100.0]},
            {"layer_name": "NeonText", "property": "Scale", "time": 0.0, "value": [50.0, 50.0]},
            {"layer_name": "NeonText", "property": "Scale", "time": 1.2, "value": [110.0, 110.0]},
            {"layer_name": "NeonText", "property": "Scale", "time": 1.5, "value": [100.0, 100.0]},
        ],
        "effects": [
            {"layer_name": "NeonText", "effect_name": "Glow", "settings": {"Glow Radius": 0.8}},
        ],
        "text_content": "NEON VIBES",
        "text_style": {"font_size": 120.0, "color": [1.0, 0.0, 0.8], "font_family": "Arial", "alignment": "center"},
        "color_grading": {"preset_name": "music_video_punch", "style_description": "高对比霓虹"},
        "estimated_complexity": 0.6,
    })

    request = CreativeRequest(
        description="做一个 15 秒的霓虹风格文字动画，文字是'NEON VIBES'，强调发光和脉冲感",
        content_type=ContentType.TEXT_ANIMATION,
        style=StylePreset.NEON,
        duration=15.0,
        output_path="output/example2_neon.mp4",
        frame_rate=60.0,
        progress_callback=make_progress_logger("  "),
    )
    result = loop.run(request)
    print_result("示例 2 结果", result)


def example_3_motion_graphics() -> None:
    """示例 3：极简动态图形。"""
    print("\n" + "=" * 60)
    print("示例 3：极简风格动态图形")
    print("=" * 60)

    loop = build_mock_loop()
    loop.llm = MockLLMGateway(plan_json={
        "comp_name": "MG_Loading",
        "duration": 4.0,
        "fps": 30.0,
        "resolution": [1080, 1080],
        "background": {"type": "solid", "color": [0.95, 0.95, 0.95]},
        "layers": [
            {"type": "shape", "name": "Circle1", "properties": {"shape": "ellipse", "size": [100, 100]}},
            {"type": "shape", "name": "Circle2", "properties": {"shape": "ellipse", "size": [100, 100]}},
            {"type": "shape", "name": "Circle3", "properties": {"shape": "ellipse", "size": [100, 100]}},
        ],
        "keyframes": [
            {"layer_name": "Circle1", "property": "Scale", "time": 0.0, "value": [60.0, 60.0]},
            {"layer_name": "Circle1", "property": "Scale", "time": 1.0, "value": [100.0, 100.0]},
        ],
        "effects": [],
        "text_content": None,
        "text_style": None,
        "color_grading": {"preset_name": "high_key_bright", "style_description": "极简高调"},
        "estimated_complexity": 0.4,
    })

    result = loop.motion_graphics(
        description="3 个圆点循环呼吸动画",
        duration=4.0,
        output_path="output/example3_mg.mp4",
        style="minimal",
    )
    print_result("示例 3 结果", result)


def example_4_lyric_video() -> None:
    """示例 4：歌词视频。"""
    print("\n" + "=" * 60)
    print("示例 4：霓虹风格歌词视频")
    print("=" * 60)

    loop = build_mock_loop()
    loop.llm = MockLLMGateway(plan_json={
        "comp_name": "Lyric_Neon",
        "duration": 8.0,
        "fps": 30.0,
        "resolution": [1920, 1080],
        "background": {"type": "solid", "color": [0.02, 0.0, 0.05]},
        "layers": [
            {
                "type": "text",
                "name": "Line1",
                "properties": {
                    "text": "城市的霓虹在闪烁",
                    "font_size": 60.0,
                    "color": [1.0, 0.2, 0.6],
                    "font_family": "Arial",
                },
            },
        ],
        "keyframes": [
            {"layer_name": "Line1", "property": "Opacity", "time": 0.0, "value": [0.0]},
            {"layer_name": "Line1", "property": "Opacity", "time": 1.0, "value": [100.0]},
        ],
        "effects": [
            {"layer_name": "Line1", "effect_name": "Glow", "settings": {"Glow Radius": 0.7}},
        ],
        "text_content": "城市的霓虹在闪烁",
        "text_style": {"font_size": 60.0, "color": [1.0, 0.2, 0.6], "font_family": "Arial", "alignment": "center"},
        "color_grading": {"preset_name": "music_video_punch", "style_description": "霓虹MV"},
        "estimated_complexity": 0.5,
    })

    lyrics = """城市的霓虹在闪烁
心跳跟着节奏走
每一次呼吸都是自由
在夜色里寻找出口"""

    result = loop.lyric_video(
        lyrics=lyrics,
        style="neon",
        duration=8.0,
        output_path="output/example4_lyric.mp4",
    )
    print_result("示例 4 结果", result)


def example_5_product_showcase() -> None:
    """示例 5：极简产品展示。"""
    print("\n" + "=" * 60)
    print("示例 5：极简品牌产品展示")
    print("=" * 60)

    loop = build_mock_loop()
    loop.llm = MockLLMGateway(plan_json={
        "comp_name": "Product_Minimal",
        "duration": 12.0,
        "fps": 30.0,
        "resolution": [1920, 1080],
        "background": {"type": "solid", "color": [0.98, 0.98, 0.98]},
        "layers": [
            {"type": "shape", "name": "ProductMock", "properties": {"shape": "rect", "size": [400, 400]}},
            {
                "type": "text",
                "name": "BrandName",
                "properties": {"text": "AURA PRO", "font_size": 48.0, "color": [0.1, 0.1, 0.1]},
            },
        ],
        "keyframes": [
            {"layer_name": "ProductMock", "property": "Scale", "time": 0.0, "value": [95.0, 95.0]},
            {"layer_name": "ProductMock", "property": "Scale", "time": 6.0, "value": [105.0, 105.0]},
        ],
        "effects": [
            {"layer_name": "ProductMock", "effect_name": "Drop Shadow", "settings": {"Shadow Opacity": 0.3}},
        ],
        "text_content": "AURA PRO",
        "text_style": {"font_size": 48.0, "color": [0.1, 0.1, 0.1], "font_family": "Arial", "alignment": "center"},
        "color_grading": {"preset_name": "high_key_bright", "style_description": "极简高调"},
        "estimated_complexity": 0.5,
    })

    result = loop.product_showcase(
        product_name="AURA PRO",
        tagline="Light in Motion",
        style="minimal",
        duration=12.0,
        output_path="output/example5_product.mp4",
    )
    print_result("示例 5 结果", result)


def example_6_transition() -> None:
    """示例 6：电影感转场。"""
    print("\n" + "=" * 60)
    print("示例 6：电影感转场效果")
    print("=" * 60)

    loop = build_mock_loop()
    loop.llm = MockLLMGateway(plan_json={
        "comp_name": "Transition_Cinema",
        "duration": 2.0,
        "fps": 60.0,
        "resolution": [1920, 1080],
        "background": {"type": "solid", "color": [0.0, 0.0, 0.0]},
        "layers": [
            {"type": "shape", "name": "Flash", "properties": {"shape": "rect", "size": [1920, 1080]}},
        ],
        "keyframes": [
            {"layer_name": "Flash", "property": "Opacity", "time": 0.0, "value": [0.0]},
            {"layer_name": "Flash", "property": "Opacity", "time": 1.0, "value": [100.0]},
            {"layer_name": "Flash", "property": "Opacity", "time": 2.0, "value": [0.0]},
        ],
        "effects": [
            {"layer_name": "Flash", "effect_name": "CC Light Sweep", "settings": {}},
        ],
        "text_content": None,
        "text_style": None,
        "color_grading": {"preset_name": "cinematic_teal_orange", "style_description": "电影感"},
        "estimated_complexity": 0.3,
    })

    result = loop.transition(
        theme="cinematic",
        duration=2.0,
        output_path="output/example6_transition.mp4",
    )
    print_result("示例 6 结果", result)


def example_7_full_with_progress() -> None:
    """示例 7：完整进度回调 + Mock 依赖。"""
    print("\n" + "=" * 60)
    print("示例 7：完整进度回调 + Mock 依赖")
    print("=" * 60)

    loop = build_mock_loop()
    loop.llm = MockLLMGateway(plan_json={
        "comp_name": "FullDemo",
        "duration": 10.0,
        "fps": 30.0,
        "resolution": [1920, 1080],
        "background": {"type": "solid", "color": [0.05, 0.05, 0.10]},
        "layers": [
            {
                "type": "text",
                "name": "Title",
                "properties": {"text": "完整体验", "font_size": 96.0, "color": [1.0, 0.95, 0.85]},
            },
            {
                "type": "shape",
                "name": "Decor",
                "properties": {"shape": "ellipse", "size": [200, 200]},
            },
        ],
        "keyframes": [
            {"layer_name": "Title", "property": "Opacity", "time": 0.0, "value": [0.0]},
            {"layer_name": "Title", "property": "Opacity", "time": 1.0, "value": [100.0]},
        ],
        "effects": [
            {"layer_name": "Title", "effect_name": "Glow", "settings": {"Glow Radius": 0.5}},
        ],
        "text_content": "完整体验",
        "text_style": {"font_size": 96.0, "color": [1.0, 0.95, 0.85], "font_family": "Arial", "alignment": "center"},
        "color_grading": {"preset_name": "cinematic_teal_orange", "style_description": "电影感"},
        "estimated_complexity": 0.5,
    })

    print("AE 调用统计：")
    result = loop.run(CreativeRequest(
        description="做一个 10 秒电影感完整体验视频",
        content_type=ContentType.MOTION_GRAPHICS,
        style=StylePreset.CINEMATIC,
        duration=10.0,
        output_path="output/example7_full.mp4",
        progress_callback=make_progress_logger("    "),
    ))
    print_result("示例 7 结果", result)

    if isinstance(loop.ae, MockUnifiedAEClient):
        print(f"\n  AE 总调用次数：{len(loop.ae.calls)}")
        for call in loop.ae.calls:
            print(f"    {call['method']}: {list(call['args'].keys())}")


def example_8_fallback_plan() -> None:
    """示例 8：LLM 失败时演示 fallback 规划。"""
    print("\n" + "=" * 60)
    print("示例 8：LLM 失败 → fallback 规划")
    print("=" * 60)

    loop = MinimalCreativeLoop(
        ae_client=MockUnifiedAEClient(),
        ae_to_davinci=MockAEToDavinciPipeline(),
        llm_gateway=FailingLLMGateway(),
    )

    result = loop.run(CreativeRequest(
        description="做一个 10 秒电影感文字动画，内容是'探索未来'",
        content_type=ContentType.TEXT_ANIMATION,
        style=StylePreset.CINEMATIC,
        duration=10.0,
        output_path="output/example8_fallback.mp4",
    ))
    print_result("示例 8 结果（fallback）", result)
    if result.warnings:
        print("\n  警告摘要（证明 fallback 触发）：")
        for w in result.warnings:
            print(f"    {w}")


# ============================================================================
# 入口
# ============================================================================

EXAMPLES = {
    "1": example_1_text_animation_quick,
    "2": example_2_text_animation_custom,
    "3": example_3_motion_graphics,
    "4": example_4_lyric_video,
    "5": example_5_product_showcase,
    "6": example_6_transition,
    "7": example_7_full_with_progress,
    "8": example_8_fallback_plan,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="MinimalCreativeLoop 使用示例")
    parser.add_argument(
        "--example",
        default="1",
        help="要运行的示例编号（1-8，或 'all'）。默认 1。",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="关闭 Mock 模式，使用真实 AE/DaVinci/LLM（需相关环境）。",
    )
    args = parser.parse_args()

    global MOCK_MODE
    MOCK_MODE = not args.real

    if args.example == "all":
        for name, fn in EXAMPLES.items():
            fn()
    else:
        fn = EXAMPLES.get(args.example)
        if fn is None:
            print(f"未知示例：{args.example}（可选：{list(EXAMPLES.keys())} 或 'all'）")
            return 1
        fn()

    return 0


if __name__ == "__main__":
    sys.exit(main())

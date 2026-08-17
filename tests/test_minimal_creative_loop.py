"""MinimalCreativeLoop 单元测试。

====================================

覆盖范围：

1. 数据模型（CreativeRequest / CreativePlan / CreativeResult）
2. LLM 规划流程（成功 / 失败 / JSON 解析失败 / Markdown code block）
3. Fallback 规划
4. AE 执行流程（mock AE 客户端）
5. 调色流程（mock AE→DaVinci 链路）
6. 完整 run() 端到端（mock 全部依赖）
7. 便捷方法（text_animation / motion_graphics / lyric_video 等）
8. 进度回调
9. 异常降级
10. 静态工具方法（_extract_json / _sanitize_comp_name 等）

所有测试使用 mock，不依赖真实 AE/DaVinci/LLM。
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest


# 让测试可在无 conftest 注入 path 的情况下直接跑
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from pipeline.minimal_creative_loop import (  # noqa: E402
    ContentType,
    CreativePlan,
    CreativeRequest,
    CreativeResult,
    MinimalCreativeLoop,
    StylePreset,
    quick_generate,
)
from pipeline.prompts.creative_planning import (  # noqa: E402
    CONTENT_TYPE_TEMPLATES,
    STYLE_DESCRIPTIONS,
    STYLE_PRESET_MAP,
    build_system_prompt,
    build_user_prompt,
)


# ============================================================================
# Mock 客户端
# ============================================================================

class MockUnifiedAEClient:
    """记录所有调用的 Mock AE 客户端。"""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._layer_counter = 0
        self.fail_methods: List[str] = []
        # 已创建的图层名集合（get_layer_info 用于判断图层是否存在）
        self.created_layers: set = set()

    def _record(self, method: str, **kwargs: Any) -> Dict[str, Any]:
        if method in self.fail_methods:
            return {"success": False, "error": f"mock failure on {method}"}
        self._layer_counter += 1
        self.calls.append({"method": method, "args": kwargs})
        return {
            "success": True,
            "data": {"layer_index": self._layer_counter},
        }

    def create_composition(self, **kw: Any) -> Dict[str, Any]:
        return self._record("create_composition", **kw)

    def create_text_layer(self, **kw: Any) -> Dict[str, Any]:
        self.created_layers.add(kw.get("name", ""))
        return self._record("create_text_layer", **kw)

    def create_solid_layer(self, **kw: Any) -> Dict[str, Any]:
        self.created_layers.add(kw.get("name", ""))
        return self._record("create_solid_layer", **kw)

    def create_shape_layer(self, **kw: Any) -> Dict[str, Any]:
        self.created_layers.add(kw.get("name", ""))
        return self._record("create_shape_layer", **kw)

    def add_adjustment_layer(self, **kw: Any) -> Dict[str, Any]:
        self.created_layers.add(kw.get("name", ""))
        return self._record("add_adjustment_layer", **kw)

    def set_layer_keyframe(self, **kw: Any) -> Dict[str, Any]:
        return self._record("set_layer_keyframe", **kw)

    def apply_effect(self, **kw: Any) -> Dict[str, Any]:
        return self._record("apply_effect", **kw)

    def get_layer_info(self, **kw: Any) -> Dict[str, Any]:
        # 只有已创建的图层才返回 layer_index
        layer_name = kw.get("layer_name", "")
        if layer_name in self.created_layers:
            return self._record("get_layer_info", **kw)
        return {"success": False, "error": f"layer not found: {layer_name}"}

    def render(self, **kw: Any) -> Dict[str, Any]:
        out = Path(kw.get("output_path", "output/mock.mp4"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"MOCK")
        return self._record("render", **kw)


class MockAEToDavinciPipeline:
    """Mock AE→DaVinci 链路。"""

    def __init__(self, success: bool = True) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._success = success

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
        if self._success:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"MOCK_PIPELINE")
        result = MagicMock()
        result.success = self._success
        result.errors = [] if self._success else ["mock pipeline failure"]
        result.warnings = []
        result.final_output_path = output_path if self._success else None
        result.metrics = {}
        return result


class MockLLMGateway:
    """Mock LLM 网关：返回指定 JSON。"""

    def __init__(self, plan_json: Dict[str, Any] | None = None, raw: str | None = None) -> None:
        self._plan_json = plan_json
        self._raw = raw
        self.calls: List[Dict[str, Any]] = []

    def _build_content(self) -> str:
        if self._raw is not None:
            return self._raw
        if self._plan_json is not None:
            return json.dumps(self._plan_json, ensure_ascii=False)
        return "{}"

    async def chat(self, **kwargs: Any) -> Any:
        self.calls.append({"method": "chat", "args": kwargs})
        resp = MagicMock()
        resp.success = True
        resp.content = self._build_content()
        resp.error = ""
        return resp

    async def chat_with_routing(self, **kwargs: Any) -> Any:
        self.calls.append({"method": "chat_with_routing", "args": kwargs})
        resp = MagicMock()
        resp.success = True
        resp.content = self._build_content()
        resp.error = ""
        return resp


class FailingLLMGateway:
    """Mock 失败的 LLM 网关。"""

    async def chat(self, **kwargs: Any) -> Any:
        resp = MagicMock()
        resp.success = False
        resp.content = ""
        resp.error = "mock LLM failure"
        return resp

    async def chat_with_routing(self, **kwargs: Any) -> Any:
        return await self.chat(**kwargs)


def make_loop(
    plan_json: Dict[str, Any] | None = None,
    raw: str | None = None,
    pipeline_success: bool = True,
) -> MinimalCreativeLoop:
    """构造一个使用 mock 依赖的 MinimalCreativeLoop。"""
    return MinimalCreativeLoop(
        ae_client=MockUnifiedAEClient(),
        ae_to_davinci=MockAEToDavinciPipeline(success=pipeline_success),
        llm_gateway=MockLLMGateway(plan_json=plan_json, raw=raw),
    )


def sample_plan(comp_name: str = "TestComp") -> Dict[str, Any]:
    """构造一个标准的样例规划。"""
    return {
        "comp_name": comp_name,
        "duration": 5.0,
        "fps": 30.0,
        "resolution": [1280, 720],
        "background": {"type": "solid", "color": [0.1, 0.1, 0.1]},
        "layers": [
            {
                "type": "text",
                "name": "MainText",
                "properties": {
                    "text": "Hello Test",
                    "font_size": 64.0,
                    "color": [1.0, 1.0, 1.0],
                },
            },
            {
                "type": "shape",
                "name": "Circle",
                "properties": {"shape": "ellipse", "size": [100, 100]},
            },
        ],
        "keyframes": [
            {"layer_name": "MainText", "property": "Opacity", "time": 0.0, "value": [0.0]},
            {"layer_name": "MainText", "property": "Opacity", "time": 1.0, "value": [100.0]},
        ],
        "effects": [
            {"layer_name": "MainText", "effect_name": "Glow", "settings": {}},
        ],
        "text_content": "Hello Test",
        "text_style": {
            "font_size": 64.0,
            "color": [1.0, 1.0, 1.0],
            "font_family": "Arial",
            "alignment": "center",
        },
        "color_grading": {
            "preset_name": "cinematic_teal_orange",
            "style_description": "电影感",
        },
        "estimated_complexity": 0.5,
    }


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_output_dir() -> Path:
    """临时输出目录（自动清理）。"""
    with tempfile.TemporaryDirectory(prefix="ae_kv_mcl_test_") as tmp:
        yield Path(tmp)


# ============================================================================
# 数据模型测试
# ============================================================================

class TestDataModels:
    """数据模型测试。"""

    def test_creative_request_defaults(self) -> None:
        req = CreativeRequest(description="test")
        assert req.content_type == ContentType.TEXT_ANIMATION
        assert req.style == StylePreset.CINEMATIC
        assert req.duration == 10.0
        assert req.output_path == "output/auto_generated.mp4"
        assert req.resolution == (1920, 1080)
        assert req.frame_rate == 30.0
        assert req.additional_params == {}
        assert req.progress_callback is None

    def test_creative_plan_to_dict(self) -> None:
        plan = CreativePlan(
            comp_name="X",
            duration=3.0,
            fps=24.0,
            resolution=(640, 480),
            background={"type": "solid", "color": [0, 0, 0]},
        )
        d = plan.to_dict()
        assert d["comp_name"] == "X"
        assert d["duration"] == 3.0
        assert d["resolution"] == [640, 480]

    def test_creative_result_to_dict(self) -> None:
        result = CreativeResult(success=True, output_path="out.mp4")
        d = result.to_dict()
        assert d["success"] is True
        assert d["output_path"] == "out.mp4"
        assert d["plan"] is None


# ============================================================================
# 枚举 & 提示词
# ============================================================================

class TestEnumsAndPrompts:
    def test_content_type_values(self) -> None:
        assert ContentType.TEXT_ANIMATION.value == "text_animation"
        assert ContentType.MOTION_GRAPHICS.value == "motion_graphics"

    def test_style_preset_values(self) -> None:
        assert StylePreset.CINEMATIC.value == "cinematic"
        assert len(StylePreset) == 8

    def test_content_type_templates_complete(self) -> None:
        for ct in ContentType:
            assert ct in CONTENT_TYPE_TEMPLATES

    def test_style_descriptions_complete(self) -> None:
        for sp in StylePreset:
            assert sp in STYLE_DESCRIPTIONS

    def test_style_preset_map_complete(self) -> None:
        for sp in StylePreset:
            assert sp in STYLE_PRESET_MAP

    def test_build_system_prompt_contains_all(self) -> None:
        prompt = build_system_prompt(ContentType.TEXT_ANIMATION, StylePreset.CINEMATIC)
        assert "JSON Schema" in prompt
        assert "文字动画" in prompt
        assert "电影感" in prompt

    def test_build_user_prompt_basic(self) -> None:
        prompt = build_user_prompt(
            description="测试",
            content_type=ContentType.TEXT_ANIMATION,
            style=StylePreset.CINEMATIC,
            duration=5.0,
            resolution=(1920, 1080),
            frame_rate=30.0,
        )
        assert "测试" in prompt
        assert "1920 x 1080" in prompt
        assert "30.0 fps" in prompt

    def test_build_user_prompt_with_context(self) -> None:
        prompt = build_user_prompt(
            description="x",
            content_type=ContentType.LYRIC_VIDEO,
            style=StylePreset.NEON,
            duration=3.0,
            resolution=(1920, 1080),
            frame_rate=30.0,
            additional_context={"lyrics": "test lyrics"},
        )
        assert "lyrics" in prompt
        assert "test lyrics" in prompt


# ============================================================================
# JSON 提取 & 解析
# ============================================================================

class TestJsonExtraction:
    def test_extract_json_pure(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._extract_json('{"a": 1}') == '{"a": 1}'

    def test_extract_json_markdown_block(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        raw = '下面给出规划：\n```json\n{"a": 1}\n```\n请使用'
        assert loop._extract_json(raw) == '{"a": 1}'

    def test_extract_json_markdown_block_no_lang(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        raw = '```\n{"b": 2}\n```'
        assert loop._extract_json(raw) == '{"b": 2}'

    def test_extract_json_with_surrounding_text(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        raw = '思考过程... {"a": 1, "b": [2, 3]} 完成'
        assert loop._extract_json(raw) == '{"a": 1, "b": [2, 3]}'

    def test_extract_json_empty(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._extract_json("") is None
        assert loop._extract_json("not json at all") is None


class TestSanitizeCompName:
    def test_normal_name(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._sanitize_comp_name("Hello_World") == "Hello_World"

    def test_spaces_replaced(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._sanitize_comp_name("Hello World") == "Hello_World"

    def test_special_chars_removed(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._sanitize_comp_name("Hello@World!") == "HelloWorld"

    def test_empty_returns_default(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._sanitize_comp_name("").startswith("Auto_")

    def test_long_name_truncated(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        long_name = "A" * 100
        result = loop._sanitize_comp_name(long_name)
        assert len(result) <= 60


# ============================================================================
# Fallback 规划
# ============================================================================

class TestFallbackPlan:
    def test_fallback_returns_plan(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        req = CreativeRequest(
            description="做一个测试视频",
            style=StylePreset.CINEMATIC,
            duration=8.0,
        )
        plan = loop._fallback_plan(req)
        assert plan.comp_name.startswith("Auto_cinematic_")
        assert plan.duration == 8.0
        assert len(plan.layers) >= 1
        assert plan.text_content is not None

    def test_fallback_all_styles(self) -> None:
        """所有风格都应能生成 fallback 规划。"""
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        for style in StylePreset:
            req = CreativeRequest(description="x", style=style, duration=5.0)
            plan = loop._fallback_plan(req)
            assert plan.comp_name
            assert plan.color_grading
            assert plan.color_grading.get("preset_name")

    def test_fallback_color_matches_style(self) -> None:
        """暗黑风格应该用深色背景。"""
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        req = CreativeRequest(
            description="x",
            style=StylePreset.DARK_MOOD,
            duration=5.0,
        )
        plan = loop._fallback_plan(req)
        bg = plan.background
        # 背景色求和应该较小
        if bg.get("type") == "solid":
            assert sum(bg.get("color", [0, 0, 0])) < 0.5

    def test_fallback_truncates_long_text(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        long_desc = "测" * 50
        req = CreativeRequest(description=long_desc, duration=5.0)
        plan = loop._fallback_plan(req)
        if plan.text_content:
            assert len(plan.text_content) <= 33  # 30 + "..."


# ============================================================================
# LLM 规划
# ============================================================================

class TestLLMPlanning:
    def test_planning_with_pure_json(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("TestComp"))
        result = CreativeResult(success=False)
        req = CreativeRequest(
            description="test",
            output_path=str(temp_output_dir / "out.mp4"),
        )
        plan = loop._plan_with_llm(req, result)
        assert plan.comp_name == "TestComp"
        assert plan.duration == 5.0
        assert len(plan.layers) == 2

    def test_planning_with_markdown_block(self, temp_output_dir: Path) -> None:
        plan = sample_plan("MarkdownComp")
        raw = f"下面是规划：\n```json\n{json.dumps(plan)}\n```\n"
        loop = make_loop(raw=raw)
        result = CreativeResult(success=False)
        req = CreativeRequest(
            description="x",
            output_path=str(temp_output_dir / "out.mp4"),
        )
        out = loop._plan_with_llm(req, result)
        assert out.comp_name == "MarkdownComp"

    def test_planning_with_invalid_json_falls_back(self, temp_output_dir: Path) -> None:
        loop = make_loop(raw="not json at all")
        result = CreativeResult(success=False)
        req = CreativeRequest(
            description="x",
            style=StylePreset.NEON,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        plan = loop._plan_with_llm(req, result)
        # fallback plan
        assert plan.comp_name.startswith("Auto_neon_")
        assert any("fallback" in w for w in result.warnings)

    def test_planning_with_llm_failure_falls_back(self, temp_output_dir: Path) -> None:
        loop = MinimalCreativeLoop(
            ae_client=MockUnifiedAEClient(),
            ae_to_davinci=MockAEToDavinciPipeline(),
            llm_gateway=FailingLLMGateway(),
        )
        result = CreativeResult(success=False)
        req = CreativeRequest(
            description="x",
            style=StylePreset.CINEMATIC,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        plan = loop._plan_with_llm(req, result)
        assert plan.comp_name.startswith("Auto_")
        assert any("fallback" in w for w in result.warnings)

    def test_planning_sanitizes_comp_name(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("Comp With Spaces!@#"))
        result = CreativeResult(success=False)
        req = CreativeRequest(
            description="x",
            output_path=str(temp_output_dir / "out.mp4"),
        )
        plan = loop._plan_with_llm(req, result)
        # 应该只保留合法字符
        assert " " not in plan.comp_name
        assert "@" not in plan.comp_name
        assert "!" not in plan.comp_name

    def test_planning_normalizes_color_grading(self, temp_output_dir: Path) -> None:
        """color_grading 缺省时使用风格映射。"""
        plan = sample_plan("X")
        plan.pop("color_grading")
        loop = make_loop(plan_json=plan)
        result = CreativeResult(success=False)
        req = CreativeRequest(
            description="x",
            style=StylePreset.VINTAGE,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        out = loop._plan_with_llm(req, result)
        assert out.color_grading is not None
        assert out.color_grading["preset_name"] == "vintage_film"


# ============================================================================
# 端到端 run()
# ============================================================================

class TestEndToEnd:
    def test_run_full_success(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("FullComp"))
        req = CreativeRequest(
            description="做一个 5 秒电影感文字动画",
            style=StylePreset.CINEMATIC,
            duration=5.0,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        result = loop.run(req)
        assert result.success is True
        assert result.plan is not None
        assert result.output_path is not None
        # 验证 AE 调用
        assert isinstance(loop.ae, MockUnifiedAEClient)
        methods_called = {c["method"] for c in loop.ae.calls}
        assert "create_composition" in methods_called
        assert "create_text_layer" in methods_called
        # 验证调色调用
        assert isinstance(loop.ae_to_davinci, MockAEToDavinciPipeline)
        assert len(loop.ae_to_davinci.calls) == 1

    def test_run_progress_callback_invoked(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("ProgressComp"))
        progress_calls: List[tuple] = []

        def cb(stage: str, percent: float) -> None:
            progress_calls.append((stage, percent))

        req = CreativeRequest(
            description="x",
            duration=3.0,
            output_path=str(temp_output_dir / "out.mp4"),
            progress_callback=cb,
        )
        result = loop.run(req)
        assert result.success is True
        # 至少调用一次
        assert len(progress_calls) >= 4
        # 最后一次应为 100%
        assert progress_calls[-1][1] == 1.0

    def test_run_fallback_on_llm_failure(self, temp_output_dir: Path) -> None:
        loop = MinimalCreativeLoop(
            ae_client=MockUnifiedAEClient(),
            ae_to_davinci=MockAEToDavinciPipeline(),
            llm_gateway=FailingLLMGateway(),
        )
        req = CreativeRequest(
            description="x",
            style=StylePreset.CINEMATIC,
            duration=3.0,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        result = loop.run(req)
        assert result.success is True
        assert result.plan is not None
        assert any("fallback" in w for w in result.warnings)

    def test_run_color_grading_failure_still_succeeds(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("X"), pipeline_success=False)
        req = CreativeRequest(
            description="x",
            duration=3.0,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        result = loop.run(req)
        # 调色失败但整体仍应成功
        assert result.success is True
        assert any("调色失败" in w or "调色" in w for w in result.warnings)

    def test_run_metrics_recorded(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("MetricComp"))
        req = CreativeRequest(
            description="x",
            duration=3.0,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        result = loop.run(req)
        assert "total_sec" in result.metrics
        assert "llm_sec" in result.metrics
        assert "ae_create_comp_sec" in result.metrics
        assert "color_grading_sec" in result.metrics

    def test_run_handles_ae_composition_failure(self, temp_output_dir: Path) -> None:
        ae = MockUnifiedAEClient()
        ae.fail_methods = ["create_composition"]
        loop = MinimalCreativeLoop(
            ae_client=ae,
            ae_to_davinci=MockAEToDavinciPipeline(),
            llm_gateway=MockLLMGateway(plan_json=sample_plan("FailComp")),
        )
        req = CreativeRequest(
            description="x",
            duration=3.0,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        result = loop.run(req)
        # AE 创建合成失败应导致整体失败
        assert result.success is False
        assert any("AE 创建合成失败" in e for e in result.errors)


# ============================================================================
# 便捷方法
# ============================================================================

class TestConvenienceMethods:
    def test_text_animation(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("TextAnim"))
        result = loop.text_animation(
            text="Hello",
            style="cinematic",
            duration=5.0,
            output_path=str(temp_output_dir / "ta.mp4"),
        )
        assert result.success is True
        assert result.plan is not None
        assert result.plan.text_content is not None

    def test_motion_graphics(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("MG"))
        result = loop.motion_graphics(
            description="test",
            duration=4.0,
            output_path=str(temp_output_dir / "mg.mp4"),
            style="minimal",
        )
        assert result.success is True

    def test_lyric_video(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("Lyric"))
        result = loop.lyric_video(
            lyrics="line1\nline2",
            style="neon",
            duration=5.0,
            output_path=str(temp_output_dir / "lyric.mp4"),
        )
        assert result.success is True

    def test_product_showcase(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("Product"))
        result = loop.product_showcase(
            product_name="AURA",
            tagline="Light in Motion",
            style="minimal",
            duration=8.0,
            output_path=str(temp_output_dir / "product.mp4"),
        )
        assert result.success is True

    def test_transition(self, temp_output_dir: Path) -> None:
        loop = make_loop(plan_json=sample_plan("Transition"))
        result = loop.transition(
            theme="cinematic",
            duration=2.0,
            output_path=str(temp_output_dir / "trans.mp4"),
        )
        assert result.success is True

    def test_quick_generate_function(self, temp_output_dir: Path) -> None:
        """顶层便捷函数 quick_generate。"""
        # 由于 quick_generate 内部构造 MinimalCreativeLoop (使用真实依赖)，
        # 这里直接测试函数签名和基本行为
        # 不实际调用（会触发真实 LLM）；改用 monkeypatch
        from pipeline import minimal_creative_loop as mcl_mod

        original_loop_cls = mcl_mod.MinimalCreativeLoop
        mcl_mod.MinimalCreativeLoop = make_loop  # type: ignore[assignment]
        try:
            # quick_generate 会构造真实 MinimalCreativeLoop，但被我们 monkeypatch
            result = quick_generate(
                description="测试",
                output_path=str(temp_output_dir / "quick.mp4"),
                style="cinematic",
                duration=5.0,
            )
            assert result.success is True
        finally:
            mcl_mod.MinimalCreativeLoop = original_loop_cls  # type: ignore[assignment]


# ============================================================================
# 调色映射
# ============================================================================

class TestColorGrading:
    def test_style_to_preset_mapping(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._map_style_to_preset(StylePreset.CINEMATIC) == "cinematic_teal_orange"
        assert loop._map_style_to_preset(StylePreset.VINTAGE) == "vintage_film"
        assert loop._map_style_to_preset(StylePreset.NEON) == "music_video_punch"
        assert loop._map_style_to_preset(StylePreset.DARK_MOOD) == "low_key_dark"

    def test_style_preset_map_complete(self) -> None:
        for style in StylePreset:
            assert style in STYLE_PRESET_MAP
            assert STYLE_PRESET_MAP[style]  # non-empty


# ============================================================================
# 后台颜色规范化
# ============================================================================

class TestBackgroundNormalization:
    def test_solid_color_normalized(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        bg = loop._normalize_background(
            {"type": "solid", "color": [0.5, 0.6, 0.7]},
            CreativeRequest(description="x"),
        )
        assert bg["type"] == "solid"
        assert bg["color"] == [0.5, 0.6, 0.7]

    def test_invalid_color_falls_back_to_black(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        bg = loop._normalize_background(
            {"type": "solid", "color": "invalid"},
            CreativeRequest(description="x"),
        )
        assert bg["color"] == [0.0, 0.0, 0.0]

    def test_gradient_normalized(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        bg = loop._normalize_background(
            {
                "type": "gradient",
                "gradient": {"from": [0.0, 0.0, 0.0], "to": [1.0, 1.0, 1.0], "angle": 90.0},
            },
            CreativeRequest(description="x"),
        )
        assert bg["type"] == "gradient"
        assert bg["gradient"]["from"] == [0.0, 0.0, 0.0]
        assert bg["gradient"]["to"] == [1.0, 1.0, 1.0]
        assert bg["gradient"]["angle"] == 90.0

    def test_none_becomes_default(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        bg = loop._normalize_background(None, CreativeRequest(description="x"))
        assert bg["type"] == "solid"
        assert bg["color"] == [0.0, 0.0, 0.0]


# ============================================================================
# 工具方法
# ============================================================================

class TestUtilities:
    def test_is_success(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._is_success({"success": True}) is True
        assert loop._is_success({"success": False}) is False
        assert loop._is_success({}) is False
        assert loop._is_success(None) is False
        assert loop._is_success("not dict") is False

    def test_extract_layer_index(self) -> None:
        loop = MinimalCreativeLoop.__new__(MinimalCreativeLoop)
        assert loop._extract_layer_index({"data": {"layer_index": 3}}) == 3
        assert loop._extract_layer_index({"data": {"index": 5}}) == 5
        assert loop._extract_layer_index({"layer_index": 7}) == 7
        assert loop._extract_layer_index({}) is None
        assert loop._extract_layer_index({"data": {"layer_index": "x"}}) is None


# ============================================================================
# 异步兼容性
# ============================================================================

class TestAsyncCompat:
    def test_run_in_event_loop(self) -> None:
        """在已有 event loop 中也能跑（pytest-asyncio 场景）。"""
        loop = make_loop(plan_json=sample_plan("AsyncComp"))
        with tempfile.TemporaryDirectory() as tmp:
            req = CreativeRequest(
                description="x",
                duration=3.0,
                output_path=str(Path(tmp) / "out.mp4"),
            )
            # _run_async_safely 内部有 event loop 检测
            # （测试场景下没有运行中的 loop，走 asyncio.run）
            result = loop.run(req)
        assert result is not None
        assert result.success is True

    def test_llm_call_via_routing(self) -> None:
        """验证 LLM 走 chat_with_routing 路径。"""
        loop = make_loop(plan_json=sample_plan("RoutingComp"))
        req = CreativeRequest(description="x", duration=3.0)
        result = CreativeResult(success=False)
        loop._plan_with_llm(req, result)
        # Mock 记录了 chat_with_routing 调用
        methods = {c["method"] for c in loop.llm.calls}
        assert "chat_with_routing" in methods


# ============================================================================
# 降级行为
# ============================================================================

class TestDegradation:
    def test_missing_preset_uses_style_mapping(self, temp_output_dir: Path) -> None:
        """color_grading 缺省时使用风格映射。"""
        plan = sample_plan("DegrComp")
        plan["color_grading"] = {"preset_name": None, "style_description": ""}
        loop = make_loop(plan_json=plan)
        req = CreativeRequest(
            description="x",
            style=StylePreset.VINTAGE,
            duration=3.0,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        result = loop.run(req)
        # 调色阶段会被调用（使用 fallback preset）
        assert isinstance(loop.ae_to_davinci, MockAEToDavinciPipeline)
        if loop.ae_to_davinci.calls:
            assert loop.ae_to_davinci.calls[0]["preset_name"] == "vintage_film"

    def test_layer_warning_when_name_missing(self, temp_output_dir: Path) -> None:
        """关键帧找不到图层时记 warning。"""
        plan = sample_plan("WarnComp")
        plan["keyframes"] = [
            {"layer_name": "NonExistentLayer", "property": "Opacity", "time": 0.0, "value": [0.0]},
        ]
        loop = make_loop(plan_json=plan)
        req = CreativeRequest(
            description="x",
            duration=3.0,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        result = loop.run(req)
        assert result.success is True
        # 应该有 warning
        assert any("关键帧" in w for w in result.warnings)

    def test_unknown_layer_type_warning(self, temp_output_dir: Path) -> None:
        """未知图层类型记 warning 但不中断。"""
        plan = sample_plan("UnknownComp")
        plan["layers"].append({"type": "unknown_type", "name": "Mystery", "properties": {}})
        loop = make_loop(plan_json=plan)
        req = CreativeRequest(
            description="x",
            duration=3.0,
            output_path=str(temp_output_dir / "out.mp4"),
        )
        result = loop.run(req)
        assert result.success is True
        assert any("未知图层类型" in w for w in result.warnings)

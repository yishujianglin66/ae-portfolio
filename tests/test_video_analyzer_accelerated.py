"""AcceleratedVideoAnalyzer 回归测试。

覆盖两个曾在生产中真实存在、且被端到端验证捕获的缺陷：

1. `_ae_params(result)` 被放在 transitions / color_features /
   motion_features / visual_effects 写入 `result` 之前调用，
   导致 AE 参数除 composition 外恒为空列表，AE 参数生成功能实际失效。

2. spawn 式进程池在调用方缺少 `if __name__ == "__main__":` 保护时
   会递归重启 __main__，表现为分析被重复执行。库代码不应把该约束
   转嫁给调用方，需要能自动降级为线程池。
"""
import os
import sys
import textwrap
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.video_analyzer_accelerated import AcceleratedVideoAnalyzer  # noqa: E402


class TestAEParamsAssembly(unittest.TestCase):
    """AE 参数必须基于已完成的分析结果生成"""

    def setUp(self):
        self.analyzer = AcceleratedVideoAnalyzer(enable_cache=False)

    def _analysis_fixture(self):
        return {
            "basic_info": {
                "width": 1920, "height": 1080, "fps": 30.0, "duration": 12.0,
            },
            "color_features": {
                "ae_lumetri_params": {"temperature": -5.6, "contrast": 27.7},
            },
            "transitions": [
                {
                    "time_sec": 2.5, "type": "zoom_in", "ae_effect": "Transform",
                    "ae_params": {"property": "scale", "from": 100, "to": 130},
                },
                {
                    "time_sec": 7.0, "type": "fade", "ae_effect": "Opacity",
                    "ae_params": {"property": "opacity", "from": 0, "to": 100},
                },
            ],
            "motion_features": {
                "camera_motion": "持续缩放进入",
                "speed_changes": [
                    {
                        "time_sec": 4.0, "type": "speed_up",
                        "ae_params": {"rate": 2.0},
                    },
                ],
            },
            "visual_effects": {
                "detected_effects": [
                    {
                        "type": "flash", "name": "闪黑", "time_sec": 7.174,
                        "ae_effect": "亮度闪白/闪黑",
                        "ae_params": {"property": "brightness", "value": -100},
                    },
                    {
                        "type": "shake", "name": "抖动", "time_sec": 9.0,
                        "ae_effect": "Wiggle",
                        "ae_params": {
                            "property": "position",
                            "expression": "wiggle(5, 20)",
                        },
                    },
                ],
            },
        }

    def test_composition_uses_basic_info(self):
        out = self.analyzer._ae_params(self._analysis_fixture())

        self.assertEqual(out["composition"]["width"], 1920)
        self.assertEqual(out["composition"]["height"], 1080)
        self.assertEqual(out["composition"]["fps"], 30.0)
        self.assertEqual(out["composition"]["duration"], 12.0)

    def test_adjustment_layer_from_color_features(self):
        out = self.analyzer._ae_params(self._analysis_fixture())

        self.assertEqual(len(out["adjustment_layers"]), 1)
        layer = out["adjustment_layers"][0]
        self.assertEqual(layer["effect"], "Lumetri Color")
        self.assertEqual(layer["params"]["contrast"], 27.7)

    def test_effects_from_transitions_and_visual_effects(self):
        out = self.analyzer._ae_params(self._analysis_fixture())

        # 2 个转场 + 1 个非表达式类视觉效果（闪黑）
        self.assertEqual(len(out["effects"]), 3)
        names = [e["name"] for e in out["effects"]]
        self.assertTrue(any("zoom_in" in n for n in names))
        self.assertTrue(any("闪黑" in n for n in names))

    def test_expression_effects_go_to_expressions(self):
        out = self.analyzer._ae_params(self._analysis_fixture())

        self.assertEqual(len(out["expressions"]), 1)
        self.assertEqual(out["expressions"][0]["expression"], "wiggle(5, 20)")

    def test_keyframes_from_speed_changes_and_camera_motion(self):
        out = self.analyzer._ae_params(self._analysis_fixture())

        # 1 个速度变化 + 1 个持续缩放
        self.assertEqual(len(out["keyframes"]), 2)
        props = {k.get("property") for k in out["keyframes"]}
        self.assertIn("timeRemap", props)
        self.assertIn("scale", props)

    def test_empty_analysis_yields_empty_lists_not_crash(self):
        out = self.analyzer._ae_params({})

        self.assertEqual(out["adjustment_layers"], [])
        self.assertEqual(out["effects"], [])
        self.assertEqual(out["keyframes"], [])
        self.assertEqual(out["expressions"], [])
        # 缺少 basic_info 时使用安全默认值
        self.assertEqual(out["composition"]["width"], 1920)

    def test_ae_params_called_after_result_fields_assigned(self):
        """回归：analyze_video 必须先填充分析字段再生成 AE 参数。

        历史缺陷是 `ae_params = self._ae_params(result)` 出现在
        `result["transitions"] = ...` 等赋值之前，读到的永远是空值。
        这里直接对源码做顺序断言，避免依赖真实视频素材。
        """
        import inspect

        source = inspect.getsource(AcceleratedVideoAnalyzer.analyze_video)

        idx_ae = source.index("self._ae_params(result)")
        for field in (
            'result["transitions"]',
            'result["color_features"]',
            'result["motion_features"]',
            'result["visual_effects"]',
        ):
            self.assertLess(
                source.index(field), idx_ae,
                f"{field} 必须在 _ae_params(result) 之前赋值，否则 AE 参数恒为空",
            )


class TestSpawnSafetyDetection(unittest.TestCase):
    """spawn 安全判定：缺少 main guard 的调用方必须降级为线程池"""

    def test_interactive_main_is_safe(self):
        """交互式解释器 / python -c 没有可重新导入的脚本体"""
        main_mod = sys.modules.get("__main__")
        original = getattr(main_mod, "__file__", None)
        try:
            if hasattr(main_mod, "__file__"):
                del main_mod.__file__
            self.assertTrue(AcceleratedVideoAnalyzer._spawn_is_safe())
        finally:
            if original is not None:
                main_mod.__file__ = original

    def test_script_with_main_guard_is_safe(self):
        self._assert_spawn_safety(
            textwrap.dedent(
                """
                def run():
                    return 1

                if __name__ == "__main__":
                    run()
                """
            ),
            expected=True,
        )

    def test_script_without_main_guard_is_unsafe(self):
        self._assert_spawn_safety(
            textwrap.dedent(
                """
                from core.video_analyzer_accelerated import AcceleratedVideoAnalyzer

                AcceleratedVideoAnalyzer().analyze_video("x.mp4")
                """
            ),
            expected=False,
        )

    def test_missing_main_file_is_unsafe(self):
        main_mod = sys.modules.get("__main__")
        original = getattr(main_mod, "__file__", None)
        try:
            main_mod.__file__ = os.path.join(
                PROJECT_ROOT, "__definitely_missing_main__.py"
            )
            self.assertFalse(AcceleratedVideoAnalyzer._spawn_is_safe())
        finally:
            if original is None:
                del main_mod.__file__
            else:
                main_mod.__file__ = original

    def _assert_spawn_safety(self, script_source: str, expected: bool):
        import tempfile

        main_mod = sys.modules.get("__main__")
        original = getattr(main_mod, "__file__", None)
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        )
        try:
            tmp.write(script_source)
            tmp.close()
            main_mod.__file__ = tmp.name
            self.assertEqual(AcceleratedVideoAnalyzer._spawn_is_safe(), expected)
        finally:
            if original is None:
                if hasattr(main_mod, "__file__"):
                    del main_mod.__file__
            else:
                main_mod.__file__ = original
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()

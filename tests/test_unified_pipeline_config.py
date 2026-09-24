# -*- coding: utf-8 -*-
"""unified_pipeline 配置校验层特征化测试（2026-09-22）。

背景：`pipeline/unified_pipeline.py` 未覆盖 1480 行（23.84%，全仓最大单点）。
编排主体需要真实引擎，但其**配置校验与钳制层**是完全可测的纯逻辑，且实现里
的 docstring 直接记录了三个历史缺陷 —— 测试正好把这些修复钉住：

  1. `max_quality_iterations = 0/负数` → 主循环 `range(0)` 一次不执行，
     **静默无输出**（用户在无报错的情况下拿不到任何东西）；
  2. 浮点（如 2.7）→ `range(float)` 抛 TypeError 崩溃；
  3. 超大值（如 100）→ 外层主循环白烧资源。

另锁：`detect_mode()` 三分支、`StageResult` 时间戳自填、`to_dict` 字段面。
并如实记录一处**大小写不一致**的既有行为（见 TestVisualJudgeEnums）。
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from pipeline.unified_pipeline import (  # noqa: E402
    PipelineConfig,
    PipelineMode,
    PipelineResult,
    StageResult,
    StageStatus,
)


# ---------------------------------------------------------------------------
# 枚举与数据类
# ---------------------------------------------------------------------------

class TestEnumsAndDataclasses:
    def test_stage_status_values(self):
        assert [s.value for s in StageStatus] == [
            "pending", "running", "done", "failed", "skipped"]

    def test_pipeline_mode_values(self):
        assert [m.value for m in PipelineMode] == [
            "text_topic", "reference_video", "mixed"]

    def test_stage_result_timestamp_autofilled(self):
        r = StageResult(stage="s1", status=StageStatus.PENDING)
        assert r.timestamp and r.data == {} and r.error == ""
        assert r.duration_sec == 0.0


# ---------------------------------------------------------------------------
# detect_mode
# ---------------------------------------------------------------------------

class TestDetectMode:
    """⚠️ 断言按 `.value` 比较，不用 `is`（套件级顺序耦合陷阱）。

    2026-09-22 定位：`tests/test_formal_spec.py:200` 为验证"绑定幂等"会执行
    `importlib.reload(pipeline.unified_pipeline)`。reload 在**原模块对象上重新
    执行代码、换掉全部类对象**，于是：

      · 本测试模块在**收集期**绑定的 `PipelineMode` 是旧类；
      · `detect_mode()` 的方法体引用模块全局，reload 后指向**新**类；
      · 两者同名同值但 `is` 不等 → 单独跑全绿、与 test_formal_spec 同跑必红。

    按值比较对 reload 免疫，也不依赖测试执行顺序。
    """

    def test_topic_only(self):
        assert PipelineConfig(input_topic="猫").detect_mode().value == "text_topic"

    def test_video_only(self):
        assert PipelineConfig(reference_video="r.mp4").detect_mode().value \
            == "reference_video"

    def test_both_is_mixed(self):
        cfg = PipelineConfig(input_topic="猫", reference_video="r.mp4")
        assert cfg.detect_mode().value == "mixed"

    def test_neither_defaults_to_text_topic(self):
        """两者都空时落 TEXT_TOPIC（而非报错）—— 调用方依赖该默认分支。"""
        assert PipelineConfig().detect_mode().value == "text_topic"


# ---------------------------------------------------------------------------
# 注：`max_quality_iterations` 与 `min_quality_score` 的钳制**不在此重复** ——
# `tests/test_pipeline_config_validation.py`（14 项）已完整断言：0/负数→1、
# False→3、浮点→2、数字串/非法串/None、超大→5、区间内保值、主循环 int 契约，
# 以及质量分的负值/超 100/非法类型/bool 回退。本文件只补它**没覆盖**的部分
# （语义权重、视觉评判三项、detect_mode、to_dict、数据类）。
# 度量印证：本轮全量实测 unified_pipeline 未覆盖仅 1480→1475（在 ±15 行噪声带内），
# 即该层早已被覆盖 —— 与第二轮 llm_gateway 是同一类重复，故按"只留独有断言"处理。
# ---------------------------------------------------------------------------


class TestSemanticWeightClamp:
    @pytest.mark.parametrize("raw,expected", [
        (-1, 0.0), (0, 0.0), (0.6, 0.6), (1, 1.0), (2.5, 1.0),
        ("0.5", 0.5), ("x", 0.6), (None, 0.6),
    ])
    def test_clamped_to_0_1(self, raw, expected):
        assert PipelineConfig(semantic_score_weight=raw).semantic_score_weight == pytest.approx(expected)

    def test_bool_falls_back_to_default(self):
        assert PipelineConfig(semantic_score_weight=True).semantic_score_weight == 0.6


class TestVisualJudgeClamp:
    @pytest.mark.parametrize("raw,expected", [
        (-5, 0.0), (60, 60.0), (200, 100.0), ("80", 80.0), ("bad", 60.0), (None, 60.0),
    ])
    def test_min_score_clamped_0_100(self, raw, expected):
        assert PipelineConfig(visual_judge_min_score=raw).visual_judge_min_score == expected

    @pytest.mark.parametrize("raw,expected", [
        ("auto", "auto"), ("vlm", "vlm"), ("rule", "rule"),
        ("bogus", "auto"), ("", "auto"),
    ])
    def test_backend_whitelist(self, raw, expected):
        assert PipelineConfig(visual_judge_backend=raw).visual_judge_backend == expected

    @pytest.mark.parametrize("raw,expected", [
        ("none", "none"), ("4bit", "4bit"), ("auto", "auto"),
        ("8bit", "auto"), ("", "auto"),
    ])
    def test_quantize_whitelist(self, raw, expected):
        assert PipelineConfig(visual_judge_quantize=raw).visual_judge_quantize == expected


class TestVisualJudgeEnums:
    def test_backend_case_is_preserved_when_valid(self):
        """既有行为（如实记录）：白名单校验用 lower() 判等，但**不回写小写**，
        于是 "AUTO" 通过校验并原样保留。消费方若做大小写敏感比较需注意。

        这里锁住现状而非"修正"它 —— 改成回写小写会改变配置语义（外部按原值比对）。
        """
        assert PipelineConfig(visual_judge_backend="AUTO").visual_judge_backend == "AUTO"
        assert PipelineConfig(visual_judge_quantize="4BIT").visual_judge_quantize == "4BIT"


# ---------------------------------------------------------------------------
# to_dict 字段面
# ---------------------------------------------------------------------------

class TestToDict:
    def test_config_to_dict_covers_all_fields(self):
        c = PipelineConfig()
        d = c.to_dict()
        assert len(d) == len(vars(c))
        assert d["render_format"] == "h264" and d["enable_vrs"] is True
        assert d["max_quality_iterations"] == 3

    def test_result_to_dict_has_core_keys(self):
        r = PipelineResult(run_id="R1", status="success")
        d = r.to_dict()
        for k in ("run_id", "status", "mode", "stages", "output_path",
                  "quality_score", "errors"):
            assert k in d, k
        assert d["run_id"] == "R1" and d["stages"] == {}

    def test_result_defaults(self):
        r = PipelineResult(run_id="R2", status="partial")
        assert r.iterations == 0 and r.errors == [] and r.render_engine == ""

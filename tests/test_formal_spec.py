import logging

import pytest

from core.formal_spec import (
    AERenderTimeout,
    FFmpegParamBoundary,
    FanPositionConstraint,
    InvariantViolation,
    check_invariants,
)


# ============================================================================
# 原有合法测试（保留）
# ============================================================================

def test_fan_position_constraint_pass():
    check_invariants({"ae_layers": [{"type": "fan_blade", "position": (0, 0), "rotation": 90}]})


def test_fan_position_constraint_fail():
    with pytest.raises(InvariantViolation):
        check_invariants({"ae_layers": [{"type": "fan_blade", "position": (961, 0)}]})


def test_ffmpeg_param_boundary_pass():
    check_invariants({"ffmpeg_params": {"bitrate": 10_000_000, "framerate": 30}})


def test_ffmpeg_param_boundary_fail():
    with pytest.raises(InvariantViolation):
        check_invariants({"ffmpeg_params": {"bitrate": 50_000_001, "framerate": 30}})


def test_ae_render_timeout_pass():
    check_invariants({"ae_render_time_ms": 30_000})


def test_ae_render_timeout_fail():
    with pytest.raises(InvariantViolation):
        check_invariants({"ae_render_time_ms": 30_001})


def test_multiple_invariants():
    context = {
        "ae_layers": [{"type": "fan_blade", "position": (10, 10), "rotation": 10}],
        "ffmpeg_params": {"bitrate": 1_000_000, "framerate": 24},
        "ae_render_time_ms": 100,
    }
    check_invariants(context)


def test_invariant_violation_raise():
    with pytest.raises(InvariantViolation, match="AERenderTimeout"):
        check_invariants({"ae_render_time_ms": 30_001})


def test_skip_invariants():
    check_invariants({"ae_render_time_ms": 999_999}, skip=True)


def test_invariant_classes_have_expected_names():
    assert FanPositionConstraint().name == "FanPositionConstraint"
    assert FFmpegParamBoundary().name == "FFmpegParamBoundary"
    assert AERenderTimeout().name == "AERenderTimeout"


# ============================================================================
# Phase C 修复新增测试
# ============================================================================

def test_empty_context_no_raise(caplog):
    """C1/M1: 空 context 不抛异常（走缺字段告警路径）。"""
    with caplog.at_level(logging.WARNING, logger="core.formal_spec"):
        check_invariants({})  # 不应抛 InvariantViolation
    assert any("未提供" in r.message for r in caplog.records)


def test_non_fan_blade_layer_skipped():
    """C1: 非 fan_blade 图层被跳过（含越界位置也不触发）。"""
    check_invariants({
        "ae_layers": [
            {"type": "text", "position": (9999, 9999)},
            {"type": "solid", "position": (5000, -5000)},
        ],
    })


def test_type_mixing_normalized():
    """H1/H2: 类型混用不抛 TypeError，行为符合归一化语义。"""
    # rotation 字符串、position None/字符串均归一化
    check_invariants({
        "ae_layers": [
            {"type": "fan_blade", "rotation": "90"},
            {"type": "fan_blade", "position": None},
            {"type": "fan_blade", "position": "10,20"},
        ],
        # bitrate/framerate 字符串形态
        "ffmpeg_params": {"bitrate": "20M", "framerate": "30"},
        "ae_render_time_ms": "1000",
    })


def test_rotation_boundary_normalized():
    """M4: rotation 负角度/超 360 归一化后通过。"""
    # -45 % 360 = 315, 450 % 360 = 90, 均在 [0, 360)
    check_invariants({
        "ae_layers": [
            {"type": "fan_blade", "position": (0, 0), "rotation": -45},
            {"type": "fan_blade", "position": (0, 0), "rotation": 450},
            {"type": "fan_blade", "position": (0, 0), "rotation": 360},
        ],
    })


def test_bitrate_boundary():
    """H2: bitrate 边界与后缀字符串形态。"""
    # 恰 50_000_000 通过, 50_000_001 违规
    check_invariants({"ffmpeg_params": {"bitrate": 50_000_000, "framerate": 30}})
    with pytest.raises(InvariantViolation, match="50 Mbps"):
        check_invariants({"ffmpeg_params": {"bitrate": 50_000_001, "framerate": 30}})
    # "20M" 通过, "51M" 违规
    check_invariants({"ffmpeg_params": {"bitrate": "20M", "framerate": 30}})
    with pytest.raises(InvariantViolation, match="50 Mbps"):
        check_invariants({"ffmpeg_params": {"bitrate": "51M", "framerate": 30}})
    # "192k" 通过; "20m" 大小写不敏感
    check_invariants({"ffmpeg_params": {"bitrate": "192k", "framerate": 30}})
    check_invariants({"ffmpeg_params": {"bitrate": "20m", "framerate": 30}})
    # 无法解析 → 违规而非抛异常
    with pytest.raises(InvariantViolation, match="码率无法解析"):
        check_invariants({"ffmpeg_params": {"bitrate": "abc", "framerate": 30}})


def test_framerate_boundary():
    """H1: framerate 边界。"""
    check_invariants({"ffmpeg_params": {"bitrate": 1_000_000, "framerate": 23.976}})
    with pytest.raises(InvariantViolation, match="帧率越界"):
        check_invariants({"ffmpeg_params": {"bitrate": 1_000_000, "framerate": 23.975}})
    check_invariants({"ffmpeg_params": {"bitrate": 1_000_000, "framerate": 120}})
    with pytest.raises(InvariantViolation, match="帧率越界"):
        check_invariants({"ffmpeg_params": {"bitrate": 1_000_000, "framerate": 120.5}})


def test_multi_violation_aggregated():
    """M2: 多重违规聚合 — 异常消息同时包含两个不变量名。"""
    context = {
        "ae_layers": [{"type": "fan_blade", "position": (961, 0)}],
        "ffmpeg_params": {"bitrate": 60_000_000, "framerate": 30},
    }
    with pytest.raises(InvariantViolation) as exc_info:
        check_invariants(context)
    msg = str(exc_info.value)
    assert "FanPositionConstraint" in msg
    assert "FFmpegParamBoundary" in msg


def test_ae_render_time_missing_no_raise(caplog):
    """M1: ae_render_time_ms 缺失时不抛异常，并发出 warning。"""
    with caplog.at_level(logging.WARNING, logger="core.formal_spec"):
        check_invariants({"ffmpeg_params": {"bitrate": 1_000_000, "framerate": 30}})
    assert any(
        "ae_render_time_ms 未提供" in r.message for r in caplog.records
    )


def test_binding_integration(tmp_path, monkeypatch):
    """C2: 不变量违规 → StageResult(FAILED)，不裸抛（run_stage 集成）。"""
    import pipeline.unified_pipeline as up

    monkeypatch.chdir(tmp_path)
    pipe = up.UnifiedPipeline(up.PipelineConfig())
    pipe._persist_dir = tmp_path  # 避免写入真实 data/pipeline_runs

    def fake_execute(self):
        # 假 execute 阶段：产出越界 ae_layers（触发 FanPositionConstraint 违规）
        return {"ae_layers": [{"type": "fan_blade", "position": (961, 0)}]}

    monkeypatch.setattr(up.UnifiedPipeline, "_run_execute", fake_execute)

    result = pipe.run_stage("execute")
    assert isinstance(result, up.StageResult)
    assert result.status == up.StageStatus.FAILED
    assert "FanPositionConstraint" in result.error
    assert result.error.startswith("[invariants]")


def test_binding_idempotent():
    """M3: 绑定幂等 — importlib.reload 二次加载仍为单层包装。"""
    import importlib

    import pipeline.unified_pipeline as up

    # 首次绑定状态: _run_stage 是包装器, _legacy_run_stage 是原始实现
    assert up.UnifiedPipeline._legacy_run_stage_stored is True
    assert up.UnifiedPipeline._run_stage.__name__ == "_run_stage_with_invariants"
    assert up.UnifiedPipeline._legacy_run_stage.__name__ == "_run_stage"
    assert up.UnifiedPipeline._legacy_run_stage is not up.UnifiedPipeline._run_stage

    # 模拟重复执行绑定区代码（importlib.reload 重新执行整个模块）
    up = importlib.reload(up)

    # 二次绑定后仍是单层包装（不递归、不双日志）:
    # _run_stage 仍为包装器, _legacy_run_stage 仍为原始实现而非包装器
    assert up.UnifiedPipeline._legacy_run_stage_stored is True
    assert up.UnifiedPipeline._run_stage.__name__ == "_run_stage_with_invariants"
    assert up.UnifiedPipeline._legacy_run_stage.__name__ == "_run_stage"
    assert up.UnifiedPipeline._legacy_run_stage is not up.UnifiedPipeline._run_stage


def test_stage_data_contract(tmp_path, monkeypatch):
    """C1: 阶段结果 data 经包装器补齐后含不变量所需字段（数据契约）。"""
    import pipeline.unified_pipeline as up

    monkeypatch.chdir(tmp_path)
    pipe = up.UnifiedPipeline(up.PipelineConfig())

    # execute: 无结构化 ae_layers → 空列表占位（字段存在）
    exe = up.StageResult(
        stage="execute", status=up.StageStatus.DONE,
        data={"project_path": "x.mp4", "layers_created": 2},
    )
    pipe._attach_stage_invariant_data("execute", exe)
    assert "ae_layers" in exe.data
    assert exe.data["ae_layers"] == []

    # render: ffmpeg_params（真实引擎参数映射, bps 整数）+ ae_render_time_ms（实测换算）
    ren = up.StageResult(
        stage="render", status=up.StageStatus.DONE,
        data={"output_path": "y.mp4", "render_engine": "ffmpeg", "render_time_sec": 12.5},
    )
    pipe._attach_stage_invariant_data("render", ren)
    assert ren.data["ffmpeg_params"]["bitrate"] == 4_000_000
    assert ren.data["ffmpeg_params"]["framerate"] == 30
    assert ren.data["ae_render_time_ms"] == 12_500

    # render 缺 render_time_sec（如 quality_passthrough 未实测）→ 不写 ae_render_time_ms，
    # 保持缺字段由不变量告警（区分"未测量"与"真实值"）
    ren2 = up.StageResult(
        stage="render", status=up.StageStatus.DONE,
        data={"output_path": "z.mp4", "render_mode": "quality_passthrough"},
    )
    pipe._attach_stage_invariant_data("render", ren2)
    assert "ffmpeg_params" in ren2.data
    assert "ae_render_time_ms" not in ren2.data


def test_missing_field_warning(caplog):
    """C1/M1: check_invariants 在缺字段时发出 warning（非静默通过）。"""
    with caplog.at_level(logging.WARNING, logger="core.formal_spec"):
        check_invariants({})
    messages = [r.message for r in caplog.records]
    assert any("ae_layers" in m and "未提供" in m for m in messages)
    assert any("ffmpeg_params" in m and "未提供" in m for m in messages)
    assert any("ae_render_time_ms" in m and "未提供" in m for m in messages)

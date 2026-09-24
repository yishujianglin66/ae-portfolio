# -*- coding: utf-8 -*-
"""look_at 相机阶段固化测试（2026-09-20）。

台账曾写"look_at 相机正立已突破；待固化进引擎"，但核实发现：仓库里只有孤立桩
（标志硬编码、两个函数从未被调用）+ 认证桩的测试，`puppet/output/` 为空。
本测试锁住"固化"后的**引擎侧契约**：

  1. 目标点由 MediaPipe 归一化 bbox 中心换算到 AE 3D 空间（含非居中用例）
  2. 检测降级（无 bbox）→ 回退原点单目标，且如实标注 degraded
  3. 输出目录越界 → 优雅拒绝，不抛异常、不写文件
  4. 产物落盘（camera_plan.json / camera_setup.jsx）且 JSX 不写自定义旋转
  5. 阶段永不因异常中断主流程（相机失败 = 该阶段失败，其他阶段照常）
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from puppet.puppet_workflow_orchestrator import (  # noqa: E402
    PuppetWorkflowOrchestrator,
    WorkflowConfig,
)


@pytest.fixture()
def stage_runner(tmp_path):
    """绕开重型 __init__，只装 config —— 相机阶段不依赖 auto_processor。"""
    orch = object.__new__(PuppetWorkflowOrchestrator)
    orch.config = WorkflowConfig(camera_radius=900.0, camera_height_offset=150.0)
    return orch, tmp_path


def _plan(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "camera_plan.json").read_text(encoding="utf-8"))


def test_centered_bbox_maps_to_origin(stage_runner):
    orch, tmp = stage_runner
    st = orch._stage_camera_setup(
        {"width": 1920, "height": 1080, "bbox": [0.3, 0.2, 0.7, 0.8]}, str(tmp))
    assert st.success and st.data["total_setups"] == 1
    poi = _plan(tmp)["setups"][0]["point_of_interest"]
    assert poi[0] == pytest.approx(0.0) and poi[1] == pytest.approx(0.0)


def test_offcenter_bbox_maps_with_axis_conversion(stage_runner):
    """2D 合成坐标 → AE 3D：x 右为正，y **向上**为正（2D 的 y 是向下的）。"""
    orch, tmp = stage_runner
    # bbox 偏左上：cx=0.3 → x<0；cy=0.2 → y>0（屏幕上方 = 3D 正 Y）
    st = orch._stage_camera_setup(
        {"width": 1000, "height": 500, "bbox": [0.2, 0.1, 0.4, 0.3]}, str(tmp))
    assert st.success
    poi = _plan(tmp)["setups"][0]["point_of_interest"]
    assert poi[0] == pytest.approx((0.3 - 0.5) * 1000)      # -200
    assert poi[1] == pytest.approx((0.5 - 0.2) * 500)       # +150（向上）
    assert poi[0] < 0 and poi[1] > 0


def test_bbox_dict_form_supported(stage_runner):
    orch, tmp = stage_runner
    st = orch._stage_camera_setup(
        {"width": 800, "height": 600, "bbox": {"x": 0.5, "y": 0.25, "w": 0.2, "h": 0.5}},
        str(tmp))
    assert st.success
    poi = _plan(tmp)["setups"][0]["point_of_interest"]
    assert poi[0] == pytest.approx((0.6 - 0.5) * 800)
    assert poi[1] == pytest.approx((0.5 - 0.5) * 600)


def test_degraded_without_bbox_falls_back_to_origin(stage_runner):
    orch, tmp = stage_runner
    st = orch._stage_camera_setup({}, str(tmp))
    assert st.success and st.data["degraded"] is True
    assert "降级" in st.error
    assert _plan(tmp)["setups"][0]["point_of_interest"] == [0.0, 0.0, 0.0]


def test_outside_project_dir_is_refused(stage_runner):
    """越界输出目录 → 优雅拒绝（不抛异常、不写文件）。"""
    orch, _ = stage_runner
    st = orch._stage_camera_setup({"bbox": [0.1, 0.1, 0.9, 0.9]},
                                  r"C:\Windows\Temp\aekv_should_not_write")
    assert st.success is False
    assert "项目外" in st.error


def test_artifacts_written_and_upright(stage_runner):
    orch, tmp = stage_runner
    st = orch._stage_camera_setup(
        {"width": 1920, "height": 1080, "bbox": [0.1, 0.1, 0.9, 0.9]}, str(tmp))
    assert st.success and st.data["all_upright"] is True
    assert (tmp / "camera_plan.json").exists()
    assert (tmp / "camera_setup.jsx").exists()
    assert st.data["max_horizon_dev_deg"] < 1e-6


def test_generated_jsx_has_no_custom_rotation(stage_runner):
    """AE 由 POI 推导朝向；写自定义旋转会与之冲突产生滚转。"""
    orch, tmp = stage_runner
    orch._stage_camera_setup({"width": 1920, "height": 1080}, str(tmp))
    jsx = (tmp / "camera_setup.jsx").read_text(encoding="utf-8")
    assert "addCamera(" in jsx and ".pointOfInterest.setValue(" in jsx
    for banned in (".orientation.setValue(", ".xRotation.setValue(",
                   ".yRotation.setValue(", ".zRotation.setValue("):
        assert banned not in jsx


def test_stage_never_raises_on_bad_input(stage_runner):
    """异常输入不得抛出 —— 相机阶段失败不能中断整条流程。"""
    orch, tmp = stage_runner
    st = orch._stage_camera_setup({"bbox": "not-a-bbox", "width": "bad"}, str(tmp))
    assert isinstance(st.success, bool)          # 不抛异常即达标


def test_config_flags_exist_for_engine_wiring():
    """固化点的配置面：引擎可开关与调参。"""
    c = WorkflowConfig()
    assert c.camera_setup is True
    assert c.camera_radius > 0 and c.camera_height_offset >= 0

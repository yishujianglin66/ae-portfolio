"""木偶动画 look_at 相机正立 —— 真契约测试（2026-09-20 重写）。

初版把**桩实现当规格锁住**了：
  · 断言 `stabilize_camera_rotation` 对倾斜输入也返回常量 (0,1,0)（旧实现忽略入参）
  · 断言 `look_at_calculated == True`（旧实现硬编码该字段，两个函数都没被调用）
  · 断言 `center_point == [960, 540, 0]`（把 2D 图层坐标误用为 AE 3D 空间中心）
本测试改为验证**真实几何不变量**：正交归一、无滚转（地平线水平）、严格指向、
退化安全，以及"标志由实算派生"这一属性（用独立重算比对，而非信任字段）。
"""
import math
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from puppet.look_at_camera import (  # noqa: E402
    build_camera_jsx,
    calculate_look_at,
    create_3d_puppet_camera_setup,
    look_at_basis,
    stabilize_camera_rotation,
)

dot = lambda a, b: sum(x * y for x, y in zip(a, b))  # noqa: E731


class TestCalculateLookAt:
    """POI 语义（AE 用 pointOfInterest 定向，故 POI 就是目标点）"""

    def test_basic_look_at_returns_target(self):
        assert calculate_look_at((0, 0, -1000), (0, 0, 0)) == (0.0, 0.0, 0.0)

    def test_offset_target_returns_target(self):
        assert calculate_look_at((100, 100, -500), (200, 200, 0)) == (200.0, 200.0, 0.0)

    def test_rejects_non_3d(self):
        with pytest.raises(ValueError):
            calculate_look_at((0, 0), (0, 0, 0))


class TestStabilizeCameraRotation:
    """正立校正：把世界上方向投影到 ⟂视线 的平面"""

    def test_horizontal_forward_gives_world_up(self):
        assert stabilize_camera_rotation((0.0, 1.0, 0.0), (0.0, 0.0, -1.0)) == \
            (0.0, 1.0, 0.0)

    def test_tilted_input_up_is_ignored_by_design(self):
        """相机正立的定义 = 地平线水平，故结果只由 world_up 与 forward 决定。

        旧实现的"忽略入参"是巧合（它连 forward 也忽略）；本实现忽略的只是
        `camera_up_vector`（待校正量），且结果**必须**与 forward 严格垂直。
        """
        up = stabilize_camera_rotation((0.1, 0.99, 0.0), (0.0, 0.0, -1.0))
        assert up == (0.0, 1.0, 0.0)

    @pytest.mark.parametrize("forward", [
        (0.0, 0.6, -0.8),        # 仰拍 37°
        (0.0, -0.6, -0.8),       # 俯拍
        (0.5, 0.5, -0.7),        # 斜向
        (0.0, 0.99, -0.14),      # 接近竖直
    ])
    def test_tilted_forward_up_perpendicular_and_unit(self, forward):
        """关键回归：旧实现返回常量 (0,1,0)，仰/俯拍时与 forward 不垂直 → 基退化。"""
        up = stabilize_camera_rotation((0.0, 1.0, 0.0), forward)
        assert abs(dot(up, forward)) < 1e-9, "up 必须与视线垂直"
        assert abs(math.sqrt(dot(up, up)) - 1.0) < 1e-9, "up 必须单位长度"

    def test_vertical_forward_is_degenerate_safe(self):
        """正上方俯视：投影为零向量，必须走确定性回退且不返回 NaN。"""
        up = stabilize_camera_rotation((0.0, 1.0, 0.0), (0.0, 1.0, 0.0))
        assert all(not math.isnan(x) for x in up)
        assert abs(math.sqrt(dot(up, up)) - 1.0) < 1e-9
        assert abs(dot(up, (0.0, 1.0, 0.0))) < 1e-9


class TestLookAtBasis:
    """基向量不变量（可验证核心）"""

    @pytest.mark.parametrize("cam,target", [
        ((0, 0, -1000), (0, 0, 0)),
        ((800, 120, 0), (100, 100, 0)),
        ((0, 500, 0), (0, 0, 0)),            # 退化
        ((-300, -200, 400), (50, 50, 50)),
    ])
    def test_orthonormal_and_upright(self, cam, target):
        b = look_at_basis(cam, target)
        for name in ("forward", "right", "up"):
            v = b[name]
            assert all(not math.isnan(x) for x in v), name
            assert abs(math.sqrt(dot(v, v)) - 1.0) < 1e-9, name
        assert abs(dot(b["forward"], b["up"])) < 1e-9
        assert abs(dot(b["right"], b["up"])) < 1e-9
        assert abs(dot(b["right"], b["forward"])) < 1e-9
        # 无滚转 ⇒ right 落在水平面内 ⇒ 地平线偏差 0°
        assert abs(b["right_horizon_deg"]) < 1e-6

    def test_forward_aims_exactly_at_target(self):
        cam, target = (123.0, 45.0, -67.0), (-10.0, 200.0, 30.0)
        b = look_at_basis(cam, target)
        d = (target[0] - cam[0], target[1] - cam[1], target[2] - cam[2])
        length = math.sqrt(dot(d, d))
        unit = tuple(c / length for c in d)
        diff = tuple(a - u for a, u in zip(b["forward"], unit))
        assert math.sqrt(dot(diff, diff)) < 1e-12

    def test_elevation_sweep_roll_stays_zero(self):
        """绕目标一整圈、含多仰角：地平线偏差必须恒为 0（这是"正立"的定义）。"""
        target = (1.0, 2.0, 3.0)
        worst = 0.0
        for r in (150.0, 900.0):
            for el_deg in (-75, -40, 0, 40, 75):
                el = math.radians(el_deg)
                for k in range(12):
                    az = 2 * math.pi * k / 12
                    cam = (target[0] + r * math.cos(el) * math.cos(az),
                           target[1] + r * math.sin(el),
                           target[2] + r * math.cos(el) * math.sin(az))
                    worst = max(worst,
                                abs(look_at_basis(cam, target)["right_horizon_deg"]))
        assert worst < 1e-6, f"轨道扫掠出现滚转偏差 {worst}°"

    def test_rotation_matrix_is_orthonormal(self):
        b = look_at_basis((300, 100, 300), (0, 0, 0))
        R = b["rotation_matrix"]
        for i in range(3):
            for j in range(3):
                expected = 1.0 if i == j else 0.0
                assert abs(sum(R[i][k] * R[j][k] for k in range(3)) - expected) < 1e-9


class TestCreatePuppetCameraSetup:
    """布点与坐标约定"""

    def test_single_puppet(self):
        r = create_3d_puppet_camera_setup(1920, 1080, [(100, 100, 0)],
                                          camera_radius=500)
        assert r["total_setups"] == 1 and len(r["setups"]) == 1
        assert r["setups"][0]["look_at_calculated"] is True

    def test_multiple_puppets_each_upright(self):
        r = create_3d_puppet_camera_setup(
            1920, 1080, [(100, 100, 0), (200, 200, 50), (300, 150, -30)],
            camera_radius=800)
        assert r["total_setups"] == 3
        for s in r["setups"]:
            assert s["look_at_calculated"] is True
            assert s["rotation_stabilized"] is True
            assert abs(s["basis"]["right_horizon_deg"]) < 1e-6

    def test_center_point_is_ae_3d_origin(self):
        """AE 3D 合成中心就是原点；(w/2, h/2, 0) 是 2D 图层坐标（初版误用）。

        初版断言 center_point == [960, 540, 0]，那会让相机绕一个偏移中心公转，
        目标根本不在画面中心。现约定 center=(0,0,0)，可用参数显式覆盖。
        """
        r = create_3d_puppet_camera_setup(1920, 1080, [(0, 0, 0)])
        assert r["center_point"] == [0.0, 0.0, 0.0]
        assert r["frame"] == {"width": 1920, "height": 1080}

    def test_custom_center_respected(self):
        r = create_3d_puppet_camera_setup(1920, 1080, [(500, 0, 0)],
                                          camera_radius=100,
                                          center=(500.0, 0.0, 0.0))
        assert r["center_point"] == [500.0, 0.0, 0.0]

    def test_flags_are_derived_not_hardcoded(self):
        """标志必须与独立重算一致 —— 防止退回"硬编码 True"的旧缺陷。"""
        r = create_3d_puppet_camera_setup(1920, 1080, [(100, 100, 0), (200, 0, 0)],
                                          camera_radius=600, height_offset=80)
        for s in r["setups"]:
            b = s["basis"]
            ortho = (abs(dot(b["forward"], b["up"])) < 1e-6
                     and abs(dot(b["right"], b["up"])) < 1e-6
                     and abs(dot(b["right"], b["forward"])) < 1e-6)
            assert s["look_at_calculated"] == ortho
            assert s["rotation_stabilized"] == (
                ortho and abs(b["right_horizon_deg"]) < 1e-6)


class TestCameraJsx:
    """AE 侧落地：只设 position + pointOfInterest（AE 据此定向且无滚转）"""

    def test_jsx_sets_position_and_poi(self):
        r = create_3d_puppet_camera_setup(1920, 1080, [(100, 100, 0)],
                                          camera_radius=500)
        jsx = build_camera_jsx(r["setups"][0], "cam_a")
        assert "addCamera('cam_a'" in jsx
        assert "cam_a.threeDLayer = true;" in jsx
        assert ".position.setValue(" in jsx
        assert ".pointOfInterest.setValue(" in jsx
        # 不得写自定义旋转：会与 AE 自身由 POI 推导的朝向冲突而产生滚转
        assert ".orientation.setValue(" not in jsx
        assert ".xRotation.setValue(" not in jsx

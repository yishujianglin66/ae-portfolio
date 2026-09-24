"""木偶动画 look_at 相机正立 —— 实现 + 可验证不变量（2026-09-20 重写）。

背景（为什么重写）
------------------
本模块此前是**自称成功的桩**：`stabilize_camera_rotation()` 忽略入参直接返回
`(0, 1, 0)`；`create_3d_puppet_camera_setup()` 把 `look_at_calculated` /
`rotation_stabilized` 两个标志**硬编码为 True**，而那两个函数根本没被调用过；
仓库里也没有 docstring 宣称的"MP4 演示"产物（`puppet/output/` 为空）。
配套测试把桩当规格锁住了（断言倾斜上向量也返回 `(0,1,0)`、断言硬编码标志为
True）—— 与 filter_engine 特征化测试同一类病：**测试在认证"什么都没算"**。

本次改为真实现，并把"正立"变成可验证的不变量：
  · 相机基向量正交归一（forward/right/up）
  · **无滚转**：up 始终落在世界竖直平面内（roll ⇒ 0，地平线水平）
  · 退化输入（视线与世界上方向平行）不产生 NaN，且给出确定性回退
  · 轨道扫掠全程偏差有界（见 `puppet/puppet_look_at_verify.py`）

AE 侧落地方式（关键概念修正）
-----------------------------
AE 的 3D 相机沿**自身 -Z** 看；让它"看向目标且正立"的标准做法是设置
**Point of Interest（兴趣点）** —— AE 据此定向并保持 up = 合成上方向，天然无滚转。
故本模块输出以 (position, point_of_interest) 为主，辅以基向量与旋转矩阵供其它
后端（Blender/自研渲染）使用。

坐标约定：世界 up = +Y；AE 3D 合成中心即原点 (0,0,0)（**不是** (w/2, h/2, 0)
—— 后者是 2D 图层坐标；旧实现把两者混用，会让轨道绕错中心）。
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

WORLD_UP = (0.0, 1.0, 0.0)
EPS = 1e-9


# ---------------------------------------------------------------------------
# 向量工具（纯函数，无第三方依赖）
# ---------------------------------------------------------------------------

def _sub(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(v: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot(v, v))
    if length < EPS:
        raise ValueError(f"零向量无法归一化: {tuple(v)}")
    return (v[0] / length, v[1] / length, v[2] / length)


def _project_perp(v: Sequence[float], axis: Sequence[float]) -> tuple[float, float, float]:
    """把 v 投影到与 axis 垂直的平面。"""
    k = _dot(v, axis)
    return (v[0] - k * axis[0], v[1] - k * axis[1], v[2] - k * axis[2])


# ---------------------------------------------------------------------------
# 1) 兴趣点（AE 语义：POI 就是目标点）
# ---------------------------------------------------------------------------

def calculate_look_at(
    camera_position: Sequence[float],
    target_position: Sequence[float],
) -> tuple[float, float, float]:
    """计算 look_at 的 Point of Interest。

    对 AE 而言 POI **就是目标点本身**（AE 据此定向）—— 故保持这一语义，返回
    `target_position`。真正的"正立"由 `stabilize_camera_rotation` 与
    `look_at_basis` 保证，不再由空实现假装。
    """
    if len(camera_position) != 3 or len(target_position) != 3:
        raise ValueError("camera_position / target_position 必须是三维坐标")
    return (float(target_position[0]), float(target_position[1]),
            float(target_position[2]))


# ---------------------------------------------------------------------------
# 2) 正立校正：把世界上方向投影到与视线垂直的平面
# ---------------------------------------------------------------------------

def stabilize_camera_rotation(
    camera_up_vector: Sequence[float],
    camera_forward: Sequence[float],
    world_up: Sequence[float] = WORLD_UP,
) -> tuple[float, float, float]:
    """把相机上方向校正为**无滚转**方向（地平线水平）。

    做法：取世界上方向在"与视线垂直的平面"上的投影并归一化::

        up = normalize(world_up - (world_up · forward) * forward)

    语义：入参 `camera_up_vector` 是**待校正**的上向量（供诊断，不参与结果计算）；
    结果只由 world_up 与 forward 决定 —— 这正是"相机正立"的定义：无论木偶如何
    倾斜，地平线都水平。

    与旧实现的区别：旧版直接返回常量 (0,1,0)。当视线含竖直分量（仰拍/俯拍）时
    它与 forward **不垂直**，基向量退化，相机会出现不可预期的滚转。本实现返回与
    forward 严格垂直的上方向。

    退化保护：视线与 world_up 平行（正上/正下俯视）时投影为零向量，此时回退取
    与 forward 垂直的确定性方向，保证不返回 NaN。
    """
    f = _norm(camera_forward)
    proj = _project_perp(world_up, f)
    if math.sqrt(_dot(proj, proj)) < 1e-6:      # 视线 ∥ 世界上方向
        fallback = (0.0, 0.0, -1.0)
        if abs(_dot(f, fallback)) > 0.999:
            fallback = (1.0, 0.0, 0.0)
        proj = _project_perp(fallback, f)
    return _norm(proj)


# ---------------------------------------------------------------------------
# 3) 完整 look_at 基（可验证核心）
# ---------------------------------------------------------------------------

def look_at_basis(
    camera_position: Sequence[float],
    target_position: Sequence[float],
    world_up: Sequence[float] = WORLD_UP,
) -> dict:
    """由相机位置与目标点算出正交归一的 look_at 基（含正立诊断）。

    返回:
        forward          单位视线向量（cam → target）
        right            forward × up（单位）
        up               world_up 投影到 ⟂forward 平面并归一（⇒ 无滚转）
        degenerate       True 表示视线与世界上方向平行（已走回退分支）
        roll_deg         滚转量（无滚转 ⇒ 0.0）
        right_horizon_deg  right 与水平面的夹角；无滚转 ⇒ 0°（地平线水平）
        rotation_matrix  3×3 行主序 [right, up, -forward]
                         （世界轴 → 相机轴；AE 相机沿 -Z 看）
    """
    f = _norm(_sub(target_position, camera_position))
    perp = _project_perp(world_up, f)
    degenerate = math.sqrt(_dot(perp, perp)) < 1e-6
    up = stabilize_camera_rotation(WORLD_UP, f, world_up)
    right = _norm(_cross(f, up))
    up = _norm(_cross(right, f))              # 再正交一次，消除浮点残差
    # 无滚转判据：right 必须落在水平面内 ⇒ right · world_up == 0 ⇒ 夹角 0°
    horizon_deg = math.degrees(math.asin(max(-1.0, min(1.0, _dot(right, world_up)))))
    return {
        "forward": f,
        "right": right,
        "up": up,
        "degenerate": bool(degenerate),
        "roll_deg": float(abs(horizon_deg)),
        "right_horizon_deg": float(horizon_deg),
        "rotation_matrix": [list(right), list(up),
                            [-f[0], -f[1], -f[2]]],
    }


# ---------------------------------------------------------------------------
# 4) 木偶相机布点（AE 3D 约定修正 + 标志由实算派生）
# ---------------------------------------------------------------------------

def create_3d_puppet_camera_setup(
    comp_width: int,
    comp_height: int,
    puppet_positions: Iterable[Sequence[float]],
    camera_radius: float = 1000.0,
    *,
    center: Sequence[float] = (0.0, 0.0, 0.0),
    height_offset: float = 0.0,
    world_up: Sequence[float] = WORLD_UP,
) -> dict:
    """为每个木偶生成一台"看向它且正立"的相机设置。

    参数:
        comp_width/comp_height: 合成尺寸（记录在 frame 字段，供构图换算）
        puppet_positions:       木偶位置列表（AE 3D 空间坐标）
        camera_radius:          轨道半径
        center:                 轨道中心。**AE 3D 合成中心即原点 (0,0,0)**；
                                旧实现用 (w/2, h/2, 0) 是把 2D 图层坐标误当 3D
                                空间，相机会绕错中心（已修正，可用本参数覆盖）
        height_offset:          相机相对中心的竖直抬升（>0 略俯视，利于木偶感）
        world_up:               世界上方向

    返回:
        total_setups / center_point / frame / setups[…]；每个 setup 含
        camera_position、point_of_interest、basis（基 + 正立诊断），
        以及 look_at_calculated / rotation_stabilized —— 后两者**由实算派生**：
        仅当基向量正交归一且无滚转时才为 True（旧实现硬编码 True，属"声明与
        计算脱钩"，会让下游误信未经验证的状态）。
    """
    positions = [tuple(float(c) for c in p) for p in puppet_positions]
    setups: list[dict] = []
    n = max(1, len(positions))
    for i, pos in enumerate(positions):
        angle = (i / n) * 2.0 * math.pi
        cam = (center[0] + math.cos(angle) * camera_radius,
               center[1] + height_offset,
               center[2] + math.sin(angle) * camera_radius)
        poi = calculate_look_at(cam, pos)
        basis = look_at_basis(cam, poi, world_up)
        orthonormal = (
            abs(_dot(basis["forward"], basis["up"])) < 1e-6
            and abs(_dot(basis["right"], basis["up"])) < 1e-6
            and abs(_dot(basis["right"], basis["forward"])) < 1e-6
        )
        setups.append({
            "camera_position": cam,
            "point_of_interest": poi,
            "basis": basis,
            "look_at_calculated": bool(orthonormal),
            "rotation_stabilized": bool(orthonormal
                                        and abs(basis["right_horizon_deg"]) < 1e-6),
        })
    return {
        "total_setups": len(setups),
        "setups": setups,
        "center_point": [float(c) for c in center],
        "frame": {"width": int(comp_width), "height": int(comp_height)},
    }


# ---------------------------------------------------------------------------
# 5) ExtendScript 片段（AE 侧落地：位置 + 兴趣点 ⇒ 看向目标且正立）
# ---------------------------------------------------------------------------

def build_camera_jsx(setup: dict, camera_name: str = "puppet_cam") -> str:
    """把一套相机设置转成 ExtendScript 片段。

    只设 position 与 pointOfInterest —— 这是 AE 里"看向目标且保持正立"的标准
    做法（AE 由 POI 推导朝向，up 保持合成上方向 ⇒ 无滚转）。不写自定义旋转，
    以免与 AE 自身推导冲突产生滚转。
    """
    b = setup["basis"]
    cam = setup["camera_position"]
    poi = setup["point_of_interest"]
    return "\n".join([
        f"// look_at 正立相机 {camera_name}: "
        f"地平线偏差 {b['right_horizon_deg']:.4f}° "
        f"(degenerate={b['degenerate']})",
        f"var {camera_name} = comp.layers.addCamera('{camera_name}', "
        f"[{cam[0]:.2f}, {cam[1]:.2f}]);",
        f"{camera_name}.threeDLayer = true;",
        f"{camera_name}.position.setValue([{cam[0]:.2f}, {cam[1]:.2f}, {cam[2]:.2f}]);",
        f"{camera_name}.pointOfInterest.setValue([{poi[0]:.2f}, {poi[1]:.2f}, "
        f"{poi[2]:.2f}]);",
    ])


if __name__ == "__main__":
    demo = create_3d_puppet_camera_setup(
        1920, 1080, [(100, 100, 0), (200, 200, 50), (300, 150, -30)],
        camera_radius=800, height_offset=120)
    print(f"生成 {demo['total_setups']} 套相机设置 (轨道中心 {demo['center_point']})")
    for i, s in enumerate(demo["setups"]):
        b = s["basis"]
        print(f"  [{i}] cam=({s['camera_position'][0]:.1f},"
              f"{s['camera_position'][1]:.1f},{s['camera_position'][2]:.1f}) "
              f"poi=({s['point_of_interest'][0]:.1f},"
              f"{s['point_of_interest'][1]:.1f},{s['point_of_interest'][2]:.1f}) "
              f"地平线偏差={b['right_horizon_deg']:.4f}° "
              f"正立={s['rotation_stabilized']}")

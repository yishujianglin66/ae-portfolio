"""puppet_look_at_verify.py — "相机正立"的可验证扫掠（2026-09-20）。

为什么需要它
------------
台账曾写"look_at 相机正立已突破"，但仓库里只有桩实现 + 认证桩的测试，没有任何
可验证产物（`puppet/output/` 为空）。本脚本把"正立"从**断言**变成**扫掠测量**：

  1. 轨道扫掠：相机绕目标一周（多半径 × 多仰角），检查
     · 基向量正交归一（|dot| < 1e-9）
     · 地平线偏差 ≡ 0°（无滚转）
     · forward 严格指向目标
  2. 退化扫掠：视线与世界上方向平行（正上/正下俯视）时不得出现 NaN/零向量
  3. 输出 `reports/puppet_look_at_verification.json` 作为可复查证据

用法:
  python puppet/puppet_look_at_verify.py [--out reports/puppet_look_at_verification.json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

from puppet.look_at_camera import (  # noqa: E402
    create_3d_puppet_camera_setup,
    look_at_basis,
    stabilize_camera_rotation,
)

_DOT = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]  # noqa: E731


def _bad_vec(v) -> bool:
    return any((x is None) or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))
               for x in v)


def orbit_sweep(radii=(200.0, 800.0, 2500.0),
                elevations=(-60.0, -25.0, 0.0, 25.0, 60.0),
                steps: int = 24) -> dict:
    """绕目标一周的全面扫掠。返回偏差统计。"""
    target = (120.0, 80.0, -40.0)
    worst_orth = worst_horizon = worst_dir = 0.0
    n = 0
    bad: list[dict] = []
    for r in radii:
        for el_deg in elevations:
            el = math.radians(el_deg)
            for k in range(steps):
                az = 2.0 * math.pi * k / steps
                cam = (target[0] + r * math.cos(el) * math.cos(az),
                       target[1] + r * math.sin(el),
                       target[2] + r * math.cos(el) * math.sin(az))
                b = look_at_basis(cam, target)
                n += 1
                if any(_bad_vec(b[k]) for k in ("forward", "right", "up")):
                    bad.append({"cam": cam, "reason": "NaN/Inf"})
                    continue
                orth = max(abs(_DOT(b["forward"], b["up"])),
                           abs(_DOT(b["right"], b["up"])),
                           abs(_DOT(b["right"], b["forward"])))
                worst_orth = max(worst_orth, orth)
                worst_horizon = max(worst_horizon, abs(b["right_horizon_deg"]))
                # forward 必须严格指向目标（含退化仰角时也是）。
                # 用**单位向量差的范数**而非 acos(点积)：后者在点积≈1 处导数发散，
                # 会把 1e-16 级浮点噪声放大成 1e-6 度的"误差"（本轮实测教训）。
                to_t = (target[0] - cam[0], target[1] - cam[1], target[2] - cam[2])
                L = math.sqrt(_DOT(to_t, to_t))
                unit = tuple(c / L for c in to_t)
                diff = (b["forward"][0] - unit[0], b["forward"][1] - unit[1],
                        b["forward"][2] - unit[2])
                worst_dir = max(worst_dir, math.sqrt(_DOT(diff, diff)))
    return {"cases": n, "worst_orthogonality": worst_orth,
            "worst_horizon_dev_deg": worst_horizon,
            # 单位向量差范数(无量纲)：见上文的 acos 数值放大说明
            "worst_aim_unit_axis_err": worst_dir,
            "failures": bad}


def degenerate_sweep() -> dict:
    """视线与世界上方向平行的退化情形。"""
    out = []
    target = (0.0, 0.0, 0.0)
    for cam in ((0.0, 500.0, 0.0), (0.0, -500.0, 0.0),   # 正上/正下
                (0.0, 1e-7, 0.0)):                        # 近退化
        b = look_at_basis(cam, target)
        up = stabilize_camera_rotation((0.0, 1.0, 0.0), b["forward"])
        out.append({
            "cam": cam,
            "degenerate": b["degenerate"],
            "up": up,
            "up_nan": _bad_vec(up),
            "up_norm": math.sqrt(_DOT(up, up)),
            "up_perp_forward": abs(_DOT(up, b["forward"])),
        })
    return {"cases": out,
            "all_finite": not any(c["up_nan"] for c in out),
            "all_unit": all(abs(c["up_norm"] - 1.0) < 1e-6 for c in out),
            "all_perpendicular": all(c["up_perp_forward"] < 1e-9 for c in out)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PROJ / "reports" / "puppet_look_at_verification.json"))
    args = ap.parse_args()

    orb = orbit_sweep()
    deg = degenerate_sweep()
    demo = create_3d_puppet_camera_setup(
        1920, 1080, [(100, 100, 0), (200, 200, 50), (300, 150, -30)],
        camera_radius=800, height_offset=120)

    flags = {
        "orthonormal": orb["worst_orthogonality"] < 1e-9
                       and all(s["look_at_calculated"] for s in demo["setups"]),
        "no_roll": orb["worst_horizon_dev_deg"] < 1e-6
                   and all(s["rotation_stabilized"] for s in demo["setups"]),
        "aim_exact": orb["worst_aim_unit_axis_err"] < 1e-12,
        "degenerate_safe": deg["all_finite"] and deg["all_unit"] and deg["all_perpendicular"],
    }
    rep = {
        "orbit_sweep": orb,
        "degenerate_sweep": deg,
        "puppet_setup": {
            "total_setups": demo["total_setups"],
            "center_point": demo["center_point"],
            "all_upright": all(s["rotation_stabilized"] for s in demo["setups"]),
            "max_horizon_dev_deg": max(abs(s["basis"]["right_horizon_deg"])
                                       for s in demo["setups"]),
        },
        "verdict": flags,
        "all_pass": all(flags.values()),
    }

    print("\n=== look_at 相机正立 扫掠验证 ===")
    print(f"  轨道扫掠 {orb['cases']} 例: 正交性最差 {orb['worst_orthogonality']:.2e} | "
          f"地平线偏差最差 {orb['worst_horizon_dev_deg']:.2e}° | "
          f"指向单位差最差 {orb['worst_aim_unit_axis_err']:.2e}")
    print(f"  退化扫掠 {len(deg['cases'])} 例: 有限={deg['all_finite']} "
          f"单位长度={deg['all_unit']} 与视线垂直={deg['all_perpendicular']}")
    print(f"  木偶布点: {demo['total_setups']} 台, 全部正立="
          f"{rep['puppet_setup']['all_upright']}")
    for k, v in flags.items():
        print(f"    {'✅' if v else '❌'} {k}")
    print(f"\n  → 全部通过: {rep['all_pass']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    print(f"  → {out}")
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

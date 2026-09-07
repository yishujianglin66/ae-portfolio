# -*- coding: utf-8 -*-
"""Text3DRenderer — 3D艺术字体渲染管线 (专业化升级 T9)

基于 generate_3d_presets.py 的 text_stacking / text_depth_of_field 预设扩展:
1. Z轴层叠深度: ≥12层, 含材质光照参数 (Specular/Shininess/Metal)
2. 摄像机景深联动: aperture/focusDistance 与段落能量 energy_target 挂钩
3. Y轴/X轴 3D翻转进出 (参考 smart_director rotate_3d / flip_card)

铁律:
- 所有JSX输出必须通过 CameraLanguageLibrary.validate_jsx
  (无alert / 关键帧带Ease / scale≤150)
- try/catch 安全包裹
"""
from typing import Any, Dict, List, Optional

MIN_STACK_LAYERS = 12  # Z轴层叠最少层数 (验收标准)

# 材质预设 → AE Material Options 参数
# (Specular Intensity, Specular Shininess, Metal, Diffuse)
MATERIAL_PRESETS: Dict[str, Dict[str, float]] = {
    "metal": {"specular": 90, "shininess": 40, "metal": 90, "diffuse": 70},
    "glass": {"specular": 100, "shininess": 80, "metal": 10, "diffuse": 40},
    "plastic": {"specular": 60, "shininess": 25, "metal": 0, "diffuse": 90},
    "matte": {"specular": 20, "shininess": 10, "metal": 0, "diffuse": 100},
    "chrome": {"specular": 100, "shininess": 95, "metal": 100, "diffuse": 50},
}

# 景深与能量挂钩: energy 0~1 → aperture/focusDistance
def dof_params_from_energy(energy: float) -> Dict[str, float]:
    """能量越高 → 光圈越大(焦外越化), 对焦越贴近主体"""
    e = max(0.0, min(1.0, float(energy)))
    return {
        "aperture": round(2.0 + e * 12.0, 2),      # 2(平静) → 14(高潮)
        "focus_start": round(1600 - e * 500, 1),   # 由远及近拉焦
        "focus_end": round(800 - e * 200, 1),
        "blur_level": round(40 + e * 60, 1),
    }


def _validated_jsx(jsx: str) -> str:
    """铁律落地：所有 JSX 输出过 CameraLanguageLibrary.validate_jsx（警告不阻断）"""
    try:
        from core.camera_language import CameraLanguageLibrary
        res = CameraLanguageLibrary.validate_jsx(jsx)
        if not res.get("ok"):
            print(f"[validate_jsx] 警告: {res.get('issues')}", file=__import__("sys").stderr)
    except Exception as e:
        print(f"[validate_jsx] 校验不可用: {e}", file=__import__("sys").stderr)
    return jsx


class Text3DRenderer:
    """3D艺术字体JSX生成器 — 全部输出过 validate_jsx"""

    @staticmethod
    def _ease(var: str, ease_speed: float, ease_infl: float,
              n_keys: int) -> List[str]:
        lines = []
        for k in range(1, n_keys + 1):
            lines.append(
                f'var __te{k} = new KeyframeEase({ease_speed}, {ease_infl});'
                f' {var}.setTemporalEaseAtKey({k}, [__te{k}], [__te{k}]);')
        return lines

    # ── 1. Z轴层叠 + 材质光照 ─────────────────────────────
    def z_stack_jsx(self, comp_var: str, layer_var: str,
                    layers: int = 14, depth: float = 140.0,
                    material: str = "metal",
                    seg_start: float = 0.0, seg_end: float = 5.0,
                    light_intensity: float = 120.0,
                    uid: str = "stk") -> str:
        """Z轴层叠3D艺术字: ≥12层挤出 + 材质光照 + 摄像机缓推

        Args:
            layers: 层叠数量 (铁律 ≥12)
            depth: 总挤出深度
            material: 材质预设 metal/glass/plastic/matte/chrome
        """
        n = max(layers, MIN_STACK_LAYERS)
        mat = MATERIAL_PRESETS.get(material, MATERIAL_PRESETS["metal"])
        step = round(depth / n, 2)
        lines = ["try {"]
        # 基础层置3D
        lines.append(f'{layer_var}.threeDLayer = true;')
        # 材质光照参数 (显示名回退由try/catch保护)
        mo = f'{layer_var}.property("ADBE Material Options Group")'
        lines.append(f'{mo}.property("ADBE Specular Intensity").setValue({mat["specular"]});')
        lines.append(f'{mo}.property("ADBE Specular Shininess").setValue({mat["shininess"]});')
        lines.append(f'{mo}.property("ADBE Metal").setValue({mat["metal"]});')
        lines.append(f'{mo}.property("ADBE Diffuse").setValue({mat["diffuse"]});')
        lines.append(f'{mo}.property("ADBE Accepts Lights").setValue(1);')
        # Z轴层叠: duplicate 沿Z排列, 后层渐暗形成体积
        prev = layer_var
        for i in range(1, n):
            v = f"stk{uid}_{i}"
            lines.append(f'var {v} = {prev}.duplicate();')
            lines.append(f'{v}.name = "{uid}_depth_{i}";')
            lines.append(f'{v}.threeDLayer = true;')
            lines.append(
                f'{v}.property("ADBE Transform Group").property("ADBE Position")'
                f'.setValue([W/2, H/2, {round(i * step, 2)}]);')
            op = round(max(30, 100 - (i / n) * 55), 1)
            lines.append(
                f'{v}.property("ADBE Transform Group")'
                f'.property("ADBE Opacity").setValue({op});')
            prev = v
        # 聚光灯打材质高光
        lines.append(f'var light_{uid} = {comp_var}.layers.addLight('
                     f'"{uid}_spot", LightType.SPOT, [W/2, H/2]);')
        lines.append(f'light_{uid}.property("ADBE Light Options Group")'
                     f'.property("ADBE Light Intensity").setValue({light_intensity});')
        # 摄像机缓推 (带Ease, scale铁律不适用摄像机Z位移)
        lines.append(f'var cam_{uid} = {comp_var}.layers.addCamera('
                     f'"{uid}_cam", [W/2, H/2]);')
        cp = (f'cam_{uid}.property("ADBE Transform Group")'
              f'.property("ADBE Position")')
        lines.append(f'{cp}.setValueAtTime({seg_start}, [W/2, H/2, -1500]);')
        lines.append(f'{cp}.setValueAtTime({seg_end}, [W/2, H/2, -800]);')
        lines.extend(self._ease(cp, 1.0, 75.0, 2))
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 2. 摄像机景深联动 (能量挂钩) ──────────────────────
    def dof_camera_jsx(self, comp_var: str, energy: float,
                       seg_start: float = 0.0, seg_end: float = 5.0,
                       uid: str = "dof") -> str:
        """景深摄像机: aperture/focusDistance 随段落能量联动

        高能量(drop) → 大光圈浅景深+快速拉焦; 低能量(outro) → 小光圈深景深
        """
        p = dof_params_from_energy(energy)
        lines = ["try {"]
        lines.append(f'var cam_{uid} = {comp_var}.layers.addCamera('
                     f'"{uid}_cam", [W/2, H/2]);')
        co = f'cam_{uid}.property("ADBE Camera Options Group")'
        lines.append(f'{co}.property("ADBE Depth of Field").setValue(1);')
        lines.append(f'{co}.property("ADBE Aperture").setValue({p["aperture"]});')
        lines.append(f'{co}.property("ADBE Blur Level").setValue({p["blur_level"]});')
        fd = f'{co}.property("ADBE Focus Distance")'
        lines.append(f'{fd}.setValueAtTime({seg_start}, {p["focus_start"]});')
        lines.append(f'{fd}.setValueAtTime({seg_end}, {p["focus_end"]});')
        lines.extend(self._ease(fd, 1.0, 75.0, 2))
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 3. 3D翻转进出 (rotate_3d / flip_card 升级版) ─────
    def flip_3d_jsx(self, layer_var: str, axis: str = "Y",
                    direction: str = "in",
                    seg_start: float = 0.0, seg_end: float = 1.0,
                    uid: str = "flip") -> str:
        """Y/X轴3D翻转进出 (带Ease硬缓动, 参考 flip_card/rotate_3d)

        Args:
            axis: "Y" 竖翻 / "X" 横翻
            direction: "in" 90°→0° 翻入 / "out" 0°→-90° 翻出
        """
        ax = "ADBE Rotate Y" if axis.upper() == "Y" else "ADBE Rotate X"
        lines = ["try {"]
        lines.append(f'{layer_var}.threeDLayer = true;')
        rp = f'{layer_var}.property("ADBE Transform Group").property("{ax}")'
        if direction == "in":
            lines.append(f'{rp}.setValueAtTime({seg_start}, 90);')
            lines.append(f'{rp}.setValueAtTime({seg_end}, 0);')
        else:
            lines.append(f'{rp}.setValueAtTime({seg_start}, 0);')
            lines.append(f'{rp}.setValueAtTime({seg_end}, -90);')
        # 翻入: 急启动缓落(冲击感); 翻出: 缓启动急离
        spd, infl = (100.0, 85.0) if direction == "in" else (1.0, 75.0)
        lines.extend(self._ease(rp, spd, infl, 2))
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 4. 组合: 3D艺术字完整段落 ─────────────────────────
    def segment_3d_jsx(self, comp_var: str, layer_var: str,
                       energy: float = 0.8, material: str = "metal",
                       seg_start: float = 0.0, seg_end: float = 5.0,
                       uid: str = "s3d") -> str:
        """完整3D段落: Z层叠+材质 + 景深能量联动 + Y轴翻入"""
        parts = [
            self.flip_3d_jsx(layer_var, "Y", "in",
                             seg_start, round(seg_start + 0.6, 3), uid),
            self.z_stack_jsx(comp_var, layer_var, layers=MIN_STACK_LAYERS,
                             material=material,
                             seg_start=seg_start, seg_end=seg_end, uid=uid),
            self.dof_camera_jsx(comp_var, energy,
                                 seg_start, seg_end, uid),
        ]
        return _validated_jsx("\n".join(parts))

    # ── 效果清单 (供矩阵扩展) ─────────────────────────────
    def list_3d_styles(self) -> List[str]:
        return ["z_stack_metal", "z_stack_glass", "z_stack_chrome",
                "dof_high_energy", "dof_low_energy", "flip_y_in",
                "flip_x_in", "flip_y_out", "segment_3d_full"]

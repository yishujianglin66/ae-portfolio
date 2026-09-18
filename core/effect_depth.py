# -*- coding: utf-8 -*-
"""EffectDepthLibrary — 本地效果插件深层开发 (专业化升级 T11)

针对 smart_director EFFECT_FONT_MATRIX 的特效组合深化:
1. Glow 深化: 双层辉光 + 色相偏移动画
2. 方向模糊: 速度线模拟 (Directional Blur 动画模糊长度)
3. RGB分离: 色差抖动 (双副本错位 + Screen混合)
4. 插件级效果: CC Particle World 粒子文字 / Saber 光线描边 /
   Trapcode Form 三维阵列 (均 try/catch 包裹, 插件缺失自动降级)
5. intensity 三档参数联动 (subtle/moderate/intense)
6. 效果与运镜联动: drop段whip → RGB分离+运动模糊;
   break段 → 柔光+降饱和

铁律: 所有JSX输出通过 CameraLanguageLibrary.validate_jsx
"""
from typing import Any, Dict, List

# 三档强度参数: 振幅/频率/透明度联动
INTENSITY_TIERS: dict[str, dict[str, float]] = {
    "subtle":   {"amp": 0.35, "freq": 0.6, "opacity": 60,
                 "glow_radius": 8, "blur_len": 6, "rgb_offset": 2},
    "moderate": {"amp": 0.7, "freq": 1.0, "opacity": 80,
                 "glow_radius": 18, "blur_len": 15, "rgb_offset": 5},
    "intense":  {"amp": 1.0, "freq": 1.6, "opacity": 100,
                 "glow_radius": 32, "blur_len": 30, "rgb_offset": 9},
}


def _ease_lines(var: str, n_keys: int, speed: float = 1.0,
                infl: float = 75.0) -> list[str]:
    out = []
    for k in range(1, n_keys + 1):
        out.append(f'var __fe{k} = new KeyframeEase({speed}, {infl});'
                   f' {var}.setTemporalEaseAtKey({k}, [__fe{k}], [__fe{k}]);')
    return out


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


class EffectDepthLibrary:
    """效果深化JSX生成器 — intensity三档联动 + 运镜联动"""

    def tier(self, intensity: str) -> dict[str, float]:
        return INTENSITY_TIERS.get(intensity, INTENSITY_TIERS["moderate"])

    # ── 1. Glow 深化: 双层辉光 + 色相偏移 ────────────────
    def glow_double_jsx(self, layer_var: str, intensity: str = "moderate",
                        seg_start: float = 0.0, seg_end: float = 3.0,
                        uid: str = "gl") -> str:
        """双层辉光: 内层小半径高阈值锐辉光 + 外层大半径弥散,
        叠加色相偏移关键帧动画 (能量脉冲感)"""
        t = self.tier(intensity)
        r_in = round(t["glow_radius"] * 0.4, 1)
        r_out = t["glow_radius"]
        lines = ["try {"]
        # 内层锐辉光
        g1 = f'{layer_var}.Effects.addProperty("ADBE Glo2")'
        lines.append(f'var gl_{uid}_1 = {g1};')
        lines.append(f'gl_{uid}_1.property("ADBE Glo2-0002").setValue({r_in});')
        lines.append(f'gl_{uid}_1.property("ADBE Glo2-0003").setValue(0.6);')
        lines.append(f'gl_{uid}_1.property("ADBE Glo2-0006").setValue({round(t["amp"]*100)});')
        # 外层弥散辉光
        lines.append(f'var gl_{uid}_2 = {g1};')
        lines.append(f'gl_{uid}_2.property("ADBE Glo2-0002").setValue({r_out});')
        lines.append(f'gl_{uid}_2.property("ADBE Glo2-0003").setValue(0.25);')
        lines.append(f'gl_{uid}_2.property("ADBE Glo2-0006").setValue({round(t["amp"]*70)});')
        # 色相偏移动画 (Hue/Saturation 的 Master Hue 关键帧)
        hs = f'{layer_var}.Effects.addProperty("ADBE HUE SATUR")'
        lines.append(f'var hue_{uid} = {hs};')
        hp = f'hue_{uid}.property("ADBE HUE SATUR-0001")'
        hue_peak = round(20 * t["amp"])
        lines.append(f'{hp}.setValueAtTime({seg_start}, 0);')
        lines.append(f'{hp}.setValueAtTime({round((seg_start+seg_end)/2, 3)}, {hue_peak});')
        lines.append(f'{hp}.setValueAtTime({seg_end}, 0);')
        lines.extend(_ease_lines(hp, 3))
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 2. 方向模糊: 速度线模拟 ──────────────────────────
    def speed_lines_jsx(self, layer_var: str, intensity: str = "intense",
                        seg_start: float = 0.0, seg_end: float = 1.0,
                        direction: float = 0.0, uid: str = "sl") -> str:
        """Directional Blur 动画模糊长度: 入场高速模糊→定格清晰(速度线感)"""
        t = self.tier(intensity)
        lines = ["try {"]
        lines.append(f'var db_{uid} = {layer_var}.Effects.addProperty("ADBE Directional Blur");')
        bp = f'db_{uid}.property("ADBE Directional Blur-0001")'
        dp = f'db_{uid}.property("ADBE Directional Blur-0002")'
        lines.append(f'{dp}.setValue({direction});')
        lines.append(f'{bp}.setValueAtTime({seg_start}, {t["blur_len"]});')
        lines.append(f'{bp}.setValueAtTime({seg_end}, 0);')
        lines.extend(_ease_lines(bp, 2, 100.0, 85.0))
        lines.append(f'{layer_var}.motionBlur = true;')
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 3. RGB分离: 色差抖动 ─────────────────────────────
    def rgb_split_jsx(self, layer_var: str, intensity: str = "moderate",
                      seg_start: float = 0.0, seg_end: float = 1.5,
                      uid: str = "rgb") -> str:
        """色差抖动: 双副本反向错位 + Screen混合 + 抖动关键帧"""
        t = self.tier(intensity)
        off = t["rgb_offset"]
        lines = ["try {"]
        for i, sign in ((1, 1), (2, -1)):
            v = f"rgb_{uid}_{i}"
            lines.append(f'var {v} = {layer_var}.duplicate();')
            lines.append(f'{v}.name = "{uid}_ch{i}";')
            lines.append(f'{v}.blendingMode = BlendingMode.SCREEN;')
            # 单通道保留: Shift Channels (红/青分离)
            lines.append(f'var sc_{uid}_{i} = {v}.Effects.addProperty("ADBE Shift Channels");')
            tgt = 2 if i == 1 else 4  # 红 / 蓝
            lines.append(f'sc_{uid}_{i}.property("ADBE Shift Channels-0001").setValue({tgt});')
            pp = f'{v}.property("ADBE Transform Group").property("ADBE Position")'
            mid = round((seg_start + seg_end) / 2, 3)
            lines.append(f'{pp}.setValueAtTime({seg_start}, [W/2 + {sign*off}, H/2, 0]);')
            lines.append(f'{pp}.setValueAtTime({mid}, [W/2 - {sign*off}, H/2, 0]);')
            lines.append(f'{pp}.setValueAtTime({seg_end}, [W/2 + {sign*off}, H/2, 0]);')
            lines.extend(_ease_lines(pp, 3, 100.0, 60.0))
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 4a. CC Particle World 粒子文字 ───────────────────
    def particle_world_jsx(self, comp_var: str, intensity: str = "intense",
                           seg_start: float = 0.0, seg_end: float = 3.0,
                           uid: str = "pw") -> str:
        """CC Particle World (AE内置): 粒子从文字区域爆发"""
        t = self.tier(intensity)
        birth = round(2.5 * t["amp"], 2)
        lines = ["try {"]
        lines.append(f'var sol_{uid} = {comp_var}.layers.addSolid('
                     f'[0,0,0], "{uid}_particles", W, H, 1);')
        lines.append(f'var pw_{uid} = sol_{uid}.Effects.addProperty("CC Particle World");')
        lines.append(f'pw_{uid}.property("Birth Rate").setValueAtTime({seg_start}, {birth});')
        lines.append(f'pw_{uid}.property("Birth Rate").setValueAtTime({seg_end}, 0);')
        lines.extend(_ease_lines(f'pw_{uid}.property("Birth Rate")', 2))
        lines.append(f'pw_{uid}.property("Longevity").setValue({round(1.5*t["freq"], 2)});')
        lines.append(f'pw_{uid}.property("Radius").setValue({round(0.3*t["amp"] + 0.1, 2)});')
        lines.append(f'sol_{uid}.blendingMode = BlendingMode.SCREEN;')
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 4b. Saber 光线描边 (VideoCopilot, 缺失自动降级) ──
    def saber_jsx(self, comp_var: str, intensity: str = "moderate",
                  uid: str = "sb") -> str:
        """Saber 光线描边; 插件不存在时静默降级(try/catch)"""
        t = self.tier(intensity)
        lines = ["try {"]
        lines.append(f'var sol_{uid} = {comp_var}.layers.addSolid('
                     f'[0,0,0], "{uid}_saber", W, H, 1);')
        lines.append(f'var saber_{uid} = sol_{uid}.Effects.addProperty("Video Copilot Saber");')
        lines.append(f'saber_{uid}.property("Glow Width").setValue({round(6*t["amp"] + 2, 1)});')
        lines.append(f'saber_{uid}.property("Core Line Width").setValue({round(2*t["amp"] + 0.5, 1)});')
        lines.append(f'sol_{uid}.blendingMode = BlendingMode.SCREEN;')
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 4c. Trapcode Form 三维阵列 (Red Giant, 缺失降级) ─
    def form_grid_jsx(self, comp_var: str, intensity: str = "moderate",
                      seg_start: float = 0.0, seg_end: float = 3.0,
                      uid: str = "fm") -> str:
        """Trapcode Form 三维粒子阵列; 插件不存在时静默降级"""
        t = self.tier(intensity)
        n = int(20 + 20 * t["amp"])
        lines = ["try {"]
        lines.append(f'var sol_{uid} = {comp_var}.layers.addSolid('
                     f'[0,0,0], "{uid}_form", W, H, 1);')
        lines.append(f'var form_{uid} = sol_{uid}.Effects.addProperty("Trapcode Form");')
        lines.append(f'form_{uid}.property("Base Layer").property("Particles in X").setValue({n});')
        lines.append(f'form_{uid}.property("Base Layer").property("Particles in Y").setValue({n});')
        lines.append(f'form_{uid}.property("Base Layer").property("Size").setValue({round(3*t["amp"] + 1, 1)});')
        rp = f'form_{uid}.property("Base Layer").property("Roll")'
        lines.append(f'{rp}.setValueAtTime({seg_start}, 0);')
        lines.append(f'{rp}.setValueAtTime({seg_end}, {round(30*t["freq"], 1)});')
        lines.extend(_ease_lines(rp, 2))
        lines.append(f'sol_{uid}.blendingMode = BlendingMode.SCREEN;')
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 5. 柔光 + 降饱和 (break段留白) ───────────────────
    def soft_breathe_jsx(self, layer_var: str, intensity: str = "subtle",
                         seg_start: float = 0.0, seg_end: float = 3.0,
                         uid: str = "sb2") -> str:
        """柔光+降饱和: Fast Blur微柔 + 饱和度随时间下降 (呼吸感)"""
        t = self.tier(intensity)
        lines = ["try {"]
        lines.append(f'var fb_{uid} = {layer_var}.Effects.addProperty("ADBE Fast Blur");')
        lines.append(f'fb_{uid}.property("ADBE Fast Blur-0001").setValue({round(2*t["amp"] + 1, 1)});')
        lines.append(f'var sat_{uid} = {layer_var}.Effects.addProperty("ADBE Saturation");')
        sp = f'sat_{uid}.property("ADBE Saturation-0001")'
        lines.append(f'{sp}.setValueAtTime({seg_start}, 100);')
        lines.append(f'{sp}.setValueAtTime({seg_end}, {round(100 - 45*t["amp"])});')
        lines.extend(_ease_lines(sp, 2))
        lines.append("} catch(e) {}")
        return _validated_jsx(" ".join(lines))

    # ── 6. 效果×运镜联动 ─────────────────────────────────
    def camera_effect_link(self, camera_id: str,
                           seg_type: str) -> list[dict[str, Any]]:
        """运镜→效果联动规则:
        - drop段 whip甩镜 → RGB分离(色差抖动) + 运动模糊(速度线)
        - break段任意运镜 → 柔光 + 降饱和
        - drop段 push → 双层Glow脉冲
        """
        links: list[dict[str, Any]] = []
        if seg_type == "drop" and camera_id == "whip":
            links.append({"effect": "rgb_split", "intensity": "intense"})
            links.append({"effect": "speed_lines", "intensity": "intense"})
        elif seg_type == "drop" and camera_id in ("push", "dolly_zoom", "shake"):
            links.append({"effect": "glow_double", "intensity": "intense"})
        if seg_type in ("break", "breath_break"):
            links.append({"effect": "soft_breathe", "intensity": "subtle"})
        return links

    def link_jsx(self, layer_var: str, comp_var: str,
                 camera_id: str, seg_type: str,
                 seg_start: float, seg_end: float) -> str:
        """按联动规则生成完整效果JSX块"""
        out = []
        for i, lk in enumerate(self.camera_effect_link(camera_id, seg_type)):
            eff, inten = lk["effect"], lk["intensity"]
            uid = f"lk{i}"
            if eff == "rgb_split":
                out.append(self.rgb_split_jsx(layer_var, inten,
                                              seg_start, seg_end, uid))
            elif eff == "speed_lines":
                out.append(self.speed_lines_jsx(layer_var, inten,
                                                seg_start, seg_end, uid=uid))
            elif eff == "glow_double":
                out.append(self.glow_double_jsx(layer_var, inten,
                                                seg_start, seg_end, uid))
            elif eff == "soft_breathe":
                out.append(self.soft_breathe_jsx(layer_var, inten,
                                                 seg_start, seg_end, uid))
        return _validated_jsx("\n".join(out))

    def list_effects(self) -> list[str]:
        return ["glow_double", "speed_lines", "rgb_split",
                "particle_world", "saber", "form_grid", "soft_breathe"]

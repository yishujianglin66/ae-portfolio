"""EditFXVocabulary — 顶尖慢剪效果语汇系统（M7）

把外网顶尖 edit（nocomply/Kaizen/temple 圈层）的核心效果语言编码为
确定性、帧精确、可复现的 AE 原生关键帧/表达式生成器：

  zoom_punch    节拍快速推拉（超调+指数衰减, 2-4 帧hit+settle）
  shake         高频手持抖动（wiggle 表达式, 多轴不同频不同种子）
  rgb_burst     时序色差爆开（Tint 对撞色 flash, 卡点瞬间, 视觉等价 CA burst）
  speed_ramp    速度斜坡（timeRemap 曲线: 速率序列积分成时间映射）
  freeze_punch  定格+推近（timeRemap 定格 + scale punch 组合）
  grain_layer   胶片颗粒后处理层（adjustment + Noise）
  glow_hit      节拍闪光（Glow 强度关键帧）
  occlusion     文字被人物遮挡（抠像 alpha 层做 Alpha Inverted track matte）

全部为纯 JSX 字符串生成（不触真机）; 由 synthesis_orchestrator 注入图层,
真机执行走既有 Bridge 链路。

用法:
    from core.edit_fx_vocabulary import zoom_punch_jsx, shake_jsx
    jsx = zoom_punch_jsx(var="layer1", times=[0.5, 1.0], amount=8)
"""
from __future__ import annotations

from typing import List, Sequence


def _tg(var: str, prop: str) -> str:
    """'ADBE Transform Group/ADBE Scale' → 链式 property 访问
    （AE 2025 property() 不支持斜杠路径, 必须拆段链式调用）"""
    chain = var
    for s in prop.split("/"):
        chain += f'.property("{s}")'
    return chain


# ── 节拍 punch：scale 超调 + 指数衰减 ────────────────────────────────

def zoom_punch_jsx(var: str, times: Sequence[float], amount: float = 8.0,
                   settle_s: float = 0.28) -> str:
    """节拍推拉 punch。每个 t: 瞬间(100+amount)% → 衰减回 100%。正=推近。"""
    chain = _tg(var, "ADBE Transform Group/ADBE Scale")
    lines: list[str] = []
    for t in times:
        a1 = amount * 0.3
        lines.append(
            f'    {chain}.setValuesAtTimes('
            f'[{t:.3f}, {t + settle_s * 0.4:.3f}, {t + settle_s:.3f}], '
            f'[[{100+amount:.1f}, {100+amount:.1f}, 100], '
            f'[{100+a1:.1f}, {100+a1:.1f}, 100], [100, 100, 100]]);'
        )
    return "\n".join(lines)


# ── 高频手持抖动（wiggle 表达式） ───────────────────────────────────

def shake_jsx(var: str, freq: float = 14.0, amp: float = 12.0,
              axis: str = "both", seed: int = 1,
              start: float = None, end: float = None) -> str:
    """多轴不同频抖动（顶尖 shake 的"贵"感来自 per-axis 频率/种子差异）。

    axis: "x" | "y" | "both" | "rot"
    start/end: 生效窗口（渐入渐出裁剪）; None=全程抖动。
    """
    pos = _tg(var, "ADBE Transform Group/ADBE Position")
    rot = _tg(var, "ADBE Transform Group/ADBE Rotation")
    win = ""
    if start is not None and end is not None:
        win = (f' * linear(time, {start}, {start + 0.03}, 0, 1)'
               f' * linear(time, {end - 0.05}, {end}, 1, 0)')
    lines: list[str] = []
    if axis in ("x", "both"):
        lines.append(
            f'    {pos}.expression = "seedRandom({seed}, true); '
            f'value + [wiggle({freq}, {amp})[0] - value[0]{win}, 0, 0]";'
        )
    if axis in ("y", "both"):
        lines.append(
            f'    {pos}.expression = "seedRandom({seed + 7}, true); '
            f'value + [0, wiggle({freq * 0.8:.1f}, {amp * 0.7:.1f})[1] - value[1]{win}, 0]";'
        )
    if axis == "rot":
        lines.append(
            f'    {rot}.expression = "seedRandom({seed + 3}, true); '
            f'wiggle({freq}, {amp * 0.12:.2f}) - value";'
        )
    return "\n".join(lines)


# ── 时序色差爆开 ───────────────────────────────────────────────────

def rgb_burst_jsx(var: str, times: Sequence[float], max_amount: float = 25.0,
                  recover_s: float = 0.18, native: bool = True) -> str:
    """卡点瞬间色差爆开回位。

    native=True: EFX Chromatic Aberration 真插件（matchName efx_chromaber,
      参数4=Amount; 系统已装, 2026-08-16 真机探测）— RGB 通道真实偏移。
    native=False: Tint 对撞色 flash 降级（无插件环境）。
    """
    fx = f'{var}.property("ADBE Effect Parade")'
    tag = var.replace("layer", "L")
    if native:
        lines = [
            f'    var _ca{tag} = {fx}.addProperty("efx_chromaber");',
            f'    if (_ca{tag}) {{',
            f'        var _amt{tag} = _ca{tag}.property(4);   // Amount(真机确认)',
        ]
        for t in times:
            lines.append(f'        _amt{tag}.setValueAtTime({t:.3f}, {max_amount});')
            lines.append(f'        _amt{tag}.setValueAtTime({t + recover_s:.3f}, 0);')
        lines.append('    }')
        return "\n".join(lines)
    lines: list[str] = [
        f'    var _tint{tag} = {fx}.addProperty("ADBE Tint");',
        f'    if (_tint{tag}) {{',
        f'        _tint{tag}.property(1).setValue([1, 0.1, 0.1, 1]);',
        f'        _tint{tag}.property(2).setValue([0.1, 0.5, 1, 1]);',
        f'        var _amt{tag} = _tint{tag}.property(3);   // Amount(真机确认索引3)',
    ]
    for t in times:
        lines.append(f'        _amt{tag}.setValueAtTime({t:.3f}, 100);')
        lines.append(f'        _amt{tag}.setValueAtTime({t + recover_s:.3f}, 0);')
    lines.append('    }')
    return "\n".join(lines)


# ── 速度斜坡（timeRemap） ───────────────────────────────────────────


def speed_ramp_jsx(var: str, source_dur: float, ramps: Sequence[dict],
                   offset: float = 0.0, source_in: float = 0.0) -> str:
    """速度斜坡: ramps=[{"t": 镜头相对时间(0~shot_dur), "v": 速率}...] → timeRemap。

    2026-08-17 真机验证最终方案 (与 layer_builders 重构配套):
    变速镜头 layer.startTime = t0 (不再前移), inPoint=t0, outPoint=t1。
    因此 layer 局部时间 0 对应合成时间 t0, 局部时间 shot_dur 对应合成 t1。
    timeRemap keyframe 时间直接写 layer-local [0, shot_dur]。
    keyframe 值 = source_in + t_map (从 source_in 开始累计源时间)。

    旧方案 (startTime=t0-source_in 前移 + keyframe 在 [source_in, source_in+shot_dur])
    真机验证发现负 startTime + timeRemap 组合导致 layer 延迟 10 帧才显示 (cut4)。
    新方案消除负 startTime, 边界更可靠。
    """
    tag = var.replace("layer", "L")
    lines = [
        f'    {var}.timeRemapEnabled = true;',
        f'    var _tr{tag} = {var}.property("ADBE Time Remapping");',
    ]
    t_map = 0.0
    prev_t_ramp = 0.0  # ramps 序列内的相对时间
    # 起始 keyframe: 合成时间 offset → 源 source_in
    lines.append(f'    _tr{tag}.setValueAtTime({offset:.3f}, {source_in:.3f});')
    for r in ramps:
        t_ramp = float(r["t"])  # 0~shot_dur 镜头相对时间 = layer-local 时间
        v = float(r.get("v", 1.0))
        dt = t_ramp - prev_t_ramp
        if dt > 0:
            t_map += v * dt
        prev_t_ramp = t_ramp
        src_time = min(source_in + t_map, source_dur)
        lines.append(f'    _tr{tag}.setValueAtTime({offset + t_ramp:.3f}, {src_time:.3f});')
    return "\n".join(lines)


def freeze_punch_jsx(var: str, freeze_t: float, punch: float = 6.0,
                     hold_s: float = 0.35, source_dur: float = 5.0) -> str:
    """定格+推近: timeRemap 定格于 freeze_t（hold_s 秒）同时 scale punch。"""
    tr = speed_ramp_jsx(var, source_dur, [
        {"t": max(freeze_t - 0.05, 0), "v": 1.0},
        {"t": freeze_t, "v": 0.001},
        {"t": freeze_t + hold_s, "v": 0.001},
        {"t": freeze_t + hold_s + 0.05, "v": 1.0},
    ])
    return tr + "\n" + zoom_punch_jsx(var, [freeze_t], amount=punch)


# ── 后处理层 ────────────────────────────────────────────────────────

def grain_layer_jsx(comp_var: str = "comp", amount: int = 12) -> str:
    """胶片颗粒后处理: adjustment 固态层 + Noise（Use Color Noise）。"""
    return (
        f'    var _grain = {comp_var}.layers.addSolid([0, 0, 0], "GrainPost", '
        f'{comp_var}.width, {comp_var}.height, 1.0, {comp_var}.duration);'
        f'    _grain.adjustmentLayer = true;'
        f'    var _gn = _grain.property("ADBE Effect Parade").addProperty("ADBE Noise");'
        f'    if (_gn) {{ _gn.property(1).setValue({amount}); _gn.property(3).setValue(1); }}'
        # 3 = Use Color Noise（真机确认: ADBE Noise 属性 1-4, 非 5）
    )


def glow_hit_jsx(var: str, times: Sequence[float], intensity: float = 2.0,
                 recover_s: float = 0.25) -> str:
    """节拍闪光: Glow 强度瞬间拉高再回位。"""
    tag = var.replace("layer", "L")
    lines = [
        f'    var _gl{tag} = {var}.property("ADBE Effect Parade").addProperty("ADBE Glo2");',
    ]
    for t in times:
        lines.append(
            f'    if (_gl{tag}) {{ var _gi{tag} = _gl{tag}.property(3); '
            f'_gi{tag}.setValueAtTime({t:.3f}, {intensity}); '
            f'_gi{tag}.setValueAtTime({t + recover_s:.3f}, 0.6); }}'
        )
    return "\n".join(lines)


# ── 遮挡穿插：文字在人物身后 ────────────────────────────────────────

def occlusion_matte_jsx(text_var: str, matte_var: str) -> str:
    """人物 alpha 层紧贴文字层上方并设 Alpha Inverted matte → 文字从人物身后穿出。"""
    return (
        f'    {matte_var}.moveAfter({text_var});'
        f'    {text_var}.trackMatteType = TrackMatteType.ALPHA_INVERTED;'
    )


__all__ = [
    "zoom_punch_jsx", "shake_jsx", "rgb_burst_jsx", "speed_ramp_jsx",
    "freeze_punch_jsx", "grain_layer_jsx", "glow_hit_jsx", "occlusion_matte_jsx",
]

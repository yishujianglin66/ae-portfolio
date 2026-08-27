"""layer_builders — 合成树图层 → JSX 创建语句（按类型分派的策略层）

2026-08-16 架构收敛(阶段2)从 synthesis_orchestrator.JsxProjectBuilder._build_layer
拆出: orchestrator 保留 校验→预备→编排→build→发送 管线, 本模块只回答
"一种图层类型怎么建"。类型无关的后处理(效果/动画/字符级动画/edit_fx/
速度斜坡)仍在 JsxProjectBuilder 上。

行为约定:
- 各 builder 返回行列表, 与拆分前逐行等价(基线对比验证, 见
  tmp/refactor_baseline/gen_baseline.py)
- 图层名/合成名/文字/报错路径经 js_str() 转义进 JS 字符串字面量 —
  拆分前 comp_name/layer.id 直插, 含引号/反斜杠时生成非法 JSX
  (2026-08-16 体检 P0-1 同类问题的 Python 侧修复)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List

if TYPE_CHECKING:  # 避免运行期循环依赖(仅类型标注)
    from core.composition_tree import CompositionTree, LayerSpec


def js_str(s: str) -> str:
    """转义为 ExtendScript 字符串字面量内容（不含两侧引号）。"""
    return (str(s).replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))


class LayerBuildContext:
    """单次 build 内各图层构建器共享的状态。"""

    def __init__(self, tree: "CompositionTree", warnings: List[str],
                 post_lines: List[str]):
        self.tree = tree
        self.warnings = warnings
        self.post_lines = post_lines  # 跨图层后处理(track matte 紧邻调整等)


def _hex_to_rgb(hex_color: str) -> List[float]:
    h = hex_color.lstrip("#")
    return [int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0]


# ── solid ─────────────────────────────────────────────────────────────


def build_solid_layer(ctx: LayerBuildContext, layer: "LayerSpec") -> List[str]:
    tree = ctx.tree
    var = f"layer{layer.z_index}"
    color = layer.content.get("color", [0, 0, 0])
    col_js = f"[{color[0]/255:.4f}, {color[1]/255:.4f}, {color[2]/255:.4f}]"
    return [
        f"    var {var} = comp.layers.addSolid({col_js}, \"{js_str(layer.id)}\", "
        f"{tree.width}, {tree.height}, 1.0, {tree.duration});",
        f"    {var}.startTime = {layer.time_range[0]};",
        f"    {var}.outPoint = {layer.time_range[1]};",
    ]


# ── adjustment ────────────────────────────────────────────────────────


def build_adjustment_layer(ctx: LayerBuildContext, layer: "LayerSpec") -> List[str]:
    tree = ctx.tree
    idx = layer.z_index
    var = f"layer{idx}"
    lines = [
        f"    var {var} = comp.layers.addSolid([0,0,0], \"{js_str(layer.id)}\", "
        f"{tree.width}, {tree.height}, 1.0, {tree.duration});",
        f"    {var}.adjustmentLayer = true;",
        f"    {var}.startTime = {layer.time_range[0]};",
        f"    {var}.outPoint = {layer.time_range[1]};",
    ]
    # M7: grain 后处理层（edit_fx_layer="grain"）
    if layer.content.get("edit_fx_layer") == "grain":
        lines.append(f"    // ── grain 后处理 ──")
        lines.append(
            f"    var _gn{idx} = {var}.property('ADBE Effect Parade')"
            f".addProperty('ADBE Noise');")
        lines.append(
            f"    if (_gn{idx}) {{ _gn{idx}.property(1).setValue("
            f"{int(layer.content.get('amount', 12))}); "
            f"_gn{idx}.property(3).setValue(1); }}")  # 3=Use Color Noise(真机确认)
    return lines


# ── text ──────────────────────────────────────────────────────────────


def build_text_layer(ctx: LayerBuildContext, layer: "LayerSpec") -> List[str]:
    tree = ctx.tree
    var = f"layer{layer.z_index}"
    text = js_str(layer.content.get("text", ""))
    size = int(layer.content.get("size", 96))
    colors = layer.content.get("colors", {})
    main = _hex_to_rgb(colors.get("main", "#FFFFFF"))
    # 字体回退链：AE 只认 PS 名。font="auto" 时按风格卡经字体风格映射解析
    # （2026-08-16: 系统 2375 字体资产经真机验证 12/12, 见 core/font_style_map.py）
    requested = str(layer.content.get("font", "auto"))
    chain: List[str] = []
    if requested == "auto":
        try:
            from core.font_style_map import resolve_font
            cjk = any('\u4e00' <= ch <= '\u9fff' for ch in text)
            chain = resolve_font(tree.style_card, layer.content.get("font_role", "title"), cjk)
        except Exception:  # noqa: BLE001 — 映射失败走原回退
            pass
    if not chain:
        for f in [requested if requested != "auto" else "SourceHanSansCN-Bold",
                  "SourceHanSansCN-Bold", "SourceHanSansCN", "Arial"]:
            if f and f not in chain:
                chain.append(f)
    fonts_js = json.dumps(chain, ensure_ascii=False)
    return [
        f"    var {var} = comp.layers.addText(\"{text}\");",
        f"    var {var}_td = {var}.property(\"ADBE Text Properties\").property(\"ADBE Text Document\");",
        f"    var _fonts = {fonts_js};",
        f"    var _fontOk = false;",
        f"    for (var _fi = 0; _fi < _fonts.length; _fi++) {{",
        f"        var {var}_doc = {var}_td.value;",
        f"        {var}_doc.resetCharStyle();",
        f"        {var}_doc.fontSize = {size};",
        f"        {var}_doc.fillColor = [{main[0]:.4f}, {main[1]:.4f}, {main[2]:.4f}];",
        f"        try {{ {var}_doc.font = _fonts[_fi]; {var}_td.setValue({var}_doc); _fontOk = true; break; }} catch(e) {{ _fontOk = false; }}",
        f"    }}",
        f"    {var}.startTime = {layer.time_range[0]};",
        f"    {var}.outPoint = {layer.time_range[1]};",
    ]


# ── particle ──────────────────────────────────────────────────────────

# 四模板统一金色贴图(经真机验证可染): spark/ember/trail/burst
_DEFAULT_SPRITES = {
    "spark": "resources/effects/_generated/sprite_gold.png",
    "ember": "resources/effects/_generated/sprite_gold.png",
    "trail": "resources/effects/_generated/sprite_gold.png",
    "burst": "resources/effects/_generated/sprite_gold.png",
}


def build_particle_layer(ctx: LayerBuildContext, layer: "LayerSpec") -> List[str]:
    tree = ctx.tree
    var = f"layer{layer.z_index}"
    lines = [
        f"    var {var} = comp.layers.addSolid([0,0,0], \"{js_str(layer.id)}\", "
        f"{tree.width}, {tree.height}, 1.0, {tree.duration});",
        f"    {var}.blendingMode = BlendingMode.ADD;",
        f"    {var}.startTime = {layer.time_range[0]};",
        f"    {var}.outPoint = {layer.time_range[1]};",
    ]
    # P2/P12: Particular 模板 + 贴图精灵（本地 4057 张特效贴图库）
    _ptpl = str(layer.content.get("template", ""))
    if _ptpl:
        from core.plugin_fx_templates import particular_jsx
        # sprite: content.sprite 显式指定; 否则按模板默认配（光点类贴图）
        _sprite = layer.content.get("sprite", _DEFAULT_SPRITES.get(_ptpl))
        if _sprite and not Path(_sprite).exists():
            ctx.warnings.append(f"粒子层 {layer.id} 贴图不存在: {_sprite}")
            _sprite = None
        try:
            lines.append(particular_jsx(
                var, template=_ptpl,
                t_hit=layer.content.get("t_hit"),
                duration=tree.duration,
                sprite=_sprite,
                psize_scale=float(layer.content.get("psize_scale", 1.0)),
                glow_mult=float(layer.content.get("_glow_mult", 1.0)),
                pps_mult=float(layer.content.get("_pps_mult", 1.0)),
                tint_black=layer.content.get("tint_black"),
                tint_white=layer.content.get("tint_white")))
        except Exception as e:  # noqa: BLE001
            ctx.warnings.append(f"粒子层 {layer.id} Particular 模板失败: {e}")
    else:
        lines.append(f'    {var}.property("ADBE Effect Parade")'
                     f'.addProperty("CC Particle World");')
    return lines


# ── footage（gen_fx 素材预备后复用同一路径）────────────────────────────


def build_footage_layer(ctx: LayerBuildContext, layer: "LayerSpec") -> List[str]:
    """素材图层：RGBA 透明 MOV/PNG 序列直投，或 彩色视频+遮罩序列 track matte"""
    tree = ctx.tree
    idx = layer.z_index
    var = f"layer{idx}"
    path = str(layer.content.get("path", ""))
    mode = str(layer.content.get("matting_mode", "rgba"))
    fit = str(layer.content.get("fit", "cover"))
    t0, t1 = layer.time_range
    lines = [
        f"    var _io{idx} = new ImportOptions(new File({json.dumps(path)}));",
        f"    var {var}_ftg = proj.importFile(_io{idx});",
    ]
    # 静态素材（gen_fx 生成的透明 PNG）无视频轨是合法的：hasVideo 检查仅对动态素材
    _allow_still = bool(layer.content.get("allow_still")) or layer.type == "gen_fx"
    if _allow_still:
        lines.append(f"    if (!{var}_ftg) throw new Error(\"素材导入失败: {js_str(path)}\");")
    else:
        lines.append(f"    if (!{var}_ftg || !{var}_ftg.hasVideo) throw new Error(\"footage 无视频轨: {js_str(path)}\");")
    lines.append(f"    var {var} = comp.layers.add({var}_ftg);")
    if fit in ("cover", "fit"):
        fn = "Math.max" if fit == "cover" else "Math.min"
        lines.append(f"    var _sc{idx} = {fn}(comp.width/{var}_ftg.width, "
                     f"comp.height/{var}_ftg.height) * 100;")
        lines.append(f"    {var}.property(\"ADBE Transform Group\").property(\"ADBE Scale\")"
                     f".setValue([_sc{idx}, _sc{idx}, _sc{idx}]);")
    # 源入点处理 (2026-08-17 真机验证重构):
    # 旧方案 startTime=t0-source_in + timeRemap keyframe 在 [source_in, source_in+shot_dur]
    # 真机验证发现负 startTime + timeRemap 组合导致 layer 在 inPoint 后延迟 10 帧才显示
    # (cut4 frame120 仍显示 shot3, frame130 才出现 shot4).
    # 新方案: 变速镜头直接 startTime=t0, timeRemap keyframe 在 [0, shot_dur]
    # (keyframe 时间为 layer-local, src_time 值 = source_in + t_map); 非变速镜头保留
    # startTime 前移让源自动从 in_s 播.
    src_in = float(layer.content.get("source_in", 0) or 0)
    has_ramps = bool(layer.content.get("speed_ramps"))
    # 2026-08-17 真机铁证 (最小实验): inPoint 在 outPoint 之后赋值时, AE 会把
    # outPoint 抬成 inPoint+原out (shot1: 2.05→3.05) → 层互相覆盖、多镜头失效。
    # 顺序必须是: startTime → inPoint → outPoint。
    if has_ramps:
        # 变速镜头: 用 timeRemap 控制源时间, layer startTime 直接对齐合成 t0
        lines.append(f"    {var}.startTime = {t0};")
        lines.append(f"    {var}.inPoint = {t0};")
        lines.append(f"    {var}.outPoint = {t1};")
    else:
        _st = t0 - src_in
        lines.append(f"    {var}.startTime = {_st};")
        if src_in > 0:
            lines.append(f"    {var}.inPoint = {t0};")
        if _allow_still:
            # 静态素材（still PNG）AE 默认 duration 可能为 0 → outPoint=inPoint 图层 0 秒长
            # （2026-08-16 M6 真机实测根因）；still 直接铺满 time_range
            lines.append(f"    {var}.outPoint = {t1};")
        else:
            lines.append(f"    {var}.outPoint = Math.min({t1}, {_st} + {var}_ftg.duration);")
    if mode == "track_matte":
        matte_dir = str(layer.content.get("matte_dir", ""))
        first_frame = str(layer.content.get("matte_first", "mask_00000.png"))
        if not matte_dir:
            ctx.warnings.append(
                f"素材层 {layer.id} track_matte 模式缺 matte_dir，按原素材直放")
            return lines
        lines.append(f"    var _mio{idx} = new ImportOptions(new File("
                     f"{json.dumps(str(Path(matte_dir) / first_frame))}));")
        lines.append(f"    _mio{idx}.sequence = true;")
        lines.append(f"    var {var}_matteFtg = proj.importFile(_mio{idx});")
        lines.append(f"    var {var}_matte = comp.layers.add({var}_matteFtg);")
        lines.append(f"    {var}_matte.startTime = {t0};")
        # 跨图层后处理：遮罩层紧贴素材层上方 + alpha 轨道遮罩（必须在所有图层入栈后执行）
        ctx.post_lines.append(f"    {var}_matte.moveAfter({var});")
        ctx.post_lines.append(f"    {var}_matte.outPoint = Math.min({var}.outPoint, "
                              f"{var}_matte.startTime + {var}_matteFtg.duration);")
        ctx.post_lines.append(f"    {var}.trackMatteType = TrackMatteType.ALPHA;")
    return lines


# ── 分派注册表 ────────────────────────────────────────────────────────

LAYER_BUILDERS: Dict[str, Callable[[LayerBuildContext, "LayerSpec"], List[str]]] = {
    "solid": build_solid_layer,
    "adjustment": build_adjustment_layer,
    "text": build_text_layer,
    "particle": build_particle_layer,
    "footage": build_footage_layer,
}


def build_layer(ctx: LayerBuildContext, layer: "LayerSpec") -> List[str]:
    """按 layer.type 分派到对应构建器; 未知类型抛 ValueError。"""
    builder = LAYER_BUILDERS.get(layer.type)
    if builder is None:
        raise ValueError(f"未知图层类型 {layer.type}")
    return builder(ctx, layer)


__all__ = ["js_str", "LayerBuildContext", "build_layer", "LAYER_BUILDERS"]

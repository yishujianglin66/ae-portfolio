"""SynthesisOrchestrator — 合成树 → JSX 工程 → AE Bridge 执行（M1b）

三层协作：
  CompositionTree（M1a 数据模型）
      ↓ JsxProjectBuilder.build()
  单个 JSX 工程脚本（创建合成/图层/效果/动画，返回 JSON 状态）
      ↓ AECommandClient.send_command("executeAtomScript")
  AE 真机执行

叶子节点复用：
  - 效果 combo → core.jsx_keyframe_animator.EffectLayerBuilder（31 组合 + 参数设置）
  - 效果 match → 直通 addProperty + 6 常见效果的参数索引小表
  - 入场动画 → EntranceAnimator.build_tracks（10 风格弹性缓动）
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.composition_tree import (
    AnimationSpec,
    CompositionTree,
    EffectRef,
    LayerSpec,
    validate_composition_tree,
)
from core.jsx_keyframe_animator import (
    AnimationDirection,
    AnimationTrack,
    EaseType,
    EntranceAnimator,
    EntranceStyle,
    Keyframe,
    LayerAnimation,
)
from core.layer_builders import LayerBuildContext, build_footage_layer, build_layer, js_str

# 入场动画预设名 → EntranceStyle 映射（树模板预设 → 动画器风格）
PRESET_TO_STYLE: dict[str, EntranceStyle] = {
    "fade_in": EntranceStyle.FADE_IN,
    "scale_bounce": EntranceStyle.SCALE_UP,
    "scale_up": EntranceStyle.SCALE_UP,
    "scale_down": EntranceStyle.SCALE_DOWN,
    "slide_up": EntranceStyle.SLIDE,
    "slide_down": EntranceStyle.SLIDE,
    "slide_left": EntranceStyle.SLIDE,
    "slide_right": EntranceStyle.SLIDE,
    "blur_in": EntranceStyle.BLUR_IN,
    "glitch_shake": EntranceStyle.GLITCH_IN,
    "whip_in": EntranceStyle.WHIP_IN,
    "flip_in": EntranceStyle.THREE_D_FLIP,
    "rotate_in": EntranceStyle.THREE_D_ROTATE,
    "zoom_blur": EntranceStyle.FADE_IN_ZOOM,
}

# match 效果参数映射: 由 effect_registry 统一提供 (整数位置索引维度)
from core.effect_registry import PARAM_POSITION_INDEX as MATCH_PARAM_MAP  # noqa: E402

# 动画轨道属性路径 → matchName 嵌套链（AE 2025 中文版 property() 不支持斜杠多段路径，
# 真机探测确认：单段显示名/matchName 均可，但 "Transform/Opacity" 这种斜杠路径返回 null）
_PROP_PATH_MAP: dict[str, list[str]] = {
    "Transform/Opacity": ["ADBE Transform Group", "ADBE Opacity"],
    "Transform/Position": ["ADBE Transform Group", "ADBE Position"],
    "Transform/Scale": ["ADBE Transform Group", "ADBE Scale"],
    "Transform/Rotation": ["ADBE Transform Group", "ADBE Rotation"],
    "Transform/X Rotation": ["ADBE Transform Group", "ADBE Rotate X"],
    "Transform/Y Rotation": ["ADBE Transform Group", "ADBE Rotate Y"],
    "Transform/Anchor Point": ["ADBE Transform Group", "ADBE Anchor Point"],
    "Effects/Gaussian Blur/Blurriness": [
        "ADBE Effect Parade", "ADBE Gaussian Blur 2", "ADBE Blurriness"],
}


def _prop_chain_js(prop_path: str) -> str | None:
    """把 'Transform/Opacity' 转成嵌套 .property(\"matchName\") 调用链；未知路径返回 None"""
    segs = _PROP_PATH_MAP.get(prop_path)
    if not segs:
        return None
    return "".join(f'.property("{s}")' for s in segs)


# combo 简名 → 效果库 combo_id（EffectLayerBuilder.EFFECT_COMBOS 的 31 组合）
COMBO_ALIAS: dict[str, str] = {
    "neon_glow": "effect_neon_pulse",
    "cyber_glow": "effect_neon_sign",
    "hologram": "effect_hologram_hud",
    "rgb_split": "effect_rgb_split",
    "color_grade": "effect_light_leak",   # 近似氛围调色（非精确映射，标注警告）
    "fire_ice": "effect_fire_ice",
    "glitch": "effect_cyber_glitch",
}


class JsxProjectBuilder:
    """CompositionTree → 单个 JSX 工程脚本"""

    def __init__(self):
        self._warnings: list[str] = []
        self._post_lines: list[str] = []  # 全图层构建完后追加（track matte moveAfter 等跨图层操作）

    @property
    def warnings(self) -> list[str]:
        return self._warnings

    # ── 主入口 ────────────────────────────────────────────────
    def build(self, tree: CompositionTree) -> str:
        self._warnings = []
        self._post_lines = []
        res = validate_composition_tree(tree)
        if not res["ok"]:
            raise ValueError(f"合成树校验失败: {res['errors']}")
        self._warnings.extend(res["warnings"])

        lines: list[str] = []
        ctx = LayerBuildContext(tree, self._warnings, self._post_lines)
        lines.append("(function() {")
        lines.append("  var _result = {};")
        lines.append("  try {")
        lines.append("    var proj = app.project;")
        lines.append(f"    var comp = proj.items.addComp(\"{js_str(tree.comp_name)}\", "
                     f"{tree.width}, {tree.height}, 1.0, {tree.duration}, {tree.fps});")
        lines.append("    comp.bgColor = [0, 0, 0];")
        # 图层循环（z_index 升序 = AE 图层栈从底到顶）
        for layer in sorted(tree.layers, key=lambda l: l.z_index):
            lines.extend(self._build_layer(ctx, layer))
        # 跨图层后处理（track matte 紧邻调整等）
        if self._post_lines:
            lines.append("    // ── 跨图层后处理 ──")
            lines.extend(self._post_lines)
        lines.append("    _result = {status:\"success\", comp:\"%s\", layers:%d, layers_actual:comp.numLayers};" % (
            js_str(tree.comp_name), len(tree.layers)))
        lines.append("  } catch(e) {")
        lines.append("    _result = {status:\"error\", message:String(e) + \" [line \" + e.line + \"]\"};")
        lines.append("  }")
        lines.append("  return JSON.stringify(_result);")
        lines.append("})();")
        return "\n".join(lines)

    # ── 图层构建 ──────────────────────────────────────────────
    def build_batches(self, tree: CompositionTree, max_chars: int = 24000) -> list[str]:
        """分块生成 (2026-08-17): ExtendScript 单脚本 ~32KB 截断 — 30 层树 JSX 55KB,
        后半被静默丢弃 → drop/outro 层从未创建, 成片后半黑屏 (seg1-3 实测)。
        分批: 首批建 comp, 后续批按 comp 名找回继续加层, 尾批跑 post_lines。
        """
        self._warnings = []
        self._post_lines = []
        res = validate_composition_tree(tree)
        if not res["ok"]:
            raise ValueError(f"合成树校验失败: {res['errors']}")
        self._warnings.extend(res["warnings"])

        ctx = LayerBuildContext(tree, self._warnings, self._post_lines)
        layer_chunks = ["\n".join(self._build_layer(ctx, l))
                        for l in sorted(tree.layers, key=lambda x: x.z_index)]

        head_first = (
            "(function() {\n  var _result = {};\n  try {\n"
            "    var proj = app.project;\n"
            f"    var comp = proj.items.addComp(\"{js_str(tree.comp_name)}\", "
            f"{tree.width}, {tree.height}, 1.0, {tree.duration}, {tree.fps});\n"
            "    comp.bgColor = [0, 0, 0];\n"
        )
        head_next = (
            "(function() {\n  var _result = {};\n  try {\n"
            "    var proj = app.project;\n    var comp = null;\n"
            "    for (var _i = 1; _i <= proj.numItems; _i++) {\n"
            "      var _it = proj.item(_i);\n"
            "      if (_it instanceof CompItem && _it.name == "
            f"\"{js_str(tree.comp_name)}\") {{ comp = _it; break; }}\n"
            "    }\n"
            '    if (!comp) { _result = {status:"error", message:"comp not found for batch"};'
            " return JSON.stringify(_result); }\n"
        )
        tail_mid = (
            '    _result = {status:"success", batch:true, layers:comp.numLayers};\n'
            "  } catch(e) {\n"
            '    _result = {status:"error", message:String(e) + " [line " + e.line + "]"};\n'
            "  }\n  return JSON.stringify(_result);\n})();"
        )
        post_part = ""
        if self._post_lines:
            post_part = "    // post\n" + "\n".join(self._post_lines) + "\n"
        tail_last = post_part + (
            '    _result = {status:"success", comp:"' + js_str(tree.comp_name)
            + f'", layers:{len(tree.layers)}, layers_actual:comp.numLayers}};\n'
            "  } catch(e) {\n"
            '    _result = {status:"error", message:String(e) + " [line " + e.line + "]"};\n'
            "  }\n  return JSON.stringify(_result);\n})();"
        )

        batches = []
        cur = []
        cur_len = len(head_first)
        head = head_first
        for chunk in layer_chunks:
            if cur and cur_len + len(chunk) > max_chars:
                batches.append(head + "\n".join(cur) + "\n" + tail_mid)
                cur = []
                cur_len = len(head_next)
                head = head_next
            cur.append(chunk)
            cur_len += len(chunk) + 1
        if cur:
            batches.append(head + "\n".join(cur) + "\n" + tail_last)
        return batches

    def _build_layer(self, ctx: LayerBuildContext, layer: LayerSpec) -> list[str]:
        """类型创建分派（core/layer_builders.py）+ 类型无关后处理。

        gen_fx 在此校验素材已预备（resolve 在 execute() 预备阶段完成），
        JSX 生成复用 footage 路径。
        """
        var = f"layer{layer.z_index}"
        lines: list[str] = [f"    // ── 图层 {layer.id} ({layer.type}) ──"]
        if layer.type == "gen_fx":
            # M6: 素材已在 execute() 预备阶段生成并写回 content.path，
            # JSX 生成完全复用 footage 导入逻辑
            if not layer.content.get("path"):
                raise ValueError(f"gen_fx 层 {layer.id} 未预备素材（缺 content.path），"
                                 f"请先经 resolve_gen_fx_layers 或 orchestrator.execute")
            lines.extend(build_footage_layer(ctx, layer))
        else:
            lines.extend(build_layer(ctx, layer))
        # 效果
        lines.extend(self._build_effects(layer, var))
        # 动画
        lines.extend(self._build_animations(layer, layer.z_index, var))
        # M7 字符级动画（Text Animator 扫动 stagger, 仅 text 层）
        if layer.type == "text":
            lines.extend(self._build_char_animator(layer, var))
        # M7 效果语汇：punch/shake/rgb_burst（确定性节拍增强, 顶尖 edit 语汇）
        lines.extend(self._build_edit_fx(layer, var))
        # P8: 速度斜坡（timeRemap）— 仅动态素材层; content.speed_ramps=[{t,v}...]
        # 2026-08-17 约定: speed_ramps[].t 为**层局部时间**（0 ~ 镜头时长）,
        # ramps 使用层局部时间；offset 由图层 time_range 起点映射到合成时间轴。
        if layer.type == "footage" and layer.content.get("speed_ramps"):
            from core.edit_fx_vocabulary import speed_ramp_jsx
            try:
                sdur = float(layer.content.get("source_dur", ctx.tree.duration))
                src_in = float(layer.content.get("source_in", 0) or 0)
                lines.append(speed_ramp_jsx(
                    var, sdur, layer.content["speed_ramps"],
                    offset=float(layer.time_range[0]), source_in=src_in,
                ))
            except Exception as e:  # noqa: BLE001
                self._warnings.append(f"素材层 {layer.id} speed_ramp 失败: {e}")
        return lines

    @staticmethod
    def _bind_beats_to_edit_fx(tree: CompositionTree) -> None:
        """M7 节拍绑定：edit_fx 缺 times 时由 beat_events 按 beat_type 自动填充。

        kick → punch(推拉) / snare → rgb_burst(色差爆开) / 其余 → glow_hit(闪光)。
        节拍事件需带 layer_id 才作用到对应图层; 无 layer_id 的事件作用于全部含 edit_fx 的图层。
        """
        if not tree.beat_events:
            return
        by_type: dict[str, list[float]] = {}
        for ev in tree.beat_events:
            by_type.setdefault(str(ev.get("beat_type", "any")), []).append(float(ev.get("time", 0)))
        kicks = by_type.get("kick", [])
        snares = by_type.get("snare", [])
        others = [t for k, ts in by_type.items() if k not in ("kick", "snare") for t in ts]
        for layer in tree.layers:
            fx = layer.content.get("edit_fx")
            if not fx:
                continue
            for name, src in (("punch", kicks), ("rgb_burst", snares), ("glow_hit", others)):
                if name in fx and not fx[name].get("times"):
                    fx[name]["times"] = sorted({round(t, 3) for t in src})

    def _build_edit_fx(self, layer: LayerSpec, var: str) -> list[str]:
        """edit_fx 注入: content.edit_fx = {punch:{...}, shake:{...}, rgb_burst:{...}, glow_hit:{...}}"""
        fx = layer.content.get("edit_fx")
        if not fx:
            return []
        from core.edit_fx_vocabulary import glow_hit_jsx, rgb_burst_jsx, shake_jsx, zoom_punch_jsx
        lines: list[str] = ["    // ── edit_fx（节拍语汇）──"]
        try:
            if "punch" in fx:
                p = fx["punch"]
                lines.append(zoom_punch_jsx(var, p.get("times", []),
                                            p.get("amount", 8.0),
                                            p.get("settle_s", 0.28)))
            if "shake" in fx:
                s = fx["shake"]
                lines.append(shake_jsx(var, s.get("freq", 14.0), s.get("amp", 12.0),
                                        s.get("axis", "both"), s.get("seed", 1),
                                        s.get("start"), s.get("end")))
            if "rgb_burst" in fx:
                b = fx["rgb_burst"]
                lines.append(rgb_burst_jsx(var, b.get("times", []),
                                            max_amount=b.get("max_amount", 25.0),
                                            recover_s=b.get("recover_s", 0.18)))
            if "glow_hit" in fx:
                g = fx["glow_hit"]
                lines.append(glow_hit_jsx(var, g.get("times", []),
                                           g.get("intensity", 2.0)))
        except Exception as e:  # noqa: BLE001 — 语汇注入失败降级为警告
            self._warnings.append(f"图层 {layer.id} edit_fx 注入失败: {e}")
        return lines

    def _build_char_animator(self, layer: LayerSpec, var: str) -> list[str]:
        """字符级动画（M7）: AE Text Animator 脚手架 + Offset 扫动 stagger。

        content.char_anim = {"preset": "tracking_stagger", "duration_ms": 450,
                             "tracking": 18, "rotation": 0}
        真机探测确认的 matchName（AE 2025 中文版）:
          animator: ADBE Text Animator | selector: addProperty('Range Selector')
          Offset: ADBE Text Percent Offset | 属性: ADBE Text Opacity/Rotation/Tracking Amount
        原理: Offset 100→-100 扫动 = 选中区从全字符退到零 → 逐字符点亮;
        Tracking 正值随扫过回收 = 顶尖 edit 的字距聚拢入场。
        """
        ca = layer.content.get("char_anim")
        if not ca:
            return []
        t0 = layer.time_range[0]
        d = float(ca.get("duration_ms", 450)) / 1000.0
        tracking = float(ca.get("tracking", 18))
        rot = float(ca.get("rotation", 0))
        preset = str(ca.get("preset", "tracking_stagger"))
        tag = var.replace("layer", "c")
        off = f"_sel{tag}.property('ADBE Text Percent Offset')"
        lines = [
            f"    // ── 字符级动画 {preset}（Text Animator 扫动 stagger）──",
            f"    var _ta{tag} = {var}.property('ADBE Text Properties')"
            f".property('ADBE Text Animators').addProperty('ADBE Text Animator');",
            f"    var _sel{tag} = _ta{tag}.property('ADBE Text Selectors')"
            f".addProperty('Range Selector');",
            f"    var _props{tag} = _ta{tag}.property('ADBE Text Animator Properties');",
        ]
        try:
            lines.append(
                f"    var _op{tag} = _props{tag}.addProperty('ADBE Text Opacity');"
                f" if (_op{tag}) _op{tag}.setValue(0); // 选中区隐藏(0=透明, Animator范围0-100), 扫过点亮"
            )
            if tracking:
                lines.append(
                    f"    var _trk{tag} = _props{tag}.addProperty('ADBE Text Tracking Amount');"
                    f" if (_trk{tag}) _trk{tag}.setValue({tracking:.1f}); // 字距聚拢"
                )
            if rot:
                lines.append(
                    f"    var _rot{tag} = _props{tag}.addProperty('ADBE Text Rotation');"
                    f" if (_rot{tag}) _rot{tag}.setValue({rot:.1f});"
                )
            lines.append(
                f"    {off}.setValuesAtTimes([{t0:.3f}, {t0 + d:.3f}], [100, -100]);"
            )
        except Exception as e:  # noqa: BLE001
            self._warnings.append(f"图层 {layer.id} char_anim 生成失败: {e}")
        return lines

    def _build_effects(self, layer: LayerSpec, var: str) -> list[str]:
        lines: list[str] = []
        for eff in layer.effects:
            if eff.kind == "combo":
                try:
                    from core.jsx_keyframe_animator import AnimationIntensity, get_effect_builder
                    builder = get_effect_builder()
                    combo_id = COMBO_ALIAS.get(eff.value, eff.value)
                    if combo_id != eff.value:
                        self._warnings.append(f"combo {eff.value} 映射为 {combo_id}")
                    inten_str = eff.params.get("intensity", "moderate")
                    try:
                        inten = AnimationIntensity(inten_str)
                    except ValueError:
                        self._warnings.append(f"强度 {inten_str} 非法，降级 moderate")
                        inten = AnimationIntensity.MODERATE
                    config = builder.build_effect_config(
                        combo_id=combo_id,
                        intensity=inten,
                    )
                    jsx = builder.to_jsx(config, var)
                    if jsx:
                        lines.append(jsx)
                    else:
                        self._warnings.append(f"combo {eff.value}({combo_id}) 无配置")
                except Exception as e:
                    self._warnings.append(f"combo {eff.value} 构建失败: {e}")
            elif eff.kind == "match":
                mn = eff.value
                lines.append(f'    var _fx = {var}.property("ADBE Effect Parade").addProperty("{mn}");')
                param_map = MATCH_PARAM_MAP.get(mn, {})
                for pname, pval in eff.params.items():
                    if pname in param_map:
                        idx = param_map[pname]
                        lines.append(f"    if (_fx) _fx.property({idx}).setValue({self._fmt_js(pval)});")
                    else:
                        self._warnings.append(f"match 效果 {mn} 参数 {pname} 无索引映射，跳过")
        return lines

    def _build_animations(self, layer: LayerSpec, idx: int, var: str) -> list[str]:
        lines: list[str] = []
        animator = EntranceAnimator()
        start = layer.time_range[0]
        # entrance
        ent = layer.animations.get("entrance")
        if ent:
            style = PRESET_TO_STYLE.get(ent.preset)
            if style is None:
                self._warnings.append(f"图层 {layer.id} 入场预设 {ent.preset} 未映射，降级 fade_in")
                style = EntranceStyle.FADE_IN
            direction = AnimationDirection.FROM_CENTER
            if ent.preset in ("slide_up", "slide_down"):
                direction = AnimationDirection.FROM_CENTER
            tracks = animator.build_tracks(style, layer_start=start,
                                           duration=ent.duration_ms / 1000.0,
                                           direction=direction)
            lines.append(f"    // 入场动画 {ent.preset}")
            for track in tracks:
                chain = _prop_chain_js(track.property_path)
                if chain is None:
                    self._warnings.append(
                        f"入场轨道路径 {track.property_path} 无 matchName 映射，跳过")
                    continue
                for kf in track.keyframes:
                    lines.append(
                        f"    {var}{chain}"
                        f".setValueAtTime({kf.time:.3f}, {self._fmt_js(kf.value)});"
                    )
        # exit：简化为 opacity 淡出
        ex = layer.animations.get("exit")
        if ex:
            dur = ex.duration_ms / 1000.0
            end = layer.time_range[1]
            lines.append("    // 出场淡出")
            lines.append(
                f"    {var}.property(\"ADBE Transform Group\").property(\"ADBE Opacity\")"
                f".setValueAtTime({end - dur:.3f}, 100);"
            )
            lines.append(
                f"    {var}.property(\"ADBE Transform Group\").property(\"ADBE Opacity\")"
                f".setValueAtTime({end:.3f}, 0);"
            )
        return lines

    # ── 工具 ──────────────────────────────────────────────────
    @staticmethod
    def _fmt_js(val: Any) -> str:
        if isinstance(val, (list, tuple)):
            return "[" + ", ".join(str(v) for v in val) + "]"
        if isinstance(val, str):
            return f'"{val}"'
        return str(val)


class SynthesisOrchestrator:
    """树 → JSX → Bridge → 结果（M1b 执行入口）"""

    def __init__(self, builder: JsxProjectBuilder | None = None):
        self.builder = builder or JsxProjectBuilder()

    def generate_jsx(self, tree: CompositionTree) -> str:
        return self.builder.build(tree)

    def execute(self, tree: CompositionTree, client: Any = None,
                dry_run: bool = False,
                sections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """校验 → gen_fx 素材预备 → 段落编排 → 生成 → 执行。

        sections: [{"type":"drop","start":..,"end":..}] 传入则按段落变奏编排
        （P5 呼吸感; 不传则按 beat_type 默认绑定）。
        """
        res = validate_composition_tree(tree)
        if not res["ok"]:
            return {"status": "invalid", "errors": res["errors"]}
        gen_fx_count = 0
        try:
            from core.gen_fx_provider import resolve_gen_fx_layers
            gen_fx_count = resolve_gen_fx_layers(tree)
        except Exception as e:  # noqa: BLE001 — 素材生成失败即整体失败
            return {"status": "error", "message": f"gen_fx 素材生成失败: {e}"}
        if sections:
            from core.section_arranger import arrange_sections
            arrange_sections(tree, sections)
        else:
            self.builder._bind_beats_to_edit_fx(tree)
        jsx = self.builder.build(tree)
        if dry_run:
            return {"status": "dry_run", "jsx": jsx,
                    "gen_fx_materials": gen_fx_count,
                    "warnings": self.builder.warnings}
        try:
            from ae.ae_command_client import AECommandClient
            client = client or AECommandClient(timeout=None)
            # 2026-08-17: JSX > 30KB 走分批 (ExtendScript ~32KB 截断, 见 build_batches)
            if len(jsx) > 30000:
                batches = self.builder.build_batches(tree)
                last = None
                for bi, bs in enumerate(batches):
                    r = client.send_command("executeAtomScript", {"script": bs})
                    last = r
                    if str(r.get("status")) != "success":
                        return {"status": "error",
                                "message": f"batch {bi + 1}/{len(batches)} failed: {r}",
                                "result": r, "gen_fx_materials": gen_fx_count,
                                "warnings": self.builder.warnings}
                return {"status": last.get("status", "unknown"), "result": last,
                        "batches": len(batches),
                        "gen_fx_materials": gen_fx_count,
                        "warnings": self.builder.warnings}
            result = client.send_command("executeAtomScript", {"script": jsx})
            return {"status": result.get("status", "unknown"), "result": result,
                    "gen_fx_materials": gen_fx_count,
                    "warnings": self.builder.warnings}
        except Exception as e:
            return {"status": "error", "message": str(e),
                    "gen_fx_materials": gen_fx_count,
                    "warnings": self.builder.warnings}


__all__ = ["JsxProjectBuilder", "SynthesisOrchestrator", "PRESET_TO_STYLE", "MATCH_PARAM_MAP"]

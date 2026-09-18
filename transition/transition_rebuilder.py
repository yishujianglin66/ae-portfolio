#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transition_rebuilder.py — 转场自动重建器
==========================================

根据 VRS v2 检测到的转场类型，自动在 AE 中创建对应的转场效果。

支持的转场类型：
  - linear_wipe:    线性擦除（直线擦除 + 关键帧动画）
  - radial_wipe:    径向擦除（扇形擦除）
  - zoom_blur:      缩放模糊（径向模糊 + 缩放关键帧）
  - glitch:         故障风格（通道偏移 + 噪波置换）
  - light_leak:     光效叠加（渐变 + Screen 混合）
  - ink_spread:     墨水扩散（湍流置换 + 蒙版动画）
  - card_flip:      卡片翻转（3D 旋转 + 卡片擦除）
  - block_dissolve: 像素方块化（CC Block Load）
  - fade:           淡入淡出（不透明度关键帧）
  - slide:          滑动（位置关键帧）

用法：
    from transition_rebuilder import TransitionRebuilder

    rebuilder = TransitionRebuilder()
    jsx = rebuilder.generate_transition_jsx(
        transition_type="linear_wipe",
        layer_a_name="Scene_A",
        layer_b_name="Scene_B",
        start_time=3.0,
        duration=0.8,
    )
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# VRS 转场类型 → AE 实现映射
# ---------------------------------------------------------------------------
TRANSITION_IMPL_MAP: dict[str, dict[str, Any]] = {
    "linear_wipe": {
        "display_name": "线性擦除",
        "effect_match": "ADBE Linear Wipe",
        "params": {
            "Wipe Angle": 0,
            "Feather": 30,
        },
        "animate": {
            "Transition Completion": {"from": 0, "to": 100},
        },
    },
    "radial_wipe": {
        "display_name": "径向擦除",
        "effect_match": "ADBE Radial Wipe",
        "params": {
            "Center": [50, 50],
            "Start Angle": 0,
            "Feather": 30,
        },
        "animate": {
            "Transition Completion": {"from": 0, "to": 100},
        },
    },
    "zoom_blur": {
        "display_name": "缩放模糊转场",
        "effect_match": "CC Radial Fast Blur",
        "params": {
            "Amount": 0,
            "Center": [50, 50],
        },
        "animate": {
            "Amount": {"from": 0, "to": 80, "back": 0},
        },
        "extra_jsx": "scale_zoom",
    },
    "glitch": {
        "display_name": "故障风格转场",
        "effects": [
            {
                "match": "ADBE Turbulent Displace",
                "params": {"Amount": 0, "Size": 30},
                "animate": {"Amount": {"from": 0, "to": 200, "back": 0}},
            },
            {
                "match": "ADBE Fractal Noise",
                "params": {
                    "Noise Type": "Blocky",
                    "Contrast": 200,
                    "Brightness": -50,
                    "Scale": [5, 80],
                },
                "animate": {},
            },
        ],
        "blend_mode": "BlendingMode.SCREEN",
        "opacity_animate": {"from": 0, "to": 100, "back": 0},
    },
    "light_leak": {
        "display_name": "光效叠加转场",
        "layer_type": "solid",
        "solid_color": "[1, 0.8, 0.4]",
        "effects": [
            {
                "match": "ADBE Fractal Noise",
                "params": {
                    "Noise Type": "Clouds",
                    "Contrast": 150,
                    "Brightness": 30,
                    "Scale": [200, 200],
                },
                "animate": {},
            },
            {
                "match": "ADBE Ramp",
                "params": {
                    "Start Color": [1, 0.6, 0.2, 1],
                    "End Color": [1, 0.2, 0.1, 0],
                    "Gradient Shape": 1,
                },
                "animate": {},
            },
        ],
        "blend_mode": "BlendingMode.SCREEN",
        "opacity_animate": {"from": 0, "to": 80, "back": 0},
    },
    "ink_spread": {
        "display_name": "墨水扩散转场",
        "effect_match": "ADBE Turbulent Displace",
        "params": {
            "Amount": 0,
            "Size": 80,
            "Complexity": 5,
        },
        "animate": {
            "Amount": {"from": 0, "to": 500},
        },
    },
    "card_flip": {
        "display_name": "卡片翻转",
        "effect_match": "ADBE Card Wipe",
        "params": {},
        "animate": {
            "Transition Completion": {"from": 0, "to": 100},
        },
    },
    "block_dissolve": {
        "display_name": "像素方块化",
        "effect_match": "CC Block Load",
        "params": {
            "BlockSize": 20,
        },
        "animate": {
            "Transition Completion": {"from": 0, "to": 100},
        },
    },
    "fade": {
        "display_name": "淡入淡出",
        "type": "opacity_keyframes",
    },
    "slide": {
        "display_name": "滑动转场",
        "type": "position_keyframes",
    },
}

# 硬编码 fallback（知识库加载失败时使用）
_HARDCODED_TRANSITION_MAP: dict[str, dict[str, Any]] = {
    k: dict(v) for k, v in TRANSITION_IMPL_MAP.items()
}

# ---------------------------------------------------------------------------
# 知识库集成：从 10-风格化剪辑知识库/ 动态加载转场配方
# 知识库配方优先，硬编码 fallback 补充缺失条目
# ---------------------------------------------------------------------------
_KB_LOADED = False

def _load_knowledge_base():
    """从知识库动态加载转场配方"""
    global _KB_LOADED
    if _KB_LOADED:
        return

    try:
        import sys
        sys.path.insert(0, str(__file__).rsplit("\\", 2)[0])
        from kb_loader import KBLoader
        loader = KBLoader()
        kb_trans_map = loader.get_transition_map()

        added = 0
        for trans_type, data in kb_trans_map.items():
            if trans_type not in TRANSITION_IMPL_MAP:
                TRANSITION_IMPL_MAP[trans_type] = data
                added += 1

        print(f"[transition_rebuilder] 知识库加载: 新增 {added} 个转场配方，总计 {len(TRANSITION_IMPL_MAP)}")
        _KB_LOADED = True
    except Exception as e:
        print(f"[transition_rebuilder] 知识库加载失败(非致命): {e}")


_load_knowledge_base()


class TransitionRebuilder:
    """转场自动重建器。"""

    def generate_transition_jsx(
        self,
        transition_type: str,
        layer_a_name: str = "Scene_A",
        layer_b_name: str = "Scene_B",
        start_time: float = 0.0,
        duration: float = 0.8,
        comp_width: int = 1920,
        comp_height: int = 1080,
    ) -> str:
        """根据转场类型生成 JSX 脚本。

        Args:
            transition_type: VRS 检测到的转场类型
            layer_a_name: 场景A图层名
            layer_b_name: 场景B图层名
            start_time: 转场开始时间（秒）
            duration: 转场持续时间（秒）
            comp_width: 合成宽度
            comp_height: 合成高度

        Returns:
            JSX 脚本字符串
        """
        impl = TRANSITION_IMPL_MAP.get(transition_type)
        if not impl:
            return self._generate_fallback_jsx(transition_type, start_time, duration)

        trans_type = impl.get("type", "effect")

        if trans_type == "opacity_keyframes":
            return self._generate_fade_jsx(layer_a_name, layer_b_name, start_time, duration)
        elif trans_type == "position_keyframes":
            return self._generate_slide_jsx(layer_a_name, layer_b_name, start_time, duration,
                                              comp_width, comp_height)
        else:
            return self._generate_effect_transition_jsx(
                impl, transition_type, layer_b_name, start_time, duration,
                comp_width, comp_height,
            )

    def list_supported_transitions(self) -> list[dict[str, str]]:
        """返回所有支持的转场类型。"""
        result = []
        for key, val in TRANSITION_IMPL_MAP.items():
            result.append({
                "type": key,
                "display_name": val.get("display_name", key),
            })
        return result

    # =========================================================================
    # 内部生成方法
    # =========================================================================

    def _generate_effect_transition_jsx(
        self,
        impl: dict[str, Any],
        transition_type: str,
        target_layer: str,
        start_time: float,
        duration: float,
        comp_width: int,
        comp_height: int,
    ) -> str:
        """生成基于效果的转场 JSX。"""
        lines = [
            f"// Transition: {impl.get('display_name', transition_type)}",
            'var targetLayer = null;',
            'for (var i = 1; i <= thisComp.numLayers; i++) {',
            f'  if (thisComp.layer(i).name === "{target_layer}") {{',
            '    targetLayer = thisComp.layer(i);',
            '    break;',
            '  }',
            '}',
            f'if (!targetLayer) {{ alert("Layer not found: {target_layer}"); }}',
            f'var st = {start_time};',
            f'var dur = {duration};',
            '',
        ]

        # 单效果转场
        if "effect_match" in impl:
            match_name = impl["effect_match"]
            params = impl.get("params", {})
            animate = impl.get("animate", {})

            lines.append(f'var eff = targetLayer.Effects.addProperty("{match_name}");')
            lines.append(f'eff.name = "{impl.get("display_name", transition_type)}";')

            # 静态参数
            for pname, pval in params.items():
                lines.append(f'eff.property("{pname}").setValue({self._format_jsx_val(pval)});')

            # 动画参数（关键帧）
            for pname, anim in animate.items():
                from_val = anim.get("from", 0)
                to_val = anim.get("to", 100)
                lines.append(f'var prop = eff.property("{pname}");')
                lines.append(f'prop.setValueAtTime(st, {from_val});')
                lines.append(f'prop.setValueAtTime(st + dur, {to_val});')
                if "back" in anim:
                    lines.append(f'prop.setValueAtTime(st + dur, {anim["back"]});')

        # 多效果转场（glitch, light_leak 等）
        if "effects" in impl:
            for idx, eff_def in enumerate(impl["effects"]):
                match_name = eff_def["match"]
                params = eff_def.get("params", {})
                animate = eff_def.get("animate", {})

                lines.append(f'var eff{idx} = targetLayer.Effects.addProperty("{match_name}");')
                for pname, pval in params.items():
                    lines.append(f'eff{idx}.property("{pname}").setValue({self._format_jsx_val(pval)});')
                for pname, anim in animate.items():
                    lines.append(f'var prop{idx} = eff{idx}.property("{pname}");')
                    lines.append(f'prop{idx}.setValueAtTime(st, {anim.get("from", 0)});')
                    lines.append(f'prop{idx}.setValueAtTime(st + dur * 0.5, {anim.get("to", 100)});')
                    if "back" in anim:
                        lines.append(f'prop{idx}.setValueAtTime(st + dur, {anim["back"]});')

            # 混合模式和不透明度
            if "blend_mode" in impl:
                lines.append(f'targetLayer.blendingMode = {impl["blend_mode"]};')
            if "opacity_animate" in impl:
                oa = impl["opacity_animate"]
                lines.append(f'targetLayer.opacity.setValueAtTime(st, {oa.get("from", 0)});')
                lines.append(f'targetLayer.opacity.setValueAtTime(st + dur * 0.5, {oa.get("to", 100)});')
                if "back" in oa:
                    lines.append(f'targetLayer.opacity.setValueAtTime(st + dur, {oa["back"]});')

        lines.append('')
        return '\n'.join(lines)

    def _generate_fade_jsx(
        self, layer_a: str, layer_b: str, start_time: float, duration: float
    ) -> str:
        """淡入淡出转场。"""
        return f"""// Transition: 淡入淡出
var layerA = null, layerB = null;
for (var i = 1; i <= thisComp.numLayers; i++) {{
  if (thisComp.layer(i).name === "{layer_a}") layerA = thisComp.layer(i);
  if (thisComp.layer(i).name === "{layer_b}") layerB = thisComp.layer(i);
}}
var st = {start_time};
var dur = {duration};

if (layerA) {{
  layerA.opacity.setValueAtTime(st, 100);
  layerA.opacity.setValueAtTime(st + dur, 0);
}}
if (layerB) {{
  layerB.opacity.setValueAtTime(st, 0);
  layerB.opacity.setValueAtTime(st + dur, 100);
}}
"""

    def _generate_slide_jsx(
        self, layer_a: str, layer_b: str, start_time: float, duration: float,
        comp_width: int, comp_height: int,
    ) -> str:
        """滑动转场。"""
        return f"""// Transition: 滑动转场
var layerA = null, layerB = null;
for (var i = 1; i <= thisComp.numLayers; i++) {{
  if (thisComp.layer(i).name === "{layer_a}") layerA = thisComp.layer(i);
  if (thisComp.layer(i).name === "{layer_b}") layerB = thisComp.layer(i);
}}
var st = {start_time};
var dur = {duration};
var w = {comp_width};

if (layerA) {{
  layerA.position.setValueAtTime(st, [w/2, {comp_height}/2]);
  layerA.position.setValueAtTime(st + dur, [-w/2, {comp_height}/2]);
}}
if (layerB) {{
  layerB.position.setValueAtTime(st, [w*1.5, {comp_height}/2]);
  layerB.position.setValueAtTime(st + dur, [w/2, {comp_height}/2]);
}}
"""

    def _generate_fallback_jsx(
        self, transition_type: str, start_time: float, duration: float
    ) -> str:
        """未知转场类型的降级处理 — 使用不透明度淡入淡出。"""
        return f"""// Transition: {transition_type} (fallback to fade)
// Unknown transition type, using opacity fade as fallback
var st = {start_time};
var dur = {duration};
var layer = thisComp.selectedLayers[0];
if (layer) {{
  layer.opacity.setValueAtTime(st, 100);
  layer.opacity.setValueAtTime(st + dur * 0.5, 0);
  layer.opacity.setValueAtTime(st + dur, 100);
}}
"""

    @staticmethod
    def _format_jsx_val(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, list):
            return f'[{", ".join(str(v) for v in value)}]'
        return str(value)


# ============================================================================
# CLI 测试入口
# ============================================================================

if __name__ == "__main__":
    rebuilder = TransitionRebuilder()

    print("支持的转场类型:")
    for t in rebuilder.list_supported_transitions():
        print(f"  {t['type']:20s} → {t['display_name']}")

    print("\n" + "=" * 60)
    print("linear_wipe 转场 JSX:")
    print("=" * 60)
    print(rebuilder.generate_transition_jsx("linear_wipe", "Scene_A", "Scene_B", 3.0, 0.8))

    print("\n" + "=" * 60)
    print("glitch 转场 JSX:")
    print("=" * 60)
    print(rebuilder.generate_transition_jsx("glitch", "Scene_A", "Scene_B", 5.0, 0.6))

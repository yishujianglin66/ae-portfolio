#!/usr/bin/env python3
"""
reverse_engineer_pipeline.py - AEP 逆向工程统一流水线

一键完成：AEP 二进制扫描 → 知识提取 → 风格匹配 → JSX 预设生成 → 入库

用法：
    # 扫描单个 AEP
    python reverse_engineer_pipeline.py --aep path/to/project.aep

    # 批量扫描目录
    python reverse_engineer_pipeline.py --aep-dir "D:/BaiduNetdiskDownload/AE新手10套"

    # 仅生成风格预设（不扫描）
    python reverse_engineer_pipeline.py --generate-presets

    # 指定输出目录
    python reverse_engineer_pipeline.py --aep path/to/project.aep --output-dir ./output
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
import re as _re
from typing import Any, Dict, List, Optional

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

from aep_binary_parser import AEPParser
from aep_analyzer.knowledge_extractor import KnowledgeExtractor
from aep_analyzer.template_learner import TemplateLearner
from aep_analyzer.preset_generator import (
    STYLE_RECIPES,
    detect_matching_styles,
    generate_full_preset_json,
    generate_preset_entry,
)
from aep_analyzer.report import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# matchName 过滤器：区分「顶层效果」与「子参数/属性组/变换属性」
# ---------------------------------------------------------------------------

# 已知的非效果 matchName 模式（属性组、变换维度、子参数容器等）
_NON_EFFECT_PATTERNS: List[str] = [
    r".*-\d{4}$",          # 子参数: ADBE Ramp-0000, ADBE Glo2-0004
    r".*_\d+$",            # 分离维度: ADBE Position_0, ADBE Scale_1
    r"^ADBE Group( End)?",  # 属性组
    r"^ADBE Transform Group",
    r"^ADBE Effect Built In Params",
    r"^ADBE (Position|Orientation|Scale|Anchor Point|Rotation)",
    r"^ADBE Opacity",
    r"^ADBE Camera .*",     # 相机属性: Camera Options Group, Camera Focus Area Width
    r"^ADBE Rotate [XYZ]",  # 3D 图层旋转属性
    r"^ADBE Envir .*",      # 环境反射属性
    r"^ADBE Blend Options Group$",
    r"^ADBE Adv Blend Group$",
    r"^ADBE Layer Styles$",  # 图层样式属性组
    r"^ADBE Material Options",
    r"^ADBE (Extrsn|Bevel|Casts|Accepts|Light Trans)",  # 3D 材质属性
    r"^ADBE Plane .*",  # 3D 平面属性
    r"(Shadow Color|Appears in Reflection|Ambient Coefficient|Diffuse Coefficient|Specular Coefficient|Metal Coefficient|Reflection Coefficient|Glossiness Coefficient|Fresnel Coefficient|Transparency Coefficient|Transp Rolloff|Index of Refraction|Shininess Coefficient)",  # 3D 材质子属性
    r"^ADBE Audio Group$",
    r"^ADBE Layer Sets$",
]

_NON_EFFECT_RES = [_re.compile(p) for p in _NON_EFFECT_PATTERNS]


def _is_top_level_effect(match_name: str) -> bool:
    """判断 matchName 是否为顶层效果（非子参数/属性组）。"""
    if not match_name:
        return False
    for pat in _NON_EFFECT_RES:
        if pat.search(match_name):
            return False
    return True


def _filter_top_effects(match_names: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """过滤出顶层效果 matchName 条目。"""
    return [mn for mn in match_names if _is_top_level_effect(mn.get("matchName", ""))]


# ---------------------------------------------------------------------------
# 核心流水线
# ---------------------------------------------------------------------------

def scan_aep_binary(aep_path: Path) -> Dict[str, Any]:
    """Step 1: 二进制扫描 AEP 文件。

    提取 compositions / layers / matchNames / file_paths 等。
    """
    logger.info(f"[1/5] 二进制扫描: {aep_path.name} ({aep_path.stat().st_size / 1024 / 1024:.1f} MB)")
    parser = AEPParser(aep_path)
    result = parser.parse()
    summary = result.get("summary", {})
    logger.info(
        f"  -> 合成 {summary.get('compositions', 0)} | "
        f"图层 {summary.get('layers', 0)} | "
        f"matchName {summary.get('unique_match_names', 0)} 种 | "
        f"素材路径 {summary.get('unique_file_paths', 0)} 条"
    )
    return result


def extract_knowledge(binary_result: Dict[str, Any]) -> Dict[str, Any]:
    """Step 2: 从二进制扫描结果提取知识。

    将 binary parser 的输出适配为 KnowledgeExtractor 期望的格式。
    """
    logger.info("[2/5] 知识提取...")

    # 将 binary parser 结果适配为 analyzer report 格式
    report = _adapt_binary_to_report(binary_result)

    extractor = KnowledgeExtractor()
    knowledge = extractor.extract_all(report)

    # 统计
    chains = knowledge.get("effect_chains", [])
    kf = knowledge.get("keyframe_patterns", {})
    logger.info(
        f"  -> 效果链 {len(chains)} 种 | "
        f"关键帧 {kf.get('total_keyframes', 0)} 个 | "
        f"贝塞尔曲线 {kf.get('bezier_curve_count', 0)} 条"
    )
    return knowledge


def detect_styles_matches(
    binary_result: Dict[str, Any],
    threshold: float = 0.4,
) -> List[Dict[str, Any]]:
    """Step 3: 将提取的效果与已知风格配方匹配。"""
    logger.info("[3/5] 风格匹配...")

    # 收集所有 matchName（仅顶层效果）
    all_match_names: set = set()
    for mn in _filter_top_effects(binary_result.get("match_names", [])):
        name = mn.get("matchName", "")
        if name:
            all_match_names.add(name)

    # 对每个合成/图层组做匹配
    all_matches: List[Dict[str, Any]] = []
    if all_match_names:
        all_matches = detect_matching_styles(list(all_match_names), threshold)

    if all_matches:
        for m in all_matches:
            logger.info(f"  -> {m['display_name']} (score={m['score']})")
    else:
        logger.info("  -> 未匹配到已知风格（可能为自定义组合）")

    return all_matches


def generate_presets(
    style_matches: List[Dict[str, Any]],
    binary_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Step 4: 生成 JSX 预设。

    对匹配到的风格生成预设；对未匹配的自定义效果链也尝试生成。
    """
    logger.info("[4/5] 生成 JSX 预设...")

    preset_entries: List[Dict[str, Any]] = []

    # 匹配到的风格 -> 直接生成
    for match in style_matches:
        key = match["style"]
        entry = generate_preset_entry(key)
        entry["match_score"] = match["score"]
        entry["source_effects"] = match.get("matched_effects", [])
        preset_entries.append(entry)
        logger.info(f"  -> 生成预设: {entry['name']} (score={match['score']})")

    # 自定义效果链（未匹配到已知风格的图层效果组合）
    custom_chains = _extract_custom_chains(binary_result, style_matches)
    for chain in custom_chains:
        entry = _generate_custom_chain_preset(chain)
        if entry:
            preset_entries.append(entry)
            logger.info(f"  -> 生成自定义预设: {entry['name']}")

    result = {
        "version": "1.0",
        "generated_at": _now_iso(),
        "source": "reverse_engineer_pipeline.py",
        "total_presets": len(preset_entries),
        "presets": preset_entries,
    }
    logger.info(f"  -> 共生成 {len(preset_entries)} 个预设")
    return result


def save_outputs(
    binary_result: Dict[str, Any],
    knowledge: Dict[str, Any],
    style_matches: List[Dict[str, Any]],
    presets: Dict[str, Any],
    output_dir: Path,
    aep_name: str = "project",
) -> Dict[str, str]:
    """Step 5: 保存所有输出文件。"""
    logger.info(f"[5/5] 保存输出到: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs: Dict[str, str] = {}

    # 1) 二进制扫描结果 JSON
    scan_path = output_dir / f"{aep_name}_scan.json"
    with open(scan_path, "w", encoding="utf-8") as f:
        json.dump(binary_result, f, ensure_ascii=False, indent=2, default=str)
    outputs["scan"] = str(scan_path)

    # 2) 知识提取 JSON
    knowledge_path = output_dir / f"{aep_name}_knowledge.json"
    with open(knowledge_path, "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=2, default=str)
    outputs["knowledge"] = str(knowledge_path)

    # 3) 风格匹配报告
    matches_path = output_dir / f"{aep_name}_style_matches.json"
    with open(matches_path, "w", encoding="utf-8") as f:
        json.dump(style_matches, f, ensure_ascii=False, indent=2)
    outputs["style_matches"] = str(matches_path)

    # 4) 预设 JSON（兼容 text_animation_presets.json 格式）
    presets_path = output_dir / f"{aep_name}_presets.json"
    with open(presets_path, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)
    outputs["presets"] = str(presets_path)

    # 5) Markdown 摘要
    md_path = output_dir / f"{aep_name}_report.md"
    md_content = _generate_markdown_report(
        binary_result, knowledge, style_matches, presets
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    outputs["report_md"] = str(md_path)

    for key, path in outputs.items():
        logger.info(f"  -> {key}: {path}")

    return outputs


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _adapt_binary_to_report(binary_result: Dict[str, Any]) -> Dict[str, Any]:
    """将 AEPParser 输出适配为 KnowledgeExtractor 期望的 report 格式。"""
    compositions: List[Dict[str, Any]] = []

    # 构建图层到合成的映射（简化：所有图层归入第一个合成）
    layers_by_comp: Dict[int, List[Dict[str, Any]]] = {}
    for layer_data in binary_result.get("layers", []):
        comp_idx = layer_data.get("composition_index", 0) or 0
        if comp_idx not in layers_by_comp:
            layers_by_comp[comp_idx] = []

        # 构建效果列表
        effects: List[Dict[str, Any]] = []
        layer_id = layer_data.get("index", -1)
        for mn in binary_result.get("match_names", []):
            if mn.get("layer_index", -1) == layer_id:
                effects.append({
                    "name": mn.get("matchName", ""),
                    "matchName": mn.get("matchName", ""),
                    "params": [],
                })

        layers_by_comp[comp_idx].append({
            "name": layer_data.get("name") or f"Layer_{layer_data.get('index', layer_id)}",
            "type": layer_data.get("type", layer_data.get("layer_type", "unknown")),
            "effects": effects,
            "transform": {},
            "parent": None,
        })

    for idx, comp_data in enumerate(binary_result.get("compositions", [])):
        comp_layers = layers_by_comp.get(idx, [])
        compositions.append({
            "name": comp_data.get("name", f"Comp {idx}"),
            "width": comp_data.get("width", 1920),
            "height": comp_data.get("height", 1080),
            "layers": comp_layers,
        })

    # 构建 effectsByType（仅顶层效果）
    effects_by_type: Dict[str, Dict[str, Any]] = {}
    for mn in _filter_top_effects(binary_result.get("match_names", [])):
        name = mn.get("matchName", "")
        if name:
            if name not in effects_by_type:
                effects_by_type[name] = {
                    "count": 0,
                    "matchName": name,
                    "category": "",
                    "isPlugin": not name.startswith("ADBE "),
                }
            effects_by_type[name]["count"] += 1

    return {
        "compositions": compositions,
        "effectsByType": effects_by_type,
        "stats": {
            "totalComps": len(compositions),
            "totalLayers": len(binary_result.get("layers", [])),
            "totalEffects": len(binary_result.get("match_names", [])),
            "totalKeyframes": 0,
            "totalExpressions": 0,
            "totalMasks": 0,
        },
        "techniques": [],
        "project": {
            "name": binary_result.get("file_info", {}).get("file_name", ""),
            "path": binary_result.get("file_info", {}).get("file_path", ""),
        },
    }


def _extract_custom_chains(
    binary_result: Dict[str, Any],
    style_matches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """提取未被已知风格覆盖的自定义效果链。"""
    matched_keys = {m["style"] for m in style_matches}
    custom: List[Dict[str, Any]] = []

    # 按图层分组效果（仅顶层效果）
    layer_effects: Dict[str, List[str]] = {}
    for mn in _filter_top_effects(binary_result.get("match_names", [])):
        layer_key = f"{mn.get('composition_index', 0)}_{mn.get('layer_index', -1)}"
        name = mn.get("matchName", "")
        if name:
            layer_effects.setdefault(layer_key, []).append(name)

    for layer_key, effects in layer_effects.items():
        if len(effects) >= 2:
            # 检查是否已被某个风格覆盖
            covered = False
            for m in style_matches:
                recipe = STYLE_RECIPES.get(m["style"], {})
                recipe_effects = {e["matchName"] for e in recipe.get("effect_chain", [])}
                if set(effects) & recipe_effects:
                    covered = True
                    break
            if not covered:
                custom.append({
                    "layer_key": layer_key,
                    "effects": effects,
                    "count": len(effects),
                })

    return custom


def _generate_custom_chain_preset(
    chain: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """为自定义效果链生成预设条目。"""
    effects = chain["effects"]
    if not effects:
        return None

    # 生成 JSX
    jsx_parts = [
        "(function(){",
        "var _r = {};",
        "try {",
        "  var c = app.project.activeItem;",
        "  if (!c || !(c instanceof CompItem)) {",
        "    _r = {status:'error',message:'No active comp'};",
        "    return JSON.stringify(_r);",
        "  }",
        "  var L = c.layer(1); // 目标图层",
    ]
    for mn in effects:
        jsx_parts.append(f"  L.property('ADBE Effect Parade').addProperty('{mn}');")
    jsx_parts.extend([
        "  _r = {status:'success', preset:'custom_chain'};",
        "} catch(e) { _r = {status:'error',message:e.toString()}; }",
        "return JSON.stringify(_r);",
        "})();",
    ])
    jsx = "\n".join(jsx_parts)

    name = " → ".join(
        e.replace("ADBE ", "").replace("CSL ", "").replace("CS ", "")
        for e in effects[:5]
    )
    return {
        "id": f"custom_{chain['layer_key']}",
        "name": f"自定义链: {name}",
        "name_en": f"Custom Chain: {name}",
        "description": f"从 AEP 逆向提取的自定义效果链 ({len(effects)} 个效果)",
        "tags": ["自定义", "逆向提取"],
        "difficulty": len(effects),
        "duration_default": 2.0,
        "parameters": [
            {"name": "targetLayerName", "type": "string", "default": "目标图层",
             "description": "目标图层名称"},
        ],
        "applies": ["AnyLayer"],
        "jsx_template": jsx,
        "source": "reverse_engineered_custom",
        "effect_chain": effects,
    }


def _generate_markdown_report(
    binary_result: Dict[str, Any],
    knowledge: Dict[str, Any],
    style_matches: List[Dict[str, Any]],
    presets: Dict[str, Any],
) -> str:
    """生成 Markdown 格式的逆向分析报告。"""
    lines: List[str] = []
    fi = binary_result.get("file_info", {})
    summary = binary_result.get("summary", {})

    lines.append(f"# AEP 逆向分析报告: {fi.get('file_name', 'Unknown')}")
    lines.append("")
    lines.append(f"**文件**: `{fi.get('file_path', '')}`")
    lines.append(f"**大小**: {fi.get('file_size', 0) / 1024 / 1024:.1f} MB")
    lines.append(f"**字节序**: {fi.get('byte_order', '')}")
    lines.append(f"**生成时间**: {_now_iso()}")
    lines.append("")

    # 统计
    lines.append("## 工程统计")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 合成 | {summary.get('compositions', 0)} |")
    lines.append(f"| 图层 | {summary.get('layers', 0)} |")
    lines.append(f"| 效果引用 | {summary.get('match_names', 0)} |")
    lines.append(f"| 去重 matchName | {summary.get('unique_match_names', 0)} |")
    lines.append(f"| 素材路径 | {summary.get('unique_file_paths', 0)} |")
    lines.append("")

    # 效果排名
    effects_by_type = knowledge.get("common_effects", [])
    if effects_by_type:
        lines.append("## 效果使用排名 (Top 15)")
        lines.append("")
        lines.append("| # | 效果 | matchName | 次数 | 插件 |")
        lines.append("|---|------|-----------|------|------|")
        for i, eff in enumerate(effects_by_type[:15], 1):
            plugin = "Yes" if eff.get("isPlugin") else "No"
            lines.append(f"| {i} | {eff['name']} | `{eff['matchName']}` | {eff['count']} | {plugin} |")
        lines.append("")

    # 风格匹配
    if style_matches:
        lines.append("## 风格匹配结果")
        lines.append("")
        for m in style_matches:
            lines.append(f"### {m['display_name']} (score={m['score']})")
            lines.append(f"- 匹配效果: {', '.join(m.get('matched_effects', []))}")
            missing = m.get("missing_effects", [])
            if missing:
                lines.append(f"- 缺失效果: {', '.join(missing)}")
            lines.append("")

    # 关键帧
    kf = knowledge.get("keyframe_patterns", {})
    if kf.get("total_keyframes", 0) > 0:
        lines.append("## 关键帧分析")
        lines.append("")
        lines.append(f"- 总关键帧: {kf['total_keyframes']}")
        lines.append(f"- 贝塞尔曲线: {kf.get('bezier_curve_count', 0)}")
        interp = kf.get("interpolation_distribution", {})
        if interp:
            lines.append(f"- 插值分布: {', '.join(f'{k}={v}' for k, v in interp.items())}")
        lines.append("")

    # 预设
    n_presets = presets.get("total_presets", 0)
    if n_presets > 0:
        lines.append("## 生成的预设")
        lines.append("")
        lines.append(f"共生成 **{n_presets}** 个可执行预设。")
        lines.append("")
        for p in presets.get("presets", []):
            lines.append(f"- **{p['name']}** — {p.get('description', '')}")
        lines.append("")

    return "\n".join(lines)


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 批量处理
# ---------------------------------------------------------------------------

def process_directory(
    aep_dir: Path,
    output_dir: Path,
) -> Dict[str, Any]:
    """批量处理目录下所有 .aep 文件。"""
    aep_files = sorted(aep_dir.rglob("*.aep"))
    if not aep_files:
        logger.warning(f"目录中未找到 .aep 文件: {aep_dir}")
        return {}

    logger.info(f"找到 {len(aep_files)} 个 AEP 文件")

    learner = TemplateLearner()
    all_outputs: Dict[str, Dict[str, str]] = {}

    for aep_path in aep_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"处理: {aep_path.relative_to(aep_dir)}")
        logger.info(f"{'='*60}")

        try:
            result = process_single(aep_path, output_dir / aep_path.stem)
            all_outputs[aep_path.name] = result

            # 添加到批量学习器
            knowledge_path = result.get("knowledge", "")
            if knowledge_path and Path(knowledge_path).exists():
                learner.add_report_from_json(knowledge_path)

        except Exception as e:
            logger.error(f"处理失败: {aep_path.name}: {e}")
            all_outputs[aep_path.name] = {"error": str(e)}

    # 批量学习输出
    if len(aep_files) > 1:
        logger.info(f"\n{'='*60}")
        logger.info("批量知识合成...")
        logger.info(f"{'='*60}")
        synthesized = learner.synthesize()
        kb_path = learner.write_to_kb("learned_aep_patterns.md")
        logger.info(f"知识库写入: {kb_path}")

    return all_outputs


def process_single(aep_path: Path, output_dir: Path) -> Dict[str, str]:
    """处理单个 AEP 文件的完整流水线。"""
    # Step 1: 二进制扫描
    binary_result = scan_aep_binary(aep_path)

    # Step 2: 知识提取
    knowledge = extract_knowledge(binary_result)

    # Step 3: 风格匹配
    style_matches = detect_styles_matches(binary_result)

    # Step 4: 生成预设
    presets = generate_presets(style_matches, binary_result)

    # Step 5: 保存输出
    outputs = save_outputs(
        binary_result, knowledge, style_matches, presets,
        output_dir, aep_name=aep_path.stem,
    )

    return outputs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEP 逆向工程统一流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--aep", type=str, help="单个 AEP 文件路径")
    parser.add_argument("--aep-dir", type=str, help="批量扫描目录")
    parser.add_argument("--output-dir", type=str, default="",
                        help="输出目录 (默认: output_director/ae_project_analysis/)")
    parser.add_argument("--generate-presets", action="store_true",
                        help="仅生成风格预设（不扫描 AEP）")

    args = parser.parse_args()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = _PROJECT_ROOT / "output_director" / "ae_project_analysis"

    if args.generate_presets:
        logger.info("仅生成风格预设...")
        presets_path = output_dir / "style_reverse_presets.json"
        result = generate_full_preset_json(str(presets_path))
        n = result["category"]["style_reverse"]["count"]
        logger.info(f"生成 {n} 个风格预设 -> {presets_path}")
        return

    if args.aep:
        aep_path = Path(args.aep)
        if not aep_path.exists():
            logger.error(f"文件不存在: {aep_path}")
            sys.exit(1)
        process_single(aep_path, output_dir / aep_path.stem)
        return

    if args.aep_dir:
        aep_dir = Path(args.aep_dir)
        if not aep_dir.is_dir():
            logger.error(f"目录不存在: {aep_dir}")
            sys.exit(1)
        process_directory(aep_dir, output_dir)
        return

    parser.print_help()


if __name__ == "__main__":
    main()

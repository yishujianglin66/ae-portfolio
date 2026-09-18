#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video_reproduce_pipeline.py — 视频逆向复现管线编排器
======================================================

端到端管线：视频输入 → VRS v2 深度分析 → 效果复现 → 转场重建 → 调色应用 → JSX 输出

流程：
  1. VRS v2 深度分析（Claude VISION 增强）
     → 效果列表 + 参数 + 风格标签 + 转场类型
  2. 效果复现引擎 (effect_reproducer.py)
     → 生成 AE JSX 脚本（图层 + 效果 + 参数）
  3. 转场重建器 (transition_rebuilder.py)
     → 补充转场效果 JSX
  4. 调色应用管线 (color_grading_applier.py)
     → 创建调色调整层 JSX
  5. 合并输出
     → 完整 JSX 脚本文件 或 通过 MCP 桥执行
  6. 复现报告
     → 置信度分析 + 需手动调整项

用法：
    # Python API
    from vrs.video_reproduce_pipeline import VideoReproducePipeline

    pipeline = VideoReproducePipeline()
    result = await pipeline.reproduce(
        video_path="input.mp4",
        output_mode="jsx",
        output_dir="output/reproduce",
    )

    # CLI
    python video_reproduce_pipeline.py --video input.mp4 --output output/reproduce
    python video_reproduce_pipeline.py --analysis analysis.json  # 跳过分析，直接从JSON复现
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

from color_grading_applier import ColorGradingApplier
from effect_reproducer import EffectReproducer
from transition_rebuilder import TransitionRebuilder


class VideoReproducePipeline:
    """视频逆向复现管线编排器。"""

    def __init__(self, output_dir: str = "output/reproduce"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.effect_reproducer = EffectReproducer()
        self.transition_rebuilder = TransitionRebuilder()
        self.color_applier = ColorGradingApplier()

    # =========================================================================
    # 公共入口
    # =========================================================================

    async def reproduce(
        self,
        video_path: str | None = None,
        analysis_json: str | None = None,
        output_mode: str = "jsx",
        detail_level: str = "full",
        auto_color_grade: bool = True,
        auto_transitions: bool = True,
        comp_name: str = "Reproduce_Comp",
    ) -> dict[str, Any]:
        """一键分析并复现。

        Args:
            video_path: 视频文件路径（与 analysis_json 二选一）
            analysis_json: 预生成的 VRS 分析结果 JSON 路径
            output_mode: "jsx" 导出脚本 / "mcp" 发送到 AE / "both" 两者
            detail_level: 分析精度 quick/standard/full
            auto_color_grade: 是否自动应用调色
            auto_transitions: 是否自动重建转场
            comp_name: AE 合成名称

        Returns:
            完整复现报告字典
        """
        report: dict[str, Any] = {
            "pipeline_version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "video_path": video_path,
            "output_mode": output_mode,
            "success": False,
        }

        # ── 第 1 步：获取分析结果 ──────────────────────────────
        if analysis_json:
            analysis = self._load_analysis(analysis_json)
            report["analysis_source"] = "pre_loaded"
        elif video_path:
            analysis = await self._run_analysis(video_path, detail_level)
            report["analysis_source"] = "vrs_v2"
        else:
            report["error"] = "必须提供 video_path 或 analysis_json"
            return report

        report["analysis"] = {
            "effects_count": len(self._extract_all_effects(analysis)),
            "style_tags": self._extract_style_tags(analysis),
        }

        # ── 第 2 步：效果复现 ──────────────────────────────────
        jsx_parts: list[str] = []

        # 文件头
        jsx_parts.append(self._generate_header(analysis, comp_name))

        # 核心效果 JSX
        effects_jsx = self.effect_reproducer.generate_jsx(analysis, comp_name=comp_name)
        jsx_parts.append(effects_jsx)

        # 置信度报告
        confidence_report = self.effect_reproducer.generate_confidence_report(analysis)
        report["confidence_report"] = confidence_report

        # ── 第 3 步：调色管线 ──────────────────────────────────
        if auto_color_grade:
            color_params = self.color_applier.extract_color_params_from_vrs(analysis)
            if color_params:
                video_info = self._extract_video_info(analysis)
                color_jsx = self.color_applier.generate_color_grade_jsx(
                    color_params,
                    comp_width=video_info.get("width", 1920),
                    comp_height=video_info.get("height", 1080),
                )
                jsx_parts.append("\n// ====== Color Grading ======")
                jsx_parts.append(color_jsx)
                report["color_grade_applied"] = True
            else:
                report["color_grade_applied"] = False

        # ── 第 4 步：转场重建 ──────────────────────────────────
        if auto_transitions:
            transitions = self._extract_transitions(analysis)
            if transitions:
                transition_jsx_parts = []
                for trans in transitions:
                    t_jsx = self.transition_rebuilder.generate_transition_jsx(
                        transition_type=trans.get("type", "fade"),
                        layer_a_name=trans.get("from_scene", "Scene_A"),
                        layer_b_name=trans.get("to_scene", "Scene_B"),
                        start_time=trans.get("time", 0),
                        duration=trans.get("duration", 0.8),
                    )
                    transition_jsx_parts.append(t_jsx)

                if transition_jsx_parts:
                    jsx_parts.append("\n// ====== Transitions ======")
                    jsx_parts.extend(transition_jsx_parts)
                    report["transitions_applied"] = len(transitions)
            else:
                report["transitions_applied"] = 0

        # ── 第 5 步：合并输出 ──────────────────────────────────
        full_jsx = "\n".join(jsx_parts)

        # 输出 JSX 文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jsx_path = self.output_dir / f"reproduce_{timestamp}.jsx"
        jsx_path.write_text(full_jsx, encoding="utf-8")
        report["jsx_path"] = str(jsx_path)

        # 输出分析报告 JSON
        report_path = self.output_dir / f"report_{timestamp}.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        report["report_path"] = str(report_path)

        report["success"] = True
        report["analysis_summary"] = self._build_summary(analysis, confidence_report)
        report["manual_review"] = confidence_report.get("manual_only", [])

        return report

    # =========================================================================
    # 内部方法
    # =========================================================================

    async def _run_analysis(self, video_path: str, detail_level: str) -> dict[str, Any]:
        """运行 VRS v2 深度分析。"""
        try:
            from vrs.video_effect_analyzer_v2 import VideoEffectAnalyzerV2
            analyzer = VideoEffectAnalyzerV2(enable_vision=True)
            result = await analyzer.analyze_video_deep(video_path, detail_level=detail_level)
            return result
        except ImportError:
            return {"error": "VRS v2 不可用，请安装依赖", "video_path": video_path}
        except Exception as exc:
            return {"error": f"分析失败: {exc}", "video_path": video_path}

    def _load_analysis(self, json_path: str) -> dict[str, Any]:
        """从 JSON 文件加载预生成的分析结果。"""
        path = Path(json_path)
        if not path.exists():
            return {"error": f"文件不存在: {json_path}"}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _generate_header(self, analysis: dict[str, Any], comp_name: str) -> str:
        """生成 JSX 文件头。"""
        style_tags = self._extract_style_tags(analysis)
        effects_count = len(self._extract_all_effects(analysis))
        return f"""// ============================================================
// Video Reproduce - Auto-generated JSX
// Time: {datetime.now().isoformat()}
// Style: {', '.join(style_tags) if style_tags else 'N/A'}
// Effects detected: {effects_count}
// Generated by: VideoReproducePipeline v1.0
// ============================================================

"""

    def _extract_all_effects(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        merged = analysis.get("merged", analysis.get("vision_result", analysis))
        return merged.get("effects", merged.get("aggregated_effects", []))

    def _extract_style_tags(self, analysis: dict[str, Any]) -> list[str]:
        merged = analysis.get("merged", analysis.get("vision_result", analysis))
        return merged.get("style_tags", [])

    def _extract_transitions(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """从分析结果中提取转场信息。"""
        cv_result = analysis.get("cv_result", {})
        transitions = cv_result.get("transitions", [])

        result = []
        for t in transitions:
            t_type = t.get("type", "fade")
            # 映射 CV 检测的转场类型到 TransitionRebuilder 支持的类型
            type_map = {
                "wipe": "linear_wipe",
                "dissolve": "fade",
                "fade": "fade",
                "slide": "slide",
                "zoom": "zoom_blur",
                "wipe_left": "linear_wipe",
                "wipe_right": "linear_wipe",
                "wipe_up": "linear_wipe",
                "wipe_down": "linear_wipe",
            }
            mapped_type = type_map.get(t_type, "fade")

            result.append({
                "type": mapped_type,
                "time": t.get("offset_frames", 0) / max(cv_result.get("basic_info", {}).get("fps", 30), 1),
                "duration": t.get("duration_frames", 15) / max(cv_result.get("basic_info", {}).get("fps", 30), 1),
                "from_scene": f"Scene_{t.get('from_scene', 'A')}",
                "to_scene": f"Scene_{t.get('to_scene', 'B')}",
            })

        # 也检查 merged 中的转场
        merged = analysis.get("merged", {})
        for t in merged.get("transitions", []):
            if isinstance(t, dict):
                result.append({
                    "type": t.get("type", "fade"),
                    "time": t.get("time", 0),
                    "duration": t.get("duration", 0.8),
                    "from_scene": t.get("from", "Scene_A"),
                    "to_scene": t.get("to", "Scene_B"),
                })

        return result

    def _extract_video_info(self, analysis: dict[str, Any]) -> dict[str, Any]:
        cv = analysis.get("cv_result", {})
        basic = cv.get("basic_info", {})
        return {
            "width": basic.get("width", 1920),
            "height": basic.get("height", 1080),
            "fps": basic.get("fps", 30),
            "duration": basic.get("duration", 10),
        }

    def _build_summary(
        self, analysis: dict[str, Any], confidence: dict[str, Any]
    ) -> str:
        """构建人类可读的分析摘要。"""
        effects = self._extract_all_effects(analysis)
        style_tags = self._extract_style_tags(analysis)
        auto_rate = confidence.get("auto_rate", 0)

        lines = [
            f"检测到 {len(effects)} 个效果，风格: {', '.join(style_tags) if style_tags else '未识别'}",
            f"自动复现率: {auto_rate:.0%} ({confidence.get('total_effects', 0)} 个效果)",
            f"  - 可自动复现: {len(confidence.get('auto_reproducible', []))} 个",
            f"  - 需检查: {len(confidence.get('needs_review', []))} 个",
            f"  - 需手动: {len(confidence.get('manual_only', []))} 个",
        ]

        if confidence.get("manual_only"):
            lines.append("\n需手动处理的效果:")
            for m in confidence["manual_only"]:
                lines.append(f"  - {m['name']} ({m.get('reason', 'unknown')})")

        return "\n".join(lines)


# ============================================================================
# CLI 入口
# ============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="视频逆向复现管线")
    parser.add_argument("--video", type=str, help="输入视频路径")
    parser.add_argument("--analysis", type=str, help="预生成的分析结果 JSON 路径")
    parser.add_argument("--output", type=str, default="output/reproduce", help="输出目录")
    parser.add_argument("--mode", type=str, default="jsx", choices=["jsx", "mcp", "both"])
    parser.add_argument("--detail", type=str, default="full", choices=["quick", "standard", "full"])
    parser.add_argument("--name", type=str, default="Reproduce_Comp", help="AE 合成名称")
    parser.add_argument("--no-color", action="store_true", help="跳过调色")
    parser.add_argument("--no-transitions", action="store_true", help="跳过转场")

    args = parser.parse_args()

    if not args.video and not args.analysis:
        parser.error("必须提供 --video 或 --analysis 参数")

    pipeline = VideoReproducePipeline(output_dir=args.output)

    result = await pipeline.reproduce(
        video_path=args.video,
        analysis_json=args.analysis,
        output_mode=args.mode,
        detail_level=args.detail,
        auto_color_grade=not args.no_color,
        auto_transitions=not args.no_transitions,
        comp_name=args.name,
    )

    print("\n" + "=" * 60)
    print("复现报告")
    print("=" * 60)
    print(f"成功: {result.get('success')}")
    if result.get("jsx_path"):
        print(f"JSX 文件: {result['jsx_path']}")
    if result.get("report_path"):
        print(f"报告文件: {result['report_path']}")
    if result.get("analysis_summary"):
        print(f"\n{result['analysis_summary']}")
    if result.get("error"):
        print(f"\n错误: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())

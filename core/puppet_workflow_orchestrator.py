#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
木偶风格化工作流编排器 v1.0
================================

将 MediaPipe 人物检测 → PuppetStyleEngine 风格化 → JSX 生成 →
AE 桥接执行 → DaVinci Resolve 调色 串联为生产级端到端工作流。

支持:
- 单视频 / 批量视频处理
- 多风格并行生成（wooden/ceramic/marionette 等）
- 三级降级: real → simulate → skip
- 进度回调与事件通知
- 完整的工作流报告（JSON + Markdown）

使用示例:
    orchestrator = PuppetWorkflowOrchestrator()
    result = orchestrator.run(
        video_path="input.mp4",
        style_types=["wooden_puppet", "ceramic_puppet"],
        execute_ae=True,
        color_grade=True,
    )
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class WorkflowConfig:
    """工作流配置

    Attributes:
        mediapipe_mode: MediaPipe 运行模式 (auto/real/simulate)
        style_types: 要生成的风格列表
        intensity: 风格强度 (0.0-2.0)
        enable_face_puppet: 是否启用面部木偶化
        execute_ae: 是否在 AE 中执行生成的 JSX 脚本
        ae_timeout: AE 执行超时时间（秒）
        color_grade: 是否进行 DaVinci Resolve 调色
        color_preset: 调色预设名称
        output_dir: 输出目录
        save_report: 是否保存报告
    """
    mediapipe_mode: str = "auto"
    style_types: list[str] = field(default_factory=lambda: ["wooden_puppet"])
    intensity: float = 1.0
    enable_face_puppet: bool = True
    execute_ae: bool = False
    ae_timeout: int = 60
    color_grade: bool = False
    color_preset: str = "puppet_warm"
    output_dir: str = ""
    save_report: bool = True


@dataclass
class StageResult:
    """单阶段结果"""
    name: str
    success: bool
    duration: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class WorkflowResult:
    """完整工作流结果"""
    success: bool = False
    total_duration: float = 0.0
    video_path: str = ""
    stages: list[StageResult] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_stage(self, stage: StageResult):
        self.stages.append(stage)
        if not stage.success and stage.error:
            self.errors.append(f"{stage.name}: {stage.error}")

    def add_artifact(self, artifact_type: str, path: str, **extra):
        item = {"type": artifact_type, "path": path}
        item.update(extra)
        self.artifacts.append(item)


# ============================================================================
# 工作流编排器
# ============================================================================


class PuppetWorkflowOrchestrator:
    """木偶风格化工作流编排器

    串联所有模块，提供生产级端到端处理能力。

    Pipeline:
        1. MediaPipe 人物检测 → bbox / joint_data / face_data
        2. PuppetStyleEngine 风格化 → effects / keyframes / layers
        3. JSX 脚本生成 → 可执行 AE 脚本
        4. AE 桥接执行 (可选) → 在 AE 中创建合成
        5. DaVinci Resolve 调色 (可选) → 最终色彩输出
        6. 报告生成 → JSON + Markdown
    """

    def __init__(self, config: WorkflowConfig | None = None):
        self.config = config or WorkflowConfig()
        self._auto_processor = None
        self._ae_client = None
        self._resolve_colorist = None
        self._init_modules()

    def _init_modules(self):
        """初始化所有依赖模块"""
        # 木偶自动处理器（包含 MediaPipe + PuppetStyleEngine）
        try:
            from puppet_auto_processor import PuppetAutoProcessor
            self._auto_processor = PuppetAutoProcessor(
                mediapipe_mode=self.config.mediapipe_mode
            )
        except ImportError as e:
            print(f"⚠️ PuppetAutoProcessor 加载失败: {e}")

        # AE 桥接客户端
        if self.config.execute_ae:
            try:
                from ae_mcp_client import AECommandClient
                self._ae_client = AECommandClient(timeout=self.config.ae_timeout)
            except ImportError as e:
                print(f"⚠️ AECommandClient 加载失败: {e}")

        # DaVinci Resolve 调色
        if self.config.color_grade:
            try:
                from davinci_resolve_integration import (
                    DavinciColorist,
                    ResolveColorConfig,
                )
                resolve_config = ResolveColorConfig(
                    mode="auto",
                    color_preset=self.config.color_preset,
                )
                self._resolve_colorist = DavinciColorist(config=resolve_config)
            except ImportError as e:
                print(f"⚠️ DavinciColorist 加载失败: {e}")

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def run(
        self,
        video_path: str,
        style_types: list[str] | None = None,
        callback: Callable[[str, float, str], None] | None = None,
    ) -> WorkflowResult:
        """运行完整工作流

        Args:
            video_path: 输入视频路径
            style_types: 覆盖配置的风格列表
            callback: 进度回调 (stage_name, progress 0-1, message)

        Returns:
            工作流结果
        """
        start_time = time.time()
        result = WorkflowResult(video_path=video_path)
        styles = style_types or self.config.style_types

        output_dir = self.config.output_dir or str(
            PROJECT_ROOT / "output" / "puppet_workflow"
        )
        os.makedirs(output_dir, exist_ok=True)

        self._notify(callback, "初始化", 0.0, "开始工作流")

        # Stage 1: MediaPipe 人物检测
        self._notify(callback, "人物检测", 0.1, "MediaPipe 检测中...")
        stage1 = self._stage_detect(video_path)
        result.add_stage(stage1)
        self._notify(callback, "人物检测", 0.2,
                      f"完成: {'成功' if stage1.success else '降级'}")

        detection_data = stage1.data if stage1.success else {}

        # Stage 2: 多风格生成
        total_styles = len(styles)
        style_results = []

        for i, style in enumerate(styles):
            progress = 0.2 + 0.3 * (i / max(total_styles, 1))
            self._notify(callback, "风格化生成", progress,
                         f"生成 {style} ({i+1}/{total_styles})")

            stage2 = self._stage_generate_style(
                detection_data, style, video_path, output_dir
            )
            result.add_stage(stage2)
            style_results.append((style, stage2))

            if stage2.success:
                jsx_path = stage2.data.get("jsx_path", "")
                if jsx_path:
                    result.add_artifact(
                        "jsx_script", jsx_path,
                        style=style,
                        size=os.path.getsize(jsx_path) if os.path.exists(jsx_path) else 0,
                    )

        self._notify(callback, "风格化生成", 0.5, "所有风格生成完成")

        # Stage 3: AE 执行（可选）
        if self.config.execute_ae and self._ae_client:
            self._notify(callback, "AE执行", 0.6, "在 AE 中执行脚本...")
            for style, stage in style_results:
                if stage.success and stage.data.get("jsx_path"):
                    jsx_path = stage.data["jsx_path"]
                    ae_stage = self._stage_execute_ae(jsx_path, style)
                    result.add_stage(ae_stage)

                    if ae_stage.success:
                        result.add_artifact(
                            "ae_composition", "",
                            style=style,
                            comp_name=ae_stage.data.get("comp_name", ""),
                        )
            self._notify(callback, "AE执行", 0.7, "AE 执行完成")
        else:
            self._notify(callback, "AE执行", 0.7, "跳过 AE 执行")

        # Stage 4: DaVinci Resolve 调色（可选）
        if self.config.color_grade and self._resolve_colorist:
            self._notify(callback, "调色", 0.75, "DaVinci Resolve 调色中...")

            # 使用视频文件作为调色输入
            grade_output = os.path.join(output_dir, "graded_output.mp4")
            grade_stage = self._stage_color_grade(video_path, grade_output)
            result.add_stage(grade_stage)

            if grade_stage.success:
                result.add_artifact(
                    "graded_video", grade_output,
                    size=os.path.getsize(grade_output) if os.path.exists(grade_output) else 0,
                )

            self._notify(callback, "调色", 0.9, "调色完成")
        else:
            self._notify(callback, "调色", 0.9, "跳过调色")

        # Stage 5: 报告生成
        self._notify(callback, "报告生成", 0.95, "生成报告...")
        report_stage = self._stage_generate_report(result, output_dir)
        result.add_stage(report_stage)

        if report_stage.success:
            result.add_artifact("report", report_stage.data.get("report_path", ""))

        result.total_duration = round(time.time() - start_time, 2)
        result.success = len(result.errors) == 0

        self._notify(callback, "完成", 1.0,
                      f"工作流完成 ({result.total_duration}s)")

        return result

    def run_batch(
        self,
        video_paths: list[str],
        style_types: list[str] | None = None,
        callback: Callable[[str, str, float, str], None] | None = None,
    ) -> list[WorkflowResult]:
        """批量处理多个视频

        Args:
            video_paths: 视频路径列表
            style_types: 风格列表
            callback: 进度回调 (video_path, stage_name, progress, message)

        Returns:
            每个视频的工作流结果列表
        """
        results = []
        total = len(video_paths)

        for i, video_path in enumerate(video_paths):
            print(f"\n{'='*60}")
            print(f"📦 批量处理 [{i+1}/{total}]: {os.path.basename(video_path)}")
            print(f"{'='*60}")

            def batch_callback(stage, progress, msg):
                self._notify(
                    lambda s, p, m: callback(video_path, s, p, m) if callback else None,
                    stage, progress, msg
                )

            result = self.run(video_path, style_types, batch_callback)
            results.append(result)

        return results

    def get_available_styles(self) -> list[dict[str, Any]]:
        """获取可用风格列表"""
        if self._auto_processor:
            return self._auto_processor.get_available_styles()
        return []

    # ------------------------------------------------------------------
    # 阶段实现
    # ------------------------------------------------------------------

    def _stage_detect(self, video_path: str) -> StageResult:
        """Stage 1: MediaPipe 人物检测"""
        start = time.time()
        stage = StageResult(name="MediaPipe人物检测", success=False)

        if not self._auto_processor:
            stage.error = "PuppetAutoProcessor 不可用"
            stage.duration = round(time.time() - start, 2)
            return stage

        try:
            detection = self._auto_processor._detect_person(video_path)
            if detection.get("success"):
                stage.success = True
                stage.data = detection
            else:
                stage.success = True  # 降级处理，不算失败
                stage.data = {}
                stage.error = f"检测降级: {detection.get('error', '')}"
        except Exception as e:
            stage.success = True  # 降级
            stage.data = {}
            stage.error = f"检测异常: {e}"

        stage.duration = round(time.time() - start, 2)
        return stage

    def _stage_generate_style(
        self,
        detection_data: dict[str, Any],
        style_type: str,
        video_path: str,
        output_dir: str,
    ) -> StageResult:
        """Stage 2: 风格化效果生成 + JSX 脚本"""
        start = time.time()
        stage = StageResult(name=f"风格化生成({style_type})", success=False)

        if not self._auto_processor:
            stage.error = "PuppetAutoProcessor 不可用"
            stage.duration = round(time.time() - start, 2)
            return stage

        try:
            style_output_dir = os.path.join(output_dir, style_type)
            os.makedirs(style_output_dir, exist_ok=True)

            process_result = self._auto_processor.process_video(
                video_path=video_path,
                style_type=style_type,
                intensity=self.config.intensity,
                enable_face_puppet=self.config.enable_face_puppet,
                output_dir=style_output_dir,
            )

            if process_result.get("success"):
                stage.success = True
                stage.data = {
                    "jsx_path": process_result.get("output_files", {}).get("jsx_script", ""),
                    "detection_path": process_result.get("output_files", {}).get("detection_result", ""),
                    "config_path": process_result.get("output_files", {}).get("style_config", ""),
                    "effects_count": 0,
                    "keyframes_count": 0,
                }

                # 提取风格化统计
                style_result = process_result.get("style_result")
                if style_result:
                    stage.data["effects_count"] = len(style_result.effects)
                    stage.data["keyframes_count"] = len(style_result.keyframes)
                    stage.data["layers_count"] = len(style_result.layers)
                    stage.data["expressions_count"] = len(style_result.expressions)
            else:
                stage.error = process_result.get("error", "未知错误")

        except Exception as e:
            stage.error = f"生成异常: {e}"

        stage.duration = round(time.time() - start, 2)
        return stage

    def _stage_execute_ae(self, jsx_path: str, style_type: str) -> StageResult:
        """Stage 3: 在 AE 中执行 JSX 脚本"""
        start = time.time()
        stage = StageResult(name=f"AE执行({style_type})", success=False)

        if not self._ae_client:
            stage.error = "AECommandClient 不可用"
            stage.duration = round(time.time() - start, 2)
            return stage

        try:
            with open(jsx_path, "r", encoding="utf-8") as f:
                jsx_content = f.read()

            result = self._ae_client.send_command("executeScript", {
                "script": jsx_content,
                "scriptLanguage": "ExtendScript",
            })

            if result.get("status") == "success":
                stage.success = True
                stage.data = {
                    "comp_name": f"Puppet_{style_type}",
                    "ae_result": result.get("data", {}),
                }
            else:
                stage.error = result.get("error", result.get("message", "AE 执行失败"))

        except Exception as e:
            stage.error = f"AE 执行异常: {e}"

        stage.duration = round(time.time() - start, 2)
        return stage

    def _stage_color_grade(self, input_path: str, output_path: str) -> StageResult:
        """Stage 4: DaVinci Resolve 调色"""
        start = time.time()
        stage = StageResult(name="DaVinci调色", success=False)

        if not self._resolve_colorist:
            stage.error = "DavinciColorist 不可用"
            stage.duration = round(time.time() - start, 2)
            return stage

        try:
            grade_result = self._resolve_colorist.color_grade(
                input_path=input_path,
                output_path=output_path,
            )

            if grade_result.success:
                stage.success = True
                stage.data = {
                    "output_path": grade_result.output_path,
                    "mode": grade_result.mode,
                    "nodes_applied": grade_result.nodes_applied,
                    "duration": grade_result.duration,
                }
            else:
                stage.error = f"调色失败: {grade_result.error or '未知'}"

        except Exception as e:
            stage.error = f"调色异常: {e}"

        stage.duration = round(time.time() - start, 2)
        return stage

    def _stage_generate_report(self, result: WorkflowResult, output_dir: str) -> StageResult:
        """Stage 5: 生成工作流报告"""
        start = time.time()
        stage = StageResult(name="报告生成", success=False)

        try:
            report = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "video_path": result.video_path,
                "success": result.success,
                "total_duration": result.total_duration,
                "stages": [
                    {
                        "name": s.name,
                        "success": s.success,
                        "duration": s.duration,
                        "data": s.data,
                        "error": s.error,
                    }
                    for s in result.stages
                ],
                "artifacts": result.artifacts,
                "errors": result.errors,
            }

            report_path = os.path.join(output_dir, "workflow_report.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)

            # 生成 Markdown 摘要
            md_path = os.path.join(output_dir, "workflow_report.md")
            md_content = self._generate_markdown_report(report)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            stage.success = True
            stage.data = {
                "report_path": report_path,
                "markdown_path": md_path,
            }

        except Exception as e:
            stage.error = f"报告生成异常: {e}"

        stage.duration = round(time.time() - start, 2)
        return stage

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _notify(
        self,
        callback: Callable | None,
        stage: str,
        progress: float,
        message: str,
    ):
        """发送进度通知"""
        if callback:
            try:
                callback(stage, progress, message)
            except Exception:
                pass
        print(f"  [{progress*100:.0f}%] {stage}: {message}")

    def _generate_markdown_report(self, report: dict) -> str:
        """生成 Markdown 格式报告"""
        lines = [
            "# 木偶风格化工作流报告",
            "",
            f"- **时间**: {report['timestamp']}",
            f"- **视频**: `{report['video_path']}`",
            f"- **状态**: {'✅ 成功' if report['success'] else '❌ 失败'}",
            f"- **总耗时**: {report['total_duration']} 秒",
            "",
            "## 阶段详情",
            "",
        ]

        for stage in report.get("stages", []):
            status = "✅" if stage["success"] else "❌"
            lines.append(f"### {status} {stage['name']} ({stage['duration']}s)")
            if stage.get("error"):
                lines.append(f"- 错误: {stage['error']}")
            if stage.get("data"):
                for k, v in stage["data"].items():
                    if isinstance(v, (str, int, float, bool)):
                        lines.append(f"- {k}: {v}")
            lines.append("")

        if report.get("artifacts"):
            lines.append("## 输出文件")
            lines.append("")
            for art in report["artifacts"]:
                size_str = f" ({art.get('size', 0)} bytes)" if "size" in art else ""
                lines.append(f"- **{art['type']}**: `{os.path.basename(art.get('path', ''))}`{size_str}")
            lines.append("")

        if report.get("errors"):
            lines.append("## 错误列表")
            lines.append("")
            for err in report["errors"]:
                lines.append(f"- {err}")
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# CLI 入口
# ============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="木偶风格化工作流编排器")
    parser.add_argument("--video", "-v", required=True, help="输入视频路径")
    parser.add_argument(
        "--styles", "-s",
        nargs="+",
        default=["wooden_puppet"],
        help="风格列表（空格分隔）",
    )
    parser.add_argument("--intensity", "-i", type=float, default=1.0, help="风格强度")
    parser.add_argument("--no-face", action="store_true", help="禁用面部木偶化")
    parser.add_argument("--execute-ae", action="store_true", help="在 AE 中执行脚本")
    parser.add_argument("--ae-timeout", type=int, default=60, help="AE 执行超时")
    parser.add_argument("--color-grade", action="store_true", help="DaVinci Resolve 调色")
    parser.add_argument("--color-preset", default="puppet_warm", help="调色预设")
    parser.add_argument("--output", "-o", help="输出目录")
    parser.add_argument("--mediapipe-mode", default="auto", help="MediaPipe 模式")
    parser.add_argument("--batch", nargs="+", help="批量处理视频列表")
    parser.add_argument("--list-styles", action="store_true", help="列出可用风格")

    args = parser.parse_args()

    config = WorkflowConfig(
        mediapipe_mode=args.mediapipe_mode,
        style_types=args.styles,
        intensity=args.intensity,
        enable_face_puppet=not args.no_face,
        execute_ae=args.execute_ae,
        ae_timeout=args.ae_timeout,
        color_grade=args.color_grade,
        color_preset=args.color_preset,
        output_dir=args.output or "",
    )

    orchestrator = PuppetWorkflowOrchestrator(config)

    if args.list_styles:
        styles = orchestrator.get_available_styles()
        print(f"可用风格 ({len(styles)} 种):")
        for s in styles:
            print(f"  - {s['name']}: {s['display_name']}")
        return

    print("=" * 60)
    print("🎭 木偶风格化工作流编排器")
    print("=" * 60)
    print(f"视频: {args.video}")
    print(f"风格: {', '.join(args.styles)}")
    print(f"强度: {args.intensity}")
    print(f"AE执行: {'是' if args.execute_ae else '否'}")
    print(f"调色: {'是' if args.color_grade else '否'}")

    if args.batch:
        videos = [args.video] + args.batch
        print(f"\n批量处理 {len(videos)} 个视频...")
        results = orchestrator.run_batch(videos, args.styles)

        print(f"\n{'='*60}")
        print("📊 批量处理结果")
        print(f"{'='*60}")
        for i, r in enumerate(results):
            status = "✅" if r.success else "❌"
            print(f"  {status} [{i+1}] {os.path.basename(r.video_path)} ({r.total_duration}s)")
            for art in r.artifacts:
                print(f"      → {art['type']}: {os.path.basename(art.get('path', ''))}")
    else:
        result = orchestrator.run(args.video)

        print(f"\n{'='*60}")
        print("📊 工作流结果")
        print(f"{'='*60}")
        print(f"  状态: {'✅ 成功' if result.success else '❌ 失败'}")
        print(f"  耗时: {result.total_duration}s")

        print("\n  阶段:")
        for s in result.stages:
            status = "✅" if s.success else "❌"
            print(f"    {status} {s.name} ({s.duration}s)")
            if s.error:
                print(f"       错误: {s.error}")

        if result.artifacts:
            print("\n  输出文件:")
            for art in result.artifacts:
                size = art.get("size", 0)
                size_str = f" ({size} bytes)" if size else ""
                print(f"    - {art['type']}: {os.path.basename(art.get('path', ''))}{size_str}")

        if result.errors:
            print("\n  错误:")
            for err in result.errors:
                print(f"    - {err}")


if __name__ == "__main__":
    main()

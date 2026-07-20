"""Roto Service - SAM2 + Silhouette 联合抠像工作流服务.

提供三种抠像模式：
    - sam2_only: 仅使用 SAM2 自动分割（快速，精度一般）
    - silhouette_only: 仅使用 Silhouette 自动抠像（精度高，较慢）
    - hybrid: SAM2 粗分 + Silhouette 精修（推荐，精度与速度平衡）

工作流程（hybrid 模式）：
    1. SAM2 自动生成初始遮罩序列（粗分割）
    2. SAM2 导出 Silhouette 兼容的形状数据
    3. Silhouette 导入形状并进行精修（羽化、运动模糊、贝塞尔简化）
    4. 渲染最终 alpha 通道
    5. 质量评估与报告生成
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from loguru import logger

from ..engines.sam2.engine import SAM2Engine
from ..engines.silhouette.engine import SilhouetteEngine


class RotoService:
    """SAM2 + Silhouette 联合抠像服务.

    整合 SAM2 的快速自动分割能力与 Silhouette 的专业 roto 精修能力，
    提供高质量、高效率的视频抠像解决方案。
    """

    VALID_MODES = ("sam2_only", "silhouette_only", "hybrid")

    def __init__(
        self,
        sam2_engine: Optional[SAM2Engine] = None,
        silhouette_engine: Optional[SilhouetteEngine] = None,
    ):
        """初始化联合抠像服务.

        Args:
            sam2_engine: SAM2 引擎实例（可选，默认从配置创建）
            silhouette_engine: Silhouette 引擎实例（可选，默认从配置创建）
        """
        self.sam2 = sam2_engine or SAM2Engine()
        self.silhouette = silhouette_engine or SilhouetteEngine()
        logger.info("RotoService initialized")

    async def auto_roto(
        self,
        video_path: Path | str,
        output_dir: Path | str,
        mode: Literal["sam2_only", "silhouette_only", "hybrid"] = "hybrid",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """自动抠像主入口 - 支持三种模式.

        Args:
            video_path: 输入视频路径
            output_dir: 输出目录
            mode: 抠像模式
                - "sam2_only": 仅 SAM2 快速分割
                - "silhouette_only": 仅 Silhouette 自动抠像
                - "hybrid": SAM2 粗分 + Silhouette 精修（默认）
            **kwargs: 额外参数
                - model_size: SAM2 模型大小（base/large）
                - feather: 边缘羽化值（像素）
                - motion_blur: 运动模糊强度（0-1）
                - bezier_simplify: 贝塞尔简化容差
                - prompts: SAM2 点提示列表
                - quality: Silhouette 质量 1-100

        Returns:
            包含以下字段的字典：
                - success: 是否成功
                - mask_path: 最终遮罩路径
                - alpha_path: alpha 通道路径
                - quality_score: 质量评分（0-100）
                - duration: 总耗时（秒）
                - mode: 使用的模式
                - details: 各阶段详情
        """
        start_time = time.time()
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if mode not in self.VALID_MODES:
            return {
                "success": False,
                "error": f"Invalid mode: {mode}. Valid: {self.VALID_MODES}",
                "duration": time.time() - start_time,
            }

        if not video_path.exists():
            return {
                "success": False,
                "error": f"Video not found: {video_path}",
                "duration": time.time() - start_time,
            }

        logger.info(f"[Roto] Starting auto_roto, mode={mode}, video={video_path}")

        details: Dict[str, Any] = {}
        mask_path: Optional[Path] = None
        alpha_path: Optional[Path] = None
        quality_score = 0.0

        try:
            if mode == "sam2_only":
                result = await self.sam2_auto_mask(video_path, output_dir, **kwargs)
                if not result.get("success"):
                    return {
                        "success": False,
                        "error": result.get("error", "SAM2 mask generation failed"),
                        "duration": time.time() - start_time,
                        "mode": mode,
                        "details": result,
                    }
                mask_path = Path(result["mask_dir"])
                alpha_path = mask_path
                quality_score = result.get("quality_score", 0.0)
                details["sam2"] = result

            elif mode == "silhouette_only":
                sil_output = output_dir / "silhouette_masks"
                sil_result = await self.silhouette.create_roto_session(
                    input_path=video_path,
                    output_path=sil_output,
                    quality=kwargs.get("quality", 80),
                    auto_roto=True,
                )
                if not sil_result.success:
                    return {
                        "success": False,
                        "error": sil_result.error or "Silhouette roto failed",
                        "duration": time.time() - start_time,
                        "mode": mode,
                        "details": {"silhouette": sil_result.metadata},
                    }
                mask_path = sil_result.output_path
                alpha_path = sil_result.output_path
                if mask_path and mask_path.exists():
                    quality_score = self._evaluate_dir_quality(mask_path)
                details["silhouette"] = sil_result.metadata

            else:
                hybrid_result = await self._hybrid_roto_pipeline(
                    video_path, output_dir, **kwargs
                )
                if not hybrid_result.get("success"):
                    return {
                        "success": False,
                        "error": hybrid_result.get("error", "Hybrid roto pipeline failed"),
                        "duration": time.time() - start_time,
                        "mode": mode,
                        "details": hybrid_result.get("details", {}),
                    }
                mask_path = Path(hybrid_result["mask_path"])
                alpha_path = Path(hybrid_result["alpha_path"])
                quality_score = hybrid_result.get("quality_score", 0.0)
                details = hybrid_result.get("details", {})

            total_duration = time.time() - start_time

            result = {
                "success": True,
                "mask_path": str(mask_path) if mask_path else None,
                "alpha_path": str(alpha_path) if alpha_path else None,
                "quality_score": round(quality_score, 2),
                "duration": round(total_duration, 2),
                "mode": mode,
                "video_path": str(video_path),
                "output_dir": str(output_dir),
                "details": details,
            }

            report = self.generate_roto_report(result)
            report_path = output_dir / "roto_report.txt"
            report_path.write_text(report, encoding="utf-8")
            result["report_path"] = str(report_path)

            logger.info(
                f"[Roto] auto_roto completed, mode={mode}, "
                f"quality={quality_score:.1f}, duration={total_duration:.1f}s"
            )

            return result

        except Exception as e:
            total_duration = time.time() - start_time
            logger.error(f"[Roto] auto_roto failed: {e}")
            return {
                "success": False,
                "error": str(e)[:500],
                "duration": total_duration,
                "mode": mode,
                "details": details,
            }

    async def sam2_auto_mask(
        self,
        video_path: Path | str,
        output_dir: Path | str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """调用 SAM2 引擎进行自动分割.

        输出每帧 mask PNG 序列，并进行质量评估。

        Args:
            video_path: 输入视频路径
            output_dir: 输出目录
            **kwargs: 额外参数
                - model_size: 模型大小（base/large）
                - prompts: 点提示列表
                - mask_prefix: 遮罩文件名前缀

        Returns:
            包含以下字段的字典：
                - success: 是否成功
                - mask_dir: 遮罩目录路径
                - mask_count: 遮罩帧数
                - quality_score: 质量评分
                - duration: 耗时
        """
        start = time.time()
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        mask_dir = output_dir / "sam2_masks"

        logger.info(f"[Roto] SAM2 auto mask: {video_path}")

        try:
            result = await self.sam2.export_mask_sequence(
                video_path=video_path,
                output_dir=mask_dir,
                prompts=kwargs.get("prompts"),
                model_size=kwargs.get("model_size", "base"),
                mask_prefix=kwargs.get("mask_prefix", "mask_"),
            )

            if not result.success:
                return {
                    "success": False,
                    "error": result.error or "SAM2 mask export failed",
                    "duration": time.time() - start,
                }

            quality_score = self._evaluate_dir_quality(mask_dir)

            return {
                "success": True,
                "mask_dir": str(mask_dir),
                "mask_count": result.metadata.get("mask_count", 0),
                "model_size": result.metadata.get("model_size", "base"),
                "quality_score": round(quality_score, 2),
                "duration": round(result.duration_seconds, 2),
            }

        except Exception as e:
            logger.error(f"[Roto] SAM2 auto mask failed: {e}")
            return {
                "success": False,
                "error": str(e)[:500],
                "duration": time.time() - start,
            }

    async def silhouette_refine(
        self,
        mask_dir: Path | str,
        output_dir: Path | str,
        video_path: Optional[Path | str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """调用 Silhouette 引擎精修 mask.

        进行贝塞尔曲线简化、边缘羽化、运动模糊等精修处理。

        Args:
            mask_dir: 输入遮罩序列目录
            output_dir: 输出目录
            video_path: 原始视频路径（可选，用于运动分析）
            **kwargs: 额外参数
                - feather: 边缘羽化值（像素，默认2.0）
                - motion_blur: 运动模糊强度（0-1，默认0.5）
                - bezier_simplify: 贝塞尔简化容差（默认1.0）

        Returns:
            包含以下字段的字典：
                - success: 是否成功
                - refined_mask_dir: 精修后遮罩目录
                - quality_score: 质量评分
                - duration: 耗时
                - feather: 羽化值
                - motion_blur: 运动模糊强度
        """
        start = time.time()
        mask_dir = Path(mask_dir)
        output_dir = Path(output_dir)
        refined_dir = output_dir / "silhouette_refined"

        logger.info(f"[Roto] Silhouette refine: {mask_dir} -> {refined_dir}")

        try:
            if not mask_dir.exists():
                return {
                    "success": False,
                    "error": f"Mask directory not found: {mask_dir}",
                    "duration": time.time() - start,
                }

            result = await self.silhouette.refine_mask(
                mask_dir=mask_dir,
                output_dir=refined_dir,
                video_path=Path(video_path) if video_path else None,
                feather=kwargs.get("feather", 2.0),
                motion_blur=kwargs.get("motion_blur", 0.5),
                bezier_simplify=kwargs.get("bezier_simplify", 1.0),
            )

            if not result.success:
                return {
                    "success": False,
                    "error": result.error or "Silhouette refine failed",
                    "duration": time.time() - start,
                }

            quality_score = self._evaluate_dir_quality(refined_dir)

            return {
                "success": True,
                "refined_mask_dir": str(refined_dir),
                "quality_score": round(quality_score, 2),
                "duration": round(result.duration_seconds, 2),
                "feather": kwargs.get("feather", 2.0),
                "motion_blur": kwargs.get("motion_blur", 0.5),
                "bezier_simplify": kwargs.get("bezier_simplify", 1.0),
            }

        except Exception as e:
            logger.error(f"[Roto] Silhouette refine failed: {e}")
            return {
                "success": False,
                "error": str(e)[:500],
                "duration": time.time() - start,
            }

    def evaluate_quality(
        self,
        mask_path: Path | str,
        reference: Optional[Path | str] = None,
    ) -> float:
        """计算 mask 质量分（边缘锐度、连通性、噪声等）.

        评估指标：
            - 边缘锐度：基于 Sobel 边缘检测的梯度幅度
            - 连通性：最大连通区域占比
            - 噪声水平：高频噪声占比
            - 填充率：前景像素占比合理性

        Args:
            mask_path: 单张 mask 图片路径
            reference: 参考 mask 路径（可选，用于 IoU 计算）

        Returns:
            质量评分（0-100）
        """
        mask_path = Path(mask_path)
        if not mask_path.exists():
            return 0.0

        try:
            import cv2
            import numpy as np

            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                return 0.0

            _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

            edge_sharpness = self._calc_edge_sharpness(mask)
            connectivity = self._calc_connectivity(binary)
            noise_level = self._calc_noise_level(mask)
            fill_ratio = self._calc_fill_ratio(binary)

            score = (
                edge_sharpness * 0.35
                + connectivity * 0.30
                + (100 - noise_level) * 0.20
                + fill_ratio * 0.15
            )

            if reference and Path(reference).exists():
                ref_mask = cv2.imread(str(reference), cv2.IMREAD_GRAYSCALE)
                if ref_mask is not None:
                    _, ref_binary = cv2.threshold(ref_mask, 127, 255, cv2.THRESH_BINARY)
                    iou = self._calc_iou(binary, ref_binary)
                    score = score * 0.6 + iou * 100 * 0.4

            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.warning(f"[Roto] Quality evaluation failed: {e}")
            return 0.0

    def generate_roto_report(self, result: Dict[str, Any]) -> str:
        """生成抠像报告（质量、耗时、参数）.

        Args:
            result: auto_roto 返回的结果字典

        Returns:
            格式化的报告字符串
        """
        lines = []
        lines.append("=" * 60)
        lines.append("           ROTO 抠像报告")
        lines.append("=" * 60)
        lines.append("")

        status = "成功" if result.get("success") else "失败"
        lines.append(f"状态: {status}")
        lines.append(f"模式: {result.get('mode', 'unknown')}")
        lines.append(f"总耗时: {result.get('duration', 0):.2f} 秒")
        lines.append(f"质量评分: {result.get('quality_score', 0):.2f}/100")
        lines.append("")

        lines.append("-" * 60)
        lines.append("路径信息")
        lines.append("-" * 60)
        lines.append(f"输入视频: {result.get('video_path', 'N/A')}")
        lines.append(f"输出目录: {result.get('output_dir', 'N/A')}")
        lines.append(f"遮罩路径: {result.get('mask_path', 'N/A')}")
        lines.append(f"Alpha 路径: {result.get('alpha_path', 'N/A')}")
        if result.get("report_path"):
            lines.append(f"报告路径: {result['report_path']}")
        lines.append("")

        details = result.get("details", {})
        if details:
            lines.append("-" * 60)
            lines.append("各阶段详情")
            lines.append("-" * 60)

            if "sam2" in details:
                sam2 = details["sam2"]
                lines.append("")
                lines.append("[SAM2 粗分割]")
                lines.append(f"  状态: {'成功' if sam2.get('success') else '失败'}")
                lines.append(f"  遮罩数量: {sam2.get('mask_count', 0)}")
                lines.append(f"  模型大小: {sam2.get('model_size', 'N/A')}")
                lines.append(f"  质量评分: {sam2.get('quality_score', 0):.2f}/100")
                lines.append(f"  耗时: {sam2.get('duration', 0):.2f} 秒")

            if "shape_export" in details:
                shape = details["shape_export"]
                lines.append("")
                lines.append("[形状导出]")
                lines.append(f"  状态: {'成功' if shape.get('success') else '失败'}")
                lines.append(f"  帧数: {shape.get('frame_count', 0)}")
                lines.append(f"  简化容差: {shape.get('simplify_tolerance', 0)}")

            if "silhouette_import" in details:
                sil_import = details["silhouette_import"]
                lines.append("")
                lines.append("[Silhouette 导入]")
                lines.append(f"  状态: {'成功' if sil_import.get('success') else '失败'}")

            if "silhouette_refine" in details:
                refine = details["silhouette_refine"]
                lines.append("")
                lines.append("[Silhouette 精修]")
                lines.append(f"  状态: {'成功' if refine.get('success') else '失败'}")
                lines.append(f"  边缘羽化: {refine.get('feather', 0)}px")
                lines.append(f"  运动模糊: {refine.get('motion_blur', 0)}")
                lines.append(f"  贝塞尔简化: {refine.get('bezier_simplify', 0)}")
                lines.append(f"  质量评分: {refine.get('quality_score', 0):.2f}/100")
                lines.append(f"  耗时: {refine.get('duration', 0):.2f} 秒")

            if "silhouette" in details and isinstance(details["silhouette"], dict):
                sil = details["silhouette"]
                lines.append("")
                lines.append("[Silhouette 自动抠像]")
                lines.append(f"  边缘羽化: {sil.get('feather', 'N/A')}")
                lines.append(f"  输出格式: {sil.get('output_format', 'N/A')}")

            if "alpha_render" in details:
                alpha = details["alpha_render"]
                lines.append("")
                lines.append("[Alpha 渲染]")
                lines.append(f"  状态: {'成功' if alpha.get('success') else '失败'}")
                lines.append(f"  输出格式: {alpha.get('output_format', 'N/A')}")

        if not result.get("success"):
            lines.append("")
            lines.append("-" * 60)
            lines.append("错误信息")
            lines.append("-" * 60)
            lines.append(f"错误: {result.get('error', 'Unknown error')}")

        lines.append("")
        lines.append("=" * 60)
        lines.append(f"报告生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)

        return "\n".join(lines)

    async def _hybrid_roto_pipeline(
        self,
        video_path: Path,
        output_dir: Path,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Hybrid 模式完整流水线：SAM2 粗分 → 形状导出 → Silhouette 精修 → Alpha 渲染.

        Args:
            video_path: 输入视频路径
            output_dir: 输出根目录
            **kwargs: 额外参数

        Returns:
            包含 pipeline 结果的字典
        """
        details: Dict[str, Any] = {}
        current_masks: Optional[Path] = None

        stage1_dir = output_dir / "01_sam2_masks"
        stage2_dir = output_dir / "02_shapes"
        stage3_dir = output_dir / "03_silhouette_refined"
        alpha_dir = output_dir / "alpha"

        sam2_result = await self.sam2_auto_mask(
            video_path, stage1_dir, **kwargs
        )
        details["sam2"] = sam2_result
        if not sam2_result.get("success"):
            return {
                "success": False,
                "error": f"SAM2 stage failed: {sam2_result.get('error')}",
                "details": details,
            }
        current_masks = Path(sam2_result["mask_dir"])
        logger.info("[Roto] Stage 1 (SAM2 mask) completed")

        shape_path = stage2_dir / "sam2_shapes.json"
        shape_result = await self.sam2.export_silhouette_shape(
            mask_dir=current_masks,
            output_path=shape_path,
            video_path=video_path,
            simplify_tolerance=kwargs.get("simplify_tolerance", 1.0),
        )
        details["shape_export"] = {
            "success": shape_result.success,
            "frame_count": shape_result.metadata.get("frame_count", 0),
            "simplify_tolerance": shape_result.metadata.get("simplify_tolerance", 0),
        }
        if not shape_result.success:
            logger.warning(
                f"[Roto] Shape export failed: {shape_result.error}, "
                "continuing with mask-only refine"
            )
        else:
            logger.info("[Roto] Stage 2 (shape export) completed")

        refine_result = await self.silhouette_refine(
            mask_dir=current_masks,
            output_dir=stage3_dir,
            video_path=video_path,
            **kwargs,
        )
        details["silhouette_refine"] = refine_result
        if not refine_result.get("success"):
            logger.warning(
                f"[Roto] Silhouette refine failed: {refine_result.get('error')}, "
                "using SAM2 masks as final"
            )
        else:
            current_masks = Path(refine_result["refined_mask_dir"])
            logger.info("[Roto] Stage 3 (Silhouette refine) completed")

        alpha_result = await self.silhouette.render_alpha(
            input_path=current_masks,
            output_path=alpha_dir,
            output_format="PNG",
            alpha_only=True,
        )
        details["alpha_render"] = {
            "success": alpha_result.success,
            "output_format": alpha_result.metadata.get("output_format", "PNG"),
        }
        if alpha_result.success and alpha_result.output_path:
            final_alpha = alpha_result.output_path
        else:
            final_alpha = current_masks
            logger.warning(
                f"[Roto] Alpha render failed: {alpha_result.error}, "
                "using mask dir as alpha output"
            )

        quality_score = self._evaluate_dir_quality(current_masks)

        return {
            "success": True,
            "mask_path": str(current_masks),
            "alpha_path": str(final_alpha),
            "quality_score": quality_score,
            "details": details,
        }

    def _evaluate_dir_quality(self, mask_dir: Path) -> float:
        """评估整个目录的 mask 平均质量.

        Args:
            mask_dir: 遮罩目录

        Returns:
            平均质量评分（0-100）
        """
        mask_dir = Path(mask_dir)
        if not mask_dir.exists():
            return 0.0

        mask_files = sorted(mask_dir.glob("*.png"))
        if not mask_files:
            return 0.0

        sample_count = min(len(mask_files), 10)
        step = max(1, len(mask_files) // sample_count)
        samples = mask_files[::step][:sample_count]

        scores = []
        for mask_file in samples:
            score = self.evaluate_quality(mask_file)
            if score > 0:
                scores.append(score)

        if not scores:
            return 0.0

        return sum(scores) / len(scores)

    def _calc_edge_sharpness(self, mask: Any) -> float:
        """计算边缘锐度评分（0-100）.

        使用 Sobel 算子计算边缘梯度，梯度越大表示边缘越锐利。
        """
        import cv2
        import numpy as np

        sobel_x = cv2.Sobel(mask, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(mask, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = np.sqrt(sobel_x ** 2 + sobel_y ** 2)

        edge_pixels = magnitude[magnitude > 10]
        if len(edge_pixels) == 0:
            return 0.0

        avg_gradient = np.mean(edge_pixels)
        score = min(100.0, avg_gradient * 2.0)
        return score

    def _calc_connectivity(self, binary_mask: Any) -> float:
        """计算连通性评分（0-100）.

        最大连通区域占总前景面积的比例越高，连通性越好。
        """
        import cv2
        import numpy as np

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            binary_mask, connectivity=8
        )

        if num_labels <= 1:
            foreground_pixels = np.sum(binary_mask > 0)
            if foreground_pixels == 0:
                return 50.0
            return 100.0

        areas = stats[1:, cv2.CC_STAT_AREA]
        if len(areas) == 0:
            return 0.0

        largest_area = np.max(areas)
        total_area = np.sum(areas)

        if total_area == 0:
            return 0.0

        ratio = largest_area / total_area
        score = ratio * 100.0
        return score

    def _calc_noise_level(self, mask: Any) -> float:
        """计算噪声水平评分（0-100，值越高噪声越多）.

        使用中值滤波前后的差异估计噪声水平。
        """
        import cv2
        import numpy as np

        denoised = cv2.medianBlur(mask, 3)
        diff = cv2.absdiff(mask, denoised)

        noise_pixels = np.sum(diff > 20)
        total_pixels = mask.size

        if total_pixels == 0:
            return 0.0

        noise_ratio = noise_pixels / total_pixels
        score = min(100.0, noise_ratio * 1000.0)
        return score

    def _calc_fill_ratio(self, binary_mask: Any) -> float:
        """计算填充率合理性评分（0-100）.

        前景占比在 10%-70% 之间认为是合理的，得分较高。
        """
        import numpy as np

        total_pixels = binary_mask.size
        if total_pixels == 0:
            return 50.0

        foreground_ratio = np.sum(binary_mask > 0) / total_pixels

        if 0.1 <= foreground_ratio <= 0.7:
            score = 100.0
        elif foreground_ratio < 0.1:
            score = foreground_ratio * 10 * 100
        else:
            score = (1.0 - foreground_ratio) / 0.3 * 100

        return max(0.0, min(100.0, score))

    def _calc_iou(self, mask1: Any, mask2: Any) -> float:
        """计算两个二值 mask 的交并比（IoU）.

        Args:
            mask1: 二值 mask 1
            mask2: 二值 mask 2

        Returns:
            IoU 值（0-1）
        """
        import numpy as np

        intersection = np.logical_and(mask1 > 0, mask2 > 0)
        union = np.logical_or(mask1 > 0, mask2 > 0)

        if np.sum(union) == 0:
            return 0.0

        return np.sum(intersection) / np.sum(union)

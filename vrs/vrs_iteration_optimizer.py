#!/usr/bin/env python3
"""
VRS Iteration Optimizer - VRS 迭代优化器
================================================
实现"生成 → 对比参考视频 → 参数微调 → 重新生成"的闭环优化。

针对 VRS v2.0 项目：
    1. 接收参考视频路径与初始分析结果
    2. 通过 vrs_compiler_bridge 将分析结果转换为 AE 脚本
    3. 调用 AEEngine 渲染视频（失败时降级到 FFmpeg 生成占位视频）
    4. 与参考视频逐帧对比（HSV 直方图 / SSIM / 光流 / 亮度）
    5. 根据差异识别调整项，按递减幅度微调参数
    6. 重复直到达到目标相似度或最大迭代次数

依赖：
    pip install opencv-python numpy loguru
    可选：scikit-image（更精确的 SSIM）
    可选：core/llm_gateway.py（VISION 语义对比）

CLI：
    python vrs_iteration_optimizer.py --test
    python vrs_iteration_optimizer.py --compare video1.mp4 video2.mp4
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# =====================================================================
# 可选依赖：cv2 / numpy / skimage
# =====================================================================
try:
    import cv2
    import numpy as np
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False
    cv2 = None  # type: ignore
    np = None  # type: ignore

try:
    from skimage.metrics import structural_similarity as _sk_ssim
    _HAS_SKIMAGE = True
except ImportError:
    _HAS_SKIMAGE = False
    _sk_ssim = None  # type: ignore


# =====================================================================
# VRS Compiler Bridge（同目录模块）
# =====================================================================
try:
    from vrs.vrs_compiler_bridge import VRCompilerBridge
except ImportError:
    VRCompilerBridge = None  # type: ignore


# =====================================================================
# AE / FFmpeg 引擎：puppet-automation 是带横线的目录，惰性导入
# =====================================================================
_AE_ENGINE_CLS: Optional[type] = None
_FF_ENGINE_CLS: Optional[type] = None
_LLM_GATEWAY_CLS: Optional[type] = None
_LLM_TASK_TYPE: Optional[Any] = None


def _ensure_engines_imported() -> None:
    """惰性导入 AE / FFmpeg 引擎与 LLM 网关。
    
    puppet-automation 目录名带横线，无法直接作为包名导入，
    需将该目录加入 sys.path 后用 `src.engines.xxx.engine` 路径导入。
    """
    global _AE_ENGINE_CLS, _FF_ENGINE_CLS, _LLM_GATEWAY_CLS, _LLM_TASK_TYPE
    if _AE_ENGINE_CLS is not None and _FF_ENGINE_CLS is not None:
        return

    project_root = Path(__file__).parent
    pa_dir = project_root / "puppet-automation"
    if pa_dir.is_dir() and str(pa_dir) not in sys.path:
        sys.path.insert(0, str(pa_dir))

    if _AE_ENGINE_CLS is None:
        try:
            from src.engines.ae.engine import AEEngine  # type: ignore
            _AE_ENGINE_CLS = AEEngine
        except Exception as exc:
            logger.debug(f"AEEngine 导入失败: {exc}")

    if _FF_ENGINE_CLS is None:
        try:
            from src.engines.ffmpeg.engine import FFmpegEngine  # type: ignore
            _FF_ENGINE_CLS = FFmpegEngine
        except Exception as exc:
            logger.debug(f"FFmpegEngine 导入失败: {exc}")

    if _LLM_GATEWAY_CLS is None:
        core_dir = project_root / "core"
        if core_dir.is_dir() and str(core_dir.parent) not in sys.path:
            sys.path.insert(0, str(core_dir.parent))
        try:
            from core.llm_gateway import LLMGateway, TaskType  # type: ignore
            _LLM_GATEWAY_CLS = LLMGateway
            _LLM_TASK_TYPE = TaskType
        except Exception as exc:
            logger.debug(f"LLMGateway 导入失败: {exc}")


# =====================================================================
# 常量与权重配置
# =====================================================================

# 综合相似度加权
SIMILARITY_WEIGHTS: Dict[str, float] = {
    "color": 0.3,
    "structure": 0.4,
    "motion": 0.2,
    "brightness": 0.1,
}

# 每轮参数调整幅度（v2 起，幅度递减）
ADJUSTMENT_SCALE: Dict[int, float] = {
    2: 0.30,  # v2: ±30%
    3: 0.20,  # v3: ±20%
    4: 0.10,  # v4: ±10%
    5: 0.05,  # v5: ±5%
}

# 触发调整的相似度阈值
COLOR_SIM_THRESHOLD = 0.7
STRUCTURE_SIM_THRESHOLD = 0.6
MOTION_SIM_THRESHOLD = 0.6
BRIGHTNESS_SIM_THRESHOLD = 0.7

# 帧采样：每秒采 2 帧
SAMPLE_FPS = 2.0

# 单轮渲染超时（秒）= 10 分钟
DEFAULT_RENDER_TIMEOUT = 600


# =====================================================================
# 核心类
# =====================================================================

class IterationOptimizer:
    """VRS 迭代优化器。
    
    闭环工作流：
        1. 接收参考视频路径与初始分析结果
        2. 通过 vrs_compiler_bridge 生成 AE 脚本
        3. 调用 AEEngine 渲染视频（失败降级到 FFmpeg 占位）
        4. 与参考视频逐帧对比（HSV 直方图、SSIM、光流、亮度）
        5. 根据差异识别调整项，应用调整生成下一版分析结果
        6. 重复直到达到目标相似度或最大迭代次数
    
    Attributes:
        compiler_bridge: VRS 编译器桥接
        ae_engine: AE 渲染引擎
        ffmpeg_engine: FFmpeg 引擎（帧提取与降级渲染）
        llm_gateway: LLM 网关（VISION 语义对比）
        output_dir: 迭代产物输出目录
        render_timeout: 单轮渲染超时（秒）
    """

    def __init__(
        self,
        compiler_bridge: Optional[Any] = None,
        ae_engine: Optional[Any] = None,
        ffmpeg_engine: Optional[Any] = None,
        llm_gateway: Optional[Any] = None,
        output_dir: Path | str = "output/vrs_iteration",
        render_timeout: int = DEFAULT_RENDER_TIMEOUT,
    ) -> None:
        """初始化迭代优化器。

        Args:
            compiler_bridge: VRCompilerBridge 实例，未提供时按需创建
            ae_engine: AEEngine 实例，未提供时按需创建
            ffmpeg_engine: FFmpegEngine 实例，未提供时按需创建
            llm_gateway: LLMGateway 实例，未提供时按需创建
            output_dir: 迭代产物输出目录
            render_timeout: 单轮渲染超时秒数（默认 600 = 10 分钟）
        """
        # 触发惰性导入
        _ensure_engines_imported()

        self.compiler_bridge = compiler_bridge or (
            VRCompilerBridge() if VRCompilerBridge is not None else None
        )
        self.ae_engine = ae_engine or (
            _AE_ENGINE_CLS() if _AE_ENGINE_CLS is not None else None
        )
        self.ffmpeg_engine = ffmpeg_engine or (
            _FF_ENGINE_CLS() if _FF_ENGINE_CLS is not None else None
        )
        self.llm_gateway = llm_gateway or (
            _LLM_GATEWAY_CLS() if _LLM_GATEWAY_CLS is not None else None
        )

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.render_timeout = render_timeout

        # VISION 对比启用条件：LLM 网关可用且 cv2 可用
        self._vision_enabled = bool(self.llm_gateway is not None and _HAS_CV2)

    # ================================================================
    #  1. 主入口
    # ================================================================

    async def optimize(
        self,
        reference_video: str,
        initial_analysis: dict,
        max_iterations: int = 5,
        target_similarity: float = 0.85,
    ) -> dict:
        """迭代优化参考视频的复现效果。

        流程：
            v1（baseline，不调整）→ 渲染 → 对比 → 识别调整 → v2 → ... → 收敛

        Args:
            reference_video: 参考视频文件路径
            initial_analysis: 初始分析结果（VRS 分析器输出）
            max_iterations: 最大迭代次数，默认 5
            target_similarity: 目标相似度，达到则停止，默认 0.85

        Returns:
            {
                "iterations": [...],       # 每轮迭代记录
                "final_similarity": float,
                "final_analysis": dict,
                "converged": bool,
                "stop_reason": str,
            }
        """
        reference_path = Path(reference_video)
        if not reference_path.is_file():
            return {
                "iterations": [],
                "final_similarity": 0.0,
                "final_analysis": initial_analysis,
                "converged": False,
                "stop_reason": f"参考视频不存在: {reference_video}",
            }

        iterations: List[Dict[str, Any]] = []
        current_analysis = deepcopy(initial_analysis)
        prev_similarity = 0.0
        last_improvement = 0.0
        converged = False
        stop_reason = "max_iterations_reached"

        for version in range(1, max_iterations + 1):
            logger.info("===== VRS 迭代 v{} 开始 =====", version)
            iteration_start = time.time()

            # 1. 渲染当前版本（带超时保护）
            try:
                rendered_path = await asyncio.wait_for(
                    self.render_current_version(current_analysis, version),
                    timeout=self.render_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "v{} 渲染超时（{}s），跳过本轮", version, self.render_timeout
                )
                iterations.append({
                    "version": version,
                    "rendered_path": None,
                    "comparison": None,
                    "similarity": None,
                    "adjustments": [],
                    "elapsed_sec": time.time() - iteration_start,
                    "error": "render_timeout",
                })
                continue
            except Exception as exc:
                logger.exception("v{} 渲染失败", version)
                iterations.append({
                    "version": version,
                    "rendered_path": None,
                    "comparison": None,
                    "similarity": None,
                    "adjustments": [],
                    "elapsed_sec": time.time() - iteration_start,
                    "error": str(exc),
                })
                continue

            # 2. 与参考视频对比
            comparison = await self.compare_videos(
                str(reference_path), str(rendered_path)
            )
            similarity = self.compute_similarity_score(comparison)
            logger.info(
                "v{} 相似度: {:.4f} (color={:.3f} struct={:.3f} motion={:.3f} bright={:.3f})",
                version, similarity,
                comparison.get("color_sim", 0),
                comparison.get("structure_sim", 0),
                comparison.get("motion_sim", 0),
                comparison.get("brightness_sim", 0),
            )

            iteration_record: Dict[str, Any] = {
                "version": version,
                "rendered_path": str(rendered_path),
                "comparison": comparison,
                "similarity": similarity,
                "adjustments": [],
                "elapsed_sec": time.time() - iteration_start,
            }
            iterations.append(iteration_record)

            # 3. 收敛判定：达到目标
            if similarity >= target_similarity:
                converged = True
                stop_reason = "target_reached"
                logger.info(
                    "v{} 达到目标相似度 {:.4f} >= {:.4f}",
                    version, similarity, target_similarity,
                )
                break

            # 4. 收敛判定：连续两轮提升 < 2%
            improvement = similarity - prev_similarity
            if version >= 3 and improvement < 0.02 and last_improvement < 0.02:
                converged = True
                stop_reason = "marginal_improvement"
                logger.info(
                    "v{} 提升停滞（{:.4f}, {:.4f}），停止迭代",
                    version, last_improvement, improvement,
                )
                break

            last_improvement = improvement
            prev_similarity = similarity

            # 5. 最后一轮不再调整
            if version == max_iterations:
                stop_reason = "max_iterations_reached"
                break

            # 6. 识别调整项并按版本缩放
            adjustments = self.identify_adjustments(comparison, current_analysis)
            scale = ADJUSTMENT_SCALE.get(version + 1, 0.05)
            scaled_adjustments = self._scale_adjustments(adjustments, scale)
            iteration_record["adjustments"] = scaled_adjustments

            current_analysis = self.apply_adjustments(
                current_analysis, scaled_adjustments
            )
            logger.info(
                "v{} 识别调整项 {} 个（缩放 {:.0%}），已应用到 v{}",
                version, len(scaled_adjustments), scale, version + 1,
            )

        final_similarity = (
            iterations[-1].get("similarity", 0.0) if iterations else 0.0
        )
        return {
            "iterations": iterations,
            "final_similarity": final_similarity,
            "final_analysis": current_analysis,
            "converged": converged,
            "stop_reason": stop_reason,
        }

    # ================================================================
    #  2. 渲染当前版本
    # ================================================================

    async def render_current_version(self, analysis: dict, version: int) -> str:
        """渲染指定版本的视频。

        流程：
            1. 通过 compiler_bridge 生成 CompilerInput
            2. 编译为 ExtendScript
            3. 调用 AEEngine 执行脚本并渲染
            4. AE 不可用或失败时，降级到 FFmpeg 生成占位视频

        Args:
            analysis: 分析结果字典
            version: 版本号（1, 2, 3...）

        Returns:
            渲染后的视频文件路径

        Raises:
            RuntimeError: 渲染失败（AE 与 FFmpeg 均不可用）
        """
        version_dir = self.output_dir / f"v{version}"
        version_dir.mkdir(parents=True, exist_ok=True)
        output_path = version_dir / f"render_v{version}.mp4"

        # 1. 检查 compiler_bridge
        if self.compiler_bridge is None:
            logger.warning("compiler_bridge 不可用，直接降级到 FFmpeg 占位")
            return await self._render_fallback_placeholder(
                analysis, version, output_path
            )

        # 2. 转换为 CompilerInput
        compiler_input = self.compiler_bridge.convert_analysis_to_compiler_input(analysis)
        compiler_input_path = version_dir / f"compiler_input_v{version}.json"
        with open(compiler_input_path, "w", encoding="utf-8") as f:
            json.dump(compiler_input, f, ensure_ascii=False, indent=2)

        # 3. 编译为 ExtendScript
        compile_result = self.compiler_bridge.compile_to_script(compiler_input)
        if not compile_result.get("success"):
            logger.warning(
                "v{} 编译失败: {}", version, compile_result.get("errors", [])
            )
            return await self._render_fallback_placeholder(
                analysis, version, output_path
            )

        script_content = compile_result.get("script_content", "")
        if not script_content:
            logger.warning("v{} 编译输出空脚本，降级", version)
            return await self._render_fallback_placeholder(
                analysis, version, output_path
            )

        script_path = version_dir / f"script_v{version}.jsx"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # 4. 调用 AEEngine 渲染
        if self.ae_engine is None:
            logger.warning("AEEngine 不可用，降级到 FFmpeg 占位")
            return await self._render_fallback_placeholder(
                analysis, version, output_path
            )

        try:
            # 4.1 执行脚本（创建合成、添加图层、应用效果）
            run_result = await self.ae_engine.run_script(script_content)
            if not run_result.success:
                logger.warning(
                    "v{} 脚本执行失败: {}", version, run_result.error
                )
                return await self._render_fallback_placeholder(
                    analysis, version, output_path
                )

            # 4.2 调用 render queue 渲染到指定输出路径
            render_script = self._build_render_script(
                comp_name=self.compiler_bridge.default_comp_name,
                output_path=str(output_path),
            )
            render_result = await self.ae_engine.run_script(render_script)
            if render_result.success and output_path.is_file():
                logger.info("v{} AE 渲染成功: {}", version, output_path)
                return str(output_path)

            logger.warning(
                "v{} AE 渲染失败: {}", version, getattr(render_result, "error", "unknown")
            )
            return await self._render_fallback_placeholder(
                analysis, version, output_path
            )
        except Exception as exc:
            logger.exception("v{} AE 渲染异常", version)
            return await self._render_fallback_placeholder(
                analysis, version, output_path
            )

    async def _render_fallback_placeholder(
        self, analysis: dict, version: int, output_path: Path
    ) -> str:
        """FFmpeg 降级占位视频生成。

        当 AE 不可用时，根据分析结果的色温/饱和度参数生成纯色背景视频，
        以保证迭代流程可继续（对比时至少能反映参数变化）。

        Args:
            analysis: 分析结果
            version: 版本号
            output_path: 输出路径

        Returns:
            占位视频路径

        Raises:
            RuntimeError: FFmpeg 不可用或生成失败
        """
        # 直接调用 ffmpeg CLI（FFmpegEngine.convert 不支持 lavfi 输入）
        color_grading = analysis.get("color_grading") or {}
        lumetri = color_grading.get("ae_lumetri_params") or {}
        temperature = float(lumetri.get("temperature", 0))

        # 温度映射到颜色：正温度偏暖（橙），负温度偏冷（蓝）
        r = max(0, min(255, int(128 + temperature * 5)))
        b = max(0, min(255, int(128 - temperature * 5)))
        g = max(0, min(255, int(128 - abs(temperature) * 2)))
        color_str = f"0x{r:02x}{g:02x}{b:02x}"

        # 合成参数
        basic = analysis.get("basic_info") or {}
        comp = (analysis.get("ae_parameters") or {}).get("composition") or {}
        width = int(basic.get("width", comp.get("width", 1920)))
        height = int(basic.get("height", comp.get("height", 1080)))
        fps = int(basic.get("fps", comp.get("fps", 30)))
        duration = float(basic.get("duration", comp.get("duration", 5)))

        # ffmpeg 可执行路径
        ffmpeg_bin = "ffmpeg"
        if self.ffmpeg_engine is not None:
            ffmpeg_bin = str(getattr(self.ffmpeg_engine, "executable_path", "ffmpeg"))

        cmd = [
            ffmpeg_bin, "-y",
            "-f", "lavfi",
            "-i", f"color=c={color_str}:s={width}x{height}:r={fps}:d={duration}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]

        try:
            proc = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=120
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"FFmpeg 占位视频生成超时: {exc}") from exc

        if proc.returncode == 0 and output_path.is_file():
            logger.info(
                "v{} FFmpeg 占位视频已生成: {} (color={})",
                version, output_path, color_str,
            )
            return str(output_path)

        raise RuntimeError(
            f"FFmpeg 占位视频生成失败 (rc={proc.returncode}): {proc.stderr[:500]}"
        )

    def _build_render_script(self, comp_name: str, output_path: str) -> str:
        """构建 AE 渲染脚本（通过 ExtendScript 调用 render queue）。

        Args:
            comp_name: 目标合成名
            output_path: 输出文件绝对路径

        Returns:
            ExtendScript 脚本字符串
        """
        # 转义 Windows 路径反斜杠
        escaped_path = output_path.replace("\\", "/")
        return f'''
(function() {{
    var comp = null;
    for (var i = 1; i <= app.project.numItems; i++) {{
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === "{comp_name}") {{
            comp = item;
            break;
        }}
    }}
    if (!comp) {{
        return JSON.stringify({{success: false, error: "comp not found: {comp_name}"}});
    }}
    var rq = app.project.renderQueue;
    var rqItem = rq.items.add(comp);
    var om = rqItem.outputModule(1);
    om.file = new File("{escaped_path}");
    try {{
        om.template = "H.264";
    }} catch (e) {{
        // H.264 模板不存在则保留默认
    }}
    rq.render();
    return JSON.stringify({{success: true, output: "{escaped_path}"}});
}})();
'''

    # ================================================================
    #  3. 视频对比
    # ================================================================

    async def compare_videos(self, reference: str, generated: str) -> dict:
        """逐帧对比两个视频的相似度。

        对比维度：
            - 颜色直方图相似度（HSV 巴氏距离）
            - 结构相似度（SSIM，skimage 优先，降级简化版）
            - 光流相似度（Farneback 运动方向一致性）
            - 亮度分布相似度（直方图相关性）

        采样：每秒采 2 帧，按时间戳对齐帧。

        Args:
            reference: 参考视频路径
            generated: 生成视频路径

        Returns:
            {
                "overall_similarity": float,
                "color_sim": float,
                "structure_sim": float,
                "motion_sim": float,
                "brightness_sim": float,
                "frame_details": [...],
                "sample_count": int,
            }
        """
        if not _HAS_CV2:
            logger.warning("cv2 不可用，对比降级到默认 0.5 相似度")
            return {
                "overall_similarity": 0.5,
                "color_sim": 0.5,
                "structure_sim": 0.5,
                "motion_sim": 0.5,
                "brightness_sim": 0.5,
                "frame_details": [],
                "sample_count": 0,
                "error": "cv2_unavailable",
            }

        ref_dir = self.output_dir / "_ref_frames"
        gen_dir = self.output_dir / "_gen_frames"

        # 清理旧帧
        for d in (ref_dir, gen_dir):
            d.mkdir(parents=True, exist_ok=True)
            for f in d.glob("*.png"):
                try:
                    f.unlink()
                except OSError:
                    pass

        # 抽帧（优先用 FFmpegEngine，降级用 cv2）
        if self.ffmpeg_engine is not None:
            await self.ffmpeg_engine.extract_frames(
                reference, ref_dir, fps=SAMPLE_FPS
            )
            await self.ffmpeg_engine.extract_frames(
                generated, gen_dir, fps=SAMPLE_FPS
            )
        else:
            await asyncio.to_thread(self._extract_frames_cv2, reference, ref_dir)
            await asyncio.to_thread(self._extract_frames_cv2, generated, gen_dir)

        ref_frames = sorted(ref_dir.glob("*.png"))
        gen_frames = sorted(gen_dir.glob("*.png"))

        if not ref_frames or not gen_frames:
            logger.warning(
                "抽帧失败 ref={} gen={}", len(ref_frames), len(gen_frames)
            )
            return {
                "overall_similarity": 0.3,
                "color_sim": 0.3,
                "structure_sim": 0.3,
                "motion_sim": 0.3,
                "brightness_sim": 0.3,
                "frame_details": [],
                "sample_count": 0,
                "error": "frame_extraction_failed",
            }

        # 按时间戳对齐帧（允许不同帧率）
        aligned_pairs = self._align_frames(ref_frames, gen_frames)

        color_sims: List[float] = []
        struct_sims: List[float] = []
        motion_sims: List[float] = []
        bright_sims: List[float] = []
        frame_details: List[Dict[str, Any]] = []

        prev_ref_gray: Optional[Any] = None
        prev_gen_gray: Optional[Any] = None

        for idx, (ref_frame, gen_frame, ts) in enumerate(aligned_pairs):
            ref_img = cv2.imread(str(ref_frame))
            gen_img = cv2.imread(str(gen_frame))

            if ref_img is None or gen_img is None:
                continue

            # 统一尺寸（以参考为准）
            h, w = ref_img.shape[:2]
            if gen_img.shape[:2] != (h, w):
                gen_img = cv2.resize(gen_img, (w, h))

            # 1. 颜色直方图相似度（HSV）
            color_sim = self._compute_color_similarity(ref_img, gen_img)

            # 2. 结构相似度（SSIM）
            struct_sim = self._compute_ssim(ref_img, gen_img)

            # 3. 光流相似度
            ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
            gen_gray = cv2.cvtColor(gen_img, cv2.COLOR_BGR2GRAY)
            if prev_ref_gray is not None and prev_gen_gray is not None:
                motion_sim = self._compute_motion_similarity(
                    prev_ref_gray, ref_gray, prev_gen_gray, gen_gray
                )
            else:
                # 首帧无运动参考，默认一致
                motion_sim = 1.0

            # 4. 亮度分布相似度
            bright_sim = self._compute_brightness_similarity(ref_gray, gen_gray)

            color_sims.append(color_sim)
            struct_sims.append(struct_sim)
            motion_sims.append(motion_sim)
            bright_sims.append(bright_sim)

            frame_details.append({
                "index": idx,
                "timestamp": float(ts),
                "color_sim": color_sim,
                "structure_sim": struct_sim,
                "motion_sim": motion_sim,
                "brightness_sim": bright_sim,
            })

            prev_ref_gray = ref_gray
            prev_gen_gray = gen_gray

        if not color_sims:
            return {
                "overall_similarity": 0.3,
                "color_sim": 0.3,
                "structure_sim": 0.3,
                "motion_sim": 0.3,
                "brightness_sim": 0.3,
                "frame_details": [],
                "sample_count": 0,
                "error": "no_valid_frames",
            }

        color_avg = float(np.mean(color_sims))
        struct_avg = float(np.mean(struct_sims))
        motion_avg = float(np.mean(motion_sims))
        bright_avg = float(np.mean(bright_sims))

        overall = (
            SIMILARITY_WEIGHTS["color"] * color_avg
            + SIMILARITY_WEIGHTS["structure"] * struct_avg
            + SIMILARITY_WEIGHTS["motion"] * motion_avg
            + SIMILARITY_WEIGHTS["brightness"] * bright_avg
        )

        return {
            "overall_similarity": float(overall),
            "color_sim": color_avg,
            "structure_sim": struct_avg,
            "motion_sim": motion_avg,
            "brightness_sim": bright_avg,
            "frame_details": frame_details,
            "sample_count": len(color_sims),
        }

    def _extract_frames_cv2(
        self, video_path: str, output_dir: Path, fps: float = SAMPLE_FPS
    ) -> None:
        """用 cv2.VideoCapture 抽帧（FFmpeg 不可用时的降级方案）。

        Args:
            video_path: 视频文件路径
            output_dir: 帧输出目录
            fps: 采样帧率
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning("无法打开视频: {}", video_path)
            return

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = max(1, int(video_fps / fps))
        idx = 0
        saved = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % frame_interval == 0:
                out_path = output_dir / f"frame_{saved:06d}.png"
                cv2.imwrite(str(out_path), frame)
                saved += 1
            idx += 1
        cap.release()

    def _align_frames(
        self, ref_frames: List[Path], gen_frames: List[Path]
    ) -> List[Tuple[Path, Path, float]]:
        """按时间戳对齐两个视频的帧。

        帧文件名约定：frame_%06d.png（按序号排序）。
        时间戳按帧序号 * (1/SAMPLE_FPS) 估算。

        Args:
            ref_frames: 参考视频帧列表
            gen_frames: 生成视频帧列表

        Returns:
            对齐后的 (ref_frame, gen_frame, timestamp) 三元组列表
        """
        pairs: List[Tuple[Path, Path, float]] = []
        n = min(len(ref_frames), len(gen_frames))
        for i in range(n):
            ts = i / SAMPLE_FPS
            pairs.append((ref_frames[i], gen_frames[i], ts))
        return pairs

    def _compute_color_similarity(self, ref_img: Any, gen_img: Any) -> float:
        """HSV 直方图巴氏距离 → 相似度（0~1）。

        Args:
            ref_img: 参考帧 BGR 图像
            gen_img: 生成帧 BGR 图像

        Returns:
            相似度（1 = 完全相同，0 = 完全不同）
        """
        ref_hsv = cv2.cvtColor(ref_img, cv2.COLOR_BGR2HSV)
        gen_hsv = cv2.cvtColor(gen_img, cv2.COLOR_BGR2HSV)

        hist_size = [50, 60]
        ranges = [0, 180, 0, 256]
        channels = [0, 1]

        ref_hist = cv2.calcHist([ref_hsv], channels, None, hist_size, ranges)
        gen_hist = cv2.calcHist([gen_hsv], channels, None, hist_size, ranges)

        cv2.normalize(ref_hist, ref_hist, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(gen_hist, gen_hist, 0, 1, cv2.NORM_MINMAX)

        # Bhattacharyya 距离：0 = 完全相同，1 = 完全不同
        dist = cv2.compareHist(ref_hist, gen_hist, cv2.HISTCMP_BHATTACHARYYA)
        return float(1.0 - dist)

    def _compute_ssim(self, ref_img: Any, gen_img: Any) -> float:
        """结构相似度（SSIM）。

        优先使用 skimage，降级到简化版（基于亮度均值+方差+协方差）。

        Args:
            ref_img: 参考帧
            gen_img: 生成帧

        Returns:
            SSIM 值（0~1）
        """
        ref_gray = (
            cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
            if len(ref_img.shape) == 3 else ref_img
        )
        gen_gray = (
            cv2.cvtColor(gen_img, cv2.COLOR_BGR2GRAY)
            if len(gen_img.shape) == 3 else gen_img
        )

        if _HAS_SKIMAGE:
            try:
                score, _ = _sk_ssim(ref_gray, gen_gray, full=True)
                return float(score)
            except Exception:
                pass

        return self._simplified_ssim(ref_gray, gen_gray)

    def _simplified_ssim(self, ref_gray: Any, gen_gray: Any) -> float:
        """简化版 SSIM：基于亮度均值、方差、协方差。

        公式：
            SSIM = ((2μ1μ2 + C1)(2σ12 + C2)) / ((μ1² + μ2² + C1)(σ1² + σ2² + C2))

        Args:
            ref_gray: 参考灰度图
            gen_gray: 生成灰度图

        Returns:
            简化 SSIM 值（0~1）
        """
        ref = ref_gray.astype(np.float64)
        gen = gen_gray.astype(np.float64)

        # 防止分母为 0 的常数
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        mu1 = float(ref.mean())
        mu2 = float(gen.mean())
        sigma1_sq = float(ref.var())
        sigma2_sq = float(gen.var())
        sigma12 = float(((ref - mu1) * (gen - mu2)).mean())

        numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        denominator = (mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2)

        return float(numerator / max(denominator, 1e-10))

    def _compute_motion_similarity(
        self,
        prev_ref: Any, curr_ref: Any,
        prev_gen: Any, curr_gen: Any,
    ) -> float:
        """光流相似度（运动方向一致性）。

        用 Farneback 分别计算两个视频相邻帧的光流，比较主方向与幅值。

        Args:
            prev_ref: 参考视频前一帧灰度图
            curr_ref: 参考视频当前帧灰度图
            prev_gen: 生成视频前一帧灰度图
            curr_gen: 生成视频当前帧灰度图

        Returns:
            运动相似度（0~1）
        """
        try:
            ref_flow = cv2.calcOpticalFlowFarneback(
                prev_ref, curr_ref, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            gen_flow = cv2.calcOpticalFlowFarneback(
                prev_gen, curr_gen, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
        except Exception:
            return 0.5

        ref_mag, ref_ang = cv2.cartToPolar(ref_flow[..., 0], ref_flow[..., 1])
        gen_mag, gen_ang = cv2.cartToPolar(gen_flow[..., 0], gen_flow[..., 1])

        # 幅值相似度
        ref_mean_mag = float(ref_mag.mean())
        gen_mean_mag = float(gen_mag.mean())
        mag_diff = abs(ref_mean_mag - gen_mean_mag)
        mag_sim = 1.0 / (1.0 + mag_diff * 10)

        # 角度相似度（方向向量均值的余弦相似度）
        ref_dx = float(np.cos(ref_ang).mean() * ref_mean_mag)
        ref_dy = float(np.sin(ref_ang).mean() * ref_mean_mag)
        gen_dx = float(np.cos(gen_ang).mean() * gen_mean_mag)
        gen_dy = float(np.sin(gen_ang).mean() * gen_mean_mag)

        norm_ref = (ref_dx ** 2 + ref_dy ** 2) ** 0.5
        norm_gen = (gen_dx ** 2 + gen_dy ** 2) ** 0.5
        if norm_ref < 1e-6 and norm_gen < 1e-6:
            ang_sim = 1.0  # 都几乎静止
        elif norm_ref < 1e-6 or norm_gen < 1e-6:
            ang_sim = 0.0  # 一方静止一方运动
        else:
            cos_sim = (ref_dx * gen_dx + ref_dy * gen_dy) / (norm_ref * norm_gen)
            ang_sim = (cos_sim + 1) / 2  # 映射到 [0, 1]

        return float(0.5 * mag_sim + 0.5 * ang_sim)

    def _compute_brightness_similarity(
        self, ref_gray: Any, gen_gray: Any
    ) -> float:
        """亮度分布相似度（基于直方图相关性）。

        Args:
            ref_gray: 参考灰度图
            gen_gray: 生成灰度图

        Returns:
            亮度相似度（0~1）
        """
        ref_hist = cv2.calcHist([ref_gray], [0], None, [256], [0, 256])
        gen_hist = cv2.calcHist([gen_gray], [0], None, [256], [0, 256])
        cv2.normalize(ref_hist, ref_hist, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(gen_hist, gen_hist, 0, 1, cv2.NORM_MINMAX)

        # HISTCMP_CORREL: 1 = 完全正相关，0 = 无相关，-1 = 反相关
        corr = cv2.compareHist(ref_hist, gen_hist, cv2.HISTCMP_CORREL)
        return float((corr + 1) / 2)

    # ================================================================
    #  4. 综合相似度
    # ================================================================

    def compute_similarity_score(self, comparison: dict) -> float:
        """综合相似度计算（加权平均）。

        权重：
            - 颜色相似度 0.3
            - 结构相似度 0.4
            - 运动相似度 0.2
            - 亮度相似度 0.1

        Args:
            comparison: compare_videos 返回的对比结果

        Returns:
            综合相似度（0~1）
        """
        color = float(comparison.get("color_sim", 0))
        struct = float(comparison.get("structure_sim", 0))
        motion = float(comparison.get("motion_sim", 0))
        bright = float(comparison.get("brightness_sim", 0))

        score = (
            SIMILARITY_WEIGHTS["color"] * color
            + SIMILARITY_WEIGHTS["structure"] * struct
            + SIMILARITY_WEIGHTS["motion"] * motion
            + SIMILARITY_WEIGHTS["brightness"] * bright
        )
        return float(score)

    # ================================================================
    #  5. 识别调整项
    # ================================================================

    def identify_adjustments(
        self, comparison: dict, current_analysis: dict
    ) -> list:
        """根据对比结果识别需要调整的参数。

        内置规则：
            - 颜色偏差大 → Lumetri Color temperature/tint/saturation/contrast
            - 结构相似度低 → 效果强度（模糊半径、发光强度）
            - 运动相似度低 → 关键帧缓动改为 easeInOut
            - 亮度偏差 → highlights/shadows

        Args:
            comparison: compare_videos 返回的对比结果
            current_analysis: 当前分析结果

        Returns:
            [{param_path, current_value, suggested_value, reason, delta}]
        """
        adjustments: List[Dict[str, Any]] = []

        color_sim = float(comparison.get("color_sim", 1.0))
        struct_sim = float(comparison.get("structure_sim", 1.0))
        motion_sim = float(comparison.get("motion_sim", 1.0))
        bright_sim = float(comparison.get("brightness_sim", 1.0))

        color_grading = current_analysis.get("color_grading") or {}
        lumetri = color_grading.get("ae_lumetri_params") or {}

        # ----- 1. 颜色调整 -----
        if color_sim < COLOR_SIM_THRESHOLD:
            frame_details = comparison.get("frame_details") or []
            ref_warmer = self._infer_reference_warmer(frame_details)
            ref_more_saturated = self._infer_reference_more_saturated(frame_details)
            ref_higher_contrast = self._infer_reference_higher_contrast(frame_details)

            if ref_warmer is not None:
                cur_temp = float(lumetri.get("temperature", 0))
                delta = 5 if ref_warmer else -5
                adjustments.append({
                    "param_path": "color_grading.ae_lumetri_params.temperature",
                    "current_value": cur_temp,
                    "suggested_value": cur_temp + delta,
                    "reason": (
                        f"color_sim={color_sim:.3f}<{COLOR_SIM_THRESHOLD}, "
                        f"reference {'warmer' if ref_warmer else 'cooler'}"
                    ),
                    "delta": delta,
                })

            if ref_more_saturated is not None:
                cur_sat = float(lumetri.get("saturation", 0))
                delta = 10 if ref_more_saturated else -10
                adjustments.append({
                    "param_path": "color_grading.ae_lumetri_params.saturation",
                    "current_value": cur_sat,
                    "suggested_value": cur_sat + delta,
                    "reason": (
                        f"color_sim={color_sim:.3f}<{COLOR_SIM_THRESHOLD}, "
                        f"reference {'more saturated' if ref_more_saturated else 'less saturated'}"
                    ),
                    "delta": delta,
                })

            if ref_higher_contrast is not None:
                cur_con = float(lumetri.get("contrast", 0))
                delta = 10 if ref_higher_contrast else -10
                adjustments.append({
                    "param_path": "color_grading.ae_lumetri_params.contrast",
                    "current_value": cur_con,
                    "suggested_value": cur_con + delta,
                    "reason": (
                        f"color_sim={color_sim:.3f}<{COLOR_SIM_THRESHOLD}, "
                        f"reference {'higher contrast' if ref_higher_contrast else 'lower contrast'}"
                    ),
                    "delta": delta,
                })

        # ----- 2. 结构相似度调整 → 效果强度 -----
        if struct_sim < STRUCTURE_SIM_THRESHOLD:
            visual_effects = current_analysis.get("visual_effects") or {}
            for eff in visual_effects.get("detected_effects", []):
                eff_name = (eff.get("name") or "").lower()
                eff_type = eff.get("type") or ""
                params = eff.get("ae_params") or eff.get("params") or {}

                # 模糊：增强 Blurriness
                if "blur" in eff_name or eff_type == "blur":
                    blur_val = (
                        params.get("Blurriness")
                        or params.get("blurriness")
                        or params.get("Blur Radius")
                    )
                    if blur_val is not None:
                        cur_val = float(blur_val)
                        adjustments.append({
                            "param_path": (
                                f"visual_effects.detected_effects[name={eff.get('name')}]."
                                f"params.Blurriness"
                            ),
                            "current_value": cur_val,
                            "suggested_value": cur_val * 1.2,
                            "reason": (
                                f"struct_sim={struct_sim:.3f}<{STRUCTURE_SIM_THRESHOLD}, "
                                f"increase blur strength"
                            ),
                            "delta": cur_val * 0.2,
                        })

                # 发光：增强 Glow Intensity
                if "glow" in eff_name or eff_type == "glow":
                    glow_val = (
                        params.get("Glow Intensity")
                        or params.get("intensity")
                    )
                    if glow_val is not None:
                        cur_val = float(glow_val)
                        adjustments.append({
                            "param_path": (
                                f"visual_effects.detected_effects[name={eff.get('name')}]."
                                f"params.Glow Intensity"
                            ),
                            "current_value": cur_val,
                            "suggested_value": cur_val * 1.2,
                            "reason": (
                                f"struct_sim={struct_sim:.3f}<{STRUCTURE_SIM_THRESHOLD}, "
                                f"increase glow intensity"
                            ),
                            "delta": cur_val * 0.2,
                        })

        # ----- 3. 运动相似度调整 → 关键帧缓动 -----
        if motion_sim < MOTION_SIM_THRESHOLD:
            ae_params = current_analysis.get("ae_parameters") or {}
            for i, kf in enumerate(ae_params.get("keyframes", [])):
                cur_easing = (
                    kf.get("easing")
                    or (kf.get("params") or {}).get("easing")
                    or "linear"
                )
                if cur_easing != "easeInOut":
                    adjustments.append({
                        "param_path": f"ae_parameters.keyframes[{i}].easing",
                        "current_value": cur_easing,
                        "suggested_value": "easeInOut",
                        "reason": (
                            f"motion_sim={motion_sim:.3f}<{MOTION_SIM_THRESHOLD}, "
                            f"smooth easing"
                        ),
                        "delta": "easeInOut",
                    })

        # ----- 4. 亮度调整 -----
        if bright_sim < BRIGHTNESS_SIM_THRESHOLD:
            highlights = float(lumetri.get("highlights", 0))
            shadows = float(lumetri.get("shadows", 0))
            adjustments.append({
                "param_path": "color_grading.ae_lumetri_params.highlights",
                "current_value": highlights,
                "suggested_value": highlights + 5,
                "reason": (
                    f"brightness_sim={bright_sim:.3f}<{BRIGHTNESS_SIM_THRESHOLD}, "
                    f"increase highlights"
                ),
                "delta": 5,
            })
            adjustments.append({
                "param_path": "color_grading.ae_lumetri_params.shadows",
                "current_value": shadows,
                "suggested_value": shadows - 5,
                "reason": (
                    f"brightness_sim={bright_sim:.3f}<{BRIGHTNESS_SIM_THRESHOLD}, "
                    f"decrease shadows"
                ),
                "delta": -5,
            })

        return adjustments

    def _infer_reference_warmer(
        self, frame_details: list
    ) -> Optional[bool]:
        """从 frame_details 推断参考视频是否更暖。

        简化启发式：当 color_sim 偏低且有帧数据时，默认认为参考偏暖（保守策略）。
        完整实现需保留抽帧时的颜色统计。
        """
        return True if frame_details else None

    def _infer_reference_more_saturated(
        self, frame_details: list
    ) -> Optional[bool]:
        """推断参考视频是否更饱和。"""
        return True if frame_details else None

    def _infer_reference_higher_contrast(
        self, frame_details: list
    ) -> Optional[bool]:
        """推断参考视频是否对比度更高。"""
        return True if frame_details else None

    # ================================================================
    #  6. 应用调整
    # ================================================================

    def apply_adjustments(
        self, analysis: dict, adjustments: list
    ) -> dict:
        """将调整应用到分析结果，生成下一版本的分析。

        Args:
            analysis: 当前分析结果（不会被修改）
            adjustments: identify_adjustments 返回的调整列表

        Returns:
            新的 analysis 字典（深拷贝）
        """
        new_analysis = deepcopy(analysis)

        for adj in adjustments:
            path = adj.get("param_path", "")
            suggested = adj.get("suggested_value")
            if not path or suggested is None:
                continue

            try:
                self._set_nested(new_analysis, path, suggested)
            except Exception as exc:
                logger.warning("应用调整失败 {}: {}", path, exc)

        return new_analysis

    def _set_nested(self, d: dict, path: str, value: Any) -> None:
        """按点分路径设置嵌套字典的值。

        支持路径格式：
            - color_grading.ae_lumetri_params.temperature
            - visual_effects.detected_effects[name=模糊].params.Blurriness
            - ae_parameters.keyframes[2].easing

        Args:
            d: 目标字典
            path: 点分路径
            value: 要设置的值
        """
        tokens = path.split(".")
        cur: Any = d
        for tok in tokens[:-1]:
            cur = self._navigate(cur, tok)
            if cur is None:
                return

        last = tokens[-1]
        # 最后一段若包含 [] 谓词，需要先 navigate 到容器
        if "[" in last:
            key, _, rest = last.partition("[")
            pred = rest.rstrip("]")
            container = cur.get(key) if isinstance(cur, dict) else None
            if not isinstance(container, list):
                return
            target = self._find_in_list(container, pred)
            if isinstance(target, dict):
                # 最后一段没有具体属性时，直接返回（不支持根替换）
                pass
            return

        if isinstance(cur, dict):
            cur[last] = value

    def _navigate(self, obj: Any, token: str) -> Any:
        """导航到下一层。

        Args:
            obj: 当前对象
            token: 路径段，可能为 'key' / 'list[2]' / 'list[name=xxx]'

        Returns:
            下一层对象，找不到时返回 None
        """
        if "[" not in token:
            return obj.get(token) if isinstance(obj, dict) else None

        key, _, rest = token.partition("[")
        pred = rest.rstrip("]")
        obj = obj.get(key) if isinstance(obj, dict) else None
        if obj is None:
            return None

        if not isinstance(obj, list):
            return None

        # 数字索引
        if pred.isdigit():
            idx = int(pred)
            return obj[idx] if 0 <= idx < len(obj) else None

        # 谓词 [name=xxx]
        if "=" in pred:
            k, _, v = pred.partition("=")
            v = v.strip("'\"")
            for item in obj:
                if isinstance(item, dict) and str(item.get(k)) == v:
                    return item
        return None

    def _find_in_list(self, lst: list, pred: str) -> Optional[dict]:
        """按谓词从列表中查找元素。"""
        if "=" in pred:
            k, _, v = pred.partition("=")
            v = v.strip("'\"")
            for item in lst:
                if isinstance(item, dict) and str(item.get(k)) == v:
                    return item
        return None

    def _scale_adjustments(
        self, adjustments: list, scale: float
    ) -> list:
        """按版本缩放调整幅度。

        以 v2 的 30% 为基准（scale=0.3 → 1.0 倍），其他版本按比例缩放。

        Args:
            adjustments: 原始调整列表
            scale: 当前版本幅度（0~0.3）

        Returns:
            缩放后的调整列表
        """
        scaled: List[Dict[str, Any]] = []
        ratio = scale / 0.3  # 以 v2 的 30% 为基准
        for adj in adjustments:
            new_adj = dict(adj)
            delta = adj.get("delta")
            if isinstance(delta, (int, float)):
                new_delta = delta * ratio
                cur = adj.get("current_value")
                if isinstance(cur, (int, float)):
                    new_adj["suggested_value"] = cur + new_delta
                new_adj["delta"] = new_delta
                new_adj["scale_factor"] = scale
            # 非数值调整（如缓动类型）不缩放
            scaled.append(new_adj)
        return scaled

    # ================================================================
    #  7. VISION 语义对比
    # ================================================================

    async def vision_compare(
        self, reference: str, generated: str
    ) -> dict:
        """用 VISION 模型做语义级对比。

        抽取关键帧（首/中/尾），让 VISION 模型判断"两个视频效果是否相似"。
        成本较高，建议仅在常规对比无法收敛时调用。

        Args:
            reference: 参考视频路径
            generated: 生成视频路径

        Returns:
            {
                "semantic_similarity": float,
                "differences": [...],
                "suggestions": [...],
            }
        """
        if not self._vision_enabled:
            return {
                "semantic_similarity": 0.0,
                "differences": [],
                "suggestions": [],
                "error": "vision_compare 未启用（LLM 网关或 cv2 不可用）",
            }

        # 抽取关键帧（首、中、尾）
        ref_frames = await self._extract_key_frames(reference, count=3)
        gen_frames = await self._extract_key_frames(generated, count=3)

        if not ref_frames or not gen_frames:
            return {
                "semantic_similarity": 0.0,
                "differences": [],
                "suggestions": [],
                "error": "关键帧抽取失败",
            }

        ref_b64 = [self._image_to_base64(p) for p in ref_frames]
        gen_b64 = [self._image_to_base64(p) for p in gen_frames]
        images = ref_b64 + gen_b64

        prompt = (
            "请对比以下两组视频关键帧的视觉效果相似度。\n"
            f"前 {len(ref_b64)} 张为参考视频关键帧（按时间顺序），"
            f"后 {len(gen_b64)} 张为生成视频关键帧。\n\n"
            "请输出严格的 JSON 格式：\n"
            "{\n"
            '  "semantic_similarity": 0.0-1.0,\n'
            '  "differences": ["差异点1", "差异点2"],\n'
            '  "suggestions": ["改进建议1", "改进建议2"]\n'
            "}\n"
            "对比维度：色彩调性、画面构图、视觉效果强度、运动节奏。"
        )

        try:
            # 走 LLM 网关：VISION 任务类型自动路由到视觉模型
            if _LLM_TASK_TYPE is not None:
                response = await self.llm_gateway.chat_with_routing(
                    message=prompt,
                    task_type=_LLM_TASK_TYPE.SCENE_DESCRIPTION,
                    system_prompt="你是视频效果对比专家，请输出严格的 JSON。",
                    temperature=0.2,
                    images=images,
                )
            else:
                response = await self.llm_gateway.chat(
                    message=prompt,
                    system_prompt="你是视频效果对比专家，请输出严格的 JSON。",
                    temperature=0.2,
                    images=images,
                )

            if not getattr(response, "success", False):
                return {
                    "semantic_similarity": 0.0,
                    "differences": [],
                    "suggestions": [],
                    "error": f"LLM 调用失败: {getattr(response, 'error', 'unknown')}",
                }

            content = (response.content or "").strip()
            # 去除 markdown 代码块
            if content.startswith("```"):
                lines = content.split("\n")
                if len(lines) > 2:
                    content = "\n".join(lines[1:-1])
                else:
                    content = "\n".join(lines[1:])

            try:
                data = json.loads(content)
                return {
                    "semantic_similarity": float(data.get("semantic_similarity", 0.0)),
                    "differences": data.get("differences", []),
                    "suggestions": data.get("suggestions", []),
                }
            except json.JSONDecodeError:
                return {
                    "semantic_similarity": 0.0,
                    "differences": [],
                    "suggestions": [],
                    "error": f"LLM 响应非 JSON: {content[:200]}",
                    "raw_response": content,
                }
        except Exception as exc:
            logger.exception("VISION 对比失败")
            return {
                "semantic_similarity": 0.0,
                "differences": [],
                "suggestions": [],
                "error": str(exc),
            }

    async def _extract_key_frames(
        self, video_path: str, count: int = 3
    ) -> List[Path]:
        """抽取关键帧（首、中、尾均匀采样）。

        Args:
            video_path: 视频路径
            count: 采样帧数

        Returns:
            关键帧文件路径列表
        """
        if not _HAS_CV2:
            return []

        frames_dir = self.output_dir / f"_keyframes_{Path(video_path).stem}_{count}"
        frames_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return []

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            cap.release()
            return []

        # 均匀采样 count 帧
        positions = [int(total * (i + 1) / (count + 1)) for i in range(count)]
        paths: List[Path] = []
        for i, pos in enumerate(positions):
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ret, frame = cap.read()
            if not ret:
                continue
            out_path = frames_dir / f"key_{i:02d}.png"
            cv2.imwrite(str(out_path), frame)
            paths.append(out_path)

        cap.release()
        return paths

    def _image_to_base64(self, image_path: Path) -> str:
        """图片转 base64 编码。

        Args:
            image_path: 图片路径

        Returns:
            base64 字符串
        """
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    # ================================================================
    #  8. 优化报告
    # ================================================================

    def generate_optimization_report(self, iterations: list) -> str:
        """生成 Markdown 格式的优化报告。

        包含：
            - 迭代概览表
            - 每轮详情（相似度、对比维度、调整项）
            - 最终结论

        Args:
            iterations: optimize() 返回的 iterations 列表

        Returns:
            Markdown 字符串
        """
        if not iterations:
            return "# VRS 迭代优化报告\n\n无迭代记录。"

        lines: List[str] = []
        lines.append("# VRS 迭代优化报告")
        lines.append("")
        lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"总迭代轮数：{len(iterations)}")
        lines.append("")

        # 概览表
        lines.append("## 迭代概览")
        lines.append("")
        lines.append(
            "| 版本 | 相似度 | color | struct | motion | bright | 调整数 | 耗时(s) |"
        )
        lines.append(
            "|------|--------|-------|--------|--------|--------|--------|---------|"
        )
        for it in iterations:
            comp = it.get("comparison") or {}
            sim = it.get("similarity")
            sim_str = f"{sim:.4f}" if isinstance(sim, (int, float)) else "N/A"
            lines.append(
                f"| v{it.get('version', '?')} "
                f"| {sim_str} "
                f"| {comp.get('color_sim', 0):.3f} "
                f"| {comp.get('structure_sim', 0):.3f} "
                f"| {comp.get('motion_sim', 0):.3f} "
                f"| {comp.get('brightness_sim', 0):.3f} "
                f"| {len(it.get('adjustments', []))} "
                f"| {it.get('elapsed_sec', 0):.1f} |"
            )
        lines.append("")

        # 每轮详情
        lines.append("## 各轮详情")
        lines.append("")
        for it in iterations:
            lines.append(f"### v{it.get('version')}")
            lines.append("")
            comp = it.get("comparison") or {}
            sim = it.get("similarity")
            sim_str = f"{sim:.4f}" if isinstance(sim, (int, float)) else "N/A"
            lines.append(f"- 渲染输出：`{it.get('rendered_path', 'N/A')}`")
            lines.append(f"- 综合相似度：**{sim_str}**")
            lines.append(
                f"- color_sim={comp.get('color_sim', 0):.3f}, "
                f"struct_sim={comp.get('structure_sim', 0):.3f}, "
                f"motion_sim={comp.get('motion_sim', 0):.3f}, "
                f"bright_sim={comp.get('brightness_sim', 0):.3f}"
            )
            lines.append(f"- 采样帧数：{comp.get('sample_count', 0)}")
            lines.append(f"- 耗时：{it.get('elapsed_sec', 0):.1f}s")
            if it.get("error"):
                lines.append(f"- 错误：`{it['error']}`")

            adjs = it.get("adjustments") or []
            if adjs:
                lines.append("")
                lines.append("**调整项：**")
                lines.append("")
                lines.append("| 参数路径 | 当前值 | 建议值 | 原因 |")
                lines.append("|---------|--------|--------|------|")
                for adj in adjs:
                    lines.append(
                        f"| `{adj.get('param_path', '')}` "
                        f"| {adj.get('current_value', '')} "
                        f"| {adj.get('suggested_value', '')} "
                        f"| {adj.get('reason', '')} |"
                    )
            lines.append("")

        # 最终结论
        last = iterations[-1]
        sim = last.get("similarity")
        sim_str = f"{sim:.4f}" if isinstance(sim, (int, float)) else "N/A"
        lines.append("## 结论")
        lines.append("")
        lines.append(f"- 最终相似度：**{sim_str}**")
        lines.append(
            f"- 收敛状态：{'已收敛' if last.get('converged') else '未收敛'}"
        )
        lines.append("")

        return "\n".join(lines)


# =====================================================================
#  CLI 测试入口
# =====================================================================

def _configure_logger() -> None:
    """配置 loguru 输出。"""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<level>{level: <8}</level> | {message}")


async def _run_test() -> None:
    """--test：跑 1 轮迭代测试。"""
    project_root = Path(__file__).parent
    ref_video = project_root / "output" / "test_sample.mp4"
    analysis_file = project_root / "output" / "saitama_analysis.json"

    if not ref_video.is_file():
        print(f"[ERROR] 参考视频不存在: {ref_video}")
        return
    if not analysis_file.is_file():
        print(f"[ERROR] 分析结果不存在: {analysis_file}")
        return

    with open(analysis_file, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    optimizer = IterationOptimizer(
        output_dir=project_root / "output" / "vrs_iteration_test"
    )
    result = await optimizer.optimize(
        reference_video=str(ref_video),
        initial_analysis=analysis,
        max_iterations=1,
        target_similarity=0.85,
    )

    print("\n========== 迭代结果 ==========")
    print(f"收敛: {result['converged']}")
    print(f"停止原因: {result['stop_reason']}")
    print(f"最终相似度: {result['final_similarity']:.4f}")
    for it in result["iterations"]:
        sim = it.get("similarity")
        sim_str = f"{sim:.4f}" if isinstance(sim, (int, float)) else "N/A"
        print(
            f"  v{it['version']}: sim={sim_str}, "
            f"rendered={it.get('rendered_path')}"
        )

    # 生成报告
    report = optimizer.generate_optimization_report(result["iterations"])
    report_path = project_root / "output" / "vrs_iteration_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已保存: {report_path}")


async def _run_compare(v1: str, v2: str) -> None:
    """--compare video1 video2：对比两个视频的相似度。"""
    optimizer = IterationOptimizer()
    result = await optimizer.compare_videos(v1, v2)
    print("\n========== 对比结果 ==========")
    print(f"overall_similarity: {result.get('overall_similarity', 0):.4f}")
    print(f"color_sim:          {result.get('color_sim', 0):.4f}")
    print(f"structure_sim:      {result.get('structure_sim', 0):.4f}")
    print(f"motion_sim:         {result.get('motion_sim', 0):.4f}")
    print(f"brightness_sim:     {result.get('brightness_sim', 0):.4f}")
    print(f"sample_count:       {result.get('sample_count', 0)}")
    if result.get("error"):
        print(f"error:              {result['error']}")
    if result.get("frame_details"):
        print("\n帧详情（前 5 帧）：")
        for fd in result["frame_details"][:5]:
            print(
                f"  #{fd['index']} t={fd['timestamp']:.2f}s "
                f"color={fd['color_sim']:.3f} struct={fd['structure_sim']:.3f} "
                f"motion={fd['motion_sim']:.3f} bright={fd['brightness_sim']:.3f}"
            )


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="VRS 迭代优化器：生成→对比→调整闭环"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="用 output/test_sample.mp4 + output/saitama_analysis.json 跑 1 轮迭代测试",
    )
    parser.add_argument(
        "--compare", nargs=2, metavar=("VIDEO1", "VIDEO2"),
        help="对比两个视频的相似度",
    )
    args = parser.parse_args()

    _configure_logger()

    if args.test:
        asyncio.run(_run_test())
    elif args.compare:
        asyncio.run(_run_compare(args.compare[0], args.compare[1]))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

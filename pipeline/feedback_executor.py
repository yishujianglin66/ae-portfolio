"""
反馈自动执行器 — 将质检建议转化为实际视频处理
==================================================

将 QualityAgent 的评分和 FeedbackLoop 的调整建议，
自动映射为 FFmpeg 滤镜参数并执行，实现质量闭环。

核心类:
- FeedbackExecutor: 反馈→滤镜映射+执行
- AdjustmentMapper: 调整建议→FFmpeg参数映射

Author: AE-Knowledge-Vault Team
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from pipeline.ffmpeg_edit_engine import (
        ColorGradeParams,
        FFmpegEditEngine,
        FFmpegFilterBuilder,
        SharpenParams,
        SpeedParams,
        VignetteParams,
    )
    _FFMPEG_ENGINE_AVAILABLE = True
except Exception:  # ImportError or any init error
    _FFMPEG_ENGINE_AVAILABLE = False
    FFmpegEditEngine = None  # type: ignore
    FFmpegFilterBuilder = None  # type: ignore
    ColorGradeParams = None  # type: ignore
    SharpenParams = None  # type: ignore
    VignetteParams = None  # type: ignore
    SpeedParams = None  # type: ignore

logger = logging.getLogger(__name__)

# ── Score defaults & thresholds ──────────────────────────
_DEFAULT_SCORE = 50
_DEFAULT_VQ_SCORE = 70
_DEFAULT_CC_SCORE = 70
_VQ_SCORE_THRESHOLD = 60
_CC_SCORE_THRESHOLD = 60
_LOW_SCORE_THRESHOLD = 40

# ── Sharpness detection ──────────────────────────────────
_DEFAULT_SHARPNESS = 30
_SHARPNESS_EXTREME_THRESHOLD = 10
_SHARPNESS_LOW_THRESHOLD = 20

# ── Brightness correction ────────────────────────────────
_DEFAULT_AVG_BRIGHTNESS = 0.5
_BRIGHTNESS_EXTREME_LOW = 0.15
_BRIGHTNESS_EXTREME_HIGH = 0.85
_BRIGHTNESS_MODERATE_LOW = 0.3
_BRIGHTNESS_MODERATE_HIGH = 0.7
_BRIGHTNESS_BOOST_EXTREME = 0.25
_BRIGHTNESS_BOOST_MODERATE = 0.15
_BRIGHTNESS_REDUCE_MODERATE = -0.1
_BRIGHTNESS_REDUCE_EXTREME = -0.2

# ── Filter presets ───────────────────────────────────────
_SHARPEN_EXTREME = {"amount": 3.0, "radius": 2.0}
_SHARPEN_STRONG = {"amount": 2.0, "radius": 1.0}
_SHARPEN_MODERATE = {"amount": 1.2, "radius": 0.8}
_SHARPEN_UPSCALE = {"amount": 1.8, "radius": 1.2}

_COLOR_GRADE_QUALITY = {"contrast": 1.15, "saturation": 1.05, "gamma": 1.05}
_COLOR_GRADE_CORRECTION = {"contrast": 1.1, "saturation": 1.08, "gamma": 1.05}
_COLOR_GRADE_CINEMATIC = {"contrast": 1.12, "saturation": 1.1, "gamma": 1.03}
_COLOR_GRADE_FULL_ENHANCE = {"brightness": 0.05, "contrast": 1.2, "saturation": 1.15, "gamma": 1.08}

_VIGNETTE_DEFAULT = {"angle": 2.5, "x0": 0.5, "y0": 0.5}


@dataclass
class AdjustmentAction:
    """单个调整动作"""
    type: str           # sharpen / color_grade / vignette / speed / text / transition
    params: dict        # 参数字典
    priority: int = 0   # 优先级 (越高越先执行)
    reason: str = ""    # 触发原因


class AdjustmentMapper:
    """
    将质检反馈映射为具体调整动作
    
    映射规则:
    - visual_quality < 60 → 锐化 + 对比度提升
    - color_consistency < 60 → 色彩校正
    - brightness 异常 → 亮度调整
    - 建议超分 → 锐化增强
    - 建议调色 → 自动调色
    """

    @staticmethod
    def map_feedback(quality_report: dict) -> list[AdjustmentAction]:
        """
        将质检报告映射为调整动作列表
        
        Args:
            quality_report: QualityAgent 产出的评分报告
                {
                    "score": 53.3,
                    "checks": {
                        "visual_quality": {"score": 45, "sharpness": 20.5, ...},
                        "color_consistency": {"score": 55, "avg_brightness": 0.3, ...},
                        ...
                    },
                    "suggestions": ["建议使用超分辨率", ...]
                }
        """
        actions = []
        score = quality_report.get("score", _DEFAULT_SCORE)
        checks = quality_report.get("checks", {})
        suggestions = quality_report.get("suggestions", [])

        # === 画质偏低 → 锐化 + 对比度 ===
        vq = checks.get("visual_quality", {})
        vq_score = vq.get("score", _DEFAULT_VQ_SCORE)
        if vq_score < _VQ_SCORE_THRESHOLD:
            sharpness = vq.get("sharpness", _DEFAULT_SHARPNESS)
            # 越模糊，锐化越强
            if sharpness < _SHARPNESS_EXTREME_THRESHOLD:
                # 极模糊: 用更大半径和接近上限的 amount, msize=5 能恢复更多细节
                actions.append(AdjustmentAction(
                    type="sharpen",
                    params=_SHARPEN_EXTREME,
                    priority=10,
                    reason=f"画质极低(锐度{sharpness:.1f})，应用最大强度锐化"
                ))
            elif sharpness < _SHARPNESS_LOW_THRESHOLD:
                actions.append(AdjustmentAction(
                    type="sharpen",
                    params=_SHARPEN_STRONG,
                    priority=10,
                    reason=f"画质偏低(锐度{sharpness:.0f})，应用强锐化"
                ))
            else:
                actions.append(AdjustmentAction(
                    type="sharpen",
                    params=_SHARPEN_MODERATE,
                    priority=10,
                    reason=f"画质偏低(锐度{sharpness:.0f})，应用适度锐化"
                ))
            # 同时提升对比度
            actions.append(AdjustmentAction(
                type="color_grade",
                params=_COLOR_GRADE_QUALITY,
                priority=8,
                reason="画质偏低，提升对比度和饱和度"
            ))

        # === 色彩不一致 → 色彩校正 ===
        cc = checks.get("color_consistency", {})
        cc_score = cc.get("score", _DEFAULT_CC_SCORE)
        avg_brightness = cc.get("avg_brightness", _DEFAULT_AVG_BRIGHTNESS)
        # 即使 cc_score 合格, 极端亮度也需要单独修正 (避免画面过暗/过亮)
        extreme_brightness = avg_brightness < _BRIGHTNESS_EXTREME_LOW or avg_brightness > _BRIGHTNESS_EXTREME_HIGH
        if cc_score < _CC_SCORE_THRESHOLD or extreme_brightness:
            # 根据平均亮度调整
            brightness_adj = 0.0
            if avg_brightness < _BRIGHTNESS_EXTREME_LOW:
                brightness_adj = _BRIGHTNESS_BOOST_EXTREME  # 极暗, 强提亮
            elif avg_brightness < _BRIGHTNESS_MODERATE_LOW:
                brightness_adj = _BRIGHTNESS_BOOST_MODERATE  # 太暗，提亮
            elif avg_brightness > _BRIGHTNESS_EXTREME_HIGH:
                brightness_adj = _BRIGHTNESS_REDUCE_EXTREME  # 极亮, 强压暗
            elif avg_brightness > _BRIGHTNESS_MODERATE_HIGH:
                brightness_adj = _BRIGHTNESS_REDUCE_MODERATE  # 太亮，压暗

            actions.append(AdjustmentAction(
                type="color_grade",
                params={
                    "brightness": brightness_adj,
                    **_COLOR_GRADE_CORRECTION,
                },
                priority=9,
                reason=f"色彩不一致(分数{cc_score}, 亮度{avg_brightness:.2f})，自动校正"
            ))

        # === 建议文本解析 ===
        suggestion_text = " ".join(suggestions).lower()
        
        if "超分" in suggestion_text or "超分辨率" in suggestion_text or "upscale" in suggestion_text:
            # 超分建议 → 强锐化 (FFmpeg无法真正超分，但锐化是最佳近似)
            if not any(a.type == "sharpen" for a in actions):
                actions.append(AdjustmentAction(
                    type="sharpen",
                    params=_SHARPEN_UPSCALE,
                    priority=10,
                    reason="质检建议超分，应用强锐化近似"
                ))

        if "调色" in suggestion_text or "color" in suggestion_text:
            if not any(a.type == "color_grade" for a in actions):
                actions.append(AdjustmentAction(
                    type="color_grade",
                    params=_COLOR_GRADE_CINEMATIC,
                    priority=8,
                    reason="质检建议调色，自动应用电影感调色"
                ))

        if "暗角" in suggestion_text or "vignette" in suggestion_text:
            actions.append(AdjustmentAction(
                type="vignette",
                params=_VIGNETTE_DEFAULT,
                priority=5,
                reason="质检建议添加暗角"
            ))

        # === 综合评分过低 → 全面增强 ===
        if score < _LOW_SCORE_THRESHOLD:
            actions.append(AdjustmentAction(
                type="color_grade",
                params=_COLOR_GRADE_FULL_ENHANCE,
                priority=10,
                reason=f"综合评分极低({score})，全面增强"
            ))
            actions.append(AdjustmentAction(
                type="sharpen",
                params=_SHARPEN_STRONG,
                priority=10,
                reason="综合评分极低，强锐化"
            ))

        # 按优先级排序
        actions.sort(key=lambda a: -a.priority)
        return actions

    @staticmethod
    def actions_to_filter_builder(actions: list[AdjustmentAction]) -> FFmpegFilterBuilder:
        """将调整动作列表转换为 FFmpeg 滤镜链

        合并策略:
        - color_grade: 多个动作的参数**累加合并**(brightness/gamma 相加, contrast/saturation 相乘),
          避免后一个动作覆盖前一个动作的 brightness 提亮等关键参数
        - sharpen / vignette: 取最后一个 (同类通常只有一组语义)
        """
        fb = FFmpegFilterBuilder()

        # 合并 color_grade 参数
        merged_brightness = 0.0
        merged_contrast = 1.0
        merged_saturation = 1.0
        merged_gamma = 1.0
        has_color = False
        sharpen_params = None
        vignette_params = None

        for action in actions:
            if action.type == "color_grade":
                has_color = True
                p = action.params
                # brightness / gamma 是偏移量, 相加
                merged_brightness += float(p.get("brightness", 0.0))
                merged_gamma *= float(p.get("gamma", 1.0))
                # contrast / saturation 是倍率, 相乘
                merged_contrast *= float(p.get("contrast", 1.0))
                merged_saturation *= float(p.get("saturation", 1.0))
            elif action.type == "sharpen":
                sharpen_params = action.params
            elif action.type == "vignette":
                vignette_params = action.params

        # 限幅, 防止过度合成
        merged_brightness = max(-1.0, min(1.0, merged_brightness))
        merged_contrast = max(0.5, min(2.0, merged_contrast))
        merged_saturation = max(0.0, min(2.0, merged_saturation))
        merged_gamma = max(0.5, min(2.0, merged_gamma))

        # 按顺序应用: 调色 → 锐化 → 暗角
        if has_color:
            fb.color_grade(ColorGradeParams(
                brightness=merged_brightness,
                contrast=merged_contrast,
                saturation=merged_saturation,
                gamma=merged_gamma
            ))
        if sharpen_params:
            fb.sharpen(SharpenParams(
                amount=sharpen_params.get("amount", 1.0),
                radius=sharpen_params.get("radius", 0.8)
            ))
        if vignette_params:
            fb.vignette(VignetteParams(
                angle=vignette_params.get("angle", 3.0),
                x0=vignette_params.get("x0", 0.5),
                y0=vignette_params.get("y0", 0.5)
            ))

        return fb


class FeedbackExecutor:
    """
    反馈自动执行器 — 质检→调整→重新渲染 闭环
    
    用法:
        executor = FeedbackExecutor()
        result = executor.execute(
            input_video="output/e2e_pipeline_run/e2e_demo_output.mp4",
            quality_report={"score": 53.3, "checks": {...}, "suggestions": [...]},
            output="output/e2e_pipeline_run/e2e_demo_output_enhanced.mp4"
        )
    
    M2.4增强: 集成贝叶斯优化器，自动推荐最优参数并记录调整轨迹
    """

    def __init__(self, ffmpeg_bin: str = "", use_bayesian_optimizer: bool = True):
        if not _FFMPEG_ENGINE_AVAILABLE:
            logger.warning("[FeedbackExecutor] ffmpeg_edit_engine unavailable, executor disabled")
            self.engine = None
        else:
            self.engine = FFmpegEditEngine(ffmpeg_bin)
        self._optimizer = None
        self._adjustment_log: list[dict] = []  # M2.6: 参数调整轨迹记录
        
        if use_bayesian_optimizer:
            try:
                from core.bayesian_optimizer import get_optimizer
                self._optimizer = get_optimizer()
            except Exception as e:
                logger.debug(f"[FeedbackExecutor] Bayesian optimizer unavailable: {e}")

    def execute(self, input_video: str, quality_report: dict,
                output: str = "") -> dict:
        """
        执行反馈调整
        
        Args:
            input_video: 输入视频
            quality_report: 质检报告
            output: 输出路径(默认为 input_enhanced.mp4)
        
        Returns:
            {
                "success": bool,
                "output": str,
                "actions": [...],
                "filter_chain": str,
                "before_score": float,
                "reasoning": str,
                "optimizer_used": bool  # M2.4
            }
        """
        if not os.path.isfile(input_video):
            return {"success": False, "error": f"输入文件不存在: {input_video}"}

        if self.engine is None:
            return {"success": False, "error": "FFmpegEditEngine不可用，无法执行调整"}

        if not output:
            base, ext = os.path.splitext(input_video)
            output = f"{base}_enhanced{ext}"

        before_score = quality_report.get("score", 0)

        # 1. 映射反馈为调整动作
        actions = AdjustmentMapper.map_feedback(quality_report)
        if not actions:
            return {
                "success": True,
                "output": input_video,
                "actions": [],
                "filter_chain": "",
                "before_score": before_score,
                "reasoning": "质检评分良好，无需调整",
                "optimizer_used": False
            }

        # M2.4: 贝叶斯优化器参数推荐
        optimizer_used = False
        if self._optimizer is not None:
            actions = self._optimize_actions(actions, quality_report)
            optimizer_used = True

        # 2. 构建滤镜链
        fb = AdjustmentMapper.actions_to_filter_builder(actions)
        filter_chain = fb.build()

        # 3. 执行滤镜
        total_dur = self.engine._get_duration(input_video)
        success = self.engine.apply_filters(input_video, output, fb, total_dur)

        reasoning_parts = [f"原始评分: {before_score}"]
        for a in actions:
            reasoning_parts.append(f"  [{a.type}] {a.reason}")

        # M2.4/M2.6: 记录调整轨迹
        self._record_adjustment(actions, before_score, success, quality_report)

        return {
            "success": success,
            "output": output if success else input_video,
            "actions": [{"type": a.type, "params": a.params, "reason": a.reason} for a in actions],
            "filter_chain": filter_chain,
            "before_score": before_score,
            "reasoning": "\n".join(reasoning_parts),
            "optimizer_used": optimizer_used
        }

    def execute_multi_pass(self, input_video: str, quality_report_fn,
                           max_passes: int = 3, threshold: float = 70.0) -> dict:
        """
        多轮迭代优化 — 反复质检+调整直到达标
        
        Args:
            input_video: 输入视频
            quality_report_fn: 质检函数 (filepath) -> quality_report dict
            max_passes: 最大迭代次数
            threshold: 目标分数
        """

        # 纵深防御：函数级硬上限。即使调用方未钳位也不会爆炸。
        MAX_PASSES_HARD_CAP = 10
        try:
            max_passes_int = int(max_passes)
        except (TypeError, ValueError):
            max_passes_int = 3
        if max_passes_int < 1:
            max_passes_int = 1
        if max_passes_int > MAX_PASSES_HARD_CAP:
            max_passes_int = MAX_PASSES_HARD_CAP
        current = input_video
        history = []

        for pass_idx in range(max_passes_int):
            # 质检
            report = quality_report_fn(current)
            if not isinstance(report, dict):
                report = {"score": 0, "error": "invalid_report"}
            score = report.get("score", 0)
            if not isinstance(score, (int, float)):
                try: score = float(score)
                except: score = 0
            history.append({"pass": pass_idx + 1, "score": score, "file": current})

            if score >= threshold:
                return {
                    "success": True,
                    "final_file": current,
                    "final_score": score,
                    "passes": pass_idx + 1,
                    "history": history,
                    "reasoning": f"第{pass_idx+1}轮达到目标分数{score:.1f}>={threshold}"
                }

            # 调整
            base, ext = os.path.splitext(current)
            output = f"{base}_pass{pass_idx+2}{ext}"
            result = self.execute(current, report, output)
            if not isinstance(result, dict):
                result = {"success": False, "output": current, "error": "execute_return_invalid"}
            if not result.get("success", False):
                return {
                    "success": False,
                    "final_file": current,
                    "final_score": score,
                    "passes": pass_idx + 1,
                    "history": history,
                    "reasoning": f"第{pass_idx+1}轮调整失败: {result.get('error','')[:200]}"
                }
            current = result.get("output") or current

        return {
            "success": score >= threshold,
            "final_file": current,
            "final_score": score,
            "passes": max_passes,
            "history": history,
            "reasoning": f"达到最大迭代次数{max_passes}，最终分数{score:.1f}",
            "adjustment_log": self._adjustment_log[-max_passes:]  # M2.6
        }

    # ----------------------------------------------------------------
    #  M2.4/M2.6: 贝叶斯优化器集成与调整轨迹记录
    # ----------------------------------------------------------------

    def _optimize_actions(
        self, actions: list[AdjustmentAction], quality_report: dict
    ) -> list[AdjustmentAction]:
        """使用贝叶斯优化器推荐最优参数替换默认参数"""
        if self._optimizer is None:
            return actions

        # 映射调整类型到效果名
        type_to_effect = {
            "sharpen": "Sharpen",
            "color_grade": "ColorBalance",
            "vignette": "Vignette",
        }

        optimized = []
        for action in actions:
            effect_name = type_to_effect.get(action.type)
            if not effect_name:
                optimized.append(action)
                continue

            try:
                suggestions = self._optimizer.recommend(
                    effect_name=effect_name,
                    style_context={"quality_score": quality_report.get("score", 50)},
                    constraints={},
                    n_suggestions=1
                )
                if suggestions:
                    # 用优化器推荐的参数替换默认参数
                    rec_params = suggestions[0].parameters
                    new_params = dict(action.params)
                    # 仅替换匹配的数值参数
                    for k, v in rec_params.items():
                        if k in new_params and isinstance(v, (int, float)):
                            new_params[k] = v
                    optimized.append(AdjustmentAction(
                        type=action.type,
                        params=new_params,
                        priority=action.priority,
                        reason=f"[BOpt] {action.reason}"
                    ))
                else:
                    optimized.append(action)
            except Exception as e:
                logger.debug(f"[FeedbackExecutor] Optimizer recommend failed for {action.type}: {e}")
                optimized.append(action)

        return optimized

    def _record_adjustment(
        self, actions: list[AdjustmentAction], before_score: float,
        success: bool, quality_report: dict
    ) -> None:
        """M2.6: 记录参数调整轨迹，供后续学习"""
        import time
        record = {
            "timestamp": time.time(),
            "before_score": before_score,
            "success": success,
            "actions": [
                {"type": a.type, "params": a.params, "reason": a.reason}
                for a in actions
            ],
            "quality_checks": quality_report.get("checks", {}),
        }
        self._adjustment_log.append(record)

        # 如果执行成功且有优化器，记录正向观测
        if success and self._optimizer is not None:
            # quality 为估计值 (before_score + 10)，非真实质量测量，可能污染学习闭环
            logger.warning(
                "[FeedbackExecutor] optimizer.observe 使用估计 quality=%.1f "
                "(before_score=%.1f + 10)，非真实测量值",
                min(100.0, before_score + 10), before_score,
            )
            type_to_effect = {
                "sharpen": "Sharpen", "color_grade": "ColorBalance",
                "vignette": "Vignette",
            }
            for action in actions:
                effect_name = type_to_effect.get(action.type)
                if effect_name:
                    try:
                        self._optimizer.observe(
                            effect_name=effect_name,
                            params=action.params,
                            quality=min(100.0, before_score + 10),  # 估计提升
                            render_time=0,
                            file_size=0,
                            success=True
                        )
                    except Exception:
                        pass

    def get_adjustment_log(self) -> list[dict]:
        """M2.6: 获取参数调整轨迹日志"""
        return list(self._adjustment_log)

"""
pipeline/feedback_loop.py — 管线反馈闭环
==========================================

将 QualityAgent 质检结果转化为可学习的知识，写入知识库，
供未来同类项目参考。

核心流程:
  1. 接收 QualityAgent 评分 + 检查详情
  2. 分析失败原因 (画质/音画同步/色彩/节奏)
  3. 生成改进建议
  4. 写入 KB 反馈库 (data/pipeline_feedback/)
  5. 生成下次迭代的参数调整建议

用法:
    from pipeline.feedback_loop import FeedbackLoop

    loop = FeedbackLoop()
    adjustment = loop.process(
        run_id="run_20260720_123456",
        quality_result={"score": 45, "checks": {...}},
        pipeline_context={"style": "cinematic", "effects": [...]},
    )
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class QualityIssue:
    """质量问题"""
    category: str  # visual / audio_sync / color / rhythm / file
    severity: str  # critical / warning / info
    description: str
    metric_name: str = ""
    metric_value: float = 0.0
    metric_threshold: float = 0.0
    recommendation: str = ""


@dataclass
class AdjustmentAdvice:
    """迭代调整建议"""
    target_stage: str  # 需要重跑的阶段: perceive/analyze/plan/execute/render
    parameter: str     # 需要调整的参数
    current_value: Any = None
    suggested_value: Any = None
    reason: str = ""
    confidence: float = 0.5


@dataclass
class FeedbackResult:
    """反馈处理结果"""
    run_id: str
    passed: bool
    overall_score: float
    issues: list[QualityIssue] = field(default_factory=list)
    adjustments: list[AdjustmentAdvice] = field(default_factory=list)
    kb_entry: dict[str, Any] = field(default_factory=dict)
    should_retry: bool = False
    retry_stages: list[str] = field(default_factory=list)


# ============================================================================
#  质量阈值表
# ============================================================================

QUALITY_THRESHOLDS = {
    "visual_quality": {
        "min_score": 60.0,       # Laplacian 方差 (越高越清晰)
        "max_noise": 30.0,       # 噪声水平
        "min_resolution": 1280,  # 最小宽度
    },
    "audio_sync": {
        "max_drift_ms": 100,     # 最大音画偏移
    },
    "color_consistency": {
        "max_hsv_delta": 25.0,   # HSV 最大偏差
    },
    "rhythm": {
        "max_beat_drift": 0.15,  # 节拍偏移比例
    },
}


# ============================================================================
#  反馈闭环引擎
# ============================================================================

class FeedbackLoop:
    """管线反馈闭环引擎"""

    def __init__(
        self, feedback_dir: str | Path | None = None
    ):
        # 默认写入二线实战反馈隔离目录 settings.feedback_dir，
        # 显式传入时尊重调用方指定路径
        self.feedback_dir = Path(feedback_dir) if feedback_dir is not None else Path(settings.feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        run_id: str,
        quality_result: dict[str, Any],
        pipeline_context: dict[str, Any] | None = None,
    ) -> FeedbackResult:
        """处理质检结果，生成反馈和调整建议。

        Args:
            run_id: 管线运行 ID
            quality_result: QualityAgent 返回的结果
            pipeline_context: 管线上下文 (style, effects, etc.)

        Returns:
            FeedbackResult: 包含问题列表和调整建议
        """
        score = quality_result.get("overall_score", quality_result.get("score", 0))
        checks = quality_result.get("checks", {})
        passed = quality_result.get("passed", score >= 60)

        # 1. 分析质量问题
        issues = self._analyze_issues(checks, score)

        # 2. 生成调整建议
        adjustments = self._generate_adjustments(issues, pipeline_context or {})

        # 3. 决定是否重试
        should_retry = not passed and len(adjustments) > 0
        retry_stages = list(set(adj.target_stage for adj in adjustments))

        # 4. 构建 KB 条目
        kb_entry = self._build_kb_entry(
            run_id, score, passed, issues, adjustments, pipeline_context
        )

        # 5. 写入反馈文件
        self._write_feedback(run_id, kb_entry)

        return FeedbackResult(
            run_id=run_id,
            passed=passed,
            overall_score=score,
            issues=issues,
            adjustments=adjustments,
            kb_entry=kb_entry,
            should_retry=should_retry,
            retry_stages=retry_stages,
        )

    def get_historical_feedback(self, style: str = "", limit: int = 5) -> list[dict]:
        """获取历史反馈记录。

        Args:
            style: 风格过滤条件
            limit: 最大返回数

        Returns:
            历史反馈列表
        """
        results = []
        for f in self.feedback_dir.glob("feedback_*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    entry = json.load(fh)
                if style and entry.get("style") != style:
                    continue
                results.append(entry)
            except Exception:
                continue

        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return results[:limit]

    def get_success_patterns(self, style: str = "") -> list[dict]:
        """获取成功模式 (score >= 80 的项目)。"""
        all_feedback = self.get_historical_feedback(style, limit=50)
        return [f for f in all_feedback if f.get("score", 0) >= 80]

    def get_failure_patterns(self, style: str = "") -> list[dict]:
        """获取失败模式 (score < 60 的项目)。"""
        all_feedback = self.get_historical_feedback(style, limit=50)
        return [f for f in all_feedback if f.get("score", 0) < 60]

    # ----------------------------------------------------------------
    #  内部方法
    # ----------------------------------------------------------------

    def _analyze_issues(self, checks: dict, score: float) -> list[QualityIssue]:
        """从质检结果中分析问题"""
        issues = []

        # 画质问题
        visual = checks.get("visual_quality", checks.get("visual", {}))
        if isinstance(visual, dict):
            sharpness = visual.get("sharpness", visual.get("laplacian", 0))
            if sharpness < QUALITY_THRESHOLDS["visual_quality"]["min_score"]:
                issues.append(QualityIssue(
                    category="visual",
                    severity="critical" if sharpness < 30 else "warning",
                    description=f"画面清晰度不足 (sharpness={sharpness:.1f})",
                    metric_name="sharpness",
                    metric_value=sharpness,
                    metric_threshold=QUALITY_THRESHOLDS["visual_quality"]["min_score"],
                    recommendation="提高源素材分辨率或减少模糊效果强度",
                ))

        # 音画同步问题
        av_sync = checks.get("audio_sync", checks.get("av_sync", {}))
        if isinstance(av_sync, dict):
            drift = av_sync.get("drift_ms", av_sync.get("offset_ms", 0))
            if abs(drift) > QUALITY_THRESHOLDS["audio_sync"]["max_drift_ms"]:
                issues.append(QualityIssue(
                    category="audio_sync",
                    severity="critical",
                    description=f"音画偏移 {drift:.0f}ms 超出阈值",
                    metric_name="drift_ms",
                    metric_value=abs(drift),
                    metric_threshold=QUALITY_THRESHOLDS["audio_sync"]["max_drift_ms"],
                    recommendation="调整音频轨道偏移或重新对齐节拍点",
                ))

        # 色彩一致性问题
        color = checks.get("color_consistency", checks.get("color", {}))
        if isinstance(color, dict):
            delta = color.get("hsv_delta", color.get("delta_e", 0))
            if delta > QUALITY_THRESHOLDS["color_consistency"]["max_hsv_delta"]:
                issues.append(QualityIssue(
                    category="color",
                    severity="warning",
                    description=f"色彩一致性偏差 {delta:.1f}",
                    metric_name="hsv_delta",
                    metric_value=delta,
                    metric_threshold=QUALITY_THRESHOLDS["color_consistency"]["max_hsv_delta"],
                    recommendation="统一调色参数或使用 LUT 预设",
                ))

        # 节奏问题
        rhythm = checks.get("rhythm", checks.get("beat_sync", {}))
        if isinstance(rhythm, dict):
            drift = rhythm.get("beat_drift", rhythm.get("drift_ratio", 0))
            if drift > QUALITY_THRESHOLDS["rhythm"]["max_beat_drift"]:
                issues.append(QualityIssue(
                    category="rhythm",
                    severity="warning",
                    description=f"节拍偏移 {drift:.1%}",
                    metric_name="beat_drift",
                    metric_value=drift,
                    metric_threshold=QUALITY_THRESHOLDS["rhythm"]["max_beat_drift"],
                    recommendation="重新对齐剪辑点到节拍",
                ))

        # 文件问题
        file_check = checks.get("file_check", checks.get("file", {}))
        if isinstance(file_check, dict) and not file_check.get("valid", True):
            issues.append(QualityIssue(
                category="file",
                severity="critical",
                description=f"输出文件异常: {file_check.get('error', 'unknown')}",
                recommendation="检查编码参数和渲染设置",
            ))

        return issues

    def _generate_adjustments(
        self, issues: list[QualityIssue], context: dict
    ) -> list[AdjustmentAdvice]:
        """根据问题生成调整建议"""
        context = context or {}
        adjustments = []

        for issue in issues:
            if issue.category == "visual":
                adjustments.append(AdjustmentAdvice(
                    target_stage="execute",
                    parameter="effect_intensity",
                    current_value=context.get("effect_intensity", 1.0),
                    suggested_value=max(0.3, context.get("effect_intensity", 1.0) * 0.7),
                    reason=issue.description,
                    confidence=0.7,
                ))
            elif issue.category == "audio_sync":
                adjustments.append(AdjustmentAdvice(
                    target_stage="execute",
                    parameter="audio_offset_ms",
                    current_value=context.get("audio_offset_ms", 0),
                    suggested_value=0,  # 重置偏移
                    reason=issue.description,
                    confidence=0.9,
                ))
            elif issue.category == "color":
                adjustments.append(AdjustmentAdvice(
                    target_stage="execute",
                    parameter="color_grade_preset",
                    current_value=context.get("color_preset", ""),
                    suggested_value="neutral",
                    reason=issue.description,
                    confidence=0.6,
                ))
            elif issue.category == "rhythm":
                adjustments.append(AdjustmentAdvice(
                    target_stage="plan",
                    parameter="beat_alignment",
                    current_value=context.get("beat_alignment", False),
                    suggested_value=True,
                    reason=issue.description,
                    confidence=0.8,
                ))

        return adjustments

    def _build_kb_entry(
        self,
        run_id: str,
        score: float,
        passed: bool,
        issues: list[QualityIssue],
        adjustments: list[AdjustmentAdvice],
        context: dict,
    ) -> dict[str, Any]:
        """构建知识库条目"""
        context = context or {}
        return {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "score": score,
            "passed": passed,
            "style": context.get("style", context.get("vrs_style", {}).get("name", "")),
            "issues": [
                {"category": i.category, "severity": i.severity,
                 "description": i.description, "recommendation": i.recommendation}
                for i in issues
            ],
            "adjustments": [
                {"stage": a.target_stage, "param": a.parameter,
                 "from": str(a.current_value), "to": str(a.suggested_value),
                 "reason": a.reason}
                for a in adjustments
            ],
            "effects_used": context.get("effects", []),
            "transitions_used": context.get("transitions", []),
            "total_issues": len(issues),
            "critical_issues": sum(1 for i in issues if i.severity == "critical"),
        }

    def _write_feedback(self, run_id: str, entry: dict):
        """写入反馈文件"""
        filepath = self.feedback_dir / f"feedback_{run_id}.json"

        def _sanitize(obj):
            """处理 numpy 类型不可序列化问题"""
            import numpy as np
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2, default=_sanitize)
            logger.info(f"[FeedbackLoop] Written: {filepath}")
        except Exception as e:
            logger.warning(f"[FeedbackLoop] Write failed: {e}")


# ============================================================================
#  便捷函数
# ============================================================================

def process_quality_feedback(
    run_id: str,
    quality_result: dict,
    context: dict | None = None,
) -> FeedbackResult:
    """快捷函数: 处理质检反馈"""
    loop = FeedbackLoop()
    return loop.process(run_id, quality_result, context)


def get_past_feedback(style: str = "", limit: int = 5) -> list[dict]:
    """快捷函数: 获取历史反馈"""
    loop = FeedbackLoop()
    return loop.get_historical_feedback(style, limit)


def get_success_patterns(style: str = "") -> list[dict]:
    """快捷函数: 获取成功模式"""
    loop = FeedbackLoop()
    return loop.get_success_patterns(style)


# ============================================================================
#  P0: 错误模式记忆与自动修复 (Agentic 增强)
# ============================================================================

@dataclass
class ErrorPattern:
    """错误模式记录"""
    error_type: str
    error_msg: str
    error_keywords: list[str]
    context_keys: list[str]
    fix_applied: str
    fix_code: str = ""
    success: bool = False
    occurrence_count: int = 1
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())


class ErrorPatternMemory:
    """
    错误模式记忆库 - 存储错误特征→修复方案映射
    
    核心能力:
    1. 记录错误模式及其修复方案
    2. 基于错误特征匹配历史修复方案
    3. 统计修复成功率，优先推荐高成功率方案
    
    用法:
        memory = ErrorPatternMemory()
        
        # 记录错误
        memory.record_error(
            error=ValueError("Text Animator matchName not found"),
            context={"stage": "execute", "effect": "text_animator"},
            fix_applied="use_adbe_matchname",
            fix_code='animator.property("ADBE Text Animator")',
            success=True
        )
        
        # 查找修复方案
        fix = memory.find_similar_error(
            error=ValueError("Text Animator matchName not found"),
            context={"stage": "execute"}
        )
        if fix:
            print(f"推荐修复: {fix['fix_applied']} (成功率: {fix['success_rate']:.0%})")
    """
    
    # 多引擎已知陷阱知识库 (硬编码规则，离线可用)
    # 覆盖 AE ExtendScript / DaVinci Resolve / FFmpeg 三大引擎
    KNOWN_ENGINE_PITFALLS = {
        # =====================================================================
        # AE ExtendScript 陷阱
        # =====================================================================
        "matchname": {
            "engine": "ae",
            "pattern": ["matchname", "match_name", "property not found"],
            "fix_type": "use_correct_matchname",
            "fix_code": 'layer.property("ADBE Text Properties").property("ADBE Text Animators")',
            "description": "AE 2025中Text Animator属性必须使用ADBE matchName而非显示名",
            "confidence": 0.95,
        },
        "opacity_range": {
            "engine": "ae",
            "pattern": ["opacity", "out of range", "0-1", "value"],
            "fix_type": "scale_opacity",
            "fix_code": "opacity_value = min(100, max(0, opacity * 100))",
            "description": "AE 2025中opacity参数必须使用0-100范围而非0-1",
            "confidence": 0.95,
        },
        "temporal_ease": {
            "engine": "ae",
            "pattern": ["settemporaleaseatkey", "dimension", "ease"],
            "fix_type": "match_ease_dimensions",
            "fix_code": "ease = KeyframeEase(0, 75); prop.setTemporalEaseAtKey(key, [ease], [ease])",
            "description": "setTemporalEaseAtKey需匹配属性维度，多维属性需传入数组",
            "confidence": 0.90,
        },
        "layer_move": {
            "engine": "ae",
            "pattern": ["layer.move", "move is not a function", "undefined"],
            "fix_type": "use_parent_or_position",
            "fix_code": "layer.property('Position').setValue([x, y])",
            "description": "ExtendScript中layer.move()不存在，需使用Position属性",
            "confidence": 0.95,
        },
        "efx_crash": {
            "engine": "ae",
            "pattern": ["efx", "chromatic", "crash", "effect"],
            "fix_type": "remove_unstable_effect",
            "fix_code": "if (effect.matchName === 'EFX') effect.remove()",
            "description": "EFX色差效果不稳定，建议移除或使用替代效果",
            "confidence": 0.85,
        },
        "font_missing": {
            "engine": "ae",
            "pattern": ["font", "missing", "not found", "substitute"],
            "fix_type": "font_fallback",
            "fix_code": 'textLayer.font = "Source Han Sans CN"',
            "description": "字体缺失时使用思源黑体等系统字体替代",
            "confidence": 0.90,
        },
        "hevc_compat": {
            "engine": "ae",
            "pattern": ["hevc", "h265", "codec", "import"],
            "fix_type": "transcode_to_h264",
            "fix_code": "ffmpeg -i input.mp4 -c:v libx264 output.mp4",
            "description": "HEVC视频兼容性问题，需转码为H.264",
            "confidence": 0.90,
        },
        # --- S1.1 新增 AE 陷阱 ---
        "expression_engine": {
            "engine": "ae",
            "pattern": ["expression", "javascript", "extendscript", "engine", "syntax error"],
            "fix_type": "set_expression_engine",
            "fix_code": 'app.project.expressionEngine = "javascript-1.0"',
            "description": "表达式引擎版本不匹配，需在JavaScript和ExtendScript之间切换",
            "confidence": 0.85,
        },
        "render_queue_config": {
            "engine": "ae",
            "pattern": ["renderqueue", "outputmodule", "outputpath", "render item"],
            "fix_type": "configure_render_queue",
            "fix_code": "renderItem.outputModule(1).file = new File(absolutePath)",
            "description": "渲染队列未正确配置outputModule和outputPath，需使用绝对路径File对象",
            "confidence": 0.85,
        },
        "file_object_path": {
            "engine": "ae",
            "pattern": ["file path", "relative path", "new file", "save"],
            "fix_type": "use_absolute_file_object",
            "fix_code": "var f = new File('/absolute/path/to/file.aep'); app.project.save(f)",
            "description": "AE必须使用绝对路径的File对象，相对路径会导致保存/导入失败",
            "confidence": 0.90,
        },
        "property_group_nesting": {
            "engine": "ae",
            "pattern": ["propertygroup", "nesting", "property index", "property("],
            "fix_type": "correct_property_nesting",
            "fix_code": 'layer.property("ADBE Transform").property("ADBE Position")',
            "description": "属性需按正确层级访问，不能跳过PropertyGroup直接访问子属性",
            "confidence": 0.85,
        },
        "import_file_format": {
            "engine": "ae",
            "pattern": ["importfile", "importoptions", "footage", "import"],
            "fix_type": "set_import_options",
            "fix_code": "opts = new ImportOptions(f); opts.sequence = true; app.project.importFile(opts)",
            "description": "导入文件需先创建ImportOptions对象并设置序列/alpha等选项",
            "confidence": 0.85,
        },
        "comp_resolution_mismatch": {
            "engine": "ae",
            "pattern": ["resolution", "composition", "downsample", "full res"],
            "fix_type": "set_comp_resolution",
            "fix_code": "comp.renderSettings[0].resolutionFactor = [1, 1]  # 全分辨率",
            "description": "合成分辨率设置不匹配，需确保renderSettings的resolutionFactor为[1,1]",
            "confidence": 0.80,
        },
        # =====================================================================
        # DaVinci Resolve 陷阱
        # =====================================================================
        "davinci_lua_api_version": {
            "engine": "davinci",
            "pattern": ["davinci", "resolve", "lua", "api version", "fuscript"],
            "fix_type": "check_davinci_api_version",
            "fix_code": "-- 检查Resolve版本: resolve.GetAppManager():GetProductVersion()",
            "description": "DaVinci Resolve不同版本的Lua API存在差异，需先检查版本再调用对应API",
            "confidence": 0.85,
        },
        "fusion_node_connection": {
            "engine": "davinci",
            "pattern": ["fusion", "node", "connect", "input", "output", "addtool"],
            "fix_type": "fix_fusion_node_connection",
            "fix_code": "tool:AddInput('Input', otherTool.Output)",
            "description": "Fusion节点连接需使用正确的Input/Output端口名，不能硬编码索引",
            "confidence": 0.85,
        },
        "color_space_transform": {
            "engine": "davinci",
            "pattern": ["color space", "colorspace", "rec709", "rec2020", "srgb", "lut"],
            "fix_type": "set_color_space_correctly",
            "fix_code": "clip:SetClipProperty('Color Space', 'Rec.709')",
            "description": "调色空间转换需明确设置输入/输出色彩空间，否则颜色偏移严重",
            "confidence": 0.90,
        },
        "project_db_lock": {
            "engine": "davinci",
            "pattern": ["projectdb", "database", "lock", "busy", "concurrent"],
            "fix_type": "handle_db_lock",
            "fix_code": "-- 等待数据库解锁: resolve.ProjectManager():LoadProject(name)",
            "description": "DaVinci项目数据库锁定，需等待或切换到独占模式",
            "confidence": 0.80,
        },
        "timeline_clip_format": {
            "engine": "davinci",
            "pattern": ["timeline", "clip", "unsupported media", "media pool"],
            "fix_type": "convert_clip_format",
            "fix_code": "-- 通过MediaPool导入后再添加到Timeline",
            "description": "不支持的格式不能直接添加到Timeline，需先通过MediaPool导入转码",
            "confidence": 0.85,
        },
        "grading_node_order": {
            "engine": "davinci",
            "pattern": ["grade", "node order", "serial", "parallel", "layer"],
            "fix_type": "fix_node_order",
            "fix_code": "-- 确保节点顺序: Serial -> Parallel -> Layer Mixer",
            "description": "调色节点顺序影响最终效果，需按正确拓扑排列（串行/并行/层叠）",
            "confidence": 0.80,
        },
        # =====================================================================
        # FFmpeg 陷阱
        # =====================================================================
        "ffmpeg_encoder_compat": {
            "engine": "ffmpeg",
            "pattern": ["encoder", "codec", "libx264", "libx265", "prores", "unsupported"],
            "fix_type": "fallback_encoder",
            "fix_code": "ffmpeg -i input -c:v libx264 -preset medium -crf 18 output.mp4",
            "description": "编码器不兼容时降级到libx264，确保广泛兼容性",
            "confidence": 0.90,
        },
        "ffmpeg_hdr_to_sdr": {
            "engine": "ffmpeg",
            "pattern": ["hdr", "sdr", "tonemap", "bt2020", "pq", "hlg", "color_primaries"],
            "fix_type": "apply_tonemap_filter",
            "fix_code": "ffmpeg -i hdr_input -vf zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv -c:v libx264 sdr_output.mp4",
            "description": "HDR转SDR需使用tonemap滤镜链，否则颜色严重偏移或过曝",
            "confidence": 0.90,
        },
        "ffmpeg_audio_samplerate": {
            "engine": "ffmpeg",
            "pattern": ["audio", "samplerate", "sample_rate", "44100", "48000", "resample"],
            "fix_type": "match_audio_samplerate",
            "fix_code": "ffmpeg -i input -ar 48000 -ac 2 output.mp4",
            "description": "音频采样率不匹配导致音画不同步，需统一为48000Hz",
            "confidence": 0.85,
        },
        "ffmpeg_subtitle_encoding": {
            "engine": "ffmpeg",
            "pattern": ["subtitle", "srt", "ass", "encoding", "charset", "utf-8", "gbk"],
            "fix_type": "fix_subtitle_encoding",
            "fix_code": "ffmpeg -i input -vf subtitles=sub.srt:charenc=UTF-8 output.mp4",
            "description": "字幕编码格式不匹配（UTF-8/GBK），需显式指定charenc参数",
            "confidence": 0.85,
        },
        "ffmpeg_filter_complex": {
            "engine": "ffmpeg",
            "pattern": ["filter_complex", "filtergraph", "stream mapping", "lavfi"],
            "fix_type": "simplify_filter_chain",
            "fix_code": "ffmpeg -i input -filter_complex '[0:v]scale=1920:1080[v]' -map '[v]' -map 0:a output.mp4",
            "description": "复杂滤镜链语法错误，需正确标记输入输出流并使用-map关联",
            "confidence": 0.80,
        },
        "ffmpeg_pixel_format": {
            "engine": "ffmpeg",
            "pattern": ["pixel format", "yuv420p", "yuv444", "pix_fmt", "compatibility"],
            "fix_type": "set_pixel_format",
            "fix_code": "ffmpeg -i input -pix_fmt yuv420p -c:v libx264 output.mp4",
            "description": "像素格式不兼容（如yuv444p在部分播放器无法解码），需统一为yuv420p",
            "confidence": 0.90,
        },
    }
    
    def __init__(self, memory_dir: str | Path | None = None):
        # 默认写入二线实战反馈隔离目录 settings.feedback_dir 下的 error_patterns，
        # 显式传入时尊重调用方指定路径
        self.memory_dir = Path(memory_dir) if memory_dir is not None else Path(settings.feedback_dir) / "error_patterns"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._patterns: list[dict] = []
        self._load_patterns()
    
    def _load_patterns(self):
        """从磁盘加载历史错误模式"""
        patterns_file = self.memory_dir / "error_patterns.json"
        if patterns_file.exists():
            try:
                with open(patterns_file, "r", encoding="utf-8") as f:
                    self._patterns = json.load(f)
                logger.info(f"[ErrorMemory] Loaded {len(self._patterns)} error patterns")
            except Exception as e:
                logger.warning(f"[ErrorMemory] Load failed: {e}")
                self._patterns = []
    
    def _save_patterns(self):
        """持久化错误模式到磁盘"""
        patterns_file = self.memory_dir / "error_patterns.json"
        try:
            with open(patterns_file, "w", encoding="utf-8") as f:
                json.dump(self._patterns, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[ErrorMemory] Save failed: {e}")
    
    def _extract_keywords(self, error_msg: str) -> list[str]:
        """从错误消息中提取关键词"""
        # 移除常见无意义词
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "with", "by"}
        words = error_msg.lower().replace("_", " ").replace("-", " ").split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords[:10]  # 最多10个关键词
    
    def record_error(
        self,
        error: Exception,
        context: dict,
        fix_applied: str,
        fix_code: str = "",
        success: bool = False,
    ):
        """
        记录错误模式
        
        Args:
            error: 异常对象
            context: 执行上下文 (stage, effect, etc.)
            fix_applied: 应用的修复方案名称
            fix_code: 修复代码片段
            success: 修复是否成功
        """
        error_msg = str(error)[:200]
        error_type = type(error).__name__
        keywords = self._extract_keywords(error_msg)
        
        # 查找是否已有相同模式
        existing = self._find_exact_match(error_type, keywords)
        if existing:
            # 更新现有记录
            existing["occurrence_count"] = existing.get("occurrence_count", 1) + 1
            existing["last_seen"] = datetime.now().isoformat()
            if success:
                existing["success_count"] = existing.get("success_count", 0) + 1
            existing["fix_applied"] = fix_applied
            existing["fix_code"] = fix_code or existing.get("fix_code", "")
        else:
            # 创建新记录
            pattern = {
                "error_type": error_type,
                "error_msg": error_msg,
                "error_keywords": keywords,
                "context_keys": list(context.keys())[:10],
                "context_stage": context.get("stage", ""),
                "fix_applied": fix_applied,
                "fix_code": fix_code,
                "success_count": 1 if success else 0,
                "occurrence_count": 1,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            }
            self._patterns.append(pattern)
        
        self._save_patterns()
        logger.info(f"[ErrorMemory] Recorded: {error_type} -> {fix_applied} (success={success})")
    
    def _find_exact_match(self, error_type: str, keywords: list[str]) -> dict | None:
        """查找精确匹配的错误模式"""
        for pattern in self._patterns:
            if pattern.get("error_type") == error_type:
                pattern_keywords = set(pattern.get("error_keywords", []))
                if len(set(keywords) & pattern_keywords) >= len(keywords) * 0.7:
                    return pattern
        return None
    
    def find_similar_error(
        self,
        error: Exception,
        context: dict,
        min_confidence: float = 0.5,
    ) -> dict | None:
        """
        查找相似错误的历史修复方案
        
        Args:
            error: 当前异常
            context: 执行上下文
            min_confidence: 最低置信度阈值
        
        Returns:
            修复方案字典，包含 fix_applied, fix_code, success_rate, confidence
            未找到时返回 None
        """
        error_msg = str(error).lower()
        error_type = type(error).__name__
        keywords = self._extract_keywords(str(error))
        
        # 1. 首先检查硬编码的已知陷阱 (最高优先级)
        known_fix = self._check_known_pitfalls(error_msg)
        if known_fix and known_fix["confidence"] >= min_confidence:
            return known_fix
        
        # 2. 检查历史错误模式库
        best_match = None
        best_score = 0.0
        
        for pattern in self._patterns:
            score = self._calculate_similarity(
                error_type, keywords, context,
                pattern
            )
            if score > best_score:
                best_score = score
                best_match = pattern
        
        if best_match and best_score >= min_confidence:
            occurrence = best_match.get("occurrence_count", 1)
            success_count = best_match.get("success_count", 0)
            success_rate = success_count / occurrence if occurrence > 0 else 0
            
            return {
                "source": "history",
                "fix_applied": best_match.get("fix_applied", ""),
                "fix_code": best_match.get("fix_code", ""),
                "success_rate": success_rate,
                "confidence": best_score * (0.5 + 0.5 * success_rate),  # 综合相似度+成功率
                "occurrence_count": occurrence,
                "description": f"历史修复方案 (出现{occurrence}次, 成功率{success_rate:.0%})",
            }
        
        return None
    
    def _check_known_pitfalls(self, error_msg: str) -> dict | None:
        """检查已知引擎陷阱知识库（大小写不敏感匹配）"""
        error_msg_lower = error_msg.lower()
        for pitfall_name, pitfall in self.KNOWN_ENGINE_PITFALLS.items():
            patterns = pitfall.get("pattern", [])
            # 检查是否匹配任一模式关键词（大小写不敏感）
            if any(p.lower() in error_msg_lower for p in patterns):
                return {
                    "source": "known_pitfall",
                    "pitfall_name": pitfall_name,
                    "fix_type": pitfall["fix_type"],
                    "fix_applied": pitfall["fix_type"],
                    "fix_code": pitfall["fix_code"],
                    "confidence": pitfall["confidence"],
                    "success_rate": pitfall["confidence"],  # 已知陷阱视为高成功率
                    "description": pitfall["description"],
                }
        return None
    
    def _calculate_similarity(
        self,
        error_type: str,
        keywords: list[str],
        context: dict,
        pattern: dict,
    ) -> float:
        """计算当前错误与历史模式的相似度"""
        score = 0.0
        
        # 错误类型匹配 (权重 0.3)
        if pattern.get("error_type") == error_type:
            score += 0.3
        
        # 关键词匹配 (权重 0.4)
        pattern_keywords = set(pattern.get("error_keywords", []))
        if keywords and pattern_keywords:
            overlap = len(set(keywords) & pattern_keywords)
            keyword_score = overlap / max(len(keywords), 1)
            score += 0.4 * keyword_score
        
        # 上下文匹配 (权重 0.2)
        if context.get("stage") and pattern.get("context_stage"):
            if context["stage"] == pattern["context_stage"]:
                score += 0.2
        
        # 历史成功率加成 (权重 0.1)
        occurrence = pattern.get("occurrence_count", 1)
        success_count = pattern.get("success_count", 0)
        if occurrence > 0:
            success_rate = success_count / occurrence
            score += 0.1 * success_rate
        
        return min(score, 1.0)
    
    def get_statistics(self) -> dict:
        """获取错误模式统计信息"""
        total = len(self._patterns)
        total_occurrences = sum(p.get("occurrence_count", 1) for p in self._patterns)
        total_successes = sum(p.get("success_count", 0) for p in self._patterns)
        
        # 按错误类型分组
        by_type = {}
        for p in self._patterns:
            t = p.get("error_type", "Unknown")
            if t not in by_type:
                by_type[t] = {"count": 0, "occurrences": 0, "successes": 0}
            by_type[t]["count"] += 1
            by_type[t]["occurrences"] += p.get("occurrence_count", 1)
            by_type[t]["successes"] += p.get("success_count", 0)
        
        return {
            "total_patterns": total,
            "total_occurrences": total_occurrences,
            "total_successes": total_successes,
            "overall_success_rate": total_successes / total_occurrences if total_occurrences > 0 else 0,
            "by_error_type": by_type,
            "known_pitfalls_count": len(self.KNOWN_ENGINE_PITFALLS),
        }
    
    def clear(self):
        """清空错误模式库"""
        self._patterns = []
        self._save_patterns()
        logger.info("[ErrorMemory] Cleared all patterns")


# 全局错误记忆实例
_error_memory: ErrorPatternMemory | None = None


def get_error_memory() -> ErrorPatternMemory:
    """获取全局错误记忆实例"""
    global _error_memory
    if _error_memory is None:
        _error_memory = ErrorPatternMemory()
    return _error_memory


def record_error_pattern(
    error: Exception,
    context: dict,
    fix_applied: str,
    fix_code: str = "",
    success: bool = False,
):
    """快捷函数: 记录错误模式"""
    get_error_memory().record_error(error, context, fix_applied, fix_code, success)


def find_error_fix(error: Exception, context: dict) -> dict | None:
    """快捷函数: 查找错误修复方案"""
    return get_error_memory().find_similar_error(error, context)

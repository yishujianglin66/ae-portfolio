"""
core/error_diagnostician.py - LLM辅助错误诊断器 v1.0
=====================================================

当错误模式记忆库(ErrorPatternMemory)无匹配时，调用LLM诊断错误并生成修复建议。

设计原则:
1. 离线优先: LLM不可用时自动降级到规则引擎(P0错误记忆库)
2. 领域知识内嵌: Prompt包含AE ExtendScript已知陷阱
3. 结构化输出: 解析LLM响应为DiagnosticResult
4. 延迟加载: LLMGateway按需初始化，避免启动开销

集成方式:
    from core.error_diagnostician import get_diagnostician

    diagnostician = get_diagnostician()
    result = await diagnostician.diagnose(error, context)
    if result.confidence > 0.6:
        apply_fix(result.fix_code)
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 数据结构
# -----------------------------------------------------------------------------

class FixType(Enum):
    """修复类型"""
    CODE_PATCH = auto()       # 代码补丁（替换/插入代码）
    PARAMETER_FIX = auto()    # 参数修正（修改参数值）
    WORKAROUND = auto()       # 绕行方案（使用替代API）
    RETRY_WITH_DELAY = auto() # 延迟重试（临时性故障）
    SKIP_STEP = auto()        # 跳过步骤（非关键路径）
    MANUAL_REQUIRED = auto()  # 需人工介入


@dataclass
class DiagnosticResult:
    """诊断结果"""
    success: bool = False
    fix_type: FixType = FixType.MANUAL_REQUIRED
    fix_description: str = ""
    fix_code: str = ""
    confidence: float = 0.0
    root_cause: str = ""
    alternatives: List[str] = field(default_factory=list)
    source: str = "none"  # "llm" | "rule_engine" | "none"
    latency_ms: float = 0.0
    error: str = ""


# -----------------------------------------------------------------------------
# 多引擎领域知识（内嵌到诊断Prompt中）
# -----------------------------------------------------------------------------

ENGINE_KNOWN_PITFALLS = """
已知多引擎陷阱与修复模式:

=== AE ExtendScript ===

1. Text Animator 属性名:
   - 错误: 使用显示名 "Position" / "Scale"
   - 正确: 使用 matchName "ADBE Text Position" / "ADBE Text Scale"
   - 修复: 通过 property.matchName 访问

2. Opacity 范围:
   - 错误: 设置 0.0-1.0
   - 正确: 范围 0-100
   - 修复: value * 100

3. setTemporalEaseAtKey 维度:
   - 错误: 传入1维ease给多维属性
   - 正确: KeyframeEase数组长度必须匹配属性维度
   - 修复: 根据 property.value.length 构造对应数量的KeyframeEase

4. layer.move() 不存在:
   - 错误: 调用 layer.move()
   - 正确: 使用 layer.parent = target 或修改 transform.position
   - 修复: 通过parent关系或position关键帧实现

5. 效果插件崩溃 (EFX/第三方):
   - 错误: 直接applyEffect不检查可用性
   - 正确: 先 app.effects 检查是否安装
   - 修复: try-catch + 备选内置效果

6. 字体缺失:
   - 错误: 使用未安装字体导致渲染异常
   - 正确: 先检查 app.fonts 列表
   - 修复: 映射到系统已有字体

7. HEVC/H.265 编码兼容:
   - 错误: 旧版AE不支持HEVC输出
   - 正确: 检查版本，降级到H.264
   - 修复: 使用H.264编码或外部FFmpeg转码

8. 表达式引擎版本:
   - 错误: 使用JavaScript表达式但项目设置为ExtendScript
   - 正确: 检查项目表达式引擎设置
   - 修复: 设置 app.project.expressionEngine = "javascript-1.0"

9. 渲染队列配置:
   - 错误: 添加渲染项后直接render
   - 正确: 需设置outputModule和outputPath
   - 修复: 完整配置renderItem.outputModule(1).file = new File(path)

10. File对象路径:
    - 错误: 使用相对路径
    - 正确: 必须使用绝对路径 File 对象
    - 修复: new File(absolutePath)

11. PropertyGroup嵌套:
    - 错误: 跳过PropertyGroup直接访问子属性
    - 正确: 按层级访问 layer.property("ADBE Transform").property("ADBE Position")
    - 修复: 使用正确的属性层级路径

12. 导入文件格式:
    - 错误: 直接importFile不设置选项
    - 正确: 先创建ImportOptions对象
    - 修复: opts = new ImportOptions(f); opts.sequence = true; app.project.importFile(opts)

=== DaVinci Resolve ===

13. Lua API版本差异:
    - 错误: 不检查Resolve版本直接调用API
    - 正确: 先获取版本号再选择对应API
    - 修复: resolve.GetAppManager():GetProductVersion()

14. Fusion节点连接:
    - 错误: 硬编码输入/输出端口索引
    - 正确: 使用正确的Input/Output端口名
    - 修复: tool:AddInput('Input', otherTool.Output)

15. 色彩空间转换:
    - 错误: 不明确设置输入/输出色彩空间
    - 正确: 显式设置色彩空间参数
    - 修复: clip:SetClipProperty('Color Space', 'Rec.709')

16. 项目数据库锁定:
    - 错误: 并发访问项目数据库
    - 正确: 等待解锁或使用独占模式
    - 修复: resolve.ProjectManager():LoadProject(name)

=== FFmpeg ===

17. HDR转SDR:
    - 错误: 直接转换HDR视频导致颜色偏移
    - 正确: 使用tonemap滤镜链
    - 修复: -vf zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable

18. 音频采样率不匹配:
    - 错误: 不统一音频采样率导致音画不同步
    - 正确: 统一为48000Hz
    - 修复: -ar 48000 -ac 2

19. 字幕编码格式:
    - 错误: 不指定字幕编码导致乱码
    - 正确: 显式指定charenc参数
    - 修复: -vf subtitles=sub.srt:charenc=UTF-8

20. 像素格式不兼容:
    - 错误: 使用yuv444p导致部分播放器无法解码
    - 正确: 统一为yuv420p
    - 修复: -pix_fmt yuv420p
"""


# -----------------------------------------------------------------------------
# 规则引擎降级（LLM不可用时的兜底诊断）
# -----------------------------------------------------------------------------

RULE_BASED_DIAGNOSTICS: List[Dict[str, Any]] = [
    # === AE ExtendScript ===
    {
        "pattern": r"(?i)matchname|match_name|property.*not found",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "属性名不匹配，应使用matchName而非显示名",
        "fix_hint": "使用 property.matchName 或检查 ADBE 前缀",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)opacity|value.*out of range|0\.\d+.*100",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "Opacity值范围错误，AE使用0-100而非0-1",
        "fix_hint": "将 opacity 值乘以 100",
        "confidence": 0.80,
    },
    {
        "pattern": r"(?i)temporal.*ease|KeyframeEase|dimension",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "缓动参数维度不匹配",
        "fix_hint": "KeyframeEase数组长度需匹配属性维度(property.value.length)",
        "confidence": 0.80,
    },
    {
        "pattern": r"(?i)move.*not.*function|layer\.move|undefined.*method",
        "fix_type": FixType.WORKAROUND,
        "description": "layer.move()方法不存在于ExtendScript API",
        "fix_hint": "使用 layer.parent 或 position 关键帧替代",
        "confidence": 0.90,
    },
    {
        "pattern": r"(?i)effect.*not found|applyEffect.*fail|plugin.*crash",
        "fix_type": FixType.WORKAROUND,
        "description": "效果插件不可用或崩溃",
        "fix_hint": "检查 app.effects 列表，使用内置效果替代",
        "confidence": 0.75,
    },
    {
        "pattern": r"(?i)font.*not found|missing.*font|glyph",
        "fix_type": FixType.WORKAROUND,
        "description": "字体缺失",
        "fix_hint": "映射到系统已有字体，检查 app.fonts",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)hevc|h\.?265|codec.*not.*support",
        "fix_type": FixType.WORKAROUND,
        "description": "HEVC编码不兼容",
        "fix_hint": "降级到H.264或使用FFmpeg外部转码",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)expression.*engine|javascript.*extendscript|expressionEngine",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "表达式引擎版本不匹配",
        "fix_hint": '设置 app.project.expressionEngine = "javascript-1.0"',
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)renderqueue|outputmodule|outputpath|render item",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "渲染队列未正确配置",
        "fix_hint": "配置renderItem.outputModule(1).file = new File(absolutePath)",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)file.*path|relative.*path|new file.*save",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "AE必须使用绝对路径File对象",
        "fix_hint": "使用 new File('/absolute/path/to/file')",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)propertygroup|nesting|property.*index",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "属性需按正确层级访问",
        "fix_hint": '使用 layer.property("ADBE Transform").property("ADBE Position")',
        "confidence": 0.80,
    },
    {
        "pattern": r"(?i)importfile|importoptions|footage.*import",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "导入文件需先创建ImportOptions对象",
        "fix_hint": "opts = new ImportOptions(f); opts.sequence = true; app.project.importFile(opts)",
        "confidence": 0.80,
    },
    # === DaVinci Resolve ===
    {
        "pattern": r"(?i)davinci|resolve|lua.*api|fuscript|version.*api",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "DaVinci Resolve Lua API版本差异",
        "fix_hint": "先检查版本: resolve.GetAppManager():GetProductVersion()",
        "confidence": 0.80,
    },
    {
        "pattern": r"(?i)fusion.*node|node.*connect|addtool|input.*output",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "Fusion节点连接端口错误",
        "fix_hint": "使用正确的Input/Output端口名: tool:AddInput('Input', otherTool.Output)",
        "confidence": 0.80,
    },
    {
        "pattern": r"(?i)color.*space|colorspace|rec709|rec2020|srgb|lut|color.*transform",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "色彩空间转换未正确设置",
        "fix_hint": "显式设置: clip:SetClipProperty('Color Space', 'Rec.709')",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)projectdb|database.*lock|busy|concurrent.*access",
        "fix_type": FixType.RETRY_WITH_DELAY,
        "description": "DaVinci项目数据库锁定",
        "fix_hint": "等待数据库解锁或使用独占模式",
        "confidence": 0.75,
    },
    {
        "pattern": r"(?i)timeline.*clip|unsupported.*media|media.*pool|clip.*unsupported",
        "fix_type": FixType.WORKAROUND,
        "description": "不支持的格式不能直接添加到Timeline",
        "fix_hint": "先通过MediaPool导入转码后再添加到Timeline",
        "confidence": 0.80,
    },
    # === FFmpeg ===
    {
        "pattern": r"(?i)encoder|libx264|libx265|prores|codec.*unsupported",
        "fix_type": FixType.WORKAROUND,
        "description": "FFmpeg编码器不兼容",
        "fix_hint": "降级到libx264: -c:v libx264 -preset medium -crf 18",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)hdr|sdr|tonemap|bt2020|pq|hlg|color_primaries",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "HDR转SDR需使用tonemap滤镜",
        "fix_hint": "-vf zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)audio.*samplerate|sample_rate|44100|48000|resample|audio.*sync",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "音频采样率不匹配导致音画不同步",
        "fix_hint": "统一采样率: -ar 48000 -ac 2",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)subtitle|srt|ass|subtitle.*encoding|charenc|charset",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "字幕编码格式不匹配",
        "fix_hint": "指定字幕编码: -vf subtitles=sub.srt:charenc=UTF-8",
        "confidence": 0.85,
    },
    {
        "pattern": r"(?i)filter_complex|filtergraph|stream.*mapping|lavfi",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "FFmpeg复杂滤镜链语法错误",
        "fix_hint": "正确标记输入输出流并使用-map关联",
        "confidence": 0.75,
    },
    {
        "pattern": r"(?i)pixel.*format|yuv420p|yuv444|pix_fmt",
        "fix_type": FixType.PARAMETER_FIX,
        "description": "像素格式不兼容",
        "fix_hint": "统一为yuv420p: -pix_fmt yuv420p",
        "confidence": 0.85,
    },
    # === 通用 ===
    {
        "pattern": r"(?i)timeout|timed?\s*out|connection.*refused|ECONNREFUSED",
        "fix_type": FixType.RETRY_WITH_DELAY,
        "description": "连接超时或服务暂不可用",
        "fix_hint": "延迟后重试，检查目标服务是否启动",
        "confidence": 0.70,
    },
    {
        "pattern": r"(?i)permission|access denied|read.only|EPERM",
        "fix_type": FixType.WORKAROUND,
        "description": "文件权限不足",
        "fix_hint": "检查文件/目录权限，尝试使用临时目录",
        "confidence": 0.75,
    },
    {
        "pattern": r"(?i)out of memory|heap|allocation.*fail",
        "fix_type": FixType.SKIP_STEP,
        "description": "内存不足",
        "fix_hint": "减少并发任务数，清理缓存，分批处理",
        "confidence": 0.65,
    },
]


# -----------------------------------------------------------------------------
# 核心诊断器
# -----------------------------------------------------------------------------

class ErrorDiagnostician:
    """LLM辅助错误诊断器
    
    诊断流程:
    1. 规则引擎快速匹配（<1ms）
    2. 若规则引擎置信度不足，调用LLM深度诊断（~2-5s）
    3. LLM不可用时，返回规则引擎最佳结果
    """

    # 置信度阈值：规则引擎结果高于此值则不调用LLM
    RULE_CONFIDENCE_THRESHOLD = 0.80
    # LLM诊断超时（秒）
    LLM_TIMEOUT_SECONDS = 30
    # 缓存TTL（秒）：缓存条目过期时间
    CACHE_TTL_SECONDS = 3600  # 1小时
    # LLM置信度权重因子（校准用）
    LLM_CONFIDENCE_WEIGHT = 0.85  # LLM自报置信度乘以该因子进行校准

    def __init__(self, min_confidence: float = 0.5, stats_file: str = "data/diagnostician_stats.json"):
        self._gateway = None  # 延迟加载
        self._diagnosis_cache: Dict[str, tuple] = {}  # key -> (result, timestamp)
        self._min_confidence = min_confidence  # S2.4: 可配置最小置信度
        self._stats_file = Path(stats_file)
        self._stats = self._load_statistics()

    @property
    def gateway(self):
        """延迟加载LLMGateway"""
        if self._gateway is None:
            try:
                from core.llm_gateway import llm_gateway
                self._gateway = llm_gateway
            except ImportError:
                logger.warning("[ErrorDiagnostician] LLMGateway不可用，仅使用规则引擎")
        return self._gateway

    async def diagnose(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        use_llm: bool = True,
    ) -> DiagnosticResult:
        """诊断错误并生成修复建议
        
        Args:
            error: 异常实例
            context: 执行上下文（阶段名、参数等）
            use_llm: 是否允许调用LLM（False则仅用规则引擎）
            
        Returns:
            DiagnosticResult 结构化诊断结果
        """
        start_time = time.time()
        self._stats["total_diagnoses"] += 1
        context = context or {}

        try:
            # 0. 缓存检查（带TTL）
            cache_key = self._make_cache_key(error, context)
            if cache_key in self._diagnosis_cache:
                cached_result, cached_time = self._diagnosis_cache[cache_key]
                if time.time() - cached_time < self.CACHE_TTL_SECONDS:
                    self._stats["cache_hits"] += 1
                    cached_result.latency_ms = (time.time() - start_time) * 1000
                    return cached_result
                else:
                    del self._diagnosis_cache[cache_key]

            # 1. 规则引擎快速诊断
            rule_result = self._rule_based_diagnose(error, context)

            # 2. 规则引擎置信度足够高，直接返回
            if rule_result.confidence >= self.RULE_CONFIDENCE_THRESHOLD:
                self._stats["rule_engine_hits"] += 1
                rule_result.latency_ms = (time.time() - start_time) * 1000
                self._diagnosis_cache[cache_key] = (rule_result, time.time())
                return rule_result

            # 3. 尝试LLM深度诊断
            if use_llm and self.gateway is not None:
                llm_result = await self._llm_diagnose(error, context)
                if llm_result.success and llm_result.confidence > rule_result.confidence:
                    self._stats["llm_diagnoses"] += 1
                    llm_result.latency_ms = (time.time() - start_time) * 1000
                    self._diagnosis_cache[cache_key] = (llm_result, time.time())
                    return llm_result
                else:
                    self._stats["llm_failures"] += 1

            # 4. 回退到规则引擎结果
            rule_result.latency_ms = (time.time() - start_time) * 1000
            self._diagnosis_cache[cache_key] = (rule_result, time.time())
            return rule_result
        finally:
            # S2.5: 每次诊断后持久化统计
            self._save_statistics()

    def _rule_based_diagnose(
        self, error: Exception, context: Dict[str, Any]
    ) -> DiagnosticResult:
        """规则引擎诊断（基于正则匹配已知模式）"""
        error_msg = str(error)
        error_type = type(error).__name__
        combined_text = f"{error_type}: {error_msg}"

        best_match: Optional[Dict] = None
        best_score = 0.0

        for rule in RULE_BASED_DIAGNOSTICS:
            if re.search(rule["pattern"], combined_text):
                # 基础置信度
                score = rule["confidence"]
                # 上下文加分：如果上下文包含相关关键词
                context_str = json.dumps(context, ensure_ascii=False, default=str)
                rule_keywords = rule["description"].lower().split()
                keyword_hits = sum(1 for kw in rule_keywords if kw in context_str.lower())
                score = min(1.0, score + keyword_hits * 0.02)

                if score > best_score:
                    best_score = score
                    best_match = rule

        if best_match:
            return DiagnosticResult(
                success=True,
                fix_type=best_match["fix_type"],
                fix_description=best_match["description"],
                fix_code=best_match["fix_hint"],
                confidence=best_score,
                root_cause=best_match["description"],
                source="rule_engine",
            )

        # 无匹配：返回低置信度通用结果
        return DiagnosticResult(
            success=False,
            fix_type=FixType.MANUAL_REQUIRED,
            fix_description="未匹配已知错误模式",
            confidence=0.1,
            root_cause=f"{error_type}: {error_msg[:200]}",
            source="rule_engine",
        )

    async def _llm_diagnose(
        self, error: Exception, context: Dict[str, Any]
    ) -> DiagnosticResult:
        """LLM深度诊断"""
        try:
            from core.llm_gateway import TaskType as LLMTaskType

            prompt = self._build_diagnostic_prompt(error, context)
            system_prompt = (
                "你是After Effects自动化和ExtendScript专家。"
                "诊断以下错误并给出精确修复方案。"
                "输出严格JSON格式，不要包含其他文字。"
            )

            response = await self.gateway.chat_with_routing(
                prompt,
                task_type=LLMTaskType.FEEDBACK_ANALYSIS,
                system_prompt=system_prompt,
            )

            if not response.success:
                logger.debug(f"[ErrorDiagnostician] LLM调用失败: {response.error}")
                return DiagnosticResult(success=False, error=response.error)

            return self._parse_llm_response(response.content)

        except Exception as e:
            logger.debug(f"[ErrorDiagnostician] LLM诊断异常: {e}")
            return DiagnosticResult(success=False, error=str(e))

    def _build_diagnostic_prompt(
        self, error: Exception, context: Dict[str, Any]
    ) -> str:
        """构建诊断Prompt（包含领域知识 + Few-shot示例）"""
        error_type = type(error).__name__
        error_msg = str(error)[:500]
        context_str = json.dumps(context, ensure_ascii=False, default=str)[:800]

        return f"""## 错误诊断请求

错误类型: {error_type}
错误消息: {error_msg}
执行上下文: {context_str}

## 领域知识参考
{ENGINE_KNOWN_PITFALLS}

## 诊断示例（Few-shot）

示例1:
输入: ValueError("Text Animator matchName not found: Position")
输出:
{{"fix_type": "parameter_fix", "fix_description": "AE属性名必须使用matchName而非显示名", "fix_code": "layer.property('ADBE Text Properties').property('ADBE Text Animators')", "confidence": 0.92, "root_cause": "使用了显示名Position而非ADBE matchName", "alternatives": ["通过propertyGroup层级访问"]}}

示例2:
输入: RuntimeError("HDR video tonemap color offset after conversion")
输出:
{{"fix_type": "parameter_fix", "fix_description": "HDR转SDR需使用tonemap滤镜链", "fix_code": "-vf zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable", "confidence": 0.88, "root_cause": "HDR视频直接转换到SDR色彩空间导致颜色偏移", "alternatives": ["使用FFmpeg tonemap滤镜", "手动调整LUT"]}}

## 输出要求
请输出严格JSON格式（不要markdown代码块）:
{{
    "fix_type": "code_patch|parameter_fix|workaround|retry_with_delay|skip_step|manual_required",
    "fix_description": "修复方案简述",
    "fix_code": "具体修复代码或操作步骤",
    "confidence": 0.0到1.0的置信度,
    "root_cause": "根因分析",
    "alternatives": ["备选方案1", "备选方案2"]
}}"""

    def _parse_llm_response(self, content: str) -> DiagnosticResult:
        """解析LLM响应为结构化结果"""
        try:
            # 尝试提取JSON（处理可能的markdown包裹）
            json_str = content.strip()
            # 移除可能的 ```json ... ``` 包裹
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', json_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接找 { ... }
                brace_match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if brace_match:
                    json_str = brace_match.group(0)

            data = json.loads(json_str)

            # 映射fix_type字符串到枚举
            fix_type_map = {
                "code_patch": FixType.CODE_PATCH,
                "parameter_fix": FixType.PARAMETER_FIX,
                "workaround": FixType.WORKAROUND,
                "retry_with_delay": FixType.RETRY_WITH_DELAY,
                "skip_step": FixType.SKIP_STEP,
                "manual_required": FixType.MANUAL_REQUIRED,
            }
            fix_type = fix_type_map.get(
                data.get("fix_type", "manual_required"),
                FixType.MANUAL_REQUIRED,
            )

            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            # S2.2: 置信度校准 — LLM自报置信度 × 来源权重因子
            calibrated_confidence = confidence * self.LLM_CONFIDENCE_WEIGHT

            return DiagnosticResult(
                success=True,
                fix_type=fix_type,
                fix_description=data.get("fix_description", ""),
                fix_code=data.get("fix_code", ""),
                confidence=calibrated_confidence,
                root_cause=data.get("root_cause", ""),
                alternatives=data.get("alternatives", []),
                source="llm",
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug(f"[ErrorDiagnostician] LLM响应解析失败: {e}")
            return DiagnosticResult(
                success=False,
                error=f"LLM响应解析失败: {e}",
                source="llm",
            )

    def _make_cache_key(self, error: Exception, context: Dict[str, Any]) -> str:
        """生成缓存键"""
        error_sig = f"{type(error).__name__}:{str(error)[:100]}"
        ctx_keys = sorted(context.keys()) if context else []
        return f"{error_sig}|{'|'.join(ctx_keys[:5])}"

    def get_statistics(self) -> Dict[str, Any]:
        """获取诊断统计信息"""
        # 清理过期缓存
        now = time.time()
        expired_keys = [
            k for k, (_, ts) in self._diagnosis_cache.items()
            if now - ts >= self.CACHE_TTL_SECONDS
        ]
        for k in expired_keys:
            del self._diagnosis_cache[k]
        return {
            **self._stats,
            "cache_size": len(self._diagnosis_cache),
            "llm_available": self.gateway is not None,
            "min_confidence": self._min_confidence,
            "cache_ttl_seconds": self.CACHE_TTL_SECONDS,
            "llm_confidence_weight": self.LLM_CONFIDENCE_WEIGHT,
        }

    def clear_cache(self) -> None:
        """清除诊断缓存"""
        self._diagnosis_cache.clear()

    def _load_statistics(self) -> Dict[str, Any]:
        """S2.5: 从磁盘加载诊断统计"""
        default_stats = {
            "total_diagnoses": 0,
            "rule_engine_hits": 0,
            "llm_diagnoses": 0,
            "llm_failures": 0,
            "cache_hits": 0,
        }
        if self._stats_file.exists():
            try:
                with open(self._stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"[ErrorDiagnostician] Load stats failed: {e}")
        return default_stats

    def _save_statistics(self) -> None:
        """S2.5: 持久化诊断统计到磁盘"""
        try:
            self._stats_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._stats_file, "w", encoding="utf-8") as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"[ErrorDiagnostician] Save stats failed: {e}")


# -----------------------------------------------------------------------------
# 全局单例
# -----------------------------------------------------------------------------

_diagnostician_instance: Optional[ErrorDiagnostician] = None


def get_diagnostician() -> ErrorDiagnostician:
    """获取全局诊断器实例"""
    global _diagnostician_instance
    if _diagnostician_instance is None:
        _diagnostician_instance = ErrorDiagnostician()
    return _diagnostician_instance

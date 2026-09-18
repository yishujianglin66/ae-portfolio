"""
core/failure_postmortem.py — 失败复盘 (P4.4)
==============================================

自动收集失败上下文，调用因果引擎进行根因分析，
并通过规则蒸馏器提炼可复用教训，生成 Markdown / JSON 报告。

设计原则:
1. 自动收集: 从 TracePropagator / ArtifactManager / 日志自动聚合上下文
2. 因果分析: 集成 core.causal_engine.root_cause_chain (graceful degrade)
3. 教训蒸馏: 集成 core.self_evolution_engine.RuleDistiller (graceful degrade)
4. 相似检索: 基于失败签名 (failure signature) 检索历史相似失败
5. 持久化归档: 报告写入 data/postmortem/

集成方式:
    from core.failure_postmortem import get_failure_postmortem, FailureRecord

    pm = get_failure_postmortem()
    record = FailureRecord(
        run_id="run_2025_001",
        stage="execute",
        error_type="RuntimeError",
        error_message="AE Bridge timeout",
        traceback_str="...",
    )
    report = pm.analyze(record)
    print(pm.generate_report(report, format="markdown"))
    pm.archive_report(report)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
#  数据类
# ============================================================================

@dataclass
class FailureSignature:
    """失败签名 - 用于相似失败检索

    由 error_type + stage + error_message 关键词生成。
    同签名的失败视为同类，可聚类分析。

    Attributes:
        signature: 签名字符串 (sha256 前 16 位)
        error_type: 异常类型名
        stage: 失败阶段
        keywords: 从错误信息中提取的关键词
    """
    signature: str = ""
    error_type: str = ""
    stage: str = ""
    keywords: list[str] = field(default_factory=list)

    @classmethod
    def from_record(
        cls,
        error_type: str,
        stage: str,
        error_message: str,
    ) -> "FailureSignature":
        """从失败记录生成签名

        关键词提取策略:
        - 转小写
        - 按空格/标点切分
        - 过滤长度 < 4 的词
        - 取前 5 个

        Args:
            error_type: 异常类型
            stage: 失败阶段
            error_message: 错误信息

        Returns:
            FailureSignature
        """
        # 关键词提取
        msg_lower = error_message.lower()
        # 简单分词: 非字母数字字符作为分隔符
        import re
        tokens = re.split(r"[^a-z0-9_]+", msg_lower)
        keywords = [t for t in tokens if len(t) >= 4][:5]
        sig_src = f"{error_type}|{stage}|{'-'.join(keywords)}"
        sig = hashlib.sha256(sig_src.encode("utf-8")).hexdigest()[:16]
        return cls(
            signature=sig,
            error_type=error_type,
            stage=stage,
            keywords=keywords,
        )


@dataclass
class FixRecommendation:
    """修复建议

    Attributes:
        title: 建议标题
        description: 详细描述
        confidence: 置信度 [0, 1]
        source: 来源 ("causal" / "rule" / "expert" / "heuristic")
        action: 具体动作
    """
    title: str = ""
    description: str = ""
    confidence: float = 0.0
    source: str = "heuristic"
    action: str = ""


@dataclass
class FailureRecord:
    """失败记录 - 复盘的输入

    Attributes:
        run_id: 所属 run_id
        stage: 失败阶段
        error_type: 异常类型名
        error_message: 错误信息
        traceback_str: 完整 traceback
        timestamp: 失败时间戳
        context: 额外上下文（配置、参数等）
        trace_id: 关联的 trace_id（可选）
    """
    run_id: str = ""
    stage: str = ""
    error_type: str = ""
    error_message: str = ""
    traceback_str: str = ""
    timestamp: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""


@dataclass
class PostmortemReport:
    """复盘报告

    Attributes:
        report_id: 报告唯一 ID
        run_id: 关联的 run_id
        signature: 失败签名
        failure: 原始失败记录
        root_causes: 根因链（来自 causal_engine）
        recommendations: 修复建议列表
        distilled_rules: 蒸馏出的规则（来自 RuleDistiller）
        similar_failures: 相似历史失败 ID 列表
        created_at: 报告生成时间戳
        trace_spans: 关联的 trace span 摘要
        artifacts: 关联的产物列表
    """
    report_id: str = ""
    run_id: str = ""
    signature: FailureSignature = field(default_factory=FailureSignature)
    failure: FailureRecord = field(default_factory=FailureRecord)
    root_causes: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[FixRecommendation] = field(default_factory=list)
    distilled_rules: list[dict[str, Any]] = field(default_factory=list)
    similar_failures: list[str] = field(default_factory=list)
    created_at: float = 0.0
    trace_spans: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "signature": asdict(self.signature),
            "failure": asdict(self.failure),
            "root_causes": self.root_causes,
            "recommendations": [asdict(r) for r in self.recommendations],
            "distilled_rules": self.distilled_rules,
            "similar_failures": self.similar_failures,
            "created_at": self.created_at,
            "trace_spans": self.trace_spans,
            "artifacts": self.artifacts,
        }


# ============================================================================
#  旗舰管线八类错误枚举 + 修复建议模板
# ============================================================================

from enum import Enum


class FlagshipErrorCode(str, Enum):
    """旗舰管线八类错误枚举。

    每个错误码对应一类可恢复/不可恢复失败，
    用于统一分类、报告生成和自动修复建议。
    """
    BRIDGE_DOWN = "BRIDGE_DOWN"
    LICENSE_MISSING = "LICENSE_MISSING"
    OUTPUT_CORRUPT = "OUTPUT_CORRUPT"
    SCRIPT_SYNTAX = "SCRIPT_SYNTAX"
    TIMEOUT = "TIMEOUT"
    USER_CANCELLED = "USER_CANCELLED"
    DISK_FULL = "DISK_FULL"
    LICENCE_POPUP_BLOCKING = "LICENCE_POPUP_BLOCKING"


# 修复建议模板：错误码 → (title, description, action, confidence)
FLAGSHIP_FIX_TEMPLATES: dict[str, dict[str, Any]] = {
    FlagshipErrorCode.BRIDGE_DOWN: {
        "title": "Bridge 连接中断",
        "description": "MCP Bridge 文件轮询协议无法连通目标软件。可能是软件未启动、listener 未加载、或 Bridge 目录被删除。",
        "action": "1. 确认目标软件已启动\n2. 重新加载 Bridge listener 脚本\n3. 检查 Bridge 目录权限",
        "confidence": 0.9,
    },
    FlagshipErrorCode.LICENSE_MISSING: {
        "title": "许可证缺失",
        "description": "目标软件未激活或许可证已过期，无法执行自动化操作。",
        "action": "1. 打开软件手动激活许可证\n2. 检查 Adobe Creative Cloud 登录状态\n3. 确认订阅未过期",
        "confidence": 0.95,
    },
    FlagshipErrorCode.OUTPUT_CORRUPT: {
        "title": "输出产物损坏",
        "description": "渲染/导出产物无法解码或文件大小为 0，可能是编码失败或磁盘写入中断。",
        "action": "1. 检查磁盘空间\n2. 重新执行渲染\n3. 检查编解码器是否可用",
        "confidence": 0.8,
    },
    FlagshipErrorCode.SCRIPT_SYNTAX: {
        "title": "脚本语法错误",
        "description": "ExtendScript/Lua 脚本存在语法错误，可能是参数转义问题或 API 版本不兼容。",
        "action": "1. 检查脚本中的特殊字符转义\n2. 确认软件版本与 API 兼容\n3. 在软件中手动执行脚本调试",
        "confidence": 0.85,
    },
    FlagshipErrorCode.TIMEOUT: {
        "title": "执行超时",
        "description": "操作在规定时间内未完成。可能是渲染复杂度过高、系统资源不足、或软件挂起。",
        "action": "1. 增加超时时间\n2. 检查系统 CPU/GPU/内存使用率\n3. 简化合成/序列复杂度\n4. 重启目标软件",
        "confidence": 0.75,
    },
    FlagshipErrorCode.USER_CANCELLED: {
        "title": "用户取消",
        "description": "用户主动取消了执行操作。",
        "action": "无需修复，等待用户重新触发执行。",
        "confidence": 1.0,
    },
    FlagshipErrorCode.DISK_FULL: {
        "title": "磁盘空间不足",
        "description": "目标磁盘剩余空间不足以完成渲染/导出操作。",
        "action": "1. 清理磁盘空间（至少 50GB）\n2. 更换输出目录到大容量磁盘\n3. 删除旧的渲染缓存",
        "confidence": 0.95,
    },
    FlagshipErrorCode.LICENCE_POPUP_BLOCKING: {
        "title": "许可弹窗阻塞",
        "description": "软件弹出了许可协议/更新提示弹窗，阻塞了自动化脚本执行。",
        "action": "1. 手动关闭弹窗\n2. 在软件设置中禁用自动更新提示\n3. 使用健康检查的 license_popup_detected 检测",
        "confidence": 0.9,
    },
}


def classify_error(error_code: str, error_message: str = "") -> FlagshipErrorCode:
    """将错误码/错误信息分类为八类错误之一。

    Args:
        error_code: 引擎返回的错误码
        error_message: 错误信息（用于辅助分类）

    Returns:
        FlagshipErrorCode 枚举值
    """
    code_upper = (error_code or "").upper()
    msg_lower = (error_message or "").lower()

    # 直接匹配
    try:
        return FlagshipErrorCode(code_upper)
    except ValueError:
        pass

    # 关键词匹配
    if "bridge" in msg_lower or "bridge" in code_upper:
        return FlagshipErrorCode.BRIDGE_DOWN
    if "license" in msg_lower or "licence" in msg_lower:
        if "popup" in msg_lower or "blocking" in msg_lower:
            return FlagshipErrorCode.LICENCE_POPUP_BLOCKING
        return FlagshipErrorCode.LICENSE_MISSING
    if "corrupt" in msg_lower or "decode" in msg_lower:
        return FlagshipErrorCode.OUTPUT_CORRUPT
    if "syntax" in msg_lower or "script" in msg_lower:
        return FlagshipErrorCode.SCRIPT_SYNTAX
    if "timeout" in msg_lower or "timed out" in msg_lower:
        return FlagshipErrorCode.TIMEOUT
    if "cancel" in msg_lower:
        return FlagshipErrorCode.USER_CANCELLED
    if "disk" in msg_lower or "space" in msg_lower or "full" in msg_lower:
        return FlagshipErrorCode.DISK_FULL

    # 默认归类为 TIMEOUT（最常见的未分类失败）
    return FlagshipErrorCode.TIMEOUT


def get_fix_recommendation(error_code: FlagshipErrorCode) -> FixRecommendation:
    """根据错误码获取修复建议。

    Args:
        error_code: 八类错误枚举

    Returns:
        FixRecommendation
    """
    template = FLAGSHIP_FIX_TEMPLATES.get(error_code, {})
    return FixRecommendation(
        title=template.get("title", "未知错误"),
        description=template.get("description", "无可用描述"),
        confidence=template.get("confidence", 0.5),
        source="expert",
        action=template.get("action", "请检查日志获取更多信息"),
    )


# ============================================================================
#  FailurePostmortem
# ============================================================================

class FailurePostmortem:
    """失败复盘器

    流程:
    1. 接收 FailureRecord
    2. 生成 FailureSignature
    3. 收集上下文: trace / artifacts / 日志
    4. 调用 causal_engine.root_cause_chain 获取根因链
    5. 调用 RuleDistiller.distill_from_episodes 蒸馏教训
    6. 生成 FixRecommendation
    7. 检索相似历史失败
    8. 持久化到 data/postmortem/

    所有外部依赖均 graceful degrade:
    - causal_engine 不可用 → root_causes 为空
    - RuleDistiller 不可用 → distilled_rules 为空
    - TracePropagator 不可用 → trace_spans 为空
    - ArtifactManager 不可用 → artifacts 为空
    """

    def __init__(self, archive_dir: str = "data/postmortem"):
        """初始化失败复盘器

        Args:
            archive_dir: 报告归档目录
        """
        self._archive_dir = Path(archive_dir)
        try:
            self._archive_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        # 内存索引: signature -> List[report_id]
        self._signature_index: dict[str, list[str]] = {}
        # 内存缓存: report_id -> PostmortemReport
        self._reports: dict[str, PostmortemReport] = {}
        self._load_existing_reports()
        self._logger = logging.getLogger(__name__ + ".FailurePostmortem")

    def _load_existing_reports(self) -> None:
        """加载已归档的报告，建立索引"""
        try:
            for f in self._archive_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    report = self._dict_to_report(data)
                    self._reports[report.report_id] = report
                    sig = report.signature.signature
                    if sig:
                        self._signature_index.setdefault(sig, []).append(report.report_id)
                except Exception:
                    continue
        except Exception as e:
            self._logger.debug("[FailurePostmortem] load reports failed: %s", e)

    def _dict_to_report(self, data: dict[str, Any]) -> PostmortemReport:
        """字典转 PostmortemReport"""
        sig_data = data.get("signature", {})
        fail_data = data.get("failure", {})
        recs_data = data.get("recommendations", [])
        return PostmortemReport(
            report_id=data.get("report_id", ""),
            run_id=data.get("run_id", ""),
            signature=FailureSignature(**sig_data) if sig_data else FailureSignature(),
            failure=FailureRecord(**fail_data) if fail_data else FailureRecord(),
            root_causes=data.get("root_causes", []),
            recommendations=[FixRecommendation(**r) for r in recs_data],
            distilled_rules=data.get("distilled_rules", []),
            similar_failures=data.get("similar_failures", []),
            created_at=data.get("created_at", 0.0),
            trace_spans=data.get("trace_spans", []),
            artifacts=data.get("artifacts", []),
        )

    # ---- 上下文收集 ----
    def _collect_trace_spans(self, trace_id: str) -> list[dict[str, Any]]:
        """收集 trace 上下文（graceful degrade）"""
        if not trace_id:
            return []
        try:
            from core.observability import get_trace_propagator
            prop = get_trace_propagator()
            spans = prop.get_trace_spans(trace_id)
            return [s.to_dict() for s in spans]
        except Exception as e:
            self._logger.debug("[FailurePostmortem] trace collection failed: %s", e)
            return []

    def _collect_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        """收集产物上下文（graceful degrade）"""
        if not run_id:
            return []
        try:
            from core.artifact_manager import get_artifact_manager
            mgr = get_artifact_manager()
            return [a.to_dict() for a in mgr.list_by_run(run_id)]
        except Exception as e:
            self._logger.debug("[FailurePostmortem] artifact collection failed: %s", e)
            return []

    def _query_root_causes(self, failure: FailureRecord) -> list[dict[str, Any]]:
        """调用因果引擎获取根因链（graceful degrade）"""
        try:
            from core.causal_engine import get_causal_engine
            engine = get_causal_engine()
            # 用 run_id 作为 failure_id（因果引擎内部会查找）
            failure_id = failure.run_id or f"{failure.stage}_{failure.error_type}"
            # root_cause_chain 是同步方法
            chain = engine.root_cause_chain(failure_id, max_hops=3)
            # CausalLink 转 dict
            result = []
            for link in chain:
                # CausalLink 字段: source, target, weight, confidence, explanation
                if hasattr(link, "to_dict"):
                    result.append(link.to_dict())
                else:
                    result.append({
                        "source": getattr(link, "source", ""),
                        "target": getattr(link, "target", ""),
                        "weight": getattr(link, "weight", 0.0),
                        "confidence": getattr(link, "confidence", 0.0),
                        "explanation": getattr(link, "explanation", ""),
                    })
            return result
        except Exception as e:
            self._logger.debug("[FailurePostmortem] causal engine query failed: %s", e)
            return []

    def _distill_lessons(self, failure: FailureRecord) -> list[dict[str, Any]]:
        """调用 RuleDistiller 蒸馏教训（graceful degrade）"""
        try:
            from core.self_evolution_engine import (
                ExecutionEpisode,
                RuleDistiller,
            )
            distiller = RuleDistiller(min_support=1, min_confidence=0.5)
            # 构造单个 episode（蒸馏器要求 List，单个也行）
            episode = ExecutionEpisode(
                episode_id=failure.run_id,
                context_features={
                    "stage": failure.stage,
                    "error_type": failure.error_type,
                },
                action_taken=failure.context.get("action_taken", "execute_stage"),
                outcome_success=False,
                outcome_quality=0.0,
                outcome_duration=failure.context.get("duration", 0.0),
                timestamp=failure.timestamp or time.time(),
            )
            rules = distiller.distill_from_episodes([episode])
            return [r.to_dict() for r in rules]
        except Exception as e:
            self._logger.debug("[FailurePostmortem] lesson distillation failed: %s", e)
            return []

    def _generate_recommendations(
        self,
        failure: FailureRecord,
        root_causes: list[dict[str, Any]],
        distilled_rules: list[dict[str, Any]],
    ) -> list[FixRecommendation]:
        """根据根因和规则生成修复建议

        启发式策略:
        - 若有 distilled_rules，优先采用
        - 若有 root_causes，根据 source/target 推荐干预
        - 兜底建议: 重试 + 检查日志
        """
        recs: list[FixRecommendation] = []

        # 1. 从蒸馏规则生成建议
        for rule in distilled_rules:
            recs.append(FixRecommendation(
                title=f"应用蒸馏规则: {rule.get('rule_id', '')}",
                description=rule.get("condition", ""),
                confidence=float(rule.get("confidence", 0.5)),
                source="rule",
                action=rule.get("action", ""),
            ))

        # 2. 从根因链生成建议
        for cause in root_causes:
            source = cause.get("source", "")
            weight = float(cause.get("weight", 0.0))
            confidence = float(cause.get("confidence", 0.0))
            direction = "促进" if weight > 0 else "抑制"
            recs.append(FixRecommendation(
                title=f"干预根因节点: {source}",
                description=(
                    f"根因 {source} {direction} {cause.get('target', '')}; "
                    f"权重={weight:+.2f}, 置信度={confidence:.2f}"
                ),
                confidence=max(0.0, min(1.0, confidence)),
                source="causal",
                action=f"在 {source} 节点处检查并干预",
            ))

        # 3. 启发式兜底建议
        if not recs:
            recs.append(FixRecommendation(
                title="重试失败阶段",
                description=(
                    f"阶段 {failure.stage} 因 {failure.error_type} 失败；"
                    f"建议检查错误信息并重试"
                ),
                confidence=0.3,
                source="heuristic",
                action="retry_with_logs",
            ))

        # 4. 错误类型特定建议（同时检查 error_type 和 error_message）
        err_lower = failure.error_type.lower()
        msg_lower = failure.error_message.lower()
        combined = err_lower + " " + msg_lower
        if "timeout" in combined or "timed out" in combined or "timedout" in combined:
            recs.append(FixRecommendation(
                title="检查超时配置",
                description="错误涉及超时，建议增加超时阈值或优化性能",
                confidence=0.7,
                source="expert",
                action="increase_timeout",
            ))
        elif "memory" in combined or "oom" in combined:
            recs.append(FixRecommendation(
                title="检查内存使用",
                description="错误类型为内存相关，建议降低批大小或释放内存",
                confidence=0.7,
                source="expert",
                action="reduce_batch_size",
            ))
        elif "file" in combined or "notfound" in combined or "not found" in combined:
            recs.append(FixRecommendation(
                title="检查文件路径",
                description="错误涉及文件不存在，建议验证路径与权限",
                confidence=0.8,
                source="expert",
                action="verify_file_paths",
            ))

        return recs

    # ---- 核心 API ----
    def analyze(self, failure_record: FailureRecord) -> PostmortemReport:
        """分析失败记录，生成复盘报告

        Args:
            failure_record: 失败记录

        Returns:
            PostmortemReport
        """
        # 1. 生成签名
        signature = FailureSignature.from_record(
            error_type=failure_record.error_type,
            stage=failure_record.stage,
            error_message=failure_record.error_message,
        )

        # 2. 收集上下文（全部 graceful degrade）
        trace_spans = self._collect_trace_spans(failure_record.trace_id)
        artifacts = self._collect_artifacts(failure_record.run_id)
        root_causes = self._query_root_causes(failure_record)
        distilled_rules = self._distill_lessons(failure_record)

        # 3. 生成修复建议
        recommendations = self._generate_recommendations(
            failure_record, root_causes, distilled_rules,
        )

        # 4. 检索相似历史失败
        similar = self._signature_index.get(signature.signature, [])
        # 排除自身（即将生成的 report_id 还未生成，但用 run_id 防重）
        similar = [s for s in similar if s != failure_record.run_id]

        # 5. 生成报告
        import uuid
        report_id = f"pm_{uuid.uuid4().hex[:12]}"
        report = PostmortemReport(
            report_id=report_id,
            run_id=failure_record.run_id,
            signature=signature,
            failure=failure_record,
            root_causes=root_causes,
            recommendations=recommendations,
            distilled_rules=distilled_rules,
            similar_failures=similar,
            created_at=time.time(),
            trace_spans=trace_spans,
            artifacts=artifacts,
        )

        # 6. 缓存并更新索引
        self._reports[report_id] = report
        self._signature_index.setdefault(signature.signature, []).append(report_id)

        self._logger.info(
            "[FailurePostmortem] analyzed: %s (sig=%s, root_causes=%d, recs=%d, similar=%d)",
            report_id, signature.signature, len(root_causes),
            len(recommendations), len(similar),
        )
        return report

    def generate_report(
        self,
        report: PostmortemReport,
        format: str = "markdown",
    ) -> str:
        """生成报告

        Args:
            report: PostmortemReport
            format: "markdown" 或 "json"

        Returns:
            报告字符串
        """
        if format == "json":
            return json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str)

        # Markdown 格式
        lines: list[str] = []
        lines.append(f"# 失败复盘报告: {report.report_id}")
        lines.append("")
        lines.append(f"- **Run ID**: {report.run_id}")
        lines.append(f"- **失败签名**: `{report.signature.signature}`")
        lines.append(f"- **生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.created_at))}")
        lines.append("")

        lines.append("## 失败信息")
        f = report.failure
        lines.append(f"- **阶段**: {f.stage}")
        lines.append(f"- **错误类型**: `{f.error_type}`")
        lines.append(f"- **错误信息**: {f.error_message}")
        if f.traceback_str:
            lines.append("")
            lines.append("```")
            lines.append(f.traceback_str)
            lines.append("```")
        lines.append("")

        lines.append("## 根因分析")
        if report.root_causes:
            for i, cause in enumerate(report.root_causes, 1):
                lines.append(f"{i}. **{cause.get('source', '?')}** → {cause.get('target', '?')}")
                lines.append(f"   - 权重: {cause.get('weight', 0):+.2f}")
                lines.append(f"   - 置信度: {cause.get('confidence', 0):.2f}")
                if cause.get("explanation"):
                    lines.append(f"   - 说明: {cause['explanation']}")
        else:
            lines.append("_无根因链数据（causal_engine 不可用或未找到匹配）_")
        lines.append("")

        lines.append("## 修复建议")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"{i}. **{rec.title}** (来源: {rec.source}, 置信度: {rec.confidence:.0%})")
            if rec.description:
                lines.append(f"   - {rec.description}")
            if rec.action:
                lines.append(f"   - 动作: `{rec.action}`")
        lines.append("")

        lines.append("## 蒸馏规则")
        if report.distilled_rules:
            for rule in report.distilled_rules:
                lines.append(f"- `{rule.get('rule_id', '')}`: {rule.get('condition', '')} → {rule.get('action', '')} (conf={rule.get('confidence', 0):.2f})")
        else:
            lines.append("_无蒸馏规则（RuleDistiller 不可用或样本不足）_")
        lines.append("")

        lines.append("## 相似历史失败")
        if report.similar_failures:
            for sid in report.similar_failures:
                lines.append(f"- {sid}")
        else:
            lines.append("_无相似历史失败_")
        lines.append("")

        if report.trace_spans:
            lines.append("## Trace Spans")
            for span in report.trace_spans:
                lines.append(f"- {span.get('stage_name', '')} ({span.get('span_id', '')}) status={span.get('status', '')}")
            lines.append("")

        if report.artifacts:
            lines.append("## 关联产物")
            for art in report.artifacts:
                lines.append(f"- [{art.get('stage', '')}] {art.get('type', '')}: {art.get('path', '')}")
            lines.append("")

        return "\n".join(lines)

    def archive_report(self, report: PostmortemReport) -> str:
        """归档报告到 data/postmortem/

        Args:
            report: PostmortemReport

        Returns:
            归档文件路径
        """
        try:
            out_file = self._archive_dir / f"{report.report_id}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, ensure_ascii=False, indent=2, default=str)
            self._logger.info("[FailurePostmortem] archived: %s", out_file)
            return str(out_file)
        except Exception as e:
            self._logger.warning("[FailurePostmortem] archive failed: %s", e)
            return ""

    def get_sim_failures(self, failure_signature: str) -> list[PostmortemReport]:
        """检索相似历史失败

        Args:
            failure_signature: 失败签名（FailureSignature.signature）

        Returns:
            相似报告列表
        """
        report_ids = self._signature_index.get(failure_signature, [])
        return [self._reports[rid] for rid in report_ids if rid in self._reports]


# ============================================================================
#  全局单例
# ============================================================================

_global_failure_postmortem: FailurePostmortem | None = None


def get_failure_postmortem() -> FailurePostmortem:
    """获取全局 FailurePostmortem 单例

    Returns:
        FailurePostmortem 实例
    """
    global _global_failure_postmortem
    if _global_failure_postmortem is None:
        _global_failure_postmortem = FailurePostmortem()
    return _global_failure_postmortem


def reset_failure_postmortem() -> None:
    """重置全局 FailurePostmortem（仅用于测试）"""
    global _global_failure_postmortem
    _global_failure_postmortem = None

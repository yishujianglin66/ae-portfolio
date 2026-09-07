#!/usr/bin/env python3
"""
Agent 安全执行层 - SecurityManager v1.0

设计原则（基于 Runta 安全架构）：
1. 分级防护：按任务风险等级分配不同安全策略
2. 深度防御：多层安全检查（代码扫描、路径校验、权限控制）
3. 审计追踪：所有操作完整记录，不可篡改
4. 熔断机制：异常行为触发自动熔断
5. 失败安全：安全模块自身异常时默认拒绝

四大能力：
- 安全分级（Security Level）：SAFE / LOW / MEDIUM / HIGH / CRITICAL
- 行为审计（Audit Logging）：完整操作审计链
- 输出扫描（Output Scanning）：危险模式检测
- 熔断机制（Circuit Breaker）：违规阈值触发熔断

架构参考：
- OWASP Top 10
- NIST Cybersecurity Framework
- AWS Well-Architected Security Pillar
- Runta Agent Security Architecture
"""
import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# -----------------------------------------------------------------------------
# 弱 Token 集合 — 单一定义源（canonical source）
# -----------------------------------------------------------------------------
# 开发环境默认值，生产环境禁止使用。所有认证模块必须从此处 import，
# 禁止在业务代码中重复定义本地 WEAK_TOKENS。
# 合并自 web/integrator_api.py、puppet-automation/src/{api,mcp_gateway} 等历史定义，
# 取并集作为更严格的版本（任一历史弱 token 在所有模块中都会被识别为弱）。
WEAK_TOKENS = frozenset({
    "",
    "change-me",
    "change-me-in-production",
    "dev-token",
    "dev-token-change-me",
    "default-token",
    "integrator-token-change-me",
})


class SecurityLevel(Enum):
    """安全级别 — 任务风险分级"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionType(Enum):
    """权限类型"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EXECUTE = "file_execute"
    NETWORK_ACCESS = "network_access"
    SYSTEM_CALL = "system_call"
    PROCESS_CONTROL = "process_control"
    CONFIG_MODIFY = "config_modify"


@dataclass
class SecurityContext:
    """安全上下文 — 随任务传递的安全信息"""
    security_level: SecurityLevel = SecurityLevel.LOW
    required_permissions: List[PermissionType] = field(default_factory=list)
    sandbox_id: Optional[str] = None
    allowed_paths: List[str] = field(default_factory=list)
    max_execution_time_ms: Optional[int] = None
    max_memory_mb: Optional[int] = None


@dataclass
class AuditLogEntry:
    """审计日志条目 — 一旦创建不可修改"""
    timestamp: float
    workflow_id: str
    task_id: str
    task_type: str
    security_level: str
    action: str
    status: str
    input_hash: str = ""
    output_hash: str = ""
    duration_ms: float = 0.0
    resources_used: Dict[str, Any] = field(default_factory=dict)
    details: str = ""


@dataclass
class SecurityScanResult:
    """安全扫描结果"""
    passed: bool = True
    risk_level: str = "low"
    warnings: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    blocked_patterns: List[str] = field(default_factory=list)
    scan_duration_ms: float = 0.0


class SecurityManager:
    """安全管理器 — 统一的安全执行网关

    职责：
    1. 权限校验：检查任务是否具备所需权限
    2. 代码扫描：检测 JSX/Shell 等代码中的危险模式
    3. 路径校验：防止路径遍历攻击
    4. 审计日志：完整记录所有安全相关操作
    5. 熔断机制：违规次数超标时触发熔断
    """

    def __init__(self, default_security_level: SecurityLevel = SecurityLevel.LOW):
        self._default_level = default_security_level
        self._audit_logs: List[AuditLogEntry] = []
        self._violation_count = 0
        self._circuit_breaker_tripped = False
        self._circuit_breaker_threshold = 5
        self._dangerous_patterns = self._init_dangerous_patterns()

    def _init_dangerous_patterns(self) -> Dict[str, List[str]]:
        """初始化危险模式检测规则"""
        return {
            "jsx": [
                r'eval\s*\(',
                r'Function\s*\(',
                r'execCommand\s*\(',
                r'app\.system\.',
                r'File\(\s*["\'].*["\']\s*,\s*["\']w["\']',
                r'Folder\.fs\.',
                r'while\s*\(\s*true\s*\)',
                r'for\s*\([^)]*;;[^)]*\)',
                r'do\s*\{[^}]*\}\s*while\s*\(\s*true\s*\)',
                r'process\.env',
                r'child_process',
                r'fs\.',
                r'\$\(',
                r'\`[^`]*rm\s+-rf[^`]*\`',
                r'\`[^`]*format\s+[A-Z]:[^`]*\`',
                r'\`[^`]*del\s+/s/q[^`]*\`',
                r'\`[^`]*shutdown\s+/s[^`]*\`',
                r'\`[^`]*cat\s+/etc/passwd[^`]*\`',
                r'\`[^`]*cat\s+/etc/shadow[^`]*\`',
                r'\`[^`]*whoami[^`]*\`',
                r'\`[^`]*curl\s+[^`]*\`',
                r'\`[^`]*wget\s+[^`]*\`',
                r'\`[^`]*python\s+-c[^`]*\`',
                r'\`[^`]*bash\s+-c[^`]*\`',
                r'\`[^`]*sh\s+-c[^`]*\`',
                r'\`[^`]*cmd\s+/c[^`]*\`',
                r'rm\s+-rf',
                r'format\s+[A-Z]:',
                r'del\s+/s/q',
                r'reg\s+add',
                r'shutdown\s+/s',
                r'/etc/passwd',
                r'/etc/shadow',
                r'C:\\Windows\\System32',
                r'\\.\\.\\',
                r'\.\./',
                r'%2e%2e',
                r'Array\s*\(\s*\d{7,}',
                r'/\^\([^)]+\)\+\$/',
                r'function\s+\w+\s*\(\s*\)\s*\{[^}]*\1[^}]*\}',
                r'function\s+\w+\s*\([^)]*\)\s*\{[^}]*\w+\s*\(\s*\)[^}]*\}',
                r'C:\\\\Windows\\\\',
                r'C:\\\\System32\\\\',
            ],
            "shell": [
                r'rm\s+-rf',
                r'format\s+[A-Z]:',
                r'del\s+/s/q',
                r'reg\s+add',
                r'shutdown\s+/s',
                r'cat\s+/etc/passwd',
                r'cat\s+/etc/shadow',
                r'ls\s+-la',
                r'whoami',
                r'curl\s+',
                r'wget\s+',
                r'python\s+-c',
                r'bash\s+-c',
                r'sh\s+-c',
                r'cmd\s+/c',
            ],
            "path_traversal": [
                r'\.\./\.\./',
                r'%2e%2e%2f',
                r'\.\./',
                r'%2e%2e',
                r'\\.\\.\\',
                r'/etc/passwd',
                r'/etc/shadow',
                r'C:\\Windows\\System32',
                r'\boot\.ini',
                r'C:\\Windows\\',
                r'C:\\System32\\',
            ],
        }

    def check_permission(self, context: SecurityContext, required: PermissionType) -> bool:
        """检查权限

        Args:
            context: 安全上下文
            required: 需要的权限类型

        Returns:
            True 表示有权限，False 表示无权限
        """
        try:
            return required in context.required_permissions
        except Exception:
            return False

    def scan_code(self, code: str, code_type: str = "jsx") -> SecurityScanResult:
        """扫描代码中的危险模式

        Args:
            code: 待扫描的代码字符串
            code_type: 代码类型 ("jsx" / "shell_code")

        Returns:
            SecurityScanResult 扫描结果
        """
        result = SecurityScanResult(passed=True, risk_level="low")
        start_time = time.time()

        try:
            if not code:
                result.scan_duration_ms = (time.time() - start_time) * 1000
                return result

            if len(code) > 10000:
                result.passed = False
                result.risk_level = "high"
                result.violations.append(f"代码长度超限: {len(code)} 字符")
                result.scan_duration_ms = (time.time() - start_time) * 1000
                return result

            patterns = self._dangerous_patterns.get(code_type, [])
            for pattern in patterns:
                try:
                    matches = re.findall(pattern, code, re.IGNORECASE)
                    if matches:
                        result.passed = False
                        result.risk_level = "high"
                        result.blocked_patterns.append(pattern)
                        result.violations.append(
                            f"检测到危险模式: {pattern} (出现 {len(matches)} 次)"
                        )
                except re.error:
                    continue

        except Exception as e:
            result.passed = False
            result.risk_level = "critical"
            result.warnings.append(f"扫描过程异常: {str(e)}")

        result.scan_duration_ms = (time.time() - start_time) * 1000
        return result

    def scan_path(self, path: str, allowed_paths: List[str]) -> SecurityScanResult:
        """路径安全扫描 — 防止路径遍历

        Args:
            path: 待校验的路径
            allowed_paths: 允许访问的路径列表

        Returns:
            SecurityScanResult 扫描结果
        """
        result = SecurityScanResult(passed=True, risk_level="low")
        start_time = time.time()

        try:
            if not path:
                result.passed = False
                result.warnings.append("路径为空")
                result.scan_duration_ms = (time.time() - start_time) * 1000
                return result

            normalized_path = os.path.normpath(path)

            traversal_patterns = self._dangerous_patterns.get("path_traversal", [])
            for pattern in traversal_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    result.passed = False
                    result.risk_level = "high"
                    result.blocked_patterns.append(pattern)
                    result.violations.append(f"检测到路径遍历攻击: {pattern}")

            if allowed_paths:
                path_allowed = False
                abs_normalized = os.path.abspath(normalized_path)
                normalized_root = Path(abs_normalized)
                for allowed in allowed_paths:
                    abs_allowed = os.path.abspath(allowed)
                    root = Path(abs_allowed)
                    # M6 修复: 使用 is_relative_to 语义, 防止 startswith 前缀绕过
                    # (如 data/sandbox_evil 命中 data/sandbox 前缀)
                    if normalized_root == root or root in normalized_root.parents:
                        path_allowed = True
                        break
                if not path_allowed:
                    result.passed = False
                    result.risk_level = "high"
                    result.violations.append(
                        f"路径不在允许范围内: {normalized_path}"
                    )

        except Exception as e:
            result.passed = False
            result.risk_level = "critical"
            result.warnings.append(f"路径扫描异常: {str(e)}")

        result.scan_duration_ms = (time.time() - start_time) * 1000
        return result

    def log_audit(self, entry: AuditLogEntry) -> None:
        """记录审计日志 — 追加写入，不可修改

        Args:
            entry: 审计日志条目
        """
        try:
            self._audit_logs.append(entry)
            if entry.status == "denied":
                self._violation_count += 1
                if self._violation_count >= self._circuit_breaker_threshold:
                    self._circuit_breaker_tripped = True
        except Exception:
            pass

    def check_circuit_breaker(self) -> bool:
        """检查熔断器状态

        Returns:
            True 表示熔断已触发，应拒绝所有操作
        """
        return self._circuit_breaker_tripped

    def reset_circuit_breaker(self) -> None:
        """重置熔断器"""
        self._circuit_breaker_tripped = False
        self._violation_count = 0

    def get_audit_stats(self) -> Dict[str, Any]:
        """获取审计统计信息

        Returns:
            统计信息字典
        """
        try:
            by_action: Dict[str, int] = {}
            by_status: Dict[str, int] = {}

            for entry in self._audit_logs:
                by_action[entry.action] = by_action.get(entry.action, 0) + 1
                by_status[entry.status] = by_status.get(entry.status, 0) + 1

            return {
                "total_audits": len(self._audit_logs),
                "violation_count": self._violation_count,
                "circuit_breaker_tripped": self._circuit_breaker_tripped,
                "by_action": by_action,
                "by_status": by_status,
            }
        except Exception:
            return {
                "total_audits": 0,
                "violation_count": self._violation_count,
                "circuit_breaker_tripped": self._circuit_breaker_tripped,
                "by_action": {},
                "by_status": {},
            }

    def get_audit_logs(
        self,
        action: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """获取审计日志（支持过滤）

        Args:
            action: 按 action 过滤
            status: 按 status 过滤
            limit: 返回最大条数

        Returns:
            审计日志条目列表
        """
        try:
            logs = self._audit_logs
            if action:
                logs = [e for e in logs if e.action == action]
            if status:
                logs = [e for e in logs if e.status == status]
            return logs[-limit:]
        except Exception:
            return []

    @staticmethod
    def hash_content(content: str) -> str:
        """计算内容哈希（用于审计追踪）

        Args:
            content: 待哈希的内容字符串

        Returns:
            SHA-256 哈希前 32 位
        """
        try:
            if content is None:
                content = ""
            return hashlib.sha256(str(content).encode("utf-8")).hexdigest()[:32]
        except Exception:
            return "hash_error"


# -----------------------------------------------------------------------------
# 全局实例
# -----------------------------------------------------------------------------

_global_security_manager: Optional[SecurityManager] = None
_global_security_manager_lock = threading.Lock()


def get_security_manager() -> SecurityManager:
    """获取全局安全管理器单例

    Returns:
        SecurityManager 实例
    """
    global _global_security_manager
    # D8 修复: double-checked locking, 防止多线程首次调用创建多个实例
    if _global_security_manager is None:
        with _global_security_manager_lock:
            if _global_security_manager is None:
                _global_security_manager = SecurityManager()
    return _global_security_manager


def reset_security_manager() -> None:
    """重置全局安全管理器（仅用于测试）"""
    global _global_security_manager
    _global_security_manager = None


# -----------------------------------------------------------------------------
# Phase B: L1-L5 安全护栏（RiskGuard）
# -----------------------------------------------------------------------------
from enum import IntEnum
from pathlib import Path
from dataclasses import asdict
import asyncio
import inspect
import json
import logging
import tempfile
from typing import Awaitable, Callable, Tuple


class SecurityError(PermissionError):
    """安全护栏拒绝执行时抛出的异常。"""


class RiskLevel(IntEnum):
    """信通院 L1-L5 风险分级。"""
    L1_READONLY = 1
    L2_GENERATE = 2
    L3_OVERWRITE_SAFE = 3
    L4_DESTRUCTIVE = 4
    L5_EXTERNAL = 5


@dataclass
class RiskAssessment:
    """单任务风险评估结果。"""
    risk_level: RiskLevel
    reasons: List[str]
    requires_sandbox: bool
    requires_approval: bool
    requires_audit_chain: bool
    requires_second_confirm: bool
    allowed_paths: List[str] = field(default_factory=list)
    forbidden_paths: List[str] = field(default_factory=list)
    max_execution_time_ms: int = 300_000
    max_memory_mb: int = 4096


@dataclass
class ApprovalRequest:
    """人工审批请求。"""
    request_id: str
    task_id: str
    task_type: str
    risk_level: RiskLevel
    reasons: List[str]
    args_preview: Dict[str, Any]
    requested_at: float
    timeout_seconds: int = 300


@dataclass
class ApprovalResult:
    """人工审批结果。"""
    request_id: str
    approved: bool
    approver: str
    approved_at: float
    comment: str = ""
    second_confirmed: bool = False


class RiskAssessor:
    """基于任务类型、路径和操作关键词评估风险。"""
    # C1 修复: 补齐 TaskType 全部 29 个枚举成员映射,
    # 未覆盖的字符串类型默认 L3(fail-closed, 见 assess)。
    DEFAULT_RISK_MAP: Dict[str, RiskLevel] = {
        # L1 只读/纯感知
        "perception": RiskLevel.L1_READONLY,
        "style_classification": RiskLevel.L1_READONLY,
        "understanding": RiskLevel.L1_READONLY,
        "feature_extraction": RiskLevel.L1_READONLY,
        "planning": RiskLevel.L1_READONLY,
        "feedback": RiskLevel.L1_READONLY,
        # L2 生成/纯计算
        "param_mapping": RiskLevel.L2_GENERATE,
        "ae_compile": RiskLevel.L2_GENERATE,
        "jsx_generate": RiskLevel.L2_GENERATE,
        "cache_write": RiskLevel.L2_GENERATE,
        "pr_import": RiskLevel.L2_GENERATE,
        "whisper_subtitle": RiskLevel.L2_GENERATE,
        "sub_workflow": RiskLevel.L2_GENERATE,  # 子任务各自评估
        # L3 可能覆盖文件(白名单沙箱保护)
        "ae_execute": RiskLevel.L3_OVERWRITE_SAFE,
        "ffmpeg_transcode": RiskLevel.L3_OVERWRITE_SAFE,
        "davinci_grade": RiskLevel.L3_OVERWRITE_SAFE,
        "silhouette_roto": RiskLevel.L3_OVERWRITE_SAFE,
        "silhouette_track": RiskLevel.L3_OVERWRITE_SAFE,
        "silhouette_paint": RiskLevel.L3_OVERWRITE_SAFE,
        "pr_edit": RiskLevel.L3_OVERWRITE_SAFE,
        "pr_transition": RiskLevel.L3_OVERWRITE_SAFE,
        "ps_preprocess": RiskLevel.L3_OVERWRITE_SAFE,
        "c4d_mograph": RiskLevel.L3_OVERWRITE_SAFE,
        # L4 破坏性/不可逆
        "ae_render": RiskLevel.L4_DESTRUCTIVE,
        "ffmpeg_export": RiskLevel.L4_DESTRUCTIVE,
        "pr_export": RiskLevel.L4_DESTRUCTIVE,
        "blender_render": RiskLevel.L4_DESTRUCTIVE,
        "topaz_enhance": RiskLevel.L4_DESTRUCTIVE,
        "ame_encode": RiskLevel.L4_DESTRUCTIVE,
        "file_delete": RiskLevel.L4_DESTRUCTIVE,
        # L5 外部调用/付费
        "external_api_call": RiskLevel.L5_EXTERNAL,
        "cloud_render_submit": RiskLevel.L5_EXTERNAL,
        "stock_purchase": RiskLevel.L5_EXTERNAL,
        "runway_generate": RiskLevel.L5_EXTERNAL,
        "pika_generate": RiskLevel.L5_EXTERNAL,
        "flux3_generate": RiskLevel.L5_EXTERNAL,
        # H3 付费生成类(按秒/次计费, 统一 L5)
        "video_generation": RiskLevel.L5_EXTERNAL,
        "video_editing": RiskLevel.L5_EXTERNAL,
        "image_generation": RiskLevel.L5_EXTERNAL,
        "subtitle_modification": RiskLevel.L3_OVERWRITE_SAFE,
        "style_transfer": RiskLevel.L5_EXTERNAL,
        "motion_transfer": RiskLevel.L5_EXTERNAL,
        "object_replacement": RiskLevel.L5_EXTERNAL,
        "scene_alteration": RiskLevel.L5_EXTERNAL,
        "rate_adjustment": RiskLevel.L5_EXTERNAL,
        "inpainting": RiskLevel.L5_EXTERNAL,
        "minimax_h3_generate": RiskLevel.L5_EXTERNAL,
    }
    USER_DATA_PATTERNS = ("data/user_materials/", "data/input/", "output/final/")
    # M3 修复: 关键字检测限定到"动作类"键, 不匹配任意字符串参数
    ACTION_KEY_NAMES = ("action", "operation", "command", "mode", "op", "verb", "type")
    DANGEROUS_WORDS = (
        "delete", "remove", "overwrite", "truncate",
        "format", "wipe", "purge", "unlink", "drop",
        "shutdown", "reformat", "erase", "reset",
    )
    PAYMENT_WORDS = ("pay", "purchase", "subscribe")
    # 纯文件名(无路径分隔符)也视为可疑文件路径
    _FILENAME_RE = re.compile(r"^[^\s/\\]{1,200}$")
    _EXT_SUFFIX_RE = re.compile(r"\.(env|ini|cfg|json|txt|log|yaml|yml|py|js|jsx|mov|mp4|aep|psd|png|jpg|jpeg|mp3|wav|aif|exr|dpx|xml|csv|zip|tar|gz)$", re.IGNORECASE)

    def __init__(self, workspace_root: Optional[Path] = None):
        self._workspace = Path(workspace_root or Path.cwd())
        self._logger = logging.getLogger(f"{__name__}.RiskAssessor")

    def assess(self, task_type: str, task_args: Dict[str, Any]) -> RiskAssessment:
        # C1(b) 修复: 未知类型默认 L3(fail-closed), 不再默认 L2。
        if task_type in self.DEFAULT_RISK_MAP:
            level = self.DEFAULT_RISK_MAP[task_type]
        else:
            level = RiskLevel.L3_OVERWRITE_SAFE
            reasons = [f"task_type={task_type} -> unknown, defaulted_to_L3"]
            reasons.append("unknown_task_type_defaulted_to_L3")
            return self._build_assessment(level, reasons, task_args)
        reasons = [f"task_type={task_type} -> L{level.value}"]
        return self._build_assessment(level, reasons, task_args)

    def _build_assessment(self, level: RiskLevel, reasons: List[str], task_args: Dict[str, Any]) -> RiskAssessment:
        """评估辅助: 叠加路径/动作/付费信号后构造最终 RiskAssessment。"""
        paths = self._extract_paths(task_args or {})
        user_hits = [p for p in paths if self._is_user_data(p)]
        # H1 修复: 区分读写——只读任务(L1/L2)触及素材升级 L3(只读防护),
        # 写级任务(L3+)触及素材升级 L4。
        if user_hits:
            if level >= RiskLevel.L3_OVERWRITE_SAFE:
                level = RiskLevel.L4_DESTRUCTIVE
                reasons.append(f"触及用户素材(写级任务): {user_hits}")
            else:
                level = RiskLevel.L3_OVERWRITE_SAFE
                reasons.append(f"触及用户素材(只读防护): {user_hits}")
        # M3 修复: 关键字检测只作用于"动作类"键值 + 布尔键名, 不再对整串子串匹配。
        if self._has_destructive_intent(task_args):
            if level < RiskLevel.L4_DESTRUCTIVE:
                level = RiskLevel.L4_DESTRUCTIVE
                reasons.append("检测到 delete/overwrite 关键字")
        if self._has_payment_intent(task_args):
            if level < RiskLevel.L5_EXTERNAL:
                level = RiskLevel.L5_EXTERNAL
                reasons.append("检测到付费操作")
        return RiskAssessment(
            risk_level=level,
            reasons=reasons,
            requires_sandbox=level >= RiskLevel.L3_OVERWRITE_SAFE,
            requires_approval=level >= RiskLevel.L4_DESTRUCTIVE,
            requires_audit_chain=level >= RiskLevel.L4_DESTRUCTIVE,
            requires_second_confirm=level >= RiskLevel.L5_EXTERNAL,
            allowed_paths=paths,
        )

    @classmethod
    def _has_destructive_intent(cls, task_args: Any) -> bool:
        """检测破坏性动作意图(限定动作类键 + 布尔键名声明)。"""
        if isinstance(task_args, dict):
            for key, value in task_args.items():
                key_lower = str(key).lower()
                if isinstance(value, bool) and any(w in key_lower for w in ("delete", "overwrite")):
                    # 布尔值键名本身就是意图声明(如 {"delete": True})
                    return True
                if key_lower in cls.ACTION_KEY_NAMES:
                    if cls._word_match(str(value)):
                        return True
            # 顶层字符串值也视为动作声明(如直接传 "delete")
            for value in task_args.values():
                if isinstance(value, str) and cls._word_match(value):
                    return True
        elif isinstance(task_args, str) and cls._word_match(task_args):
            return True
        return False

    @classmethod
    def _has_payment_intent(cls, task_args: Any) -> bool:
        """检测付费操作意图(动作类键)。"""
        if isinstance(task_args, dict):
            for key, value in task_args.items():
                if str(key).lower() in cls.ACTION_KEY_NAMES and isinstance(value, str):
                    lowered = value.lower()
                    if any(w in lowered for w in cls.PAYMENT_WORDS):
                        return True
            for value in task_args.values():
                if isinstance(value, str):
                    lowered = value.lower()
                    if any(w in lowered for w in cls.PAYMENT_WORDS):
                        return True
        elif isinstance(task_args, str) and any(w in task_args.lower() for w in cls.PAYMENT_WORDS):
            return True
        return False

    @classmethod
    def _word_match(cls, text: str) -> bool:
        """按词边界匹配危险词, 避免 delete_me.mp4 之类的误报。"""
        lowered = text.lower()
        for word in cls.DANGEROUS_WORDS:
            start = 0
            while True:
                idx = lowered.find(word, start)
                if idx == -1:
                    break
                before = idx == 0 or not lowered[idx - 1].isalnum() and lowered[idx - 1] != "_"
                after = idx + len(word) >= len(lowered) or (
                    not lowered[idx + len(word)].isalnum() and lowered[idx + len(word)] != "_"
                )
                if before and after:
                    return True
                start = idx + 1
        return False

    @classmethod
    def _extract_paths(cls, args: Any) -> List[str]:
        """C2(a) 修复: 递归提取所有 str / pathlib.Path 值(含嵌套 dict/list/tuple)。

        提取规则:
        - pathlib.Path 对象一律转 str;
        - 含路径分隔符(/ 或 \\)的字符串;
        - 纯文件名(如 ".env" / "secret.txt" / "delete_me.mp4")作为可疑文件路径提取。
        """
        paths: List[str] = []
        seen: set[str] = set()

        def _looks_like_path(text: str) -> bool:
            if "/" in text or "\\" in text:
                return True
            if text.startswith("."):  # .env / .gitignore 等隐藏文件
                return True
            if cls._EXT_SUFFIX_RE.search(text) and cls._FILENAME_RE.match(text):
                return True
            return False

        def _walk(value: Any) -> None:
            if isinstance(value, Path):
                text = str(value)
            elif isinstance(value, str):
                text = value
            else:
                if isinstance(value, dict):
                    for v in value.values():
                        _walk(v)
                elif isinstance(value, (list, tuple, set)):
                    for v in value:
                        _walk(v)
                return
            if text in seen or not _looks_like_path(text):
                return
            seen.add(text)
            paths.append(text)

        _walk(args)
        return paths

    def _is_user_data(self, path: str) -> bool:
        normalized = path.replace("\\", "/").lower()
        return any(pattern in normalized for pattern in self.USER_DATA_PATTERNS)


class SandboxPolicy:
    """L3+ 文件白名单沙箱策略。"""
    def __init__(self, workspace_root: Path):
        self._workspace = Path(workspace_root).resolve()
        self._allowed_roots = [
            self._workspace / "data" / "sandbox",
            self._workspace / "output" / "temp",
            self._workspace / "data" / "cache",
            self._workspace / "output" / "h3_downloads",
            self._workspace / "data" / "h3_cache",
        ]
        self._forbidden_patterns = ("*.aep", ".env")
        self._resource_limits = {"max_execution_time_ms": 300_000, "max_memory_mb": 4096, "max_cpu_percent": 80}
        self._logger = logging.getLogger(f"{__name__}.SandboxPolicy")

    def validate_paths(self, paths: List[str]) -> Tuple[bool, List[str]]:
        violations: List[str] = []
        roots = [root.resolve() for root in self._allowed_roots]
        for raw_path in paths:
            path = Path(raw_path).resolve()
            in_whitelist = any(path == root or root in path.parents for root in roots)
            normalized = path.as_posix().lower()
            in_blacklist = path.match("*.aep") or path.name.lower() == ".env" or "/output/final/" in normalized
            if not in_whitelist or in_blacklist:
                violations.append(raw_path)
        return not violations, violations

    async def wrap_execution(self, task_fn: Callable[..., Any], task_args: Dict[str, Any], assessment: RiskAssessment) -> Any:
        """C2(b/c/d) 修复: 路径级沙箱包装。

        - 无路径参数的 L3 任务(纯计算)记录 debug 后放行, 不进沙箱路径校验;
        - 存在路径参数时全部校验, 违规即拒绝(保留原拒绝语义);
        - 创建临时目录并注入 ``sandbox_dir`` 到任务参数, 任务函数可感知;
        - 临时目录在 with 块结束自动清理。

        注意: 当前为路径级沙箱, 进程级资源限制未启用
        (``_resource_limits`` 字段保留, 仅作为后续扩展占位)。
        """
        extracted = list(assessment.allowed_paths or [])
        if not extracted:
            self._logger.debug(
                "L3+ 任务无路径参数，按纯计算处理，跳过沙箱路径校验"
            )
        else:
            passed, violations = self.validate_paths(extracted)
            if not passed:
                raise SecurityError(f"沙箱路径校验失败，违规路径: {violations}")
        with tempfile.TemporaryDirectory(prefix="aekv_sandbox_") as tmpdir:
            task_args = dict(task_args or {})
            task_args.setdefault("sandbox_dir", str(tmpdir))
            result = task_fn(**task_args)
            return await result if inspect.isawaitable(result) else result


class ApprovalPolicy:
    """L4/L5 人工审批策略。"""
    def __init__(self, callback: Optional[Callable[[ApprovalRequest], Awaitable[ApprovalResult]]] = None):
        self._callback = callback or self._default_callback
        self._logger = logging.getLogger(f"{__name__}.ApprovalPolicy")

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """H4(a) 修复: 审批带超时, 超时按拒绝处理, 不永久挂起。"""
        try:
            return await asyncio.wait_for(
                self._callback(request),
                timeout=request.timeout_seconds,
            )
        except asyncio.TimeoutError:
            self._logger.warning(
                f"审批超时: request_id={request.request_id}, "
                f"timeout={request.timeout_seconds}s"
            )
            return ApprovalResult(
                request.request_id,
                False,
                "system",
                time.time(),
                "审批超时",
            )

    @staticmethod
    async def _default_callback(request: ApprovalRequest) -> ApprovalResult:
        return ApprovalResult(request.request_id, False, "system", time.time(), "未配置审批回调")


# H2 修复: 模块级共享锁(按日志文件绝对路径 key, 进程内单例)。
# 不同 AuditChain 实例(如每个 WorkflowOrchestrator 各建一个)并发写
# 同一文件时共享同一把锁, 避免交错写入破坏哈希链。
_AUDIT_CHAIN_LOCKS: Dict[str, threading.Lock] = {}
_AUDIT_CHAIN_LOCKS_GUARD = threading.Lock()


def _audit_chain_lock_for(path: Path) -> threading.Lock:
    """按日志文件绝对路径获取进程内共享锁。"""
    key = str(Path(path).resolve())
    with _AUDIT_CHAIN_LOCKS_GUARD:
        lock = _AUDIT_CHAIN_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _AUDIT_CHAIN_LOCKS[key] = lock
        return lock


class AuditChain:
    """追加式 SHA-256 审计哈希链。

    防篡改能力边界(M4):
    - 可检测链内部不一致(prev_hash / current_hash 不匹配)与单条记录修改;
    - 可检测尾部被截断/删除(与实例最后写入哈希比对, 或显式传入
      ``expect_last_hash`` 锚点);
    - 无法防止"整体截断 + 伪造完整重写", 需要外部锚点(如定期归档保存
      尾部哈希到外部只读存储)。
    """

    def __init__(self, log_path: Path):
        self._path = Path(log_path)
        self._logger = logging.getLogger(f"{__name__}.AuditChain")
        self._parse_failed = False
        # H2 修复: 构造时缓存仅作初始化快照, append 前会重新读取文件尾部
        self._prev_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        """读取文件末尾一条记录的 current_hash(解析失败置标志并告警)。"""
        if not self._path.exists():
            return "0" * 64
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            if not lines:
                return "0" * 64
            record = json.loads(lines[-1])
            return record.get("current_hash", "0" * 64)
        except (OSError, ValueError, TypeError) as exc:
            # M5 修复: 解析失败不再静默回退, 置标志供 verify_chain 提示
            self._parse_failed = True
            self._logger.warning(f"审计链上次哈希解析失败: {exc}")
            return "0" * 64

    @staticmethod
    def _hash(prev_hash: str, entry: Dict[str, Any], timestamp: float) -> str:
        canonical_entry = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload = f"{prev_hash}|{canonical_entry}|{timestamp}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _read_tail_hash(self) -> str:
        """append 前重新读取文件尾部 current_hash, 不依赖构造时缓存。"""
        if not self._path.exists():
            return "0" * 64
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            if not lines:
                return "0" * 64
            record = json.loads(lines[-1])
            return record.get("current_hash", "0" * 64)
        except (OSError, ValueError, TypeError) as exc:
            self._parse_failed = True
            self._logger.warning(f"审计链尾部哈希读取失败: {exc}")
            return "0" * 64

    def append(self, entry: AuditLogEntry) -> str:
        with _audit_chain_lock_for(self._path):
            timestamp = time.time()
            entry_data = asdict(entry) if hasattr(entry, "__dataclass_fields__") else dict(entry)
            prev_hash = self._read_tail_hash()
            current_hash = self._hash(prev_hash, entry_data, timestamp)
            record = {"entry": entry_data, "prev_hash": prev_hash, "current_hash": current_hash, "timestamp": timestamp}
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            self._prev_hash = current_hash
            return current_hash

    def verify_chain(self, expect_last_hash: Optional[str] = None) -> Tuple[bool, List[str]]:
        """M4 修复: 校验链完整性, 并区分文件缺失 / 空文件 / 截断。

        Args:
            expect_last_hash: 期望的尾部哈希锚点(外部保存), 提供时额外校验。

        Returns:
            (链是否完整, 违规/标注列表)。文件不存在视为违规(fail-closed)。
        """
        if not self._path.exists():
            return False, ["audit_chain 文件不存在"]
        violations: List[str] = []
        previous = "0" * 64
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            return False, [f"audit_chain 读取失败: {exc}"]
        lines = text.splitlines()
        if not lines:
            # 空文件视为合法链(标注)
            self._logger.info(f"审计链为空文件: {self._path}")
            return True, []
        current_hashes: set[str] = set()
        for line_number, line in enumerate(lines, 1):
            try:
                record = json.loads(line)
                if record["prev_hash"] != previous:
                    violations.append(f"行 {line_number}: prev_hash 不匹配")
                expected = self._hash(record["prev_hash"], record["entry"], record["timestamp"])
                if expected != record["current_hash"]:
                    violations.append(f"行 {line_number}: current_hash 不匹配")
                previous = record["current_hash"]
                current_hashes.add(previous)
            except (KeyError, TypeError, ValueError) as exc:
                violations.append(f"行 {line_number}: 解析失败 - {exc}")
        if self._parse_failed:
            violations.append("上次解析失败，链可能不完整")
        # M4(b): 尾部哈希与实例最后写入哈希比对。仅当实例缓存哈希已不在链中
        # 才判定为截断/删除——若其他实例继续追加, 缓存哈希仍是链中合法记录。
        if previous != self._prev_hash and self._prev_hash not in current_hashes:
            violations.append("文件尾部哈希与实例记录不一致(可能被截断/删除)")
        if expect_last_hash is not None and previous != expect_last_hash:
            violations.append("文件尾部哈希与期望值不一致")
        return not violations, violations

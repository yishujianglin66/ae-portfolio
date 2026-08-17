"""core.security 单元测试 - SecurityManager 安全执行网关

覆盖范围（高优先级缺口）：
- 权限校验（grant/deny/fail-closed）
- JSX/Shell 危险代码模式扫描（eval, exec, path traversal）
- 路径遍历攻击防御（../, %2e, Windows 路径）
- 审计日志不可篡改 + 过滤
- 熔断器阈值触发
- 内容哈希用于审计追踪
- 单例 / 重置隔离
"""
from __future__ import annotations

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.security import (
    SecurityLevel,
    PermissionType,
    SecurityContext,
    AuditLogEntry,
    SecurityScanResult,
    SecurityManager,
    get_security_manager,
    reset_security_manager,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def security_manager():
    """每个测试独立获取新实例"""
    reset_security_manager()
    return get_security_manager()


@pytest.fixture(autouse=True)
def _reset_global_singleton():
    """每个测试后重置全局单例，避免测试间污染"""
    yield
    reset_security_manager()


# ============================================================
# 枚举与数据类测试
# ============================================================


class TestEnums:
    def test_security_level_values(self):
        assert SecurityLevel.SAFE.value == "safe"
        assert SecurityLevel.LOW.value == "low"
        assert SecurityLevel.MEDIUM.value == "medium"
        assert SecurityLevel.HIGH.value == "high"
        assert SecurityLevel.CRITICAL.value == "critical"

    def test_permission_type_values(self):
        # 验证所有权限类型都已定义
        for perm in (
            PermissionType.FILE_READ,
            PermissionType.FILE_WRITE,
            PermissionType.FILE_EXECUTE,
            PermissionType.NETWORK_ACCESS,
            PermissionType.SYSTEM_CALL,
            PermissionType.PROCESS_CONTROL,
            PermissionType.CONFIG_MODIFY,
        ):
            assert perm.value is not None


class TestSecurityContext:
    def test_default_values(self):
        ctx = SecurityContext()
        assert ctx.security_level == SecurityLevel.LOW
        assert ctx.required_permissions == []
        assert ctx.sandbox_id is None
        assert ctx.allowed_paths == []
        assert ctx.max_execution_time_ms is None
        assert ctx.max_memory_mb is None

    def test_custom_values(self):
        ctx = SecurityContext(
            security_level=SecurityLevel.HIGH,
            required_permissions=[PermissionType.FILE_READ, PermissionType.NETWORK_ACCESS],
            sandbox_id="sb-001",
            allowed_paths=["/tmp", "/data"],
            max_execution_time_ms=5000,
            max_memory_mb=1024,
        )
        assert ctx.security_level == SecurityLevel.HIGH
        assert PermissionType.FILE_READ in ctx.required_permissions
        assert ctx.sandbox_id == "sb-001"
        assert ctx.max_execution_time_ms == 5000


# ============================================================
# 权限校验 — 业务关键
# ============================================================


class TestCheckPermission:
    def test_granted_permission_returns_true(self, security_manager):
        ctx = SecurityContext(
            required_permissions=[PermissionType.FILE_READ, PermissionType.FILE_WRITE]
        )
        assert security_manager.check_permission(ctx, PermissionType.FILE_READ) is True
        assert security_manager.check_permission(ctx, PermissionType.FILE_WRITE) is True

    def test_missing_permission_returns_false(self, security_manager):
        ctx = SecurityContext(required_permissions=[PermissionType.FILE_READ])
        assert security_manager.check_permission(ctx, PermissionType.FILE_WRITE) is False
        assert security_manager.check_permission(ctx, PermissionType.NETWORK_ACCESS) is False

    def test_empty_context_returns_false(self, security_manager):
        ctx = SecurityContext()
        assert security_manager.check_permission(ctx, PermissionType.FILE_READ) is False

    def test_fail_closed_on_exception(self, security_manager):
        """如果权限检查自身异常，必须默认拒绝（fail-closed）"""
        # 构造一个会导致异常的 context（None 不在 required_permissions 中，但用魔法值触发）
        class BadContext:
            required_permissions = None

        # 权限检查应该捕获异常并返回 False
        result = security_manager.check_permission(BadContext(), PermissionType.FILE_READ)
        assert result is False


# ============================================================
# JSX 危险代码扫描 — 业务关键
# ============================================================


class TestScanCodeJsx:
    def test_safe_code_passes(self, security_manager):
        code = "var comp = app.project.activeItem; var layer = comp.selectedLayers[0];"
        result = security_manager.scan_code(code, "jsx")
        assert result.passed is True
        assert result.violations == []
        assert result.risk_level == "low"

    def test_empty_code_passes(self, security_manager):
        result = security_manager.scan_code("", "jsx")
        assert result.passed is True

    def test_eval_blocked(self, security_manager):
        code = "var x = eval('alert(1)');"
        result = security_manager.scan_code(code, "jsx")
        assert result.passed is False
        assert result.risk_level == "high"
        assert any("eval" in v for v in result.violations)

    def test_function_constructor_blocked(self, security_manager):
        code = "var f = new Function('return 1');"
        result = security_manager.scan_code(code, "jsx")
        assert result.passed is False

    def test_system_call_blocked(self, security_manager):
        code = "app.system('rm -rf /');"
        result = security_manager.scan_code(code, "jsx")
        assert result.passed is False

    def test_while_true_blocked(self, security_manager):
        code = "while (true) { doSomething(); }"
        result = security_manager.scan_code(code, "jsx")
        assert result.passed is False

    def test_shell_command_in_backticks_blocked(self, security_manager):
        code = "var x = `rm -rf /`;"
        result = security_manager.scan_code(code, "jsx")
        assert result.passed is False

    def test_path_traversal_in_code_blocked(self, security_manager):
        code = "var path = '../../etc/passwd';"
        result = security_manager.scan_code(code, "jsx")
        assert result.passed is False

    def test_oversized_code_blocked(self, security_manager):
        """超过 10000 字符直接拒绝"""
        code = "var x = 1;\n" * 5000  # ~60000 字符
        result = security_manager.scan_code(code, "jsx")
        assert result.passed is False
        assert result.risk_level == "high"
        assert any("长度超限" in v for v in result.violations)

    def test_scan_duration_recorded(self, security_manager):
        result = security_manager.scan_code("var x = 1;", "jsx")
        assert result.scan_duration_ms >= 0


# ============================================================
# Shell 危险命令扫描
# ============================================================


class TestScanCodeShell:
    def test_safe_shell_passes(self, security_manager):
        code = "echo 'hello world'"
        result = security_manager.scan_code(code, "shell")
        assert result.passed is True

    def test_rm_rf_blocked(self, security_manager):
        code = "rm -rf /var/data"
        result = security_manager.scan_code(code, "shell")
        assert result.passed is False

    def test_format_command_blocked(self, security_manager):
        code = "format C:"
        result = security_manager.scan_code(code, "shell")
        assert result.passed is False

    def test_etc_passwd_blocked(self, security_manager):
        code = "cat /etc/passwd"
        result = security_manager.scan_code(code, "shell")
        assert result.passed is False

    def test_bash_c_blocked(self, security_manager):
        code = "bash -c 'malicious code'"
        result = security_manager.scan_code(code, "shell")
        assert result.passed is False

    def test_unknown_code_type_returns_empty_patterns(self, security_manager):
        """未知 code_type 不会报错，但也不会扫描出任何违规"""
        result = security_manager.scan_code("eval(1)", "unknown_type")
        assert result.passed is True


# ============================================================
# 路径遍历攻击防护 — 业务关键
# ============================================================


class TestScanPath:
    def test_safe_path_passes(self, security_manager):
        result = security_manager.scan_path("/tmp/test.txt", [])
        assert result.passed is True

    def test_empty_path_fails(self, security_manager):
        result = security_manager.scan_path("", [])
        assert result.passed is False
        assert any("路径为空" in w for w in result.warnings)

    def test_path_traversal_dotdot_blocked(self, security_manager):
        result = security_manager.scan_path("../../etc/passwd", [])
        assert result.passed is False
        assert result.risk_level == "high"

    def test_url_encoded_traversal_blocked(self, security_manager):
        result = security_manager.scan_path("%2e%2e%2fpasswd", [])
        assert result.passed is False

    def test_windows_path_blocked(self, security_manager):
        result = security_manager.scan_path("C:\\Windows\\System32\\cmd.exe", [])
        assert result.passed is False

    def test_etc_passwd_blocked(self, security_manager):
        result = security_manager.scan_path("/etc/passwd", [])
        assert result.passed is False

    def test_url_encoded_passwd_blocked(self, security_manager):
        """%2e%2e 模式应被检测"""
        result = security_manager.scan_path("%2e%2e%2f", [])
        assert result.passed is False

    def test_path_within_allowed_paths(self, security_manager, tmp_path):
        """路径在允许范围内通过校验"""
        safe_dir = str(tmp_path)
        safe_file = os.path.join(safe_dir, "data.txt")
        result = security_manager.scan_path(safe_file, [safe_dir])
        assert result.passed is True

    def test_path_outside_allowed_paths_blocked(self, security_manager, tmp_path):
        """路径不在允许范围内被阻止"""
        allowed = str(tmp_path / "allowed")
        forbidden = str(tmp_path / "forbidden" / "data.txt")
        os.makedirs(allowed, exist_ok=True)
        os.makedirs(os.path.dirname(forbidden), exist_ok=True)

        result = security_manager.scan_path(forbidden, [allowed])
        assert result.passed is False
        assert any("不在允许范围内" in v for v in result.violations)

    def test_scan_path_none_returns_not_passed(self, security_manager):
        """None 输入应被拒绝（不会崩溃）"""
        result = security_manager.scan_path(None, [])
        assert result.passed is False
        # 风险等级可能是 low（空路径分支）或 critical（异常分支），两者都合理


# ============================================================
# 审计日志 — 不可篡改
# ============================================================


class TestAuditLog:
    def test_log_entry_creation(self):
        entry = AuditLogEntry(
            timestamp=1234567890.0,
            workflow_id="wf-1",
            task_id="t-1",
            task_type="ae_compile",
            security_level="low",
            action="execute",
            status="allowed",
        )
        assert entry.workflow_id == "wf-1"
        assert entry.status == "allowed"
        assert entry.input_hash == ""
        assert entry.output_hash == ""
        assert entry.duration_ms == 0.0

    def test_log_audit_appends(self, security_manager):
        entry = AuditLogEntry(
            timestamp=1.0,
            workflow_id="wf-1",
            task_id="t-1",
            task_type="test",
            security_level="low",
            action="x",
            status="allowed",
        )
        security_manager.log_audit(entry)
        logs = security_manager.get_audit_logs()
        assert len(logs) == 1
        assert logs[0].workflow_id == "wf-1"

    def test_log_audit_failed_does_not_raise(self, security_manager):
        """日志记录失败不应中断主流程"""
        # 通过传递一个非法 entry 测试（构造一个 dataclass 字段异常的对象）
        class BadEntry:
            pass

        # 不应抛异常
        security_manager.log_audit(BadEntry())  # type: ignore[arg-type]

    def test_get_audit_logs_filter_by_action(self, security_manager):
        for action in ["compile", "execute", "compile", "render"]:
            security_manager.log_audit(AuditLogEntry(
                timestamp=1.0, workflow_id="w", task_id="t",
                task_type="x", security_level="low",
                action=action, status="allowed",
            ))

        logs = security_manager.get_audit_logs(action="compile")
        assert len(logs) == 2
        assert all(e.action == "compile" for e in logs)

    def test_get_audit_logs_filter_by_status(self, security_manager):
        for status in ["allowed", "denied", "allowed", "error"]:
            security_manager.log_audit(AuditLogEntry(
                timestamp=1.0, workflow_id="w", task_id="t",
                task_type="x", security_level="low",
                action="x", status=status,
            ))

        logs = security_manager.get_audit_logs(status="allowed")
        assert len(logs) == 2
        assert all(e.status == "allowed" for e in logs)

    def test_get_audit_logs_limit(self, security_manager):
        for i in range(20):
            security_manager.log_audit(AuditLogEntry(
                timestamp=float(i), workflow_id="w", task_id=f"t-{i}",
                task_type="x", security_level="low",
                action="x", status="allowed",
            ))

        logs = security_manager.get_audit_logs(limit=5)
        assert len(logs) == 5
        # 应返回最近 5 条
        assert logs[-1].task_id == "t-19"

    def test_get_audit_stats(self, security_manager):
        security_manager.log_audit(AuditLogEntry(
            timestamp=1.0, workflow_id="w", task_id="t",
            task_type="x", security_level="low",
            action="compile", status="allowed",
        ))
        security_manager.log_audit(AuditLogEntry(
            timestamp=2.0, workflow_id="w", task_id="t",
            task_type="x", security_level="low",
            action="execute", status="denied",
        ))

        stats = security_manager.get_audit_stats()
        assert stats["total_audits"] == 2
        assert stats["by_action"]["compile"] == 1
        assert stats["by_action"]["execute"] == 1
        assert stats["by_status"]["allowed"] == 1
        assert stats["by_status"]["denied"] == 1
        assert stats["violation_count"] == 1
        assert stats["circuit_breaker_tripped"] is False


# ============================================================
# 熔断器 — 关键安全机制
# ============================================================


class TestCircuitBreaker:
    def test_initial_state_not_tripped(self, security_manager):
        assert security_manager.check_circuit_breaker() is False

    def test_circuit_breaker_trips_after_threshold(self, security_manager):
        """超过阈值（5）次 denied 后触发熔断"""
        threshold = security_manager._circuit_breaker_threshold
        for i in range(threshold):
            security_manager.log_audit(AuditLogEntry(
                timestamp=float(i), workflow_id="w", task_id="t",
                task_type="x", security_level="low",
                action="x", status="denied",
            ))

        assert security_manager.check_circuit_breaker() is True

    def test_circuit_breaker_not_tripped_by_allowed(self, security_manager):
        """allowed 状态不应计入违规"""
        for i in range(20):
            security_manager.log_audit(AuditLogEntry(
                timestamp=float(i), workflow_id="w", task_id="t",
                task_type="x", security_level="low",
                action="x", status="allowed",
            ))

        assert security_manager.check_circuit_breaker() is False

    def test_reset_circuit_breaker(self, security_manager):
        """重置熔断器应清除违规计数并取消熔断"""
        for i in range(10):
            security_manager.log_audit(AuditLogEntry(
                timestamp=float(i), workflow_id="w", task_id="t",
                task_type="x", security_level="low",
                action="x", status="denied",
            ))

        assert security_manager.check_circuit_breaker() is True

        security_manager.reset_circuit_breaker()
        assert security_manager.check_circuit_breaker() is False
        assert security_manager._violation_count == 0


# ============================================================
# 内容哈希 — 审计追踪
# ============================================================


class TestHashContent:
    def test_hash_returns_32_chars(self):
        h = SecurityManager.hash_content("hello world")
        assert len(h) == 32

    def test_hash_deterministic(self):
        h1 = SecurityManager.hash_content("test content")
        h2 = SecurityManager.hash_content("test content")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = SecurityManager.hash_content("content A")
        h2 = SecurityManager.hash_content("content B")
        assert h1 != h2

    def test_hash_none_input(self):
        """None 输入应安全处理"""
        h = SecurityManager.hash_content(None)
        assert len(h) == 32
        # 与空字符串哈希应一致
        h_empty = SecurityManager.hash_content("")
        assert h == h_empty

    def test_hash_non_string_input(self):
        """非字符串输入应安全处理"""
        h = SecurityManager.hash_content(12345)
        assert len(h) == 32

    def test_unicode_content(self):
        h = SecurityManager.hash_content("中文测试 战吼 🎬")
        assert len(h) == 32


# ============================================================
# 全局单例
# ============================================================


class TestSingleton:
    def test_singleton_returns_same_instance(self):
        reset_security_manager()
        m1 = get_security_manager()
        m2 = get_security_manager()
        assert m1 is m2

    def test_reset_creates_new_instance(self):
        m1 = get_security_manager()
        reset_security_manager()
        m2 = get_security_manager()
        assert m1 is not m2

    def test_singleton_preserves_state(self):
        """单例状态应在多次获取间保留"""
        m1 = get_security_manager()
        m1.log_audit(AuditLogEntry(
            timestamp=1.0, workflow_id="w", task_id="t",
            task_type="x", security_level="low",
            action="x", status="allowed",
        ))
        m2 = get_security_manager()
        assert len(m2.get_audit_logs()) == 1


# ============================================================
# 自定义安全级别
# ============================================================


class TestCustomSecurityLevel:
    def test_custom_default_level(self):
        mgr = SecurityManager(default_security_level=SecurityLevel.HIGH)
        assert mgr._default_level == SecurityLevel.HIGH

    def test_dangerous_patterns_initialized(self):
        mgr = SecurityManager()
        assert "jsx" in mgr._dangerous_patterns
        assert "shell" in mgr._dangerous_patterns
        assert "path_traversal" in mgr._dangerous_patterns
        # 应包含关键的 eval 模式
        jsx_patterns = mgr._dangerous_patterns["jsx"]
        assert any("eval" in p for p in jsx_patterns)

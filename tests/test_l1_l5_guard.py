import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

from core.security import (
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResult,
    AuditChain,
    AuditLogEntry,
    RiskAssessor,
    RiskLevel,
    SandboxPolicy,
    SecurityError,
    SecurityManager,
)
from core.workflow_orchestrator import (
    TaskDefinition,
    TaskStatus,
    TaskType,
    WorkflowOrchestrator,
)


def make_entry(task_id="task"):
    return AuditLogEntry(
        timestamp=1.0,
        workflow_id="workflow",
        task_id=task_id,
        task_type="file_delete",
        security_level="L4",
        action="task_executed",
        status="completed",
    )


@pytest.mark.asyncio
async def test_l1_readonly_direct_execute():
    guard = WorkflowOrchestrator(enable_security=True)
    result = await guard._execute_task_with_guard(
        TaskDefinition("t", TaskType.PERCEPTION, "read", lambda context: "ok"),
        type("Instance", (), {"duration": 0.0})(),
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_l2_generate_direct_execute():
    guard = WorkflowOrchestrator(enable_security=True)
    result = await guard._execute_task_with_guard(
        TaskDefinition("t", TaskType.AE_COMPILE, "generate", lambda context: "ok"),
        type("Instance", (), {"duration": 0.0})(),
    )
    assert result == "ok"


@pytest.mark.asyncio
async def test_l3_sandbox_execute(tmp_path):
    policy = SandboxPolicy(tmp_path)
    assessment = RiskAssessor().assess("ae_execute", {})
    assert assessment.requires_sandbox and not assessment.requires_approval
    # C2(c): wrap_execution 会注入 sandbox_dir, 任务函数通过 **kwargs 感知
    assert await policy.wrap_execution(lambda **kwargs: "ok", {}, assessment) == "ok"


@pytest.mark.asyncio
async def test_l4_approval_required():
    requests = []

    async def approve(request):
        requests.append(request)
        return ApprovalResult(request.request_id, True, "test", 1.0)

    policy = ApprovalPolicy(approve)
    request = ApprovalRequest("id", "task", "ae_render", RiskLevel.L4_DESTRUCTIVE, [], {}, 1.0)
    result = await policy.request_approval(request)
    assert requests and result.approved


@pytest.mark.asyncio
async def test_l4_approval_rejected():
    async def reject(request):
        return ApprovalResult(request.request_id, False, "test", 1.0, "rejected")

    guard = WorkflowOrchestrator(enable_security=True)
    guard._approval_policy = ApprovalPolicy(reject)
    task = TaskDefinition("t", TaskType.AE_RENDER, "render", lambda context: "bad")
    with pytest.raises(SecurityError):
        await guard._execute_task_with_guard(task, type("Instance", (), {"duration": 0.0})())


@pytest.mark.asyncio
async def test_l5_second_confirm_required():
    seen = []

    async def approve(request):
        seen.append(request)
        return ApprovalResult(request.request_id, True, "test", 1.0, second_confirmed=False)

    guard = WorkflowOrchestrator(enable_security=True)
    guard._approval_policy = ApprovalPolicy(approve)
    task = TaskDefinition("t", TaskType.SUB_WORKFLOW, "pay", lambda context: "bad", args={"action": "pay"})
    with pytest.raises(SecurityError):
        await guard._execute_task_with_guard(task, type("Instance", (), {"duration": 0.0})())
    assert seen[0].risk_level == RiskLevel.L5_EXTERNAL


def test_user_material_path_upgrade():
    # H1 新语义: perception(L1 只读)读取素材 -> L3(只读防护), 不再误升 L4
    result = RiskAssessor().assess("perception", {"path": "data/user_materials/a.mov"})
    assert result.risk_level == RiskLevel.L3_OVERWRITE_SAFE


def test_user_material_with_delete_keyword_l4():
    # H1: 只读任务 + 素材 + delete 动作 -> L4
    result = RiskAssessor().assess(
        "perception", {"path": "data/user_materials/a.mov", "action": "delete"}
    )
    assert result.risk_level == RiskLevel.L4_DESTRUCTIVE
    # H1: 写级任务(L3)触及素材 -> L4
    result2 = RiskAssessor().assess("ae_execute", {"path": "data/user_materials/a.mov"})
    assert result2.risk_level == RiskLevel.L4_DESTRUCTIVE


def test_delete_keyword_upgrade():
    result = RiskAssessor().assess("perception", {"action": "delete"})
    assert result.risk_level == RiskLevel.L4_DESTRUCTIVE


def test_pay_keyword_upgrade():
    result = RiskAssessor().assess("general", {"action": "purchase"})
    assert result.risk_level == RiskLevel.L5_EXTERNAL


def test_sandbox_path_whitelist(tmp_path):
    policy = SandboxPolicy(tmp_path)
    path = str(tmp_path / "data" / "sandbox" / "file.txt")
    assert policy.validate_paths([path]) == (True, [])


def test_sandbox_path_blacklist(tmp_path):
    policy = SandboxPolicy(tmp_path)
    path = str(tmp_path / "data" / "sandbox" / "project.aep")
    passed, violations = policy.validate_paths([path])
    assert not passed and violations == [path]


def test_audit_chain_append(tmp_path):
    chain = AuditChain(tmp_path / "audit.jsonl")
    current = chain.append(make_entry())
    record = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
    assert record["current_hash"] == current
    assert len(current) == 64


def test_audit_chain_verify(tmp_path):
    chain = AuditChain(tmp_path / "audit.jsonl")
    chain.append(make_entry())
    chain.append(make_entry("task-2"))
    assert chain.verify_chain() == (True, [])


def test_audit_chain_tamper_detect(tmp_path):
    path = tmp_path / "audit.jsonl"
    chain = AuditChain(path)
    chain.append(make_entry())
    record = json.loads(path.read_text(encoding="utf-8"))
    record["entry"]["task_id"] = "tampered"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    assert chain.verify_chain()[0] is False


@pytest.mark.asyncio
async def test_workflow_orchestrator_integration():
    seen = []

    async def approve(request):
        seen.append(request)
        return ApprovalResult(request.request_id, True, "test", 1.0)

    guard = WorkflowOrchestrator(enable_security=True)
    guard._approval_policy = ApprovalPolicy(approve)
    task = TaskDefinition("export", TaskType.AE_RENDER, "render", lambda context: "ok")
    guard.add_task(task)
    context = await guard.run(workflow_id="wf")
    assert seen and context.tasks["export"].result == "ok"


# ---------------------------------------------------------------------------
# Phase B 漏洞修复新增测试
# ---------------------------------------------------------------------------

# 1. 风险映射完整性: 遍历 TaskType 全部成员（枚举持续扩展，不硬编码数量）
def test_risk_map_covers_all_task_types():
    missing = [
        t.value
        for t in TaskType
        if t.value not in RiskAssessor.DEFAULT_RISK_MAP
    ]
    assert missing == []
    assert len(list(TaskType)) >= 29, "TaskType 枚举不应少于最初设计数量"


# 2. 未知类型默认 L3(fail-closed)
def test_unknown_task_type_defaults_l3():
    result = RiskAssessor().assess("totally_unknown_type", {})
    assert result.risk_level == RiskLevel.L3_OVERWRITE_SAFE
    assert any("unknown_task_type_defaulted_to_L3" in r for r in result.reasons)


# 3. 路径递归提取: 嵌套 dict / Path 对象 / 纯文件名
def test_extract_paths_recursive():
    args = {
        "nested": {
            "input": Path("data/input/a.mov"),
            "list": ["output/final/b.mov", {"deep": "cache/xyz.tmp"}],
        },
        "tuple_val": ("data/sandbox/t.mov",),
        "hidden": ".env",
        "plain": "secret.txt",
        "plain_no_ext": "plaintext",
    }
    paths = RiskAssessor._extract_paths(args)
    import os
    for expected in (
        "data/input/a.mov",
        "output/final/b.mov",
        "cache/xyz.tmp",
        "data/sandbox/t.mov",
        ".env",
        "secret.txt",
    ):
        # Path 对象 str() 在 Windows 上为反斜杠分隔, 普通字符串保留正斜杠
        assert expected in paths or expected.replace("/", os.sep) in paths
    # 无路径特征字符串不误提取
    assert "plaintext" not in paths


# 4. 空路径 L3 任务可执行(不误拦), sandbox_dir 注入可感知
@pytest.mark.asyncio
async def test_l3_no_path_args_executes(tmp_path):
    policy = SandboxPolicy(tmp_path)
    assessment = RiskAssessor().assess("ae_execute", {"action": "render"})
    assert assessment.requires_sandbox and not assessment.requires_approval
    seen = {}

    async def runner(**kwargs):
        seen["sandbox_dir"] = kwargs.get("sandbox_dir")
        return "ok"

    result = await policy.wrap_execution(runner, {}, assessment)
    assert result == "ok"
    assert seen["sandbox_dir"]  # C2(c): 临时目录已注入


# 5. 关键字误报修复: 文件名不再触发升级, 动作键 format/wipe 触发
def test_keyword_false_positive_fixed():
    r1 = RiskAssessor().assess("perception", {"path": "data/sandbox/delete_me.mp4"})
    assert r1.risk_level < RiskLevel.L4_DESTRUCTIVE
    r2 = RiskAssessor().assess("perception", {"action": "format"})
    assert r2.risk_level == RiskLevel.L4_DESTRUCTIVE
    r3 = RiskAssessor().assess("perception", {"operation": "wipe"})
    assert r3.risk_level == RiskLevel.L4_DESTRUCTIVE


# 6. 审计链并发: 两个实例(多线程)交错写同一文件后 verify_chain 仍通过
def test_audit_chain_concurrent_instances(tmp_path):
    path = tmp_path / "audit.jsonl"
    chain_a = AuditChain(path)
    chain_b = AuditChain(path)

    def write_a():
        for i in range(20):
            chain_a.append(make_entry(f"a-{i}"))

    def write_b():
        for i in range(20):
            chain_b.append(make_entry(f"b-{i}"))

    threads = [threading.Thread(target=write_a), threading.Thread(target=write_b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok_a, violations_a = chain_a.verify_chain()
    assert ok_a, violations_a
    ok_b, violations_b = chain_b.verify_chain()
    assert ok_b, violations_b


# 7a. 审批拒绝 -> 审计条目 status="denied"
@pytest.mark.asyncio
async def test_audit_denied_entry(tmp_path):
    async def reject(request):
        return ApprovalResult(request.request_id, False, "test", 1.0, "rejected")

    guard = WorkflowOrchestrator(enable_security=True)
    guard._approval_policy = ApprovalPolicy(reject)
    guard._audit_chain = AuditChain(tmp_path / "audit.jsonl")
    task = TaskDefinition("t", TaskType.AE_RENDER, "render", lambda **kwargs: "bad")
    guard.add_task(task)
    await guard.run(workflow_id="wf")
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1])
    assert last["entry"]["status"] == "denied"


# 7b. 任务异常 -> 审计条目 status="failed"
@pytest.mark.asyncio
async def test_audit_failed_entry(tmp_path):
    async def approve(request):
        return ApprovalResult(request.request_id, True, "test", 1.0)

    guard = WorkflowOrchestrator(enable_security=True)
    guard._approval_policy = ApprovalPolicy(approve)
    guard._audit_chain = AuditChain(tmp_path / "audit.jsonl")

    def boom(**kwargs):
        raise ValueError("boom")

    task = TaskDefinition("t", TaskType.AE_RENDER, "render", boom)
    guard.add_task(task)
    await guard.run(workflow_id="wf")
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1])
    assert last["entry"]["status"] == "failed"


# 8. 审批超时: timeout_seconds=0.1 且 callback 挂起 -> 快速拒绝, 不永久挂起
@pytest.mark.asyncio
async def test_approval_timeout():
    async def hang(request):
        await asyncio.sleep(10)
        return ApprovalResult(request.request_id, True, "test", 1.0)

    policy = ApprovalPolicy(hang)
    request = ApprovalRequest(
        request_id="id",
        task_id="task",
        task_type="ae_render",
        risk_level=RiskLevel.L4_DESTRUCTIVE,
        reasons=[],
        args_preview={},
        requested_at=time.time(),
        timeout_seconds=0.1,
    )
    result = await asyncio.wait_for(policy.request_approval(request), timeout=2.0)
    assert result.approved is False
    assert "超时" in result.comment


# 9. SecurityError 不重试: 审批拒绝 -> FAILED 且 retry_attempts 不增加
@pytest.mark.asyncio
async def test_security_error_not_retried():
    async def reject(request):
        return ApprovalResult(request.request_id, False, "test", 1.0, "rejected")

    guard = WorkflowOrchestrator(enable_security=True)
    guard._approval_policy = ApprovalPolicy(reject)
    task = TaskDefinition(
        "t",
        TaskType.AE_RENDER,
        "render",
        lambda **kwargs: "bad",
        retry_count=3,
        retry_delay_ms=5,
    )
    guard.add_task(task)
    ctx = await guard.run(workflow_id="wf")
    inst = ctx.tasks["t"]
    assert inst.status == TaskStatus.FAILED
    assert inst.retry_attempts == 0
    assert isinstance(inst.error, SecurityError)


# 10. 绑定幂等: 重复执行绑定不递归
def test_binding_idempotent():
    from core import workflow_orchestrator as wo

    wo._bind_guard_entry()
    wo._bind_guard_entry()
    legacy = wo.WorkflowOrchestrator._execute_task_legacy
    assert legacy is not wo.WorkflowOrchestrator._execute_task_with_guard
    assert legacy.__name__ == "_execute_task_func"
    wo._bind_guard_entry()
    assert wo.WorkflowOrchestrator._execute_task_legacy is legacy
    assert wo.WorkflowOrchestrator._execute_task_func is wo.WorkflowOrchestrator._execute_task_with_guard


# 11. _sanitize_args 递归脱敏
def test_sanitize_args_recursive():
    args = {
        "api_key": "sk-123",
        "nested": {
            "credential": "user:pass",
            "sub_list": [{"token": "abc", "safe": 1}, "plain"],
        },
        "path": {"filename": "x.txt"},
    }
    out = WorkflowOrchestrator._sanitize_args(args)
    assert out["api_key"] == "***REDACTED***"
    assert out["nested"]["credential"] == "***REDACTED***"
    assert out["nested"]["sub_list"][0]["token"] == "***REDACTED***"
    assert out["nested"]["sub_list"][0]["safe"] == 1
    assert out["nested"]["sub_list"][1] == "plain"
    assert out["path"]["filename"] == "x.txt"


# 12. verify_chain 截断检测: 删掉最后一条记录后返回 False
def test_audit_chain_truncation_detect(tmp_path):
    path = tmp_path / "audit.jsonl"
    chain = AuditChain(path)
    chain.append(make_entry())
    chain.append(make_entry("task-2"))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    path.write_text(lines[0] + "\n", encoding="utf-8")  # 截断最后一条
    ok, violations = chain.verify_chain()
    assert ok is False
    assert any("截断" in v for v in violations)


# 13. scan_path 前缀绕过回归(M6)
def test_scan_path_prefix_bypass_regression(tmp_path):
    root = tmp_path / "data"
    sandbox = root / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    evil = root / "sandbox_evil"
    evil.mkdir(parents=True, exist_ok=True)
    allowed = str(sandbox)

    mgr = SecurityManager()
    good = str(sandbox / "file.txt")
    assert mgr.scan_path(good, [allowed]).passed is True
    bad = str(evil / "file.txt")
    result = mgr.scan_path(bad, [allowed])
    assert result.passed is False

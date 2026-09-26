# -*- coding: utf-8 -*-
"""
执行结果契约（docs/execution_result_contract.md）结构验证 — 修复方案 FIX-01
==========================================================================
两部分：
  1) 行为测试：exceptions.UntrustedSuccessError（根级 exceptions.py，E504）的真实
     可导入/可抛出/字段/字符串格式化行为——断言"值"而非"不抛异常"（contributing 铁律2）。
  2) 契约文档结构测试：文档是数据（非源码），校验必备章节与关键定义存在，
     防止修订时删掉判据条款。

注意（contributing 铁律3）：本套件存在 importlib.reload 生产模块的用例，
枚举一律按 .value 比较，不用 is。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from exceptions import (
    ErrorCode,
    UntrustedSuccessError,
    WorkflowError,
    AEKnowledgeVaultError,
    get_error_message,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DOC = REPO_ROOT / "docs" / "execution_result_contract.md"


class TestUntrustedSuccessErrorBehavior:
    """E504 异常行为（真实执行验证）"""

    def test_error_code_value(self):
        assert ErrorCode.UNTRUSTED_SUCCESS.value == "E504"

    def test_error_message_registered(self):
        # 新错误码必须进 ERROR_MESSAGES 映射表（否则 get_error_message 回退"未知错误"）
        msg = get_error_message(ErrorCode.UNTRUSTED_SUCCESS)
        assert msg != "未知错误"
        assert "execution_path" in msg or "success" in msg

    def test_hierarchy_matches_workflow_family(self):
        assert issubclass(UntrustedSuccessError, WorkflowError)
        assert issubclass(UntrustedSuccessError, AEKnowledgeVaultError)

    def test_default_message_uses_registry(self):
        # 不传 message 时应回落到 ERROR_MESSAGES 注册文案（值断言）
        exc = UntrustedSuccessError(producer="integrations/topaz_integration.py")
        assert "integrations/topaz_integration.py" in exc.message
        assert exc.error_code.value == "E504"

    def test_default_reason_field(self):
        exc = UntrustedSuccessError(producer="ai/auto_produce.py")
        assert exc.details["producer"] == "ai/auto_produce.py"
        assert exc.details["reason"] == "missing_execution_path"

    def test_custom_reason_recorded(self):
        exc = UntrustedSuccessError(
            producer="ai/ai_video_generator.py",
            reason="simulated_without_explicit_request",
        )
        assert exc.details["reason"] == "simulated_without_explicit_request"

    def test_str_contains_error_code_bracket(self):
        exc = UntrustedSuccessError(producer="x.py")
        text = str(exc)
        assert text.startswith("[E504]")
        assert "producer=x.py" in text

    def test_to_dict_serializable(self):
        exc = UntrustedSuccessError(producer="x.py")
        d = exc.to_dict()
        assert d["error_type"] == "UntrustedSuccessError"
        assert d["error_code"] == "E504"

    def test_raising_and_catching_as_base(self):
        # 消费端可用基类统一捕获（与既有工作流异常一致）
        with pytest.raises(AEKnowledgeVaultError) as ei:
            raise UntrustedSuccessError(producer="consumer_check")
        assert ei.value.details["producer"] == "consumer_check"


def _assert_success_needs_execution_path(result: dict) -> None:
    """契约 §1 判定规则的最小实现示例（消费端模式）。"""
    if result.get("success") and "execution_path" not in result:
        raise UntrustedSuccessError(producer="result-producer")


class TestContractGateLogic:
    """契约核心判据的可执行样例：无标记 success 必须被拦下"""

    def test_unmarked_success_is_rejected(self):
        with pytest.raises(UntrustedSuccessError):
            _assert_success_needs_execution_path({"success": True})

    def test_marked_real_success_passes(self):
        _assert_success_needs_execution_path(
            {"success": True, "execution_path": "real"}
        )

    def test_failure_without_mark_is_fine(self):
        _assert_success_needs_execution_path({"success": False})


@pytest.mark.skipif(not CONTRACT_DOC.exists(), reason="契约文档不存在（FIX-01 未落地）")
class TestContractDocumentStructure:
    """契约文档必备条款（修订时不得静默删除判据）"""

    @pytest.fixture(scope="class")
    def doc_text(self) -> str:
        return CONTRACT_DOC.read_text(encoding="utf-8")

    def test_required_sections_present(self, doc_text):
        for marker in (
            "核心字段定义",
            "产物落盘规范",
            "默认值纪律",
            "进展声明规范",
            "诚实失败样板",
            "已知违规反例索引",
            "白名单与例外机制",
            "异常与工具映射",
        ):
            assert marker in doc_text, f"契约缺少章节: {marker}"

    def test_execution_path_values_defined(self, doc_text):
        for token in ("execution_path", "real", "simulated", "fallback", "fallback_reason"):
            assert token in doc_text

    def test_error_code_binding_documented(self, doc_text):
        # 异常映射指向根级 exceptions.py 与 E504
        assert "E504" in doc_text
        assert "UntrustedSuccessError" in doc_text

    def test_counterexample_classes_covered(self, doc_text):
        # 六类形态 A-F 的反例锚点必须在位（对照 0924 审计 §7.0b）
        for anchor in ("伪造产物文件", "伪造成功", "伪装成 real", "路径分裂", "守护网空转"):
            assert anchor in doc_text

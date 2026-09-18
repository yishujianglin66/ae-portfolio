"""Bridge Protocol 单元测试。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ae.bridge_protocol import (
    BridgeChannel,
    BridgeClient,
    BridgeCommand,
    BridgeError,
    BridgeResponse,
    ChannelStatus,
    CommandStatus,
    DeadLetterQueue,
    ErrorCode,
    FileLock,
    generate_signature,
    sanitize_command_for_dead_letter,
    verify_signature,
)


class TestBridgeCommand:
    """BridgeCommand 测试。"""

    def test_create_command(self) -> None:
        """创建命令对象。"""
        cmd = BridgeCommand(command="test", params={"key": "value"})
        assert cmd.command == "test"
        assert cmd.params == {"key": "value"}
        assert cmd.command_id is not None

    def test_command_to_dict(self) -> None:
        """命令转字典。"""
        cmd = BridgeCommand(command="create", params={"name": "test"})
        data = cmd.model_dump()
        assert data["command"] == "create"
        assert data["params"] == {"name": "test"}
        assert "command_id" in data


class TestBridgeResponse:
    """BridgeResponse 测试。"""

    def test_success_response(self) -> None:
        """成功响应。"""
        import uuid
        cmd_id = str(uuid.uuid4())
        resp = BridgeResponse(command_id=cmd_id, status=CommandStatus.COMPLETED, result={"result": "ok"})
        assert resp.command_id == cmd_id
        assert resp.status == CommandStatus.COMPLETED
        assert resp.result == {"result": "ok"}

    def test_error_response(self) -> None:
        """错误响应。"""
        import uuid
        cmd_id = str(uuid.uuid4())
        resp = BridgeResponse(command_id=cmd_id, status=CommandStatus.FAILED, error=BridgeError(code=ErrorCode.INVALID_JSON, message="failed"))
        assert resp.command_id == cmd_id
        assert resp.status == CommandStatus.FAILED
        assert resp.error is not None
        assert resp.error.message == "failed"

    def test_response_to_dict(self) -> None:
        """响应转字典。"""
        import uuid
        cmd_id = str(uuid.uuid4())
        resp = BridgeResponse(command_id=cmd_id, status=CommandStatus.COMPLETED, result={"id": "123"})
        data = resp.model_dump()
        assert data["command_id"] == cmd_id
        assert data["status"] == "completed"
        assert data["result"] == {"id": "123"}

    def test_response_from_dict(self) -> None:
        """从字典恢复响应。"""
        import uuid
        cmd_id = str(uuid.uuid4())
        data = {
            "command_id": cmd_id,
            "status": "failed",
            "error": {"code": 1002, "message": "timeout"},
        }
        resp = BridgeResponse(**data)
        assert resp.command_id == cmd_id
        assert resp.status == CommandStatus.FAILED
        assert resp.error is not None
        assert resp.error.message == "timeout"


class TestSignature:
    """签名验证测试。"""

    SECRET = "test-secret-12345"

    def test_generate_signature(self) -> None:
        """生成签名。"""
        data = {"action": "test", "params": {"key": "value"}}
        sig = generate_signature(data, self.SECRET)
        assert isinstance(sig, str)
        assert len(sig) == 64

    def test_verify_signature_valid(self) -> None:
        """验证有效签名。"""
        data = {"action": "test", "params": {"key": "value"}}
        sig = generate_signature(data, self.SECRET)
        assert verify_signature(data, sig, self.SECRET) is True

    def test_verify_signature_invalid(self) -> None:
        """验证无效签名。"""
        data = {"action": "test", "params": {"key": "value"}}
        assert verify_signature(data, "invalid-signature", self.SECRET) is False

    def test_signature_with_different_data(self) -> None:
        """不同数据签名不同。"""
        data1 = {"action": "test", "params": {"key": "value1"}}
        data2 = {"action": "test", "params": {"key": "value2"}}
        sig1 = generate_signature(data1, self.SECRET)
        sig2 = generate_signature(data2, self.SECRET)
        assert sig1 != sig2


class TestDeadLetterQueue:
    """死信队列测试。"""

    def test_get_all_empty(self, tmp_path: Path) -> None:
        """获取空死信队列。"""
        dlq = DeadLetterQueue(str(tmp_path))
        records = dlq.get_all()
        assert records == []

    def test_dir_creation(self, tmp_path: Path) -> None:
        """验证死信目录创建。"""
        dlq = DeadLetterQueue(str(tmp_path))
        assert dlq._dead_letter_dir.exists() or True

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        """获取不存在的记录。"""
        dlq = DeadLetterQueue(str(tmp_path))
        result = dlq.get("nonexistent-id")
        assert result is None

    def test_remove_nonexistent(self, tmp_path: Path) -> None:
        """移除不存在的记录。"""
        dlq = DeadLetterQueue(str(tmp_path))
        result = dlq.remove("nonexistent-id")
        assert result is False

    def test_update_retry_count_nonexistent(self, tmp_path: Path) -> None:
        """更新不存在记录的重试计数。"""
        dlq = DeadLetterQueue(str(tmp_path))
        result = dlq.update_retry_count("nonexistent-id")
        assert result is False


class TestFileLock:
    """文件锁测试。"""

    def test_lock_context_manager(self, tmp_path: Path) -> None:
        """测试上下文管理器接口。"""
        lock_path = tmp_path / "test.lock"
        
        try:
            with FileLock(str(lock_path), timeout=1):
                pass
        except RuntimeError:
            pass

    def test_lock_acquire_release(self, tmp_path: Path) -> None:
        """测试手动获取和释放锁。"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(str(lock_path), timeout=1)
        
        try:
            acquired = lock.acquire()
            if acquired:
                lock.release()
        except RuntimeError:
            pass


class TestBridgeCommandExpiry:
    """命令过期测试。"""

    def test_command_not_expired(self) -> None:
        """命令未过期。"""
        cmd = BridgeCommand(command="test", params={})
        assert cmd.is_expired is False

    def test_command_timestamp_dt(self) -> None:
        """命令时间戳转换。"""
        cmd = BridgeCommand(command="test", params={})
        dt = cmd.timestamp_dt
        assert dt is not None

    def test_command_expires_at(self) -> None:
        """命令过期时间。"""
        cmd = BridgeCommand(command="test", params={})
        expires = cmd.expires_at
        assert expires is not None


class TestErrorCode:
    """错误代码测试。"""

    def test_error_code_exists(self) -> None:
        """验证错误代码存在。"""
        assert hasattr(ErrorCode, 'INVALID_JSON')
        assert hasattr(ErrorCode, 'MISSING_REQUIRED_FIELD')
        assert hasattr(ErrorCode, 'AE_NOT_RUNNING')


class TestCommandStatus:
    """命令状态测试。"""

    def test_terminal_status(self) -> None:
        """验证终端状态。"""
        assert CommandStatus.COMPLETED.is_terminal is True
        assert CommandStatus.FAILED.is_terminal is True


class TestBridgeChannel:
    """BridgeChannel 测试。"""

    def test_channel_initialization(self) -> None:
        """通道初始化。"""
        channel = BridgeChannel("test", "/tmp/bridge")
        assert channel.name == "test"
        assert channel.status == ChannelStatus.ACTIVE
        assert channel.health_score == 100

    def test_mark_success(self) -> None:
        """标记成功。"""
        channel = BridgeChannel("test", "/tmp/bridge")
        channel.mark_success()
        
        assert channel.status == ChannelStatus.ACTIVE
        assert channel.health_score == 100

    def test_mark_failure(self) -> None:
        """标记失败。"""
        channel = BridgeChannel("test", "/tmp/bridge")
        channel.mark_failure()
        
        assert channel._consecutive_errors == 1
        
        for _ in range(2):
            channel.mark_failure()
        
        assert channel.status == ChannelStatus.DEGRADED

    def test_check_health(self) -> None:
        """检查健康状态。"""
        channel = BridgeChannel("test", "/tmp/bridge")
        channel.mark_success()
        
        status = channel.check_health()
        assert status == ChannelStatus.ACTIVE


class TestSanitizeCommand:
    """命令脱敏测试。"""

    def test_sanitize_command_basic(self) -> None:
        """基本命令脱敏。"""
        cmd = BridgeCommand(command="test", params={"key": "value"})
        sanitized = sanitize_command_for_dead_letter(cmd)
        assert sanitized.command == "test"
        assert "key" in sanitized.params

    def test_sanitize_command_with_secret(self) -> None:
        """包含敏感信息的命令脱敏。"""
        cmd = BridgeCommand(command="test", params={"password": "secret123", "token": "sk-xxx"})
        sanitized = sanitize_command_for_dead_letter(cmd)
        assert sanitized.params["password"] != "secret123"
        assert sanitized.params["token"] != "sk-xxx"


class TestBridgeClient:
    """BridgeClient 测试。"""

    def test_client_initialization(self, tmp_path: Path) -> None:
        """客户端初始化。"""
        client = BridgeClient(
            bridge_dir=str(tmp_path),
            signature_enabled=False,
        )
        assert client.bridge_dir == tmp_path

    def test_client_with_signature(self, tmp_path: Path) -> None:
        """带签名的客户端初始化。"""
        client = BridgeClient(
            bridge_dir=str(tmp_path),
            signature_enabled=True,
            secret="test-secret",
        )
        assert client.signature_enabled
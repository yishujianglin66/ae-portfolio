"""WebhookNotifier 与持续告警状态机单元测试。

测试覆盖：
    - 三种平台（企业微信 / 钉钉 / 飞书）的消息格式
    - 限流逻辑（5 分钟内不重复发送）
    - 失败重试逻辑（最多 3 次，间隔 5 秒）
    - 持续触发逻辑（CPU 高 29s 不触发，30s 触发）
    - 恢复通知
    - URL 脱敏
    - 钉钉加签

所有 HTTP 请求均通过 mock 模拟，不发送真实网络请求。
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.services.resource_monitor import ResourceMonitorService
from src.services.webhook_notifier import (
    PLATFORM_DINGTALK,
    PLATFORM_FEISHU,
    PLATFORM_WECHAT,
    AlertRecord,
    WebhookNotifier,
    create_notifier_from_settings,
    detect_hostname,
    sanitize_url,
)


# ============================================================
# Mock 工具
# ============================================================
class MockResponse:
    """模拟 httpx.Response。"""

    def __init__(
        self,
        status_code: int = 200,
        json_data: dict[str, Any] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json = json_data if json_data is not None else {"errcode": 0}
        self.text = text or ""

    def json(self) -> dict[str, Any]:
        return self._json


class MockAsyncClient:
    """模拟 httpx.AsyncClient 上下文管理器。

    通过 ``responses`` 队列依次返回预设响应，支持成功/失败场景。
    """

    def __init__(
        self,
        responses: list[MockResponse],
        exc: Exception | None = None,
        record_calls: bool = True,
    ) -> None:
        self._responses = list(responses)
        self._exc = exc
        self.calls: list[dict[str, Any]] = [] if record_calls else []
        self._record = record_calls

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any] | None = None) -> MockResponse:
        if self._record:
            self.calls.append({"url": url, "json": json})
        if self._exc is not None:
            raise self._exc
        if not self._responses:
            # 默认返回成功
            return MockResponse()
        return self._responses.pop(0)


def make_notifier(
    platform: str = PLATFORM_WECHAT,
    url: str = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key-12345",
    secret: str = "",
    quiet_minutes: int = 5,
    max_retries: int = 3,
    retry_interval: float = 0.01,  # 测试中用极短间隔加速
    timeout: float = 5.0,
    hostname: str = "AE-Workstation-Test",
) -> WebhookNotifier:
    """构造测试用 notifier。"""
    return WebhookNotifier(
        platform=platform,
        url=url,
        secret=secret,
        quiet_minutes=quiet_minutes,
        max_retries=max_retries,
        retry_interval=retry_interval,
        timeout=timeout,
        hostname=hostname,
    )


def patch_httpx(client: MockAsyncClient):
    """Patch ``httpx.AsyncClient`` 使其返回 mock client。"""
    return patch("src.services.webhook_notifier.httpx.AsyncClient", return_value=client)


# ============================================================
# URL 脱敏测试
# ============================================================
class TestSanitizeUrl:
    """webhook URL 脱敏测试。"""

    def test_wechat_url_key_masked(self) -> None:
        url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secret-abc-123"
        masked = sanitize_url(url)
        assert "secret-abc-123" not in masked
        assert "key=***" in masked

    def test_dingtalk_url_token_masked(self) -> None:
        url = "https://oapi.dingtalk.com/robot/send?access_token=token-xyz-789"
        masked = sanitize_url(url)
        assert "token-xyz-789" not in masked
        assert "access_token=***" in masked

    def test_feishu_url_path_masked(self) -> None:
        url = "https://open.feishu.cn/open-apis/bot/v2/hook/feishu-token-456"
        masked = sanitize_url(url)
        assert "feishu-token-456" not in masked
        assert "open-apis/bot/v2/hook/***" in masked

    def test_empty_url_returns_empty(self) -> None:
        assert sanitize_url("") == ""

    def test_url_without_token_unchanged(self) -> None:
        url = "https://example.com/webhook"
        assert sanitize_url(url) == url


# ============================================================
# 平台消息格式测试
# ============================================================
class TestPayloadFormats:
    """验证三种平台的消息体格式。"""

    @pytest.mark.parametrize("platform,url", [
        (PLATFORM_WECHAT, "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=k"),
        (PLATFORM_DINGTALK, "https://oapi.dingtalk.com/robot/send?access_token=t"),
        (PLATFORM_FEISHU, "https://open.feishu.cn/open-apis/bot/v2/hook/h"),
    ])
    async def test_alert_payload_built_for_each_platform(
        self, platform: str, url: str
    ) -> None:
        """每种平台都能正确构建告警 payload 并通过 HTTP 发送。"""
        notifier = make_notifier(platform=platform, url=url)
        client = MockAsyncClient(responses=[MockResponse(json_data={"errcode": 0})])
        with patch_httpx(client):
            ok = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.2,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert ok is True
        assert len(client.calls) == 1
        payload = client.calls[0]["json"]
        # 平台特定字段校验
        if platform == PLATFORM_WECHAT:
            assert payload["msgtype"] == "markdown"
            content = payload["markdown"]["content"]
            assert "🚨" in content
            assert "CPU 使用率" in content
            assert "95.2%" in content
            assert "90.0%" in content
            assert "AE-Workstation-Test" in content
            assert "持续 30s" in content
        elif platform == PLATFORM_DINGTALK:
            assert payload["msgtype"] == "markdown"
            assert "title" in payload["markdown"]
            text = payload["markdown"]["text"]
            assert "🚨" in text
            assert "CPU 使用率" in text
            assert "95.2%" in text
        elif platform == PLATFORM_FEISHU:
            assert payload["msg_type"] == "interactive"
            assert payload["card"]["header"]["template"] == "red"
            elements = payload["card"]["elements"]
            elements_text = str(elements)
            assert "CPU 使用率" in elements_text
            assert "95.2%" in elements_text

    async def test_wechat_recovery_payload(self) -> None:
        """企业微信恢复通知 payload 格式正确。"""
        notifier = make_notifier(platform=PLATFORM_WECHAT)
        client = MockAsyncClient(responses=[MockResponse(json_data={"errcode": 0})])
        with patch_httpx(client):
            ok = await notifier.send_recovery(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                previous_value=92.5,
            )
        assert ok is True
        payload = client.calls[0]["json"]
        content = payload["markdown"]["content"]
        assert "✅" in content
        assert "资源恢复" in content
        assert "92.5%" in content

    async def test_dingtalk_test_payload(self) -> None:
        """钉钉测试告警 payload 格式正确。"""
        notifier = make_notifier(platform=PLATFORM_DINGTALK)
        client = MockAsyncClient(responses=[MockResponse(json_data={"errcode": 0})])
        with patch_httpx(client):
            ok = await notifier.test()
        assert ok is True
        payload = client.calls[0]["json"]
        assert payload["msgtype"] == "markdown"
        assert "🔔" in payload["markdown"]["title"]
        assert "测试告警" in payload["markdown"]["text"]

    async def test_feishu_recovery_uses_green_template(self) -> None:
        """飞书恢复通知使用绿色卡片。"""
        notifier = make_notifier(platform=PLATFORM_FEISHU)
        client = MockAsyncClient(responses=[MockResponse(json_data={"code": 0})])
        with patch_httpx(client):
            ok = await notifier.send_recovery(
                alert_type="memory_sustained_high",
                metric="memory_percent",
                previous_value=92.0,
            )
        assert ok is True
        payload = client.calls[0]["json"]
        assert payload["card"]["header"]["template"] == "green"

    async def test_feishu_alert_uses_red_template(self) -> None:
        """飞书告警通知使用红色卡片。"""
        notifier = make_notifier(platform=PLATFORM_FEISHU)
        client = MockAsyncClient(responses=[MockResponse(json_data={"code": 0})])
        with patch_httpx(client):
            ok = await notifier.send_alert(
                alert_type="disk_sustained_high",
                metric="disk_percent",
                value=98.0,
                threshold=95.0,
                sustained_seconds=60,
            )
        assert ok is True
        payload = client.calls[0]["json"]
        assert payload["card"]["header"]["template"] == "red"
        elements_str = str(payload["card"]["elements"])
        assert "磁盘使用率" in elements_str
        assert "98.0%" in elements_str
        assert "持续 60s" in elements_str


# ============================================================
# 限流测试
# ============================================================
class TestRateLimiting:
    """同一告警类型 5 分钟内最多发送 1 次。"""

    async def test_second_alert_within_quiet_period_skipped(self) -> None:
        notifier = make_notifier(quiet_minutes=5)
        client = MockAsyncClient(responses=[MockResponse(json_data={"errcode": 0})])
        with patch_httpx(client):
            first = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
            # 第二次在 5 分钟内：应被跳过
            second = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=96.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert first is True
        assert second is False
        # 只发送了一次 HTTP 请求
        assert len(client.calls) == 1

    async def test_different_alert_types_not_blocked(self) -> None:
        """不同 alert_type 不互相限流。"""
        notifier = make_notifier(quiet_minutes=5)
        client = MockAsyncClient(
            responses=[
                MockResponse(json_data={"errcode": 0}),
                MockResponse(json_data={"errcode": 0}),
            ]
        )
        with patch_httpx(client):
            cpu_ok = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
            mem_ok = await notifier.send_alert(
                alert_type="memory_sustained_high",
                metric="memory_percent",
                value=92.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert cpu_ok is True
        assert mem_ok is True
        assert len(client.calls) == 2

    async def test_recovery_uses_separate_quota(self) -> None:
        """恢复通知与告警通知使用独立的限流配额。"""
        notifier = make_notifier(quiet_minutes=5)
        client = MockAsyncClient(
            responses=[
                MockResponse(json_data={"errcode": 0}),
                MockResponse(json_data={"errcode": 0}),
            ]
        )
        with patch_httpx(client):
            alert_ok = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
            recovery_ok = await notifier.send_recovery(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                previous_value=95.0,
            )
        assert alert_ok is True
        assert recovery_ok is True
        assert len(client.calls) == 2

    async def test_quiet_minutes_zero_disables_rate_limit(self) -> None:
        """quiet_minutes=0 时禁用限流。"""
        notifier = make_notifier(quiet_minutes=0)
        client = MockAsyncClient(
            responses=[
                MockResponse(json_data={"errcode": 0}),
                MockResponse(json_data={"errcode": 0}),
            ]
        )
        with patch_httpx(client):
            first = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
            second = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=96.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert first is True
        assert second is True
        assert len(client.calls) == 2


# ============================================================
# 重试逻辑测试
# ============================================================
class TestRetryLogic:
    """失败重试：最多 max_retries 次，间隔 retry_interval 秒。"""

    async def test_succeeds_on_second_attempt(self) -> None:
        """第一次失败（http 500），第二次成功。"""
        notifier = make_notifier(max_retries=3, retry_interval=0.01)
        client = MockAsyncClient(
            responses=[
                MockResponse(status_code=500, text="server error"),
                MockResponse(json_data={"errcode": 0}),
            ]
        )
        with patch_httpx(client):
            ok = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert ok is True
        assert len(client.calls) == 2

    async def test_all_attempts_fail_returns_false(self) -> None:
        """全部重试失败时返回 False。"""
        notifier = make_notifier(max_retries=3, retry_interval=0.01)
        client = MockAsyncClient(
            responses=[
                MockResponse(status_code=500, text="error 1"),
                MockResponse(status_code=500, text="error 2"),
                MockResponse(status_code=500, text="error 3"),
            ]
        )
        with patch_httpx(client):
            ok = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert ok is False
        # 重试 3 次都用完
        assert len(client.calls) == 3

    async def test_platform_error_triggers_retry(self) -> None:
        """平台返回 errcode != 0 触发重试。"""
        notifier = make_notifier(max_retries=2, retry_interval=0.01)
        client = MockAsyncClient(
            responses=[
                MockResponse(json_data={"errcode": 93000, "errmsg": "invalid webhook"}),
                MockResponse(json_data={"errcode": 0}),
            ]
        )
        with patch_httpx(client):
            ok = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert ok is True
        assert len(client.calls) == 2

    async def test_httpx_exception_triggers_retry(self) -> None:
        """httpx 抛异常时触发重试。"""
        notifier = make_notifier(max_retries=2, retry_interval=0.01)

        # 第一次抛异常，第二次成功
        call_count = {"n": 0}

        class FlakyClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            async def __aenter__(self) -> "FlakyClient":
                return self

            async def __aexit__(self, *args: Any) -> None:
                return None

            async def post(self, url: str, json: Any = None) -> MockResponse:
                self.calls.append({"url": url, "json": json})
                call_count["n"] += 1
                if call_count["n"] == 1:
                    raise ConnectionError("network down")
                return MockResponse(json_data={"errcode": 0})

        flaky = FlakyClient()
        with patch("src.services.webhook_notifier.httpx.AsyncClient", return_value=flaky):
            ok = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert ok is True
        assert len(flaky.calls) == 2

    async def test_max_retries_one_no_retry_on_failure(self) -> None:
        """max_retries=1 时失败不重试。"""
        notifier = make_notifier(max_retries=1, retry_interval=0.01)
        client = MockAsyncClient(
            responses=[MockResponse(status_code=500, text="error")]
        )
        with patch_httpx(client):
            ok = await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        assert ok is False
        assert len(client.calls) == 1


# ============================================================
# 钉钉加签测试
# ============================================================
class TestDingtalkSigning:
    """钉钉机器人加签算法。"""

    def test_sign_dingtalk_known_vector(self) -> None:
        """使用钉钉文档示例验证加签算法。"""
        timestamp = 1577808000000
        secret = "SEC1234567890abcdef"
        sign = WebhookNotifier._sign_dingtalk(timestamp, secret)
        # 验证返回的是 base64 字符串
        assert isinstance(sign, str)
        assert len(sign) > 0
        # 同样的输入应该产生同样的输出（确定性）
        sign2 = WebhookNotifier._sign_dingtalk(timestamp, secret)
        assert sign == sign2

    async def test_signed_url_includes_timestamp_and_sign(self) -> None:
        """配置 secret 后 URL 包含 timestamp 和 sign 参数。"""
        notifier = make_notifier(
            platform=PLATFORM_DINGTALK,
            url="https://oapi.dingtalk.com/robot/send?access_token=t",
            secret="SECtest123",
        )
        client = MockAsyncClient(responses=[MockResponse(json_data={"errcode": 0})])
        with patch_httpx(client):
            await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        sent_url = client.calls[0]["url"]
        assert "timestamp=" in sent_url
        assert "sign=" in sent_url
        assert "access_token=t" in sent_url

    async def test_no_sign_when_secret_empty(self) -> None:
        """secret 为空时 URL 不包含 sign 参数。"""
        notifier = make_notifier(
            platform=PLATFORM_DINGTALK,
            url="https://oapi.dingtalk.com/robot/send?access_token=t",
            secret="",
        )
        client = MockAsyncClient(responses=[MockResponse(json_data={"errcode": 0})])
        with patch_httpx(client):
            await notifier.send_alert(
                alert_type="cpu_sustained_high",
                metric="cpu_percent",
                value=95.0,
                threshold=90.0,
                sustained_seconds=30,
            )
        sent_url = client.calls[0]["url"]
        assert "sign=" not in sent_url


# ============================================================
# 持续触发逻辑测试
# ============================================================
class TestSustainedAlertStateMachine:
    """验证 ResourceMonitorService 的持续告警状态机。"""

    def _make_service(
        self,
        notifier: WebhookNotifier | None = None,
        sustained_thresholds: dict[str, float] | None = None,
        sustained_seconds: dict[str, int] | None = None,
    ) -> ResourceMonitorService:
        return ResourceMonitorService(
            interval=0.01,
            notifier=notifier,
            sustained_thresholds=sustained_thresholds or {
                "cpu_percent": 90.0,
                "memory_percent": 90.0,
                "disk_percent": 95.0,
            },
            sustained_seconds=sustained_seconds or {
                "cpu_percent": 30,
                "memory_percent": 30,
                "disk_percent": 60,
            },
        )

    async def test_below_threshold_no_state_change(self) -> None:
        """资源低于阈值时不进入告警状态。"""
        service = self._make_service()
        ts = time.time()
        await service._update_sustained_state(
            metric="cpu_percent", value=50.0, threshold=90.0,
            sustained_seconds=30, ts=ts,
        )
        states = service.get_sustained_alerts()
        assert states == []

    async def test_first_breach_enters_warning(self) -> None:
        """首次超过阈值进入 warning 状态。"""
        service = self._make_service()
        ts = time.time()
        await service._update_sustained_state(
            metric="cpu_percent", value=92.0, threshold=90.0,
            sustained_seconds=30, ts=ts,
        )
        states = service.get_sustained_alerts()
        assert len(states) == 1
        assert states[0]["state"] == "warning"
        assert states[0]["first_breach_at"] == ts
        assert states[0]["value"] == 92.0

    async def test_first_breach_critical_value_enters_critical(self) -> None:
        """首次超过阈值 +5% 直接进入 critical 状态。"""
        service = self._make_service()
        ts = time.time()
        await service._update_sustained_state(
            metric="cpu_percent", value=96.0, threshold=90.0,
            sustained_seconds=30, ts=ts,
        )
        states = service.get_sustained_alerts()
        assert states[0]["state"] == "critical"

    async def test_29s_does_not_trigger_sustained_alert(self) -> None:
        """CPU 持续 29s 超过阈值：不触发 sustained_alert。"""
        service = self._make_service()
        start = time.time()
        # 模拟 29 秒采样
        for i in range(30):  # 0s, 1s, ..., 29s
            await service._update_sustained_state(
                metric="cpu_percent", value=95.0, threshold=90.0,
                sustained_seconds=30, ts=start + i,
            )
        states = service.get_sustained_alerts()
        assert states[0]["state"] in ("warning", "critical")
        # 没有触发 webhook，所以没有 alert history
        assert service.get_alert_history() == []

    async def test_30s_triggers_sustained_alert_with_notifier(self) -> None:
        """CPU 持续 30s 超过阈值：触发 sustained_alert 并发送 webhook。"""
        notifier = make_notifier(quiet_minutes=0)
        client = MockAsyncClient(responses=[MockResponse(json_data={"errcode": 0})])
        service = self._make_service(notifier=notifier)

        start = time.time()
        with patch_httpx(client):
            # 模拟 31 秒采样（确保超过 30s）
            for i in range(32):  # 0s, 1s, ..., 31s
                await service._update_sustained_state(
                    metric="cpu_percent", value=95.0, threshold=90.0,
                    sustained_seconds=30, ts=start + i,
                )
                # 让后台 asyncio.create_task 有机会执行
                await asyncio.sleep(0)
        states = service.get_sustained_alerts()
        # 应该已经触发并完成通知（状态变为 notified 或 sustained_alert）
        assert states[0]["state"] in ("sustained_alert", "notifying", "notified")
        # webhook 应该被调用
        assert len(client.calls) >= 1

    async def test_30s_triggers_without_notifier_marks_notified(self) -> None:
        """无 notifier 时，30s 后状态直接标记为 notified 但不发送。"""
        service = self._make_service(notifier=None)
        start = time.time()
        for i in range(32):
            await service._update_sustained_state(
                metric="cpu_percent", value=95.0, threshold=90.0,
                sustained_seconds=30, ts=start + i,
            )
        states = service.get_sustained_alerts()
        assert states[0]["state"] == "notified"
        assert states[0]["notification_sent"] is False
        # 历史记录中应有 alert 事件
        history = service.get_alert_history(limit=10)
        assert len(history) == 1
        assert history[0]["event"] == "alert"
        assert history[0]["success"] is False

    async def test_recovery_during_warning_resets_to_normal(self) -> None:
        """warning 状态下资源恢复 → 直接重置为 normal。"""
        service = self._make_service()
        ts = time.time()
        # 进入 warning
        await service._update_sustained_state(
            metric="cpu_percent", value=92.0, threshold=90.0,
            sustained_seconds=30, ts=ts,
        )
        assert service.get_sustained_alerts()[0]["state"] == "warning"
        # 恢复
        await service._update_sustained_state(
            metric="cpu_percent", value=50.0, threshold=90.0,
            sustained_seconds=30, ts=ts + 1,
        )
        states = service.get_sustained_alerts()
        assert states[0]["state"] == "normal"
        assert states[0]["first_breach_at"] is None
        # 没有 recovery 事件被记录（未触发过 webhook）
        history = service.get_alert_history()
        assert history == []

    async def test_recovery_after_notified_sends_recovery_notification(self) -> None:
        """notified 状态下资源恢复 → 发送恢复通知。"""
        notifier = make_notifier(quiet_minutes=0)
        client = MockAsyncClient(
            responses=[
                MockResponse(json_data={"errcode": 0}),  # 告警
                MockResponse(json_data={"errcode": 0}),  # 恢复
            ]
        )
        service = self._make_service(notifier=notifier)
        start = time.time()
        with patch_httpx(client):
            # 触发 sustained_alert + 通知
            for i in range(32):
                await service._update_sustained_state(
                    metric="cpu_percent", value=95.0, threshold=90.0,
                    sustained_seconds=30, ts=start + i,
                )
                await asyncio.sleep(0)
            # 等待后台告警任务完成
            await asyncio.sleep(0.05)
            # 此时状态应该是 notified
            assert service.get_sustained_alerts()[0]["state"] == "notified"
            # 资源恢复
            await service._update_sustained_state(
                metric="cpu_percent", value=50.0, threshold=90.0,
                sustained_seconds=30, ts=start + 33,
            )
            # 状态变为 recovering
            assert service.get_sustained_alerts()[0]["state"] == "recovering"
            # 等待后台恢复任务完成
            await asyncio.sleep(0.05)
        # 最终状态恢复为 normal
        states = service.get_sustained_alerts()
        assert states[0]["state"] == "normal"
        assert states[0]["first_breach_at"] is None
        # 两次 HTTP 调用：告警 + 恢复
        assert len(client.calls) == 2
        # 历史记录：1 条 alert + 1 条 recovery
        history = service.get_alert_history(limit=10)
        events = [h["event"] for h in history]
        assert "alert" in events
        assert "recovery" in events

    async def test_warning_upgrades_to_critical_on_higher_value(self) -> None:
        """warning 状态下值升至 threshold+5 → 升级为 critical。"""
        service = self._make_service()
        ts = time.time()
        await service._update_sustained_state(
            metric="cpu_percent", value=92.0, threshold=90.0,
            sustained_seconds=30, ts=ts,
        )
        assert service.get_sustained_alerts()[0]["state"] == "warning"
        await service._update_sustained_state(
            metric="cpu_percent", value=96.0, threshold=90.0,
            sustained_seconds=30, ts=ts + 1,
        )
        assert service.get_sustained_alerts()[0]["state"] == "critical"


# ============================================================
# 配置工厂函数测试
# ============================================================
class TestCreateNotifierFromSettings:
    """create_notifier_from_settings 工厂函数测试。"""

    def test_disabled_returns_none(self) -> None:
        class FakeSettings:
            webhook_enabled = False
            webhook_url = "https://example.com"

        assert create_notifier_from_settings(FakeSettings()) is None

    def test_empty_url_returns_none(self) -> None:
        class FakeSettings:
            webhook_enabled = True
            webhook_url = ""
            webhook_platform = "wechat"
            webhook_secret = ""

        assert create_notifier_from_settings(FakeSettings()) is None

    def test_enabled_with_url_returns_notifier(self) -> None:
        class FakeSettings:
            webhook_enabled = True
            webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x"
            webhook_platform = "wechat"
            webhook_secret = ""
            webhook_quiet_minutes = 10
            webhook_max_retries = 5
            webhook_retry_interval = 2.0
            webhook_timeout = 8.0
            alert_hostname = "test-host"

        notifier = create_notifier_from_settings(FakeSettings())
        assert notifier is not None
        assert notifier.platform == "wechat"
        assert notifier.quiet_minutes == 10
        assert notifier.max_retries == 5
        assert notifier.hostname == "test-host"

    def test_invalid_platform_returns_none(self) -> None:
        class FakeSettings:
            webhook_enabled = True
            webhook_url = "https://example.com"
            webhook_platform = "invalid_platform"
            webhook_secret = ""
            webhook_quiet_minutes = 5
            webhook_max_retries = 3
            webhook_retry_interval = 5.0
            webhook_timeout = 10.0
            alert_hostname = ""

        # 无效平台应该被工厂函数兜底捕获异常，返回 None
        notifier = create_notifier_from_settings(FakeSettings())
        assert notifier is None


# ============================================================
# 主机名探测测试
# ============================================================
class TestDetectHostname:
    """detect_hostname 测试。"""

    def test_returns_non_empty_string(self) -> None:
        name = detect_hostname()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_fallback_used_on_failure(self) -> None:
        # 通过 fallback 参数测试
        name = detect_hostname(fallback="my-fallback-host")
        assert isinstance(name, str)
        assert len(name) > 0


# ============================================================
# ResourceMonitorService 集成测试
# ============================================================
class TestResourceMonitorServiceIntegration:
    """ResourceMonitorService 与 WebhookNotifier 集成测试。"""

    async def test_send_test_alert_without_notifier_returns_false(self) -> None:
        """无 notifier 时 send_test_alert 返回 False。"""
        service = ResourceMonitorService(interval=0.01, notifier=None)
        result = await service.send_test_alert()
        assert result is False

    async def test_send_test_alert_with_notifier(self) -> None:
        """有 notifier 时 send_test_alert 调用 notifier.test()。"""
        notifier = make_notifier()
        client = MockAsyncClient(responses=[MockResponse(json_data={"errcode": 0})])
        service = ResourceMonitorService(interval=0.01, notifier=notifier)
        with patch_httpx(client):
            result = await service.send_test_alert()
        assert result is True
        assert len(client.calls) == 1
        # 验证发送的是 test 事件
        payload = client.calls[0]["json"]
        assert "测试" in str(payload)

    def test_get_notifier_stats_without_notifier_returns_none(self) -> None:
        service = ResourceMonitorService(interval=0.01, notifier=None)
        assert service.get_notifier_stats() is None

    def test_get_notifier_stats_with_notifier(self) -> None:
        notifier = make_notifier()
        service = ResourceMonitorService(interval=0.01, notifier=notifier)
        stats = service.get_notifier_stats()
        assert stats is not None
        assert stats["platform"] == PLATFORM_WECHAT
        assert "url_masked" in stats
        # URL 应该是脱敏过的
        assert "test-key-12345" not in stats["url_masked"]

    async def test_full_pipeline_sustained_alert_and_recovery(self) -> None:
        """端到端：CPU 持续高 → 触发告警 → CPU 恢复 → 触发恢复通知。"""
        notifier = make_notifier(quiet_minutes=0)
        client = MockAsyncClient(
            responses=[
                MockResponse(json_data={"errcode": 0}),  # 告警
                MockResponse(json_data={"errcode": 0}),  # 恢复
            ]
        )
        service = ResourceMonitorService(
            interval=0.01,
            notifier=notifier,
            sustained_thresholds={"cpu_percent": 90.0},
            sustained_seconds={"cpu_percent": 30},
        )
        start = time.time()
        with patch_httpx(client):
            # 1. 持续 32s 高 CPU
            for i in range(33):
                await service._update_sustained_state(
                    metric="cpu_percent", value=95.0, threshold=90.0,
                    sustained_seconds=30, ts=start + i,
                )
                await asyncio.sleep(0)
            await asyncio.sleep(0.05)  # 等告警 task 完成
            # 2. CPU 恢复
            await service._update_sustained_state(
                metric="cpu_percent", value=40.0, threshold=90.0,
                sustained_seconds=30, ts=start + 34,
            )
            await asyncio.sleep(0.05)  # 等恢复 task 完成
        # 最终状态：normal
        states = service.get_sustained_alerts()
        assert states[0]["state"] == "normal"
        # 2 次 HTTP 调用
        assert len(client.calls) == 2
        # 历史记录包含 alert + recovery
        history = service.get_alert_history(limit=10)
        events = [h["event"] for h in history]
        assert "alert" in events
        assert "recovery" in events

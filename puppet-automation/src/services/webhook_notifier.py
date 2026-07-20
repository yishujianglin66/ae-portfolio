"""Webhook 告警通知器 - 支持企业微信 / 钉钉 / 飞书。

当 ``ResourceMonitorService`` 检测到资源持续超过阈值时，通过本模块异步
发送告警消息。所有 HTTP 调用基于 ``httpx.AsyncClient``，失败重试 + 限流
避免告警风暴。

平台支持：
    - 企业微信（Markdown 消息）：``https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx``
    - 钉钉（Markdown 消息 + 加签）：``https://oapi.dingtalk.com/robot/send?access_token=xxx``
    - 飞书（Interactive Card 消息）：``https://open.feishu.cn/open-apis/bot/v2/hook/xxx``

安全约束：
    - webhook URL 中的 key/token 在日志输出时统一掩码为 ``***``
    - ``webhook_secret`` 永不打印
    - 同一告警类型在 ``quiet_minutes`` 内最多发送一次
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import re
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

# httpx 为项目核心依赖（见 requirements.txt）
try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover - 环境差异
    httpx = None  # type: ignore
    _HTTPX_AVAILABLE = False
    logger.warning("httpx 未安装，WebhookNotifier 将无法发送 HTTP 请求")


# ============================================================
# 平台常量
# ============================================================
PLATFORM_WECHAT = "wechat"
PLATFORM_DINGTALK = "dingtalk"
PLATFORM_FEISHU = "feishu"
SUPPORTED_PLATFORMS = {PLATFORM_WECHAT, PLATFORM_DINGTALK, PLATFORM_FEISHU}

# 指标 → 中文描述映射
METRIC_LABELS: Dict[str, str] = {
    "cpu_percent": "CPU 使用率",
    "memory_percent": "内存使用率",
    "disk_percent": "磁盘使用率",
}

# 指标 → 处置建议
METRIC_SUGGESTIONS: Dict[str, str] = {
    "cpu_percent": "检查渲染任务或杀掉异常进程",
    "memory_percent": "关闭不必要的程序或重启服务",
    "disk_percent": "清理临时文件或转移素材到其他磁盘",
}


# ============================================================
# URL 脱敏
# ============================================================
# 匹配 webhook URL 中的 key/access_token 路径段
_SENSITIVE_PATTERNS = (
    re.compile(r"(key=)[^&]+", re.IGNORECASE),
    re.compile(r"(access_token=)[^&]+", re.IGNORECASE),
    # 飞书 webhook 路径末尾的 token
    re.compile(r"(open-apis/bot/v2/hook/)[^/\s?&]+", re.IGNORECASE),
)


def sanitize_url(url: str) -> str:
    """脱敏 webhook URL，将敏感 key/token 替换为 ``***``。

    Args:
        url: 原始 webhook URL。

    Returns:
        脱敏后可用于日志输出的 URL 字符串。
    """
    if not url:
        return ""
    masked = url
    for pattern in _SENSITIVE_PATTERNS:
        masked = pattern.sub(r"\1***", masked)
    return masked


def detect_hostname(fallback: str = "") -> str:
    """获取本机主机名，失败时回退到 fallback。"""
    try:
        name = socket.gethostname() or fallback
        return name or "unknown-host"
    except Exception:  # pragma: no cover - 平台差异
        return fallback or "unknown-host"


# ============================================================
# 数据结构
# ============================================================
@dataclass
class AlertRecord:
    """单条告警记录（用于状态机追踪和 API 返回）。"""

    alert_type: str  # 例如 "cpu_sustained_high"
    metric: str  # 例如 "cpu_percent"
    state: str  # normal / warning / critical / sustained_alert / notifying / notified / recovering
    value: float = 0.0
    threshold: float = 0.0
    first_breach_at: Optional[float] = None  # 首次超过阈值的时间戳
    sustained_seconds: int = 0
    last_notified_at: Optional[float] = None  # 最近一次发送 webhook 的时间
    last_recovery_at: Optional[float] = None
    notification_sent: bool = False
    recovery_sent: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_type": self.alert_type,
            "metric": self.metric,
            "state": self.state,
            "value": round(self.value, 2),
            "threshold": round(self.threshold, 2),
            "first_breach_at": self.first_breach_at,
            "sustained_seconds": self.sustained_seconds,
            "last_notified_at": self.last_notified_at,
            "last_recovery_at": self.last_recovery_at,
            "notification_sent": self.notification_sent,
            "recovery_sent": self.recovery_sent,
            "error": self.error,
        }


# ============================================================
# WebhookNotifier
# ============================================================
class WebhookNotifier:
    """异步 webhook 通知器，支持企业微信 / 钉钉 / 飞书。

    特性：
        - 异步发送（``httpx.AsyncClient``），不阻塞监控主循环
        - 失败重试（最多 ``max_retries`` 次，间隔 ``retry_interval`` 秒）
        - 限流（同一 ``alert_type`` 在 ``quiet_minutes`` 内最多发送一次）
        - 日志脱敏（URL 中的 key/token 用 ``***`` 替换）

    使用示例::

        notifier = WebhookNotifier(
            platform="wechat",
            url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
            quiet_minutes=5,
        )
        await notifier.send_alert(
            alert_type="cpu_sustained_high",
            metric="cpu_percent",
            value=95.2,
            threshold=90.0,
            sustained_seconds=30,
        )
    """

    def __init__(
        self,
        platform: str,
        url: str,
        secret: str = "",
        quiet_minutes: int = 5,
        max_retries: int = 3,
        retry_interval: float = 5.0,
        timeout: float = 10.0,
        hostname: str = "",
    ) -> None:
        """初始化 webhook 通知器。

        Args:
            platform: 平台标识，``wechat`` / ``dingtalk`` / ``feishu``。
            url: 完整 webhook URL。
            secret: 钉钉加签密钥（可选，仅 ``dingtalk`` 使用）。
            quiet_minutes: 同一告警类型静默期（分钟）。
            max_retries: 发送失败重试次数。
            retry_interval: 重试间隔（秒）。
            timeout: 单次 HTTP 请求超时（秒）。
            hostname: 告警消息中显示的主机名，空则自动探测。
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError(
                f"不支持的平台 '{platform}'，可选: {sorted(SUPPORTED_PLATFORMS)}"
            )
        if not url:
            raise ValueError("webhook url 不能为空")

        self.platform = platform
        self.url = url
        self.secret = secret or ""
        self.quiet_minutes = max(0, int(quiet_minutes))
        self.max_retries = max(1, int(max_retries))
        self.retry_interval = max(0.1, float(retry_interval))
        self.timeout = max(1.0, float(timeout))
        self.hostname = hostname or detect_hostname()

        # 限流记账：alert_type -> 最近一次成功发送的时间戳
        self._last_sent: Dict[str, float] = {}
        # 发送中标记，避免同一告警类型并发发送
        self._in_flight: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------
    async def send_alert(
        self,
        alert_type: str,
        metric: str,
        value: float,
        threshold: float,
        sustained_seconds: int,
        hostname: str = "",
        suggestion: str = "",
    ) -> bool:
        """发送告警通知（自动限流）。

        Args:
            alert_type: 告警类型标识，用于限流，例如 ``cpu_sustained_high``。
            metric: 指标名，例如 ``cpu_percent``。
            value: 当前值。
            threshold: 阈值。
            sustained_seconds: 持续秒数。
            hostname: 主机名（覆盖默认值）。
            suggestion: 处置建议，空则按 metric 自动选择。

        Returns:
            是否成功发送（限流期内返回 ``False``）。
        """
        if not self._can_send(alert_type):
            logger.debug(
                f"告警 {alert_type} 处于静默期（{self.quiet_minutes}min），跳过发送"
            )
            return False

        host = hostname or self.hostname
        suggestion = suggestion or METRIC_SUGGESTIONS.get(metric, "请检查系统状态")
        payload = self._build_payload(
            event="alert",
            alert_type=alert_type,
            metric=metric,
            value=value,
            threshold=threshold,
            sustained_seconds=sustained_seconds,
            hostname=host,
            suggestion=suggestion,
        )
        success = await self._send_with_retry(alert_type, payload, event="alert")
        if success:
            self._last_sent[alert_type] = time.time()
            logger.info(
                f"告警通知发送成功: type={alert_type} metric={metric} "
                f"value={value:.1f} threshold={threshold:.1f} host={host}"
            )
        return success

    async def send_recovery(
        self,
        alert_type: str,
        metric: str,
        hostname: str = "",
        previous_value: float = 0.0,
    ) -> bool:
        """发送恢复通知。

        恢复通知不复用告警限流，但通过 ``alert_type + ":recovery"`` 单独记账
        避免短时间内重复发送恢复消息。

        Args:
            alert_type: 原告警类型标识。
            metric: 指标名。
            hostname: 主机名。
            previous_value: 恢复前的最近一次告警值（可选）。

        Returns:
            是否成功发送。
        """
        recovery_key = f"{alert_type}:recovery"
        if not self._can_send(recovery_key):
            logger.debug(f"恢复通知 {alert_type} 处于静默期，跳过发送")
            return False

        host = hostname or self.hostname
        payload = self._build_payload(
            event="recovery",
            alert_type=alert_type,
            metric=metric,
            value=previous_value,
            threshold=0.0,
            sustained_seconds=0,
            hostname=host,
            suggestion="",
        )
        success = await self._send_with_retry(recovery_key, payload, event="recovery")
        if success:
            self._last_sent[recovery_key] = time.time()
            logger.info(
                f"恢复通知发送成功: type={alert_type} metric={metric} host={host}"
            )
        return success

    async def test(
        self,
        hostname: str = "",
    ) -> bool:
        """发送一条测试告警，用于验证 webhook 配置是否正确。

        Args:
            hostname: 主机名。

        Returns:
            是否成功发送。
        """
        host = hostname or self.hostname
        payload = self._build_payload(
            event="test",
            alert_type="test",
            metric="test",
            value=0.0,
            threshold=0.0,
            sustained_seconds=0,
            hostname=host,
            suggestion="这是一条测试消息，用于验证 webhook 配置",
        )
        # 测试消息不复用限流，但要避免短时间频繁发送
        test_key = "test"
        if not self._can_send(test_key, quiet_seconds=10):
            logger.debug("测试告警 10s 内已发送过，跳过")
            return False
        success = await self._send_with_retry(test_key, payload, event="test")
        if success:
            self._last_sent[test_key] = time.time()
            logger.info(f"测试告警发送成功: host={host} platform={self.platform}")
        return success

    def get_stats(self) -> Dict[str, Any]:
        """获取通知器统计信息。"""
        return {
            "platform": self.platform,
            "url_masked": sanitize_url(self.url),
            "hostname": self.hostname,
            "quiet_minutes": self.quiet_minutes,
            "max_retries": self.max_retries,
            "httpx_available": _HTTPX_AVAILABLE,
            "last_sent": dict(self._last_sent),
        }

    # ------------------------------------------------------------------
    # 限流
    # ------------------------------------------------------------------
    def _can_send(self, key: str, quiet_seconds: Optional[float] = None) -> bool:
        """检查当前是否可以发送指定 key 的通知。

        Args:
            key: 通知标识。
            quiet_seconds: 自定义静默秒数，None 则使用 ``quiet_minutes * 60``。

        Returns:
            ``True`` 表示可以发送。
        """
        if quiet_seconds is None:
            quiet_seconds = self.quiet_minutes * 60.0
        if quiet_seconds <= 0:
            return True
        last = self._last_sent.get(key)
        if last is None:
            return True
        return (time.time() - last) >= quiet_seconds

    # ------------------------------------------------------------------
    # HTTP 发送 + 重试
    # ------------------------------------------------------------------
    async def _send_with_retry(
        self,
        key: str,
        payload: Dict[str, Any],
        event: str,
    ) -> bool:
        """发送 HTTP POST 请求，失败时按 ``max_retries`` 重试。

        Args:
            key: 通知标识，用于 in-flight 标记。
            payload: 请求体 JSON。
            event: 事件类型（alert/recovery/test），仅用于日志。

        Returns:
            是否最终成功。
        """
        if not _HTTPX_AVAILABLE:
            logger.error("httpx 不可用，无法发送 webhook")
            return False

        if self._in_flight.get(key):
            logger.debug(f"通知 {key} 正在发送中，跳过本次触发")
            return False

        self._in_flight[key] = True
        url = self._build_signed_url()
        masked_url = sanitize_url(url)

        try:
            last_error = ""
            for attempt in range(1, self.max_retries + 1):
                try:
                    success, err = await self._post_once(url, payload)
                    if success:
                        return True
                    last_error = err
                    logger.warning(
                        f"webhook 发送失败 attempt={attempt}/{self.max_retries} "
                        f"event={event} url={masked_url} error={err}"
                    )
                except Exception as e:  # noqa: BLE001
                    last_error = str(e)
                    logger.warning(
                        f"webhook 发送异常 attempt={attempt}/{self.max_retries} "
                        f"event={event} url={masked_url} error={e}"
                    )
                # 未达上限则等待重试
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_interval)
            logger.error(
                f"webhook 最终发送失败 event={event} url={masked_url} "
                f"attempts={self.max_retries} last_error={last_error}"
            )
            return False
        finally:
            self._in_flight[key] = False

    async def _post_once(
        self,
        url: str,
        payload: Dict[str, Any],
    ) -> tuple[bool, str]:
        """执行一次 HTTP POST。

        Returns:
            (success, error_message) 元组。
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
        # 不同平台成功码判定
        if resp.status_code != 200:
            return False, f"http {resp.status_code}: {resp.text[:200]}"
        try:
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            return False, f"invalid json: {e}"
        # 飞书成功响应码 0；钉钉 errcode=0；企业微信 errcode=0
        errcode = data.get("errcode", data.get("code", 0))
        if errcode not in (0, None):
            return False, f"platform error: {data}"
        return True, ""

    def _build_signed_url(self) -> str:
        """钉钉加签 URL，其它平台直接返回原始 URL。"""
        if self.platform != PLATFORM_DINGTALK or not self.secret:
            return self.url
        timestamp = int(time.time() * 1000)
        sign = self._sign_dingtalk(timestamp, self.secret)
        sep = "&" if "?" in self.url else "?"
        return f"{self.url}{sep}timestamp={timestamp}&sign={sign}"

    @staticmethod
    def _sign_dingtalk(timestamp: int, secret: str) -> str:
        """钉钉机器人加签算法。

        Args:
            timestamp: 毫秒时间戳。
            secret: 加签密钥。

        Returns:
            URL 编码后的签名字符串。
        """
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    # ------------------------------------------------------------------
    # 消息构建
    # ------------------------------------------------------------------
    def _build_payload(
        self,
        event: str,
        alert_type: str,
        metric: str,
        value: float,
        threshold: float,
        sustained_seconds: int,
        hostname: str,
        suggestion: str,
    ) -> Dict[str, Any]:
        """根据平台分发到具体的 payload 构造器。"""
        if self.platform == PLATFORM_WECHAT:
            return self._build_wechat_payload(
                event, alert_type, metric, value, threshold,
                sustained_seconds, hostname, suggestion,
            )
        if self.platform == PLATFORM_DINGTALK:
            return self._build_dingtalk_payload(
                event, alert_type, metric, value, threshold,
                sustained_seconds, hostname, suggestion,
            )
        if self.platform == PLATFORM_FEISHU:
            return self._build_feishu_payload(
                event, alert_type, metric, value, threshold,
                sustained_seconds, hostname, suggestion,
            )
        raise ValueError(f"不支持的平台: {self.platform}")

    @staticmethod
    def _format_timestamp(ts: Optional[float] = None) -> str:
        """格式化时间戳为 ``YYYY-MM-DD HH:MM:SS``。"""
        if ts is None:
            ts = time.time()
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    def _build_wechat_payload(
        self,
        event: str,
        alert_type: str,
        metric: str,
        value: float,
        threshold: float,
        sustained_seconds: int,
        hostname: str,
        suggestion: str,
    ) -> Dict[str, Any]:
        """企业微信 Markdown 消息。"""
        metric_label = METRIC_LABELS.get(metric, metric)
        if event == "recovery":
            title = "✅ 资源恢复"
            lines = [
                f"## ✅ 资源恢复",
                f"**类型**: {metric_label} 已恢复正常",
                f"**主机**: {hostname}",
                f"**最近告警值**: {value:.1f}%",
                f"**时间**: {self._format_timestamp()}",
                f"**告警类型**: {alert_type}",
            ]
        elif event == "test":
            title = "🔔 测试告警"
            lines = [
                f"## 🔔 测试告警",
                f"**主机**: {hostname}",
                f"**平台**: 企业微信",
                f"**时间**: {self._format_timestamp()}",
                f"**说明**: {suggestion or '这是一条测试消息'}",
            ]
        else:
            title = "🚨 资源告警"
            lines = [
                f"## 🚨 资源告警",
                f"**类型**: {metric_label} 持续高负载",
                f"**主机**: {hostname}",
                f"**当前值**: {value:.1f}%",
                f"**阈值**: {threshold:.1f}% (持续 {sustained_seconds}s)",
                f"**时间**: {self._format_timestamp()}",
                f"**建议**: {suggestion}",
            ]
        content = "\n".join(lines)
        return {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }

    def _build_dingtalk_payload(
        self,
        event: str,
        alert_type: str,
        metric: str,
        value: float,
        threshold: float,
        sustained_seconds: int,
        hostname: str,
        suggestion: str,
    ) -> Dict[str, Any]:
        """钉钉 Markdown 消息。"""
        metric_label = METRIC_LABELS.get(metric, metric)
        if event == "recovery":
            title = "✅ 资源恢复"
            text = (
                f"### ✅ 资源恢复\n\n"
                f"**类型**: {metric_label} 已恢复正常\n\n"
                f"**主机**: {hostname}\n\n"
                f"**最近告警值**: {value:.1f}%\n\n"
                f"**时间**: {self._format_timestamp()}\n\n"
                f"**告警类型**: {alert_type}\n"
            )
        elif event == "test":
            title = "🔔 测试告警"
            text = (
                f"### 🔔 测试告警\n\n"
                f"**主机**: {hostname}\n\n"
                f"**平台**: 钉钉\n\n"
                f"**时间**: {self._format_timestamp()}\n\n"
                f"**说明**: {suggestion or '这是一条测试消息'}\n"
            )
        else:
            title = "🚨 资源告警"
            text = (
                f"### 🚨 资源告警\n\n"
                f"**类型**: {metric_label} 持续高负载\n\n"
                f"**主机**: {hostname}\n\n"
                f"**当前值**: {value:.1f}%\n\n"
                f"**阈值**: {threshold:.1f}% (持续 {sustained_seconds}s)\n\n"
                f"**时间**: {self._format_timestamp()}\n\n"
                f"**建议**: {suggestion}\n"
            )
        return {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }

    def _build_feishu_payload(
        self,
        event: str,
        alert_type: str,
        metric: str,
        value: float,
        threshold: float,
        sustained_seconds: int,
        hostname: str,
        suggestion: str,
    ) -> Dict[str, Any]:
        """飞书 Interactive Card 消息。"""
        metric_label = METRIC_LABELS.get(metric, metric)

        if event == "recovery":
            template = "green"
            header_title = "✅ 资源恢复"
            elements = [
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**类型**: {metric_label} 已恢复正常"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**主机**: {hostname}"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**最近告警值**: {value:.1f}%"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**时间**: {self._format_timestamp()}"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**告警类型**: {alert_type}"}},
            ]
        elif event == "test":
            template = "blue"
            header_title = "🔔 测试告警"
            elements = [
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**主机**: {hostname}"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**平台**: 飞书"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**时间**: {self._format_timestamp()}"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**说明**: {suggestion or '这是一条测试消息'}"}},
            ]
        else:
            template = "red"
            header_title = "🚨 资源告警"
            elements = [
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**类型**: {metric_label} 持续高负载"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**主机**: {hostname}"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**当前值**: {value:.1f}%"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**阈值**: {threshold:.1f}% (持续 {sustained_seconds}s)"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**时间**: {self._format_timestamp()}"}},
                {"tag": "div", "text": {"tag": "lark_md",
                    "content": f"**建议**: {suggestion}"}},
                {"tag": "note",
                 "elements": [{"tag": "plain_text",
                               "content": f"alert_type={alert_type}"}]},
            ]

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": header_title},
                    "template": template,
                },
                "elements": elements,
            },
        }


# ============================================================
# 工厂函数
# ============================================================
def create_notifier_from_settings(settings_obj: Any) -> Optional[WebhookNotifier]:
    """根据 ``Settings`` 实例创建 ``WebhookNotifier``。

    当 ``webhook_enabled=False`` 或 URL 为空时返回 ``None``。

    Args:
        settings_obj: ``puppet-automation/src/config/settings.py`` 的 Settings 实例。

    Returns:
        配置好的 ``WebhookNotifier`` 实例，或 ``None`` 表示未启用。
    """
    if not getattr(settings_obj, "webhook_enabled", False):
        return None
    url = getattr(settings_obj, "webhook_url", "") or ""
    if not url:
        logger.warning("webhook_enabled=True 但 webhook_url 未配置，跳过初始化")
        return None
    try:
        return WebhookNotifier(
            platform=getattr(settings_obj, "webhook_platform", "wechat"),
            url=url,
            secret=getattr(settings_obj, "webhook_secret", "") or "",
            quiet_minutes=getattr(settings_obj, "webhook_quiet_minutes", 5),
            max_retries=getattr(settings_obj, "webhook_max_retries", 3),
            retry_interval=getattr(settings_obj, "webhook_retry_interval", 5.0),
            timeout=getattr(settings_obj, "webhook_timeout", 10.0),
            hostname=getattr(settings_obj, "alert_hostname", "") or "",
        )
    except Exception as e:  # pragma: no cover - 配置错误兜底
        logger.error(f"WebhookNotifier 初始化失败: {e}")
        return None

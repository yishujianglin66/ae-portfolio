#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控告警系统
============

提供 Prometheus 指标采集与告警通知能力。

功能:
- 自定义指标注册 (Counter / Gauge / Histogram / Summary)
- Prometheus 文本格式导出 (/metrics 端点)
- 告警规则评估 (阈值触发)
- 多渠道通知 (日志 / Webhook / 邮件占位)
- 告警状态机 (pending -> firing -> resolved)
- 系统资源自动采集 (CPU / 内存 / 磁盘 / 网络)
- FastAPI 集成中间件 (请求计数 / 延迟直方图)
- 指标缓存与并发安全
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from datetime import datetime

try:
    from logger import get_logger
    _logger = get_logger("metrics")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("metrics")


# ============================================================================
# 指标类型枚举
# ============================================================================

class MetricType(str, Enum):
    COUNTER = "counter"      # 单调递增 (如请求数)
    GAUGE = "gauge"          # 可增可减 (如内存使用)
    HISTOGRAM = "histogram"  # 直方图 (如请求延迟分布)
    SUMMARY = "summary"      # 摘要 (如分位数)


class AlertState(str, Enum):
    PENDING = "pending"    # 已触发但未达持续时间
    FIRING = "firing"      # 持续中
    RESOLVED = "resolved"  # 已恢复


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


# ============================================================================
# 指标数据结构
# ============================================================================

@dataclass(frozen=True)
class LabelSet:
    """标签集合"""
    labels: Tuple[Tuple[str, str], ...]

    @classmethod
    def from_dict(cls, labels: Optional[Dict[str, str]] = None) -> "LabelSet":
        if not labels:
            return cls(labels=())
        return cls(labels=tuple(sorted(labels.items())))

    def to_dict(self) -> Dict[str, str]:
        return dict(self.labels)

    def to_str(self) -> str:
        if not self.labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in self.labels]
        return "{" + ",".join(parts) + "}"


@dataclass
class MetricSample:
    """指标样本"""
    name: str
    labels: LabelSet
    value: float
    timestamp: float = field(default_factory=time.time)


class Counter:
    """计数器 (单调递增)"""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help = help_text
        self._values: Dict[LabelSet, float] = defaultdict(float)
        self._lock = threading.RLock()

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        if value < 0:
            raise ValueError("Counter 只能递增")
        ls = LabelSet.from_dict(labels)
        with self._lock:
            self._values[ls] += value

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        ls = LabelSet.from_dict(labels)
        with self._lock:
            return self._values.get(ls, 0.0)

    def samples(self) -> List[MetricSample]:
        with self._lock:
            return [
                MetricSample(self.name, ls, val)
                for ls, val in self._values.items()
            ]

    def export(self) -> str:
        """导出 Prometheus 文本格式"""
        lines = []
        if self.help:
            lines.append(f"# HELP {self.name} {self.help}")
        lines.append(f"# TYPE {self.name} counter")
        for sample in self.samples():
            lines.append(f"{sample.name}{sample.labels.to_str()} {sample.value}")
        return "\n".join(lines)


class Gauge:
    """仪表盘 (可增可减)"""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help = help_text
        self._values: Dict[LabelSet, float] = defaultdict(float)
        self._lock = threading.RLock()

    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        ls = LabelSet.from_dict(labels)
        with self._lock:
            self._values[ls] = value

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        ls = LabelSet.from_dict(labels)
        with self._lock:
            self._values[ls] += value

    def dec(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        self.inc(-value, labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        ls = LabelSet.from_dict(labels)
        with self._lock:
            return self._values.get(ls, 0.0)

    def samples(self) -> List[MetricSample]:
        with self._lock:
            return [
                MetricSample(self.name, ls, val)
                for ls, val in self._values.items()
            ]

    def export(self) -> str:
        lines = []
        if self.help:
            lines.append(f"# HELP {self.name} {self.help}")
        lines.append(f"# TYPE {self.name} gauge")
        for sample in self.samples():
            lines.append(f"{sample.name}{sample.labels.to_str()} {sample.value}")
        return "\n".join(lines)


class Histogram:
    """直方图"""

    DEFAULT_BUCKETS = (
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5,
        1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0,
    )

    def __init__(self, name: str, help_text: str = "",
                 buckets: Optional[Tuple[float, ...]] = None):
        self.name = name
        self.help = help_text
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: Dict[LabelSet, List[int]] = defaultdict(
            lambda: [0] * (len(self.buckets) + 1)
        )
        self._sums: Dict[LabelSet, float] = defaultdict(float)
        self._totals: Dict[LabelSet, int] = defaultdict(int)
        self._lock = threading.RLock()

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        ls = LabelSet.from_dict(labels)
        with self._lock:
            idx = 0
            for i, bound in enumerate(self.buckets):
                if value <= bound:
                    idx = i
                    break
            else:
                idx = len(self.buckets)
            # 累积计数
            counts = self._counts[ls]
            for i in range(idx, len(counts)):
                counts[i] += 1
            self._sums[ls] += value
            self._totals[ls] += 1

    def samples(self) -> List[MetricSample]:
        with self._lock:
            samples = []
            for ls in self._counts:
                counts = self._counts[ls]
                for i, bound in enumerate(self.buckets):
                    label_dict = ls.to_dict()
                    label_dict["le"] = str(bound)
                    samples.append(MetricSample(
                        f"{self.name}_bucket",
                        LabelSet.from_dict(label_dict),
                        float(counts[i]),
                    ))
                # +Inf 桶
                label_dict = ls.to_dict()
                label_dict["le"] = "+Inf"
                samples.append(MetricSample(
                    f"{self.name}_bucket",
                    LabelSet.from_dict(label_dict),
                    float(counts[-1]),
                ))
                samples.append(MetricSample(
                    f"{self.name}_sum", ls, self._sums[ls]
                ))
                samples.append(MetricSample(
                    f"{self.name}_count", ls, float(self._totals[ls])
                ))
            return samples

    def export(self) -> str:
        lines = []
        if self.help:
            lines.append(f"# HELP {self.name} {self.help}")
        lines.append(f"# TYPE {self.name} histogram")
        for sample in self.samples():
            lines.append(f"{sample.name}{sample.labels.to_str()} {sample.value}")
        return "\n".join(lines)

    def quantile(self, q: float, labels: Optional[Dict[str, str]] = None) -> float:
        """估算分位数 (基于 bucket)"""
        ls = LabelSet.from_dict(labels)
        with self._lock:
            total = self._totals.get(ls, 0)
            if total == 0:
                return 0.0
            target = q * total
            counts = self._counts.get(ls, [0] * (len(self.buckets) + 1))
            cumulative = 0
            for i, bound in enumerate(self.buckets):
                cumulative = counts[i]
                if cumulative >= target:
                    return bound
            return self.buckets[-1] if self.buckets else 0.0


class Summary:
    """摘要 (基于滑动窗口)"""

    def __init__(self, name: str, help_text: str = "",
                 window_size: int = 60, max_samples: int = 1000):
        self.name = name
        self.help = help_text
        self.window_size = window_size
        self.max_samples = max_samples
        self._samples: Dict[LabelSet, deque] = defaultdict(
            lambda: deque(maxlen=max_samples)
        )
        self._lock = threading.RLock()

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        ls = LabelSet.from_dict(labels)
        with self._lock:
            self._samples[ls].append((time.time(), value))

    def quantile(self, q: float, labels: Optional[Dict[str, str]] = None) -> float:
        ls = LabelSet.from_dict(labels)
        now = time.time()
        with self._lock:
            samples = [
                v for t, v in self._samples[ls]
                if now - t <= self.window_size
            ]
        if not samples:
            return 0.0
        samples.sort()
        idx = max(0, min(len(samples) - 1, int(q * len(samples))))
        return samples[idx]

    def samples(self) -> List[MetricSample]:
        result = []
        for q in (0.5, 0.9, 0.99):
            with self._lock:
                label_sets = list(self._samples.keys())
            for ls in label_sets:
                label_dict = ls.to_dict()
                label_dict["quantile"] = str(q)
                result.append(MetricSample(
                    self.name,
                    LabelSet.from_dict(label_dict),
                    self.quantile(q, ls.to_dict()),
                ))
        # sum 和 count
        now = time.time()
        with self._lock:
            for ls, samples in self._samples.items():
                valid = [v for t, v in samples if now - t <= self.window_size]
                if valid:
                    result.append(MetricSample(
                        f"{self.name}_sum", ls, sum(valid)
                    ))
                    result.append(MetricSample(
                        f"{self.name}_count", ls, float(len(valid))
                    ))
        return result

    def export(self) -> str:
        lines = []
        if self.help:
            lines.append(f"# HELP {self.name} {self.help}")
        lines.append(f"# TYPE {self.name} summary")
        for sample in self.samples():
            lines.append(f"{sample.name}{sample.labels.to_str()} {sample.value}")
        return "\n".join(lines)


# ============================================================================
# 告警
# ============================================================================

@dataclass
class AlertRule:
    """告警规则"""
    name: str
    expression: Callable[["MetricsRegistry"], float]  # 返回指标值
    threshold: float
    comparison: str = ">"  # >, <, >=, <=, ==, !=
    duration: float = 0.0  # 持续时间 (秒), 0=立即触发
    severity: AlertSeverity = AlertSeverity.WARNING
    message: str = ""
    labels: Dict[str, str] = field(default_factory=dict)

    def evaluate(self, registry: "MetricsRegistry") -> bool:
        value = self.expression(registry)
        if self.comparison == ">":
            return value > self.threshold
        elif self.comparison == "<":
            return value < self.threshold
        elif self.comparison == ">=":
            return value >= self.threshold
        elif self.comparison == "<=":
            return value <= self.threshold
        elif self.comparison == "==":
            return abs(value - self.threshold) < 1e-9
        elif self.comparison == "!=":
            return abs(value - self.threshold) >= 1e-9
        return False


@dataclass
class Alert:
    """告警实例"""
    alert_id: str
    rule: AlertRule
    state: AlertState
    value: float
    started_at: float
    fired_at: Optional[float] = None
    resolved_at: Optional[float] = None
    last_evaluated: float = field(default_factory=time.time)
    notifications_sent: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "name": self.rule.name,
            "state": self.state.value,
            "severity": self.rule.severity.value,
            "value": self.value,
            "threshold": self.rule.threshold,
            "comparison": self.rule.comparison,
            "message": self.rule.message,
            "started_at": self.started_at,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
            "last_evaluated": self.last_evaluated,
            "labels": self.rule.labels,
        }


class AlertManager:
    """告警管理器"""

    def __init__(self, registry: "MetricsRegistry"):
        self.registry = registry
        self._rules: List[AlertRule] = []
        self._active_alerts: Dict[str, Alert] = {}  # rule_name -> Alert
        self._history: List[Alert] = []
        self._lock = threading.RLock()
        self._notifiers: List[Callable[[Alert], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._eval_interval = 5.0

    def add_rule(self, rule: AlertRule) -> None:
        with self._lock:
            self._rules.append(rule)
        _logger.info(f"已添加告警规则: {rule.name} ({rule.severity.value})")

    def add_notifier(self, notifier: Callable[[Alert], None]) -> None:
        self._notifiers.append(notifier)

    def evaluate(self) -> List[Alert]:
        """评估所有规则, 返回本次新触发/状态变更的告警列表"""
        changed = []
        with self._lock:
            rules = list(self._rules)
            active = dict(self._active_alerts)

        now = time.time()
        for rule in rules:
            try:
                triggered = rule.evaluate(self.registry)
                value = rule.expression(self.registry)
            except Exception as e:
                _logger.error(f"评估规则 {rule.name} 失败: {e}")
                continue

            existing = active.get(rule.name)

            if triggered:
                if existing is None:
                    # 新告警
                    alert = Alert(
                        alert_id=uuid.uuid4().hex[:12],
                        rule=rule,
                        state=AlertState.PENDING,
                        value=value,
                        started_at=now,
                    )
                    with self._lock:
                        self._active_alerts[rule.name] = alert
                    changed.append(alert)
                    _logger.info(f"告警触发 (pending): {rule.name} value={value:.2f}")
                else:
                    existing.value = value
                    existing.last_evaluated = now
                    # 检查是否达到持续时间
                    if existing.state == AlertState.PENDING:
                        if now - existing.started_at >= rule.duration:
                            existing.state = AlertState.FIRING
                            existing.fired_at = now
                            changed.append(existing)
                            self._notify(existing)
                            _logger.warning(
                                f"告警触发 (firing): {rule.name} "
                                f"value={value:.2f} threshold={rule.threshold}"
                            )
            else:
                if existing is not None:
                    existing.state = AlertState.RESOLVED
                    existing.resolved_at = now
                    existing.last_evaluated = now
                    changed.append(existing)
                    self._notify(existing)
                    with self._lock:
                        self._active_alerts.pop(rule.name, None)
                        self._history.append(existing)
                        if len(self._history) > 1000:
                            self._history = self._history[-1000:]
                    _logger.info(f"告警已恢复: {rule.name}")

        return changed

    def _notify(self, alert: Alert) -> None:
        """通知所有 notifiers"""
        for notifier in self._notifiers:
            try:
                notifier(alert)
            except Exception as e:
                _logger.error(f"通知器执行失败: {e}")
        alert.notifications_sent += 1

    def start(self, eval_interval: float = 5.0) -> None:
        """启动后台评估线程"""
        if self._running:
            return
        self._eval_interval = eval_interval
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        _logger.info(f"告警评估线程已启动 (间隔 {eval_interval}s)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        _logger.info("告警评估线程已停止")

    def _run(self) -> None:
        while self._running:
            try:
                self.evaluate()
            except Exception as e:
                _logger.error(f"告警评估异常: {e}")
            time.sleep(self._eval_interval)

    def list_active_alerts(self) -> List[Alert]:
        with self._lock:
            return list(self._active_alerts.values())

    def list_history(self, limit: int = 100) -> List[Alert]:
        with self._lock:
            return list(self._history[-limit:])


# ============================================================================
# 指标注册中心
# ============================================================================

class MetricsRegistry:
    """指标注册中心"""

    def __init__(self):
        self._metrics: Dict[str, Union[Counter, Gauge, Histogram, Summary]] = {}
        self._lock = threading.RLock()
        self._init_default_metrics()

    def _init_default_metrics(self) -> None:
        """初始化默认系统指标"""
        # HTTP 请求指标
        self.register(Counter(
            "http_requests_total",
            "HTTP 请求总数",
        ))
        self.register(Histogram(
            "http_request_duration_seconds",
            "HTTP 请求处理耗时",
        ))
        self.register(Gauge(
            "http_requests_in_progress",
            "处理中的 HTTP 请求数",
        ))

        # 任务指标
        self.register(Counter(
            "tasks_total",
            "任务总数",
        ))
        self.register(Counter(
            "tasks_completed_total",
            "已完成的任务总数",
        ))
        self.register(Counter(
            "tasks_failed_total",
            "失败的任务总数",
        ))
        self.register(Gauge(
            "tasks_in_queue",
            "队列中的任务数",
        ))
        self.register(Histogram(
            "task_duration_seconds",
            "任务执行耗时",
        ))

        # 系统资源指标
        self.register(Gauge(
            "system_cpu_percent",
            "CPU 使用率 (%)",
        ))
        self.register(Gauge(
            "system_memory_percent",
            "内存使用率 (%)",
        ))
        self.register(Gauge(
            "system_memory_used_bytes",
            "已用内存 (字节)",
        ))
        self.register(Gauge(
            "system_memory_total_bytes",
            "总内存 (字节)",
        ))
        self.register(Gauge(
            "system_disk_percent",
            "磁盘使用率 (%)",
        ))
        self.register(Gauge(
            "system_disk_free_bytes",
            "磁盘剩余空间 (字节)",
        ))

        # 应用指标
        self.register(Gauge(
            "app_uptime_seconds",
            "应用运行时间 (秒)",
        ))
        self.register(Gauge(
            "app_info",
            "应用信息",
        ))

    def register(self, metric: Union[Counter, Gauge, Histogram, Summary]) -> None:
        with self._lock:
            if metric.name in self._metrics:
                raise ValueError(f"指标已存在: {metric.name}")
            self._metrics[metric.name] = metric

    def counter(self, name: str) -> Counter:
        m = self._metrics.get(name)
        if not isinstance(m, Counter):
            raise KeyError(f"Counter 不存在: {name}")
        return m

    def gauge(self, name: str) -> Gauge:
        m = self._metrics.get(name)
        if not isinstance(m, Gauge):
            raise KeyError(f"Gauge 不存在: {name}")
        return m

    def histogram(self, name: str) -> Histogram:
        m = self._metrics.get(name)
        if not isinstance(m, Histogram):
            raise KeyError(f"Histogram 不存在: {name}")
        return m

    def summary(self, name: str) -> Summary:
        m = self._metrics.get(name)
        if not isinstance(m, Summary):
            raise KeyError(f"Summary 不存在: {name}")
        return m

    def get(self, name: str) -> Optional[Union[Counter, Gauge, Histogram, Summary]]:
        return self._metrics.get(name)

    def list_metrics(self) -> List[str]:
        with self._lock:
            return list(self._metrics.keys())

    def export(self) -> str:
        """导出所有指标为 Prometheus 文本格式"""
        with self._lock:
            metrics = list(self._metrics.values())
        lines = []
        for metric in metrics:
            exported = metric.export()
            if exported:
                lines.append(exported)
        return "\n".join(lines) + "\n"

    def export_dict(self) -> Dict[str, Any]:
        """导出为字典 (JSON 友好)"""
        result = {}
        with self._lock:
            for name, metric in self._metrics.items():
                samples = metric.samples()
                if samples:
                    result[name] = {
                        "type": metric.__class__.__name__.lower(),
                        "help": metric.help,
                        "samples": [
                            {
                                "labels": s.labels.to_dict(),
                                "value": s.value,
                                "timestamp": s.timestamp,
                            }
                            for s in samples
                        ],
                    }
        return result


# ============================================================================
# 系统资源采集器
# ============================================================================

class SystemCollector:
    """系统资源采集器"""

    def __init__(self, registry: MetricsRegistry, interval: float = 10.0):
        self.registry = registry
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        _logger.info(f"系统资源采集器已启动 (间隔 {self.interval}s)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        _logger.info("系统资源采集器已停止")

    def _run(self) -> None:
        while self._running:
            try:
                self.collect()
            except Exception as e:
                _logger.error(f"系统资源采集异常: {e}")
            time.sleep(self.interval)

    def collect(self) -> None:
        """采集一次系统资源"""
        now = time.time()

        # uptime
        try:
            self.registry.gauge("app_uptime_seconds").set(now - self._start_time)
        except Exception:
            pass

        # app_info
        try:
            self.registry.gauge("app_info").set(1.0, {
                "version": "1.0.0",
                "hostname": socket.gethostname(),
                "python": f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
            })
        except Exception:
            pass

        # CPU / 内存
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.registry.gauge("system_cpu_percent").set(cpu_percent)

            mem = psutil.virtual_memory()
            self.registry.gauge("system_memory_percent").set(mem.percent)
            self.registry.gauge("system_memory_used_bytes").set(mem.used)
            self.registry.gauge("system_memory_total_bytes").set(mem.total)
        except ImportError:
            pass

        # 磁盘
        try:
            if os.name == "nt":
                # Windows
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(os.getcwd()),
                    None,
                    ctypes.pointer(total_bytes),
                    ctypes.pointer(free_bytes),
                )
                used = total_bytes.value - free_bytes.value
                percent = (used / total_bytes.value * 100) if total_bytes.value else 0
                self.registry.gauge("system_disk_percent").set(percent)
                self.registry.gauge("system_disk_free_bytes").set(float(free_bytes.value))
            else:
                import shutil
                usage = shutil.disk_usage("/")
                percent = (usage.used / usage.total * 100) if usage.total else 0
                self.registry.gauge("system_disk_percent").set(percent)
                self.registry.gauge("system_disk_free_bytes").set(float(usage.free))
        except Exception as e:
            _logger.debug(f"磁盘信息获取失败: {e}")


# ============================================================================
# 通知器
# ============================================================================

def log_notifier(alert: Alert) -> None:
    """日志通知器"""
    if alert.state == AlertState.FIRING:
        _logger.warning(
            f"[告警触发] {alert.rule.name}: {alert.rule.message} "
            f"(value={alert.value:.2f}, threshold={alert.rule.threshold})"
        )
    elif alert.state == AlertState.RESOLVED:
        _logger.info(
            f"[告警恢复] {alert.rule.name}: value={alert.value:.2f}"
        )
    elif alert.state == AlertState.PENDING:
        _logger.info(
            f"[告警待确认] {alert.rule.name}: value={alert.value:.2f}"
        )


def webhook_notifier(url: str) -> Callable[[Alert], None]:
    """Webhook 通知器工厂"""
    def notifier(alert: Alert) -> None:
        try:
            import urllib.request
            data = json.dumps(alert.to_dict()).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5.0)
        except Exception as e:
            _logger.error(f"Webhook 通知失败: {e}")
    return notifier


# ============================================================================
# FastAPI 中间件
# ============================================================================

def create_metrics_middleware(registry: MetricsRegistry):
    """创建 FastAPI 指标采集中间件

    用法:
        registry = get_metrics_registry()
        middleware = create_metrics_middleware(registry)

        @app.middleware("http")
        async def metrics_middleware(request, call_next):
            return await middleware(request, call_next)
    """
    def middleware(request, call_next):
        import asyncio

        async def _middleware(request, call_next):
            start_time = time.time()
            method = request.method
            endpoint = request.url.path

            # 增加进行中请求
            registry.gauge("http_requests_in_progress").inc(
                labels={"method": method}
            )
            registry.counter("http_requests_total").inc(
                labels={"method": method, "endpoint": endpoint}
            )

            try:
                response = await call_next(request)
                status_code = str(response.status_code)
                registry.counter("http_requests_total").inc(
                    labels={
                        "method": method,
                        "endpoint": endpoint,
                        "status": status_code,
                    }
                )
                return response
            except Exception as e:
                registry.counter("http_requests_total").inc(
                    labels={
                        "method": method,
                        "endpoint": endpoint,
                        "status": "500",
                    }
                )
                raise
            finally:
                duration = time.time() - start_time
                registry.histogram("http_request_duration_seconds").observe(
                    duration,
                    labels={"method": method, "endpoint": endpoint},
                )
                registry.gauge("http_requests_in_progress").dec(
                    labels={"method": method}
                )

        return _middleware(request, call_next)

    return middleware


def create_metrics_endpoint(registry: MetricsRegistry):
    """创建 /metrics 端点处理函数

    用法:
        metrics_endpoint = create_metrics_endpoint(registry)

        @app.get("/metrics")
        async def get_metrics():
            return PlainTextResponse(metrics_endpoint())
    """
    def endpoint():
        return registry.export()

    return endpoint


# ============================================================================
# 单例
# ============================================================================

_registry: Optional[MetricsRegistry] = None
_alert_manager: Optional[AlertManager] = None
_system_collector: Optional[SystemCollector] = None


def get_metrics_registry() -> MetricsRegistry:
    """获取指标注册中心单例"""
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


def get_alert_manager() -> AlertManager:
    """获取告警管理器单例"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager(get_metrics_registry())
        _alert_manager.add_notifier(log_notifier)
    return _alert_manager


def get_system_collector(interval: float = 10.0) -> SystemCollector:
    """获取系统资源采集器单例"""
    global _system_collector
    if _system_collector is None:
        _system_collector = SystemCollector(get_metrics_registry(), interval=interval)
    return _system_collector


# ============================================================================
# 测试
# ============================================================================

def _run_tests():
    """运行测试"""
    print("=" * 70)
    print("  监控告警系统测试 (Prometheus 指标)")
    print("=" * 70)

    # 使用独立实例
    registry = MetricsRegistry()

    # ---------- 1. 默认指标 ----------
    print("\n1. 默认指标...")
    metrics = registry.list_metrics()
    assert len(metrics) > 0, "应有默认指标"
    print(f"  已注册指标数: {len(metrics)}")
    for name in metrics[:5]:
        print(f"    - {name}")
    print(f"    ... (共 {len(metrics)} 个)")

    # ---------- 2. Counter ----------
    print("\n2. Counter...")
    counter = registry.counter("http_requests_total")
    counter.inc(labels={"method": "GET", "endpoint": "/api/v1/tasks"})
    counter.inc(labels={"method": "GET", "endpoint": "/api/v1/tasks"})
    counter.inc(5, labels={"method": "POST", "endpoint": "/api/v1/tasks"})
    assert counter.get(labels={"method": "GET", "endpoint": "/api/v1/tasks"}) == 2
    assert counter.get(labels={"method": "POST", "endpoint": "/api/v1/tasks"}) == 5
    print(f"  GET /api/v1/tasks: {counter.get(labels={'method': 'GET', 'endpoint': '/api/v1/tasks'})}")
    print(f"  POST /api/v1/tasks: {counter.get(labels={'method': 'POST', 'endpoint': '/api/v1/tasks'})}")

    # 负值应失败
    try:
        counter.inc(-1)
        assert False
    except ValueError:
        print(f"  负值拒绝: OK")

    # ---------- 3. Gauge ----------
    print("\n3. Gauge...")
    gauge = registry.gauge("system_cpu_percent")
    gauge.set(45.6)
    assert gauge.get() == 45.6
    gauge.inc(10)
    assert gauge.get() == 55.6
    gauge.dec(5)
    assert gauge.get() == 50.6
    print(f"  CPU 使用率: {gauge.get()}%")

    gauge.set(80.0, labels={"core": "0"})
    gauge.set(60.0, labels={"core": "1"})
    print(f"  Core 0: {gauge.get(labels={'core': '0'})}%")
    print(f"  Core 1: {gauge.get(labels={'core': '1'})}%")

    # ---------- 4. Histogram ----------
    print("\n4. Histogram...")
    hist = registry.histogram("http_request_duration_seconds")
    for v in [0.005, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]:
        hist.observe(v)
    samples = hist.samples()
    assert len(samples) > 0
    print(f"  样本数: {len(samples)}")
    print(f"  P50 估算: {hist.quantile(0.5):.3f}s")
    print(f"  P90 估算: {hist.quantile(0.9):.3f}s")
    print(f"  P99 估算: {hist.quantile(0.99):.3f}s")

    # ---------- 5. Summary ----------
    print("\n5. Summary...")
    summary = Summary("test_summary", "测试摘要")
    for v in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
        summary.observe(v)
    print(f"  P50: {summary.quantile(0.5):.2f}")
    print(f"  P90: {summary.quantile(0.9):.2f}")
    print(f"  P99: {summary.quantile(0.99):.2f}")

    # ---------- 6. Prometheus 导出 ----------
    print("\n6. Prometheus 文本导出...")
    text = registry.export()
    assert "# HELP" in text
    assert "# TYPE" in text
    lines = text.strip().split("\n")
    print(f"  导出行数: {len(lines)}")
    # 显示前 10 行
    for line in lines[:10]:
        print(f"    {line[:80]}{'...' if len(line) > 80 else ''}")
    print(f"    ... (共 {len(lines)} 行)")

    # ---------- 7. JSON 导出 ----------
    print("\n7. JSON 导出...")
    data = registry.export_dict()
    assert "http_requests_total" in data
    print(f"  指标数: {len(data)}")
    http_metric = data["http_requests_total"]
    print(f"  http_requests_total 类型: {http_metric['type']}")
    print(f"  http_requests_total 样本数: {len(http_metric['samples'])}")

    # ---------- 8. 告警规则 ----------
    print("\n8. 告警规则...")
    alert_mgr = AlertManager(registry)
    alert_mgr.add_notifier(log_notifier)

    # CPU 高使用率告警 (持续时间 0s 立即触发)
    alert_mgr.add_rule(AlertRule(
        name="high_cpu_usage",
        expression=lambda r: r.gauge("system_cpu_percent").get(),
        threshold=40.0,
        comparison=">",
        duration=0.0,
        severity=AlertSeverity.WARNING,
        message="CPU 使用率过高",
    ))

    # 内存高使用率告警 (持续时间 0s)
    alert_mgr.add_rule(AlertRule(
        name="high_memory_usage",
        expression=lambda r: r.gauge("system_memory_percent").get(),
        threshold=90.0,
        comparison=">",
        duration=0.0,
        severity=AlertSeverity.CRITICAL,
        message="内存使用率过高",
    ))

    print(f"  规则数: {len(alert_mgr._rules)}")

    # ---------- 9. 告警评估 ----------
    print("\n9. 告警评估...")
    # CPU 已设为 50.6, 应触发
    changed = alert_mgr.evaluate()
    assert len(changed) > 0, "应有告警触发"
    fired = [a for a in changed if a.rule.name == "high_cpu_usage"]
    assert len(fired) > 0, "CPU 告警应触发"
    print(f"  触发告警数: {len(changed)}")
    for alert in changed:
        print(f"    - {alert.rule.name}: state={alert.state.value}, value={alert.value:.2f}")

    # ---------- 10. 告警状态机 ----------
    print("\n10. 告警状态机 (持续时间)...")
    # 新增高持续时间告警
    alert_mgr.add_rule(AlertRule(
        name="cpu_warning",
        expression=lambda r: r.gauge("system_cpu_percent").get(),
        threshold=40.0,
        comparison=">",
        duration=1.0,  # 持续 1 秒
        severity=AlertSeverity.WARNING,
        message="CPU 持续偏高",
    ))

    # 第一次评估: PENDING
    changed = alert_mgr.evaluate()
    pending = [a for a in changed if a.rule.name == "cpu_warning"]
    if pending:
        assert pending[0].state == AlertState.PENDING
        print(f"  PENDING: OK (value={pending[0].value:.2f})")

    # 等待 1.5 秒
    time.sleep(1.5)

    # 第二次评估: FIRING
    changed = alert_mgr.evaluate()
    firing = [a for a in changed if a.rule.name == "cpu_warning"]
    if firing:
        assert firing[0].state == AlertState.FIRING
        print(f"  FIRING: OK (value={firing[0].value:.2f})")

    # ---------- 11. 告警恢复 ----------
    print("\n11. 告警恢复...")
    # 把 CPU 降到阈值以下
    registry.gauge("system_cpu_percent").set(20.0)
    changed = alert_mgr.evaluate()
    resolved = [a for a in changed if a.state == AlertState.RESOLVED]
    assert len(resolved) > 0, "应有告警恢复"
    print(f"  恢复告警数: {len(resolved)}")
    for alert in resolved:
        print(f"    - {alert.rule.name}: resolved at value={alert.value:.2f}")

    # ---------- 12. 活跃告警列表 ----------
    print("\n12. 活跃告警列表...")
    active = alert_mgr.list_active_alerts()
    print(f"  活跃告警数: {len(active)}")
    for alert in active:
        print(f"    - {alert.rule.name}: {alert.state.value} (value={alert.value:.2f})")

    # ---------- 13. 告警历史 ----------
    print("\n13. 告警历史...")
    history = alert_mgr.list_history()
    print(f"  历史告警数: {len(history)}")
    for alert in history[-3:]:
        print(f"    - {alert.rule.name}: {alert.state.value} -> resolved")

    # ---------- 14. 系统资源采集 ----------
    print("\n14. 系统资源采集...")
    collector = SystemCollector(registry, interval=60.0)
    collector.collect()  # 手动采集一次
    uptime = registry.gauge("app_uptime_seconds").get()
    print(f"  运行时间: {uptime:.2f}s")

    try:
        import psutil
        cpu = registry.gauge("system_cpu_percent").get()
        mem = registry.gauge("system_memory_percent").get()
        print(f"  CPU: {cpu:.1f}%")
        print(f"  内存: {mem:.1f}%")
    except ImportError:
        print(f"  psutil 未安装, 跳过 CPU/内存采集")

    disk = registry.gauge("system_disk_percent").get()
    disk_free = registry.gauge("system_disk_free_bytes").get()
    print(f"  磁盘使用率: {disk:.1f}%")
    print(f"  磁盘剩余: {disk_free / (1024**3):.2f} GB")

    # ---------- 15. 后台评估线程 ----------
    print("\n15. 后台评估线程...")
    alert_mgr.start(eval_interval=0.5)
    print(f"  线程已启动: {alert_mgr._thread.is_alive()}")
    time.sleep(1.5)
    alert_mgr.stop()
    print(f"  线程已停止")

    # ---------- 16. FastAPI 集成 ----------
    print("\n16. FastAPI 集成...")
    try:
        middleware = create_metrics_middleware(registry)
        endpoint = create_metrics_endpoint(registry)
        assert callable(middleware)
        assert callable(endpoint)
        print(f"  中间件创建: OK")
        print(f"  端点函数创建: OK")
        # 端点输出
        output = endpoint()
        assert "# TYPE" in output
        print(f"  端点输出长度: {len(output)} 字符")
    except Exception as e:
        print(f"  FastAPI 集成失败: {e}")

    # ---------- 17. 自定义指标 ----------
    print("\n17. 自定义指标...")
    custom_counter = Counter("custom_operations_total", "自定义操作计数")
    custom_gauge = Gauge("custom_queue_size", "自定义队列大小")
    custom_hist = Histogram("custom_processing_seconds", "自定义处理耗时")
    registry.register(custom_counter)
    registry.register(custom_gauge)
    registry.register(custom_hist)

    custom_counter.inc(labels={"op": "insert"})
    custom_counter.inc(labels={"op": "insert"})
    custom_counter.inc(labels={"op": "delete"})
    custom_gauge.set(42)
    custom_hist.observe(0.15)

    assert custom_counter.get(labels={"op": "insert"}) == 2
    assert custom_counter.get(labels={"op": "delete"}) == 1
    assert custom_gauge.get() == 42
    print(f"  insert: {custom_counter.get(labels={'op': 'insert'})}")
    print(f"  delete: {custom_counter.get(labels={'op': 'delete'})}")
    print(f"  queue_size: {custom_gauge.get()}")

    # ---------- 18. 并发安全 ----------
    print("\n18. 并发安全...")
    def worker(worker_id: int):
        for _ in range(100):
            custom_counter.inc(labels={"worker": str(worker_id)})
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total = sum(custom_counter.get(labels={"worker": str(i)}) for i in range(5))
    assert total == 500, f"并发计数错误: {total}"
    print(f"  5 线程 x 100 次 = {total}: OK")

    # ---------- 19. Webhook 通知器 ----------
    print("\n19. Webhook 通知器...")
    wh = webhook_notifier("http://localhost:9999/nonexistent")
    # 应不会抛出异常 (只是记录错误)
    fake_alert = Alert(
        alert_id="test",
        rule=AlertRule(
            name="test", expression=lambda r: 0, threshold=0,
            message="测试"
        ),
        state=AlertState.FIRING,
        value=1.0,
        started_at=time.time(),
    )
    wh(fake_alert)
    print(f"  Webhook 失败容错: OK")

    # ---------- 20. 统计 ----------
    print("\n20. 统计...")
    print(f"  指标总数: {len(registry.list_metrics())}")
    print(f"  活跃告警: {len(alert_mgr.list_active_alerts())}")
    print(f"  告警历史: {len(alert_mgr.list_history())}")

    print("\n" + "=" * 70)
    print("  测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    _run_tests()

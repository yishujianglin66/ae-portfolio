"""资源监控服务 - 基于 psutil 的 CPU/内存/磁盘/GPU 监控。

提供周期性采样、阈值告警与统计信息能力。所有 psutil 调用均通过
``asyncio.to_thread`` 包装为异步，避免阻塞事件循环。psutil 与 pynvml
均为可选依赖：若未安装则降级为不可用状态，不影响主流程。

持续告警状态机：
    normal → warning → critical → sustained_alert → notifying → notified
                                                                ↓
                                                            recovering → normal

    - ``normal``: 资源正常
    - ``warning``: 单次超过阈值
    - ``critical``: 严重超过阈值（threshold + 5）
    - ``sustained_alert``: 持续超过阈值达到指定秒数
    - ``notifying``: 正在发送 webhook 通知
    - ``notified``: webhook 通知已发送，等待资源恢复
    - ``recovering``: 资源已恢复，正在发送恢复通知
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from .webhook_notifier import AlertRecord, WebhookNotifier

# psutil 为可选依赖，缺失时禁用相应能力
try:
    import psutil  # type: ignore
    _PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover - 环境差异
    psutil = None  # type: ignore
    _PSUTIL_AVAILABLE = False
    logger.warning("psutil 未安装，资源监控服务将降级为空数据")

# pynvml（NVIDIA GPU 监控）同样为可选依赖
try:
    import pynvml  # type: ignore
    _PYNVML_AVAILABLE = True
except ImportError:  # pragma: no cover - 环境差异
    pynvml = None  # type: ignore
    _PYNVML_AVAILABLE = False


class ResourceMonitorService:
    """系统资源监控服务，支持周期性采样和告警。

    监控维度：
        - CPU 使用率（总体 + 每核）
        - 内存使用率与可用量
        - 系统盘使用率
        - GPU 使用率 / 显存（若 pynvml 可用）

    采样数据保留最近 ``_max_samples`` 条（默认 100）。当任一指标超过
    ``_thresholds`` 配置时生成告警，告警 severity 取 warning / critical。

    持续告警：当资源持续超过 ``_sustained_thresholds`` 指定阈值达到
    ``_sustained_seconds`` 秒时，通过 ``WebhookNotifier`` 发送告警通知；
    资源恢复后发送恢复通知。通知发送异步进行，不影响监控主循环。
    """

    def __init__(
        self,
        interval: float = 5.0,
        notifier: Optional[WebhookNotifier] = None,
        sustained_thresholds: Optional[Dict[str, float]] = None,
        sustained_seconds: Optional[Dict[str, int]] = None,
    ) -> None:
        """初始化资源监控服务。

        Args:
            interval: 采样间隔（秒），默认 5.0。
            notifier: ``WebhookNotifier`` 实例。若为 ``None`` 则不发送外部通知，
                仅维护内存中的告警状态。通常由 ``create_notifier_from_settings``
                工厂函数根据配置创建。
            sustained_thresholds: 各指标的持续告警阈值（百分比），默认
                ``{cpu_percent: 90, memory_percent: 90, disk_percent: 95}``。
            sustained_seconds: 各指标的持续触发秒数，默认
                ``{cpu_percent: 30, memory_percent: 30, disk_percent: 60}``。
        """
        self.interval = interval
        self._running: bool = False
        self._samples: List[Dict[str, Any]] = []
        self._max_samples: int = 100  # 保留最近 100 个采样
        self._alerts: List[Dict[str, Any]] = []
        self._thresholds: Dict[str, float] = {
            "cpu_percent": 90.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
        }
        # 持续告警阈值（百分比）：达到此阈值并持续 sustained_seconds 秒后触发 webhook
        self._sustained_thresholds: Dict[str, float] = sustained_thresholds or {
            "cpu_percent": 90.0,
            "memory_percent": 90.0,
            "disk_percent": 95.0,
        }
        self._sustained_seconds: Dict[str, int] = sustained_seconds or {
            "cpu_percent": 30,
            "memory_percent": 30,
            "disk_percent": 60,
        }
        # Webhook 通知器
        self._notifier: Optional[WebhookNotifier] = notifier
        # 持续告警状态追踪：metric -> AlertRecord
        self._sustained_alerts: Dict[str, AlertRecord] = {}
        # 告警事件历史记录（含 webhook 发送结果），用于 API 查询
        self._alert_history: List[Dict[str, Any]] = []
        self._max_alert_history: int = 200
        # GPU 监控句柄，懒初始化
        self._nvml_initialized: bool = False
        self._gpu_device_count: int = 0
        # 后台采样任务句柄
        self._task: Optional[asyncio.Task] = None
        # 采样起点时间，用于计算统计区间
        self._started_at: Optional[float] = None

    # ------------------------------------------------------------------
    # GPU 初始化
    # ------------------------------------------------------------------
    def _ensure_nvml(self) -> None:
        """惰性初始化 pynvml，仅调用一次。"""
        if not _PYNVML_AVAILABLE or self._nvml_initialized:
            return
        try:
            pynvml.nvmlInit()
            self._gpu_device_count = pynvml.nvmlDeviceGetCount()
            self._nvml_initialized = True
            logger.info(
                f"pynvml 初始化成功，检测到 {self._gpu_device_count} 个 NVIDIA GPU"
            )
        except Exception as e:  # pragma: no cover - 依赖硬件
            logger.warning(f"pynvml 初始化失败，GPU 监控将不可用: {e}")
            self._nvml_initialized = False

    def _sample_gpu(self) -> List[Dict[str, Any]]:
        """采集所有 NVIDIA GPU 的状态。失败时返回空列表。"""
        if not _PYNVML_AVAILABLE or not self._nvml_initialized:
            return []
        gpus: List[Dict[str, Any]] = []
        for idx in range(self._gpu_device_count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="ignore")
                gpus.append({
                    "index": idx,
                    "name": name,
                    "gpu_percent": float(util.gpu),
                    "memory_percent": float(util.memory),
                    "memory_used_mb": float(mem.used) / 1024 / 1024,
                    "memory_total_mb": float(mem.total) / 1024 / 1024,
                })
            except Exception as e:  # pragma: no cover - 单 GPU 故障不影响其他
                logger.debug(f"GPU {idx} 采样失败: {e}")
        return gpus

    # ------------------------------------------------------------------
    # 快照采集
    # ------------------------------------------------------------------
    async def get_snapshot(self) -> Dict[str, Any]:
        """获取当前资源快照。

        Returns:
            包含 timestamp / cpu / memory / disk / gpu 字段的字典。
            若 psutil 不可用，则返回带 ``available=False`` 的空快照。
        """
        if not _PSUTIL_AVAILABLE:
            return {
                "timestamp": time.time(),
                "available": False,
                "reason": "psutil not installed",
            }

        def _collect() -> Dict[str, Any]:
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
            mem = psutil.virtual_memory()
            # 取系统盘（项目所在盘）使用率
            try:
                disk = psutil.disk_usage("/")
            except Exception:
                # Windows 下根路径可能为驱动器，回退到 C:
                disk = psutil.disk_usage("C:\\")
            load_avg: Optional[List[float]] = None
            try:
                # loadavg 仅在 POSIX 上可用
                load_avg = list(psutil.getloadavg())
            except (AttributeError, OSError):  # pragma: no cover - 平台差异
                load_avg = None
            return {
                "timestamp": time.time(),
                "cpu_percent": float(cpu_percent),
                "cpu_per_core": [float(v) for v in cpu_per_core],
                "cpu_count": psutil.cpu_count(logical=True),
                "memory": {
                    "total_mb": float(mem.total) / 1024 / 1024,
                    "used_mb": float(mem.used) / 1024 / 1024,
                    "available_mb": float(mem.available) / 1024 / 1024,
                    "percent": float(mem.percent),
                },
                "disk": {
                    "total_gb": float(disk.total) / 1024 / 1024 / 1024,
                    "used_gb": float(disk.used) / 1024 / 1024 / 1024,
                    "free_gb": float(disk.free) / 1024 / 1024 / 1024,
                    "percent": float(disk.percent),
                },
                "load_avg": load_avg,
            }

        try:
            snapshot = await asyncio.to_thread(_collect)
        except Exception as e:
            logger.warning(f"资源采样失败: {e}")
            return {
                "timestamp": time.time(),
                "available": False,
                "reason": str(e),
            }

        # GPU 采集（同样可能阻塞，使用 to_thread）
        try:
            self._ensure_nvml()
            gpus = await asyncio.to_thread(self._sample_gpu)
            snapshot["gpu"] = gpus
            snapshot["gpu_available"] = bool(gpus)
        except Exception as e:  # pragma: no cover - GPU 异常不应影响主流程
            snapshot["gpu"] = []
            snapshot["gpu_available"] = False
            logger.debug(f"GPU 采样异常: {e}")

        snapshot["available"] = True
        return snapshot

    # ------------------------------------------------------------------
    # 周期性监控
    # ------------------------------------------------------------------
    async def start_monitoring(self) -> None:
        """启动周期性监控任务。

        若已有监控任务在运行则直接返回。重复调用是安全的。
        """
        if self._running:
            logger.warning("资源监控任务已在运行，忽略重复启动请求")
            return
        self._running = True
        self._started_at = time.time()
        logger.info(
            f"启动资源监控任务，采样间隔 {self.interval}s，保留 {self._max_samples} 条样本"
        )
        # 立即采集一次，避免首次调用方等待 interval
        await self._sample_once()
        self._task = asyncio.create_task(self._run_loop())

    async def _run_loop(self) -> None:
        """后台采样循环。"""
        try:
            while self._running:
                await asyncio.sleep(self.interval)
                if not self._running:
                    break
                await self._sample_once()
        except asyncio.CancelledError:  # pragma: no cover - 关闭流程
            logger.info("资源监控任务被取消")
            raise
        except Exception as e:  # pragma: no cover - 兜底
            logger.error(f"资源监控循环异常退出: {e}")
        finally:
            self._running = False

    async def _sample_once(self) -> None:
        """执行一次采样、追加到样本列表并触发告警检查。"""
        snapshot = await self.get_snapshot()
        if not snapshot.get("available", False):
            return
        self._samples.append(snapshot)
        # 控制内存占用：保留最近 N 条
        if len(self._samples) > self._max_samples:
            del self._samples[: len(self._samples) - self._max_samples]
        await self._check_thresholds(snapshot)

    def stop_monitoring(self) -> None:
        """停止监控任务。重复调用是安全的。"""
        if not self._running and self._task is None:
            return
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            logger.info("资源监控任务已请求取消")
        self._task = None

    # ------------------------------------------------------------------
    # 告警
    # ------------------------------------------------------------------
    async def _check_thresholds(self, snapshot: Dict[str, Any]) -> None:
        """根据阈值检查最新快照，必要时生成告警。

        本方法同时执行两类检查：
            1. 即时阈值告警（``_thresholds``）— 追加到 ``_alerts`` 列表，
               severity 为 warning / critical，用于历史记录查询。
            2. 持续阈值告警（``_sustained_thresholds`` + ``_sustained_seconds``）
               — 通过状态机追踪持续超过阈值的指标，达到持续秒数后触发
               ``WebhookNotifier`` 发送外部通知。
        """
        try:
            cpu_p = float(snapshot.get("cpu_percent", 0.0))
            mem_p = float(snapshot.get("memory", {}).get("percent", 0.0))
            disk_p = float(snapshot.get("disk", {}).get("percent", 0.0))
        except (TypeError, ValueError):
            return

        ts = float(snapshot.get("timestamp", time.time()))
        checks = (
            ("cpu_percent", cpu_p),
            ("memory_percent", mem_p),
            ("disk_percent", disk_p),
        )

        # 1. 即时阈值告警（保持原有行为）
        for key, value in checks:
            threshold = self._thresholds.get(key)
            if threshold is None or value < threshold:
                continue
            # 超过阈值 +5% 视为 critical，否则 warning
            severity = "critical" if value >= threshold + 5 else "warning"
            self._alerts.append({
                "timestamp": ts,
                "metric": key,
                "value": value,
                "threshold": threshold,
                "severity": severity,
                "message": f"{key} = {value:.1f}% (阈值 {threshold:.1f}%)",
            })
            logger.bind(metric=key, severity=severity).warning(
                f"资源告警: {key}={value:.1f}% 超过阈值 {threshold:.1f}%"
            )
        # 限制告警列表长度，避免无界增长
        if len(self._alerts) > 500:
            del self._alerts[: len(self._alerts) - 500]

        # 2. 持续阈值告警（状态机 + webhook 通知）
        await self._check_sustained_thresholds(checks, ts)

    async def _check_sustained_thresholds(
        self,
        checks: tuple[tuple[str, float], ...],
        ts: float,
    ) -> None:
        """对每个指标运行持续告警状态机。

        状态机：
            normal → warning/critical → sustained_alert → notifying → notified
                                                                    ↓
                                                                recovering → normal

        Args:
            checks: ``(metric, value)`` 元组列表。
            ts: 当前快照时间戳。
        """
        for metric, value in checks:
            threshold = self._sustained_thresholds.get(metric)
            if threshold is None:
                continue
            sustained_secs = self._sustained_seconds.get(metric, 30)
            await self._update_sustained_state(
                metric=metric,
                value=value,
                threshold=threshold,
                sustained_seconds=sustained_secs,
                ts=ts,
            )

    async def _update_sustained_state(
        self,
        metric: str,
        value: float,
        threshold: float,
        sustained_seconds: int,
        ts: float,
    ) -> None:
        """更新单个指标的持续告警状态。

        See class docstring for the state machine diagram.
        """
        alert_type = f"{metric}_sustained_high"
        record = self._sustained_alerts.get(metric)

        # ---------- 超过阈值 ----------
        if value >= threshold:
            if record is None or record.state == "normal":
                # 首次超过阈值 → warning / critical
                record = AlertRecord(
                    alert_type=alert_type,
                    metric=metric,
                    state="critical" if value >= threshold + 5 else "warning",
                    value=value,
                    threshold=threshold,
                    first_breach_at=ts,
                    sustained_seconds=sustained_seconds,
                )
                self._sustained_alerts[metric] = record
                logger.info(
                    f"持续告警状态机: {metric} 进入 {record.state} "
                    f"value={value:.1f}% threshold={threshold:.1f}%"
                )
                return

            # 已在告警状态：更新 value，必要时升级 warning → critical
            record.value = value
            if value >= threshold + 5 and record.state == "warning":
                record.state = "critical"
                logger.info(f"持续告警状态机: {metric} 升级 warning → critical")

            # 检查是否达到持续触发条件
            if (
                record.state in ("warning", "critical")
                and record.first_breach_at is not None
            ):
                elapsed = ts - record.first_breach_at
                if elapsed >= sustained_seconds:
                    record.state = "sustained_alert"
                    record.sustained_seconds = sustained_seconds
                    logger.warning(
                        f"持续告警触发: {metric} 持续 {elapsed:.1f}s 超过阈值 "
                        f"{threshold:.1f}% (current={value:.1f}%)，准备发送 webhook"
                    )
                    await self._trigger_webhook_alert(record)
            return

        # ---------- 资源恢复正常 ----------
        if record is None or record.state == "normal":
            return

        # 已发送过告警通知 → 触发恢复通知
        if record.state == "notified":
            record.state = "recovering"
            record.value = value  # 记录恢复时的值
            logger.info(
                f"资源恢复: {metric}={value:.1f}% 已低于阈值 {threshold:.1f}%，"
                f"准备发送恢复通知"
            )
            await self._trigger_webhook_recovery(record)
            return

        # 正在发送告警通知时恢复 → 等待通知完成后由 _async_send_alert 处理状态
        if record.state == "notifying":
            # 不打断发送流程，但记录恢复事件
            record.value = value
            logger.debug(
                f"资源恢复但 {metric} 仍在 notifying 状态，等待通知完成后处理"
            )
            return

        # 正在发送恢复通知 → 等待完成
        if record.state == "recovering":
            return

        # warning/critical/sustained_alert（未发送通知就恢复）→ 直接重置
        if record.state in ("warning", "critical", "sustained_alert"):
            logger.info(
                f"持续告警未触发通知即恢复: {metric}={value:.1f}% "
                f"(previous_state={record.state})"
            )
            record.state = "normal"
            record.first_breach_at = None
            record.value = value

    async def _trigger_webhook_alert(self, record: AlertRecord) -> None:
        """触发 webhook 告警通知（异步、不阻塞监控主循环）。

        若 ``_notifier`` 为 ``None``，直接将状态标记为 ``notified`` 但不发送
        实际通知，便于在没有 webhook 配置的环境下仍能追踪状态机。
        """
        if self._notifier is None:
            record.state = "notified"
            record.notification_sent = False
            record.last_notified_at = time.time()
            self._record_alert_history(record, event="alert", success=False,
                                        reason="notifier not configured")
            return

        record.state = "notifying"
        # 异步发送，不等待结果，避免阻塞监控循环
        asyncio.create_task(self._async_send_alert(record))

    async def _async_send_alert(self, record: AlertRecord) -> None:
        """异步发送告警 webhook（在后台任务中执行）。"""
        if self._notifier is None:
            return
        try:
            success = await self._notifier.send_alert(
                alert_type=record.alert_type,
                metric=record.metric,
                value=record.value,
                threshold=record.threshold,
                sustained_seconds=record.sustained_seconds,
            )
            record.notification_sent = success
            record.last_notified_at = time.time()
            if success:
                record.state = "notified"
                record.error = ""
            else:
                # 发送失败：回到 sustained_alert 等待下次采样重试
                record.state = "sustained_alert"
                record.error = "webhook send failed"
            self._record_alert_history(record, event="alert", success=success)
        except Exception as e:  # noqa: BLE001
            record.state = "sustained_alert"
            record.error = str(e)
            record.last_notified_at = time.time()
            self._record_alert_history(record, event="alert", success=False,
                                        reason=str(e))
            logger.error(f"webhook 告警发送异常: {e}")

    async def _trigger_webhook_recovery(self, record: AlertRecord) -> None:
        """触发 webhook 恢复通知（异步）。"""
        if self._notifier is None:
            record.state = "normal"
            record.first_breach_at = None
            record.recovery_sent = False
            record.last_recovery_at = time.time()
            self._record_alert_history(record, event="recovery", success=False,
                                        reason="notifier not configured")
            return

        asyncio.create_task(self._async_send_recovery(record))

    async def _async_send_recovery(self, record: AlertRecord) -> None:
        """异步发送恢复 webhook（在后台任务中执行）。"""
        if self._notifier is None:
            return
        try:
            success = await self._notifier.send_recovery(
                alert_type=record.alert_type,
                metric=record.metric,
                previous_value=record.value,
            )
            record.recovery_sent = success
            record.last_recovery_at = time.time()
            if success:
                record.state = "normal"
                record.first_breach_at = None
                record.error = ""
            else:
                # 恢复通知失败：回到 notified 等待下次采样重试
                record.state = "notified"
                record.error = "webhook recovery send failed"
            self._record_alert_history(record, event="recovery", success=success)
        except Exception as e:  # noqa: BLE001
            record.state = "notified"
            record.error = str(e)
            record.last_recovery_at = time.time()
            self._record_alert_history(record, event="recovery", success=False,
                                        reason=str(e))
            logger.error(f"webhook 恢复通知发送异常: {e}")

    def _record_alert_history(
        self,
        record: AlertRecord,
        event: str,
        success: bool,
        reason: str = "",
    ) -> None:
        """记录告警/恢复事件到历史列表。"""
        self._alert_history.append({
            "timestamp": time.time(),
            "event": event,  # "alert" or "recovery"
            "alert_type": record.alert_type,
            "metric": record.metric,
            "state": record.state,
            "value": round(record.value, 2),
            "threshold": round(record.threshold, 2),
            "sustained_seconds": record.sustained_seconds,
            "success": success,
            "error": reason or record.error,
        })
        if len(self._alert_history) > self._max_alert_history:
            del self._alert_history[: len(self._alert_history) - self._max_alert_history]

    def get_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的告警列表。

        Args:
            limit: 返回的最大告警数量，按时间倒序。

        Returns:
            告警字典列表，最近的告警排在最前。
        """
        if limit <= 0:
            return []
        return list(reversed(self._alerts[-limit:]))

    def get_sustained_alerts(self) -> List[Dict[str, Any]]:
        """获取当前所有指标的持续告警状态。

        Returns:
            ``AlertRecord.to_dict()`` 列表，包含 state / value /
            first_breach_at / last_notified_at 等字段。
        """
        return [r.to_dict() for r in self._sustained_alerts.values()]

    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取告警事件历史记录（含 webhook 发送结果）。

        Args:
            limit: 返回的最大记录数，按时间倒序。

        Returns:
            告警事件字典列表。
        """
        if limit <= 0:
            return []
        limit = min(limit, self._max_alert_history)
        return list(reversed(self._alert_history[-limit:]))

    async def send_test_alert(self) -> bool:
        """发送一条测试告警，用于验证 webhook 配置是否正确。

        Returns:
            是否成功发送。若 ``_notifier`` 为 ``None`` 返回 ``False``。
        """
        if self._notifier is None:
            logger.warning("Webhook 通知器未配置，无法发送测试告警")
            return False
        return await self._notifier.test()

    def get_notifier_stats(self) -> Optional[Dict[str, Any]]:
        """获取 webhook 通知器统计信息。"""
        if self._notifier is None:
            return None
        return self._notifier.get_stats()

    def clear_alerts(self) -> None:
        """清除所有告警。"""
        self._alerts.clear()
        logger.info("已清除所有资源告警记录")

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（平均值/最大值/当前值）。

        Returns:
            包含 sample_count / monitoring_seconds / cpu / memory / disk /
            gpu 各指标 avg / max / current 的字典。
        """
        if not self._samples:
            return {
                "available": False,
                "sample_count": 0,
                "reason": "no samples collected yet",
            }

        cpu_values = [float(s.get("cpu_percent", 0.0)) for s in self._samples]
        mem_values = [
            float(s.get("memory", {}).get("percent", 0.0)) for s in self._samples
        ]
        disk_values = [
            float(s.get("disk", {}).get("percent", 0.0)) for s in self._samples
        ]

        latest = self._samples[-1]
        monitoring_seconds = 0.0
        if self._started_at is not None:
            monitoring_seconds = time.time() - self._started_at

        # GPU 统计：取所有样本中最后一个 GPU 的均值/峰值
        gpu_percents: List[float] = []
        gpu_mem_percents: List[float] = []
        for s in self._samples:
            for g in s.get("gpu", []) or []:
                gpu_percents.append(float(g.get("gpu_percent", 0.0)))
                gpu_mem_percents.append(float(g.get("memory_percent", 0.0)))

        def _stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"avg": 0.0, "max": 0.0, "current": 0.0}
            return {
                "avg": sum(values) / len(values),
                "max": max(values),
                "current": values[-1],
            }

        return {
            "available": True,
            "sample_count": len(self._samples),
            "monitoring_seconds": round(monitoring_seconds, 1),
            "interval": self.interval,
            "started_at": self._started_at,
            "cpu": _stats(cpu_values),
            "memory": _stats(mem_values),
            "disk": _stats(disk_values),
            "gpu": (
                {
                    "gpu_percent": _stats(gpu_percents),
                    "memory_percent": _stats(gpu_mem_percents),
                }
                if gpu_percents else None
            ),
            "latest": latest,
        }

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取历史采样数据。

        Args:
            limit: 返回的最大样本数量，按时间正序（旧→新）。

        Returns:
            采样快照列表。
        """
        if limit <= 0:
            return []
        # 取最后 limit 条，但保持时间正序
        return list(self._samples[-limit:])

    # ------------------------------------------------------------------
    # 阈值管理
    # ------------------------------------------------------------------
    def set_threshold(self, metric: str, value: float) -> None:
        """更新某项指标的告警阈值。

        Args:
            metric: 指标名，如 ``cpu_percent`` / ``memory_percent`` / ``disk_percent``。
            value: 阈值百分比（0-100）。
        """
        self._thresholds[metric] = float(value)
        logger.info(f"资源告警阈值更新: {metric}={value}")

    def get_thresholds(self) -> Dict[str, float]:
        """获取当前阈值配置副本。"""
        return dict(self._thresholds)

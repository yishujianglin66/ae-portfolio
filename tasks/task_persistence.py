#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务持久化模块
=============

提供任务状态的持久化存储与恢复能力，支持服务重启后任务恢复。

功能:
- JSON 文件持久化
- 服务重启后任务恢复
- 任务历史记录
- 持久化配置
- 周期性自动保存
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from logger import get_logger
    _logger = get_logger("task-persistence")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("task-persistence")


# ============================================================================
# 持久化配置
# ============================================================================

@dataclass
class PersistenceConfig:
    """持久化配置"""
    enabled: bool = True
    storage_path: str = "./data/tasks"
    auto_save_interval: float = 10.0
    max_history: int = 1000
    save_on_change: bool = True
    compress_history: bool = False


# ============================================================================
# 任务持久化管理器
# ============================================================================

class TaskPersistence:
    """任务持久化管理器

    负责任务状态的持久化存储与恢复。
    """

    def __init__(self, config: Optional[PersistenceConfig] = None):
        self._config = config or PersistenceConfig()
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []
        self._auto_save_timer: Optional[threading.Timer] = None
        self._running = False
        self._closed = False

        if self._config.enabled:
            self._ensure_storage_dir()
            self._load_tasks()
            self._load_history()
            self._start_auto_save()

    def _ensure_storage_dir(self):
        """确保存储目录存在"""
        Path(self._config.storage_path).mkdir(parents=True, exist_ok=True)

    @property
    def _tasks_file(self) -> str:
        return os.path.join(self._config.storage_path, "tasks.json")

    @property
    def _history_file(self) -> str:
        return os.path.join(self._config.storage_path, "history.json")

    # --------------------------------------------------------------------
    # 加载与保存
    # --------------------------------------------------------------------

    def _load_tasks(self):
        """从磁盘加载任务"""
        if not os.path.exists(self._tasks_file):
            return

        try:
            # 检查文件是否为空
            if os.path.getsize(self._tasks_file) == 0:
                _logger.warning(f"任务文件为空，跳过加载: {self._tasks_file}")
                return

            with open(self._tasks_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    _logger.warning(f"任务文件内容为空字符串，跳过加载: {self._tasks_file}")
                    return
                data = json.loads(content)
                if isinstance(data, dict):
                    self._tasks = data
                    _logger.info(f"已加载 {len(self._tasks)} 个任务")
        except json.JSONDecodeError as e:
            _logger.error(f"任务文件格式错误 (JSON解析失败): {e}, 文件: {self._tasks_file}")
        except Exception as e:
            _logger.error(f"加载任务失败: {e}")

    def _save_tasks(self):
        """保存任务到磁盘"""
        if not self._config.enabled:
            return

        try:
            with self._lock:
                tasks_copy = dict(self._tasks)

                tmp_file = self._tasks_file + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(tasks_copy, f, ensure_ascii=False, indent=2, default=str)

                os.replace(tmp_file, self._tasks_file)
        except Exception as e:
            _logger.error(f"保存任务失败: {e}")

    def _load_history(self):
        """加载历史记录"""
        if not os.path.exists(self._history_file):
            return

        try:
            # 检查文件是否为空
            if os.path.getsize(self._history_file) == 0:
                _logger.warning(f"历史文件为空，跳过加载: {self._history_file}")
                return

            with open(self._history_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    _logger.warning(f"历史文件内容为空字符串，跳过加载: {self._history_file}")
                    return
                data = json.loads(content)
                if isinstance(data, list):
                    self._history = data[-self._config.max_history:]
                    _logger.info(f"已加载 {len(self._history)} 条历史记录")
        except json.JSONDecodeError as e:
            _logger.error(f"历史文件格式错误 (JSON解析失败): {e}, 文件: {self._history_file}")
        except Exception as e:
            _logger.error(f"加载历史记录失败: {e}")

    def _save_history(self):
        """保存历史记录"""
        if not self._config.enabled:
            return

        try:
            with self._lock:
                history_copy = list(self._history[-self._config.max_history:])

                tmp_file = self._history_file + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(history_copy, f, ensure_ascii=False, indent=2, default=str)

                os.replace(tmp_file, self._history_file)
        except Exception as e:
            _logger.error(f"保存历史记录失败: {e}")

    def _start_auto_save(self):
        """启动自动保存定时器"""
        if not self._config.enabled or self._config.auto_save_interval <= 0:
            return

        self._running = True
        self._schedule_auto_save()

    def _schedule_auto_save(self):
        """调度下一次自动保存"""
        if not self._running:
            return

        self._auto_save_timer = threading.Timer(
            self._config.auto_save_interval,
            self._auto_save_tick,
        )
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()

    def _auto_save_tick(self):
        """自动保存触发"""
        try:
            self._save_tasks()
            self._save_history()
        except Exception as e:
            _logger.error(f"自动保存失败: {e}")
        finally:
            self._schedule_auto_save()

    # --------------------------------------------------------------------
    # 任务管理
    # --------------------------------------------------------------------

    def save_task(self, task_id: str, task_data: Dict[str, Any]):
        """保存任务状态

        Args:
            task_id: 任务 ID
            task_data: 任务数据
        """
        if not self._config.enabled:
            return

        with self._lock:
            self._tasks[task_id] = {
                **task_data,
                "last_updated": time.time(),
            }

        if self._config.save_on_change:
            self._save_tasks()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务数据

        Args:
            task_id: 任务 ID

        Returns:
            任务数据或 None
        """
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务"""
        with self._lock:
            return dict(self._tasks)

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取待执行任务（用于重启恢复）"""
        pending = []
        with self._lock:
            for task_data in self._tasks.values():
                status = task_data.get("status", "")
                if status in ("pending", "running"):
                    pending.append(task_data)
        return pending

    def remove_task(self, task_id: str, add_to_history: bool = True):
        """移除任务

        Args:
            task_id: 任务 ID
            add_to_history: 是否添加到历史记录
        """
        with self._lock:
            task_data = self._tasks.pop(task_id, None)
            if task_data and add_to_history:
                self._history.append({
                    **task_data,
                    "removed_at": time.time(),
                })
                if len(self._history) > self._config.max_history:
                    self._history = self._history[-self._config.max_history:]

        if self._config.save_on_change:
            self._save_tasks()
            self._save_history()

    def clear_completed(self, older_than_hours: float = 24) -> int:
        """清理已完成的任务

        Args:
            older_than_hours: 清理多少小时前的已完成任务

        Returns:
            清理的任务数量
        """
        cutoff = time.time() - older_than_hours * 3600
        count = 0

        with self._lock:
            to_remove = []
            for task_id, task_data in self._tasks.items():
                status = task_data.get("status", "")
                completed_at = task_data.get("completed_at", 0)
                if status == "completed" and completed_at and completed_at < cutoff:
                    to_remove.append(task_id)

            for task_id in to_remove:
                task_data = self._tasks.pop(task_id)
                self._history.append({
                    **task_data,
                    "removed_at": time.time(),
                })
                count += 1

            if len(self._history) > self._config.max_history:
                self._history = self._history[-self._config.max_history:]

        if count > 0 and self._config.save_on_change:
            self._save_tasks()
            self._save_history()

        return count

    # --------------------------------------------------------------------
    # 历史记录
    # --------------------------------------------------------------------

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取历史记录

        Args:
            limit: 限制数量
            offset: 偏移量
            status: 按状态过滤

        Returns:
            历史记录列表
        """
        with self._lock:
            history = list(reversed(self._history))

        if status:
            history = [h for h in history if h.get("status") == status]

        return history[offset:offset + limit]

    def get_history_count(self, status: Optional[str] = None) -> int:
        """获取历史记录数量"""
        with self._lock:
            if status:
                return sum(1 for h in self._history if h.get("status") == status)
            return len(self._history)

    def clear_history(self) -> int:
        """清空历史记录

        Returns:
            清空的记录数
        """
        with self._lock:
            count = len(self._history)
            self._history = []

        if self._config.save_on_change:
            self._save_history()

        return count

    # --------------------------------------------------------------------
    # 重启恢复
    # --------------------------------------------------------------------

    def recover_tasks(self, queue) -> int:
        """恢复任务到队列

        将 pending/running 状态的任务重新加入队列。

        Args:
            queue: BatchQueue 实例

        Returns:
            恢复的任务数量
        """
        if not self._config.enabled:
            return 0

        pending_tasks = self.get_pending_tasks()
        recovered = 0

        for task_data in pending_tasks:
            task_id = task_data.get("task_id")
            if not task_id:
                continue

            status = task_data.get("status", "pending")
            _logger.info(f"恢复任务: {task_id} (状态: {status})")

            task_data["status"] = "pending"
            task_data["recovered"] = True
            task_data["recovered_at"] = time.time()
            self.save_task(task_id, task_data)
            recovered += 1

        _logger.info(f"共恢复 {recovered} 个任务")
        return recovered

    # --------------------------------------------------------------------
    # 统计信息
    # --------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取持久化统计信息"""
        with self._lock:
            task_count = len(self._tasks)
            history_count = len(self._history)

            status_counts: Dict[str, int] = {}
            for task_data in self._tasks.values():
                status = task_data.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "enabled": self._config.enabled,
            "storage_path": self._config.storage_path,
            "active_tasks": task_count,
            "history_count": history_count,
            "status_counts": status_counts,
            "auto_save_interval": self._config.auto_save_interval,
            "max_history": self._config.max_history,
        }

    # --------------------------------------------------------------------
    # 生命周期
    # --------------------------------------------------------------------

    def shutdown(self):
        """关闭持久化管理器（幂等，多次调用安全）"""
        if self._closed:
            return
        self._closed = True
        self._running = False

        if self._auto_save_timer:
            self._auto_save_timer.cancel()
            self._auto_save_timer = None

        self._save_tasks()
        self._save_history()
        _logger.info("任务持久化管理器已关闭")


# ============================================================================
# 模块单例
# ============================================================================

_default_persistence: Optional[TaskPersistence] = None


def get_task_persistence(config: Optional[PersistenceConfig] = None) -> TaskPersistence:
    """获取默认持久化管理器实例"""
    global _default_persistence
    if _default_persistence is None:
        _default_persistence = TaskPersistence(config)
    return _default_persistence


# ============================================================================
# 命令行测试入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("任务持久化模块测试")
    print("=" * 60)

    import tempfile
    import shutil

    tmp_dir = tempfile.mkdtemp(prefix="task_persist_test_")
    print(f"\n测试目录: {tmp_dir}")

    try:
        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_dir,
            auto_save_interval=0,
            max_history=100,
        )

        persist = TaskPersistence(config)

        print("\n1. 保存任务...")
        for i in range(5):
            task_data = {
                "task_id": f"task_{i:03d}",
                "name": f"测试任务-{i}",
                "status": "pending" if i < 3 else "completed",
                "priority": 5,
                "progress": 0.0 if i < 3 else 1.0,
                "created_at": time.time() - i * 3600,
                "completed_at": time.time() - i * 3600 + 1800 if i >= 3 else None,
                "result": {"output": f"result_{i}"} if i >= 3 else None,
            }
            persist.save_task(f"task_{i:03d}", task_data)
            print(f"  保存任务 task_{i:03d}")

        print("\n2. 获取任务统计...")
        stats = persist.get_stats()
        print(f"  活跃任务: {stats['active_tasks']}")
        print(f"  历史记录: {stats['history_count']}")
        print(f"  状态分布: {stats['status_counts']}")

        print("\n3. 获取待执行任务...")
        pending = persist.get_pending_tasks()
        print(f"  待执行任务数: {len(pending)}")
        for t in pending:
            print(f"    - {t['task_id']}: {t['name']}")

        print("\n4. 清理已完成任务...")
        cleared = persist.clear_completed(older_than_hours=0.1)
        print(f"  清理了 {cleared} 个任务")

        print("\n5. 验证历史记录...")
        history = persist.get_history(limit=10)
        print(f"  历史记录数: {len(history)}")
        for h in history[:3]:
            print(f"    - {h['task_id']}: {h['status']}")

        print("\n" + "=" * 60)
        print("测试完成！")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"\n测试目录已清理")

"""task_persistence 模块单元测试

覆盖范围:
- 任务 CRUD 操作
- 持久化与恢复（重启场景）
- 并发写入安全性
- 历史记录管理
- 边界条件与异常容错
- 配置禁用场景
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from task_persistence import PersistenceConfig, TaskPersistence


@pytest.fixture
def tmp_storage():
    """创建临时存储目录，测试后自动清理"""
    tmp_dir = tempfile.mkdtemp(prefix="task_persist_test_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def persistence(tmp_storage):
    """创建一个启用的持久化实例"""
    config = PersistenceConfig(
        enabled=True,
        storage_path=tmp_storage,
        auto_save_interval=0,
        max_history=100,
        save_on_change=True,
    )
    p = TaskPersistence(config)
    yield p
    p.shutdown()


@pytest.fixture
def disabled_persistence(tmp_storage):
    """创建一个禁用的持久化实例"""
    config = PersistenceConfig(
        enabled=False,
        storage_path=tmp_storage,
        auto_save_interval=0,
        max_history=100,
    )
    return TaskPersistence(config)


class TestPersistenceConfig:
    """PersistenceConfig 数据类测试"""

    def test_default_values(self):
        config = PersistenceConfig()
        assert config.enabled is True
        assert config.storage_path == "./data/tasks"
        assert config.auto_save_interval == 10.0
        assert config.max_history == 1000
        assert config.save_on_change is True
        assert config.compress_history is False

    def test_custom_values(self):
        config = PersistenceConfig(
            enabled=False,
            storage_path="/custom/path",
            auto_save_interval=5.0,
            max_history=500,
            save_on_change=False,
            compress_history=True,
        )
        assert config.enabled is False
        assert config.storage_path == "/custom/path"
        assert config.auto_save_interval == 5.0
        assert config.max_history == 500
        assert config.save_on_change is False
        assert config.compress_history is True


class TestTaskCRUD:
    """任务基本 CRUD 操作测试"""

    def test_save_and_get_task(self, persistence):
        task_data = {
            "task_id": "task_001",
            "name": "测试任务",
            "status": "pending",
            "priority": 5,
        }
        persistence.save_task("task_001", task_data)

        result = persistence.get_task("task_001")
        assert result is not None
        assert result["task_id"] == "task_001"
        assert result["name"] == "测试任务"
        assert result["status"] == "pending"
        assert result["priority"] == 5
        assert "last_updated" in result

    def test_get_nonexistent_task_returns_none(self, persistence):
        assert persistence.get_task("nonexistent") is None

    def test_get_all_tasks(self, persistence):
        for i in range(5):
            persistence.save_task(
                f"task_{i:03d}",
                {"task_id": f"task_{i:03d}", "status": "pending"},
            )

        all_tasks = persistence.get_all_tasks()
        assert len(all_tasks) == 5
        assert "task_000" in all_tasks
        assert "task_004" in all_tasks

    def test_get_all_tasks_returns_shallow_copy(self, persistence):
        persistence.save_task("t1", {"status": "pending"})
        tasks = persistence.get_all_tasks()
        tasks["new_key"] = "should_not_affect_original"

        original = persistence.get_all_tasks()
        assert "new_key" not in original

    def test_update_existing_task(self, persistence):
        persistence.save_task("t1", {"status": "pending", "progress": 0.0})

        persistence.save_task("t1", {"status": "running", "progress": 0.5})

        task = persistence.get_task("t1")
        assert task["status"] == "running"
        assert task["progress"] == 0.5

    def test_remove_task_with_history(self, persistence):
        persistence.save_task("t1", {"task_id": "t1", "status": "completed"})
        persistence.remove_task("t1", add_to_history=True)

        assert persistence.get_task("t1") is None
        history = persistence.get_history(limit=10)
        assert len(history) >= 1
        assert history[0]["task_id"] == "t1"
        assert "removed_at" in history[0]

    def test_remove_task_without_history(self, persistence):
        persistence.save_task("t1", {"task_id": "t1", "status": "completed"})
        history_before = persistence.get_history_count()

        persistence.remove_task("t1", add_to_history=False)

        assert persistence.get_task("t1") is None
        assert persistence.get_history_count() == history_before

    def test_remove_nonexistent_task_no_error(self, persistence):
        persistence.remove_task("nonexistent")


class TestPendingTasks:
    """待执行任务相关测试"""

    def test_get_pending_tasks(self, persistence):
        statuses = ["pending", "running", "completed", "failed", "pending"]
        for i, status in enumerate(statuses):
            persistence.save_task(
                f"task_{i}",
                {"task_id": f"task_{i}", "status": status},
            )

        pending = persistence.get_pending_tasks()
        assert len(pending) == 3
        pending_statuses = [t["status"] for t in pending]
        assert "pending" in pending_statuses
        assert "running" in pending_statuses
        assert "completed" not in pending_statuses

    def test_empty_pending_tasks(self, persistence):
        assert persistence.get_pending_tasks() == []


class TestClearCompleted:
    """清理已完成任务测试"""

    def test_clear_old_completed(self, persistence):
        now = time.time()
        persistence.save_task(
            "old_completed",
            {
                "task_id": "old_completed",
                "status": "completed",
                "completed_at": now - 3600 * 2,
            },
        )
        persistence.save_task(
            "recent_completed",
            {
                "task_id": "recent_completed",
                "status": "completed",
                "completed_at": now - 60,
            },
        )
        persistence.save_task(
            "still_running",
            {"task_id": "still_running", "status": "running"},
        )

        cleared = persistence.clear_completed(older_than_hours=1)
        assert cleared == 1

        assert persistence.get_task("old_completed") is None
        assert persistence.get_task("recent_completed") is not None
        assert persistence.get_task("still_running") is not None

        history = persistence.get_history(limit=10)
        assert any(h["task_id"] == "old_completed" for h in history)

    def test_clear_zero_hours(self, persistence):
        now = time.time()
        persistence.save_task(
            "just_completed",
            {
                "task_id": "just_completed",
                "status": "completed",
                "completed_at": now - 1,
            },
        )

        cleared = persistence.clear_completed(older_than_hours=0)
        assert cleared == 1
        assert persistence.get_task("just_completed") is None

    def test_clear_nothing_to_clear(self, persistence):
        persistence.save_task(
            "running",
            {"task_id": "running", "status": "running"},
        )
        cleared = persistence.clear_completed(older_than_hours=0)
        assert cleared == 0


class TestHistory:
    """历史记录管理测试"""

    def test_get_history_pagination(self, persistence):
        for i in range(20):
            persistence.save_task(
                f"t_{i}",
                {"task_id": f"t_{i}", "status": "completed"},
            )
            persistence.remove_task(f"t_{i}", add_to_history=True)

        first_page = persistence.get_history(limit=10, offset=0)
        assert len(first_page) == 10

        second_page = persistence.get_history(limit=10, offset=10)
        assert len(second_page) == 10

        first_ids = [t["task_id"] for t in first_page]
        second_ids = [t["task_id"] for t in second_page]
        assert set(first_ids).isdisjoint(set(second_ids))

    def test_get_history_filter_by_status(self, persistence):
        statuses = ["completed", "failed", "completed", "cancelled"]
        for i, status in enumerate(statuses):
            persistence.save_task(
                f"t_{i}",
                {"task_id": f"t_{i}", "status": status},
            )
            persistence.remove_task(f"t_{i}", add_to_history=True)

        completed = persistence.get_history(limit=100, status="completed")
        assert len(completed) == 2
        assert all(h["status"] == "completed" for h in completed)

    def test_get_history_count(self, persistence):
        for i in range(5):
            persistence.save_task(f"t_{i}", {"task_id": f"t_{i}", "status": "done"})
            persistence.remove_task(f"t_{i}", add_to_history=True)

        assert persistence.get_history_count() == 5

    def test_get_history_count_with_status(self, persistence):
        for i in range(3):
            persistence.save_task(f"t_{i}", {"task_id": f"t_{i}", "status": "success"})
            persistence.remove_task(f"t_{i}", add_to_history=True)
        for i in range(2):
            persistence.save_task(f"f_{i}", {"task_id": f"f_{i}", "status": "failed"})
            persistence.remove_task(f"f_{i}", add_to_history=True)

        assert persistence.get_history_count(status="success") == 3
        assert persistence.get_history_count(status="failed") == 2
        assert persistence.get_history_count(status="nonexistent") == 0

    def test_clear_history(self, persistence):
        for i in range(5):
            persistence.save_task(f"t_{i}", {"task_id": f"t_{i}", "status": "done"})
            persistence.remove_task(f"t_{i}", add_to_history=True)

        count = persistence.clear_history()
        assert count == 5
        assert persistence.get_history_count() == 0

    def test_history_max_limit(self, tmp_storage):
        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_storage,
            auto_save_interval=0,
            max_history=5,
            save_on_change=True,
        )
        p = TaskPersistence(config)

        for i in range(10):
            p.save_task(f"t_{i}", {"task_id": f"t_{i}", "status": "done"})
            p.remove_task(f"t_{i}", add_to_history=True)

        assert p.get_history_count() == 5

        history = p.get_history(limit=10)
        assert len(history) == 5
        assert history[0]["task_id"] == "t_9"
        assert history[-1]["task_id"] == "t_5"

        p.shutdown()

    def test_history_order_is_reverse_chronological(self, persistence):
        for i in range(5):
            persistence.save_task(f"t_{i}", {"task_id": f"t_{i}", "status": "done"})
            persistence.remove_task(f"t_{i}", add_to_history=True)
            time.sleep(0.01)

        history = persistence.get_history(limit=10)
        assert history[0]["task_id"] == "t_4"
        assert history[-1]["task_id"] == "t_0"


class TestPersistenceAndRecovery:
    """持久化与恢复测试（模拟重启场景）"""

    def test_tasks_persist_to_disk(self, persistence, tmp_storage):
        persistence.save_task("t1", {"task_id": "t1", "status": "pending"})
        persistence.save_task("t2", {"task_id": "t2", "status": "running"})

        tasks_file = os.path.join(tmp_storage, "tasks.json")
        assert os.path.exists(tasks_file)

        with open(tasks_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "t1" in data
        assert "t2" in data
        assert data["t1"]["status"] == "pending"

    def test_reload_tasks_after_restart(self, tmp_storage):
        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_storage,
            auto_save_interval=0,
            max_history=100,
        )

        p1 = TaskPersistence(config)
        p1.save_task("task_a", {"task_id": "task_a", "status": "pending", "progress": 0.3})
        p1.save_task("task_b", {"task_id": "task_b", "status": "completed"})
        p1.shutdown()

        p2 = TaskPersistence(config)
        assert p2.get_task("task_a") is not None
        assert p2.get_task("task_a")["status"] == "pending"
        assert p2.get_task("task_a")["progress"] == 0.3
        assert p2.get_task("task_b") is not None
        p2.shutdown()

    def test_reload_history_after_restart(self, tmp_storage):
        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_storage,
            auto_save_interval=0,
            max_history=100,
        )

        p1 = TaskPersistence(config)
        for i in range(3):
            p1.save_task(f"t_{i}", {"task_id": f"t_{i}", "status": "done"})
            p1.remove_task(f"t_{i}", add_to_history=True)
        p1.shutdown()

        p2 = TaskPersistence(config)
        assert p2.get_history_count() == 3
        p2.shutdown()

    def test_corrupted_tasks_file_graceful_degradation(self, tmp_storage):
        os.makedirs(tmp_storage, exist_ok=True)
        tasks_file = os.path.join(tmp_storage, "tasks.json")
        with open(tasks_file, "w", encoding="utf-8") as f:
            f.write("this is not valid json {{{")

        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_storage,
            auto_save_interval=0,
            max_history=100,
        )
        p = TaskPersistence(config)

        assert p.get_all_tasks() == {}

        p.save_task("t1", {"task_id": "t1", "status": "pending"})
        assert p.get_task("t1") is not None
        p.shutdown()

    def test_empty_tasks_file(self, tmp_storage):
        os.makedirs(tmp_storage, exist_ok=True)
        tasks_file = os.path.join(tmp_storage, "tasks.json")
        with open(tasks_file, "w", encoding="utf-8") as f:
            json.dump([], f)

        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_storage,
            auto_save_interval=0,
            max_history=100,
        )
        p = TaskPersistence(config)
        assert p.get_all_tasks() == {}
        p.shutdown()

    def test_atomic_write_does_not_corrupt_on_crash(self, tmp_storage):
        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_storage,
            auto_save_interval=0,
            max_history=100,
        )
        p = TaskPersistence(config)
        p.save_task("t1", {"task_id": "t1", "status": "pending"})

        tasks_file = os.path.join(tmp_storage, "tasks.json")
        tmp_file = tasks_file + ".tmp"

        assert not os.path.exists(tmp_file)

        with open(tasks_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "t1" in data

        p.shutdown()

    def test_recover_tasks(self, persistence):
        persistence.save_task("pending_1", {"task_id": "pending_1", "status": "pending"})
        persistence.save_task("running_1", {"task_id": "running_1", "status": "running"})
        persistence.save_task("completed_1", {"task_id": "completed_1", "status": "completed"})

        mock_queue = []
        recovered = persistence.recover_tasks(mock_queue)

        assert recovered == 2

        pending_1 = persistence.get_task("pending_1")
        assert pending_1["status"] == "pending"
        assert pending_1.get("recovered") is True
        assert "recovered_at" in pending_1

        running_1 = persistence.get_task("running_1")
        assert running_1["status"] == "pending"
        assert running_1.get("recovered") is True


class TestConcurrency:
    """并发写入安全性测试"""

    def test_concurrent_save_tasks(self, persistence):
        num_threads = 10
        tasks_per_thread = 50

        def worker(thread_id):
            for i in range(tasks_per_thread):
                task_id = f"thread_{thread_id}_task_{i}"
                persistence.save_task(
                    task_id,
                    {"task_id": task_id, "thread": thread_id, "index": i},
                )

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        all_tasks = persistence.get_all_tasks()
        assert len(all_tasks) == num_threads * tasks_per_thread

    def test_concurrent_remove_tasks(self, persistence):
        num_tasks = 100
        for i in range(num_tasks):
            persistence.save_task(f"t_{i}", {"task_id": f"t_{i}", "status": "pending"})

        def worker(start, end):
            for i in range(start, end):
                persistence.remove_task(f"t_{i}", add_to_history=True)

        half = num_tasks // 2
        t1 = threading.Thread(target=worker, args=(0, half))
        t2 = threading.Thread(target=worker, args=(half, num_tasks))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(persistence.get_all_tasks()) == 0
        assert persistence.get_history_count() == num_tasks

    def test_concurrent_read_write(self, persistence):
        for i in range(20):
            persistence.save_task(f"t_{i}", {"task_id": f"t_{i}", "status": "pending"})

        errors = []

        def reader():
            try:
                for _ in range(100):
                    tasks = persistence.get_all_tasks()
                    _ = len(tasks)
                    history = persistence.get_history(limit=10)
                    _ = len(history)
            except Exception as e:
                errors.append(e)

        def writer():
            for i in range(50):
                persistence.save_task(f"w_{i}", {"task_id": f"w_{i}", "status": "running"})

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=reader))
        threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发读取时发生错误: {errors}"


class TestDisabledPersistence:
    """禁用持久化时的行为测试"""

    def test_save_task_does_nothing(self, disabled_persistence):
        disabled_persistence.save_task("t1", {"task_id": "t1", "status": "pending"})
        assert disabled_persistence.get_task("t1") is None

    def test_get_all_tasks_empty(self, disabled_persistence):
        assert disabled_persistence.get_all_tasks() == {}

    def test_recover_tasks_returns_zero(self, disabled_persistence):
        assert disabled_persistence.recover_tasks(None) == 0

    def test_stats_show_disabled(self, disabled_persistence):
        stats = disabled_persistence.get_stats()
        assert stats["enabled"] is False
        assert stats["active_tasks"] == 0


class TestStats:
    """统计信息测试"""

    def test_stats_basic(self, persistence):
        persistence.save_task("t1", {"task_id": "t1", "status": "pending"})
        persistence.save_task("t2", {"task_id": "t2", "status": "running"})
        persistence.save_task("t3", {"task_id": "t3", "status": "completed"})

        stats = persistence.get_stats()
        assert stats["enabled"] is True
        assert stats["active_tasks"] == 3
        assert stats["history_count"] == 0
        assert stats["status_counts"]["pending"] == 1
        assert stats["status_counts"]["running"] == 1
        assert stats["status_counts"]["completed"] == 1

    def test_stats_empty(self, persistence):
        stats = persistence.get_stats()
        assert stats["active_tasks"] == 0
        assert stats["history_count"] == 0
        assert stats["status_counts"] == {}


class TestAutoSave:
    """自动保存功能测试"""

    def test_auto_save_disabled_when_interval_zero(self, tmp_storage):
        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_storage,
            auto_save_interval=0,
            max_history=100,
            save_on_change=False,
        )
        p = TaskPersistence(config)
        p.save_task("t1", {"task_id": "t1", "status": "pending"})

        tasks_file = os.path.join(tmp_storage, "tasks.json")
        assert not os.path.exists(tasks_file)

        p.shutdown()

    def test_shutdown_saves_even_without_auto_save(self, tmp_storage):
        config = PersistenceConfig(
            enabled=True,
            storage_path=tmp_storage,
            auto_save_interval=0,
            max_history=100,
            save_on_change=False,
        )
        p = TaskPersistence(config)
        p.save_task("t1", {"task_id": "t1", "status": "pending"})
        p.shutdown()

        tasks_file = os.path.join(tmp_storage, "tasks.json")
        assert os.path.exists(tasks_file)

        with open(tasks_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "t1" in data


class TestSingleton:
    """单例模式测试"""

    def test_get_task_persistence_returns_same_instance(self, tmp_storage):
        import task_persistence as tp
        from task_persistence import _default_persistence, get_task_persistence

        original = tp._default_persistence
        tp._default_persistence = None

        try:
            config = PersistenceConfig(
                enabled=True,
                storage_path=tmp_storage,
                auto_save_interval=0,
                max_history=100,
            )
            p1 = get_task_persistence(config)
            p2 = get_task_persistence()
            assert p1 is p2
        finally:
            if tp._default_persistence:
                tp._default_persistence.shutdown()
            tp._default_persistence = original

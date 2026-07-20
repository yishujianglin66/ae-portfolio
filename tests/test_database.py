"""database 模块单元测试 - SQLite 持久化层

覆盖范围:
- DatabaseConfig 配置
- 数据库初始化与 Schema
- 任务 CRUD 操作
- 项目 CRUD 操作
- 历史记录操作
- 插件配置操作
- 工作流运行记录
- 事务与并发安全
- 边界条件与异常容错
"""
import os
import sys
import json
import time
import tempfile
import threading
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database, DatabaseConfig


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_db_path():
    """创建临时数据库文件，测试后自动清理"""
    tmp_dir = tempfile.mkdtemp(prefix="db_test_")
    db_path = os.path.join(tmp_dir, "test.db")
    yield db_path
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def db(tmp_db_path):
    """创建一个测试用数据库实例"""
    config = DatabaseConfig(
        db_path=tmp_db_path,
        enable_wal=False,
        busy_timeout=5000,
        journal_mode="MEMORY",
        foreign_keys=True,
    )
    d = Database(config)
    yield d


# ============================================================================
# DatabaseConfig 测试
# ============================================================================

class TestDatabaseConfig:
    """数据库配置测试"""

    def test_default_values(self):
        config = DatabaseConfig()
        assert config.db_path == "./data/ae_knowledge_vault.db"
        assert config.enable_wal is True
        assert config.busy_timeout == 5000
        assert config.journal_mode == "WAL"
        assert config.foreign_keys is True

    def test_custom_values(self):
        config = DatabaseConfig(
            db_path="/custom/path.db",
            enable_wal=False,
            busy_timeout=10000,
            journal_mode="DELETE",
            foreign_keys=False,
        )
        assert config.db_path == "/custom/path.db"
        assert config.enable_wal is False
        assert config.busy_timeout == 10000
        assert config.journal_mode == "DELETE"
        assert config.foreign_keys is False


# ============================================================================
# 数据库初始化测试
# ============================================================================

class TestDatabaseInit:
    """数据库初始化测试"""

    def test_creates_db_file(self, tmp_db_path):
        Database(DatabaseConfig(db_path=tmp_db_path))
        assert os.path.exists(tmp_db_path)

    def test_creates_tables(self, db):
        conn = db._get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [row["name"] for row in tables]

        assert "tasks" in table_names
        assert "projects" in table_names
        assert "history" in table_names
        assert "plugin_configs" in table_names
        assert "workflow_runs" in table_names
        assert "schema_meta" in table_names

    def test_schema_version_set(self, db):
        conn = db._get_connection()
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()
        assert row is not None
        assert row["value"] == str(db._SCHEMA_VERSION)

    def test_creates_indexes(self, db):
        conn = db._get_connection()
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = [row["name"] for row in indexes]

        assert "idx_tasks_status" in index_names
        assert "idx_tasks_type" in index_names
        assert "idx_tasks_created" in index_names
        assert "idx_projects_status" in index_names
        assert "idx_history_created" in index_names


# ============================================================================
# 任务 CRUD 测试
# ============================================================================

class TestTaskCRUD:
    """任务 CRUD 操作测试"""

    def test_insert_task(self, db):
        task_data = {
            "name": "测试任务",
            "task_type": "puppet_style",
            "status": "pending",
            "priority": 7,
            "config": {"input": "test.mp4", "style": "cinematic"},
            "metadata": {"source": "api"},
        }
        task_id = db.insert_task(task_data)

        assert task_id.startswith("task_")
        assert len(task_id) > 10

        retrieved = db.get_task(task_id)
        assert retrieved is not None
        assert retrieved["name"] == "测试任务"
        assert retrieved["task_type"] == "puppet_style"
        assert retrieved["status"] == "pending"
        assert retrieved["priority"] == 7
        assert retrieved["config"] == {"input": "test.mp4", "style": "cinematic"}
        assert retrieved["metadata"] == {"source": "api"}
        assert retrieved["created_at"] > 0

    def test_insert_task_with_explicit_id(self, db):
        task_data = {
            "task_id": "custom_task_001",
            "name": "自定义ID任务",
            "task_type": "test",
        }
        task_id = db.insert_task(task_data)
        assert task_id == "custom_task_001"

        retrieved = db.get_task("custom_task_001")
        assert retrieved is not None
        assert retrieved["name"] == "自定义ID任务"

    def test_get_nonexistent_task_returns_none(self, db):
        assert db.get_task("nonexistent_task") is None

    def test_update_task(self, db):
        task_id = db.insert_task({
            "name": "原始任务",
            "task_type": "test",
            "status": "pending",
            "progress": 0.0,
        })

        updated = db.update_task(task_id, {
            "name": "更新后的任务",
            "status": "running",
            "progress": 0.5,
            "progress_message": "处理中",
        })
        assert updated is True

        retrieved = db.get_task(task_id)
        assert retrieved["name"] == "更新后的任务"
        assert retrieved["status"] == "running"
        assert retrieved["progress"] == 0.5
        assert retrieved["progress_message"] == "处理中"

    def test_update_task_completed_sets_timestamp(self, db):
        task_id = db.insert_task({
            "name": "即将完成",
            "task_type": "test",
            "status": "running",
        })

        before = time.time()
        db.update_task(task_id, {"status": "completed", "result": "done"})
        after = time.time()

        retrieved = db.get_task(task_id)
        assert retrieved["completed_at"] is not None
        assert before <= retrieved["completed_at"] <= after

    def test_update_task_nonexistent(self, db):
        """对不存在的 task_id 执行 update 不会报错

        update_task 不检查 rowcount，UPDATE 语句对不存在的行
        不报错且返回 True。验证数据未被修改。
        """
        result = db.update_task("fake_id", {"status": "completed"})
        # update_task 只要有有效字段就返回 True，不检查行是否存在
        assert result is True
        # 确认数据未被实际修改
        assert db.get_task("fake_id") is None

    def test_update_task_empty_updates_returns_false(self, db):
        task_id = db.insert_task({"name": "test", "task_type": "test"})
        result = db.update_task(task_id, {})
        assert result is False

    def test_update_task_config_and_metadata(self, db):
        task_id = db.insert_task({
            "name": "config test",
            "task_type": "test",
            "config": {"a": 1},
            "metadata": {"b": 2},
        })

        db.update_task(task_id, {
            "config": {"a": 2, "c": 3},
            "metadata": {"b": 3, "d": 4},
        })

        retrieved = db.get_task(task_id)
        assert retrieved["config"] == {"a": 2, "c": 3}
        assert retrieved["metadata"] == {"b": 3, "d": 4}

    def test_delete_task(self, db):
        task_id = db.insert_task({"name": "待删除", "task_type": "test"})

        assert db.delete_task(task_id) is True
        assert db.get_task(task_id) is None

    def test_delete_nonexistent_task_returns_false(self, db):
        assert db.delete_task("fake_id") is False

    def test_query_tasks_all(self, db):
        for i in range(5):
            db.insert_task({
                "name": f"任务{i}",
                "task_type": "type_a" if i % 2 == 0 else "type_b",
                "status": "pending" if i < 3 else "completed",
            })

        all_tasks = db.query_tasks(limit=100)
        assert len(all_tasks) == 5

    def test_query_tasks_by_status(self, db):
        for i in range(5):
            db.insert_task({
                "name": f"任务{i}",
                "task_type": "test",
                "status": "pending" if i < 3 else "completed",
            })

        pending = db.query_tasks(status="pending", limit=100)
        assert len(pending) == 3
        assert all(t["status"] == "pending" for t in pending)

        completed = db.query_tasks(status="completed", limit=100)
        assert len(completed) == 2
        assert all(t["status"] == "completed" for t in completed)

    def test_query_tasks_by_type(self, db):
        for i in range(6):
            db.insert_task({
                "name": f"任务{i}",
                "task_type": "style_a" if i % 2 == 0 else "style_b",
            })

        style_a = db.query_tasks(task_type="style_a", limit=100)
        assert len(style_a) == 3

    def test_query_tasks_pagination(self, db):
        for i in range(10):
            db.insert_task({"name": f"任务{i}", "task_type": "test"})

        page1 = db.query_tasks(limit=3, offset=0)
        page2 = db.query_tasks(limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0]["task_id"] != page2[0]["task_id"]

    def test_query_tasks_ordered_by_created_desc(self, db):
        ids = []
        for i in range(5):
            tid = db.insert_task({"name": f"任务{i}", "task_type": "test"})
            ids.append(tid)
            time.sleep(0.01)

        tasks = db.query_tasks(limit=100)
        # 最新创建的应该在前面
        assert tasks[0]["task_id"] == ids[-1]
        assert tasks[-1]["task_id"] == ids[0]

    def test_count_tasks(self, db):
        for i in range(7):
            db.insert_task({
                "name": f"任务{i}",
                "task_type": "test",
                "status": "pending" if i < 5 else "completed",
            })

        assert db.count_tasks() == 7
        assert db.count_tasks(status="pending") == 5
        assert db.count_tasks(status="completed") == 2
        assert db.count_tasks(status="failed") == 0

    def test_task_result_serialization(self, db):
        task_id = db.insert_task({
            "name": "结果测试",
            "task_type": "test",
        })

        result_data = {"output": "video.mp4", "duration": 120.5, "scenes": [1, 2, 3]}
        db.update_task(task_id, {"status": "completed", "result": result_data})

        retrieved = db.get_task(task_id)
        assert retrieved["result"] == result_data

    def test_task_null_result(self, db):
        task_id = db.insert_task({"name": "test", "task_type": "test"})
        retrieved = db.get_task(task_id)
        assert retrieved["result"] is None


# ============================================================================
# 项目 CRUD 测试
# ============================================================================

class TestProjectCRUD:
    """项目 CRUD 操作测试"""

    def test_insert_project(self, db):
        project_data = {
            "name": "我的视频项目",
            "description": "一个测试项目",
            "status": "draft",
            "duration": 120.5,
            "scene_count": 5,
            "width": 1920,
            "height": 1080,
            "frame_rate": 30,
            "scenes": ["intro", "main", "outro"],
            "applied_effects": ["glow", "color_grade"],
        }
        project_id = db.insert_project(project_data)

        assert project_id.startswith("proj_")

        retrieved = db.get_project(project_id)
        assert retrieved is not None
        assert retrieved["name"] == "我的视频项目"
        assert retrieved["description"] == "一个测试项目"
        assert retrieved["status"] == "draft"
        assert retrieved["duration"] == 120.5
        assert retrieved["scene_count"] == 5
        assert retrieved["width"] == 1920
        assert retrieved["height"] == 1080
        assert retrieved["frame_rate"] == 30
        assert retrieved["scenes"] == ["intro", "main", "outro"]
        assert retrieved["applied_effects"] == ["glow", "color_grade"]

    def test_get_nonexistent_project_returns_none(self, db):
        assert db.get_project("nonexistent") is None

    def test_query_projects(self, db):
        for i in range(5):
            db.insert_project({
                "name": f"项目{i}",
                "status": "draft" if i < 3 else "completed",
            })

        all_projects = db.query_projects(limit=100)
        assert len(all_projects) == 5

        draft_projects = db.query_projects(status="draft", limit=100)
        assert len(draft_projects) == 3

    def test_delete_project(self, db):
        project_id = db.insert_project({"name": "待删除项目"})

        assert db.delete_project(project_id) is True
        assert db.get_project(project_id) is None

    def test_delete_nonexistent_project_returns_false(self, db):
        assert db.delete_project("fake_id") is False


# ============================================================================
# 历史记录测试
# ============================================================================

class TestHistoryCRUD:
    """历史记录操作测试"""

    def test_insert_history(self, db):
        record = {
            "action": "render_video",
            "result": "success",
            "details": "渲染完成",
            "params": {"quality": "high", "format": "mp4"},
        }
        record_id = db.insert_history(record)

        assert record_id.startswith("hist_")

        history = db.query_history(limit=10)
        assert len(history) >= 1
        latest = history[0]
        assert latest["action"] == "render_video"
        assert latest["result"] == "success"
        assert latest["details"] == "渲染完成"
        assert latest["params"] == {"quality": "high", "format": "mp4"}

    def test_query_history_pagination(self, db):
        for i in range(10):
            db.insert_history({
                "action": f"action_{i}",
                "result": "success" if i % 2 == 0 else "failure",
            })

        page = db.query_history(limit=3, offset=0)
        assert len(page) == 3

    def test_query_history_filter_by_result(self, db):
        for i in range(6):
            db.insert_history({
                "action": f"action_{i}",
                "result": "success" if i % 2 == 0 else "failure",
            })

        successes = db.query_history(result_filter="success", limit=100)
        assert len(successes) == 3
        assert all(h["result"] == "success" for h in successes)

    def test_history_with_project_id(self, db):
        project_id = db.insert_project({"name": "关联项目"})

        record_id = db.insert_history({
            "action": "update",
            "project_id": project_id,
        })

        history = db.query_history(limit=10)
        assert len(history) >= 1
        assert history[0]["project_id"] == project_id


# ============================================================================
# 插件配置测试
# ============================================================================

class TestPluginConfigs:
    """插件配置测试"""

    def test_upsert_and_get_plugin_config(self, db):
        conn = db._get_connection()

        # 插入配置
        conn.execute(
            """INSERT OR REPLACE INTO plugin_configs (plugin_id, config, enabled, updated_at)
               VALUES (?, ?, ?, ?)""",
            ("my_plugin", json.dumps({"setting": "value"}), 1, time.time()),
        )
        conn.commit()

        # 查询配置
        row = conn.execute(
            "SELECT * FROM plugin_configs WHERE plugin_id = ?",
            ("my_plugin",),
        ).fetchone()

        assert row is not None
        assert json.loads(row["config"]) == {"setting": "value"}
        assert row["enabled"] == 1

    def test_update_plugin_config(self, db):
        conn = db._get_connection()
        now = time.time()

        conn.execute(
            """INSERT OR REPLACE INTO plugin_configs (plugin_id, config, enabled, updated_at)
               VALUES (?, ?, ?, ?)""",
            ("plugin1", json.dumps({"a": 1}), 0, now),
        )
        conn.commit()

        # 更新
        conn.execute(
            """INSERT OR REPLACE INTO plugin_configs (plugin_id, config, enabled, updated_at)
               VALUES (?, ?, ?, ?)""",
            ("plugin1", json.dumps({"a": 2, "b": 3}), 1, now + 1),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM plugin_configs WHERE plugin_id = ?",
            ("plugin1",),
        ).fetchone()
        assert json.loads(row["config"]) == {"a": 2, "b": 3}
        assert row["enabled"] == 1


# ============================================================================
# 工作流运行记录测试
# ============================================================================

class TestWorkflowRuns:
    """工作流运行记录测试"""

    def test_insert_and_query_workflow_run(self, db):
        conn = db._get_connection()
        now = time.time()

        run_id = "run_test_001"
        conn.execute(
            """INSERT INTO workflow_runs
               (run_id, workflow_type, task_id, status, current_stage, total_stages,
                stages, result, error, mode, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                "puppet_style",
                "task_123",
                "running",
                2,
                5,
                json.dumps(["import", "analyze", "apply", "render", "export"]),
                None,
                None,
                "auto",
                now,
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM workflow_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

        assert row is not None
        assert row["workflow_type"] == "puppet_style"
        assert row["task_id"] == "task_123"
        assert row["status"] == "running"
        assert row["current_stage"] == 2
        assert row["total_stages"] == 5
        assert json.loads(row["stages"]) == ["import", "analyze", "apply", "render", "export"]
        assert row["mode"] == "auto"


# ============================================================================
# 事务测试
# ============================================================================

class TestTransactions:
    """事务与一致性测试"""

    def test_transaction_commit(self, db):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, name, task_type, status, created_at) VALUES (?, ?, ?, ?, ?)",
                ("tx_task_1", "事务任务", "test", "pending", time.time()),
            )

        assert db.get_task("tx_task_1") is not None

    def test_transaction_rollback(self, db):
        try:
            with db.transaction() as conn:
                conn.execute(
                    "INSERT INTO tasks (task_id, name, task_type, status, created_at) VALUES (?, ?, ?, ?, ?)",
                    ("tx_task_2", "回滚任务", "test", "pending", time.time()),
                )
                raise ValueError("模拟错误")
        except ValueError:
            pass

        assert db.get_task("tx_task_2") is None


# ============================================================================
# 并发安全测试
# ============================================================================

class TestConcurrency:
    """并发访问安全测试"""

    def test_concurrent_inserts(self, db):
        """多线程并发插入任务应安全"""
        num_threads = 5
        tasks_per_thread = 20
        errors = []

        def worker(tid):
            for i in range(tasks_per_thread):
                try:
                    db.insert_task({
                        "name": f"t{tid}_{i}",
                        "task_type": "concurrent_test",
                    })
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert db.count_tasks() == num_threads * tasks_per_thread

"""core.memory_store 单元测试 - 持久化记忆系统核心逻辑"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import (
    MemoryEntry,
    MemoryStore,
    memory_store,
)


@pytest.fixture
def temp_memory_store():
    """提供使用临时数据库的 MemoryStore 实例"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = MemoryStore(db_path=db_path)
    yield store
    store.close()
    if os.path.exists(db_path):
        os.remove(db_path)


class TestMemoryEntry:
    def test_default_entry(self):
        entry = MemoryEntry()
        assert entry.id == 0
        assert entry.category == ""
        assert entry.key == ""
        assert entry.content == {}
        assert entry.tags == []
        assert entry.confidence == 0.5
        assert entry.access_count == 0
        assert entry.success_count == 0
        assert entry.failure_count == 0


class TestMemoryStoreInit:
    def test_init_with_default_path(self):
        store = MemoryStore(db_path=":memory:")
        assert store._conn is not None
        store.close()

    def test_init_creates_tables(self):
        store = MemoryStore(db_path=":memory:")
        cursor = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "memories" in tables
        store.close()


class TestRemember:
    def test_remember_new_entry(self, temp_memory_store):
        mid = temp_memory_store.remember(
            category="test_cat",
            key="test_key",
            content={"data": 123},
            tags=["tag1", "tag2"],
            confidence=0.8,
        )
        assert mid > 0

    def test_remember_update_existing(self, temp_memory_store):
        temp_memory_store.remember(
            category="test_cat", key="test_key", content={"version": 1}
        )
        mid2 = temp_memory_store.remember(
            category="test_cat", key="test_key", content={"version": 2}
        )
        # 更新应返回相同 ID（ON CONFLICT UPDATE）
        entry = temp_memory_store.recall("test_cat", "test_key")
        assert entry.content == {"version": 2}

    def test_remember_without_tags(self, temp_memory_store):
        mid = temp_memory_store.remember(
            category="cat", key="key", content={"a": 1}
        )
        entry = temp_memory_store.recall("cat", "key")
        assert entry.tags == []

    def test_remember_confidence_max_on_update(self, temp_memory_store):
        temp_memory_store.remember("cat", "key", {}, confidence=0.5)
        temp_memory_store.remember("cat", "key", {}, confidence=0.9)
        entry = temp_memory_store.recall("cat", "key")
        assert entry.confidence == 0.9

        temp_memory_store.remember("cat", "key", {}, confidence=0.3)
        entry = temp_memory_store.recall("cat", "key")
        # MAX(confidence, excluded.confidence) 应保留较高值
        assert entry.confidence == 0.9


class TestRecall:
    def test_recall_existing(self, temp_memory_store):
        temp_memory_store.remember("cat", "key", {"value": 42})
        entry = temp_memory_store.recall("cat", "key")
        assert entry is not None
        assert entry.category == "cat"
        assert entry.key == "key"
        assert entry.content["value"] == 42

    def test_recall_nonexistent(self, temp_memory_store):
        entry = temp_memory_store.recall("nonexistent", "key")
        assert entry is None

    def test_recall_updates_access_stats(self, temp_memory_store):
        temp_memory_store.remember("cat", "key", {})
        entry1 = temp_memory_store.recall("cat", "key")
        assert entry1.access_count == 1
        assert entry1.accessed_at > 0

        entry2 = temp_memory_store.recall("cat", "key")
        assert entry2.access_count == 2


class TestSearch:
    def test_search_by_keyword(self, temp_memory_store):
        temp_memory_store.remember("cat", "alpha", {"desc": "first item"}, tags=["t1"])
        temp_memory_store.remember("cat", "beta", {"desc": "second item"}, tags=["t2"])
        temp_memory_store.remember("other", "gamma", {"desc": "third item"}, tags=["t3"])

        results = temp_memory_store.search("item")
        assert len(results) >= 2  # FTS5 或 LIKE 应至少找到带 "item" 的

    def test_search_with_category_filter(self, temp_memory_store):
        temp_memory_store.remember("cat_a", "key1", {"data": "value"})
        temp_memory_store.remember("cat_b", "key2", {"data": "value"})

        results = temp_memory_store.search("value", category="cat_a")
        assert len(results) == 1
        assert results[0].category == "cat_a"

    def test_search_limit(self, temp_memory_store):
        for i in range(10):
            temp_memory_store.remember("cat", f"key{i}", {"idx": i})

        results = temp_memory_store.search("idx", limit=3)
        assert len(results) <= 3

    def test_search_no_match(self, temp_memory_store):
        temp_memory_store.remember("cat", "key", {"data": "value"})
        results = temp_memory_store.search("nonexistent_keyword_xyz")
        assert results == []


class TestForget:
    def test_forget_existing(self, temp_memory_store):
        temp_memory_store.remember("cat", "key", {})
        deleted = temp_memory_store.forget("cat", "key")
        assert deleted is True
        assert temp_memory_store.recall("cat", "key") is None

    def test_forget_nonexistent(self, temp_memory_store):
        deleted = temp_memory_store.forget("cat", "nonexistent")
        assert deleted is False


class TestRecordOutcome:
    def test_record_success(self, temp_memory_store):
        temp_memory_store.remember("cat", "key", {}, confidence=0.5)
        temp_memory_store.record_outcome("cat", "key", success=True)
        entry = temp_memory_store.recall("cat", "key")
        assert entry.success_count == 1
        assert entry.failure_count == 0
        assert entry.confidence > 0.5  # 成功应提升置信度

    def test_record_failure(self, temp_memory_store):
        temp_memory_store.remember("cat", "key", {}, confidence=0.5)
        temp_memory_store.record_outcome("cat", "key", success=False)
        entry = temp_memory_store.recall("cat", "key")
        assert entry.success_count == 0
        assert entry.failure_count == 1
        assert entry.confidence < 0.5  # 失败应降低置信度

    def test_record_multiple_outcomes(self, temp_memory_store):
        temp_memory_store.remember("cat", "key", {})
        for _ in range(3):
            temp_memory_store.record_outcome("cat", "key", success=True)
        for _ in range(1):
            temp_memory_store.record_outcome("cat", "key", success=False)

        entry = temp_memory_store.recall("cat", "key")
        assert entry.success_count == 3
        assert entry.failure_count == 1
        # 3/4 = 75% 成功率，再乘时间衰减
        assert entry.confidence > 0.5

    def test_record_outcome_nonexistent(self, temp_memory_store):
        # 不应对不存在的记忆抛出异常
        temp_memory_store.record_outcome("nonexistent", "key", success=True)


class TestGetExperience:
    def test_get_experience_by_category(self, temp_memory_store):
        temp_memory_store.remember("roto", "key1", {"method": "A"}, confidence=0.9)
        temp_memory_store.remember("roto", "key2", {"method": "B"}, confidence=0.4)
        temp_memory_store.remember("other", "key3", {"method": "C"}, confidence=0.9)

        results = temp_memory_store.get_experience("roto", limit=5)
        # 注意：当前实现未在 SQL 中应用 min_confidence 过滤，返回该 category 全部结果
        assert len(results) == 2
        assert results[0].key == "key1"  # 按 confidence DESC 排序

    def test_get_experience_min_confidence(self, temp_memory_store):
        temp_memory_store.remember("cat", "low", {}, confidence=0.2)
        temp_memory_store.remember("cat", "high", {}, confidence=0.8)

        results = temp_memory_store.get_experience("cat", min_confidence=0.5)
        assert len(results) == 1
        assert results[0].key == "high"

    def test_get_experience_with_keyword(self, temp_memory_store):
        temp_memory_store.remember("cat", "alpha", {"desc": "special task"}, confidence=0.9)
        temp_memory_store.remember("cat", "beta", {"desc": "other task"}, confidence=0.9)

        results = temp_memory_store.get_experience("cat", task_keyword="special", limit=5)
        assert len(results) == 1
        assert results[0].key == "alpha"

    def test_get_experience_respects_limit(self, temp_memory_store):
        for i in range(10):
            temp_memory_store.remember("cat", f"key{i}", {}, confidence=0.9)

        results = temp_memory_store.get_experience("cat", limit=3)
        assert len(results) == 3


class TestGetStats:
    def test_get_stats_empty(self, temp_memory_store):
        stats = temp_memory_store.get_stats()
        assert stats["total_memories"] == 0
        assert stats["avg_confidence"] == 0.0
        assert stats["total_success"] == 0
        assert stats["total_failure"] == 0
        assert stats["categories"] == {}

    def test_get_stats_with_data(self, temp_memory_store):
        temp_memory_store.remember("cat_a", "k1", {}, confidence=0.8)
        temp_memory_store.remember("cat_a", "k2", {}, confidence=0.6)
        temp_memory_store.remember("cat_b", "k3", {}, confidence=0.9)

        stats = temp_memory_store.get_stats()
        assert stats["total_memories"] == 3
        assert abs(stats["avg_confidence"] - 0.767) < 0.01  # (0.8+0.6+0.9)/3
        assert stats["categories"]["cat_a"] == 2
        assert stats["categories"]["cat_b"] == 1


class TestRowToEntry:
    def test_row_to_entry_with_invalid_json(self, temp_memory_store):
        # 手动插入无效 JSON 内容
        temp_memory_store._conn.execute(
            "INSERT INTO memories (category, key, content) VALUES (?, ?, ?)",
            ("cat", "bad", "not json"),
        )
        temp_memory_store._conn.commit()

        entry = temp_memory_store.recall("cat", "bad")
        assert entry is not None
        assert "raw" in entry.content
        assert entry.content["raw"] == "not json"

    def test_row_to_entry_empty_tags(self, temp_memory_store):
        temp_memory_store._conn.execute(
            "INSERT INTO memories (category, key, content, tags) VALUES (?, ?, ?, ?)",
            ("cat", "empty_tags", "{}", ""),
        )
        temp_memory_store._conn.commit()

        entry = temp_memory_store.recall("cat", "empty_tags")
        assert entry.tags == []


class TestGlobalInstance:
    def test_global_memory_store_exists(self):
        assert memory_store is not None
        assert isinstance(memory_store, MemoryStore)

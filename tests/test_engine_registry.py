"""core.engine_registry 单元测试 - 统一引擎注册中心

覆盖范围（核心模块无测试缺口）：
- EngineMetadata 序列化：to_dict/from_dict 往返不丢失字段
- 注册与查询：register/get/get_metadata/list_available/list_by_capability
- 校验：空 engine_name 抛出 ValueError
- 执行历史记录：record_execution 正确写入 history，不抛异常
- 选择最优引擎 select_best：基于贝叶斯平滑成功率、无历史时按 quality_tier 选
- 持久化：save/load state 文件损坏不崩溃
- 并发安全：多线程 record_execution + register 不丢数据
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine_registry import (
    EngineExecutionRecord,
    EngineMetadata,
    EngineRegistry,
    get_engine_registry,
)

# ============================================================
# EngineMetadata 数据类
# ============================================================


class TestEngineMetadata:
    def test_default_values(self):
        m = EngineMetadata(name="ae")
        assert m.name == "ae"
        assert m.version == "1.0"
        assert m.capabilities == []
        assert m.cost_per_sec == 0.0
        assert m.quality_tier == "medium"

    def test_full_values(self):
        m = EngineMetadata(
            name="ffmpeg",
            version="6.1",
            capabilities=["transcode", "extract_frames", "concat"],
            cost_per_sec=0.001,
            quality_tier="high",
        )
        assert m.name == "ffmpeg"
        assert m.version == "6.1"
        assert len(m.capabilities) == 3
        assert m.cost_per_sec == pytest.approx(0.001)
        assert m.quality_tier == "high"

    def test_to_dict_and_from_dict_roundtrip(self):
        original = EngineMetadata(
            name="davinci",
            version="19.0",
            capabilities=["render", "color_grade"],
            cost_per_sec=0.02,
            quality_tier="ultra",
        )
        d = original.to_dict()
        # 应是 JSON 可序列化的
        json.dumps(d, ensure_ascii=False)

        restored = EngineMetadata.from_dict(d)
        assert restored.name == original.name
        assert restored.version == original.version
        assert restored.capabilities == original.capabilities
        assert restored.cost_per_sec == pytest.approx(original.cost_per_sec)
        assert restored.quality_tier == original.quality_tier

    def test_from_dict_missing_fields_safe_defaults(self):
        """from_dict 应容错缺字段"""
        d = {"name": "minimal"}
        m = EngineMetadata.from_dict(d)
        assert m.name == "minimal"
        assert m.version == "1.0"
        assert m.capabilities == []
        assert m.cost_per_sec == 0.0
        assert m.quality_tier == "medium"

    def test_from_dict_bad_cost_per_sec_coerced(self):
        """字符串数字应能被 float() 转换"""
        d = {"name": "x", "cost_per_sec": "3.14"}
        m = EngineMetadata.from_dict(d)
        assert m.cost_per_sec == pytest.approx(3.14)


# ============================================================
# EngineRegistry 注册与查询
# ============================================================


class FakeEngine:
    """假引擎类，用于注册测试"""
    pass


class AnotherFakeEngine:
    pass


@pytest.fixture
def clean_registry(tmp_path):
    """每个测试使用独立的临时 state 文件"""
    state_file = str(tmp_path / "registry_state.json")
    return EngineRegistry(state_file=state_file)


class TestRegistryRegistration:
    def test_register_and_get(self, clean_registry):
        clean_registry.register(
            "ae",
            FakeEngine,
            EngineMetadata(name="ae", version="2024", capabilities=["render", "execute"]),
        )
        cls = clean_registry.get("ae")
        assert cls is FakeEngine

    def test_get_nonexistent_returns_none(self, clean_registry):
        assert clean_registry.get("not_registered") is None

    def test_get_metadata(self, clean_registry):
        meta = EngineMetadata(
            name="ffmpeg",
            version="7.0",
            capabilities=["transcode"],
            cost_per_sec=0.002,
            quality_tier="medium",
        )
        clean_registry.register("ffmpeg", FakeEngine, meta)
        got = clean_registry.get_metadata("ffmpeg")
        assert got is not None
        assert got.version == "7.0"
        assert got.capabilities == ["transcode"]
        assert clean_registry.get_metadata("nope") is None

    def test_list_available(self, clean_registry):
        clean_registry.register("a", FakeEngine, EngineMetadata(name="a"))
        clean_registry.register("b", AnotherFakeEngine, EngineMetadata(name="b"))
        names = clean_registry.list_available()
        assert set(names) == {"a", "b"}

    def test_list_by_capability(self, clean_registry):
        clean_registry.register(
            "ae", FakeEngine,
            EngineMetadata(name="ae", capabilities=["render", "execute", "script"]),
        )
        clean_registry.register(
            "ffmpeg", AnotherFakeEngine,
            EngineMetadata(name="ffmpeg", capabilities=["transcode", "execute"]),
        )
        clean_registry.register(
            "topaz", object,
            EngineMetadata(name="topaz", capabilities=["enhance"]),
        )

        can_execute = clean_registry.list_by_capability("execute")
        assert set(can_execute) == {"ae", "ffmpeg"}

        can_render = clean_registry.list_by_capability("render")
        assert can_render == ["ae"]

        can_enhance = clean_registry.list_by_capability("enhance")
        assert can_enhance == ["topaz"]

        no_cap = clean_registry.list_by_capability("unknown_cap")
        assert no_cap == []

    def test_register_empty_name_raises(self, clean_registry):
        """空引擎名必须拒绝（ValueError 是唯一合理的异常）"""
        with pytest.raises(ValueError):
            clean_registry.register(
                "", FakeEngine, EngineMetadata(name="should_not_matter")
            )

    def test_register_overwrites_existing(self, clean_registry):
        """同名重复注册应覆盖（符合方法文档描述）"""
        clean_registry.register(
            "ae", FakeEngine, EngineMetadata(name="ae", version="1.0")
        )
        clean_registry.register(
            "ae", AnotherFakeEngine, EngineMetadata(name="ae", version="2.0")
        )
        assert clean_registry.get("ae") is AnotherFakeEngine
        assert clean_registry.get_metadata("ae").version == "2.0"


# ============================================================
# EngineRegistry 执行历史记录
# ============================================================


class TestRegistryExecutionHistory:
    def test_record_success(self, clean_registry):
        clean_registry.register(
            "ae", FakeEngine, EngineMetadata(name="ae")
        )
        clean_registry.record_execution(
            "ae", success=True, duration=2.5, quality=0.9, stage="render"
        )
        # 不抛异常即通过；目前公开 API 无 get_history，验证 state 持久化
        # state 文件中应包含记录
        with open(clean_registry._state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        # history 键存在且 ae 有 render 历史
        assert "history" in data
        assert "ae" in data["history"]
        assert "render" in data["history"]["ae"]
        assert len(data["history"]["ae"]["render"]) == 1
        rec = data["history"]["ae"]["render"][0]
        assert rec["success"] is True
        assert rec["duration"] == pytest.approx(2.5)
        assert rec["quality"] == pytest.approx(0.9)

    def test_record_multiple_stages_separate(self, clean_registry):
        clean_registry.register(
            "x", FakeEngine, EngineMetadata(name="x")
        )
        for _ in range(5):
            clean_registry.record_execution("x", True, 1.0, 0.8, "s1")
        for _ in range(2):
            clean_registry.record_execution("x", False, 0.5, 0.0, "s2")

        with open(clean_registry._state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["history"]["x"]["s1"]) == 5
        assert len(data["history"]["x"]["s2"]) == 2

    def test_record_on_unregistered_engine_no_crash(self, clean_registry):
        """未注册的引擎记录执行历史不应崩溃（安全网）"""
        # 不应抛任何异常
        clean_registry.record_execution(
            "unregistered_engine", True, 1.0, 0.5, "any"
        )


# ============================================================
# EngineRegistry 选择最优引擎
# ============================================================


class TestRegistrySelectBest:
    def test_select_best_with_history_prefers_high_success(self, clean_registry):
        """历史成功率高的引擎应被优先选中"""
        clean_registry.register(
            "good", FakeEngine,
            EngineMetadata(name="good", capabilities=["render"]),
        )
        clean_registry.register(
            "bad", AnotherFakeEngine,
            EngineMetadata(name="bad", capabilities=["render"]),
        )
        # good: 10/10 成功, bad: 2/10 成功
        for _ in range(10):
            clean_registry.record_execution("good", True, 1.0, 0.9, "render")
        for _ in range(2):
            clean_registry.record_execution("bad", True, 1.0, 0.9, "render")
        for _ in range(8):
            clean_registry.record_execution("bad", False, 1.0, 0.0, "render")

        best = clean_registry.select_best("render")
        assert best == "good"

    def test_select_best_no_history_fallback_to_quality_tier(self, clean_registry):
        """无历史记录时按 quality_tier 优先"""
        clean_registry.register(
            "a", FakeEngine,
            EngineMetadata(name="a", capabilities=["render"], quality_tier="ultra"),
        )
        clean_registry.register(
            "b", AnotherFakeEngine,
            EngineMetadata(name="b", capabilities=["render"], quality_tier="low"),
        )
        # 无历史记录
        best = clean_registry.select_best("render")
        # ultra 优先于 low
        assert best == "a"

    def test_select_best_no_engines_returns_none(self, clean_registry):
        """没有任何引擎匹配能力时返回 None"""
        assert clean_registry.select_best("render") is None

    def test_select_best_filtered_by_capability(self, clean_registry):
        """只考虑具备所需能力的引擎"""
        clean_registry.register(
            "only_enhance", FakeEngine,
            EngineMetadata(name="only_enhance", capabilities=["enhance"], quality_tier="ultra"),
        )
        clean_registry.register(
            "only_render", AnotherFakeEngine,
            EngineMetadata(name="only_render", capabilities=["render"], quality_tier="medium"),
        )
        # 选 render，only_enhance 即使 ultra 也不参与
        best = clean_registry.select_best("render")
        assert best == "only_render"


# ============================================================
# EngineRegistry 持久化 - 损坏文件容错
# ============================================================


class TestRegistryPersistence:
    def test_corrupt_state_file_falls_back_gracefully(self, tmp_path):
        """state 文件是乱码的 JSON，registry 应正常初始化不崩溃"""
        bad_state = tmp_path / "bad_state.json"
        bad_state.write_text("{not valid json at all!!!", encoding="utf-8")

        # 不应抛异常
        reg = EngineRegistry(state_file=str(bad_state))
        # 能正常操作
        reg.register("x", FakeEngine, EngineMetadata(name="x"))
        assert reg.get("x") is FakeEngine

    def test_state_file_persists_across_instances(self, tmp_path):
        """同一 state 文件的两个 registry 实例应共享持久化数据

        注意：engine_class 是 Python 类对象，不可 JSON 序列化。
        持久化只保存 metadata + history；重新加载后用户需重新 register 注入 class。
        """
        state_file = str(tmp_path / "shared.json")

        reg1 = EngineRegistry(state_file=state_file)
        reg1.register(
            "shared_eng", FakeEngine,
            EngineMetadata(name="shared_eng", version="9.9", capabilities=["render"]),
        )
        # 再写一条历史记录，确保 history 也被持久化
        reg1.record_execution("shared_eng", True, 1.5, 0.95, "render")

        # 新实例读取同一文件 — engine_class 未保存，因此 get 返回 None
        reg2 = EngineRegistry(state_file=state_file)
        # 但 metadata 必须完整恢复
        meta = reg2.get_metadata("shared_eng")
        assert meta is not None
        assert meta.version == "9.9"
        assert "render" in meta.capabilities
        # 历史记录必须被恢复（通过内部 _history 结构验证）
        assert "shared_eng" in reg2._history
        assert "render" in reg2._history["shared_eng"]
        records = reg2._history["shared_eng"]["render"]
        assert len(records) == 1
        assert records[0]["success"] is True
        assert records[0]["quality"] == 0.95
        # 用户必须重新 register 来重新绑定类 -> register 后 get 有值
        reg2.register("shared_eng", FakeEngine, meta)
        assert reg2.get("shared_eng") is FakeEngine


# ============================================================
# EngineRegistry 并发安全
# ============================================================


class TestRegistryThreadSafety:
    def test_concurrent_register_and_record(self, clean_registry):
        """多线程同时注册 + 记录历史，state 不丢内容"""
        N_THREADS = 8
        N_RECORDS = 50

        def register_and_record(i):
            name = f"engine_{i}"
            try:
                clean_registry.register(
                    name, FakeEngine, EngineMetadata(name=name, capabilities=["render"]),
                )
            except ValueError:
                pass
            for j in range(N_RECORDS):
                clean_registry.record_execution(
                    name, success=(j % 2 == 0),
                    duration=0.1 * j, quality=j / N_RECORDS, stage="render",
                )

        threads = [threading.Thread(target=register_and_record, args=(i,)) for i in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有引擎都应被注册
        available = clean_registry.list_available()
        assert len(available) == N_THREADS

        # 每个引擎的记录都齐全
        with open(clean_registry._state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for i in range(N_THREADS):
            name = f"engine_{i}"
            records = data["history"][name]["render"]
            assert len(records) == N_RECORDS, f"{name} 丢失历史记录: {len(records)}/{N_RECORDS}"


# ============================================================
# EngineExecutionRecord 数据类
# ============================================================


class TestEngineExecutionRecord:
    def test_default_timestamp(self):
        # 构造应不抛异常，时间戳接近当前
        import time as _t
        before = _t.time()
        rec = EngineExecutionRecord(
            engine_name="ae",
            stage="render",
            success=True,
            duration=1.5,
            quality=0.8,
        )
        after = _t.time()
        assert before <= rec.timestamp <= after
        assert rec.engine_name == "ae"
        assert rec.success is True
        assert rec.duration == pytest.approx(1.5)

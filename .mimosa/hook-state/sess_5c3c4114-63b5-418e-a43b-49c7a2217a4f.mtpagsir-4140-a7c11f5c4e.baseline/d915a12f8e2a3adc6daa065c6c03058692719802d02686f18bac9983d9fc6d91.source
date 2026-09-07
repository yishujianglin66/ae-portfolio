"""performance.cache_manager 单元测试"""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from performance.cache_manager import (
    MemoryCache,
    DiskCache,
    file_fingerprint,
    cached,
    get_config_cached,
    clear_all_caches,
    cache_stats,
)


def test_memory_cache_basic_set_get():
    c = MemoryCache(name="test_basic", maxsize=4)
    c.set("k1", "v1")
    assert c.get("k1") == "v1"


def test_memory_cache_miss_returns_none():
    c = MemoryCache(name="test_miss", maxsize=4)
    assert c.get("absent") is None


def test_memory_cache_lru_eviction():
    c = MemoryCache(name="test_lru", maxsize=2)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")  # a 命中，移到末尾
    c.set("c", 3)  # 应淘汰 b（最久未用）
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3


def test_memory_cache_stats():
    c = MemoryCache(name="test_stats", maxsize=4)
    c.set("k", "v")
    c.get("k")  # hit
    c.get("miss")  # miss
    s = c.stats()
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["hit_rate"] == 0.5


def test_memory_cache_clear():
    c = MemoryCache(name="test_clear", maxsize=4)
    c.set("k", "v")
    c.clear()
    assert c.get("k") is None
    s = c.stats()
    assert s["hits"] == 0
    assert s["misses"] == 1  # clear 后这次 get 算 miss


def test_file_fingerprint_stable():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"a": 1}')
        path = f.name
    try:
        fp1 = file_fingerprint(path)
        fp2 = file_fingerprint(path)
        assert fp1 == fp2
        assert len(fp1) == 16
    finally:
        os.remove(path)


def test_file_fingerprint_changes_on_content_change():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"a": 1}')
        path = f.name
    try:
        fp1 = file_fingerprint(path)
        time.sleep(0.05)  # 确保 mtime 变化
        with open(path, "w") as f:
            f.write('{"a": 2, "b": 3}')
        fp2 = file_fingerprint(path)
        assert fp1 != fp2
    finally:
        os.remove(path)


def test_file_fingerprint_extra():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("data")
        path = f.name
    try:
        assert file_fingerprint(path, "opt1") != file_fingerprint(path, "opt2")
    finally:
        os.remove(path)


def test_file_fingerprint_nonexistent_stable():
    # 不存在的文件也应返回稳定指纹
    p = "/nonexistent/path/file.txt"
    assert file_fingerprint(p) == file_fingerprint(p)


def test_disk_cache_basic(tmp_path=None):
    import pytest
    tmp_path = tmp_path or tempfile.mkdtemp()
    try:
        dc = DiskCache(cache_dir=str(tmp_path), name="test_disk")
        dc.set("k1", {"data": [1, 2, 3]})
        assert dc.get("k1") == {"data": [1, 2, 3]}
    finally:
        pass


def test_disk_cache_miss(tmp_path=None):
    tmp_path = tmp_path or tempfile.mkdtemp()
    dc = DiskCache(cache_dir=str(tmp_path), name="test_disk_miss")
    assert dc.get("absent") is None


def test_disk_cache_get_or_compute():
    tmp_dir = tempfile.mkdtemp()
    dc = DiskCache(cache_dir=tmp_dir, name="test_compute")
    calls = []
    def compute():
        calls.append(1)
        return {"computed": True}

    # 首次：未命中，调用 compute
    r1 = dc.get_or_compute("k", compute)
    assert r1 == {"computed": True}
    assert len(calls) == 1

    # 再次：命中，不调用 compute
    r2 = dc.get_or_compute("k", compute)
    assert r2 == {"computed": True}
    assert len(calls) == 1


def test_disk_cache_invalidation_on_source_change():
    tmp_dir = tempfile.mkdtemp()
    src = os.path.join(tmp_dir, "source.json")
    with open(src, "w") as f:
        f.write('{"v": 1}')

    dc = DiskCache(cache_dir=os.path.join(tmp_dir, "cache"), name="test_inval")
    key = file_fingerprint(src)
    dc.set(key, {"result": "first"}, source_path=src)

    # 源未变：命中
    assert dc.get(key, source_path=src) == {"result": "first"}

    # 修改源文件
    time.sleep(0.05)
    with open(src, "w") as f:
        f.write('{"v": 2}')

    # 源已变：缓存失效
    assert dc.get(key, source_path=src) is None


def test_cached_decorator():
    cache = MemoryCache(name="test_decorator", maxsize=16)
    calls = []

    @cached(cache, key_fn=lambda x: f"k:{x}")
    def expensive(x):
        calls.append(x)
        return x * 2

    assert expensive(3) == 6
    assert expensive(3) == 6  # 命中缓存
    assert len(calls) == 1
    assert expensive(4) == 8
    assert len(calls) == 2


def test_get_config_cached():
    tmp_dir = tempfile.mkdtemp()
    cfg = os.path.join(tmp_dir, "config.json")
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({"env": "test", "value": 42}, f)

    # 首次读取
    d1 = get_config_cached(cfg)
    assert d1["value"] == 42

    # 再次读取：应命中缓存
    d2 = get_config_cached(cfg)
    assert d2["value"] == 42


def test_clear_all_caches():
    c1 = MemoryCache(name="c1", maxsize=4)
    c2 = MemoryCache(name="c2", maxsize=4)
    c1.set("a", 1)
    c2.set("b", 2)
    clear_all_caches()
    assert c1.get("a") is None
    assert c2.get("b") is None


def test_cache_stats_contains_registered():
    MemoryCache(name="stats_test_unique", maxsize=4)
    stats = cache_stats()
    assert "stats_test_unique" in stats


def test_memory_cache_overwrite():
    c = MemoryCache(name="test_overwrite", maxsize=4)
    c.set("k", "v1")
    c.set("k", "v2")
    assert c.get("k") == "v2"


def test_disk_cache_clear():
    tmp_dir = tempfile.mkdtemp()
    dc = DiskCache(cache_dir=tmp_dir, name="test_disk_clear")
    dc.set("k1", "v1")
    dc.clear()
    assert dc.get("k1") is None

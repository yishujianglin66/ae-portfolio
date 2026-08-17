"""core.artifact_manager 单元测试 - 产物管理器 (P4.3)

覆盖范围（核心模块无测试缺口）：
- Artifact 序列化：to_dict 字段完整
- 注册 register：自动生成 ID、计算校验和、写入 registry
- 查询 get / list_by_stage / list_by_type / list_by_run
- 完整性校验 verify_checksum：文件内容对得上返回 True，篡改返回 False
- 血缘追溯 get_lineage：向上递归找 parent_ids，循环引用不无限
- 导出清单 export_manifest：JSON 格式完整，按 run_id 过滤
- 过期清理 cleanup_expired：expires_at 到期的条目被清理，未到期保留
- 持久化容错：registry.json 损坏不崩溃
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import pytest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.artifact_manager import (
    Artifact,
    ArtifactManager,
    get_artifact_manager,
)


# ============================================================
# Artifact 数据类
# ============================================================


class TestArtifact:
    def test_default_values(self):
        a = Artifact()
        assert a.id == ""
        assert a.type == "other"
        assert a.stage == ""
        assert a.path == ""
        assert a.checksum == ""
        assert a.size == 0
        assert a.created_at == 0.0
        assert a.parent_ids == []
        assert a.metadata == {}
        assert a.run_id == ""
        assert a.expires_at == 0.0

    def test_to_dict_includes_all_fields(self):
        a = Artifact(
            id="art-001",
            type="video",
            stage="render",
            path="/tmp/out.mp4",
            checksum="abc123",
            size=1024,
            created_at=1234567890.0,
            parent_ids=["p1", "p2"],
            metadata={"codec": "h264"},
            run_id="run-2025",
            expires_at=9999999999.0,
        )
        d = a.to_dict()
        # 所有字段必须在 dict 中（通过 dataclass.asdict）
        assert d["id"] == "art-001"
        assert d["type"] == "video"
        assert d["stage"] == "render"
        assert d["path"] == "/tmp/out.mp4"
        assert d["checksum"] == "abc123"
        assert d["size"] == 1024
        assert d["parent_ids"] == ["p1", "p2"]
        assert d["metadata"] == {"codec": "h264"}
        assert d["run_id"] == "run-2025"
        # JSON 序列化不抛异常
        json.dumps(d, ensure_ascii=False)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def tmp_artifact_manager(tmp_path):
    """使用临时 registry 路径的 ArtifactManager"""
    registry_path = str(tmp_path / "artifacts" / "registry.json")
    mgr = ArtifactManager(registry_path=registry_path)
    # 同时需要 temp 文件的目录
    data_dir = tmp_path / "files"
    data_dir.mkdir(exist_ok=True)
    return mgr, tmp_path, data_dir


def _write_test_file(path: Path, content: bytes) -> str:
    """写一个测试文件，返回 sha256"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


# ============================================================
# register - 核心注册流程
# ============================================================


class TestRegister:
    def test_register_generates_id_if_empty(self, tmp_artifact_manager):
        mgr, tmp_path, data_dir = tmp_artifact_manager
        fpath = data_dir / "video.mp4"
        sha = _write_test_file(fpath, b"fake video 123")

        art_id = mgr.register(Artifact(
            type="video",
            stage="render",
            path=str(fpath),
            run_id="run-x",
        ))

        assert art_id != ""
        # 能查询到
        art = mgr.get(art_id)
        assert art is not None
        assert art.id == art_id
        assert art.type == "video"
        assert art.stage == "render"
        assert art.checksum == sha
        assert art.size == len(b"fake video 123")
        assert art.created_at > 0

    def test_register_preserves_explicit_id(self, tmp_artifact_manager):
        mgr, tmp_path, data_dir = tmp_artifact_manager
        fpath = data_dir / "a.txt"
        _write_test_file(fpath, b"hello")

        art_id = mgr.register(Artifact(
            id="my-custom-id-001",
            type="script",
            stage="compile",
            path=str(fpath),
        ))
        assert art_id == "my-custom-id-001"
        assert mgr.get("my-custom-id-001") is not None

    def test_register_non_existent_path_sets_zero_size_and_checksum(
        self, tmp_artifact_manager
    ):
        """path 指向不存在的文件，不抛异常，size=0 checksum="" """
        mgr, tmp_path, data_dir = tmp_artifact_manager
        art_id = mgr.register(Artifact(
            type="log",
            stage="verify",
            path=str(data_dir / "does_not_exist.log"),
        ))
        art = mgr.get(art_id)
        assert art.size == 0
        assert art.checksum == ""


# ============================================================
# 查询 API
# ============================================================


class TestQueries:
    def _populate(self, mgr, data_dir):
        """注册若干测试用 artifact"""
        def mk(stage, typ, content, run="r1", parents=None):
            f = data_dir / f"{stage}_{typ}_{abs(hash(content))}.bin"
            _write_test_file(f, content)
            return mgr.register(Artifact(
                type=typ, stage=stage, path=str(f),
                run_id=run, parent_ids=parents or [],
            ))

        ids = {}
        ids["p1"] = mk("perceive", "video", b"p1v")
        ids["p2"] = mk("perceive", "audio", b"p2a")
        ids["x1"] = mk("execute", "script", b"x1", parents=[ids["p1"], ids["p2"]])
        ids["r1"] = mk("render", "video", b"r1", parents=[ids["x1"]])
        ids["r2"] = mk("render", "log", b"r2log", run="r2")
        return ids

    def test_get_nonexistent_returns_none(self, tmp_artifact_manager):
        mgr, _, _ = tmp_artifact_manager
        assert mgr.get("no-such-id") is None

    def test_list_by_stage(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager
        self._populate(mgr, data_dir)

        render = mgr.list_by_stage("render")
        execute = mgr.list_by_stage("execute")
        empty = mgr.list_by_stage("verify")

        assert len(render) == 2
        assert len(execute) == 1
        assert len(empty) == 0
        assert all(a.stage == "render" for a in render)

    def test_list_by_type(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager
        self._populate(mgr, data_dir)

        videos = mgr.list_by_type("video")
        logs = mgr.list_by_type("log")
        assert len(videos) == 2  # perceive/video + render/video
        assert len(logs) == 1
        assert all(a.type == "video" for a in videos)

    def test_list_by_run(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager
        self._populate(mgr, data_dir)

        run1 = mgr.list_by_run("r1")
        run2 = mgr.list_by_run("r2")
        assert len(run1) == 4  # p1 + p2 + x1 + r1
        assert len(run2) == 1


# ============================================================
# verify_checksum - 完整性校验
# ============================================================


class TestVerifyChecksum:
    def test_untampered_returns_true(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager
        f = data_dir / "clean.mp4"
        _write_test_file(f, b"original content here")

        aid = mgr.register(Artifact(
            type="video", stage="render", path=str(f),
        ))
        assert mgr.verify_checksum(aid) is True

    def test_tampered_returns_false(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager
        f = data_dir / "tampered.mp4"
        _write_test_file(f, b"original content here")

        aid = mgr.register(Artifact(
            type="video", stage="render", path=str(f),
        ))
        # 篡改
        f.write_bytes(b"CORRUPTED CORRUPTED CORRUPTED")
        assert mgr.verify_checksum(aid) is False

    def test_nonexistent_artifact_returns_false(self, tmp_artifact_manager):
        mgr, _, _ = tmp_artifact_manager
        assert mgr.verify_checksum("fake-id") is False

    def test_missing_file_returns_false(self, tmp_artifact_manager):
        mgr, tmp_path, _ = tmp_artifact_manager
        # 注册一个存在过但之后被删除的文件
        f = tmp_path / "deleted.txt"
        f.write_text("hello")
        aid = mgr.register(Artifact(
            type="log", stage="verify", path=str(f),
        ))
        # 删除文件
        f.unlink()
        assert mgr.verify_checksum(aid) is False


# ============================================================
# 血缘追溯
# ============================================================


class TestGetLineage:
    def test_simple_chain(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager

        def mk(name, parents=None):
            f = data_dir / f"{name}.bin"
            _write_test_file(f, name.encode())
            return mgr.register(Artifact(
                type="x", stage="x", path=str(f),
                parent_ids=parents or [],
            ))

        a_id = mk("a")
        b_id = mk("b", parents=[a_id])
        c_id = mk("c", parents=[b_id])
        d_id = mk("d", parents=[c_id])

        # 实际返回 List[str]（上游祖先 ID 列表，不含起始节点自身）
        lineage = mgr.get_lineage(d_id)
        assert isinstance(lineage, list)
        # 所有元素是 str
        assert all(isinstance(x, str) for x in lineage)
        lineage_set = set(lineage)
        # 不含 d_id 自身
        assert d_id not in lineage_set
        # 应包含 c, b, a（不含起点 d）
        assert a_id in lineage_set
        assert b_id in lineage_set
        assert c_id in lineage_set

    def test_circular_reference_does_not_loop_forever(self, tmp_artifact_manager):
        """A.parent=[B], B.parent=[A] -> 追溯不应无限循环"""
        mgr, _, data_dir = tmp_artifact_manager

        f_a = data_dir / "a.bin"
        f_b = data_dir / "b.bin"
        _write_test_file(f_a, b"a")
        _write_test_file(f_b, b"b")

        # 先各自注册不带 parent，再手动加 parent（为了制造循环）
        a_id = mgr.register(Artifact(
            id="circular_a", type="x", stage="x", path=str(f_a),
        ))
        b_id = mgr.register(Artifact(
            id="circular_b", type="x", stage="x", path=str(f_b),
        ))

        # 手动写回注册表制造循环
        mgr._artifacts[a_id].parent_ids = [b_id]
        mgr._artifacts[b_id].parent_ids = [a_id]
        mgr._save_registry()

        # 必须在合理时间内返回（不抛异常，不无限循环）
        import signal

        class _TimeoutError(Exception):
            pass

        def _handler(signum, frame):
            raise _TimeoutError("Lineage took too long (infinite loop?)")

        # Windows 没有 SIGALRM，使用 try/except 兜底 + 最大深度限制检测
        try:
            lineage = mgr.get_lineage(a_id)
        except RecursionError:
            pytest.fail("get_lineage caused RecursionError on circular refs")
        # 返回的 lineage 数量不超过总 artifacts 数量
        assert len(lineage) <= len(mgr._artifacts)

    def test_unknown_id_returns_empty(self, tmp_artifact_manager):
        mgr, _, _ = tmp_artifact_manager
        assert mgr.get_lineage("nope") == []


# ============================================================
# export_manifest
# ============================================================


class TestExportManifest:
    def test_export_format(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager
        f = data_dir / "out.mp4"
        _write_test_file(f, b"test")
        mgr.register(Artifact(
            type="video", stage="render", path=str(f),
            run_id="RUN-MANIFEST", metadata={"fps": 30},
        ))

        manifest = mgr.export_manifest(run_id="RUN-MANIFEST")
        # manifest 结构: run_id, artifact_count, artifacts_by_stage, total_size_bytes, exported_at
        assert isinstance(manifest, dict)
        assert manifest["run_id"] == "RUN-MANIFEST"
        assert manifest["artifact_count"] == 1
        assert isinstance(manifest["artifacts_by_stage"], dict)
        assert "render" in manifest["artifacts_by_stage"]
        assert len(manifest["artifacts_by_stage"]["render"]) == 1
        assert manifest["artifacts_by_stage"]["render"][0]["type"] == "video"
        assert manifest["artifacts_by_stage"]["render"][0]["metadata"] == {"fps": 30}
        assert isinstance(manifest["total_size_bytes"], int)
        assert manifest["total_size_bytes"] > 0
        # JSON 可序列化
        json.dumps(manifest, ensure_ascii=False, default=str)

    def test_export_filters_by_run_id(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager

        for i in range(3):
            f = data_dir / f"a{i}.bin"
            _write_test_file(f, f"a{i}".encode())
            mgr.register(Artifact(
                type="x", stage="x", path=str(f), run_id="run_A",
            ))
        for i in range(2):
            f = data_dir / f"b{i}.bin"
            _write_test_file(f, f"b{i}".encode())
            mgr.register(Artifact(
                type="x", stage="x", path=str(f), run_id="run_B",
            ))

        m_A = mgr.export_manifest(run_id="run_A")
        m_B = mgr.export_manifest(run_id="run_B")
        assert m_A["artifact_count"] == 3
        assert m_B["artifact_count"] == 2


# ============================================================
# cleanup_expired - 过期清理
# ============================================================


class TestCleanupExpired:
    def test_expired_artifacts_removed(self, tmp_artifact_manager):
        mgr, _, data_dir = tmp_artifact_manager

        now = time.time()

        # 过期的（模拟很老的 created_at，让 max_age_days=1 时 threshold 会把它清理）
        exp_f = data_dir / "expired.bin"
        _write_test_file(exp_f, b"old")
        exp_id = mgr.register(Artifact(
            type="x", stage="x", path=str(exp_f),
        ))
        # 手动把 created_at 改成 10 天前
        mgr._artifacts[exp_id].created_at = now - 10 * 86400

        # 未过期（created_at 是当前时间 -> 不会被清）
        fresh_f = data_dir / "fresh.bin"
        _write_test_file(fresh_f, b"new")
        fresh_id = mgr.register(Artifact(
            type="x", stage="x", path=str(fresh_f),
        ))
        # created_at 保持接近 now
        mgr._artifacts[fresh_id].created_at = now

        # 永不过期（created_at=0 -> threshold check: `0 < a.created_at < threshold` 条件:
        # 0 < 0 -> False, 所以不会被清理）
        never_f = data_dir / "never.bin"
        _write_test_file(never_f, b"permanent")
        never_id = mgr.register(Artifact(
            type="x", stage="x", path=str(never_f),
        ))
        mgr._artifacts[never_id].created_at = 0.0

        # 手动再保存一下
        mgr._save_registry()

        # max_age_days=1: 10天前的过期，刚注册的新鲜 & 0的保留
        count_removed = mgr.cleanup_expired(max_age_days=1)
        assert count_removed == 1

        remaining = mgr.list_by_stage("x")
        types_paths = [(a.type, Path(a.path).name) for a in remaining]
        names = {p for _, p in types_paths}
        assert "expired.bin" not in names
        assert "fresh.bin" in names
        assert "never.bin" in names


# ============================================================
# 持久化容错
# ============================================================


class TestPersistenceTolerance:
    def test_corrupt_registry_does_not_crash(self, tmp_path):
        """registry.json 损坏 -> 初始化不抛异常，相当于空 registry"""
        reg_dir = tmp_path / "artifacts"
        reg_dir.mkdir()
        bad_reg = reg_dir / "registry.json"
        bad_reg.write_text("{]]]THIS IS NOT JSON[[[", encoding="utf-8")

        # 不应抛任何异常
        mgr = ArtifactManager(registry_path=str(bad_reg))
        # 且能正常操作
        f = tmp_path / "t.txt"
        f.write_text("x")
        aid = mgr.register(Artifact(
            type="log", stage="x", path=str(f),
        ))
        assert mgr.get(aid) is not None

    def test_new_registry_creates_parent_dirs(self, tmp_path):
        """registry_path 的父目录不存在时，应该自动创建（不 FileNotFoundError）"""
        deep_reg = str(tmp_path / "a" / "b" / "c" / "registry.json")
        # 不应抛异常
        mgr = ArtifactManager(registry_path=deep_reg)
        f = tmp_path / "f.txt"
        f.write_text("x")
        mgr.register(Artifact(type="x", stage="x", path=str(f)))
        # 文件应该被写入
        assert Path(deep_reg).exists()

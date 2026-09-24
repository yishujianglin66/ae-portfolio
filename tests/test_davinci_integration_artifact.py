# -*- coding: utf-8 -*-
"""DaVinci 集成：调色 artifact 与可执行探测层（2026-09-22）。

背景：`integrations/davinci_resolve_integration.py` 未覆盖 685 行（12.06%）。
真实调色需要 Resolve 在场，但**两层是可测的纯逻辑**，且都是跨工具互通的接口面：

  · `ColorGradeArtifact` —— color_grade.v1 标准调色描述（Resolve / FFmpeg / AE
    三方互通）。序列化契约一旦漂移，跨工具交接就静默出错，故锁死往返与默认值；
  · `_find_resolve_exe` —— 安装路径探测（两种常见目录布局）；
  · `_check_availability` —— 可用性判定与 fuscript 探测（Resolve 启动慢，
    实现刻意"先查文件存在性再试 --version"）。

本文件不触发真实 Resolve：`subprocess.run` 一律打桩。
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import integrations.davinci_resolve_integration as dri  # noqa: E402
from integrations.davinci_resolve_integration import (  # noqa: E402
    ColorGradeArtifact,
    ColorGradeNode,
    DavinciColorist,
    ResolveColorConfig,
)


# ---------------------------------------------------------------------------
# ColorGradeArtifact —— 跨工具互通的标准格式
# ---------------------------------------------------------------------------

class TestArtifactRoundTrip:
    def _artifact(self) -> ColorGradeArtifact:
        return ColorGradeArtifact(
            version="1.0",
            preset_name="电影暖光",              # 中文必须原样保留
            source="resolve",
            created_at="2026-09-22T10:00:00",
            nodes=[{"node_type": "primary",
                    "settings": {"lift": [0.1, 0.0, -0.1]}}],
            ffmpeg_filter="eq=saturation=1.2",
            metadata={"note": "暖调 + 冷阴影"},
        )

    def test_dict_roundtrip_preserves_fields(self):
        a = self._artifact()
        b = ColorGradeArtifact.from_dict(a.to_dict())
        assert b.preset_name == a.preset_name == "电影暖光"
        assert b.nodes == a.nodes and b.metadata == a.metadata
        assert b.source == "resolver" or b.source == "resolve"
        assert b.ffmpeg_filter == a.ffmpeg_filter

    def test_to_dict_has_contract_keys(self):
        d = self._artifact().to_dict()
        for k in ("version", "preset_name", "source", "created_at",
                  "nodes", "ffmpeg_filter", "metadata"):
            assert k in d, k

    def test_created_at_autofilled_when_empty(self):
        a = ColorGradeArtifact(preset_name="p")
        assert a.created_at == ""
        assert a.to_dict()["created_at"]           # 序列化时补时间戳

    def test_created_at_preserved_when_set(self):
        a = ColorGradeArtifact(created_at="2026-01-01T00:00:00")
        assert a.to_dict()["created_at"] == "2026-01-01T00:00:00"

    def test_json_keeps_unicode(self):
        """ensure_ascii=False：中文不得被转义成 \\uXXXX（可读性与外部工具兼容）。"""
        js = self._artifact().to_json()
        assert "电影暖光" in js
        assert "\\u" not in js

    def test_from_dict_tolerates_missing_keys(self):
        """旧版/手写 artifact 缺字段时必须取默认值，而不是 KeyError。"""
        a = ColorGradeArtifact.from_dict({})
        assert a.version == "1.0" and a.source == "auto"
        assert a.nodes == [] and a.metadata == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        a = self._artifact()
        p = tmp_path / "nested" / "grade.json"     # 父目录不存在 → 应自建
        saved = a.save(str(p))
        assert saved == str(p) and p.exists()
        b = ColorGradeArtifact.load(str(p))
        assert b.preset_name == a.preset_name and b.nodes == a.nodes
        assert json.loads(p.read_text(encoding="utf-8"))["version"] == "1.0"

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ColorGradeArtifact.load(str(tmp_path / "nope.json"))


class TestColorGradeNode:
    def test_defaults(self):
        n = ColorGradeNode()
        assert n.node_type == "primary" and n.name == "Node"
        assert n.settings == {} and n.enabled is True

    def test_settings_mutable_independent(self):
        """默认值不得共享同一个 dict（dataclass 陷阱）。"""
        a, b = ColorGradeNode(), ColorGradeNode()
        a.settings["contrast"] = 1.2
        assert b.settings == {}


# ---------------------------------------------------------------------------
# 可执行探测（不触发真实 Resolve）
# ---------------------------------------------------------------------------

class TestFindResolveExe:
    def _colorist_with_install(self, install: Path) -> DavinciColorist:
        """绕开 __init__ 的可用性探测，只装 config。"""
        c = object.__new__(DavinciColorist)
        c.config = ResolveColorConfig(install_path=str(install))
        return c

    def test_flat_layout(self, tmp_path):
        (tmp_path / "Resolve.exe").write_bytes(b"MZ")
        c = self._colorist_with_install(tmp_path)
        assert c._find_resolve_exe() == tmp_path / "Resolve.exe"

    def test_nested_layout(self, tmp_path):
        nested = tmp_path / "Resolve"
        nested.mkdir()
        (nested / "Resolve.exe").write_bytes(b"MZ")
        c = self._colorist_with_install(tmp_path)
        assert c._find_resolve_exe() == nested / "Resolve.exe"

    def test_missing_falls_back_to_discovery(self, tmp_path, monkeypatch):
        """配置目录为空时回退全局发现器；发现器也给不出答案才返回 None。

        打桩全局发现器而非依赖本机是否装了 Resolve，测试结论与机器无关。
        """
        monkeypatch.setattr(dri, "find_resolve_exe", lambda: None)
        c = self._colorist_with_install(tmp_path)
        assert c._find_resolve_exe() is None

    def test_stale_install_path_recovers_via_discovery(self, tmp_path, monkeypatch):
        """配置指向过期目录时，回退发现器恢复出真实安装路径。

        这是 2026-09-23 实测暴露的缺陷：旧默认 D:\\DaVinci Resolve 不存在，
        而真实安装在 D:\\app，已安装的 Resolve Studio 被判成未安装。
        """
        discovered = tmp_path / "discovered" / "Resolve.exe"
        discovered.parent.mkdir()
        discovered.write_bytes(b"MZ")
        monkeypatch.setattr(dri, "find_resolve_exe", lambda: discovered)
        stale = tmp_path / "stale"
        stale.mkdir()
        c = self._colorist_with_install(stale)
        assert c._find_resolve_exe() == discovered

    def test_prefers_flat_layout_when_both_exist(self, tmp_path):
        (tmp_path / "Resolve.exe").write_bytes(b"MZ")
        nested = tmp_path / "Resolve"
        nested.mkdir()
        (nested / "Resolve.exe").write_bytes(b"MZ")
        c = self._colorist_with_install(tmp_path)
        assert c._find_resolve_exe() == tmp_path / "Resolve.exe"


class TestCheckAvailability:
    def _colorist(self, exe: Path | None) -> DavinciColorist:
        c = object.__new__(DavinciColorist)
        c.config = ResolveColorConfig()
        c._exe_path = exe
        c._fuscript_available = False
        return c

    def test_false_when_exe_absent(self):
        assert self._colorist(None)._check_availability() is False

    def test_false_when_exe_missing_on_disk(self, tmp_path):
        assert self._colorist(tmp_path / "gone.exe")._check_availability() is False

    def test_detects_fuscript_next_to_exe(self, tmp_path, monkeypatch):
        exe = tmp_path / "Resolve.exe"
        exe.write_bytes(b"MZ")
        (tmp_path / "fuscript.exe").write_bytes(b"MZ")

        class _R:
            returncode = 0
            stdout = ""
            stderr = ""

        monkeypatch.setattr(dri.subprocess, "run", lambda *a, **k: _R())
        c = self._colorist(exe)
        assert c._check_availability() is True
        assert c._fuscript_available is True

    def test_version_banner_counts_as_available(self, tmp_path, monkeypatch):
        """实现刻意兼容"退出码非 0 但横幅含 DaVinci"的情况。"""
        exe = tmp_path / "Resolve.exe"
        exe.write_bytes(b"MZ")

        class _R:
            returncode = 1
            stdout = "DaVinci Resolve Studio 20.0"
            stderr = ""

        monkeypatch.setattr(dri.subprocess, "run", lambda *a, **k: _R())
        assert self._colorist(exe)._check_availability() is True

    def test_unexpected_output_means_unavailable(self, tmp_path, monkeypatch):
        exe = tmp_path / "Resolve.exe"
        exe.write_bytes(b"MZ")

        class _R:
            returncode = 1
            stdout = ""
            stderr = "unknown error"

        monkeypatch.setattr(dri.subprocess, "run", lambda *a, **k: _R())
        assert self._colorist(exe)._check_availability() is False

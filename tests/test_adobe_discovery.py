"""tests/test_adobe_discovery.py — Adobe 安装位置统一发现器测试

验证修复：已安装但未运行的 Adobe 产品不再被误报为"未安装"。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import adobe_discovery
from core.adobe_discovery import (
    ADOBE_PRODUCTS,
    clear_cache,
    find_adobe_exe,
    is_adobe_installed,
    scan_all_adobe,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


class TestEnvOverride:
    def test_env_var_points_to_existing_exe(self, tmp_path: Path, monkeypatch):
        fake_exe = tmp_path / "Adobe Media Encoder.exe"
        fake_exe.write_bytes(b"MZ")
        monkeypatch.setenv("AEKV_ADOBE_AME_PATH", str(fake_exe))
        assert find_adobe_exe("media_encoder", force_check=True) == fake_exe
        assert is_adobe_installed("media_encoder")

    def test_env_var_invalid_falls_through(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("AEKV_ADOBE_AME_PATH", str(tmp_path / "not_exist.exe"))
        monkeypatch.setattr(adobe_discovery, "_resolve_shortcut_targets", lambda kw: [])
        monkeypatch.setattr(adobe_discovery, "_search_registry", lambda kw, exe: None)
        monkeypatch.setitem(ADOBE_PRODUCTS["media_encoder"], "candidate_dirs", [])
        assert find_adobe_exe("media_encoder", force_check=True) is None


class TestCandidatePaths:
    def test_candidate_dir_hit(self, tmp_path: Path, monkeypatch):
        exe_name = str(ADOBE_PRODUCTS["media_encoder"]["exe_name"])
        fake_exe = tmp_path / exe_name
        fake_exe.write_bytes(b"MZ")
        monkeypatch.setitem(
            ADOBE_PRODUCTS["media_encoder"], "candidate_dirs", [str(tmp_path)]
        )
        assert find_adobe_exe("media_encoder", force_check=True) == fake_exe

    def test_cache_serves_repeat_calls(self, tmp_path: Path, monkeypatch):
        exe_name = str(ADOBE_PRODUCTS["premiere"]["exe_name"])
        fake_exe = tmp_path / exe_name
        fake_exe.write_bytes(b"MZ")
        monkeypatch.setitem(ADOBE_PRODUCTS["premiere"], "candidate_dirs", [str(tmp_path)])
        first = find_adobe_exe("premiere", force_check=True)
        # 删掉候选后仍应命中缓存
        monkeypatch.setitem(ADOBE_PRODUCTS["premiere"], "candidate_dirs", [])
        assert find_adobe_exe("premiere") == first


class TestShortcutFallback:
    def test_shortcut_target_used_when_candidates_miss(self, tmp_path: Path, monkeypatch):
        exe_name = str(ADOBE_PRODUCTS["after_effects"]["exe_name"])
        fake_exe = tmp_path / exe_name
        fake_exe.write_bytes(b"MZ")
        monkeypatch.setitem(ADOBE_PRODUCTS["after_effects"], "candidate_dirs", [])
        monkeypatch.setattr(
            adobe_discovery, "_resolve_shortcut_targets", lambda kw: [fake_exe]
        )
        assert find_adobe_exe("after_effects", force_check=True) == fake_exe


class TestRegistryFallback:
    def test_registry_hit(self, tmp_path: Path, monkeypatch):
        exe_name = str(ADOBE_PRODUCTS["photoshop"]["exe_name"])
        fake_exe = tmp_path / exe_name
        fake_exe.write_bytes(b"MZ")
        monkeypatch.setitem(ADOBE_PRODUCTS["photoshop"], "candidate_dirs", [])
        monkeypatch.setattr(adobe_discovery, "_resolve_shortcut_targets", lambda kw: [])
        monkeypatch.setattr(
            adobe_discovery, "_search_registry", lambda kw, exe: fake_exe
        )
        assert find_adobe_exe("photoshop", force_check=True) == fake_exe


class TestScanAll:
    def test_scan_all_returns_all_products(self):
        report = scan_all_adobe()
        assert set(report) == set(ADOBE_PRODUCTS)
        for entry in report.values():
            assert set(entry) == {"installed", "exe_path"}

    def test_unknown_product_raises(self):
        with pytest.raises(ValueError):
            find_adobe_exe("not_a_product")

# -*- coding: utf-8 -*-
"""core.resolve_discovery 契约测试（2026-09-23）。

背景：Resolve 路径发现曾有 6~7 份各自独立的实现，多数硬编码了本机不存在的路径，
结果是"已安装 Resolve Studio 21"被多处误报成未安装：
  · ai/resolve_executor.py 的 3 个候选路径全部不存在，且失败后静默返回空串；
  · integrations/davinci_resolve_integration.py 默认 D:\\DaVinci Resolve（不存在）；
  · 同文件另有两处自持候选表（一处列出 C:/D:/E:/F:，不含真实安装目录 D:\\app）。

本模块是唯一权威来源。测试全部打桩，不要求本机装 Resolve，也不启动任何进程。
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import core.resolve_discovery as rd  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_discovery(monkeypatch):
    """隔离"运行环境相关"的发现来源，使本文件的断言与本机装了什么无关。

    背景（全量套件实测）：本机可解析的 puppet settings 会把 davinci_path 解析成
    `D:\\app`，在发现链里**抢在候选目录之前**命中，于是我这几条"候选阶段"用例
    单独跑全绿、进全量套件 7 条全红 —— 典型的顺序/环境耦合。
    另：本机还存在系统级 RESOLVE_HOME 残留值，必须清掉。

    env 覆盖那一级**不隔离**（用例用 monkeypatch.setenv / delenv 自行控制）。
    """
    monkeypatch.delenv("AEKV_RESOLVE_HOME", raising=False)
    monkeypatch.delenv("AEKV_RESOLVE_FUSCRIPT", raising=False)
    monkeypatch.setattr(rd, "_settings_home", lambda: None)
    monkeypatch.setattr(rd, "_search_registry", lambda: None)
    monkeypatch.setattr(rd, "_process_home", lambda: None)
    rd.clear_cache()
    yield
    rd.clear_cache()


def _make_install(root: Path, exe_name: str = "Resolve.exe") -> Path:
    """造一个最小安装目录：Resolve.exe 与 fuscript.exe 同级（本机实测布局）"""
    root.mkdir(parents=True, exist_ok=True)
    (root / exe_name).write_bytes(b"MZ")
    (root / "fuscript.exe").write_bytes(b"MZ")
    return root


# ---------------------------------------------------------------------------
# 候选目录优先级
# ---------------------------------------------------------------------------

class TestCandidateHomes:
    def test_env_override_wins(self, tmp_path, monkeypatch):
        home = _make_install(tmp_path / "custom")
        monkeypatch.setenv("AEKV_RESOLVE_HOME", str(home))
        assert rd.resolve_home(force_check=True) == home

    def test_nonexistent_env_override_is_ignored(self, tmp_path, monkeypatch):
        """环境变量指向不存在的目录时不得采信（本机 RESOLVE_HOME 就是这种遗留值）"""
        monkeypatch.setenv("AEKV_RESOLVE_HOME", str(tmp_path / "nope"))
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(tmp_path / "real"),))
        home = _make_install(tmp_path / "real")
        assert rd.resolve_home(force_check=True) == home

    def test_fuscript_env_override_uses_its_parent(self, tmp_path, monkeypatch):
        home = _make_install(tmp_path / "viacustom")
        monkeypatch.setenv("AEKV_RESOLVE_FUSCRIPT", str(home / "fuscript.exe"))
        assert rd.resolve_home(force_check=True) == home

    def test_candidate_home_without_resolve_exe_is_skipped(self, tmp_path, monkeypatch):
        """目录存在但没有 Resolve.exe 不算命中"""
        empty = tmp_path / "empty"
        empty.mkdir()
        real = _make_install(tmp_path / "real")
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(empty), str(real)))
        assert rd.resolve_home(force_check=True) == real

    def test_not_found_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(tmp_path / "nothing"),))
        monkeypatch.setattr(rd, "_search_registry", lambda: None)
        monkeypatch.setattr(rd, "_process_home", lambda: None)
        monkeypatch.setattr(rd, "_settings_home", lambda: None)
        monkeypatch.setattr(rd, "_env_home", lambda: None)
        assert rd.resolve_home(force_check=True) is None

    def test_exe_path_in_candidate_list_is_normalized(self, tmp_path, monkeypatch):
        """候选写成 exe 全路径时归一到其父目录"""
        home = _make_install(tmp_path / "real")
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(home / "Resolve.exe"),))
        assert rd.resolve_home(force_check=True) == home

    def test_env_beats_candidates(self, tmp_path, monkeypatch):
        """锁住发现顺序第 1 级：环境变量优先于候选目录"""
        via_env = _make_install(tmp_path / "via_env")
        via_cand = _make_install(tmp_path / "via_cand")
        monkeypatch.setenv("AEKV_RESOLVE_HOME", str(via_env))
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(via_cand),))
        assert rd.resolve_home(force_check=True) == via_env

    def test_settings_beats_candidates(self, tmp_path, monkeypatch):
        """锁住发现顺序第 2 级：settings 优先于候选目录。

        这一条是**回归锁**：全量套件里本机 settings 命中 D:\\app 抢在候选之前，
        曾让 7 条候选阶段用例全红。顺序本身是设计意图，故显式断言而非靠环境偶然。
        """
        via_settings = _make_install(tmp_path / "via_settings")
        via_cand = _make_install(tmp_path / "via_cand")
        monkeypatch.setattr(rd, "_settings_home", lambda: via_settings)
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(via_cand),))
        assert rd.resolve_home(force_check=True) == via_settings

    def test_registry_beats_process_probe(self, tmp_path, monkeypatch):
        """锁住发现顺序末两级：注册表优先于活进程反查"""
        via_registry = _make_install(tmp_path / "via_registry")
        via_process = _make_install(tmp_path / "via_process")
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(tmp_path / "nothing"),))
        monkeypatch.setattr(rd, "_search_registry", lambda: via_registry)
        monkeypatch.setattr(rd, "_process_home", lambda: via_process)
        assert rd.resolve_home(force_check=True) == via_registry


# ---------------------------------------------------------------------------
# exe 定位
# ---------------------------------------------------------------------------

class TestExeResolution:
    def test_find_resolve_exe(self, tmp_path, monkeypatch):
        home = _make_install(tmp_path / "real")
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(home),))
        assert rd.find_resolve_exe(force_check=True) == home / "Resolve.exe"

    def test_find_fuscript_is_sibling_of_resolve(self, tmp_path, monkeypatch):
        """fuscript.exe 与 Resolve.exe 同目录，故复用 resolve_home 而非单独硬编码"""
        home = _make_install(tmp_path / "real")
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(home),))
        assert rd.find_fuscript_exe(force_check=True) == home / "fuscript.exe"

    def test_fuscript_missing_when_home_has_only_resolve(self, tmp_path, monkeypatch):
        home = tmp_path / "dieresis"
        home.mkdir()
        (home / "Resolve.exe").write_bytes(b"MZ")
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(home),))
        assert rd.find_fuscript_exe(force_check=True) is None

    def test_cache_avoids_rescan(self, tmp_path, monkeypatch):
        home = _make_install(tmp_path / "real")
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(home),))
        calls = []

        def _counting():
            calls.append(1)
            return None

        monkeypatch.setattr(rd, "_search_registry", _counting)
        assert rd.resolve_home(force_check=True) == home
        first = len(calls)
        rd.resolve_home()  # 命中缓存，不再走到注册表
        assert len(calls) == first


# ---------------------------------------------------------------------------
# 启动校验
# ---------------------------------------------------------------------------

class TestLaunchGuards:
    def test_launch_refuses_when_not_found(self, monkeypatch):
        monkeypatch.setattr(rd, "find_resolve_exe", lambda force_check=False: None)
        assert rd.launch_resolve(wait_s=0) is False

    def test_launch_refuses_unexpected_exe_name(self, tmp_path, monkeypatch):
        """文件名不是 Resolve.exe 一律拒启动"""
        other = tmp_path / "evil.exe"
        other.write_bytes(b"MZ")
        monkeypatch.setattr(rd, "find_resolve_exe", lambda force_check=False: other)
        monkeypatch.setattr(rd, "resolve_home", lambda force_check=False: tmp_path)
        assert rd.launch_resolve(wait_s=0) is False

    def test_launch_refuses_exe_outside_discovered_home(self, tmp_path, monkeypatch):
        """Resolve.exe 不在已发现安装目录内 → 拒绝启动"""
        outside = tmp_path / "other" / "Resolve.exe"
        outside.parent.mkdir()
        outside.write_bytes(b"MZ")
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(rd, "find_resolve_exe", lambda force_check=False: outside)
        monkeypatch.setattr(rd, "resolve_home", lambda force_check=False: home)
        assert rd.launch_resolve(wait_s=0) is False


# ---------------------------------------------------------------------------
# 能力探针
# ---------------------------------------------------------------------------

class TestCapabilityProbe:
    def test_schema_and_unavailable_when_fuscript_missing(self, monkeypatch):
        monkeypatch.setattr(rd, "find_fuscript_exe", lambda force_check=False: None)
        monkeypatch.setattr(rd, "find_resolve_exe", lambda force_check=False: None)
        report = rd.capability_probe()
        for key in (
            "installed", "headless_ok", "api_reachable", "resolve_exe",
            "fuscript_exe", "resolve_running", "product", "version",
            "project_count", "detail",
        ):
            assert key in report, f"缺少字段 {key}"
        assert report["installed"] is False
        assert report["headless_ok"] is False
        assert report["api_reachable"] is False
        assert "fuscript" in str(report["detail"])

    def test_headless_ok_but_api_not_reachable_when_resolve_not_running(
        self, tmp_path, monkeypatch
    ):
        """核心事实：fuscript 可无头执行，但 Resolve() 只在活实例存在时返回句柄。

        用假 fuscript 回放真机观测到的输出（resolve_is_nil=true）。
        """
        fake = tmp_path / "fuscript.exe"
        fake.write_bytes(b"MZ")
        monkeypatch.setattr(rd, "find_fuscript_exe", lambda force_check=False: fake)
        monkeypatch.setattr(rd, "find_resolve_exe", lambda force_check=False: None)
        monkeypatch.setattr(rd, "is_process_running", lambda: False)

        class _Result:
            returncode = 0
            stdout = "resolve_is_nil=true\n"

        monkeypatch.setattr(rd.subprocess, "run", lambda *a, **k: _Result())
        report = rd.capability_probe()
        assert report["installed"] is True
        assert report["headless_ok"] is True
        assert report["api_reachable"] is False
        assert "未运行" in str(report["detail"])

    def test_api_reachable_path_parses_evidence(self, tmp_path, monkeypatch):
        """Resolve 运行时的真机输出形状：product/version/project_count 被解析出来"""
        fake = tmp_path / "fuscript.exe"
        fake.write_bytes(b"MZ")
        monkeypatch.setattr(rd, "find_fuscript_exe", lambda force_check=False: fake)
        monkeypatch.setattr(rd, "find_resolve_exe", lambda force_check=False: None)
        monkeypatch.setattr(rd, "is_process_running", lambda: True)

        class _Result:
            returncode = 0
            stdout = (
                "resolve_is_nil=false\n"
                "product=DaVinci Resolve Studio\n"
                "version=21.0.3.7\n"
                "project_count=29\n"
            )

        monkeypatch.setattr(rd.subprocess, "run", lambda *a, **k: _Result())
        report = rd.capability_probe()
        assert report["api_reachable"] is True
        assert report["product"] == "DaVinci Resolve Studio"
        assert report["version"] == "21.0.3.7"
        assert report["project_count"] == 29
        assert report["detail"] == "API 可达"

    def test_nonzero_exit_is_reported(self, tmp_path, monkeypatch):
        fake = tmp_path / "fuscript.exe"
        fake.write_bytes(b"MZ")
        monkeypatch.setattr(rd, "find_fuscript_exe", lambda force_check=False: fake)
        monkeypatch.setattr(rd, "find_resolve_exe", lambda force_check=False: None)
        monkeypatch.setattr(rd, "is_process_running", lambda: False)

        class _Result:
            returncode = 1
            stdout = "boom"

        monkeypatch.setattr(rd.subprocess, "run", lambda *a, **k: _Result())
        report = rd.capability_probe()
        assert report["headless_ok"] is False
        assert "退出码 1" in str(report["detail"])

    def test_timeout_is_reported(self, tmp_path, monkeypatch):
        fake = tmp_path / "fuscript.exe"
        fake.write_bytes(b"MZ")
        monkeypatch.setattr(rd, "find_fuscript_exe", lambda force_check=False: fake)
        monkeypatch.setattr(rd, "find_resolve_exe", lambda force_check=False: None)
        monkeypatch.setattr(rd, "is_process_running", lambda: False)

        def _boom(*a, **k):
            raise rd.subprocess.TimeoutExpired(cmd="fuscript", timeout=1)

        monkeypatch.setattr(rd.subprocess, "run", _boom)
        report = rd.capability_probe()
        assert report["headless_ok"] is False
        assert "超时" in str(report["detail"])


# ---------------------------------------------------------------------------
# 调用点收敛：同一工具不得再有第二份路径实现
# ---------------------------------------------------------------------------

class TestCallSiteConvergence:
    """5 个模块此前各自持有一份 Resolve 路径实现，多数硬编码本机不存在的路径。
    这些断言锁死"所有调用点解析到同一个安装目录"这一契约。"""

    def test_davinci_fuscript_color_engine_uses_discovery(self, tmp_path, monkeypatch):
        """resolve_home 省略时取发现结果；未找到时不得退化成 Path('.')。

        旧实现 `Path(resolve_home or "D:\\app") / "fuscript.exe"` 在未找到时
        若回退成 `Path(".")`，"目录存在"会让可用性判定误报为 True。
        """
        import integrations.davinci_fuscript as df

        home = _make_install(tmp_path / "app")
        monkeypatch.setattr(rd, "CANDIDATE_HOMES", (str(home),))
        rd.clear_cache()
        monkeypatch.setattr(df, "find_fuscript_exe", lambda: home / "fuscript.exe")
        engine = df.ResolveColorEngine()
        assert engine.fuscript_path == home / "fuscript.exe"

    def test_color_engine_missing_is_not_falsely_available(self, monkeypatch):
        import integrations.davinci_fuscript as df

        monkeypatch.setattr(df, "find_fuscript_exe", lambda: None)
        engine = df.ResolveColorEngine()
        assert engine.fuscript_path is None
        assert engine._engine.available is False

    def test_unified_pipeline_default_is_discovery_backed(self):
        """UnifiedVideoPipeline() 的旧默认 r"D:\\DaVinci Resolve" 使 Resolve 调色
        步骤永远降级；默认必须是 None（交给发现器）。"""
        import inspect

        import integrations.unified_video_pipeline as uvp

        sig = inspect.signature(uvp.UnifiedVideoPipeline.__init__)
        assert sig.parameters["resolve_home"].default is None


# ---------------------------------------------------------------------------
# 进程探测的可移植性
# ---------------------------------------------------------------------------

class TestProcessProbe:
    def test_non_windows_returns_false(self, monkeypatch):
        monkeypatch.setattr(rd.os, "name", "posix")
        assert rd.is_process_running() is False

    def test_decode_error_does_not_mask_running_process(self, monkeypatch):
        """中文 Windows 下 tasklist 按 OEM 代码页输出：严格 utf-8 解码会在读取线程
        抛 UnicodeDecodeError 并吞掉 stdout，导致在跑的进程被判成未运行。
        这里断言我们显式传了 errors='replace'，且 ASCII 进程名仍能匹配。"""
        captured = {}

        class _Result:
            stdout = "Resolve.exe                  19624 Console                    1  2,307,856 K"

        def _run(cmd, **kwargs):
            captured.update(kwargs)
            return _Result()

        monkeypatch.setattr(rd.os, "name", "nt")
        monkeypatch.setattr(rd.subprocess, "run", _run)
        assert rd.is_process_running() is True
        assert captured.get("errors") == "replace"
        assert captured.get("encoding") == "utf-8"

    def test_process_probe_is_ttl_cached(self, monkeypatch):
        """构造热路径会反复问"在跑吗"，每次起一个 tasklist 子进程太贵；
        TTL 内复用结果，force_check 可穿透。"""
        calls = []

        class _Result:
            stdout = "Resolve.exe  1 Console  1  100 K"

        def _run(cmd, **kwargs):
            calls.append(1)
            return _Result()

        monkeypatch.setattr(rd.os, "name", "nt")
        monkeypatch.setattr(rd.subprocess, "run", _run)
        assert rd.is_process_running() is True
        assert rd.is_process_running() is True
        assert len(calls) == 1, "TTL 内应复用缓存"
        assert rd.is_process_running(force_check=True) is True
        assert len(calls) == 2, "force_check 应穿透缓存"

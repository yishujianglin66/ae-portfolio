"""
core/resolve_discovery.py — DaVinci Resolve 安装位置与能力统一发现器
=====================================================================

修复历史缺陷：Resolve 路径发现存在 4 份互不一致的实现
（ai/resolve_executor.py、integrations/resolve_engine.py、
integrations/davinci_resolve_integration.py、pipeline/flagship_runner.py）。
其中 resolve_executor 的 3 个候选路径在本机全部不存在，且失败后静默返回空串，
导致"已安装 Resolve Studio 21"被误报为未找到。

本模块是唯一权威来源。发现顺序（与 core/adobe_discovery.py 对齐）：
    1. 环境变量 AEKV_RESOLVE_HOME（安装目录）/ AEKV_RESOLVE_FUSCRIPT（exe 全路径）
    2. settings 中央配置 davinci_path
    3. 已知安装候选目录（含 D:\\app 这类自定义安装目录）
    4. Windows 注册表 Uninstall 条目（DisplayName 匹配 Blackmagic）
    5. 活进程反查：Resolve.exe 正在运行时取其镜像路径

fuscript.exe 与 Resolve.exe 同目录（本机实测 D:\\app\\ 下同级），
故 fuscript 定位复用 resolve_home()，不再各处单独硬编码。

能力事实（2026-09-23 本机实测，Resolve Studio 21.0.3.7）：
    - fuscript.exe 可完全无头执行 Lua（退出码 0、产物落盘）；
    - 但脚本内 Resolve() 仅在 Resolve.exe 运行时返回句柄，未运行时返回 nil。
    即该 API 是【对活实例的远程控制】，不能无头拉起。capability_probe() 据此判断。

结果进程内缓存，重复调用零成本。
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

from loguru import logger

RESOLVE_EXE_NAME = "Resolve.exe"
FUSCRIPT_EXE_NAME = "fuscript.exe"

# 已知安装候选目录（含本机自定义安装目录 D:\app；见模块 docstring）
CANDIDATE_HOMES: tuple[str, ...] = (
    r"D:\app",
    r"D:\DaVinci Resolve",
    r"C:\Program Files\Blackmagic Design\DaVinci Resolve",
    r"C:\Program Files (x86)\Blackmagic Design\DaVinci Resolve",
    r"D:\Program Files\Blackmagic Design\DaVinci Resolve",
    r"D:\Blackmagic Design\DaVinci Resolve",
    r"C:\Blackmagic Design\DaVinci Resolve",
)

_cache: dict[str, Path | None] = {}


def _env_home() -> Path | None:
    """环境变量覆盖：AEKV_RESOLVE_HOME 目录 / AEKV_RESOLVE_FUSCRIPT exe 全路径"""
    exe_override = os.environ.get("AEKV_RESOLVE_FUSCRIPT", "").strip()
    if exe_override:
        p = Path(exe_override)
        if p.suffix.lower() == ".exe" and p.exists():
            return p.parent
        logger.warning(f"[ResolveDiscovery] AEKV_RESOLVE_FUSCRIPT 路径不存在: {exe_override}")
    home_override = os.environ.get("AEKV_RESOLVE_HOME", "").strip()
    if home_override:
        p = Path(home_override)
        if p.exists():
            return p
        logger.warning(f"[ResolveDiscovery] AEKV_RESOLVE_HOME 路径不存在: {home_override}")
    return None


def _settings_home() -> Path | None:
    """settings 中央配置（puppet_automation.src.config.settings.davinci_path）"""
    try:
        from puppet_automation.src.config.settings import get_settings

        p = Path(get_settings().davinci_path)
        if p.exists():
            return p
    except Exception:
        pass
    return None


def _process_home() -> Path | None:
    """活进程反查：Resolve.exe 在运行时取其镜像路径所在目录"""
    if os.name != "nt":
        return None
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Process -Name Resolve -ErrorAction SilentlyContinue | "
                "Select-Object -First 1 -ExpandProperty Path",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return None
    line = (proc.stdout or "").strip().strip('"')
    if not line:
        return None
    p = Path(line)
    if p.exists():
        return p.parent
    return None


def _search_registry() -> Path | None:
    """注册表 Uninstall 条目查找（DisplayIcon / InstallLocation / InstallSource）"""
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    for hive, keypath in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ):
        try:
            with winreg.OpenKey(hive, keypath) as key:
                n_sub = winreg.QueryInfoKey(key)[0]
        except OSError:
            continue
        for i in range(n_sub):
            try:
                name = winreg.EnumKey(key, i)
                with winreg.OpenKey(hive, f"{keypath}\\{name}") as sub:
                    try:
                        dn, _ = winreg.QueryValueEx(sub, "DisplayName")
                    except OSError:
                        continue
                    if "blackmagic" not in str(dn).lower() and "davinci" not in str(dn).lower():
                        continue
                    for field in ("DisplayIcon", "InstallLocation", "InstallSource"):
                        try:
                            val, _ = winreg.QueryValueEx(sub, field)
                        except OSError:
                            continue
                        p = Path(str(val).strip().split(",")[0].strip('"'))
                        if str(p) in ("", "."):
                            continue
                        if p.suffix.lower() == ".exe" and p.exists():
                            return p.parent
                        if (p / RESOLVE_EXE_NAME).exists():
                            return p
            except OSError:
                continue
    return None


def resolve_home(force_check: bool = False) -> Path | None:
    """发现 Resolve 安装目录（未安装返回 None）。

    顺序：环境变量 → settings → 候选目录 → 注册表 → 活进程。
    活进程放最后：它证明"确实在用"，但安装检测不应依赖是否正在运行。
    """
    if not force_check and "home" in _cache:
        return _cache["home"]

    for label, probe in (
        ("环境变量", _env_home),
        ("settings", _settings_home),
    ):
        hit = probe()
        if hit is not None:
            logger.info(f"[ResolveDiscovery] Resolve 安装目录已定位（{label}）: {hit}")
            _cache["home"] = hit
            return hit

    for d in CANDIDATE_HOMES:
        p = Path(d)
        # 候选可写成目录，也可误写成 exe 全路径；两者都归一到目录
        if p.suffix.lower() == ".exe":
            p = p.parent
        if (p / RESOLVE_EXE_NAME).exists():
            logger.info(f"[ResolveDiscovery] Resolve 安装目录已定位（候选目录）: {p}")
            _cache["home"] = p
            return p

    for label, probe in (("注册表", _search_registry), ("活进程", _process_home)):
        hit = probe()
        if hit is not None:
            logger.info(f"[ResolveDiscovery] Resolve 安装目录已定位（{label}）: {hit}")
            _cache["home"] = hit
            return hit

    logger.warning(
        "[ResolveDiscovery] Resolve 未找到（环境变量/settings/候选目录/注册表/活进程均未命中）；"
        "可设 AEKV_RESOLVE_HOME 指向安装目录"
    )
    _cache["home"] = None
    return None


def find_resolve_exe(force_check: bool = False) -> Path | None:
    """发现 Resolve.exe 全路径（未安装返回 None）"""
    if not force_check and "resolve_exe" in _cache:
        return _cache["resolve_exe"]
    home = resolve_home(force_check=force_check)
    exe = (home / RESOLVE_EXE_NAME) if home is not None else None
    exe = exe if exe is not None and exe.exists() else None
    _cache["resolve_exe"] = exe
    return exe


def find_fuscript_exe(force_check: bool = False) -> Path | None:
    """发现 fuscript.exe 全路径（与 Resolve.exe 同目录）"""
    if not force_check and "fuscript_exe" in _cache:
        return _cache["fuscript_exe"]
    home = resolve_home(force_check=force_check)
    exe = (home / FUSCRIPT_EXE_NAME) if home is not None else None
    exe = exe if exe is not None and exe.exists() else None
    if exe is None:
        logger.warning("[ResolveDiscovery] fuscript.exe 未找到（通常与 Resolve.exe 同目录）")
    _cache["fuscript_exe"] = exe
    return exe


_PROCESS_CACHE_TTL_S = 5.0
_process_cache: dict[str, tuple[float, bool]] = {}


def is_process_running(force_check: bool = False) -> bool:
    """Resolve.exe 是否正在运行（进程探测，非安装检测）。

    结果按短 TTL（5s）缓存：构造函数等热路径会反复问这个问题，而每次都要起一个
    tasklist 子进程；TTL 保证既不在紧循环里重复付代价，又不会把"已退出"缓存太久。
    """
    if os.name != "nt":
        return False
    now = time.monotonic()
    if not force_check and "running" in _process_cache:
        cached_at, cached = _process_cache["running"]
        if now - cached_at < _PROCESS_CACHE_TTL_S:
            return cached
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"],
            capture_output=True,
            text=True,
            timeout=15,
            # 中文 Windows 下 tasklist 按 OEM 代码页输出，严格 utf-8 解码会在读取线程
            # 抛 UnicodeDecodeError 并吞掉全部 stdout，导致在跑的进程被误判为未运行
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        _process_cache["running"] = (now, False)
        return False
    running = RESOLVE_EXE_NAME in (result.stdout or "")
    _process_cache["running"] = (now, running)
    return running


def launch_resolve(wait_s: int = 5) -> bool:
    """启动 Resolve.exe。

    启动前校验：文件名必须是 Resolve.exe，且位于已发现的安装目录内，否则拒绝启动。
    经 Windows ShellExecute（os.startfile）拉起，不经过 shell 命令行。
    """
    exe = find_resolve_exe()
    if exe is None:
        logger.warning("[ResolveDiscovery] 未找到 Resolve.exe，无法启动")
        return False
    if exe.name != RESOLVE_EXE_NAME:
        logger.warning(f"[ResolveDiscovery] 非预期可执行文件名，拒绝启动: {exe.name}")
        return False
    home = resolve_home()
    if home is None or exe.parent != home:
        logger.warning(f"[ResolveDiscovery] 可执行文件不在已发现安装目录内，拒绝启动: {exe}")
        return False
    if not hasattr(os, "startfile"):
        logger.warning("[ResolveDiscovery] 当前平台不支持自动启动，请手动打开 Resolve")
        return False
    os.startfile(str(exe))  # noqa: S606 — 路径已校验为安装目录内的 Resolve.exe
    time.sleep(wait_s)
    return True


# 能力探针：fuscript 无头执行的最小 Lua，只回答"API 句柄是否可达"
_PROBE_LUA = """
local out = {}
local resolve = Resolve()
out[#out + 1] = "resolve_is_nil=" .. tostring(resolve == nil)
if resolve ~= nil then
    local ok, v = pcall(function() return resolve:GetProductName() end)
    out[#out + 1] = "product=" .. tostring(v)
    local ok2, v2 = pcall(function() return resolve:GetVersionString() end)
    out[#out + 1] = "version=" .. tostring(v2)
    local ok3, pm = pcall(function() return resolve:GetProjectManager() end)
    if ok3 and pm ~= nil then
        local ok4, list = pcall(function() return pm:GetProjectListInCurrentFolder() end)
        if ok4 and list ~= nil then out[#out + 1] = "project_count=" .. tostring(#list) end
    end
end
print(table.concat(out, "\\n"))
"""


def capability_probe(timeout: int = 90) -> dict[str, object]:
    """实测 Resolve 能力，返回可复核的 evidence 字典。

    关键判据（本机 2026-09-23 实测）：
        installed   — fuscript.exe 是否存在
        headless_ok — fuscript 能否无头执行并产出输出（不依赖 Resolve 运行）
        api_reachable — Resolve() 是否返回句柄（要求 Resolve.exe 正在运行）
    """
    report: dict[str, object] = {
        "installed": False,
        "headless_ok": False,
        "api_reachable": False,
        "resolve_exe": None,
        "fuscript_exe": None,
        "resolve_running": False,
        "product": None,
        "version": None,
        "project_count": None,
        "detail": "",
    }

    fuscript = find_fuscript_exe()
    resolve_exe = find_resolve_exe()
    report["resolve_exe"] = str(resolve_exe) if resolve_exe else None
    report["fuscript_exe"] = str(fuscript) if fuscript else None
    report["resolve_running"] = is_process_running()
    if fuscript is None:
        report["detail"] = "fuscript.exe 未找到，Resolve 不可用"
        return report

    report["installed"] = True
    probe_dir = Path(tempfile.gettempdir()) / "resolve_capability_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_file = probe_dir / "probe.lua"
    probe_file.write_text(_PROBE_LUA, encoding="utf-8")

    try:
        proc = subprocess.run(
            [str(fuscript), "-lua", str(probe_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        report["detail"] = f"fuscript 执行超时（{timeout}s）"
        return report
    except Exception as exc:
        report["detail"] = f"fuscript 执行失败: {exc}"
        return report

    stdout = proc.stdout or ""
    if proc.returncode != 0:
        report["detail"] = f"fuscript 退出码 {proc.returncode}: {stdout.strip()[:200]}"
        return report

    report["headless_ok"] = True
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()

    if "resolve_is_nil" not in values:
        report["detail"] = "探针输出缺少 resolve_is_nil 字段"
        return report

    report["api_reachable"] = values.get("resolve_is_nil") == "false"
    report["product"] = values.get("product")
    report["version"] = values.get("version")
    count = values.get("project_count")
    report["project_count"] = int(count) if count and count.isdigit() else None

    if not report["api_reachable"]:
        report["detail"] = (
            "fuscript 无头可执行，但 Resolve() 返回 nil —— "
            "Resolve 未运行。该 API 是对活实例的远程控制，需先启动 Resolve.exe。"
        )
    else:
        report["detail"] = "API 可达"
    return report


def clear_cache() -> None:
    """清空缓存（测试用）"""
    _cache.clear()
    _process_cache.clear()


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(capability_probe(), ensure_ascii=False, indent=2))

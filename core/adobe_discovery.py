"""
core/adobe_discovery.py — Adobe 产品安装位置统一发现器
=====================================================

修复历史缺陷：各调度器仅以 tasklist 进程探测判定"可用性"，
导致已安装但未运行的 Adobe 产品被误报为"未安装"。

本模块提供真正的【安装检测】，发现顺序（与 find_resolve_exe 对齐）：
    1. 环境变量覆盖（AEKV_ADOBE_<KEY>_PATH，指向 exe 全路径）
    2. 已知安装候选路径（含 D 盘自定义目录）
    3. 开始菜单快捷方式目标解析（WScript.Shell COM，适配任意自定义安装位置）
    4. Windows 注册表 Uninstall 条目（DisplayName 匹配）

结果进程内缓存，重复调用零成本。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

# ---------------------------------------------------------------------------
# 产品注册表：key → (exe 文件名, 快捷方式名关键词, DisplayName 关键词, 候选目录)
# ---------------------------------------------------------------------------

ADOBE_PRODUCTS: Dict[str, Dict[str, object]] = {
    "after_effects": {
        "exe_name": "AfterFX.exe",
        "shortcut_kw": "After Effects",
        "display_kw": "Adobe After Effects",
        "env_var": "AEKV_ADOBE_AE_PATH",
        "candidate_dirs": [
            r"C:\Program Files\Adobe\Adobe After Effects 2026\Support Files",
            r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files",
            r"D:\Ae26\Adobe After Effects 2026\Support Files",
            r"D:\Ae\Adobe After Effects 2026\Support Files",
            r"D:\Ae25\Adobe After Effects 2025\Support Files",
        ],
    },
    "media_encoder": {
        "exe_name": "Adobe Media Encoder.exe",
        "shortcut_kw": "Media Encoder",
        "display_kw": "Adobe Media Encoder",
        "env_var": "AEKV_ADOBE_AME_PATH",
        "candidate_dirs": [
            r"D:\Me\Adobe Media Encoder 2026",
            r"D:\Me\Adobe Media Encoder 2025",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2026",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2025",
        ],
    },
    "premiere": {
        "exe_name": "Adobe Premiere Pro.exe",
        "shortcut_kw": "Premiere Pro",
        "display_kw": "Adobe Premiere Pro",
        "env_var": "AEKV_ADOBE_PR_PATH",
        "candidate_dirs": [
            r"D:\pr\Adobe Premiere Pro 2026",
            r"D:\Pr26\Adobe Premiere Pro 2026",
            r"D:\Pr25\Adobe Premiere Pro 2025",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2026",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2025",
        ],
    },
    "audition": {
        "exe_name": "Adobe Audition.exe",
        "shortcut_kw": "Audition",
        "display_kw": "Adobe Audition",
        "env_var": "AEKV_ADOBE_AU_PATH",
        "candidate_dirs": [
            r"D:\Au\Adobe Audition 2026",
            r"D:\Au\Adobe Audition 2025",
            r"D:\Au25\Adobe Audition 2025",
            r"C:\Program Files\Adobe\Adobe Audition 2026",
            r"C:\Program Files\Adobe\Adobe Audition 2025",
        ],
    },
    "photoshop": {
        "exe_name": "Photoshop.exe",
        "shortcut_kw": "Photoshop",
        "display_kw": "Adobe Photoshop",
        "env_var": "AEKV_ADOBE_PS_PATH",
        "candidate_dirs": [
            r"D:\ps\Adobe Photoshop 2026",
            r"D:\ps\Adobe Photoshop 2025",
            r"C:\Program Files\Adobe\Adobe Photoshop 2026",
        ],
    },
}

# 进程内缓存：product_key → exe 路径（None 表示已确认未找到）
_cache: Dict[str, Optional[Path]] = {}


def _start_menu_dirs() -> List[Path]:
    """系统 + 用户开始菜单 Programs 目录"""
    dirs: List[Path] = []
    program_data = os.environ.get("ProgramData")
    if program_data:
        dirs.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [d for d in dirs if d.exists()]


def _resolve_shortcut_targets(keyword: str) -> List[Path]:
    """解析开始菜单中包含 keyword 的 .lnk 目标（仅 Windows，失败静默）

    优先 win32com（pywin32）；不可用时降级 PowerShell WScript.Shell 一次性批量解析。
    """
    if os.name != "nt":
        return []
    # 优先 win32com
    shell = None
    try:
        import win32com.client  # type: ignore
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:
        shell = None
    if shell is not None:
        targets: List[Path] = []
        for base in _start_menu_dirs():
            try:
                for lnk in base.rglob("*.lnk"):
                    if keyword.lower() not in lnk.stem.lower():
                        continue
                    try:
                        sc = shell.CreateShortcut(str(lnk))
                        target = getattr(sc, "TargetPath", "") or ""
                        if target and Path(target).exists():
                            targets.append(Path(target))
                    except Exception:
                        continue
            except Exception:
                continue
        return targets
    # 降级：PowerShell 批量解析（一次调用返回全部 lnk 目标）
    return _resolve_shortcuts_via_powershell(keyword)


def _resolve_shortcuts_via_powershell(keyword: str) -> List[Path]:
    """PowerShell WScript.Shell 批量解析快捷方式（win32com 缺失时的兜底）"""
    import subprocess
    dirs = _start_menu_dirs()
    if not dirs:
        return []
    dir_list = ",".join(f"'{d}'" for d in dirs)
    ps_script = (
        "$sh=New-Object -ComObject WScript.Shell;"
        f"Get-ChildItem {dir_list} -Recurse -Filter *.lnk -ErrorAction SilentlyContinue |"
        f" Where-Object {{ $_.Name -like '*{keyword}*' }} |"
        " ForEach-Object { $sh.CreateShortcut($_.FullName).TargetPath }"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
    except Exception:
        return []
    targets: List[Path] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip().strip('"')
        if line and Path(line).exists():
            targets.append(Path(line))
    return targets


def _search_registry(display_kw: str, exe_name: str) -> Optional[Path]:
    """注册表 Uninstall 条目查找（DisplayIcon / InstallLocation）"""
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
                    if display_kw.lower() not in str(dn).lower():
                        continue
                    for field in ("DisplayIcon", "InstallLocation", "InstallSource"):
                        try:
                            val, _ = winreg.QueryValueEx(sub, field)
                        except OSError:
                            continue
                        p = Path(str(val).strip().split(",")[0].strip('"'))
                        if not str(p):
                            continue
                        if p.suffix.lower() == ".exe" and p.exists():
                            return p
                        cand = p / exe_name
                        if cand.exists():
                            return cand
            except OSError:
                continue
    return None


def find_adobe_exe(product: str, force_check: bool = False) -> Optional[Path]:
    """发现指定 Adobe 产品的 exe 路径（未安装返回 None）。

    Args:
        product: ADOBE_PRODUCTS 的 key（after_effects / media_encoder /
                 premiere / audition / photoshop）
        force_check: 忽略缓存重新扫描

    Returns:
        exe 绝对路径；未找到返回 None（结果缓存）
    """
    if product not in ADOBE_PRODUCTS:
        raise ValueError(f"Unknown Adobe product key: {product}")
    if not force_check and product in _cache:
        return _cache[product]

    spec = ADOBE_PRODUCTS[product]
    exe_name = str(spec["exe_name"])

    # 1. 环境变量覆盖
    env_val = os.environ.get(str(spec["env_var"]), "").strip()
    if env_val:
        p = Path(env_val)
        if p.exists():
            logger.info(f"[AdobeDiscovery] {product} 已定位（环境变量）: {p}")
            _cache[product] = p
            return p
        logger.warning(f"[AdobeDiscovery] 环境变量 {spec['env_var']} 路径不存在: {env_val}")

    # 2. 已知候选路径
    for d in spec["candidate_dirs"]:  # type: ignore[union-attr]
        cand = Path(str(d)) / exe_name
        if cand.exists():
            logger.info(f"[AdobeDiscovery] {product} 已定位（候选路径）: {cand}")
            _cache[product] = cand
            return cand

    # 3. 开始菜单快捷方式
    for target in _resolve_shortcut_targets(str(spec["shortcut_kw"])):
        if target.name.lower() == exe_name.lower() and target.exists():
            logger.info(f"[AdobeDiscovery] {product} 已定位（快捷方式）: {target}")
            _cache[product] = target
            return target

    # 4. 注册表
    reg_hit = _search_registry(str(spec["display_kw"]), exe_name)
    if reg_hit is not None:
        logger.info(f"[AdobeDiscovery] {product} 已定位（注册表）: {reg_hit}")
        _cache[product] = reg_hit
        return reg_hit

    logger.warning(f"[AdobeDiscovery] {product} 未找到（环境变量/候选路径/快捷方式/注册表均未命中）")
    _cache[product] = None
    return None


def is_adobe_installed(product: str) -> bool:
    """产品是否已安装（真实安装检测，非进程探测）"""
    return find_adobe_exe(product) is not None


def scan_all_adobe(force_check: bool = False) -> Dict[str, Dict[str, object]]:
    """扫描全部已注册 Adobe 产品的安装状态（供诊断/仪表盘使用）"""
    report: Dict[str, Dict[str, object]] = {}
    for key in ADOBE_PRODUCTS:
        exe = find_adobe_exe(key, force_check=force_check)
        report[key] = {
            "installed": exe is not None,
            "exe_path": str(exe) if exe else None,
        }
    return report


def clear_cache() -> None:
    """清空缓存（测试用）"""
    _cache.clear()


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(scan_all_adobe(force_check=True), ensure_ascii=False, indent=2))

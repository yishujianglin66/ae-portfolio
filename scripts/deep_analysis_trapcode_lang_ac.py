#!/usr/bin/env python3
"""
深度分析：Trapcode 安装状态、中英文界面、AfterCodecs
"""
from __future__ import annotations

import os
import winreg
from pathlib import Path
from typing import List

ae_root = Path("C:/Program Files/Adobe/Adobe After Effects 2025")
output_lines: List[str] = []


def log(line: str = "") -> None:
    output_lines.append(line)
    print(line)


def scan_trapcode() -> None:
    log("=== 1. Trapcode Suite 深度安装扫描 ===")

    plugins_dir = ae_root / "Support Files" / "Plug-ins"
    if not plugins_dir.exists():
        log("  插件目录不存在")
        return

    # 搜索所有相关关键词
    keywords = [
        "trapcode", "red giant", "rg_", "particular", "form", "shine",
        "starglow", "lux", "mir", "tao", "echospace", "3d stroke",
        "sound keys", "grow bounds", "horizon", "geo", "stardust",
    ]

    found_files = []
    for f in plugins_dir.rglob("*.*"):
        if not f.is_file():
            continue
        name_lower = f.name.lower()
        if any(kw in name_lower for kw in keywords):
            found_files.append(f)

    log(f"  插件目录中找到 {len(found_files)} 个 Red Giant / Trapcode 相关文件")
    for f in found_files[:30]:
        rel = f.relative_to(plugins_dir)
        size_kb = f.stat().st_size / 1024
        log(f"    {rel} ({size_kb:.1f} KB)")
    if len(found_files) > 30:
        log(f"    ... 还有 {len(found_files) - 30} 个")
    log()

    # 检查 Common Files
    log("  --- Common Files 中的 Red Giant ---")
    common_paths = [
        Path("C:/Program Files/Adobe/Common/Plug-ins/7.0/MediaCore"),
        Path("C:/Program Files/Red Giant"),
        Path("C:/Program Files/Maxon"),
        Path("C:/Program Files (x86)/Red Giant"),
    ]
    for cp in common_paths:
        if cp.exists():
            files = list(cp.rglob("*.aex")) + list(cp.rglob("*.aex"))
            tg_files = [f for f in files if any(kw in f.name.lower() for kw in keywords)]
            log(f"  {cp}: {len(files)} 个插件文件, {len(tg_files)} 个Trapcode相关")
            for f in tg_files[:5]:
                log(f"    {f.name}")
    log()

    # 检查预设中的 Trapcode
    log("  --- Presets 中的 Trapcode 预设 ---")
    presets_dir = ae_root / "Support Files" / "Presets"
    if presets_dir.exists():
        ffx_files = list(presets_dir.rglob("*.ffx"))
        tg_presets = [f for f in ffx_files if any(kw in f.name.lower() for kw in ["trapcode", "particular", "form", "shine", "mir", "tao"])]
        log(f"  Trapcode 相关预设: {len(tg_presets)} 个")
        # 分类统计
        from collections import Counter
        cats = Counter()
        for f in tg_presets:
            parent = f.parent.name
            cats[parent] += 1
        for cat, count in cats.most_common(10):
            log(f"    {cat}: {count} 个")
    log()

    # 注册表检查
    log("  --- 注册表检查 ---")
    try:
        key_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Red Giant"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Maxon"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Red Giant"),
        ]
        for hive, path in key_paths:
            try:
                key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
                log(f"  HKLM\\{path} 存在")
                subkeys = []
                i = 0
                while True:
                    try:
                        subkeys.append(winreg.EnumKey(key, i))
                        i += 1
                    except OSError:
                        break
                for sk in subkeys[:10]:
                    log(f"    {sk}")
                winreg.CloseKey(key)
            except FileNotFoundError:
                pass
    except Exception as e:
        log(f"  注册表访问异常: {e}")
    log()


def scan_language() -> None:
    log("=== 2. 中英文界面状态分析 ===")

    # AMT 语言配置
    amt_dir = ae_root / "Support Files" / "AMT"
    if amt_dir.exists():
        log(f"  AMT 目录: {amt_dir}")
        # 语言包目录
        lang_dir = amt_dir / "Languages"
        if lang_dir.exists():
            langs = [d.name for d in lang_dir.iterdir() if d.is_dir()]
            log(f"  已安装语言包: {langs}")

        # application.xml
        app_xml = amt_dir / "application.xml"
        if app_xml.exists():
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(app_xml)
                root = tree.getroot()
                # 查找支持语言
                for elem in root.iter():
                    if "language" in elem.tag.lower() or "locale" in elem.tag.lower():
                        log(f"  语言配置: {elem.tag} = {elem.text}")
                        break
            except Exception as e:
                log(f"  解析 XML 失败: {e}")
    log()

    # 用户配置中的语言
    appdata_ae = Path(os.environ.get("APPDATA", "")) / "Adobe" / "After Effects"
    if appdata_ae.exists():
        log(f"  用户配置目录: {appdata_ae}")
        for ver_dir in appdata_ae.iterdir():
            if ver_dir.is_dir():
                log(f"    版本: {ver_dir.name}")
                prefs_dir = ver_dir / "Prefs"
                if prefs_dir.exists():
                    lang_files = list(prefs_dir.glob("*lang*")) + list(prefs_dir.glob("*zh*")) + list(prefs_dir.glob("*zh_CN*"))
                    if lang_files:
                        log(f"      语言相关配置: {[f.name for f in lang_files]}")
                    # 列出所有 .txt 配置文件
                    txt_files = list(prefs_dir.glob("*.txt"))
                    if txt_files:
                        log(f"      Prefs 配置文件: {len(txt_files)} 个")
                        for f in txt_files[:5]:
                            log(f"        {f.name}")
    log()

    # 检查汉化痕迹
    log("  --- 汉化/中文语言包痕迹 ---")
    cn_files = []
    for f in ae_root.rglob("*"):
        if not f.is_file():
            continue
        name = f.name
        if any(kw in name for kw in ["中文", "汉化", "Chinese", "zh_CN", "zh-TW", "cn_"]):
            cn_files.append(f)
    log(f"  中文/汉化相关文件: {len(cn_files)} 个")
    for f in cn_files[:15]:
        rel = f.relative_to(ae_root)
        log(f"    {rel}")
    log()


def scan_aftercodecs() -> None:
    log("=== 3. AfterCodecs 安装状态检查 ===")

    plugins_dir = ae_root / "Support Files" / "Plug-ins"
    ac_files = []
    if plugins_dir.exists():
        for f in plugins_dir.rglob("*"):
            if not f.is_file():
                continue
            name_lower = f.name.lower()
            if "aftercodecs" in name_lower or "autokroma" in name_lower:
                ac_files.append(f)

    log(f"  AE 插件目录 AfterCodecs: {len(ac_files)} 个文件")
    for f in ac_files:
        rel = f.relative_to(plugins_dir)
        size_kb = f.stat().st_size / 1024
        log(f"    {rel} ({size_kb:.1f} KB)")
    log()

    # 脚本中的 AfterCodecs
    scripts_dir = ae_root / "Support Files" / "Scripts"
    if scripts_dir.exists():
        ac_scripts = [f for f in scripts_dir.rglob("*") if f.is_file() and "aftercodecs" in f.name.lower()]
        log(f"  脚本目录 AfterCodecs: {len(ac_scripts)} 个")
        for f in ac_scripts:
            log(f"    {f.relative_to(scripts_dir)}")
    log()

    # Autokroma 目录
    autokroma_paths = [
        Path("C:/Program Files/Autokroma"),
        Path("C:/Program Files (x86)/Autokroma"),
    ]
    found_ak = False
    for ap in autokroma_paths:
        if ap.exists():
            log(f"  Autokroma 目录存在: {ap}")
            files = list(ap.rglob("*.*"))
            log(f"    文件数: {len(files)}")
            for f in files[:10]:
                if f.is_file():
                    log(f"      {f.name}")
            found_ak = True
    if not found_ak:
        log("  Autokroma 目录不存在（AfterCodecs 未独立安装）")
    log()

    # PR / AME 中的 AfterCodecs
    log("  --- Premiere Pro / AME 中的 AfterCodecs ---")
    pr_paths = [
        Path("D:/Me/Adobe Media Encoder 2025"),
        Path("C:/Program Files/Adobe/Adobe Premiere Pro 2025"),
    ]
    for prp in pr_paths:
        if prp.exists():
            pr_plugins = prp / "Plug-ins" / "Common"
            if not pr_plugins.exists():
                pr_plugins = prp / "Plug-ins"
            if pr_plugins.exists():
                ac_pr = [f for f in pr_plugins.rglob("*") if f.is_file() and "aftercodecs" in f.name.lower()]
                log(f"  {prp.name}: {len(ac_pr)} 个 AfterCodecs 文件")
                for f in ac_pr:
                    log(f"    {f.name}")
    log()


def main() -> None:
    log("=== AE 2025 深度分析：Trapcode / 中英文 / AfterCodecs ===")
    log()

    scan_trapcode()
    scan_language()
    scan_aftercodecs()

    log("=== 扫描完成 ===")

    # 保存
    output_path = Path("D:/AE-Work/ae_deep_analysis.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"\n报告已保存到: {output_path}")


if __name__ == "__main__":
    main()

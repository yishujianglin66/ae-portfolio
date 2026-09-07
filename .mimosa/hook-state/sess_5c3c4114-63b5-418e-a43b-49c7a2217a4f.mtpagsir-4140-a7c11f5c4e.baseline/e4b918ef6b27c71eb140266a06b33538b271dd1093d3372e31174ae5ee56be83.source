#!/usr/bin/env python3
"""
深度分析 AE 2025 插件和资源库完整性
直接扫描文件系统，生成结构化分析报告
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

AE_ROOT = Path("C:/Program Files/Adobe/Adobe After Effects 2025")
RES_ROOT = Path("D:/AE-Work/resources")
OUTPUT_PATH = Path("D:/AE-Work/ae_resource_gap_analysis.txt")

output_lines: List[str] = []


def log(line: str = "") -> None:
    output_lines.append(line)
    print(line)


def scan_plugins() -> Dict[str, List[Path]]:
    """扫描所有 .aex 插件，按顶层目录分组"""
    plugins_dir = AE_ROOT / "Support Files" / "Plug-ins"
    result: Dict[str, List[Path]] = {}
    if not plugins_dir.exists():
        return result
    for top_dir in plugins_dir.iterdir():
        if top_dir.is_dir():
            aex_files = list(top_dir.rglob("*.aex"))
            result[top_dir.name] = aex_files
    return result


def scan_scripts() -> List[Path]:
    """扫描所有脚本文件"""
    scripts_dir = AE_ROOT / "Support Files" / "Scripts"
    if not scripts_dir.exists():
        return []
    return list(scripts_dir.rglob("*.jsx")) + list(scripts_dir.rglob("*.jsxbin"))


def main() -> None:
    log("=== AE 2025 深度资源分析报告 ===")
    log()

    # 1. 基本安装信息
    log("=== 1. AE 2025 安装状态 ===")
    if AE_ROOT.exists():
        total_size = sum(f.stat().st_size for f in AE_ROOT.rglob("*") if f.is_file())
        total_files = sum(1 for f in AE_ROOT.rglob("*") if f.is_file())
        log(f"  状态: 已安装")
        log(f"  路径: {AE_ROOT}")
        log(f"  总大小: {total_size / 1024**3:.2f} GB")
        log(f"  文件数: {total_files:,}")
    else:
        log("  状态: 未安装")
    log()

    # 2. 插件扫描
    log("=== 2. 插件深度扫描 ===")
    plugins = scan_plugins()
    total_plugins = sum(len(v) for v in plugins.values())
    log(f"  插件总数: {total_plugins} 个 .aex 文件")
    log(f"  插件包数量: {len(plugins)} 个")
    log()
    log("  插件包清单 (按数量排序):")
    sorted_plugins = sorted(plugins.items(), key=lambda x: len(x[1]), reverse=True)
    for name, files in sorted_plugins:
        size = sum(f.stat().st_size for f in files) if files else 0
        log(f"    {name}: {len(files)} 个插件, {size / 1024 / 1024:.1f} MB")
    log()

    # 3. 空/近空插件目录
    log("=== 3. 空或接近空的插件目录 (可能不完整) ===")
    for name, files in sorted_plugins:
        if len(files) <= 2:
            dir_path = AE_ROOT / "Support Files" / "Plug-ins" / name
            all_files = list(dir_path.rglob("*.*"))
            log(f"  {name} ({len(files)} .aex / {len(all_files)} 总文件):")
            for f in all_files[:5]:
                log(f"    - {f.name} ({f.stat().st_size / 1024:.1f} KB)")
    log()

    # 4. 必备插件检查
    log("=== 4. 必备插件/脚本检查 ===")
    all_aex = [f.name.lower() for files in plugins.values() for f in files]
    scripts = scan_scripts()
    all_script_names = [f.name.lower() for f in scripts]

    must_haves = [
        ("Trapcode Suite (粒子系统)", ["particular", "form", "trapcode", "shine"], "plugin"),
        ("Red Giant Magic Bullet (调色)", ["magic bullet", "looks", "colorista", "mojo"], "plugin"),
        ("Red Giant Universe", ["universe"], "plugin"),
        ("Boris Continuum (特效包)", ["continuum", "bcc"], "plugin"),
        ("Boris Sapphire (蓝宝石)", ["sapphire", "s_"], "plugin"),
        ("Video Copilot Element 3D", ["element.aex", "videocopilot"], "plugin"),
        ("FXConsole (特效控制台)", ["fxconsole"], "script"),
        ("Duik Bassel (角色绑定)", ["duik"], "script"),
        ("Motion 2/3 (动效工具)", ["motion 2", "motion 3", "motion 4", "motion2", "motion3"], "script"),
        ("Flow (曲线编辑器)", ["flow"], "script"),
        ("AfterCodecs (编码加速)", ["aftercodecs"], "plugin"),
        ("BG Renderer (后台渲染)", ["bg renderer", "bgrenderer"], "script"),
        ("Pastiche (拼贴)", ["pastiche"], "plugin"),
        ("Deep Glow (高级发光)", ["deep glow"], "plugin"),
        ("Shadow Studio (阴影)", ["shadow studio"], "plugin"),
        ("Projection 3D (3D投影)", ["projection 3d"], "script"),
        ("GifGun (GIF导出)", ["gifgun"], "script"),
        ("AutoSway (自然摆动)", ["autosway"], "script"),
        ("Animation Composer", ["animation composer", "animationcomposer"], "script"),
        ("RubberHose (角色动画)", ["rubberhose", "rubber hose"], "script"),
    ]

    for name, keywords, type_ in must_haves:
        found_items = []
        if type_ == "plugin":
            for kw in keywords:
                if any(kw.lower() in aex for aex in all_aex):
                    found_items.append(kw)
        else:
            for kw in keywords:
                if any(kw.lower() in s for s in all_script_names):
                    found_items.append(kw)

        status = "✅ 已安装" if found_items else "❌ 缺失"
        detail = f"({', '.join(found_items)})" if found_items else ""
        log(f"  {status} {name} {detail}")
    log()

    # 5. 脚本分析
    log("=== 5. 脚本分析 ===")
    log(f"  脚本总数: {len(scripts)} 个")
    script_ui_dir = AE_ROOT / "Support Files" / "Scripts" / "ScriptUI Panels"
    if script_ui_dir.exists():
        ui_scripts = list(script_ui_dir.glob("*.jsx")) + list(script_ui_dir.glob("*.jsxbin"))
        log(f"  ScriptUI 面板: {len(ui_scripts)} 个")
        log()
        log("  ScriptUI 面板清单:")
        for s in ui_scripts[:30]:
            size_kb = s.stat().st_size / 1024
            log(f"    - {s.name} ({size_kb:.1f} KB)")
        if len(ui_scripts) > 30:
            log(f"    ... 还有 {len(ui_scripts) - 30} 个")
    log()

    # 6. 预设分析
    log("=== 6. 预设 (Presets) 分析 ===")
    presets_dir = AE_ROOT / "Support Files" / "Presets"
    if presets_dir.exists():
        ffx_files = list(presets_dir.rglob("*.ffx"))
        log(f"  预设总数: {len(ffx_files)} 个 .ffx")
        cats = {}
        for f in ffx_files:
            cat = f.relative_to(presets_dir).parts[0] if len(f.relative_to(presets_dir).parts) > 1 else "Root"
            cats[cat] = cats.get(cat, 0) + 1
        for cat, count in sorted(cats.items(), key=lambda x: x[1], reverse=True):
            log(f"    {cat}: {count} 个")
    log()

    # 7. 资源库状态
    log("=== 7. 资源库 (D:/AE-Work/resources) 状态 ===")
    resource_cats = [
        ("plugins", "AE 插件安装包/ZXP"),
        ("scripts", "AE 脚本"),
        ("presets", "动画预设 FFX"),
        ("effects", "特效素材"),
        ("videos", "视频素材"),
        ("images", "图片素材"),
        ("templates", "AE 工程模板"),
        ("fonts", "字体"),
        ("luts", "调色 LUT"),
        ("audio", "音频音效"),
        ("models", "3D 模型"),
        ("tutorials", "教程"),
        ("software", "软件安装包"),
        ("projects", "AE 工程文件"),
        ("psd", "PSD 素材"),
        ("davinci", "达芬奇插件/预设"),
        ("premiere", "PR 插件/预设"),
    ]
    for name, desc in resource_cats:
        cat_path = RES_ROOT / name
        if cat_path.exists():
            file_count = sum(1 for f in cat_path.rglob("*") if f.is_file())
            log(f"  ✅ {name} ({file_count} 个文件): {desc}")
        else:
            log(f"  ❌ {name} (缺失): {desc}")
    log()

    # 8. 已安装字体
    log("=== 8. 字体统计 ===")
    fonts_dir = RES_ROOT / "fonts"
    if fonts_dir.exists():
        font_files = list(fonts_dir.rglob("*.ttf")) + list(fonts_dir.rglob("*.otf")) + list(fonts_dir.rglob("*.ttc"))
        log(f"  资源库字体: {len(font_files)} 个")
    log()

    # 9. LUT 统计
    log("=== 9. LUT 调色统计 ===")
    luts_dir = RES_ROOT / "luts"
    if luts_dir.exists():
        lut_files = list(luts_dir.rglob("*.cube"))
        log(f"  LUT 文件: {len(lut_files)} 个")
        lut_cats = [d.name for d in luts_dir.iterdir() if d.is_dir()]
        log(f"  风格类别: {len(lut_cats)} 种")
        for cat in lut_cats[:15]:
            count = len(list((luts_dir / cat).rglob("*.cube")))
            log(f"    - {cat}: {count} 个")
        if len(lut_cats) > 15:
            log(f"    ... 还有 {len(lut_cats) - 15} 种")
    log()

    # 10. 音频统计
    log("=== 10. 音频音效统计 ===")
    audio_dir = RES_ROOT / "audio"
    if audio_dir.exists():
        audio_files = list(audio_dir.rglob("*.mp3")) + list(audio_dir.rglob("*.wav"))
        log(f"  音频文件: {len(audio_files)} 个")
    log()

    # 11. 项目配置集成建议
    log("=== 11. 项目配置集成建议 ===")
    log("  AE 2025 路径已在 puppet-automation/src/config/settings.py 中配置")
    log("  需要补充:")
    log("    1. 资源库缺失类别目录创建")
    log("    2. 资源索引服务新增脚本/模板等类别")
    log("    3. AE 引擎 aerender 路径验证")
    log("    4. LLM 网关配置")
    log()

    # 保存
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"\n分析报告已保存到: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

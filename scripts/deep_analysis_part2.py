#!/usr/bin/env python3
"""
进一步深入分析：Trapcode完整列表、语言配置详情、AfterCodecs版本
"""
from __future__ import annotations

from pathlib import Path

output = []

def log(s=""):
    output.append(s)
    print(s)

log("=== 深入分析补充 ===")
log()

# 1. 完整的 Trapcode 插件列表（MediaCore）
log("=== 1. MediaCore 中完整的 Trapcode/Red Giant 插件列表 ===")
media_core = Path("C:/Program Files/Adobe/Common/Plug-ins/7.0/MediaCore")
if media_core.exists():
    all_aex = sorted(media_core.glob("*.aex"))
    log(f"  MediaCore 总插件数: {len(all_aex)}")
    
    # 分类
    trapcode_keywords = ["Trapcode", "Particular", "Form", "Shine", "Starglow", "Lux", "Mir", 
                         "Tao", "Echospace", "3D Stroke", "Sound Keys", "Grow Bounds", 
                         "Horizon", "Geo", "Soundkeys"]
    
    mb_keywords = ["Magic Bullet", "Looks", "Colorista", "Mojo", "Denoiser", "Cosmo", "Film", "Renoiser"]
    universe_keywords = ["Universe", "UN_"]
    
    trapcode_files = []
    mb_files = []
    universe_files = []
    other_rg = []
    
    for f in all_aex:
        name = f.name
        name_lower = name.lower()
        if any(kw.lower() in name_lower for kw in trapcode_keywords) or "trapcode" in str(f.parent).lower():
            trapcode_files.append(f)
        elif any(kw.lower() in name_lower for kw in mb_keywords):
            mb_files.append(f)
        elif any(kw.lower() in name_lower for kw in universe_keywords):
            universe_files.append(f)
        elif "red giant" in str(f).lower() or "RG_" in name or "RedGiant" in name:
            other_rg.append(f)
    
    log(f"  Trapcode Suite: {len(trapcode_files)} 个")
    for f in trapcode_files:
        size_mb = f.stat().st_size / 1024 / 1024
        log(f"    {f.name} ({size_mb:.2f} MB)")
    
    log(f"  Magic Bullet Suite: {len(mb_files)} 个")
    for f in mb_files:
        size_mb = f.stat().st_size / 1024 / 1024
        log(f"    {f.name} ({size_mb:.2f} MB)")
    
    log(f"  Red Giant Universe: {len(universe_files)} 个")
    for f in universe_files[:10]:
        log(f"    {f.name}")
    if len(universe_files) > 10:
        log(f"    ... 还有 {len(universe_files) - 10} 个")
    
    log(f"  其他 Red Giant: {len(other_rg)} 个")
    for f in other_rg:
        log(f"    {f.name}")
log()

# 2. AE 语言配置深入
log("=== 2. AE 语言配置详细分析 ===")

ae_root = Path("C:/Program Files/Adobe/Adobe After Effects 2025")

# 检查 Dictionaries
dict_dir = ae_root / "Support Files" / "Dictionaries"
if dict_dir.exists():
    log(f"  词典目录: {dict_dir}")
    lang_dirs = [d.name for d in dict_dir.iterdir() if d.is_dir()]
    log(f"  可用语言词典: {lang_dirs}")
    for ld in lang_dirs:
        files = list((dict_dir / ld).iterdir())
        log(f"    {ld}: {len(files)} 个文件")

# 检查 AMT Languages
amt_lang = ae_root / "Support Files" / "AMT" / "Languages"
if amt_lang.exists():
    log(f"  AMT 语言包: {[d.name for d in amt_lang.iterdir() if d.is_dir()]}")

# 检查用户 Prefs 中的语言设置
import os

appdata = Path(os.environ.get("APPDATA", ""))
ae_prefs = appdata / "Adobe" / "After Effects" / "25.3" / "Prefs"
if ae_prefs.exists():
    log(f"  Prefs 目录: {ae_prefs}")
    # 找所有 .txt 文件，搜索 language 相关
    for f in sorted(ae_prefs.glob("*.txt")):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if "language" in content.lower() or "locale" in content.lower() or "zh_" in content or "en_" in content:
                log(f"  语言相关配置文件: {f.name}")
                # 提取相关行
                for line in content.split("\n"):
                    if any(kw in line.lower() for kw in ["language", "locale", "\"en\"", "\"zh\"", "en_us", "zh_cn"]):
                        log(f"    {line.strip()[:120]}")
        except Exception as e:
            pass
log()

# 3. AfterCodecs 详细信息
log("=== 3. AfterCodecs 详细信息 ===")
plugins_dir = ae_root / "Support Files" / "Plug-ins"
ac_files = [f for f in plugins_dir.rglob("*") if f.is_file() and "AfterCodecs" in f.name]

for f in ac_files:
    size_mb = f.stat().st_size / 1024 / 1024
    log(f"  {f.name} - {size_mb:.2f} MB")
    # 尝试读取版本信息（PE文件头）
    try:
        # 使用 Windows API 获取文件版本
        try:
            from win32com.client import Dispatch
            ver_parser = Dispatch("Scripting.FileSystemObject")
            fv = ver_parser.GetFileVersion(str(f))
            log(f"    版本: {fv}")
        except ImportError:
            pass
    except Exception:
        pass

# 检查 AE 插件中的 AfterCodecs 子目录
for d in plugins_dir.iterdir():
    if d.is_dir() and ("AfterCodecs" in d.name or "Autokroma" in d.name):
        log(f"  AfterCodecs 子目录: {d.name}")
        for f in d.rglob("*"):
            if f.is_file():
                log(f"    {f.name} ({f.stat().st_size / 1024:.1f} KB)")
log()

# 4. AE 安装的所有 Red Giant 产品总览
log("=== 4. Red Giant / Maxon 产品总览 ===")
total_rg = len(trapcode_files) + len(mb_files) + len(universe_files) + len(other_rg)
log(f"  Trapcode Suite: {len(trapcode_files)} 个插件")
log(f"  Magic Bullet Suite: {len(mb_files)} 个插件")
log(f"  Red Giant Universe: {len(universe_files)} 个插件")
log(f"  其他 Red Giant: {len(other_rg)} 个插件")
log(f"  MediaCore 总计: {total_rg} 个 Red Giant 插件")
log()

# 保存
out_path = Path("D:/AE-Work/ae_deep_analysis_2.txt")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text("\n".join(output), encoding="utf-8")
log(f"报告已保存: {out_path}")

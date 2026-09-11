# -*- coding: utf-8 -*-
"""L1 白名单字体安装器 (需管理员) —— 读 schemas/font_whitelist_l1.json, 装到系统级
安全: ① 只装白名单内且非授权风险的字体 ② 目标目录固定为系统字体目录 ③ 可逆(删文件+注册表项)
用法(提权): Start-Process <python> -ArgumentList scripts/install_fonts_l1.py -Verb RunAs
"""
import json
import os
import shutil
import sys
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WHITELIST = ROOT / "schemas" / "font_whitelist_l1.json"
USER_DIR = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"
DEST = Path(os.environ["WINDIR"]) / "Fonts"
LOG = ROOT / "tmp" / "font_install_l1.log"
KIND = {".ttf": "TrueType", ".ttc": "TrueType", ".otf": "OpenType", ".otc": "OpenType"}


def main():
    wl = json.loads(WHITELIST.read_text(encoding="utf-8"))
    fonts = [f for f in wl["fonts"]]
    lines, ok, skip, fail = [], [], [], []
    key = None
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
                             0, winreg.KEY_SET_VALUE)
        lines.append("HKLM 可写: OK")
    except Exception as e:
        lines.append(f"HKLM 拒绝访问(需提权): {e}")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        sys.exit(1)

    for f in fonts:
        src = USER_DIR / f["file"]
        if not src.exists():
            skip.append(f"{f['ps_name']}(源文件缺失)")
            continue
        try:
            dst = DEST / f["file"]
            if not dst.exists():
                shutil.copy2(src, dst)
            kind = KIND.get(src.suffix.lower(), "TrueType")
            winreg.SetValueEx(key, f"{f['ps_name']} ({kind})", 0, winreg.REG_SZ, f["file"])
            ok.append(f["ps_name"])
        except Exception as e:
            fail.append(f"{f['ps_name']}: {e}")
    winreg.CloseKey(key)
    lines.append(f"INSTALLED({len(ok)}): " + ", ".join(ok))
    if skip:
        lines.append(f"SKIPPED({len(skip)}): " + ", ".join(skip))
    if fail:
        lines.append(f"FAILED({len(fail)}): " + " | ".join(fail))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines)[:1500])


if __name__ == "__main__":
    main()

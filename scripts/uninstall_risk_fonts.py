# -*- coding: utf-8 -*-
"""卸载授权风险字体 (trial/demo/personal-use) —— 从系统字体目录与注册表移除 (需管理员)
安全: ① 仅操作显式清单 ② 只删系统字体目录下的具体文件 ③ 先校验文件名含风险标记
用法(提权): Start-Process <python> -ArgumentList scripts/uninstall_risk_fonts.py -Verb RunAs
"""
import os
import sys
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = Path(os.environ["WINDIR"]) / "Fonts"
LOG = ROOT / "tmp" / "font_uninstall_risk.log"

# (PS 名, 文件名) —— 文件名必须含风险标记才允许删除
TARGETS = [("BRUSHSTRIKE", "Brushstrike trial.ttf")]
RISK_KEYS = ("trial", "demo", "free", "personal", "non-commercial", "preview", "sample")


def main():
    lines, done, skipped = [], [], []
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

    for ps, fn in TARGETS:
        if not any(k in fn.lower() for k in RISK_KEYS):
            skipped.append(f"{fn}(文件名无风险标记, 拒删)")
            continue
        # 删注册表值 (两种类型名都试)
        for kind in ("TrueType", "OpenType"):
            try:
                winreg.DeleteValue(key, f"{ps} ({kind})")
                lines.append(f"注册表已删: {ps} ({kind})")
            except FileNotFoundError:
                pass
            except Exception as e:
                lines.append(f"注册表删除失败 {ps}: {e}")
        # 删文件
        p = DEST / fn
        try:
            if p.exists():
                p.unlink()
                done.append(fn)
            else:
                skipped.append(f"{fn}(文件不存在)")
        except Exception as e:
            lines.append(f"文件删除失败 {fn}: {e}")
    winreg.CloseKey(key)
    lines.append(f"DELETED({len(done)}): " + ", ".join(done))
    if skipped:
        lines.append("SKIPPED: " + ", ".join(skipped))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

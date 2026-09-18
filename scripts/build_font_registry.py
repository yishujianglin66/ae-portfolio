# -*- coding: utf-8 -*-
"""字体注册表构建器 —— 扫描系统(HKLM)与用户目录全部字体 face, 记录四个维度事实:
  PS 名 / 位置 / 授权风险标记 / 字形覆盖(本项目词库) ; 输出 schemas/font_registry.json
用法: python scripts/build_font_registry.py [--out schemas/font_registry.json]
说明: 本会话已实证四条独立维度必须分开记录(PS名存在 ≠ 可解析 ≠ 有字形 ≠ 可商用)"""
import argparse
import json
import os
import re
import sys
import winreg
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

ROOT = Path(__file__).resolve().parent.parent
USER_DIR = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"
SYS_DIR = Path(os.environ["WINDIR"]) / "Fonts"

# 本项目词库 (与 build_text_overlay.DEFAULT_WORDS 同源; 用于覆盖判定)
JP_WORDS = "最強爆発無下限崩壊余韻無限束縛臨界"
CN_WORDS = "五条悟加速迂回静止虚式"
LATIN_WORDS = "BREAKZEROIMPACTREDLIMITTHEENDVIOLATIONREVERSE"

RISK_KEYS = ("trial", "demo", "free", "personal", "non-commercial", "preview", "sample")


def registered_ps_names() -> set:
    """HKLM 字体注册表中的 (显示名) 集合, 用于判定'文件在但未注册'"""
    out = set()
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        i = 0
        while True:
            try:
                name, val, _ = winreg.EnumValue(k, i)
                out.add((name or "").lower())
                i += 1
            except OSError:
                break
        winreg.CloseKey(k)
    except Exception:
        pass
    return out


def faces_of(p: Path):
    """返回 [(ps_name, family, subfamily)]; 含 TTC 多 face"""
    res = []
    try:
        coll = TTCollection(str(p), lazy=True)
        for f in coll.fonts:
            try:
                n = f["name"]
                res.append((n.getDebugName(6), n.getDebugName(1), n.getDebugName(2)))
            except Exception:
                pass
        return res
    except Exception:
        pass
    try:
        f = TTFont(str(p), lazy=True)
        n = f["name"]
        return [(n.getDebugName(6), n.getDebugName(1), n.getDebugName(2))]
    except Exception:
        return []


def coverage(p: Path):
    """(jp, cn, latin) 覆盖计数; 无 cmap 或失败返回 None"""
    cmap = None
    try:
        cmap = TTFont(str(p), lazy=True).getBestCmap()
    except Exception:
        try:
            cmap = TTCollection(str(p), lazy=True).fonts[0].getBestCmap()
        except Exception:
            cmap = None
    if not cmap:
        return None

    def cnt(s):
        return sum(1 for ch in set(s) if ord(ch) in cmap)
    return cnt(JP_WORDS), cnt(CN_WORDS), cnt(LATIN_WORDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="schemas/font_registry.json")
    args = ap.parse_args()
    out_p = ROOT / args.out
    out_p.parent.mkdir(parents=True, exist_ok=True)

    reg = registered_ps_names()
    records, seen_ps = [], {}
    files = []
    for d, loc in ((SYS_DIR, "system"), (USER_DIR, "user")):
        if d.exists():
            files += [(p, loc) for p in sorted(d.iterdir())
                      if p.suffix.lower() in (".ttf", ".otf", ".ttc", ".otc")]
    total = len(files)
    print(f"扫描 {total} 个字体文件 ...")
    for idx, (p, loc) in enumerate(files, 1):
        if idx % 300 == 0:
            print(f"  ... {idx}/{total}")
        low = p.name.lower()
        risk = any(k in low for k in RISK_KEYS)
        cov = coverage(p)
        for ps, fam, sub in faces_of(p):
            if not ps:
                continue
            rec = {
                "ps_name": ps,
                "family": fam or "",
                "subfamily": sub or "",
                "file": p.name,
                "location": loc,
                "registered": any(ps.lower() in r for r in reg) if loc == "system" else False,
                "license_risk": risk,
                "cov_jp": cov[0] if cov else None,
                "cov_cn": cov[1] if cov else None,
                "cov_latin": cov[2] if cov else None,
                "jp_full": bool(cov and cov[0] == len(set(JP_WORDS))),
                "cn_full": bool(cov and cov[1] == len(set(CN_WORDS))),
                "latin_full": bool(cov and cov[2] == len(set(LATIN_WORDS))),
            }
            key = ps.lower()
            if key in seen_ps:            # 同名去重: 系统优先
                if rec["location"] == "system" and seen_ps[key]["location"] != "system":
                    seen_ps[key] = rec
                continue
            seen_ps[key] = rec
            records.append(rec)

    # 当前池中字体 (用于标注 pool_role)
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_text_overlay as bto  # noqa
        pooled = {}
        for style, by_script in bto.FONT_POOLS.items():
            for script, names in by_script.items():
                for n in names:
                    pooled.setdefault(n, []).append(f"{style}/{script}")
        for r in records:
            if r["ps_name"] in pooled:
                r["pool_role"] = pooled[r["ps_name"]]
    except Exception as e:
        print("池标注跳过:", e)

    records.sort(key=lambda r: (r["location"] != "system", not r["latin_full"], r["ps_name"].lower()))
    doc = {
        "generated_by": "scripts/build_font_registry.py",
        "word_bank": {"jp": JP_WORDS, "cn": CN_WORDS, "latin": LATIN_WORDS},
        "total_files": total,
        "total_faces": len(records),
        "system_faces": sum(1 for r in records if r["location"] == "system"),
        "user_faces": sum(1 for r in records if r["location"] == "user"),
        "license_risk_faces": sum(1 for r in records if r["license_risk"]),
        "fonts": records,
    }
    out_p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n写出 {out_p}")
    print(f"  faces={doc['total_faces']} (system={doc['system_faces']} / user={doc['user_faces']})")
    print(f"  授权风险 face={doc['license_risk_faces']}")
    print(f"  拉丁全覆盖={sum(1 for r in records if r['latin_full'])}"
          f" / 中文全覆盖={sum(1 for r in records if r['cn_full'])}"
          f" / 日文全覆盖={sum(1 for r in records if r['jp_full'])}")


if __name__ == "__main__":
    main()

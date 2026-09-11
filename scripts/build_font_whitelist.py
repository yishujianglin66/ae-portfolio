# -*- coding: utf-8 -*-
"""生成 L1 展示级字体白名单: 预设库类别 PS 名 ∩ 注册表(用户目录可装) ∩ 非授权风险
输出 schemas/font_whitelist_l1.json —— 供 scripts/install_fonts_l1.py 安装
用法: python scripts/build_font_whitelist.py"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "10-风格化剪辑知识库" / "字体预设库.md"
REGISTRY = ROOT / "schemas" / "font_registry.json"
OUT = ROOT / "schemas" / "font_whitelist_l1.json"


def parse_catalog():
    """返回 [(category, ps_name)]; 类别取 ### N.N 标题, PS 名取表格第 2 列的反引号内容"""
    cat, out = "未分类", []
    for line in CATALOG.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^###\s+\d+\.\d+\s+(.*)", line)
        if m:
            cat = m.group(1).strip()
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2:
                for ps in re.findall(r"`([A-Za-z][A-Za-z0-9_.-]{2,45})`", cells[1]):
                    out.append((cat, ps))
    return out


def main():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_ps = {}
    for f in reg["fonts"]:
        by_ps.setdefault(f["ps_name"], f)
    pairs = parse_catalog()
    entries, missing, risky, already = [], [], [], []
    seen = set()
    for cat, ps in pairs:
        if ps in seen:
            continue
        seen.add(ps)
        f = by_ps.get(ps)
        if not f:
            missing.append((cat, ps))
            continue
        if f["license_risk"]:
            risky.append((cat, ps, f["file"]))
            continue
        if f["location"] == "system":
            already.append((cat, ps))
            continue
        entries.append({
            "ps_name": ps, "category": cat, "file": f["file"],
            "family": f["family"], "cov_jp": f["cov_jp"], "cov_cn": f["cov_cn"],
            "cov_latin": f["cov_latin"], "jp_full": f["jp_full"], "cn_full": f["cn_full"],
            "latin_full": f["latin_full"],
        })
    by_cat = {}
    for e in entries:
        by_cat.setdefault(e["category"], []).append(e["ps_name"])
    OUT.write_text(json.dumps({
        "generated_by": "scripts/build_font_whitelist.py",
        "source_catalog": str(CATALOG.relative_to(ROOT)),
        "source_registry": str(REGISTRY.relative_to(ROOT)),
        "note": "L1 = 预设库文档化展示字体 ∩ 用户目录可装 ∩ 非授权风险; 安装后必须过渲染差分探针",
        "count": len(entries),
        "by_category": by_cat,
        "fonts": entries,
        "excluded": {"already_system": [(c, p) for c, p in already],
                     "license_risk": [{"category": c, "ps_name": p, "file": fn} for c, p, fn in risky],
                     "not_installed": [(c, p) for c, p in missing]},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"白名单 {len(entries)} 个 -> {OUT.relative_to(ROOT)}")
    for cat, names in sorted(by_cat.items()):
        print(f"  {cat}: {len(names)} -> {', '.join(names[:6])}{' ...' if len(names) > 6 else ''}")
    print(f"\n排除: 已在系统 {len(already)} / 授权风险 {len(risky)} / 未安装 {len(missing)}")
    if risky:
        print("  授权风险(不装):", ", ".join(f"{p}({c})" for c, p, _ in risky[:8]))


if __name__ == "__main__":
    main()

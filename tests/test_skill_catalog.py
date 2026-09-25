# -*- coding: utf-8 -*-
"""技能台账静态页生成器测试（P2-13 分发面 MVP）。

锁两条不变式：
 1. 生成成功且卡片数与 registry 一致（页面数据不脱节）
 2. 产物含全部 skill_id 与关键结构锚点（四标签/抽屉函数存在）
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json  # noqa: E402

from scripts.skill_catalog_html import ROOT as _R2, build  # noqa: E402


def test_build_catalog(tmp_path):
    out = tmp_path / "skills" / "index.html"
    n = build(out)
    reg = json.loads((_R2 / "schemas" / "skill_cards" / "registry.json").read_text(encoding="utf-8"))
    assert n == reg["count"] == len(reg["skills"])
    html = out.read_text(encoding="utf-8")
    # 每个 skill_id 都进了页面数据
    for sid in reg["skills"]:
        assert sid in html, f"缺卡片 {sid}"
    # 结构锚点
    for anchor in ("全景卡片墙", "功能域分组", "无头能力矩阵", "成本计量表",
                   "openDrawer", "initStats", "evidence_chain"):
        assert anchor in html, f"缺锚点 {anchor}"

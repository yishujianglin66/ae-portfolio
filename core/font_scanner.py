# -*- coding: utf-8 -*-
"""SystemFontScanner — 本地系统字体扫描与智能搭配 (专业化升级 T10)

.. deprecated:: 2026-08-16
    生产路径已收口到 core/font_style_map.py, 本模块仅剩测试引用;
    新代码请用 font_style_map.resolve_font()。

参考 scripts/apply_font_design.py 的 FONT_STRATEGY 架构:
1. 扫描 C:/Windows/Fonts/ 下所有 .ttf/.otf/.ttc
2. 提取字体名/粗度/风格标签 (文件名启发式, 无外部依赖)
3. 按20种场景标签自动匹配最优字体组合
4. 主标题+副标题+正文三级字体层次自动分配
"""
import os
import re
from typing import Any, Dict, List, Optional

FONT_DIRS = ["C:/Windows/Fonts"]
FONT_EXTS = (".ttf", ".otf", ".ttc")

# 文件名启发式 → 粗度 (weight 数值近似 OpenType 标准)
_WEIGHT_KEYWORDS = [
    ("black", 900), ("heavy", 900), ("ultra", 900),
    ("extrabold", 800), ("extrabd", 800),
    ("bold", 700), ("bd", 700),
    ("semibold", 600), ("demibold", 600), ("sb", 600),
    ("medium", 500), ("md", 500),
    ("regular", 400), ("normal", 400), ("book", 400),
    ("light", 300), ("lt", 300), ("thin", 100),
]
# 风格关键词 → 标签
_STYLE_KEYWORDS = {
    "italic": "italic", "oblique": "italic", "it": "italic",
    "condensed": "condensed", "cond": "condensed", "narrow": "condensed",
    "mono": "monospace", "courier": "monospace", "consolas": "monospace",
    "serif": "serif", ("times",): "serif", "bodoni": "serif",
    "impact": "display", "black": "display", "stencil": "display",
    "script": "handwriting", "brush": "handwriting", "hand": "handwriting",
    "kai": "calligraphy", "xingkai": "calligraphy", "shuti": "calligraphy",
    "hei": "gothic", "yahei": "gothic", "gothic": "gothic",
    "song": "serif_cjk", "ming": "serif_cjk", "serifsc": "serif_cjk",
    "yuan": "rounded", "round": "rounded", "cooper": "rounded",
}

# 20种场景标签 → 匹配偏好 (weight_min + 风格标签优先级 + 名称关键词)
# 标签集与 SmartMatcher 20合法场景标签一致
SCENE_FONT_RULES: dict[str, dict[str, Any]] = {
    "battle":     {"weight_min": 700, "prefer": ["display", "gothic"],
                   "names": ["impact", "simhei", "yahei", "hupo"]},
    "cyberpunk":  {"weight_min": 400, "prefer": ["monospace", "display"],
                   "names": ["consolas", "courier", "bahnschrift", "din"]},
    "cinematic":  {"weight_min": 400, "prefer": ["serif", "serif_cjk"],
                   "names": ["bodoni", "times", "song", "xinwei", "serif"]},
    "anime":      {"weight_min": 600, "prefer": ["gothic", "rounded"],
                   "names": ["gothic", "yahei", "simhei", "youyuan"]},
    "ink_wash":   {"weight_min": 400, "prefer": ["calligraphy"],
                   "names": ["xingkai", "kaiti", "kai", "shuti", "fzshuti"]},
    "neon":       {"weight_min": 300, "prefer": ["handwriting", "rounded"],
                   "names": ["brush", "script", "curlz"]},
    "social":     {"weight_min": 400, "prefer": ["rounded"],
                   "names": ["youyuan", "cooper", "curlz", "yahei"]},
    "horror":     {"weight_min": 400, "prefer": ["handwriting", "display"],
                   "names": ["chiller", "rage", "stencil"]},
    "tech":       {"weight_min": 400, "prefer": ["monospace", "gothic"],
                   "names": ["consolas", "bahnschrift", "din", "simhei"]},
    "elegant":    {"weight_min": 300, "prefer": ["serif", "italic"],
                   "names": ["bodoni", "palace", "georgia", "kaiti"]},
    "sport":      {"weight_min": 700, "prefer": ["display", "condensed"],
                   "names": ["impact", "arial black", "bahnschrift"]},
    "retro":      {"weight_min": 400, "prefer": ["serif", "display"],
                   "names": ["playbill", "broadway", "niagara"]},
    "magic":      {"weight_min": 400, "prefer": ["handwriting", "serif"],
                   "names": ["chiller", "palace", "vladimir"]},
    "industrial": {"weight_min": 600, "prefer": ["display", "condensed"],
                   "names": ["stencil", "impact", "din"]},
    "cute":       {"weight_min": 400, "prefer": ["rounded", "handwriting"],
                   "names": ["youyuan", "curlz", "comic"]},
    "data":       {"weight_min": 400, "prefer": ["monospace"],
                   "names": ["consolas", "courier"]},
    "brand":      {"weight_min": 500, "prefer": ["gothic", "serif"],
                   "names": ["yahei", "bahnschrift", "bodoni"]},
    "comic":      {"weight_min": 700, "prefer": ["display", "gothic"],
                   "names": ["hupo", "impact", "simhei", "yahei"]},
    "title_kit":  {"weight_min": 600, "prefer": ["display", "serif"],
                   "names": ["impact", "bodoni", "yahei"]},
    "lyric":      {"weight_min": 300, "prefer": ["serif_cjk", "calligraphy"],
                   "names": ["kaiti", "song", "yahei", "xingkai"]},
}


def _parse_font_file(fname: str) -> dict[str, Any] | None:
    """文件名启发式解析: 字体名/粗度/风格标签"""
    stem = os.path.splitext(fname)[0]
    low = stem.lower().replace(" ", "")
    name = re.sub(r"[-_\. ]+", " ", stem).strip()

    weight = 400
    for kw, w in _WEIGHT_KEYWORDS:
        if kw in low:
            weight = w
            break
    styles: list[str] = []
    for kw, tag in _STYLE_KEYWORDS.items():
        k = kw[0] if isinstance(kw, tuple) else kw
        if k in low and tag not in styles:
            styles.append(tag)
    cjk = any(t in styles for t in
              ("gothic", "calligraphy", "serif_cjk", "rounded")) or \
        any(k in low for k in ("simhei", "simsun", "kaiti", "msyh", "yahei"))
    return {"name": name, "file": fname, "weight": weight,
            "styles": styles, "cjk": cjk}


class SystemFontScanner:
    """系统字体扫描 + 场景智能搭配 + 三级层次分配"""

    def __init__(self, font_dirs: list[str] | None = None):
        self.font_dirs = font_dirs or FONT_DIRS
        self._cache: list[dict[str, Any]] = []

    # ── 扫描 ──────────────────────────────────────────────
    def scan(self) -> list[dict[str, Any]]:
        """扫描字体目录, 返回 [{name, file, weight, styles, cjk}]"""
        if self._cache:
            return self._cache
        found: dict[str, dict[str, Any]] = {}
        for d in self.font_dirs:
            if not os.path.isdir(d):
                continue
            for fname in os.listdir(d):
                if not fname.lower().endswith(FONT_EXTS):
                    continue
                info = _parse_font_file(fname)
                if info and info["name"].lower() not in found:
                    found[info["name"].lower()] = info
        self._cache = sorted(found.values(),
                             key=lambda x: (x["name"].lower()))
        return self._cache

    def stats(self) -> dict[str, int]:
        fonts = self.scan()
        return {
            "total": len(fonts),
            "cjk": sum(1 for f in fonts if f["cjk"]),
            "bold_plus": sum(1 for f in fonts if f["weight"] >= 700),
            "monospace": sum(1 for f in fonts
                             if "monospace" in f["styles"]),
        }

    # ── 场景匹配 ─────────────────────────────────────────
    def _score(self, font: dict[str, Any],
               rule: dict[str, Any]) -> float:
        s = 0.0
        low = font["name"].lower()
        for kw in rule.get("names", []):
            if kw in low:
                s += 10.0
        for tag in rule.get("prefer", []):
            if tag in font["styles"]:
                s += 4.0
        if font["weight"] >= rule.get("weight_min", 400):
            s += 3.0
        elif font["weight"] < rule.get("weight_min", 400) - 300:
            s -= 4.0
        return s

    def match_scene(self, scene_tag: str, top_k: int = 5) -> list[str]:
        """按场景标签返回最优字体名列表(得分降序)"""
        rule = SCENE_FONT_RULES.get(scene_tag)
        if rule is None:
            rule = {"weight_min": 400, "prefer": [], "names": []}
        scored = [(self._score(f, rule), f["name"])
                  for f in self.scan()]
        scored.sort(key=lambda x: (-x[0], x[1].lower()))
        return [name for _, name in scored[:top_k]]

    # ── 三级层次分配 ────────────────────────────────────
    def hierarchy(self, scene_tag: str) -> dict[str, str]:
        """主标题+副标题+正文三级字体层次

        主标题: 场景最优(最重/最个性) / 副标题: 次优 / 正文: 高可读(CJK优先)
        """
        pool = self.match_scene(scene_tag, top_k=8)
        if not pool:
            return {"title": "Impact", "subtitle": "Arial",
                    "body": "Arial"}
        title = pool[0]
        subtitle = pool[1] if len(pool) > 1 else pool[0]
        # 正文: 优先CJK可读字体, 再退回池内
        body = title
        for f in self.scan():
            if f["cjk"] and 400 <= f["weight"] <= 500:
                body = f["name"]
                break
        else:
            body = pool[-1]
        return {"title": title, "subtitle": subtitle, "body": body}

    def all_scene_matches(self) -> dict[str, list[str]]:
        """20场景全覆盖匹配报告"""
        return {tag: self.match_scene(tag) for tag in SCENE_FONT_RULES}

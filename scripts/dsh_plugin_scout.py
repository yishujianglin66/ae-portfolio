"""
DSH 插件生态每日侦察脚本
=========================
搜索 npm 上 dsh- 开头的插件，对比已安装列表，
按项目相关性评分，输出 markdown 报告。

用法:
    py -3.12 scripts/dsh_plugin_scout.py

输出:
    reports/dsh_plugin_scout_YYYY-MM-DD.md
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DSH_PROFILE = Path.home() / ".dsh" / "profiles" / "web"
_REPORT_DIR = _PROJECT_ROOT / "reports"

# 项目关键词 — 用于相关性评分
_PROJECT_KEYWORDS = [
    # 核心领域
    "after effects", "aftereffects", "ae", "premiere", "premiere pro",
    "davinci", "resolve", "video", "editing", "clip", "render",
    "animation", "motion", "composition", "vfx", "effect",
    # 项目特色
    "knowledge", "style", "剪辑", "风格", "特效", "转场", "调色",
    "粒子", "光效", "抠像", "追踪", "合成",
    # 技术栈
    "mcp", "tool", "filesystem", "search", "browser", "git",
    "python", "ffmpeg", "pipeline", "automation",
    # 实用功能
    "undo", "backup", "cache", "monitor", "debug", "log",
    "test", "lint", "format", "deploy", "ci",
    "cost", "token", "balance", "usage",
    "memory", "context", "rag", "embedding",
    "image", "audio", "subtitle", "caption",
]

# 已知的"无聊"包 — 过滤掉
_IGNORE_PACKAGES = {
    "@deepseek-ai/dsh",  # DSH 本体
}


def _run_npm_search(keyword: str, limit: int = 30) -> List[Dict[str, Any]]:
    """执行 npm search 并返回解析结果。"""
    try:
        result = subprocess.run(
            ["npm", "search", keyword,
             "--registry=https://registry.npmmirror.com",
             "--json", f"--searchlimit={limit}"],
            capture_output=True, timeout=90, shell=True,
        )
        raw = result.stdout
        # npm search 输出可能是 UTF-8 或 UTF-16
        for enc in ("utf-8", "utf-16"):
            try:
                text = raw.decode(enc, errors="replace").strip()
                data = json.loads(text)
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
    except Exception as e:
        print(f"  [WARN] npm search '{keyword}' failed: {e}", file=sys.stderr)
    return []


def _get_installed_packages() -> Set[str]:
    """读取已安装的 DSH 插件列表。"""
    pkg_json = _DSH_PROFILE / "package.json"
    if not pkg_json.exists():
        return set()
    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
        deps = set(data.get("dependencies", {}).keys())
        bundles = set(data.get("dsh", {}).get("profile", {}).get("bundles", []))
        return deps | bundles
    except Exception:
        return set()


def _score_relevance(package: Dict[str, Any]) -> Tuple[float, List[str]]:
    """计算包与项目的相关性分数。"""
    name = (package.get("name") or "").lower()
    desc = (package.get("description") or "").lower()
    keywords = package.get("keywords") or []
    if isinstance(keywords, list):
        keywords_text = " ".join(keywords).lower()
    else:
        keywords_text = ""

    haystack = f"{name} {desc} {keywords_text}"
    matched = []
    score = 0.0

    for kw in _PROJECT_KEYWORDS:
        if kw.lower() in haystack:
            matched.append(kw)
            # 名称匹配权重更高
            if kw.lower() in name:
                score += 3.0
            else:
                score += 1.0

    # 新鲜度加分 (最近 7 天发布/更新)
    date_str = package.get("date") or ""
    if date_str:
        try:
            pkg_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            age_days = (datetime.now(pkg_date.tzinfo) - pkg_date).days
            if age_days <= 7:
                score += 5.0
                matched.append("NEW(7d)")
            elif age_days <= 30:
                score += 2.0
                matched.append(f"recent({age_days}d)")
        except Exception:
            pass

    return score, matched


def _format_report(
    new_packages: List[Tuple[Dict[str, Any], float, List[str]]],
    updated_packages: List[Tuple[Dict[str, Any], float, List[str]]],
    installed: Set[str],
    total_searched: int,
) -> str:
    """生成 markdown 报告。"""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# DSH 插件生态日报 — {today}",
        "",
        f"> 搜索了 {total_searched} 个包，发现 "
        f"**{len(new_packages)}** 个新插件、"
        f"**{len(updated_packages)}** 个已安装插件有更新。",
        "",
        f"已安装: {', '.join(sorted(installed))}",
        "",
    ]

    if new_packages:
        lines.append("## 新发现的插件（按相关性排序）")
        lines.append("")
        for pkg, score, matched in new_packages[:15]:
            name = pkg.get("name", "?")
            ver = pkg.get("version", "?")
            desc = (pkg.get("description") or "")[:120]
            date = pkg.get("date", "?")[:10]
            lines.append(f"### `{name}` v{ver}")
            lines.append(f"- 发布/更新日期: {date}")
            lines.append(f"- 相关度: {score:.0f} 分")
            lines.append(f"- 匹配关键词: {', '.join(matched[:8])}")
            lines.append(f"- 描述: {desc}")
            lines.append(f"- 安装: `dsh plugin --profile web add {name}`")
            lines.append("")
    else:
        lines.append("## 新发现的插件")
        lines.append("")
        lines.append("今天没有发现新的相关插件。")
        lines.append("")

    if updated_packages:
        lines.append("## 已安装插件更新")
        lines.append("")
        for pkg, score, matched in updated_packages:
            name = pkg.get("name", "?")
            ver = pkg.get("version", "?")
            lines.append(f"- `{name}` 最新版 v{ver}")
        lines.append("")

    lines.append("---")
    lines.append(f"*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def main() -> None:
    print("=" * 60)
    print("  DSH 插件生态侦察")
    print("=" * 60)

    # 1. 获取已安装列表
    installed = _get_installed_packages()
    print(f"\n已安装 {len(installed)} 个插件: {sorted(installed)}")

    # 2. 搜索 npm
    search_keywords = [
        "dsh-plugin", "dsh-", "deepseek-harness",
        "dsh-tool", "dsh-mcp", "cordis-plugin",
    ]
    all_packages: Dict[str, Dict[str, Any]] = {}
    for kw in search_keywords:
        print(f"\n搜索: {kw} ...")
        results = _run_npm_search(kw)
        print(f"  找到 {len(results)} 个包")
        for pkg in results:
            name = pkg.get("name", "")
            if name and name not in _IGNORE_PACKAGES:
                # 保留最新版本
                if name not in all_packages or \
                   pkg.get("version", "") > all_packages[name].get("version", ""):
                    all_packages[name] = pkg

    print(f"\n去重后共 {len(all_packages)} 个包")

    # 3. 评分 & 分类
    new_packages = []
    updated_packages = []

    for name, pkg in all_packages.items():
        score, matched = _score_relevance(pkg)
        if score < 1.0:
            continue  # 不相关，跳过

        if name in installed:
            updated_packages.append((pkg, score, matched))
        else:
            new_packages.append((pkg, score, matched))

    # 按分数排序
    new_packages.sort(key=lambda x: x[1], reverse=True)
    updated_packages.sort(key=lambda x: x[1], reverse=True)

    # 4. 生成报告
    report = _format_report(
        new_packages, updated_packages, installed, len(all_packages)
    )

    # 5. 写入文件
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = _REPORT_DIR / f"dsh_plugin_scout_{today}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n报告已写入: {report_path}")

    # 6. 打印摘要
    print(f"\n{'=' * 60}")
    print(f"  新插件: {len(new_packages)} 个")
    print(f"  已安装更新: {len(updated_packages)} 个")
    if new_packages:
        print(f"\n  TOP 3 新插件:")
        for pkg, score, matched in new_packages[:3]:
            print(f"    {pkg['name']} v{pkg.get('version','')} "
                  f"(score={score:.0f}, keys={matched[:3]})")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

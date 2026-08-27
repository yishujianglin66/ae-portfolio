"""
知识库 & 桥接状态 MCP Server
=============================
为 DSH Agent 提供:
1. 风格化剪辑知识库检索 (10-风格化剪辑知识库, 262 个 md 文件)
2. 大师知识检索 (11-大师知识库, 15 个 md 文件)
3. AE/PR 桥接状态监控

工具命名: mcp__knowledge__<tool_name>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根目录在 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastmcp import FastMCP

mcp = FastMCP("Knowledge-Bridge")

# 知识库路径
_KB_DIR = str(_PROJECT_ROOT / "10-风格化剪辑知识库")
_MASTER_KB_DIR = str(_PROJECT_ROOT / "11-大师知识库")
_AE_BRIDGE_DIR = str(_PROJECT_ROOT / ".ae-mcp-bridge")
_PR_BRIDGE_DIR = str(_PROJECT_ROOT / ".premiere-mcp-bridge")

# 大师知识库缓存 (启动时加载一次)
_master_kb_index: Optional[List[Dict[str, Any]]] = None


def _get_kb_loader():
    """懒加载 KnowledgeBaseLoader 单例。"""
    from knowledge_base.kb_loader import KnowledgeBaseLoader
    return KnowledgeBaseLoader.get_instance()


def _ensure_master_index() -> List[Dict[str, Any]]:
    """构建大师知识库索引 (标题 + 标签 + 内容摘要)。"""
    global _master_kb_index
    if _master_kb_index is not None:
        return _master_kb_index

    _master_kb_index = []
    kb_dir = Path(_MASTER_KB_DIR)
    if not kb_dir.is_dir():
        return _master_kb_index

    for md_file in sorted(kb_dir.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # 提取标题 (第一行 # xxx)
        title = md_file.stem
        for line in text.splitlines()[:5]:
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                title = stripped
                break

        # 提取标签 (第二行 > 标签: xxx)
        tags = ""
        for line in text.splitlines()[:10]:
            if "标签" in line and ":" in line:
                tags = line.split(":", 1)[-1].strip().strip(">").strip()
                break

        # 内容摘要 (前 500 字)
        summary = text[:500].replace("\r\n", "\n").strip()

        _master_kb_index.append({
            "file": md_file.name,
            "title": title,
            "tags": tags,
            "summary": summary,
            "full_text": text,
        })

    return _master_kb_index


# =====================================================================
# 工具 1: 风格化剪辑知识库搜索
# =====================================================================
@mcp.tool()
def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """搜索风格化剪辑知识库 (262 个 md 文件)。

    返回匹配的效果映射、转场配方、风格配方、调色预设。

    Args:
        query: 搜索关键词 (如 "发光效果", "转场配方", "高燃混剪")
        max_results: 最大返回结果数 (默认 5)

    Returns:
        格式化的搜索结果
    """
    try:
        loader = _get_kb_loader()
        results = loader.search(query, max_results=max_results)
    except Exception as e:
        return f"搜索失败: {e}"

    if not results:
        return f"未找到与 \"{query}\" 相关的知识。"

    lines = [f"## 知识库搜索结果 (query=\"{query}\", {len(results)} 条)\n"]
    for i, r in enumerate(results, 1):
        type_label = {
            "effect": "效果",
            "transition": "转场",
            "style_recipe": "风格配方",
            "color_preset": "调色预设",
        }.get(r.get("type", ""), "知识")
        lines.append(f"### {i}. [{type_label}] {r['title']}")
        lines.append(f"相关度: {r.get('score', 0):.0%}")
        lines.append(f"内容: {r['content']}\n")

    return "\n".join(lines)


# =====================================================================
# 工具 2: 风格上下文生成
# =====================================================================
@mcp.tool()
def get_style_context(prompt: str) -> str:
    """根据剪辑提示词获取风格上下文 (效果推荐 + 转场推荐 + 风格配方 + 调色预设)。

    适合在剪辑前调用，获取风格参考。

    Args:
        prompt: 剪辑提示词 (如 "进击的巨人高燃混剪", "赛博朋克风格 MV")

    Returns:
        格式化的风格上下文，可直接参考
    """
    try:
        loader = _get_kb_loader()
        context = loader.get_style_context_for_prompt(prompt)
    except Exception as e:
        return f"获取风格上下文失败: {e}"

    if not context:
        return f"未找到与 \"{prompt}\" 相关的风格知识。"

    return f"## 风格上下文 (prompt=\"{prompt}\")\n\n{context}"


# =====================================================================
# 工具 3: 大师知识检索
# =====================================================================
@mcp.tool()
def search_master_knowledge(query: str, max_results: int = 3) -> str:
    """搜索大师知识库 (15 位剪辑大师的知识文件)。

    大师包括: Andrew Kramer (Video Copilot), Peter McKinnon, Casey Neistat,
    Jordy Vandeput, Ben Morris 等。

    Args:
        query: 搜索关键词 (如 "粒子", "3D合成", "VFX", "调色")
        max_results: 最大返回结果数 (默认 3)

    Returns:
        匹配的大师知识摘要
    """
    index = _ensure_master_index()
    if not index:
        return "大师知识库为空或目录不存在。"

    query_lower = query.lower()
    query_terms = set(query_lower.split())

    scored = []
    for entry in index:
        haystack = f"{entry['title']} {entry['tags']} {entry['summary']}".lower()
        score = sum(1 for t in query_terms if t in haystack)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_results]

    if not top:
        return f"未找到与 \"{query}\" 相关的大师知识。"

    lines = [f"## 大师知识检索 (query=\"{query}\", {len(top)} 条)\n"]
    for i, (score, entry) in enumerate(top, 1):
        lines.append(f"### {i}. {entry['title']}")
        lines.append(f"文件: {entry['file']}")
        if entry["tags"]:
            lines.append(f"标签: {entry['tags']}")
        lines.append(f"相关度: {score}/{len(query_terms)}")
        # 返回前 800 字摘要
        lines.append(f"\n{entry['summary'][:800]}\n")

    return "\n".join(lines)


# =====================================================================
# 工具 4: 列出知识库文件
# =====================================================================
@mcp.tool()
def list_knowledge_files(category: str = "all") -> str:
    """列出知识库中的文件。

    Args:
        category: 知识库类别
            - "style" = 10-风格化剪辑知识库 (262 个文件)
            - "master" = 11-大师知识库 (15 个文件)
            - "all" = 两者都列

    Returns:
        文件列表
    """
    result = []

    if category in ("style", "all"):
        kb_dir = Path(_KB_DIR)
        if kb_dir.is_dir():
            files = sorted(f.name for f in kb_dir.glob("*.md"))
            result.append(f"## 风格化剪辑知识库 ({len(files)} 个文件)\n")
            for f in files[:30]:
                result.append(f"- {f}")
            if len(files) > 30:
                result.append(f"- ... 还有 {len(files) - 30} 个文件")

    if category in ("master", "all"):
        index = _ensure_master_index()
        result.append(f"\n## 大师知识库 ({len(index)} 位大师)\n")
        for entry in index:
            tags = f" [{entry['tags']}]" if entry["tags"] else ""
            result.append(f"- {entry['title']}{tags} ({entry['file']})")

    return "\n".join(result) if result else "无文件。"


# =====================================================================
# 工具 5: 桥接状态监控
# =====================================================================
@mcp.tool()
def get_bridge_status() -> str:
    """获取 AE/PR 桥接状态。

    检查 After Effects 和 Premiere Pro 的 MCP Bridge 通信状态，
    包括最新命令、结果、连接状态。

    Returns:
        桥接状态报告
    """
    lines = ["## 桥接状态报告\n"]

    # --- AE Bridge ---
    lines.append("### After Effects Bridge")
    ae_dir = Path(_AE_BRIDGE_DIR)
    if ae_dir.is_dir():
        # 检查 trigger/command/result 文件
        trigger = ae_dir / "ae_trigger.json"
        command = ae_dir / "ae_command.json"
        result = ae_dir / "ae_result.json"
        log = ae_dir / "ae_auto_listener.log"

        if trigger.exists():
            try:
                t_data = json.loads(trigger.read_text(encoding="utf-8"))
                lines.append(f"- 最新触发: {json.dumps(t_data, ensure_ascii=False)[:200]}")
            except Exception:
                lines.append(f"- trigger 文件存在但解析失败")

        if command.exists():
            try:
                c_data = json.loads(command.read_text(encoding="utf-8"))
                lines.append(f"- 最新命令: {json.dumps(c_data, ensure_ascii=False)[:200]}")
            except Exception:
                lines.append(f"- command 文件存在但解析失败")

        if result.exists():
            try:
                r_data = json.loads(result.read_text(encoding="utf-8"))
                r_str = json.dumps(r_data, ensure_ascii=False)[:200]
                lines.append(f"- 最新结果: {r_str}")
            except Exception:
                lines.append(f"- result 文件存在但解析失败")

        if log.exists():
            try:
                log_text = log.read_text(encoding="utf-8", errors="replace")
                log_lines = log_text.strip().splitlines()
                if log_lines:
                    lines.append(f"- 监听日志最后 3 行:")
                    for ll in log_lines[-3:]:
                        lines.append(f"  `{ll[:120]}`")
            except Exception:
                pass
    else:
        lines.append("- AE Bridge 目录不存在")

    # --- PR Bridge ---
    lines.append("\n### Premiere Pro Bridge")
    pr_dir = Path(_PR_BRIDGE_DIR)
    if pr_dir.is_dir():
        # 关键状态文件
        status_files = {
            "bridge_ready.txt": "Bridge 就绪状态",
            "playhead_info.txt": "播放头位置",
            "clip_info.txt": "当前片段信息",
            "mcp_bridge_config.json": "Bridge 配置",
        }
        for fname, label in status_files.items():
            fpath = pr_dir / fname
            if fpath.exists():
                try:
                    if fname.endswith(".json"):
                        data = json.loads(fpath.read_text(encoding="utf-8"))
                        lines.append(f"- {label}: {json.dumps(data, ensure_ascii=False)[:200]}")
                    else:
                        text = fpath.read_text(encoding="utf-8", errors="replace").strip()
                        lines.append(f"- {label}: {text[:200]}")
                except Exception:
                    lines.append(f"- {label}: 文件存在但读取失败")

        # 最近日志
        startup_log = pr_dir / "fullauto_startup_log.txt"
        if startup_log.exists():
            try:
                log_text = startup_log.read_text(encoding="utf-8", errors="replace")
                log_lines = log_text.strip().splitlines()
                if log_lines:
                    lines.append(f"- 启动日志最后 3 行:")
                    for ll in log_lines[-3:]:
                        lines.append(f"  `{ll[:120]}`")
            except Exception:
                pass
    else:
        lines.append("- PR Bridge 目录不存在")

    return "\n".join(lines)


# =====================================================================
# 入口
# =====================================================================
if __name__ == "__main__":
    mcp.run()

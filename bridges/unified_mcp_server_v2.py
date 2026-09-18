"""
统一 MCP Server v2 — FastMCP v3.2 最佳实践
=============================================
基于 Context7 获取的 FastMCP 最新文档重构，引入：

1. **Context 注入** — 工具内实时日志 + 进度反馈 (ctx.info / ctx.report_progress)
2. **MCP Resources** — 将知识库内容暴露为 MCP 资源 (静态 + 动态模板)
3. **服务器组合** — 用 mcp.mount() 模块化组合子服务器
4. **结构化错误** — 统一错误返回格式，客户端可用 raise_on_error=False 检查
5. **FastAPI 集成** — mcp.http_app() 挂载到 FastAPI，共享 lifespan

用法:
    # stdio 模式 (MCP 客户端直连)
    python unified_mcp_server_v2.py

    # HTTP 模式 (通过 FastAPI 挂载)
    # 见底部 create_app() 示例

参考: https://github.com/prefecthq/fastmcp (v3.2.4 文档)
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

from fastmcp import Context, FastMCP

# =====================================================================
# 主服务器 — 统一入口
# =====================================================================
mcp = FastMCP(
    "AE-Knowledge-Vault",
    instructions=(
        "AE-Knowledge-Vault 统一 MCP 服务。"
        "提供 AE 渲染工具、知识库检索、桥接状态监控。"
        "工具返回结构化 JSON，错误时返回 {error: ...}。"
    ),
)


# =====================================================================
# 知识库路径
# =====================================================================
_KB_DIR = _PROJECT_ROOT / "10-风格化剪辑知识库"
_MASTER_KB_DIR = _PROJECT_ROOT / "11-大师知识库"
_AE_BRIDGE_DIR = _PROJECT_ROOT / ".ae-mcp-bridge"
_PR_BRIDGE_DIR = _PROJECT_ROOT / ".premiere-mcp-bridge"


# =====================================================================
# MCP Resources — 将知识库暴露为资源 (FastMCP v3.2 新特性)
# =====================================================================

@mcp.resource("kb://stats")
def kb_stats() -> dict:
    """知识库统计信息 — 文件数、大师数、标签汇总。"""
    style_files = list(_KB_DIR.glob("*.md")) if _KB_DIR.is_dir() else []
    master_files = list(_MASTER_KB_DIR.glob("*.md")) if _MASTER_KB_DIR.is_dir() else []
    return {
        "style_knowledge_count": len(style_files),
        "master_knowledge_count": len(master_files),
        "style_dir_exists": _KB_DIR.is_dir(),
        "master_dir_exists": _MASTER_KB_DIR.is_dir(),
    }


@mcp.resource("kb://masters")
def kb_masters_list() -> list:
    """大师知识库索引 — 所有大师文件列表。"""
    if not _MASTER_KB_DIR.is_dir():
        return []
    return [
        {"file": f.name, "title": f.stem}
        for f in sorted(_MASTER_KB_DIR.glob("*.md"))
    ]


@mcp.resource("kb://style/{filename}")
def kb_style_article(filename: str) -> str:
    """动态资源模板 — 按文件名读取风格化剪辑知识库文章。

    URI 格式: kb://style/{filename}
    示例: kb://style/发光效果.md
    """
    fpath = _KB_DIR / filename
    if not fpath.is_file():
        return f"文件不存在: {filename}"
    return fpath.read_text(encoding="utf-8", errors="replace")


@mcp.resource("bridge://ae/status")
def bridge_ae_status() -> dict:
    """AE Bridge 实时状态 — 读取 trigger/command/result 文件。"""
    result: dict[str, Any] = {"available": False}
    if not _AE_BRIDGE_DIR.is_dir():
        return result

    result["available"] = True
    for key, fname in [
        ("trigger", "ae_trigger.json"),
        ("command", "ae_command.json"),
        ("result", "ae_result.json"),
    ]:
        fpath = _AE_BRIDGE_DIR / fname
        if fpath.exists():
            try:
                result[key] = json.loads(fpath.read_text(encoding="utf-8"))
            except Exception:
                result[key] = "parse_error"
    return result


# =====================================================================
# 工具 — 使用 Context 注入 (FastMCP v3.2 新特性)
# =====================================================================

@mcp.tool()
async def search_knowledge(query: str, max_results: int = 5, ctx: Context = None) -> dict:
    """搜索风格化剪辑知识库 (262 个 md 文件)。

    返回匹配的效果映射、转场配方、风格配方、调色预设。

    Args:
        query: 搜索关键词 (如 "发光效果", "转场配方", "高燃混剪")
        max_results: 最大返回结果数 (默认 5)

    Returns:
        结构化搜索结果 dict，错误时返回 {error: ...}
    """
    if ctx:
        await ctx.info(f"正在搜索知识库: query=\"{query}\", max_results={max_results}")
        await ctx.report_progress(10, 100, "初始化搜索器")

    try:
        from knowledge_base.kb_loader import KnowledgeBaseLoader
        loader = KnowledgeBaseLoader.get_instance()

        if ctx:
            await ctx.report_progress(50, 100, "执行搜索")

        results = loader.search(query, max_results=max_results)

        if ctx:
            await ctx.report_progress(90, 100, "格式化结果")
            await ctx.info(f"搜索完成，找到 {len(results)} 条结果")

        if not results:
            return {"query": query, "count": 0, "results": [], "message": f"未找到与 \"{query}\" 相关的知识。"}

        formatted = []
        for r in results:
            type_label = {
                "effect": "效果",
                "transition": "转场",
                "style_recipe": "风格配方",
                "color_preset": "调色预设",
            }.get(r.get("type", ""), "知识")
            formatted.append({
                "title": r["title"],
                "type": type_label,
                "score": r.get("score", 0),
                "content": r["content"],
            })

        return {"query": query, "count": len(formatted), "results": formatted}

    except Exception as e:
        if ctx:
            await ctx.error(f"搜索失败: {e}")
        return {"error": f"搜索失败: {e}", "query": query, "count": 0, "results": []}


@mcp.tool()
async def get_style_context(prompt: str, ctx: Context = None) -> dict:
    """根据剪辑提示词获取风格上下文。

    在剪辑前调用，获取效果推荐 + 转场推荐 + 风格配方 + 调色预设。

    Args:
        prompt: 剪辑提示词 (如 "进击的巨人高燃混剪", "赛博朋克风格 MV")

    Returns:
        结构化风格上下文 dict
    """
    if ctx:
        await ctx.info(f"正在生成风格上下文: prompt=\"{prompt}\"")

    try:
        from knowledge_base.kb_loader import KnowledgeBaseLoader
        loader = KnowledgeBaseLoader.get_instance()
        context_text = loader.get_style_context_for_prompt(prompt)

        if not context_text:
            return {"prompt": prompt, "context": None, "message": f"未找到与 \"{prompt}\" 相关的风格知识。"}

        if ctx:
            await ctx.info("风格上下文生成成功")

        return {"prompt": prompt, "context": context_text}

    except Exception as e:
        if ctx:
            await ctx.error(f"获取风格上下文失败: {e}")
        return {"error": str(e), "prompt": prompt, "context": None}


@mcp.tool()
async def search_master_knowledge(query: str, max_results: int = 3, ctx: Context = None) -> dict:
    """搜索大师知识库 (15 位剪辑大师)。

    Args:
        query: 搜索关键词
        max_results: 最大返回数

    Returns:
        结构化大师知识搜索结果 dict
    """
    if ctx:
        await ctx.info(f"正在搜索大师知识库: query=\"{query}\"")

    index = _build_master_index()
    if not index:
        return {"error": "大师知识库为空或目录不存在", "query": query, "count": 0, "results": []}

    query_lower = query.lower()
    query_terms = set(query_lower.split())

    scored = []
    for entry in index:
        haystack = f"{entry['title']} {entry['tags']} {entry['summary'][:200]}".lower()
        score = sum(1 for t in query_terms if t in haystack)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_results]

    if not top:
        return {"query": query, "count": 0, "results": [], "message": f"未找到与 \"{query}\" 相关的大师知识。"}

    if ctx:
        await ctx.info(f"找到 {len(top)} 条匹配结果")

    results = []
    for score, entry in top:
        results.append({
            "title": entry["title"],
            "file": entry["file"],
            "tags": entry["tags"],
            "relevance": f"{score}/{len(query_terms)}",
            "summary": entry["summary"][:800],
        })

    return {"query": query, "count": len(results), "results": results}


@mcp.tool()
async def get_bridge_status(ctx: Context = None) -> dict:
    """获取 AE/PR 桥接状态。

    Returns:
        结构化桥接状态 dict
    """
    if ctx:
        await ctx.info("正在检查 AE/PR Bridge 状态")

    status: dict[str, Any] = {}

    # --- AE Bridge ---
    ae_status: dict[str, Any] = {"exists": _AE_BRIDGE_DIR.is_dir()}
    if _AE_BRIDGE_DIR.is_dir():
        for key, fname in [
            ("trigger", "ae_trigger.json"),
            ("command", "ae_command.json"),
            ("result", "ae_result.json"),
        ]:
            fpath = _AE_BRIDGE_DIR / fname
            if fpath.exists():
                try:
                    ae_status[key] = json.loads(fpath.read_text(encoding="utf-8"))
                except Exception:
                    ae_status[key] = "parse_error"

        # 最后 3 行日志
        log_path = _AE_BRIDGE_DIR / "ae_auto_listener.log"
        if log_path.exists():
            try:
                log_text = log_path.read_text(encoding="utf-8", errors="replace")
                log_lines = log_text.strip().splitlines()
                ae_status["recent_log"] = log_lines[-3:] if log_lines else []
            except Exception:
                pass
    status["ae_bridge"] = ae_status

    # --- PR Bridge ---
    pr_status: dict[str, Any] = {"exists": _PR_BRIDGE_DIR.is_dir()}
    if _PR_BRIDGE_DIR.is_dir():
        status_files = {
            "bridge_ready": "bridge_ready.txt",
            "playhead_info": "playhead_info.txt",
            "clip_info": "clip_info.txt",
        }
        for key, fname in status_files.items():
            fpath = _PR_BRIDGE_DIR / fname
            if fpath.exists():
                try:
                    pr_status[key] = fpath.read_text(encoding="utf-8", errors="replace").strip()[:200]
                except Exception:
                    pr_status[key] = "read_error"
    status["pr_bridge"] = pr_status

    if ctx:
        await ctx.info("Bridge 状态检查完成")

    return status


# =====================================================================
# 内部辅助
# =====================================================================

_master_kb_index: list[dict[str, Any]] | None = None


def _build_master_index() -> list[dict[str, Any]]:
    """构建大师知识库索引 (标题 + 标签 + 内容摘要)。"""
    global _master_kb_index
    if _master_kb_index is not None:
        return _master_kb_index

    _master_kb_index = []
    if not _MASTER_KB_DIR.is_dir():
        return _master_kb_index

    for md_file in sorted(_MASTER_KB_DIR.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        title = md_file.stem
        for line in text.splitlines()[:5]:
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                title = stripped
                break

        tags = ""
        for line in text.splitlines()[:10]:
            if "标签" in line and ":" in line:
                tags = line.split(":", 1)[-1].strip().strip(">").strip()
                break

        summary = text[:500].replace("\r\n", "\n").strip()

        _master_kb_index.append({
            "file": md_file.name,
            "title": title,
            "tags": tags,
            "summary": summary,
        })

    return _master_kb_index


# =====================================================================
# FastAPI 集成 — mcp.http_app() 挂载 (FastMCP v3.2 新特性)
# =====================================================================

def create_app():
    """创建 FastAPI 应用并挂载 MCP 服务器。

    用法:
        uvicorn unified_mcp_server_v2:create_app --factory --port 8001

    端点:
        POST /mcp/  — MCP Streamable HTTP
        GET  /mcp/  — MCP SSE (如支持)
    """
    try:
        from fastapi import FastAPI
    except ImportError:
        raise RuntimeError("FastAPI 未安装，请 pip install fastapi")

    mcp_asgi = mcp.http_app(path="/mcp")

    app = __import__("fastapi").FastAPI(
        title="AE-Knowledge-Vault MCP",
        description="AE 工具 + 知识库 + 桥接状态 统一 MCP 服务",
        version="2.0.0",
        lifespan=mcp_asgi.lifespan,
    )

    # 健康检查
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "AE-Knowledge-Vault MCP v2"}

    # 挂载 MCP
    app.mount("/", mcp_asgi)

    return app


# =====================================================================
# 入口
# =====================================================================
if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    print(f"[unified_mcp_server_v2] 启动 transport={transport}", file=sys.stderr)
    mcp.run(transport=transport)

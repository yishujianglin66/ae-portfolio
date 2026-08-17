#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bootstrap.py — AE-Knowledge-Vault 统一路径引导层
=================================================

解决项目代码"碎片化"导致的跨目录 import 失败问题：
  - ae_tools_mcp_server.py 依赖 rendering/ 下的模块（ae_render_engine 等）
  - web/api_server.py 依赖 tools/ 下的模块（batch_queue / logger / toolchain_api）

将各子模块目录统一注入 sys.path，使所有入口脚本都能 import 到彼此。

用法（在任意入口脚本顶部，确保项目根在 sys.path 后）：
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import bootstrap

本文件只做路径注入，不修改任何业务逻辑，不触碰架构红线文件
（after-effects-mcp/src/index.ts、mcp-bridge-auto.jsx）。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 项目根目录（bootstrap.py 所在的 AE-Knowledge-Vault）
PROJECT_ROOT = Path(__file__).resolve().parent

# 需要加入 sys.path 的子目录（相对项目根）。
# 集中维护在此，避免各 server 各自硬编码路径。
SUBDIRS = [
    ".",                             # 根目录（logger/exceptions/config_schema 等 py-modules）
    "web",
    "tools",
    "rendering",
    "ae",
    "core",
    "config",
    "puppet_effects",
    "performance",
    "vrs",
    "software_sdk",
    "effects",
    "video",
    "audio",
    "analysis",
    "scene",
    "learning",
    "compiler",
    "media",
    "integrations",
    "pipeline",
    "knowledge_base",
    "13-素材获取与搜索",
    "13-素材获取与搜索/03-AI语义搜索",
    "13-素材获取与搜索/02-免费素材API",
]

# 仅注入真实存在的目录，避免污染 sys.path
_INSERTED: list[str] = []
for _sub in SUBDIRS:
    _p = PROJECT_ROOT / _sub
    _abs = str(_p)
    if _p.is_dir() and _abs not in sys.path:
        sys.path.insert(0, _abs)
        _INSERTED.append(_abs)


def inserted_paths() -> list[str]:
    """返回本次注入成功的路径列表（调试用）。"""
    return list(_INSERTED)


if __name__ == "__main__":
    print(f"PROJECT_ROOT = {PROJECT_ROOT}")
    print(f"inserted {len(_INSERTED)} path(s):")
    for _p in _INSERTED:
        print(f"  + {_p}")

"""API 启动包装脚本。

直接运行 api/main.py 时相对导入会报错（attempted relative import beyond top-level package），
因为此时 `api.main` 的 `__package__` 只有一层 'api'，无法 `..config`。
本脚本手动模拟包层级为 `src.api.main`（即设置 __package__ 并将 src 父目录加入 path），
使相对导入 `from ..config import settings` → 解析为 `from src.config import settings`。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent  # = puppet-automation/src
_PARENT = _THIS_DIR.parent  # = puppet-automation
_PROJECT_ROOT = _PARENT.parent  # = AE-Knowledge-Vault

# 顺序很重要：先让 Python 能 import 到 "src" 这个包（即把 _PARENT 加进去）
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
# 项目根也要加，便于 api/main.py 里自己写的 sys.path 逻辑不冲突
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 强制把当前文件模拟成 src._start_api（即便没有真正的父包）
# 这样 import src.api.main 时相对导入就能工作
__package__ = "src"  # noqa: A001 - allow shadowing builtin for package setup

from src.api.main import app  # noqa: E402 - import after path setup

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8765")),
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )

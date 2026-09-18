"""素材下载 Media API 端点。

将独立的 yt-dlp 素材下载子系统（此前游离于 FastAPI 之外）接入统一 HTTP 入口。
复用 ``13-素材获取与搜索/01-下载器/unified_downloader.py`` 的
``UnifiedDownloader`` 接口（自动识别抖音/B站/YouTube 并路由下载）。

端点：
- POST /api/v1/media/download   URL → 下载到素材目录并返回路径
- GET  /api/v1/media/list       列出已下载素材
- GET  /api/v1/media/status     下载器可用性 + 下载任务状态

设计说明：
- 下载器依赖外部命令/库（yt-dlp、httpx 等），不可用时端点 graceful 返回
  可用性状态（503 + 明确原因），而非 500。
- 下载为同步阻塞操作，通过 ``asyncio.to_thread`` 放到线程池执行，避免
  阻塞 FastAPI 事件循环。
- 任务状态保存在进程内内存注册表（重启即清空），与 unified_downloader
  自身"每次调用即完成任务"的同步语义一致。
"""
from __future__ import annotations

import asyncio
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["media"])

# ── 项目根录（unified_downloader 位于根目录下的下载器子模块） ──
PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
DOWNLOADER_DIR = PROJECT_ROOT / "13-素材获取与搜索" / "01-下载器"

# 默认素材下载目录（可通过 output_dir 覆盖）
DEFAULT_MEDIA_DIR = PROJECT_ROOT / "media" / "downloads"

# 支持的下载扩展名（用于 list 过滤）
_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".flv",
    ".webm",
    ".m4a",
    ".mp3",
    ".wav",
    ".aac",
    ".flac",
}

# ── 进程内任务注册表 ──
_TASKS: dict[str, dict[str, Any]] = {}
_TASKS_LOCK = threading.Lock()


# ============================================================
#  下载器加载与可用性探测
# ============================================================


def _ensure_downloader_dir_in_path() -> None:
    """将下载器目录加入 sys.path，保证 import unified_downloader 可用。"""
    if str(DOWNLOADER_DIR) not in sys.path:
        sys.path.insert(0, str(DOWNLOADER_DIR))


def _get_unified_downloader():
    """加载统一的 yt-dlp 下载器实例；失败返回 None（不抛异常）。"""
    _ensure_downloader_dir_in_path()
    try:
        from unified_downloader import UnifiedDownloader

        return UnifiedDownloader()
    except Exception as e:
        logger.warning(f"[media] unified_downloader 加载失败: {e}")
        return None


def _check_capabilities() -> dict[str, Any]:
    """探测下载器及依赖可用性，用于 /status graceful 展示。"""
    caps: dict[str, Any] = {}

    _ensure_downloader_dir_in_path()

    # unified_downloader 模块本身
    try:
        import unified_downloader  # noqa: F401

        caps["unified_downloader"] = True
    except Exception:
        caps["unified_downloader"] = False

    # yt-dlp（bilibili / youtube 平台依赖）
    try:
        import yt_dlp  # noqa: F401

        caps["yt_dlp"] = True
    except Exception:
        caps["yt_dlp"] = False

    # httpx（抖音平台依赖）
    try:
        import httpx  # noqa: F401

        caps["httpx"] = True
    except Exception:
        caps["httpx"] = False

    # 各平台专用下载器能否加载
    caps["platforms"] = {}
    if caps["unified_downloader"]:
        try:
            from unified_downloader import _ModuleLoader

            for platform in ("douyin", "bilibili", "youtube"):
                try:
                    if platform == "douyin":
                        _, err = _ModuleLoader.get_douyin_downloader()
                    elif platform == "bilibili":
                        _, err = _ModuleLoader.get_bilibili_downloader()
                    else:
                        _, err = _ModuleLoader.get_youtube_downloader()
                    caps["platforms"][platform] = err is None
                except Exception as exc:
                    caps["platforms"][platform] = f"error: {exc}"
        except Exception as exc:
            logger.warning(f"[media] 平台能力探测失败: {exc}")

    return caps


def _downloader_available() -> bool:
    """统一下载器是否可实例化。"""
    return _get_unified_downloader() is not None


# ============================================================
#  任务注册表
# ============================================================


def _register_task(url: str, **extra: Any) -> str:
    """登记一个下载任务，返回 task_id。"""
    task_id = uuid.uuid4().hex[:12]
    with _TASKS_LOCK:
        _TASKS[task_id] = {
            "task_id": task_id,
            "url": url,
            "status": "running",
            "start_time": time.time(),
            "end_time": None,
            "result": None,
            "error": None,
            **extra,
        }
    return task_id


def _finish_task(task_id: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
    """标记任务完成（成功或失败）。"""
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        task["status"] = "failed" if (error or (result and not result.get("success", False))) else "completed"
        task["end_time"] = time.time()
        task["result"] = result
        task["error"] = error


def _list_tasks() -> list[dict[str, Any]]:
    """返回全部任务（按创建时间倒序）。"""
    with _TASKS_LOCK:
        tasks = list(_TASKS.values())
    tasks.sort(key=lambda t: t.get("start_time", 0), reverse=True)
    return tasks


# ============================================================
#  请求模型
# ============================================================


class MediaDownloadRequest(BaseModel):
    """素材下载请求体。"""

    url: str = Field(..., min_length=1, description="视频 URL（抖音/B站/YouTube）")
    output_dir: str | None = Field(None, description="输出目录，默认使用素材目录")
    audio_only: bool = Field(False, description="是否仅下载音频")
    quality: str = Field("1080p", description="画质（用于视频下载）")


# ============================================================
#  端点
# ============================================================


@router.get("/media/status")
async def media_status(
    task_id: str | None = Query(None, description="按 task_id 查询单个任务状态"),
):
    """查询素材下载器的可用性、依赖能力及下载任务状态。

    下载器依赖外部命令/库（yt-dlp、httpx 等），此端点始终返回 200，
    用 ``available`` / ``capabilities`` 字段描述可用性，供前端 graceful 展示。
    """
    capabilities = _check_capabilities()
    available = capabilities.get("unified_downloader", False)

    if task_id:
        with _TASKS_LOCK:
            task = _TASKS.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"下载任务 '{task_id}' 不存在")
        return {"success": True, "available": available, "task": task}

    return {
        "success": True,
        "available": available,
        "default_media_dir": str(DEFAULT_MEDIA_DIR),
        "capabilities": capabilities,
        "task_summary": {
            "total": len(_list_tasks()),
            "running": sum(1 for t in _list_tasks() if t["status"] == "running"),
            "completed": sum(1 for t in _list_tasks() if t["status"] == "completed"),
            "failed": sum(1 for t in _list_tasks() if t["status"] == "failed"),
        },
        "tasks": _list_tasks(),
    }


@router.post("/media/download")
async def media_download(req: MediaDownloadRequest):
    """下载素材到素材目录并返回路径。

    复用 ``UnifiedDownloader.download()`` 自动识别平台并路由：
    - 抖音 → httpx 直连 API
    - B站 / YouTube → yt-dlp

    下载器不可用时返回 503（graceful 可用性状态），而非 500。
    """
    downloader = _get_unified_downloader()
    if downloader is None:
        capabilities = _check_capabilities()
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "MEDIA_DOWNLOADER_UNAVAILABLE",
                "message": "素材下载器不可用（依赖缺失），请检查 yt-dlp / httpx 等依赖",
                "capabilities": capabilities,
            },
        )

    output_dir = req.output_dir or str(DEFAULT_MEDIA_DIR)
    resolved_out = Path(output_dir).resolve()
    try:
        resolved_out.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="输出目录不在项目根目录下")
    output_dir = str(resolved_out)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    task_id = _register_task(req.url, output_dir=output_dir, audio_only=req.audio_only)

    try:
        result = await asyncio.to_thread(
            downloader.download,
            req.url,
            output_dir=output_dir,
            audio_only=req.audio_only,
            quality=req.quality,
        )
    except Exception as e:
        logger.exception(f"[media] 下载任务异常 task_id={task_id}: {e}")
        _finish_task(task_id, error=f"下载过程异常: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "MEDIA_DOWNLOAD_ERROR",
                "message": f"素材下载失败: {e}",
                "task_id": task_id,
            },
        )

    # 记录任务终态
    _finish_task(task_id, result=result)

    if not result.get("success", False):
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": "MEDIA_DOWNLOAD_FAILED",
                "message": result.get("error", "下载失败"),
                "task_id": task_id,
                "platform": result.get("platform"),
            },
        )

    return {
        "success": True,
        "task_id": task_id,
        "file_path": result.get("file_path"),
        "title": result.get("title"),
        "author": result.get("author"),
        "duration": result.get("duration"),
        "platform": result.get("platform"),
        "output_dir": output_dir,
    }


@router.get("/media/list")
async def media_list(
    output_dir: str | None = Query(None, description="素材目录，默认使用默认素材目录"),
    extension: str | None = Query(None, description="按扩展名过滤，如 .mp4"),
    limit: int = Query(200, ge=1, le=1000, description="返回条数上限"),
):
    """列出已下载素材（默认素材目录及其子目录下）。"""
    base_dir = Path(output_dir).resolve() if output_dir else DEFAULT_MEDIA_DIR
    if output_dir:
        try:
            base_dir.relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="素材目录不在项目根目录下")
    if not base_dir.exists():
        return {"success": True, "base_dir": str(base_dir), "total": 0, "files": []}

    files: list[dict[str, Any]] = []
    for p in base_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _MEDIA_EXTENSIONS:
            continue
        if extension and p.suffix.lower() != extension.lower():
            continue
        try:
            stat = p.stat()
            files.append(
                {
                    "path": str(p),
                    "name": p.name,
                    "extension": p.suffix.lower(),
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": int(stat.st_mtime),
                }
            )
        except OSError:
            continue

    files.sort(key=lambda f: f["modified"], reverse=True)
    files = files[:limit]
    return {
        "success": True,
        "base_dir": str(base_dir),
        "total": len(files),
        "files": files,
    }
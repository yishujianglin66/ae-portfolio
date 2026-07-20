"""FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from ..config import settings

_security = HTTPBearer(auto_error=False)

WEAK_TOKENS = {"", "change-me-in-production", "dev-token-change-me", "default-token"}


def require_mcp_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> bool:
    """Puppet Automation API Bearer Token 认证。

    安全策略：
    - 生产环境必须设置有效 MCP_AUTH_TOKEN，否则 503。
    - 开发环境默认值时警告但允许（便于本地开发）。
    - 配置了自定义 token 时必须匹配。
    """
    token = credentials.credentials if credentials else ""
    configured = settings.mcp_auth_token

    if settings.env == "production":
        if configured in WEAK_TOKENS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="生产环境必须配置 MCP_AUTH_TOKEN",
            )
        if not token or token != configured:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return True

    if configured in WEAK_TOKENS:
        logger.warning(
            "Puppet API 使用默认认证令牌，仅限开发环境。生产环境请设置 MCP_AUTH_TOKEN。"
        )
        return True
    if token != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True

from ..engines.ae import AEEngine
from ..engines.ffmpeg import FFmpegEngine
from ..engines.topaz import TopazEngine
from ..engines.silhouette import SilhouetteEngine
from ..engines.blender import BlenderEngine
from ..engines.davinci import DavinciEngine
from ..engines.media_encoder import MediaEncoderEngine
from ..mcp_gateway import mcp_router, initialize_gateway, mcp_registry
from ..orchestrator import PipelineOrchestrator
from ..models.pipeline import PipelineJob, PuppetStyle, VideoMetadata
from ..ai_planner import AIPlanner


class _ConfigService:
    """Configuration wrapper for MCP tool access."""

    def __init__(self, settings_obj):
        self._settings = settings_obj

    def get_safe_config(self):
        """Get safe configuration (secrets masked)."""
        import re
        from pathlib import Path

        result = {}
        for key, val in self._settings.model_dump().items():
            if isinstance(val, Path):
                result[key] = str(val)
            elif isinstance(val, str) and any(kw in key.lower() for kw in ["key", "token", "secret", "password"]):
                result[key] = "***" if val else ""
            else:
                result[key] = val
        return result

    def get_resource_paths(self):
        """Get all resource directory paths."""
        paths = {}
        for key, val in self._settings.model_dump().items():
            if key.endswith("_dir") or key.endswith("_path"):
                paths[key] = str(val)
        return paths


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("Starting Puppet Automation Pipeline...")
    settings.ensure_dirs()

    # Initialize engines (fail-safe: skip unavailable ones)
    engines = {}
    engine_classes = {
        "ffmpeg": FFmpegEngine,
        "ae": AEEngine,
        "topaz": TopazEngine,
        "silhouette": SilhouetteEngine,
        "blender": BlenderEngine,
        "davinci": DavinciEngine,
        "media_encoder": MediaEncoderEngine,
    }
    for name, cls in engine_classes.items():
        try:
            engines[name] = cls()
            logger.info(f"Engine [{name}] initialized")
        except Exception as e:
            logger.warning(f"Engine [{name}] failed to init: {e}")

    # Initialize ComfyUI engine (HTTP-based, always instantiable)
    try:
        from ..engines.comfyui import ComfyUIEngine, WorkflowManager
        comfyui_engine = ComfyUIEngine(
            base_url=settings.comfyui_base_url,
            output_dir=settings.comfyui_output_dir,
            input_dir=settings.comfyui_input_dir,
            timeout=settings.comfyui_timeout,
        )
        engines["comfyui"] = comfyui_engine
        wf_mgr = WorkflowManager(
            engine=comfyui_engine,
            workflows_dir=settings.comfyui_workflows_dir,
        )
        app.state.comfyui_engine = comfyui_engine
        app.state.wf_manager = wf_mgr
        logger.info(f"Engine [comfyui] initialized (url={settings.comfyui_base_url})")
    except Exception as e:
        logger.warning(f"Engine [comfyui] failed to init: {e}")
        app.state.comfyui_engine = None
        app.state.wf_manager = None

    app.state.engines = engines
    logger.info(f"Initialized {len(engines)}/{len(engine_classes)} engines")

    # Initialize Pipeline Orchestrator
    orchestrator = PipelineOrchestrator(engines)
    app.state.orchestrator = orchestrator
    logger.info("Pipeline Orchestrator initialized")

    # Initialize AI Planner
    ai_planner = AIPlanner()
    app.state.ai_planner = ai_planner
    logger.info("AI Planner initialized")

    # Initialize AI Planner Service (LLM 网关-backed 意图解析)
    try:
        from ..services.ai_planner import AIPlannerService
        app.state.ai_planner_service = AIPlannerService()
        logger.info("AI Planner Service initialized (via LLM gateway)")
    except Exception as e:
        logger.warning(f"AI Planner Service init failed: {e}")
        app.state.ai_planner_service = None

    # Initialize Resource Monitor (psutil-based, fail-safe)
    try:
        from ..services.resource_monitor import ResourceMonitorService
        from ..services.webhook_notifier import create_notifier_from_settings
        # 根据 settings.webhook_enabled 决定是否创建 notifier
        notifier = create_notifier_from_settings(settings)
        if notifier is not None:
            logger.info(
                f"Webhook notifier enabled: platform={notifier.platform} "
                f"host={notifier.hostname} quiet_minutes={notifier.quiet_minutes}"
            )
        else:
            logger.info("Webhook notifier disabled (webhook_enabled=false or url missing)")
        resource_monitor = ResourceMonitorService(
            interval=5.0,
            notifier=notifier,
            sustained_thresholds={
                "cpu_percent": settings.alert_cpu_threshold,
                "memory_percent": settings.alert_memory_threshold,
                "disk_percent": settings.alert_disk_threshold,
            },
            sustained_seconds={
                "cpu_percent": settings.alert_cpu_sustained_seconds,
                "memory_percent": settings.alert_memory_sustained_seconds,
                "disk_percent": settings.alert_disk_sustained_seconds,
            },
        )
        app.state.resource_monitor = resource_monitor
        app.state.webhook_notifier = notifier
        await resource_monitor.start_monitoring()
        logger.info("Resource Monitor started (interval=5.0s)")
    except Exception as e:
        logger.warning(f"Resource Monitor init failed: {e}")
        app.state.resource_monitor = None
        app.state.webhook_notifier = None

    # Render progress parsers registry: job_id -> RenderProgressParser
    # 由 AEEngine 等执行器在启动 aerender 时主动注册，API 端点按 job_id 查询
    app.state.render_parsers = {}

    # Initialize Render Job Repository (SQLite 持久化)
    try:
        from ..services.render_repository import render_repository
        await render_repository.connect()
        app.state.render_repository = render_repository
        logger.info(
            f"RenderJobRepository connected (db={settings.render_db_path})"
        )

        # 启动恢复：清理因服务异常退出而卡住的任务
        if settings.render_auto_cleanup:
            stale_count = await render_repository.mark_stale_as_failed(
                stale_minutes=settings.render_stale_timeout_minutes
            )
            if stale_count > 0:
                logger.warning(
                    f"启动恢复: {stale_count} 个 stale 渲染任务已标记为 failed "
                    f"(timeout={settings.render_stale_timeout_minutes}min)"
                )

        # 查询仍处于活跃态的任务并记录日志（实际不自动恢复 aerender 进程）
        active_jobs = await render_repository.get_active_jobs()
        if active_jobs:
            logger.info(
                f"启动恢复: 检测到 {len(active_jobs)} 个活跃渲染任务（不自动重启 "
                f"aerender 进程，仅状态保留）："
            )
            for job in active_jobs[:10]:  # 仅打印前 10 条
                logger.info(
                    f"  - job_id={job.job_id} status={job.status} "
                    f"project={job.project_path} comp={job.comp_name}"
                )
            if len(active_jobs) > 10:
                logger.info(f"  ... 其余 {len(active_jobs) - 10} 个任务省略")
    except Exception as e:
        logger.warning(f"RenderJobRepository init failed: {e}")
        app.state.render_repository = None

    # Initialize AE high-level services (fail-safe: skip on init error)
    # 文字效果 / 插件封装 / 多段调色 / 音频绑定 — 仅实例化，不触发 AE 调用
    try:
        from ..services import (
            AEPluginService,
            AudioBindingService,
            ColorGradingService,
            TextEffectService,
        )
        # 复用已初始化的 AE 引擎，若不可用则按配置新建（仅实例化，不调用）
        ae_svc_engine = engines.get("ae") or AEEngine(settings.aerender_path)
        app.state.text_effect_service = TextEffectService(ae_engine=ae_svc_engine)
        app.state.ae_plugin_service = AEPluginService(ae_engine=ae_svc_engine)
        app.state.color_grading_service = ColorGradingService(ae_engine=ae_svc_engine)
        app.state.audio_binding_service = AudioBindingService(ae_engine=ae_svc_engine)
        logger.info("AE high-level services initialized (text/plugin/color/audio)")
    except Exception as e:
        logger.warning(f"AE high-level services init failed: {e}")
        app.state.text_effect_service = None
        app.state.ae_plugin_service = None
        app.state.color_grading_service = None
        app.state.audio_binding_service = None

    # Initialize Resource Index Service (统一资源索引 - P0 任务)
    # 提供 D:/AE-Work/resources/ 资源库的 find_font/find_lut/list_fonts 等 API
    # 供 AI 规划器注入提示词与引擎/服务查询资源使用
    try:
        from ..services.resource_index_service import resource_index_service
        app.state.resource_index_service = resource_index_service
        logger.info("Resource Index Service initialized (lazy scan on first query)")
    except Exception as e:
        logger.warning(f"Resource Index Service init failed: {e}")
        app.state.resource_index_service = None

    # Initialize MCP Gateway (after all engines & services are ready)
    mcp_services = {}
    if getattr(app.state, "resource_index_service", None):
        mcp_services["resource_index"] = app.state.resource_index_service
    if getattr(app.state, "ae_plugin_service", None):
        mcp_services["ae_plugin"] = app.state.ae_plugin_service
    mcp_services["config"] = _ConfigService(settings)

    gateway = initialize_gateway(engines, mcp_services)
    app.state.mcp_gateway = gateway
    logger.info(f"MCP Gateway: {len(gateway.tools)} tools, {len(gateway.engines)} engines, {len(mcp_services)} services")

    yield

    logger.info("Shutting down Puppet Automation Pipeline...")

    # Close Render Job Repository
    render_repo = getattr(app.state, "render_repository", None)
    if render_repo is not None:
        try:
            await render_repo.close()
            logger.info("RenderJobRepository closed")
        except Exception as e:  # pragma: no cover - 关闭流程兜底
            logger.warning(f"RenderJobRepository close error: {e}")

    # Stop Resource Monitor
    monitor = getattr(app.state, "resource_monitor", None)
    if monitor is not None:
        try:
            monitor.stop_monitoring()
            logger.info("Resource Monitor stopped")
        except Exception as e:  # pragma: no cover - 关闭流程兜底
            logger.warning(f"Resource Monitor stop error: {e}")


app = FastAPI(
    title="Puppet Video Automation Pipeline",
    description="Multi-engine orchestration for puppet-style video production",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "PUPPET_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "env": settings.env,
        "engines": list(app.state.engines.keys()),
    }


@app.get("/api/v1/engines")
async def list_engines():
    """List all registered engines and their status."""
    engines_info = []
    for name, engine in app.state.engines.items():
        info = {"name": name}
        if hasattr(engine, "executable_path"):
            info["executable"] = str(engine.executable_path)
            info["available"] = engine.executable_path.exists()
        elif hasattr(engine, "base_url"):
            info["url"] = engine.base_url
            info["available"] = None  # HTTP engine, needs async check
        else:
            info["available"] = False
        engines_info.append(info)
    return {"engines": engines_info}


@app.post("/api/v1/engines/{engine_name}/execute")
async def execute_engine(
    engine_name: str,
    action: str,
    params: dict,
    _auth: bool = Depends(require_mcp_auth),
):
    """Execute an action on a specific engine."""
    if engine_name not in app.state.engines:
        raise HTTPException(status_code=404, detail=f"Engine '{engine_name}' not found")

    engine = app.state.engines[engine_name]
    result = await engine.execute(action=action, **params)
    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
    }


# ---- MCP Gateway ----
app.include_router(mcp_router)


# ---- Resource Index Service (P0 任务：统一资源索引) ----
@app.get("/api/v1/resources/summary")
async def get_resource_summary():
    """获取资源索引摘要（各类别资源数量）。

    首次调用会触发资源库扫描，可能耗时几秒到几十秒。
    """
    svc = app.state.resource_index_service
    if svc is None:
        raise HTTPException(status_code=503, detail="Resource Index Service not available")
    await svc._ensure_initialized()
    summary = svc.get_index_summary()
    return {
        "total": svc.get_total_count(),
        "categories": summary,
        "initialized": svc.is_initialized(),
    }


@app.post("/api/v1/resources/refresh")
async def refresh_resource_index(
    _auth: bool = Depends(require_mcp_auth),
):
    """刷新资源索引（重新扫描资源库）。"""
    svc = app.state.resource_index_service
    if svc is None:
        raise HTTPException(status_code=503, detail="Resource Index Service not available")
    await svc.refresh_index()
    return {
        "status": "refreshed",
        "total": svc.get_total_count(),
        "categories": svc.get_index_summary(),
    }


@app.get("/api/v1/resources/{category}")
async def list_resources(
    category: str,
    limit: int = 100,
    offset: int = 0,
):
    """列出指定类别的资源清单。

    Args:
        category: 资源类别（fonts/luts/effects/psd/audio/video/models/davinci/premiere/projects）
        limit: 返回数量上限（默认 100，最大 500）
        offset: 分页偏移量
    """
    svc = app.state.resource_index_service
    if svc is None:
        raise HTTPException(status_code=503, detail="Resource Index Service not available")
    valid_categories = {
        "fonts", "luts", "effects", "psd", "audio",
        "video", "models", "davinci", "premiere", "projects",
    }
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Valid: {sorted(valid_categories)}",
        )
    limit = max(1, min(limit, 500))
    items = await svc.list_resources_by_type(category, limit, offset)
    return {
        "category": category,
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@app.get("/api/v1/resources/{category}/find")
async def find_resource(
    category: str,
    name: str,
    exact: bool = False,
):
    """按名称查找资源文件路径。

    Args:
        category: 资源类别
        name: 资源名称（文件名，可不含扩展名）
        exact: 是否精确匹配（默认模糊匹配）
    """
    svc = app.state.resource_index_service
    if svc is None:
        raise HTTPException(status_code=503, detail="Resource Index Service not available")
    path = await svc.find_resource(category, name, exact)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Resource '{name}' not found in '{category}'")
    return {
        "category": category,
        "name": name,
        "found": True,
        "path": str(path),
    }


# ---- Pipeline Orchestration ----
@app.post("/api/v1/pipeline/jobs", status_code=201)
async def create_pipeline_job(
    job: PipelineJob,
    _auth: bool = Depends(require_mcp_auth),
):
    """Create a new pipeline job and start execution."""
    orch: PipelineOrchestrator = app.state.orchestrator
    job_id = orch.start_job_async(job)
    state = orch.get_state(job_id)
    return {"job_id": job_id, "state": state.model_dump()}


@app.get("/api/v1/pipeline/jobs")
async def list_pipeline_jobs():
    """List all pipeline jobs."""
    orch: PipelineOrchestrator = app.state.orchestrator
    jobs = orch.list_jobs()
    return {"jobs": [j.model_dump() for j in jobs]}


@app.get("/api/v1/pipeline/jobs/{job_id}")
async def get_pipeline_job(job_id: str):
    """Get status of a specific pipeline job."""
    from fastapi import HTTPException
    orch: PipelineOrchestrator = app.state.orchestrator
    state = orch.get_state(job_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"job_id": job_id, "state": state.model_dump()}


@app.post("/api/v1/pipeline/jobs/{job_id}/cancel")
async def cancel_pipeline_job(
    job_id: str,
    _auth: bool = Depends(require_mcp_auth),
):
    """Cancel a running pipeline job."""
    orch: PipelineOrchestrator = app.state.orchestrator
    success = orch.cancel_job(job_id)
    return {"job_id": job_id, "cancelled": success}


@app.post("/api/v1/pipeline/run")
async def run_pipeline_sync(
    job: PipelineJob,
    _auth: bool = Depends(require_mcp_auth),
):
    """Run a pipeline job synchronously and return full result."""
    orch: PipelineOrchestrator = app.state.orchestrator
    state = await orch.run_pipeline(job)
    return {"job_id": job.job_id, "state": state.model_dump()}


# ---- AI Planner ----
@app.post("/api/v1/ai/plan")
async def ai_plan(
    user_query: str,
    video_path: str,
    _auth: bool = Depends(require_mcp_auth),
):
    """Generate a pipeline plan from natural language query."""
    from fastapi import HTTPException
    from core.llm_gateway import LLMUnavailableError
    planner: AIPlanner = app.state.ai_planner
    try:
        result = await planner.plan_from_query(user_query, video_path)
        return {
            "job": result.job.model_dump(),
            "style_recommendation": (
                {
                    "primary_style": result.style_recommendation.primary_style.value,
                    "alternatives": [s.value for s in result.style_recommendation.alternatives],
                    "confidence": result.style_recommendation.confidence,
                    "reasoning": result.style_recommendation.reasoning,
                    "style_tips": result.style_recommendation.style_tips,
                }
                if result.style_recommendation else None
            ),
            "optimized_params": (
                {
                    "recommended_resolution": list(result.optimized_params.recommended_resolution),
                    "recommended_fps": result.optimized_params.recommended_fps,
                    "recommended_quality": result.optimized_params.recommended_quality,
                    "enable_topaz": result.optimized_params.enable_topaz,
                    "enable_silhouette_roto": result.optimized_params.enable_silhouette_roto,
                    "enable_3d_stage": result.optimized_params.enable_3d_stage,
                    "enable_color_grade": result.optimized_params.enable_color_grade,
                    "estimated_processing_time_minutes": result.optimized_params.estimated_processing_time_minutes,
                    "optimization_notes": result.optimized_params.optimization_notes,
                }
                if result.optimized_params else None
            ),
            "explanation": result.explanation,
            "reasoning": result.reasoning,
        }
    except LLMUnavailableError as e:
        # LLM 网关不可用 — 返回 503 让客户端感知降级
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM 服务不可用: {e}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI planning failed: {e}")


@app.post("/api/v1/ai/parse-intent")
async def ai_parse_intent(
    user_query: str,
    video_path: str = "",
    _auth: bool = Depends(require_mcp_auth),
):
    """通过 LLM 网关解析自然语言指令为结构化参数。

    返回 ``{"intent": str, "params": dict, "raw_response": str}``。
    LLM 不可用时返回 503。
    """
    from fastapi import HTTPException
    from core.llm_gateway import LLMUnavailableError

    service = getattr(app.state, "ai_planner_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Planner Service 未初始化",
        )

    try:
        result = await service.plan(user_query, video_path=video_path)
        return result
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM 服务不可用: {e}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intent parsing failed: {e}")


@app.post("/api/v1/ai/recommend-style")
async def ai_recommend_style(
    video_path: str = "",
    user_preferences: str = "",
):
    """Recommend puppet style based on video and preferences."""
    from fastapi import HTTPException
    planner: AIPlanner = app.state.ai_planner
    try:
        rec = await planner.recommend_style(video_path, user_preferences=user_preferences)
        return {
            "primary_style": rec.primary_style.value,
            "alternatives": [s.value for s in rec.alternatives],
            "confidence": rec.confidence,
            "reasoning": rec.reasoning,
            "style_tips": rec.style_tips,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Style recommendation failed: {e}")


@app.get("/api/v1/ai/styles")
async def list_puppet_styles():
    """List all available puppet styles."""
    styles = {
        PuppetStyle.WOODEN.value: "木质木偶 - 温暖棕色调，关节分明，经典童话感",
        PuppetStyle.STOP_MOTION.value: "定格动画 - 低帧率，黏土质感，创意艺术表达",
        PuppetStyle.MINIATURE.value: "微缩模型 - 浅景深，工作室打光，小人国效果",
        PuppetStyle.CLAY.value: "黏土风格 - 次表面散射，柔和色彩，可爱治愈",
        PuppetStyle.SHADOW.value: "皮影风格 - 剪影效果，背光打亮，传统艺术",
        PuppetStyle.PAPER.value: "纸艺剪纸 - 分层效果，扁平化打光，清新文艺",
        PuppetStyle.VOXEL.value: "体素风格 - 像素化方块感，有限调色板，游戏感",
        PuppetStyle.HANDLE.value: "提线木偶 - 可见控制杆和线，舞台剧感，经典马戏",
    }
    return {"styles": styles}


@app.post("/api/v1/ai/plan-and-run")
async def ai_plan_and_run(
    user_query: str,
    video_path: str,
    _auth: bool = Depends(require_mcp_auth),
):
    """Generate a plan from query and run the pipeline immediately."""
    from fastapi import HTTPException
    from core.llm_gateway import LLMUnavailableError
    planner: AIPlanner = app.state.ai_planner
    orch: PipelineOrchestrator = app.state.orchestrator
    try:
        result = await planner.plan_from_query(user_query, video_path)
        job_id = orch.start_job_async(result.job)
        return {
            "job_id": job_id,
            "explanation": result.explanation,
            "style": result.job.style.value,
            "quality": result.job.quality_preset,
        }
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM 服务不可用: {e}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI plan and run failed: {e}")


# ---- ComfyUI ----

from fastapi import UploadFile, File, Body
from pydantic import BaseModel
from typing import Optional


class WorkflowUploadRequest(BaseModel):
    """Request body for uploading a custom workflow."""
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = "user"
    style: Optional[str] = None
    workflow: dict  # ComfyUI prompt JSON


class WorkflowExecuteRequest(BaseModel):
    """Request body for executing a workflow."""
    workflow_name: str
    params: Optional[dict] = None
    output_dir: Optional[str] = None


@app.get("/api/v1/comfyui/status")
async def comfyui_server_status():
    """Check if ComfyUI server is reachable and get system stats."""
    from fastapi import HTTPException
    engine = app.state.comfyui_engine
    if not engine:
        raise HTTPException(status_code=503, detail="ComfyUI engine not initialized")

    available = await engine.is_available(force_check=True)
    if not available:
        return {"available": False, "base_url": engine.base_url}

    try:
        stats = await engine.get_system_stats()
        queue = await engine.get_queue()
        return {
            "available": True,
            "base_url": engine.base_url,
            "system_stats": stats,
            "queue": queue,
        }
    except Exception as e:
        return {"available": True, "base_url": engine.base_url, "error": str(e)}


@app.get("/api/v1/comfyui/workflows")
async def list_comfyui_workflows(category: Optional[str] = None):
    """List all available ComfyUI workflows (builtin + user)."""
    wf_mgr = app.state.wf_manager
    if not wf_mgr:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Workflow manager not initialized")

    workflows = wf_mgr.list_workflows(category=category)
    return {
        "total": len(workflows),
        "workflows": [
            {
                "name": w.name,
                "display_name": w.display_name,
                "description": w.description,
                "category": w.category,
                "style": w.style,
                "builtin": w.builtin,
            }
            for w in workflows
        ],
    }


@app.get("/api/v1/comfyui/workflows/{name}")
async def get_comfyui_workflow(name: str):
    """Get a specific workflow JSON by name."""
    from fastapi import HTTPException
    wf_mgr = app.state.wf_manager
    if not wf_mgr:
        raise HTTPException(status_code=503, detail="Workflow manager not initialized")

    workflow = wf_mgr.get_workflow(name)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")

    # Get metadata
    infos = wf_mgr.list_workflows()
    info = next((w for w in infos if w.name == name), None)

    return {
        "name": name,
        "display_name": info.display_name if info else name,
        "description": info.description if info else "",
        "category": info.category if info else "unknown",
        "style": info.style if info else None,
        "builtin": info.builtin if info else False,
        "workflow": workflow,
    }


@app.post("/api/v1/comfyui/workflows")
async def upload_comfyui_workflow(
    req: WorkflowUploadRequest,
    _auth: bool = Depends(require_mcp_auth),
):
    """Upload/save a custom ComfyUI workflow."""
    from fastapi import HTTPException
    wf_mgr = app.state.wf_manager
    if not wf_mgr:
        raise HTTPException(status_code=503, detail="Workflow manager not initialized")

    try:
        path = wf_mgr.save_workflow(
            name=req.name,
            workflow=req.workflow,
            metadata={
                "display_name": req.display_name or req.name,
                "description": req.description or "",
                "category": req.category or "user",
                "style": req.style,
            },
            overwrite=True,
        )
        return {
            "success": True,
            "name": req.name,
            "path": str(path),
            "message": f"Workflow '{req.name}' saved successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/comfyui/workflows/{name}")
async def delete_comfyui_workflow(
    name: str,
    _auth: bool = Depends(require_mcp_auth),
):
    """Delete a user workflow by name."""
    from fastapi import HTTPException
    wf_mgr = app.state.wf_manager
    if not wf_mgr:
        raise HTTPException(status_code=503, detail="Workflow manager not initialized")

    # Prevent deleting builtin workflows
    infos = wf_mgr.list_workflows()
    info = next((w for w in infos if w.name == name), None)
    if info and info.builtin:
        raise HTTPException(status_code=403, detail="Cannot delete built-in workflow")

    deleted = wf_mgr.delete_workflow(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found or cannot be deleted")

    return {"success": True, "name": name, "message": f"Workflow '{name}' deleted"}


@app.post("/api/v1/comfyui/execute")
async def execute_comfyui_workflow(
    req: WorkflowExecuteRequest,
    _auth: bool = Depends(require_mcp_auth),
):
    """Execute a ComfyUI workflow by name with optional parameters."""
    from fastapi import HTTPException
    wf_mgr = app.state.wf_manager
    if not wf_mgr:
        raise HTTPException(status_code=503, detail="Workflow manager not initialized")

    output_dir = Path(req.output_dir) if req.output_dir else None

    result = await wf_mgr.execute_workflow(
        workflow_name=req.workflow_name,
        params=req.params,
        output_dir=output_dir,
    )

    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
    }


@app.post("/api/v1/comfyui/upload-image")
async def comfyui_upload_image(
    file: UploadFile = File(...),
    _auth: bool = Depends(require_mcp_auth),
):
    """Upload an image to ComfyUI's input folder for use in workflows."""
    from fastapi import HTTPException
    engine = app.state.comfyui_engine
    if not engine:
        raise HTTPException(status_code=503, detail="ComfyUI engine not initialized")

    # Save uploaded file temporarily
    import tempfile
    tmp_path = Path(tempfile.gettempdir()) / file.filename
    content = await file.read()
    tmp_path.write_bytes(content)

    filename = await engine.upload_image(tmp_path)
    tmp_path.unlink(missing_ok=True)

    if not filename:
        raise HTTPException(status_code=500, detail="Failed to upload image to ComfyUI")

    return {
        "success": True,
        "filename": filename,
        "message": f"Image uploaded as '{filename}'",
    }


# ---- Audio Analysis ----
@app.post("/api/v1/audio/transcribe")
async def audio_transcribe(
    file: UploadFile = File(...),
    detect_speakers: bool = False,
    _auth: bool = Depends(require_mcp_auth),
):
    """Transcribe audio file using Whisper, optionally with speaker diarization."""
    from fastapi import HTTPException
    from ..services.audio_analysis import AudioAnalysisService

    try:
        import tempfile
        tmp_path = Path(tempfile.gettempdir()) / file.filename
        content = await file.read()
        tmp_path.write_bytes(content)

        service = AudioAnalysisService()
        result = await service.analyze_audio(tmp_path, detect_speakers=detect_speakers)
        tmp_path.unlink(missing_ok=True)

        return {
            "success": True,
            **result,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio transcription failed: {e}")


@app.post("/api/v1/audio/detect-speakers")
async def audio_detect_speakers(
    file: UploadFile = File(...),
    _auth: bool = Depends(require_mcp_auth),
):
    """Detect speakers in audio file using PyAnnote."""
    return await audio_transcribe(file, detect_speakers=True)


# ---- Scene Detection ----
@app.post("/api/v1/video/detect-scenes")
async def video_detect_scenes(
    file: UploadFile = File(...),
    threshold: float = 30.0,
    _auth: bool = Depends(require_mcp_auth),
):
    """Detect scenes in video using PySceneDetect."""
    from fastapi import HTTPException
    from ..services.scene_detection import SceneDetectionService

    try:
        import tempfile
        tmp_path = Path(tempfile.gettempdir()) / file.filename
        content = await file.read()
        tmp_path.write_bytes(content)

        service = SceneDetectionService()
        result = await service.detect_scenes(tmp_path, threshold=threshold)
        tmp_path.unlink(missing_ok=True)

        return {
            "success": True,
            **result,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scene detection failed: {e}")


@app.post("/api/v1/video/extract-keyframes")
async def video_extract_keyframes(
    file: UploadFile = File(...),
    scene_threshold: float = 30.0,
    _auth: bool = Depends(require_mcp_auth),
):
    """Extract keyframes from video scenes."""
    from fastapi import HTTPException
    from ..services.scene_detection import SceneDetectionService

    try:
        import tempfile
        tmp_path = Path(tempfile.gettempdir()) / file.filename
        content = await file.read()
        tmp_path.write_bytes(content)

        service = SceneDetectionService()
        result = await service.extract_keyframes(tmp_path, scene_threshold=scene_threshold)
        tmp_path.unlink(missing_ok=True)

        return {
            "success": True,
            **result,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Keyframe extraction failed: {e}")


# ============================================================
# After Effects - 高层操作 API
# ============================================================

@app.post("/api/v1/ae/comp/create")
async def ae_create_comp(
    name: str,
    width: int,
    height: int,
    fps: float,
    duration: float,
    project_path: Optional[str] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """创建 AE 合成。

    Args:
        name: 合成名称
        width: 宽度（像素）
        height: 高度（像素）
        fps: 帧率
        duration: 时长（秒）
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.create_comp(
        name=name,
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/footage/import")
async def ae_import_footage(
    footage_path: str,
    comp_name: Optional[str] = None,
    as_sequence: bool = False,
    position: Optional[int] = None,
    project_path: Optional[str] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """导入素材到 AE 项目。

    Args:
        footage_path: 素材文件路径
        comp_name: 目标合成名称（可选）
        as_sequence: 是否作为序列导入
        position: 在合成中的图层位置（1-based）
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.import_footage(
        footage_path=footage_path,
        comp_name=comp_name,
        as_sequence=as_sequence,
        position=position,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/layer/add")
async def ae_add_layer(
    comp_name: str,
    layer_type: str,
    name: str,
    position: Optional[int] = None,
    project_path: Optional[str] = None,
    params: Optional[dict] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """在合成中添加图层。

    Args:
        comp_name: 合成名称
        layer_type: 图层类型（solid, null, adjustment, text, shape）
        name: 图层名称
        position: 插入位置（1-based）
        project_path: 项目路径（可选）
        params: 其他参数（如 color, width, height）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    kwargs = params or {}
    result = await engine.add_layer(
        comp_name=comp_name,
        layer_type=layer_type,
        name=name,
        position=position,
        project_path=project_path,
        **kwargs,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/effect/add")
async def ae_add_effect(
    comp_name: str,
    layer_index: int,
    effect_name: str,
    params: Optional[dict] = None,
    project_path: Optional[str] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """为图层添加效果。

    Args:
        comp_name: 合成名称
        layer_index: 图层索引（1-based）
        effect_name: 效果匹配名
        params: 效果参数
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.add_effect(
        comp_name=comp_name,
        layer_index=layer_index,
        effect_name=effect_name,
        params=params,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/keyframes/set")
async def ae_set_keyframes(
    comp_name: str,
    layer_index: int,
    property_path: str,
    keyframes: List[dict],
    project_path: Optional[str] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """设置属性关键帧。

    Args:
        comp_name: 合成名称
        layer_index: 图层索引（1-based）
        property_path: 属性路径（如 "Transform/Position"）
        keyframes: 关键帧列表（time, value, easingType）
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.set_keyframes(
        comp_name=comp_name,
        layer_index=layer_index,
        property_path=property_path,
        keyframes=keyframes,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/preset/apply")
async def ae_apply_preset(
    comp_name: str,
    layer_index: int,
    preset_path: str,
    project_path: Optional[str] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """应用效果预设。

    Args:
        comp_name: 合成名称
        layer_index: 图层索引（1-based）
        preset_path: 预设文件路径（.ffx）
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.apply_preset(
        comp_name=comp_name,
        layer_index=layer_index,
        preset_path=preset_path,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "error": result.error,
    }


@app.post("/api/v1/ae/blend-mode/set")
async def ae_set_blend_mode(
    comp_name: str,
    layer_index: int,
    mode: str,
    project_path: Optional[str] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """设置图层混合模式。

    Args:
        comp_name: 合成名称
        layer_index: 图层索引（1-based）
        mode: 混合模式（SCREEN, MULTIPLY, ADD 等）
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.set_blend_mode(
        comp_name=comp_name,
        layer_index=layer_index,
        mode=mode,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/track-matte/set")
async def ae_set_track_matte(
    comp_name: str,
    layer_index: int,
    matte_type: str,
    project_path: Optional[str] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """设置轨道遮罩类型。

    Args:
        comp_name: 合成名称
        layer_index: 图层索引（1-based）
        matte_type: 遮罩类型（ALPHA_TRACK_MATTE, LUMA_TRACK_MATTE 等）
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.set_track_matte(
        comp_name=comp_name,
        layer_index=layer_index,
        matte_type=matte_type,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/adjustment-layer/add")
async def ae_add_adjustment_layer(
    comp_name: str,
    name: str,
    effects: Optional[List[dict]] = None,
    position: Optional[int] = None,
    project_path: Optional[str] = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """添加调整图层。

    Args:
        comp_name: 合成名称
        name: 图层名称
        effects: 效果列表（effectName, params）
        position: 插入位置（1-based）
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.add_adjustment_layer(
        comp_name=comp_name,
        name=name,
        effects=effects,
        position=position,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/render/segment")
async def ae_render_segment(
    comp_name: str,
    start_frame: int,
    end_frame: int,
    output_path: str,
    project_path: str,
    output_module: str = "H.264",
    render_settings: str = "Best Settings",
    _auth: bool = Depends(require_mcp_auth),
):
    """渲染合成片段。

    Args:
        comp_name: 合成名称
        start_frame: 起始帧
        end_frame: 结束帧
        output_path: 输出文件路径
        project_path: 项目路径
        output_module: 输出模块模板
        render_settings: 渲染设置模板
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.render_segment(
        comp_name=comp_name,
        start_frame=start_frame,
        end_frame=end_frame,
        output_path=output_path,
        project_path=project_path,
        output_module=output_module,
        render_settings=render_settings,
    )
    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
    }


# ============================================================
# Media Encoder - 交付编码
# ============================================================

@app.get("/api/v1/me/presets")
async def me_list_presets(_auth: bool = Depends(require_mcp_auth)):
    """列出所有 Media Encoder 平台预设。"""
    from ..engines.media_encoder import PLATFORM_PRESETS
    return {
        "presets": {
            k: {
                "name": v["name"],
                "resolution": f"{v['resolution'][0]}x{v['resolution'][1]}",
                "fps": v["fps"],
                "bitrate": v["bitrate"],
                "audio_bitrate": v["audio_bitrate"],
            }
            for k, v in PLATFORM_PRESETS.items()
        }
    }


@app.post("/api/v1/me/encode")
async def me_encode(
    file: UploadFile = File(...),
    platform: str = "douyin",
    _auth: bool = Depends(require_mcp_auth),
):
    """使用 Media Encoder 编码视频到指定平台格式。

    平台预设: douyin / bilili / youtube / xiaohongshu / wechat / master
    """
    import tempfile
    try:
        tmp_path = Path(tempfile.gettempdir()) / f"me_input_{file.filename}"
        content = await file.read()
        tmp_path.write_bytes(content)

        output_path = settings.output_dir / "me_encoded" / f"{file.stem}_{platform}.mp4"

        engine = MediaEncoderEngine()
        result = await engine.encode(
            input_path=tmp_path,
            output_path=output_path,
            platform=platform,
        )
        tmp_path.unlink(missing_ok=True)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "ME encode failed")

        return {
            "success": True,
            "output_path": str(result.output_path),
            "platform": platform,
            "metadata": result.metadata,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ME encode failed: {e}")


@app.post("/api/v1/me/batch")
async def me_batch_encode(
    input_dir: str,
    output_dir: str,
    platform: str = "douyin",
    _auth: bool = Depends(require_mcp_auth),
):
    """批量编码：将整个目录的视频用 ME 编码到指定平台格式。"""
    try:
        engine = MediaEncoderEngine()
        result = await engine.batch_encode(
            input_dir=input_dir,
            output_dir=output_dir,
            platform=platform,
        )
        return {
            "success": result.success,
            "total": result.metadata.get("total", 0),
            "success_count": result.metadata.get("success", 0),
            "failed_count": result.metadata.get("failed", 0),
            "results": result.metadata.get("results", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ME batch encode failed: {e}")


@app.post("/api/v1/me/watch-folder/add")
async def me_add_to_watch_folder(
    file: UploadFile = File(...),
    platform: str = "douyin",
    _auth: bool = Depends(require_mcp_auth),
):
    """将视频添加到 ME Watch Folder（异步处理，不等待完成）。"""
    import tempfile
    try:
        tmp_path = Path(tempfile.gettempdir()) / f"me_wf_{file.filename}"
        content = await file.read()
        tmp_path.write_bytes(content)

        engine = MediaEncoderEngine()
        result = await engine.add_to_watch_folder(
            input_path=tmp_path,
            platform=platform,
        )
        tmp_path.unlink(missing_ok=True)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "Add to watch folder failed")

        return {
            "success": True,
            "watch_folder": str(result.metadata.get("watch_folder")),
            "file": str(result.output_path),
            "platform": platform,
            "note": result.metadata.get("note", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Watch folder add failed: {e}")


# ============================================================
# System Monitoring - 资源监控 & 渲染进度
# ============================================================

@app.get("/api/v1/system/resources")
async def system_resources_snapshot(_auth: bool = Depends(require_mcp_auth)):
    """获取当前系统资源快照（CPU/内存/磁盘/GPU）。"""
    monitor = getattr(app.state, "resource_monitor", None)
    if monitor is None:
        raise HTTPException(
            status_code=503,
            detail="Resource monitor not initialized",
        )
    try:
        snapshot = await monitor.get_snapshot()
        return {
            "success": True,
            "snapshot": snapshot,
            "thresholds": monitor.get_thresholds(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get resource snapshot: {e}",
        )


@app.get("/api/v1/system/resources/history")
async def system_resources_history(
    limit: int = 100,
    _auth: bool = Depends(require_mcp_auth),
):
    """获取历史资源采样数据及统计信息。

    Query Params:
        limit: 返回的最大样本数（默认 100，上限 100）。
    """
    monitor = getattr(app.state, "resource_monitor", None)
    if monitor is None:
        raise HTTPException(
            status_code=503,
            detail="Resource monitor not initialized",
        )
    # 限制 limit 范围，避免一次性返回过多数据
    limit = max(1, min(int(limit), 100))
    try:
        history = monitor.get_history(limit=limit)
        stats = monitor.get_stats()
        alerts = monitor.get_alerts(limit=10)
        return {
            "success": True,
            "sample_count": len(history),
            "limit": limit,
            "history": history,
            "stats": stats,
            "recent_alerts": alerts,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get resource history: {e}",
        )


@app.get("/api/v1/system/alerts")
async def system_alerts(
    history_limit: int = 50,
    _auth: bool = Depends(require_mcp_auth),
):
    """获取当前告警状态和历史告警记录。

    Query Params:
        history_limit: 历史记录最大数量（默认 50，上限 200）。

    Returns:
        - ``sustained_alerts``: 当前各指标的持续告警状态机状态
        - ``history``: 告警事件历史（含 webhook 发送结果）
        - ``notifier``: webhook 通知器配置统计信息
    """
    monitor = getattr(app.state, "resource_monitor", None)
    if monitor is None:
        raise HTTPException(
            status_code=503,
            detail="Resource monitor not initialized",
        )
    history_limit = max(1, min(int(history_limit), 200))
    try:
        return {
            "success": True,
            "sustained_alerts": monitor.get_sustained_alerts(),
            "history": monitor.get_alert_history(limit=history_limit),
            "recent_alerts": monitor.get_alerts(limit=10),
            "notifier": monitor.get_notifier_stats(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get alert state: {e}",
        )


@app.post("/api/v1/system/alerts/test")
async def system_alerts_test(_auth: bool = Depends(require_mcp_auth)):
    """发送测试告警，用于验证 webhook 配置是否正确。

    若 webhook 通知器未启用，返回 503。
    """
    monitor = getattr(app.state, "resource_monitor", None)
    if monitor is None:
        raise HTTPException(
            status_code=503,
            detail="Resource monitor not initialized",
        )
    try:
        success = await monitor.send_test_alert()
        return {
            "success": success,
            "notifier": monitor.get_notifier_stats(),
            "message": (
                "测试告警已发送，请检查群消息" if success
                else "测试告警发送失败，请检查 webhook URL 与平台配置"
            ),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test alert: {e}",
        )


@app.get("/api/v1/render/progress/{job_id}")
async def render_progress(job_id: str, _auth: bool = Depends(require_mcp_auth)):
    """获取指定任务的 AE 渲染进度。

    优先级：
    1. ``app.state.render_parsers`` 注册的实时解析器（帧级进度）
    2. ``RenderJobRepository`` 中的持久化历史记录
    3. Pipeline Orchestrator 的任务状态（阶段级进度）
    """
    from fastapi import HTTPException

    # 1. 优先查 render_parsers 注册表（实时进度）
    parsers = getattr(app.state, "render_parsers", {}) or {}
    parser = parsers.get(job_id)
    persisted = None
    if parser is not None:
        progress = parser.progress
        # 同时附带持久化记录（如果存在）
        render_repo = getattr(app.state, "render_repository", None)
        if render_repo is not None:
            try:
                persisted = await render_repo.get_job(job_id)
            except Exception:
                persisted = None
        response: dict = {
            "success": True,
            "job_id": job_id,
            "source": "aerender_parser",
            "progress": {
                "current_frame": progress.current_frame,
                "total_frames": progress.total_frames,
                "percent": round(progress.percent, 2),
                "elapsed_seconds": round(progress.elapsed_seconds, 2),
                "estimated_remaining_seconds": round(
                    progress.estimated_remaining_seconds, 2
                ),
                "frames_per_second": round(progress.frames_per_second, 3),
                "current_layer": progress.current_layer,
                "status": progress.status,
            },
        }
        if persisted is not None:
            response["job"] = persisted.to_dict()
        return response

    # 2. 回退到 RenderJobRepository（持久化历史）
    render_repo = getattr(app.state, "render_repository", None)
    if render_repo is not None:
        try:
            job = await render_repo.get_job(job_id)
        except Exception as e:
            logger.warning(f"render_progress: repository 查询失败: {e}")
            job = None
        if job is not None:
            return {
                "success": True,
                "job_id": job_id,
                "source": "render_repository",
                "progress": {
                    "current_frame": job.current_frame,
                    "total_frames": job.total_frames,
                    "percent": round(job.percent, 2),
                    "elapsed_seconds": round(job.elapsed_seconds, 2),
                    "estimated_remaining_seconds": (
                        round(job.estimated_remaining_seconds, 2)
                        if job.estimated_remaining_seconds is not None
                        else None
                    ),
                    "frames_per_second": 0.0,
                    "current_layer": "",
                    "status": job.status,
                },
                "job": job.to_dict(),
            }

    # 3. 回退到 Pipeline Orchestrator 任务状态
    orch = getattr(app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not initialized",
        )
    state = orch.get_state(job_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Render job '{job_id}' not found",
        )

    # 仅在 Phase4 渲染阶段映射为 rendering，其他阶段映射为 idle/completed/failed
    status_map = {
        "pending": "idle",
        "running": "rendering",
        "success": "completed",
        "failed": "failed",
        "cancelled": "failed",
        "skipped": "idle",
    }
    aerender_status = status_map.get(state.overall_status.value, "idle")
    return {
        "success": True,
        "job_id": job_id,
        "source": "orchestrator_state",
        "progress": {
            "current_frame": 0,
            "total_frames": 0,
            "percent": round(state.progress, 2),
            "elapsed_seconds": 0.0,
            "estimated_remaining_seconds": 0.0,
            "frames_per_second": 0.0,
            "current_layer": "",
            "status": aerender_status,
            "current_phase": (
                state.current_phase.value if state.current_phase else None
            ),
        },
        "state": state.model_dump(),
    }


# ---- Render Jobs 持久化查询 ----

@app.get("/api/v1/render/jobs")
async def list_render_jobs(
    status: Optional[str] = None,
    project: Optional[str] = None,
    days: int = 7,
    limit: int = 50,
    offset: int = 0,
    _auth: bool = Depends(require_mcp_auth),
):
    """列出渲染任务（支持按状态/项目/时间筛选）。

    Query Params:
        status: 按状态过滤 (pending/rendering/completed/failed/cancelled)。
        project: 按项目路径精确匹配过滤。
        days: 只返回最近 N 天内创建的任务，默认 7。
        limit: 返回条数上限，默认 50，最大 500。
        offset: 偏移量，用于分页。
    """
    from fastapi import HTTPException

    render_repo = getattr(app.state, "render_repository", None)
    if render_repo is None:
        raise HTTPException(
            status_code=503,
            detail="Render repository not initialized",
        )
    try:
        jobs = await render_repo.list_jobs(
            status=status,
            project_path=project,
            days=days,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list render jobs: {e}",
        )
    return {
        "success": True,
        "total": len(jobs),
        "filters": {
            "status": status,
            "project": project,
            "days": days,
            "limit": limit,
            "offset": offset,
        },
        "jobs": [j.to_dict() for j in jobs],
    }


@app.get("/api/v1/render/jobs/{job_id}")
async def get_render_job(
    job_id: str,
    _auth: bool = Depends(require_mcp_auth),
):
    """查询单个渲染任务详情。"""
    from fastapi import HTTPException

    render_repo = getattr(app.state, "render_repository", None)
    if render_repo is None:
        raise HTTPException(
            status_code=503,
            detail="Render repository not initialized",
        )
    try:
        job = await render_repo.get_job(job_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get render job: {e}",
        )
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Render job '{job_id}' not found",
        )
    return {"success": True, "job": job.to_dict()}


@app.delete("/api/v1/render/jobs/{job_id}")
async def delete_render_job(
    job_id: str,
    _auth: bool = Depends(require_mcp_auth),
):
    """删除渲染任务记录。"""
    from fastapi import HTTPException

    render_repo = getattr(app.state, "render_repository", None)
    if render_repo is None:
        raise HTTPException(
            status_code=503,
            detail="Render repository not initialized",
        )
    try:
        deleted = await render_repo.delete_job(job_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete render job: {e}",
        )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Render job '{job_id}' not found",
        )
    return {
        "success": True,
        "job_id": job_id,
        "message": f"Render job '{job_id}' deleted",
    }


@app.get("/api/v1/render/stats")
async def render_stats(
    days: int = 30,
    _auth: bool = Depends(require_mcp_auth),
):
    """渲染统计：成功率 / 平均耗时 / 失败原因分布 Top 5。"""
    from fastapi import HTTPException

    render_repo = getattr(app.state, "render_repository", None)
    if render_repo is None:
        raise HTTPException(
            status_code=503,
            detail="Render repository not initialized",
        )
    try:
        stats = await render_repo.get_stats(days=days)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute render stats: {e}",
        )
    return {"success": True, "days": days, "stats": stats.to_dict()}


@app.post("/api/v1/render/jobs/{job_id}/cancel")
async def cancel_render_job(
    job_id: str,
    _auth: bool = Depends(require_mcp_auth),
):
    """取消渲染任务（标记状态为 cancelled）。

    注意：本端点仅更新持久化状态，不会实际终止 aerender 进程。如需终止
    进程，请额外调用 Pipeline Orchestrator 的 cancel 端点。
    """
    from fastapi import HTTPException

    render_repo = getattr(app.state, "render_repository", None)
    if render_repo is None:
        raise HTTPException(
            status_code=503,
            detail="Render repository not initialized",
        )
    try:
        job = await render_repo.get_job(job_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query render job: {e}",
        )
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Render job '{job_id}' not found",
        )
    if job.is_terminal:
        raise HTTPException(
            status_code=409,
            detail=f"任务已处于终态 ({job.status})，无法取消",
        )
    try:
        updated = await render_repo.update_job(
            job_id,
            status="cancelled",
            failure_reason="用户主动取消",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel render job: {e}",
        )
    return {
        "success": True,
        "job_id": job_id,
        "job": updated.to_dict() if updated else None,
        "message": f"Render job '{job_id}' cancelled",
    }


# ============================================================
# AE High-Level Services - 文字效果/插件/调色/音频绑定
# ============================================================

@app.get("/api/v1/ae-services/status")
async def ae_services_status(_auth: bool = Depends(require_mcp_auth)):
    """获取 AE 高层服务（文字效果/插件/调色/音频绑定）的初始化状态。

    用于运维侧确认四个高层服务是否随服务启动成功加载。
    业务调用端点按需在后续迭代中补齐，此处仅暴露就绪状态。
    """
    services = {
        "text_effect": getattr(app.state, "text_effect_service", None),
        "ae_plugin": getattr(app.state, "ae_plugin_service", None),
        "color_grading": getattr(app.state, "color_grading_service", None),
        "audio_binding": getattr(app.state, "audio_binding_service", None),
    }
    return {
        "success": True,
        "services": {
            name: {"initialized": svc is not None}
            for name, svc in services.items()
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )

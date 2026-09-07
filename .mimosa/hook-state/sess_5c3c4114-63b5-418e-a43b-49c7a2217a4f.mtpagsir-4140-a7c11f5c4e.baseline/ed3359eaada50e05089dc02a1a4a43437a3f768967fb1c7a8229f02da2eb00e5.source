"""FastAPI application entry point."""

from __future__ import annotations

import os
import re

# ----------------------------------------------------------------------
# 将项目根（AE-Knowledge-Vault）加入 sys.path，让 puppet-automation venv 中
# 的 import 能直接解析 core/* 和 learning/*
# 注意：必须在任何 from learning / from core 导入之前执行！
# ----------------------------------------------------------------------
import sys as _sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))
del _sys


def _safe_upload_name(filename: str) -> str:
    """清洗上传文件名，防路径逃逸（../ 等）与非法字符。

    仅保留文件 basename，并将非常规字符替换为下划线。
    """
    name = Path(filename or "").name
    name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]", "_", name)
    return name or "upload.bin"

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi import (
    Path as FastAPIPath,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ----------------------------------------------------------------------
# core.llm_gateway 的标准 logging → loguru 拦截：
# LLM 网关内部用标准 logging（INFO 级别默认无 handler 不输出），
# 这里将其接入 loguru 统一控制台，确保「密钥刷新完成」等关键日志可见。
# 仅拦截 core.llm_gateway 一个 logger，不影响 uvicorn 自身的日志配置。
# ----------------------------------------------------------------------
import logging as _logging


class _InterceptHandler(_logging.Handler):
    def emit(self, record: _logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=8, exception=record.exc_info).log(level, record.getMessage())


_llm_gw_logger = _logging.getLogger("core.llm_gateway")
_llm_gw_logger.handlers = [_InterceptHandler()]
_llm_gw_logger.setLevel(_logging.INFO)
_llm_gw_logger.propagate = False

from ..config import settings
from .. import auth as shared_auth

# 弱 Token 集合：从 core.security 统一导入（单一定义源，禁止本地重复定义）
from core.security import WEAK_TOKENS

_security = HTTPBearer(auto_error=False)

# 公开 /api/v1/* 端点（无需认证即可访问）。
# 新增公开端点时必须加入此列表，否则会被 MCPPublicRouteAuthMiddleware 拦截。
API_V1_PUBLIC_ENDPOINTS: set[tuple[str, str]] = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
    ("GET", "/api/v1/health"),
}


def _get_configured_mcp_token() -> str:
    """提取 settings.mcp_auth_token 为明文字符串。"""
    raw = settings.mcp_auth_token
    return raw.get_secret_value() if hasattr(raw, "get_secret_value") else raw


def _check_mcp_auth_token(token: str) -> None:
    """统一认证检查：接受 MCP Token 或用户 JWT Session Token。

    认证优先级：
    1. 先尝试 MCP 静态 Token（用于 MCP 工具/脚本调用）
    2. MCP Token 不匹配时，尝试用户 JWT Session Token（用于前端 Dashboard）
    3. PUPPET_DISABLE_AUTH=1 时开发环境放行

    检查失败 → 抛出 HTTPException；通过 → 无返回值。
    """
    configured = _get_configured_mcp_token()

    # ── 1. 检查是否为 MCP Token ──
    mcp_valid = False
    if settings.env == "production":
        if configured in WEAK_TOKENS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="生产环境必须配置 MCP_AUTH_TOKEN",
            )
        if token and token == configured:
            mcp_valid = True
    else:
        # 开发环境：配置了非弱 token 时精确匹配
        if configured not in WEAK_TOKENS:
            if token and token == configured:
                mcp_valid = True
        else:
            # 弱/默认 token：匹配即通过（但会在下面 warning）
            if token and token == configured:
                mcp_valid = True

    if mcp_valid:
        if configured in WEAK_TOKENS and settings.env != "production":
            logger.warning(
                "Puppet API 使用默认 MCP 认证令牌，仅限开发环境。生产环境请设置 MCP_AUTH_TOKEN。"
            )
        return

    # ── 2. 检查是否为用户 JWT Session Token ──
    if token and shared_auth.verify_user_token(token, refresh=False):
        return

    # ── 3. 开发环境：PUPPET_DISABLE_AUTH=1 放行 ──
    if settings.env != "production" and os.environ.get("PUPPET_DISABLE_AUTH", "").lower() in ("1", "true"):
        # 后门警告：每次走此分支都大声告警，避免开发环境配置泄漏到生产
        logger.warning("=" * 60)
        logger.warning("⚠️  认证已禁用 (PUPPET_DISABLE_AUTH=1)！仅限本地开发，生产环境严禁使用！")
        logger.warning("=" * 60)
        return

    # ── 4. 全部失败 → 401 ──
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证令牌",
        headers={"WWW-Authenticate": "Bearer"},
    )


class MCPPublicRouteAuthMiddleware(BaseHTTPMiddleware):
    """对所有 62 个顶层 @app.*("/api/v1/...") 路由强制 Bearer Token 认证。

    背景：
        main.py 中存在大量直接使用 @app.get/post("/api/v1/X") 装饰的顶层路由，
        它们不在任何 include_router 的子路由中，因此无法通过
        include_router(..., dependencies=[Depends(require_mcp_auth)]) 统一保护。
        本中间件作为 VULN-003-2 的补救方案，为这些顶层 /api/v1/* 路由提供
        纵深防御（defense-in-depth）。

    豁免列表（API_V1_PUBLIC_ENDPOINTS）：
        - POST /api/v1/auth/login     登录
        - POST /api/v1/auth/refresh   刷新令牌

    注意：子路由（dashboard_router / creative_router / advanced_router）
    仍然由 include_router 的 dependencies 额外执行一次认证（双重检查，不是坏事）。
    """

    @staticmethod
    def _extract_bearer_token(request: Request) -> str:
        auth_header = request.headers.get("authorization", "") or request.headers.get(
            "Authorization", ""
        )
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        return ""

    async def dispatch(self, request: Request, call_next) -> Response:
        raw_path = request.url.path
        method = request.method

        # 规范化：1) 连续斜杠 // -> /   2) 百分号解码（防止 %2F 绕过） 3) 再规范化一次
        try:
            normalized = re.sub(r"/+", "/", raw_path or "/")
            decoded = unquote(normalized)
            path = re.sub(r"/+", "/", decoded)
        except Exception:
            # 解码异常 → 视为不可信路径，直接走认证流程
            path = raw_path or "/"

        # 非 /api/v1/ 前缀直接放行（顶层 /health、静态文件、mcp router 等）
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        # 公开端点放行（使用规范化后的 method+path）
        if (method, path) in API_V1_PUBLIC_ENDPOINTS:
            return await call_next(request)

        token = self._extract_bearer_token(request)
        try:
            _check_mcp_auth_token(token)
        except HTTPException as exc:
            headers = dict(exc.headers or {})
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=headers,
            )

        return await call_next(request)

def require_mcp_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> bool:
    """Puppet Automation API Bearer Token 认证（FastAPI Depends 版本）。

    子路由 dashboard_router/creative_router/advanced_router 仍使用此 Depends。
    内部委托给 _check_mcp_auth_token 纯函数，与中间件保持行为一致。
    """
    token = credentials.credentials if credentials else ""
    _check_mcp_auth_token(token)
    return True


from ..ai_planner import AIPlanner
from ..engines.ae import AEEngine
from ..engines.audition import AuditionEngine
from ..engines.blender import BlenderEngine
from ..engines.cinema4d import Cinema4DEngine
from ..engines.davinci import DavinciEngine
from ..engines.ffmpeg import FFmpegEngine
from ..engines.media_encoder import MediaEncoderEngine
from ..engines.moviepy import MoviePyEngine
from ..engines.matting import MattingEngine
from ..engines.openmontage import OpenMontageEngine
from ..engines.photoshop import PhotoshopEngine
from ..engines.premiere import PremiereEngine
from ..engines.rife import RifeEngine
from ..engines.sadtalker import SadTalkerEngine
from ..engines.sam2 import SAM2Engine
from ..engines.silhouette import SilhouetteEngine
from ..engines.topaz import TopazEngine
from ..engines.whisper import WhisperEngine
from ..mcp_gateway import initialize_gateway, mcp_router
from ..models.pipeline import PipelineJob, PuppetStyle
from ..orchestrator import PipelineOrchestrator


class _ConfigService:
    """Configuration wrapper for MCP tool access."""

    SENSITIVE_KEY_KEYWORDS = [
        "key",
        "token",
        "secret",
        "password",
        "authorization",
        "credential",
        "bearer",
        "apikey",
        "api_key",
        "private_key",
        "access_key",
        "access_token",
        "refresh_token",
        "id_token",
        "session_key",
        "signing_key",
    ]

    def __init__(self, settings_obj):
        self._settings = settings_obj

    @staticmethod
    def _is_sensitive_value(val: str) -> bool:
        if not isinstance(val, str) or len(val) < 4:
            return False
        if val.startswith(
            (
                "sk-",
                "sk_live_",
                "sk_test_",
                "Bearer ",
                "Bearer\t",
                "eyJ",
                "xoxb-",
                "xoxp-",
                "ghp_",
                "glpat-",
            )
        ):
            return True
        return False

    @staticmethod
    def _mask_value(val: str) -> str:
        if len(val) <= 4:
            return "***"
        return val[:2] + "*" * max(4, len(val) - 4) + val[-2:]

    def get_safe_config(self):
        """Get safe configuration (secrets masked)."""
        from pathlib import Path

        result = {}
        for key, val in self._settings.model_dump().items():
            if isinstance(val, Path):
                result[key] = str(val)
            elif isinstance(val, str):
                key_sensitive = any(
                    kw in key.lower() for kw in self.SENSITIVE_KEY_KEYWORDS
                )
                val_sensitive = self._is_sensitive_value(val)
                if key_sensitive or val_sensitive:
                    result[key] = self._mask_value(val) if val else ""
                else:
                    result[key] = val
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


def _get_allowed_roots() -> list[Path]:
    output_root = Path(settings.output_dir).resolve()
    if hasattr(settings, "data_dir"):
        data_root = Path(settings.data_dir).resolve()
    else:
        data_root = Path(settings.project_root) / "data"
    temp_root = Path(settings.project_root) / "temp"
    return [output_root, data_root, temp_root]


def _validate_under_allowed(user_path_str: str, field_name: str) -> Path:
    user_path = Path(user_path_str).resolve()
    allowed_roots = _get_allowed_roots()
    for root in allowed_roots:
        try:
            user_path.relative_to(root)
            return user_path
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail={
            "error_code": "PATH_OUTSIDE_ALLOWED",
            "message": f"{field_name} must be under one of: {[str(r) for r in allowed_roots]}",
        },
    )


def _assert_critical_routes(app: FastAPI) -> None:
    """启动后断言：检查关键路由是否全部注册成功。

    防止"路由注册 try/except 静默降级"导致关键端点 404 的事故
    （"24 路由 404 事故"结构性根因）。
    缺失任一关键路由时直接 raise RuntimeError，让进程 fail-fast。
    """
    # 关键路由清单：缺失即视为启动失败
    # 注：/api/v1/flagship/execute 为旗舰管线入口
    #     （flagship_routes 的 router prefix=/api/v1/flagship）
    critical_paths = {
        "/health",
        "/api/v1/engines",
        "/api/v1/flagship/execute",
    }

    def _collect_paths(routes) -> set:
        """收集路由路径，兼容新版 FastAPI/Starlette 的 _IncludedRouter 惰性委派。

        FastAPI >= 0.140 / Starlette 1.x 中 include_router 不再立即展开子路由，
        而是以 _IncludedRouter 惰性对象挂载；其自身没有 .path 属性，需递归
        展开 original_router 内部路由才能拿到真实路径。
        """
        paths: set = set()
        for route in routes:
            p = getattr(route, "path", None)
            if p:
                paths.add(p)
                continue
            inner = getattr(route, "original_router", None)
            if inner is not None:
                paths |= _collect_paths(getattr(inner, "routes", []))
        return paths

    registered = _collect_paths(app.routes)
    missing = critical_paths - registered
    if missing:
        raise RuntimeError(
            f"关键路由注册缺失: {sorted(missing)}；"
            f"已注册路由数={len(app.routes)}。"
            f"通常由路由模块 import/include_router 失败导致，请检查启动日志。"
        )
    logger.info(
        f"Critical routes assertion passed: {sorted(critical_paths)} "
        f"(total routes={len(app.routes)})"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("Starting Puppet Automation Pipeline...")

    # ── 后门警告：PUPPET_DISABLE_AUTH=1 仅限本地开发，生产环境严禁使用 ──
    if os.environ.get("PUPPET_DISABLE_AUTH", "").lower() in ("1", "true"):
        logger.warning("=" * 60)
        logger.warning("⚠️  认证已禁用 (PUPPET_DISABLE_AUTH=1)！仅限本地开发，生产环境严禁使用！")
        logger.warning("=" * 60)

    settings.ensure_dirs()

    # Initialize engines via unified registry (shared with Celery worker)
    from ..engines.registry import build_engine_registry

    engines = build_engine_registry()

    # ComfyUI WorkflowManager 需要单独持有引用
    comfyui_engine = engines.get("comfyui")
    if comfyui_engine is not None:
        from ..engines.comfyui import WorkflowManager
        app.state.comfyui_engine = comfyui_engine
        app.state.wf_manager = WorkflowManager(
            engine=comfyui_engine,
            workflows_dir=settings.comfyui_workflows_dir,
        )
    else:
        app.state.comfyui_engine = None
        app.state.wf_manager = None

    app.state.flux3_engine = engines.get("flux3")

    app.state.engines = engines
    logger.info(f"Initialized {len(engines)} engines")

    # NOTE: MCP Gateway 初始化推迟到所有 service 就绪后执行（见 lifespan 末尾），
    # 否则 resource_index / ae_plugin / config 等 service-layer 工具会被静默丢弃。

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
            logger.info(
                "Webhook notifier disabled (webhook_enabled=false or url missing)"
            )
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
        logger.info(f"RenderJobRepository connected (db={settings.render_db_path})")

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
    # 必须传入 mcp_services，否则 find_font/find_lut/apply_saber/get_safe_config
    # 等 15 个 service-layer 工具会被 _build_service_tool_definitions() 定义但跳过注册
    mcp_services = {}
    if getattr(app.state, "resource_index_service", None):
        mcp_services["resource_index"] = app.state.resource_index_service
    if getattr(app.state, "ae_plugin_service", None):
        mcp_services["ae_plugin"] = app.state.ae_plugin_service
    mcp_services["config"] = _ConfigService(settings)

    gateway = initialize_gateway(engines, mcp_services)
    app.state.mcp_gateway = gateway
    logger.info(
        f"MCP Gateway: {len(gateway.tools)} tools, {len(gateway.engines)} engines, {len(mcp_services)} services"
    )

    # Initialize Dashboard Storage (SQLite-backed project/history persistence)
    try:
        from ..services.dashboard_storage import _seed_demo_data, dashboard_storage

        await dashboard_storage.connect()
        await _seed_demo_data(dashboard_storage)
        app.state.dashboard_storage = dashboard_storage
        logger.info("Dashboard storage initialized (SQLite)")
    except Exception as e:
        logger.warning(f"Dashboard storage init failed: {e}")
        app.state.dashboard_storage = None

    # 启动后断言：确保关键路由已注册（防止路由注册静默降级导致 404）
    _assert_critical_routes(app)

    # ── LLM Key 状态自动刷新（每次启动执行一次，后台线程不阻塞启动）──
    # 重跑 scripts/check_llm_keys.py（--no-comment，不修改配置文件）刷新
    # data/llm_key_status.json，网关随即熔断失效 Provider，避免误用失效 key。
    try:
        from core.llm_gateway import llm_gateway

        llm_gateway.ensure_configured()
        llm_gateway.refresh_key_status(blocking=False)
        logger.info("LLM key 状态已提交后台刷新（scripts/check_llm_keys.py --no-comment）")
    except Exception as e:
        logger.warning(f"LLM key 状态刷新钩子失败（非致命，不影响启动）: {e}")

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

# 对顶层 @app.*("/api/v1/...") 路由的强制认证中间件。
# 注：Starlette 的 add_middleware 按"后注册先执行"（LIFO）顺序应用，
# 因此在本文件中，先注册 Auth 中间件、再注册 CORS 中间件，意味着：
#   请求到达 → CORS（先）→ Auth（后）→ 路由。
# 这样 CORS 预检（OPTIONS）在 Auth 之前被 CORSMiddleware 处理，无需 Bearer Token。
app.add_middleware(MCPPublicRouteAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "PUPPET_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 前端面板静态文件 ----
_DASHBOARD_DIST = (
    Path(__file__).resolve().parent.parent.parent.parent / "ae-dashboard" / "dist"
)
if _DASHBOARD_DIST.exists():
    app.mount(
        "/app", StaticFiles(directory=str(_DASHBOARD_DIST), html=True), name="dashboard"
    )
    logger.info(f"Dashboard static files mounted at /app -> {_DASHBOARD_DIST}")


# ---- 通用请求模型 ----


class ExecuteEngineRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    params: dict = Field(default_factory=dict)


class BlenderNLParams(BaseModel):
    """自然语言 → Blender 操作请求参数。"""

    command: str = Field(..., min_length=1, max_length=2000, description="用户自然语言指令（中文）")
    scene_context: Optional[str] = Field(None, max_length=4000, description="场景上下文描述（可选）")
    max_attempts: int = Field(2, ge=1, le=5, description="最大尝试次数（含自修复重试）")


class MattingParams(BaseModel):
    """Matting 抠像引擎执行参数。"""

    action: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="执行动作: human_matting (单图/目录抠像) 或 batch_frames (帧序列批处理)",
    )
    input_path: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="输入图片路径或图片目录/帧序列目录",
    )
    output_dir: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="输出目录（alpha遮罩+透明PNG将写入此处）",
    )
    model_name: Optional[str] = Field(
        None,
        max_length=256,
        description="可选：模型文件名（在 matting_model_dir 中查找），默认自动选择 PP-MattingV2",
    )


@app.get("/health")
@app.get("/api/v1/health")
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
    engine_name: str = FastAPIPath(..., pattern=r"^[a-zA-Z0-9_]+$"),
    req: ExecuteEngineRequest = ...,
    _auth: bool = Depends(require_mcp_auth),
):
    """Execute an action on a specific engine."""
    if engine_name not in app.state.engines:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "ENGINE_NOT_FOUND",
                "message": f"Engine '{engine_name}' not found. Available: {list(app.state.engines.keys())}",
            },
        )
    engine = app.state.engines[engine_name]

    dangerous = {"__class__", "__init__", "__del__", "__dict__", "mro", "new"}
    if any(k in dangerous for k in req.params.keys()):
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "PARAM_FORBIDDEN",
                "message": "Dangerous parameter keys are not allowed",
            },
        )

    try:
        result = await engine.execute(
            action=req.action,
            **req.params,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_PARAM", "message": str(e)[:500]},
        )
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={
                "error_code": "ENGINE_TIMEOUT",
                "message": "Engine execution timed out",
            },
        )
    except Exception as e:
        logger.exception(f"[API] engine {engine_name} execute error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "ENGINE_ERROR",
                "message": "引擎执行失败，请查看服务日志获取详情",
            },
        )

    # 安全：对外响应中脱敏 error 字段（截断+过滤绝对路径）
    _safe_error = None
    if result.error:
        _safe_error = str(result.error)[:500]
        import re
        _safe_error = re.sub(r'[A-Za-z]:\\[^\s"\']+', '[PATH]', _safe_error)

    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": _safe_error,
        "error_code": result.error_code,
        "available": getattr(result, "available", True),
        "duration_seconds": getattr(result, "duration_seconds", 0.0),
    }


# ---- Blender 自然语言操作 ----

@app.post("/api/v1/blender/nl_execute")
async def blender_nl_execute(
    req: BlenderNLParams,
    _auth: bool = Depends(require_mcp_auth),
):
    """自然语言 → Blender 操作：将中文指令转换为 bpy 脚本并执行。

    能力：
    - 中文 Prompt + Blender Python API few-shot 引导 LLM 生成纯 bpy 脚本
    - 静态安全审查：禁止 exec/eval/subprocess/os.system 等高危调用
    - 错误自修复：失败时将 traceback 附入 Prompt，最多重试 max_attempts-1 次
    - 执行：通过 BlenderEngine --python <tmp> 模式执行，记录 stdout/stderr

    Args:
        req: BlenderNLParams(command, scene_context, max_attempts)

    Returns:
        {status, generated_code, attempt_count, stdout, stderr, error}
    """
    from fastapi import HTTPException

    try:
        from ..services.blender_nl_service import get_default_service
    except Exception as e:
        logger.warning(f"[API] BlenderNLService 导入失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "BLENDER_NL_SERVICE_UNAVAILABLE",
                "message": "Blender 自然语言服务未就绪，请查看服务日志",
            },
        )

    try:
        service = get_default_service()
        nl_result = await service.execute(
            command=req.command,
            scene_context=req.scene_context,
            max_attempts=req.max_attempts,
        )
        result_dict = nl_result.to_dict()

        # 安全脱敏：错误信息中截断绝对路径
        if result_dict.get("error"):
            import re as _re
            result_dict["error"] = _re.sub(r'[A-Za-z]:\\[^\s"\']+', '[PATH]', result_dict["error"])
        if result_dict.get("stderr"):
            import re as _re2
            result_dict["stderr"] = _re2.sub(r'[A-Za-z]:\\[^\s"\']+', '[PATH]', result_dict["stderr"])

        # 根据 status 映射 HTTP 状态码
        status_map = {
            "success": 200,
            "safety_violation": 400,
            "llm_unavailable": 503,
            "execution_failed": 422,
            "max_attempts_exceeded": 422,
        }
        http_code = status_map.get(nl_result.status, 500)

        if http_code != 200:
            result_dict.setdefault(
                "error_code",
                {
                    "safety_violation": "SAFETY_VIOLATION",
                    "llm_unavailable": "LLM_UNAVAILABLE",
                    "execution_failed": "EXECUTION_FAILED",
                    "max_attempts_exceeded": "MAX_ATTEMPTS_EXCEEDED",
                }.get(nl_result.status, "UNKNOWN_ERROR"),
            )

        return JSONResponse(status_code=http_code, content=result_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[API] blender_nl_execute error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "BLENDER_NL_INTERNAL_ERROR",
                "message": "Blender 自然语言服务内部错误，请查看服务日志",
            },
        )


# ---- MCP Gateway ----
app.include_router(mcp_router)

# ---- Dashboard API (前端面板数据) ----
try:
    from .dashboard_routes import (
        auth_public_router,
    )
    from .dashboard_routes import (
        router as dashboard_router,
    )

    # 1) 公开认证端点（/auth/login、/auth/refresh）：无需 MCP Token
    #    （FastAPI include_router dependencies 与 endpoint dependencies 是合并执行，
    #     不能用 endpoint dependencies=[] 覆盖，因此单独放到无依赖路由器中）
    app.include_router(auth_public_router)
    # 2) 其余 80+ Dashboard 端点：全局注入 require_mcp_auth 认证依赖
    app.include_router(dashboard_router, dependencies=[Depends(require_mcp_auth)])
    logger.info("Dashboard routes registered")
except Exception as e:
    logger.warning(f"Dashboard routes not available: {e}")

# ---- Creative Routes (P3/P4: 风格迁移/导演系统/镜头语言/自动复刻) ----
try:
    from .creative_routes import router as creative_router

    app.include_router(creative_router, dependencies=[Depends(require_mcp_auth)])
    logger.info("Creative routes registered")
except Exception as e:
    logger.warning(f"Creative routes not available: {e}")

# ---- Advanced Routes (高级功能: 效果库/图层管线/抠像/OpenMontage/任务/仪表盘总览/WebSocket) ----
try:
    from .advanced_routes import router as advanced_router

    app.include_router(advanced_router, dependencies=[Depends(require_mcp_auth)])
    logger.info("Advanced routes registered")
except Exception as e:
    # fail-fast：路由注册失败必须中止启动，避免关键端点 404（"24 路由 404 事故"根因）
    logger.error(f"Advanced routes registration failed: {e}")
    raise

# ---- Flagship Pipeline Routes (旗舰管线: S0-S7 全链路) ----
try:
    from .flagship_routes import router as flagship_router

    app.include_router(flagship_router, dependencies=[Depends(require_mcp_auth)])
    logger.info("Flagship pipeline routes registered")
except Exception as e:
    logger.warning(f"Flagship routes not available: {e}")

# ---- Evolution Routes (P2: 自进化闭环观测) ----
try:
    from .evolution_routes import router as evolution_router

    app.include_router(evolution_router, dependencies=[Depends(require_mcp_auth)])
    logger.info("Evolution routes registered")
except Exception as e:
    logger.warning(f"Evolution routes not available: {e}")

# ---- Media Routes (素材下载子系统: 复用 13-素材获取与搜索/01-下载器/unified_downloader.py) ----
try:
    from .media_router import router as media_router

    app.include_router(media_router, dependencies=[Depends(require_mcp_auth)])
    logger.info("Media routes registered")
except Exception as e:
    logger.warning(f"Media routes not available: {e}")


# ---- Pipeline Orchestration ----
@app.post("/api/v1/pipeline/jobs", status_code=201)
async def create_pipeline_job(
    job: PipelineJob,
    _auth: bool = Depends(require_mcp_auth),
):
    """Create a new pipeline job and start execution."""
    orch: PipelineOrchestrator = app.state.orchestrator
    try:
        job_id = orch.start_job_async(job)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"任务调度失败: {type(e).__name__}: {str(e)[:300]}")
    if job_id is None or job_id == "":
        raise HTTPException(status_code=500, detail="任务调度失败，未返回有效 job_id")
    state = orch.get_state(job_id)
    if state is None:
        raise HTTPException(status_code=500, detail=f"任务 '{job_id}' 创建成功但状态不可用")
    try:
        state_dump = state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"任务状态序列化失败: {type(e).__name__}: {str(e)[:200]}")
    return {"job_id": job_id, "state": state_dump}


@app.get("/api/v1/pipeline/jobs")
async def list_pipeline_jobs(
    _auth: bool = Depends(require_mcp_auth),
):
    """List all pipeline jobs."""
    orch: PipelineOrchestrator = app.state.orchestrator
    jobs = orch.list_jobs()
    if jobs is None or not isinstance(jobs, list):
        jobs = []
    return {"jobs": [j.model_dump() for j in jobs]}


@app.get("/api/v1/pipeline/jobs/{job_id}")
async def get_pipeline_job(
    job_id: str,
    _auth: bool = Depends(require_mcp_auth),
):
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
                    "alternatives": [
                        s.value for s in result.style_recommendation.alternatives
                    ],
                    "confidence": result.style_recommendation.confidence,
                    "reasoning": result.style_recommendation.reasoning,
                    "style_tips": result.style_recommendation.style_tips,
                }
                if result.style_recommendation
                else None
            ),
            "optimized_params": (
                {
                    "recommended_resolution": list(
                        result.optimized_params.recommended_resolution
                    ),
                    "recommended_fps": result.optimized_params.recommended_fps,
                    "recommended_quality": result.optimized_params.recommended_quality,
                    "enable_topaz": result.optimized_params.enable_topaz,
                    "enable_silhouette_roto": result.optimized_params.enable_silhouette_roto,
                    "enable_3d_stage": result.optimized_params.enable_3d_stage,
                    "enable_color_grade": result.optimized_params.enable_color_grade,
                    "estimated_processing_time_minutes": result.optimized_params.estimated_processing_time_minutes,
                    "optimization_notes": result.optimized_params.optimization_notes,
                }
                if result.optimized_params
                else None
            ),
            "explanation": result.explanation,
            "reasoning": result.reasoning,
        }
    except LLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "LLM_UNAVAILABLE", "message": "LLM 服务不可用"},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_INPUT", "message": str(e)[:500]},
        )
    except Exception as e:
        logger.exception(f"[API] AI endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "AI_SERVICE_ERROR",
                "message": "AI服务调用失败，请查看服务日志获取详情",
            },
        )


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
    except LLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "LLM_UNAVAILABLE", "message": "LLM 服务不可用"},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_INPUT", "message": str(e)[:500]},
        )
    except Exception as e:
        logger.exception(f"[API] AI endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "AI_SERVICE_ERROR",
                "message": "AI服务调用失败，请查看服务日志获取详情",
            },
        )


@app.post("/api/v1/ai/recommend-style")
async def ai_recommend_style(
    video_path: str = "",
    user_preferences: str = "",
    _auth: bool = Depends(require_mcp_auth),
):
    """Recommend puppet style based on video and preferences."""
    from fastapi import HTTPException

    planner: AIPlanner = app.state.ai_planner
    try:
        rec = await planner.recommend_style(
            video_path, user_preferences=user_preferences
        )
        return {
            "primary_style": rec.primary_style.value,
            "alternatives": [s.value for s in rec.alternatives],
            "confidence": rec.confidence,
            "reasoning": rec.reasoning,
            "style_tips": rec.style_tips,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_INPUT", "message": str(e)[:500]},
        )
    except Exception as e:
        logger.exception(f"[API] AI endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "AI_SERVICE_ERROR",
                "message": "AI服务调用失败，请查看服务日志获取详情",
            },
        )


@app.get("/api/v1/ai/styles")
async def list_puppet_styles(
    _auth: bool = Depends(require_mcp_auth),
):
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
    except LLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "LLM_UNAVAILABLE", "message": "LLM 服务不可用"},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_INPUT", "message": str(e)[:500]},
        )
    except Exception as e:
        logger.exception(f"[API] AI endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "AI_SERVICE_ERROR",
                "message": "AI服务调用失败，请查看服务日志获取详情",
            },
        )


# ---- ComfyUI ----


class WorkflowUploadRequest(BaseModel):
    """Request body for uploading a custom workflow."""

    name: str
    display_name: str | None = None
    description: str | None = None
    category: str | None = "user"
    style: str | None = None
    workflow: dict  # ComfyUI prompt JSON


class WorkflowExecuteRequest(BaseModel):
    """Request body for executing a workflow."""

    workflow_name: str
    params: dict | None = None
    output_dir: str | None = None


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
async def list_comfyui_workflows(category: str | None = None):
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
        raise HTTPException(
            status_code=404, detail=f"Workflow '{name}' not found or cannot be deleted"
        )

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

    output_dir = (
        _validate_under_allowed(req.output_dir, "output_dir")
        if req.output_dir
        else None
    )

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

    tmp_path = Path(tempfile.gettempdir()) / _safe_upload_name(file.filename)
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


# ---- Flux 3 音画一体生成 ----


class Flux3ImageRequest(BaseModel):
    """文生图 / 图生图请求。"""

    prompt: str = ""
    model: str = "flux-1.1-pro"
    width: int = 1024
    height: int = 1024
    steps: int | None = None
    seed: int | None = None
    image_path: str | None = None  # 若提供则为图生图
    strength: float = 0.7
    output_dir: str | None = None
    extra_params: dict | None = None


class Flux3VideoRequest(BaseModel):
    """文生视频 / 图生视频请求（Flux 3 音画一体）。"""

    prompt: str = ""
    model: str = "flux-3"
    width: int = 1280
    height: int = 720
    duration: float = 20.0
    fps: int = 24
    seed: int | None = None
    image_path: str | None = None  # 若提供则为图生视频
    audio_enabled: bool = True
    audio_prompt: str | None = None
    output_dir: str | None = None
    extra_params: dict | None = None


class Flux3AudioRequest(BaseModel):
    """纯音频生成请求。"""

    prompt: str
    model: str = "flux-3-audio"
    duration: float = 10.0
    seed: int | None = None
    output_dir: str | None = None
    extra_params: dict | None = None


@app.get("/api/v1/flux3/status")
async def flux3_status(
    _auth: bool = Depends(require_mcp_auth),
):
    """查询 Flux 3 API 状态、支持的模型和功能清单。"""
    from fastapi import HTTPException

    engine = getattr(app.state, "flux3_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="Flux 3 engine not initialized")
    result = await engine.execute(action="get_status")
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/flux3/generate-image")
async def flux3_generate_image(
    req: Flux3ImageRequest,
    _auth: bool = Depends(require_mcp_auth),
):
    """文生图或图生图。"""
    from fastapi import HTTPException

    engine = getattr(app.state, "flux3_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="Flux 3 engine not initialized")

    kwargs: dict = {
        "prompt": req.prompt,
        "model": req.model,
        "width": req.width,
        "height": req.height,
    }
    if req.steps is not None:
        kwargs["steps"] = req.steps
    if req.seed is not None:
        kwargs["seed"] = req.seed
    if req.output_dir:
        kwargs["output_dir"] = req.output_dir
    if req.extra_params:
        # 安全过滤: 仅允许白名单参数透传，防止覆盖 output_dir 等敏感字段
        _ALLOWED_EXTRA = {
            "negative_prompt",
            "guidance_scale",
            "sampler",
            "prompt_strength",
        }
        for k, v in req.extra_params.items():
            if k in _ALLOWED_EXTRA and k not in kwargs:
                kwargs[k] = v

    if req.image_path:
        result = await engine.image_to_image(
            image_path=req.image_path,
            strength=req.strength,
            **kwargs,
        )
    else:
        result = await engine.generate_image(**kwargs)

    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
    }


@app.post("/api/v1/flux3/generate-video")
async def flux3_generate_video(
    req: Flux3VideoRequest,
    _auth: bool = Depends(require_mcp_auth),
):
    """文生视频或图生视频（Flux 3 原生音画同步）。"""
    from fastapi import HTTPException

    engine = getattr(app.state, "flux3_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="Flux 3 engine not initialized")

    kwargs: dict = {
        "model": req.model,
        "width": req.width,
        "height": req.height,
        "duration": req.duration,
        "fps": req.fps,
        "audio_enabled": req.audio_enabled,
    }
    if req.seed is not None:
        kwargs["seed"] = req.seed
    if req.audio_prompt:
        kwargs["audio_prompt"] = req.audio_prompt
    if req.output_dir:
        kwargs["output_dir"] = req.output_dir
    if req.extra_params:
        # 安全过滤: 仅允许白名单参数透传，防止覆盖 output_dir 等敏感字段
        _ALLOWED_EXTRA = {
            "negative_prompt",
            "guidance_scale",
            "sampler",
            "prompt_strength",
        }
        for k, v in req.extra_params.items():
            if k in _ALLOWED_EXTRA and k not in kwargs:
                kwargs[k] = v

    if req.image_path:
        result = await engine.image_to_video(
            image_path=req.image_path,
            prompt=req.prompt,
            **kwargs,
        )
    else:
        result = await engine.generate_video(
            prompt=req.prompt,
            **kwargs,
        )

    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
    }


@app.post("/api/v1/flux3/generate-audio")
async def flux3_generate_audio(
    req: Flux3AudioRequest,
    _auth: bool = Depends(require_mcp_auth),
):
    """纯音频生成。"""
    from fastapi import HTTPException

    engine = getattr(app.state, "flux3_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="Flux 3 engine not initialized")

    kwargs: dict = {
        "prompt": req.prompt,
        "model": req.model,
        "duration": req.duration,
    }
    if req.seed is not None:
        kwargs["seed"] = req.seed
    if req.output_dir:
        kwargs["output_dir"] = req.output_dir
    if req.extra_params:
        # 安全过滤: 仅允许白名单参数透传，防止覆盖 output_dir 等敏感字段
        _ALLOWED_EXTRA = {
            "negative_prompt",
            "guidance_scale",
            "sampler",
            "prompt_strength",
        }
        for k, v in req.extra_params.items():
            if k in _ALLOWED_EXTRA and k not in kwargs:
                kwargs[k] = v

    result = await engine.generate_audio(**kwargs)

    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
    }


# ---- SadTalker ----
class SadTalkerGenerateRequest(BaseModel):
    """音频驱动数字人视频生成请求。"""

    source_image: str
    driven_audio: str
    output_path: str | None = None
    preprocess: str = "crop"
    size: int = 256
    enhancer: str | None = None
    still_mode: bool = False
    pose_style: int = 0
    expression_scale: float = 1.0
    batch_size: int = 2


@app.get("/api/v1/sadtalker/status")
async def sadtalker_status():
    """查询 SadTalker 引擎状态。"""
    from fastapi import HTTPException

    engine = app.state.engines.get("sadtalker")
    if not engine:
        raise HTTPException(status_code=503, detail="SadTalker engine not initialized")
    return {
        "success": True,
        **engine.get_info(),
    }


@app.post("/api/v1/sadtalker/generate")
async def sadtalker_generate(
    req: SadTalkerGenerateRequest,
    _auth: bool = Depends(require_mcp_auth),
):
    """生成音频驱动说话头像视频（图片 + 音频 → 口型同步视频）。"""
    from fastapi import HTTPException

    engine = app.state.engines.get("sadtalker")
    if not engine:
        raise HTTPException(status_code=503, detail="SadTalker engine not initialized")

    result = await engine.generate(
        source_image=req.source_image,
        driven_audio=req.driven_audio,
        output_path=req.output_path,
        preprocess=req.preprocess,
        size=req.size,
        enhancer=req.enhancer,
        still_mode=req.still_mode,
        pose_style=req.pose_style,
        expression_scale=req.expression_scale,
        batch_size=req.batch_size,
        timeout=settings.sadtalker_timeout,
    )

    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
    }


@app.get("/api/v1/matting/status")
async def matting_status(
    _auth: bool = Depends(require_mcp_auth),
):
    """查询 Matting 抠像引擎状态与模型检测报告（需 MCP 认证）。"""
    from fastapi import HTTPException

    engine = app.state.engines.get("matting")
    if not engine:
        raise HTTPException(status_code=503, detail="Matting engine not initialized")
    info = engine.get_info() if hasattr(engine, "get_info") else {"name": "matting"}
    return {
        "success": True,
        **info,
    }


@app.post("/api/v1/matting/execute")
async def matting_execute(
    req: MattingParams,
    _auth: bool = Depends(require_mcp_auth),
):
    """执行 Matting 抠像引擎任务（需 MCP 认证）。

    支持 action:
    - human_matting: 单图或目录批量人像抠像，输出 Alpha 遮罩 + 透明 PNG
    - batch_frames: 帧序列批量抠像，保持原文件名一一对应
    """
    from fastapi import HTTPException

    engine = app.state.engines.get("matting")
    if not engine:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "MATTING_NOT_INITIALIZED",
                "message": "Matting engine not initialized",
            },
        )

    try:
        result = await engine.execute(
            action=req.action,
            input_path=req.input_path,
            output_dir=req.output_dir,
            model_name=req.model_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_PARAM", "message": str(e)[:500]},
        )
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={
                "error_code": "MATTING_TIMEOUT",
                "message": "Matting execution timed out",
            },
        )
    except Exception as e:
        logger.exception(f"[API] matting execute error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "MATTING_ERROR",
                "message": "抠像引擎执行失败，请查看服务日志获取详情",
            },
        )

    _safe_error = None
    if result.error:
        _safe_error = str(result.error)[:500]
        import re
        _safe_error = re.sub(r'[A-Za-z]:\\[^\s"\']+', '[PATH]', _safe_error)

    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": _safe_error,
        "error_code": result.error_code,
        "available": getattr(result, "available", True),
        "duration_seconds": getattr(result, "duration_seconds", 0.0),
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

        tmp_path = Path(tempfile.gettempdir()) / _safe_upload_name(file.filename)
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

        tmp_path = Path(tempfile.gettempdir()) / _safe_upload_name(file.filename)
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

        tmp_path = Path(tempfile.gettempdir()) / _safe_upload_name(file.filename)
        content = await file.read()
        tmp_path.write_bytes(content)

        service = SceneDetectionService()
        result = await service.extract_keyframes(
            tmp_path, scene_threshold=scene_threshold
        )
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
    project_path: str | None = None,
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
    comp_name: str | None = None,
    as_sequence: bool = False,
    position: int | None = None,
    project_path: str | None = None,
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
    position: int | None = None,
    project_path: str | None = None,
    params: dict | None = None,
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
    params: dict | None = None,
    project_path: str | None = None,
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
    keyframes: list[dict],
    project_path: str | None = None,
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
    project_path: str | None = None,
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
    project_path: str | None = None,
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
    project_path: str | None = None,
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
    effects: list[dict] | None = None,
    position: int | None = None,
    project_path: str | None = None,
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
# After Effects - 字幕 API
# ============================================================


@app.post("/api/v1/ae/subtitles/import")
async def ae_import_subtitles(
    comp_name: str,
    subtitle_path: str,
    project_path: str | None = None,
    font_family: str = "Arial",
    font_size: int = 48,
    font_color: list[float] | None = None,
    stroke_color: list[float] | None = None,
    stroke_width: float = 2.0,
    glow_enabled: bool = True,
    glow_color: list[float] | None = None,
    glow_radius: float = 15.0,
    position_y: float = 0.85,
    _auth: bool = Depends(require_mcp_auth),
):
    """导入字幕文件到 AE 合成。

    Args:
        comp_name: 合成名称
        subtitle_path: 字幕文件路径（SRT/VTT/ASS）
        project_path: 项目路径（可选）
        font_family: 字体名称
        font_size: 字号
        font_color: 字体颜色 [r, g, b]（0-1范围）
        stroke_color: 描边颜色 [r, g, b]（0-1范围）
        stroke_width: 描边宽度
        glow_enabled: 是否启用发光效果
        glow_color: 发光颜色 [r, g, b]（0-1范围）
        glow_radius: 发光半径
        position_y: Y轴位置（0-1，底部为1）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.import_subtitles(
        comp_name=comp_name,
        subtitle_path=subtitle_path,
        project_path=project_path,
        font_family=font_family,
        font_size=font_size,
        font_color=font_color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        glow_enabled=glow_enabled,
        glow_color=glow_color,
        glow_radius=glow_radius,
        position_y=position_y,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/subtitles/export")
async def ae_export_subtitles(
    comp_name: str,
    output_path: str,
    format: str = "srt",
    project_path: str | None = None,
    _auth: bool = Depends(require_mcp_auth),
):
    """导出 AE 文字图层为字幕文件。

    Args:
        comp_name: 合成名称
        output_path: 输出文件路径
        format: 导出格式（srt/vtt/ass）
        project_path: 项目路径（可选）
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.export_subtitles(
        comp_name=comp_name,
        output_path=output_path,
        format=format,
        project_path=project_path,
    )
    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.post("/api/v1/ae/subtitles/generate")
async def ae_generate_subtitles(
    audio_path: str,
    comp_name: str,
    language: str = "zh",
    use_llm: bool = True,
    project_path: str | None = None,
    font_family: str = "Arial",
    font_size: int = 48,
    _auth: bool = Depends(require_mcp_auth),
):
    """从音频生成字幕并导入到 AE 合成。

    Args:
        audio_path: 音频文件路径
        comp_name: 合成名称
        language: 语言代码（zh/en/ja/ko 等）
        use_llm: 是否使用 LLM 优化字幕
        project_path: 项目路径（可选）
        font_family: 字体名称
        font_size: 字号
    """
    engine = app.state.engines.get("ae")
    if not engine:
        raise HTTPException(status_code=503, detail="AE engine not initialized")

    result = await engine.generate_subtitles_from_audio(
        audio_path=audio_path,
        comp_name=comp_name,
        language=language,
        use_llm=use_llm,
        project_path=project_path,
        font_family=font_family,
        font_size=font_size,
    )
    return {
        "success": result.success,
        "metadata": result.metadata,
        "error": result.error,
    }


# ============================================================
# Blender - Cel-Shading (3渲2) API
# ============================================================


class CelShadingRequest(BaseModel):
    """请求体：Cel-Shading 渲染参数。"""

    model_config = ConfigDict(protected_namespaces=())
    style: str = "anime"
    model_path: str | None = None
    output_dir: str | None = None
    resolution: list[int] | None = None
    frame_start: int = 1
    frame_end: int = 60
    outline_mode: str = "lineart"
    export_fbx: bool = False


@app.post("/api/v1/blender/cel-shading")
async def blender_cel_shading(
    req: CelShadingRequest,
    _auth: bool = Depends(require_mcp_auth),
):
    """执行 Blender Cel-Shading (3渲2) 渲染。

    支持五种风格预设：
    - anime: 日系动漫（柔和色彩，细线轮廓）
    - cartoon: 美式卡通（强对比，粗线轮廓）
    - cyberpunk: 赛博朋克（霓虹渐变，发光效果）
    - ink: 水墨风格（灰度渐变，毛笔感）
    - lowpoly: 低多边形（平面硬切，明亮色彩）

    Args:
        style: 风格预设，默认 "anime"
        model_path: 外部模型路径（FBX/OBJ/GLB/.blend），未提供时使用默认 Suzanne
        output_dir: 输出目录，默认自动生成
        resolution: 输出分辨率 [width, height]，默认 [1920, 1080]
        frame_start: 渲染起始帧，默认 1
        frame_end: 渲染结束帧，默认 60
        outline_mode: 轮廓模式 "lineart" | "freestyle" | "none"，默认 "lineart"
        export_fbx: 是否同时导出 FBX 文件供 AE 使用，默认 False
    """
    from fastapi import HTTPException

    engine = app.state.engines.get("blender")
    if not engine:
        raise HTTPException(status_code=503, detail="Blender engine not initialized")

    if req.output_dir:
        output_dir = Path(req.output_dir)
    else:
        import uuid

        output_dir = settings.output_dir / "blender_cel" / str(uuid.uuid4())[:8]

    resolution = tuple(req.resolution) if req.resolution else (1920, 1080)

    result = await engine.execute(
        action="render_cel_animation",
        output_dir=str(output_dir),
        style=req.style,
        model_path=req.model_path,
        resolution=resolution,
        frame_start=req.frame_start,
        frame_end=req.frame_end,
        outline_mode=req.outline_mode,
        export_fbx=req.export_fbx,
    )

    return {
        "success": result.success,
        "output_path": str(result.output_path) if result.output_path else None,
        "metadata": result.metadata,
        "error": result.error,
    }


@app.get("/api/v1/blender/cel-shading/styles")
async def blender_cel_shading_styles():
    """列出所有可用的 Cel-Shading 风格预设。"""
    from ..engines.blender.cel_shading import get_style_preset

    styles = {}
    for style_key in ["anime", "cartoon", "cyberpunk", "ink", "lowpoly"]:
        preset = get_style_preset(style_key)
        styles[style_key] = {
            "display_name": preset["display_name"],
            "outline_thickness": preset["outline_thickness"],
            "render_samples": preset.get("render_samples", 64),
            "use_bloom": preset.get("use_bloom", False),
        }
    return {"styles": styles}


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
        tmp_path = Path(tempfile.gettempdir()) / f"me_input_{_safe_upload_name(file.filename)}"
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
            raise HTTPException(
                status_code=500, detail=result.error or "ME encode failed"
            )

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
        safe_input_dir = _validate_under_allowed(input_dir, "input_dir")
        safe_output_dir = _validate_under_allowed(output_dir, "output_dir")
        engine = MediaEncoderEngine()
        result = await engine.batch_encode(
            input_dir=str(safe_input_dir),
            output_dir=str(safe_output_dir),
            platform=platform,
        )
        return {
            "success": result.success,
            "total": result.metadata.get("total", 0),
            "success_count": result.metadata.get("success", 0),
            "failed_count": result.metadata.get("failed", 0),
            "results": result.metadata.get("results", []),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_INPUT", "message": str(e)[:500]},
        )
    except Exception as e:
        logger.exception(f"[API] ME batch encode error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "ME_BATCH_ERROR",
                "message": "ME批量编码失败，请查看服务日志获取详情",
            },
        )


@app.post("/api/v1/me/watch-folder/add")
async def me_add_to_watch_folder(
    file: UploadFile = File(...),
    platform: str = "douyin",
    _auth: bool = Depends(require_mcp_auth),
):
    """将视频添加到 ME Watch Folder（异步处理，不等待完成）。"""
    import tempfile

    try:
        tmp_path = Path(tempfile.gettempdir()) / f"me_wf_{_safe_upload_name(file.filename)}"
        content = await file.read()
        tmp_path.write_bytes(content)

        engine = MediaEncoderEngine()
        result = await engine.add_to_watch_folder(
            input_path=tmp_path,
            platform=platform,
        )
        tmp_path.unlink(missing_ok=True)

        if not result.success:
            raise HTTPException(
                status_code=500, detail=result.error or "Add to watch folder failed"
            )

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
                "测试告警已发送，请检查群消息"
                if success
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
    status: str | None = None,
    project: str | None = None,
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


# ---- Learning System (PersistentLearningLoop + BayesianOptimizer + MemoryStore) ----
# 接入 feedback_api 让前端评分三态（satisfied/adjusted/undone）触发对应学习策略
# sys.path 已经在文件最顶部注入了项目根，直接 import 即可
try:
    from learning.feedback_api import get_feedback_api as _get_fb_api

    _feedback_api = _get_fb_api()
    logger.info(f"Feedback API initialized (history_dir={_feedback_api._history_dir})")
except Exception as _e:  # pragma: no cover - fail-safe 兜底
    import traceback as _tb

    _feedback_api = None
    logger.error(
        f"Feedback API 初始化失败（learning/feedback_api 不可用）：{_e}\n{_tb.format_exc()}"
    )


try:
    from typing import Any as _Any

    from fastapi import Body as _Body

    @app.post("/api/v1/learning/feedback")
    async def learning_submit_feedback(
        payload: dict[str, _Any] = _Body(
            ...,
            description="前端评分提交：{run_id, feedback_type in {satisfied,adjusted,undone},"
            " adjusted_params?, rating?, comment?, plan_context?, execute_context?,"
            " verify_context?}",
        ),
        _auth: bool = Depends(require_mcp_auth),
    ):
        """前端评分接入——三态学习闭环入口。

        - **satisfied (rating≥4)** → 模板保存 + reasoning_path 置信度提升 + case_store 使用计数+1
        - **adjusted** (需附带 adjusted_params) → 参数偏差写入 default_value_store + 新参数写入贝叶斯观测
        - **undone (或 rating≤3)** → reasoning_path 置信度惩罚 + 模板 user_rating=negative
        """
        from fastapi import HTTPException

        if _feedback_api is None:
            raise HTTPException(
                status_code=503,
                detail="Feedback API 未初始化（learning 模块缺失？详见启动日志中的 error）",
            )
        try:
            result = _feedback_api.submit_feedback_dict(payload)
            if not result.get("success", False):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": result.get("message", "feedback submission failed"),
                        "errors": result.get("errors", []),
                    },
                )
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"/api/v1/learning/feedback 异常：{e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/learning/stats")
    async def learning_stats():
        """三个学习系统总览（给前端 Dashboard 学习仪表盘）。"""
        from fastapi import HTTPException

        if _feedback_api is None:
            raise HTTPException(
                status_code=503,
                detail="Feedback API 未初始化（learning 模块缺失？详见启动日志中的 error）",
            )
        try:
            return {"success": True, "stats": _feedback_api.get_learning_stats()}
        except Exception as e:
            logger.exception(f"/api/v1/learning/stats 异常：{e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/learning/debug-state")
    async def learning_debug_state():
        """排错用：返回 FeedbackApi 内部实例状态。
        仅用于开发环境下定位“反馈历史未写入”等问题。
        """
        from fastapi import HTTPException

        if _feedback_api is None:
            raise HTTPException(
                status_code=503,
                detail="Feedback API 未初始化",
            )
        try:
            api = _feedback_api
            history_file = Path(api._history_file)
            return {
                "success": True,
                "debug": {
                    "history_dir": str(api._history_dir),
                    "history_dir_exists": bool(api._history_dir.exists()),
                    "history_file": str(history_file),
                    "history_file_exists": bool(history_file.exists()),
                    "history_file_size_bytes": int(history_file.stat().st_size)
                    if history_file.exists()
                    else 0,
                    "history_line_count": sum(
                        1 for _ in history_file.open(encoding="utf-8")
                    )
                    if history_file.exists()
                    else 0,
                    "learner_loaded": api._learner is not None,
                    "optimizer_loaded": api._optimizer is not None,
                    "memory_store_loaded": api._memory_store is not None,
                    "optimizer_data_dir": str(
                        getattr(api._optimizer, "_data_dir", "N/A")
                    )
                    if api._optimizer
                    else "N/A",
                    "memory_db_path": str(getattr(api._memory_store, "_db_path", "N/A"))
                    if api._memory_store
                    else "N/A",
                    "learner_state_dir": getattr(api._learner, "_state_dir", "N/A")
                    if api._learner
                    else "N/A",
                },
            }
        except Exception as e:
            logger.exception(f"/api/v1/learning/debug-state 异常：{e}")
            raise HTTPException(status_code=500, detail=str(e))

    logger.info(
        "Learning routes registered: /api/v1/learning/feedback + /stats + /debug-state"
    )
except Exception as _e:  # pragma: no cover
    import traceback as _tb

    logger.error(f"Learning routes 注册失败：{_e}\n{_tb.format_exc()}")


# ---- 根路径前端服务（必须在所有API路由之后注册）----
if _DASHBOARD_DIST.exists():
    _ASSETS_DIR = _DASHBOARD_DIST / "assets"
    if _ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend_root(full_path: str):
        """Catch-all: 将非API请求转发到前端index.html（SPA路由支持）"""
        # API和WebSocket路径不拦截
        if full_path.startswith("api/") or full_path.startswith("ws"):
            raise HTTPException(status_code=404)
        # 检查是否是静态文件（favicon等）
        static_file = _DASHBOARD_DIST / full_path
        if full_path and static_file.is_file():
            return FileResponse(str(static_file))
        return FileResponse(str(_DASHBOARD_DIST / "index.html"))

    logger.info(f"Dashboard frontend mounted at root -> {_DASHBOARD_DIST}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )

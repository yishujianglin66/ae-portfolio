#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 服务层
=============

提供 RESTful API 接口，封装所有核心能力为 HTTP 服务。

功能:
- 健康检查与系统状态
- 任务管理（提交/查询/取消）
- 木偶风格化工作流 API
- 视频质量评估 API
- 参数优化 API
- 批量处理 API
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

try:
    from logger import get_logger
    _logger = get_logger("api-server")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("api-server")

try:
    from batch_queue import BatchQueue, Task, TaskStatus, get_default_queue
    _BATCH_QUEUE_AVAILABLE = True
except ImportError:
    _BATCH_QUEUE_AVAILABLE = False


# ============================================================================
# Pydantic 模型定义
# ============================================================================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: float = Field(default_factory=time.time)
    uptime: float = 0.0
    services: dict[str, str] = Field(default_factory=dict)


class SystemStatsResponse(BaseModel):
    """系统统计响应"""
    tasks: dict[str, int] = Field(default_factory=dict)
    workers: int = 0
    uptime: float = 0.0
    memory_usage: float | None = None
    cpu_usage: float | None = None


class TaskSubmitRequest(BaseModel):
    """任务提交请求"""
    task_type: str = Field(..., description="任务类型: puppet_style, quality_assess, parameter_optimize")
    input_path: str | None = Field(None, description="输入文件路径")
    output_path: str | None = Field(None, description="输出文件路径")
    config: dict[str, Any] = Field(default_factory=dict, description="任务配置")
    priority: int = Field(5, ge=1, le=10, description="优先级 1-10")
    callback_url: str | None = Field(None, description="完成回调 URL")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    name: str
    status: str
    progress: float = 0.0
    progress_message: str = ""
    priority: int
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    duration: float = 0.0
    result: Any | None = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 0


class TaskListResponse(BaseModel):
    """任务列表响应"""
    total: int
    tasks: list[TaskResponse]
    page: int
    page_size: int


class PuppetStyleRequest(BaseModel):
    """木偶风格化请求"""
    input_video: str = Field(..., description="输入视频路径")
    output_dir: str = Field(..., description="输出目录")
    style: str = Field("wood", description="风格类型: wood, ceramic, cloth, stop_motion")
    auto_detect: bool = Field(True, description="自动检测人物姿态")
    quality: str = Field("high", description="输出质量: low, medium, high")
    mode: str = Field("auto", description="执行模式: real, simulate, auto")


class QualityAssessRequest(BaseModel):
    """质量评估请求"""
    reference_video: str = Field(..., description="参考视频路径")
    test_video: str = Field(..., description="待评估视频路径")
    metrics: list[str] = Field(default_factory=lambda: ["psnr", "ssim", "vmaf"])
    mode: str = Field("auto", description="执行模式")


class BatchSubmitRequest(BaseModel):
    """批量任务提交请求"""
    tasks: list[dict[str, Any]] = Field(..., description="任务列表")
    batch_name: str = Field("batch", description="批次名称")
    priority: int = Field(5, ge=1, le=10, description="优先级")


# ============================================================================
# 认证系统
# ============================================================================

try:
    from auth_system import (
        AuthManager,
        Permission,
        Role,
    )
    from auth_system import (
        get_auth_manager as _get_auth_manager,
    )
    _AUTH_AVAILABLE = True
    _auth: AuthManager | None = _get_auth_manager()
except ImportError:
    _AUTH_AVAILABLE = False
    _auth = None

_security = HTTPBearer(auto_error=False)


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(_security)):
    """认证依赖 - 要求已登录

    安全要求：fail-closed。
    当认证模块不可用（导入失败 / 未配置）时，必须拒绝访问并返回 503，
    绝不能返回 None 后由业务层隐式放行，否则会造成未授权访问。
    """
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证系统不可用，请联系管理员",
        )
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _auth.get_user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(permission: Permission):
    """权限依赖 - 要求指定权限"""
    def _checker(user: Any = Depends(require_auth)) -> Any:
        if not _AUTH_AVAILABLE or user is None:
            # 已经在 require_auth 中处理；这里再兜底
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="认证系统不可用",
            )
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足: 需要 {permission.value}",
            )
        return user
    return _checker


# ============================================================================
# 指标与监控系统
# ============================================================================

try:
    from monitoring import (
        AlertManager,
        AlertRule,
        AlertSeverity,
        MetricsRegistry,
        SystemCollector,
    )
    from monitoring import (
        get_alert_manager as _get_alert_manager,
    )
    from monitoring import (
        get_metrics_registry as _get_metrics_registry,
    )
    from monitoring import (
        get_system_collector as _get_system_collector,
    )
    _MONITORING_AVAILABLE = True
    _metrics: MetricsRegistry | None = _get_metrics_registry()
    _alerts: AlertManager | None = _get_alert_manager()
    _system_collector: SystemCollector | None = _get_system_collector(interval=15.0)
except ImportError:
    _MONITORING_AVAILABLE = False
    _metrics = None
    _alerts = None
    _system_collector = None


# ============================================================================
# 全局状态
# ============================================================================

_start_time = time.time()
_queue: BatchQueue | None = None


def get_queue() -> BatchQueue:
    """获取批处理队列单例"""
    global _queue
    if _queue is None and _BATCH_QUEUE_AVAILABLE:
        _queue = get_default_queue(max_workers=3)
    return _queue


# ============================================================================
# 任务执行函数
# ============================================================================

def _execute_puppet_style_task(config: dict[str, Any]) -> dict[str, Any]:
    """执行木偶风格化任务"""
    from pathlib import Path

    input_video = config.get("input_video", "")
    output_dir = config.get("output_dir", "./output")
    style = config.get("style", "wood")
    auto_detect = config.get("auto_detect", True)
    quality = config.get("quality", "high")
    # FIX-02/契约 §3：默认 real；simulate 仅限显式请求，且不得在异常时伪造成功
    mode = config.get("mode", "real")

    os.makedirs(output_dir, exist_ok=True)

    # FIX-02：原 except 分支在异常时伪造 frames_processed=100 等指标回 success=True，
    # 违反执行结果契约 §1/§5（诚实失败），已删除——异常直接上抛由任务队列记录失败。
    from puppet_workflow_orchestrator import PuppetWorkflowOrchestrator
    orchestrator = PuppetWorkflowOrchestrator()

    result = orchestrator.process_video(
        input_path=input_video,
        output_dir=output_dir,
        style=style,
        auto_detect=auto_detect,
        quality=quality,
        mode=mode,
    )

    return {
        "success": True,
        "style": style,
        "input_video": input_video,
        "output_dir": output_dir,
        "mode": mode,
        "execution_path": "real" if mode == "real" else ("simulated" if mode == "simulate" else "fallback"),
        "result": result if hasattr(result, '__dict__') else str(result),
    }


def _execute_quality_assessment(config: dict[str, Any]) -> dict[str, Any]:
    """执行视频质量评估任务"""
    reference = config.get("reference_video", "")
    test = config.get("test_video", "")
    metrics = config.get("metrics", ["psnr", "ssim", "vmaf"])
    # FIX-02/契约 §3：默认 real；异常不再回伪造分数（原假 psnr/ssim/vmaf 分支已删，契约 §1）
    mode = config.get("mode", "real")

    from video_quality_assessor import VideoQualityAssessor
    assessor = VideoQualityAssessor()
    result = assessor.assess(reference, test, mode=mode)
    return {
        "success": True,
        "reference_video": reference,
        "test_video": test,
        "metrics": metrics,
        "result": result if hasattr(result, '__dict__') else str(result),
        "execution_path": "real" if mode == "real" else ("simulated" if mode == "simulate" else "fallback"),
    }


def _execute_parameter_optimize(config: dict[str, Any]) -> dict[str, Any]:
    """执行参数优化任务"""
    context = config.get("context", {})
    use_feedback = config.get("use_feedback", True)
    # FIX-02/契约 §3：默认 real；异常不再回伪造优化结果（原假 optimized_params 分支已删，契约 §1）
    mode = config.get("mode", "real")

    from parameter_optimizer import EnhancedParameterOptimizer
    optimizer = EnhancedParameterOptimizer()
    from parameter_optimizer import ParameterContext
    ctx = ParameterContext(**context) if context else ParameterContext()
    result = optimizer.optimize_with_feedback(ctx, use_feedback=use_feedback)
    return {
        "success": True,
        "mode": mode,
        "execution_path": "real" if mode == "real" else ("simulated" if mode == "simulate" else "fallback"),
        "result": result if hasattr(result, '__dict__') else str(result),
    }


_TASK_HANDLERS = {
    "puppet_style": _execute_puppet_style_task,
    "quality_assess": _execute_quality_assessment,
    "parameter_optimize": _execute_parameter_optimize,
}


# ============================================================================
# FastAPI 应用
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    _logger.info("API 服务启动中...")

    if _BATCH_QUEUE_AVAILABLE:
        queue = get_queue()
        _logger.info(f"批处理队列已启动，工作线程数: {queue._max_workers}")

    if _MONITORING_AVAILABLE and _system_collector is not None:
        _system_collector.start()
        _logger.info("系统资源采集器已启动")

    if _MONITORING_AVAILABLE and _alerts is not None:
        _alerts.start(eval_interval=10.0)
        _logger.info("告警评估线程已启动")

    if _AUTH_AVAILABLE:
        _logger.info("JWT 认证系统已启用")

    yield

    _logger.info("API 服务关闭中...")
    if _queue is not None:
        _queue.stop(wait=True)
        _logger.info("批处理队列已停止")

    if _MONITORING_AVAILABLE and _system_collector is not None:
        _system_collector.stop()
        _logger.info("系统资源采集器已停止")

    if _MONITORING_AVAILABLE and _alerts is not None:
        _alerts.stop()
        _logger.info("告警评估线程已停止")


app = FastAPI(
    title="AE Knowledge Vault API",
    description="AE 知识库自动化管线 RESTful API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "AE_VAULT_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 速率限制（简易令牌桶实现）
# ============================================================================

_RATE_LIMIT_ENABLED = os.environ.get("AE_VAULT_RATE_LIMIT_ENABLED", "true").lower() == "true"
_RATE_LIMIT_PER_MINUTE = int(os.environ.get("AE_VAULT_RATE_LIMIT_PER_MINUTE", "60"))
_rate_limit_buckets: dict[str, dict[str, float]] = defaultdict(
    lambda: {"tokens": float(_RATE_LIMIT_PER_MINUTE), "last_time": time.time()}
)
_rate_limit_lock = asyncio.Lock()


def _get_client_ip(request: Request) -> str:
    """获取客户端 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check_rate_limit(client_id: str) -> bool:
    """检查速率限制，返回 True 表示允许通过"""
    if not _RATE_LIMIT_ENABLED:
        return True
    async with _rate_limit_lock:
        now = time.time()
        bucket = _rate_limit_buckets[client_id]
        elapsed = now - bucket["last_time"]
        bucket["last_time"] = now
        bucket["tokens"] = min(
            _RATE_LIMIT_PER_MINUTE,
            bucket["tokens"] + elapsed * (_RATE_LIMIT_PER_MINUTE / 60.0)
        )
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """速率限制中间件"""
    if request.method == "OPTIONS":
        return await call_next(request)
    client_id = _get_client_ip(request)
    if not await _check_rate_limit(client_id):
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded", "message": "请求过于频繁，请稍后再试"},
            headers={"Retry-After": "60"}
        )
    response = await call_next(request)
    return response


# ============================================================================
# Prometheus 指标中间件
# ============================================================================

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """HTTP 请求指标采集"""
    if not _MONITORING_AVAILABLE or _metrics is None:
        return await call_next(request)

    start_time = time.time()
    method = request.method
    endpoint = request.url.path

    try:
        _metrics.gauge("http_requests_in_progress").inc(labels={"method": method})
        _metrics.counter("http_requests_total").inc(
            labels={"method": method, "endpoint": endpoint}
        )
    except Exception:
        pass

    response = None
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        try:
            _metrics.counter("http_requests_total").inc(
                labels={"method": method, "endpoint": endpoint, "status": status_code}
            )
        except Exception:
            pass
        return response
    except Exception as e:
        try:
            _metrics.counter("http_requests_total").inc(
                labels={"method": method, "endpoint": endpoint, "status": "500"}
            )
        except Exception:
            pass
        raise
    finally:
        duration = time.time() - start_time
        try:
            _metrics.histogram("http_request_duration_seconds").observe(
                duration, labels={"method": method, "endpoint": endpoint}
            )
            _metrics.gauge("http_requests_in_progress").dec(labels={"method": method})
        except Exception:
            pass


# ============================================================================
# 健康检查
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查端点"""
    uptime = time.time() - _start_time
    services = {"api": "healthy"}

    if _BATCH_QUEUE_AVAILABLE and _queue is not None:
        services["batch_queue"] = "healthy"
    if _AUTH_AVAILABLE and _auth is not None:
        services["auth"] = "healthy"
    if _MONITORING_AVAILABLE and _metrics is not None:
        services["monitoring"] = "healthy"

    return HealthResponse(
        status="healthy",
        uptime=uptime,
        services=services,
    )


@app.get("/health/live", tags=["系统"])
async def liveness_probe():
    """存活探针"""
    return {"status": "alive"}


@app.get("/health/ready", tags=["系统"])
async def readiness_probe():
    """就绪探针"""
    ready = True
    checks = {"api": True}

    if _BATCH_QUEUE_AVAILABLE:
        checks["batch_queue"] = _queue is not None
        ready = ready and checks["batch_queue"]

    return {
        "ready": ready,
        "checks": checks,
    }


# ============================================================================
# 系统统计
# ============================================================================

@app.get("/api/v1/stats", response_model=SystemStatsResponse, tags=["系统"])
async def get_system_stats():
    """获取系统统计信息"""
    uptime = time.time() - _start_time
    tasks_stats = {}
    workers = 0

    if _BATCH_QUEUE_AVAILABLE and _queue is not None:
        stats = _queue.get_stats()
        tasks_stats = {
            "total_submitted": stats["total_submitted"],
            "total_completed": stats["total_completed"],
            "total_failed": stats["total_failed"],
            "pending": stats["pending"],
            "running": stats["running"],
        }
        workers = stats["max_workers"]

    memory_usage = None
    cpu_usage = None
    try:
        import psutil
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=0.1)
    except ImportError:
        pass

    return SystemStatsResponse(
        tasks=tasks_stats,
        workers=workers,
        uptime=uptime,
        memory_usage=memory_usage,
        cpu_usage=cpu_usage,
    )


# ============================================================================
# Prometheus /metrics 端点
# ============================================================================

@app.get("/metrics", tags=["监控"])
async def prometheus_metrics():
    """Prometheus 指标导出端点"""
    if not _MONITORING_AVAILABLE or _metrics is None:
        return PlainTextResponse("", media_type="text/plain")
    return PlainTextResponse(_metrics.export(), media_type="text/plain")


@app.get("/api/v1/metrics/summary", tags=["监控"])
async def metrics_summary(user: Any = Depends(require_auth)):
    """指标摘要 (JSON 格式，含友好结构)"""
    if not _MONITORING_AVAILABLE or _metrics is None:
        return {"error": "monitoring not available", "metrics": {}}
    data = _metrics.export_dict()

    system_metrics: dict[str, float] = {}
    cpu_metric = data.get("system_cpu_percent")
    if cpu_metric and cpu_metric["samples"]:
        system_metrics["cpu_percent"] = cpu_metric["samples"][0]["value"]
    mem_metric = data.get("system_memory_percent")
    if mem_metric and mem_metric["samples"]:
        system_metrics["memory_percent"] = mem_metric["samples"][0]["value"]
    disk_metric = data.get("system_disk_percent")
    if disk_metric and disk_metric["samples"]:
        system_metrics["disk_percent"] = disk_metric["samples"][0]["value"]
    uptime_metric = data.get("app_uptime_seconds")
    if uptime_metric and uptime_metric["samples"]:
        system_metrics["uptime_seconds"] = uptime_metric["samples"][0]["value"]

    http_total = 0
    http_errors = 0
    http_latency_sum = 0.0
    http_latency_count = 0
    req_total = data.get("http_requests_total")
    if req_total and req_total["samples"]:
        for s in req_total["samples"]:
            v = float(s["value"])
            http_total += v
            status = s["labels"].get("status", "")
            if status.startswith("4") or status.startswith("5"):
                http_errors += v
    latencies = data.get("http_request_duration_seconds")
    if latencies and latencies["samples"]:
        for s in latencies["samples"]:
            if s.get("name") == "http_request_duration_seconds_sum":
                http_latency_sum = float(s["value"])
            elif s.get("name") == "http_request_duration_seconds_count":
                http_latency_count = float(s["value"])

    http_requests = {
        "total": int(http_total),
        "error_count": int(http_errors),
        "error_rate": (http_errors / http_total * 100) if http_total > 0 else 0.0,
        "avg_latency_ms": (http_latency_sum / http_latency_count * 1000) if http_latency_count > 0 else 0.0,
    }

    return {
        "total_metrics": len(data),
        "metrics": data,
        "system_metrics": system_metrics,
        "http_requests": http_requests,
    }


# ============================================================================
# 认证 API
# ============================================================================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., description="密码")
    role: str = Field("viewer", description="角色: admin/operator/viewer")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., description="新密码")


class RefreshRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str = Field(..., description="刷新令牌")


@app.post("/api/v1/auth/login", tags=["认证"])
async def login(request: LoginRequest):
    """用户登录"""
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")

    try:
        user, tokens = _auth.authenticate(request.username, request.password)
        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": "Bearer",
            "expires_in": tokens.expires_in,
            "user": user.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/api/v1/auth/refresh", tags=["认证"])
async def refresh_tokens(request: RefreshRequest):
    """刷新访问令牌"""
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")

    try:
        tokens = _auth.refresh_token(request.refresh_token)
        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": "Bearer",
            "expires_in": tokens.expires_in,
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/api/v1/auth/logout", tags=["认证"])
async def logout(user: Any = Depends(require_auth), credentials: HTTPAuthorizationCredentials | None = Depends(_security)):
    """用户登出 (撤销当前令牌)"""
    if not _AUTH_AVAILABLE or _auth is None:
        return {"logged_out": True}
    if credentials and user:
        try:
            import jwt as _
        except ImportError:
            pass
        try:
            from auth_system import jwt_decode
            payload = jwt_decode(credentials.credentials, _auth.secret_key)
            token_id = payload.get("jti", "")
            exp = payload.get("exp", time.time() + 3600)
            _auth.logout(token_id, exp, user.user_id, user.username)
        except Exception:
            pass
    return {"logged_out": True}


@app.get("/api/v1/auth/me", tags=["认证"])
async def get_current_user(user: Any = Depends(require_auth)):
    """获取当前用户信息"""
    if user is None:
        raise HTTPException(status_code=401, detail="未认证")
    return user.to_dict()


@app.post("/api/v1/auth/change-password", tags=["认证"])
async def change_password(request: ChangePasswordRequest, user: Any = Depends(require_auth)):
    """修改当前用户密码"""
    if not _AUTH_AVAILABLE or _auth is None or user is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")

    try:
        _auth.change_password(user.user_id, request.old_password, request.new_password)
        return {"success": True, "message": "密码修改成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# 用户管理 API (admin 权限)
# ============================================================================

@app.get("/api/v1/users", tags=["用户管理"])
async def list_users(user: Any = Depends(require_auth)):
    """获取用户列表 (需 admin 权限)"""
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")
    if user is None or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    users = _auth.users.list_users()
    return {
        "users": [u.to_dict() for u in users],
        "total": len(users),
    }


@app.post("/api/v1/users", tags=["用户管理"])
async def create_user_api(request: RegisterRequest, user: Any = Depends(require_auth)):
    """创建新用户 (需 admin 权限)"""
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")
    if user is None or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效角色: {request.role}")

    try:
        new_user = _auth.register_user(
            username=request.username,
            email=request.email,
            password=request.password,
            role=role,
        )
        return {"user": new_user.to_dict(), "created": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/users/{user_id}", tags=["用户管理"])
async def get_user_detail(user_id: str, user: Any = Depends(require_auth)):
    """获取用户详情 (需 admin 权限)"""
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")
    if user is None or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    target = _auth.users.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")
    return target.to_dict()


@app.put("/api/v1/users/{user_id}", tags=["用户管理"])
async def update_user_api(user_id: str, updates: dict[str, Any], user: Any = Depends(require_auth)):
    """更新用户信息 (需 admin 权限)"""
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")
    if user is None or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        updated = _auth.update_user(user_id, updates, operator=user)
        return {"user": updated.to_dict(), "updated": True}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/users/{user_id}", tags=["用户管理"])
async def delete_user_api(user_id: str, user: Any = Depends(require_auth)):
    """删除用户 (需 admin 权限)"""
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")
    if user is None or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        ok = _auth.delete_user(user_id, operator=user)
        if not ok:
            raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")
        return {"deleted": True, "user_id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/auth/audit-log", tags=["认证"])
async def get_audit_log(
    action: str | None = Query(None, description="按操作过滤"),
    limit: int = Query(50, ge=1, le=500),
    user: Any = Depends(require_auth),
):
    """获取审计日志 (需 admin 权限)"""
    if not _AUTH_AVAILABLE or _auth is None:
        raise HTTPException(status_code=503, detail="认证系统不可用")
    if user is None or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    entries = _auth.audit.list_entries(action=action, limit=limit)
    return {
        "entries": [
            {
                "log_id": e.log_id,
                "user_id": e.user_id,
                "username": e.username,
                "action": e.action,
                "resource": e.resource,
                "timestamp": e.timestamp,
                "ip_address": e.ip_address,
                "success": e.success,
                "details": e.details,
            }
            for e in entries
        ],
        "total": len(entries),
    }


# ============================================================================
# 告警 API
# ============================================================================

@app.get("/api/v1/alerts/active", tags=["告警"])
async def list_active_alerts(user: Any = Depends(require_auth)):
    """获取活跃告警列表"""
    if not _MONITORING_AVAILABLE or _alerts is None:
        return {"alerts": [], "total": 0}

    alerts = _alerts.list_active_alerts()
    return {
        "alerts": [a.to_dict() for a in alerts],
        "total": len(alerts),
    }


@app.get("/api/v1/alerts/history", tags=["告警"])
async def list_alert_history(
    limit: int = Query(50, ge=1, le=500),
    user: Any = Depends(require_auth),
):
    """获取告警历史"""
    if not _MONITORING_AVAILABLE or _alerts is None:
        return {"alerts": [], "total": 0}

    alerts = _alerts.list_history(limit=limit)
    return {
        "alerts": [a.to_dict() for a in alerts],
        "total": len(alerts),
    }


# ============================================================================
# 任务管理
# ============================================================================

def _task_to_response(task: Task) -> TaskResponse:
    """将 Task 对象转换为响应模型"""
    return TaskResponse(
        task_id=task.task_id,
        name=task.name,
        status=task.status.value,
        progress=task.progress,
        progress_message=task.progress_message,
        priority=task.priority,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        duration=task.duration,
        result=task.result,
        error=task.error,
        retries=task.retries,
        max_retries=task.max_retries,
    )


@app.post("/api/v1/tasks", response_model=TaskResponse, tags=["任务"])
async def submit_task(
    request: TaskSubmitRequest,
    background_tasks: BackgroundTasks,
    user: Any = Depends(require_auth),
):
    """提交任务"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()

    handler = _TASK_HANDLERS.get(request.task_type)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的任务类型: {request.task_type}，支持的类型: {list(_TASK_HANDLERS.keys())}"
        )

    task_config = {
        "input_path": request.input_path,
        "output_path": request.output_path,
        **request.config,
    }

    def task_wrapper():
        return handler(task_config)

    task = queue.submit(
        task_wrapper,
        name=f"{request.task_type}-{uuid.uuid4().hex[:6]}",
        priority=request.priority,
        max_retries=2,
        metadata={"task_type": request.task_type, "callback_url": request.callback_url},
    )

    return _task_to_response(task)


@app.get("/api/v1/tasks", response_model=TaskListResponse, tags=["任务"])
async def list_tasks(
    status: str | None = Query(None, description="按状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user: Any = Depends(require_auth),
):
    """获取任务列表"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()

    if status:
        try:
            task_status = TaskStatus(status)
            tasks = queue.get_tasks_by_status(task_status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的状态: {status}")
    else:
        tasks = queue.get_all_tasks()

    tasks.sort(key=lambda t: t.created_at, reverse=True)

    total = len(tasks)
    start = (page - 1) * page_size
    end = start + page_size
    page_tasks = tasks[start:end]

    return TaskListResponse(
        total=total,
        tasks=[_task_to_response(t) for t in page_tasks],
        page=page,
        page_size=page_size,
    )


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse, tags=["任务"])
async def get_task(task_id: str, user: Any = Depends(require_auth)):
    """获取任务详情"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    return _task_to_response(task)


@app.post("/api/v1/tasks/{task_id}/cancel", response_model=TaskResponse, tags=["任务"])
async def cancel_task(
    task_id: str,
    user: Any = Depends(require_auth),
):
    """取消任务"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()
    success = queue.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"无法取消任务: {task_id}")

    task = queue.get_task(task_id)
    return _task_to_response(task)


@app.post("/api/v1/tasks/{task_id}/wait", response_model=TaskResponse, tags=["任务"])
async def wait_for_task(
    task_id: str,
    timeout: float = Query(60.0, ge=1.0, le=600.0),
    user: Any = Depends(require_auth),
):
    """等待任务完成"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()
    task = queue.wait_for_task(task_id, timeout=timeout)
    return _task_to_response(task)


# ============================================================================
# 木偶风格化 API
# ============================================================================

@app.post("/api/v1/puppet/style", response_model=TaskResponse, tags=["木偶风格化"])
async def puppet_style(
    request: PuppetStyleRequest,
    background_tasks: BackgroundTasks,
    user: Any = Depends(require_auth),
):
    """提交木偶风格化任务"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()

    config = request.model_dump()

    def style_task():
        return _execute_puppet_style_task(config)

    task = queue.submit(
        style_task,
        name=f"puppet-{request.style}-{uuid.uuid4().hex[:6]}",
        priority=6,
        max_retries=1,
        metadata={"task_type": "puppet_style", "style": request.style},
    )

    return _task_to_response(task)


@app.get("/api/v1/puppet/styles", tags=["木偶风格化"])
async def list_puppet_styles():
    """获取支持的木偶风格列表"""
    return {
        "styles": [
            {"id": "wood", "name": "木质木偶", "description": "经典木质纹理木偶效果"},
            {"id": "ceramic", "name": "陶瓷娃娃", "description": "光滑陶瓷质感效果"},
            {"id": "cloth", "name": "布偶", "description": "布艺玩偶柔软质感"},
            {"id": "stop_motion", "name": "定格动画", "description": "逐帧定格动画效果"},
            {"id": "paper", "name": "纸艺", "description": "纸剪艺术风格"},
            {"id": "clay", "name": "黏土", "description": "黏土动画质感"},
        ],
        "total": 6,
    }


# ============================================================================
# 视频质量评估 API
# ============================================================================

@app.post("/api/v1/quality/assess", response_model=TaskResponse, tags=["质量评估"])
async def quality_assess(
    request: QualityAssessRequest,
    background_tasks: BackgroundTasks,
    user: Any = Depends(require_auth),
):
    """提交视频质量评估任务"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()

    config = request.model_dump()

    def assess_task():
        return _execute_quality_assessment(config)

    task = queue.submit(
        assess_task,
        name=f"quality-{uuid.uuid4().hex[:6]}",
        priority=5,
        max_retries=1,
        metadata={"task_type": "quality_assess"},
    )

    return _task_to_response(task)


@app.get("/api/v1/quality/metrics", tags=["质量评估"])
async def list_quality_metrics():
    """获取支持的质量评估指标"""
    return {
        "metrics": [
            {"id": "psnr", "name": "PSNR", "description": "峰值信噪比，单位 dB", "higher_is_better": True},
            {"id": "ssim", "name": "SSIM", "description": "结构相似性指数，范围 0-1", "higher_is_better": True},
            {"id": "vmaf", "name": "VMAF", "description": "视频多方法评估融合，范围 0-100", "higher_is_better": True},
            {"id": "brisque", "name": "BRISQUE", "description": "无参考图像质量评估，越低越好", "higher_is_better": False},
        ],
        "total": 4,
    }


# ============================================================================
# 参数优化 API
# ============================================================================

@app.post("/api/v1/optimize/parameters", response_model=TaskResponse, tags=["参数优化"])
async def optimize_parameters(
    context: dict[str, Any],
    use_feedback: bool = Query(True, description="是否使用历史反馈"),
    mode: str = Query("auto", description="执行模式"),
    user: Any = Depends(require_auth),
):
    """提交参数优化任务"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()

    config = {
        "context": context,
        "use_feedback": use_feedback,
        "mode": mode,
    }

    def optimize_task():
        return _execute_parameter_optimize(config)

    task = queue.submit(
        optimize_task,
        name=f"optimize-{uuid.uuid4().hex[:6]}",
        priority=4,
        max_retries=2,
        metadata={"task_type": "parameter_optimize"},
    )

    return _task_to_response(task)


# ============================================================================
# 批量处理 API
# ============================================================================

@app.post("/api/v1/batch", tags=["批量处理"])
async def submit_batch(
    request: BatchSubmitRequest,
    user: Any = Depends(require_auth),
):
    """批量提交任务"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    queue = get_queue()

    task_list = []
    for task_config in request.tasks:
        task_type = task_config.get("task_type", "")
        handler = _TASK_HANDLERS.get(task_type)
        if not handler:
            continue

        config = task_config.get("config", {})

        def make_task_handler(h, c):
            def task_func():
                return h(c)
            return task_func

        task_list.append((
            make_task_handler(handler, config),
            (),
            {"name": f"{request.batch_name}-{len(task_list)}", "priority": request.priority},
        ))

    tasks = queue.submit_batch(
        [(f, a, k) for f, a, k in task_list],
        batch_name=request.batch_name,
        priority=request.priority,
    )

    return {
        "batch_id": f"batch_{uuid.uuid4().hex[:12]}",
        "batch_name": request.batch_name,
        "total_tasks": len(tasks),
        "tasks": [_task_to_response(t) for t in tasks],
    }


# ============================================================================
# WebSocket 实时进度
# ============================================================================

class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket, token: str | None = Query(None)):
    """WebSocket 实时进度推送

    认证方式：通过 query 参数 token 传递 Bearer Token。
    示例：ws://host/ws/progress?token=<jwt_token>
    """
    if not _AUTH_AVAILABLE or _auth is None:
        await websocket.close(code=1013, reason="认证系统不可用")
        return

    if not token:
        await websocket.close(code=1008, reason="未提供认证令牌")
        return

    user = _auth.get_user_from_token(token)
    if not user:
        await websocket.close(code=1008, reason="令牌无效或用户不存在")
        return

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")

            if action == "subscribe":
                task_id = data.get("task_id")
                await websocket.send_json({"type": "subscribed", "task_id": task_id})

            elif action == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================================
# 效果库 API
# ============================================================================

@app.get("/api/v1/effects", tags=["效果库"])
async def list_effects(category: str | None = Query(None, description="按分类过滤")):
    """获取效果列表"""
    effects = [
        {
            "id": "ADBE Glo2",
            "name": "发光",
            "name_en": "Glow",
            "category": "视觉效果",
            "icon": "Sparkles",
            "description": "为图层添加发光效果",
            "params": [
                {"name": "发光半径", "value": 20, "min": 0, "max": 100, "unit": "px"},
                {"name": "发光强度", "value": 0.8, "min": 0, "max": 2, "unit": ""},
                {"name": "发光颜色", "value": 0.5, "min": 0, "max": 1, "unit": ""},
            ],
        },
        {
            "id": "ADBE Blur",
            "name": "模糊",
            "name_en": "Gaussian Blur",
            "category": "视觉效果",
            "icon": "Wind",
            "description": "高斯模糊效果",
            "params": [
                {"name": "模糊量", "value": 10, "min": 0, "max": 50, "unit": "px"},
                {"name": "模糊类型", "value": 1, "min": 0, "max": 3, "unit": ""},
            ],
        },
        {
            "id": "ADBE Particular",
            "name": "粒子",
            "name_en": "Particular",
            "category": "特效",
            "icon": "CircleDot",
            "description": "粒子发射器效果",
            "params": [
                {"name": "粒子数量", "value": 100, "min": 1, "max": 1000, "unit": ""},
                {"name": "粒子大小", "value": 5, "min": 1, "max": 50, "unit": "px"},
                {"name": "发射速率", "value": 10, "min": 1, "max": 100, "unit": "/s"},
            ],
        },
        {
            "id": "ADBE Noise",
            "name": "噪波",
            "name_en": "Noise",
            "category": "视觉效果",
            "icon": "Zap",
            "description": "添加噪波纹理",
            "params": [
                {"name": "噪波量", "value": 20, "min": 0, "max": 100, "unit": "%"},
                {"name": "噪波类型", "value": 0, "min": 0, "max": 2, "unit": ""},
            ],
        },
        {
            "id": "ADBE Ramp",
            "name": "渐变",
            "name_en": "Ramp",
            "category": "生成效果",
            "icon": "Layers",
            "description": "渐变填充效果",
            "params": [
                {"name": "起始颜色", "value": 0, "min": 0, "max": 1, "unit": ""},
                {"name": "结束颜色", "value": 1, "min": 0, "max": 1, "unit": ""},
                {"name": "渐变角度", "value": 90, "min": 0, "max": 360, "unit": "°"},
            ],
        },
        {
            "id": "ADBE Drop Shadow",
            "name": "阴影",
            "name_en": "Drop Shadow",
            "category": "透视",
            "icon": "Square",
            "description": "投影效果",
            "params": [
                {"name": "不透明度", "value": 50, "min": 0, "max": 100, "unit": "%"},
                {"name": "距离", "value": 10, "min": 0, "max": 100, "unit": "px"},
                {"name": "柔度", "value": 5, "min": 0, "max": 50, "unit": "px"},
            ],
        },
        {
            "id": "ADBE Color Balance",
            "name": "色彩平衡",
            "name_en": "Color Balance",
            "category": "颜色校正",
            "icon": "Palette",
            "description": "调整色彩平衡",
            "params": [
                {"name": "红色", "value": 0, "min": -100, "max": 100, "unit": ""},
                {"name": "绿色", "value": 0, "min": -100, "max": 100, "unit": ""},
                {"name": "蓝色", "value": 0, "min": -100, "max": 100, "unit": ""},
            ],
        },
        {
            "id": "ADBE Motion Tile",
            "name": "动态平铺",
            "name_en": "Motion Tile",
            "category": "扭曲",
            "icon": "Grid",
            "description": "平铺图层内容",
            "params": [
                {"name": "平铺宽度", "value": 100, "min": 1, "max": 600, "unit": "%"},
                {"name": "平铺高度", "value": 100, "min": 1, "max": 600, "unit": "%"},
            ],
        },
    ]

    if category:
        effects = [e for e in effects if e["category"] == category]

    categories = list(set(e["category"] for e in effects))

    return {
        "effects": effects,
        "total": len(effects),
        "categories": categories,
    }


@app.get("/api/v1/effects/categories", tags=["效果库"])
async def list_effect_categories():
    """获取效果分类列表"""
    return {
        "categories": [
            {"id": "visual", "name": "视觉效果", "count": 4},
            {"id": "special", "name": "特效", "count": 1},
            {"id": "generate", "name": "生成效果", "count": 1},
            {"id": "perspective", "name": "透视", "count": 1},
            {"id": "color", "name": "颜色校正", "count": 1},
            {"id": "distort", "name": "扭曲", "count": 1},
        ]
    }


# ============================================================================
# 风格模板 API
# ============================================================================

@app.get("/api/v1/styles", tags=["风格模板"])
async def list_styles():
    """获取风格模板列表"""
    styles = [
        {
            "id": "cinematic",
            "name": "电影感",
            "description": "深邃的色彩分级和电影质感",
            "effects": ["发光", "模糊", "渐变"],
            "intensity": 0.8,
            "thumbnail": "",
        },
        {
            "id": "cyberpunk",
            "name": "赛博朋克",
            "description": "霓虹灯光和未来感视觉效果",
            "effects": ["发光", "粒子", "渐变"],
            "intensity": 1.0,
            "thumbnail": "",
        },
        {
            "id": "minimal",
            "name": "极简",
            "description": "干净简洁的视觉风格",
            "effects": ["模糊"],
            "intensity": 0.3,
            "thumbnail": "",
        },
        {
            "id": "vintage",
            "name": "复古",
            "description": "怀旧的复古胶片质感",
            "effects": ["噪波", "渐变"],
            "intensity": 0.7,
            "thumbnail": "",
        },
        {
            "id": "dreamy",
            "name": "梦幻",
            "description": "柔和梦幻的视觉效果",
            "effects": ["发光", "模糊"],
            "intensity": 0.6,
            "thumbnail": "",
        },
        {
            "id": "puppet_wood",
            "name": "木质木偶",
            "description": "经典木质纹理木偶效果",
            "effects": ["色彩平衡", "噪波"],
            "intensity": 0.9,
            "thumbnail": "",
        },
    ]

    return {
        "styles": styles,
        "total": len(styles),
    }


@app.get("/api/v1/styles/{style_id}", tags=["风格模板"])
async def get_style(style_id: str):
    """获取风格模板详情"""
    styles_response = await list_styles()
    for style in styles_response["styles"]:
        if style["id"] == style_id:
            return style
    raise HTTPException(status_code=404, detail=f"风格模板不存在: {style_id}")


# ============================================================================
# 项目管理 API
# ============================================================================

# 内存存储（后续可替换为数据库）
_projects_store: dict[str, dict[str, Any]] = {}


@app.get("/api/v1/projects", tags=["项目管理"])
async def list_projects(
    status: str | None = Query(None, description="按状态过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取项目列表"""
    projects = list(_projects_store.values())

    if status:
        projects = [p for p in projects if p.get("status") == status]

    projects.sort(key=lambda p: p.get("createdAt", ""), reverse=True)

    total = len(projects)
    start = (page - 1) * page_size
    end = start + page_size
    page_projects = projects[start:end]

    return {
        "projects": page_projects,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.post("/api/v1/projects", tags=["项目管理"])
async def create_project(
    project_data: dict[str, Any],
    user: Any = Depends(require_auth),
):
    """创建项目"""
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    now = time.time()

    project = {
        "id": project_id,
        "name": project_data.get("name", "未命名项目"),
        "description": project_data.get("description", ""),
        "status": "draft",
        "createdAt": now,
        "updatedAt": now,
        "duration": project_data.get("duration", 0),
        "sceneCount": project_data.get("sceneCount", 0),
        "width": project_data.get("width", 1920),
        "height": project_data.get("height", 1080),
        "frameRate": project_data.get("frameRate", 30),
        "scenes": project_data.get("scenes", []),
        "appliedEffects": project_data.get("appliedEffects", []),
    }

    _projects_store[project_id] = project

    return project


@app.get("/api/v1/projects/{project_id}", tags=["项目管理"])
async def get_project_detail(project_id: str):
    """获取项目详情"""
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")
    return project


@app.put("/api/v1/projects/{project_id}", tags=["项目管理"])
async def update_project(
    project_id: str,
    updates: dict[str, Any],
    user: Any = Depends(require_auth),
):
    """更新项目"""
    project = _projects_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

    for key, value in updates.items():
        if key != "id":
            project[key] = value

    project["updatedAt"] = time.time()

    return project


@app.delete("/api/v1/projects/{project_id}", tags=["项目管理"])
async def delete_project(
    project_id: str,
    user: Any = Depends(require_auth),
):
    """删除项目"""
    if project_id not in _projects_store:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")

    deleted = _projects_store.pop(project_id)
    return {"deleted": True, "project_id": project_id, "name": deleted.get("name")}


# ============================================================================
# 历史记录 API
# ============================================================================

_history_store: list[dict[str, Any]] = []


@app.get("/api/v1/history", tags=["历史记录"])
async def list_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    result: str | None = Query(None, description="按结果过滤"),
):
    """获取历史记录"""
    history = list(reversed(_history_store))

    if result:
        history = [h for h in history if h.get("result") == result]

    total = len(history)
    page_history = history[offset:offset + limit]

    return {
        "history": page_history,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.post("/api/v1/history", tags=["历史记录"])
async def add_history(
    item: dict[str, Any],
    user: Any = Depends(require_auth),
):
    """添加历史记录"""
    record = {
        "id": f"hist_{uuid.uuid4().hex[:12]}",
        "action": item.get("action", ""),
        "timestamp": time.time(),
        "result": item.get("result", "success"),
        "details": item.get("details", ""),
        "projectId": item.get("projectId"),
        "params": item.get("params"),
    }

    _history_store.append(record)

    if len(_history_store) > 500:
        _history_store[:] = _history_store[-500:]

    return record


# ============================================================================
# 工具链 API 集成
# ============================================================================

try:
    from toolchain_api import get_toolchain_manager, register_toolchain_routes
    _TOOLCHAIN_AVAILABLE = True
    register_toolchain_routes(app)
    _logger.info("工具链 API 路由已注册")
except ImportError as e:
    _TOOLCHAIN_AVAILABLE = False
    _logger.warning(f"工具链 API 模块导入失败: {e}")


@app.get("/api/v1/toolchain/status", tags=["工具链"])
async def toolchain_status():
    """获取工具链状态"""
    if not _TOOLCHAIN_AVAILABLE:
        return {"status": "unavailable", "error": "工具链模块未安装"}

    try:
        manager = get_toolchain_manager()
        status = manager.get_all_tool_status()
        return {
            "status": "healthy",
            "total_tools": status["total_tools"],
            "categories": status["categories"],
            "engine_count": len([t for t in status["tools"] if t["category"] == "engine"]),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.delete("/api/v1/history", tags=["历史记录"])
async def clear_history(
    user: Any = Depends(require_auth),
):
    """清空历史记录"""
    count = len(_history_store)
    _history_store.clear()
    return {"cleared": True, "count": count}


# ============================================================================
# 资源监控 API
# ============================================================================

@app.get("/api/v1/resources", tags=["资源监控"])
async def get_resources():
    """获取系统资源信息"""
    try:
        from resource_manager import get_resource_manager
        manager = get_resource_manager()
        return manager.get_summary()
    except ImportError:
        return {
            "error": "resource_manager not available",
            "cpu": {"usage_percent": 0, "logical_cores": 0},
            "memory": {"percent": 0, "used_gb": 0, "total_gb": 0},
            "gpus": [],
            "disks": [],
        }


# ============================================================================
# 工作流 API
# ============================================================================

@app.post("/api/v1/workflow/puppet", response_model=TaskResponse, tags=["工作流"])
async def submit_puppet_workflow(
    input_video: str,
    output_dir: str,
    style: str = "wood",
    auto_detect: bool = True,
    quality: str = "high",
    mode: str = "auto",
    priority: int = Query(5, ge=1, le=10),
    user: Any = Depends(require_auth),
):
    """提交木偶风格化工作流（多阶段流水线）"""
    if not _BATCH_QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="批处理队列不可用")

    try:
        from workflow_batch_integration import get_workflow_batch_integration
        integration = get_workflow_batch_integration()

        wf_task = integration.submit_puppet_workflow(
            input_path=input_video,
            output_dir=output_dir,
            style=style,
            auto_detect=auto_detect,
            quality=quality,
            mode=mode,
            priority=priority,
        )

        return TaskResponse(
            task_id=wf_task.task_id,
            name=wf_task.name,
            status=wf_task.status,
            progress=wf_task.progress,
            progress_message=wf_task.progress_message,
            priority=wf_task.priority,
            created_at=wf_task.created_at,
            started_at=wf_task.started_at,
            completed_at=wf_task.completed_at,
            duration=wf_task.duration,
            result=wf_task.result,
            error=wf_task.error,
            retries=0,
            max_retries=1,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/workflow/{task_id}", tags=["工作流"])
async def get_workflow_status(task_id: str, user: Any = Depends(require_auth)):
    """获取工作流状态"""
    try:
        from workflow_batch_integration import get_workflow_batch_integration
        integration = get_workflow_batch_integration()

        wf_task = integration.get_workflow_task(task_id)
        if not wf_task:
            raise HTTPException(status_code=404, detail=f"工作流任务不存在: {task_id}")

        return wf_task.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 插件系统 API
# ============================================================================

@app.get("/api/v1/plugins", tags=["插件系统"])
async def list_plugins():
    """获取插件列表"""
    try:
        from plugin_system import get_plugin_manager
        manager = get_plugin_manager()
        return {
            "plugins": manager.list_plugins(),
            "total": len(manager.list_plugins()),
        }
    except ImportError:
        return {"plugins": [], "total": 0, "error": "plugin_system not available"}


@app.get("/api/v1/plugins/stats", tags=["插件系统"])
async def get_plugin_stats():
    """获取插件统计信息"""
    try:
        from plugin_system import get_plugin_manager
        manager = get_plugin_manager()
        return manager.get_stats()
    except ImportError:
        return {"error": "plugin_system not available"}


@app.post("/api/v1/plugins/{plugin_id}/enable", tags=["插件系统"])
async def enable_plugin_api(
    plugin_id: str,
    user: Any = Depends(require_auth),
):
    """启用插件"""
    try:
        from plugin_system import get_plugin_manager
        manager = get_plugin_manager()
        success = manager.enable_plugin(plugin_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"无法启用插件: {plugin_id}")
        return {"enabled": True, "plugin_id": plugin_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/plugins/{plugin_id}/disable", tags=["插件系统"])
async def disable_plugin_api(
    plugin_id: str,
    user: Any = Depends(require_auth),
):
    """禁用插件"""
    try:
        from plugin_system import get_plugin_manager
        manager = get_plugin_manager()
        success = manager.disable_plugin(plugin_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"无法禁用插件: {plugin_id}")
        return {"disabled": True, "plugin_id": plugin_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/plugins/{plugin_id}/reload", tags=["插件系统"])
async def reload_plugin_api(
    plugin_id: str,
    user: Any = Depends(require_auth),
):
    """重新加载插件"""
    try:
        from plugin_system import get_plugin_manager
        manager = get_plugin_manager()
        success = manager.reload_plugin(plugin_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"无法重载插件: {plugin_id}")
        return {"reloaded": True, "plugin_id": plugin_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/plugins/discover", tags=["插件系统"])
async def discover_plugins_api(
    user: Any = Depends(require_auth),
):
    """发现新插件"""
    try:
        from plugin_system import get_plugin_manager
        manager = get_plugin_manager()
        discovered = manager.discover_plugins()
        return {"discovered": discovered, "count": len(discovered)}
    except ImportError:
        return {"error": "plugin_system not available"}


# ============================================================================
# 视频风格智能复制 API
# ============================================================================

try:
    from style_copy.api import register as register_style_copy
    register_style_copy(app)
    _logger.info("视频风格智能复制 API 已注册")
except ImportError:
    _logger.warning("视频风格智能复制 API 不可用")


# ============================================================================
# AI Chat API 集成（V4 原生 Tool Calling 对接）
# ============================================================================

try:
    from ai_chat_api import register_ai_chat_routes
    register_ai_chat_routes(app)
    _logger.info("AI Chat API（V4 Tool Calling）已注册")
except ImportError as e:
    _logger.warning(f"AI Chat API 模块导入失败: {e}")


# ============================================================================
# 工具执行引擎 API（模型驱动）
# ============================================================================

class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    tool_name: str = Field(..., description="工具名称")
    arguments: dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolOrchestrateRequest(BaseModel):
    """模型驱动工具编排请求"""
    user_request: str = Field(..., description="用户自然语言请求")
    max_tool_calls: int = Field(5, ge=1, le=20, description="最大工具调用次数")


class ToolListResponse(BaseModel):
    """工具列表响应"""
    tools: list[dict[str, Any]]
    total: int


@app.get("/api/v1/tools", response_model=ToolListResponse, tags=["工具执行引擎"])
async def list_tools():
    """获取所有可用工具列表"""
    try:
        from tool_executor import get_executor
        executor = get_executor()
        tools = []
        for name, tool in executor.tools.items():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "type": tool.type.value,
                "input_schema": tool.input_schema,
            })
        return {"tools": tools, "total": len(tools)}
    except ImportError:
        raise HTTPException(status_code=503, detail="工具执行引擎不可用")


@app.get("/api/v1/tools/{tool_name}", tags=["工具执行引擎"])
async def get_tool_detail(tool_name: str):
    """获取工具详情"""
    try:
        from tool_executor import get_executor
        executor = get_executor()
        tool = executor.get_tool(tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"工具不存在: {tool_name}")
        return {
            "name": tool.name,
            "description": tool.description,
            "type": tool.type.value,
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="工具执行引擎不可用")


@app.post("/api/v1/tools/{tool_name}/execute", tags=["工具执行引擎"])
async def execute_tool_api(
    tool_name: str,
    arguments: dict[str, Any] = {},
    user: Any = Depends(require_auth),
):
    """执行指定工具"""
    try:
        from tool_executor import execute_tool
        result = execute_tool(tool_name, **arguments)
        return {"success": result.get("status") == "success", "result": result}
    except ImportError:
        raise HTTPException(status_code=503, detail="工具执行引擎不可用")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tools/orchestrate", tags=["工具执行引擎"])
async def orchestrate_tools(
    request: ToolOrchestrateRequest,
    user: Any = Depends(require_auth),
):
    """模型驱动的工具编排
    
    使用V4-Pro分析用户请求，自动选择并执行工具链。
    """
    try:
        from tool_executor import model_execute
        result = model_execute(request.user_request)
        return result
    except ImportError:
        raise HTTPException(status_code=503, detail="工具执行引擎不可用")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tools/history", tags=["工具执行引擎"])
async def get_tool_history():
    """获取工具调用历史"""
    try:
        from tool_executor import get_executor
        executor = get_executor()
        history = [result.to_dict() for result in executor.call_history]
        return {"history": history, "total": len(history)}
    except ImportError:
        raise HTTPException(status_code=503, detail="工具执行引擎不可用")


# ============================================================================
# 错误处理
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    _logger.error(f"API 异常: {exc}", exception=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": str(exc),
            "detail": None,
        },
    )


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    """启动 API 服务"""
    import uvicorn

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))

    _logger.info(f"启动 API 服务: {host}:{port}")
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


# ============================================================================
# V4 远程编排 API（外出远程触发 AE 自动化）
# ============================================================================

class CompositionTaskRequest(BaseModel):
    """合成任务请求"""
    task_description: str = Field(..., description="自然语言描述合成任务")
    mode: str = Field("auto", description="执行模式: auto/preset/script")
    preset_name: str | None = Field(None, description="预设名称")
    overrides: dict[str, Any] = Field(default_factory=dict, description="预设覆盖参数")


class CompositionTaskResponse(BaseModel):
    """合成任务响应"""
    success: bool
    task_type: str = ""
    steps_count: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    ae_script: str = ""
    error: str = ""


@app.post("/api/v1/compose", response_model=CompositionTaskResponse, tags=["V4远程编排"])
async def compose_task(request: CompositionTaskRequest):
    """V4 驱动的智能合成 - 自然语言描述即可创建AE合成

    示例:
    - "创建576x768竖屏音乐视频，导入冰海战记素材，添加发光和粒子"
    - "渲染E2E_音乐视频合成为mp4"
    - "给图层1添加Glow效果，半径20，强度0.8"
    """
    try:
        from ae_smart_orchestrator import AESmartOrchestrator
        orch = AESmartOrchestrator()

        if request.mode == "preset" and request.preset_name:
            result = orch.compose_from_preset(
                request.preset_name, **request.overrides
            )
        else:
            result = orch.compose(
                request.task_description, mode=request.mode
            )

        return CompositionTaskResponse(
            success=result.get("success", False),
            task_type=result.get("task_type", ""),
            steps_count=len(result.get("steps", [])),
            results=result.get("results", []),
            ae_script=result.get("ae_script", ""),
            error=result.get("error", ""),
        )
    except Exception as e:
        return CompositionTaskResponse(
            success=False, error=str(e)
        )


@app.post("/api/v1/compose/quick/{preset}", tags=["V4远程编排"])
async def quick_compose(
    preset: str,
    params: dict[str, Any] = Body(default={}),
):
    """快速合成预设 - 一键创建

    可用预设: music_video, puppet, text_animation, particle_fx, render
    """
    try:
        from ae_smart_orchestrator import AESmartOrchestrator
        orch = AESmartOrchestrator()

        preset_map = {
            "music_video": orch.quick_music_video,
            "puppet": orch.quick_puppet,
            "text_animation": orch.quick_text_animation,
            "particle_fx": orch.quick_particle_fx,
            "render": orch.quick_render,
        }

        handler = preset_map.get(preset)
        if not handler:
            raise HTTPException(
                status_code=400,
                detail=f"未知预设: {preset}，可用: {list(preset_map.keys())}"
            )

        result = handler(**params)
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/compose/tools", tags=["V4远程编排"])
async def list_compose_tools():
    """列出所有可用的AE合成工具（V4 Function Calling格式）"""
    try:
        from v4_remote_orchestrator import V4RemoteOrchestrator
        orch = V4RemoteOrchestrator()
        tools = orch.get_available_tools()
        return {"tools": tools, "total": len(tools)}
    except Exception as e:
        return {"tools": [], "error": str(e)}


@app.get("/api/v1/compose/presets", tags=["V4远程编排"])
async def list_compose_presets():
    """列出所有合成预设"""
    try:
        from ae_composition_presets import get_preset_names, list_presets
        return {"presets": list_presets(), "names": get_preset_names()}
    except Exception as e:
        return {"presets": [], "error": str(e)}


@app.get("/api/v1/compose/status", tags=["V4远程编排"])
async def compose_status():
    """获取编排器状态"""
    try:
        from ae_smart_orchestrator import AESmartOrchestrator
        orch = AESmartOrchestrator()
        return orch.get_status()
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    main()

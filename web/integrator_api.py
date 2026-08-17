#!/usr/bin/env python3
"""
统一工具集成调度器 - REST API 服务
====================================

提供 HTTP 接口，支持远程调用工作流、查询状态、暂停/恢复/取消等操作。

启动方式:
    py -3.11 integrator_api.py                          # 默认端口 8765
    py -3.11 integrator_api.py --port 9000               # 自定义端口
    py -3.11 integrator_api.py --mode simulate            # 指定默认模式

API 端点:
    GET  /api/v1/health           - 健康检查
    GET  /api/v1/tools            - 获取所有工具状态
    GET  /api/v1/presets          - 获取所有工作流预设
    POST /api/v1/workflow/run     - 启动工作流（异步）
    GET  /api/v1/workflow/{wid}   - 查询工作流状态
    POST /api/v1/workflow/{wid}/pause    - 暂停工作流
    POST /api/v1/workflow/{wid}/resume   - 恢复工作流
    POST /api/v1/workflow/{wid}/cancel   - 取消工作流
    POST /api/v1/workflow/resume-from-checkpoint - 从检查点恢复
    GET  /api/v1/workflows/active       - 获取所有活跃工作流
"""

import argparse
import logging
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# 确保可以导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 项目根加入 sys.path，便于 from core.security import WEAK_TOKENS（单一定义源）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unified_tool_integrator import (
    PhaseStatus,
    UnifiedToolIntegrator,
    WorkflowResult,
)

# 弱 Token 集合：从 core.security 统一导入（单一定义源，禁止本地重复定义）
from core.security import WEAK_TOKENS  # noqa: E402

# ============================================================================
# 安全配置
# ============================================================================

# API Token 配置
AEK_INTEGRATOR_API_TOKEN = os.environ.get("AEK_INTEGRATOR_API_TOKEN", "")


async def require_integrator_auth(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> bool:
    """集成调度器 API 认证函数

    安全规则（强制，不区分环境）：
    - AEK_INTEGRATOR_API_TOKEN 必须是非空非弱值
    - 请求必须在 Authorization 头中携带有效的 Bearer Token
    - /health 端点不调用本函数（公开）

    本函数之前的 bug：当 token 为空/弱值且 AEK_ENVIRONMENT != production
    时，会静默放行所有请求，仅输出 Python warning。结合 CORS 默认 "*"，
    任意站点的前端 JavaScript 都可以无凭证调用工作流启动/取消/检查点恢复
    等破坏性接口。修复后：弱 token 配置一律 401 拒绝。
    """
    has_strong_token = AEK_INTEGRATOR_API_TOKEN not in WEAK_TOKENS

    # 强制: 服务器端必须配置非弱 token。否则直接 500 提示管理员配置缺失
    if not has_strong_token:
        import logging

        logging.getLogger("integrator_api").error(
            "AEK_INTEGRATOR_API_TOKEN 未配置或为弱值（空串/默认值）。"
            "请设置 AEK_INTEGRATOR_API_TOKEN 环境变量为高强度随机字符串。"
            "参考: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "服务器认证配置缺失：AEK_INTEGRATOR_API_TOKEN 未配置或不安全。"
                "请管理员设置非弱值 token。"
            ),
        )

    # 获取请求中的 token
    request_token = ""
    if credentials is not None:
        request_token = credentials.credentials or ""

    if not request_token:
        raise HTTPException(
            status_code=401,
            detail="未提供认证 Token，请在 Authorization 头中使用 Bearer Token",
        )
    # 使用 constant-time 比较，避免时序攻击
    import hmac

    if not hmac.compare_digest(request_token, AEK_INTEGRATOR_API_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="认证 Token 无效",
        )
    return True


# ============================================================================
# 请求/响应模型
# ============================================================================


class WorkflowRunRequest(BaseModel):
    """工作流启动请求"""

    preset_id: str = Field(..., description="工作流预设ID")
    input_params: dict[str, Any] | None = Field(default=None, description="输入参数")
    mode: str | None = Field(default=None, description="执行模式 real/simulate/auto")
    max_workers: int | None = Field(
        default=None, ge=1, le=64,
        description="并行最大线程数 (1-64)，超出范围自动钳位",
    )


class V4OrchestrateRequest(BaseModel):
    """V4智能编排请求"""

    request: str = Field(..., description="自然语言需求描述")
    model: str | None = Field(default="pro", description="V4模型: pro/flash")
    dry_run: bool | None = Field(default=False, description="仅生成工作流不执行")
    mode: str | None = Field(default=None, description="执行模式 real/simulate/auto")


class CheckpointResumeRequest(BaseModel):
    """检查点恢复请求"""

    checkpoint_path: str = Field(..., description="检查点文件路径")
    preset_id: str = Field(..., description="工作流预设ID")
    input_params: dict[str, Any] | None = Field(default=None, description="输入参数")


class WorkflowStatusResponse(BaseModel):
    """工作流状态响应"""

    workflow_id: str
    workflow_name: str
    status: str
    paused: bool
    total_steps: int
    completed_steps: int
    successful_steps: int
    failed_steps: int
    total_duration_ms: float
    started_at: str
    finished_at: str
    error: str
    summary: str
    output_files: list[str]
    log_file_path: str
    report_file_path: str
    checkpoint_path: str


# ============================================================================
# API 服务器
# ============================================================================


class IntegratorAPIServer:
    """集成调度器 API 服务器"""

    def __init__(
        self,
        default_mode: str = "auto",
        output_dir: str = r"D:\AE-Work\_integrator_output",
        preset_file: str | None = None,
        config_file: str | None = None,
    ):
        self._default_mode = default_mode
        self._output_dir = output_dir
        self._preset_file = preset_file
        self._config_file = config_file
        self._lock = threading.Lock()
        self._workflow_threads: dict[str, threading.Thread] = {}
        self._workflow_results: dict[str, WorkflowResult] = {}
        self._integrators: dict[str, UnifiedToolIntegrator] = {}
        # 新增: 全局并发工作流上限，防止无线程池导致线程爆炸
        self._concurrency_sem = threading.BoundedSemaphore(value=16)

        # 创建共享的 integrator 实例（用于查询工具/预设）
        self._shared_integrator = self._create_integrator()

    def _create_integrator(
        self, mode: str | None = None, max_workers: int = 4
    ) -> UnifiedToolIntegrator:
        """创建新的 integrator 实例"""
        return UnifiedToolIntegrator(
            default_mode=mode or self._default_mode,
            output_dir=self._output_dir,
            preset_file=self._preset_file,
            config_file=self._config_file,
            max_workers=max_workers,
        )

    def run_workflow_async(
        self,
        workflow_id: str,
        integrator: UnifiedToolIntegrator,
        preset_id: str,
        input_params: dict[str, Any],
    ):
        """在后台线程中执行工作流"""
        try:
            result = integrator.run_workflow(preset_id, input_params)
            with self._lock:
                self._workflow_results[workflow_id] = result
        except Exception as e:
            # 创建一个错误结果
            error_result = WorkflowResult(
                workflow_name=preset_id,
                status=PhaseStatus.ERROR.value,
                error=str(e),
                summary=f"工作流启动失败: {e}",
                workflow_id=workflow_id,
                finished_at=datetime.now().isoformat(),
            )
            with self._lock:
                self._workflow_results[workflow_id] = error_result
        finally:
            try:
                self._concurrency_sem.release()
            except Exception:
                pass

    def start_workflow(self, request: WorkflowRunRequest) -> dict[str, Any]:
        """启动工作流（异步）"""
        # 验证预设存在
        presets = self._shared_integrator.list_presets()
        preset_ids = [p["id"] for p in presets]
        if request.preset_id not in preset_ids:
            raise HTTPException(
                status_code=404,
                detail=f"未知预设: {request.preset_id}. 可用: {preset_ids}",
            )

        # 创建 integrator 实例
        mode = request.mode or self._default_mode
        try:
            requested_workers = int(request.max_workers) if request.max_workers else 4
        except (TypeError, ValueError):
            requested_workers = 4
        max_workers = max(1, min(requested_workers, 64))  # 硬钳位 1..64
        integrator = self._create_integrator(mode=mode, max_workers=max_workers)

        # 生成工作流ID
        import uuid

        workflow_id = str(uuid.uuid4())[:8]

        # 并发信号量检查
        acquired = self._concurrency_sem.acquire(blocking=False)
        if not acquired:
            raise HTTPException(
                status_code=503,
                detail="工作流并发已满（当前上限=16），请稍后再试",
            )
        try:
            thread = threading.Thread(
                target=self.run_workflow_async,
                args=(workflow_id, integrator, request.preset_id, request.input_params or {}),
                daemon=True,
            )
            thread.start()
        except Exception as e:
            self._concurrency_sem.release()
            raise HTTPException(status_code=500, detail=f"工作流启动失败: {type(e).__name__}: {str(e)[:200]}")

        with self._lock:
            self._workflow_threads[workflow_id] = thread
            self._integrators[workflow_id] = integrator
            # 预设一个 running 状态结果
            self._workflow_results[workflow_id] = WorkflowResult(
                workflow_name=request.preset_id,
                status=PhaseStatus.RUNNING.value,
                started_at=datetime.now().isoformat(),
                workflow_id=workflow_id,
            )

        return {
            "workflow_id": workflow_id,
            "preset_id": request.preset_id,
            "status": "running",
            "message": f"工作流 {request.preset_id} 已启动",
        }

    def get_workflow_status(self, workflow_id: str) -> WorkflowStatusResponse:
        """查询工作流状态"""
        with self._lock:
            result = self._workflow_results.get(workflow_id)
            integrator = self._integrators.get(workflow_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"未找到工作流: {workflow_id}")

        # 获取实时暂停状态
        try:
            paused = integrator.is_paused() if integrator else False
        except Exception:
            paused = False

        steps_list = result.steps if result and hasattr(result, "steps") else []
        total = len(steps_list or [])
        try:
            succ = result.successful_steps() if result else []
        except Exception:
            succ = []
        successful = len(succ or [])
        try:
            fail = result.failed_steps() if result else []
        except Exception:
            fail = []
        failed = len(fail or [])

        return WorkflowStatusResponse(
            workflow_id=result.workflow_id,
            workflow_name=result.workflow_name,
            status=result.status,
            paused=paused,
            total_steps=total,
            completed_steps=total,
            successful_steps=successful,
            failed_steps=failed,
            total_duration_ms=result.total_duration_ms,
            started_at=result.started_at,
            finished_at=result.finished_at,
            error=result.error,
            summary=result.summary,
            output_files=result.output_files,
            log_file_path=result.log_file_path,
            report_file_path=result.report_file_path,
            checkpoint_path=result.checkpoint_path,
        )

    def pause_workflow(self, workflow_id: str) -> dict[str, Any]:
        """暂停工作流"""
        with self._lock:
            integrator = self._integrators.get(workflow_id)
            if integrator is None:
                raise HTTPException(status_code=404, detail='未找到工作流: {workflow_id}')
        try:
            integrator.pause_workflow(workflow_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=("暂停失败: " + type(e).__name__ + ": " + str(e)[:200]))
        return {
            "workflow_id": workflow_id,
            "action": "paused",
            "message": "暂停请求已发送",
        }

    def resume_workflow(self, workflow_id: str) -> dict[str, Any]:
        """恢复工作流"""
        with self._lock:
            integrator = self._integrators.get(workflow_id)
            if integrator is None:
                raise HTTPException(status_code=404, detail='未找到工作流: {workflow_id}')
        try:
            integrator.resume_workflow(workflow_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=("恢复失败: " + type(e).__name__ + ": " + str(e)[:200]))
        return {
            "workflow_id": workflow_id,
            "action": "resumed",
            "message": "恢复请求已发送",
        }

    def cancel_workflow(self, workflow_id: str) -> dict[str, Any]:
        """取消工作流"""
        with self._lock:
            integrator = self._integrators.get(workflow_id)
            if integrator is None:
                raise HTTPException(status_code=404, detail='未找到工作流: {workflow_id}')
        try:
            integrator.cancel_workflow(workflow_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"取消失败: {type(e).__name__}: {str(e)[:200]}")
        return {
            "workflow_id": workflow_id,
            "action": "cancelled",
            "message": "取消请求已发送",
        }

    def resume_from_checkpoint(
        self, request: CheckpointResumeRequest
    ) -> dict[str, Any]:
        """从检查点恢复工作流"""
        from pathlib import Path

        raw_path = request.checkpoint_path
        # 安全校验 0a: 拒绝 NUL 字节（Win32 API 路径截断）
        if "\x00" in raw_path:
            raise HTTPException(status_code=400, detail="路径包含非法 NUL 字节")

        # 安全校验 0b: 拒绝 Windows 非法文件名字符（防止文件系统调用异常/奇怪路径）
        _illegal_filename_chars = set('*?"<>|')
        if any(c in _illegal_filename_chars for c in raw_path):
            raise HTTPException(status_code=400, detail='路径包含 Windows 非法文件 *?"<>| 字符')

        # 安全校验 0c: 拒绝非盘符位置的冒号（防止 NTFS 交替数据流 filename:stream）
        _colon_positions = [i for i, c in enumerate(raw_path) if c == ":"]
        for pos in _colon_positions:
            # 仅允许"第1个字符之后"作为盘符（例如 D:）
            if pos != 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"路径第 {pos} 字符位置存在非法冒号（禁止 NTFS 交替数据流 / 网络路径）",
                )

        # 安全校验 0: 路径长度硬上限（Windows MAX_PATH=260, 留出安全冗余到 4096）
        if len(raw_path) > 4096:
            raise HTTPException(
                status_code=400,
                detail=f"路径长度超过最大限制(4096): 实际{len(raw_path)}",
            )
        # 安全校验 1: 检查原始路径中是否包含 ".." 组件
        path_parts = raw_path.replace("\\", "/").split("/")
        if ".." in path_parts:
            raise HTTPException(
                status_code=400,
                detail=f"路径包含非法 '..' 组件: {raw_path}",
            )

        # 安全校验 2: 规范化路径（解析符号链接、相对路径等）
        try:
            normalized_path = os.path.abspath(raw_path)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"路径规范化失败: {raw_path}, 错误: {e}",
            )

        # 安全校验 3: 检查路径后缀必须以 checkpoint.json 结尾
        if not normalized_path.endswith("checkpoint.json"):
            raise HTTPException(
                status_code=400,
                detail=f"路径必须以 checkpoint.json 结尾: {raw_path}",
            )

        # 安全校验 4: 计算允许的根目录并检查子路径关系
        allowed_root = os.path.abspath(self._output_dir)
        # 确保根目录以分隔符结尾，避免前缀匹配误判（例如 D:\output 和 D:\output_evil）
        if not allowed_root.endswith(os.sep):
            allowed_root_with_sep = allowed_root + os.sep
        else:
            allowed_root_with_sep = allowed_root

        # 使用 Path.is_relative_to 进行子路径检查（Python 3.9+）
        try:
            normalized_p = Path(normalized_path)
            allowed_root_p = Path(allowed_root)
            is_relative_fn = getattr(normalized_p, "is_relative_to", None)
            if callable(is_relative_fn):
                is_under_root = is_relative_fn(allowed_root_p)
            else:
                # 方法不存在或属性被置为 None → 走兼容分支
                is_under_root = (
                    normalized_path.startswith(allowed_root_with_sep)
                    or normalized_path == allowed_root
                )
        except Exception:
            # 任何异常（AttributeError / TypeError / 其他）都降级到兼容方案，
            # 避免路径校验阶段出现未处理异常导致 500 崩溃。
            # 兼容方案通过 allowed_root_with_sep 防止前缀碰撞，且后续还有多层校验兜底。
            is_under_root = (
                normalized_path.startswith(allowed_root_with_sep)
                or normalized_path == allowed_root
            )

        if not is_under_root:
            raise HTTPException(
                status_code=400,
                detail=f"路径超出允许的输出目录范围。允许根目录: {allowed_root}, 请求路径: {raw_path}",
            )

        # 安全校验 5: 检查文件是否存在
        if not os.path.exists(normalized_path):
            raise HTTPException(status_code=404, detail=f"检查点文件不存在: {raw_path}")

        if not os.path.isfile(normalized_path):
            raise HTTPException(
                status_code=400, detail=f"检查点路径不是文件: {raw_path}"
            )

        integrator = self._create_integrator()
        import uuid

        workflow_id = str(uuid.uuid4())[:8]

        # 并发信号量检查
        acquired = self._concurrency_sem.acquire(blocking=False)
        if not acquired:
            raise HTTPException(
                status_code=503,
                detail="工作流并发已满（当前上限=16），请稍后再试",
            )
        try:
            thread = threading.Thread(
                target=self._run_checkpoint_resume,
                args=(
                    workflow_id,
                    integrator,
                    normalized_path,
                    request.preset_id,
                    request.input_params or {},
                ),
                daemon=True,
            )
            thread.start()
        except Exception as e:
            self._concurrency_sem.release()
            raise HTTPException(status_code=500, detail=f"检查点恢复启动失败: {type(e).__name__}: {str(e)[:200]}")

        with self._lock:
            self._workflow_threads[workflow_id] = thread
            self._integrators[workflow_id] = integrator
            self._workflow_results[workflow_id] = WorkflowResult(
                workflow_name=f"恢复:{request.preset_id}",
                status=PhaseStatus.RUNNING.value,
                started_at=datetime.now().isoformat(),
                workflow_id=workflow_id,
            )

        return {
            "workflow_id": workflow_id,
            "preset_id": request.preset_id,
            "checkpoint_path": normalized_path,
            "status": "running",
            "message": "工作流从检查点恢复执行",
        }

    def _run_checkpoint_resume(
        self,
        workflow_id: str,
        integrator: UnifiedToolIntegrator,
        checkpoint_path: str,
        preset_id: str,
        input_params: dict[str, Any],
    ):
        """后台执行检查点恢复"""
        try:
            result = integrator.resume_from_checkpoint(
                checkpoint_path, preset_id, input_params
            )
            with self._lock:
                self._workflow_results[workflow_id] = result
        except Exception as e:
            error_result = WorkflowResult(
                workflow_name=f"恢复:{preset_id}",
                status=PhaseStatus.ERROR.value,
                error=str(e),
                summary=f"检查点恢复失败: {e}",
                workflow_id=workflow_id,
                finished_at=datetime.now().isoformat(),
            )
            with self._lock:
                self._workflow_results[workflow_id] = error_result
        finally:
            try:
                self._concurrency_sem.release()
            except Exception:
                pass

    def get_active_workflows(self) -> list[dict[str, Any]]:
        """获取所有活跃工作流"""
        active = []
        with self._lock:
            for wid, result in self._workflow_results.items():
                if result.status == PhaseStatus.RUNNING.value:
                    integrator = self._integrators.get(wid)
                    active.append(
                        {
                            "workflow_id": wid,
                            "workflow_name": result.workflow_name,
                            "status": result.status,
                            "paused": integrator.is_paused() if integrator else False,
                            "steps_completed": len(result.steps),
                        }
                    )
        return active

    def get_tools(self) -> dict[str, Any]:
        """获取所有工具信息"""
        return self._shared_integrator.get_all_tools_info()

    def get_presets(self) -> list[dict[str, Any]]:
        """获取所有预设"""
        return self._shared_integrator.list_presets()

    def v4_orchestrate(self, request: V4OrchestrateRequest) -> dict[str, Any]:
        """V4智能编排 - 自然语言到工具链执行"""
        try:
            from v4_orchestrator import V4Orchestrator
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"V4编排器未安装: {e}",
            )

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="未设置 DEEPSEEK_API_KEY 环境变量",
            )

        mode = request.mode or self._default_mode
        orchestrator = V4Orchestrator(
            api_key=api_key,
            default_mode=mode,
            output_dir=self._output_dir,
            config_file=self._config_file,
            preset_file=self._preset_file,
        )

        result = orchestrator.run(
            request.request,
            model=request.model or "pro",
            dry_run=request.dry_run or False,
        )

        return result


# ============================================================================
# FastAPI 应用
# ============================================================================


def create_app(
    default_mode: str = "auto",
    output_dir: str = r"D:\AE-Work\_integrator_output",
    preset_file: str | None = None,
    config_file: str | None = None,
) -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="统一工具集成调度器 API",
        description="跨工具工作流协同调度 REST API",
        version="2.0.0",
    )

    # CORS
    # 安全修复: allow_credentials=True 时 allow_origins 不能为 "*" (Fetch 规范),
    # 且默认 "*" 会让任意站点跨域调用 API。未配置时仅放行本地开发来源。
    # 之前的默认 cors_origins=["*"] + allow_credentials=True + 认证静默绕过
    # 组合导致任意网页 JS 可无凭证调用所有工作流接口。
    cors_origins_env = os.environ.get("AEK_INTEGRATOR_CORS_ORIGINS", "")
    if cors_origins_env:
        cors_origins = [
            origin.strip() for origin in cors_origins_env.split(",") if origin.strip()
        ]
    else:
        cors_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Step 4 Phase B: 端点收敛 Deprecation 标记（加法式，不改业务）----
    # 网关 (puppet-automation/src/api/main.py :8000) 为统一执行面真源；
    # 本服务中与网关规范端点重复的端点集中标记 Deprecation 引导迁移。
    # 仅注入响应头，完全不改业务逻辑；回退只需清空 _DEPRECATED。
    import json as _json
    import os as _os

    def _deprecation_hit_logger():
        """Phase C 观测：惰性挂载 JSONL 文件 handler（与 api_server 同款，fail-open）。"""
        lg = logging.getLogger("deprecation")
        for h in lg.handlers:
            if getattr(h, "_deprecation_jsonl", False):
                return lg
        try:
            _os.makedirs("logs", exist_ok=True)
            fh = logging.FileHandler("logs/deprecated_hits.jsonl", encoding="utf-8")
            fh._deprecation_jsonl = True
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter("%(message)s"))
            lg.addHandler(fh)
            lg.setLevel(logging.INFO)
            lg.propagate = False
        except Exception:
            pass
        return lg

    _deprecated_sunset = (
        datetime.now(timezone.utc) + timedelta(days=180)
    ).strftime("%a, %d %b %Y %H:%M:%S GMT")
    _DEPRECATED = [
        ("/api/v1/tools", "/api/v1/engines"),
        ("/api/v1/v4/tools", "/api/v1/engines"),
        ("/api/v1/v4/orchestrate", "/api/v1/ai/plan-and-run"),
    ]

    @app.middleware("http")
    async def deprecation_middleware(request: Request, call_next):
        response = await call_next(request)
        for prefix, canonical in _DEPRECATED:
            if request.url.path == prefix or request.url.path.startswith(prefix + "/"):
                # Phase C 观测：每次命中记录结构化 JSON 日志，供观测期统计弃用端点残留调用方
                _deprecation_hit_logger().info(_json.dumps(
                    {"event": "DEPRECATED_HIT", "service": "integrator",
                     "path": request.url.path, "method": request.method,
                     "status": response.status_code, "canonical": canonical,
                     "ts": datetime.now(timezone.utc).isoformat()},
                    ensure_ascii=False,
                ))
                if not response.headers.get("Deprecation"):
                    response.headers["Deprecation"] = "true"
                    response.headers["Sunset"] = _deprecated_sunset
                    response.headers["Link"] = f'<{canonical}>; rel="deprecation"'
                break
        return response

    # 初始化服务器
    server = IntegratorAPIServer(
        default_mode=default_mode,
        output_dir=output_dir,
        preset_file=preset_file,
        config_file=config_file,
    )

    @app.get("/api/v1/auth/test")
    async def auth_test(_auth: bool = Depends(require_integrator_auth)):
        """认证功能自检（需要认证）"""
        return {
            "status": "ok",
            "message": "认证成功",
            "timestamp": datetime.now().isoformat(),
        }

    @app.get("/api/v1/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
        }

    @app.get("/api/v1/tools")
    async def get_tools(_auth: bool = Depends(require_integrator_auth)):
        """获取所有工具状态"""
        return server.get_tools()

    @app.get("/api/v1/presets")
    async def get_presets(_auth: bool = Depends(require_integrator_auth)):
        """获取所有工作流预设"""
        return server.get_presets()

    @app.post("/api/v1/workflow/run")
    async def run_workflow(
        request: WorkflowRunRequest, _auth: bool = Depends(require_integrator_auth)
    ):
        """启动工作流（异步执行）"""
        return server.start_workflow(request)

    @app.get("/api/v1/workflow/{workflow_id}")
    async def get_workflow_status(
        workflow_id: str, _auth: bool = Depends(require_integrator_auth)
    ):
        """查询工作流状态"""
        return server.get_workflow_status(workflow_id)

    @app.post("/api/v1/workflow/{workflow_id}/pause")
    async def pause_workflow(
        workflow_id: str, _auth: bool = Depends(require_integrator_auth)
    ):
        """暂停工作流"""
        return server.pause_workflow(workflow_id)

    @app.post("/api/v1/workflow/{workflow_id}/resume")
    async def resume_workflow(
        workflow_id: str, _auth: bool = Depends(require_integrator_auth)
    ):
        """恢复工作流"""
        return server.resume_workflow(workflow_id)

    @app.post("/api/v1/workflow/{workflow_id}/cancel")
    async def cancel_workflow(
        workflow_id: str, _auth: bool = Depends(require_integrator_auth)
    ):
        """取消工作流"""
        return server.cancel_workflow(workflow_id)

    @app.post("/api/v1/workflow/resume-from-checkpoint")
    async def resume_from_checkpoint(
        request: CheckpointResumeRequest, _auth: bool = Depends(require_integrator_auth)
    ):
        """从检查点恢复工作流"""
        return server.resume_from_checkpoint(request)

    @app.get("/api/v1/workflows/active")
    async def get_active_workflows(_auth: bool = Depends(require_integrator_auth)):
        """获取所有活跃工作流"""
        return server.get_active_workflows()

    @app.post("/api/v1/v4/orchestrate")
    async def v4_orchestrate(
        request: V4OrchestrateRequest, _auth: bool = Depends(require_integrator_auth)
    ):
        """V4智能编排 - 自然语言到工具链执行"""
        return server.v4_orchestrate(request)

    @app.get("/api/v1/v4/tools")
    async def v4_available_tools(_auth: bool = Depends(require_integrator_auth)):
        """获取V4编排器可用的工具列表"""
        tools = server.get_tools()
        return {
            "available": {k: v for k, v in tools.items() if v.get("available")},
            "unavailable": {k: v for k, v in tools.items() if not v.get("available")},
        }

    # 存储服务器实例供外部访问
    app.state.server = server

    return app


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="统一工具集成调度器 - REST API 服务")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="监听地址（默认: 0.0.0.0）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="监听端口（默认: 8765）",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["real", "simulate", "auto"],
        default="auto",
        help="默认执行模式（默认: auto）",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=r"D:\AE-Work\_integrator_output",
        help="输出根目录",
    )
    parser.add_argument(
        "--presets-file",
        help="外部工作流预设JSON文件路径",
    )
    parser.add_argument(
        "--config-file",
        help="工具路径配置文件路径",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="开发模式（热重载）",
    )

    args = parser.parse_args()

    # 确定预设文件
    preset_file = args.presets_file
    if not preset_file:
        default_preset = os.path.join(
            os.path.dirname(__file__), "workflow_presets_library.json"
        )
        if os.path.exists(default_preset):
            preset_file = default_preset

    print("=" * 60)
    print("  统一工具集成调度器 - REST API 服务")
    print("=" * 60)
    print(f"  监听地址: http://{args.host}:{args.port}")
    print(f"  默认模式: {args.mode}")
    print(f"  输出目录: {args.output_dir}")
    if preset_file:
        print(f"  预设文件: {preset_file}")
    print(f"  API文档: http://{args.host}:{args.port}/docs")
    print("=" * 60)
    print()

    app = create_app(
        default_mode=args.mode,
        output_dir=args.output_dir,
        preset_file=preset_file,
        config_file=args.config_file,
    )

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()

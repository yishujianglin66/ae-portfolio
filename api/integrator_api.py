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
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 确保可以导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unified_tool_integrator import (
    PhaseStatus,
    StepResult,
    UnifiedToolIntegrator,
    WorkflowResult,
)

# ============================================================================
# 请求/响应模型
# ============================================================================

class WorkflowRunRequest(BaseModel):
    """工作流启动请求"""
    preset_id: str = Field(..., description="工作流预设ID")
    input_params: dict[str, Any] | None = Field(default=None, description="输入参数")
    mode: str | None = Field(default=None, description="执行模式 real/simulate/auto")
    max_workers: int | None = Field(default=None, description="并行最大线程数")


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

        # 创建共享的 integrator 实例（用于查询工具/预设）
        self._shared_integrator = self._create_integrator()

    def _create_integrator(self, mode: str | None = None, max_workers: int = 4) -> UnifiedToolIntegrator:
        """创建新的 integrator 实例"""
        return UnifiedToolIntegrator(
            default_mode=mode or self._default_mode,
            output_dir=self._output_dir,
            preset_file=self._preset_file,
            config_file=self._config_file,
            max_workers=max_workers,
        )

    def run_workflow_async(self, workflow_id: str, integrator: UnifiedToolIntegrator,
                           preset_id: str, input_params: dict[str, Any]):
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

    def start_workflow(self, request: WorkflowRunRequest) -> dict[str, Any]:
        """启动工作流（异步）"""
        # 验证预设存在
        presets = self._shared_integrator.list_presets()
        preset_ids = [p["id"] for p in presets]
        if request.preset_id not in preset_ids:
            raise HTTPException(status_code=404, detail=f"未知预设: {request.preset_id}. 可用: {preset_ids}")

        # 创建 integrator 实例
        mode = request.mode or self._default_mode
        max_workers = request.max_workers or 4
        integrator = self._create_integrator(mode=mode, max_workers=max_workers)

        # 生成工作流ID
        import uuid
        workflow_id = str(uuid.uuid4())[:8]

        # 启动后台线程
        thread = threading.Thread(
            target=self.run_workflow_async,
            args=(workflow_id, integrator, request.preset_id, request.input_params or {}),
            daemon=True,
        )
        thread.start()

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
        paused = integrator.is_paused() if integrator else False

        total = len(result.steps)
        successful = len(result.successful_steps())
        failed = len(result.failed_steps())

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
        if not integrator:
            raise HTTPException(status_code=404, detail=f"未找到工作流: {workflow_id}")
        integrator.pause_workflow(workflow_id)
        return {"workflow_id": workflow_id, "action": "paused", "message": "暂停请求已发送"}

    def resume_workflow(self, workflow_id: str) -> dict[str, Any]:
        """恢复工作流"""
        with self._lock:
            integrator = self._integrators.get(workflow_id)
        if not integrator:
            raise HTTPException(status_code=404, detail=f"未找到工作流: {workflow_id}")
        integrator.resume_workflow(workflow_id)
        return {"workflow_id": workflow_id, "action": "resumed", "message": "恢复请求已发送"}

    def cancel_workflow(self, workflow_id: str) -> dict[str, Any]:
        """取消工作流"""
        with self._lock:
            integrator = self._integrators.get(workflow_id)
        if not integrator:
            raise HTTPException(status_code=404, detail=f"未找到工作流: {workflow_id}")
        integrator.cancel_workflow(workflow_id)
        return {"workflow_id": workflow_id, "action": "cancelled", "message": "取消请求已发送"}

    def resume_from_checkpoint(self, request: CheckpointResumeRequest) -> dict[str, Any]:
        """从检查点恢复工作流"""
        resolved = Path(request.checkpoint_path).resolve()
        allowed_root = Path(self._output_dir).resolve()
        try:
            resolved.relative_to(allowed_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="检查点路径不在允许范围内")
        if not os.path.exists(resolved):
            raise HTTPException(status_code=404, detail=f"检查点文件不存在: {request.checkpoint_path}")

        integrator = self._create_integrator()
        import uuid
        workflow_id = str(uuid.uuid4())[:8]

        thread = threading.Thread(
            target=self._run_checkpoint_resume,
            args=(workflow_id, integrator, request.checkpoint_path, request.preset_id, request.input_params or {}),
            daemon=True,
        )
        thread.start()

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
            "checkpoint_path": request.checkpoint_path,
            "status": "running",
            "message": "工作流从检查点恢复执行",
        }

    def _run_checkpoint_resume(self, workflow_id: str, integrator: UnifiedToolIntegrator,
                                checkpoint_path: str, preset_id: str, input_params: dict[str, Any]):
        """后台执行检查点恢复"""
        try:
            result = integrator.resume_from_checkpoint(checkpoint_path, preset_id, input_params)
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

    def get_active_workflows(self) -> list[dict[str, Any]]:
        """获取所有活跃工作流"""
        active = []
        with self._lock:
            for wid, result in self._workflow_results.items():
                if result.status == PhaseStatus.RUNNING.value:
                    integrator = self._integrators.get(wid)
                    active.append({
                        "workflow_id": wid,
                        "workflow_name": result.workflow_name,
                        "status": result.status,
                        "paused": integrator.is_paused() if integrator else False,
                        "steps_completed": len(result.steps),
                    })
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 初始化服务器
    server = IntegratorAPIServer(
        default_mode=default_mode,
        output_dir=output_dir,
        preset_file=preset_file,
        config_file=config_file,
    )

    @app.get("/api/v1/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
        }

    @app.get("/api/v1/tools")
    async def get_tools():
        """获取所有工具状态"""
        return server.get_tools()

    @app.get("/api/v1/presets")
    async def get_presets():
        """获取所有工作流预设"""
        return server.get_presets()

    @app.post("/api/v1/workflow/run")
    async def run_workflow(request: WorkflowRunRequest):
        """启动工作流（异步执行）"""
        return server.start_workflow(request)

    @app.get("/api/v1/workflow/{workflow_id}")
    async def get_workflow_status(workflow_id: str):
        """查询工作流状态"""
        return server.get_workflow_status(workflow_id)

    @app.post("/api/v1/workflow/{workflow_id}/pause")
    async def pause_workflow(workflow_id: str):
        """暂停工作流"""
        return server.pause_workflow(workflow_id)

    @app.post("/api/v1/workflow/{workflow_id}/resume")
    async def resume_workflow(workflow_id: str):
        """恢复工作流"""
        return server.resume_workflow(workflow_id)

    @app.post("/api/v1/workflow/{workflow_id}/cancel")
    async def cancel_workflow(workflow_id: str):
        """取消工作流"""
        return server.cancel_workflow(workflow_id)

    @app.post("/api/v1/workflow/resume-from-checkpoint")
    async def resume_from_checkpoint(request: CheckpointResumeRequest):
        """从检查点恢复工作流"""
        return server.resume_from_checkpoint(request)

    @app.get("/api/v1/workflows/active")
    async def get_active_workflows():
        """获取所有活跃工作流"""
        return server.get_active_workflows()

    @app.post("/api/v1/v4/orchestrate")
    async def v4_orchestrate(request: V4OrchestrateRequest):
        """V4智能编排 - 自然语言到工具链执行"""
        return server.v4_orchestrate(request)

    @app.get("/api/v1/v4/tools")
    async def v4_available_tools():
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
    parser = argparse.ArgumentParser(
        description="统一工具集成调度器 - REST API 服务"
    )
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
        "--mode", "-m",
        choices=["real", "simulate", "auto"],
        default="auto",
        help="默认执行模式（默认: auto）",
    )
    parser.add_argument(
        "--output-dir", "-o",
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
        default_preset = os.path.join(os.path.dirname(__file__), "workflow_presets_library.json")
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

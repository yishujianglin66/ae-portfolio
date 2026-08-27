#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具链 API 模块 (Toolchain API)
=============================

提供工具链管理器的 RESTful API 接口，支持:
- 工具发现与状态查询
- 工具执行
- 工作流编排与执行
- 批量工具操作

依赖:
- toolchain_manager.py - 工具链统一管理器
- api_server.py - FastAPI主服务
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

try:
    from toolchain_manager import (
        ToolchainManager, ToolInfo, ToolResult, WorkflowResult,
        ToolCategory, ToolStatus, ExecutionMode,
    )
    _TOOLCHAIN_AVAILABLE = True
    _manager: Optional[ToolchainManager] = None
except ImportError:
    _TOOLCHAIN_AVAILABLE = False
    _manager = None

try:
    from auth_system import (
        AuthManager, Role,
        get_auth_manager as _get_auth_manager,
    )
    _AUTH_AVAILABLE = True
    _auth: Optional[AuthManager] = _auth if '_auth' in globals() else None
except ImportError:
    _AUTH_AVAILABLE = False
    _auth = None

_security = HTTPBearer(auto_error=False)


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
):
    """认证依赖 - 要求已登录

    fail-closed 策略：认证模块不可用时拒绝访问。
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


def get_toolchain_manager() -> ToolchainManager:
    """获取工具链管理器单例"""
    global _manager
    if _manager is None and _TOOLCHAIN_AVAILABLE:
        _manager = ToolchainManager()
    return _manager


# ============================================================================
# Pydantic 模型
# ============================================================================

class ToolStatusResponse(BaseModel):
    """工具状态响应"""
    name: str
    category: str
    status: str
    description: str
    executable_path: str = ""
    capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolListResponse(BaseModel):
    """工具列表响应"""
    total: int
    categories: Dict[str, int]
    tools: List[ToolStatusResponse]


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    tool_name: str = Field(..., description="工具名称")
    operation: str = Field(..., description="操作名称")
    params: Dict[str, Any] = Field(default_factory=dict, description="操作参数")
    mode: str = Field("auto", description="执行模式: real, simulate, auto")


class ToolExecuteResponse(BaseModel):
    """工具执行响应"""
    success: bool
    tool_name: str
    operation: str
    output_path: Optional[str] = None
    output_data: Dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0
    mode_used: str = "simulate"
    log: List[str] = Field(default_factory=list)


class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求"""
    workflow_name: str = Field(..., description="工作流名称")
    input_path: str = Field(..., description="输入文件路径")
    output_path: str = Field(..., description="输出文件路径")
    mode: str = Field("auto", description="执行模式")
    steps: Optional[List[str]] = Field(None, description="指定执行步骤")


class WorkflowExecuteResponse(BaseModel):
    """工作流执行响应"""
    workflow_name: str
    status: str
    total_duration_ms: float = 0
    output_files: List[str] = Field(default_factory=list)
    error: str = ""
    summary: str = ""
    steps: List[ToolExecuteResponse] = Field(default_factory=list)


class WorkflowDetailResponse(BaseModel):
    """工作流详情响应"""
    workflow_name: str
    step_count: int
    steps: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# API 路由
# ============================================================================

router = APIRouter(
    prefix="/api/v1/toolchain",
    tags=["工具链"],
)


# ============================================================================
# 工具管理 API
# ============================================================================

@router.get("/tools/categories")
async def list_categories():
    """列出工具分类"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()
    status = manager.get_all_tool_status()

    return {
        "categories": list(status["categories"].keys()),
        "counts": status["categories"],
    }


@router.get("/tools/engines")
async def list_engines():
    """列出所有软件引擎"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()
    status = manager.get_all_tool_status()

    engines = [
        tool for tool in status["tools"]
        if tool["category"] == ToolCategory.ENGINE.value
    ]

    return {
        "total": len(engines),
        "engines": engines,
    }


@router.get("/tools", response_model=ToolListResponse)
async def list_tools(category: Optional[str] = Query(None, description="按分类筛选")):
    """列出所有工具"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()
    status = manager.get_all_tool_status()

    tools = []
    for tool_info in status["tools"]:
        if category and tool_info["category"] != category:
            continue
        tools.append(ToolStatusResponse(**tool_info))

    return ToolListResponse(
        total=len(tools),
        categories=status["categories"],
        tools=tools,
    )


@router.get("/tools/{tool_name}", response_model=ToolStatusResponse)
async def get_tool_status(tool_name: str):
    """获取工具状态"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()
    status = manager.get_tool_status(tool_name)

    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"工具不存在: {tool_name}")

    return ToolStatusResponse(**status)


# ============================================================================
# 工具执行 API
# ============================================================================

@router.post("/tools/execute", response_model=ToolExecuteResponse)
async def execute_tool(
    request: ToolExecuteRequest,
    user: Any = Depends(require_auth),
):
    """执行工具操作"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()

    try:
        result = manager.execute_tool(
            tool_name=request.tool_name,
            operation=request.operation,
            params=request.params,
            mode=request.mode,
        )

        return ToolExecuteResponse(
            success=result.success,
            tool_name=result.tool_name,
            operation=result.operation,
            output_path=result.output_path,
            output_data=result.output_data,
            error=result.error,
            duration_ms=result.duration_ms,
            mode_used=result.mode_used,
            log=result.log,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/{tool_name}/execute", response_model=ToolExecuteResponse)
async def execute_tool_by_name(
    tool_name: str,
    operation: str = Query(..., description="操作名称"),
    params: Optional[Dict[str, Any]] = None,
    mode: str = Query("auto", description="执行模式"),
    user: Any = Depends(require_auth),
):
    """按名称执行工具"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()

    try:
        result = manager.execute_tool(
            tool_name=tool_name,
            operation=operation,
            params=params or {},
            mode=mode,
        )

        return ToolExecuteResponse(**result.__dict__)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 工作流 API
# ============================================================================

@router.get("/workflows")
async def list_workflows():
    """列出所有工作流"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()
    workflows = manager.list_workflows()

    details = []
    for wf in workflows:
        detail = manager.get_workflow_details(wf)
        details.append(detail)

    return {
        "total": len(workflows),
        "workflows": workflows,
        "details": details,
    }


@router.get("/workflows/{workflow_name}", response_model=WorkflowDetailResponse)
async def get_workflow_detail(workflow_name: str):
    """获取工作流详情"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()
    try:
        details = manager.get_workflow_details(workflow_name)
        return WorkflowDetailResponse(**details)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_name}")


@router.post("/workflows/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow(
    request: WorkflowExecuteRequest,
    user: Any = Depends(require_auth),
):
    """执行工作流"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()

    try:
        result = manager.run_workflow(
            workflow_name=request.workflow_name,
            input_path=request.input_path,
            output_path=request.output_path,
            mode=request.mode,
        )

        step_responses = []
        for step in result.steps:
            step_responses.append(ToolExecuteResponse(**step.__dict__))

        return WorkflowExecuteResponse(
            workflow_name=result.workflow_name,
            status=result.status,
            total_duration_ms=result.total_duration_ms,
            output_files=result.output_files,
            error=result.error,
            summary=result.summary,
            steps=step_responses,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_name}/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow_by_name(
    workflow_name: str,
    input_path: str = Query(..., description="输入路径"),
    output_path: str = Query(..., description="输出路径"),
    mode: str = Query("auto", description="执行模式"),
    user: Any = Depends(require_auth),
):
    """按名称执行工作流"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()

    try:
        result = manager.run_workflow(
            workflow_name=workflow_name,
            input_path=input_path,
            output_path=output_path,
            mode=mode,
        )

        step_responses = [ToolExecuteResponse(**s.__dict__) for s in result.steps]

        return WorkflowExecuteResponse(
            workflow_name=result.workflow_name,
            status=result.status,
            total_duration_ms=result.total_duration_ms,
            output_files=result.output_files,
            error=result.error,
            summary=result.summary,
            steps=step_responses,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 快捷操作 API
# ============================================================================

@router.post("/quick/render")
async def quick_render(
    project_path: str = Query(..., description="AE项目路径"),
    comp_name: str = Query(..., description="合成名称"),
    output_path: str = Query(..., description="输出路径"),
    mode: str = Query("auto", description="执行模式"),
    user: Any = Depends(require_auth),
):
    """快捷渲染 - 使用AE渲染合成"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()

    result = manager.execute_tool(
        tool_name="after_effects",
        operation="render_comp",
        params={
            "project_path": project_path,
            "comp_name": comp_name,
            "output_path": output_path,
        },
        mode=mode,
    )

    return ToolExecuteResponse(**result.__dict__)


@router.post("/quick/enhance")
async def quick_enhance(
    input_path: str = Query(..., description="输入视频路径"),
    output_path: str = Query(..., description="输出视频路径"),
    model: str = Query("proteus", description="Topaz模型"),
    scale: float = Query(2.0, description="缩放倍数"),
    mode: str = Query("auto", description="执行模式"),
    user: Any = Depends(require_auth),
):
    """快捷增强 - 使用Topaz增强视频"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()

    result = manager.execute_tool(
        tool_name="topaz_video_ai",
        operation="enhance",
        params={
            "input_path": input_path,
            "output_path": output_path,
            "model": model,
            "scale": scale,
        },
        mode=mode,
    )

    return ToolExecuteResponse(**result.__dict__)


@router.post("/quick/encode")
async def quick_encode(
    input_path: str = Query(..., description="输入文件路径"),
    output_path: str = Query(..., description="输出文件路径"),
    codec: str = Query("h264", description="编码格式"),
    mode: str = Query("auto", description="执行模式"),
    user: Any = Depends(require_auth),
):
    """快捷编码 - 使用FFmpeg转码"""
    if not _TOOLCHAIN_AVAILABLE:
        raise HTTPException(status_code=503, detail="工具链模块不可用")

    manager = get_toolchain_manager()

    result = manager.execute_tool(
        tool_name="ffmpeg",
        operation="encode",
        params={
            "input_path": input_path,
            "output_path": output_path,
            "codec": codec,
        },
        mode=mode,
    )

    return ToolExecuteResponse(**result.__dict__)


# ============================================================================
# 模块注册函数
# ============================================================================

def register_toolchain_routes(app) -> None:
    """将工具链路由注册到FastAPI应用"""
    app.include_router(router)
    global _auth
    if _AUTH_AVAILABLE:
        _auth = _get_auth_manager()


if __name__ == "__main__":
    """测试入口"""
    from fastapi.testclient import TestClient

    app = __import__("api_server", fromlist=["app"]).app
    register_toolchain_routes(app)

    client = TestClient(app)

    print("=" * 60)
    print("工具链 API 测试")
    print("=" * 60)

    print("\n1. 获取工具列表")
    response = client.get("/api/v1/toolchain/tools")
    data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"工具总数: {data['total']}")
    print(f"分类: {data['categories']}")

    print("\n2. 获取引擎列表")
    response = client.get("/api/v1/toolchain/engines")
    data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"引擎数: {data['total']}")
    for engine in data["engines"]:
        print(f"  {engine['status']} {engine['name']}: {engine['description']}")

    print("\n3. 获取工作流列表")
    response = client.get("/api/v1/toolchain/workflows")
    data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"工作流数: {data['total']}")
    for wf in data["workflows"]:
        print(f"  • {wf}")

    print("\n4. 执行工具模拟")
    response = client.post(
        "/api/v1/toolchain/tools/execute",
        json={
            "tool_name": "after_effects",
            "operation": "render_comp",
            "params": {"comp_name": "Test Comp", "output_path": "output.mp4"},
            "mode": "simulate",
        },
    )
    data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"成功: {data['success']}")
    print(f"模式: {data['mode_used']}")

    print("\n5. 执行工作流模拟")
    response = client.post(
        "/api/v1/toolchain/workflows/execute",
        json={
            "workflow_name": "delivery_pipeline",
            "input_path": "input.mp4",
            "output_path": "output.mp4",
            "mode": "simulate",
        },
    )
    data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"工作流: {data['workflow_name']}")
    print(f"状态: {data['status']}")
    print(f"摘要: {data['summary']}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
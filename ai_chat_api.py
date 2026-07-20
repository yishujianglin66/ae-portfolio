#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Chat API 模块（V4 原生 Tool Calling 对接）
==============================================

提供自然语言 → 工具调用的完整链路 RESTful 接口:

- POST /api/v1/ai/chat         自然语言对话（自动工具调用）
- GET  /api/v1/ai/tools        列出已注册的 V4 Function Calling 工具
- POST /api/v1/ai/agent/run    一次性 Agent 任务执行（无状态）
- GET  /api/v1/ai/health       AI 服务健康检查

设计要点:
- 使用 ai_agent.V4Agent.chat_with_tools() 实现原生 V4 Tool Calling 闭环
- 工具定义来自 tool_executor.ToolExecutor.list_v4_tools()
- 支持自定义 system_prompt、max_iterations、temperature
- 复用 api_server 的 JWT 认证（require_auth 依赖）

依赖:
- ai_agent.py           - V4Agent.chat_with_tools
- tool_executor.py      - ToolExecutor（工具定义 + 执行）
- auth_system.py        - JWT 认证
- api_server.py         - FastAPI 主服务（注册路由）
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# 尝试导入 V4 Agent
try:
    from ai_agent import V4Agent, get_agent
    _AGENT_AVAILABLE = True
    _agent: Optional[V4Agent] = None
except ImportError:
    _AGENT_AVAILABLE = False
    _agent = None

# 尝试导入工具执行器
try:
    from tool_executor import ToolExecutor, get_executor
    _EXECUTOR_AVAILABLE = True
    _executor: Optional[ToolExecutor] = None
except ImportError:
    _EXECUTOR_AVAILABLE = False
    _executor = None

# 尝试导入认证系统
try:
    from auth_system import get_auth_manager
    _AUTH_AVAILABLE = True
except ImportError:
    _AUTH_AVAILABLE = False

_security = HTTPBearer(auto_error=False)


def _get_agent() -> V4Agent:
    """获取全局 V4 Agent 实例（惰性初始化）"""
    global _agent
    if _agent is None:
        try:
            _agent = get_agent()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"V4 Agent 初始化失败: {e}",
            )
    return _agent


def _get_executor() -> ToolExecutor:
    """获取全局工具执行器实例"""
    global _executor
    if _executor is None:
        if not _EXECUTOR_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="工具执行器不可用",
            )
        try:
            _executor = get_executor()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"工具执行器初始化失败: {e}",
            )
    return _executor


async def _require_auth(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    """JWT 认证依赖（认证系统不可用时降级为放行）"""
    if not _AUTH_AVAILABLE:
        return {"user": "anonymous", "auth_disabled": True}
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        auth = get_auth_manager()
        payload = auth.verify_token(credentials.credentials)
        return {"user": payload.get("sub", "unknown"), "token_payload": payload}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"认证失败: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# 请求/响应模型
# ============================================================================

class AIChatRequest(BaseModel):
    """AI 对话请求（自动 Tool Calling）"""
    message: str = Field(..., min_length=1, max_length=8000, description="用户自然语言请求")
    model: str = Field("pro", description="模型选择: pro / flash")
    use_tools: bool = Field(True, description="是否启用原生 Tool Calling")
    max_iterations: int = Field(5, ge=1, le=20, description="最大工具调用迭代次数")
    max_tokens: int = Field(4096, ge=256, le=32768, description="单次响应最大 token")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="采样温度")
    system_prompt: Optional[str] = Field(None, description="自定义系统提示词")
    tool_names: Optional[List[str]] = Field(
        None, description="限定可用工具名列表（None=全部已注册工具）"
    )


class ToolCallRecord(BaseModel):
    """单次工具调用记录"""
    name: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]
    duration: float
    iteration: int
    tool_call_id: str = ""


class AIChatResponse(BaseModel):
    """AI 对话响应"""
    content: str = Field("", description="最终回答文本")
    tool_calls: List[ToolCallRecord] = Field(default_factory=list, description="工具调用记录")
    iterations: int = Field(0, description="实际迭代次数")
    usage: Dict[str, int] = Field(default_factory=dict, description="token 使用统计")
    model: str = Field("", description="实际使用的模型名")
    provider: str = Field("", description="API 提供商")
    error: str = Field("", description="错误信息（成功时为空）")
    duration: float = Field(0.0, description="总耗时（秒）")
    request_id: str = Field("", description="请求ID")


class AgentRunRequest(BaseModel):
    """Agent 一次性任务执行请求（无状态，不保存历史）"""
    task: str = Field(..., min_length=1, max_length=8000, description="任务描述")
    model: str = Field("pro", description="模型选择")
    max_iterations: int = Field(10, ge=1, le=30, description="最大迭代次数")
    system_prompt: Optional[str] = Field(None, description="自定义系统提示词")
    tool_names: Optional[List[str]] = Field(None, description="限定工具列表")


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    type: str
    engine_name: str = ""
    action: str = ""


class ToolListResponse(BaseModel):
    """工具列表响应"""
    total: int
    tools: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# 路由注册
# ============================================================================

def register_ai_chat_routes(app) -> None:
    """将 AI Chat API 路由注册到 FastAPI app"""
    router = APIRouter(prefix="/api/v1/ai", tags=["AI Agent"])

    @router.get("/health", response_model=Dict[str, Any])
    async def ai_health():
        """AI 服务健康检查"""
        return {
            "status": "healthy" if _AGENT_AVAILABLE else "unavailable",
            "agent_available": _AGENT_AVAILABLE,
            "executor_available": _EXECUTOR_AVAILABLE,
            "auth_available": _AUTH_AVAILABLE,
            "provider": _agent.provider if _agent is not None else "uninitialized",
        }

    @router.get("/tools", response_model=ToolListResponse)
    async def list_ai_tools(user: dict = Depends(_require_auth)):
        """列出已注册的 V4 Function Calling 工具"""
        if not _EXECUTOR_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="工具执行器不可用",
            )
        executor = _get_executor()
        tools = executor.list_v4_tools()
        return ToolListResponse(total=len(tools), tools=tools)

    @router.post("/chat", response_model=AIChatResponse)
    async def ai_chat(req: AIChatRequest, user: dict = Depends(_require_auth)):
        """AI 对话（原生 V4 Tool Calling 闭环）

        流程: 用户消息 + tools → V4 返回 tool_calls → 本地执行 →
              结果回传 V4 → V4 生成最终回答
        """
        if not _AGENT_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="V4 Agent 不可用（未配置 API Key 或模块缺失）",
            )

        agent = _get_agent()
        request_id = f"ai_{int(time.time() * 1000)}"

        # 构造工具定义列表
        tools: Optional[List[Dict[str, Any]]] = None
        if req.use_tools and _EXECUTOR_AVAILABLE:
            executor = _get_executor()
            all_tools = executor.list_v4_tools()
            if req.tool_names:
                # 过滤出指定工具
                wanted = set(req.tool_names)
                tools = [t for t in all_tools if t.get("function", {}).get("name", "") in wanted]
                if not tools:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"指定的工具均未注册: {req.tool_names}",
                    )
            else:
                tools = all_tools if all_tools else None

        start = time.time()
        try:
            result = agent.chat_with_tools(
                message=req.message,
                tools=tools,
                tool_executor=None,  # 使用默认 tool_executor.execute_tool
                model=req.model,
                max_iterations=req.max_iterations,
                max_tokens=req.max_tokens,
                system_prompt=req.system_prompt,
                temperature=req.temperature,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI 对话异常: {e}",
            )

        duration = time.time() - start

        # 序列化工具调用记录
        tool_calls = [
            ToolCallRecord(
                name=tc.get("name", ""),
                arguments=tc.get("arguments", {}),
                result=tc.get("result", {}),
                duration=tc.get("duration", 0.0),
                iteration=tc.get("iteration", 0),
                tool_call_id=tc.get("tool_call_id", ""),
            )
            for tc in result.get("tool_calls", [])
        ]

        return AIChatResponse(
            content=result.get("content", ""),
            tool_calls=tool_calls,
            iterations=result.get("iterations", 0),
            usage=result.get("usage", {}),
            model=result.get("model", ""),
            provider=result.get("provider", ""),
            error=result.get("error", ""),
            duration=round(duration, 3),
            request_id=request_id,
        )

    @router.post("/agent/run", response_model=AIChatResponse)
    async def agent_run(req: AgentRunRequest, user: dict = Depends(_require_auth)):
        """Agent 一次性任务执行（无状态）

        与 /chat 区别:
        - 不读取/写入 agent.history
        - 默认 max_iterations 更高（10）
        - 适合一次性自动化任务
        """
        if not _AGENT_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="V4 Agent 不可用",
            )

        # 创建独立 agent 实例（避免污染全局历史）
        try:
            from ai_agent import V4Agent as _V4A
            standalone_agent = _V4A()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Agent 创建失败: {e}",
            )

        # 工具定义
        tools: Optional[List[Dict[str, Any]]] = None
        if _EXECUTOR_AVAILABLE:
            executor = _get_executor()
            all_tools = executor.list_v4_tools()
            if req.tool_names:
                wanted = set(req.tool_names)
                tools = [t for t in all_tools if t.get("function", {}).get("name", "") in wanted]
            else:
                tools = all_tools if all_tools else None

        request_id = f"agent_{int(time.time() * 1000)}"
        start = time.time()

        try:
            result = standalone_agent.chat_with_tools(
                message=req.task,
                tools=tools,
                model=req.model,
                max_iterations=req.max_iterations,
                system_prompt=req.system_prompt,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent 执行异常: {e}",
            )

        duration = time.time() - start
        tool_calls = [
            ToolCallRecord(
                name=tc.get("name", ""),
                arguments=tc.get("arguments", {}),
                result=tc.get("result", {}),
                duration=tc.get("duration", 0.0),
                iteration=tc.get("iteration", 0),
                tool_call_id=tc.get("tool_call_id", ""),
            )
            for tc in result.get("tool_calls", [])
        ]

        return AIChatResponse(
            content=result.get("content", ""),
            tool_calls=tool_calls,
            iterations=result.get("iterations", 0),
            usage=result.get("usage", {}),
            model=result.get("model", ""),
            provider=result.get("provider", ""),
            error=result.get("error", ""),
            duration=round(duration, 3),
            request_id=request_id,
        )

    app.include_router(router)

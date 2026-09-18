#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy/api.py
视频风格智能复制 - FastAPI接口

复用项目:
  - api_server.py 的路由注册
  - style_copy/workflow.py 的工作流
"""

import json
import os
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from style_copy.workflow import StyleCopyWorkflow

router = APIRouter(prefix="/api/style-copy", tags=["style-copy"])


class StyleCopyRequest(BaseModel):
    input: str
    work_dir: str | None = None


class StyleCopyResponse(BaseModel):
    success: bool
    step: str
    error: str | None = None
    data: dict | None = None


@router.post("/run", response_model=StyleCopyResponse)
async def run_style_copy(request: StyleCopyRequest):
    """执行风格复制工作流"""
    try:
        workflow = StyleCopyWorkflow(work_dir=request.work_dir)
        result = workflow.run(request.input)
        
        return StyleCopyResponse(
            success=result.get("success", False),
            step=result.get("step", "unknown"),
            error=result.get("error"),
            data=result.get("data")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_style(request: StyleCopyRequest):
    """仅分析风格，不执行"""
    try:
        from style_copy.input_parser import InputParser
        from style_copy.style_analyzer import StyleAnalyzer
        
        parser = InputParser()
        parse_result = parser.parse(request.input)
        
        if not parse_result["success"]:
            return {"success": False, "error": parse_result.get("error")}
        
        analyzer = StyleAnalyzer()
        
        if parse_result["type"] == "url":
            style_result = analyzer.analyze_from_video(
                parse_result["video_path"],
                parse_result.get("keyframe_paths", [])
            )
        else:
            style_result = analyzer.analyze_from_prompt(parse_result["prompt"])
        
        return style_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestrate")
async def orchestrate_tools(request: dict):
    """生成工具调用序列"""
    try:
        from style_copy.tool_orchestrator import ToolOrchestrator
        
        style = request.get("style")
        input_video = request.get("input_video", "")
        
        if not style:
            raise HTTPException(status_code=400, detail="缺少style参数")
        
        orchestrator = ToolOrchestrator()
        result = orchestrator.generate_tool_sequence(style, input_video)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "module": "style-copy"}


def register(app):
    """注册路由到主应用"""
    app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI(title="Style Copy API")
    register(app)
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
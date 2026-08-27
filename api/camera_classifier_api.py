#!/usr/bin/env python3
"""
运镜分类器API服务
提供REST API接口用于视频运镜分类
"""

import os
import sys
from pathlib import Path
import tempfile
import json
from typing import Dict, Tuple, Optional
import logging

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from models.camera_classifier.camera_classifier_2class import CameraClassifier2Class
from models.camera_classifier.camera_classifier_hierarchical import HierarchicalCameraClassifier
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
from pydantic import BaseModel

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Camera Motion Classifier API", version="1.0.0")

# 全局分类器实例
classifier_2class = None
classifier_hierarchical = None

class ClassificationResult(BaseModel):
    prediction: str
    confidence: float
    method: str
    description: Optional[str] = None
    processing_time: float

class ClassificationRequest(BaseModel):
    video_path: str
    use_vlm: bool = True

def init_classifiers():
    """初始化分类器"""
    global classifier_2class, classifier_hierarchical
    
    logger.info("正在初始化2类运镜分类器...")
    try:
        classifier_2class = CameraClassifier2Class(
            model_path="models/camera_classifier/d2_cnn_2class_best.pt",
            device="cpu"
        )
        logger.info("2类运镜分类器初始化完成")
    except Exception as e:
        logger.error(f"2类运镜分类器初始化失败: {e}")
        raise
    
    logger.info("正在初始化分层运镜分类器...")
    try:
        classifier_hierarchical = HierarchicalCameraClassifier(
            cnn_model_path="models/camera_classifier/d2_cnn_2class_best.pt",
            device="cpu"  # VLM会在需要时加载
        )
        logger.info("分层运镜分类器初始化完成")
    except Exception as e:
        logger.error(f"分层运镜分类器初始化失败: {e}")
        raise

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化分类器"""
    try:
        init_classifiers()
        logger.info("API服务启动完成")
    except Exception as e:
        logger.error(f"API服务启动失败: {e}")
        raise

@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "name": "Camera Motion Classifier API",
        "version": "1.0.0",
        "description": "用于视频运镜分类的API服务，支持2类(static/motion)和3类(static/zoom/tilt-orbit)分类",
        "endpoints": {
            "/classify_2class": "2类运镜分类 (static vs motion)",
            "/classify_3class": "3类运镜分类 (static/zoom/tilt-orbit)",
            "/health": "健康检查"
        },
        "performance": {
            "2class_accuracy": 0.6725,
            "2class_inference_time": "~1-2秒 (CPU)",
            "3class_expected_accuracy": "0.50-0.60"
        }
    }

@app.post("/classify_2class", response_model=ClassificationResult)
async def classify_2class(
    video: UploadFile = File(...),
    use_cnn: bool = Form(True)
):
    """2类运镜分类接口"""
    start_time = asyncio.get_event_loop().time()
    
    try:
        # 检查文件类型
        if not video.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')):
            raise HTTPException(status_code=400, detail="仅支持视频文件 (mp4, avi, mov, mkv, wmv, flv)")
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video.filename)[1]) as tmp_file:
            content = await video.read()
            tmp_file.write(content)
            temp_path = tmp_file.name
        
        try:
            # 执行分类
            if classifier_2class is None:
                raise HTTPException(status_code=500, detail="分类器未初始化")
            
            pred, conf, method = classifier_2class.predict(temp_path, use_cnn=use_cnn)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            result = ClassificationResult(
                prediction=pred,
                confidence=conf,
                method=method,
                processing_time=processing_time
            )
            
            logger.info(f"2类分类完成: {pred} (confidence: {conf:.3f}, time: {processing_time:.2f}s)")
            
            return result
            
        finally:
            # 清理临时文件
            os.unlink(temp_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2类分类失败: {e}")
        raise HTTPException(status_code=500, detail=f"分类失败: {str(e)}")

@app.post("/classify_3class", response_model=ClassificationResult)
async def classify_3class(
    video: UploadFile = File(...),
    use_vlm: bool = Form(True)
):
    """3类运镜分类接口"""
    start_time = asyncio.get_event_loop().time()
    
    try:
        # 检查文件类型
        if not video.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')):
            raise HTTPException(status_code=400, detail="仅支持视频文件 (mp4, avi, mov, mkv, wmv, flv)")
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video.filename)[1]) as tmp_file:
            content = await video.read()
            tmp_file.write(content)
            temp_path = tmp_file.name
        
        try:
            # 执行分类
            if classifier_hierarchical is None:
                raise HTTPException(status_code=500, detail="分层分类器未初始化")
            
            pred, conf, method, desc = classifier_hierarchical.predict(temp_path, use_vlm=use_vlm)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            result = ClassificationResult(
                prediction=pred,
                confidence=conf,
                method=method,
                description=desc,
                processing_time=processing_time
            )
            
            logger.info(f"3类分类完成: {pred} (confidence: {conf:.3f}, time: {processing_time:.2f}s)")
            
            return result
            
        finally:
            # 清理临时文件
            os.unlink(temp_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"3类分类失败: {e}")
        raise HTTPException(status_code=500, detail=f"分类失败: {str(e)}")

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "classifiers_initialized": {
            "2class": classifier_2class is not None,
            "hierarchical": classifier_hierarchical is not None
        },
        "model_info": {
            "2class_accuracy": 0.6725,
            "2class_model_path": "models/camera_classifier/d2_cnn_2class_best.pt",
            "expected_3class_accuracy": "0.50-0.60"
        }
    }

def run_api(host: str = "0.0.0.0", port: int = 8000):
    """运行API服务"""
    logger.info(f"启动运镜分类API服务，地址: {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    # 可以通过命令行参数指定主机和端口
    import argparse
    
    parser = argparse.ArgumentParser(description="运镜分类器API服务")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听主机地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    
    args = parser.parse_args()
    
    run_api(host=args.host, port=args.port)
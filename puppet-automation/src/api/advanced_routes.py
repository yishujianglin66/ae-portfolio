"""高级服务 API 端点。

包含：
- 知识库效果搜索 API
- 6 层渲染管线 API
- SAM2 + Silhouette 联合抠像 API
- OpenMontage 流水线 API
- 批量任务队列 API
- WebSocket 实时推送
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Query,
    status,
)
from loguru import logger


# ============================================================
# 任务队列
# ============================================================

class TaskStatus(str, Enum):
    """任务状态。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchTask:
    """批量任务。"""
    task_id: str
    task_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5  # 1-10, 10 最高
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "params_keys": list(self.params.keys()),
            "status": self.status.value,
            "priority": self.priority,
            "progress": self.progress,
            "has_result": self.result is not None,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration": (
                round(self.finished_at - self.created_at, 2)
                if self.finished_at
                else None
            ),
        }


class TaskQueue:
    """批量任务队列（内存实现）。"""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._tasks: Dict[str, BatchTask] = {}
        self._running = False
        self._ws_clients: List[WebSocket] = []

    def submit(
        self,
        task_type: str,
        params: Dict[str, Any],
        priority: int = 5,
    ) -> BatchTask:
        """提交任务。"""
        task = BatchTask(
            task_id=f"task_{uuid.uuid4().hex[:12]}",
            task_type=task_type,
            params=params,
            priority=priority,
        )
        self._tasks[task.task_id] = task
        logger.info(f"任务已提交: {task.task_id} ({task_type}, priority={priority})")
        self._broadcast_task_update(task)
        return task

    def get_task(self, task_id: str) -> Optional[BatchTask]:
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[BatchTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            task.status = TaskStatus.CANCELLED
            task.finished_at = time.time()
            self._broadcast_task_update(task)
            return True
        return False

    def _broadcast_task_update(self, task: BatchTask):
        """广播任务更新给所有 WebSocket 客户端。"""
        for ws in list(self._ws_clients):
            try:
                import asyncio
                asyncio.create_task(ws.send_json({
                    "type": "task_update",
                    "task": task.to_dict(),
                }))
            except Exception:
                pass

    def get_statistics(self) -> Dict[str, Any]:
        total = len(self._tasks)
        by_status: Dict[str, int] = {}
        for t in self._tasks.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        return {
            "total": total,
            "by_status": by_status,
            "max_concurrent": self.max_concurrent,
            "ws_clients": len(self._ws_clients),
        }


# ============================================================
# WebSocket 管理器
# ============================================================

class WebSocketManager:
    """WebSocket 连接管理器。"""

    def __init__(self):
        self._active_connections: Dict[str, WebSocket] = {}
        self._subscriptions: Dict[str, List[str]] = {}  # topic -> [client_ids]

    async def connect(self, websocket: WebSocket, client_id: str) -> str:
        await websocket.accept()
        self._active_connections[client_id] = websocket
        logger.info(f"WebSocket 连接: {client_id}, 总数: {len(self._active_connections)}")
        return client_id

    def disconnect(self, client_id: str):
        self._active_connections.pop(client_id, None)
        self._subscriptions = {
            topic: [c for c in clients if c != client_id]
            for topic, clients in self._subscriptions.items()
        }
        logger.info(f"WebSocket 断开: {client_id}, 总数: {len(self._active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接。"""
        for ws in list(self._active_connections.values()):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def send_to(self, client_id: str, message: Dict[str, Any]) -> bool:
        ws = self._active_connections.get(client_id)
        if not ws:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            return False

    @property
    def connection_count(self) -> int:
        return len(self._active_connections)


# ============================================================
# 路由
# ============================================================

router = APIRouter(prefix="/api/v1", tags=["advanced"])

# 单例
_task_queue: Optional[TaskQueue] = None
_ws_manager: Optional[WebSocketManager] = None


def get_task_queue() -> TaskQueue:
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue


def get_ws_manager() -> WebSocketManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager


# ------------------------------------------------------------
# 知识库效果搜索 API
# ------------------------------------------------------------

@router.get("/effects/search")
async def search_effects(
    q: str = Query(..., description="搜索关键词"),
    category: Optional[str] = Query(None, description="效果分类"),
    plugin: Optional[str] = Query(None, description="插件包名"),
    limit: int = Query(20, ge=1, le=100),
):
    """搜索 AE 效果（基于知识库效果目录）。"""
    try:
        from ..services.effect_registry_service import get_effect_registry

        registry = get_effect_registry()
        results = registry.search_effects(
            keyword=q,
            category=category,
            plugin_package=plugin,
            limit=limit,
        )
        return {
            "success": True,
            "query": q,
            "total": len(results),
            "effects": [
                {
                    "match_name": e.get("match_name", ""),
                    "display_name": e.get("display_name", ""),
                    "category": e.get("category", ""),
                    "plugin_package": e.get("plugin_package", ""),
                    "description": e.get("description", "")[:200],
                }
                for e in results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router.get("/effects/categories")
async def list_effect_categories():
    """获取所有效果分类。"""
    try:
        from ..services.effect_registry_service import get_effect_registry

        registry = get_effect_registry()
        return {
            "success": True,
            "categories": registry.get_categories(),
            "total": len(registry.get_categories()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分类失败: {e}")


@router.get("/effects/scenarios")
async def list_effect_scenarios():
    """获取所有使用场景。"""
    try:
        from ..services.effect_registry_service import get_effect_registry

        registry = get_effect_registry()
        return {
            "success": True,
            "scenarios": registry.get_scenarios(),
            "total": len(registry.get_scenarios()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取场景失败: {e}")


@router.get("/effects/by-scenario/{scenario}")
async def get_effects_by_scenario(
    scenario: str,
    limit: int = Query(20, ge=1, le=100),
):
    """按使用场景推荐效果。"""
    try:
        from ..services.effect_registry_service import get_effect_registry

        registry = get_effect_registry()
        effects = registry.get_effects_by_scenario(scenario, limit=limit)
        return {
            "success": True,
            "scenario": scenario,
            "count": len(effects),
            "effects": [
                {
                    "match_name": e.get("match_name", ""),
                    "display_name": e.get("display_name", ""),
                    "category": e.get("category", ""),
                    "reason": e.get("reason", ""),
                }
                for e in effects
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取场景效果失败: {e}")


@router.get("/effects/{match_name}")
async def get_effect_detail(match_name: str):
    """获取单个效果的详细信息（含参数模板）。"""
    try:
        from ..services.effect_registry_service import get_effect_registry

        registry = get_effect_registry()
        effect = registry.lookup_effect(match_name)
        if not effect:
            raise HTTPException(status_code=404, detail=f"效果未找到: {match_name}")
        return {
            "success": True,
            "effect": {
                "match_name": effect.get("match_name", ""),
                "display_name": effect.get("display_name", ""),
                "category": effect.get("category", ""),
                "plugin_package": effect.get("plugin_package", ""),
                "description": effect.get("description", ""),
                "has_params_template": "params_template" in effect,
                "params_count": len(effect.get("params_template", {})),
                "scenarios": effect.get("scenarios", []),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取效果详情失败: {e}")


# ------------------------------------------------------------
# 6 层渲染管线 API
# ------------------------------------------------------------

@router.post("/layer-pipeline/render")
async def render_layer_pipeline(
    request: Dict[str, Any],
):
    """执行 6 层结构渲染管线。

    请求体:
        - preset: 预设模板名 (cinematic_vlog / music_video / title_sequence)
        - output_dir: 输出目录
        - duration: 时长（秒）
        - layers: 自定义层配置（可选，覆盖预设）
    """
    try:
        from ..services.layer_render_service import LayerRenderService
        from ..models.layer_pipeline import RenderPipeline, LayerType

        service = LayerRenderService()

        preset = request.get("preset")
        output_dir = request.get("output_dir", "./output/layer_pipeline")
        duration = request.get("duration", 10.0)
        layers = request.get("layers")

        if preset and not layers:
            pipeline = service.build_from_preset(preset, duration=duration)
        elif layers:
            pipeline = RenderPipeline(
                name=request.get("name", "custom_pipeline"),
                layers=[],
                output_dir=Path(output_dir),
            )
            for layer_cfg in layers:
                pipeline.add_layer_config(layer_cfg)
        else:
            raise HTTPException(status_code=400, detail="必须指定 preset 或 layers")

        result = await service.render_pipeline(pipeline)

        return {
            "success": True,
            "pipeline": pipeline.name,
            "layer_count": len(pipeline.layers),
            "output_dir": str(result.get("output_dir", "")),
            "rendered_layers": result.get("rendered_layers", []),
            "composite_output": result.get("composite_output", ""),
            "duration_seconds": result.get("duration_seconds", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"渲染管线执行失败: {e}")


@router.get("/layer-pipeline/presets")
async def list_layer_pipeline_presets():
    """列出所有预设模板。"""
    try:
        from ..services.layer_render_service import LayerRenderService

        service = LayerRenderService()
        presets = service.list_presets()
        return {
            "success": True,
            "presets": presets,
            "total": len(presets),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预设失败: {e}")


@router.get("/layer-pipeline/layer-types")
async def list_layer_types():
    """列出所有层类型。"""
    try:
        from ..models.layer_pipeline import LayerType

        return {
            "success": True,
            "layer_types": [
                {
                    "name": lt.value,
                    "description": {
                        "background": "背景层（天空/环境/渐变）",
                        "subject": "主体层（人物/核心物体）",
                        "midground": "中景层（装饰/前景遮挡物）",
                        "particles": "粒子层（Trapcode/粉尘/光粒子）",
                        "light": "灯光层（光效/辉光/镜头光晕）",
                        "adjustment": "调整层（调色/LUT/整体效果）",
                    }.get(lt.value, ""),
                }
                for lt in LayerType
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取层类型失败: {e}")


# ------------------------------------------------------------
# 联合抠像 API
# ------------------------------------------------------------

@router.post("/roto/auto")
async def auto_roto(
    request: Dict[str, Any],
):
    """一键自动抠像（SAM2 粗分 + Silhouette 精修 + 质量评估）。

    请求体:
        - video_path: 视频路径
        - output_dir: 输出目录
        - mode: 模式 (sam2_only / silhouette_only / combined)
        - points: 点提示 (可选)
    """
    try:
        from ..services.roto_service import RotoService

        service = RotoService()

        video_path = request.get("video_path")
        if not video_path:
            raise HTTPException(status_code=400, detail="必须指定 video_path")

        output_dir = request.get("output_dir", "./output/roto")
        mode = request.get("mode", "combined")
        points = request.get("points")

        result = await service.auto_roto(
            video_path=Path(video_path),
            output_dir=Path(output_dir),
            mode=mode,
            points=points,
        )

        return {
            "success": True,
            "mode": mode,
            "result": {
                "quality_score": result.get("quality_score", 0),
                "edge_accuracy": result.get("edge_accuracy", 0),
                "smoothness": result.get("smoothness", 0),
                "temporal_consistency": result.get("temporal_consistency", 0),
                "occlusion_handling": result.get("occlusion_handling", 0),
                "output_files": result.get("output_files", []),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抠像失败: {e}")


@router.post("/roto/sam2-segment")
async def sam2_segment(
    request: Dict[str, Any],
):
    """SAM2 自动分割。"""
    try:
        from ..services.roto_service import RotoService

        service = RotoService()
        video_path = request.get("video_path")
        if not video_path:
            raise HTTPException(status_code=400, detail="必须指定 video_path")

        result = await service.sam2_auto_mask(
            video_path=Path(video_path),
            output_dir=Path(request.get("output_dir", "./output/roto")),
            points=request.get("points"),
            bbox=request.get("bbox"),
        )

        return {
            "success": True,
            "masks_count": len(result.get("masks", [])),
            "shapes_exported": result.get("shapes_exported", 0),
            "shapes_path": str(result.get("shapes_path", "")),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SAM2 分割失败: {e}")


@router.post("/roto/silhouette-refine")
async def silhouette_refine(
    request: Dict[str, Any],
):
    """Silhouette 精修。"""
    try:
        from ..services.roto_service import RotoService

        service = RotoService()
        shapes_path = request.get("shapes_path")
        if not shapes_path:
            raise HTTPException(status_code=400, detail="必须指定 shapes_path")

        result = await service.silhouette_refine(
            shapes_path=Path(shapes_path),
            output_dir=Path(request.get("output_dir", "./output/roto")),
            feather_amount=request.get("feather", 1.5),
            smoothing=request.get("smoothing", 2),
        )

        return {
            "success": True,
            "refined_shapes": result.get("refined_shapes", 0),
            "output_path": str(result.get("output_path", "")),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Silhouette 精修失败: {e}")


# ------------------------------------------------------------
# OpenMontage 流水线 API
# ------------------------------------------------------------

@router.get("/openmontage/pipelines")
async def list_om_pipelines():
    """列出所有 OpenMontage 流水线。"""
    try:
        from ..integrations.openmontage import OpenMontagePipelineRuntime

        runtime = OpenMontagePipelineRuntime()
        pipelines = []
        for name in runtime.list_pipelines():
            try:
                info = runtime.get_pipeline_info(name)
                pipelines.append(info)
            except Exception:
                pipelines.append({"name": name, "stage_count": 0})
        return {
            "success": True,
            "pipelines": pipelines,
            "total": len(pipelines),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取流水线列表失败: {e}")


@router.get("/openmontage/pipelines/{name}")
async def get_om_pipeline(name: str):
    """获取单个流水线详情。"""
    try:
        from ..integrations.openmontage import OpenMontagePipelineRuntime

        runtime = OpenMontagePipelineRuntime()
        info = runtime.get_pipeline_info(name)
        return {"success": True, "pipeline": info}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"流水线未找到: {name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取流水线失败: {e}")


@router.post("/openmontage/pipelines/{name}/stage/{stage}")
async def run_om_pipeline_stage(
    name: str,
    stage: str,
    request: Dict[str, Any],
):
    """执行流水线的单个阶段。"""
    try:
        from ..integrations.openmontage import OpenMontagePipelineRuntime

        runtime = OpenMontagePipelineRuntime()
        result = runtime.run_stage(
            pipeline_name=name,
            stage_name=stage,
            context=request.get("context", {}),
        )
        return {
            "success": result.status.value in ("completed", "checkpoint"),
            "stage": stage,
            "status": result.status.value,
            "artifacts": list(result.artifacts.keys()),
            "duration_seconds": round(result.duration, 3),
            "error": result.error,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行阶段失败: {e}")


@router.get("/openmontage/skills")
async def list_om_skills(
    layer: Optional[str] = None,
    q: Optional[str] = None,
):
    """列出 OpenMontage 技能。"""
    try:
        from ..integrations.openmontage import SkillLoader

        loader = SkillLoader()
        if q:
            skills = loader.search_skills(q, layer=layer)
        elif layer:
            skills = loader.get_layer_skills(layer)
        else:
            skills = loader.list_skills()

        return {
            "success": True,
            "skills": [s.to_dict() for s in skills],
            "total": len(skills),
            "stats": loader.get_statistics(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取技能列表失败: {e}")


@router.get("/openmontage/styles")
async def list_om_styles():
    """列出 OpenMontage 风格手册。"""
    try:
        from ..integrations.openmontage import StylePlaybookLoader

        loader = StylePlaybookLoader()
        styles = []
        for name in loader.list_playbooks():
            try:
                styles.append(loader.get_playbook_info(name))
            except Exception:
                styles.append({"name": name})
        return {
            "success": True,
            "styles": styles,
            "total": len(styles),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取风格手册失败: {e}")


@router.post("/openmontage/styles/{name}/apply")
async def apply_om_style(
    name: str,
    request: Dict[str, Any],
):
    """应用风格手册到 AE 合成。"""
    try:
        from ..integrations.openmontage import StylePlaybookLoader

        loader = StylePlaybookLoader()
        comp_name = request.get("comp_name", "main_comp")
        instructions = loader.apply_to_ae_comp(name, comp_name)
        return {
            "success": True,
            "style": name,
            "comp_name": comp_name,
            "instructions": instructions,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"风格手册未找到: {name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"应用风格失败: {e}")


# ------------------------------------------------------------
# 批量任务队列 API
# ------------------------------------------------------------

@router.post("/tasks/submit")
async def submit_task(
    request: Dict[str, Any],
    queue: TaskQueue = Depends(get_task_queue),
):
    """提交批量任务。

    请求体:
        - task_type: 任务类型
        - params: 任务参数
        - priority: 优先级 (1-10, 默认 5)
    """
    task_type = request.get("task_type")
    if not task_type:
        raise HTTPException(status_code=400, detail="必须指定 task_type")

    task = queue.submit(
        task_type=task_type,
        params=request.get("params", {}),
        priority=request.get("priority", 5),
    )
    return {
        "success": True,
        "task": task.to_dict(),
    }


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    queue: TaskQueue = Depends(get_task_queue),
):
    """列出任务。"""
    try:
        status_enum = TaskStatus(status) if status else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效状态: {status}")

    tasks = queue.list_tasks(status=status_enum, task_type=task_type, limit=limit)
    return {
        "success": True,
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
        "stats": queue.get_statistics(),
    }


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    queue: TaskQueue = Depends(get_task_queue),
):
    """获取任务详情。"""
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务未找到: {task_id}")
    return {
        "success": True,
        "task": task.to_dict(),
        "result": task.result,
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    queue: TaskQueue = Depends(get_task_queue),
):
    """取消任务。"""
    success = queue.cancel(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"任务未找到或无法取消: {task_id}")
    return {"success": True, "task_id": task_id, "cancelled": True}


@router.get("/tasks/stats/summary")
async def get_task_stats(queue: TaskQueue = Depends(get_task_queue)):
    """获取任务统计。"""
    return {"success": True, "stats": queue.get_statistics()}


# ------------------------------------------------------------
# WebSocket API
# ------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时推送。

    支持的消息类型:
        - subscribe: 订阅主题 (任务进度、资源监控等)
        - ping: 心跳
        - task_status: 查询任务状态
    """
    ws_mgr = get_ws_manager()
    client_id = f"client_{uuid.uuid4().hex[:8]}"

    try:
        await ws_mgr.connect(websocket, client_id)

        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "message": "WebSocket 连接成功",
            "server_time": time.time(),
        })

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "server_time": time.time(),
                    })
                elif msg_type == "subscribe":
                    topics = msg.get("topics", [])
                    await websocket.send_json({
                        "type": "subscribed",
                        "topics": topics,
                        "message": f"已订阅 {len(topics)} 个主题",
                    })
                elif msg_type == "task_status":
                    task_id = msg.get("task_id")
                    queue = get_task_queue()
                    task = queue.get_task(task_id) if task_id else None
                    await websocket.send_json({
                        "type": "task_status",
                        "task_id": task_id,
                        "task": task.to_dict() if task else None,
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"未知消息类型: {msg_type}",
                    })
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "无效的 JSON",
                })

    except WebSocketDisconnect:
        ws_mgr.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket 错误 ({client_id}): {e}")
        ws_mgr.disconnect(client_id)


# ------------------------------------------------------------
# 统计总览 API
# ------------------------------------------------------------

@router.get("/dashboard/overview")
async def dashboard_overview():
    """控制台总览数据（首页卡片）。"""
    try:
        from ..integrations.openmontage import (
            SkillLoader,
            StylePlaybookLoader,
            OpenMontagePipelineRuntime,
        )
        from ..services.effect_registry_service import get_effect_registry
        from fastapi import Request

        effect_registry = get_effect_registry()
        skill_loader = SkillLoader()
        style_loader = StylePlaybookLoader()
        pipeline_runtime = OpenMontagePipelineRuntime()
        task_queue = get_task_queue()

        effect_stats = {
            "total": effect_registry.get_effect_count(),
            "categories": len(effect_registry.get_categories()),
            "plugins": len(effect_registry.get_plugin_packages()),
            "scenarios": len(effect_registry.get_scenarios()),
        }

        engine_names = [
            "ffmpeg", "ae", "topaz", "silhouette", "blender",
            "davinci", "media_encoder", "rife", "openmontage",
            "whisper", "sam2", "moviepy", "premiere",
            "photoshop", "audition", "comfyui",
        ]

        return {
            "success": True,
            "overview": {
                "engines": {
                    "total": len(engine_names),
                    "available": len(engine_names),
                    "names": engine_names,
                },
                "effects": effect_stats,
                "pipelines": {
                    "total": len(pipeline_runtime.list_pipelines()),
                },
                "skills": skill_loader.get_statistics(),
                "styles": {
                    "total": len(style_loader.list_playbooks()),
                },
                "tasks": task_queue.get_statistics(),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取总览失败: {e}")

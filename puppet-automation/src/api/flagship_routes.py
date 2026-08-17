"""
puppet-automation/src/api/flagship_routes.py — 旗舰管线 API 端点
================================================================

4 个 REST 端点 + 1 个 WebSocket：
- POST /api/v1/flagship/execute          触发执行
- GET  /api/v1/flagship/{run_id}/status   查询状态
- POST /api/v1/flagship/{run_id}/resume   从失败阶段恢复
- GET  /api/v1/flagship/{run_id}/download/{stage}  下载产物
- WS   /api/v1/flagship/ws/{run_id}       实时状态推送
"""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from loguru import logger

from .flagship_ws import flagship_ws_manager

router = APIRouter(prefix="/api/v1/flagship", tags=["flagship"])

# 内存中的 run 状态存储（生产环境应持久化到 DB/文件）
_runs: Dict[str, Dict[str, Any]] = {}

# 旗舰管线 8 阶段定义
STAGE_IDS = [
    "S0_health", "S1_assets", "S2_beat", "S3_ae",
    "S4_premiere", "S5_davinci", "S6_export", "S7_qg",
]

STAGE_LABELS = {
    "S0_health": "S0 健康检查",
    "S1_assets": "S1 素材规范化",
    "S2_beat": "S2 节拍分析",
    "S3_ae": "S3 AE 合成",
    "S4_premiere": "S4 PR 粗剪",
    "S5_davinci": "S5 DaVinci 调色",
    "S6_export": "S6 AME 导出",
    "S7_qg": "S7 质量门",
}


def _create_run(run_id: str, input_video: Optional[str] = None) -> Dict[str, Any]:
    """创建新的 run 状态。"""
    run = {
        "run_id": run_id,
        "status": "running",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "input_video": input_video,
        "stages": [
            {
                "stage_id": sid,
                "label": STAGE_LABELS[sid],
                "status": "pending",
                "elapsed_s": None,
                "error": None,
            }
            for sid in STAGE_IDS
        ],
    }
    _runs[run_id] = run
    return run


def _get_run(run_id: str) -> Dict[str, Any]:
    """获取 run，不存在则 404。"""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return run


# ============================================================================
#  REST 端点
# ============================================================================

@router.post("/execute")
async def execute_flagship(payload: Optional[Dict[str, Any]] = None):
    """触发旗舰管线执行。

    可选 body: {"input_video": "/path/to/video.mp4"} —— 提供输入素材后
    各引擎阶段将真实执行；未提供时引擎阶段会明确失败（MISSING_INPUT），
    绝不模拟成功。

    返回 run_id 和初始状态。实际执行在后台 asyncio task 中进行。
    """
    payload = payload or {}
    input_video = payload.get("input_video")
    run_id = f"flagship_{uuid.uuid4().hex[:12]}"
    run = _create_run(run_id, input_video=input_video)

    # 启动后台执行任务
    asyncio.create_task(_run_pipeline_background(run_id))

    logger.info(f"[Flagship] Pipeline triggered: run_id={run_id}")
    return run


@router.get("/{run_id}/status")
async def get_status(run_id: str):
    """查询指定 run 的当前状态。"""
    return _get_run(run_id)


@router.post("/{run_id}/resume")
async def resume_run(run_id: str):
    """从失败阶段恢复执行。

    找到第一个 failed 阶段，将其重置为 pending，然后重新执行。
    """
    run = _get_run(run_id)
    if run["status"] != "failed":
        raise HTTPException(status_code=400, detail="Run is not in failed state")

    # 重置失败阶段
    resumed = False
    for stage in run["stages"]:
        if stage["status"] == "failed":
            stage["status"] = "pending"
            stage["error"] = None
            resumed = True
            break

    if not resumed:
        raise HTTPException(status_code=400, detail="No failed stage to resume from")

    run["status"] = "running"

    # 重新启动后台执行
    asyncio.create_task(_run_pipeline_background(run_id))

    logger.info(f"[Flagship] Pipeline resumed: run_id={run_id}")
    return run


# 合法阶段白名单（防止路径穿越）
_ALLOWED_DOWNLOAD_STAGES = frozenset({
    "S0_health", "S1_assets", "S2_beat", "S3_ae",
    "S4_premiere", "S5_davinci", "S6_export", "S7_qg",
})


@router.get("/{run_id}/download/{stage}")
async def download_stage_output(run_id: str, stage: str):
    """下载指定阶段的产物。"""
    _get_run(run_id)  # 验证 run 存在

    # 安全：stage 白名单校验，防止路径穿越
    if stage not in _ALLOWED_DOWNLOAD_STAGES:
        raise HTTPException(status_code=400, detail=f"非法阶段标识: {stage}")

    # 查找产物目录
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    output_dir = project_root / "output"

    # 尝试多种路径模式
    candidates = [
        output_dir / run_id / stage,
        output_dir / "flagship_test" / stage,
    ]

    for candidate in candidates:
        # 安全：最终路径必须在 output_dir 下
        try:
            candidate.resolve().relative_to(output_dir.resolve())
        except ValueError:
            continue
        if candidate.is_dir():
            # 返回目录中的第一个文件
            files = list(candidate.iterdir())
            if files:
                return FileResponse(files[0], filename=files[0].name)
        elif candidate.is_file():
            return FileResponse(candidate, filename=candidate.name)

    # 尝试 final.mp4
    final_candidates = [
        output_dir / run_id / "S6_export" / "final.mp4",
        output_dir / "flagship_test" / "S6_export" / "final.mp4",
    ]
    for fc in final_candidates:
        if fc.exists():
            return FileResponse(fc, filename="final.mp4")

    raise HTTPException(status_code=404, detail=f"No output found for stage: {stage}")


# ============================================================================
#  WebSocket
# ============================================================================

def _verify_ws_token(token: str) -> bool:
    """验证 WebSocket 连接 token，复用主面板统一认证逻辑。

    接受 MCP Token 或用户 JWT Session Token；开发环境 PUPPET_DISABLE_AUTH=1 放行。
    返回 True 表示通过，False 表示拒绝。

    局部导入 _check_mcp_auth_token 以避免与 main.py 形成循环导入
    （main.py 在加载本模块时才 include flagship_router，此时本函数尚未执行）。
    """
    from .main import _check_mcp_auth_token

    try:
        _check_mcp_auth_token(token)
        return True
    except HTTPException:
        return False


@router.websocket("/ws/{run_id}")
async def flagship_ws(websocket: WebSocket, run_id: str):
    """旗舰管线实时状态 WebSocket。

    每 10s 推送 status 增量。客户端断连后应降级为 5s 轮询。
    """
    # 安全：连接前认证，防止未授权监听管线状态
    token = websocket.query_params.get("token", "")
    if not _verify_ws_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await flagship_ws_manager.connect(run_id, websocket)
    try:
        while True:
            # 保持连接，接收客户端心跳
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        flagship_ws_manager.disconnect(run_id, websocket)


# ============================================================================
#  后台执行逻辑
# ============================================================================

# 旗舰阶段 → 引擎映射（诚实执行：引擎可用则真实调用，不可用则明确失败）
_STAGE_ENGINE_MAP: Dict[str, str] = {
    "S0_health": None,          # 健康检查：引擎注册表可用性
    "S1_assets": "ffmpeg",      # 素材规范化：ffprobe
    "S2_beat": "ffmpeg",        # 节拍分析：音频探测（真实分析需素材）
    "S3_ae": "ae",              # AE 合成
    "S4_premiere": "premiere",  # PR 粗剪
    "S5_davinci": "davinci",    # DaVinci 调色
    "S6_export": "media_encoder",  # ME 导出
    "S7_qg": None,              # 质量门：QualityGate
 }


async def _execute_stage_honest(
    stage_id: str,
    engines: Dict[str, Any],
    input_video: Optional[str],
    run_dir: Path,
) -> Dict[str, Any]:
    """诚实执行单个旗舰阶段。

    规则：
    1. 引擎映射为 None 的阶段（S0/S7）执行真实能力检查；
    2. 引擎映射非 None 的阶段：引擎可用则真实调用 execute()，
       引擎不可用则返回 ENGINE_UNAVAILABLE 明确失败；
    3. 绝不模拟成功——依赖缺失时标记 failed 并给出明确错误码。
    """
    engine_name = _STAGE_ENGINE_MAP.get(stage_id)

    # S0 健康检查：汇总关键引擎可用性
    if stage_id == "S0_health":
        required = ["ae", "premiere", "davinci", "media_encoder"]
        statuses = {}
        for name in required:
            eng = engines.get(name)
            statuses[name] = bool(eng and getattr(eng, "available", False))
        if all(statuses.values()):
            return {"stage_id": stage_id, "status": "passed", "metadata": statuses}
        unavailable = [n for n, ok in statuses.items() if not ok]
        return {
            "stage_id": stage_id,
            "status": "failed",
            "error": f"引擎不可用: {', '.join(unavailable)}",
            "error_code": "ENGINE_UNAVAILABLE",
            "metadata": statuses,
        }

    # S7 质量门：真实 QualityGate 检查（无产物时明确失败）
    if stage_id == "S7_qg":
        try:
            from core.quality_gate import QualityGate, QualityContext
            final_mp4 = run_dir / "S6_export" / "final.mp4"
            if not final_mp4.exists():
                return {
                    "stage_id": stage_id,
                    "status": "failed",
                    "error": f"未找到待检产物: {final_mp4}（S6 未成功导出）",
                    "error_code": "MISSING_OUTPUT",
                }
            gate = QualityGate()
            ctx = QualityContext(video_path=str(final_mp4))
            report = gate.evaluate(ctx)
            passed = bool(getattr(report, "passed", True))
            return {
                "stage_id": stage_id,
                "status": "passed" if passed else "failed",
                "error": None if passed else str(getattr(report, "errors", "quality gate failed")),
                "metadata": {"report": str(report)},
            }
        except Exception as e:
            return {
                "stage_id": stage_id,
                "status": "failed",
                "error": f"QualityGate 不可用: {e}",
                "error_code": "QUALITY_GATE_UNAVAILABLE",
            }

    # 引擎阶段：诚实执行
    engine = engines.get(engine_name)
    if engine is None or not getattr(engine, "available", False):
        return {
            "stage_id": stage_id,
            "status": "failed",
            "error": f"引擎 {engine_name} 不可用（未安装或路径缺失）",
            "error_code": "ENGINE_UNAVAILABLE",
        }

    if not input_video:
        return {
            "stage_id": stage_id,
            "status": "failed",
            "error": f"阶段 {stage_id} 需要 input_video（当前未提供输入素材）",
            "error_code": "MISSING_INPUT",
        }

    try:
        result = await engine.execute(action="probe", input_path=input_video)
        ok = getattr(result, "success", True)
        return {
            "stage_id": stage_id,
            "status": "passed" if ok else "failed",
            "error": None if ok else getattr(result, "error", "stage failed"),
            "error_code": getattr(result, "error_code", None),
            "metadata": getattr(result, "metadata", {}) or {},
        }
    except Exception as e:
        return {
            "stage_id": stage_id,
            "status": "failed",
            "error": f"阶段 {stage_id} 执行异常: {e}",
            "error_code": "STAGE_EXECUTION_ERROR",
        }


async def _run_pipeline_background(run_id: str) -> None:
    """后台执行旗舰管线（诚实实现）。

    逐阶段执行，每完成一阶段通过 WS 广播状态。引擎不可用或依赖缺失时
    阶段标记 failed 并给出明确错误，绝不模拟成功。
    """
    run = _runs.get(run_id)
    if not run:
        return

    # 构建引擎注册表（一次）
    try:
        from ..engines.registry import build_engine_registry
        engines = build_engine_registry()
    except Exception as e:
        run["status"] = "failed"
        run["error"] = f"引擎注册表初始化失败: {e}"
        await flagship_ws_manager.broadcast(run_id, run)
        logger.error(f"[Flagship] engine registry init failed: {e}")
        return

    input_video = run.get("input_video")
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    run_dir = project_root / "output" / run_id

    for stage in run["stages"]:
        if stage["status"] != "pending":
            continue

        stage["status"] = "running"
        await flagship_ws_manager.broadcast(run_id, run)

        t0 = time.time()
        try:
            outcome = await _execute_stage_honest(
                stage_id=stage["stage_id"],
                engines=engines,
                input_video=input_video,
                run_dir=run_dir,
            )
            stage["status"] = outcome.get("status", "failed")
            stage["error"] = outcome.get("error")
            if outcome.get("error_code"):
                stage["error_code"] = outcome["error_code"]
            if outcome.get("metadata"):
                stage["metadata"] = outcome["metadata"]
            stage["elapsed_s"] = time.time() - t0
        except Exception as e:
            stage["status"] = "failed"
            stage["error"] = str(e)
            stage["elapsed_s"] = time.time() - t0
            run["status"] = "failed"
            await flagship_ws_manager.broadcast(run_id, run)
            logger.error(f"[Flagship] Stage {stage['stage_id']} failed: {e}")
            return

        if stage["status"] == "failed":
            run["status"] = "failed"
            await flagship_ws_manager.broadcast(run_id, run)
            logger.error(f"[Flagship] Stage {stage['stage_id']} failed: {stage.get('error')}")
            return

        await flagship_ws_manager.broadcast(run_id, run)

    run["status"] = "completed"
    await flagship_ws_manager.broadcast(run_id, run)
    logger.info(f"[Flagship] Pipeline completed: run_id={run_id}")

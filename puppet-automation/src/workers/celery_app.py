"""Celery worker for async pipeline task processing.

Architecture
------------
* The Celery worker executes the full pipeline (all phases) as a single task
  rather than one task per phase. This avoids the need for a complex workflow
  engine while still supporting retries, time limits and result backend.

* Job state is persisted in a Redis hash so that:
    - the API can query progress without depending on Celery's result backend
      being fast enough,
    - state survives API/worker restarts.

* A Redis SETNX lock prevents duplicate submissions of the same job_id.

* ``CELERY_ENABLED`` defaults to ``False`` so that the existing 191 unit tests
  (which never have Redis running) keep working. Production deployments set
  ``CELERY_ENABLED=true`` and run ``celery -A src.workers.celery_app worker``.

The FastAPI orchestrator talks to this module through ``celery_backend`` which
falls back to the existing ``asyncio`` implementation when Celery is disabled
or Redis is unreachable.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from celery import Celery
from celery.exceptions import CeleryError
from loguru import logger

from ..config import settings

# ============================================================
# Celery app factory
# ============================================================

celery_app = Celery(
    "puppet_automation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=14400,  # 4 hours hard limit
    task_soft_time_limit=13800,  # 3h50m soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

# Feature flag - read from env at import time so tests can override
CELERY_ENABLED = os.environ.get("CELERY_ENABLED", "false").lower() in ("1", "true", "yes")


# ============================================================
# Redis state store (graceful fallback if Redis is unavailable)
# ============================================================

class _NullRedis:
    """No-op Redis stand-in used when Redis is not reachable.

    The Celery backend falls back to the in-process asyncio implementation in
    this case.  All operations are no-ops; reads return None.
    """

    def set(self, *a, **kw):  # noqa: D401
        return True

    def setnx(self, *a, **kw):
        return True

    def get(self, *a, **kw):
        return None

    def hset(self, *a, **kw):
        return 1

    def hgetall(self, *a, **kw):
        return {}

    def delete(self, *a, **kw):
        return 1

    def scan_iter(self, *a, **kw):
        return iter([])

    def expire(self, *a, **kw):
        return True

    def close(self):
        return None


_redis_client: Any = None


def get_redis():
    """Return a Redis client or a no-op stand-in if Redis is unreachable."""
    global _redis_client
    if not CELERY_ENABLED:
        return _NullRedis()
    if _redis_client is not None:
        return _redis_client
    try:
        import redis  # type: ignore
        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        client.ping()
        _redis_client = client
        logger.info(f"Celery backend connected to Redis at {settings.redis_host}:{settings.redis_port}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Redis unavailable ({exc}); falling back to NullRedis")
        _redis_client = _NullRedis()
    return _redis_client


# ============================================================
# State helpers (Redis hash <-> PipelineState)
# ============================================================

def _state_key(job_id: str) -> str:
    return f"puppet:job:{job_id}:state"


def _lock_key(job_id: str) -> str:
    return f"puppet:job:{job_id}:lock"


def _index_key() -> str:
    return "puppet:jobs:index"


def save_state_to_redis(state_dict: dict[str, Any]) -> None:
    """Persist a serialised PipelineState to Redis.

    The dict is expected to already be JSON-safe (enums converted to strings,
    datetimes to isoformat).  Pydantic's ``model_dump(mode="json")`` produces
    exactly that.
    """
    r = get_redis()
    if isinstance(r, _NullRedis):
        return
    try:
        r.hset(_state_key(state_dict["job_id"]), mapping={
            k: json.dumps(v) if not isinstance(v, str) else v
            for k, v in state_dict.items()
        })
        r.sadd(_index_key(), state_dict["job_id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to persist state for {state_dict.get('job_id')}: {exc}")


def load_state_from_redis(job_id: str) -> dict[str, Any] | None:
    r = get_redis()
    if isinstance(r, _NullRedis):
        return None
    try:
        data = r.hgetall(_state_key(job_id))
        if not data:
            return None
        return data
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to load state for {job_id}: {exc}")
        return None


def list_states_from_redis() -> list[str]:
    r = get_redis()
    if isinstance(r, _NullRedis):
        return []
    try:
        return list(r.smembers(_index_key()))
    except Exception:  # noqa: BLE001
        return []


def delete_state_from_redis(job_id: str) -> None:
    r = get_redis()
    if isinstance(r, _NullRedis):
        return
    try:
        r.delete(_state_key(job_id))
        r.srem(_index_key(), job_id)
    except Exception:  # noqa: BLE001
        pass


# ============================================================
# Distributed lock (SETNX + expiry)
# ============================================================

def acquire_job_lock(job_id: str, ttl_seconds: int = 3600) -> bool:
    """Return True if this caller now owns the job lock.

    The lock auto-expires after ``ttl_seconds`` so a crashed worker cannot
    hold the lock indefinitely.
    """
    r = get_redis()
    if isinstance(r, _NullRedis):
        return True  # no lock contention when no Redis
    try:
        return bool(r.set(_lock_key(job_id), "1", nx=True, ex=ttl_seconds))
    except Exception:  # noqa: BLE001
        return True


def release_job_lock(job_id: str) -> None:
    r = get_redis()
    if isinstance(r, _NullRedis):
        return
    try:
        r.delete(_lock_key(job_id))
    except Exception:  # noqa: BLE001
        pass


# ============================================================
# Celery task: run the full pipeline
# ============================================================

@celery_app.task(
    name="pipeline.run",
    bind=True,
    autoretry_for=(CeleryError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=2,
)
def run_pipeline_task(self, job_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute the full four-stage pipeline for a job.

    The job is supplied as a plain dict (already validated by the API side
    via Pydantic) to keep the Celery payload JSON-only.
    """
    from ..models.pipeline import PipelineJob
    from ..orchestrator import PipelineOrchestrator

    job = PipelineJob.model_validate(job_dict)
    logger.info(f"[Celery] Running pipeline for job {job.job_id}")

    # Acquire lock to prevent two workers from picking up the same job
    if not acquire_job_lock(job.job_id):
        logger.warning(f"[Celery] Job {job.job_id} is locked; another worker is handling it")
        return {"job_id": job.job_id, "status": "skipped", "reason": "locked"}

    try:
        # 真实修复（test_registry 长期红）：worker 侧用 build_engine_registry 构造引擎，
        # 不再空 engines={}（只探测路径不启动应用，开销毫秒级；失败引擎自行诚实降级）
        from ..engines.registry import build_engine_registry

        orchestrator = PipelineOrchestrator(engines=build_engine_registry())
        import asyncio
        state = asyncio.run(orchestrator.run_pipeline(job))
        # Persist final state for API polling
        save_state_to_redis(state.model_dump(mode="json"))
        return {
            "job_id": job.job_id,
            "status": state.overall_status.value,
            "output_path": str(state.phase_results.get(list(state.phase_results.keys())[-1]).output_path)
                if state.phase_results else None,
        }
    finally:
        release_job_lock(job.job_id)


# ============================================================
# Convenience: per-phase tasks (legacy placeholders kept for compatibility)
# ============================================================

@celery_app.task(name="pipeline.run_phase1_preprocess")
def run_phase1_preprocess(video_path: str, options: dict[str, Any] | None = None):
    """Phase 1: Preprocessing pipeline (legacy per-phase task)."""
    logger.info(f"Phase 1 preprocessing: {video_path}")
    return {"status": "pending", "video": video_path}


@celery_app.task(name="pipeline.run_phase2_keying")
def run_phase2_keying(video_path: str, options: dict[str, Any] | None = None):
    """Phase 2: Keying & tracking via Silhouette (legacy per-phase task)."""
    logger.info(f"Phase 2 keying: {video_path}")
    return {"status": "pending", "video": video_path}


@celery_app.task(name="pipeline.run_phase3_stylize")
def run_phase3_stylize(video_path: str, options: dict[str, Any] | None = None):
    """Phase 3: Puppet stylization via AE + Blender (legacy per-phase task)."""
    logger.info(f"Phase 3 stylize: {video_path}")
    return {"status": "pending", "video": video_path}


@celery_app.task(name="pipeline.run_phase4_render")
def run_phase4_render(project_path: str, options: dict[str, Any] | None = None):
    """Phase 4: Final render via aerender + ffmpeg (legacy per-phase task)."""
    logger.info(f"Phase 4 render: {project_path}")
    return {"status": "pending", "project": project_path}


# ============================================================
# Submission helper used by the orchestrator
# ============================================================

def submit_pipeline_job(job_dict: dict[str, Any]) -> str | None:
    """Submit a job to Celery.  Returns the Celery task id, or None if disabled.

    The caller is responsible for persisting the initial PENDING state.
    """
    if not CELERY_ENABLED:
        return None
    try:
        async_result = run_pipeline_task.delay(job_dict)
        return async_result.id
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to submit job to Celery: {exc}")
        return None


def revoke_pipeline_job(task_id: str, terminate: bool = True) -> bool:
    """Revoke a Celery task.  Returns True on success."""
    if not CELERY_ENABLED or not task_id:
        return False
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to revoke task {task_id}: {exc}")
        return False


if __name__ == "__main__":
    celery_app.start()

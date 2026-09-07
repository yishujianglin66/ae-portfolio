"""Celery backend adapter for PipelineOrchestrator.

This module exposes a thin layer that lets the orchestrator transparently
use Celery (when enabled) or fall back to the in-process asyncio implementation
(when disabled / Redis is unreachable).  It owns:

* submission of jobs to Celery,
* per-job ``task_id`` tracking,
* cancellation via Celery revoke,
* state persistence to the Redis hash,
* state hydration back into ``PipelineState`` objects.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from ..models.pipeline import PipelineJob, PipelineState, TaskStatus


def _get_celery_app_module():
    """Return the celery_app *module* object (not the Celery app instance).

    The ``src.workers`` package re-exports the Celery app under the same
    name (``celery_app``), so a plain ``from . import celery_app`` would
    return the Celery instance rather than the module.  We sidestep this by
    loading the module by its fully qualified path.
    """
    return importlib.import_module("src.workers.celery_app")


# Cache the module reference at import time.
_celery_app_module = _get_celery_app_module()


def is_enabled() -> bool:
    """Return True iff Celery backend is enabled and reachable."""
    return _celery_app_module.CELERY_ENABLED


# Historical alias - the orchestrator accesses this via the submodule.
celery_is_enabled = is_enabled


# Indirection layer so tests can patch the underlying helpers without
# reaching into private aliases.
def _load_state(job_id: str):
    return _celery_app_module.load_state_from_redis(job_id)


def _save_state(state_dict: dict[str, Any]) -> None:
    _celery_app_module.save_state_to_redis(state_dict)


def _list_state_ids() -> list[str]:
    return _celery_app_module.list_states_from_redis()


def _delete_state(job_id: str) -> None:
    _celery_app_module.delete_state_from_redis(job_id)


def submit_job(job: PipelineJob) -> Optional[str]:
    """Submit a job to Celery.  Returns the Celery task id, or None if disabled.

    Initial PipelineState is created lazily by the orchestrator so we do not
    duplicate state.
    """
    if not is_enabled():
        return None
    job_dict = job.model_dump(mode="json")
    return _celery_app_module.submit_pipeline_job(job_dict)


def cancel_task(task_id: Optional[str]) -> bool:
    """Cancel a Celery task.  Returns True on success or no-op."""
    if not is_enabled() or not task_id:
        return False
    return _celery_app_module.revoke_pipeline_job(task_id, terminate=True)


def persist_state(state: PipelineState) -> None:
    """Persist a PipelineState to Redis (no-op when Celery is disabled)."""
    if not is_enabled():
        return
    _save_state(state.model_dump(mode="json"))


def hydrate_state(job_id: str) -> Optional[PipelineState]:
    """Load a PipelineState from Redis (or None if absent / disabled)."""
    if not is_enabled():
        return None
    raw = _load_state(job_id)
    if not raw:
        return None
    try:
        # The hash values are stored as JSON strings; decode them.  When the
        # value is already a dict/list (e.g. in unit tests that mock the
        # helper directly), use it as-is.
        decoded: dict[str, Any] = {}
        for k, v in raw.items():
            if isinstance(v, (dict, list, int, float, bool, type(None))):
                decoded[k] = v
            else:
                try:
                    decoded[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    decoded[k] = v
        # Datetime fields may need parsing.
        for dt_field in ("started_at", "completed_at"):
            if decoded.get(dt_field) and isinstance(decoded[dt_field], str):
                try:
                    decoded[dt_field] = datetime.fromisoformat(decoded[dt_field])
                except ValueError:
                    decoded[dt_field] = None
        # phase_results comes back as a string-keyed dict; Pydantic can handle
        # conversion of the enum values during validation.
        return PipelineState.model_validate(decoded)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to hydrate state for {job_id}: {exc}")
        return None


def list_known_job_ids() -> list[str]:
    """Return all job ids known to the Celery backend (best-effort)."""
    if not is_enabled():
        return []
    return _list_state_ids()


def delete_state(job_id: str) -> None:
    """Remove a job's state from Redis (used on cancel / cleanup)."""
    if not is_enabled():
        return
    _delete_state(job_id)

"""Worker process module: Celery app + Redis state store + backend adapter."""
from .celery_app import (
    CELERY_ENABLED,
    acquire_job_lock,
    celery_app,
    delete_state_from_redis,
    get_redis,
    list_states_from_redis,
    load_state_from_redis,
    release_job_lock,
    revoke_pipeline_job,
    run_pipeline_task,
    save_state_to_redis,
    submit_pipeline_job,
)
from .celery_backend import (
    cancel_task,
    delete_state,
    hydrate_state,
    is_enabled,
    list_known_job_ids,
    persist_state,
    submit_job,
)

# Re-export ``is_enabled`` under the historical name expected by the
# orchestrator (``celery_backend.celery_is_enabled``) so call sites do not
# have to know about the backend module's name.
celery_is_enabled = is_enabled

__all__ = [
    "celery_app",
    "CELERY_ENABLED",
    "run_pipeline_task",
    "submit_pipeline_job",
    "revoke_pipeline_job",
    "save_state_to_redis",
    "load_state_from_redis",
    "list_states_from_redis",
    "delete_state_from_redis",
    "acquire_job_lock",
    "release_job_lock",
    "get_redis",
    "is_enabled",
    "celery_is_enabled",
    "submit_job",
    "cancel_task",
    "persist_state",
    "hydrate_state",
    "list_known_job_ids",
    "delete_state",
]

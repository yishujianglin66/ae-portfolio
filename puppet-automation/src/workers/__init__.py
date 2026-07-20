"""Worker process module: Celery app + Redis state store + backend adapter."""
from .celery_app import (
    celery_app,
    CELERY_ENABLED,
    run_pipeline_task,
    submit_pipeline_job,
    revoke_pipeline_job,
    save_state_to_redis,
    load_state_from_redis,
    list_states_from_redis,
    delete_state_from_redis,
    acquire_job_lock,
    release_job_lock,
    get_redis,
)
from .celery_backend import (
    is_enabled,
    submit_job,
    cancel_task,
    persist_state,
    hydrate_state,
    list_known_job_ids,
    delete_state,
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

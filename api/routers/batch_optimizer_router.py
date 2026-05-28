"""Batch image-optimization endpoints (v2.3 M0.12.5).

Endpoints:
- POST /api/fixes/batch-optimize/start
- GET  /api/fixes/batch-optimize/{batch_id}/status
- POST /api/fixes/batch-optimize/{batch_id}/pause
- POST /api/fixes/batch-optimize/{batch_id}/resume
- POST /api/fixes/batch-optimize/{batch_id}/cancel
- GET  /api/fixes/batch-optimize/list

Backed by api/services/batch_optimizer.py (create_batch, start_batch,
pause/resume/cancel, get_batch_status, list_batches). Batch state lives
in an in-memory dict (_BATCH_JOBS) — survives the duration of the
backend process, doesn't persist across restarts. Documented limitation.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.routers.fixes_shared import (
    _CREDS_PATH,
    _validate_wp_domain_for_job,
    get_store,
)
from api.services.auth import require_auth
from api.services.batch_optimizer import (
    cancel_batch,
    create_batch,
    get_batch_status,
    list_batches,
    pause_batch,
    resume_batch,
    start_batch,
)
from api.services.error_responses import _err

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixes", dependencies=[Depends(require_auth)])


class StartBatchRequest(BaseModel):
    job_id: str
    image_urls: list[str] = Field(..., min_length=1, max_length=500)
    target_width: int = Field(default=1200, ge=100, le=4000)
    apply_gps: bool = True
    generate_geo_metadata: bool = True
    parallel_limit: int = Field(default=3, ge=1, le=10)


# ---------------------------------------------------------------------------
# POST /batch-optimize/start
# ---------------------------------------------------------------------------

@router.post("/batch-optimize/start", response_model=None)
async def start_batch_endpoint(
    body: StartBatchRequest,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Create and launch a batch optimization job in the background.

    Returns the batch_id immediately. Frontend then polls /status to follow
    progress.
    """
    job = await store.get_job(body.job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {body.job_id}", 404)

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = await _validate_wp_domain_for_job(store, body.job_id)
    if domain_err is not None:
        return domain_err

    # Load GeoConfig if present — required for GPS injection. Falling back
    # gracefully if the GEO store hasn't been configured yet.
    geo_config: Any = None
    try:
        from api.services.geo_settings_store import load_geo_config
        geo_config = await load_geo_config(store, body.job_id)
    except Exception as exc:
        logger.debug("geo_config_unavailable", extra={"error": str(exc)})

    batch = create_batch(
        job_id=body.job_id,
        image_urls=body.image_urls,
        target_width=body.target_width,
        apply_gps=body.apply_gps,
        generate_geo_metadata=body.generate_geo_metadata,
        parallel_limit=body.parallel_limit,
    )
    started = await start_batch(batch.batch_id, _CREDS_PATH, geo_config, store)
    if started is None:
        return _err("BATCH_START_FAILED", "Failed to start batch job", 500)

    return {
        "batch_id": batch.batch_id,
        "total": len(body.image_urls),
        "status": started.status,
    }


# ---------------------------------------------------------------------------
# GET /batch-optimize/{batch_id}/status
# ---------------------------------------------------------------------------

@router.get("/batch-optimize/{batch_id}/status", response_model=None)
async def batch_status_endpoint(batch_id: str) -> dict | JSONResponse:
    """Poll status for a running batch."""
    status = get_batch_status(batch_id)
    if status is None:
        return _err("BATCH_NOT_FOUND", f"No batch with id {batch_id}", 404)
    return status


# ---------------------------------------------------------------------------
# POST /batch-optimize/{batch_id}/pause
# ---------------------------------------------------------------------------

@router.post("/batch-optimize/{batch_id}/pause", response_model=None)
async def batch_pause_endpoint(batch_id: str) -> dict | JSONResponse:
    """Pause an in-flight batch. Already-running per-image tasks complete; the
    queue stops advancing until resume is called."""
    ok = pause_batch(batch_id)
    if not ok:
        return _err("BATCH_NOT_FOUND", f"No batch with id {batch_id}", 404)
    return {"batch_id": batch_id, "status": "paused"}


# ---------------------------------------------------------------------------
# POST /batch-optimize/{batch_id}/resume
# ---------------------------------------------------------------------------

@router.post("/batch-optimize/{batch_id}/resume", response_model=None)
async def batch_resume_endpoint(batch_id: str) -> dict | JSONResponse:
    """Resume a paused batch."""
    ok = resume_batch(batch_id)
    if not ok:
        return _err("BATCH_NOT_FOUND", f"No batch with id {batch_id}", 404)
    return {"batch_id": batch_id, "status": "running"}


# ---------------------------------------------------------------------------
# POST /batch-optimize/{batch_id}/cancel
# ---------------------------------------------------------------------------

@router.post("/batch-optimize/{batch_id}/cancel", response_model=None)
async def batch_cancel_endpoint(batch_id: str) -> dict | JSONResponse:
    """Cancel a batch. Already-completed images stay applied — the cancel
    stops processing of remaining items."""
    ok = cancel_batch(batch_id)
    if not ok:
        return _err("BATCH_NOT_FOUND", f"No batch with id {batch_id}", 404)
    return {"batch_id": batch_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# GET /batch-optimize/list
# ---------------------------------------------------------------------------

@router.get("/batch-optimize/list", response_model=None)
async def batch_list_endpoint(
    job_id: str | None = Query(None, description="Optional: filter by job_id"),
) -> dict | JSONResponse:
    """List recent batch jobs (filterable by job_id)."""
    batches = list_batches(job_id)
    return {"batches": batches, "count": len(batches)}

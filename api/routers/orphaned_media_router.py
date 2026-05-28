"""Orphaned media endpoint (v2.3 M0.12.4).

Endpoint:
- GET /api/fixes/orphaned-media/{job_id}  WP media not referenced on crawled pages

Small router by design — orphaned media is a single read-only feature. The
service (api/services/wp_fixer.find_orphaned_media) survived the v2.0 split.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from api.routers.fixes_shared import (
    _CREDS_PATH,
    _validate_wp_domain_for_job,
    get_store,
)
from api.services.auth import require_auth
from api.services.error_responses import _err
from api.services.wp_client import WPClient, WPAuthError
from api.services.wp_fixer import find_orphaned_media

logger = logging.getLogger(__name__)

# UUID pattern shared with fix_manager_router so /orphaned-media/predefined-codes
# can't shadow other endpoints (defense in depth — same lesson as M0.12.0).
_UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

router = APIRouter(prefix="/api/fixes", dependencies=[Depends(require_auth)])


@router.get("/orphaned-media/{job_id}", response_model=None)
async def get_orphaned_media_endpoint(
    job_id: str = Path(..., pattern=_UUID_PATTERN),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """List WordPress media items not referenced on any page in the crawl.

    Compares wp_media library against image URLs found on crawled pages.
    Handles WP size variants (e.g. `image-600x403.jpg` vs `image.jpg`) in
    both directions so the same underlying image referenced via a thumbnail
    URL is correctly identified as "in use."
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = await _validate_wp_domain_for_job(store, job_id)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            orphans = await find_orphaned_media(wp, job_id, store)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("orphaned_media_failed", extra={"job_id": job_id})
        return _err("ORPHANED_MEDIA_FAILED", str(exc), 500)

    return {"orphaned": orphans, "count": len(orphans)}

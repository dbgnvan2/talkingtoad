"""Image-related fix endpoints (v2.3 M0.12.3).

Endpoints:
- GET  /api/fixes/image-info                 fetch live WP metadata for one image
- POST /api/fixes/update-image-meta          patch alt/title/caption/description
- POST /api/fixes/refresh-image-from-wp      cache-busted re-fetch from WP
- POST /api/fixes/optimize-image             simple optimize wrapper (existing image)
- POST /api/fixes/optimize-existing-preview  preview Workflow A
- POST /api/fixes/optimize-existing          run Workflow A (existing WP image)
- POST /api/fixes/optimize-upload-preview    preview Workflow B (local file)
- POST /api/fixes/optimize-upload            run Workflow B (upload local file)

All services backing these endpoints exist in api/services/wp_image_fixer.py
(survived the v2.0 split). This router restores the HTTP wiring with auth,
WP domain validation, and SSRF guards (already in the underlying service
via M0.6.7).
"""

from __future__ import annotations

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.routers.fixes_shared import (
    _CREDS_PATH,
    _validate_wp_domain_for_job,
    _validate_wp_domain_for_url,
    get_store,
)
from api.services.auth import require_auth
from api.services.error_responses import _err
from api.services.wp_client import WPClient, WPAuthError
from api.services.wp_image_fixer import (
    get_attachment_info,
    optimize_existing_image,
    optimize_local_image,
    preview_optimization,
    update_image_metadata,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixes", dependencies=[Depends(require_auth)])


# ---------------------------------------------------------------------------
# Body models for the JSON endpoints
# ---------------------------------------------------------------------------


class OptimizeExistingRequest(BaseModel):
    """Body for POST /optimize-existing — Workflow A (optimize an existing WP image)."""
    job_id: str
    image_url: str
    target_width: int = Field(default=1200, ge=100, le=4000)
    apply_gps: bool = True
    seo_keyword: str | None = None
    generate_geo_metadata: bool = False
    page_h1: str = ""
    surrounding_text: str = ""


# ---------------------------------------------------------------------------
# GET /image-info
# ---------------------------------------------------------------------------

@router.get("/image-info", response_model=None)
async def image_info_endpoint(
    image_url: str = Query(..., description="Full URL of the image"),
) -> dict | JSONResponse:
    """Fetch live WordPress metadata for one image (alt, title, caption, etc)."""
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = _validate_wp_domain_for_url(image_url)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            info = await get_attachment_info(wp, image_url)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("image_info_failed", extra={"image_url": image_url})
        return _err("IMAGE_INFO_FAILED", str(exc), 500)

    return info


# ---------------------------------------------------------------------------
# POST /update-image-meta
# ---------------------------------------------------------------------------

@router.post("/update-image-meta", response_model=None)
async def update_image_meta_endpoint(
    image_url: str = Query(..., description="Image URL to update"),
    alt_text: str | None = Query(None),
    title: str | None = Query(None),
    caption: str | None = Query(None),
    description: str | None = Query(None),
) -> dict | JSONResponse:
    """Update alt/title/caption/description on a WP media attachment."""
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = _validate_wp_domain_for_url(image_url)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await update_image_metadata(
                wp,
                image_url,
                alt_text=alt_text,
                title=title,
                caption=caption,
                description=description,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("update_image_meta_failed", extra={"image_url": image_url})
        return _err("UPDATE_META_FAILED", str(exc), 500)

    return result


# ---------------------------------------------------------------------------
# POST /refresh-image-from-wp
# ---------------------------------------------------------------------------

@router.post("/refresh-image-from-wp", response_model=None)
async def refresh_image_from_wp_endpoint(
    image_url: str = Query(...),
    job_id: str = Query(...),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Cache-busted re-fetch of WP metadata for this image.

    Same as /image-info but explicitly tells get_attachment_info to bypass
    any HTTP caches (the WP REST API can be fronted by Cloudflare or WP Rocket
    that holds stale metadata for hours).
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
            info = await get_attachment_info(wp, image_url, cache_bust=True)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("refresh_image_failed", extra={"image_url": image_url})
        return _err("REFRESH_FAILED", str(exc), 500)

    return info


# ---------------------------------------------------------------------------
# POST /optimize-image (simple wrapper)
# ---------------------------------------------------------------------------

@router.post("/optimize-image", response_model=None)
async def optimize_image_endpoint(
    job_id: str = Query(...),
    image_url: str = Query(...),
    target_width: int | None = Query(None, ge=100, le=4000),
    new_filename: str | None = Query(None),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Simple single-image optimization wrapper.

    Delegates to optimize_existing_image with sensible defaults — apply_gps=True,
    no GEO metadata generation, archive in default location. For the full
    Workflow A with all options, frontend uses POST /optimize-existing
    with a JSON body.
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
            result = await optimize_existing_image(
                wp=wp,
                image_url=image_url,
                target_width=target_width or 1200,
                seo_keyword=new_filename,
                apply_gps=True,
                generate_geo_metadata=False,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("optimize_image_failed", extra={"image_url": image_url})
        return _err("OPTIMIZE_FAILED", str(exc), 500)

    return result


# ---------------------------------------------------------------------------
# POST /optimize-existing-preview (Workflow A preview)
# ---------------------------------------------------------------------------

@router.post("/optimize-existing-preview", response_model=None)
async def optimize_existing_preview_endpoint(
    job_id: str = Query(...),
    image_url: str = Query(...),
    target_width: int = Query(1200, ge=100, le=4000),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Preview Workflow A optimization without uploading to WP.

    Returns estimated savings (size, dimensions) so the user can confirm
    before committing.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    domain_err = await _validate_wp_domain_for_job(store, job_id)
    if domain_err is not None:
        return domain_err

    try:
        result = await preview_optimization(
            image_url=image_url,
            target_width=target_width,
        )
    except Exception as exc:
        logger.exception("preview_optimization_failed", extra={"image_url": image_url})
        return _err("PREVIEW_FAILED", str(exc), 500)

    return result


# ---------------------------------------------------------------------------
# POST /optimize-existing (Workflow A, full options)
# ---------------------------------------------------------------------------

@router.post("/optimize-existing", response_model=None)
async def optimize_existing_endpoint(
    body: OptimizeExistingRequest,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Workflow A: optimize an existing WP image and upload as a new file.

    Original stays in WP — user manually replaces references after reviewing
    the new file. Optional GEO metadata generation when geo_keyword + page
    context are provided.
    """
    job = await store.get_job(body.job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {body.job_id}", 404)

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = await _validate_wp_domain_for_job(store, body.job_id)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await optimize_existing_image(
                wp=wp,
                image_url=body.image_url,
                target_width=body.target_width,
                apply_gps=body.apply_gps,
                seo_keyword=body.seo_keyword,
                generate_geo_metadata=body.generate_geo_metadata,
                page_h1=body.page_h1,
                surrounding_text=body.surrounding_text,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("optimize_existing_failed", extra={"image_url": body.image_url})
        return _err("OPTIMIZE_FAILED", str(exc), 500)

    return result


# ---------------------------------------------------------------------------
# POST /optimize-upload-preview (Workflow B preview)
# ---------------------------------------------------------------------------

@router.post("/optimize-upload-preview", response_model=None)
async def optimize_upload_preview_endpoint(
    file: UploadFile = File(...),
    target_width: int = Form(1200),
) -> dict | JSONResponse:
    """Preview Workflow B (local file upload) optimization."""
    if target_width < 100 or target_width > 4000:
        return _err("INVALID_WIDTH", "target_width must be 100-4000", 422)

    try:
        with NamedTemporaryFile(delete=False, suffix=Path(file.filename or "upload").suffix) as tmp:
            tmp_path = Path(tmp.name)
            content = await file.read()
            tmp.write(content)

        result = await preview_optimization(
            local_path=tmp_path,
            target_width=target_width,
        )
    except Exception as exc:
        logger.exception("upload_preview_failed")
        return _err("PREVIEW_FAILED", str(exc), 500)
    finally:
        # Clean up tmp file
        if 'tmp_path' in locals() and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return result


# ---------------------------------------------------------------------------
# POST /optimize-upload (Workflow B, full)
# ---------------------------------------------------------------------------

@router.post("/optimize-upload", response_model=None)
async def optimize_upload_endpoint(
    file: UploadFile = File(...),
    target_width: int = Form(1200),
    apply_gps: bool = Form(True),
    generate_geo_metadata: bool = Form(False),
    seo_keyword: str | None = Form(None),
    job_id: str | None = Form(None),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Workflow B: upload a local image, optimize, push to WP. One file in WP.

    job_id is optional but recommended: when provided, the credentials-domain
    validation runs against the job's domain.
    """
    if target_width < 100 or target_width > 4000:
        return _err("INVALID_WIDTH", "target_width must be 100-4000", 422)

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    if job_id is not None:
        job = await store.get_job(job_id)
        if job is None:
            return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)
        domain_err = await _validate_wp_domain_for_job(store, job_id)
        if domain_err is not None:
            return domain_err

    tmp_path = None
    try:
        with NamedTemporaryFile(delete=False, suffix=Path(file.filename or "upload").suffix) as tmp:
            tmp_path = Path(tmp.name)
            content = await file.read()
            tmp.write(content)

        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await optimize_local_image(
                wp=wp,
                local_path=tmp_path,
                target_width=target_width,
                apply_gps=apply_gps,
                seo_keyword=seo_keyword,
                generate_geo_metadata=generate_geo_metadata,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("upload_optimize_failed")
        return _err("UPLOAD_OPTIMIZE_FAILED", str(exc), 500)
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return result

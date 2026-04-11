"""
WordPress Fix Manager endpoints (v2.0).

POST   /api/fixes/generate/{job_id}   — generate fix proposals from crawl issues
GET    /api/fixes/{job_id}            — list all fixes for a job
PATCH  /api/fixes/{fix_id}            — update proposed_value or status
POST   /api/fixes/apply/{job_id}      — apply all approved fixes (stops on failure)
DELETE /api/fixes/{job_id}            — clear fixes so they can be regenerated
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.models.fix import (
    ApplyFixesResponse,
    Fix,
    FixPatch,
    GenerateFixesResponse,
)
from api.services.auth import require_auth
from api.services.wp_client import WPClient, WPAuthError
from api.services.wp_fixer import (
    apply_fix,
    detect_seo_plugin,
    generate_fixes,
    get_fixable_codes,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixes", dependencies=[Depends(require_auth)])

_CREDS_PATH = Path("wp-credentials.json")


# ── Dependency injection ───────────────────────────────────────────────────

def get_store():
    from api.main import _store
    return _store


def _err(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message, "http_status": http_status}},
    )


# ── Helper: row dict → Fix model ───────────────────────────────────────────

def _row_to_fix(row: dict) -> Fix:
    return Fix(
        id=row["id"],
        job_id=row["job_id"],
        issue_code=row["issue_code"],
        page_url=row["page_url"],
        wp_post_id=row.get("wp_post_id"),
        wp_post_type=row.get("wp_post_type"),
        field=row["field"],
        label=row["label"],
        current_value=row.get("current_value"),
        proposed_value=row.get("proposed_value", ""),
        status=row.get("status", "pending"),
        error=row.get("error"),
        applied_at=row.get("applied_at"),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/generate/{job_id}", response_model=GenerateFixesResponse)
async def generate_fixes_endpoint(
    job_id: str,
    store=Depends(get_store),
) -> GenerateFixesResponse | JSONResponse:
    """Connect to WordPress, detect SEO plugin, and generate fix proposals
    for all fixable issues found in the crawl."""

    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    if not _CREDS_PATH.exists():
        return _err(
            "NO_CREDENTIALS",
            "wp-credentials.json not found. Create it with site_url, login_url, username, password.",
            400,
        )

    # Clear any existing fixes so generation is idempotent
    await store.delete_fixes(job_id)

    # Fetch all fixable issues for this job
    all_issues = await store.get_all_issues(job_id)
    fixable_codes = get_fixable_codes()
    fixable_issues = [
        {"code": i.issue_code, "page_url": i.page_url}
        for i in all_issues
        if i.issue_code in fixable_codes and i.page_url
    ]

    if not fixable_issues:
        return GenerateFixesResponse(
            fixes=[],
            seo_plugin=None,
            skipped_urls=[],
            message="No fixable issues found in this crawl.",
        )

    # Build a lookup of crawled page data — used as fallback when WP returns
    # no stored value (e.g. Yoast uses a template rather than an explicit field)
    pages = await store.get_pages(job_id)
    crawled: dict[str, object] = {p.url: p for p in pages}

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)
            logger.info(
                "wp_plugin_detected",
                extra={"job_id": job_id, "plugin": seo_plugin},
            )

            fix_dicts, skipped = await generate_fixes(
                wp, job_id, fixable_issues, seo_plugin
            )

    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("generate_fixes_error", extra={"job_id": job_id})
        return _err("WP_ERROR", str(exc), 500)

    # Fill missing current_value from crawl data.
    # Yoast/Rank Math don't store an explicit value when using their default
    # template — the rendered title we saw during crawl is the real current value.
    _crawl_fallback = {"seo_title": "title", "meta_description": "meta_description"}
    for fix in fix_dicts:
        if fix.get("current_value") is None:
            attr = _crawl_fallback.get(fix["field"])
            if attr and fix["page_url"] in crawled:
                crawled_val = getattr(crawled[fix["page_url"]], attr, None)
                if crawled_val:
                    fix["current_value"] = crawled_val
                    # Re-run auto-propose now that we have a real current value
                    from api.services.wp_fixer import _auto_propose
                    fix["proposed_value"] = _auto_propose(fix["issue_code"], crawled_val)

    await store.save_fixes(fix_dicts)

    fixes = [_row_to_fix(f) for f in fix_dicts]
    return GenerateFixesResponse(
        fixes=fixes,
        seo_plugin=seo_plugin,
        skipped_urls=skipped,
        message=(
            f"Found {len(fixes)} fix{'es' if len(fixes) != 1 else ''} "
            f"using {seo_plugin or 'no SEO plugin'}."
            + (f" Could not resolve {len(skipped)} URL(s)." if skipped else "")
        ),
    )


@router.get("/{job_id}", response_model=list[Fix])
async def list_fixes(
    job_id: str,
    store=Depends(get_store),
) -> list[Fix] | JSONResponse:
    """Return all fix proposals for a crawl job."""
    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    rows = await store.get_fixes(job_id)
    return [_row_to_fix(r) for r in rows]


@router.patch("/{fix_id}", response_model=Fix)
async def update_fix_endpoint(
    fix_id: str,
    body: FixPatch,
    store=Depends(get_store),
) -> Fix | JSONResponse:
    """Update the proposed value or status of a fix."""
    # Find the fix via job store
    all_rows = await store.get_fixes_by_id(fix_id)
    if not all_rows:
        return _err("FIX_NOT_FOUND", f"No fix with id {fix_id}", 404)

    updates: dict = {}
    if body.proposed_value is not None:
        updates["proposed_value"] = body.proposed_value
    if body.status is not None:
        valid_statuses = {"pending", "approved", "skipped"}
        if body.status not in valid_statuses:
            return _err("INVALID_STATUS", f"Status must be one of: {', '.join(valid_statuses)}", 400)
        updates["status"] = body.status
        if body.status == "pending":
            updates["error"] = None  # clear error when re-queuing

    if updates:
        await store.update_fix(fix_id, **updates)

    updated_rows = await store.get_fixes_by_id(fix_id)
    return _row_to_fix(updated_rows[0])


@router.post("/apply/{job_id}", response_model=ApplyFixesResponse)
async def apply_fixes_endpoint(
    job_id: str,
    store=Depends(get_store),
) -> ApplyFixesResponse | JSONResponse:
    """Apply all approved fixes for a job.

    Applies fixes one at a time. Stops on the first failure — successfully
    applied fixes remain applied. The failed fix can be retried by re-approving it.
    """
    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    rows = await store.get_fixes(job_id)
    approved = [r for r in rows if r["status"] == "approved"]

    if not approved:
        return ApplyFixesResponse(
            applied=0, failed=0, skipped=0, results=[],
            stopped_at=None,
        )

    results: list[dict] = []
    applied_count = 0
    failed_count = 0
    stopped_at: str | None = None

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)

            for fix in approved:
                fix_id = fix["id"]
                success, error_msg = await apply_fix(wp, fix, seo_plugin)

                if success:
                    now = datetime.now(timezone.utc).isoformat()
                    await store.update_fix(
                        fix_id, status="applied", applied_at=now, error=None
                    )
                    applied_count += 1
                    results.append({"fix_id": fix_id, "status": "applied", "page_url": fix["page_url"], "field": fix["field"]})
                    logger.info(
                        "fix_applied",
                        extra={"fix_id": fix_id, "field": fix["field"], "page_url": fix["page_url"]},
                    )
                else:
                    await store.update_fix(fix_id, status="failed", error=error_msg)
                    failed_count += 1
                    stopped_at = fix_id
                    results.append({"fix_id": fix_id, "status": "failed", "page_url": fix["page_url"], "field": fix["field"], "error": error_msg})
                    logger.warning(
                        "fix_failed",
                        extra={"fix_id": fix_id, "error": error_msg},
                    )
                    break  # stop on first failure

    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("apply_fixes_error", extra={"job_id": job_id})
        return _err("WP_ERROR", str(exc), 500)

    skipped_count = len(approved) - applied_count - failed_count

    return ApplyFixesResponse(
        applied=applied_count,
        failed=failed_count,
        skipped=skipped_count,
        stopped_at=stopped_at,
        results=results,
    )


@router.delete("/{job_id}")
async def delete_fixes(
    job_id: str,
    store=Depends(get_store),
) -> JSONResponse:
    """Clear all fixes for a job so they can be regenerated."""
    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    await store.delete_fixes(job_id)
    return JSONResponse({"message": "Fixes cleared."})

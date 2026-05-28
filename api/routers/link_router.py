"""Link and inline-fix endpoints (v2.3 M0.12.6).

Endpoints:
- GET  /api/fixes/link-sources              pages that link to a target URL
- POST /api/fixes/replace-link              swap old_url -> new_url in a WP post
- POST /api/fixes/verify-broken-links       re-check broken links for a job
- POST /api/fixes/mark-broken-link-fixed    mark a broken-link issue resolved
- POST /api/fixes/mark-anchor-fixed         mark one anchor href fixed
- POST /api/fixes/mark-issue-fixed          mark issues by code+URL fixed
- POST /api/fixes/apply-one                 generic single-fix dispatcher
- GET  /api/fixes/wp-value                  current value of a WP field

Two services were already present (apply_fix and replace_link_in_post
and get_current_value in wp_fixer.py); the rest are thin store wrappers
or HTTP re-check loops that didn't have dedicated service helpers.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.crawler.fetcher import fetch_page, is_ssrf_safe, make_client
from api.routers.fixes_shared import (
    _CREDS_PATH,
    _validate_wp_domain_for_job,
    _validate_wp_domain_for_url,
    get_store,
)
from api.services.auth import require_auth
from api.services.error_responses import _err
from api.services.wp_client import WPClient, WPAuthError
from api.services.wp_fixer import (
    apply_fix,
    detect_seo_plugin,
    find_post_by_url,
    get_current_value,
    replace_link_in_post,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixes", dependencies=[Depends(require_auth)])


# ---------------------------------------------------------------------------
# Body models
# ---------------------------------------------------------------------------


class ReplaceLinkRequest(BaseModel):
    job_id: str
    source_url: str
    old_url: str
    new_url: str


class MarkBrokenLinkFixedRequest(BaseModel):
    job_id: str
    target_url: str


class MarkAnchorFixedRequest(BaseModel):
    job_id: str
    page_url: str
    anchor_href: str


class MarkIssueFixedRequest(BaseModel):
    job_id: str
    page_url: str
    issue_codes: list[str] = Field(..., min_length=1)


class ApplyOneRequest(BaseModel):
    """Generic single-fix dispatcher used by FixInlinePanel."""
    job_id: str
    page_url: str
    issue_code: str
    proposed_value: str | None = None


# ---------------------------------------------------------------------------
# GET /link-sources  (pure read — no WP)
# ---------------------------------------------------------------------------

@router.get("/link-sources", response_model=None)
async def link_sources_endpoint(
    job_id: str = Query(..., description="Job ID to search within"),
    target_url: str = Query(..., min_length=1, description="The target URL to find links to"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Return every page (and link text) that links to *target_url*.

    Used by the broken-link fix UI to show "this URL is referenced from N
    pages" before the user replaces it.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    links = await store.get_links_by_target(job_id, target_url)
    return {"target_url": target_url, "sources": links, "count": len(links)}


# ---------------------------------------------------------------------------
# POST /replace-link
# ---------------------------------------------------------------------------

@router.post("/replace-link", response_model=None)
async def replace_link_endpoint(
    body: ReplaceLinkRequest,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Replace *old_url* with *new_url* in the WP post at *source_url*."""
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
            ok, err = await replace_link_in_post(
                wp, body.source_url, body.old_url, body.new_url,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("replace_link_failed", extra={"source_url": body.source_url})
        return _err("REPLACE_LINK_FAILED", str(exc), 500)

    return {"success": ok, "error": err}


# ---------------------------------------------------------------------------
# POST /verify-broken-links/{job_id}
# ---------------------------------------------------------------------------

@router.post("/verify-broken-links/{job_id}", response_model=None)
async def verify_broken_links_endpoint(
    job_id: str,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Re-check all broken-link targets for a job; remove issues for URLs
    that now return 200.

    Useful for the workflow "I fixed a broken link manually in WP — now tell
    me which broken-link issues to clear."
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    # Collect every distinct broken-link target across the job's issues.
    # Use the existing get_links_by_target inverted: pull all issues
    # categorized as broken_link, gather their page_urls/extras.
    issues, _total = await store.get_issues(job_id, category="broken_link", page=1, limit=10000)
    targets: set[str] = set()
    for issue in issues:
        # issue.extra commonly has the broken target URL
        extra = issue.extra or {}
        for key in ("target", "target_url", "url", "href"):
            v = extra.get(key)
            if v and isinstance(v, str):
                targets.add(v)
                break

    if not targets:
        return {"checked": 0, "still_broken": 0, "now_ok": 0, "cleared": []}

    # HEAD each target via fetch_page (which has SSRF guard + redirect chain
    # checking). Anything that returns 200-399 is considered "now OK".
    cleared: list[str] = []
    still_broken: list[str] = []
    async with make_client() as client:
        for target in targets:
            # Skip private addresses up-front so we don't even try.
            if not is_ssrf_safe(target):
                still_broken.append(target)
                continue
            try:
                result = await fetch_page(target, client, is_head=True)
                if 200 <= result.status_code < 400:
                    cleared.append(target)
                else:
                    still_broken.append(target)
            except Exception:
                still_broken.append(target)

    # For each cleared target, find its issues and delete them.
    deleted_count = 0
    for target in cleared:
        for issue in issues:
            extra = issue.extra or {}
            issue_target = extra.get("target") or extra.get("target_url") or extra.get("url")
            if issue_target == target:
                deleted = await store.delete_issues_by_code_and_url(
                    job_id, issue.issue_code, issue.page_url,
                )
                deleted_count += deleted

    return {
        "checked": len(targets),
        "still_broken": len(still_broken),
        "now_ok": len(cleared),
        "cleared": cleared,
        "issues_deleted": deleted_count,
    }


# ---------------------------------------------------------------------------
# POST /mark-broken-link-fixed
# ---------------------------------------------------------------------------

@router.post("/mark-broken-link-fixed", response_model=None)
async def mark_broken_link_fixed_endpoint(
    body: MarkBrokenLinkFixedRequest,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Mark all broken-link issues for a specific target URL as fixed."""
    job = await store.get_job(body.job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {body.job_id}", 404)

    # Find every issue whose extra references this target_url.
    issues, _total = await store.get_issues(
        body.job_id, category="broken_link", page=1, limit=10000,
    )
    deleted = 0
    for issue in issues:
        extra = issue.extra or {}
        if (
            extra.get("target") == body.target_url
            or extra.get("target_url") == body.target_url
            or extra.get("url") == body.target_url
        ):
            deleted += await store.delete_issues_by_code_and_url(
                body.job_id, issue.issue_code, issue.page_url,
            )

    return {"success": True, "deleted": deleted}


# ---------------------------------------------------------------------------
# POST /mark-anchor-fixed
# ---------------------------------------------------------------------------

@router.post("/mark-anchor-fixed", response_model=None)
async def mark_anchor_fixed_endpoint(
    body: MarkAnchorFixedRequest,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Mark one specific anchor href as fixed within a LINK_EMPTY_ANCHOR issue.

    Removes the href from the issue's extra.empty_anchor_hrefs list. If that
    leaves the list empty, the entire issue is deleted; otherwise the issue
    persists with the smaller list.
    """
    job = await store.get_job(body.job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {body.job_id}", 404)

    # Find the LINK_EMPTY_ANCHOR issue on this page.
    issues, _total = await store.get_issues(
        body.job_id, page=1, limit=10000,
    )
    target_issue = None
    for issue in issues:
        if (
            issue.issue_code == "LINK_EMPTY_ANCHOR"
            and (issue.page_url == body.page_url
                 or (issue.page_url or "").rstrip("/") == body.page_url.rstrip("/"))
        ):
            target_issue = issue
            break

    if target_issue is None:
        return _err(
            "ISSUE_NOT_FOUND",
            f"No LINK_EMPTY_ANCHOR issue on {body.page_url}",
            404,
        )

    extra = dict(target_issue.extra or {})
    hrefs = list(extra.get("empty_anchor_hrefs") or [])
    if body.anchor_href in hrefs:
        hrefs.remove(body.anchor_href)

    if not hrefs:
        # Whole issue resolved.
        await store.delete_issues_by_code_and_url(
            body.job_id, "LINK_EMPTY_ANCHOR", target_issue.page_url,
        )
        return {"success": True, "issue_deleted": True, "remaining": 0}

    # Update with the smaller href list.
    extra["empty_anchor_hrefs"] = hrefs
    await store.update_issue_extra(
        body.job_id, "LINK_EMPTY_ANCHOR", target_issue.page_url, extra,
    )
    return {"success": True, "issue_deleted": False, "remaining": len(hrefs)}


# ---------------------------------------------------------------------------
# POST /mark-issue-fixed
# ---------------------------------------------------------------------------

@router.post("/mark-issue-fixed", response_model=None)
async def mark_issue_fixed_endpoint(
    body: MarkIssueFixedRequest,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Mark issues with the given codes on the given page as fixed (deletes them)."""
    job = await store.get_job(body.job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {body.job_id}", 404)

    deleted = 0
    for code in body.issue_codes:
        deleted += await store.delete_issues_by_code_and_url(
            body.job_id, code, body.page_url,
        )

    return {"success": True, "deleted": deleted}


# ---------------------------------------------------------------------------
# POST /apply-one (generic single-fix dispatcher)
# ---------------------------------------------------------------------------

@router.post("/apply-one", response_model=None)
async def apply_one_endpoint(
    body: ApplyOneRequest,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Apply a single fix to a WP page. Generic dispatcher used by
    FixInlinePanel — the issue_code determines which field gets patched.
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
            seo_plugin = await detect_seo_plugin(wp)
            # apply_fix expects a "fix record" dict with the page URL, issue
            # code, proposed value, etc.
            fix_record = {
                "page_url": body.page_url,
                "issue_code": body.issue_code,
                "proposed_value": body.proposed_value or "",
            }
            ok, err = await apply_fix(wp, fix_record, seo_plugin)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("apply_one_failed", extra={"page_url": body.page_url})
        return _err("APPLY_ONE_FAILED", str(exc), 500)

    return {"success": ok, "error": err}


# ---------------------------------------------------------------------------
# GET /wp-value (current value lookup for FixInlinePanel)
# ---------------------------------------------------------------------------

@router.get("/wp-value", response_model=None)
async def wp_value_endpoint(
    page_url: str = Query(..., description="WP page URL"),
    field: str = Query(..., description="Field key (title, meta_description, etc.)"),
) -> dict | JSONResponse:
    """Fetch the current value of a WP post field via the WP REST API.

    Used by FixInlinePanel to show "current value: ..." next to the proposed fix.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = _validate_wp_domain_for_url(page_url)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            post_info = await find_post_by_url(wp, page_url)
            if not post_info:
                return _err(
                    "POST_NOT_FOUND",
                    f"No WordPress post found for {page_url}",
                    404,
                )
            seo_plugin = await detect_seo_plugin(wp)
            value = await get_current_value(wp, post_info, field, seo_plugin)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("wp_value_failed", extra={"page_url": page_url, "field": field})
        return _err("WP_VALUE_FAILED", str(exc), 500)

    return {"page_url": page_url, "field": field, "value": value}

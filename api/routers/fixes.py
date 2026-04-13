"""
WordPress Fix Manager endpoints (v2.0).

POST   /api/fixes/generate/{job_id}   — generate fix proposals from crawl issues
GET    /api/fixes/wp-value            — fetch live WP value for one page+field (inline fix)
POST   /api/fixes/apply-one           — apply a single fix immediately (inline fix)
GET    /api/fixes/{job_id}            — list all fixes for a job
PATCH  /api/fixes/{fix_id}            — update proposed_value or status
POST   /api/fixes/apply/{job_id}      — apply all approved fixes (stops on failure)
DELETE /api/fixes/{job_id}            — clear fixes so they can be regenerated
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.models.fix import (
    ApplyFixesResponse,
    ApplyOneRequest,
    ApplyOneResponse,
    Fix,
    FixPatch,
    GenerateFixesResponse,
    LinkSource,
    ReplaceLinkRequest,
    ReplaceLinkResponse,
    WpValueResponse,
)
from api.services.auth import require_auth
from api.services.wp_client import WPClient, WPAuthError
from api.services.wp_fixer import (
    apply_fix,
    bulk_trim_titles,
    change_heading_level,
    convert_heading_to_bold,
    detect_seo_plugin,
    find_post_by_url,
    generate_fixes,
    get_attachment_info,
    get_current_value,
    get_fixable_codes,
    replace_link_in_post,
    trim_title_one,
    update_image_metadata,
    PREDEFINED_FIX_VALUES,
    _FIELD_SPECS,
    _CODE_TO_FIELD,
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
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    store=Depends(get_store),
) -> GenerateFixesResponse | JSONResponse:
    """Connect to WordPress and generate fix proposals for fixable issues.

    Processes fixes in batches (default 20 at a time). Call with offset=0
    to start fresh; call with offset=N to load the next batch without
    clearing already-generated fixes.
    """

    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    if not _CREDS_PATH.exists():
        return _err(
            "NO_CREDENTIALS",
            "wp-credentials.json not found. Create it with site_url, login_url, username, password.",
            400,
        )

    # On first batch, clear any stale fixes so regeneration is idempotent
    if offset == 0:
        await store.delete_fixes(job_id)

    # Collect all fixable (page_url, field) pairs, deduped
    all_issues = await store.get_all_issues(job_id)
    fixable_codes = get_fixable_codes()

    seen: set[tuple[str, str]] = set()
    all_fixable: list[dict] = []
    for i in all_issues:
        if i.issue_code not in fixable_codes or not i.page_url:
            continue
        from api.services.wp_fixer import _CODE_TO_FIELD
        field = _CODE_TO_FIELD.get(i.issue_code)
        if not field:
            continue
        key = (i.page_url, field)
        if key in seen:
            continue
        seen.add(key)
        all_fixable.append({"code": i.issue_code, "page_url": i.page_url})

    total_fixable = len(all_fixable)

    if total_fixable == 0:
        return GenerateFixesResponse(
            fixes=[],
            seo_plugin=None,
            skipped_urls=[],
            message="No fixable issues found in this crawl.",
            total_fixable=0,
            offset=0,
            has_more=False,
        )

    batch = all_fixable[offset: offset + limit]
    has_more = (offset + limit) < total_fixable

    # Crawled page data — fallback when WP returns no stored value
    # (Yoast uses a template rather than an explicit field for many pages)
    pages = await store.get_pages(job_id)
    crawled = {p.url: p for p in pages}

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)
            logger.info(
                "wp_plugin_detected",
                extra={"job_id": job_id, "plugin": seo_plugin, "batch_offset": offset},
            )

            fix_dicts, skipped = await generate_fixes(wp, job_id, batch, seo_plugin)

    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("generate_fixes_error", extra={"job_id": job_id})
        return _err("WP_ERROR", str(exc), 500)

    # Fill missing current_value from crawl data
    _crawl_fallback = {"seo_title": "title", "meta_description": "meta_description"}
    from api.services.wp_fixer import _auto_propose
    for fix in fix_dicts:
        if fix.get("current_value") is None:
            attr = _crawl_fallback.get(fix["field"])
            if attr and fix["page_url"] in crawled:
                crawled_val = getattr(crawled[fix["page_url"]], attr, None)
                if crawled_val:
                    fix["current_value"] = crawled_val
                    fix["proposed_value"] = _auto_propose(fix["issue_code"], crawled_val)

    await store.save_fixes(fix_dicts)

    fixes = [_row_to_fix(f) for f in fix_dicts]
    remaining = total_fixable - offset - len(fixes)
    return GenerateFixesResponse(
        fixes=fixes,
        seo_plugin=seo_plugin,
        skipped_urls=skipped,
        message=(
            f"Loaded {offset + len(fixes)} of {total_fixable} fixable issues."
            + (f" {remaining} more available." if has_more else " All issues loaded.")
            + (f" Could not resolve {len(skipped)} URL(s)." if skipped else "")
        ),
        total_fixable=total_fixable,
        offset=offset,
        has_more=has_more,
    )


@router.get("/wp-value", response_model=WpValueResponse)
async def get_wp_value(
    job_id: str = Query(...),
    page_url: str = Query(...),
    field: str = Query(...),
    store=Depends(get_store),
) -> WpValueResponse | JSONResponse:
    """Fetch the current WordPress value for a single page + field.

    Used by the inline Fix panel — called on demand when the user clicks Fix
    on an issue row. Returns the live value from WordPress REST API.
    """
    if field not in _FIELD_SPECS:
        return _err("INVALID_FIELD", f"Unknown field: {field}", 400)

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)
            post_info = await find_post_by_url(wp, page_url)
            if not post_info:
                return _err(
                    "POST_NOT_FOUND",
                    f"Could not resolve a WordPress post for: {page_url}",
                    404,
                )
            current = await get_current_value(wp, post_info, field, seo_plugin)

            # Crawl fallback when Yoast uses template and stores nothing
            if not current:
                pages = await store.get_pages(job_id)
                crawled = {p.url: p for p in pages}
                _crawl_fallback = {"seo_title": "title", "meta_description": "meta_description"}
                attr = _crawl_fallback.get(field)
                if attr and page_url in crawled:
                    crawled_val = getattr(crawled[page_url], attr, None)
                    if crawled_val:
                        current = crawled_val

    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("get_wp_value_error", extra={"page_url": page_url, "field": field})
        return _err("WP_ERROR", str(exc), 500)

    return WpValueResponse(
        page_url=page_url,
        field=field,
        current_value=current,
        wp_post_id=post_info["id"],
        wp_post_type=post_info["type"],
        seo_plugin=seo_plugin,
    )


@router.post("/apply-one", response_model=ApplyOneResponse)
async def apply_one_fix(
    body: ApplyOneRequest,
) -> ApplyOneResponse | JSONResponse:
    """Apply a single fix to WordPress immediately — no stored record required.

    Called by the inline Fix panel. Resolves the WP post, applies the value,
    and returns success/failure. The user sees the result inline; no fix record
    is created in the database.
    """
    if body.field not in _FIELD_SPECS:
        return _err("INVALID_FIELD", f"Unknown field: {body.field}", 400)

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)
            post_info = await find_post_by_url(wp, body.page_url)
            if not post_info:
                return _err(
                    "POST_NOT_FOUND",
                    f"Could not resolve a WordPress post for: {body.page_url}",
                    404,
                )

            fix_dict = {
                "field": body.field,
                "proposed_value": body.proposed_value,
                "wp_post_id": post_info["id"],
                "wp_post_type": post_info["type"],
                "page_url": body.page_url,
            }
            success, error_msg = await apply_fix(wp, fix_dict, seo_plugin)

    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("apply_one_fix_error", extra={"page_url": body.page_url, "field": body.field})
        return _err("WP_ERROR", str(exc), 500)

    if success:
        logger.info(
            "inline_fix_applied",
            extra={"page_url": body.page_url, "field": body.field},
        )
        return ApplyOneResponse(success=True)
    return ApplyOneResponse(success=False, error=error_msg)


@router.get("/link-sources", response_model=list[LinkSource])
async def get_link_sources(
    job_id: str = Query(...),
    target_url: str = Query(...),
    store=Depends(get_store),
) -> list[LinkSource] | JSONResponse:
    """Return the source pages that contain a link to *target_url*.

    Used by the broken-link Fix panel to show where the broken link lives
    before the user chooses a replacement URL.
    """
    rows = await store.get_links_by_target(job_id, target_url)
    return [LinkSource(source_url=r["source_url"], link_text=r.get("link_text")) for r in rows]


@router.post("/replace-link", response_model=ReplaceLinkResponse)
async def replace_link_endpoint(
    body: ReplaceLinkRequest,
) -> ReplaceLinkResponse | JSONResponse:
    """Replace a broken link URL in WordPress post content.

    Fetches the raw content of the post at *source_url*, replaces every
    occurrence of *old_url* with *new_url*, and saves it back via PATCH.
    Works for Gutenberg and classic-editor posts.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    if not body.new_url.strip():
        return _err("EMPTY_URL", "Replacement URL cannot be empty.", 400)

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            success, error_msg = await replace_link_in_post(
                wp, body.source_url, body.old_url, body.new_url
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("replace_link_error", extra={"source_url": body.source_url})
        return _err("WP_ERROR", str(exc), 500)

    if success:
        logger.info(
            "link_replaced",
            extra={"source_url": body.source_url, "old_url": body.old_url},
        )
        return ReplaceLinkResponse(success=True)
    return ReplaceLinkResponse(success=False, error=error_msg)


@router.get("/predefined-codes", response_model=None)
async def get_predefined_codes() -> dict:
    """Return issue codes whose fix is a predetermined value (no user input needed)."""
    return {
        code: PREDEFINED_FIX_VALUES[_CODE_TO_FIELD[code]]
        for code in _CODE_TO_FIELD
        if _CODE_TO_FIELD[code] in PREDEFINED_FIX_VALUES
    }


@router.post("/bulk-trim-titles", response_model=None)
async def bulk_trim_titles_endpoint(
    job_id: str = Query(..., description="Crawl job to pull TITLE_TOO_LONG pages from"),
    store=Depends(get_store),
) -> list[dict] | JSONResponse:
    """Remove the site-name suffix from every too-long SEO title.

    For each page with TITLE_TOO_LONG:
    - If the per-page Yoast/Rank Math title is empty (global template active),
      writes %%title%% (or %title% for Rank Math) — the plugin's post-title
      variable — so it renders just the page title without the suffix.
    - If a custom per-page title is already set, strips the site-name suffix
      from that string.
    - Falls back to stripping from the rendered title when the meta cannot be read.

    Returns a list of per-URL result dicts including a 'method' key indicating
    which strategy was used: 'variable', 'strip_custom', or 'strip_rendered'.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    # Collect all distinct page URLs with TITLE_TOO_LONG issues for this job
    issues, _ = await store.get_issues(
        job_id, category="metadata", page=1, limit=5000
    )
    flagged_urls = {
        i.page_url for i in issues
        if i.issue_code == "TITLE_TOO_LONG" and i.page_url
    }
    if not flagged_urls:
        return _err("NO_ISSUES", "No TITLE_TOO_LONG issues found for this job.", 404)

    # Fetch crawled title for each flagged URL
    all_pages = await store.get_pages(job_id)
    pages_to_fix = [
        {"page_url": p.url, "title": p.title}
        for p in all_pages
        if p.url in flagged_urls and p.title
    ]
    if not pages_to_fix:
        return _err("NO_PAGES", "Could not find crawled title data for flagged pages.", 404)

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)
            results = await bulk_trim_titles(wp, pages_to_fix, seo_plugin)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("bulk_trim_titles_error", extra={"job_id": job_id})
        return _err("WP_ERROR", str(exc), 500)

    logger.info(
        "bulk_trim_titles_complete",
        extra={
            "job_id": job_id,
            "total": len(results),
            "succeeded": sum(1 for r in results if r["success"]),
        },
    )
    return results


@router.post("/trim-title-one", response_model=None)
async def trim_title_one_endpoint(
    page_url: str = Query(..., description="URL of the page whose title should be trimmed"),
) -> dict | JSONResponse:
    """Strip the site-name suffix from the SEO title of a single page.

    Uses the same strategy as bulk-trim-titles: writes %%title%% (Yoast) or
    %title% (Rank Math) when no per-page override is set, or strips the suffix
    from a custom title if one exists.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)
            result = await trim_title_one(wp, page_url, seo_plugin)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("trim_title_one_error", extra={"page_url": page_url})
        return _err("WP_ERROR", str(exc), 500)

    return result


@router.post("/heading-to-bold", response_model=None)
async def heading_to_bold_endpoint(
    page_url: str = Query(..., description="URL of the page to edit"),
    heading_text: str | None = Query(None, description="Exact text of the H4 to convert; omit to convert all H4s"),
) -> dict | JSONResponse:
    """Convert H4 headings to bold paragraphs in WordPress post content.

    Handles both Gutenberg block syntax and classic editor HTML.
    If heading_text is provided, only that specific H4 is converted.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await convert_heading_to_bold(wp, page_url, heading_text)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("heading_to_bold_error", extra={"page_url": page_url})
        return _err("WP_ERROR", str(exc), 500)

    return result


@router.get("/find-heading", response_model=None)
async def find_heading_endpoint(
    job_id:       str = Query(..., description="Crawl job to search"),
    heading_text: str = Query(..., description="Exact heading text to find"),
    level:        int | None = Query(None, description="Limit to a specific heading level (1–6)"),
    store=Depends(get_store),
) -> list[dict] | JSONResponse:
    """Find all crawled pages that contain a specific heading text.

    Returns a list of {url, level, context} dicts — one per matching heading.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    pages = await store.get_pages(job_id)
    matches = []
    needle = heading_text.strip().lower()
    for page in pages:
        for h in (page.headings_outline or []):
            if h.get("text", "").strip().lower() == needle:
                if level is not None and h.get("level") != level:
                    continue
                matches.append({
                    "url":   page.url,
                    "level": h["level"],
                    "text":  h["text"],
                })
    return matches


@router.post("/bulk-replace-heading", response_model=None)
async def bulk_replace_heading_endpoint(
    job_id:       str = Query(..., description="Crawl job"),
    heading_text: str = Query(..., description="Exact heading text to replace"),
    from_level:   int = Query(..., description="Current heading level (1–6)"),
    to_level:     int | None = Query(None, description="Target heading level; omit to convert to bold"),
    store=Depends(get_store),
) -> list[dict] | JSONResponse:
    """Change or bold a specific heading across every page in the crawl job.

    Finds all crawled pages containing *heading_text* at *from_level* and applies
    the change via the WordPress REST API.  Returns per-URL results.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    # Find all pages with this heading
    pages = await store.get_pages(job_id)
    needle = heading_text.strip().lower()
    target_urls = [
        p.url for p in pages
        if any(
            h.get("text", "").strip().lower() == needle and h.get("level") == from_level
            for h in (p.headings_outline or [])
        )
    ]
    if not target_urls:
        return _err(
            "NOT_FOUND",
            f"No pages found with H{from_level} heading \"{heading_text}\".",
            404,
        )

    results = []
    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            for url in target_urls:
                if to_level is not None:
                    r = await change_heading_level(wp, url, heading_text, from_level, to_level)
                else:
                    r = await convert_heading_to_bold(wp, url, heading_text)
                results.append({"url": url, **r})
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("bulk_replace_heading_error", extra={"job_id": job_id})
        return _err("WP_ERROR", str(exc), 500)

    logger.info(
        "bulk_replace_heading_complete",
        extra={
            "job_id":   job_id,
            "heading":  heading_text,
            "total":    len(results),
            "succeeded": sum(1 for r in results if r.get("success")),
        },
    )
    return results


@router.post("/change-heading-level", response_model=None)
async def change_heading_level_endpoint(
    page_url:     str = Query(..., description="URL of the page to edit"),
    heading_text: str = Query(..., description="Exact plain text of the heading to change"),
    from_level:   int = Query(..., description="Current heading level (1–6)"),
    to_level:     int = Query(..., description="Target heading level (1–6)"),
) -> dict | JSONResponse:
    """Change the level of a specific heading in WordPress post content.

    Matches the heading by its plain-text content and current level, then
    updates the HTML tag (and Gutenberg block comment if present).
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await change_heading_level(wp, page_url, heading_text, from_level, to_level)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("change_heading_level_error", extra={"page_url": page_url})
        return _err("WP_ERROR", str(exc), 500)

    return result


@router.get("/image-info", response_model=None)
async def get_image_info(
    image_url: str = Query(..., description="Absolute URL of the image"),
) -> dict | JSONResponse:
    """Fetch WordPress attachment metadata for an image URL.

    Returns attachment id, current alt_text, title, caption, and a direct
    link to the WP Media Library edit page.  Used by the IMG_OVERSIZED and
    IMG_ALT_MISSING fix panels.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)
    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await get_attachment_info(wp, image_url)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("get_image_info_error", extra={"image_url": image_url})
        return _err("WP_ERROR", str(exc), 500)
    return result


@router.post("/update-image-meta", response_model=None)
async def update_image_meta_endpoint(
    image_url: str = Query(..., description="Absolute URL of the image"),
    alt_text:  str | None = Query(None, description="New alt text (omit to leave unchanged)"),
    title:     str | None = Query(None, description="New media title (omit to leave unchanged)"),
    caption:   str | None = Query(None, description="New caption (omit to leave unchanged)"),
) -> dict | JSONResponse:
    """Update alt text, title, and/or caption for a WordPress media attachment.

    Only the fields explicitly provided are updated.  Used by the
    IMG_ALT_MISSING fix panel.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)
    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await update_image_metadata(wp, image_url, alt_text=alt_text, title=title, caption=caption)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 400)
    except Exception as exc:
        logger.exception("update_image_meta_error", extra={"image_url": image_url})
        return _err("WP_ERROR", str(exc), 500)
    return result


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

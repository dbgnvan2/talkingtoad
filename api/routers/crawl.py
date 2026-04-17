"""
Crawl management endpoints (spec §6.1, §6.2, §6.4).

POST  /api/crawl/start
GET   /api/crawl/{job_id}/status
POST  /api/crawl/{job_id}/cancel
GET   /api/crawl/{job_id}/results
GET   /api/crawl/{job_id}/results/{category}
GET   /api/crawl/{job_id}/pages
GET   /api/crawl/{job_id}/pages/issues
GET   /api/crawl/{job_id}/export/csv
GET   /api/crawl/{job_id}/export/csv/{category}
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.crawler.engine import CrawlResult, CrawlSettings as EngineCrawlSettings, run_crawl
from api.crawler.issue_checker import Issue as EngIssue
from api.crawler.parser import ParsedPage as EngPage
from api.models.issue import PHASE_1_CATEGORIES, Issue
from api.models.job import CrawlJob, CrawlSettings
from api.models.link import Link
from api.models.page import CrawledPage
from api.services.auth import require_auth
from api.services.job_store import SQLiteJobStore, RedisJobStore
from api.services.rate_limiter import CRAWL_START_LIMIT, limiter
from api.services.report_generator import generate_pdf_report
from api.services.excel_generator import generate_excel_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawl", dependencies=[Depends(require_auth)])

# Valid category slugs for the filtered results endpoint
_VALID_CATEGORIES: frozenset[str] = frozenset(
    ["broken_link", "metadata", "heading", "redirect",
     "crawlability", "duplicate", "sitemap", "security", "url_structure", "ai_readiness", "image"]
)

# Per-job cancel events (job_id → asyncio.Event)
_cancel_events: dict[str, asyncio.Event] = {}

# CSV column order (spec §4.4)
_CSV_FIELDS = ["url", "issue_code", "severity", "category", "phase", "description", "recommendation"]


# ── Dependency injection ───────────────────────────────────────────────────

def get_store() -> SQLiteJobStore | RedisJobStore:
    """Return the app-level job store. Overridden in tests via dependency_overrides."""
    from api.main import _store
    return _store  # type: ignore[return-value]


# ── Helper: standard error response ───────────────────────────────────────

def _err(code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": code, "message": message, "http_status": http_status}},
    )


# ── Type conversion: engine → model ───────────────────────────────────────

def _engine_page_to_model(page: EngPage, job_id: str) -> CrawledPage:
    redirect_url = page.final_url if page.final_url != page.url else None
    return CrawledPage(
        job_id=job_id,
        url=page.url,
        status_code=page.status_code,
        redirect_url=redirect_url,
        title=page.title,
        meta_description=page.meta_description,
        canonical_url=page.canonical_url,
        og_title=page.og_title,
        og_description=page.og_description,
        has_favicon=page.has_favicon,
        h1_tags=page.h1_tags,
        headings_outline=page.headings_outline,
        is_indexable=page.is_indexable,
        robots_directive=page.robots_directive,
        response_size_bytes=page.response_size_bytes,
        crawled_at=datetime.now(timezone.utc),
        has_viewport_meta=page.has_viewport_meta,
        schema_types=page.schema_types,
        external_script_count=page.external_script_count,
        external_stylesheet_count=page.external_stylesheet_count,
        word_count=page.word_count,
        crawl_depth=page.crawl_depth,
        pagination_next=page.pagination_next,
        pagination_prev=page.pagination_prev,
        amphtml_url=page.amphtml_url,
        meta_refresh_url=page.meta_refresh_url,
        mixed_content_count=page.mixed_content_count,
        unsafe_cross_origin_count=page.unsafe_cross_origin_count,
        has_hsts=page.has_hsts,
        text_to_html_ratio=page.text_to_html_ratio,
        has_json_ld=page.has_json_ld,
        pdf_metadata=page.pdf_metadata,
        image_urls=page.image_urls or [],
    )


def _engine_issue_to_model(issue: EngIssue, job_id: str) -> Issue:
    return Issue(
        job_id=job_id,
        page_url=issue.page_url,
        category=issue.category,  # type: ignore[arg-type]
        severity=issue.severity,  # type: ignore[arg-type]
        issue_code=issue.code,
        description=issue.description,
        recommendation=issue.recommendation,
        impact=issue.impact,
        effort=issue.effort,
        priority_rank=issue.priority_rank,
        human_description=issue.human_description,
        extra=issue.extra,
    )


# ── Background crawl task ──────────────────────────────────────────────────

async def _run_crawl_background(
    job_id: str,
    target_url: str,
    engine_settings: EngineCrawlSettings,
    store: SQLiteJobStore | RedisJobStore,
    cancel_event: asyncio.Event,
) -> None:
    """Background task: run the crawl, persist results, update job status."""
    try:
        await store.update_job(job_id, status="running")

        # Load verified link URLs so the engine can suppress false-positive notices.
        engine_settings.verified_link_urls = await store.get_verified_link_urls()
        # Load exempt anchor URLs so icon links don't flood LINK_EMPTY_ANCHOR.
        engine_settings.exempt_anchor_urls = await store.get_exempt_anchor_url_set()

        async def on_progress(p: dict) -> None:
            await store.update_job(
                job_id,
                pages_crawled=p["pages_crawled"],
                pages_total=p["pages_total"],
                current_url=p["current_url"],
                phase=p.get("phase", "crawling_pages"),
                external_links_checked=p.get("external_links_checked", 0),
                external_links_total=p.get("external_links_total", 0),
            )

        result: CrawlResult = await run_crawl(
            job_id,
            target_url,
            engine_settings,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

        print(f"[ROUTER] Crawl complete. Pages: {len(result.pages)}, Issues: {len(result.issues)}, Images: {len(result.images)}")

        pages = [_engine_page_to_model(p, job_id) for p in result.pages]
        issues = [_engine_issue_to_model(i, job_id) for i in result.issues]
        broken_links = [
            Link(
                job_id=job_id,
                source_url=src,
                target_url=tgt,
                link_text=txt,
                link_type="external",
                is_broken=True,
            )
            for tgt, src, txt in result.broken_link_sources
        ]

        if pages:
            await store.save_pages(pages)
        if issues:
            await store.save_issues(issues)
        if broken_links:
            await store.save_links(broken_links)
        if result.images:
            await store.save_images(result.images)

        final_status = "cancelled" if result.cancelled else "complete"
        await store.update_job(
            job_id,
            status=final_status,
            pages_crawled=result.pages_crawled,
            completed_at=datetime.now(timezone.utc),
        )
        logger.info("crawl_persisted", extra={"job_id": job_id, "status": final_status})

    except Exception as exc:
        logger.exception("crawl_background_failed", extra={"job_id": job_id})
        await store.update_job(
            job_id,
            status="failed",
            error_message=str(exc),
            completed_at=datetime.now(timezone.utc),
        )
    finally:
        _cancel_events.pop(job_id, None)


# ── Exempt anchor URL filtering ───────────────────────────────────────────

def _apply_exempt_anchors(issues: list, exempt_urls: set[str]) -> list:
    """Remove exempted hrefs from LINK_EMPTY_ANCHOR issues; drop the issue if all hrefs are exempt.

    Works on both Issue model objects and plain dicts (as returned by _issue_dict).
    """
    if not exempt_urls:
        return issues

    filtered = []
    for issue in issues:
        # Support both model objects and dicts
        code = issue.get("issue_code") if isinstance(issue, dict) else getattr(issue, "issue_code", None)
        if code != "LINK_EMPTY_ANCHOR":
            filtered.append(issue)
            continue

        desc = issue.get("description") if isinstance(issue, dict) else getattr(issue, "description", "")
        if not desc:
            filtered.append(issue)
            continue

        # Parse "N links with no anchor text: url1, url2, ..."
        import re as _re
        m = _re.match(r"^(\d+) links? with no anchor text:\s*(.+)$", desc or "")
        if not m:
            filtered.append(issue)
            continue

        hrefs = [h.strip() for h in m.group(2).split(",")]
        remaining = [h for h in hrefs if h not in exempt_urls]
        if not remaining:
            continue  # all hrefs exempted — drop issue entirely

        # Rebuild description with remaining hrefs
        n = len(remaining)
        listed = ", ".join(remaining[:5])
        suffix = f" and {n - 5} more" if n > 5 else ""
        new_desc = f"{n} link{'s' if n > 1 else ''} with no anchor text: {listed}{suffix}"

        if isinstance(issue, dict):
            issue = {**issue, "description": new_desc}
        else:
            issue.description = new_desc
        filtered.append(issue)

    return filtered


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/recent", response_model=None)
async def list_recent_jobs(
    limit: int = 10,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> list[dict]:
    """Return the most recent crawl jobs (newest first) for the home page."""
    jobs = await store.list_recent_jobs(limit=min(limit, 20))
    return [
        {
            "job_id": j.job_id,
            "target_url": j.target_url,
            "status": j.status,
            "pages_crawled": j.pages_crawled,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]


@router.post("/start", status_code=202, response_model=None)
@limiter.limit(CRAWL_START_LIMIT)
async def start_crawl(
    request: Request,
    body: dict,
    background_tasks: BackgroundTasks,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict:
    """Submit a new crawl job (spec §6.4 POST /api/crawl/start)."""
    import sys
    print("[START] ====== start_crawl endpoint called ======", flush=True)
    sys.stderr.write("[START] ====== STDERR start_crawl ======\n")
    sys.stderr.flush()
    target_url = body.get("target_url", "").strip()
    if not target_url or not target_url.startswith(("http://", "https://")):
        return _err("INVALID_URL", "target_url must be a valid http or https URL.", 422)

    sitemap_url = body.get("sitemap_url")
    settings_data: dict = body.get("settings") or {}
    settings = CrawlSettings(**{k: v for k, v in settings_data.items() if v is not None})

    job = CrawlJob(
        job_id=str(uuid4()),
        target_url=target_url,
        sitemap_url=sitemap_url,
        settings=settings,
    )
    await store.create_job(job)

    cancel_event = asyncio.Event()
    _cancel_events[job.job_id] = cancel_event

    engine_settings = EngineCrawlSettings(
        max_pages=settings.max_pages,
        crawl_delay_ms=settings.crawl_delay_ms,
        respect_robots=settings.respect_robots,
        include_subdomains=settings.include_subdomains,
        enabled_analyses=settings.enabled_analyses,
        img_size_limit_kb=settings.img_size_limit_kb,
        suppress_h1_strings=settings.suppress_h1_strings,
        suppress_banner_h1=settings.suppress_banner_h1,
    )

    background_tasks.add_task(
        _run_crawl_background,
        job.job_id,
        target_url,
        engine_settings,
        store,
        cancel_event,
    )

    logger.info("crawl_started", extra={"job_id": job.job_id, "target_url": target_url})

    return {
        "job_id": job.job_id,
        "status": "queued",
        "poll_url": f"/api/crawl/{job.job_id}/status",
    }


@router.get("/{job_id}/status", response_model=None)
async def job_status(
    job_id: str,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Return job progress and status (spec §6.4 GET /status)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    estimated: int | None = None
    if (
        job.pages_total is not None
        and job.pages_crawled >= 5
        and job.pages_crawled < job.pages_total
        and job.started_at
    ):
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        rate = elapsed / job.pages_crawled if job.pages_crawled else 0
        remaining = job.pages_total - job.pages_crawled
        estimated = int(rate * remaining)

    return {
        "job_id": job.job_id,
        "status": job.status,
        "pages_crawled": job.pages_crawled,
        "pages_total": job.pages_total,
        "current_url": job.current_url,
        "started_at": job.started_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "estimated_seconds_remaining": estimated,
        "error_message": job.error_message,
    }


@router.post("/{job_id}/cancel", response_model=None)
async def cancel_job(
    job_id: str,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Cancel a running crawl (spec §6.4 POST /cancel)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    if job.status in ("complete", "failed", "cancelled"):
        return _err("JOB_ALREADY_COMPLETE", "This job has already finished and cannot be cancelled.", 409)

    if job.status == "queued":
        # Background task hasn't started — cancel directly
        await store.update_job(
            job_id,
            status="cancelled",
            completed_at=datetime.now(timezone.utc),
        )
    else:
        # Signal the running engine
        event = _cancel_events.get(job_id)
        if event:
            event.set()

    return {"job_id": job_id, "status": "cancelled"}


@router.get("/{job_id}/results", response_model=None)
async def get_results(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    severity: str | None = Query(None),
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Paginated results for a completed job (spec §6.4 GET /results)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    issues, total = await store.get_issues(job_id, severity=severity, page=page, limit=limit)
    exempt_urls = await store.get_exempt_anchor_url_set()
    issue_dicts = _apply_exempt_anchors([_issue_dict(i) for i in issues], exempt_urls)
    summary = await store.get_summary(job_id)
    total_pages = max(1, math.ceil(total / limit))

    return {
        "job_id": job_id,
        "summary": summary,
        "pagination": {"page": page, "limit": limit, "total_issues": total, "total_pages": total_pages},
        "issues": issue_dicts,
    }


@router.get("/{job_id}/results/{category}", response_model=None)
async def get_results_by_category(
    job_id: str,
    category: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=5000),
    severity: str | None = Query(None),
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Paginated results filtered by category (spec §6.4 GET /results/{category})."""
    if category not in _VALID_CATEGORIES:
        return _err(
            "INVALID_CATEGORY",
            f"'{category}' is not a valid category. Valid values: {sorted(_VALID_CATEGORIES)}",
            422,
        )

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    issues, total = await store.get_issues(job_id, category=category, severity=severity, page=page, limit=limit)
    exempt_urls = await store.get_exempt_anchor_url_set()
    issue_dicts = _apply_exempt_anchors([_issue_dict(i) for i in issues], exempt_urls)
    summary = await store.get_summary(job_id)
    total_pages = max(1, math.ceil(total / limit))

    return {
        "job_id": job_id,
        "summary": summary,
        "pagination": {"page": page, "limit": limit, "total_issues": total, "total_pages": total_pages},
        "issues": issue_dicts,
    }


@router.get("/{job_id}/pages", response_model=None)
async def get_pages(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    min_severity: str | None = Query(None),
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """All crawled pages with per-page issue counts (spec §6.1, By Page view)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    pages, total_crawled = await store.get_pages_with_issue_counts(
        job_id, min_severity=min_severity, page=page, limit=limit
    )
    total_pages = max(1, math.ceil(total_crawled / limit))

    return {
        "job_id": job_id,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages_crawled": job.pages_crawled,
            "total_pages": total_pages,
        },
        "pages": pages,
    }


@router.get("/{job_id}/pages/issues", response_model=None)
async def get_page_issues(
    job_id: str,
    url: str = Query(..., description="Exact URL of the crawled page"),
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """All issues for one specific page, grouped by category (spec §6.1, By Page view)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    crawled_page, by_category = await store.get_page_issues_by_url(job_id, url)
    if crawled_page is None:
        return _err("PAGE_NOT_FOUND", f"No crawled page found with URL: {url}", 404)

    exempt_urls = await store.get_exempt_anchor_url_set()

    # Filter exempted anchor hrefs from LINK_EMPTY_ANCHOR before counting/returning
    filtered_by_category = {
        cat: _apply_exempt_anchors([_issue_dict(i) for i in issues], exempt_urls)
        for cat, issues in by_category.items()
    }
    # Drop empty categories after filtering
    filtered_by_category = {cat: issues for cat, issues in filtered_by_category.items() if issues}

    total = sum(len(v) for v in filtered_by_category.values())

    # Include the raw page fields so the UI can show the actual offending content
    # (title text, meta description, H1s, robots directive, etc.) per issue.
    page_data = {
        "title":            crawled_page.title,
        "meta_description": crawled_page.meta_description,
        "h1_tags":          crawled_page.h1_tags,
        "headings_outline": crawled_page.headings_outline,
        "canonical_url":    crawled_page.canonical_url,
        "robots_directive": crawled_page.robots_directive,
        "redirect_chain":   crawled_page.redirect_chain,
        "redirect_url":     crawled_page.redirect_url,
        "og_title":         crawled_page.og_title,
        "og_description":   crawled_page.og_description,
        "amphtml_url":      crawled_page.amphtml_url,
        "meta_refresh_url": crawled_page.meta_refresh_url,
        "response_size_bytes": crawled_page.response_size_bytes,
        "word_count":       crawled_page.word_count,
    }

    return {
        "job_id": job_id,
        "url": url,
        "status_code": crawled_page.status_code,
        "total_issues": total,
        "page_data": page_data,
        "by_category": filtered_by_category,
    }


@router.post("/{job_id}/rescan-url", response_model=None)
async def rescan_url(
    job_id: str,
    url: str = Query(..., description="The crawled page URL to rescan"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Re-fetch a single page and update its issues in the database.

    Useful for verifying that a fix worked. Replaces the stored issues for
    this URL with the results from a fresh fetch and issue check.
    """
    from api.crawler.fetcher import fetch_page, make_client, _RESCAN_TIMEOUT
    from api.crawler.parser import parse_page
    from api.crawler.issue_checker import check_page, issue_for_status, make_issue
    from api.crawler.engine import (
        _check_external_link, _is_bot_blocking_domain,
        _EXTERNAL_LINK_CAP_PER_PAGE,
    )
    from api.crawler.normaliser import normalise_url

    # Normalize the URL to match how it was stored during the original crawl.
    # e.g. trailing slashes may differ between what the UI sends and what's in DB.
    try:
        url = normalise_url(url)
    except Exception:
        pass  # fall through with original url if normalisation fails

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    crawled_page, old_by_cat = await store.get_page_issues_by_url(job_id, url)
    if crawled_page is None:
        return _err("PAGE_NOT_FOUND", f"No crawled page found with URL: {url}", 404)
    # Include broken-link issue codes where this URL is the source page
    # (stored under dead-URL page_url, so not returned by get_page_issues_by_url)
    old_codes: set[str] = {i.issue_code for issues in old_by_cat.values() for i in issues}
    old_codes |= await store.get_broken_link_codes_for_source(job_id, url)

    base_url = job.target_url
    is_homepage = url.rstrip("/") == base_url.rstrip("/")
    suppress_h1s: list[str] = job.settings.suppress_h1_strings if job.settings else []
    suppress_banner: bool = job.settings.suppress_banner_h1 if job.settings else False

    try:
        async with make_client() as client:
            result = await fetch_page(url, client, timeout=_RESCAN_TIMEOUT, bypass_cache=True)
    except Exception as exc:
        return _err("FETCH_ERROR", str(exc), 500)

    if result.status_code == 0:
        error_msg = result.error or "Unknown error"
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            friendly = f"Page timed out after {int(_RESCAN_TIMEOUT)}s — the site may be slow. Try again in a moment."
        elif "connect" in error_msg.lower():
            friendly = "Could not connect to the site — check that it is online."
        else:
            friendly = f"Could not fetch page: {error_msg}"
        return _err("FETCH_ERROR", friendly, 502)

    try:
        page = parse_page(result, base_url, is_homepage=is_homepage)
    except Exception as exc:
        return _err("PARSE_ERROR", f"Could not parse page: {exc}", 500)

    # Run issue checks (single-page — no cross-page or sitemap checks)
    exempt_urls = await store.get_exempt_anchor_url_set()
    eng_issues = check_page(
        page,
        suppress_h1_strings=suppress_h1s or None,
        suppress_banner_h1=suppress_banner,
        exempt_anchor_urls=exempt_urls or None,
    )

    # Re-check external links found on this page (up to per-page cap)
    # This ensures broken links that were removed get cleared, and any still
    # present are re-verified. Mirrors the engine's external link phase.
    verified_link_urls: set[str] = set()
    try:
        vl = await store.get_verified_links()
        verified_link_urls = {v["url"] for v in vl} if vl else set()
    except Exception:
        pass

    external_links = [lnk for lnk in (page.links or []) if not lnk.is_internal]
    ext_checked = 0
    async with make_client() as ext_client:
        for lnk in external_links:
            if ext_checked >= _EXTERNAL_LINK_CAP_PER_PAGE:
                break
            target = lnk.url
            if _is_bot_blocking_domain(target):
                if target not in verified_link_urls:
                    skip_issue = make_issue("EXTERNAL_LINK_SKIPPED", target)
                    skip_issue.extra = {"source_url": url}
                    eng_issues.append(skip_issue)
                ext_checked += 1
                continue
            try:
                ext_result = await _check_external_link(target, ext_client)
            except Exception:
                ext_checked += 1
                continue
            ext_checked += 1
            if ext_result is None:
                continue
            if ext_result.status_code == 0 and ext_result.error:
                timeout_issue = make_issue("EXTERNAL_LINK_TIMEOUT", target)
                timeout_issue.extra = {"source_url": url}
                eng_issues.append(timeout_issue)
            else:
                broken = issue_for_status(ext_result.status_code, target)
                if broken:
                    broken.extra = {"source_url": url}
                    eng_issues.append(broken)

    # Convert engine dataclasses → Pydantic models, stamping job/page context.
    # For broken-link/skipped/timeout issues the page_url is the dead target URL
    # (set by make_issue/issue_for_status) — keep that as-is so the category view
    # can group by target URL.  For all other issues set page_url to the source page.
    _BROKEN_LINK_CATEGORIES = {"broken_link"}
    new_issues = [
        _engine_issue_to_model(i, job_id)
        for i in eng_issues
    ]
    for issue in new_issues:
        if issue.category not in _BROKEN_LINK_CATEGORIES:
            issue.page_url = url
        # broken-link issues keep page_url = dead_url (from make_issue/issue_for_status)
        # and have extra.source_url = url (already set above)

    # Update the stored page record with fresh data from the rescan.
    # This ensures headings_outline, title, meta_description, etc. reflect
    # the current state of the page — not the original crawl snapshot.
    # crawl_depth is preserved from the original record (single-page rescan has no depth context).
    updated_page = _engine_page_to_model(page, job_id)
    updated_page.url = url  # use the normalised URL
    updated_page.status_code = result.status_code
    updated_page.redirect_url = result.final_url if result.is_redirect else None
    if crawled_page:
        updated_page.crawl_depth = crawled_page.crawl_depth
        updated_page.page_id = crawled_page.page_id
    await store.save_pages([updated_page])

    # Replace stored issues for this URL.
    # Two passes: (1) issues with page_url = url (metadata, heading, etc.)
    #             (2) broken-link issues stored with page_url = dead_url but
    #                 extra.source_url = url — these are missed by pass 1.
    old_count = await store.delete_issues_for_url(job_id, url)
    old_count += await store.delete_broken_link_issues_for_source(job_id, url)
    await store.save_issues(new_issues)
    new_count = len(new_issues)

    # Record which issue codes were resolved (present before, gone after)
    new_codes: set[str] = {i.issue_code for i in new_issues}
    resolved_codes = sorted(old_codes - new_codes)
    if resolved_codes:
        await store.record_fixed_issues(job_id, url, resolved_codes)

    by_category: dict[str, list] = {}
    for issue in new_issues:
        by_category.setdefault(issue.category, []).append(_issue_dict(issue))
    # Apply exempt filter to the response (issues were stored without exemption filtering)
    by_category = {
        cat: _apply_exempt_anchors(issues, exempt_urls)
        for cat, issues in by_category.items()
    }
    by_category = {cat: issues for cat, issues in by_category.items() if issues}

    rescan_page_data = {
        "title":              page.title,
        "meta_description":   page.meta_description,
        "h1_tags":            page.h1_tags,
        "headings_outline":   page.headings_outline,
        "canonical_url":      page.canonical_url,
        "robots_directive":   page.robots_directive,
        "redirect_chain":     result.redirect_chain,
        "redirect_url":       result.final_url if result.is_redirect else None,
        "og_title":           page.og_title,
        "og_description":     page.og_description,
        "amphtml_url":        page.amphtml_url,
        "meta_refresh_url":   page.meta_refresh_url,
        "response_size_bytes": None,
        "word_count":         page.word_count,
    }

    filtered_count = sum(len(v) for v in by_category.values())

    return {
        "url": url,
        "status_code": result.status_code,
        "old_count": old_count,
        "new_count": filtered_count,
        "resolved": max(0, old_count - filtered_count),
        "added": max(0, filtered_count - old_count),
        "resolved_codes": resolved_codes,
        "total_issues": filtered_count,
        "page_data": rescan_page_data,
        "by_category": by_category,
    }


@router.post("/scan-page", response_model=None)
async def scan_single_page(
    url: str = Query(..., description="The page URL to fetch and analyse"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Create a new single-page job, fetch the URL, run issue checks, and return the job_id.

    The caller can navigate straight to /results/{job_id} — no polling needed
    because the scan runs synchronously before this endpoint returns.
    """
    from urllib.parse import urlparse
    from api.crawler.fetcher import fetch_page, make_client, _RESCAN_TIMEOUT
    from api.crawler.parser import parse_page
    from api.crawler.issue_checker import check_page, issue_for_status, make_issue
    from api.crawler.engine import (
        _check_external_link, _is_bot_blocking_domain,
        _EXTERNAL_LINK_CAP_PER_PAGE,
    )
    from api.crawler.normaliser import normalise_url

    if not url or not url.startswith(("http://", "https://")):
        return _err("INVALID_URL", "url must be a valid http or https URL.", 422)

    try:
        url = normalise_url(url)
    except Exception:
        pass

    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    job = CrawlJob(
        target_url=origin,
        status="running",
        pages_crawled=0,
        pages_total=1,
    )
    await store.create_job(job)
    job_id = job.job_id

    try:
        async with make_client() as client:
            result = await fetch_page(url, client, timeout=_RESCAN_TIMEOUT)
    except Exception as exc:
        await store.update_job(job_id, status="failed", error_message=str(exc))
        return _err("FETCH_ERROR", str(exc), 500)

    if result.status_code == 0:
        error_msg = result.error or "Unknown error"
        await store.update_job(job_id, status="failed", error_message=error_msg)
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            friendly = f"Page timed out after {int(_RESCAN_TIMEOUT)}s."
        elif "connect" in error_msg.lower():
            friendly = "Could not connect to the site — check that it is online."
        else:
            friendly = f"Could not fetch page: {error_msg}"
        return _err("FETCH_ERROR", friendly, 502)

    is_homepage = url.rstrip("/") == origin.rstrip("/")
    try:
        page = parse_page(result, origin, is_homepage=is_homepage)
    except Exception as exc:
        await store.update_job(job_id, status="failed", error_message=str(exc))
        return _err("PARSE_ERROR", f"Could not parse page: {exc}", 500)

    # Inherit suppress_h1_strings and suppress_banner_h1 from the most recent
    # completed job for this origin so that theme-injected headings stay suppressed
    # in ad-hoc single-page scans.
    suppress_h1s: list[str] = []
    suppress_banner: bool = False
    try:
        recent = await store.list_recent_jobs(limit=20)
        for rj in recent:
            if rj.target_url.rstrip("/") == origin.rstrip("/") and rj.settings:
                suppress_h1s = rj.settings.suppress_h1_strings or []
                suppress_banner = rj.settings.suppress_banner_h1
                break
    except Exception:
        pass

    exempt_urls = await store.get_exempt_anchor_url_set()
    eng_issues = check_page(
        page,
        suppress_h1_strings=suppress_h1s or None,
        suppress_banner_h1=suppress_banner,
        exempt_anchor_urls=exempt_urls or None,
    )

    verified_link_urls: set[str] = set()
    try:
        vl = await store.get_verified_links()
        verified_link_urls = {v["url"] for v in vl} if vl else set()
    except Exception:
        pass

    external_links = [lnk for lnk in (page.links or []) if not lnk.is_internal]
    ext_checked = 0
    async with make_client() as ext_client:
        for lnk in external_links:
            if ext_checked >= _EXTERNAL_LINK_CAP_PER_PAGE:
                break
            target = lnk.url
            if _is_bot_blocking_domain(target):
                if target not in verified_link_urls:
                    skip_issue = make_issue("EXTERNAL_LINK_SKIPPED", target)
                    skip_issue.extra = {"source_url": url}
                    eng_issues.append(skip_issue)
                ext_checked += 1
                continue
            try:
                ext_result = await _check_external_link(target, ext_client)
            except Exception:
                ext_checked += 1
                continue
            ext_checked += 1
            if ext_result is None:
                continue
            if ext_result.status_code == 0 and ext_result.error:
                timeout_issue = make_issue("EXTERNAL_LINK_TIMEOUT", target)
                timeout_issue.extra = {"source_url": url}
                eng_issues.append(timeout_issue)
            else:
                broken = issue_for_status(ext_result.status_code, target)
                if broken:
                    broken.extra = {"source_url": url}
                    eng_issues.append(broken)

    _BROKEN_LINK_CATEGORIES = {"broken_link"}
    new_issues = [_engine_issue_to_model(i, job_id) for i in eng_issues]
    for issue in new_issues:
        if issue.category not in _BROKEN_LINK_CATEGORIES:
            issue.page_url = url

    # ── Image collection (v1.9image) ────────────────────────────────────
    from api.models.image import ImageInfo
    from api.crawler.image_analyzer import analyze_batch as analyze_images
    from api.crawler.engine import _guess_format_from_url, _extract_filename

    all_images: list[ImageInfo] = []
    if page.image_data:
        for img_data in page.image_data:
            img_url = img_data.get("url")
            if not img_url:
                continue
            image_info = ImageInfo(
                url=img_url,
                page_url=url,
                job_id=job_id,
                alt=img_data.get("alt"),
                title=img_data.get("title"),
                filename=_extract_filename(img_url),
                format=_guess_format_from_url(img_url),
                width=None,
                height=None,
                rendered_width=img_data.get("rendered_width"),
                rendered_height=img_data.get("rendered_height"),
                file_size_bytes=None,
                load_time_ms=None,
                http_status=0,
                is_lazy_loaded=img_data.get("is_lazy_loaded", False),
                has_srcset=img_data.get("has_srcset", False),
                srcset_candidates=img_data.get("srcset_candidates", []),
                is_decorative=img_data.get("is_decorative", False),
                surrounding_text=img_data.get("surrounding_text", ""),
                content_hash=None,
                data_source="html_only",
            )
            all_images.append(image_info)

        if all_images:
            analyzed_images, image_issues = analyze_images(all_images, job_id=job_id)
            all_images = analyzed_images
            # Add image issues to the issues list
            new_issues.extend([_engine_issue_to_model(i, job_id) for i in image_issues])

    page_model = _engine_page_to_model(page, job_id)
    page_model.url = url
    page_model.status_code = result.status_code
    page_model.redirect_url = result.final_url if result.is_redirect else None

    await store.save_pages([page_model])
    if new_issues:
        await store.save_issues(new_issues)
    if all_images:
        await store.save_images(all_images)

    await store.update_job(
        job_id,
        status="complete",
        pages_crawled=1,
        pages_total=1,
    )

    logger.info("scan_page_complete", extra={"job_id": job_id, "url": url, "issues": len(new_issues), "images": len(all_images)})

    return {"job_id": job_id, "status": "complete", "url": url, "issues": len(new_issues)}


@router.post("/{job_id}/mark-fixed", response_model=None)
async def mark_fixed(
    job_id: str,
    url: str = Query(..., description="Source page URL where the issue was fixed"),
    codes: str = Query(..., description="Comma-separated issue codes that were fixed"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Manually record that issues were fixed on a page without running a rescan.

    Called when the user visits a page, fixes an issue themselves, then comes
    back and clicks 'Fixed'. Records the fix date in fix_history.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if code_list:
        await store.record_fixed_issues(job_id, url, code_list)

    return {"url": url, "fixed_codes": code_list, "status": "recorded"}


@router.get("/{job_id}/fix-history", response_model=None)
async def fix_history(
    job_id: str,
    store=Depends(get_store),
) -> list[dict] | JSONResponse:
    """Return all issue codes that were resolved via rescan for this job, with timestamps."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    return await store.get_fix_history(job_id)


@router.get("/{job_id}/export/csv", response_model=None)
async def export_csv_full(
    job_id: str,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> StreamingResponse | JSONResponse:
    """Download all issues as CSV (spec §6.2)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    issues = await store.get_all_issues(job_id)
    return _csv_response(issues, filename=f"crawl-{job_id}.csv")


@router.get("/{job_id}/export/pdf", response_model=None)
async def export_pdf_report(
    job_id: str,
    include_help: bool = Query(True, description="Include detailed help text for each issue category"),
    include_pages: bool = Query(True, description="List affected URLs for each issue type"),
    summary_only: bool = Query(False, description="Generate summary pages only (ignores help and page lists)"),
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> StreamingResponse | JSONResponse:
    """Generate and download a professional PDF audit report."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    # Load GEO config for the domain to get report preferences
    try:
        from urllib.parse import urlparse
        domain = urlparse(job.target_url).netloc.replace('www.', '')
        geo_config = await store.get_geo_config(domain)

        if geo_config:
            # Override job settings with GEO config if available
            if geo_config.client_name:
                job.settings.client_name = geo_config.client_name
            if geo_config.prepared_by:
                job.settings.prepared_by = geo_config.prepared_by
            logger.info("geo_config_loaded_for_report", extra={"domain": domain, "has_client_name": bool(geo_config.client_name)})
    except Exception as exc:
        logger.warning("geo_config_load_failed", extra={"error": str(exc)})
        # Continue with job settings as fallback

    issues = await store.get_all_issues(job_id)
    summary = await store.get_summary(job_id)

    # Fetch top 10 pages for the report
    top_pages_data, _ = await store.get_pages_with_issue_counts(job_id, page=1, limit=10)

    # Fetch image data for the report
    image_summary = await store.get_image_summary(job_id)
    top_images, _ = await store.get_images(job_id, page=1, limit=20, sort_by="score")

    # summary_only is a shortcut for disabling help and pages
    if summary_only:
        include_help = False
        include_pages = False

    try:
        logger.info("generating_pdf_report", extra={
            "job_id": job_id,
            "issues_count": len(issues),
            "include_help": include_help,
            "include_pages": include_pages
        })
        pdf_bytes = await generate_pdf_report(
            job, issues, summary,
            include_help=include_help,
            include_pages=include_pages,
            top_pages=top_pages_data,
            image_summary=image_summary,
            top_images=top_images,
        )
        logger.info("pdf_report_generated", extra={"job_id": job_id, "size_bytes": len(pdf_bytes)})
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="TalkingToad-Audit-{job_id[:8]}.pdf"'},
        )
    except Exception as exc:
        logger.exception("pdf_generation_failed", extra={"job_id": job_id, "error": str(exc)})
        return _err("REPORT_ERROR", f"Failed to generate PDF: {str(exc)}", 500)


@router.get("/{job_id}/export/excel", response_model=None)
async def export_excel_report(
    job_id: str,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> StreamingResponse | JSONResponse:
    """Generate and download a multi-sheet Excel audit report."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    issues = await store.get_all_issues(job_id)
    summary = await store.get_summary(job_id)

    # Fetch image data for the report
    image_summary = await store.get_image_summary(job_id)
    images_list, _ = await store.get_images(job_id, page=1, limit=500, sort_by="score")

    try:
        excel_bytes = generate_excel_report(
            job, issues, summary,
            image_summary=image_summary,
            images=images_list,
        )
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="TalkingToad-Audit-{job_id[:8]}.xlsx"'},
        )
    except Exception as exc:
        logger.exception("excel_generation_failed", extra={"job_id": job_id})
        return _err("REPORT_ERROR", f"Failed to generate Excel: {str(exc)}", 500)


@router.get("/{job_id}/export/csv/{category}", response_model=None)
async def export_csv_category(
    job_id: str,
    category: str,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> StreamingResponse | JSONResponse:
    """Download one category's issues as CSV (spec §6.2)."""
    if category not in _VALID_CATEGORIES:
        return _err(
            "INVALID_CATEGORY",
            f"'{category}' is not a valid category. Valid values: {sorted(_VALID_CATEGORIES)}",
            422,
        )

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    issues, _ = await store.get_issues(job_id, category=category, limit=10_000)
    return _csv_response(issues, filename=f"crawl-{job_id}-{category}.csv")


# ── Private helpers ────────────────────────────────────────────────────────

def _issue_dict(issue: Issue) -> dict:
    return {
        "issue_id": issue.issue_id,
        "page_url": issue.page_url,
        "category": issue.category,
        "severity": issue.severity,
        "issue_code": issue.issue_code,
        "description": issue.description,
        "recommendation": issue.recommendation,
        "impact": issue.impact,
        "effort": issue.effort,
        "priority_rank": issue.priority_rank,
        "human_description": issue.human_description,
        "extra": issue.extra,
    }


@router.get("/{job_id}/images", response_model=None)
async def get_images(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),  # Increased from 100 to 1000 for bulk operations
    sort_by: str = Query("score", regex="^(score|size|load_time)$"),
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Return paginated list of images for a job with scores and issues."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    images = await store.get_images(job_id, page=page, limit=limit, sort_by=sort_by)
    summary = await store.get_image_summary(job_id)

    total = summary.get("total_images", 0)
    total_pages = max(1, math.ceil(total / limit))

    return {
        "job_id": job_id,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_images": total,
            "total_pages": total_pages,
        },
        "images": [_image_dict(img) for img in images],
    }


@router.get("/{job_id}/images/summary", response_model=None)
async def get_images_summary(
    job_id: str,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Return image analysis summary stats for a job."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    summary = await store.get_image_summary(job_id)
    return {
        "job_id": job_id,
        **summary,
    }


@router.get("/{job_id}/images/{image_url:path}", response_model=None)
async def get_image_detail(
    job_id: str,
    image_url: str,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Return detailed info for a specific image by URL."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    image = await store.get_image_by_url(job_id, image_url)
    if image is None:
        return _err("IMAGE_NOT_FOUND", f"No image found with URL: {image_url}", 404)

    return {
        "job_id": job_id,
        "image": _image_dict(image),
    }


@router.post("/{job_id}/images/fetch", response_model=None)
async def fetch_image_details(
    job_id: str,
    image_url: str = Query(..., description="URL of the image to fetch"),
    fetch_wp_metadata: bool = Query(True, description="Also fetch WordPress metadata (alt text, title)"),
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Fetch full image details: image file (dimensions, size, format) + WordPress metadata (alt text, title).

    This is the unified "Fetch WP Data" endpoint that gets the complete truth from live sources.
    """
    import hashlib
    import time
    from urllib.parse import urlparse
    import json
    from pathlib import Path

    print(f"\n{'='*80}")
    print(f"[FETCH] START - Image URL: {image_url}")
    print(f"[FETCH] Job ID: {job_id}")
    print(f"[FETCH] Fetch WP metadata: {fetch_wp_metadata}")
    print(f"{'='*80}\n")

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    image = await store.get_image_by_url(job_id, image_url)
    if image is None:
        return _err("IMAGE_NOT_FOUND", f"No image found with URL: {image_url}", 404)

    print(f"[FETCH] Got image from DB:")
    print(f"  - Image URL: {image.url}")
    print(f"  - Current alt: '{image.alt}'")
    print(f"  - Current title: '{image.title}'")
    print(f"  - File size: {image.file_size_bytes}")
    print(f"  - Dimensions: {image.width}x{image.height}")

    # Step 1: Fetch WordPress metadata if requested
    wp_fetch_success = False
    if fetch_wp_metadata:
        try:
            from api.services.wp_client import WPClient
            from api.services.wp_fixer import get_attachment_info

            _CREDS_PATH = Path("wp-credentials.json")
            if _CREDS_PATH.exists():
                with open(_CREDS_PATH) as f:
                    creds = json.load(f)

                # Validate domain
                job_domain = urlparse(job.target_url).netloc
                creds_domain = urlparse(creds.get("site_url", "")).netloc

                if job_domain == creds_domain:
                    wp = WPClient(
                        site_url=creds["site_url"],
                        login_url=creds["login_url"],
                        username=creds["username"],
                        password=creds["password"],
                    )
                    async with wp:
                        wp_info = await get_attachment_info(wp, image_url, cache_bust=True)

                    if wp_info.get("success"):
                        wp_alt = wp_info.get("alt_text", "")
                        wp_title = wp_info.get("title", "")
                        wp_caption = wp_info.get("caption", "")
                        wp_description = wp_info.get("description", "")
                        wp_media_id = wp_info.get("id")
                        wp_source_url = wp_info.get("source_url", "")

                        print(f"\n[FETCH] WordPress Response:")
                        print(f"  - WP Media ID: {wp_media_id}")
                        print(f"  - WP Source URL: {wp_source_url}")
                        print(f"  - WP Alt Text: '{wp_alt}'")
                        print(f"  - WP Title: '{wp_title}'")
                        print(f"  - WP Caption: '{wp_caption}'")
                        print(f"  - WP Description: '{wp_description}'")
                        print(f"  - URL Match: {wp_source_url == image_url}")

                        # CRITICAL: Only update if URLs match exactly
                        if wp_source_url == image_url:
                            image.alt = wp_alt
                            image.title = wp_title
                            image.caption = wp_caption
                            image.description = wp_description
                            wp_fetch_success = True
                            print(f"  ✓ URLs match - updating metadata")
                        else:
                            print(f"  ✗ URL MISMATCH - NOT updating metadata!")
                            print(f"    Requested: {image_url}")
                            print(f"    Got:       {wp_source_url}")
                    else:
                        print(f"[FETCH] WordPress fetch failed: {wp_info.get('error')}")
                        print(f"  ⚠ Image not found in WordPress Media Library")
                        print(f"  This image exists on the server but wasn't uploaded via WP Media Library")
                        # Continue with image file fetch - we can still get dimensions/size/etc.
                else:
                    print(f"[FETCH] Domain mismatch - job: {job_domain}, creds: {creds_domain}")
        except Exception as e:
            print(f"[FETCH] WordPress fetch error: {e}")
            logger.warning("wp_fetch_failed_in_fetch", extra={"error": str(e)})

    # Step 2: Fetch the actual image file
    try:
        import httpx
        from PIL import Image as PILImage
        import io as pio

        start_time = time.time()
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(image_url)

        load_time_ms = int((time.time() - start_time) * 1000)
        http_status = response.status_code

        width, height, fmt, content_hash, file_size_bytes = None, None, "unknown", None, None

        if response.status_code < 400:
            content = response.content
            file_size_bytes = len(content)
            content_hash = hashlib.md5(content).hexdigest()

            try:
                img = PILImage.open(pio.BytesIO(content))
                width, height = img.size
                fmt = img.format.lower() if img.format else "unknown"
            except Exception:
                pass

        # Update the stored image with fetched data
        image.width = width
        image.height = height
        image.format = fmt
        image.file_size_bytes = file_size_bytes
        image.load_time_ms = load_time_ms
        image.http_status = http_status
        image.content_hash = content_hash
        image.data_source = "full_fetch"

        # Step 3: Re-analyze with ALL new data (including WP metadata if fetched)
        from api.crawler.image_analyzer import analyze_image
        issues, scores = analyze_image(image, job_id=job_id)
        image.performance_score = scores["performance_score"]
        image.accessibility_score = scores["accessibility_score"]
        image.semantic_score = scores["semantic_score"]
        image.technical_score = scores["technical_score"]
        image.overall_score = scores["overall_score"]
        image.issues = [i.code for i in issues]

        print(f"\n[FETCH] Before Save to DB:")
        print(f"  - Image URL: {image.url}")
        print(f"  - Alt text to save: '{image.alt}'")
        print(f"  - Title to save: '{image.title}'")
        print(f"  - Overall score: {image.overall_score}")
        print(f"  - Issues: {image.issues}")

        # Save updated image
        await store.save_images([image])

        print(f"\n[FETCH] After Save - verifying:")
        print(f"  - Image URL in object: {image.url}")
        print(f"  - Alt text in object: '{image.alt}'")

        result_image = _image_dict(image)
        print(f"\n[FETCH] Returning to frontend:")
        print(f"  - URL: {result_image['url']}")
        print(f"  - Alt: '{result_image['alt']}'")
        print(f"  - Overall score: {result_image['overall_score']}")
        print(f"{'='*80}\n")

        return {
            "job_id": job_id,
            "fetched": True,
            "wp_metadata_fetched": wp_fetch_success,
            "image": result_image,
        }

    except Exception as e:
        logger.exception("image_fetch_failed", extra={"image_url": image_url})
        return _err("FETCH_FAILED", f"Failed to fetch image: {str(e)}", 500)


# ── Private helpers ────────────────────────────────────────────────────────

def _image_dict(img) -> dict:
    """Convert ImageInfo to API response dict."""
    return {
        "url": img.url,
        "page_url": img.page_url,
        "alt": img.alt,
        "title": img.title,
        "caption": img.caption,
        "description": img.description,
        "filename": img.filename,
        "format": img.format,
        "width": img.width,
        "height": img.height,
        "rendered_width": img.rendered_width,
        "rendered_height": img.rendered_height,
        "file_size_bytes": img.file_size_bytes,
        "file_size_kb": round(img.file_size_bytes / 1024, 1) if img.file_size_bytes else None,
        "load_time_ms": img.load_time_ms,
        "http_status": img.http_status,
        "is_lazy_loaded": img.is_lazy_loaded,
        "has_srcset": img.has_srcset,
        "srcset_candidates": img.srcset_candidates,
        "surrounding_text": img.surrounding_text,
        "is_decorative": img.is_decorative,
        "content_hash": img.content_hash,
        "performance_score": img.performance_score,
        "accessibility_score": img.accessibility_score,
        "semantic_score": img.semantic_score,
        "technical_score": img.technical_score,
        "overall_score": img.overall_score,
        "issues": img.issues,
        "data_source": img.data_source,
        # GEO AI fields (v1.9geo)
        "long_description": img.long_description,
        "geo_entities_detected": img.geo_entities_detected,
        "geo_location_used": img.geo_location_used,
        "ai_analysis_metadata": img.ai_analysis_metadata,
    }


def _csv_response(issues: list[Issue], filename: str) -> StreamingResponse:
    def generate():
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        yield buf.getvalue()

        for issue in issues:
            buf.seek(0)
            buf.truncate()
            writer.writerow({
                "url": issue.page_url or "",
                "issue_code": issue.issue_code,
                "severity": issue.severity,
                "category": issue.category,
                "phase": "1" if issue.category in PHASE_1_CATEGORIES else "2",
                "description": issue.description,
                "recommendation": issue.recommendation,
            })
            yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{job_id}/images/analyze-ai")
async def analyze_image_with_ai_endpoint(
    job_id: str,
    image_url: str = Query(..., description="URL of the image to analyze"),
    store=Depends(get_store)
):
    """
    Analyze an image using AI vision models (Gemini Vision or GPT-4V).

    Updates the image's semantic_score and issues based on AI analysis.
    """
    from api.services.ai_analyzer import analyze_image_with_ai

    # Get current image data
    image = await store.get_image_by_url(job_id, image_url)
    if not image:
        return {"error": f"Image not found: {image_url}"}

    # Analyze with AI
    analysis = await analyze_image_with_ai(image_url, image.alt or "")

    # Update image with AI analysis results
    image.semantic_score = analysis["semantic_score"]

    # Add AI-generated issues if accuracy or quality is low
    new_issues = []
    if analysis["accuracy_score"] < 70:
        new_issues.append("IMG_ALT_INACCURATE")
    if analysis["quality_score"] < 70:
        new_issues.append("IMG_ALT_LOW_QUALITY")

    # Merge with existing issues (avoid duplicates)
    existing_issues = set(image.issues)
    for issue in new_issues:
        if issue not in existing_issues:
            image.issues.append(issue)

    # Save updated image
    await store.save_images([image])

    return {
        "image_url": image_url,
        "analysis": analysis,
        "updated_scores": {
            "semantic_score": image.semantic_score,
            "overall_score": image.overall_score
        }
    }


@router.api_route("/{job_id}/export/ai-images-pdf", methods=["GET", "POST"])
async def export_ai_analysis_pdf(
    job_id: str,
    request: Request,
    store=Depends(get_store)
):
    """Export AI image analysis results as a detailed PDF."""
    from fpdf import FPDF
    from urllib.parse import unquote

    def clean_text(text: str) -> str:
        """Clean text for Latin-1 PDF encoding."""
        if not text:
            return ""
        # Convert to string and replace non-Latin-1 characters
        text = str(text)
        return text.encode('latin-1', errors='ignore').decode('latin-1')

    def clean_filename(url: str) -> str:
        """Extract and decode filename from URL."""
        if not url:
            return "Unknown"
        # Get last part of URL
        filename = url.split('/')[-1]
        # URL decode (converts %20 to space, %2B to +, etc.)
        filename = unquote(filename)
        # Replace + with space (sometimes used in URLs)
        filename = filename.replace('+', ' ')
        # Clean for Latin-1
        return clean_text(filename)

    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", "Job not found", 404)

    # Check if we have AI results from POST
    ai_results = None
    if request.method == "POST":
        try:
            body = await request.json()
            ai_results = body.get("ai_results", [])
            # Debug logging
            if ai_results:
                print(f"[PDF Export] Received {len(ai_results)} AI results")
                if ai_results:
                    first = ai_results[0]
                    print(f"[PDF Export] First result keys: {list(first.keys())}")
                    if "analysis" in first:
                        print(f"[PDF Export] Analysis keys: {list(first['analysis'].keys())}")
                        print(f"[PDF Export] Accuracy score: {first['analysis'].get('accuracy_score')}")
        except Exception as e:
            print(f"[PDF Export] Error parsing POST body: {e}")
            import traceback
            traceback.print_exc()
            pass

    # Get all images (returns list of ImageInfo objects)
    all_images = await store.get_images(job_id, page=1, limit=1000, sort_by="score")

    # Create PDF with detailed AI analysis
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'AI Image Analysis Results', ln=True, align='C')
    pdf.ln(5)

    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f'Job: {job_id[:20]}...', ln=True)

    if ai_results:
        pdf.cell(0, 10, f'Images Analyzed: {len(ai_results)}', ln=True)
    else:
        pdf.cell(0, 10, f'Total Images: {len(all_images)}', ln=True)
    pdf.ln(5)

    # Use AI results if available, otherwise fall back to basic image data
    if ai_results:
        # Detailed AI analysis results
        for idx, result in enumerate(ai_results, 1):
            if idx > 50:  # Limit to first 50
                break

            # Filename
            pdf.set_font('Arial', 'B', 11)
            image_url = result.get("imageUrl", "")
            filename = clean_filename(image_url)[:70]
            pdf.cell(0, 7, f'{idx}. {filename}', ln=True)

            analysis = result.get("analysis", {})
            error = result.get("error")

            if error:
                pdf.set_font('Arial', 'I', 9)
                pdf.cell(0, 5, clean_text(str(error)[:100]), ln=True)
            else:
                pdf.set_font('Arial', '', 9)

                # Scores
                acc_score = int(analysis.get("accuracy_score", 0))
                qual_score = int(analysis.get("quality_score", 0))
                sem_score = int(analysis.get("semantic_score", 0))
                pdf.cell(0, 5, f'Accuracy: {acc_score}/100  |  Quality: {qual_score}/100  |  Semantic: {sem_score}/100', ln=True)

                # Description
                description = clean_text(analysis.get("description", "N/A"))
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 5, 'AI Description:', ln=True)
                pdf.set_font('Arial', '', 8)
                # Split into lines manually to avoid multi_cell issues
                words = description.split()
                line = ""
                for word in words:
                    if len(line + " " + word) > 90:
                        pdf.cell(0, 4, line, ln=True)
                        line = word
                    else:
                        line = line + " " + word if line else word
                if line:
                    pdf.cell(0, 4, line, ln=True)

                # Suggested Alt Text
                suggested = clean_text(analysis.get("suggested_alt", "N/A"))
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 5, 'Suggested Alt:', ln=True)
                pdf.set_font('Arial', 'I', 8)
                pdf.cell(0, 4, f'"{suggested[:120]}"', ln=True)

                # Issues
                issues = analysis.get("issues", [])
                if issues:
                    pdf.set_font('Arial', '', 8)
                    issue_text = ", ".join(str(i) for i in issues[:5])
                    pdf.cell(0, 4, f'Issues: {issue_text}', ln=True)

            pdf.ln(4)
    else:
        # Fallback to basic image data
        for idx, img in enumerate(all_images, 1):
            if idx > 50:  # Limit to first 50
                break

            pdf.set_font('Arial', 'B', 11)
            filename = clean_text(img.filename or "Unknown")[:50]
            pdf.cell(0, 8, f'{idx}. {filename}', ln=True)

            pdf.set_font('Arial', '', 9)
            sem_score = int(img.semantic_score)
            overall_score = int(img.overall_score)
            pdf.cell(0, 6, f'   Semantic: {sem_score}/100  Overall: {overall_score}/100', ln=True)

            alt_text = clean_text(img.alt or "(none)")[:80]
            pdf.cell(0, 6, f'   Alt: {alt_text}', ln=True)
            pdf.ln(2)

    # Generate PDF bytes
    pdf_bytes = pdf.output()
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode('latin-1')

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="AI-Analysis-{job_id[:8]}.pdf"'}
    )

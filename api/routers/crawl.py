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
from api.models.page import CrawledPage
from api.services.auth import require_auth
from api.services.job_store import SQLiteJobStore, RedisJobStore
from api.services.rate_limiter import CRAWL_START_LIMIT, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawl", dependencies=[Depends(require_auth)])

# Valid category slugs for the filtered results endpoint
_VALID_CATEGORIES: frozenset[str] = frozenset(
    ["broken_link", "metadata", "heading", "redirect",
     "crawlability", "duplicate", "sitemap", "security", "url_structure"]
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

        async def on_progress(p: dict) -> None:
            await store.update_job(
                job_id,
                pages_crawled=p["pages_crawled"],
                pages_total=p["pages_total"],
                current_url=p["current_url"],
            )

        result: CrawlResult = await run_crawl(
            job_id,
            target_url,
            engine_settings,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

        pages = [_engine_page_to_model(p, job_id) for p in result.pages]
        issues = [_engine_issue_to_model(i, job_id) for i in result.issues]

        if pages:
            await store.save_pages(pages)
        if issues:
            await store.save_issues(issues)

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


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/start", status_code=202, response_model=None)
@limiter.limit(CRAWL_START_LIMIT)
async def start_crawl(
    request: Request,
    body: dict,
    background_tasks: BackgroundTasks,
    store: SQLiteJobStore | RedisJobStore = Depends(get_store),
) -> dict:
    """Submit a new crawl job (spec §6.4 POST /api/crawl/start)."""
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
    summary = await store.get_summary(job_id)
    total_pages = max(1, math.ceil(total / limit))

    return {
        "job_id": job_id,
        "summary": summary,
        "pagination": {"page": page, "limit": limit, "total_issues": total, "total_pages": total_pages},
        "issues": [_issue_dict(i) for i in issues],
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
    summary = await store.get_summary(job_id)
    total_pages = max(1, math.ceil(total / limit))

    return {
        "job_id": job_id,
        "summary": summary,
        "pagination": {"page": page, "limit": limit, "total_issues": total, "total_pages": total_pages},
        "issues": [_issue_dict(i) for i in issues],
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

    total = sum(len(v) for v in by_category.values())

    return {
        "job_id": job_id,
        "url": url,
        "status_code": crawled_page.status_code,
        "total_issues": total,
        "by_category": {
            cat: [_issue_dict(i) for i in issues]
            for cat, issues in by_category.items()
        },
    }


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

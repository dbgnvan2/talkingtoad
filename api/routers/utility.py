"""
Utility endpoints: health check, robots.txt inspection, sitemap inspection (spec §6.3).
Also: suppressed issue codes (global setting — excluded from health score calculation).
"""

import logging

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from api.services.error_responses import _err
from pydantic import BaseModel

from api.crawler.fetcher import is_ssrf_safe
from api.crawler.normaliser import is_wp_noise_path
from api.crawler.robots import fetch_robots
from api.crawler.sitemap import fetch_sitemap_recursive
from api.routers.crawl import get_store
from api.services.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

# Public router for endpoints that must not require auth (health checks, etc.)
public_router = APIRouter(prefix="/api")


class LLMSTxtSaveRequest(BaseModel):
    job_id: str
    content: str


@router.get("/utility/generate-llms-txt")
async def generate_llms_txt(
    job_id: str = Query(..., description="Job ID to generate llms.txt from"),
    store=Depends(get_store),
):
    """Generate or retrieve an llms.txt formatted Markdown file from crawl data (spec §2.2)."""
    job = await store.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    # If we already have a custom one saved, return it
    if job.llms_txt_custom:
        return {
            "job_id": job_id,
            "content": job.llms_txt_custom,
            "filename": "llms.txt",
            "is_custom": True
        }

    pages = await store.get_pages(job_id)
    if not pages:
        return JSONResponse(status_code=404, content={"error": "No pages found for this job"})

    # Filter out WordPress noise and non-indexable pages
    valid_pages = [
        p for p in pages
        if p.is_indexable and p.status_code == 200 and not is_wp_noise_path(p.url)
    ]

    # Find homepage for summary
    homepage = next((p for p in valid_pages if p.crawl_depth == 0), None)
    if not homepage and valid_pages:
        homepage = valid_pages[0]

    title = homepage.title if homepage else "Website Content"
    summary = homepage.meta_description if homepage else "A collection of high-value pages."

    # Sort by crawl_depth (asc) and then by link count (desc)
    valid_pages.sort(key=lambda p: (p.crawl_depth or 99, -(len(p.h1_tags) + (p.word_count or 0) // 100)))

    # Limit to top 20 high-value links as per spec
    top_pages = valid_pages[:20]

    # Format as Markdown
    lines = [
        f"# {title}",
        "",
        f"> {summary}",
        "",
    ]
    for p in top_pages:
        p_title = p.title or p.url
        lines.append(f"- [{p_title}]({p.url})")

    return {
        "job_id": job_id,
        "content": "\n".join(lines),
        "filename": "llms.txt",
        "is_custom": False
    }


@router.post("/utility/save-llms-txt")
async def save_llms_txt(
    body: LLMSTxtSaveRequest,
    store=Depends(get_store),
):
    """Persist a custom llms.txt content for a job."""
    await store.update_job(body.job_id, llms_txt_custom=body.content)
    return {"success": True, "job_id": body.job_id}


@public_router.get("/health")
async def health() -> dict:
    """Health check endpoint (spec §6.3). No auth required."""
    return {"status": "ok", "version": "3.0.0"}


@router.get("/robots")
async def robots_check(url: str = Query(..., description="Base URL of the site to inspect")):
    """Fetch and parse robots.txt for the given domain (spec §6.3)."""
    # v2.3 (M0.6.8) SSRF guard: this endpoint accepts an arbitrary user URL and
    # fetches its robots.txt via httpx — without this check a post-auth user
    # could pivot to localhost/AWS-metadata.
    if not is_ssrf_safe(url):
        logger.warning("robots_check_ssrf_blocked", extra={"url": url})
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "SSRF_BLOCKED",
                    "message": "URL resolves to a private/internal address.",
                    "http_status": 400,
                }
            },
        )
    try:
        async with httpx.AsyncClient() as client:
            data = await fetch_robots(url, client)
    except Exception as exc:
        logger.warning("robots_check_error", extra={"url": url, "error": str(exc)})
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "TARGET_UNREACHABLE",
                    "message": f"Could not fetch robots.txt for {url}: {exc}",
                    "http_status": 502,
                }
            },
        )

    return {
        "url": url,
        "crawl_delay": data.crawl_delay,
        "sitemap_urls": data.sitemap_urls,
        "raw_text": data.raw_text,
    }


@router.get("/sitemap")
async def sitemap_check(url: str = Query(..., description="Base URL of the site to inspect")):
    """Discover and parse the sitemap for the given domain (spec §6.3)."""
    # v2.3 (M0.6.8) SSRF guard — same rationale as /robots.
    if not is_ssrf_safe(url):
        logger.warning("sitemap_check_ssrf_blocked", extra={"url": url})
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "SSRF_BLOCKED",
                    "message": "URL resolves to a private/internal address.",
                    "http_status": 400,
                }
            },
        )
    try:
        async with httpx.AsyncClient() as client:
            result = await fetch_sitemap_recursive(url, client)
    except Exception as exc:
        logger.warning("sitemap_check_error", extra={"url": url, "error": str(exc)})
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "TARGET_UNREACHABLE",
                    "message": f"Could not fetch sitemap for {url}: {exc}",
                    "http_status": 502,
                }
            },
        )

    if not result.found:
        return {
            "url": url,
            "found": False,
            "source_url": None,
            "url_count": 0,
            "urls": [],
        }

    return {
        "url": url,
        "found": True,
        "source_url": result.source_url,
        "url_count": len(result.urls),
        "urls": result.urls,
    }


# ── Suppressed issue codes ─────────────────────────────────────────────────


class SuppressRequest(BaseModel):
    code: str


@router.get("/suppressed-codes")
async def list_suppressed_codes(store=Depends(get_store)) -> list[str]:
    """Return all issue codes currently suppressed from the health score."""
    return await store.get_suppressed_codes()


@router.post("/suppressed-codes")
async def suppress_code(body: SuppressRequest, store=Depends(get_store)) -> dict:
    """Add an issue code to the suppressed list. Health score ignores its impact."""
    await store.add_suppressed_code(body.code.strip().upper())
    return {"code": body.code.strip().upper(), "status": "suppressed"}


@router.delete("/suppressed-codes")
async def unsuppress_code(
    code: str = Query(..., description="Issue code to remove from suppressed list"),
    store=Depends(get_store),
) -> dict:
    """Remove an issue code from the suppressed list."""
    await store.remove_suppressed_code(code.strip().upper())
    return {"code": code.strip().upper(), "status": "unsuppressed"}


# ── F1: per-domain issue filter ────────────────────────────────────────────
#
# PRESENTATIONAL ONLY. This hides findings from the results lists; it never
# touches the health score. That is the whole difference from the suppressed
# codes above, which change scoring by design — see docs/functional-specification.md (F1).


class DomainFilterRequest(BaseModel):
    domain: str
    issue_code: str | None = None
    severity: str | None = None


def _validate_filter_rule(body: "DomainFilterRequest") -> JSONResponse | None:
    """Reject rules that cannot do what the operator expects.

    An unknown code accepted silently is a filter that never fires, and the
    operator has no way to tell that from a filter that fires and finds
    nothing. The severity allowlist is derived from the catalogue rather than
    written out, so it cannot drift away from the real severities.
    """
    from api.crawler.checkers.registry import _CATALOGUE

    has_code = bool(body.issue_code)
    has_sev = bool(body.severity)
    if has_code == has_sev:
        return _err(
            "INVALID_RULE",
            "A filter rule must name exactly one of issue_code or severity.",
            422,
        )
    if has_code and body.issue_code.strip().upper() not in _CATALOGUE:
        return _err(
            "UNKNOWN_ISSUE_CODE",
            f"No such issue code: {body.issue_code}. A filter naming a code "
            "that does not exist would never fire.",
            404,
        )
    if has_sev:
        valid = {s.severity for s in _CATALOGUE.values()}
        if body.severity.strip().lower() not in valid:
            return _err(
                "UNKNOWN_SEVERITY",
                f"No such severity: {body.severity}. Valid: {sorted(valid)}.",
                422,
            )
    return None


@router.get("/domain-filters")
async def list_domain_filters(
    domain: str = Query(..., description="Site host or URL; normalised server-side"),
    store=Depends(get_store),
) -> dict:
    """Return the filter rules for one domain."""
    from api.services.domain_filter import normalise_filter_domain
    return {
        "domain": normalise_filter_domain(domain),
        "rules": await store.get_domain_filters(domain),
    }


@router.post("/domain-filters", response_model=None)
async def add_domain_filter(
    body: DomainFilterRequest, store=Depends(get_store)
) -> dict | JSONResponse:
    """Add one filter rule for a domain. Hides findings; never changes the score."""
    err = _validate_filter_rule(body)
    if err is not None:
        return err
    code = body.issue_code.strip().upper() if body.issue_code else None
    sev = body.severity.strip().lower() if body.severity else None
    await store.add_domain_filter(body.domain, issue_code=code, severity=sev)
    from api.services.domain_filter import normalise_filter_domain
    return {"domain": normalise_filter_domain(body.domain),
            "issue_code": code, "severity": sev, "status": "filtered"}


@router.delete("/domain-filters", response_model=None)
async def remove_domain_filter(
    domain: str = Query(...),
    issue_code: str | None = Query(None),
    severity: str | None = Query(None),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Remove one filter rule."""
    code = issue_code.strip().upper() if issue_code else None
    sev = severity.strip().lower() if severity else None
    if bool(code) == bool(sev):
        return _err("INVALID_RULE",
                    "Name exactly one of issue_code or severity.", 422)
    await store.remove_domain_filter(domain, issue_code=code, severity=sev)
    from api.services.domain_filter import normalise_filter_domain
    return {"domain": normalise_filter_domain(domain),
            "issue_code": code, "severity": sev, "status": "unfiltered"}


# ── Exempt anchor URLs ─────────────────────────────────────────────────────


class ExemptAnchorRequest(BaseModel):
    url: str
    note: str = ""


@router.get("/exempt-anchor-urls")
async def list_exempt_anchor_urls(store=Depends(get_store)) -> list[dict]:
    """Return all URLs exempt from LINK_EMPTY_ANCHOR checks."""
    return await store.get_exempt_anchor_urls()


@router.post("/exempt-anchor-urls")
async def add_exempt_anchor_url(body: ExemptAnchorRequest, store=Depends(get_store)) -> dict:
    """Add a URL to the exempt list. Future crawls will ignore empty anchor text on this URL."""
    url = body.url.strip()
    if not url:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "EMPTY_URL", "message": "URL cannot be empty.", "http_status": 400}},
        )
    await store.add_exempt_anchor_url(url, body.note)
    return {"url": url, "note": body.note, "status": "exempted"}


@router.delete("/exempt-anchor-urls")
async def remove_exempt_anchor_url(
    url: str = Query(..., description="URL to remove from exempt list"),
    store=Depends(get_store),
) -> dict:
    """Remove a URL from the exempt list."""
    await store.remove_exempt_anchor_url(url.strip())
    return {"url": url.strip(), "status": "removed"}


# ── Ignored image patterns ─────────────────────────────────────────────────


class IgnoredImageRequest(BaseModel):
    pattern: str
    note: str = ""


@router.get("/ignored-image-patterns")
async def list_ignored_image_patterns(store=Depends(get_store)) -> list[dict]:
    """Return all ignored image URL patterns."""
    return await store.get_ignored_image_patterns()


@router.post("/ignored-image-patterns")
async def add_ignored_image_pattern(body: IgnoredImageRequest, store=Depends(get_store)) -> dict:
    """Add a URL pattern to the ignored list. Images matching this pattern
    will be excluded from IMG_ALT_MISSING and other image issue checks.
    Matching is by substring — e.g. '/location.svg' matches any URL containing that string."""
    pattern = body.pattern.strip()
    if not pattern:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "EMPTY_PATTERN", "message": "Pattern cannot be empty.", "http_status": 400}},
        )
    await store.add_ignored_image_pattern(pattern, body.note)
    return {"pattern": pattern, "note": body.note, "status": "added"}


@router.delete("/ignored-image-patterns")
async def remove_ignored_image_pattern(
    pattern: str = Query(..., description="Pattern to remove from ignored list"),
    store=Depends(get_store),
) -> dict:
    """Remove a pattern from the ignored list."""
    await store.remove_ignored_image_pattern(pattern.strip())
    return {"pattern": pattern.strip(), "status": "removed"}

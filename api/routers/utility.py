"""
Utility endpoints: health check, robots.txt inspection, sitemap inspection (spec §6.3).
Also: suppressed issue codes (global setting — excluded from health score calculation).
"""

import logging

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.crawler.normaliser import is_wp_noise_path
from api.crawler.robots import fetch_robots
from api.crawler.sitemap import fetch_sitemap_recursive
from api.routers.crawl import get_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/utility/generate-llms-txt")
async def generate_llms_txt(
    job_id: str = Query(..., description="Job ID to generate llms.txt from"),
    store=Depends(get_store),
):
    """Generate an llms.txt formatted Markdown file from crawl data (spec §2.2)."""
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
    # We want shallow pages with many links first
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
        "filename": "llms.txt"
    }


@router.get("/health")
async def health() -> dict:
    """Health check endpoint (spec §6.3)."""
    return {"status": "ok", "version": "1.7"}


@router.get("/robots")
async def robots_check(url: str = Query(..., description="Base URL of the site to inspect")):
    """Fetch and parse robots.txt for the given domain (spec §6.3)."""
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

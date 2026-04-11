"""
Utility endpoints: health check, robots.txt inspection, sitemap inspection (spec §6.3).
"""

import logging

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from api.crawler.robots import fetch_robots
from api.crawler.sitemap import fetch_sitemap_recursive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict:
    """Health check endpoint (spec §6.3)."""
    return {"status": "ok", "version": "1.4"}


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

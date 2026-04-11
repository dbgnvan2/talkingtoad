"""
CrawledPage Pydantic model (spec §5.2).

Phase 2 fields are collected during the Phase 1 crawl and stored immediately,
but are suppressed from the UI and CSV until Phase 2 is released.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


class CrawledPage(BaseModel):
    """All data extracted from a single crawled page (spec §5.2)."""

    page_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str

    # Request / response
    url: str
    status_code: int
    redirect_url: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    response_size_bytes: int = 0
    crawled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadata
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    has_favicon: bool | None = None   # true/false on homepage; null elsewhere

    # Headings
    h1_tags: list[str] = Field(default_factory=list)
    headings_outline: list[dict] = Field(default_factory=list)

    # Crawlability
    is_indexable: bool = True
    robots_directive: str | None = None

    # Phase 2 — collected now, surfaced later
    has_viewport_meta: bool = False
    schema_types: list[str] = Field(default_factory=list)
    external_script_count: int | None = None
    external_stylesheet_count: int | None = None

    # v1.5 extension fields
    word_count: int | None = None
    crawl_depth: int | None = None
    pagination_next: str | None = None
    pagination_prev: str | None = None
    amphtml_url: str | None = None
    meta_refresh_url: str | None = None
    mixed_content_count: int = 0
    unsafe_cross_origin_count: int = 0
    has_hsts: bool | None = None

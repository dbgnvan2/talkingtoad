"""
CrawlJob Pydantic models (spec §5.1).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class CrawlSettings(BaseModel):
    """Per-job crawler configuration (spec §5.1)."""

    max_pages: int = Field(default=500, ge=1, le=10_000)
    crawl_delay_ms: int = Field(default=500, ge=200)
    respect_robots: bool = True
    include_subdomains: list[str] = Field(default_factory=list)
    # Analysis toggles (v1.3 §3.1) — None means all categories enabled.
    # Accepted group names: "link_integrity", "seo_essentials",
    # "site_structure", "indexability". Each maps to a set of issue categories.
    enabled_analyses: list[str] | None = None
    # Image size threshold in KB — images larger than this are flagged as IMG_OVERSIZED.
    img_size_limit_kb: int = Field(default=200, ge=10, le=10_000)
    # H1 strings to suppress from heading checks — useful for theme-injected headings
    # (e.g. a sidebar or page-header template that repeats the same H1 on every post).
    suppress_h1_strings: list[str] = Field(default_factory=list)
    # When True, any H1 that shares no significant words with the page title is
    # treated as a banner/navigation heading and ignored in all H1 checks.
    # Handles themes (Salient, Avada, Divi, etc.) that inject a parent-page title
    # as an H1 banner on every sub-page without requiring explicit suppress strings.
    suppress_banner_h1: bool = False


JobStatus = Literal["queued", "running", "complete", "failed", "cancelled"]


class CrawlJob(BaseModel):
    """Persistent state for a single crawl job (spec §5.1)."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    target_url: str
    sitemap_url: str | None = None
    status: JobStatus = "queued"
    pages_crawled: int = 0
    pages_total: int | None = None
    current_url: str | None = None   # most recently fetched URL (for progress display)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error_message: str | None = None
    settings: CrawlSettings = Field(default_factory=CrawlSettings)

"""
Job store protocol and shared utilities.

Defines the JobStore interface that all implementations (SQLite, Redis) must follow,
plus shared helper functions and database schema.
"""

from __future__ import annotations

import aiosqlite
import logging
from typing import Any, Protocol, runtime_checkable

from api.models.geo_config import GeoConfig
from api.models.image import ImageInfo
from api.models.issue import Issue, IssueCategory, PHASE_1_CATEGORIES
from api.models.job import CrawlJob, CrawlSettings, JobStatus
from api.models.link import Link
from api.models.page import CrawledPage

logger = logging.getLogger(__name__)

_DEFAULT_TTL_DAYS = 7
_DEFAULT_SQLITE_PATH = "./talkingtoad.db"

# SQL expressions for ordering issues by severity and priority (impact)
_SEVERITY_ORDER = "CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 WHEN 'info' THEN 3 ELSE 4 END"
_PRIORITY_ORDER = "CASE WHEN impact IS NOT NULL THEN -impact ELSE 0 END"


def _density_health_score(by_severity: dict[str, int], pages_crawled: int) -> int:
    """Fallback density-based score used when impact data is unavailable (pre-v1.5 crawls).

    Deducts points based on issue density per page:
      - Critical density × 50 (max −50)
      - Warning  density × 30 (max −30)
      - Info     density × 10 (max −10)
    """
    pages = max(1, pages_crawled)
    c_density = min(1.0, by_severity.get("critical", 0) / pages)
    w_density = min(1.0, by_severity.get("warning",  0) / pages)
    i_density = min(1.0, by_severity.get("info",     0) / pages)
    deduction = round((c_density * 50) + (w_density * 30) + (i_density * 10))
    return max(0, 100 - deduction)


async def _compute_v15_health_score(
    db: aiosqlite.Connection,
    job_id: str,
    by_severity: dict[str, int],
    pages_crawled: int,
    suppressed_codes: set[str] | None = None,
) -> tuple[int, int]:
    """Compute v1.5 page and site health scores (spec §4.1 v1.5).

    Page Health = max(0, 100 − Σ(impact of all issues on that page)).
    Site Health = average of all page health scores (pages with no issues score 100).

    Issues whose issue_code is in *suppressed_codes* are excluded from the score.

    Falls back to the density-based formula when all impact values are zero,
    which happens for jobs crawled before the v1.5 scoring data was introduced.

    Returns (site_health_score, page_count).
    """
    # Sum of impacts per page that has issues, excluding suppressed codes.
    # Normalize trailing slashes so issues and pages always match.
    if suppressed_codes:
        placeholders = ",".join("?" * len(suppressed_codes))
        sql = f"""
            SELECT RTRIM(page_url, '/') AS norm_url, SUM(impact) AS total_impact
            FROM issues
            WHERE job_id = ? AND page_url IS NOT NULL
              AND issue_code NOT IN ({placeholders})
            GROUP BY norm_url
        """
        params: tuple = (job_id, *suppressed_codes)
    else:
        sql = """
            SELECT RTRIM(page_url, '/') AS norm_url, SUM(impact) AS total_impact
            FROM issues
            WHERE job_id = ? AND page_url IS NOT NULL
            GROUP BY norm_url
        """
        params = (job_id,)

    async with db.execute(sql, params) as cursor:
        impact_rows = await cursor.fetchall()

    # If all impacts are 0 but issues exist, this is a pre-v1.5 crawl — use fallback formula
    total_impact_sum = sum(r[1] for r in impact_rows)
    total_issues = sum(by_severity.values())
    if total_issues > 0 and total_impact_sum == 0:
        score = _density_health_score(by_severity, pages_crawled)
        return score, pages_crawled

    impact_by_url: dict[str, int] = {r[0]: r[1] for r in impact_rows}

    # All crawled pages for this job
    async with db.execute(
        "SELECT url FROM crawled_pages WHERE job_id = ?",
        (job_id,),
    ) as cursor:
        page_rows = await cursor.fetchall()

    if not page_rows:
        return 100, 0

    page_scores = []
    for (url,) in page_rows:
        # Normalize trailing slash to match issue page_url
        norm_url = url.rstrip("/")
        total_impact = impact_by_url.get(norm_url, 0)
        page_health = max(0, 100 - total_impact)
        page_scores.append(page_health)

    site_health = round(sum(page_scores) / len(page_scores))
    return site_health, len(page_scores)


@runtime_checkable
class JobStore(Protocol):
    """Async interface for job persistence."""

    async def init(self) -> None: ...
    async def close(self) -> None: ...

    async def create_job(self, job: CrawlJob) -> None: ...
    async def get_job(self, job_id: str) -> CrawlJob | None: ...
    async def update_job(self, job_id: str, **fields: Any) -> None: ...
    async def list_recent_jobs(self, limit: int = 10) -> list[CrawlJob]: ...
    async def list_jobs_by_domain(self, domain: str, limit: int = 10) -> list[CrawlJob]: ...

    async def save_pages(self, pages: list[CrawledPage]) -> None: ...
    async def get_pages(self, job_id: str) -> list[CrawledPage]: ...
    async def save_issues(self, issues: list[Issue]) -> None: ...
    async def save_links(self, links: list[Link]) -> None: ...
    async def get_links_by_target(self, job_id: str, target_url: str) -> list[dict]: ...
    async def delete_issues_for_url(self, job_id: str, page_url: str) -> int: ...
    async def delete_issues_by_code_and_url(self, job_id: str, issue_code: str, page_url: str) -> int: ...
    async def update_issue_extra(self, job_id: str, issue_code: str, page_url: str, extra: dict) -> bool: ...
    async def delete_broken_link_issues_for_source(self, job_id: str, source_url: str) -> int: ...
    async def get_broken_link_codes_for_source(self, job_id: str, source_url: str) -> set[str]: ...

    async def get_issues(
        self,
        job_id: str,
        *,
        category: str | None = None,
        severity: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Issue], int]: ...

    async def get_summary(self, job_id: str) -> dict: ...
    async def get_pages(self, job_id: str) -> list[CrawledPage]: ...
    async def get_all_issues(self, job_id: str) -> list[Issue]: ...

    async def get_pages_with_issue_counts(
        self,
        job_id: str,
        *,
        min_severity: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[dict], int]: ...

    async def get_page_issues_by_url(
        self, job_id: str, url: str
    ) -> tuple[CrawledPage | None, dict[str, list[Issue]]]: ...

    async def cleanup_expired_jobs(self) -> int: ...

    # Fix Manager
    async def save_fixes(self, fixes: list[dict]) -> None: ...
    async def get_fixes(self, job_id: str) -> list[dict]: ...
    async def get_fixes_by_id(self, fix_id: str) -> list[dict]: ...
    async def update_fix(self, fix_id: str, **fields: Any) -> None: ...
    async def delete_fixes(self, job_id: str) -> None: ...
    async def get_wp_post_cache(self, urls: list[str]) -> dict[str, dict]: ...
    async def save_wp_post_cache(self, entries: dict[str, dict]) -> None: ...

    # Verified links
    async def get_verified_links(self) -> list[dict]: ...
    async def add_verified_link(self, url: str) -> str: ...
    async def remove_verified_link(self, url: str) -> bool: ...
    async def get_verified_link_urls(self) -> set[str]: ...

    # Fix history
    async def record_fixed_issues(self, job_id: str, page_url: str, codes: list[str]) -> None: ...
    async def get_fix_history(self, job_id: str) -> list[dict]: ...

    # Image analysis (v1.9image)
    async def save_images(self, images: list[ImageInfo]) -> None: ...
    async def get_images(
        self,
        job_id: str,
        *,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "score",
    ) -> list[ImageInfo]: ...
    async def get_image_summary(self, job_id: str) -> dict: ...
    async def get_image_by_url(self, job_id: str, url: str) -> ImageInfo | None: ...

    # GEO configuration (v1.9geo)
    async def save_geo_config(self, config: Any) -> None: ...
    async def get_geo_config(self, domain: str) -> Any: ...
    async def delete_geo_config(self, domain: str) -> bool: ...


# Database schema and SQL constants
SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_jobs (
    job_id          TEXT PRIMARY KEY,
    target_url      TEXT NOT NULL,
    sitemap_url     TEXT,
    status          TEXT NOT NULL DEFAULT 'queued',
    pages_crawled   INTEGER NOT NULL DEFAULT 0,
    pages_total     INTEGER,
    current_url     TEXT,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    error_message   TEXT,
    settings_json   TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS crawled_pages (
    page_id                    TEXT PRIMARY KEY,
    job_id                     TEXT NOT NULL,
    url                        TEXT NOT NULL,
    status_code                INTEGER NOT NULL,
    redirect_url               TEXT,
    redirect_chain_json        TEXT NOT NULL DEFAULT '[]',
    title                      TEXT,
    meta_description           TEXT,
    canonical_url              TEXT,
    og_title                   TEXT,
    og_description             TEXT,
    has_favicon                INTEGER,
    h1_tags_json               TEXT NOT NULL DEFAULT '[]',
    headings_outline_json      TEXT NOT NULL DEFAULT '[]',
    is_indexable               INTEGER NOT NULL DEFAULT 1,
    robots_directive           TEXT,
    response_size_bytes        INTEGER NOT NULL DEFAULT 0,
    crawled_at                 TEXT NOT NULL,
    has_viewport_meta          INTEGER NOT NULL DEFAULT 0,
    schema_types_json          TEXT NOT NULL DEFAULT '[]',
    external_script_count      INTEGER,
    external_stylesheet_count  INTEGER,
    word_count                 INTEGER,
    crawl_depth                INTEGER,
    pagination_next            TEXT,
    pagination_prev            TEXT,
    amphtml_url                TEXT,
    meta_refresh_url           TEXT,
    mixed_content_count        INTEGER NOT NULL DEFAULT 0,
    unsafe_cross_origin_count  INTEGER NOT NULL DEFAULT 0,
    has_hsts                   INTEGER,
    text_to_html_ratio         REAL,
    has_json_ld                INTEGER NOT NULL DEFAULT 0,
    pdf_metadata_json          TEXT,
    image_urls_json            TEXT,
    FOREIGN KEY (job_id) REFERENCES crawl_jobs(job_id)
);

CREATE TABLE IF NOT EXISTS issues (
    issue_id        TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    page_id         TEXT,
    page_url        TEXT,
    link_id         TEXT,
    category        TEXT NOT NULL,
    severity        TEXT NOT NULL,
    issue_code           TEXT NOT NULL,
    description          TEXT NOT NULL,
    recommendation       TEXT NOT NULL,
    impact               INTEGER NOT NULL DEFAULT 0,
    priority_rank        INTEGER NOT NULL DEFAULT 0,
    effort               INTEGER NOT NULL DEFAULT 0,
    human_description    TEXT NOT NULL DEFAULT '',
    what_it_is           TEXT,
    impact_desc          TEXT,
    how_to_fix           TEXT,
    extra                TEXT,
    fixability           TEXT NOT NULL DEFAULT 'developer_needed',
    FOREIGN KEY (job_id) REFERENCES crawl_jobs(job_id)
);

CREATE TABLE IF NOT EXISTS links (
    link_id         TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    target_url      TEXT NOT NULL,
    link_text       TEXT,
    link_type       TEXT NOT NULL,
    status_code     INTEGER,
    is_broken       INTEGER NOT NULL DEFAULT 0,
    check_skipped   INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (job_id) REFERENCES crawl_jobs(job_id)
);

CREATE TABLE IF NOT EXISTS fixes (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    issue_code      TEXT NOT NULL,
    page_url        TEXT NOT NULL,
    wp_post_id      INTEGER,
    wp_post_type    TEXT,
    field           TEXT NOT NULL,
    label           TEXT NOT NULL,
    current_value   TEXT,
    proposed_value  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    error           TEXT,
    applied_at      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES crawl_jobs(job_id),
    UNIQUE (job_id, page_url, field)
);

CREATE TABLE IF NOT EXISTS wp_post_cache (
    page_url        TEXT PRIMARY KEY,
    wp_post_id      INTEGER NOT NULL,
    wp_post_type    TEXT NOT NULL,
    cached_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS verified_links (
    url             TEXT PRIMARY KEY,
    verified_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fixed_issues (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT NOT NULL,
    page_url     TEXT NOT NULL,
    issue_code   TEXT NOT NULL,
    fixed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES crawl_jobs(job_id)
);

CREATE TABLE IF NOT EXISTS suppressed_issue_codes (
    issue_code   TEXT PRIMARY KEY,
    suppressed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exempt_anchor_urls (
    url          TEXT PRIMARY KEY,
    note         TEXT,
    added_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ignored_image_patterns (
    pattern      TEXT PRIMARY KEY,
    note         TEXT,
    added_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS images (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                TEXT NOT NULL,
    url                   TEXT NOT NULL,
    page_url              TEXT NOT NULL,
    alt                   TEXT,
    title                 TEXT,
    filename              TEXT,
    format                TEXT,
    width                 INTEGER,
    height                INTEGER,
    rendered_width        INTEGER,
    rendered_height       INTEGER,
    file_size_bytes       INTEGER,
    load_time_ms          INTEGER,
    http_status           INTEGER,
    is_lazy_loaded        INTEGER NOT NULL DEFAULT 0,
    has_srcset            INTEGER NOT NULL DEFAULT 0,
    srcset_candidates     TEXT,
    is_decorative         INTEGER NOT NULL DEFAULT 0,
    surrounding_text      TEXT,
    content_hash          TEXT,
    performance_score     REAL NOT NULL DEFAULT 100.0,
    accessibility_score   REAL NOT NULL DEFAULT 100.0,
    semantic_score        REAL NOT NULL DEFAULT 100.0,
    technical_score       REAL NOT NULL DEFAULT 100.0,
    overall_score         REAL NOT NULL DEFAULT 100.0,
    issues                TEXT,
    data_source           TEXT NOT NULL DEFAULT 'html_only',
    long_description      TEXT,
    geo_entities_detected TEXT,
    geo_location_used     TEXT,
    ai_analysis_metadata  TEXT,
    FOREIGN KEY (job_id) REFERENCES crawl_jobs(job_id),
    UNIQUE(job_id, url)
);

CREATE TABLE IF NOT EXISTS config (
    key       TEXT PRIMARY KEY,
    value     TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issues_job_id ON issues(job_id);
CREATE INDEX IF NOT EXISTS idx_issues_job_category ON issues(job_id, category);
CREATE INDEX IF NOT EXISTS idx_issues_job_severity ON issues(job_id, severity);
CREATE INDEX IF NOT EXISTS idx_pages_job_id ON crawled_pages(job_id);
CREATE INDEX IF NOT EXISTS idx_links_job_id ON links(job_id);
CREATE INDEX IF NOT EXISTS idx_fixes_job_id ON fixes(job_id);
CREATE INDEX IF NOT EXISTS idx_images_job_id ON images(job_id);
CREATE INDEX IF NOT EXISTS idx_images_hash ON images(content_hash);
"""

SEVERITY_ORDER   = "CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END"
PRIORITY_ORDER   = "priority_rank DESC"

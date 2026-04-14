"""
Job store abstraction layer for the TalkingToad crawler.

Provides a common async interface backed by SQLite (dev) or Upstash Redis (prod).
The active backend is selected from the DATABASE_URL environment variable:
  - Not set / empty → SQLiteJobStore (local file or :memory:)
  - Starts with "redis" → RedisJobStore (Upstash, not yet implemented)

Spec §3.2 requirements implemented here:
  - Create, read, update CrawlJob
  - Store/retrieve CrawledPage, Issue, Link records per job
  - Paginated issue queries with severity and category filters
  - TTL management (RESULT_TTL_DAYS env var, default 7)
  - Job summary aggregation (by_severity, by_category counts)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

import aiosqlite

from api.models.issue import Issue, IssueCategory, PHASE_1_CATEGORIES
from api.models.job import CrawlJob, CrawlSettings, JobStatus
from api.models.link import Link
from api.models.page import CrawledPage

logger = logging.getLogger(__name__)

_DEFAULT_TTL_DAYS = int(os.getenv("RESULT_TTL_DAYS", "7"))
_DEFAULT_SQLITE_PATH = os.getenv("SQLITE_PATH", "talkingtoad.db")


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
    # Sum of impacts per page that has issues, excluding suppressed codes
    if suppressed_codes:
        placeholders = ",".join("?" * len(suppressed_codes))
        sql = f"""
            SELECT page_url, SUM(impact) AS total_impact
            FROM issues
            WHERE job_id = ? AND page_url IS NOT NULL
              AND issue_code NOT IN ({placeholders})
            GROUP BY page_url
        """
        params: tuple = (job_id, *suppressed_codes)
    else:
        sql = """
            SELECT page_url, SUM(impact) AS total_impact
            FROM issues
            WHERE job_id = ? AND page_url IS NOT NULL
            GROUP BY page_url
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
        total_impact = impact_by_url.get(url, 0)
        page_health = max(0, 100 - total_impact)
        page_scores.append(page_health)

    site_health = round(sum(page_scores) / len(page_scores))
    return site_health, len(page_scores)


# ---------------------------------------------------------------------------
# Protocol — what every store implementation must provide
# ---------------------------------------------------------------------------

@runtime_checkable
class JobStore(Protocol):
    """Async interface for job persistence."""

    async def init(self) -> None: ...
    async def close(self) -> None: ...

    async def create_job(self, job: CrawlJob) -> None: ...
    async def get_job(self, job_id: str) -> CrawlJob | None: ...
    async def update_job(self, job_id: str, **fields: Any) -> None: ...
    async def list_recent_jobs(self, limit: int = 10) -> list[CrawlJob]: ...

    async def save_pages(self, pages: list[CrawledPage]) -> None: ...
    async def get_pages(self, job_id: str) -> list[CrawledPage]: ...
    async def save_issues(self, issues: list[Issue]) -> None: ...
    async def save_links(self, links: list[Link]) -> None: ...
    async def get_links_by_target(self, job_id: str, target_url: str) -> list[dict]: ...
    async def delete_issues_for_url(self, job_id: str, page_url: str) -> int: ...
    async def delete_issues_by_code_and_url(self, job_id: str, issue_code: str, page_url: str) -> int: ...
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


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------

_SCHEMA = """
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
    has_favicon                INTEGER,   -- NULL=not checked, 0=false, 1=true
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
    extra                TEXT,
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

CREATE INDEX IF NOT EXISTS idx_issues_job_id ON issues(job_id);
CREATE INDEX IF NOT EXISTS idx_issues_job_category ON issues(job_id, category);
CREATE INDEX IF NOT EXISTS idx_issues_job_severity ON issues(job_id, severity);
CREATE INDEX IF NOT EXISTS idx_pages_job_id ON crawled_pages(job_id);
CREATE INDEX IF NOT EXISTS idx_links_job_id ON links(job_id);
CREATE INDEX IF NOT EXISTS idx_fixes_job_id ON fixes(job_id);
"""

# ORDER BY expressions
_SEVERITY_ORDER   = "CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END"
_PRIORITY_ORDER   = "priority_rank DESC"  # highest priority_rank first


class SQLiteJobStore:
    """SQLite-backed job store. Use as an async context manager or call ``init()`` manually."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def init(self) -> None:
        """Open the database and create schema if needed."""
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        await self._migrate()
        logger.info("job_store_init", extra={"db_path": self._db_path})

    async def _migrate(self) -> None:
        """Add columns introduced after initial schema creation (idempotent)."""
        page_columns = [
            ("word_count",                "INTEGER"),
            ("crawl_depth",               "INTEGER"),
            ("pagination_next",           "TEXT"),
            ("pagination_prev",           "TEXT"),
            ("amphtml_url",               "TEXT"),
            ("meta_refresh_url",          "TEXT"),
            ("mixed_content_count",       "INTEGER NOT NULL DEFAULT 0"),
            ("unsafe_cross_origin_count", "INTEGER NOT NULL DEFAULT 0"),
            ("has_hsts",                  "INTEGER"),
            ("text_to_html_ratio",        "REAL"),
            ("has_json_ld",               "INTEGER NOT NULL DEFAULT 0"),
            ("pdf_metadata_json",         "TEXT"),
            ("image_urls_json",           "TEXT"),
        ]
        for col, col_type in page_columns:
            try:
                await self._db.execute(
                    f"ALTER TABLE crawled_pages ADD COLUMN {col} {col_type}"
                )
            except Exception:
                pass  # column already exists

        issue_columns = [
            ("impact",             "INTEGER NOT NULL DEFAULT 0"),
            ("priority_rank",      "INTEGER NOT NULL DEFAULT 0"),
            ("effort",             "INTEGER NOT NULL DEFAULT 0"),
            ("human_description",  "TEXT NOT NULL DEFAULT ''"),
            ("extra",              "TEXT"),
        ]
        for col, col_type in issue_columns:
            try:
                await self._db.execute(
                    f"ALTER TABLE issues ADD COLUMN {col} {col_type}"
                )
            except Exception:
                pass  # column already exists

        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> "SQLiteJobStore":
        await self.init()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── Job CRUD ───────────────────────────────────────────────────────────

    async def create_job(self, job: CrawlJob) -> None:
        await self._db.execute(
            """
            INSERT INTO crawl_jobs
              (job_id, target_url, sitemap_url, status, pages_crawled, pages_total,
               current_url, started_at, completed_at, error_message, settings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id,
                job.target_url,
                job.sitemap_url,
                job.status,
                job.pages_crawled,
                job.pages_total,
                job.current_url,
                job.started_at.isoformat(),
                job.completed_at.isoformat() if job.completed_at else None,
                job.error_message,
                job.settings.model_dump_json(),
            ),
        )
        await self._db.commit()

    async def get_job(self, job_id: str) -> CrawlJob | None:
        async with self._db.execute(
            "SELECT * FROM crawl_jobs WHERE job_id = ?", (job_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_job(dict(row))

    async def list_recent_jobs(self, limit: int = 10) -> list[CrawlJob]:
        """Return the most recent jobs, newest first."""
        async with self._db.execute(
            "SELECT * FROM crawl_jobs ORDER BY started_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_job(dict(r)) for r in rows]

    async def update_job(self, job_id: str, **fields: Any) -> None:
        """Update specific fields on a job record.

        Accepted field names: status, pages_crawled, pages_total, current_url,
        completed_at, error_message.
        """
        if not fields:
            return

        _ALLOWED = {
            "status", "pages_crawled", "pages_total", "current_url",
            "completed_at", "error_message",
        }
        unknown = set(fields) - _ALLOWED
        if unknown:
            raise ValueError(f"update_job: unknown fields {unknown}")

        # Serialise datetime values
        serialised = {}
        for k, v in fields.items():
            if isinstance(v, datetime):
                serialised[k] = v.isoformat()
            else:
                serialised[k] = v

        set_clause = ", ".join(f"{k} = ?" for k in serialised)
        values = list(serialised.values()) + [job_id]
        await self._db.execute(
            f"UPDATE crawl_jobs SET {set_clause} WHERE job_id = ?", values
        )
        await self._db.commit()

    # ── Page storage ───────────────────────────────────────────────────────

    async def save_pages(self, pages: list[CrawledPage]) -> None:
        rows = [_page_to_row(p) for p in pages]
        await self._db.executemany(
            """
            INSERT OR REPLACE INTO crawled_pages VALUES
              (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await self._db.commit()

    async def get_pages(self, job_id: str) -> list[CrawledPage]:
        async with self._db.execute(
            "SELECT * FROM crawled_pages WHERE job_id = ?", (job_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_page(dict(r)) for r in rows]

    # ── Issue storage ──────────────────────────────────────────────────────

    async def save_issues(self, issues: list[Issue]) -> None:
        rows = [_issue_to_row(i) for i in issues]
        await self._db.executemany(
            """
            INSERT OR REPLACE INTO issues VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await self._db.commit()

    async def get_issues(
        self,
        job_id: str,
        *,
        category: str | None = None,
        severity: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Issue], int]:
        """Return (issues_on_page, total_count) with optional filters."""
        conditions = ["job_id = ?"]
        params: list[Any] = [job_id]

        if category is not None:
            conditions.append("category = ?")
            params.append(category)
        if severity is not None:
            conditions.append("severity = ?")
            params.append(severity)

        where = " AND ".join(conditions)

        # Total count
        async with self._db.execute(
            f"SELECT COUNT(*) FROM issues WHERE {where}", params
        ) as cursor:
            total = (await cursor.fetchone())[0]

        # Paginated results — priority-rank first, then severity, then category
        offset = (page - 1) * limit
        async with self._db.execute(
            f"""
            SELECT * FROM issues
            WHERE {where}
            ORDER BY {_PRIORITY_ORDER}, {_SEVERITY_ORDER}, category
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ) as cursor:
            rows = await cursor.fetchall()

        return [_row_to_issue(dict(r)) for r in rows], total

    async def get_all_issues(self, job_id: str) -> list[Issue]:
        async with self._db.execute(
            f"""
            SELECT * FROM issues WHERE job_id = ?
            ORDER BY {_PRIORITY_ORDER}, {_SEVERITY_ORDER}, category
            """,
            (job_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_issue(dict(r)) for r in rows]

    # ── Link storage ───────────────────────────────────────────────────────

    async def save_links(self, links: list[Link]) -> None:
        rows = [_link_to_row(lk) for lk in links]
        await self._db.executemany(
            """
            INSERT OR REPLACE INTO links VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await self._db.commit()

    async def delete_issues_for_url(self, job_id: str, page_url: str) -> int:
        """Delete all issues for a specific page URL and return the count deleted."""
        async with self._db.execute(
            "SELECT COUNT(*) FROM issues WHERE job_id = ? AND page_url = ?",
            (job_id, page_url),
        ) as cursor:
            row = await cursor.fetchone()
        count = row[0] if row else 0
        await self._db.execute(
            "DELETE FROM issues WHERE job_id = ? AND page_url = ?",
            (job_id, page_url),
        )
        await self._db.commit()
        return count

    async def delete_issues_by_code_and_url(self, job_id: str, issue_code: str, page_url: str) -> int:
        """Delete issues matching a specific code and page_url. Returns count deleted."""
        async with self._db.execute(
            "SELECT COUNT(*) FROM issues WHERE job_id = ? AND issue_code = ? AND page_url = ?",
            (job_id, issue_code, page_url),
        ) as cursor:
            row = await cursor.fetchone()
        count = row[0] if row else 0
        await self._db.execute(
            "DELETE FROM issues WHERE job_id = ? AND issue_code = ? AND page_url = ?",
            (job_id, issue_code, page_url),
        )
        await self._db.commit()
        return count

    async def delete_broken_link_issues_for_source(self, job_id: str, source_url: str) -> int:
        """Delete broken-link issues linked to *source_url* as the source page.

        Two strategies, both needed for robustness:
        1. issues with extra.source_url = source_url (new crawls with extra column populated)
        2. issues with page_url IN (target_urls from links table for this source_url)
           — covers issues from crawls before the extra column was added
        """
        # Strategy 1: extra.source_url match
        async with self._db.execute(
            """
            SELECT COUNT(*) FROM issues
            WHERE job_id = ?
              AND category = 'broken_link'
              AND json_extract(extra, '$.source_url') = ?
            """,
            (job_id, source_url),
        ) as cursor:
            row = await cursor.fetchone()
        count = row[0] if row else 0
        if count:
            await self._db.execute(
                """
                DELETE FROM issues
                WHERE job_id = ?
                  AND category = 'broken_link'
                  AND json_extract(extra, '$.source_url') = ?
                """,
                (job_id, source_url),
            )

        # Strategy 2: cross-reference links table (covers legacy data without extra column)
        # Count first, then delete
        async with self._db.execute(
            """
            SELECT COUNT(*) FROM issues
            WHERE job_id = ?
              AND category = 'broken_link'
              AND page_url IN (
                  SELECT target_url FROM links
                  WHERE job_id = ? AND source_url = ?
              )
            """,
            (job_id, job_id, source_url),
        ) as cursor:
            row2 = await cursor.fetchone()
        count2 = row2[0] if row2 else 0
        if count2:
            await self._db.execute(
                """
                DELETE FROM issues
                WHERE job_id = ?
                  AND category = 'broken_link'
                  AND page_url IN (
                      SELECT target_url FROM links
                      WHERE job_id = ? AND source_url = ?
                  )
                """,
                (job_id, job_id, source_url),
            )
            count += count2

        await self._db.commit()
        return count

    async def get_broken_link_codes_for_source(self, job_id: str, source_url: str) -> set[str]:
        """Return the set of broken-link issue codes for issues linked to *source_url*.

        Combines extra.source_url lookup (new data) with links-table cross-reference (legacy data).
        """
        async with self._db.execute(
            """
            SELECT DISTINCT issue_code FROM issues
            WHERE job_id = ?
              AND category = 'broken_link'
              AND (
                json_extract(extra, '$.source_url') = ?
                OR page_url IN (
                    SELECT target_url FROM links
                    WHERE job_id = ? AND source_url = ?
                )
              )
            """,
            (job_id, source_url, job_id, source_url),
        ) as cursor:
            rows = await cursor.fetchall()
        return {r[0] for r in rows}

    async def get_links_by_target(self, job_id: str, target_url: str) -> list[dict]:
        """Return links records where target_url matches, for a given job."""
        async with self._db.execute(
            """
            SELECT source_url, target_url, link_text, link_type
              FROM links
             WHERE job_id = ? AND target_url = ?
             ORDER BY source_url
            """,
            (job_id, target_url),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Summary ────────────────────────────────────────────────────────────

    async def get_summary(self, job_id: str) -> dict:
        """Return aggregated issue counts for a job (spec API §6.4)."""
        job = await self.get_job(job_id)
        if job is None:
            return {}

        # Count by severity
        async with self._db.execute(
            "SELECT severity, COUNT(*) FROM issues WHERE job_id = ? GROUP BY severity",
            (job_id,),
        ) as cursor:
            severity_rows = await cursor.fetchall()
        by_severity = {"critical": 0, "warning": 0, "info": 0}
        for row in severity_rows:
            by_severity[row[0]] = row[1]

        # Count by category (Phase 1 only)
        async with self._db.execute(
            "SELECT category, COUNT(*) FROM issues WHERE job_id = ? GROUP BY category",
            (job_id,),
        ) as cursor:
            category_rows = await cursor.fetchall()
        by_category: dict[str, int] = {c: 0 for c in PHASE_1_CATEGORIES}
        for row in category_rows:
            cat = row[0]
            if cat in PHASE_1_CATEGORIES:
                by_category[cat] = row[1]

        total_issues = sum(by_severity.values())

        # Count pages with HTTP errors (4xx / 5xx)
        async with self._db.execute(
            "SELECT COUNT(*) FROM crawled_pages WHERE job_id = ? AND status_code >= 400",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()
        pages_with_errors = row[0] if row else 0

        suppressed = await self.get_suppressed_codes()
        health_score, _ = await _compute_v15_health_score(
            self._db, job_id, by_severity, job.pages_crawled,
            suppressed_codes=set(suppressed) if suppressed else None,
        )

        return {
            "pages_crawled": job.pages_crawled,
            "pages_with_errors": pages_with_errors,
            "total_issues": total_issues,
            "by_severity": by_severity,
            "by_category": by_category,
            "health_score": health_score,
        }

    # ── By-page views ─────────────────────────────────────────────────────

    async def get_pages_with_issue_counts(
        self,
        job_id: str,
        *,
        min_severity: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """Return crawled pages with aggregated issue counts, sorted by total issues desc.

        Each entry is a dict:
          {url, status_code, issue_counts: {total, critical, warning, info}}

        When *min_severity* is set, only pages that have at least one issue of
        that severity (or higher) are returned.
        Severity ordering: critical > warning > info.
        """
        _SEVERITY_RANK = {"critical": 1, "warning": 2, "info": 3}
        min_rank = _SEVERITY_RANK.get(min_severity, 4) if min_severity else 4

        # Aggregate issue counts per page URL for this job
        async with self._db.execute(
            """
            SELECT
                cp.url,
                cp.status_code,
                COUNT(i.issue_id)                                          AS total,
                SUM(CASE WHEN i.severity = 'critical' THEN 1 ELSE 0 END)  AS critical,
                SUM(CASE WHEN i.severity = 'warning'  THEN 1 ELSE 0 END)  AS warning,
                SUM(CASE WHEN i.severity = 'info'     THEN 1 ELSE 0 END)  AS info
            FROM crawled_pages cp
            LEFT JOIN issues i ON i.page_url = cp.url AND i.job_id = cp.job_id
            WHERE cp.job_id = ?
            GROUP BY cp.url, cp.status_code
            ORDER BY total DESC, cp.url
            """,
            (job_id,),
        ) as cursor:
            all_rows = await cursor.fetchall()

        # Apply min_severity filter in Python (simpler than SQL HAVING with rank)
        if min_severity:
            filtered = []
            for row in all_rows:
                r = dict(row)
                has_qualifying = (
                    (1 <= min_rank and r["critical"] > 0)
                    or (2 <= min_rank and r["warning"] > 0)
                    or (3 <= min_rank and r["info"] > 0)
                )
                if has_qualifying:
                    filtered.append(r)
        else:
            filtered = [dict(r) for r in all_rows]

        total_count = len(filtered)
        offset = (page - 1) * limit
        sliced = filtered[offset : offset + limit]

        result = [
            {
                "url": r["url"],
                "status_code": r["status_code"],
                "issue_counts": {
                    "total": r["total"] or 0,
                    "critical": r["critical"] or 0,
                    "warning": r["warning"] or 0,
                    "info": r["info"] or 0,
                },
            }
            for r in sliced
        ]
        return result, total_count

    async def get_page_issues_by_url(
        self, job_id: str, url: str
    ) -> tuple[CrawledPage | None, dict[str, list[Issue]]]:
        """Return (page, issues_by_category) for a specific crawled URL.

        Returns (None, {}) if the URL was not crawled in this job.
        Issues within each category are sorted critical-first.
        """
        async with self._db.execute(
            "SELECT * FROM crawled_pages WHERE job_id = ? AND url = ?",
            (job_id, url),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None, {}

        crawled_page = _row_to_page(dict(row))

        async with self._db.execute(
            f"""
            SELECT * FROM issues
            WHERE job_id = ? AND page_url = ?
            ORDER BY {_SEVERITY_ORDER}, category
            """,
            (job_id, url),
        ) as cursor:
            issue_rows = await cursor.fetchall()

        by_category: dict[str, list[Issue]] = {}
        for r in issue_rows:
            issue = _row_to_issue(dict(r))
            by_category.setdefault(issue.category, []).append(issue)

        return crawled_page, by_category

    # ── TTL cleanup ────────────────────────────────────────────────────────

    async def cleanup_expired_jobs(self, ttl_days: int = _DEFAULT_TTL_DAYS) -> int:
        """Delete jobs older than *ttl_days* days and their associated data.

        Returns the number of jobs deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        cutoff_iso = cutoff.isoformat()

        async with self._db.execute(
            "SELECT job_id FROM crawl_jobs WHERE started_at < ?", (cutoff_iso,)
        ) as cursor:
            rows = await cursor.fetchall()

        expired_ids = [r[0] for r in rows]
        if not expired_ids:
            return 0

        placeholders = ",".join("?" * len(expired_ids))
        for table in ("issues", "crawled_pages", "links"):
            await self._db.execute(
                f"DELETE FROM {table} WHERE job_id IN ({placeholders})", expired_ids
            )
        await self._db.execute(
            f"DELETE FROM crawl_jobs WHERE job_id IN ({placeholders})", expired_ids
        )
        await self._db.commit()

        logger.info(
            "expired_jobs_cleaned",
            extra={"count": len(expired_ids), "ttl_days": ttl_days},
        )
        return len(expired_ids)

    # ── Fix Manager (v2.0) ─────────────────────────────────────────────────

    async def save_fixes(self, fixes: list[dict]) -> None:
        """Insert or replace a list of fix dicts (from wp_fixer.generate_fixes)."""
        if not fixes:
            return
        db = self._db
        assert db is not None
        await db.executemany(
            """
            INSERT OR IGNORE INTO fixes
                (id, job_id, issue_code, page_url, wp_post_id, wp_post_type,
                 field, label, current_value, proposed_value, status, error, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f["id"], f["job_id"], f["issue_code"], f["page_url"],
                    f.get("wp_post_id"), f.get("wp_post_type"),
                    f["field"], f["label"],
                    f.get("current_value"), f.get("proposed_value", ""),
                    f.get("status", "pending"), f.get("error"), f.get("applied_at"),
                )
                for f in fixes
            ],
        )
        await db.commit()

    async def get_fixes(self, job_id: str) -> list[dict]:
        """Return all fix dicts for *job_id* ordered by page_url then field."""
        db = self._db
        assert db is not None
        async with db.execute(
            """
            SELECT id, job_id, issue_code, page_url, wp_post_id, wp_post_type,
                   field, label, current_value, proposed_value, status, error, applied_at
            FROM fixes
            WHERE job_id = ?
            ORDER BY page_url, field
            """,
            (job_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_fix(self, fix_id: str, **fields: object) -> None:
        """Update one or more columns on a fix record."""
        if not fields:
            return
        db = self._db
        assert db is not None
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [fix_id]
        await db.execute(
            f"UPDATE fixes SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

    async def get_fixes_by_id(self, fix_id: str) -> list[dict]:
        """Return fix row(s) matching *fix_id* (0 or 1 result)."""
        db = self._db
        assert db is not None
        async with db.execute(
            "SELECT * FROM fixes WHERE id = ?", (fix_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def delete_fixes(self, job_id: str) -> None:
        """Remove all fix records for *job_id* (allows regeneration)."""
        db = self._db
        assert db is not None
        await db.execute("DELETE FROM fixes WHERE job_id = ?", (job_id,))
        await db.commit()

    async def get_wp_post_cache(self, urls: list[str]) -> dict[str, dict]:
        """Return cached {url: {id, type}} entries for the given URLs."""
        if not urls:
            return {}
        db = self._db
        assert db is not None
        placeholders = ",".join("?" * len(urls))
        async with db.execute(
            f"SELECT page_url, wp_post_id, wp_post_type FROM wp_post_cache WHERE page_url IN ({placeholders})",
            urls,
        ) as cursor:
            rows = await cursor.fetchall()
        return {r["page_url"]: {"id": r["wp_post_id"], "type": r["wp_post_type"]} for r in rows}

    async def save_wp_post_cache(self, entries: dict[str, dict]) -> None:
        """Persist URL→post_id mappings. Safe to call repeatedly."""
        if not entries:
            return
        db = self._db
        assert db is not None
        await db.executemany(
            """
            INSERT OR REPLACE INTO wp_post_cache (page_url, wp_post_id, wp_post_type)
            VALUES (?, ?, ?)
            """,
            [(url, info["id"], info["type"]) for url, info in entries.items()],
        )
        await db.commit()

    # ── Verified links ─────────────────────────────────────────────────────

    async def get_verified_links(self) -> list[dict]:
        """Return all verified link records as {url, verified_at} dicts."""
        db = self._db
        assert db is not None
        async with db.execute(
            "SELECT url, verified_at FROM verified_links ORDER BY verified_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"url": r["url"], "verified_at": r["verified_at"]} for r in rows]

    async def add_verified_link(self, url: str) -> str:
        """Mark a URL as verified. Returns the verified_at timestamp."""
        db = self._db
        assert db is not None
        await db.execute(
            "INSERT OR REPLACE INTO verified_links (url) VALUES (?)", (url,)
        )
        await db.commit()
        async with db.execute(
            "SELECT verified_at FROM verified_links WHERE url = ?", (url,)
        ) as cursor:
            row = await cursor.fetchone()
        return row["verified_at"] if row else ""

    async def remove_verified_link(self, url: str) -> bool:
        """Remove a URL from the verified list. Returns True if it existed."""
        db = self._db
        assert db is not None
        async with db.execute(
            "SELECT 1 FROM verified_links WHERE url = ?", (url,)
        ) as cursor:
            existed = await cursor.fetchone() is not None
        await db.execute("DELETE FROM verified_links WHERE url = ?", (url,))
        await db.commit()
        return existed

    async def get_verified_link_urls(self) -> set[str]:
        """Return the set of all verified URLs (for engine to check efficiently)."""
        db = self._db
        assert db is not None
        async with db.execute("SELECT url FROM verified_links") as cursor:
            rows = await cursor.fetchall()
        return {r["url"] for r in rows}

    # ── Fix history ────────────────────────────────────────────────────────

    async def record_fixed_issues(self, job_id: str, page_url: str, codes: list[str]) -> None:
        """Record that the given issue codes were resolved on page_url during a rescan."""
        db = self._db
        assert db is not None
        rows = [(job_id, page_url, code) for code in codes]
        await db.executemany(
            "INSERT INTO fixed_issues (job_id, page_url, issue_code) VALUES (?, ?, ?)",
            rows,
        )
        await db.commit()

    async def get_fix_history(self, job_id: str) -> list[dict]:
        """Return all fixed-issue records for a job, newest first."""
        db = self._db
        assert db is not None
        async with db.execute(
            "SELECT page_url, issue_code, fixed_at FROM fixed_issues "
            "WHERE job_id = ? ORDER BY fixed_at DESC",
            (job_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {"page_url": r["page_url"], "issue_code": r["issue_code"], "fixed_at": r["fixed_at"]}
            for r in rows
        ]

    # ── Suppressed issue codes ─────────────────────────────────────────────

    async def get_suppressed_codes(self) -> list[str]:
        """Return all issue codes suppressed from the health score (global, not per-job)."""
        db = self._db
        assert db is not None
        async with db.execute(
            "SELECT issue_code FROM suppressed_issue_codes ORDER BY suppressed_at"
        ) as cursor:
            rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def add_suppressed_code(self, code: str) -> None:
        """Add an issue code to the suppressed list (no-op if already suppressed)."""
        db = self._db
        assert db is not None
        await db.execute(
            "INSERT OR IGNORE INTO suppressed_issue_codes (issue_code) VALUES (?)",
            (code,),
        )
        await db.commit()

    async def remove_suppressed_code(self, code: str) -> None:
        """Remove an issue code from the suppressed list (no-op if not present)."""
        db = self._db
        assert db is not None
        await db.execute(
            "DELETE FROM suppressed_issue_codes WHERE issue_code = ?",
            (code,),
        )
        await db.commit()

    # ── Exempt anchor URLs ─────────────────────────────────────────────────

    async def get_exempt_anchor_urls(self) -> list[dict]:
        """Return all URLs exempt from LINK_EMPTY_ANCHOR (global, not per-job)."""
        db = self._db
        assert db is not None
        async with db.execute(
            "SELECT url, note, added_at FROM exempt_anchor_urls ORDER BY added_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"url": r[0], "note": r[1], "added_at": r[2]} for r in rows]

    async def add_exempt_anchor_url(self, url: str, note: str = "") -> None:
        """Add a URL to the exempt list (no-op if already present)."""
        db = self._db
        assert db is not None
        await db.execute(
            "INSERT OR REPLACE INTO exempt_anchor_urls (url, note) VALUES (?, ?)",
            (url, note),
        )
        await db.commit()

    async def remove_exempt_anchor_url(self, url: str) -> None:
        """Remove a URL from the exempt list (no-op if not present)."""
        db = self._db
        assert db is not None
        await db.execute("DELETE FROM exempt_anchor_urls WHERE url = ?", (url,))
        await db.commit()

    async def get_exempt_anchor_url_set(self) -> set[str]:
        """Return the exempt URLs as a set for fast lookup during crawl."""
        rows = await self.get_exempt_anchor_urls()
        return {r["url"] for r in rows}


# ---------------------------------------------------------------------------
# Row ↔ Model conversion helpers
# ---------------------------------------------------------------------------

def _row_to_job(row: dict) -> CrawlJob:
    settings_data = json.loads(row.get("settings_json") or "{}")
    return CrawlJob(
        job_id=row["job_id"],
        target_url=row["target_url"],
        sitemap_url=row["sitemap_url"],
        status=row["status"],
        pages_crawled=row["pages_crawled"],
        pages_total=row["pages_total"],
        current_url=row["current_url"],
        started_at=datetime.fromisoformat(row["started_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        error_message=row["error_message"],
        settings=CrawlSettings(**settings_data),
    )


def _page_to_row(p: CrawledPage) -> tuple:
    return (
        p.page_id,
        p.job_id,
        p.url,
        p.status_code,
        p.redirect_url,
        json.dumps(p.redirect_chain),
        p.title,
        p.meta_description,
        p.canonical_url,
        p.og_title,
        p.og_description,
        None if p.has_favicon is None else int(p.has_favicon),
        json.dumps(p.h1_tags),
        json.dumps(p.headings_outline),
        int(p.is_indexable),
        p.robots_directive,
        p.response_size_bytes,
        p.crawled_at.isoformat(),
        int(p.has_viewport_meta),
        json.dumps(p.schema_types),
        p.external_script_count,
        p.external_stylesheet_count,
        p.word_count,
        p.crawl_depth,
        p.pagination_next,
        p.pagination_prev,
        p.amphtml_url,
        p.meta_refresh_url,
        p.mixed_content_count,
        p.unsafe_cross_origin_count,
        None if p.has_hsts is None else int(p.has_hsts),
        p.text_to_html_ratio,
        int(p.has_json_ld),
        json.dumps(p.pdf_metadata) if p.pdf_metadata else None,
        json.dumps(p.image_urls),
    )


def _row_to_page(row: dict) -> CrawledPage:
    has_favicon_raw = row["has_favicon"]
    has_favicon: bool | None = None if has_favicon_raw is None else bool(has_favicon_raw)
    return CrawledPage(
        page_id=row["page_id"],
        job_id=row["job_id"],
        url=row["url"],
        status_code=row["status_code"],
        redirect_url=row["redirect_url"],
        redirect_chain=json.loads(row["redirect_chain_json"] or "[]"),
        title=row["title"],
        meta_description=row["meta_description"],
        canonical_url=row["canonical_url"],
        og_title=row["og_title"],
        og_description=row["og_description"],
        has_favicon=has_favicon,
        h1_tags=json.loads(row["h1_tags_json"] or "[]"),
        headings_outline=json.loads(row["headings_outline_json"] or "[]"),
        is_indexable=bool(row["is_indexable"]),
        robots_directive=row["robots_directive"],
        response_size_bytes=row["response_size_bytes"],
        crawled_at=datetime.fromisoformat(row["crawled_at"]),
        has_viewport_meta=bool(row["has_viewport_meta"]),
        schema_types=json.loads(row["schema_types_json"] or "[]"),
        external_script_count=row["external_script_count"],
        external_stylesheet_count=row["external_stylesheet_count"],
        word_count=row.get("word_count"),
        crawl_depth=row.get("crawl_depth"),
        pagination_next=row.get("pagination_next"),
        pagination_prev=row.get("pagination_prev"),
        amphtml_url=row.get("amphtml_url"),
        meta_refresh_url=row.get("meta_refresh_url"),
        mixed_content_count=row.get("mixed_content_count") or 0,
        unsafe_cross_origin_count=row.get("unsafe_cross_origin_count") or 0,
        has_hsts=None if row.get("has_hsts") is None else bool(row["has_hsts"]),
        text_to_html_ratio=row.get("text_to_html_ratio"),
        has_json_ld=bool(row.get("has_json_ld", 0)),
        pdf_metadata=json.loads(row.get("pdf_metadata_json")) if row.get("pdf_metadata_json") else None,
        image_urls=json.loads(row.get("image_urls_json") or "[]"),
    )


def _issue_to_row(i: Issue) -> tuple:
    return (
        i.issue_id,
        i.job_id,
        i.page_id,
        i.page_url,
        i.link_id,
        i.category,
        i.severity,
        i.issue_code,
        i.description,
        i.recommendation,
        i.impact,
        i.priority_rank,
        i.effort,
        i.human_description,
        json.dumps(i.extra) if i.extra else None,
    )


def _row_to_issue(row: dict) -> Issue:
    raw_extra = row.get("extra")
    extra = None
    if raw_extra:
        try:
            extra = json.loads(raw_extra)
        except Exception:
            extra = None
    return Issue(
        issue_id=row["issue_id"],
        job_id=row["job_id"],
        page_id=row["page_id"],
        page_url=row["page_url"],
        link_id=row["link_id"],
        category=row["category"],
        severity=row["severity"],
        issue_code=row["issue_code"],
        description=row["description"],
        recommendation=row["recommendation"],
        impact=row.get("impact") or 0,
        priority_rank=row.get("priority_rank") or 0,
        effort=row.get("effort") or 0,
        human_description=row.get("human_description") or "",
        extra=extra,
    )


def _link_to_row(lk: Link) -> tuple:
    return (
        lk.link_id,
        lk.job_id,
        lk.source_url,
        lk.target_url,
        lk.link_text,
        lk.link_type,
        lk.status_code,
        int(lk.is_broken),
        int(lk.check_skipped),
    )


def _row_to_link(row: dict) -> Link:
    return Link(
        link_id=row["link_id"],
        job_id=row["job_id"],
        source_url=row["source_url"],
        target_url=row["target_url"],
        link_text=row["link_text"],
        link_type=row["link_type"],
        status_code=row["status_code"],
        is_broken=bool(row["is_broken"]),
        check_skipped=bool(row["check_skipped"]),
    )


# ---------------------------------------------------------------------------
# Upstash Redis implementation
# ---------------------------------------------------------------------------

class RedisJobStore:
    """Upstash Redis-backed job store for production (Vercel serverless).

    Uses the Upstash REST API via ``upstash-redis``.  All job fields are stored
    in a Redis Hash; pages and issues are stored as JSON blobs (written once at
    the end of a crawl).  TTL is set on every key so Redis self-cleans.

    Required env vars: UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
    """

    _JOB_TTL_S = _DEFAULT_TTL_DAYS * 86400

    def __init__(self, url: str, token: str) -> None:
        self._url = url
        self._token = token
        self._r: Any = None  # upstash_redis.asyncio.Redis, imported lazily

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def init(self) -> None:
        from upstash_redis.asyncio import Redis  # type: ignore[import]
        self._r = Redis(url=self._url, token=self._token)
        logger.info("redis_store_init", extra={"url": self._url})

    async def close(self) -> None:
        pass  # REST client — nothing to close

    async def __aenter__(self) -> "RedisJobStore":
        await self.init()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── Key helpers ────────────────────────────────────────────────────────

    def _jk(self, job_id: str) -> str:
        return f"tt:job:{job_id}"

    def _pk(self, job_id: str) -> str:
        return f"tt:job:{job_id}:pages"

    def _ik(self, job_id: str) -> str:
        return f"tt:job:{job_id}:issues"

    # ── Job CRUD ───────────────────────────────────────────────────────────

    async def create_job(self, job: CrawlJob) -> None:
        key = self._jk(job.job_id)
        await self._r.hset(key, values=self._job_to_mapping(job))
        await self._r.expire(key, self._JOB_TTL_S)

    async def get_job(self, job_id: str) -> CrawlJob | None:
        data = await self._r.hgetall(self._jk(job_id))
        if not data:
            return None
        return self._mapping_to_job(data)

    async def list_recent_jobs(self, limit: int = 10) -> list[CrawlJob]:
        return []  # Redis implementation tracks jobs by ID only — no index to list by date

    async def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        _ALLOWED = {
            "status", "pages_crawled", "pages_total", "current_url",
            "completed_at", "error_message",
        }
        unknown = set(fields) - _ALLOWED
        if unknown:
            raise ValueError(f"update_job: unknown fields {unknown}")

        mapping: dict[str, str] = {}
        for k, v in fields.items():
            if v is None:
                mapping[k] = ""
            elif isinstance(v, datetime):
                mapping[k] = v.isoformat()
            else:
                mapping[k] = str(v)

        await self._r.hset(self._jk(job_id), values=mapping)

    # ── Page storage ───────────────────────────────────────────────────────

    async def save_pages(self, pages: list[CrawledPage]) -> None:
        if not pages:
            return
        job_id = pages[0].job_id
        key = self._pk(job_id)
        await self._r.set(key, json.dumps([self._page_to_dict(p) for p in pages]))
        await self._r.expire(key, self._JOB_TTL_S)

    async def get_pages(self, job_id: str) -> list[CrawledPage]:
        return await self._load_pages(job_id)

    # ── Issue storage ──────────────────────────────────────────────────────

    async def save_issues(self, issues: list[Issue]) -> None:
        if not issues:
            return
        job_id = issues[0].job_id
        key = self._ik(job_id)
        await self._r.set(key, json.dumps([self._issue_to_dict(i) for i in issues]))
        await self._r.expire(key, self._JOB_TTL_S)

    async def save_links(self, links: list[Link]) -> None:
        pass  # Not needed for MVP results display

    async def delete_issues_for_url(self, job_id: str, page_url: str) -> int:
        return 0  # Not implemented for Redis MVP

    async def delete_issues_by_code_and_url(self, job_id: str, issue_code: str, page_url: str) -> int:
        return 0  # Not implemented for Redis MVP

    async def delete_broken_link_issues_for_source(self, job_id: str, source_url: str) -> int:
        return 0  # Not implemented for Redis MVP

    async def get_broken_link_codes_for_source(self, job_id: str, source_url: str) -> set[str]:
        return set()  # Not implemented for Redis MVP

    async def get_links_by_target(self, job_id: str, target_url: str) -> list[dict]:
        return []  # Links not stored in Redis MVP

    # ── Query helpers ──────────────────────────────────────────────────────

    async def get_issues(
        self,
        job_id: str,
        *,
        category: str | None = None,
        severity: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Issue], int]:
        issues = await self._load_issues(job_id)
        if category:
            issues = [i for i in issues if i.category == category]
        if severity:
            issues = [i for i in issues if i.severity == severity]
        _rank = {"critical": 1, "warning": 2, "info": 3}
        issues.sort(key=lambda i: _rank.get(i.severity, 4))
        total = len(issues)
        offset = (page - 1) * limit
        return issues[offset: offset + limit], total

    async def get_all_issues(self, job_id: str) -> list[Issue]:
        issues = await self._load_issues(job_id)
        _rank = {"critical": 1, "warning": 2, "info": 3}
        issues.sort(key=lambda i: _rank.get(i.severity, 4))
        return issues

    async def get_summary(self, job_id: str) -> dict:
        job = await self.get_job(job_id)
        if not job:
            return {}
        issues = await self._load_issues(job_id)

        by_severity: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
        by_category: dict[str, int] = {c: 0 for c in PHASE_1_CATEGORIES}
        for issue in issues:
            if issue.severity in by_severity:
                by_severity[issue.severity] += 1
            if issue.category in by_category:
                by_category[issue.category] += 1

        pages = await self._load_pages(job_id)
        pages_with_errors = sum(1 for p in pages if p.status_code >= 400)

        return {
            "pages_crawled": job.pages_crawled,
            "pages_with_errors": pages_with_errors,
            "total_issues": len(issues),
            "by_severity": by_severity,
            "by_category": by_category,
            "health_score": _compute_health_score(by_severity, job.pages_crawled),
        }

    async def get_pages_with_issue_counts(
        self,
        job_id: str,
        *,
        min_severity: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        pages = await self._load_pages(job_id)
        issues = await self._load_issues(job_id)

        _RANK = {"critical": 1, "warning": 2, "info": 3}
        min_rank = _RANK.get(min_severity, 4) if min_severity else 4

        # Aggregate issue counts per page URL
        counts: dict[str, dict[str, int]] = {}
        for issue in issues:
            if not issue.page_url:
                continue
            c = counts.setdefault(
                issue.page_url, {"total": 0, "critical": 0, "warning": 0, "info": 0}
            )
            c["total"] += 1
            if issue.severity in c:
                c[issue.severity] += 1

        result = []
        for p in pages:
            c = counts.get(p.url, {"total": 0, "critical": 0, "warning": 0, "info": 0})
            if min_severity:
                has = (
                    (1 <= min_rank and c["critical"] > 0)
                    or (2 <= min_rank and c["warning"] > 0)
                    or (3 <= min_rank and c["info"] > 0)
                )
                if not has:
                    continue
            result.append({"url": p.url, "status_code": p.status_code, "issue_counts": c})

        result.sort(key=lambda r: r["issue_counts"]["total"], reverse=True)
        total_count = len(result)
        offset = (page - 1) * limit
        return result[offset: offset + limit], total_count

    async def get_page_issues_by_url(
        self, job_id: str, url: str
    ) -> tuple[CrawledPage | None, dict[str, list[Issue]]]:
        pages = await self._load_pages(job_id)
        matched = next((p for p in pages if p.url == url), None)
        if matched is None:
            return None, {}

        issues = await self._load_issues(job_id)
        by_category: dict[str, list[Issue]] = {}
        _rank = {"critical": 1, "warning": 2, "info": 3}
        for issue in sorted(issues, key=lambda i: _rank.get(i.severity, 4)):
            if issue.page_url == url:
                by_category.setdefault(issue.category, []).append(issue)

        return matched, by_category

    async def cleanup_expired_jobs(self, ttl_days: int = _DEFAULT_TTL_DAYS) -> int:
        return 0  # Redis TTL handles expiry automatically

    # ── Fix Manager ────────────────────────────────────────────────────────

    def _fk(self, job_id: str) -> str:
        return f"tt:job:{job_id}:fixes"

    async def save_fixes(self, fixes: list[dict]) -> None:
        if not fixes:
            return
        # Group by job_id (all fixes in a batch share one job_id)
        by_job: dict[str, list[dict]] = {}
        for fix in fixes:
            by_job.setdefault(fix["job_id"], []).append(fix)
        for job_id, job_fixes in by_job.items():
            key = self._fk(job_id)
            existing_raw = await self._r.get(key)
            existing: list[dict] = json.loads(existing_raw) if existing_raw else []
            existing_by_id = {f["id"]: f for f in existing}
            for fix in job_fixes:
                existing_by_id[fix["id"]] = fix
                # Write secondary index: fix_id → job_id
                await self._r.set(f"tt:fix:{fix['id']}:job", job_id)
                await self._r.expire(f"tt:fix:{fix['id']}:job", self._JOB_TTL_S)
            await self._r.set(key, json.dumps(list(existing_by_id.values())))
            await self._r.expire(key, self._JOB_TTL_S)

    async def get_fixes(self, job_id: str) -> list[dict]:
        raw = await self._r.get(self._fk(job_id))
        if not raw:
            return []
        fixes = json.loads(raw)
        return sorted(fixes, key=lambda f: (f.get("page_url", ""), f.get("field", "")))

    async def get_fixes_by_id(self, fix_id: str) -> list[dict]:
        # We don't have a direct index by fix_id in Redis, so we need to scan.
        # Fix ids are UUIDs; we store them under the job key. The router always
        # has the job_id available via a prior lookup, but the Protocol only
        # exposes fix_id here. We use a secondary index key for fix→job mapping.
        job_id_raw = await self._r.get(f"tt:fix:{fix_id}:job")
        if not job_id_raw:
            return []
        fixes = await self.get_fixes(job_id_raw)
        return [f for f in fixes if f["id"] == fix_id]

    async def update_fix(self, fix_id: str, **fields: object) -> None:
        job_id_raw = await self._r.get(f"tt:fix:{fix_id}:job")
        if not job_id_raw:
            return
        key = self._fk(job_id_raw)
        raw = await self._r.get(key)
        if not raw:
            return
        fixes: list[dict] = json.loads(raw)
        for fix in fixes:
            if fix["id"] == fix_id:
                fix.update(fields)
                break
        await self._r.set(key, json.dumps(fixes))
        await self._r.expire(key, self._JOB_TTL_S)

    async def delete_fixes(self, job_id: str) -> None:
        await self._r.delete(self._fk(job_id))

    async def get_wp_post_cache(self, urls: list[str]) -> dict[str, dict]:
        if not urls:
            return {}
        result = {}
        for url in urls:
            raw = await self._r.get(f"tt:wpcache:{url}")
            if raw:
                import json as _json
                result[url] = _json.loads(raw)
        return result

    async def save_wp_post_cache(self, entries: dict[str, dict]) -> None:
        import json as _json
        for url, info in entries.items():
            key = f"tt:wpcache:{url}"
            await self._r.set(key, _json.dumps(info))
            await self._r.expire(key, 86400 * 90)  # 90-day TTL

    # ── Verified links (Redis — not implemented, returns empty) ────────────

    async def get_verified_links(self) -> list[dict]:
        return []

    async def add_verified_link(self, url: str) -> str:
        return ""

    async def remove_verified_link(self, url: str) -> bool:
        return False

    async def get_verified_link_urls(self) -> set[str]:
        return set()

    async def record_fixed_issues(self, job_id: str, page_url: str, codes: list[str]) -> None:
        pass  # Not implemented for Redis MVP

    async def get_fix_history(self, job_id: str) -> list[dict]:
        return []  # Not implemented for Redis MVP

    # ── Private serialisation ──────────────────────────────────────────────

    async def _load_issues(self, job_id: str) -> list[Issue]:
        raw = await self._r.get(self._ik(job_id))
        if not raw:
            return []
        return [self._dict_to_issue(d) for d in json.loads(raw)]

    async def _load_pages(self, job_id: str) -> list[CrawledPage]:
        raw = await self._r.get(self._pk(job_id))
        if not raw:
            return []
        return [self._dict_to_page(d) for d in json.loads(raw)]

    def _job_to_mapping(self, job: CrawlJob) -> dict[str, str]:
        return {
            "job_id": job.job_id,
            "target_url": job.target_url,
            "sitemap_url": job.sitemap_url or "",
            "status": job.status,
            "pages_crawled": str(job.pages_crawled),
            "pages_total": "" if job.pages_total is None else str(job.pages_total),
            "current_url": job.current_url or "",
            "started_at": job.started_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else "",
            "error_message": job.error_message or "",
            "settings_json": job.settings.model_dump_json(),
        }

    def _mapping_to_job(self, m: dict) -> CrawlJob:
        settings_data = json.loads(m.get("settings_json") or "{}")
        return CrawlJob(
            job_id=m["job_id"],
            target_url=m["target_url"],
            sitemap_url=m.get("sitemap_url") or None,
            status=m["status"],
            pages_crawled=int(m.get("pages_crawled") or 0),
            pages_total=int(m["pages_total"]) if m.get("pages_total") else None,
            current_url=m.get("current_url") or None,
            started_at=datetime.fromisoformat(m["started_at"]),
            completed_at=datetime.fromisoformat(m["completed_at"]) if m.get("completed_at") else None,
            error_message=m.get("error_message") or None,
            settings=CrawlSettings(**settings_data),
        )

    def _issue_to_dict(self, i: Issue) -> dict:
        return {
            "issue_id": i.issue_id,
            "job_id": i.job_id,
            "page_id": i.page_id,
            "page_url": i.page_url,
            "link_id": i.link_id,
            "category": i.category,
            "severity": i.severity,
            "issue_code": i.issue_code,
            "description": i.description,
            "recommendation": i.recommendation,
        }

    def _dict_to_issue(self, d: dict) -> Issue:
        return Issue(**d)

    def _page_to_dict(self, p: CrawledPage) -> dict:
        return {
            "page_id": p.page_id,
            "job_id": p.job_id,
            "url": p.url,
            "status_code": p.status_code,
            "redirect_url": p.redirect_url,
            "redirect_chain": p.redirect_chain,
            "title": p.title,
            "meta_description": p.meta_description,
            "canonical_url": p.canonical_url,
            "og_title": p.og_title,
            "og_description": p.og_description,
            "has_favicon": p.has_favicon,
            "h1_tags": p.h1_tags,
            "headings_outline": p.headings_outline,
            "is_indexable": p.is_indexable,
            "robots_directive": p.robots_directive,
            "response_size_bytes": p.response_size_bytes,
            "crawled_at": p.crawled_at.isoformat(),
            "has_viewport_meta": p.has_viewport_meta,
            "schema_types": p.schema_types,
            "external_script_count": p.external_script_count,
            "external_stylesheet_count": p.external_stylesheet_count,
            "text_to_html_ratio": p.text_to_html_ratio,
            "has_json_ld": p.has_json_ld,
            "pdf_metadata": p.pdf_metadata,
        }

    def _dict_to_page(self, d: dict) -> CrawledPage:
        return CrawledPage(
            page_id=d["page_id"],
            job_id=d["job_id"],
            url=d["url"],
            status_code=d["status_code"],
            redirect_url=d.get("redirect_url"),
            redirect_chain=d.get("redirect_chain", []),
            title=d.get("title"),
            meta_description=d.get("meta_description"),
            canonical_url=d.get("canonical_url"),
            og_title=d.get("og_title"),
            og_description=d.get("og_description"),
            has_favicon=d.get("has_favicon"),
            h1_tags=d.get("h1_tags", []),
            headings_outline=d.get("headings_outline", []),
            is_indexable=d.get("is_indexable", True),
            robots_directive=d.get("robots_directive"),
            response_size_bytes=d.get("response_size_bytes", 0),
            crawled_at=datetime.fromisoformat(d["crawled_at"]),
            has_viewport_meta=d.get("has_viewport_meta", False),
            schema_types=d.get("schema_types", []),
            external_script_count=d.get("external_script_count"),
            external_stylesheet_count=d.get("external_stylesheet_count"),
            text_to_html_ratio=d.get("text_to_html_ratio"),
            has_json_ld=d.get("has_json_ld", False),
            pdf_metadata=d.get("pdf_metadata"),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_job_store() -> "SQLiteJobStore | RedisJobStore":
    """Return the appropriate job store for the current environment.

    Selection order:
      1. UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN set → RedisJobStore
      2. DATABASE_URL set (sqlite:///... or path) → SQLiteJobStore at that path
      3. Neither set → SQLiteJobStore at SQLITE_PATH (default: talkingtoad.db)
    """
    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "")
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
    if redis_url and redis_token:
        logger.info("using_redis_store")
        return RedisJobStore(url=redis_url, token=redis_token)

    url = os.getenv("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):] or _DEFAULT_SQLITE_PATH
    elif url:
        db_path = url
    else:
        db_path = _DEFAULT_SQLITE_PATH

    return SQLiteJobStore(db_path=db_path)

"""SQLite-backed job store implementation."""

from __future__ import annotations

import aiosqlite
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from api.models.geo_config import GeoConfig
from api.models.image import ImageInfo
from api.models.issue import Issue, PHASE_1_CATEGORIES
from api.models.job import CrawlJob, CrawlSettings
from api.models.link import Link
from api.models.page import CrawledPage

from api.services.job_store_base import (
    JobStore,
    SCHEMA,
    _SEVERITY_ORDER,
    _PRIORITY_ORDER,
    _compute_v15_health_score,
    _DEFAULT_TTL_DAYS,
)

logger = logging.getLogger(__name__)


class SQLiteJobStore:
    """SQLite-backed job store. Use as an async context manager or call ``init()`` manually."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def init(self) -> None:
        """Open the database and create schema if needed."""
        self._db = await aiosqlite.connect(self._db_path, timeout=30)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
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
            except aiosqlite.OperationalError:
                # Column likely already exists
                pass

        # Job level migrations
        job_columns = [
            ("llms_txt_custom", "TEXT"),
            ("phase", "TEXT NOT NULL DEFAULT 'queued'"),
            ("external_links_checked", "INTEGER NOT NULL DEFAULT 0"),
            ("external_links_total", "INTEGER NOT NULL DEFAULT 0"),
            ("robots_txt_found", "INTEGER"),
            ("robots_txt_rules", "TEXT"),
            ("sitemap_found", "INTEGER"),
            ("sitemap_url_found", "TEXT"),
            ("sitemap_url_count", "INTEGER"),
            ("executive_summary", "TEXT"),
        ]
        for col, col_type in job_columns:
            try:
                await self._db.execute(
                    f"ALTER TABLE crawl_jobs ADD COLUMN {col} {col_type}"
                )
            except aiosqlite.OperationalError:
                # Column likely already exists
                pass

        issue_columns = [
            ("impact",             "INTEGER NOT NULL DEFAULT 0"),
            ("priority_rank",      "INTEGER NOT NULL DEFAULT 0"),
            ("effort",             "INTEGER NOT NULL DEFAULT 0"),
            ("human_description",  "TEXT"),
            ("what_it_is",         "TEXT"),
            ("impact_desc",        "TEXT"),
            ("how_to_fix",         "TEXT"),
            ("extra",              "TEXT"),
            ("fixability",         "TEXT NOT NULL DEFAULT 'developer_needed'"),
        ]
        for col, col_type in issue_columns:
            try:
                await self._db.execute(
                    f"ALTER TABLE issues ADD COLUMN {col} {col_type}"
                )
            except aiosqlite.OperationalError:
                # Column already exists
                pass

        # Image table migrations (v1.9image)
        image_columns = [
            ("data_source", "TEXT NOT NULL DEFAULT 'html_only'"),
            ("long_description", "TEXT"),
            ("geo_entities_detected", "TEXT"),
            ("geo_location_used", "TEXT"),
            ("ai_analysis_metadata", "TEXT"),
        ]
        for col, col_type in image_columns:
            try:
                await self._db.execute(
                    f"ALTER TABLE images ADD COLUMN {col} {col_type}"
                )
            except aiosqlite.OperationalError:
                # Column already exists
                pass

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

    async def list_jobs_by_domain(self, domain: str, limit: int = 10) -> list[CrawlJob]:
        """Return completed jobs for URLs containing the given domain, newest first."""
        async with self._db.execute(
            "SELECT * FROM crawl_jobs WHERE target_url LIKE ? AND status = 'complete' ORDER BY started_at DESC LIMIT ?",
            (f"%{domain}%", limit),
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
            "completed_at", "error_message", "llms_txt_custom",
            "phase", "external_links_checked", "external_links_total",
            "robots_txt_found", "robots_txt_rules", "sitemap_found",
            "sitemap_url_found", "sitemap_url_count",
            "executive_summary",
        }
        unknown = set(fields) - _ALLOWED
        if unknown:
            raise ValueError(f"update_job: unknown fields {unknown}")

        # Serialise datetime and list values
        serialised = {}
        for k, v in fields.items():
            if isinstance(v, datetime):
                serialised[k] = v.isoformat()
            elif isinstance(v, list):
                serialised[k] = json.dumps(v)
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
            INSERT OR REPLACE INTO issues (
                issue_id, job_id, page_id, page_url, link_id, category, severity,
                issue_code, description, recommendation, impact, priority_rank,
                effort, human_description, what_it_is, impact_desc, how_to_fix, extra,
                fixability
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        cursor = await self._db.execute(
            "DELETE FROM issues WHERE job_id = ? AND page_url = ?",
            (job_id, page_url),
        )
        await self._db.commit()
        return cursor.rowcount

    async def delete_issues_by_code_and_url(self, job_id: str, issue_code: str, page_url: str) -> int:
        """Delete issues matching a specific code and page_url. Returns count deleted."""
        cursor = await self._db.execute(
            "DELETE FROM issues WHERE job_id = ? AND issue_code = ? AND page_url = ?",
            (job_id, issue_code, page_url),
        )
        await self._db.commit()
        return cursor.rowcount

    async def update_issue_extra(self, job_id: str, issue_code: str, page_url: str, extra: dict) -> bool:
        """Update the extra JSON field for a specific issue. Returns True if a row was updated."""
        result = await self._db.execute(
            "UPDATE issues SET extra = ? WHERE job_id = ? AND issue_code = ? AND page_url = ?",
            (json.dumps(extra), job_id, issue_code, page_url),
        )
        await self._db.commit()
        return result.rowcount > 0

    async def delete_broken_link_issues_for_source(self, job_id: str, source_url: str) -> int:
        """Delete broken-link issues linked to *source_url* as the source page.

        Two strategies, both needed for robustness:
        1. issues with extra.source_url = source_url (new crawls with extra column populated)
        2. issues with page_url IN (target_urls from links table for this source_url)
           — covers issues from crawls before the extra column was added
        """
        # Strategy 1: extra.source_url match
        cursor1 = await self._db.execute(
            """
            DELETE FROM issues
            WHERE job_id = ?
              AND category = 'broken_link'
              AND json_extract(extra, '$.source_url') = ?
            """,
            (job_id, source_url),
        )
        count = cursor1.rowcount

        # Strategy 2: cross-reference links table (covers legacy data without extra column)
        cursor2 = await self._db.execute(
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
        count += cursor2.rowcount

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

        # Load discovery info from job record
        robots_info = None
        sitemap_info = None
        try:
            async with self._db.execute(
                "SELECT robots_txt_found, robots_txt_rules, sitemap_found, sitemap_url_found, sitemap_url_count FROM crawl_jobs WHERE job_id = ?",
                (job_id,),
            ) as cursor:
                row = await cursor.fetchone()
            if row:
                robots_info = {
                    "found": bool(row[0]) if row[0] is not None else None,
                    "rules": json.loads(row[1]) if row[1] else [],
                }
                sitemap_info = {
                    "found": bool(row[2]) if row[2] is not None else None,
                    "url": row[3],
                    "url_count": row[4] or 0,
                }
        except (aiosqlite.DatabaseError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load discovery info for job {job_id}: {e}")

        return {
            "target_url": job.target_url,
            "pages_crawled": job.pages_crawled,
            "pages_with_errors": pages_with_errors,
            "total_issues": total_issues,
            "by_severity": by_severity,
            "by_category": by_category,
            "health_score": health_score,
            "robots_txt": robots_info,
            "sitemap": sitemap_info,
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
        for table in ("issues", "crawled_pages", "links", "fixes", "fixed_issues", "images"):
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

    # ── Ignored image patterns ──────────────────────────────────────────────

    async def get_ignored_image_patterns(self) -> list[dict]:
        """Return all ignored image URL patterns (global, not per-job)."""
        db = self._db
        assert db is not None
        async with db.execute(
            "SELECT pattern, note, added_at FROM ignored_image_patterns ORDER BY added_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"pattern": r[0], "note": r[1], "added_at": r[2]} for r in rows]

    async def add_ignored_image_pattern(self, pattern: str, note: str = "") -> None:
        """Add a URL pattern to the ignored list (substring match)."""
        db = self._db
        assert db is not None
        await db.execute(
            "INSERT OR REPLACE INTO ignored_image_patterns (pattern, note) VALUES (?, ?)",
            (pattern.strip(), note),
        )
        await db.commit()

    async def remove_ignored_image_pattern(self, pattern: str) -> None:
        """Remove a pattern from the ignored list."""
        db = self._db
        assert db is not None
        await db.execute("DELETE FROM ignored_image_patterns WHERE pattern = ?", (pattern.strip(),))
        await db.commit()

    async def get_ignored_image_pattern_list(self) -> list[str]:
        """Return patterns as a list for filtering during issue checks."""
        rows = await self.get_ignored_image_patterns()
        return [r["pattern"] for r in rows]

    # ── Image analysis (v1.9image) ──────────────────────────────────────────

    async def save_images(self, images: list[ImageInfo]) -> None:
        """Save a batch of ImageInfo records for a job."""
        if not images:
            return
        db = self._db
        assert db is not None
        rows = [_image_to_row(img) for img in images]
        await db.executemany(
            """
            INSERT OR REPLACE INTO images (
                job_id, url, page_url, alt, title, filename, format,
                width, height, rendered_width, rendered_height,
                file_size_bytes, load_time_ms, http_status,
                is_lazy_loaded, has_srcset, srcset_candidates, is_decorative,
                surrounding_text, content_hash,
                performance_score, accessibility_score, semantic_score,
                technical_score, overall_score, issues, data_source,
                long_description, geo_entities_detected, geo_location_used, ai_analysis_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await db.commit()

    async def get_images(
        self,
        job_id: str,
        *,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "score",
    ) -> list[ImageInfo]:
        """Return images for a job with pagination and sorting."""
        db = self._db
        assert db is not None

        # Sorting options
        if sort_by == "size":
            order_clause = "file_size_bytes DESC NULLS LAST"
        elif sort_by == "load_time":
            order_clause = "load_time_ms DESC NULLS LAST"
        else:  # default: score (lowest first = worst images first)
            order_clause = "overall_score ASC"

        offset = (page - 1) * limit
        async with db.execute(
            f"""
            SELECT * FROM images
            WHERE job_id = ?
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
            """,
            (job_id, limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_image(dict(r)) for r in rows]

    async def get_image_summary(self, job_id: str) -> dict:
        """Return image health summary for a job."""
        db = self._db
        assert db is not None

        # Total and analyzed counts
        async with db.execute(
            "SELECT COUNT(*) FROM images WHERE job_id = ?",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()
        total_images = row[0] if row else 0

        if total_images == 0:
            return {
                "total_images": 0,
                "images_analyzed": 0,
                "images_with_metadata": 0,
                "image_health_score": 100,
                "by_issue": {},
                "by_format": {},
                "total_size_kb": 0,
                "avg_load_time_ms": 0,
                "avg_score": 100,
            }

        # Analyzed = those with http_status > 0 (full fetch)
        async with db.execute(
            "SELECT COUNT(*) FROM images WHERE job_id = ? AND data_source = 'full_fetch'",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()
        images_analyzed = row[0] if row else 0

        # Images with metadata (crawl_meta or full_fetch)
        async with db.execute(
            "SELECT COUNT(*) FROM images WHERE job_id = ? AND data_source IN ('crawl_meta', 'full_fetch')",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()
        images_with_metadata = row[0] if row else 0

        # Average scores — include all images that have been scored
        # (file_size_bytes is populated from HEAD requests during crawl)
        async with db.execute(
            """
            SELECT
                AVG(overall_score) as avg_score,
                AVG(load_time_ms) as avg_load_time
            FROM images
            WHERE job_id = ? AND file_size_bytes IS NOT NULL
            """,
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()
        avg_score = row[0] if row and row[0] else 100
        avg_load_time = row[1] if row and row[1] else 0

        # Total size (all images, including those analyzed during crawl)
        async with db.execute(
            """
            SELECT SUM(file_size_bytes)
            FROM images
            WHERE job_id = ?
            """,
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()
        total_size_bytes = row[0] if row and row[0] else 0

        # Count by format
        async with db.execute(
            """
            SELECT format, COUNT(*) FROM images
            WHERE job_id = ? AND format IS NOT NULL
            GROUP BY format
            """,
            (job_id,),
        ) as cursor:
            format_rows = await cursor.fetchall()
        by_format = {r[0]: r[1] for r in format_rows}

        # Count by issue code (need to parse JSON issues array)
        by_issue: dict[str, int] = {}
        async with db.execute(
            "SELECT issues FROM images WHERE job_id = ? AND issues IS NOT NULL",
            (job_id,),
        ) as cursor:
            issue_rows = await cursor.fetchall()
        for row in issue_rows:
            try:
                codes = json.loads(row[0]) if row[0] else []
                for code in codes:
                    by_issue[code] = by_issue.get(code, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "total_images": total_images,
            "images_analyzed": images_analyzed,
            "images_with_metadata": images_with_metadata,
            "image_health_score": round(avg_score),
            "by_issue": by_issue,
            "by_format": by_format,
            "total_size_kb": round(total_size_bytes / 1024) if total_size_bytes else 0,
            "avg_load_time_ms": round(avg_load_time) if avg_load_time else 0,
            "avg_score": round(avg_score, 1),
        }

    async def get_image_by_url(self, job_id: str, url: str) -> ImageInfo | None:
        """Get a single image by URL."""
        db = self._db
        assert db is not None
        async with db.execute(
            "SELECT * FROM images WHERE job_id = ? AND url = ?",
            (job_id, url),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_image(dict(row))

    # ── GEO Configuration (v1.9geo) - Simple config table ─────────────────

    async def save_geo_config(self, config: GeoConfig) -> None:
        """Save GEO configuration for a domain in config table."""
        db = self._db
        assert db is not None
        now = datetime.now(timezone.utc).isoformat()

        # Update timestamps
        if not config.created_at:
            config.created_at = now
        config.updated_at = now

        # Store as JSON blob with key = geo_config:{domain}
        key = f"geo_config:{config.domain}"
        value = json.dumps(config.to_dict())

        await db.execute(
            """
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
        await db.commit()
        logger.info("geo_config_saved", extra={"domain": config.domain})

    async def get_geo_config(self, domain: str) -> GeoConfig | None:
        """Get GEO configuration for a domain from config table."""
        db = self._db
        assert db is not None
        key = f"geo_config:{domain}"

        async with db.execute(
            "SELECT value FROM config WHERE key = ?",
            (key,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        try:
            data = json.loads(row[0])
            return GeoConfig.from_dict(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("geo_config_parse_error", extra={"error": str(e), "domain": domain})
            return None

    async def delete_geo_config(self, domain: str) -> bool:
        """Delete GEO configuration for a domain from config table."""
        db = self._db
        assert db is not None
        key = f"geo_config:{domain}"

        cursor = await db.execute(
            "DELETE FROM config WHERE key = ?",
            (key,),
        )
        await db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("geo_config_deleted", extra={"domain": domain})
        return deleted


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
        llms_txt_custom=row.get("llms_txt_custom"),
        executive_summary=row.get("executive_summary"),
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
        i.what_it_is,
        i.impact_desc,
        i.how_to_fix,
        json.dumps(i.extra) if i.extra else None,
        i.fixability,
    )


def _row_to_issue(row: dict) -> Issue:
    raw_extra = row.get("extra")
    extra = None
    if raw_extra:
        try:
            extra = json.loads(raw_extra)
        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse issue extra data: {e}")
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
        what_it_is=row.get("what_it_is") or "",
        impact_desc=row.get("impact_desc") or "",
        how_to_fix=row.get("how_to_fix") or "",
        extra=extra,
        fixability=row.get("fixability") or "developer_needed",
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


def _image_to_row(img: ImageInfo) -> tuple:
    return (
        img.job_id,
        img.url,
        img.page_url,
        img.alt,
        img.title,
        img.filename,
        img.format,
        img.width,
        img.height,
        img.rendered_width,
        img.rendered_height,
        img.file_size_bytes,
        img.load_time_ms,
        img.http_status,
        int(img.is_lazy_loaded),
        int(img.has_srcset),
        json.dumps(img.srcset_candidates) if img.srcset_candidates else None,
        int(img.is_decorative),
        img.surrounding_text,
        img.content_hash,
        img.performance_score,
        img.accessibility_score,
        img.semantic_score,
        img.technical_score,
        img.overall_score,
        json.dumps(img.issues) if img.issues else None,
        img.data_source,
        img.long_description,
        json.dumps(img.geo_entities_detected) if img.geo_entities_detected else None,
        img.geo_location_used,
        json.dumps(img.ai_analysis_metadata) if img.ai_analysis_metadata else None,
    )


def _row_to_image(row: dict) -> ImageInfo:
    srcset_raw = row.get("srcset_candidates")
    srcset = []
    if srcset_raw:
        try:
            srcset = json.loads(srcset_raw)
        except (json.JSONDecodeError, TypeError):
            srcset = []

    issues_raw = row.get("issues")
    issues = []
    if issues_raw:
        try:
            issues = json.loads(issues_raw)
        except (json.JSONDecodeError, TypeError):
            issues = []

    geo_entities_raw = row.get("geo_entities_detected")
    geo_entities = []
    if geo_entities_raw:
        try:
            geo_entities = json.loads(geo_entities_raw)
        except (json.JSONDecodeError, TypeError):
            geo_entities = []

    ai_metadata_raw = row.get("ai_analysis_metadata")
    ai_metadata = None
    if ai_metadata_raw:
        try:
            ai_metadata = json.loads(ai_metadata_raw)
        except (json.JSONDecodeError, TypeError):
            ai_metadata = None

    return ImageInfo(
        job_id=row["job_id"],
        url=row["url"],
        page_url=row["page_url"],
        alt=row.get("alt"),
        title=row.get("title"),
        filename=row.get("filename") or "",
        format=row.get("format") or "unknown",
        width=row.get("width"),
        height=row.get("height"),
        rendered_width=row.get("rendered_width"),
        rendered_height=row.get("rendered_height"),
        file_size_bytes=row.get("file_size_bytes"),
        load_time_ms=row.get("load_time_ms"),
        http_status=row.get("http_status") or 0,
        is_lazy_loaded=bool(row.get("is_lazy_loaded")),
        has_srcset=bool(row.get("has_srcset")),
        srcset_candidates=srcset,
        is_decorative=bool(row.get("is_decorative")),
        surrounding_text=row.get("surrounding_text") or "",
        content_hash=row.get("content_hash"),
        performance_score=row.get("performance_score") or 100.0,
        accessibility_score=row.get("accessibility_score") or 100.0,
        semantic_score=row.get("semantic_score") or 100.0,
        technical_score=row.get("technical_score") or 100.0,
        overall_score=row.get("overall_score") or 100.0,
        issues=issues,
        data_source=row.get("data_source") or "html_only",
        long_description=row.get("long_description"),
        geo_entities_detected=geo_entities,
        geo_location_used=row.get("geo_location_used"),
        ai_analysis_metadata=ai_metadata,
    )

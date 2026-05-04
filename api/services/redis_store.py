"""Upstash Redis-backed job store implementation for production."""

from __future__ import annotations

import json
import logging
from typing import Any

from api.models.geo_config import GeoConfig
from api.models.image import ImageInfo
from api.models.issue import Issue, PHASE_1_CATEGORIES
from api.models.job import CrawlJob, CrawlSettings
from api.models.link import Link
from api.models.page import CrawledPage
from datetime import datetime, timezone

from api.services.job_store_base import (
    _DEFAULT_TTL_DAYS,
)

logger = logging.getLogger(__name__)


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

    async def list_jobs_by_domain(self, domain: str, limit: int = 10) -> list[CrawlJob]:
        # Redis MVP — return empty
        return []

    async def update_job(self, job_id: str, **fields: Any) -> None:
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

    async def update_issue_extra(self, job_id: str, issue_code: str, page_url: str, extra: dict) -> bool:
        return False  # Not implemented for Redis MVP

    async def delete_broken_link_issues_for_source(self, job_id: str, source_url: str) -> int:
        return 0  # Not implemented for Redis MVP

    async def get_broken_link_codes_for_source(self, job_id: str, source_url: str) -> set[str]:
        return set()  # Not implemented for Redis MVP

    async def get_links_by_target(self, job_id: str, target_url: str) -> list[dict]:
        return []  # Links not stored in Redis MVP

    # ── Ignored image patterns (Redis) ────────────────────────────────────

    _IMG_PATTERNS_KEY = "tt:ignored_image_patterns"

    async def get_ignored_image_patterns(self) -> list[dict]:
        """Return all ignored image URL patterns stored in Redis."""
        raw = await self._r.get(self._IMG_PATTERNS_KEY)
        if not raw:
            return []
        return json.loads(raw)

    async def add_ignored_image_pattern(self, pattern: str, note: str = "") -> None:
        """Add a URL pattern to the ignored list."""
        patterns = await self.get_ignored_image_patterns()
        # Replace if exists, else append
        patterns = [p for p in patterns if p["pattern"] != pattern.strip()]
        patterns.append({
            "pattern": pattern.strip(),
            "note": note,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        await self._r.set(self._IMG_PATTERNS_KEY, json.dumps(patterns))

    async def remove_ignored_image_pattern(self, pattern: str) -> None:
        """Remove a pattern from the ignored list."""
        patterns = await self.get_ignored_image_patterns()
        patterns = [p for p in patterns if p["pattern"] != pattern.strip()]
        await self._r.set(self._IMG_PATTERNS_KEY, json.dumps(patterns))

    async def get_ignored_image_pattern_list(self) -> list[str]:
        """Return patterns as a list of strings for filtering."""
        rows = await self.get_ignored_image_patterns()
        return [r["pattern"] for r in rows]

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

        health_score = self._compute_health_score(by_severity, job.pages_crawled)

        return {
            "target_url": job.target_url,
            "pages_crawled": job.pages_crawled,
            "pages_with_errors": pages_with_errors,
            "total_issues": len(issues),
            "by_severity": by_severity,
            "by_category": by_category,
            "health_score": health_score,
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
                result[url] = json.loads(raw)
        return result

    async def save_wp_post_cache(self, entries: dict[str, dict]) -> None:
        for url, info in entries.items():
            key = f"tt:wpcache:{url}"
            await self._r.set(key, json.dumps(info))
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

    # ── Image analysis (Redis — not implemented for MVP) ───────────────────

    async def save_images(self, images: list[ImageInfo]) -> None:
        pass  # Not implemented for Redis MVP

    async def get_images(
        self,
        job_id: str,
        *,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "score",
    ) -> list[ImageInfo]:
        return []  # Not implemented for Redis MVP

    async def get_image_summary(self, job_id: str) -> dict:
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

    async def get_image_by_url(self, job_id: str, url: str) -> ImageInfo | None:
        return None  # Not implemented for Redis MVP

    # ── GEO Configuration (Redis — not implemented for MVP) ────────────────

    async def save_geo_config(self, config: GeoConfig) -> None:
        pass  # Not implemented for Redis MVP

    async def get_geo_config(self, domain: str) -> GeoConfig | None:
        return None  # Not implemented for Redis MVP

    async def delete_geo_config(self, domain: str) -> bool:
        return False  # Not implemented for Redis MVP

    # ── Private serialisation ──────────────────────────────────────────────

    async def _load_issues(self, job_id: str) -> list[Issue]:
        raw = await self._r.get(self._ik(job_id))
        if not raw:
            return []
        return [Issue(**d) for d in json.loads(raw)]

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
            "llms_txt_custom": job.llms_txt_custom or "",
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
            llms_txt_custom=m.get("llms_txt_custom") or None,
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
            "impact": i.impact,
            "priority_rank": i.priority_rank,
            "effort": i.effort,
            "human_description": i.human_description,
            "what_it_is": i.what_it_is,
            "impact_desc": i.impact_desc,
            "how_to_fix": i.how_to_fix,
            "extra": i.extra,
        }

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

    @staticmethod
    def _compute_health_score(by_severity: dict[str, int], pages_crawled: int) -> int:
        """Fallback density-based score used when impact data is unavailable (pre-v1.5 crawls)."""
        pages = max(1, pages_crawled)
        c_density = min(1.0, by_severity.get("critical", 0) / pages)
        w_density = min(1.0, by_severity.get("warning", 0) / pages)
        i_density = min(1.0, by_severity.get("info", 0) / pages)
        deduction = round((c_density * 50) + (w_density * 30) + (i_density * 10))
        return max(0, 100 - deduction)

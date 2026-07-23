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
from api.models.performance import PerformanceRecord

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


# ---------------------------------------------------------------------------
# R4 — cluster suppression (audit 2026-07-03).
# The additive page formula (100 − Σ impact) double-counts when one underlying
# condition trips several codes. These rules charge the ROOT CAUSE once: when a
# parent code is present on a page, its correlated children are excluded from
# THAT PAGE's impact sum. This is a SCORING-ONLY transform — every issue stays
# visible in the issue list/counts; only the health score changes.
# Spec: docs/pending/2026-07-03_r4-cluster-suppression.md
# ---------------------------------------------------------------------------
_CLUSTER_SUPPRESSION: dict[str, frozenset[str]] = {
    # ── R5.2 §6.2 no JSON-LD → JSON_LD_MISSING is the root cause for the whole
    # structured-data family; every schema-detail finding is downstream of it.
    # (§7: SCHEMA_MISSING was deleted as a duplicate of JSON_LD_MISSING, which is
    # now the sole parent of this family.)
    "JSON_LD_MISSING": frozenset({
        "SCHEMA_ORG_MISSING", "FAQ_SCHEMA_MISSING", "DATE_PUBLISHED_MISSING",
        "DATE_MODIFIED_MISSING", "SCHEMA_TYPE_CONFLICT", "SCHEMA_TYPE_MISMATCH",
        "SCHEMA_VISIBLE_MISMATCH", "SCHEMA_DEPRECATED_TYPE", "JSON_LD_INVALID",
    }),
    # §7: TITLE_META_DUPLICATE_PAIR deleted — TITLE_DUPLICATE and
    # META_DESC_DUPLICATE now each charge independently (two distinct fixes).
    # ── §6.1 whole page is a JS shell → its symptoms are the same root cause.
    # JS_DEPENDENT_NAVIGATION added per the Gemini R3 report (a JS shell page's
    # nav is unusable for the same reason its content is). R5.2 extends this to
    # the spec §6.1 set (render-diff, low semantic density, unstructured, thin).
    "RAW_HTML_JS_DEPENDENT": frozenset(
        {"AI_CONTENT_NOT_IN_TEXT", "CONTENT_NOT_EXTRACTABLE_NO_TEXT",
         "CONTACT_INFO_NOT_IN_HTML", "JS_DEPENDENT_NAVIGATION",
         # a JS-shell page's FAQ answers are missing for the same root cause;
         # charge the page-wide code once, not the narrow FAQ one too.
         "FAQ_ANSWERS_NOT_IN_HTML",
         # R5.2 §6.1 additions
         "JS_RENDERED_CONTENT_DIFFERS", "SEMANTIC_DENSITY_LOW",
         "CONTENT_UNSTRUCTURED", "THIN_CONTENT", "CONTENT_THIN"}
    ),
    # ── §6.15 thin page → CONTENT_THIN (<100 words) is the STRICT SUBSET of
    # THIN_CONTENT (<300 words). When the stricter code fires, the broader
    # thin-ness codes are the same root cause. NOTE the direction: R4 had
    # THIN_CONTENT→{CONTENT_THIN}; §6.15 reverses it (CONTENT_THIN is parent)
    # so a <100-word page is charged once, at the stricter code.
    "CONTENT_THIN": frozenset({
        "THIN_CONTENT", "CONTENT_UNSTRUCTURED", "STRUCTURED_ELEMENTS_LOW",
        "SEMANTIC_DENSITY_LOW",
    }),
    # ── §6.4 answer-first family (elected parent: CENTRAL_CLAIM_BURIED). All
    # three measure the same "the answer isn't up top" heuristic three ways;
    # keep all codes but charge the elected parent once.
    "CENTRAL_CLAIM_BURIED": frozenset({
        "FIRST_VIEWPORT_NO_ANSWER", "GEO_SUMMARY_BURIED",
    }),
    # ── §6.5 sourcing/citations → no citations at all is the root cause;
    # the narrower citation-quality findings are downstream.
    "CITATIONS_MISSING_SUBSTANTIAL_CONTENT": frozenset({
        "EXTERNAL_CITATIONS_LOW", "ORPHAN_CLAIM_TECHNICAL", "QUOTATIONS_MISSING",
        "LINK_PROFILE_PROMOTIONAL", "CITATIONS_ORPHANED",
        "CITATIONS_SOURCES_INACCESSIBLE",
    }),
    # ── §6.6 chunk self-containment (elected parent: CHUNKS_NOT_SELF_CONTAINED).
    # Three phrase detectors of the same theory; charge the elected parent once.
    "CHUNKS_NOT_SELF_CONTAINED": frozenset({
        "SECTION_CROSS_REFERENCES", "SECTION_VAGUE_OPENER",
    }),
    # ── §6.8 heavy image → IMG_OVERSIZED is the root cause; the other
    # image-weight findings co-occur on an oversized image.
    "IMG_OVERSIZED": frozenset({
        "IMG_POOR_COMPRESSION", "IMG_OVERSCALED", "IMG_FORMAT_LEGACY",
        "IMG_SLOW_LOAD", "IMG_NO_SRCSET",
    }),
    # ── §6.9 alt-text family. Missing alt is the root cause for images with no
    # alt; generic alt is the root cause for defective alt. IMG_ALT_TOO_LONG
    # stays independent (opposite failure mode — not a child of either).
    "IMG_ALT_MISSING": frozenset({"IMG_ALT_TOO_SHORT"}),
    "IMG_ALT_GENERIC": frozenset({
        "IMG_ALT_TOO_SHORT", "IMG_ALT_DUP_FILENAME", "IMG_ALT_MISUSED",
    }),
    # ── §6.10 social meta — now a single merged code
    # (SOCIAL_PREVIEW_METADATA_MISSING, §7), so no suppression needed here.
    # ── §6.11 blanket robots disallow is the root cause for the narrower
    # bot-blocking findings.
    "AI_BOT_BLANKET_DISALLOW": frozenset({
        "AI_BOT_SEARCH_BLOCKED", "AI_BOT_USER_FETCH_BLOCKED", "ROBOTS_BLOCKED",
        "AI_BOT_NO_AI_DIRECTIVES",
    }),
    # ── §6.13 redirect chain suppresses the single-hop redirect codes for the
    # same source. INTERNAL_REDIRECT_301 stays independent (distinct condition —
    # the link source). This is the ONLY cluster that may touch `redirect`.
    "REDIRECT_CHAIN": frozenset({"REDIRECT_301", "REDIRECT_302"}),
}

# ---------------------------------------------------------------------------
# Per-category cap + page-fatal bypass (audit R3 structural fix, 2026-07-03).
# The additive formula lets minor issues in one category stack and lets
# per-occurrence codes (many BROKEN_LINK_* on one page) zero a page. We cap each
# category's NON-FATAL deduction, so correlated minor issues can't dominate,
# while genuine page-fatal codes bypass the cap and CAN still drive a page to 0
# (a noindex'd / robots-blocked / unreachable page should score 0). This is a
# scoring-only transform; the issue list/counts are unchanged.
# ---------------------------------------------------------------------------
_CATEGORY_IMPACT_CAP = 20

_PAGE_FATAL_CODES: frozenset[str] = frozenset({
    "NOINDEX_META", "NOINDEX_HEADER", "ROBOTS_BLOCKED", "PAGE_TIMEOUT",
    "HTTP_PAGE", "HTTPS_REDIRECT_MISSING", "REDIRECT_LOOP", "LOGIN_REDIRECT",
})


# ---------------------------------------------------------------------------
# R5.3 — Noindex scope-reduction (external spec §6.12).
# A noindex'd page is deliberately hidden from search/AI, so its content-quality
# issues (thin content, missing metadata, weak headings, …) don't matter — only
# the noindex itself, plus anything that is a genuine risk regardless of
# indexing status: security and redirect problems. When NOINDEX_META or
# NOINDEX_HEADER fires on a page, every OTHER page-scoped code on that page
# contributes 0, EXCEPT codes in the ``security`` / ``redirect`` categories and
# the noindex code itself. Scoring-only: issues stay visible in the list.
# ---------------------------------------------------------------------------
_NOINDEX_CODES: frozenset[str] = frozenset({"NOINDEX_META", "NOINDEX_HEADER"})
_NOINDEX_EXEMPT_CATEGORIES: frozenset[str] = frozenset({"security", "redirect"})


def _noindex_reduced_codes(rows: list[tuple[str, int, str]]) -> set[str]:
    """Return the codes on a page that a noindex silences (contribute 0).

    Empty unless a noindex code is present. When present, every code is dropped
    except the noindex code(s) themselves and any code in an exempt category
    (``security`` / ``redirect``). Pure/deterministic.
    """
    codes_on_page = {c for c, _, _ in rows}
    if not (_NOINDEX_CODES & codes_on_page):
        return set()
    drop: set[str] = set()
    for code, _imp, category in rows:
        if code in _NOINDEX_CODES:
            continue
        if category in _NOINDEX_EXEMPT_CATEGORIES:
            continue
        drop.add(code)
    return drop


# ---------------------------------------------------------------------------
# R5.1 — Site-scope (external spec §6.3).
# Some findings are properties of the whole SITE, not of an individual page:
# a missing HTTPS redirect, serving the site over plain HTTP, a missing HSTS
# header, mixed content, or a non-canonical www/non-www host. Charging them on
# every page double-counts a single root cause across a large crawl. A
# site-scoped code deducts ONCE site-wide, at the worst-affected representative
# page — every other page ignores it entirely (including its page-fatal
# flooring: only the representative page may be floored by a site-scoped fatal
# code like HTTP_PAGE). Scoring-only: issues stay visible per page in the list.
# ---------------------------------------------------------------------------


def _is_site_scoped(code: str) -> bool:
    """True if a code is declared ``scope="site"`` in the issue catalogue."""
    # Imported lazily to avoid a module-load cycle (registry imports models
    # which import nothing here, but the store is imported very early).
    from api.crawler.checkers.registry import issue_scope

    return issue_scope(code) == "site"


def _site_scope_representatives(
    page_norm_urls: list[str],
    per_page_issues: dict[str, list[tuple[str, int, str]]],
    suppressed_codes: set[str] | None,
) -> dict[str, str]:
    """Elect ONE representative page per site-scoped code (the worst-affected).

    "Worst-affected" = the page where the code carries the highest impact; ties
    broken deterministically by URL order in ``page_norm_urls`` so the choice is
    stable across runs. Returns ``{code: representative_url}`` covering only the
    site-scoped codes actually present after job-level suppression.
    """
    # code -> (best_impact, best_url) with URL order as the tiebreak.
    best: dict[str, tuple[int, str]] = {}
    for url in page_norm_urls:
        for c, imp, _cat in per_page_issues.get(url, []):
            if suppressed_codes and c in suppressed_codes:
                continue
            if not _is_site_scoped(c):
                continue
            cur = best.get(c)
            if cur is None or imp > cur[0]:
                best[c] = (imp, url)
    return {code: url for code, (_, url) in best.items()}


def page_suppressed_codes(codes_on_page: set[str]) -> set[str]:
    """Return the child codes to EXCLUDE from a page's impact sum because a
    parent code (same root cause) is present on that page.

    Pure/deterministic. Callers pass the set of codes that would otherwise be
    charged (i.e. after any job-level suppression is removed) so a globally
    suppressed parent does not wrongly silence its children.
    """
    drop: set[str] = set()
    for parent, children in _CLUSTER_SUPPRESSION.items():
        if parent in codes_on_page:
            drop |= children & codes_on_page
    return drop


def _page_deduction(rows: list[tuple[str, int, str]]) -> int:
    """Deduction for one page: page-fatal codes summed uncapped, every other
    category capped at ``_CATEGORY_IMPACT_CAP``. ``rows`` are the CHARGED
    (post-suppression) ``(code, impact, category)`` tuples for the page."""
    fatal = 0
    by_cat: dict[str, int] = {}
    for code, impact, category in rows:
        if code in _PAGE_FATAL_CODES:
            fatal += impact
        else:
            by_cat[category] = by_cat.get(category, 0) + impact
    capped = sum(min(_CATEGORY_IMPACT_CAP, s) for s in by_cat.values())
    return fatal + capped


def _charged_page_rows(rows: list[tuple[str, int, str]]) -> list[tuple[str, int, str]]:
    """Apply the scoring-time page transforms (cluster suppression and noindex
    scope-reduction) to a page's ``(code, impact, category)`` rows and return
    only the rows that are actually charged.

    Suppressed children (a cluster parent is present) and codes silenced by a
    noindex on the page are dropped here — issues stay visible in the list; only
    the health score is affected. Pure/deterministic.
    """
    codes_on_page = {c for c, _, _ in rows}
    drop = page_suppressed_codes(codes_on_page)
    reduced = _noindex_reduced_codes(rows)
    drop |= reduced
    return [(c, imp, cat) for c, imp, cat in rows if c not in drop]


def compute_page_health(rows: list[tuple[str, int, str]]) -> int:
    """Canonical health score (0–100) for ONE page in isolation.

    ``rows`` is the list of ``(issue_code, impact, category)`` tuples charged to
    the page (one entry per issue row). Applies R4 cluster suppression, the
    noindex scope-reduction (R5.3), the per-category cap, and the page-fatal
    bypass — the exact same transform ``compute_impact_health`` applies per page.

    SINGLE SOURCE OF TRUTH for a single page's score: the summary/refresh
    endpoint and the citations endpoint both call this so they cannot diverge
    from the canonical site model (audit R5.0: they previously used raw
    ``100 − Σ impact`` sums that ignored cap + suppression).
    """
    return max(0, 100 - _page_deduction(_charged_page_rows(rows)))


def compute_impact_health(
    page_norm_urls: list[str],
    per_page_issues: dict[str, list[tuple[str, int, str]]],
    by_severity: dict[str, int],
    *,
    suppressed_codes: set[str] | None = None,
) -> tuple[int, int]:
    """Store-agnostic v1.5 impact health with R4 cluster suppression AND
    per-category caps + page-fatal bypass (R3 structural fix).

    Page Health = max(0, 100 − deduction), where deduction sums page-fatal codes
    uncapped and every other category capped at ``_CATEGORY_IMPACT_CAP``.
    Site Health = mean of page scores; pages with no issues score 100.
    ``per_page_issues`` maps a trailing-slash-normalised URL to a list of
    ``(issue_code, impact, category)`` rows — one entry per issue row (so
    per-occurrence codes like BROKEN_LINK_* appear multiple times, and the
    category cap is what bounds their stacking).

    Job-level ``suppressed_codes`` are removed first; R4 cluster suppression is
    then applied to the survivors. Falls back to the density model only for
    pre-v1.5 data (issues exist but every impact is 0). Returns (site, count).

    SINGLE SOURCE OF TRUTH — both the SQLite and Redis stores call this so their
    health scores cannot diverge (audit 2026-07-03: they previously did).
    """
    total_impact_sum = sum(imp for rows in per_page_issues.values() for _, imp, _ in rows)
    total_issues = sum(by_severity.values())
    if total_issues > 0 and total_impact_sum == 0:
        return _density_health_score(by_severity, len(page_norm_urls)), len(page_norm_urls)
    if not page_norm_urls:
        return 100, 0

    # R5.1 — site-scoped codes deduct ONCE site-wide (at the worst-affected
    # representative page), never from other pages. Elect the representative
    # page per site-scoped code before scoring, then strip that code from every
    # other page's rows so only the representative is charged (and only it can
    # be floored by a site-scoped page-fatal code such as HTTP_PAGE).
    rep_page = _site_scope_representatives(page_norm_urls, per_page_issues, suppressed_codes)

    page_scores: list[int] = []
    for url in page_norm_urls:
        rows = per_page_issues.get(url, [])
        if suppressed_codes:
            rows = [(c, imp, cat) for c, imp, cat in rows if c not in suppressed_codes]
        # Drop site-scoped codes that belong to another page's representative.
        rows = [
            (c, imp, cat) for c, imp, cat in rows
            if not (_is_site_scoped(c) and rep_page.get(c) != url)
        ]
        charged = _charged_page_rows(rows)
        page_scores.append(max(0, 100 - _page_deduction(charged)))
    return round(sum(page_scores) / len(page_scores)), len(page_scores)


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
    R4 cluster suppression is applied via the shared :func:`compute_impact_health`.

    Returns (site_health_score, page_count).
    """
    # Fetch per-issue rows (code + impact) so cluster suppression can see the
    # code set per page. Trailing slashes normalised so issues match pages.
    async with db.execute(
        "SELECT RTRIM(page_url, '/') AS norm_url, issue_code, impact, category "
        "FROM issues WHERE job_id = ? AND page_url IS NOT NULL",
        (job_id,),
    ) as cursor:
        issue_rows = await cursor.fetchall()

    per_page: dict[str, list[tuple[str, int, str]]] = {}
    for norm_url, code, impact, category in issue_rows:
        per_page.setdefault(norm_url, []).append((code, impact or 0, category or ""))

    async with db.execute(
        "SELECT url FROM crawled_pages WHERE job_id = ?",
        (job_id,),
    ) as cursor:
        page_rows = await cursor.fetchall()
    page_norm_urls = [url.rstrip("/") for (url,) in page_rows]

    return compute_impact_health(
        page_norm_urls, per_page, by_severity, suppressed_codes=suppressed_codes
    )


# ---------------------------------------------------------------------------
# Agent-readiness ("Agent Health") score (Agent-readiness Phase 1, WP6)
# ---------------------------------------------------------------------------
# The Agent Health score reuses the exact v1.5 Health-Score model
# (Page = max(0, 100 − Σ impact); Site = mean of page scores) but restricts
# the impact sum to *agent-relevant* issues: the citation-side ai_readiness
# codes (already shipped) plus the Phase 1 task-side codes (rendering,
# semantic_html, and the two placeholder-link codes that live in broken_link).
#
# Defined as (category set) ∪ (explicit code set) so the two placeholder-link
# codes are included without recategorising them out of broken_link.

_AGENT_READINESS_CATEGORIES: frozenset[str] = frozenset(
    {"ai_readiness", "rendering", "semantic_html"}
)
_AGENT_READINESS_EXTRA_CODES: frozenset[str] = frozenset(
    {"PLACEHOLDER_LINK", "WRONG_PLACEHOLDER_LINK"}
)


def _is_agent_issue(category: str, code: str) -> bool:
    """Return True if an issue counts toward the Agent Health score."""
    return category in _AGENT_READINESS_CATEGORIES or code in _AGENT_READINESS_EXTRA_CODES


def _agent_issue_sql_filter() -> str:
    """SQL fragment selecting agent-relevant issues (categories ∪ explicit codes)."""
    cats = ",".join(f"'{c}'" for c in sorted(_AGENT_READINESS_CATEGORIES))
    codes = ",".join(f"'{c}'" for c in sorted(_AGENT_READINESS_EXTRA_CODES))
    return f"(category IN ({cats}) OR issue_code IN ({codes}))"


async def _compute_agent_health_score(
    db: aiosqlite.Connection,
    job_id: str,
    pages_crawled: int,
    suppressed_codes: set[str] | None = None,
) -> tuple[int, list[dict]]:
    """Compute the Agent Health score and a per-category breakdown.

    Mirrors :func:`_compute_v15_health_score` but only sums the impact of
    agent-relevant issues. Returns ``(agent_health_score, breakdown)`` where
    breakdown is a list of ``{"category", "issues", "impact"}`` dicts (sorted
    by impact desc) covering only agent-relevant categories/codes present.
    """
    agent_filter = _agent_issue_sql_filter()

    # Per-issue rows for agent-relevant issues (suppression handled in the shared
    # helper so R4 cluster suppression applies to the agent score too).
    async with db.execute(
        f"SELECT RTRIM(page_url, '/') AS norm_url, issue_code, impact, category "
        f"FROM issues WHERE job_id = ? AND page_url IS NOT NULL AND {agent_filter}",
        (job_id,),
    ) as cursor:
        issue_rows = await cursor.fetchall()
    per_page: dict[str, list[tuple[str, int, str]]] = {}
    for norm_url, code, impact, category in issue_rows:
        per_page.setdefault(norm_url, []).append((code, impact or 0, category or ""))

    # Breakdown by category (counts + impact) for agent-relevant issues.
    async with db.execute(
        f"SELECT category, COUNT(*), COALESCE(SUM(impact), 0) "
        f"FROM issues WHERE job_id = ? AND {agent_filter} GROUP BY category",
        (job_id,),
    ) as cursor:
        cat_rows = await cursor.fetchall()
    breakdown = [
        {"category": r[0], "issues": r[1], "impact": r[2] or 0}
        for r in cat_rows
    ]
    breakdown.sort(key=lambda d: d["impact"], reverse=True)

    # Site score = mean of per-page agent-health scores over all crawled pages,
    # via the shared impact-health helper (empty by_severity ⇒ no density
    # fallback; agent scores are always v1.5+ impact-based).
    async with db.execute(
        "SELECT url FROM crawled_pages WHERE job_id = ?",
        (job_id,),
    ) as cursor:
        page_rows = await cursor.fetchall()
    page_norm_urls = [url.rstrip("/") for (url,) in page_rows]

    site, _ = compute_impact_health(
        page_norm_urls, per_page, {}, suppressed_codes=suppressed_codes
    )
    return site, breakdown


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

    # Performance ledger (M6.2)
    async def save_performance_records(self, records: list[PerformanceRecord]) -> None: ...
    async def get_performance_records(
        self, url: str | None = None, domain: str | None = None
    ) -> list[PerformanceRecord]: ...


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

CREATE TABLE IF NOT EXISTS performance_ledger (
    url                          TEXT NOT NULL,
    period                       TEXT NOT NULL,
    created_at                   TEXT,
    last_technical_improvement_at TEXT,
    gsc_clicks_mo                INTEGER DEFAULT 0,
    gsc_impressions_mo           INTEGER DEFAULT 0,
    gsc_ctr_mo                   REAL DEFAULT 0.0,
    gsc_avg_position_mo          REAL DEFAULT 0.0,
    recorded_at                  TEXT,
    PRIMARY KEY (url, period)
);

CREATE INDEX IF NOT EXISTS idx_issues_job_id ON issues(job_id);
CREATE INDEX IF NOT EXISTS idx_issues_job_category ON issues(job_id, category);
CREATE INDEX IF NOT EXISTS idx_issues_job_severity ON issues(job_id, severity);
CREATE INDEX IF NOT EXISTS idx_pages_job_id ON crawled_pages(job_id);
CREATE INDEX IF NOT EXISTS idx_links_job_id ON links(job_id);
CREATE INDEX IF NOT EXISTS idx_fixes_job_id ON fixes(job_id);
CREATE INDEX IF NOT EXISTS idx_images_job_id ON images(job_id);
CREATE INDEX IF NOT EXISTS idx_images_hash ON images(content_hash);

-- v2.6 M2.5 / Cycle DD: ai_usage event log for token-usage billing rollups.
-- Written by api/services/usage_logger.py via async fire-and-forget tasks
-- scheduled from AIRouter._log_usage. Read by api/services/sqlite_store.py
-- get_ai_usage(...) — the seam M2.6 (aggregation API) will plug into.
--
-- Column shape matches PLAN-V3.0.md M2.5 + AIRouter _SAFE_METADATA_KEYS.
-- timestamp is ISO 8601 UTC (matches every other timestamp column in this
-- schema); success is 0/1 because aiosqlite returns ints for booleans.
CREATE TABLE IF NOT EXISTS ai_usage (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id       TEXT NOT NULL,
    job_id            TEXT,            -- nullable; not every call is tied to a crawl
    session_id        TEXT,            -- correlation ID for multi-call workflows
    task_type         TEXT,            -- "advisor" / "rewriter" / etc (per M2.4)
    provider          TEXT NOT NULL,
    model             TEXT NOT NULL,
    input_tokens      INTEGER NOT NULL DEFAULT 0,
    output_tokens     INTEGER NOT NULL DEFAULT 0,
    cost_estimate_usd REAL NOT NULL DEFAULT 0.0,
    timestamp         TEXT NOT NULL,   -- ISO 8601 UTC
    success           INTEGER NOT NULL DEFAULT 1,
    error_message     TEXT
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_customer_ts ON ai_usage(customer_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_usage_job ON ai_usage(job_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_provider ON ai_usage(provider);
"""

SEVERITY_ORDER   = "CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END"
PRIORITY_ORDER   = "priority_rank DESC"

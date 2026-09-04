"""
Crawl management endpoints (spec §6.1, §6.2, §6.4).

POST  /api/crawl/start
GET   /api/crawl/{job_id}
GET   /api/crawl/{job_id}/status
POST  /api/crawl/{job_id}/cancel
GET   /api/crawl/{job_id}/results
GET   /api/crawl/{job_id}/results/{category}
GET   /api/crawl/{job_id}/pages
GET   /api/crawl/{job_id}/pages/issues
GET   /api/crawl/{job_id}/export/csv
GET   /api/crawl/{job_id}/export/csv/{category}
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path as _PathLib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.crawler.engine import (
    CrawlResult, CrawlSettings as EngineCrawlSettings, run_crawl,
    _check_external_link, _is_bot_blocking_domain, _EXTERNAL_LINK_CAP_PER_PAGE,
    _guess_format_from_url, _extract_filename,
)
from api.crawler.content_discovery import discover_scope, resolve_scope_urls
from api.crawler.fetcher import is_ssrf_safe, fetch_page, make_client, make_ssrf_guarded_client, _RESCAN_TIMEOUT
from api.crawler.issue_checker import Issue as EngIssue, check_page, collapse_per_target_occurrences, issue_for_status, issue_scope, make_issue
from api.crawler.normaliser import normalise_url
from api.crawler.parser import ParsedPage as EngPage, parse_page
from api.models.issue import PHASE_1_CATEGORIES, Issue
from api.models.job import CrawlJob, CrawlSettings
from api.models.link import Link
from api.models.page import CrawledPage
from api.services.auth import require_auth
from api.services.error_responses import _err
from api.services.job_store import SQLiteJobStore
from api.services.rate_limiter import (
    CRAWL_START_LIMIT, EXPORT_LIMIT, AI_ANALYSIS_LIMIT, DETAILS_LIMIT, limiter,
)
from api.services.report_generator import generate_pdf_report
from api.services.excel_generator import generate_excel_report
from api.crawler.checkers.registry import FIX_FOCUS_MIN_IMPACT
from api.services.fix_focus import (
    apply_verify,
    build_snapshot,
    merge_checked_state,
    set_checked,
)
from api.services.gsc_priority import (
    PriorityUploadError,
    build_existing_merge_map,
    build_ledger_records,
    parse_priority_upload,
    seed_urls,
)
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawl", dependencies=[Depends(require_auth)])

# Valid severity values for the By Page filter. This is a SECOND declaration of
# the set in `sqlite_store._SEVERITY_RANK`, not a derivation from it — the two
# can drift, and `test_every_valid_min_severity_is_accepted` is what would
# notice. Validation lives here rather than in the store because the store's
# rank default (4, which admits every severity) also encodes the legitimate
# "no filter at all" case, so the store cannot tell an omitted value from a
# typo'd one — and an unvalidated typo is not "no match", it is "match
# everything" (P14).
_VALID_SEVERITIES: frozenset[str] = frozenset({"critical", "warning", "info"})

# Valid category slugs for the filtered results endpoint
_VALID_CATEGORIES: frozenset[str] = frozenset(
    ["broken_link", "metadata", "heading", "redirect",
     "crawlability", "duplicate", "sitemap", "security", "url_structure", "ai_readiness", "image",
     # Agent-readiness Phase 1 task-side categories
     "rendering", "semantic_html",
     # Analytics & Measurement (2026-08-06 spec)
     "analytics"]
)

# Per-job cancel events (job_id → asyncio.Event)
_cancel_events: dict[str, asyncio.Event] = {}
# Phase 4 (2026-09-02) — in-process progress of a "re-check all pages" run,
# keyed by job_id. Lost on restart by design: the stored issues are updated
# page by page as it goes, so a forgotten counter loses nothing.
_recheck_progress: dict[str, dict] = {}

# CSV column order (spec §4.4)
_CSV_FIELDS = ["url", "issue_code", "severity", "info_tier", "category", "phase", "description", "recommendation"]


# ── Dependency injection ───────────────────────────────────────────────────

def get_store() -> SQLiteJobStore:
    """Return the app-level job store. Overridden in tests via dependency_overrides."""
    from api.main import _store
    return _store  # type: ignore[return-value]




# ── Type conversion: engine → model ───────────────────────────────────────

def _engine_page_to_model(page: EngPage, job_id: str) -> CrawledPage:
    redirect_url = page.final_url if page.final_url != page.url else None
    return CrawledPage(
        job_id=job_id,
        url=page.url,
        status_code=page.status_code,
        redirect_url=redirect_url,
        title=page.title,
        meta_description=page.meta_description,
        canonical_url=page.canonical_url,
        og_title=page.og_title,
        og_description=page.og_description,
        has_favicon=page.has_favicon,
        h1_tags=page.h1_tags,
        headings_outline=page.headings_outline,
        is_indexable=page.is_indexable,
        robots_directive=page.robots_directive,
        response_size_bytes=page.response_size_bytes,
        crawled_at=datetime.now(timezone.utc),
        has_viewport_meta=page.has_viewport_meta,
        schema_types=page.schema_types,
        external_script_count=page.external_script_count,
        external_stylesheet_count=page.external_stylesheet_count,
        word_count=page.word_count,
        crawl_depth=page.crawl_depth,
        pagination_next=page.pagination_next,
        pagination_prev=page.pagination_prev,
        amphtml_url=page.amphtml_url,
        meta_refresh_url=page.meta_refresh_url,
        mixed_content_count=page.mixed_content_count,
        unsafe_cross_origin_count=page.unsafe_cross_origin_count,
        has_hsts=page.has_hsts,
        text_to_html_ratio=page.text_to_html_ratio,
        has_json_ld=page.has_json_ld,
        pdf_metadata=page.pdf_metadata,
        image_urls=page.image_urls or [],
    )


def _engine_issue_to_model(issue: EngIssue, job_id: str) -> Issue:
    return Issue(
        job_id=job_id,
        page_url=issue.page_url,
        category=issue.category,  # type: ignore[arg-type]
        severity=issue.severity,  # type: ignore[arg-type]
        issue_code=issue.code,
        description=issue.description,
        recommendation=issue.recommendation,
        impact=issue.impact,
        effort=issue.effort,
        priority_rank=issue.priority_rank,
        human_description=issue.human_description,
        extra=issue.extra,
        fixability=issue.fixability,
        # v2.6 M0.2 — propagate the v2.0 confidence label (Established /
        # Reasonable proxy / Heuristic) from the engine catalogue into
        # the API Issue model. Without this the field was silently
        # dropped at the bridge and never reached frontend consumers,
        # even though every other layer (registry, _IssueSpec, make_issue,
        # Pydantic model) supported it.
        confidence_label=issue.confidence_label,
    )


# ── Single-page fetch + check helper ─────────────────────────────────────

@dataclass
class _PageCheckResult:
    """Result of fetching a single page and running issue checks."""
    page: EngPage                           # parsed page data
    fetch_result: Any                       # raw FetchResult from fetcher
    issues: list[Issue] = field(default_factory=list)   # Pydantic Issue models
    exempt_urls: set[str] = field(default_factory=set)  # for exempt anchor filtering
    # E1.2 — the fetch returned >= 400 and issue_for_status produced nothing,
    # i.e. we could not read the page and have no finding to show for it.
    # Without this the caller sees an empty issue list and cannot tell a
    # blocked page from a clean one (P2).
    page_unreadable: bool = False


async def _lookup_crawled_page(store, job_id: str, requested_url: str):
    """``(crawled_page, issues_by_category, url_as_stored)`` for *requested_url*.

    The store looks a page up by an EXACT url match. Callers used to normalise
    first, so the lookup matched how the crawl had stored the page — and ND3
    (2026-09-02) changed what "normalised" means for exactly one shape: a bare
    origin (``https://site.ca``) now normalises to ``https://site.ca/``. Two
    populations of existing jobs broke, in opposite ways (P8):

    * **43 pages across 39 jobs** stored the home page under the BARE spelling
      only. The normalised lookup misses, and "Re-check this page" on a home
      page that worked yesterday returns PAGE_NOT_FOUND.
    * **71 jobs** stored BOTH spellings as separate rows with different issue
      sets (constructive.co: 38 findings on the bare row, 21 on the slashed
      one). There the normalised lookup does not miss — it hits the TWIN. The
      panel is opened on one row and the endpoint answers for, and rewrites,
      the other; ``/pages/issues`` does not normalise, so the reload shows the
      original row untouched and the button looks inert. Silently reading the
      wrong page is worse than the 404, which at least showed.

    So the CALLER'S OWN spelling is tried first — the frontend passes the url
    straight from the page list, so an exact match is by construction the row
    the operator is looking at — then the normalised form (a hand-typed or
    tracking-param url), then the other trailing-slash spelling. Returns
    ``(None, {}, requested_url)`` when none is stored.

    Tests: tests/test_page_details_endpoint.py::TestClientContract (both bare-origin cases)
    """
    candidates = [requested_url]
    try:
        normalised = normalise_url(requested_url)
    except ValueError as exc:
        logger.debug(f"Could not normalize URL {requested_url}: {exc}")
        normalised = requested_url
    for candidate in (normalised,
                      normalised[:-1] if normalised.endswith("/") else normalised + "/"):
        if candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        crawled_page, by_cat = await store.get_page_issues_by_url(job_id, candidate)
        if crawled_page is not None:
            return crawled_page, by_cat, candidate
    return None, {}, requested_url


async def _fetch_and_check_page(
    *,
    url: str,
    job_id: str,
    base_url: str,
    store: SQLiteJobStore,
    suppress_h1_strings: list[str] | None = None,
    suppress_banner_h1: bool = True,
    bypass_cache: bool = False,
    authenticated: bool = False,
    check_external_links: bool = True,
) -> _PageCheckResult | JSONResponse:
    """Fetch a URL, parse it, run issue checks and external link checks.

    Returns a _PageCheckResult on success, or a JSONResponse error on failure.
    Both rescan_url and scan_single_page delegate their core work here.

    Parameters
    ----------
    url : str
        Already-normalised URL to fetch.
    job_id : str
        Job this page belongs to.
    base_url : str
        Site origin (scheme + host) used as base for parse_page.
    store : job store
        For loading exempt anchors, ignored image patterns, verified links.
    suppress_h1_strings / suppress_banner_h1 : H1 suppression settings.
    bypass_cache : bool
        If True, send cache-bypass headers (used by rescan).
    check_external_links : bool
        If True (default) every external link on the page is fetched, up to
        _EXTERNAL_LINK_CAP_PER_PAGE. That is 50 outbound requests to third-party
        hosts per call. `/page-details` passes False: it answers "which items on
        this page" from the parse, and re-verifying somebody else's links is not
        that question. Callers that pass False MUST report the broken-link codes
        as un-evaluated rather than absent (D6) — an unrun check that renders as
        a clean result is the failure this repo keeps re-finding.
    """
    is_homepage = url.rstrip("/") == base_url.rstrip("/")

    # ── Fetch ─────────────────────────────────────────────────────────
    # D1 — an unpublished page returns 404 to anyone not logged in, so auditing
    # a draft before publishing needs an authenticated fetch. Opt-in per scan,
    # single page only: run_crawl must keep making no authenticated calls (the
    # architecture test forbids it, and a site-wide authenticated crawl would
    # audit content no search engine can see, silently changing what the health
    # score means).
    # Spec:  docs/functional-specification.md (D1)
    # Tests: tests/test_draft_scanning.py
    if authenticated is True:
        from api.routers.fixes_shared import _validate_wp_domain_for_url

        domain_err = _validate_wp_domain_for_url(url)
        if domain_err is not None:
            return domain_err
        try:
            result = await _fetch_page_as_logged_in_user(
                url, bypass_cache=bypass_cache)
        except Exception as exc:
            return _err(
                "WP_AUTH_ERROR",
                f"Could not sign in to WordPress to read this page: {exc}",
                502,
            )
    else:
        try:
            # D6 sweep — was make_client(). fetch_page re-checks
            # redirect_chain + final_url, but only AFTER httpx has followed the
            # hop, so a public host 302-ing to 169.254.169.254 had that request
            # issued and the response merely discarded. Blind SSRF. The guarded
            # client refuses the Location header before following it, which is
            # what CLAUDE.md's "blocked at start *and* on every redirect hop"
            # actually requires. Inherited from the rescan/scan-page path this
            # function has always served; fixed for all three at once.
            async with make_ssrf_guarded_client() as client:
                result = await fetch_page(
                    url, client, timeout=_RESCAN_TIMEOUT,
                    bypass_cache=bypass_cache,
                )
        except Exception as exc:
            return _err("FETCH_ERROR", str(exc), 500)

    if result.status_code == 0:
        error_msg = result.error or "Unknown error"
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            friendly = (
                f"Page timed out after {int(_RESCAN_TIMEOUT)}s "
                "— the site may be slow. Try again in a moment."
            )
        elif "connect" in error_msg.lower():
            friendly = "Could not connect to the site — check that it is online."
        else:
            friendly = f"Could not fetch page: {error_msg}"
        return _err("FETCH_ERROR", friendly, 502)

    # ── Parse ─────────────────────────────────────────────────────────
    try:
        page = parse_page(result, base_url, is_homepage=is_homepage)
    except Exception as exc:
        return _err("PARSE_ERROR", f"Could not parse page: {exc}", 500)

    # ── Issue checks ──────────────────────────────────────────────────
    exempt_urls = await store.get_exempt_anchor_url_set()
    ignored_img_patterns = await store.get_ignored_image_pattern_list()

    # E1 — an error page is not content. run_crawl already skips SEO checks on
    # 4xx/5xx and emits the broken-link finding instead; this path did not, so
    # the same URL was audited or not depending on which button reached it.
    #
    # What that produced, on a real report: a 404 for an unpublished post came
    # back with NOINDEX_META, UNSAFE_CROSS_ORIGIN_LINK and CONSENT_MODE_MISSING
    # — all describing WordPress's 404 TEMPLATE. The "unsafe cross-origin
    # links" were the site footer's social icons; the noindex was the 404
    # template's own, which is correct behaviour for a 404. Every one of them
    # charged the site's health score for a page that does not exist.
    #
    # Spec:  docs/functional-specification.md (E1)
    # Tests: tests/test_error_pages_not_audited.py
    if result.status_code >= 400:
        broken = issue_for_status(result.status_code, url)
        err_issues = [_engine_issue_to_model(broken, job_id)] if broken else []
        for issue in err_issues:
            issue.page_url = url
        return _PageCheckResult(
            page=page,
            fetch_result=result,
            issues=err_issues,
            exempt_urls=exempt_urls,
            # E1.2 — issue_for_status covers 404, 410, 503 and 5xx only. Every
            # other 4xx (401, 403, 405, 429, 451 …) yields None, so without
            # this flag a Cloudflare-blocked or rate-limited page is returned
            # with zero issues and reads as clean.
            page_unreadable=not err_issues,
        )

    eng_issues = check_page(
        page,
        suppress_h1_strings=suppress_h1_strings or None,
        suppress_banner_h1=suppress_banner_h1,
        exempt_anchor_urls=exempt_urls or None,
        ignored_image_patterns=ignored_img_patterns or None,
    )

    # ── External link checks ──────────────────────────────────────────
    verified_link_urls: set[str] = set()
    try:
        vl = await store.get_verified_links()
        verified_link_urls = {v["url"] for v in vl} if vl else set()
    except Exception as e:
        logger.warning(f"Could not load verified links: {e}")

    external_links = ([lnk for lnk in (page.links or []) if not lnk.is_internal]
                      if check_external_links else [])
    ext_checked = 0
    # Same reasoning as above: an external link that redirects to an internal
    # host must be refused at the Location header, not after the fetch.
    async with make_ssrf_guarded_client() as ext_client:
        for lnk in external_links:
            if ext_checked >= _EXTERNAL_LINK_CAP_PER_PAGE:
                break
            target = lnk.url
            if _is_bot_blocking_domain(target):
                if target not in verified_link_urls:
                    skip_issue = make_issue("EXTERNAL_LINK_SKIPPED", target)
                    skip_issue.extra = {"source_url": url}
                    eng_issues.append(skip_issue)
                ext_checked += 1
                continue
            try:
                ext_result = await _check_external_link(target, ext_client)
            except (RuntimeError, ValueError, TimeoutError) as e:
                logger.debug(f"Error checking external link {target}: {e}")
                ext_checked += 1
                continue
            ext_checked += 1
            if ext_result is None:
                continue
            # Engine convention (so §2 collapse + scoring match the full crawl):
            # attribute the finding to the SOURCE page, target URL in extra.
            if ext_result.status_code == 0 and ext_result.error:
                timeout_issue = make_issue("EXTERNAL_LINK_TIMEOUT", url)
                timeout_issue.extra = {"target_url": target}
                eng_issues.append(timeout_issue)
            else:
                broken = issue_for_status(ext_result.status_code, target)
                if broken:
                    broken.page_url = url
                    broken.extra = {"target_url": target}
                    eng_issues.append(broken)

    # §2: collapse per-target rows (broken links / redirects) to one row per
    # (page, code) with the occurrence multiplier baked in — same transform the
    # full crawl applies, so a rescan of a multi-broken-link page scores
    # identically instead of reverting to the pre-§2 per-link sum.
    eng_issues = collapse_per_target_occurrences(eng_issues)

    # ── Convert engine issues → Pydantic models ──────────────────────
    if authenticated is True:
        # A draft has no inbound links, is not in the sitemap, and WordPress
        # marks preview output noindex. Reporting any of those is noise the
        # owner would have to learn to ignore, and "learning to ignore a
        # finding" is how a report stops being read.
        eng_issues = [i for i in eng_issues
                      if i.code not in _PREPUBLICATION_NOISE_CODES]

    # All eng_issues are attributed to this page (`url`) now.
    new_issues = [_engine_issue_to_model(i, job_id) for i in eng_issues]
    for issue in new_issues:
        issue.page_url = url

    return _PageCheckResult(
        page=page,
        fetch_result=result,
        issues=new_issues,
        exempt_urls=exempt_urls,
    )


# D1 — where the WordPress credentials live. A module constant so a test can
# point it elsewhere without writing to the real file (P28).
_WP_CREDENTIALS_PATH = _PathLib("wp-credentials.json")

# D1 — codes that are meaningless before a page is published. A draft has no
# inbound links, is not in the sitemap, and WordPress marks preview output
# noindex; reporting them on a deliberate draft scan is noise.
# Spec: docs/functional-specification.md (D1)
_PREPUBLICATION_NOISE_CODES = frozenset({
    "ORPHAN_PAGE", "NOT_IN_SITEMAP", "NOINDEX_META",
})

# D2 — codes a single-page scan cannot produce, because _fetch_and_check_page
# never calls check_cross_page and passes sitemap_urls=None to check_page.
# Derived from the registry's `needs_full_crawl` flag rather than listed here:
# a literal copy would be a hand-mirrored enumeration, which is the class this
# disclosure exists to stop. Bound to the checkers by
# tests/test_single_page_scan_discloses_inert_checks.py.
#
# Distinct from _PREPUBLICATION_NOISE_CODES above. That set is *suppressed* on
# a draft scan because it is meaningless before publication; this set is *not
# run* because of which code path executed. Merging them would let one reason
# stand in for the other.
# One home, in the registry beside the `needs_full_crawl` flag these derive from.
from api.crawler.checkers.registry import CHECKS_NOT_RUN_REASON as _CHECKS_NOT_RUN_REASON


async def _filter_for_domain(store, target_url: str, issue_dicts: list[dict]) -> tuple[list[dict], dict]:
    """Apply the domain's presentational filter and return (kept, report).

    F1 — hides findings from the results LIST only. The health score is
    computed by the store from the unfiltered set and is deliberately not
    touched here: LEARNINGS records that suppressing ORPHAN_PAGE *raised* the
    score, and a per-domain filter is a far easier lever to pull.

    The report always travels with the response. 123 of the 170 catalogue codes
    are `info`, so the severity rule hides roughly 72% of findings — a list
    that simply came back shorter would read as a cleaner site (P31/P24).
    """
    from api.services.domain_filter import apply_domain_filter
    try:
        rules = await store.get_domain_filters(target_url)
    except Exception as exc:  # a filter must never take the results page down
        logger.warning("domain_filter_load_failed", extra={"error": str(exc)})
        return issue_dicts, {"hidden": 0, "by_rule": {}, "unavailable": True}
    kept, report = apply_domain_filter(issue_dicts, rules)
    from api.services.domain_filter import normalise_filter_domain
    report["domain"] = normalise_filter_domain(target_url)
    return kept, report


async def _filter_issue_models_for_domain(store, target_url: str, issues: list):
    """Apply the domain filter to Issue MODELS, for the export paths.

    The owner asked for "a report of what shows on the screen — not something
    different", so every export goes through the same rule engine the results
    list uses. Returns (kept, caveat_note|None); the note is provenance, not
    content — a PDF leaves the building and its reader is usually not the
    operator who set the filter.
    """
    from api.services.domain_filter import (filter_issue_models,
                                            filter_caveat_note,
                                            normalise_filter_domain)
    try:
        rules = await store.get_domain_filters(target_url)
    except Exception as exc:  # an export must never fail because of a filter
        logger.warning("export_filter_load_failed", extra={"error": str(exc)})
        return issues, None
    kept, report = filter_issue_models(issues, rules)
    report["domain"] = normalise_filter_domain(target_url)
    return kept, filter_caveat_note(report)


def _filter_issue_models_for_info_detail(job, issues: list, note: str | None = None):
    """Apply the scan's ``info_detail`` to Issue MODELS for the export paths.

    Returns ``(kept, combined_note)``. The note names what the level excluded
    from the document AND from its score — the PDF's reader is usually not the
    operator who chose the level.
    """
    from api.services.info_tier_filter import combine_notes, filter_issue_models, info_caveat_note
    kept, report = filter_issue_models(issues, job.settings.info_detail)
    return kept, combine_notes(note, info_caveat_note(report))


async def _paginate_filtered(store, job, *, severity=None, category=None,
                             page: int, limit: int, exempt_urls,
                             info_detail: str | None = None):
    """Fetch, filter, THEN slice. Returns (page_dicts, total, filtered_report,
    info_report).

    ``info_detail`` is the LEVEL TO SERVE AT (already resolved against the
    job's own level by ``resolve_info_detail``); ``scored`` on each row is
    always relative to the job's level.

    The filter must run before pagination, not after. Filtering the already-
    sliced page produced: empty pages behind a live pager (60 findings, one
    rule, `limit=50` → page 1 shows nothing while the pager advertises two
    pages); a per-page `hidden` count, so the banner said 50 when 60 were
    hidden and said something different on every page; and a screen that
    disagreed with the export, which counts over the whole job — falsifying
    the whole point of sharing one rule engine.

    When the domain has no rules this defers to the store's own pagination, so
    the common path keeps its SQL LIMIT/OFFSET.
    """
    from api.services.info_tier_filter import annotate_scored, apply_info_detail
    job_level = job.settings.info_detail
    level = info_detail or job_level
    rules = []
    try:
        rules = await store.get_domain_filters(job.target_url)
    except Exception as exc:
        logger.warning("domain_filter_load_failed", extra={"error": str(exc)})

    if not rules and level == "all":
        issues, total = await store.get_issues(
            job_id=job.job_id, severity=severity, category=category,
            page=page, limit=limit)
        dicts = _apply_exempt_anchors([_issue_dict(i) for i in issues], exempt_urls)
        annotate_scored(dicts, job_level)
        from api.services.domain_filter import normalise_filter_domain
        return (dicts, total,
                {"hidden": 0, "by_rule": {}, "domain": normalise_filter_domain(job.target_url)},
                {"hidden": 0, "by_tier": {}, "info_detail": level})

    # Rules or an info level exist: the kept set cannot be known without
    # seeing every row.
    all_issues, _ = await store.get_issues(
        job_id=job.job_id, severity=severity, category=category,
        page=1, limit=100_000)
    dicts = _apply_exempt_anchors([_issue_dict(i) for i in all_issues], exempt_urls)
    kept, report = await _filter_for_domain(store, job.target_url, dicts)
    kept, info_report = apply_info_detail(annotate_scored(kept, job_level), level)
    start = (page - 1) * limit
    return kept[start:start + limit], len(kept), report, info_report


def _rescan_is_conclusive(status_code: int) -> bool:
    """Is this rescan evidence about the page's issues, or just a failed read?

    A rescan deletes the URL's stored issues and writes the difference to the
    fixed-issues ledger. That is only sound when the fetch actually told us
    something about the page:

      - 2xx/3xx: we read it. Whatever is gone is genuinely fixed.
      - 404/410: the page is gone. Its old findings genuinely no longer apply.
      - anything else >= 400 (401, 403, 405, 429, 451, 5xx) and status 0:
        we learned nothing. Treating "no issues found" as "all issues fixed"
        writes a transient block into the ledger as a permanent positive (P1),
        which is the one outcome the operator cannot undo by re-running.

    E1.2 — tests/test_error_pages_not_audited.py.
    """
    if status_code == 0:
        return False
    if status_code in (404, 410):
        return True
    return status_code < 400


def _checks_a_single_page_scan_cannot_run() -> list[str]:
    """Thin alias kept for the four endpoint call sites; the list lives in the
    registry, beside the flag it derives from."""
    from api.crawler.checkers.registry import checks_a_single_page_scan_cannot_run
    return checks_a_single_page_scan_cannot_run()


async def _fetch_page_as_logged_in_user(url: str, *, bypass_cache: bool = False):
    """Fetch *url* with a WordPress logged-in session, so a draft is readable.

    Purpose: audit a page before it is published (D1).
    Spec:    docs/functional-specification.md (D1)
    Tests:   tests/test_draft_scanning.py

    The caller MUST have domain-validated the URL first: these are the owner's
    real WordPress credentials and they must never be sent to another host.

    The session cookies are copied onto an SSRF-guarded client rather than
    reusing WPClient's own, so the fetch keeps the same start-and-every-hop
    protection as the rest of the crawler.
    """
    from api.services.wp_client import WPClient

    creds_path = _WP_CREDENTIALS_PATH
    if not creds_path.exists():
        raise RuntimeError(
            "wp-credentials.json not found — an authenticated scan needs "
            "WordPress credentials for this site."
        )
    import json as _json

    with open(creds_path) as fh:
        creds = _json.load(fh)

    async with WPClient(
        site_url=creds["site_url"],
        login_url=creds["login_url"],
        username=creds["username"],
        password=creds["password"],
    ) as wp:
        await wp.login()
        cookies = {c.name: c.value for c in wp._client.cookies.jar}

    # Scope every cookie to the host the credentials belong to. `set(name,
    # value)` with no domain produces a cookie whose domain is "", and
    # http.cookiejar's domain_return_ok does `req_host.endswith(domain)` —
    # which is true for EVERY host. The client follows redirects and the SSRF
    # guard rejects private IPs, not foreign ones, so a public redirect is
    # allowed by design: a link cloaker or affiliate plugin (`/go/…`,
    # `/recommends/…`) 301ing off-domain would have shipped the owner's live
    # WordPress admin session to a third party, over plain HTTP too, since
    # flattening the jar to name/value pairs also drops the Secure flag.
    # _validate_wp_domain_for_url pins the URL the operator supplies; nothing
    # pinned where it redirects. SSRF protection is about the destination IP
    # and says nothing about credential scope.
    # Tests: TestTheSessionCookieDoesNotLeaveTheSite (both directions).
    creds_host = urlparse(url).hostname
    async with make_ssrf_guarded_client() as client:
        for name, value in cookies.items():
            client.cookies.set(name, value, creds_host)
        return await fetch_page(
            url, client, timeout=_RESCAN_TIMEOUT, bypass_cache=bypass_cache,
        )


# ── Background crawl task ──────────────────────────────────────────────────

async def _run_crawl_background(
    job_id: str,
    target_url: str,
    engine_settings: EngineCrawlSettings,
    store: SQLiteJobStore,
    cancel_event: asyncio.Event,
) -> None:
    """Background task: run the crawl, persist results, update job status."""
    try:
        await store.update_job(job_id, status="running")

        # Load verified link URLs so the engine can suppress false-positive notices.
        engine_settings.verified_link_urls = await store.get_verified_link_urls()
        # Load exempt anchor URLs so icon links don't flood LINK_EMPTY_ANCHOR.
        engine_settings.exempt_anchor_urls = await store.get_exempt_anchor_url_set()
        # Load ignored image patterns so theme icons don't flood IMG_ALT_MISSING.
        engine_settings.ignored_image_patterns = await store.get_ignored_image_pattern_list()

        async def on_progress(p: dict) -> None:
            await store.update_job(
                job_id,
                pages_crawled=p["pages_crawled"],
                pages_total=p["pages_total"],
                current_url=p["current_url"],
                phase=p.get("phase", "crawling_pages"),
                external_links_checked=p.get("external_links_checked", 0),
                external_links_total=p.get("external_links_total", 0),
            )

        result: CrawlResult = await run_crawl(
            job_id,
            target_url,
            engine_settings,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

        print(f"[ROUTER] Crawl complete. Pages: {len(result.pages)}, Issues: {len(result.issues)}, Images: {len(result.images)}")

        pages = [_engine_page_to_model(p, job_id) for p in result.pages]
        issues = [_engine_issue_to_model(i, job_id) for i in result.issues]
        # E2.3: link_type is DERIVED by the engine (a same-host 404 is internal —
        # it was hardcoded "external" here, so every internal broken link was
        # mislabelled), and status_code is persisted so a transient 503 stays
        # distinguishable from a permanent 404 (P1).
        broken_links = [
            Link(
                job_id=job_id,
                source_url=ref.source_url,
                target_url=ref.target_url,
                link_text=ref.link_text,
                link_type=ref.link_type,
                status_code=ref.status_code,
                is_broken=True,
            )
            for ref in result.broken_link_sources
        ]

        if pages:
            await store.save_pages(pages)
        if issues:
            await store.save_issues(issues)
        if broken_links:
            await store.save_links(broken_links)
        if result.images:
            await store.save_images(result.images)

        # U3 — GSC priority upload: join the uploaded per-page metrics onto the
        # crawled pages and write them to the Performance Ledger, so Page Priority
        # ranks with GSC data (i). Same join as /api/performance/ingest, sourced
        # from the file. Guarded so a ledger hiccup never fails the crawl itself.
        if not result.cancelled and pages:
            try:
                seed_job = await store.get_job(job_id)
                seed = seed_job.priority_seed if seed_job else None
                if seed and seed.get("pages"):
                    now = datetime.now(timezone.utc)
                    period = now.strftime("%Y-%m")
                    # Read-merge (P5): carry a prior real GSC value forward when the
                    # upload omitted a field — a no-op (no reads) unless it did.
                    existing_by_key = await build_existing_merge_map(
                        store, pages, seed, period)
                    ledger = build_ledger_records(
                        seed, pages, period=period, recorded_at=now.isoformat(),
                        existing_by_key=existing_by_key,
                    )
                    if ledger:
                        await store.save_performance_records(ledger)
                        logger.info("priority_seed_ledger",
                                    extra={"job_id": job_id, "records": len(ledger)})
            except Exception:
                logger.exception("priority_seed_ledger_failed", extra={"job_id": job_id})

        final_status = "cancelled" if result.cancelled else "complete"
        await store.update_job(
            job_id,
            status=final_status,
            pages_crawled=result.pages_crawled,
            completed_at=datetime.now(timezone.utc),
            robots_txt_found=result.robots_txt_found,
            robots_txt_rules=result.robots_txt_rules,
            sitemap_found=result.sitemap_found,
            sitemap_url_found=result.sitemap_url_found,
            sitemap_url_count=result.sitemap_url_count,
            # E1.4: persist the image-cap disclosure numbers with the job so
            # every export can state coverage honestly.
            images_seen_total=result.images_seen_total,
            images_collected=result.images_collected,
            # IM1: same for the dimension pass. An image whose pixels were
            # never read is "not checked", not "clean".
            images_measured=result.images_measured,
            images_measurable=result.images_measurable,
            # O2: persist WHY orphan detection did or did not run, so no surface
            # has to infer "clean" from an empty result set (P31 corollary).
            orphan_detection=result.orphan_detection,
            # AF10: persist sitemap fetch coverage alongside it.
            sitemap_coverage=result.sitemap_coverage,
            # C1: which analyses ran, so an off category is not read as clean.
            analysis_coverage=result.analysis_coverage,
        )
        logger.info("crawl_persisted", extra={"job_id": job_id, "status": final_status})

    except Exception as exc:
        logger.exception("crawl_background_failed", extra={"job_id": job_id})
        await store.update_job(
            job_id,
            status="failed",
            error_message=str(exc),
            completed_at=datetime.now(timezone.utc),
            # O2: the crawl died before the cross-page phase, so orphan
            # detection did not run. Without this the job reads back as
            # "not recorded" and the panel shows the all-clear (P31).
            orphan_detection={"status": "skipped_failed",
                              "pages_analysed": 0, "pages_out_of_scope": 0,
                              "archives_skipped": False},
        )
    finally:
        _cancel_events.pop(job_id, None)


# ── E4: site prevalence ───────────────────────────────────────────────────
# Spec: docs/pending/2026-08-29_E4-site-prevalence-escalation.md


async def _prevalence_for(store, job_id: str) -> list:
    """Prevalence rows for a job, or [] if it cannot be computed.

    Guarded: a prevalence hiccup degrades the report rather than failing it. The
    empty case is then recorded in Scope & Caveats (E7.4) instead of reading as
    "no systemic defects".
    """
    try:
        from api.services.prevalence import build_prevalence

        return await build_prevalence(store, job_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("prevalence_unavailable", extra={"job_id": job_id, "error": str(exc)})
        return []

async def _prevalence_for_display(store, job, job_id: str) -> list:
    """Prevalence rows with the domain filter applied.

    Prevalence NAMES CODES as findings, so it follows the same rule as the
    lists: a code that appears in the Prevalence sheet but nowhere else in the
    workbook is the "quick win you cannot find" problem in another costume.
    Distinct from the llms.txt status and the off-site joins, which state facts
    about the SITE and therefore reason from the unfiltered set.
    """
    rows = await _prevalence_for(store, job_id)
    if not rows:
        return rows
    # Info detail (2026-09-01): same rule as the lists — and, since P5.4, the same
    # VALUE. The comment here used to say a prevalence row was "code-level (no
    # stored impact), so the tier comes from the catalogue — the same value every
    # row of that code was stored with". That last clause is only true until a
    # recalibration, which is exactly when it matters: `derive_impact` returns
    # today's number and the lists use the row's. A row now carries its stored
    # impact, so both sides read the same one.
    level = job.settings.info_detail
    if level != "all":
        from api.crawler.checkers.registry import info_row_excluded
        rows = [r for r in rows
                if not (getattr(r, "severity", None) == "info"
                        and info_row_excluded(int(getattr(r, "impact", 0) or 0), level))]
    try:
        from api.services.domain_filter import _rule_sets
        rules = await store.get_domain_filters(job.target_url)
        if not rules:
            return rows
        codes, severities = _rule_sets(rules)
        # The field is `code`, not `issue_code` (api/services/prevalence.py:41).
        # Using the wrong name made getattr return None for every row, so the
        # filter matched nothing and silently did nothing — the shape of bug
        # this whole exercise is about.
        return [r for r in rows
                if getattr(r, "code", None) not in codes
                and getattr(r, "severity", None) not in severities]
    except Exception as exc:  # never fail an export over a filter
        logger.warning("prevalence_filter_failed", extra={"error": str(exc)})
        return rows



def _with_prevalence(summary: dict, prevalences: list) -> dict:
    """Attach prevalence rows, the systemic count and Site Hygiene to a summary."""
    if not summary:
        return summary
    from api.services.prevalence import as_dicts, site_hygiene_score, systemic

    enriched = dict(summary)
    enriched["prevalence"] = as_dicts(prevalences)
    enriched["systemic_count"] = len(systemic(prevalences))
    enriched["site_hygiene_score"] = site_hygiene_score(prevalences) if prevalences else None
    return enriched


# ── Exempt anchor URL filtering ───────────────────────────────────────────

def _apply_exempt_anchors(issues: list, exempt_urls: set[str]) -> list:
    """Remove exempted hrefs from LINK_EMPTY_ANCHOR issues; drop the issue if all hrefs are exempt.

    Works on both Issue model objects and plain dicts (as returned by _issue_dict).
    """
    if not exempt_urls:
        return issues

    filtered = []
    for issue in issues:
        # Support both model objects and dicts
        code = issue.get("issue_code") if isinstance(issue, dict) else getattr(issue, "issue_code", None)
        if code != "LINK_EMPTY_ANCHOR":
            filtered.append(issue)
            continue

        desc = issue.get("description") if isinstance(issue, dict) else getattr(issue, "description", "")
        if not desc:
            filtered.append(issue)
            continue

        # Parse "N links with no anchor text: url1, url2, ..."
        import re as _re
        m = _re.match(r"^(\d+) links? with no anchor text:\s*(.+)$", desc or "")
        if not m:
            filtered.append(issue)
            continue

        hrefs = [h.strip() for h in m.group(2).split(",")]
        remaining = [h for h in hrefs if h not in exempt_urls]
        if not remaining:
            continue  # all hrefs exempted — drop issue entirely

        # Rebuild description with remaining hrefs
        n = len(remaining)
        listed = ", ".join(remaining[:5])
        suffix = f" and {n - 5} more" if n > 5 else ""
        new_desc = f"{n} link{'s' if n > 1 else ''} with no anchor text: {listed}{suffix}"

        # The exempt list also has to be applied to `extra` — it previously
        # rewrote only the description, so the raw hrefs survived in the payload.
        # Harmless while nothing rendered them; the moment `evidence` did, the
        # UI would have shown the very anchors the user exempted.
        def _clean_extra(extra: dict | None) -> dict | None:
            if not isinstance(extra, dict):
                return extra
            cleaned = dict(extra)
            for key in ("empty_anchors", "empty_anchor_hrefs"):
                rows = cleaned.get(key)
                if not isinstance(rows, list):
                    continue
                cleaned[key] = [
                    r for r in rows
                    if (r.get("href") if isinstance(r, dict) else r) not in exempt_urls
                ]
            return cleaned

        if isinstance(issue, dict):
            new_extra = _clean_extra(issue.get("extra"))
            issue = {**issue, "description": new_desc, "extra": new_extra}
            if "evidence" in issue:
                issue.update(_evidence_fields(issue.get("issue_code"), new_extra))
        else:
            issue.description = new_desc
            issue.extra = _clean_extra(getattr(issue, "extra", None))
        filtered.append(issue)

    return filtered


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/recent", response_model=None)
async def list_recent_jobs(
    limit: int = 10,
    store: SQLiteJobStore = Depends(get_store),
) -> list[dict]:
    """Return the most recent crawl jobs (newest first) for the home page."""
    jobs = await store.list_recent_jobs(limit=min(limit, 20))
    return [
        {
            "job_id": j.job_id,
            "target_url": j.target_url,
            "status": j.status,
            "pages_crawled": j.pages_crawled,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]


def _normalise_and_validate_target(raw: str) -> tuple[str | None, JSONResponse | None]:
    """Normalise and SSRF-validate a target URL from a request body.

    Returns ``(url, None)`` on success or ``(None, error_response)`` otherwise.
    Shared by ``/start`` and ``/discover-scope`` so both apply identical
    scheme-prepend, plausible-host, and SSRF rules.
    """
    target_url = (raw or "").strip()
    # Add the scheme when the user omits it: "example.org" → "https://example.org".
    # (Bare hosts are the common case for a scan box; only prepend when there is
    # no scheme at all so we don't mangle a mistyped one like "ftp://…".)
    if target_url and "://" not in target_url:
        target_url = "https://" + target_url
    if not target_url or not target_url.startswith(("http://", "https://")):
        return None, _err("INVALID_URL", "target_url must be a valid http or https URL.", 422)
    # Require a plausible host (a dot) so typos like "example" / "not-a-url"
    # aren't silently turned into an unresolvable https:// target.
    from urllib.parse import urlparse
    _host = urlparse(target_url).netloc.split("@")[-1].split(":")[0]
    if "." not in _host:
        return None, _err("INVALID_URL", "target_url must include a valid domain (e.g. example.org).", 422)
    if not is_ssrf_safe(target_url):
        return None, _err("BLOCKED_URL", "URLs targeting private or internal networks are not allowed.", 403)
    return target_url, None


@router.post("/discover-scope", response_model=None)
@limiter.limit(CRAWL_START_LIMIT)
async def discover_scope_endpoint(
    request: Request,
    body: dict,
) -> dict | JSONResponse:
    """Discover the content types available at a URL (partial-scan setup).

    Read-only: probes the WordPress REST API and/or the site's sitemap. Requires
    no credentials and writes nothing. Returns ``{is_wordpress, discovery_tier,
    types[], categories[], category_scope_supported, retryable, notes}``.
    ``retryable`` is True (and ``discovery_tier`` is ``"unreachable"``) when the
    probes couldn't reach the site, so the caller should offer a "Try again"
    rather than the definitive "no scoping available" message (SD2.5 / CLN0).
    """
    target_url, err = _normalise_and_validate_target(body.get("target_url", ""))
    if err is not None:
        return err
    # SSRF-guarded client: discovery follows redirects and fetches child-sitemap
    # / REST URLs, so it must re-check every hop (not just the validated target).
    async with make_ssrf_guarded_client() as client:
        result = await discover_scope(target_url, client)
    logger.info(
        "scope_discovered",
        extra={
            "target_url": target_url,
            "tier": result["discovery_tier"],
            "type_count": len(result["types"]),
        },
    )
    return result


async def _launch_crawl(
    *,
    target_url: str,
    settings: CrawlSettings,
    sitemap_url: str | None,
    priority_seed: dict | None,
    store: SQLiteJobStore,
    background_tasks: BackgroundTasks,
) -> dict | JSONResponse:
    """Resolve scope, create the job, and queue the background crawl.

    Purpose: give ``/start`` and ``/{job_id}/rescan`` ONE launch path. Two
             hand-maintained copies of a crawl launcher is the shape that lets
             a scope guard, a rate limit or a seed warning exist on one doorway
             and not the other.
    Spec:    docs/pending/2026-09-01_rescan-from-home.md#R1
    Tests:   tests/test_rescan_job.py, tests/test_crawl_scope.py

    ``priority_seed`` is already parsed and domain-guarded by the caller —
    ``/start`` parses an upload, a rescan reuses the stored one.
    """
    scope_notes: list[str] = []

    # Politeness guard (Phase 3, 2026-09-02): one crawl per domain at a time.
    # Two at once halve the crawl delay against the target's server, and the
    # second would be measuring a site under load from the first.
    host = (urlparse(target_url).hostname or "").lower().removeprefix("www.")
    # A running re-check (Phase 4) fetches the same host at the same delay.
    for jid, prog in _recheck_progress.items():
        if prog.get("running") and prog.get("host") == host:
            return _err(
                "RECHECK_IN_PROGRESS",
                f"A re-check of {host} is running (job {jid}, {prog['done']} of {prog['total']} pages). "
                f"Wait for it to finish before starting a crawl.",
                409,
            )
    active = await store.active_jobs_for_domain(host) if host else []
    if active:
        running = active[0]
        return _err(
            "CRAWL_IN_PROGRESS_FOR_DOMAIN",
            f"A scan of {host} is already {running.status} (job {running.job_id}). "
            f"Wait for it to finish, or cancel it, before starting another.",
            409,
        )

    # Partial scan: resolve the content-type selection into an authoritative URL
    # allowlist now, so a bad/empty selection fails fast with a clear message
    # rather than silently running a full crawl (P2/P6).
    scope_urls: set[str] | None = None
    if settings.content_scope.mode == "types":
        cs = settings.content_scope
        if not cs.type_keys and not cs.category_ids:
            return _err("INVALID_SCOPE", "Select at least one content type for a partial scan.", 422)
        async with make_ssrf_guarded_client() as client:
            resolved, scope_notes = await resolve_scope_urls(
                target_url, cs.type_keys, cs.category_ids, client
            )
        if not resolved:
            return _err(
                "SCOPE_EMPTY",
                "The selected content types could not be resolved to any pages. "
                "Try a Full scan, or reselect content types.",
                422,
            )
        scope_urls = resolved
        logger.info(
            "scope_resolved",
            extra={"target_url": target_url, "in_scope": len(scope_urls), "notes": scope_notes},
        )

    # GSC priority seed (U1/U2, optional), already parsed and domain-guarded by
    # the caller. A rescan reuses the seed stored on the source job, so the
    # crawl ordering carries over without re-uploading the file.
    priority_urls: list[str] | None = None
    if priority_seed:
        priority_urls = seed_urls(priority_seed)
        held = priority_seed["held_out_offdomain"] + priority_seed["held_out_blank"]
        note = f"GSC priority: seeded {priority_seed['used']} of {priority_seed['total']} pages"
        scope_notes.append(note + (f" ({held} held out)" if held else ""))
        # P9 — the seed is fronted before discovered links, so a seed as large as
        # the page budget silently turns "order" into "restrict". Warn loudly
        # (D-N1: seed orders, never restricts) rather than quietly narrowing.
        if settings.max_pages and len(priority_urls) >= settings.max_pages:
            scope_notes.append(
                f"GSC priority: {len(priority_urls)} seed pages ≥ the "
                f"{settings.max_pages}-page crawl budget — non-priority pages may not "
                f"be crawled. Raise 'Max pages' to crawl the rest.")

    job = CrawlJob(
        job_id=str(uuid4()),
        target_url=target_url,
        sitemap_url=sitemap_url,
        settings=settings,
        priority_seed=priority_seed,
    )
    await store.create_job(job)
    # Blob fields aren't in create_job's fixed INSERT — persist the seed via the
    # allowlisted update path so the background crawl (which re-fetches the job)
    # sees it for the post-crawl ledger join (U3).
    if priority_seed is not None:
        await store.update_job(job.job_id, priority_seed=priority_seed)

    cancel_event = asyncio.Event()
    _cancel_events[job.job_id] = cancel_event

    engine_settings = EngineCrawlSettings(
        max_pages=settings.max_pages,
        crawl_delay_ms=settings.crawl_delay_ms,
        respect_robots=settings.respect_robots,
        include_subdomains=settings.include_subdomains,
        enabled_analyses=settings.enabled_analyses,
        img_size_limit_kb=settings.img_size_limit_kb,
        suppress_h1_strings=settings.suppress_h1_strings,
        suppress_banner_h1=settings.suppress_banner_h1,
        single_page=settings.single_page,
        scope_urls=scope_urls,
        priority_urls=priority_urls,
    )

    background_tasks.add_task(
        _run_crawl_background,
        job.job_id,
        target_url,
        engine_settings,
        store,
        cancel_event,
    )

    logger.info("crawl_started", extra={"job_id": job.job_id, "target_url": target_url})

    resp = {
        "job_id": job.job_id,
        "status": "queued",
        "poll_url": f"/api/crawl/{job.job_id}/status",
    }
    # Surface partial-scan warnings (a type resolved short, a >5000-item cap, or
    # category scoping unavailable without REST) to the caller rather than only
    # to server logs (P9). max_pages usually bites before the 5000 cap, so this
    # is mostly the "type not found / category unsupported" signal.
    if scope_notes:
        resp["scope_notes"] = scope_notes
    return resp


@router.post("/start", status_code=202, response_model=None)
@limiter.limit(CRAWL_START_LIMIT)
async def start_crawl(
    request: Request,
    body: dict,
    background_tasks: BackgroundTasks,
    store: SQLiteJobStore = Depends(get_store),
) -> dict:
    """Submit a new crawl job (spec §6.4 POST /api/crawl/start)."""
    target_url, err = _normalise_and_validate_target(body.get("target_url", ""))
    if err is not None:
        return err

    settings_data: dict = body.get("settings") or {}
    try:
        settings = CrawlSettings(**{k: v for k, v in settings_data.items() if v is not None})
    except ValidationError as exc:
        # A bad setting value (e.g. info_detail="some") used to escape as a 500;
        # it is the caller's input, so say which field and why (P2).
        return _err("INVALID_SETTINGS", f"Invalid crawl settings: {exc.errors()[0].get('msg', exc)}", 422)

    # GSC priority upload (U1/U2, optional): the browser sends the parsed
    # priority_pages.json object in the body as `gsc_priority`. Domain-guarded; a
    # wrong-site/malformed file fails fast rather than silently seeding nothing.
    priority_seed: dict | None = None
    gsc_priority = body.get("gsc_priority")
    if gsc_priority:
        try:
            priority_seed = parse_priority_upload(gsc_priority, target_url)
        except PriorityUploadError as e:
            return _err("INVALID_PRIORITY_FILE", str(e), 422)

    return await _launch_crawl(
        target_url=target_url,
        settings=settings,
        sitemap_url=body.get("sitemap_url"),
        priority_seed=priority_seed,
        store=store,
        background_tasks=background_tasks,
    )


def _is_single_page_job(job: CrawlJob) -> bool:
    """Did this job scan exactly one page, rather than crawl a site?

    Spec:  docs/pending/2026-09-01_rescan-from-home.md#R2
    Tests: tests/test_rescan_job.py

    ``/scan-page`` created its job with DEFAULT ``CrawlSettings`` until
    2026-09-01, so ``single_page`` reads False on a job that scanned one page.
    Trusting that field alone would rescan every single-page audit already in
    the database as a full-site crawl — up to 500 pages against the user's
    server, from a button on a row that says "1 page", returning 202 and
    looking entirely successful.

    Three arms, newest evidence first, because no one of them covers the whole
    history:

    1. ``settings.single_page`` — jobs from 2026-09-01 describe themselves.
    2. The ``orphan_detection`` marker ``/scan-page`` writes — but only since
       2026-08-29, so it does NOT cover "every job that predates the fix"
       (an earlier version of this docstring claimed it did; measured against
       the owner's database, 49 of 167 jobs had neither field).
    3. ``pages_total == 1`` — the last resort for jobs older than the marker.
       A genuine whole-site crawl of a one-page site also matches, and rescans
       as a page scan rather than a crawl. That direction is the safe one: it
       skips sitemap seeding on a site with one page, versus launching a
       500-page crawl of a third party from a row labelled "1 page".
    """
    if job.settings and job.settings.single_page:
        return True
    marker = job.orphan_detection if isinstance(job.orphan_detection, dict) else {}
    if marker.get("status") == "skipped_single_page":
        return True
    return job.pages_total == 1


@router.post("/{job_id}/rescan", status_code=202, response_model=None)
@limiter.limit(CRAWL_START_LIMIT)
async def rescan_job(
    request: Request,
    job_id: str,
    background_tasks: BackgroundTasks,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Re-run a past scan with the settings it was originally run with.

    Spec:  docs/pending/2026-09-01_rescan-from-home.md#R1
    Tests: tests/test_rescan_job.py

    Creates a NEW job and never touches the source one: the previous scan is
    what ``/{job_id}/comparison`` measures the new one against, so overwriting
    it would destroy the very thing a rescan is usually run to produce.

    Carries the same rate limit as ``/start`` — a second unrated doorway into
    the crawl launcher is a bypass of an existing control, not a new feature.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    if job.status in ("queued", "running"):
        return _err(
            "CRAWL_IN_PROGRESS",
            "This scan is still running. Wait for it to finish, or cancel it, before rescanning.",
            409,
        )

    # Re-validate the STORED url. SSRF safety is a property of now, not of when
    # the URL was first accepted: the host may have been re-pointed at a private
    # address since. A stored URL is caller-supplied input that has been sitting
    # in a database.
    target_url, err = _normalise_and_validate_target(job.target_url)
    if err is not None:
        return err

    if _is_single_page_job(job):
        # Calls the shared helper, not the endpoint: a route handler's
        # `Query(False)` default arrives as a truthy Query OBJECT when invoked
        # in-process, which would silently sign in to WordPress and audit
        # drafts. Unauthenticated is also the right answer here — whether the
        # original was a draft scan is not recorded on the job.
        result = await _run_single_page_scan(
            url=target_url, authenticated=False, store=store,
            # The whole point of a rescan: run it the way the source ran.
            reuse_settings=job.settings or CrawlSettings(),
            # A rescan is asked "did my fix land", so it must not answer from a
            # cached copy of the page — same reason /rescan-url bypasses.
            bypass_cache=True,
        )
        if isinstance(result, JSONResponse):
            return result
        return {
            # Spread first so the scan's own disclosures (checks_not_run and
            # its reason — the 24 codes this path cannot run) survive; the
            # rescan's keys below still win. Absence is never a pass.
            **result,
            "job_id": result["job_id"],
            "source_job_id": job_id,
            "mode": "single_page",
            "status": "complete",
            "poll_url": f"/api/crawl/{result['job_id']}/status",
        }

    launched = await _launch_crawl(
        target_url=target_url,
        settings=job.settings or CrawlSettings(),
        sitemap_url=job.sitemap_url,
        priority_seed=job.priority_seed,
        store=store,
        background_tasks=background_tasks,
    )
    if isinstance(launched, JSONResponse):
        return launched

    logger.info("crawl_rescanned",
                extra={"job_id": launched["job_id"], "source_job_id": job_id,
                       "target_url": target_url})
    return {**launched, "source_job_id": job_id, "mode": "crawl"}


@router.get("/{job_id}", response_model=None)
async def get_job(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Get job details by ID (returns target_url and other metadata)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    return {
        "job_id": job.job_id,
        "target_url": job.target_url,
        "status": job.status,
        "pages_crawled": job.pages_crawled,
        "pages_total": job.pages_total,
        # Info detail (2026-09-01): the level the scan was run and scored at.
        "settings": job.settings.model_dump(),
    }


@router.get("/{job_id}/status", response_model=None)
async def job_status(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Return job progress and status (spec §6.4 GET /status)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    estimated: int | None = None
    if (
        job.pages_total is not None
        and job.pages_crawled >= 5
        and job.pages_crawled < job.pages_total
        and job.started_at
    ):
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        rate = elapsed / job.pages_crawled if job.pages_crawled else 0
        remaining = job.pages_total - job.pages_crawled
        estimated = int(rate * remaining)

    return {
        "job_id": job.job_id,
        "status": job.status,
        "pages_crawled": job.pages_crawled,
        "pages_total": job.pages_total,
        "current_url": job.current_url,
        "started_at": job.started_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "estimated_seconds_remaining": estimated,
        "error_message": job.error_message,
    }


@router.post("/{job_id}/cancel", response_model=None)
async def cancel_job(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Cancel a running crawl (spec §6.4 POST /cancel)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    if job.status in ("complete", "failed", "cancelled"):
        return _err("JOB_ALREADY_COMPLETE", "This job has already finished and cannot be cancelled.", 409)

    if job.status == "queued":
        # Background task hasn't started — cancel directly
        await store.update_job(
            job_id,
            status="cancelled",
            completed_at=datetime.now(timezone.utc),
        )
    else:
        # Signal the running engine. After a restart there is no engine and
        # no event; the row is orphaned, so write the cancellation directly —
        # returning "cancelled" without writing it left the domain blocked
        # and the user told otherwise (Phase 3 sweep, 2026-09-02).
        event = _cancel_events.get(job_id)
        if event:
            event.set()
        else:
            await store.update_job(
                job_id, status="cancelled", completed_at=datetime.now(timezone.utc),
                error_message="Cancelled after a server restart; the scan was no longer running.",
            )

    return {"job_id": job_id, "status": "cancelled"}


@router.get("/{job_id}/results", response_model=None)
async def get_results(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    severity: str | None = Query(None),
    info_detail: str | None = Query(None, description="Reveal-only override of the scan's info detail (e.g. 'all')"),
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Paginated results for a completed job (spec §6.4 GET /results)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    from api.services.info_tier_filter import resolve_info_detail
    level = resolve_info_detail(job.settings.info_detail, info_detail)
    exempt_urls = await store.get_exempt_anchor_url_set()
    issue_dicts, total, filtered, info_filtered = await _paginate_filtered(
        store, job, severity=severity, page=page, limit=limit, exempt_urls=exempt_urls,
        info_detail=level)
    summary = await store.get_summary(job_id)
    total_pages = max(1, math.ceil(total / limit)) if total else 1

    # R5.4 — Quick-Wins list: every issue satisfying impact>=4 AND effort<=1,
    # independent of the paginated `issues` slice and of priority ordering. The
    # membership predicate is the Issue.quick_win computed field (single source
    # of truth), so this can never diverge from the per-issue `quick_win` flag.
    all_issues = await store.get_all_issues(job_id)
    quick_wins = _apply_exempt_anchors(
        [_issue_dict(i) for i in all_issues if i.quick_win], exempt_urls
    )
    # A quick win the reader cannot find anywhere in the list on the same
    # screen is worse than no quick win at all.
    quick_wins, _ = await _filter_for_domain(store, job.target_url, quick_wins)

    # E4 — the prevalence lens alongside per-page severity. Scoring is untouched;
    # this only tells the reader how much of the estate one defect touches.
    summary = _with_prevalence(summary, await _prevalence_for_display(store, job, job_id))

    return {
        "job_id": job_id,
        "summary": summary,
        "pagination": {"page": page, "limit": limit, "total_issues": total, "total_pages": total_pages},
        "issues": issue_dicts,
        "quick_wins": quick_wins,
        # R5.6 — scoring-model version stamp for this audit (None on legacy
        # audits saved before the field existed).
        "scoring_model_version": job.scoring_model_version,
        # F1 — what the domain filter removed. Always present, so a shorter
        # list can never be mistaken for a cleaner site.
        "filtered": filtered,
        # Info detail (2026-09-01) — what the scan's level left out of this
        # list AND the score. Always present, for the same reason.
        "info_filtered": info_filtered,
    }


@router.get("/{job_id}/results/{category}", response_model=None)
async def get_results_by_category(
    job_id: str,
    category: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=5000),
    severity: str | None = Query(None),
    info_detail: str | None = Query(None, description="Reveal-only override of the scan's info detail (e.g. 'all')"),
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Paginated results filtered by category (spec §6.4 GET /results/{category})."""
    if category not in _VALID_CATEGORIES:
        return _err(
            "INVALID_CATEGORY",
            f"'{category}' is not a valid category. Valid values: {sorted(_VALID_CATEGORIES)}",
            422,
        )

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    from api.services.info_tier_filter import resolve_info_detail
    level = resolve_info_detail(job.settings.info_detail, info_detail)
    exempt_urls = await store.get_exempt_anchor_url_set()
    # Same fetch-filter-slice path as /results, so a category page can never
    # advertise pages the info level emptied.
    issue_dicts, total, filtered, info_filtered = await _paginate_filtered(
        store, job, severity=severity, category=category, page=page, limit=limit,
        exempt_urls=exempt_urls, info_detail=level)
    summary = await store.get_summary(job_id)
    total_pages = max(1, math.ceil(total / limit))

    return {
        "job_id": job_id,
        "summary": summary,
        "pagination": {"page": page, "limit": limit, "total_issues": total, "total_pages": total_pages},
        "issues": issue_dicts,
        # F1 — what the domain filter removed. Always present, so a shorter
        # list can never be mistaken for a cleaner site.
        "filtered": filtered,
        "info_filtered": info_filtered,
    }


@router.get("/{job_id}/pages", response_model=None)
async def get_pages(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    min_severity: str | None = Query(None),
    info_detail: str | None = Query(None, description="Reveal-only override of the scan's info detail (e.g. 'all')"),
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """All crawled pages with per-page issue counts (spec §6.1, By Page view)."""
    # `_SEVERITY_RANK.get(x, 4)` in the store admits every severity for an
    # unrecognised value, so an unvalidated typo silently meant "everything" —
    # `?min_severity=Critical` quietly stopped filtering. Refused here beside the
    # other input validation, and NOT in the store, whose rank default also
    # encodes the legitimate "no filter at all" case.
    if min_severity is not None and min_severity not in _VALID_SEVERITIES:
        return _err(
            "INVALID_SEVERITY",
            f"'{min_severity}' is not a valid severity. Valid values: "
            f"{sorted(_VALID_SEVERITIES)}.",
            422,
        )

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    from api.services.info_tier_filter import resolve_info_detail
    level = resolve_info_detail(job.settings.info_detail, info_detail)

    pages, total_crawled, pages_hidden = await store.get_pages_with_issue_counts(
        job_id, min_severity=min_severity, page=page, limit=limit,
        info_detail=level,
    )
    total_pages = max(1, math.ceil(total_crawled / limit))

    # E5: attach the per-page GEO/citability grade (rollup of ai_readiness
    # issues) so the By-Page view can show it as a column. Computed in the
    # router — the store's count aggregate has no per-issue impact/category —
    # mirroring the /page-priority endpoint's use of compute_citability_grade.
    from api.services.job_store_base import compute_citability_grade

    # CLN7 (P9): scope the issue load to just the ≤`limit` page URLs being graded
    # here, instead of reconstructing every Issue in the job on each paginated
    # request (get_all_issues).
    page_urls = [pg.get("url") for pg in pages if pg.get("url")]
    issues = await store.get_issues_for_urls(job_id, page_urls)
    # CLN5: drop user-suppressed codes before grading so the citability column
    # reconciles with site health (get_summary already drops them). Suppression
    # is SQLite-only; on Redis this no-ops, matching Redis get_summary.
    _gs = getattr(store, "get_suppressed_codes", None)
    suppressed = set(await _gs()) if _gs else set()
    rows_by_url: dict[str, list[tuple[str, int, str]]] = {}
    for issue in issues:
        if issue.page_url and issue.issue_code not in suppressed:
            rows_by_url.setdefault(issue.page_url.rstrip("/"), []).append(
                (issue.issue_code, issue.impact or 0, issue.category or "")
            )
    for pg in pages:
        pg["citability_grade"] = compute_citability_grade(
            rows_by_url.get((pg.get("url") or "").rstrip("/"), []),
            info_detail=level,
        )

    # P5.3: the same disclosure the other three list endpoints carry, plus the
    # one only this endpoint needs. On /results the level removes ROWS and the
    # shorter list is itself visible; here it removes whole PAGES from the page
    # list, and a page that is not listed leaves no other trace (P31).
    # Job-wide, deliberately: summing `info_excluded` over the RETURNED rows
    # misses the rows on pages the level removed from the list entirely — which
    # are exactly the ones `pages_hidden` is counting. It is also stable across
    # pagination, so page 2 does not report a different site.
    excluded_report = await store.get_info_excluded_report(job_id, level)

    return {
        "job_id": job_id,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages_crawled": job.pages_crawled,
            "total_pages": total_pages,
        },
        "pages": pages,
        "info_filtered": {
            **excluded_report,
            "info_detail": level,
            "pages_hidden": pages_hidden,
        },
    }


@router.get("/{job_id}/pages/issues", response_model=None)
async def get_page_issues(
    job_id: str,
    url: str = Query(..., description="Exact URL of the crawled page"),
    info_detail: str | None = Query(None, description="Reveal-only override of the scan's info detail (e.g. 'all')"),
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """All issues for one specific page, grouped by category (spec §6.1, By Page view)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    crawled_page, by_category = await store.get_page_issues_by_url(job_id, url)
    if crawled_page is None:
        return _err("PAGE_NOT_FOUND", f"No crawled page found with URL: {url}", 404)

    exempt_urls = await store.get_exempt_anchor_url_set()

    # Filter exempted anchor hrefs from LINK_EMPTY_ANCHOR before counting/returning
    filtered_by_category = {
        cat: _apply_exempt_anchors([_issue_dict(i) for i in issues], exempt_urls)
        for cat, issues in by_category.items()
    }
    # Info detail (2026-09-01): the drawer shows the scan's audit scope, same
    # predicate as the score; the excluded count travels with the response.
    from api.services.info_tier_filter import annotate_scored, apply_info_detail, resolve_info_detail
    level = resolve_info_detail(job.settings.info_detail, info_detail)
    info_hidden = 0
    info_by_tier: dict[str, int] = {}
    for cat, issues in list(filtered_by_category.items()):
        kept, rep_ = apply_info_detail(annotate_scored(issues, job.settings.info_detail), level)
        filtered_by_category[cat] = kept
        info_hidden += rep_["hidden"]
        for t, n in rep_["by_tier"].items():
            info_by_tier[t] = info_by_tier.get(t, 0) + n
    # Drop empty categories after filtering
    filtered_by_category = {cat: issues for cat, issues in filtered_by_category.items() if issues}

    total = sum(len(v) for v in filtered_by_category.values())

    # Agent-readiness Phase 1 (WP6): a flat list of the agent-relevant issues on
    # this page, each with its evidence tier (confidence label, falling back to
    # severity). Lets the UI surface "what an agent sees" without re-deriving the
    # agent-relevant set client-side.
    from api.services.job_store_base import _is_agent_issue
    agent_issues = [
        {
            "code": i["issue_code"],
            "severity": i["severity"],
            "category": i["category"],
            "tier": i.get("confidence_label") or i["severity"],
        }
        for issues in filtered_by_category.values()
        for i in issues
        if _is_agent_issue(i["category"], i["issue_code"])
    ]

    # Include the raw page fields so the UI can show the actual offending content
    # (title text, meta description, H1s, robots directive, etc.) per issue.
    page_data = {
        "title":            crawled_page.title,
        "meta_description": crawled_page.meta_description,
        "h1_tags":          crawled_page.h1_tags,
        "headings_outline": crawled_page.headings_outline,
        "canonical_url":    crawled_page.canonical_url,
        "robots_directive": crawled_page.robots_directive,
        "redirect_chain":   crawled_page.redirect_chain,
        "redirect_url":     crawled_page.redirect_url,
        "og_title":         crawled_page.og_title,
        "og_description":   crawled_page.og_description,
        "amphtml_url":      crawled_page.amphtml_url,
        "meta_refresh_url": crawled_page.meta_refresh_url,
        "response_size_bytes": crawled_page.response_size_bytes,
        "word_count":       crawled_page.word_count,
        # M5: AI citation fields
        "ai_citation_count_30d": crawled_page.ai_citation_count_30d,
        "ai_citation_engines":   crawled_page.ai_citation_engines,
    }

    return {
        "job_id": job_id,
        "url": url,
        "status_code": crawled_page.status_code,
        "total_issues": total,
        "page_data": page_data,
        "by_category": filtered_by_category,
        "agent_issues": agent_issues,
        "info_filtered": {"hidden": info_hidden, "by_tier": info_by_tier, "info_detail": level},
    }


@router.post("/{job_id}/rescan-url", response_model=None)
async def rescan_url(
    job_id: str,
    url: str = Query(..., description="The crawled page URL to rescan"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Re-fetch a single page and update its issues in the database.

    Useful for verifying that a fix worked. Replaces the stored issues for
    this URL with the results from a fresh fetch and issue check.
    """
    # `_lookup_crawled_page` owns the normalisation: it must try the caller's
    # own spelling BEFORE the normalised one, or a job holding both spellings of
    # its home page is re-checked on the row the operator is not looking at.
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    crawled_page, old_by_cat, url = await _lookup_crawled_page(store, job_id, url)
    if crawled_page is None:
        return _err("PAGE_NOT_FOUND", f"No crawled page found with URL: {url}", 404)
    # Include broken-link issue codes where this URL is the source page
    # (stored under dead-URL page_url, so not returned by get_page_issues_by_url)
    old_codes: set[str] = {i.issue_code for issues in old_by_cat.values() for i in issues}
    old_codes |= await store.get_broken_link_codes_for_source(job_id, url)

    base_url = job.target_url
    suppress_h1s: list[str] = job.settings.suppress_h1_strings if job.settings else []

    # ── Fetch, parse, check issues (shared logic) ─────────────────────
    check = await _fetch_and_check_page(
        url=url,
        job_id=job_id,
        base_url=base_url,
        store=store,
        suppress_h1_strings=suppress_h1s,
        suppress_banner_h1=True,
        bypass_cache=True,
    )
    if isinstance(check, JSONResponse):
        return check

    page = check.page
    result = check.fetch_result
    new_issues = check.issues
    exempt_urls = check.exempt_urls

    # E1.2 — bail out before ANY write when the fetch told us nothing.
    # issue_for_status covers 404/410/503/5xx; every other 4xx yields None, so
    # a Cloudflare block (403) or a rate limit (429) produced an empty issue
    # list. Continuing past here did two irreversible things: it overwrote the
    # stored page record with the ERROR page's parse (losing the real title,
    # H1 and word count), and it deleted the URL's findings and wrote them to
    # the fixed-issues ledger as RESOLVED. A transient block became a
    # permanent positive in data the operator acts on (P1), silently (P2).
    if not _rescan_is_conclusive(result.status_code):
        existing = sum(len(v) for v in old_by_cat.values())
        logger.warning(
            "rescan_inconclusive",
            extra={"job_id": job_id, "url": url, "status": result.status_code},
        )
        return {
            "url": url,
            "status_code": result.status_code,
            "page_unreadable": True,
            "old_count": existing,
            "new_count": existing,
            "resolved": 0,
            "added": 0,
            "resolved_codes": [],
            # Present-and-empty rather than absent: a consumer must not have to
            # branch on which shape of this response it received. Nothing was
            # evaluated, so every stored finding is carried over unchecked.
            "still_present_codes": [],
            "newly_found_codes": [],
            # The same meaning as on the conclusive branch: findings kept
            # because this path cannot evaluate them. It was sorted(old_codes),
            # which also swept in the broken-link codes for this source URL and
            # paired them with checks_not_run_reason ("only run during a full
            # crawl") — false for those, and inconsistent with by_category and
            # total_issues, which count only old_by_cat. The caveat already
            # states the stronger fact that NOTHING was re-checked.
            "carried_over_codes": sorted(old_codes & set(
                _checks_a_single_page_scan_cannot_run())),
            "total_issues": existing,
            "by_category": {
                k: [_issue_dict(i) | {"rechecked": False} for i in v]
                for k, v in old_by_cat.items()
            },
            "caveat": (
                f"The page could not be read (HTTP {result.status_code}), so "
                "nothing was re-checked and no finding was marked fixed. "
                "Stored results are unchanged. A 403 or 429 is usually bot "
                "protection or rate limiting rather than a change to the page."
            ),
            "checks_not_run": _checks_a_single_page_scan_cannot_run(),
            "checks_not_run_reason": _CHECKS_NOT_RUN_REASON,
        }

    # Update the stored page record with fresh data from the rescan.
    # crawl_depth is preserved from the original record (single-page rescan has no depth context).
    updated_page = _engine_page_to_model(page, job_id)
    updated_page.url = url
    updated_page.status_code = result.status_code
    updated_page.redirect_url = result.final_url if result.is_redirect else None
    if crawled_page:
        updated_page.crawl_depth = crawled_page.crawl_depth
        updated_page.page_id = crawled_page.page_id
    await store.save_pages([updated_page])

    # D5 — a re-check may not clear what it could not check.
    #
    # This path never calls check_cross_page and passes sitemap_urls=None, so
    # the codes flagged needs_full_crawl cannot be produced here (the flag is
    # AST-bound to the checkers by test_single_page_scan_discloses_inert_checks).
    # Without this gate they were deleted, dropped from the health score, AND
    # written to the fixed-issues ledger on every re-check — the same response
    # naming them in `checks_not_run` while reporting them resolved.
    #
    # E1.2 gated on the FETCH telling us nothing. Nothing gated on the CHECK
    # not running, which fails on a perfectly successful 200.
    #
    # Derived from the registry, never listed here: a literal copy would
    # recreate the hand-mirrored enumeration D2 exists to prevent (P19).
    # Spec:  docs/functional-specification.md (D5)
    # Tests: tests/test_rescan_reports_what_it_checked.py
    unrunnable: set[str] = set(_checks_a_single_page_scan_cannot_run())
    # ...except when the page is GONE. _rescan_is_conclusive treats 404/410 as
    # conclusive precisely because "the page is gone, its old findings genuinely
    # no longer apply" — so carrying findings over there would keep ORPHAN_PAGE
    # and TITLE_DUPLICATE charging the health score for a page that no longer
    # exists, clearable only by a full crawl, and would print "Not re-checked:
    # Orphan page" beside a 404. It would also partly undo E1, whose rule is
    # that an error page is not content. Carry over only what still exists.
    page_is_gone = result.status_code in (404, 410)
    carried_over = [] if page_is_gone else [
        issue
        for issues in old_by_cat.values()
        for issue in issues
        if issue.issue_code in unrunnable
    ]

    # Replace stored issues for this URL.
    # Two passes: (1) issues with page_url = url (metadata, heading, etc.)
    #             (2) broken-link issues stored with page_url = dead_url but
    #                 extra.source_url = url — these are missed by pass 1.
    old_count = await store.delete_issues_for_url(job_id, url)
    old_count += await store.delete_broken_link_issues_for_source(job_id, url)
    # Carried-over findings are re-saved so they stay in the results list and
    # keep charging the health score. Retaining one a full crawl would now
    # clear is the recoverable error; silently clearing one is not, and the
    # ledger write cannot be undone by re-running.
    await store.save_issues(new_issues + carried_over)

    # Record which issue codes were resolved (present before, gone after, and
    # actually evaluated). Nothing enters the ledger without a check behind it.
    new_codes: set[str] = {i.issue_code for i in new_issues}
    # When the page is gone its findings genuinely no longer apply — including
    # the unrunnable ones, which is why `unrunnable` is not subtracted there.
    resolved_codes = sorted(
        (old_codes - new_codes) if page_is_gone
        else ((old_codes - new_codes) - unrunnable)
    )
    if resolved_codes:
        await store.record_fixed_issues(job_id, url, resolved_codes)

    # Code-level outcomes. Deliberately the same vocabulary as
    # /fix-focus/verify-page (verified / still_present / newly_found): two
    # surfaces reporting the same event must not invent two dialects for it.
    # These are NOT the count deltas below — three IMG_ALT_MISSING rows reduced
    # to one is `resolved: 2` with `resolved_codes: []`. Both true, different
    # questions.
    still_present_codes = sorted((old_codes & new_codes) - unrunnable)
    newly_found_codes = sorted(new_codes - old_codes)
    carried_over_codes = sorted({i.issue_code for i in carried_over})

    by_category: dict[str, list] = {}
    for issue in new_issues:
        by_category.setdefault(issue.category, []).append(
            _issue_dict(issue) | {"rechecked": True})
    # Carried-over findings travel in the response too. Kept in the database
    # but dropped from the payload, they would be invisible to the panel —
    # the same failure by a quieter route.
    for issue in carried_over:
        by_category.setdefault(issue.category, []).append(
            _issue_dict(issue) | {"rechecked": False})
    # Apply exempt filter to the response (issues were stored without exemption filtering)
    by_category = {
        cat: _apply_exempt_anchors(issues, exempt_urls)
        for cat, issues in by_category.items()
    }
    by_category = {cat: issues for cat, issues in by_category.items() if issues}

    rescan_page_data = {
        "title":              page.title,
        "meta_description":   page.meta_description,
        "h1_tags":            page.h1_tags,
        "headings_outline":   page.headings_outline,
        "canonical_url":      page.canonical_url,
        "robots_directive":   page.robots_directive,
        "redirect_chain":     result.redirect_chain,
        "redirect_url":       result.final_url if result.is_redirect else None,
        "og_title":           page.og_title,
        "og_description":     page.og_description,
        "amphtml_url":        page.amphtml_url,
        "meta_refresh_url":   page.meta_refresh_url,
        "response_size_bytes": None,
        "word_count":         page.word_count,
    }

    filtered_count = sum(len(v) for v in by_category.values())

    return {
        "url": url,
        "status_code": result.status_code,
        "old_count": old_count,
        "new_count": filtered_count,
        "resolved": max(0, old_count - filtered_count),
        "added": max(0, filtered_count - old_count),
        "resolved_codes": resolved_codes,
        "still_present_codes": still_present_codes,
        "newly_found_codes": newly_found_codes,
        # D5 — findings kept without being evaluated. Named so the panel can
        # show them as "not re-checked" rather than as a pass or a clearance.
        "carried_over_codes": carried_over_codes,
        "total_issues": filtered_count,
        "page_data": rescan_page_data,
        "by_category": by_category,
        # D2 — a rescan runs the same single-page path as /scan-page, so the
        # same codes are unreachable. Without this, `resolved` on a rescan can
        # read as "these are now fixed" when the check simply never ran.
        "checks_not_run": _checks_a_single_page_scan_cannot_run(),
        "checks_not_run_reason": _CHECKS_NOT_RUN_REASON,
    }


_CAPTURE_CAP_NOTE = (
    "The crawler records a limited number of examples per finding, so this list "
    "can be shorter than the total. The total is what the page actually has."
)


def _details_for_issues(issues, *, only_code: str | None) -> list[dict]:
    """Render one entry per issue code, with every captured row.

    D6 — uses the SHARED renderer with the row cap lifted. A second formatter
    here would drift from the one the panel, the PDF and the Excel all use,
    which is the P19 issue_evidence.py was written to prevent.
    """
    from api.services.issue_evidence import (
        PAGE_IS_THE_EVIDENCE, UNCAPPED, evidence_summary,
    )

    out: list[dict] = []
    for issue in issues:
        code = issue.issue_code
        if only_code and code != only_code:
            continue
        extra = getattr(issue, "extra", None)
        try:
            lines, total, rendered = evidence_summary(code, extra, row_cap=UNCAPPED)
        except Exception:  # noqa: BLE001 — detail must never 500 the panel
            logger.warning("details_evidence_failed", extra={"code": code}, exc_info=True)
            lines, total, rendered = [], 0, 0
        out.append({
            "issue_code": code,
            "description": getattr(issue, "description", ""),
            "items": lines,
            "items_total": total,
            # Evidence ROWS in `items`, not len(items): `items` also holds one
            # heading per key and an "... and N more" line, so comparing against
            # its length under-reports truncation by that overhead.
            "items_shown": rendered,
            "evidence_basis": "page" if code in PAGE_IS_THE_EVIDENCE else "items",
            # True when the CRAWL kept fewer rows than the page has. Lifting the
            # render cap cannot recover those: capture truncation is scattered
            # literal slices across the checkers, not one constant. Stated
            # rather than papered over — a list that is short for a reason the
            # reader cannot see is the failure this whole feature exists to fix.
            "truncated_at_capture": total > rendered,
            # This entry came from a check that actually ran. Entries for checks
            # that did NOT run are added by the caller with evaluated=False —
            # the distinction the frontend needs before it may say a finding is
            # gone. Absence must never be read as a pass.
            "evaluated": True,
        })
    return out


def _unevaluated_entries(codes, *, only_code: str | None, reason: str) -> list[dict]:
    """Entries for codes this read could not evaluate. Never omitted.

    D6 — a code that is simply MISSING from `details` is indistinguishable from
    one that was checked and found gone, and the panel renders the latter as a
    green all-clear. That is the E1.2/D5 failure arriving through a third door,
    so an un-evaluated code travels with a reason instead of vanishing.
    """
    return [
        {
            "issue_code": code,
            "description": "",
            "items": [],
            "items_total": 0,
            "items_shown": 0,
            "evidence_basis": "items",
            "truncated_at_capture": False,
            "evaluated": False,
            "not_evaluated_reason": reason,
        }
        for code in sorted(codes)
        if not only_code or code == only_code
    ]


@router.get("/{job_id}/page-details", response_model=None)
@limiter.limit(DETAILS_LIMIT)
async def get_page_details(
    request: Request,
    job_id: str,
    url: str = Query(..., description="The crawled page URL to read in full"),
    code: str | None = Query(
        None,
        description="Limit the answer to this issue code. Omit for every issue on the page.",
    ),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """D6 — the offending items for a page, read LIVE and stored nowhere.

    Answers "which links / images / fields are the problem", uncapped by the
    10-row render limit the list endpoints use, and from the page as it is right
    now rather than as it was at crawl time — which is what an operator part-way
    through fixing it actually wants.

    Writes nothing. This is the one read-only path through
    `_fetch_and_check_page`; `tests/test_page_details_endpoint.py` snapshots the
    store either side and requires it unchanged.

    Spec:  docs/functional-specification.md (D6)
    """
    # Normalisation lives in `_lookup_crawled_page` — the caller's own spelling
    # is resolved first, so the panel and the endpoint agree on which row.
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    crawled_page, old_by_cat, url = await _lookup_crawled_page(store, job_id, url)
    if crawled_page is None:
        return _err("PAGE_NOT_FOUND", f"No crawled page found with URL: {url}", 404)

    suppress_h1s: list[str] = job.settings.suppress_h1_strings if job.settings else []
    check = await _fetch_and_check_page(
        url=url,
        job_id=job_id,
        base_url=job.target_url,
        store=store,
        suppress_h1_strings=suppress_h1s,
        suppress_banner_h1=True,
        bypass_cache=True,
        # Answering "which items on this page" needs the parse, not a re-audit
        # of somebody else's links. Left on, every click cost up to
        # _EXTERNAL_LINK_CAP_PER_PAGE (50) outbound third-party requests, and
        # the panel calls this once per issue code. The broken-link codes are
        # reported un-evaluated below rather than silently absent.
        check_external_links=False,
    )
    if isinstance(check, JSONResponse):
        return check

    status_code = check.fetch_result.status_code
    stored = [i for issues in old_by_cat.values() for i in issues]
    stored_codes = {i.issue_code for i in stored}

    # Codes this read could not speak to. Absence is not a pass, so each one
    # travels as an entry with evaluated=False and a reason (D6).
    unrunnable = set(_checks_a_single_page_scan_cannot_run())
    link_codes = {c for c in stored_codes
                  if c.startswith(("BROKEN_LINK", "EXTERNAL_LINK", "REDIRECT_"))}

    # E1.2 / D5, third application. A page we could not read tells us nothing
    # about what is on it now. Fall back to the stored evidence, but LABEL it —
    # answering "what is on my page right now" with crawl-time data because the
    # fetch failed is the same false positive D5 removed, wearing a fresh coat.
    if not _rescan_is_conclusive(status_code):
        return {
            "url": url,
            "status_code": status_code,
            "source": "stored",
            "page_unreadable": True,
            "page_gone": False,
            "captured_at": crawled_page.crawled_at.isoformat()
            if getattr(crawled_page, "crawled_at", None) else None,
            "details": _details_for_issues(stored, only_code=code),
            "caveat": (
                f"The page could not be read (HTTP {status_code}), so these are "
                "the items recorded during the last crawl, not what is on the "
                "page now. A 403 or 429 is usually bot protection or rate "
                "limiting rather than a change to the page."
            ),
            "capture_cap_note": _CAPTURE_CAP_NOTE,
        }

    # A 404/410 is conclusive — the page is genuinely gone — but that is NOT the
    # same as "these findings are fixed". Without this branch the live read
    # returned an empty `details` for every code except BROKEN_LINK_404, and the
    # panel rendered each one as "no longer on the page as it is now" for a page
    # that had been unpublished. Same shape as D5, arriving through the branch
    # D5 did not cover.
    if result_page_gone := status_code in (404, 410):
        return {
            "url": url,
            "status_code": status_code,
            "source": "live",
            "page_unreadable": False,
            "page_gone": result_page_gone,
            "details": _details_for_issues(check.issues, only_code=code)
            + _unevaluated_entries(
                stored_codes - {i.issue_code for i in check.issues},
                only_code=code,
                reason=(
                    f"The page returns HTTP {status_code} — it is gone, not "
                    "fixed. These findings were not re-checked because there "
                    "is no page left to check them against."
                ),
            ),
            "caveat": (
                f"This page returns HTTP {status_code}. Its findings were not "
                "re-checked — a page that no longer exists is not a page that "
                "was repaired."
            ),
            "capture_cap_note": _CAPTURE_CAP_NOTE,
        }

    return {
        "url": url,
        "status_code": status_code,
        "source": "live",
        "page_unreadable": False,
        "page_gone": False,
        "details": _details_for_issues(check.issues, only_code=code)
        + _unevaluated_entries(
            (stored_codes & unrunnable),
            only_code=code,
            reason=_CHECKS_NOT_RUN_REASON,
        )
        + _unevaluated_entries(
            link_codes,
            only_code=code,
            reason=(
                "Links to other sites are not re-checked here, because doing so "
                "would fetch every one of them on every click. Use the broken-link "
                "verification in the Broken Links category to re-check them."
            ),
        ),
        "capture_cap_note": _CAPTURE_CAP_NOTE,
        # D5 — the same disclosure a rescan carries. A live read of one page
        # cannot evaluate these, so their absence here is not a pass.
        "checks_not_run": _checks_a_single_page_scan_cannot_run(),
        "checks_not_run_reason": _CHECKS_NOT_RUN_REASON,
    }


@router.post("/scan-page", response_model=None)
async def scan_single_page(
    url: str = Query(..., description="The page URL to fetch and analyse"),
    authenticated: bool = Query(
        False,
        description=(
            "Sign in to WordPress before fetching, so an unpublished draft can "
            "be audited before it goes live. Single page only; a draft is "
            "invisible to search engines, so its findings are pre-publication "
            "advice, not an audit of anything live."
        ),
    ),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Create a new single-page job, fetch the URL, run issue checks, and return the job_id.

    The caller can navigate straight to /results/{job_id} — no polling needed
    because the scan runs synchronously before this endpoint returns.
    """
    return await _run_single_page_scan(
        url=url, authenticated=authenticated, store=store
    )


async def _run_single_page_scan(
    *,
    url: str,
    authenticated: bool,
    store,
    reuse_settings: CrawlSettings | None = None,
    bypass_cache: bool = False,
) -> dict | JSONResponse:
    """The single-page scan itself — shared by ``/scan-page`` and a rescan.

    Spec:  docs/pending/2026-09-01_rescan-from-home.md#R2
    Tests: tests/test_rescan_job.py

    A plain function, NOT the endpoint, because FastAPI adopts any plainly
    defaulted argument on a route handler into its HTTP signature: adding
    ``bypass_cache`` to `scan_single_page` silently published
    ``/scan-page?bypass_cache=true`` as a public query parameter.

    ``reuse_settings`` is what makes a rescan reproduce the original scan.
    Without it this path re-derived suppression from "the most recent completed
    job for this ORIGIN", which for a page URL is almost never the source job —
    measured, it dropped ``suppress_h1_strings`` and inverted
    ``suppress_banner_h1``, so an unchanged page reported H1 findings its first
    scan had suppressed and the before/after showed a regression that had not
    happened.
    """
    from urllib.parse import urlparse

    if not url or not url.startswith(("http://", "https://")):
        return _err("INVALID_URL", "url must be a valid http or https URL.", 422)

    try:
        url = normalise_url(url)
    except ValueError as e:
        logger.debug(f"Could not normalize URL {url}: {e}")

    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    job = CrawlJob(
        target_url=url,
        status="running",
        pages_crawled=0,
        pages_total=1,
        # R2 (2026-09-01) — record HOW this job ran. Until this line, a
        # single-page scan stored `single_page=False`, so anything reading the
        # settings back to reproduce the job (the Rescan button) would launch a
        # full-site crawl from a one-page audit. `single_page` is read only when
        # building EngineCrawlSettings at crawl start, never in scoring or
        # reporting, so recording it changes nothing else.
        #
        # A rescan carries the SOURCE job's settings through, so the new job's
        # record says what it actually ran with rather than defaults.
        settings=(reuse_settings.model_copy(update={"single_page": True})
                  if reuse_settings else CrawlSettings(single_page=True)),
    )
    await store.create_job(job)
    job_id = job.job_id
    # O2: a single-page scan never builds a link graph, so orphan detection
    # cannot have run — record that, or the panel treats this job like a legacy
    # full crawl and prints the green all-clear (P31). Written via update_job,
    # not on the model: create_job's INSERT is a fixed column list and would
    # drop the field silently (same reason priority_seed is written this way).
    await store.update_job(job_id, orphan_detection={
        "status": "skipped_single_page", "pages_analysed": 1,
        "pages_out_of_scope": 0, "archives_skipped": False})

    # Suppression settings. A rescan supplies the SOURCE job's — an exact
    # answer, so the origin lookup below (a guess, and for a page URL usually
    # the wrong job) must not override it.
    if reuse_settings is not None:
        suppress_h1s = reuse_settings.suppress_h1_strings or []
        suppress_banner = reuse_settings.suppress_banner_h1
    else:
        # Ad-hoc scan: inherit from the most recent completed job for this
        # origin so theme-injected headings stay suppressed.
        suppress_h1s = []
        suppress_banner = True
        try:
            recent = await store.list_recent_jobs(limit=20)
            for rj in recent:
                if rj.target_url.rstrip("/") == origin.rstrip("/") and rj.settings:
                    suppress_h1s = rj.settings.suppress_h1_strings or []
                    suppress_banner = rj.settings.suppress_banner_h1
                    break
        except Exception as e:
            logger.warning(f"Could not load recent jobs for inheriting settings: {e}")

    # ── Fetch, parse, check issues (shared logic) ─────────────────────
    check = await _fetch_and_check_page(
        url=url,
        job_id=job_id,
        base_url=origin,
        store=store,
        suppress_h1_strings=suppress_h1s,
        suppress_banner_h1=suppress_banner,
        bypass_cache=bypass_cache,
        authenticated=authenticated,
    )
    if isinstance(check, JSONResponse):
        await store.update_job(job_id, status="failed", error_message="Fetch/parse failed")
        return check

    page = check.page
    result = check.fetch_result
    new_issues = check.issues

    # ── Robots.txt + AI bot access checks ────────────────────────────────
    # scan-page doesn't run the full engine, so we fetch robots.txt here
    # and run AI bot access checks against the domain.
    try:
        from api.crawler.robots import fetch_robots
        from api.services.ai_readiness import check_ai_bot_access
        async with make_client() as robots_client:
            robots_data = await fetch_robots(origin, robots_client)
        ai_bot_issues = check_ai_bot_access(robots_data, origin)
        for issue in ai_bot_issues:
            new_issues.append(_engine_issue_to_model(issue, job_id))
        robots_found = robots_data.raw_text is not None
        robots_rules = []
        if robots_data.raw_text:
            for line in robots_data.raw_text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    robots_rules.append(line)
            robots_rules = robots_rules[:10]
    except Exception as e:
        logger.warning(f"scan_page_robots_check_failed: {e}")
        robots_found = None
        robots_rules = []

    # ── Image collection (v1.9image) ────────────────────────────────────
    from api.models.image import ImageInfo
    from api.crawler.image_analyzer import analyze_batch as analyze_images

    all_images: list[ImageInfo] = []
    # E1.3 — the E1 guard lives in _fetch_and_check_page, and this endpoint
    # continued past it using `check.page`, which on a 4xx is the parsed ERROR
    # TEMPLATE. A 404 page carrying two <img> tags therefore stored
    # IMG_ALT_MISSING / IMG_ALT_GENERIC / IMG_ALT_TOO_SHORT against a URL that
    # does not exist, and counted them in the response — the same defect E1
    # was written to remove, one layer up. The functional spec claimed the path
    # "returns the BROKEN_LINK_* finding alone for any response >= 400"; that
    # was true of the helper, not of this endpoint.
    if result.status_code >= 400:
        logger.info("scan_page_images_skipped_error_page",
                    extra={"url": url, "status": result.status_code})
    elif page.image_data:
        # IM1 — measure pixel dimensions here too. Without this pass
        # IMG_OVERSCALED / IMG_NO_SRCSET / IMG_DUPLICATE_CONTENT /
        # IMG_SLOW_LOAD / IMG_POOR_COMPRESSION are silently dead on the
        # single-page scan while working on a full crawl: the capability was
        # added at one front end only (P25). Same bounds as the crawl pass,
        # and the same rule — an image that could not be measured keeps None,
        # never a guessed value.
        from api.crawler.engine import (_IMAGE_DIMENSION_BUDGET_S,
                                        _IMAGE_DIMENSION_CONCURRENCY,
                                        _IMAGE_DIMENSION_MAX_COUNT,
                                        _fetch_image_dimensions)

        dim_cache: dict[str, dict] = {}
        candidates = [d["url"] for d in page.image_data
                      if d.get("url")][:_IMAGE_DIMENSION_MAX_COUNT]
        if candidates:
            sem = asyncio.Semaphore(_IMAGE_DIMENSION_CONCURRENCY)

            async def _measure_one(u: str):
                async with sem:
                    return await _fetch_image_dimensions(u, img_client)

            async with make_ssrf_guarded_client() as img_client:
                tasks = [asyncio.create_task(_measure_one(u)) for u in candidates]
                done, pending = await asyncio.wait(
                    tasks, timeout=_IMAGE_DIMENSION_BUDGET_S)
                for task in done:
                    try:
                        item = task.result()
                    except Exception:
                        continue
                    if isinstance(item, tuple) and item[1]:
                        dim_cache[item[0]] = item[1]
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

        for img_data in page.image_data:
            img_url = img_data.get("url")
            if not img_url:
                continue
            dim = dim_cache.get(img_url, {})
            image_info = ImageInfo(
                url=img_url,
                page_url=url,
                job_id=job_id,
                alt=img_data.get("alt"),
                title=img_data.get("title"),
                filename=_extract_filename(img_url),
                format=_guess_format_from_url(img_url),
                width=dim.get("width"),
                height=dim.get("height"),
                rendered_width=img_data.get("rendered_width"),
                rendered_height=img_data.get("rendered_height"),
                file_size_bytes=dim.get("file_size_bytes"),
                load_time_ms=dim.get("load_time_ms"),
                http_status=dim.get("http_status", 0),
                is_lazy_loaded=img_data.get("is_lazy_loaded", False),
                has_srcset=img_data.get("has_srcset", False),
                srcset_candidates=img_data.get("srcset_candidates", []),
                is_decorative=img_data.get("is_decorative", False),
                surrounding_text=img_data.get("surrounding_text", ""),
                content_hash=dim.get("content_hash"),
                data_source="full_fetch" if dim.get("width") else "html_only",
            )
            all_images.append(image_info)

        if all_images:
            analyzed_images, image_issues = analyze_images(all_images, job_id=job_id)
            all_images = analyzed_images
            # Add image issues to the issues list
            new_issues.extend([_engine_issue_to_model(i, job_id) for i in image_issues])

    page_model = _engine_page_to_model(page, job_id)
    page_model.url = url
    page_model.status_code = result.status_code
    page_model.redirect_url = result.final_url if result.is_redirect else None

    await store.save_pages([page_model])
    if new_issues:
        await store.save_issues(new_issues)
    if all_images:
        await store.save_images(all_images)

    await store.update_job(
        job_id,
        status="complete",
        pages_crawled=1,
        pages_total=1,
        robots_txt_found=robots_found,
        robots_txt_rules=robots_rules,
    )

    logger.info("scan_page_complete", extra={"job_id": job_id, "url": url, "issues": len(new_issues), "images": len(all_images)})

    resp = {"job_id": job_id, "status": "complete", "url": url,
            "issues": len(new_issues),
            # D2 — a single-page scan cannot produce these codes at all, so a
            # result with few or no findings must not read as a full audit.
            # Derived from the registry; never mirror the list here.
            "checks_not_run": _checks_a_single_page_scan_cannot_run(),
            "checks_not_run_reason": _CHECKS_NOT_RUN_REASON}
    if authenticated is True:
        # D1 — say what this scan was, in the response. A draft is invisible to
        # search engines, so these findings are pre-publication advice, not an
        # audit of anything live; a reader who cannot tell the two apart will
        # read a clean draft as a clean page.
        resp["authenticated_scan"] = True
        resp["visibility"] = "not-public"
        resp["suppressed_codes"] = sorted(_PREPUBLICATION_NOISE_CODES)
        resp["caveat"] = (
            "Signed in to WordPress to read this page, so it may not be "
            "published. Search engines cannot see it: these findings are "
            "pre-publication advice, not a measurement of live SEO. "
            "ORPHAN_PAGE, NOT_IN_SITEMAP and NOINDEX_META are suppressed "
            "because they are meaningless before publication."
        )
    return resp


@router.post("/{job_id}/mark-fixed", response_model=None)
async def mark_fixed(
    job_id: str,
    url: str = Query(..., description="Source page URL where the issue was fixed"),
    codes: str = Query(..., description="Comma-separated issue codes that were fixed"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Manually record that issues were fixed on a page without running a rescan.

    Called when the user visits a page, fixes an issue themselves, then comes
    back and clicks 'Fixed'. Records the fix date in fix_history.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if code_list:
        await store.record_fixed_issues(job_id, url, code_list)

    return {"url": url, "fixed_codes": code_list, "status": "recorded"}


@router.get("/{job_id}/fix-history", response_model=None)
async def fix_history(
    job_id: str,
    store=Depends(get_store),
) -> list[dict] | JSONResponse:
    """Return all issue codes that were resolved via rescan for this job, with timestamps."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    return await store.get_fix_history(job_id)


# ── Fix Focus — curated priority-fix checklist (2026-08-13, FF1–FF6) ──────────
# Spec: docs/pending/2026-08-13_fix-focus-checklist.md

class FixFocusCheckBody(BaseModel):
    page_url: str
    issue_code: str
    checked: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _load_or_build_fix_focus(job, store, *, regenerate: bool = False) -> dict:
    """Return the persisted Fix Focus snapshot, generating+saving it on first use
    (FF3.C snapshot is frozen). ``regenerate=True`` rebuilds from current issues,
    preserving checked/verified state for surviving items (FF4.C)."""
    if not regenerate and job.fix_focus:
        return job.fix_focus
    issues = await store.get_all_issues(job.job_id)
    snapshot = build_snapshot(
        issues,
        generated_at=_now_iso(),
        scoring_model_version=job.scoring_model_version,
    )
    if regenerate and job.fix_focus:
        snapshot = merge_checked_state(snapshot, job.fix_focus)
    await store.update_job(job.job_id, fix_focus=snapshot)
    return snapshot


@router.get("/{job_id}/fix-focus", response_model=None)
async def get_fix_focus(
    job_id: str,
    focus: str = Query("all", pattern="^(all|seo|geo)$"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Return the Fix Focus checklist (FF4.A). First call generates and persists
    the snapshot; later calls return the saved one (no re-scan)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    snapshot = await _load_or_build_fix_focus(job, store)
    if focus in ("seo", "geo"):
        return {
            focus: snapshot[focus],
            "generated_at": snapshot["generated_at"],
            "scoring_model_version": snapshot["scoring_model_version"],
        }
    return snapshot


@router.post("/{job_id}/fix-focus/regenerate", response_model=None)
async def regenerate_fix_focus(
    job_id: str,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Rebuild the snapshot from current stored issues (FF4.C), preserving the
    checked/verified state of items that still exist."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    return await _load_or_build_fix_focus(job, store, regenerate=True)


@router.post("/{job_id}/fix-focus/check", response_model=None)
async def check_fix_focus_item(
    job_id: str,
    body: FixFocusCheckBody,
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Toggle a checklist item's checked state (FF4.B). Reversible."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    snapshot = await _load_or_build_fix_focus(job, store)
    item = set_checked(
        snapshot, body.page_url, body.issue_code,
        checked=body.checked, at=_now_iso() if body.checked else None,
    )
    if item is None:
        return _err(
            "ITEM_NOT_FOUND",
            f"No Fix Focus item for {body.issue_code} on {body.page_url}.", 404,
        )
    await store.update_job(job_id, fix_focus=snapshot)
    return item


@router.post("/{job_id}/fix-focus/verify-page", response_model=None)
async def verify_fix_focus_page(
    job_id: str,
    url: str = Query(..., description="The checklist page URL to re-scan and verify"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Re-scan a single page and reconcile the checklist (FF4.D/FF5). Reuses the
    existing rescan-url path (one hardened fetch path, no second crawler)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    snapshot = await _load_or_build_fix_focus(job, store)
    rescan = await rescan_url(job_id, url=url, store=store)
    if isinstance(rescan, JSONResponse):
        return rescan
    # An erroring page (>=400 with an HTML body) parses to few/no issues, which
    # would look like everything was "fixed". Refuse to reconcile it as verified —
    # a 5xx/4xx is a transient/unknown outcome, not a fix (P1). rescan_url itself
    # already returned a JSONResponse for a hard fetch failure (status 0).
    if rescan["status_code"] >= 400:
        return {
            "url": rescan["url"], "reconciled": False,
            "page_status": rescan["status_code"],
            "verified": [], "still_present": [], "newly_found": [],
        }
    # Absolute current issue set for the page, filtered to the Fix Focus floor so
    # newly_found stays consistent with FF2.C (warning-and-above only).
    present_codes = {
        i["issue_code"]
        for issues in rescan["by_category"].values()
        for i in issues
        if i.get("impact", 0) >= FIX_FOCUS_MIN_IMPACT
    }
    # Phase 4 U4.5: codes the single-page path cannot evaluate are neither
    # verified nor still present — they were not checked, and the snapshot
    # must say so rather than over-claim in either direction.
    outcome = apply_verify(snapshot, rescan["url"], present_codes=present_codes,
                           unchecked_codes=rescan.get("carried_over_codes") or [])
    await store.update_job(job_id, fix_focus=snapshot)
    return {"url": rescan["url"], "reconciled": True,
            "page_status": rescan["status_code"], **outcome}


@router.get("/{job_id}/striking-distance", response_model=None)
async def get_striking_distance(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Pages ranking inside the striking-distance band with real impressions —
    the highest-leverage inputs to the Content Rewriter (PB3, Phase 4 U4.1)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    from api.services.striking_distance import build_striking_distance
    return await build_striking_distance(store, job_id)


async def _run_recheck_all(job_id: str, urls: list[str], delay_ms: int, store) -> None:
    """Re-fetch every stored page through the single-page rescan path, in order,
    honouring the job's politeness delay. Progress lives in ``_recheck_progress``."""
    prog = _recheck_progress[job_id]
    try:
          for url in urls:
            try:
                res = await rescan_url(job_id, url=url, store=store)
                if isinstance(res, JSONResponse) or res.get("page_unreadable"):
                    prog["unreadable"] += 1
                else:
                    prog["resolved"] += int(res.get("resolved") or 0)
                    prog["added"] += int(res.get("added") or 0)
            except Exception as exc:  # one bad page must not end the run
                logger.warning("recheck_all_page_failed", extra={"job_id": job_id, "url": url, "error": str(exc)})
                prog["unreadable"] += 1
            prog["done"] += 1
            if delay_ms and url is not urls[-1]:
                await asyncio.sleep(delay_ms / 1000)

    finally:
        # Whatever ended the loop (including cancellation at shutdown), the
        # entry must not stay running:true and 409 every later start.
        prog["running"] = False
        prog["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/{job_id}/recheck-all", status_code=202, response_model=None)
async def recheck_all_pages(
    job_id: str,
    background_tasks: BackgroundTasks,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Re-check every stored page of a finished job in place (Phase 4 U4.3).

    Distinct from Rescan (a fresh crawl, a new job): this updates the current
    job's findings and score page by page without discovering new pages.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    if job.status in ("queued", "running"):
        return _err("CRAWL_IN_PROGRESS", "This scan is still running; re-check it when it finishes.", 409)
    prog = _recheck_progress.get(job_id)
    if prog and prog.get("running"):
        return _err("RECHECK_IN_PROGRESS", f"A re-check of this scan is already running ({prog['done']} of {prog['total']} pages).", 409)
    host = (urlparse(job.target_url).hostname or "").lower().removeprefix("www.")
    # Both directions of the politeness guard: no crawl of this host may be
    # running, and no other re-check of it either.
    if await store.active_jobs_for_domain(host):
        return _err("CRAWL_IN_PROGRESS_FOR_DOMAIN", f"A scan of {host} is running; re-check when it finishes.", 409)
    for jid, other in _recheck_progress.items():
        if jid != job_id and other.get("running") and other.get("host") == host:
            return _err("RECHECK_IN_PROGRESS", f"A re-check of {host} is already running (job {jid}).", 409)
    pages = await store.get_pages(job_id)
    urls = [p.url for p in pages]
    _recheck_progress[job_id] = {
        "running": True, "done": 0, "total": len(urls), "resolved": 0, "added": 0,
        "unreadable": 0, "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": None,
        "host": host,
    }
    background_tasks.add_task(_run_recheck_all, job_id, urls, job.settings.crawl_delay_ms, store)
    return {"job_id": job_id, "total": len(urls), "status": "started"}


@router.get("/{job_id}/recheck-all/status", response_model=None)
async def recheck_all_status(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Progress of the in-place re-check. ``running: false, total: 0`` when none
    has run since the process started (progress is not persisted)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)
    prog = _recheck_progress.get(job_id)
    if not prog:
        return {"job_id": job_id, "running": False, "done": 0, "total": 0, "resolved": 0,
                "added": 0, "unreadable": 0, "started_at": None, "finished_at": None}
    return {"job_id": job_id, **{k: v for k, v in prog.items() if k != "host"}}


def _emission_comparability(current: str | None,
                            previous: str | None) -> tuple[bool, str | None]:
    """``(comparable, reason)`` for two jobs' issue-emission stamps.

    A missing stamp is NOT treated as equal. Every job crawled before the stamp
    existed has NULL here, and reading that as "same as mine" is exactly how a
    silent false comparison happens (P12 — a default reaching a surface and
    reading as a real measurement).

    Spec:  docs/functional-specification.md (D5, 2026-09-03)
    Tests: tests/test_site_scope.py::TestComparabilityAcrossAnEmissionChange
    """
    if current and previous and current == previous:
        return True, None
    if not previous:
        return False, ("the previous scan predates issue-emission versioning, so "
                       "its issue counts were produced by different rules")
    if not current:
        return False, "this scan carries no issue-emission version"
    return False, (f"the issue-emission rules changed between the two scans "
                   f"({previous} vs {current}), so a change in issue count is "
                   f"partly a change in what is reported, not in the site")


@router.get("/{job_id}/comparison", response_model=None)
async def get_crawl_comparison(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Compare this crawl to the previous crawl for the same domain."""
    from urllib.parse import urlparse

    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    domain = urlparse(job.target_url).netloc
    previous_jobs = await store.list_jobs_by_domain(domain, limit=2)

    # Filter out the current job
    previous = [j for j in previous_jobs if j.job_id != job_id]
    if not previous:
        return {"comparison_available": False, "message": "No previous crawl found for this domain."}

    prev_job = previous[0]

    # Get summaries for both
    current_summary = await store.get_summary(job_id)
    prev_summary = await store.get_summary(prev_job.job_id)

    # Info detail (2026-09-01): two scores earned at different info levels are
    # not the same measurement. The delta is still returned — the UI strikes
    # it through with the reason — but a bare comparison is never implied.
    cur_level = job.settings.info_detail
    prev_level = prev_job.settings.info_detail
    # Collect EVERY reason, not the first. An info_detail mismatch is fixable by
    # re-scanning; an emission-version mismatch is permanent. Reporting only the
    # first told the operator to do something that cannot work (cold sweep).
    reasons: list[str] = []
    comparable = cur_level == prev_level
    if not comparable:
        reasons.append(f"info_detail differs ({cur_level} vs {prev_level})")
    # D5: a change in what the crawler EMITS moves the row count for reasons
    # that are not the site. `scoring_model_version` covers how we score; this
    # covers what we produce, and the two are not the same question.
    emission_ok, emission_reason = _emission_comparability(
        job.issue_emission_version, prev_job.issue_emission_version)
    if not emission_ok:
        comparable = False
        reasons.append(emission_reason or "the issue-emission rules differ")
    reason = "; ".join(reasons) if reasons else None
    # P6.1 — page scope, the fourth comparability dimension. A single-page scan
    # runs every category over one page, so info_detail, the emission version and
    # the category basis all matched and a one-page scan reported a +4
    # improvement against a ten-page crawl of the same site.
    #
    # Two single-page scans of the SAME url stay comparable: that is the rescan
    # before/after, and it is the one comparison this scope genuinely supports.
    # A blanket "single-page scans never compare" would pass the cross-scope test
    # and silently break a shipped feature.
    cur_scope = (current_summary.get("health_score_basis") or {}).get("page_scope", "site")
    prev_scope = (prev_summary.get("health_score_basis") or {}).get("page_scope", "site")
    if cur_scope != prev_scope:
        comparable = False
        reasons.append(
            "a single-page scan is not comparable with a site crawl "
            f"({cur_scope} vs {prev_scope})")
    elif cur_scope == "single_page" and job.target_url != prev_job.target_url:
        comparable = False
        reasons.append(
            "these are single-page scans of different pages "
            f"({job.target_url} vs {prev_job.target_url})")

    # A partial analysis scores 100 for what it never ran (S1); two scores over
    # different category sets are not the same measurement either.
    for label, summ in (("this scan", current_summary), ("the previous scan", prev_summary)):
        basis = summ.get("health_score_basis") or {}
        if basis.get("comparable") is False:
            comparable = False
            reasons.append(
                f"{label} was a partial analysis "
                f"({len(basis.get('categories_scored') or [])} categories scored)")
    reason = "; ".join(reasons) if reasons else None

    return {
        "comparison_available": True,
        "comparable": comparable,
        "reason": reason,
        "current": {
            "job_id": job_id,
            "info_detail": cur_level,
            "health_score_basis": current_summary.get("health_score_basis"),
            "crawled_at": job.started_at.isoformat() if job.started_at else None,
            "health_score": current_summary.get("health_score", 0),
            "pages_crawled": current_summary.get("pages_crawled", 0),
            "total_issues": current_summary.get("total_issues", 0),
            "by_severity": current_summary.get("by_severity", {}),
        },
        "previous": {
            "job_id": prev_job.job_id,
            "info_detail": prev_level,
            "health_score_basis": prev_summary.get("health_score_basis"),
            "crawled_at": prev_job.started_at.isoformat() if prev_job.started_at else None,
            "health_score": prev_summary.get("health_score", 0),
            "pages_crawled": prev_summary.get("pages_crawled", 0),
            "total_issues": prev_summary.get("total_issues", 0),
            "by_severity": prev_summary.get("by_severity", {}),
        },
        "delta": {
            "health_score": current_summary.get("health_score", 0) - prev_summary.get("health_score", 0),
            "total_issues": current_summary.get("total_issues", 0) - prev_summary.get("total_issues", 0),
            "critical": current_summary.get("by_severity", {}).get("critical", 0) - prev_summary.get("by_severity", {}).get("critical", 0),
            "warning": current_summary.get("by_severity", {}).get("warning", 0) - prev_summary.get("by_severity", {}).get("warning", 0),
        },
    }


@router.get("/{job_id}/executive-summary", response_model=None)
async def get_executive_summary(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Generate or retrieve an AI executive summary for this crawl."""
    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    # Check if we already have a cached summary
    if job.executive_summary:
        return {"summary": job.executive_summary, "cached": True}

    # Generate via AI
    try:
        from api.services.ai_analyzer import AIAnalysisError, analyze_with_ai
        summary = await store.get_summary(job_id)
        issues = await store.get_all_issues(job_id)
        top_issues_list = sorted(issues, key=lambda i: -(i.priority_rank or 0))
        top_3 = ", ".join(dict.fromkeys(i.human_description or i.issue_code for i in top_issues_list[:5]))

        context = {
            "health_score": summary.get("health_score", 0),
            "pages_crawled": summary.get("pages_crawled", 0),
            "critical": summary.get("by_severity", {}).get("critical", 0),
            "warnings": summary.get("by_severity", {}).get("warning", 0),
            "top_issues": top_3,
        }
        # P14: analyze_with_ai raises AIAnalysisError on failure. Only a real
        # summary string reaches update_job / the response — an error is never
        # cached on the job or returned as `summary` content.
        result = await analyze_with_ai("executive_summary", context)

        # Cache it on the job
        await store.update_job(job_id, executive_summary=result)

        return {"summary": result, "cached": False}
    except AIAnalysisError as exc:
        return _err("AI_UNAVAILABLE", f"Could not generate summary: {str(exc)}", 503)
    except Exception as exc:
        return _err("AI_UNAVAILABLE", f"Could not generate summary: {str(exc)}", 503)


@router.get("/{job_id}/page-priority", response_model=None)
async def get_page_priority(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Page Priority Work Queue.

    Ranks the job's crawled pages by the Authority Matrix (M6.3): Vulnerable
    Stars first, then Traffic Decay / Staleness, then worst-health, with Hidden
    Gems surfaced as opportunities. Works with OR without GSC data — when no
    Performance Ledger records exist for a page, it's ranked by health alone.
    """
    # E3.1 — the assembly lives in api/services/page_priority.py so the PDF and
    # Excel exports rank pages the same way this endpoint does. Before that
    # extraction the ranking existed only here and in the GUI panel, and the
    # client-facing PDF sorted by raw issue count (P25).
    from api.services.page_priority import build_page_priority, serialise_review_flags

    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    ranked = serialise_review_flags(await build_page_priority(store, job_id))
    # Every `health_score` and `citability_grade` in these rows was computed at
    # the job's info_detail (page_priority.py:129), so the level travels with
    # them. LEARNINGS open risk (1), 2026-09-01, in its own words: "a new surface
    # that renders health_score without info_detail beside it — the S1
    # score-basis lesson again; the contract test for that surface must assert
    # the label." This is that surface, and this is that label.
    return {
        "pages": ranked,
        "total": len(ranked),
        "info_detail": job.settings.info_detail,
    }


@router.post("/{job_id}/web-vitals", response_model=None)
async def collect_web_vitals_endpoint(
    job_id: str,
    top_n: int | None = Query(None, ge=1, le=25,
                              description="Pages to measure (default from config, max 25)"),
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Core Web Vitals for the top pages of the §6.9 priority queue (D2).

    User-triggered and post-scan by design — never inside the crawl. The binding
    CrUX/PSI constraint is 100 queries per 100 seconds, so a whole-site sweep
    would add minutes to every run for data that only matters where traffic is.
    Spec: docs/pending/2026-08-29_D2-core-web-vitals.md
    """
    from api.services.web_vitals import api_key, collect_web_vitals

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    try:
        report = await collect_web_vitals(store, job_id, top_n=top_n)
    except Exception as exc:
        # scrub(): the Google APIs take the key as a query parameter, so a
        # transport error's message carries it. It must not reach the log or the
        # response body.
        from api.services.web_vitals import scrub

        logger.exception("web_vitals_failed", extra={"job_id": job_id})
        return _err("WEB_VITALS_ERROR",
                    scrub(f"Could not collect Core Web Vitals: {exc}"), 502)

    payload = {
        "job_id": job_id,
        "strategy": report.strategy,
        "requested": report.requested,
        "field_count": report.field_count,
        "lab_count": report.lab_count,
        "unavailable_count": report.unavailable_count,
        "retryable_failures": report.retryable_failures,
        # Surfaced so the caller can distinguish "this site is fine" from
        # "we could not measure it" — never the API key itself.
        "had_api_key": bool(api_key()),
        "rows": [
            {
                "url": r.url, "source": r.source,
                "lcp_ms": r.lcp_ms, "inp_ms": r.inp_ms, "cls": r.cls,
                "performance_score": r.performance_score,
                "unavailable_reason": r.unavailable_reason,
                "retryable": r.retryable,
            }
            for r in report.rows
        ],
    }
    try:
        await store.update_job(job_id, web_vitals=payload)
    except Exception:
        logger.warning("web_vitals_persist_failed", extra={"job_id": job_id})

    # Persist the findings so they reach the report, the summary and the health
    # score like any other issue. Without this the three CWV codes would exist in
    # the catalogue and never appear on a real run (P21 — built but not wired).
    #
    # Re-running must not duplicate: clear this job's prior CWV rows first. The
    # measurement is a snapshot of a 28-day window, so the newest run replaces
    # the older one rather than accumulating alongside it.
    from api.services.web_vitals import CWV_CODES, vitals_issues

    try:
        measured_urls = {r.url for r in report.rows}
        for url in measured_urls:
            for code in CWV_CODES:
                await store.delete_issues_by_code_and_url(job_id, code, url)
        new_issues = [_engine_issue_to_model(i, job_id) for i in vitals_issues(report)]
        if new_issues:
            await store.save_issues(new_issues)
        payload["issues_recorded"] = len(new_issues)
    except Exception:
        logger.exception("web_vitals_issue_persist_failed", extra={"job_id": job_id})
        payload["issues_recorded"] = None

    return payload


@router.get("/{job_id}/export/csv", response_model=None)
async def export_csv_full(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> StreamingResponse | JSONResponse:
    """Download all issues as CSV (spec §6.2)."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    issues = await store.get_all_issues(job_id)
    # F1 — the exports show what the screen shows. Same rule engine as the
    # results list, so the two cannot describe different sites. `issues` below
    # is what gets LISTED; `_unfiltered_issues` is what the document REASONS
    # FROM. Hiding a row is presentational — deriving a FACT about the site
    # from the absence of a row is not.
    _unfiltered_issues = list(issues)
    issues, _ = await _filter_issue_models_for_domain(store, job.target_url, issues)
    issues, _ = _filter_issue_models_for_info_detail(job, issues)
    from urllib.parse import urlparse
    domain = urlparse(job.target_url).netloc.replace("www.", "")
    return _csv_response(issues, filename=f"TalkingToad-Audit-{domain}.csv")


@router.get("/{job_id}/export/pdf", response_model=None)
@limiter.limit(EXPORT_LIMIT)
async def export_pdf_report(
    request: Request,
    job_id: str,
    include_help: bool = Query(True, description="Include detailed help text for each issue category"),
    include_pages: bool = Query(True, description="List affected URLs for each issue type"),
    summary_only: bool = Query(False, description="Generate summary pages only (ignores help and page lists)"),
    include_blueprints: bool = Query(
        False,
        description="Include APPROVED page-copy drafts (D4). Off by default — "
                    "AI-drafted copy in a client report is an explicit choice.",
    ),
    store: SQLiteJobStore = Depends(get_store),
) -> StreamingResponse | JSONResponse:
    """Generate and download a professional PDF audit report."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    # Load GEO config for the domain to get report preferences
    try:
        from urllib.parse import urlparse
        domain = urlparse(job.target_url).netloc.replace('www.', '')
        geo_config = await store.get_geo_config(domain)

        if geo_config:
            # Override job settings with GEO config if available
            if geo_config.client_name:
                job.settings.client_name = geo_config.client_name
            if geo_config.prepared_by:
                job.settings.prepared_by = geo_config.prepared_by
            logger.info("geo_config_loaded_for_report", extra={"domain": domain, "has_client_name": bool(geo_config.client_name)})
    except Exception as exc:
        logger.warning("geo_config_load_failed", extra={"error": str(exc)})
        # Continue with job settings as fallback

    issues = await store.get_all_issues(job_id)
    # F1 — the exports show what the screen shows. Same rule engine as the
    # results list, so the two cannot describe different sites. `issues` below
    # is what gets LISTED; `_unfiltered_issues` is what the document REASONS
    # FROM. Hiding a row is presentational — deriving a FACT about the site
    # from the absence of a row is not.
    _unfiltered_issues = list(issues)
    issues, _filter_note = await _filter_issue_models_for_domain(store, job.target_url, issues)
    issues, _filter_note = _filter_issue_models_for_info_detail(job, issues, _filter_note)
    summary = await store.get_summary(job_id)

    # Fetch top 10 pages for the report. The level is not optional: without it the
    # rows come back at "all", so the PDF printed the STORED info count beside a
    # scoped health score — and reported `info_excluded: 0` on a job that excluded
    # rows, which asserts the opposite of the truth rather than staying silent.
    top_pages_data, _, _ = await store.get_pages_with_issue_counts(
        job_id, page=1, limit=10, info_detail=job.settings.info_detail)

    # Fetch image data for the report
    image_summary = await store.get_image_summary(job_id)
    top_images = await store.get_images(job_id, page=1, limit=20, sort_by="score")

    # summary_only disables per-page URL listings; help text is independent
    if summary_only:
        include_pages = False

    # E3 — the same ranking the /page-priority endpoint and the GUI panel use.
    # Guarded so a ledger hiccup degrades the report rather than failing the
    # export; on failure both stay None and the sections are omitted, which the
    # Scope & Caveats section then records (E7.4) rather than passing off as clean.
    performance = None
    priority_pages = None
    performance_failed = False
    try:
        from api.services.page_priority import (
            build_page_priority,
            build_performance_summary,
            serialise_review_flags,
        )
        priority_pages = serialise_review_flags(await build_page_priority(store, job_id))
        performance = await build_performance_summary(store, job_id)
    except Exception as exc:
        # Distinguish OUR failure from "the client supplied no data" — Caveats
        # says something different for each, and asserting "no data was supplied
        # for this site" when our own guard fired is a false statement about
        # the client's inputs (P1/P2).
        performance_failed = True
        logger.warning("page_priority_unavailable_for_report",
                       extra={"job_id": job_id, "error": str(exc)})

    prevalence = await _prevalence_for_display(store, job, job_id)
    summary = _with_prevalence(summary, prevalence)

    # D1 — off-site authority joined to the crawl. None when the producer
    # supplied no links section; the section is then omitted and named in Caveats.
    offsite = None
    try:
        from api.services.offsite import build_offsite, to_dict as _offsite_dict

        if job.offsite_links:
            # D2 — a FACT about the site, not a list of rows. Every
            # BROKEN_LINK_* code is `info`, and offsite.py `continue`s on a
            # broken match, so dropping one does not merely hide it: the page
            # is RE-CLASSIFIED into earned_authority_poor_health, while the
            # same PDF still prints "Broken Links: 1" from the unfiltered
            # summary and contradicts itself.
            broken = {
                i.page_url for i in _unfiltered_issues
                if i.issue_code.startswith("BROKEN_LINK_") and i.page_url
            }
            orphans = {
                i.page_url for i in _unfiltered_issues
                if i.issue_code == "ORPHAN_PAGE" and i.page_url
            }
            offsite = _offsite_dict(build_offsite(
                job.offsite_links, priority_pages or [],
                broken_target_urls=broken, orphan_urls=orphans,
            ))
    except Exception:
        logger.warning("offsite_unavailable", extra={"job_id": job_id})

    # Try to generate AI executive summary (optional — skipped if no API keys)
    executive_summary = None
    try:
        from api.services.ai_analyzer import AIAnalysisError, analyze_with_ai
        top_issues_list = sorted(issues, key=lambda i: -(i.priority_rank or 0))
        top_3 = ", ".join(dict.fromkeys(i.human_description or i.issue_code for i in top_issues_list[:5]))
        ai_context = {
            "health_score": summary.get("health_score", 0),
            "pages_crawled": summary.get("pages_crawled", 0),
            "critical": summary.get("by_severity", {}).get("critical", 0),
            "warnings": summary.get("by_severity", {}).get("warning", 0),
            "top_issues": top_3,
        }
        # P14: on failure analyze_with_ai raises; executive_summary stays None
        # so the PDF never renders an error string as report content.
        executive_summary = await analyze_with_ai("executive_summary", ai_context)
    except AIAnalysisError as exc:
        logger.info("ai_summary_skipped", extra={"reason": str(exc)})
    except Exception as exc:
        logger.info("ai_summary_skipped", extra={"reason": str(exc)})

    try:
        logger.info("generating_pdf_report", extra={
            "job_id": job_id,
            "issues_count": len(issues),
            "include_help": include_help,
            "include_pages": include_pages
        })
        pdf_bytes = await generate_pdf_report(
            job, issues, summary, filter_note=_filter_note,
            all_issues=_unfiltered_issues,
            include_help=include_help,
            include_pages=include_pages,
            top_pages=top_pages_data,
            image_summary=image_summary,
            top_images=top_images,
            executive_summary=executive_summary,
            performance=performance,
            priority_pages=priority_pages,
            prevalence=prevalence,
            performance_failed=performance_failed,
            include_blueprints=include_blueprints,
            offsite=offsite,
        )
        logger.info("pdf_report_generated", extra={"job_id": job_id, "size_bytes": len(pdf_bytes)})
        pdf_domain = urlparse(job.target_url).netloc.replace("www.", "")
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="TalkingToad-Audit-{pdf_domain}.pdf"'},
        )
    except Exception as exc:
        logger.exception("pdf_generation_failed", extra={"job_id": job_id, "error": str(exc)})
        return _err("REPORT_ERROR", f"Failed to generate PDF: {str(exc)}", 500)


@router.get("/{job_id}/export/excel", response_model=None)
@limiter.limit(EXPORT_LIMIT)
async def export_excel_report(
    request: Request,
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> StreamingResponse | JSONResponse:
    """Generate and download a multi-sheet Excel audit report."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    issues = await store.get_all_issues(job_id)
    # F1 — the exports show what the screen shows. Same rule engine as the
    # results list, so the two cannot describe different sites. `issues` below
    # is what gets LISTED; `_unfiltered_issues` is what the document REASONS
    # FROM. Hiding a row is presentational — deriving a FACT about the site
    # from the absence of a row is not.
    _unfiltered_issues = list(issues)
    issues, _filter_note = await _filter_issue_models_for_domain(store, job.target_url, issues)
    issues, _filter_note = _filter_issue_models_for_info_detail(job, issues, _filter_note)
    summary = await store.get_summary(job_id)

    # Fetch image data for the report
    image_summary = await store.get_image_summary(job_id)
    images_list = await store.get_images(job_id, page=1, limit=500, sort_by="score")

    # E3.4 — Excel parity with the PDF. Same source of truth, same guard.
    performance = None
    priority_pages = None
    try:
        from api.services.page_priority import (
            build_page_priority,
            build_performance_summary,
            serialise_review_flags,
        )
        priority_pages = serialise_review_flags(await build_page_priority(store, job_id))
        performance = await build_performance_summary(store, job_id)
    except Exception as exc:
        logger.warning("page_priority_unavailable_for_excel",
                       extra={"job_id": job_id, "error": str(exc)})

    prevalence = await _prevalence_for_display(store, job, job_id)
    summary = _with_prevalence(summary, prevalence)

    try:
        from urllib.parse import urlparse as _urlparse
        excel_domain = _urlparse(job.target_url).netloc.replace("www.", "")
        excel_bytes = generate_excel_report(
            job, issues, summary,
            image_summary=image_summary,
            images=images_list,
            performance=performance,
            priority_pages=priority_pages,
            prevalence=prevalence,
            filter_note=_filter_note,
            all_issues=_unfiltered_issues,
        )
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="TalkingToad-Audit-{excel_domain}.xlsx"'},
        )
    except Exception as exc:
        logger.exception("excel_generation_failed", extra={"job_id": job_id})
        return _err("REPORT_ERROR", f"Failed to generate Excel: {str(exc)}", 500)


@router.get("/{job_id}/export/csv/{category}", response_model=None)
async def export_csv_category(
    job_id: str,
    category: str,
    store: SQLiteJobStore = Depends(get_store),
) -> StreamingResponse | JSONResponse:
    """Download one category's issues as CSV (spec §6.2)."""
    if category not in _VALID_CATEGORIES:
        return _err(
            "INVALID_CATEGORY",
            f"'{category}' is not a valid category. Valid values: {sorted(_VALID_CATEGORIES)}",
            422,
        )

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    issues, _ = await store.get_issues(job_id, category=category, limit=10_000)
    # F1 — same filter as the on-screen category view.
    issues, _ = await _filter_issue_models_for_domain(store, job.target_url, issues)
    issues, _ = _filter_issue_models_for_info_detail(job, issues)
    from urllib.parse import urlparse as _up
    cat_domain = _up(job.target_url).netloc.replace("www.", "")
    return _csv_response(issues, filename=f"TalkingToad-Audit-{cat_domain}-{category}.csv")


# ── Private helpers ────────────────────────────────────────────────────────

def _issue_dict(issue: Issue) -> dict:
    return {
        "issue_id": issue.issue_id,
        "page_url": issue.page_url,
        "category": issue.category,
        "severity": issue.severity,
        "issue_code": issue.issue_code,
        "description": issue.description,
        "recommendation": issue.recommendation,
        "impact": issue.impact,
        "effort": issue.effort,
        "priority_rank": issue.priority_rank,
        "human_description": issue.human_description,
        "extra": issue.extra,
        "fixability": issue.fixability,
        # v2.6 M0.2 — see _engine_issue_to_model for the rationale.
        # Frontends that render ai_readiness issues depend on this
        # confidence_label to surface the evidence-strength badge.
        "confidence_label": issue.confidence_label,
        # R5.1 — scoring scope ("page" | "site"). Derived from the catalogue by
        # code (scope is a static property of the code, not stored per row) so
        # the frontend can flag a site-wide finding that is deducted only once.
        "scope": issue_scope(issue.issue_code),
        # R5.4 — quick-win flag (impact>=4 AND effort<=1). Derived on the Issue
        # model (computed_field) so it is always consistent with impact/effort;
        # serialised here so both list endpoints can surface a Quick-Wins badge.
        "quick_win": issue.quick_win,
        # Info detail (2026-09-01) — sub-grade of an info row (high | medium |
        # low), None otherwise. Derived on the model from the STORED impact.
        "info_tier": issue.info_tier,
        # EV (2026-08-29) — the rendered "what to look for" lines, computed
        # SERVER-side from `extra`. Deliberately not ported to JS: a second
        # implementation of a 15-shape renderer is a drift waiting to happen
        # (P19), and this is the single serialiser all seven consumers use, so
        # every surface gets the same evidence the PDF and Excel show.
        **_evidence_fields(issue.issue_code, issue.extra),
    }


def _evidence_fields(issue_code: str, extra: dict | None) -> dict:
    """`evidence` / `evidence_total` / `evidence_basis` for one issue. Never raises.

    D6 — `evidence_basis` distinguishes the two ways an evidence list can be
    empty, which look identical on the wire and mean opposite things:

      "page"  — the finding IS the page (TITLE_MISSING and 29 siblings). There is
                nothing to name, and a panel must say so.
      "items" — this code names items, and none were recorded here. An empty
                render then means "not captured", never "nothing wrong".

    Derived from PAGE_IS_THE_EVIDENCE rather than mirrored in JS: a 30-code copy
    in the frontend is the hand-mirrored enumeration this module exists to avoid
    (P19), and it would go stale the first time a code joins the set.
    """
    try:
        from api.services.issue_evidence import PAGE_IS_THE_EVIDENCE, evidence_summary

        lines, total, rendered = evidence_summary(issue_code, extra)
        basis = "page" if issue_code in PAGE_IS_THE_EVIDENCE else "items"
    except Exception:  # noqa: BLE001 — evidence must never break a list endpoint
        logger.warning("issue_evidence_failed", extra={"code": issue_code}, exc_info=True)
        return {"evidence": [], "evidence_total": 0, "evidence_rows": 0,
                "evidence_basis": "items"}
    return {
        "evidence": lines,
        "evidence_total": total,
        # Evidence ROWS in `evidence`, which is not len(evidence): that list
        # also holds one heading per key and an "... and N more" line. A client
        # comparing evidence_total against evidence.length under-reports
        # truncation by that overhead — with the default cap of 10 an issue with
        # 11 or 12 captured rows compares equal and looks complete (D6).
        "evidence_rows": rendered,
        "evidence_basis": basis,
    }


@router.get("/{job_id}/images", response_model=None)
async def get_images(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),  # Increased from 100 to 1000 for bulk operations
    sort_by: str = Query("score", regex="^(score|size|load_time)$"),
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Return paginated list of images for a job with scores and issues."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    images = await store.get_images(job_id, page=page, limit=limit, sort_by=sort_by)
    summary = await store.get_image_summary(job_id)

    total = summary.get("total_images", 0)
    total_pages = max(1, math.ceil(total / limit))

    return {
        "job_id": job_id,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_images": total,
            "total_pages": total_pages,
        },
        "images": [_image_dict(img) for img in images],
    }


@router.get("/{job_id}/images/summary", response_model=None)
async def get_images_summary(
    job_id: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Return image analysis summary stats for a job."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    summary = await store.get_image_summary(job_id)
    return {
        "job_id": job_id,
        **summary,
    }


@router.get("/{job_id}/images/{image_url:path}", response_model=None)
async def get_image_detail(
    job_id: str,
    image_url: str,
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Return detailed info for a specific image by URL."""
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    image = await store.get_image_by_url(job_id, image_url)
    if image is None:
        return _err("IMAGE_NOT_FOUND", f"No image found with URL: {image_url}", 404)

    return {
        "job_id": job_id,
        "image": _image_dict(image),
    }


@router.post("/{job_id}/images/fetch", response_model=None)
async def fetch_image_details(
    job_id: str,
    image_url: str = Query(..., description="URL of the image to fetch"),
    fetch_wp_metadata: bool = Query(True, description="Also fetch WordPress metadata (alt text, title)"),
    store: SQLiteJobStore = Depends(get_store),
) -> dict | JSONResponse:
    """Fetch full image details: image file (dimensions, size, format) + WordPress metadata (alt text, title).

    This is the unified "Fetch WP Data" endpoint that gets the complete truth from live sources.
    """
    import hashlib
    import time
    from urllib.parse import urlparse
    import json
    from pathlib import Path

    # v2.3 (M0.6.9) SSRF guard: image_url is user-supplied (or comes from
    # crawled HTML which is also untrusted) and is then fetched raw via httpx
    # in step 2 below. Without this check, a post-auth user could pivot to
    # localhost, AWS metadata (169.254.169.254), or internal services on the
    # Vercel/container runtime.
    if not is_ssrf_safe(image_url):
        logger.warning("images_fetch_ssrf_blocked", extra={"image_url": image_url, "job_id": job_id})
        return _err("SSRF_BLOCKED", "Image URL resolves to a private/internal address.", 400)

    print(f"\n{'='*80}")
    print(f"[FETCH] START - Image URL: {image_url}")
    print(f"[FETCH] Job ID: {job_id}")
    print(f"[FETCH] Fetch WP metadata: {fetch_wp_metadata}")
    print(f"{'='*80}\n")

    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", "No crawl job found with the given ID.", 404)

    image = await store.get_image_by_url(job_id, image_url)
    if image is None:
        return _err("IMAGE_NOT_FOUND", f"No image found with URL: {image_url}", 404)

    print(f"[FETCH] Got image from DB:")
    print(f"  - Image URL: {image.url}")
    print(f"  - Current alt: '{image.alt}'")
    print(f"  - Current title: '{image.title}'")
    print(f"  - File size: {image.file_size_bytes}")
    print(f"  - Dimensions: {image.width}x{image.height}")

    # Step 1: Fetch WordPress metadata if requested
    wp_fetch_success = False
    if fetch_wp_metadata:
        try:
            from api.services.wp_client import WPClient
            from api.services.wp_fixer import get_attachment_info

            _CREDS_PATH = Path("wp-credentials.json")
            if _CREDS_PATH.exists():
                with open(_CREDS_PATH) as f:
                    creds = json.load(f)

                # Validate domain
                job_domain = urlparse(job.target_url).netloc
                creds_domain = urlparse(creds.get("site_url", "")).netloc

                if job_domain == creds_domain:
                    wp = WPClient(
                        site_url=creds["site_url"],
                        login_url=creds["login_url"],
                        username=creds["username"],
                        password=creds["password"],
                    )
                    async with wp:
                        wp_info = await get_attachment_info(wp, image_url, cache_bust=True)

                    if wp_info.get("success"):
                        wp_alt = wp_info.get("alt_text", "")
                        wp_title = wp_info.get("title", "")
                        wp_caption = wp_info.get("caption", "")
                        wp_description = wp_info.get("description", "")
                        wp_media_id = wp_info.get("id")
                        wp_source_url = wp_info.get("source_url", "")

                        print(f"\n[FETCH] WordPress Response:")
                        print(f"  - WP Media ID: {wp_media_id}")
                        print(f"  - WP Source URL: {wp_source_url}")
                        print(f"  - WP Alt Text: '{wp_alt}'")
                        print(f"  - WP Title: '{wp_title}'")
                        print(f"  - WP Caption: '{wp_caption}'")
                        print(f"  - WP Description: '{wp_description}'")
                        print(f"  - URL Match: {wp_source_url == image_url}")

                        # CRITICAL: Only update if URLs match exactly
                        if wp_source_url == image_url:
                            image.alt = wp_alt
                            image.title = wp_title
                            image.caption = wp_caption
                            image.description = wp_description
                            wp_fetch_success = True
                            print(f"  ✓ URLs match - updating metadata")
                        else:
                            print(f"  ✗ URL MISMATCH - NOT updating metadata!")
                            print(f"    Requested: {image_url}")
                            print(f"    Got:       {wp_source_url}")
                    else:
                        print(f"[FETCH] WordPress fetch failed: {wp_info.get('error')}")
                        print(f"  ⚠ Image not found in WordPress Media Library")
                        print(f"  This image exists on the server but wasn't uploaded via WP Media Library")
                        # Continue with image file fetch - we can still get dimensions/size/etc.
                else:
                    print(f"[FETCH] Domain mismatch - job: {job_domain}, creds: {creds_domain}")
        except Exception as e:
            print(f"[FETCH] WordPress fetch error: {e}")
            logger.warning("wp_fetch_failed_in_fetch", extra={"error": str(e)})

    # Step 2: Fetch the actual image file
    try:
        import httpx
        from PIL import Image as PILImage
        import io as pio

        start_time = time.time()
        # The is_ssrf_safe check above covers the URL we were given; this
        # client follows redirects, so without the guarded client a public
        # host answering 302 to an internal address was followed. CLAUDE.md
        # requires the check at start AND on every redirect hop.
        async with make_ssrf_guarded_client() as client:
            response = await client.get(image_url, timeout=10.0)

        load_time_ms = int((time.time() - start_time) * 1000)
        http_status = response.status_code

        width, height, fmt, content_hash, file_size_bytes = None, None, "unknown", None, None

        if response.status_code < 400:
            content = response.content
            file_size_bytes = len(content)
            content_hash = hashlib.md5(content).hexdigest()

            try:
                img = PILImage.open(pio.BytesIO(content))
                width, height = img.size
                fmt = img.format.lower() if img.format else "unknown"
            except (OSError, IOError, AttributeError) as e:
                logger.debug(f"Could not analyze image format: {e}")

        # Update the stored image with fetched data
        image.width = width
        image.height = height
        image.format = fmt
        image.file_size_bytes = file_size_bytes
        image.load_time_ms = load_time_ms
        image.http_status = http_status
        image.content_hash = content_hash
        image.data_source = "full_fetch"

        # Step 3: Re-analyze with ALL new data (including WP metadata if fetched)
        from api.crawler.image_analyzer import analyze_image
        issues, scores = analyze_image(image, job_id=job_id)
        image.performance_score = scores["performance_score"]
        image.accessibility_score = scores["accessibility_score"]
        image.semantic_score = scores["semantic_score"]
        image.technical_score = scores["technical_score"]
        image.overall_score = scores["overall_score"]
        image.issues = [i.code for i in issues]

        print(f"\n[FETCH] Before Save to DB:")
        print(f"  - Image URL: {image.url}")
        print(f"  - Alt text to save: '{image.alt}'")
        print(f"  - Title to save: '{image.title}'")
        print(f"  - Overall score: {image.overall_score}")
        print(f"  - Issues: {image.issues}")

        # Save updated image
        await store.save_images([image])

        print(f"\n[FETCH] After Save - verifying:")
        print(f"  - Image URL in object: {image.url}")
        print(f"  - Alt text in object: '{image.alt}'")

        result_image = _image_dict(image)
        print(f"\n[FETCH] Returning to frontend:")
        print(f"  - URL: {result_image['url']}")
        print(f"  - Alt: '{result_image['alt']}'")
        print(f"  - Overall score: {result_image['overall_score']}")
        print(f"{'='*80}\n")

        return {
            "job_id": job_id,
            "fetched": True,
            "wp_metadata_fetched": wp_fetch_success,
            "image": result_image,
        }

    except Exception as e:
        logger.exception("image_fetch_failed", extra={"image_url": image_url})
        return _err("FETCH_FAILED", f"Failed to fetch image: {str(e)}", 500)


# ── Private helpers ────────────────────────────────────────────────────────

def _image_dict(img) -> dict:
    """Convert ImageInfo to API response dict."""
    return {
        "url": img.url,
        "page_url": img.page_url,
        "alt": img.alt,
        "title": img.title,
        "caption": img.caption,
        "description": img.description,
        "filename": img.filename,
        "format": img.format,
        "width": img.width,
        "height": img.height,
        "rendered_width": img.rendered_width,
        "rendered_height": img.rendered_height,
        "file_size_bytes": img.file_size_bytes,
        "file_size_kb": round(img.file_size_bytes / 1024, 1) if img.file_size_bytes else None,
        "load_time_ms": img.load_time_ms,
        "http_status": img.http_status,
        "is_lazy_loaded": img.is_lazy_loaded,
        "has_srcset": img.has_srcset,
        "srcset_candidates": img.srcset_candidates,
        "surrounding_text": img.surrounding_text,
        "is_decorative": img.is_decorative,
        "content_hash": img.content_hash,
        "performance_score": img.performance_score,
        "accessibility_score": img.accessibility_score,
        "semantic_score": img.semantic_score,
        "technical_score": img.technical_score,
        "overall_score": img.overall_score,
        "issues": img.issues,
        "data_source": img.data_source,
        # GEO AI fields (v1.9geo)
        "long_description": img.long_description,
        "geo_entities_detected": img.geo_entities_detected,
        "geo_location_used": img.geo_location_used,
        "ai_analysis_metadata": img.ai_analysis_metadata,
    }


def _csv_response(issues: list[Issue], filename: str) -> StreamingResponse:
    def generate():
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        yield buf.getvalue()

        for issue in issues:
            buf.seek(0)
            buf.truncate()
            writer.writerow({
                "url": issue.page_url or "",
                "issue_code": issue.issue_code,
                "severity": issue.severity,
                # Info detail (2026-09-01): the tier travels with the row, so a
                # CSV scoped to `key` can be told apart from a quieter site.
                "info_tier": issue.info_tier or "",
                "category": issue.category,
                "phase": "1" if issue.category in PHASE_1_CATEGORIES else "2",
                "description": issue.description,
                "recommendation": issue.recommendation,
            })
            yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{job_id}/images/analyze-ai")
@limiter.limit(AI_ANALYSIS_LIMIT)
async def analyze_image_with_ai_endpoint(
    request: Request,
    job_id: str,
    image_url: str = Query(..., description="URL of the image to analyze"),
    store=Depends(get_store)
):
    """
    Analyze an image using AI vision models (Gemini Vision or GPT-4V).

    Updates the image's semantic_score and issues based on AI analysis.
    """
    from api.services.ai_analyzer import analyze_image_with_ai

    # Get current image data
    image = await store.get_image_by_url(job_id, image_url)
    if not image:
        return {"error": f"Image not found: {image_url}"}

    # Analyze with AI
    analysis = await analyze_image_with_ai(image_url, image.alt or "")

    # Update image with AI analysis results
    image.semantic_score = analysis["semantic_score"]

    # Add AI-generated issues if accuracy or quality is low
    new_issues = []
    if analysis["accuracy_score"] < 70:
        new_issues.append("IMG_ALT_INACCURATE")
    if analysis["quality_score"] < 70:
        new_issues.append("IMG_ALT_LOW_QUALITY")

    # Merge with existing issues (avoid duplicates)
    existing_issues = set(image.issues)
    for issue in new_issues:
        if issue not in existing_issues:
            image.issues.append(issue)

    # Save updated image
    await store.save_images([image])

    return {
        "image_url": image_url,
        "analysis": analysis,
        "updated_scores": {
            "semantic_score": image.semantic_score,
            "overall_score": image.overall_score
        }
    }


@router.api_route("/{job_id}/export/ai-images-pdf", methods=["GET", "POST"])
async def export_ai_analysis_pdf(
    job_id: str,
    request: Request,
    store=Depends(get_store)
):
    """Export AI image analysis results as a detailed PDF."""
    from fpdf import FPDF
    from urllib.parse import unquote

    def clean_text(text: str) -> str:
        """Clean text for Latin-1 PDF encoding."""
        if not text:
            return ""
        # Convert to string and replace non-Latin-1 characters
        text = str(text)
        return text.encode('latin-1', errors='ignore').decode('latin-1')

    def clean_filename(url: str) -> str:
        """Extract and decode filename from URL."""
        if not url:
            return "Unknown"
        # Get last part of URL
        filename = url.split('/')[-1]
        # URL decode (converts %20 to space, %2B to +, etc.)
        filename = unquote(filename)
        # Replace + with space (sometimes used in URLs)
        filename = filename.replace('+', ' ')
        # Clean for Latin-1
        return clean_text(filename)

    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", "Job not found", 404)

    # Check if we have AI results from POST
    ai_results = None
    if request.method == "POST":
        try:
            body = await request.json()
            ai_results = body.get("ai_results", [])
            # Debug logging
            if ai_results:
                print(f"[PDF Export] Received {len(ai_results)} AI results")
                if ai_results:
                    first = ai_results[0]
                    print(f"[PDF Export] First result keys: {list(first.keys())}")
                    if "analysis" in first:
                        print(f"[PDF Export] Analysis keys: {list(first['analysis'].keys())}")
                        print(f"[PDF Export] Accuracy score: {first['analysis'].get('accuracy_score')}")
        except Exception as e:
            print(f"[PDF Export] Error parsing POST body: {e}")
            import traceback
            traceback.print_exc()
            pass

    # Get all images (returns list of ImageInfo objects)
    all_images = await store.get_images(job_id, page=1, limit=1000, sort_by="score")

    # Create PDF with detailed AI analysis
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'AI Image Analysis Results', ln=True, align='C')
    pdf.ln(5)

    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f'Job: {job_id[:20]}...', ln=True)

    if ai_results:
        pdf.cell(0, 10, f'Images Analyzed: {len(ai_results)}', ln=True)
    else:
        pdf.cell(0, 10, f'Total Images: {len(all_images)}', ln=True)
    pdf.ln(5)

    # Use AI results if available, otherwise fall back to basic image data
    if ai_results:
        # Detailed AI analysis results
        for idx, result in enumerate(ai_results, 1):
            if idx > 50:  # Limit to first 50
                break

            # Filename
            pdf.set_font('Arial', 'B', 11)
            image_url = result.get("imageUrl", "")
            filename = clean_filename(image_url)[:70]
            pdf.cell(0, 7, f'{idx}. {filename}', ln=True)

            analysis = result.get("analysis", {})
            error = result.get("error")

            if error:
                pdf.set_font('Arial', 'I', 9)
                pdf.cell(0, 5, clean_text(str(error)[:100]), ln=True)
            else:
                pdf.set_font('Arial', '', 9)

                # Scores
                acc_score = int(analysis.get("accuracy_score", 0))
                qual_score = int(analysis.get("quality_score", 0))
                sem_score = int(analysis.get("semantic_score", 0))
                pdf.cell(0, 5, f'Accuracy: {acc_score}/100  |  Quality: {qual_score}/100  |  Semantic: {sem_score}/100', ln=True)

                # Description
                description = clean_text(analysis.get("description", "N/A"))
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 5, 'AI Description:', ln=True)
                pdf.set_font('Arial', '', 8)
                # Split into lines manually to avoid multi_cell issues
                words = description.split()
                line = ""
                for word in words:
                    if len(line + " " + word) > 90:
                        pdf.cell(0, 4, line, ln=True)
                        line = word
                    else:
                        line = line + " " + word if line else word
                if line:
                    pdf.cell(0, 4, line, ln=True)

                # Suggested Alt Text
                suggested = clean_text(analysis.get("suggested_alt", "N/A"))
                pdf.set_font('Arial', 'B', 9)
                pdf.cell(0, 5, 'Suggested Alt:', ln=True)
                pdf.set_font('Arial', 'I', 8)
                pdf.cell(0, 4, f'"{suggested[:120]}"', ln=True)

                # Issues
                issues = analysis.get("issues", [])
                if issues:
                    pdf.set_font('Arial', '', 8)
                    issue_text = ", ".join(str(i) for i in issues[:5])
                    pdf.cell(0, 4, f'Issues: {issue_text}', ln=True)

            pdf.ln(4)
    else:
        # Fallback to basic image data
        for idx, img in enumerate(all_images, 1):
            if idx > 50:  # Limit to first 50
                break

            pdf.set_font('Arial', 'B', 11)
            filename = clean_text(img.filename or "Unknown")[:50]
            pdf.cell(0, 8, f'{idx}. {filename}', ln=True)

            pdf.set_font('Arial', '', 9)
            sem_score = int(img.semantic_score)
            overall_score = int(img.overall_score)
            pdf.cell(0, 6, f'   Semantic: {sem_score}/100  Overall: {overall_score}/100', ln=True)

            alt_text = clean_text(img.alt or "(none)")[:80]
            pdf.cell(0, 6, f'   Alt: {alt_text}', ln=True)
            pdf.ln(2)

    # Generate PDF bytes
    pdf_bytes = pdf.output()
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode('latin-1')

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="AI-Analysis-{job_id[:8]}.pdf"'}
    )

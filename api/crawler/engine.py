"""
Async crawl engine for the TalkingToad crawler.

Orchestrates the full crawl: URL queue management, robots.txt enforcement,
crawl delay, external link checking, and issue aggregation (spec §2.4, §2.8).
"""

import asyncio
import inspect
import logging
import os
import re
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlparse

import httpx

from api.crawler.fetcher import (FetchResult, fetch_page, make_client,
                                 make_ssrf_guarded_client)
from api.crawler.issue_checker import (
    Issue,
    check_amphtml_links,
    check_asset,
    check_cross_page,
    check_page,
    check_url_structure,
    collapse_per_target_occurrences,
    issue_for_status,
    issues_for_redirect,
    make_issue,
)
from api.crawler.normaliser import (
    QueryVariantTracker,
    is_admin_path,
    is_expected_disallow,
    is_same_domain,
    is_wp_noise_path,
    normalise_url,
)
from api.crawler.parser import ParsedPage, parse_page
from api.crawler.robots import RobotsData, fetch_robots
from api.crawler.sitemap import fetch_sitemap_recursive
from api.models.image import ImageInfo
from api.crawler.image_analyzer import analyze_batch as analyze_images

logger = logging.getLogger(__name__)


def _classify_fetch_error(error: str) -> str | None:
    """Classify a status-0 fetch error for accurate reporting (audit R0.4).

    Returns ``None`` for SSRF blocks (a security decision, not a page-health
    problem — the caller should skip emitting a page issue). Otherwise returns
    one of ``"timeout"``, ``"dns"``, ``"connection"``, ``"other"`` so the
    finding text is honest instead of blanket-labelling everything a timeout.
    """
    err = error or ""
    if err.startswith("SSRF_BLOCKED"):
        return None
    low = err.lower()
    if "timeout" in low or "timed out" in low:
        return "timeout"
    if "name or service" in low or "resolve" in low or "nodename" in low:
        return "dns"
    if "connect" in low or "connection" in low:
        return "connection"
    return "other"

_DEFAULT_MAX_PAGES = int(os.getenv("MAX_PAGES_PER_CRAWL", "500"))
# AF4: click depth above which HIGH_CRAWL_DEPTH fires (mirrors issue_checker).
_MAX_CLICK_DEPTH = int(os.getenv("TT_MAX_CLICK_DEPTH", "4"))
# IM1 — the dimension pass is bounded by a TOTAL byte budget, never by a
# per-image minimum size. A minimum-size gate was the first design and it was
# wrong: measured on livingsystems.ca, the only two genuinely overscaled images
# on the site are 30 KB and 9 KB, so a 100 KB gate skipped both and left
# IMG_OVERSCALED dead on exactly the cases it exists to catch (P9 — a magic
# limit that silently caps the input, justified by a narrative the data does
# not support). Overscaling is a ratio between intrinsic and display width; it
# has no lower bound in bytes.
_IMAGE_DIMENSION_TOTAL_BYTES = int(os.getenv("TT_IMAGE_DIMENSION_TOTAL_BYTES", str(48 * 1024 * 1024)))
# Skip a single pathologically large file rather than spending the whole budget
# on it. Its dimensions stay unmeasured and are reported as such.
_IMAGE_DIMENSION_MAX_BYTES = int(os.getenv("TT_IMAGE_DIMENSION_MAX_BYTES", str(12 * 1024 * 1024)))
# Kept at the per-job image cap: a larger number could never bind, and a dead
# bound makes the resource story read stronger than the code delivers.
_IMAGE_DIMENSION_MAX_COUNT = int(os.getenv("TT_IMAGE_DIMENSION_MAX_COUNT", "150"))
# A browser opens ~6 connections per host. The dimension pass previously
# launched every candidate at once, so load_time_ms measured the crawler's own
# queueing rather than the site's speed — and IMG_SLOW_LOAD is scored from it.
_IMAGE_DIMENSION_CONCURRENCY = int(os.getenv("TT_IMAGE_DIMENSION_CONCURRENCY", "6"))
_IMAGE_DIMENSION_BUDGET_S = float(os.getenv("TT_IMAGE_DIMENSION_BUDGET_S", "45"))
_IMAGE_DIMENSION_TIMEOUT_S = float(os.getenv("TT_IMAGE_DIMENSION_TIMEOUT_S", "8"))
# Budgeting happens before the download, so an image whose HEAD gave no
# content-length is charged this nominal amount against the budget.
_IMAGE_DIMENSION_UNKNOWN_SIZE = 150 * 1024
_MIN_CRAWL_DELAY_MS = 200
_EXTERNAL_LINK_CAP_PER_PAGE = 50
_EXTERNAL_LINK_CAP_PER_JOB = 500

# E2.2 (rule 8) — how many linking pages to carry in an issue's evidence list.
# The uncapped total always travels alongside it as `occurrence_urls_total`, so
# every surface can say "showing 50 of 120" instead of implying 50 is all there is.
_BROKEN_LINK_SOURCE_CAP = int(os.getenv("TT_BROKEN_LINK_SOURCE_CAP", "50"))


def _broken_link_extra(
    *,
    target_url: str,
    sources: list[str],
    first_source: str | None = None,
    anchor_texts: list[str] | None = None,
) -> dict:
    """Build the `extra` payload for a broken-link issue.

    Purpose: carry EVERY page that links to a broken target, capped for size but
             with the true total alongside, so a template-wide defect reads as one.
    Spec:    docs/pending/2026-08-29_E2-broken-link-source-attribution.md#E2.2
    Tests:   tests/test_broken_link_attribution.py::TestBrokenLinkExtra

    `source_url` is retained for backwards compatibility with existing consumers.
    """
    listed = sources[:_BROKEN_LINK_SOURCE_CAP]
    extra = {
        "target_url": target_url,
        # `occurrences` is the SCORING count and keeps its §2 meaning: how many
        # offending links this issue represents on its own page. It stays 1 here.
        #
        # It must not become the site-wide linking-page count. This issue is
        # anchored to ONE page (the first source found, or the 4xx target), and
        # `occurrence_multiplier` scales that page's deduction by it — so a
        # footer link broken on 200 pages would double the deduction on whichever
        # page the crawler happened to reach first, and per-page health would
        # become crawl-order dependent. Worse, BROKEN_LINK_503 and
        # EXTERNAL_LINK_TIMEOUT are per-target codes too, so one flaky outage on
        # a nav-linked target would be amplified 2x (P1/P7).
        "occurrences": 1,
        # Evidence: the pages that link here. Capped for payload size, with the
        # true total alongside so every surface can disclose the truncation.
        "occurrence_urls": listed,
        "occurrence_urls_total": len(sources),
    }
    primary = first_source or (sources[0] if sources else None)
    if primary:
        extra["source_url"] = primary
    if anchor_texts:
        extra["anchor_texts"] = [t for t in anchor_texts[:_BROKEN_LINK_SOURCE_CAP] if t]
    return extra

# Social media and other platforms known to block automated HTTP requests.
# Checking these produces false positives (e.g. LinkedIn returns 999, Facebook
# redirects to a login wall). We skip external link checking for these domains
# entirely — a human click will work fine even though a bot request fails.
_BOT_BLOCKING_DOMAINS: frozenset[str] = frozenset(
    [
        "linkedin.com",
        "www.linkedin.com",
        "facebook.com",
        "www.facebook.com",
        "fb.com",
        "instagram.com",
        "www.instagram.com",
        "twitter.com",
        "www.twitter.com",
        "x.com",
        "www.x.com",
        "tiktok.com",
        "www.tiktok.com",
    ]
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

# Maps analysis toggle names (v1.3 §3.1) to the issue categories they cover.
_ANALYSIS_CATEGORY_MAP: dict[str, frozenset[str]] = {
    "link_integrity": frozenset({"broken_link", "redirect"}),
    "seo_essentials": frozenset({"metadata", "url_structure"}),
    "site_structure": frozenset({"heading"}),
    "indexability":   frozenset({"crawlability", "sitemap"}),
    # CLN3: rendering + semantic_html are agent-readiness siblings of ai_readiness
    # (added by the agent-readiness P1 work) — reachable via the ai_readiness toggle.
    "ai_readiness":   frozenset({"ai_readiness", "rendering", "semantic_html"}),
    "analytics":      frozenset({"analytics"}),
    # CLN3: `image` gets its own self-named group (like analytics/ai_readiness) so
    # a partial selection can enable it — previously it belonged to no group and
    # was unreachable except via the all-on (enabled_analyses=None) path.
    "image":          frozenset({"image"}),
}
# `security` is the SOLE always-emitted category (even under a partial
# `enabled_analyses`) — critical safety issues run regardless. Every OTHER
# category must be reachable through a named group above. The union of all groups
# ∪ this set MUST equal the full registry category set — enforced by
# tests/test_engine_analysis_map.py::test_cln3_1_map_covers_every_category.
_UNGROUPED_CATEGORIES: frozenset[str] = frozenset({"security"})


def _enabled_categories(enabled_analyses: list[str] | None) -> frozenset[str] | None:
    """Return the set of allowed issue categories, or None if all are enabled."""
    if enabled_analyses is None:
        return None
    cats: set[str] = set(_UNGROUPED_CATEGORIES)
    for group in enabled_analyses:
        cats.update(_ANALYSIS_CATEGORY_MAP.get(group, frozenset()))
    return frozenset(cats)


@dataclass
class CrawlSettings:
    max_pages: int = _DEFAULT_MAX_PAGES
    crawl_delay_ms: int = 500
    respect_robots: bool = True
    include_subdomains: list[str] = field(default_factory=list)
    # None = all analyses enabled; supply a list of group names to restrict.
    enabled_analyses: list[str] | None = None
    # Image size threshold in KB — images larger than this are flagged as IMG_OVERSIZED.
    img_size_limit_kb: int = 200
    # Page HTML size threshold in KB — pages larger than this are flagged as PAGE_SIZE_LARGE.
    page_size_limit_kb: int = 300
    # Skip WordPress author/category/tag archive pages (default True).
    # These pages are auto-generated by WP and produce non-actionable issues.
    skip_wp_archives: bool = True
    # URLs that the user has manually verified as good — suppress EXTERNAL_LINK_SKIPPED for these.
    verified_link_urls: set[str] = field(default_factory=set)
    # H1 strings to ignore during heading checks — for theme-injected headings that
    # repeat on every page (e.g. a Salient/Avada page-header banner title).
    suppress_h1_strings: list[str] = field(default_factory=list)
    # When True, auto-detect and ignore H1s that don't match the page title.
    suppress_banner_h1: bool = False
    # Href URLs exempt from LINK_EMPTY_ANCHOR — for icon links (social media etc.)
    # that intentionally have no anchor text.
    exempt_anchor_urls: set[str] = field(default_factory=set)
    # URL patterns for images to ignore in issue checks (e.g. theme SVG icons).
    # Substring match — "/location.svg" matches any URL containing that string.
    ignored_image_patterns: list[str] = field(default_factory=list)
    # Single-page mode: crawl only the exact URL given, no sitemap seeding or link following
    single_page: bool = False
    # Content-type scoping allowlist (partial scan). None = no scoping (full
    # crawl). When a set, the crawler visits ONLY these URLs (plus the start URL)
    # and never follows links or seeds sitemap URLs outside the set. The set is
    # resolved from an authoritative source (WP REST or typed sitemaps) at the
    # router layer — the engine never classifies a URL by pattern.
    scope_urls: set[str] | None = None
    # GSC priority seed (2026-08-14, U2): an ORDERED list of URLs to crawl first
    # (right after the homepage, before sitemap URLs). Advisory — same-domain,
    # in-scope, deduped; off-domain/out-of-scope entries are skipped, never fatal.
    priority_urls: list[str] | None = None


@dataclass
class BrokenLinkRef:
    """One (target, source) pair for a broken link, with the facts needed to
    persist it faithfully.

    Purpose: replace the legacy 3-tuple, which forced the router to hardcode
             `link_type="external"` and to drop `status_code` entirely — so a
             same-host 404 was stored as external and a transient 503 was
             indistinguishable from a permanent 404 (P1).
    Spec:    docs/pending/2026-08-29_E2-broken-link-source-attribution.md#E2.3
    Tests:   tests/test_broken_link_attribution.py
    """
    target_url: str
    source_url: str
    link_text: str | None = None
    status_code: int | None = None
    link_type: str = "external"   # "internal" | "external", derived, never assumed


# O2 — orphan-detection coverage vocabulary. `complete` is the ONLY value that
# licenses a caller to read "zero orphans" as "no orphans found"; every other
# value means the check did not run over a whole-site link graph and a zero is
# "not checked" (P31).
ORPHAN_STATUS_COMPLETE = "complete"
ORPHAN_NOT_RUN: dict = {
    "status": "not_run", "pages_analysed": 0, "pages_out_of_scope": 0,
}


@dataclass
class CrawlResult:
    job_id: str
    pages: list[ParsedPage]
    issues: list[Issue]
    pages_crawled: int
    external_links_checked: int
    cancelled: bool = False
    # E2.3: one BrokenLinkRef per (target, source) pair for every broken link,
    # internal and external. Stored so the router can persist them to the links
    # table for the Fix panel. Was a list[tuple[str, str, str | None]] before
    # 2026-08-29 — a return-contract change, so every call site was updated in
    # the same commit (P22) and test_architecture_constraints guards the old shape.
    broken_link_sources: list[BrokenLinkRef] = field(default_factory=list)
    # v1.9image: Analyzed images with scores and issues
    images: list[ImageInfo] = field(default_factory=list)
    # Crawl discovery info for display
    robots_txt_found: bool = False
    robots_txt_rules: list[str] = field(default_factory=list)
    sitemap_found: bool = False
    sitemap_url_found: str | None = None
    sitemap_url_count: int = 0
    # Number of distinct URLs skipped because they fell outside the selected
    # content-type scope (partial scan). 0 when no scoping is active.
    scope_skipped: int = 0
    # O2 — whether ORPHAN_PAGE actually ran, and over how much of the site.
    # ORPHAN_PAGE is an absence-proof and is only sound over a complete link
    # graph (P31), so a partial scan / budget truncation / cancellation
    # suppresses it. Zero orphans then means "not checked", NOT "none found" —
    # every surface must render the two differently, so the reason travels with
    # the result rather than being inferred from a count.
    # Spec: docs/functional-specification.md §4.4 (ORPHAN_PAGE)
    # Defaults to "not_run", NOT "complete": any construction that forgets this
    # field would otherwise make an affirmative whole-site claim on behalf of a
    # crawl that may have fetched nothing. Only the one code path that has
    # actually established completeness may set "complete" (P31 — make the
    # wrong state unrepresentable rather than fixing each caller).
    orphan_detection: dict = field(default_factory=lambda: dict(ORPHAN_NOT_RUN))
    # AF10 — how much of what the sitemap declares was actually fetched.
    # {declared, crawled, not_crawled, reasons}. declared == 0 means no sitemap.
    sitemap_coverage: dict = field(default_factory=lambda: {
        "declared": 0, "crawled": 0, "not_crawled": 0, "reasons": {}})
    # C1 — which analysis groups ran. A category that was switched off must
    # render as "not checked", never as a clean 0.
    analysis_coverage: dict = field(default_factory=dict)
    # E1.4 (P9, rule 6): distinct image URLs SEEN across the crawl vs the number
    # that survived the per-job cap and were analysed. When these differ, every
    # surface must say "analysed N of M" rather than implying full coverage.
    # Spec: docs/pending/2026-08-29_E1-lazy-loaded-image-extraction.md#E1.4
    images_seen_total: int = 0
    images_collected: int = 0
    # IM1 — how many collected images had their pixel dimensions actually
    # measured. IMG_OVERSCALED / IMG_NO_SRCSET / IMG_DUPLICATE_CONTENT /
    # IMG_SLOW_LOAD are only sound over measured images: an unmeasured image
    # is "not checked", never "clean" (P31). When these differ, every surface
    # must say "measured N of M".
    images_measured: int = 0
    images_measurable: int = 0


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[dict], None]


async def run_crawl(
    job_id: str,
    target_url: str,
    settings: CrawlSettings | None = None,
    *,
    on_progress: ProgressCallback | None = None,
    cancel_event: asyncio.Event | None = None,
) -> CrawlResult:
    """Run a full crawl of *target_url* and return a :class:`CrawlResult`.

    Args:
        job_id: Unique identifier for this crawl job (used in log entries).
        target_url: The start URL to crawl (must include scheme).
        settings: Crawl configuration. Falls back to defaults if None.
        on_progress: Optional callback invoked after each page is crawled.
            Receives a dict with ``pages_crawled``, ``pages_total``, ``current_url``.
        cancel_event: If set, the engine checks this after each page and stops
            cleanly when the event fires.
    """
    print(f"[CRAWL] run_crawl started for {target_url}")
    if settings is None:
        settings = CrawlSettings()

    crawl_delay_s = max(_MIN_CRAWL_DELAY_MS, settings.crawl_delay_ms) / 1000.0

    try:
        normalised_start = normalise_url(target_url)
    except ValueError:
        logger.error("invalid_target_url", extra={"job_id": job_id, "url": target_url})
        return CrawlResult(job_id=job_id, pages=[], issues=[], pages_crawled=0, external_links_checked=0)

    log = logging.LoggerAdapter(logger, {"job_id": job_id})

    async with make_client() as client:
        # ── 1. Fetch robots.txt ────────────────────────────────────────────
        robots_data: RobotsData | None = None
        if settings.respect_robots:
            robots_data = await fetch_robots(normalised_start, client)
            crawl_delay_s = _effective_delay(crawl_delay_s, robots_data)

        # ── 2. Fetch sitemap ──────────────────────────────────────────────
        robots_sitemap_urls = robots_data.sitemap_urls if robots_data else []
        sitemap_result = await fetch_sitemap_recursive(
            normalised_start, client, robots_sitemap_urls=robots_sitemap_urls
        )

        sitemap_url_set: set[str] = set()
        for _su in sitemap_result.urls:
            try:
                sitemap_url_set.add(normalise_url(_su))
            except ValueError:
                sitemap_url_set.add(_su)
        pages_total: int | None = len(sitemap_url_set) if sitemap_url_set else None

        # Collect discovery info for display
        _robots_found = robots_data is not None and robots_data.raw_text is not None
        _robots_rules: list[str] = []
        if _robots_found and robots_data and robots_data.raw_text:
            for line in robots_data.raw_text.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    _robots_rules.append(stripped)
        _sitemap_found = sitemap_result.found
        _sitemap_url_found = sitemap_result.source_url if _sitemap_found else None
        _sitemap_url_count = len(sitemap_url_set)

        all_pages: list[ParsedPage] = []
        all_issues: list[Issue] = []
        favicon_emitted = False
        hsts_checked_hosts: set[str] = set()

        # ── 2.5. HTTPS redirect check ─────────────────────────────────────
        # If the site is HTTPS, verify that the HTTP version redirects to HTTPS.
        if normalised_start.startswith("https://"):
            http_url = "http://" + normalised_start[8:]
            try:
                http_result = await fetch_page(http_url, client)
                redirects_to_https = (
                    http_result.final_url is not None
                    and http_result.final_url.startswith("https://")
                )
                if not redirects_to_https:
                    all_issues.append(make_issue("HTTPS_REDIRECT_MISSING", normalised_start,
                                                 extra={"http_url": http_url,
                                                        "redirected_to": http_result.final_url}))
            except Exception:
                pass  # network error — cannot determine redirect behaviour

        # ── 2.55. WWW canonicalization check ──────────────────────────────
        parsed_start = urlparse(normalised_start)
        host = parsed_start.netloc
        if host.startswith("www."):
            alt_host = host[4:]  # remove www.
        else:
            alt_host = "www." + host
        alt_url = f"{parsed_start.scheme}://{alt_host}{parsed_start.path}"
        try:
            alt_result = await fetch_page(alt_url, client)
            # If alt version returns 200 and doesn't redirect to the primary, flag it
            if (alt_result.status_code == 200
                and (not alt_result.final_url or urlparse(alt_result.final_url).netloc == alt_host)):
                all_issues.append(make_issue("WWW_CANONICALIZATION", normalised_start,
                    extra={"primary": normalised_start, "alternative": alt_url}))
        except Exception:
            pass  # alt version unreachable — that's fine, only one version exists

        # ── 2.6. llms.txt check ───────────────────────────────────────────
        # Check for /llms.txt and /llms-full.txt at the root (spec §2.1).
        parsed_root = urlparse(normalised_start)
        root_url = f"{parsed_root.scheme}://{parsed_root.netloc}"
        try:
            llms_txt_url = f"{root_url}/llms.txt"
            llms_res = await fetch_page(llms_txt_url, client)
            if llms_res.status_code != 200:
                all_issues.append(make_issue("LLMS_TXT_MISSING", normalised_start,
                                           extra={"expected_url": llms_txt_url,
                                                  "status_code": llms_res.status_code}))
            else:
                # Validity per https://llmstxt.org: an llms.txt is a Markdown
                # file whose ONLY required element is the H1 project-title line
                # ("# Name"). A '>' blockquote summary, detail text, '##' link
                # sections, and the link count are all OPTIONAL — the spec sets
                # no cap. So the only structural failure we flag is a body that
                # is not a Markdown llms.txt at all: a soft-404 web page or a
                # file with no H1 title. (Strip a leading UTF-8 BOM first —
                # Yoast and other generators emit one before the '#'.)
                body = (llms_res.text or llms_res.html or "").lstrip("﻿")
                has_h1 = bool(re.search(r"^# \S", body, re.MULTILINE))
                if not has_h1:
                    issue = make_issue("LLMS_TXT_INVALID", normalised_start)
                    issue.description = (
                        "/llms.txt is not a valid llms.txt file: it has no "
                        "'# Title' heading (see https://llmstxt.org). The URL "
                        "may be returning a normal web page (soft 404) instead "
                        "of a Markdown file."
                    )
                    all_issues.append(issue)
        except Exception:
            pass

        # ── 2.7. AI bot access checks ─────────────────────────────────────
        # Check robots.txt for AI crawler blocks, misconfiguration, and deprecated directives.
        try:
            from api.services.ai_readiness import check_ai_bot_access
            ai_bot_issues = check_ai_bot_access(robots_data, normalised_start)
            all_issues.extend(ai_bot_issues)
        except Exception as e:
            log.warning("ai_bot_check_error", extra={"error": str(e)})

        # ── 2.8. ai.txt check (GEO.6.2) ─────────────────────────────────────
        try:
            ai_txt_url = f"{root_url}/ai.txt"
            ai_txt_res = await fetch_page(ai_txt_url, client)
            if ai_txt_res.status_code != 200:
                all_issues.append(make_issue("AI_TXT_MISSING", normalised_start,
                                             extra={"expected_url": ai_txt_url,
                                                    "status_code": ai_txt_res.status_code}))
        except Exception:
            pass

        # If no sitemap found, record that as an issue
        if sitemap_result.missing_issue:
            all_issues.append(
                Issue(
                    code="SITEMAP_MISSING",
                    category="sitemap",
                    severity="info",
                    description=sitemap_result.missing_issue["message"],
                    recommendation="Create an XML sitemap and submit it to Google Search Console. Most CMS platforms can generate one automatically.",
                    page_url=None,
                )
            )

        # ── 3. Crawl queue setup ──────────────────────────────────────────
        # Queue entries are (url, depth); homepage depth = 0, sitemap-seeded = None
        queue: deque[tuple[str, int | None]] = deque([(normalised_start, 0)])
        visited: set[str] = set()
        variant_tracker = QueryVariantTracker()
        depth_map: dict[str, int | None] = {normalised_start: 0}

        # Track which page discovered each URL (for broken link source reporting)
        discovered_from: dict[str, str] = {}

        # Content-type scope allowlist (partial scan). None = no scoping.
        # The start URL is always allowed so the homepage/summary still resolves.
        scope_urls = settings.scope_urls
        scope_skipped_urls: set[str] = set()
        # O1: set when the BFS stops at the page budget with URLs still queued.
        truncated_by_max_pages = False
        # AF10: why each dequeued URL was never fetched. The sitemap declares
        # N URLs; if we fetch N-k, the report must say which k and why —
        # nothing compared the two sets before (P31).
        # Spec:  docs/pending/2026-08-30_audit-fixes.md#AF10
        # Tests: tests/test_sitemap_coverage.py
        skip_reasons: dict[str, str] = {}
        unfetched_at_truncation = 0
        # O2: pages the crawl reached but could not read the links of — a
        # timeout, an SSRF block, a login wall, a parse failure. Each one is a
        # hole in the link graph: if a hub page times out, every page it links
        # to looks orphaned. Counted and disclosed rather than gated, since a
        # single 429 must not disable the check for the whole site (P1/P2).
        pages_links_unread = 0

        def _in_scope(u: str) -> bool:
            return scope_urls is None or u == normalised_start or u in scope_urls

        # Priority seed (GSC upload, U2): front these URLs so they're crawled
        # first — right after the homepage, before sitemap URLs. Advisory: enqueue
        # only same-domain, in-scope, not-already-seen URLs; a bad entry is skipped.
        if not settings.single_page and settings.priority_urls:
            for pu in settings.priority_urls:
                try:
                    norm = normalise_url(pu)
                except ValueError:
                    continue
                if norm == normalised_start or norm in depth_map:
                    continue
                if not is_same_domain(norm, normalised_start) or not _in_scope(norm):
                    continue
                queue.append((norm, None))
                depth_map[norm] = None
                discovered_from.setdefault(norm, "(gsc-priority)")

        # Seed from sitemap — skipped in single_page mode
        if not settings.single_page:
            for norm in sitemap_url_set:
                if norm != normalised_start and is_same_domain(norm, normalised_start):
                    if not _in_scope(norm):
                        scope_skipped_urls.add(norm)
                        continue
                    queue.append((norm, None))
                    if norm not in depth_map:
                        depth_map[norm] = None
                    discovered_from.setdefault(norm, "(sitemap)")

        # External links: collected during internal crawl, checked after
        # Format: {"source_url": str, "target_url": str, "link_text": str|None}
        external_link_queue: list[dict] = []
        external_per_page_count: dict[str, int] = {}
        # E2.1: a target is FETCHED once (dedupe by URL, unchanged) but every page
        # that links to it is retained. Keeping only the first source is what made
        # 120 broken internal links report as 10 targets with occurrences=1, hiding
        # that a single reusable-block edit fixes most of them.
        # Spec: docs/pending/2026-08-29_E2-broken-link-source-attribution.md#E2.1
        external_target_sources: "OrderedDict[str, list[dict]]" = OrderedDict()
        # Every page that linked to an internal URL, in discovery order. Additive:
        # `discovered_from` keeps its first-discoverer depth/parent semantics (P12).
        discovered_from_all: dict[str, list[str]] = {}
        # Every broken link found (internal + external), one record per (target, source).
        broken_link_sources: list[BrokenLinkRef] = []

        # Image data: collected during internal crawl, analyzed after
        # Format: dict from parser with url, page_url, alt, srcset, etc.
        # E1.4: the cap is configurable (rule 8) and what it drops is announced
        # (rule 6) — `image_targets_seen` counts every DISTINCT image URL found,
        # including those the cap turned away, so the report can say "N of M".
        _IMAGE_URL_CAP_PER_JOB = int(os.getenv("TT_IMAGE_URL_CAP_PER_JOB", "150"))
        image_data_queue: list[dict] = []
        image_targets_seen: set[str] = set()

        # ── 4. Internal crawl loop ────────────────────────────────────────
        while queue:
            if cancel_event and cancel_event.is_set():
                log.info("crawl_cancelled")
                return CrawlResult(
                    job_id=job_id,
                    pages=all_pages,
                    issues=all_issues,
                    pages_crawled=len(all_pages),
                    external_links_checked=0,
                    cancelled=True,
                    # Cancelled mid-crawl: the link graph stops wherever the
                    # frontier was, so ORPHAN_PAGE never ran (P31) and zero
                    # orphans must not read as "none found".
                    orphan_detection={"status": "skipped_cancelled",
                                      "pages_analysed": len(all_pages),
                                      "pages_out_of_scope": len(scope_skipped_urls) + len(queue),
                                      "archives_skipped": bool(settings.skip_wp_archives)},
                    robots_txt_found=_robots_found,
                    robots_txt_rules=_robots_rules,
                    sitemap_found=_sitemap_found,
                    sitemap_url_found=_sitemap_url_found,
                    sitemap_url_count=_sitemap_url_count,
                )

            url, current_depth = queue.popleft()

            if url in visited:
                continue
            visited.add(url)

            if not variant_tracker.record(url):
                log.warning("query_variant_cap_reached", extra={"url": url})
                skip_reasons[url] = "query_variant_cap"
                continue

            if is_admin_path(url):
                log.debug("admin_path_skipped", extra={"url": url})
                skip_reasons[url] = "admin_path"
                continue

            if settings.skip_wp_archives and is_wp_noise_path(url):
                log.debug("wp_noise_skipped", extra={"url": url})
                skip_reasons[url] = "wordpress_archive"
                continue

            if robots_data and not robots_data.is_allowed(url):
                # R2.x #8: don't flag intentional blocks (cart/checkout/account/
                # search/faceted-filter URLs) — those are correctly disallowed.
                if is_expected_disallow(url):
                    log.debug("robots_expected_disallow_skipped", extra={"url": url})
                    skip_reasons[url] = "robots_expected_disallow"
                    continue
                log.info("robots_blocked", extra={"url": url})
                all_issues.append(make_issue("ROBOTS_BLOCKED", url,
                                           extra={"blocked_url": url,
                                                  # crawl-blocking, not index-blocking
                                                  "note": "robots.txt blocks CRAWLING of this URL; "
                                                  "it does not remove an already-indexed URL. Use a "
                                                  "noindex directive to remove a page from search."}))
                skip_reasons[url] = "robots_blocked"
                continue

            if len(all_pages) >= settings.max_pages:
                log.info("max_pages_reached", extra={"max": settings.max_pages})
                # The frontier still holds unvisited URLs, so the link graph is
                # partial from here on — ORPHAN_PAGE must not run (P31). Record
                # how many were left so the disclosure quantifies the shortfall
                # rather than printing a bare 0.
                truncated_by_max_pages = True
                unfetched_at_truncation = len(queue) + 1  # +1: this URL, popped but unfetched
                break

            # URL structure checks run before fetching (pure string operations)
            all_issues.extend(check_url_structure(url))

            await asyncio.sleep(crawl_delay_s)

            if on_progress:
                payload = {
                    "pages_crawled": len(all_pages),
                    "pages_total": pages_total,
                    "current_url": url,
                    "phase": "crawling_pages",
                    "external_links_checked": 0,
                    "external_links_total": 0,
                }
                result = on_progress(payload)
                if inspect.isawaitable(result):
                    await result

            try:
                result = await fetch_page(url, client)
            except Exception as exc:
                log.warning("fetch_exception", extra={"url": url, "error": str(exc)})
                continue

            log.info(
                "page_crawled",
                extra={"url": url, "status_code": result.status_code},
            )

            # Handle redirect loop
            if result.error == "REDIRECT_LOOP":
                all_issues.append(make_issue("REDIRECT_LOOP", url))
                continue

            # Handle fetch errors / timeouts (network failure, status_code=0).
            # R0.4 (audit 2026-07-03): PAGE_TIMEOUT previously fired for ANY
            # status-0 error — DNS failures, refused connections, and even SSRF
            # blocks were reported to the user as "timeouts". Now we classify:
            #   • SSRF blocks are a security decision, not a page-health problem
            #     — log and skip, do NOT emit a page issue.
            #   • real timeouts vs other fetch failures are tagged in
            #     extra.error_type so the finding text is accurate.
            # (Follow-up R0.4-full: a dedicated FETCH_FAILED code — needs
            #  catalogue + scoring + frontend help + parity, deferred to the
            #  scoring PR. Until then we keep PAGE_TIMEOUT but label it honestly.)
            if result.error and result.status_code == 0:
                err = result.error or ""
                error_type = _classify_fetch_error(err)
                if error_type is None:  # SSRF block — security decision, not page health
                    log.warning("fetch_ssrf_blocked", extra={"url": url, "error": err})
                    pages_links_unread += 1
                    continue
                log.warning("fetch_failed", extra={"url": url, "error": err, "error_type": error_type})
                timeout_issue = make_issue("PAGE_TIMEOUT", url,
                                           extra={"error": err, "error_type": error_type})
                all_issues.append(timeout_issue)
                pages_links_unread += 1
                continue

            # Login redirect
            if result.is_login_redirect:
                all_issues.append(make_issue("LOGIN_REDIRECT", url,
                                           extra={"redirect_to": result.final_url}))
                pages_links_unread += 1
                continue

            # Redirect issues
            if result.redirect_chain:
                redirect_issues = issues_for_redirect(
                    url, result.first_status_code, result.redirect_chain,
                    final_url=result.final_url,
                    base_url=normalised_start,
                )
                all_issues.extend(redirect_issues)
                # Add final URL to visited so we don't crawl it again
                try:
                    visited.add(normalise_url(result.final_url))
                except ValueError:
                    pass

            try:
                is_homepage = (url == normalised_start)
                page = parse_page(result, normalised_start, is_homepage=is_homepage)
            except Exception as exc:
                log.warning("parse_exception", extra={"url": url, "error": str(exc)})
                pages_links_unread += 1
                continue

            page.crawl_depth = current_depth
            page.last_modified = result.headers.get("last-modified")
            all_pages.append(page)

            # ── Branch: HTML vs non-HTML assets ───────────────────────────
            ct = result.content_type
            is_html = "html" in ct
            is_asset = "pdf" in ct or ct.startswith("image/")

            if is_html:
                # Skip SEO checks on 4xx/5xx pages — they are error pages, not real content.
                # Emit a BROKEN_LINK_404 (or 5xx variant) issue so the user knows this internal
                # page is broken.
                if result.status_code >= 400:
                    broken = issue_for_status(result.status_code, url)
                    if broken:
                        source = discovered_from.get(url)
                        # E2.2: every page that links here, not just the first.
                        all_sources = [
                            s for s in discovered_from_all.get(url, [])
                            if s and s != "(sitemap)"
                        ]
                        if source and source != "(sitemap)" and source not in all_sources:
                            all_sources.insert(0, source)
                        broken.extra = _broken_link_extra(
                            target_url=url, sources=all_sources, first_source=source
                        )
                        # Store in broken_link_sources so the links table gets populated
                        # (enables "Show Source Pages" for internal broken links)
                        for src in all_sources:
                            broken_link_sources.append(BrokenLinkRef(
                                target_url=url, source_url=src, link_text=None,
                                status_code=result.status_code, link_type="internal",
                            ))
                    page_issues = [broken] if broken else []
                else:
                    try:
                        page_issues = check_page(
                            page,
                            sitemap_urls=sitemap_url_set or None,
                            favicon_emitted=favicon_emitted,
                            hsts_checked_hosts=hsts_checked_hosts,
                            page_size_limit_kb=settings.page_size_limit_kb,
                            suppress_h1_strings=settings.suppress_h1_strings,
                            suppress_banner_h1=settings.suppress_banner_h1,
                            exempt_anchor_urls=settings.exempt_anchor_urls or None,
                            ignored_image_patterns=settings.ignored_image_patterns or None,
                        )
                    except Exception as exc:
                        log.warning("issue_check_exception", extra={"url": url, "error": str(exc)})
                        page_issues = []

                # Track favicon emission so we only emit once per job
                if any(i.code == "FAVICON_MISSING" for i in page_issues):
                    favicon_emitted = True

            elif is_asset:
                log.info("asset_crawled", extra={"url": url, "content_type": ct})
                page_issues = check_asset(result, img_size_limit_kb=settings.img_size_limit_kb)

            else:
                # Unknown binary (video, font, etc.) — record status only, no checks
                log.debug("binary_skipped", extra={"url": url, "content_type": ct})
                page_issues = []

            all_issues.extend(page_issues)

            # Queue new URLs from links — skipped in single_page mode
            child_depth = (current_depth + 1) if current_depth is not None else None
            if not settings.single_page:
              for link in page.links:
                if link.is_internal:
                    try:
                        norm = normalise_url(link.url)
                    except ValueError:
                        continue
                    if norm not in visited:
                        # Content-type scope: never follow links outside the
                        # selected content types (partial scan).
                        if not _in_scope(norm):
                            scope_skipped_urls.add(norm)
                            continue
                        # Only update depth_map if we haven't seen this URL yet
                        # (first discovery via HTML gives the shallowest depth).
                        # AF4: this in-crawl value is advisory only — the
                        # authoritative click depth is recomputed after the crawl
                        # by _compute_click_depths(), which is order-independent.
                        if norm not in depth_map:
                            depth_map[norm] = child_depth
                        discovered_from.setdefault(norm, url)
                        queue.append((norm, depth_map[norm]))
                    # E2.1: record EVERY page that links here, whether or not the
                    # target is already queued/visited. `discovered_from` above
                    # keeps its first-discoverer semantics untouched (P12); this
                    # is purely additive and is what lets a 4xx page report all
                    # the pages that need editing, not just the first one found.
                    sources = discovered_from_all.setdefault(norm, [])
                    if url not in sources:
                        sources.append(url)
                else:
                    # Collect external links for later checking (subject to caps)
                    target = link.url
                    if target in external_target_sources:
                        # Already queued for fetching — record this additional
                        # source and move on. Does NOT consume the per-page quota:
                        # that quota limits how many DISTINCT targets one page
                        # contributes, not how many pages point at a known target.
                        srcs = external_target_sources[target]
                        if not any(s["source_url"] == url for s in srcs):
                            srcs.append({"source_url": url, "link_text": link.text})
                        continue
                    per_page = external_per_page_count.get(url, 0)
                    if per_page < _EXTERNAL_LINK_CAP_PER_PAGE:
                        external_link_queue.append({
                            "source_url": url,
                            "target_url": target,
                            "link_text": link.text,
                        })
                        external_per_page_count[url] = per_page + 1
                        external_target_sources[target] = [
                            {"source_url": url, "link_text": link.text}
                        ]

            # Collect image data for full analysis (v1.9image)
            if is_html:
                if page.image_data:
                    for img_data in page.image_data:
                        img_url = img_data.get("url")
                        if not img_url or img_url in image_targets_seen:
                            continue
                        # Count every distinct URL seen, cap or no cap (E1.4).
                        image_targets_seen.add(img_url)
                        if len(image_data_queue) < _IMAGE_URL_CAP_PER_JOB:
                            image_data_queue.append(img_data)

        # ── 5. External link checking ─────────────────────────────────────
        external_checked = 0
        external_total = min(len(external_link_queue), _EXTERNAL_LINK_CAP_PER_JOB)

        # Update phase to external link checking
        if on_progress and external_total > 0:
            payload = {
                "pages_crawled": len(all_pages),
                "pages_total": pages_total,
                "current_url": None,
                "phase": "checking_external_links",
                "external_links_checked": 0,
                "external_links_total": external_total,
            }
            result = on_progress(payload)
            if inspect.isawaitable(result):
                await result

        # Pre-filter bot-blocking domains (no network call needed)
        links_to_check: list[dict] = []
        for ext in external_link_queue:
            if external_checked >= _EXTERNAL_LINK_CAP_PER_JOB:
                log.info("external_link_cap_reached", extra={"cap": _EXTERNAL_LINK_CAP_PER_JOB})
                break
            target = ext["target_url"]
            if _is_bot_blocking_domain(target):
                if target not in settings.verified_link_urls:
                    issue = make_issue("EXTERNAL_LINK_SKIPPED", ext["source_url"])
                    issue.extra = {"target_url": target}
                    issue.description = f"Link to {target} was skipped — the site may block bots"
                    all_issues.append(issue)
                external_checked += 1
                continue
            links_to_check.append(ext)
            external_checked += 1

        # Check remaining links concurrently (10 at a time)
        _EXT_CONCURRENCY = 10
        sem = asyncio.Semaphore(_EXT_CONCURRENCY)

        async def _check_one(ext: dict) -> tuple[dict, FetchResult | None]:
            async with sem:
                if cancel_event and cancel_event.is_set():
                    return ext, None
                return ext, await _check_external_link(ext["target_url"], client)

        tasks = [_check_one(ext) for ext in links_to_check]
        completed = 0
        for coro in asyncio.as_completed(tasks):
            ext, result = await coro
            completed += 1

            if on_progress and (completed % 10 == 0 or completed == len(links_to_check)):
                payload = {
                    "pages_crawled": len(all_pages),
                    "pages_total": pages_total,
                    "current_url": None,
                    "phase": "checking_external_links",
                    "external_links_checked": external_checked - len(links_to_check) + completed,
                    "external_links_total": external_total,
                }
                result_prog = on_progress(payload)
                if inspect.isawaitable(result_prog):
                    await result_prog

            if result is not None:
                target = ext["target_url"]
                source_url = ext["source_url"]
                # E2.2: every page that links to this target, not just the one
                # that happened to be crawled first.
                srcs = external_target_sources.get(target) or [
                    {"source_url": source_url, "link_text": ext.get("link_text")}
                ]
                source_urls = [s["source_url"] for s in srcs]
                anchor_texts = [s.get("link_text") for s in srcs]
                link_type = "internal" if is_same_domain(target, normalised_start) else "external"

                def _record(status_code: int | None) -> None:
                    for s in srcs:
                        broken_link_sources.append(BrokenLinkRef(
                            target_url=target,
                            source_url=s["source_url"],
                            link_text=s.get("link_text"),
                            status_code=status_code,
                            link_type=link_type,
                        ))

                if result.status_code == 0 and result.error:
                    issue = make_issue("EXTERNAL_LINK_TIMEOUT", source_url)
                    issue.extra = _broken_link_extra(
                        target_url=target, sources=source_urls,
                        first_source=source_url, anchor_texts=anchor_texts,
                    )
                    issue.description = f"Link to {target} did not respond — destination may be slow or unavailable"
                    all_issues.append(issue)
                    _record(None)
                else:
                    issue = issue_for_status(result.status_code, target)
                    if issue:
                        issue.page_url = source_url
                        issue.extra = _broken_link_extra(
                            target_url=target, sources=source_urls,
                            first_source=source_url, anchor_texts=anchor_texts,
                        )
                        issue.description = f"Link to {target} returns {result.status_code}"
                        all_issues.append(issue)
                        _record(result.status_code)

        # ── 5.5 Image analysis (v1.9image) ─────────────────────────────────
        # Collect image metadata from HTML without fetching actual images
        # Full image data (dimensions, size) fetched on-demand via API
        all_images: list[ImageInfo] = []

        # E1.4 (rule 6): a cap on core input must announce what it drops.
        if len(image_targets_seen) > len(image_data_queue):
            log.warning(
                "image_cap_reached",
                extra={
                    "images_seen": len(image_targets_seen),
                    "images_queued": len(image_data_queue),
                    "cap": _IMAGE_URL_CAP_PER_JOB,
                },
            )

        print(f"[IMG] image_data_queue has {len(image_data_queue)} entries "
              f"(of {len(image_targets_seen)} distinct image URLs seen)")

        # IM1 — bound at function scope, not inside the image block: an empty
        # queue or a raised exception must still leave an honest zero rather
        # than a NameError at result construction (P13).
        images_measured = 0
        images_measurable = 0

        # SSRF: image URLs are taken from crawled HTML, so they are as
        # untrusted as the page that carried them. Both image passes go through
        # the guarded client, which refuses a private/internal target on the
        # initial request AND on every redirect hop (CLAUDE.md, Security
        # Defaults). The HEAD pass used the plain client and had the same gap;
        # a fix to one external call is a fix to the class (P5), so both move
        # together. The dimension pass makes it matter more: HEAD leaked little,
        # a GET pulls the full body back.
        img_client = make_ssrf_guarded_client()

        try:
            image_config = {
                "max_image_size_kb": settings.img_size_limit_kb,
            }

            # Filter valid images
            valid_img_data = [d for d in image_data_queue if d.get("url")]
            print(f"[IMG] valid_img_data has {len(valid_img_data)} entries")

            if valid_img_data:
                log.info("collecting_images", extra={"count": len(valid_img_data)})

                # ═══════════════════════════════════════════════════════════════════
                # CRITICAL ARCHITECTURAL PRINCIPLE - DO NOT VIOLATE
                # ═══════════════════════════════════════════════════════════════════
                #
                # The SCAN process must ONLY use data from:
                # 1. HTML parsing (alt, title from <img> tags) - ALREADY DONE in parser.py
                # 2. HTTP HEAD requests (file size, content-type) - FAST, just headers
                #
                # The SCAN must NEVER call WordPress API because:
                # - WP API calls are SLOW (100 images = 100+ API requests)
                # - WP API only works on WordPress sites (HTML works on ANY site)
                # - This would make crawls unacceptably slow
                #
                # WordPress-specific data (caption, description, WP alt text) is
                # fetched ONLY via the manual "Fetch" button using slug-based queries.
                #
                # ═══════════════════════════════════════════════════════════════════

                # Do HEAD requests to get file size and content-type for ALL images
                # This is fast (just HTTP headers) and works on any site
                head_metadata_cache: dict[str, dict] = {}
                if valid_img_data:
                    async def fetch_head_meta(img_url: str):
                        try:
                            response = await img_client.head(img_url, timeout=3.0,
                                                             follow_redirects=True)
                            if response.status_code == 200:
                                content_length = response.headers.get("content-length")
                                content_type = response.headers.get("content-type", "")
                                return (img_url, {
                                    "file_size": int(content_length) if content_length else None,
                                    "content_type": content_type,
                                })
                        except Exception:
                            pass
                        return (img_url, {})

                    try:
                        head_tasks = [fetch_head_meta(d["url"]) for d in valid_img_data]
                        if head_tasks:
                            head_results = await asyncio.wait_for(
                                asyncio.gather(*head_tasks, return_exceptions=True),
                                timeout=10.0
                            )
                            for item in head_results:
                                if isinstance(item, tuple) and item[1]:
                                    head_metadata_cache[item[0]] = item[1]
                            print(f"[IMG] Got HEAD metadata for {len(head_metadata_cache)} images")
                    except Exception as head_exc:
                        print(f"[IMG] HEAD metadata fetch failed: {head_exc}")

                # ── Dimension pass (IM1) ─────────────────────────────────
                # HEAD gives size and content-type but never pixel dimensions,
                # so four checks — IMG_NO_SRCSET, IMG_OVERSCALED,
                # IMG_DUPLICATE_CONTENT, IMG_SLOW_LOAD — had NO data and could
                # not fire in 156 jobs, and every image scored technical 0/None.
                #
                # Downloading everything is unnecessary: on livingsystems.ca 72
                # images total 6.0 MB, but only 4 exceed 200 KB. Only images at
                # or above the threshold are fetched, so the cost tracks the
                # images actually worth measuring.
                # Spec:  docs/functional-specification.md (IM1)#IM1
                # Tests: tests/test_image_dimensions.py
                dimension_cache: dict[str, dict] = {}
                measurable_total = len(valid_img_data)
                skipped_oversize = 0
                if valid_img_data:
                    # Walk in document order, charging each image's HEAD size
                    # against a total budget, and stop when it is spent. What
                    # falls off the end is counted and disclosed, never silent.
                    candidates: list[str] = []
                    budget_left = _IMAGE_DIMENSION_TOTAL_BYTES
                    skipped_budget = 0
                    for d in valid_img_data:
                        if len(candidates) >= _IMAGE_DIMENSION_MAX_COUNT:
                            skipped_budget += 1
                            continue
                        size = head_metadata_cache.get(d["url"], {}).get("file_size")
                        cost = size if size else _IMAGE_DIMENSION_UNKNOWN_SIZE
                        if size and size > _IMAGE_DIMENSION_MAX_BYTES:
                            skipped_oversize += 1
                            continue
                        if cost > budget_left:
                            # `continue`, not `break`: one large image early in
                            # document order must not end the pass for every
                            # smaller image after it, which would make coverage
                            # depend on page order.
                            skipped_budget += 1
                            continue
                        budget_left -= cost
                        candidates.append(d["url"])
                    if candidates:
                        sem = asyncio.Semaphore(_IMAGE_DIMENSION_CONCURRENCY)

                        async def _measure(u: str) -> tuple[str, dict]:
                            # Bounded: load_time_ms is scored by IMG_SLOW_LOAD,
                            # and an unbounded gather made it measure our own
                            # connection-pool queueing rather than the site.
                            async with sem:
                                return await _fetch_image_dimensions(u, img_client)

                        deadline = asyncio.get_running_loop().time() + _IMAGE_DIMENSION_BUDGET_S
                        tasks = [asyncio.create_task(_measure(u)) for u in candidates]
                        try:
                            for coro in asyncio.as_completed(tasks):
                                remaining = deadline - asyncio.get_running_loop().time()
                                if remaining <= 0:
                                    break
                                try:
                                    item = await asyncio.wait_for(coro, timeout=remaining)
                                except (asyncio.TimeoutError, Exception):
                                    continue
                                # Harvested as each finishes. A single wait_for
                                # around one gather cancelled everything on
                                # expiry, discarding every completed download
                                # and logging measured:0 — indistinguishable
                                # from "the site has no images".
                                if isinstance(item, tuple) and item[1]:
                                    dimension_cache[item[0]] = item[1]
                        finally:
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                    # Measured means Pillow read real pixels. A 404, a rejected
                    # content type or an SVG lands in the cache (its status and
                    # hash are still useful) but must not inflate coverage.
                    measured_now = sum(1 for v in dimension_cache.values() if "width" in v)
                    log.info("image_dimensions_measured", extra={
                        "measured": measured_now,
                        "attempted": len(candidates),
                        "measurable_total": measurable_total,
                        "skipped_oversize": skipped_oversize,
                        "skipped_budget": skipped_budget,
                    })
                images_measured = sum(1 for v in dimension_cache.values()
                                      if "width" in v)
                images_measurable = measurable_total

                for img_data in valid_img_data:
                    img_url = img_data["url"]
                    head_meta = head_metadata_cache.get(img_url, {})
                    dim_meta = dimension_cache.get(img_url, {})

                    # Size and content-type from HEAD; pixel dimensions and the
                    # content hash from the dimension pass above, when the image
                    # was large enough to be measured (IM1). None stays None —
                    # "not measured" must never render as a value.
                    width = dim_meta.get("width")
                    height = dim_meta.get("height")
                    file_size = head_meta.get("file_size")
                    mime_type = head_meta.get("content_type")
                    fmt = _guess_format_from_url(img_url)
                    if mime_type:
                        # Extract format from mime_type like "image/jpeg"
                        fmt = mime_type.split("/")[-1] if "/" in mime_type else fmt

                    # Data source is always "html_only" during scan
                    # Scan gets: alt/title from HTML + file size from HEAD request
                    # Full metadata (caption, description, WP fields) requires manual "Fetch"
                    data_source = "html_only"

                    image_info = ImageInfo(
                        url=img_url,
                        page_url=img_data.get("page_url", ""),
                        job_id=job_id,
                        alt=img_data.get("alt"),
                        title=img_data.get("title"),
                        filename=_extract_filename(img_url),
                        format=fmt,
                        width=width,
                        height=height,
                        rendered_width=img_data.get("rendered_width"),
                        rendered_height=img_data.get("rendered_height"),
                        # IM1: prefer the measured byte count when the image was
                        # downloaded — HEAD's content-length can be absent or wrong.
                        file_size_bytes=dim_meta.get("file_size_bytes", file_size),
                        load_time_ms=dim_meta.get("load_time_ms"),
                        http_status=dim_meta.get("http_status", 0),
                        is_lazy_loaded=img_data.get("is_lazy_loaded", False),
                        has_srcset=img_data.get("has_srcset", False),
                        srcset_candidates=img_data.get("srcset_candidates", []),
                        is_decorative=img_data.get("is_decorative", False),
                        # IM1: enables IMG_DUPLICATE_CONTENT; None when unmeasured.
                        content_hash=dim_meta.get("content_hash"),
                        surrounding_text=img_data.get("surrounding_text", ""),
                        data_source=data_source,
                    )
                    all_images.append(image_info)

            # Run batch analysis on HTML-level data (alt text checks work without fetch)
            if all_images:
                # Update phase to analyzing images
                if on_progress:
                    payload = {
                        "pages_crawled": len(all_pages),
                        "pages_total": pages_total,
                        "current_url": None,
                        "phase": "analyzing_images",
                        "external_links_checked": external_checked,
                        "external_links_total": external_total,
                    }
                    result_prog = on_progress(payload)
                    if inspect.isawaitable(result_prog):
                        await result_prog

                analyzed_images, image_issues = analyze_images(
                    all_images,
                    config=image_config,
                    job_id=job_id,
                )
                all_images = analyzed_images
                all_issues.extend(image_issues)

                log.info("images_analyzed", extra={
                    "total": len(all_images),
                    "issues_found": len(image_issues),
                })

        except Exception as img_exc:
            print(f"[IMG] Exception during image analysis: {img_exc}")
            log.exception("image_analysis_failed", extra={"error": str(img_exc)})
            all_images = []  # Continue crawl without images
        finally:
            # The guarded client is a connection pool, not a value: hiding it
            # from view is not releasing it (P30). Closed on every exit from
            # the image block, including the exception path above.
            await img_client.aclose()

        print(f"[IMG] Final all_images count: {len(all_images)}")

        # ── 6. AMP HTML link checking ────────────────────────────────────
        amp_statuses: dict[str, int] = {}
        seen_amp_urls: set[str] = set()
        for p in all_pages:
            if p.amphtml_url and p.amphtml_url not in seen_amp_urls:
                seen_amp_urls.add(p.amphtml_url)
                try:
                    amp_result = await _check_external_link(p.amphtml_url, client)
                    if amp_result is not None:
                        amp_statuses[p.amphtml_url] = amp_result.status_code
                except Exception:
                    pass
        amp_issues = check_amphtml_links(all_pages, amp_statuses)
        all_issues.extend(amp_issues)

        # ── 6-0. Sitemap coverage (AF10) ─────────────────────────────────
        # The sitemap is the site's own declaration of what exists. Comparing it
        # against what we actually fetched is the only way a reader can tell
        # "checked and clean" from "never looked" for a declared URL.
        _crawled_norm = set()
        for _pg in all_pages:
            try:
                _crawled_norm.add(normalise_url(_pg.url))
            except Exception:
                continue
        _missed = sorted(sitemap_url_set - _crawled_norm)
        sitemap_coverage = {
            "declared": len(sitemap_url_set),
            "crawled": len(sitemap_url_set & _crawled_norm),
            "not_crawled": len(_missed),
            # Why each declared URL went unfetched, so the gap is actionable
            # rather than a bare number.
            "reasons": {u: skip_reasons.get(u, "not_reached") for u in _missed[:50]},
        }
        if _missed:
            log.info("sitemap_urls_not_crawled",
                     extra={"count": len(_missed), "declared": len(sitemap_url_set)})

        # ── 6a. Self-inflicted trailing-slash redirects (AF2) ────────────
        # `normalise_url` strips a trailing slash, so we FETCH `/x` on a site
        # whose canonical form is `/x/`. The server 301s back, and we reported
        # that redirect as a defect: 147 of 147 findings on livingsystems.ca
        # differed only by the slash, 3,590 lifetime — every one an artifact of
        # our own request, invisible to a visitor because the site's sitemap and
        # every internal link already use the destination form.
        #
        # A genuine finding still exists: if some page really does link to the
        # pre-redirect form, the inconsistency is the site's. `ParsedLink.url`
        # keeps the ORIGINAL href, so that is decidable.
        # Spec:  docs/pending/2026-08-30_audit-fixes.md#AF2
        # Tests: tests/test_redirect_trailing_slash.py
        _raw_internal_hrefs = {
            (l.url or "").split("#")[0].split("?")[0]
            for pg in all_pages for l in (pg.links or []) if l.is_internal
        }
        _before = len(all_issues)
        all_issues = [
            i for i in all_issues
            if not (i.code == "REDIRECT_TRAILING_SLASH"
                    and _is_self_inflicted_slash_redirect(i, _raw_internal_hrefs))
        ]
        if len(all_issues) != _before:
            log.info("self_inflicted_slash_redirects_suppressed",
                     extra={"suppressed": _before - len(all_issues)})

        # ── 6b. Click depth (AF4) ────────────────────────────────────────
        # Recompute depth over the link graph the crawl actually observed.
        # The in-crawl depth_map is order-dependent: sitemap seeding enqueues
        # every URL with depth None before any link is followed, so on a site
        # with a sitemap most pages kept `None` and HIGH_CRAWL_DEPTH could not
        # fire (0 hits in 156 jobs; 255 of 256 pages NULL on livingsystems.ca).
        # A BFS over the finished graph is deterministic and gives the true
        # shortest click distance from the homepage.
        # Spec:  docs/pending/2026-08-30_audit-fixes.md#AF4
        # Tests: tests/test_crawl_depth.py
        _compute_click_depths(all_pages, normalised_start)
        # The per-page check ran during the crawl, when most depths were still
        # unknown, so emit for pages the post-crawl pass has now placed. Guarded
        # against duplicates for pages whose depth WAS known at check time.
        _already = {i.page_url for i in all_issues if i.code == "HIGH_CRAWL_DEPTH"}
        for _p in all_pages:
            if (_p.crawl_depth is not None and _p.crawl_depth > _MAX_CLICK_DEPTH
                    and _p.url not in _already):
                all_issues.append(make_issue("HIGH_CRAWL_DEPTH", _p.url,
                                             extra={"crawl_depth": _p.crawl_depth}))
                _already.add(_p.url)

        # ── 7. Cross-page duplicate checks (HTML pages only) ─────────────
        # O1 — ORPHAN_PAGE reasons about the ABSENCE of an inbound link, which
        # is only decidable over the whole site. Three things narrow the crawl
        # legitimately and would otherwise turn "not fetched" into "not linked"
        # (P31): single-page mode, a content-type partial scan, and the
        # max_pages budget. Cancellation returns earlier and never reaches this
        # line; a crawl that raised is recorded by the router's failure path.
        html_pages = [p for p in all_pages if p.title is not None or p.meta_description is not None or p.h1_tags]
        if settings.single_page:
            # No sitemap seeding and no link following: one page, no graph.
            orphan_status = "skipped_single_page"
        elif scope_urls is not None:
            orphan_status = "skipped_partial_scan"
        elif truncated_by_max_pages:
            orphan_status = "skipped_truncated"
        else:
            orphan_status = ORPHAN_STATUS_COMPLETE
        orphan_detection = {
            "status": orphan_status,
            # The population the check actually reasons over — html_pages below,
            # not every fetched byte. Reporting len(all_pages) would overstate
            # coverage by counting PDFs and images as analysed pages.
            "pages_analysed": len(html_pages),
            # Out-of-scope URLs on a partial scan; on a truncation, what was
            # still queued when the budget ran out. Either way a real shortfall,
            # never a silent 0 (P9 — announce what was dropped).
            "pages_out_of_scope": len(scope_skipped_urls) + unfetched_at_truncation,
            # skip_wp_archives (default ON) drops WordPress archives before their
            # outbound links are read, so even a "complete" crawl has not seen
            # every anchor on the site. Disclosed rather than gated: gating on a
            # default-on setting would disable the check on every crawl.
            "archives_skipped": bool(settings.skip_wp_archives),
            # Pages reached but unreadable (timeout, SSRF block, login wall,
            # parse failure). Measured on livingsystems.ca: 5 of 256 on a real
            # full crawl. Each is a hole in the graph, so a "complete" status
            # with a non-zero count here still carries a caveat.
            "pages_links_unread": pages_links_unread,
        }
        if orphan_status != ORPHAN_STATUS_COMPLETE:
            log.info("orphan_detection_skipped", extra=orphan_detection)

        cross_issues = check_cross_page(
            html_pages, start_url=normalised_start,
            link_graph_complete=(orphan_status == ORPHAN_STATUS_COMPLETE),
            # Links come from EVERY crawled page. A page with no title/meta/h1
            # fails the html_pages filter but still carries real anchors, and
            # dropping it from the graph invents orphans on a complete crawl.
            link_source_pages=all_pages)
        all_issues.extend(cross_issues)

        # ── 7b. Citation source accessibility (R6) ───────────────────────
        # Collect the pages' cited external-source URLs and HEAD-check them
        # (reuses fetch_page retry+SSRF via check_source_accessibility, capped),
        # then flag pages whose sources are broken/blocked.
        try:
            from api.crawler.issue_checker import build_page_citations, citation_source_issues
            from api.services.citation_model import check_source_accessibility
            cite_urls: set[str] = set()
            for p in html_pages:
                if getattr(p, "is_indexable", True) and (p.word_count or 0) > 200:
                    cite_urls |= {c.url for c in build_page_citations(p).citations if c.url}
            if cite_urls:
                inaccessible = await check_source_accessibility(cite_urls, client)
                all_issues.extend(citation_source_issues(html_pages, inaccessible))
        except Exception as e:
            log.warning("citation_accessibility_error", extra={"error": str(e)})

        # ── 7c. JS-render / cloaking checks (R7, Playwright-gated) ───────
        # run_js_render_checks renders each page with Playwright and compares
        # raw vs rendered vs AI-user-agent content. Expensive → gated on
        # Playwright availability + ai_readiness enablement, capped per job.
        # Degrades to a no-op (emits nothing) when Playwright is absent.
        try:
            from api.services.js_renderer import HAS_PLAYWRIGHT, run_js_render_checks
            from api.crawler.issue_checker import js_render_issues
            _render_cats = _enabled_categories(settings.enabled_analyses)
            _render_on = _render_cats is None or "ai_readiness" in _render_cats
            if HAS_PLAYWRIGHT and _render_on:
                _JS_RENDER_CAP = 10
                for p in [pg for pg in html_pages if getattr(pg, "is_indexable", True)][:_JS_RENDER_CAP]:
                    try:
                        render_result = await run_js_render_checks(p.url)
                        all_issues.extend(js_render_issues(render_result))
                    except Exception:
                        continue  # one page's render failure must not abort the crawl
        except Exception as e:
            log.warning("js_render_error", extra={"error": str(e)})

        # ── 7.9 §2 per-target counting: collapse broken-link / redirect rows
        # to one per (page, code) with an occurrence multiplier baked into
        # impact, before the category filter and save.
        all_issues = collapse_per_target_occurrences(all_issues)

        # ── 8. Apply analysis-toggle category filter ──────────────────────
        allowed = _enabled_categories(settings.enabled_analyses)
        if allowed is not None:
            all_issues = [i for i in all_issues if i.category in allowed]

        log.info(
            "crawl_complete",
            extra={
                "pages_crawled": len(all_pages),
                "issues_found": len(all_issues),
                "external_links_checked": external_checked,
            },
        )

        # Update phase to complete
        if on_progress:
            payload = {
                "pages_crawled": len(all_pages),
                "pages_total": pages_total,
                "current_url": None,
                "phase": "complete",
                "external_links_checked": external_checked,
                "external_links_total": external_total,
            }
            result_prog = on_progress(payload)
            if inspect.isawaitable(result_prog):
                await result_prog

        if scope_urls is not None:
            log.info(
                "content_scope_applied",
                extra={
                    "in_scope": len(scope_urls),
                    "skipped_out_of_scope": len(scope_skipped_urls),
                },
            )

        return CrawlResult(
            job_id=job_id,
            pages=all_pages,
            issues=all_issues,
            pages_crawled=len(all_pages),
            external_links_checked=external_checked,
            broken_link_sources=broken_link_sources,
            images=all_images,
            robots_txt_found=_robots_found,
            robots_txt_rules=_robots_rules,
            sitemap_found=_sitemap_found,
            sitemap_url_found=_sitemap_url_found,
            sitemap_url_count=_sitemap_url_count,
            scope_skipped=len(scope_skipped_urls),
            orphan_detection=orphan_detection,
            sitemap_coverage=sitemap_coverage,
            analysis_coverage=_build_analysis_coverage(settings),
            images_seen_total=len(image_targets_seen),
            images_collected=len(all_images),
            images_measured=images_measured,
            images_measurable=images_measurable,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_image_dimensions(url: str, client) -> tuple[str, dict]:
    """Download one image and measure it.

    Purpose: HEAD cannot report pixel dimensions, and five image checks plus the
             technical score depend on them (IM1).
    Spec:    docs/functional-specification.md (IM1)#IM1
    Tests:   tests/test_image_dimensions.py

    Always returns ``http_status`` when the server answered, so a 404 image is
    distinguishable from one that was never fetched — the caller stores it and
    IMG_BROKEN can fire from the scan path.

    ``width``/``height`` appear ONLY when Pillow decoded real image bytes. The
    caller counts a measurement by the presence of ``width``, not by a non-empty
    dict, so a partial result never inflates the coverage figure.

    The body is streamed and abandoned past ``_IMAGE_DIMENSION_MAX_BYTES``. The
    byte budget upstream is computed from the HEAD ``content-length``, which the
    remote host supplies and may understate or omit — so the only real ceiling
    is the one enforced here, while reading.
    """
    import hashlib
    import io
    import time

    started = time.time()
    try:
        async with client.stream("GET", url,
                                 timeout=_IMAGE_DIMENSION_TIMEOUT_S) as response:
            status = response.status_code
            if status >= 400:
                return url, {"http_status": status}
            content_type = (response.headers.get("content-type") or "").lower()
            if not content_type.startswith("image/"):
                # A soft-404 HTML page served for a missing image would
                # otherwise be hashed and sized as though it were the image:
                # ten broken <img> tags returning the same error page hash
                # identically and fabricate IMG_DUPLICATE_CONTENT on nine.
                return url, {"http_status": status,
                             "rejected_content_type": content_type[:80]}
            buf = bytearray()
            async for chunk in response.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > _IMAGE_DIMENSION_MAX_BYTES:
                    return url, {"http_status": status, "oversize_abandoned": True}
            content = bytes(buf)

        out: dict = {
            "file_size_bytes": len(content),
            "content_hash": hashlib.md5(content).hexdigest(),
            "load_time_ms": int((time.time() - started) * 1000),
            "http_status": status,
        }
        try:
            from PIL import Image
            # Only im.size is read (a header parse, not a raster decode), but
            # the ceiling is set explicitly rather than left to whatever the
            # installed Pillow defaults to — this runs on every crawl now, on
            # bytes from an arbitrary host.
            if Image.MAX_IMAGE_PIXELS is None or Image.MAX_IMAGE_PIXELS > 80_000_000:
                Image.MAX_IMAGE_PIXELS = 80_000_000
            with Image.open(io.BytesIO(content)) as im:
                out["width"], out["height"] = im.size
                if im.format:
                    out["format"] = im.format.lower()
        except Exception:
            # SVGs and anything Pillow cannot decode keep size and hash but no
            # dimensions — a partial measurement, honestly partial, and not
            # counted as measured.
            pass
        return url, out
    except Exception:
        return url, {}


def _is_self_inflicted_slash_redirect(issue, raw_internal_hrefs: set[str]) -> bool:
    """True when a trailing-slash redirect exists only because WE stripped the slash.

    Purpose: stop reporting a redirect no visitor can reach.
    Spec:    docs/pending/2026-08-30_audit-fixes.md#AF2
    Tests:   tests/test_redirect_trailing_slash.py

    The redirect is the site's problem only if some page actually links to the
    pre-redirect form. Compared against the ORIGINAL hrefs, not normalised ones —
    normalising both sides would make every case look identical, which is the
    bug itself.
    """
    extra = issue.extra or {}
    src, dst = extra.get("from") or issue.page_url or "", extra.get("to") or ""
    if not src or not dst:
        return False
    if src.rstrip("/") != dst.rstrip("/") or src == dst:
        return False  # not a slash-only difference
    # Did any page link to the exact pre-redirect form?
    return src not in raw_internal_hrefs and src.rstrip("/") not in raw_internal_hrefs


def _build_analysis_coverage(settings: "CrawlSettings") -> dict:
    """Record which analysis groups ran, and which categories they cover.

    Purpose: a scan with categories switched off renders exactly like a thorough
             scan of a healthy site — same layout, fewer findings. Two full
             crawls of one site 49 minutes apart read 1 warning and 118 because
             the first ran only `link_integrity`, and nothing on any surface said
             so (P31: an absent finding read as a passing one).
    Spec:    docs/pending/2026-08-30_analysis-coverage-disclosure.md#C1
    Tests:   tests/test_analysis_coverage.py
    """
    all_groups = sorted(_ANALYSIS_CATEGORY_MAP)
    enabled = settings.enabled_analyses
    if enabled is None:
        groups_enabled, groups_disabled = all_groups, []
    else:
        chosen = {g for g in enabled if g in _ANALYSIS_CATEGORY_MAP}
        groups_enabled = sorted(chosen)
        groups_disabled = sorted(set(all_groups) - chosen)

    checked: set[str] = set(_UNGROUPED_CATEGORIES)  # security always runs
    for g in groups_enabled:
        checked |= _ANALYSIS_CATEGORY_MAP[g]
    every: set[str] = set(_UNGROUPED_CATEGORIES)
    for cats in _ANALYSIS_CATEGORY_MAP.values():
        every |= cats

    return {
        "mode": "all" if enabled is None else "partial",
        "groups_enabled": groups_enabled,
        "groups_disabled": groups_disabled,
        "categories_checked": sorted(checked),
        "categories_unchecked": sorted(every - checked),
    }


def _compute_click_depths(pages: list[ParsedPage], start_url: str | None) -> None:
    """Assign ``crawl_depth`` = shortest click distance from the start URL.

    Purpose: give every crawled page a real click depth, independent of the
             order the crawler happened to visit them in.
    Spec:    docs/pending/2026-08-30_audit-fixes.md#AF4
    Tests:   tests/test_crawl_depth.py

    A page not reachable by any observed internal link keeps ``crawl_depth =
    None`` — "unknown", not "deep". Callers must keep treating None as unknown
    (``HIGH_CRAWL_DEPTH`` already does).
    """
    if not pages or not start_url:
        return

    by_norm: dict[str, ParsedPage] = {}
    edges: dict[str, set[str]] = {}
    for page in pages:
        try:
            norm = normalise_url(page.url)
        except Exception:
            continue
        by_norm.setdefault(norm, page)
        targets = edges.setdefault(norm, set())
        for link in page.links or []:
            if not link.is_internal:
                continue
            try:
                targets.add(normalise_url(link.url))
            except Exception:
                continue

    if start_url not in by_norm:
        return

    depths: dict[str, int] = {start_url: 0}
    frontier = [start_url]
    while frontier:
        nxt: list[str] = []
        for node in frontier:
            for target in edges.get(node, ()):  # unvisited neighbours only
                if target not in depths and target in by_norm:
                    depths[target] = depths[node] + 1
                    nxt.append(target)
        frontier = nxt

    for norm, page in by_norm.items():
        page.crawl_depth = depths.get(norm)


def _is_bot_blocking_domain(url: str) -> bool:
    """Return True if *url* belongs to a domain known to block automated requests."""
    host = urlparse(url).hostname or ""
    return host in _BOT_BLOCKING_DOMAINS


async def _check_external_link(
    url: str, client: httpx.AsyncClient
) -> FetchResult | None:
    """Issue a HEAD request for *url*, falling back to GET on 405."""
    result = await fetch_page(url, client, is_head=True)
    if result.status_code == 405:
        result = await fetch_page(url, client, is_head=False)
    return result


async def _fetch_image_full(
    url: str,
    client: httpx.AsyncClient,
    timeout: float = 3.0,
    max_size: int = 5 * 1024 * 1024,  # 5MB
) -> dict:
    """Fetch full image data including bytes for dimension extraction.

    Returns a dict with:
    - http_status: int
    - file_size_bytes: int|None
    - load_time_ms: int|None
    - width: int|None (intrinsic)
    - height: int|None (intrinsic)
    - format: str
    - content_hash: str|None (MD5)
    - error: str|None
    """
    import hashlib
    import time

    start_time = time.time()
    result = {
        "url": url,
        "http_status": 0,
        "file_size_bytes": None,
        "load_time_ms": None,
        "width": None,
        "height": None,
        "format": "unknown",
        "content_hash": None,
        "error": None,
    }

    try:
        response = await client.get(url, timeout=timeout)
        result["http_status"] = response.status_code
        result["load_time_ms"] = int((time.time() - start_time) * 1000)

        if response.status_code < 400:
            content = response.content
            result["file_size_bytes"] = len(content)

            # Hash for duplicate detection
            result["content_hash"] = hashlib.md5(content).hexdigest()

            # Extract dimensions using Pillow
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(content))
                result["width"], result["height"] = img.size
                result["format"] = img.format.lower() if img.format else "unknown"
            except Exception:
                pass

    except Exception as e:
        result["error"] = str(e)
        result["load_time_ms"] = int((time.time() - start_time) * 1000)

    return result


def _extract_filename(url: str) -> str:
    """Extract filename from URL path."""
    try:
        path = urlparse(url).path
        if path:
            return path.rstrip("/").rsplit("/", 1)[-1]
    except Exception:
        pass
    return ""


def _guess_format_from_url(url: str) -> str:
    """Guess image format from URL extension."""
    try:
        path = urlparse(url).path.lower()
        if path.endswith(".webp"):
            return "webp"
        elif path.endswith(".avif"):
            return "avif"
        elif path.endswith((".jpg", ".jpeg")):
            return "jpeg"
        elif path.endswith(".png"):
            return "png"
        elif path.endswith(".gif"):
            return "gif"
        elif path.endswith(".svg"):
            return "svg"
        elif path.endswith(".ico"):
            return "ico"
    except Exception:
        pass
    return "unknown"


async def _get_wp_image_metadata(
    image_url: str,
    client: httpx.AsyncClient,
    wp_api_base: str | None = None,
) -> dict | None:
    """Try to get image metadata from WordPress REST API.

    Returns dict with width, height, filesize, mime_type if found, else None.
    """
    if not wp_api_base:
        # Derive from image URL - assume /wp-content/uploads/ pattern
        parsed = urlparse(image_url)
        if "/wp-content/uploads/" not in parsed.path:
            return None
        wp_api_base = f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2"

    # Extract filename from URL for search
    filename = image_url.rsplit("/", 1)[-1] if "/" in image_url else ""
    if not filename:
        return None

    # Remove size suffix like -300x200 before extension
    import re
    base_filename = re.sub(r'-\d+x\d+(\.[a-z]+)$', r'\1', filename, flags=re.IGNORECASE)
    search_term = base_filename.rsplit(".", 1)[0] if "." in base_filename else base_filename

    try:
        # Search WordPress media library
        search_url = f"{wp_api_base}/media?search={search_term}&per_page=5"
        response = await client.get(search_url, timeout=5.0)

        if response.status_code != 200:
            return None

        media_items = response.json()
        if not media_items or not isinstance(media_items, list):
            return None

        # Find matching image by URL
        for item in media_items:
            source_url = item.get("source_url", "")
            # Check if this is our image (match base filename)
            if base_filename in source_url or filename in source_url:
                details = item.get("media_details", {})
                return {
                    "width": details.get("width"),
                    "height": details.get("height"),
                    "filesize": details.get("filesize"),
                    "mime_type": item.get("mime_type"),
                    "alt_text": item.get("alt_text"),
                    "wp_id": item.get("id"),
                }

        # If no exact match, return first result if filename is similar
        if media_items:
            item = media_items[0]
            details = item.get("media_details", {})
            return {
                "width": details.get("width"),
                "height": details.get("height"),
                "filesize": details.get("filesize"),
                "mime_type": item.get("mime_type"),
                "alt_text": item.get("alt_text"),
                "wp_id": item.get("id"),
            }

    except Exception:
        pass

    return None


def _effective_delay(base_delay_s: float, robots_data: RobotsData | None) -> float:
    """Return the effective crawl delay, respecting robots.txt and the minimum."""
    min_s = _MIN_CRAWL_DELAY_MS / 1000.0
    if robots_data and robots_data.crawl_delay is not None:
        return max(min_s, robots_data.crawl_delay, base_delay_s)
    return max(min_s, base_delay_s)



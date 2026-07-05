"""AI-readiness / GEO static checks: run_geo_checks plus all helper regexes
and counters used by the v2.1 GEO analyzer.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function bodies and regex strings are byte-identical to
the originals.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue

logger = logging.getLogger(__name__)

# FAQ_ANSWERS_NOT_IN_HTML: a FAQ answer with fewer than this many characters of
# text present in the RAW HTML is treated as absent (JS-injected on click).
# See docs/thresholds.md.
_FAQ_ANSWER_MIN_CHARS = 40


def _run_geo_checks(page: "ParsedPage", url: str, issues: list) -> None:
    """Run all v2.1 GEO Analyzer static checks (called from check_page)."""
    if not page.is_indexable or url.endswith(".pdf"):
        return

    word_count = page.word_count or 0
    schema_types = page.schema_types or []
    headings = page.headings_outline or []
    links = page.links or []

    # ── SPA shell check (GEO.1.3a) ──────────────────────────────────────────
    if page.is_spa_shell and (page.text_to_html_ratio or 0) < 0.05:
        issues.append(make_issue("RAW_HTML_JS_DEPENDENT", url, extra={
            "text_to_html_ratio": round(page.text_to_html_ratio or 0, 4),
        }))

    # ── Aggarwal et al. checks — only on 500+ word pages ────────────────────
    if word_count >= 500:
        # GEO.A.1: Statistics count
        # v2.3 Cycle E: extended scope from first_200_words to first_600_words
        # per docs-review §2 STATISTICS_COUNT_LOW recommendation. The 200-word
        # window missed statistics that appear later in the introduction; the
        # 600-word scope covers a typical article's first 2-3 paragraphs.
        stat_count = _count_statistics(page.first_1500_words or page.first_600_words or page.first_200_words or "", links, page)
        if stat_count == 0:
            issues.append(make_issue("STATISTICS_COUNT_LOW", url, extra={
                "word_count": word_count,
                "statistics_found": 0,
            }))

        # GEO.A.2: External citations in body text
        ext_links = _count_external_body_links(links, url)
        if ext_links == 0:
            issues.append(make_issue("EXTERNAL_CITATIONS_LOW", url, extra={
                "word_count": word_count,
                "external_links": 0,
            }))

        # GEO.A.3: Quotations (blockquotes or attribution patterns)
        q_count = (page.blockquote_count or 0) + _count_inline_quotations(page)
        if q_count == 0:
            issues.append(make_issue("QUOTATIONS_MISSING", url, extra={
                "word_count": word_count,
                "quotations_found": 0,
            }))

    # GEO.A.4: Orphan claims on technical pages
    is_technical = (
        any(t in schema_types for t in ("TechArticle", "HowTo"))
        or any(seg in url for seg in ("/how-to/", "/guide/", "/tutorial/", "/setup/"))
    )
    if is_technical and word_count >= 300:
        orphan_count = _count_orphan_claims(page, links, url)
        if orphan_count >= 3:
            issues.append(make_issue("ORPHAN_CLAIM_TECHNICAL", url, extra={
                "orphan_claim_count": orphan_count,
            }))

    # ── GEO.2.3: First-viewport answer signal (spec §4.2) ───────────────────
    if word_count >= 200 and page.first_200_words:
        if not _has_answer_signal(page.first_200_words):
            issues.append(make_issue("FIRST_VIEWPORT_NO_ANSWER", url, extra={
                "first_200_words": page.first_200_words[:200],
            }))

    # ── Tier 1 §4.3: Query coverage ─────────────────────────────────────────
    if word_count >= 200 and getattr(page, "query_coverage_weak", False):
        issues.append(make_issue("QUERY_COVERAGE_WEAK", url, extra={
            "h1": (page.h1_tags or [""])[0][:120],
        }))

    # ── Tier 1 §4.4: Vague section openers ──────────────────────────────────
    vague = getattr(page, "vague_opener_count", 0)
    if vague > 0:
        issues.append(make_issue("SECTION_VAGUE_OPENER", url, extra={
            "vague_opener_count": vague,
        }))

    # ── Tier 1 §4.5: Backward cross-references ──────────────────────────────
    xrefs = getattr(page, "cross_reference_count", 0)
    if xrefs > 0:
        issues.append(make_issue("SECTION_CROSS_REFERENCES", url, extra={
            "cross_reference_count": xrefs,
        }))

    # ── GEO.4.2: Author byline on blog/article pages ────────────────────────
    is_article = (
        any(t in schema_types for t in ("BlogPosting", "Article", "NewsArticle"))
        or any(seg in url for seg in ("/blog/", "/post/", "/article/", "/news/", "/stories/"))
    )
    if is_article and not page.author_detected:
        issues.append(make_issue("AUTHOR_BYLINE_MISSING", url))

    # ── GEO.4.3: Date signals on blog/article pages ─────────────────────────
    if is_article:
        if not page.date_published:
            issues.append(make_issue("DATE_PUBLISHED_MISSING", url))
        if not page.date_modified:
            issues.append(make_issue("DATE_MODIFIED_MISSING", url))

    # ── GEO.8.1: Code blocks on technical pages ──────────────────────────────
    if is_technical and word_count >= 200:
        # Check for numbered list of steps
        has_numbered_steps = _has_numbered_steps(headings, page)
        if has_numbered_steps and (page.code_block_count or 0) == 0:
            issues.append(make_issue("CODE_BLOCK_MISSING_TECHNICAL", url, extra={
                "code_blocks_found": 0,
            }))

    # ── GEO.8.2: Comparison table ────────────────────────────────────────────
    _COMPARISON_RE = re.compile(
        r"\b(vs\.?|versus|compared to|difference between|comparison of)\b", re.I
    )
    heading_texts = " ".join(h.get("text", "") for h in headings)
    if _COMPARISON_RE.search(heading_texts) and (page.table_count or 0) == 0:
        issues.append(make_issue("COMPARISON_TABLE_MISSING", url, extra={
            "comparison_signal": True, "tables_found": 0,
        }))

    # ── GEO.8.3: All-internal link profile ──────────────────────────────────
    if links and word_count >= 300:
        try:
            from api.services.link_classifier import classify_body_links
            counts = classify_body_links(links, url)
            external_total = counts.get("external_body_total", 0)
            promo = counts.get("promotional", 0)
            other = counts.get("other", 0)
            if external_total > 0:
                promo_ratio = promo / external_total
                if promo_ratio > 0.8:
                    issues.append(make_issue("LINK_PROFILE_PROMOTIONAL", url, extra={
                        "promotional": promo,
                        "external_total": external_total,
                        "promotional_ratio": round(promo_ratio, 2),
                    }))
        except Exception as e:
            logger.warning("link_classifier_error", extra={"url": url, "error": str(e)})

    # ── GEO.5.1: Invalid JSON-LD ────────────────────────────────────────────
    if page.schema_blocks:
        # Defensive: JSON-LD allows the root element to be an array of
        # objects (the @graph pattern), and some parsers surface that as
        # a list inside schema_blocks. Calling .get() on a list raises
        # AttributeError and kills the crawl. Flatten one level so a
        # list-block contributes its inner dicts; drop any non-dict
        # remnants entirely.
        flat_blocks: list[dict] = []
        for b in page.schema_blocks:
            if isinstance(b, dict):
                flat_blocks.append(b)
            elif isinstance(b, list):
                for inner in b:
                    if isinstance(inner, dict):
                        flat_blocks.append(inner)
            # else: malformed entry — drop
        # A JSON-LD node is invalid only if it lacks @type. Do NOT require
        # @context per node: in the @graph pattern (Yoast/RankMath/most WP SEO
        # plugins) @context lives once on the ROOT and the @graph children
        # inherit it — requiring it on every flattened child false-positived on
        # essentially every WordPress site (audit accuracy fix 2026-07-04).
        invalid = [b for b in flat_blocks if not b.get("@type")]
        if invalid:
            issues.append(make_issue("JSON_LD_INVALID", url, extra={
                "invalid_count": len(invalid),
            }))

    # ── GEO.5.2: FAQ section without FAQPage schema ─────────────────────────
    # Questions are detected accordion-aware at parse time (page.faq_blocks) so
    # Elementor/Gutenberg <details>/accordion FAQs are counted, not just <h?>
    # questions. Fixes the silent false-negative where an accordion FAQ with no
    # literal "FAQ" heading was missed (audit 2026-07-04).
    _FAQ_RE = re.compile(r"\bfrequently\s+asked\s+questions?\b|\bfaq\b", re.I)
    faq_blocks = page.faq_blocks or []
    if "FAQPage" not in schema_types:
        has_faq_heading = any(_FAQ_RE.search(h.get("text", "")) for h in headings)
        question_count = len(faq_blocks)
        sources: dict[str, int] = {}
        for b in faq_blocks:
            c = b.get("container", "other")
            sources[c] = sources.get(c, 0) + 1
        if has_faq_heading or question_count >= 3:
            issues.append(make_issue("FAQ_SCHEMA_MISSING", url, extra={
                "faq_heading": has_faq_heading,
                "question_count": question_count,
                "sources": sources,
            }))

    # ── FAQ answers absent from raw HTML (JS-hydrated → invisible to AI) ─────
    # The crawler reads raw HTML with no JS, exactly as a non-rendering AI crawler
    # does. If FAQ question titles are present but their answer bodies are not,
    # the answers are injected on click and no AI/search bot can read them.
    if faq_blocks:
        missing = [b for b in faq_blocks
                   if b.get("answer_char_count", 0) < _FAQ_ANSWER_MIN_CHARS]
        total = len(faq_blocks)
        # Require a systematic pattern (>=2 and >=half) so a single genuinely
        # terse answer doesn't false-positive; N-of-M announced in extra.
        if len(missing) >= 2 and len(missing) >= 0.5 * total:
            issues.append(make_issue("FAQ_ANSWERS_NOT_IN_HTML", url, extra={
                "affected": len(missing),
                "total": total,
                "examples": [b["question"] for b in missing[:3]],
            }))

    # ── GEO.2.2: Structured elements count (metric only — no pass/fail) ─────
    # Emitting as info when count is low relative to word count
    if word_count >= 500 and (page.structured_element_count or 0) == 0:
        issues.append(make_issue("STRUCTURED_ELEMENTS_LOW", url, extra={
            "structured_element_count": 0,
            "word_count": word_count,
        }))


# ---------------------------------------------------------------------------
# GEO check helpers
# ---------------------------------------------------------------------------

_STAT_RE = re.compile(
    # number (possibly comma-formatted) followed by a unit or % — no trailing \b so % works
    r"\b\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|percent|kb|mb|gb|tb|ms|seconds?|minutes?|hours?|days?|months?|years?"
    r"|users?|customers?|companies|organisations?|organizations?"
    r"|times?\s+faster|times?\s+more|\dx?\s+faster|\dx?\s+more"
    r"|Gbps|Mbps|fps|rpm|mph|km|mi|kg|lbs?"
    r"|million|billion|trillion|thousand|hundred)(?:\b|(?=\s|$))"
    r"|\b(?:19|20)\d{2}\b"                 # year references: 2023, 1999, etc.
    r"|\b\d+\s+(?:of|out\s+of)\s+\d+\b",  # "3 out of 5"
    re.I,
)


def _count_statistics(first_words: str, links: list, page: "ParsedPage") -> int:
    """Count statistic-bearing sentences on the page using the full visible text."""
    # Cap heading contribution to first 10 headings to prevent inflation on
    # pages with many headings that contain no statistics in their body text.
    # Defensive: `.get("text", "")` returns None when the key is present
    # with an explicit None value (parser artifact for malformed headings).
    # `" ".join([..., None, ...])` raises TypeError and crashes the crawl.
    # The `or ""` coalesces both "missing key" and "key with None value".
    all_text_sources = [first_words or ""]
    for h in (page.headings_outline or [])[:10]:
        all_text_sources.append(h.get("text") or "")
    combined = " ".join(all_text_sources)
    return len(_STAT_RE.findall(combined))


def _count_external_body_links(links: list, page_url: str) -> int:
    """Count outbound links to external domains (not navigation/footer heuristic)."""
    from urllib.parse import urlparse
    page_netloc = urlparse(page_url).netloc.lstrip("www.")
    count = 0
    for link in links:
        # Strip whitespace before scheme check and before parsing.
        # Parsers sometimes preserve leading whitespace from href
        # attributes ("  https://x.com", "\nhttp://y.com");
        # startswith("http") returns False on the raw form, silently
        # dropping valid external citations.
        href = (getattr(link, "url", "") or "").strip()
        if not href.startswith("http"):
            continue
        netloc = urlparse(href).netloc.lstrip("www.")
        if netloc and netloc != page_netloc:
            count += 1
    return count


_ATTRIBUTION_RE = re.compile(
    r'(?:according\s+to|says?|said|stated|noted|wrote|reports?|"[^"]{10,200}"\s*—)',
    re.I,
)


def _count_inline_quotations(page: "ParsedPage") -> int:
    """Count attribution patterns in first_600_words as proxy for inline quotes."""
    text = getattr(page, "first_1500_words", None) or getattr(page, "first_600_words", None) or page.first_200_words or ""
    return len(_ATTRIBUTION_RE.findall(text))


_CLAIM_RE = re.compile(
    r"\b(?:supports?|enables?|allows?|provides?|reduces?|increases?|improves?|"
    r"processes?|handles?|scales?|integrates?)\b[^.!?]{5,120}[.!?]",
    re.I,
)


def _count_orphan_claims(page: "ParsedPage", links: list, url: str) -> int:
    """Count technical claims in first_200_words not paired with a source link."""
    text = page.first_200_words or ""
    claims = _CLAIM_RE.findall(text)
    ext_links = _count_external_body_links(links, url)
    if ext_links > 0:
        return max(0, len(claims) - ext_links)
    return len(claims)


_ANSWER_SIGNAL_RE = re.compile(
    # Explicit shorthand meta-signals
    r"tl;?dr"
    r"|in\s+short[,:]?"
    r"|the\s+short\s+answer\s+is"
    r"|key\s+takeaway[s:]?"
    r"|in\s+summary"
    r"|to\s+summarize"
    r"|bottom\s+line"
    # Sentence-start definition: "Noun/Proper-noun is a/an ..."
    # Require a capitalised subject; exclude pronouns/demonstratives that are not nouns.
    # The (?-i:...) inline flag disables the outer re.I so that [A-Z]
    # actually requires capitalisation. Without this, re.I makes [A-Z]
    # match lowercase letters too, destroying the capitalisation
    # constraint and flooding the system with false positives like
    # "dog is a good boy".
    r"|(?-i:(?:(?:^|(?<=[.!?])\s+)"
    r"(?!(?:There|This|That|These|Those|It|He|She|They|We|I|You|Our|The|A|An)\b)"
    r"[A-Z]\w{2,}(?:\s+[A-Z]?\w+){0,3}\s+(?:is|are)\s+(?:a|an)\s+\w{3,}))"
    # Explicit relation markers (safe, rare in non-definition prose)
    r"|\brefers?\s+to\b"
    r"|\bdefined\s+as\b",
    re.I | re.MULTILINE,
)


def _has_answer_signal(text: str) -> bool:
    return bool(_ANSWER_SIGNAL_RE.search(text))


_NUMBERED_STEP_RE = re.compile(r"^\s*\d+[\.\)]\s+\w", re.M)


def _has_numbered_steps(headings: list, page: "ParsedPage") -> bool:
    text = page.first_200_words or ""
    return bool(_NUMBERED_STEP_RE.search(text))


# ---------------------------------------------------------------------------
# M4.1: CONTENT_DATE_STALE_VISIBLE — page-type-aware freshness check
# ---------------------------------------------------------------------------

# Cadence in months per page type.  None means "never stale" (exempt).
_PAGE_TYPE_CADENCE: dict[str, int | None] = {
    "article": 12,
    "service": 24,
    "about": 24,
    "home": 24,
    "contact": 24,
    "faq": 24,
    "unknown": 24,
    "team_member": None,  # biographical — never stale
}


def check_content_date_stale_visible(
    page: ParsedPage,
    *,
    today: date,
) -> Optional[Dict[str, Any]]:
    """Check if visible modified date is stale for page type.

    DETERMINISM: ``today`` is explicit so tests can pin a fixed date.
    The caller in ``issue_checker.check_page`` passes
    ``today=datetime.now(timezone.utc).date()``.

    Returns:
        dict with issue details or None if no issue.
    """
    if not page.date_modified:
        return None

    # Parse the date robustly
    try:
        if isinstance(page.date_modified, str):
            dt = datetime.fromisoformat(page.date_modified)
            visible_date = dt.date() if hasattr(dt, "date") else dt
        elif isinstance(page.date_modified, datetime):
            visible_date = page.date_modified.date()
        elif isinstance(page.date_modified, date):
            visible_date = page.date_modified
        else:
            return None
    except (ValueError, TypeError):
        return None

    # Calculate age in months (approximate: 30-day months)
    age_days = (today - visible_date).days
    age_months = age_days // 30

    # Get page type and cadence — reuse the established classifier
    from api.services.page_classifier import infer_page_type
    page_type = infer_page_type(page)
    cadence = _PAGE_TYPE_CADENCE.get(page_type)

    # team_member: never stale
    if cadence is None:
        return None

    # Strict > comparison: exactly at cadence is NOT flagged
    if age_months <= cadence:
        return None

    return {
        "visible_date": visible_date.isoformat(),
        "age_months": age_months,
        "page_type": page_type,
        "recommended_refresh_months": cadence,
    }


# ---------------------------------------------------------------------------
# M4.2: CONTENT_STAT_OUTDATED — outdated year reference detection
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def detect_outdated_stat(text: str, *, current_year: int) -> dict | None:
    """Detect a year >=24mo old without current-year mention in same text window.

    DETERMINISM: ``current_year`` is explicit so tests can pin a fixed year.
    The caller in ``issue_checker.check_page`` passes ``datetime.now().year``.

    Args:
        text: Scanned text window (first_1500_words or fallback).
        current_year: Explicit year for deterministic testing.

    Returns:
        dict with keys "year" (int) and "sentence" (str, <=160 chars) or None.
    """
    if not text or not isinstance(text, str):
        return None

    # Check if current year is present anywhere in the window — skip if so
    if re.search(rf"\b{current_year}\b", text):
        return None

    # Find all 20xx years
    years = set(int(m.group()) for m in _YEAR_RE.finditer(text))

    # Filter: only years >=24 months old (i.e. <= current_year - 2)
    threshold = current_year - 2
    old_years = [y for y in years if y <= threshold]

    if not old_years:
        return None

    # Find the oldest flagged year and its context
    target_year = min(old_years)

    # Find first occurrence of that year in the text
    match = re.search(rf"\b{target_year}\b", text)
    if not match:
        return None

    # Exclude copyright lines (© or "copyright" preceding the year)
    pre_text = text[max(0, match.start() - 20):match.start()]
    if re.search(r'(?:©|copyright)', pre_text, re.IGNORECASE):
        return None

    # Exclude date ranges like 20xx-20yy or 20xx–20yy
    range_pattern = rf"{target_year}[–\-]\d{{4}}"
    if re.search(range_pattern, text):
        return None

    # Extract snippet around the match (up to 160 chars)
    start = max(0, match.start() - 60)
    end = min(len(text), match.end() + 100)
    snippet = text[start:end].strip()

    # Truncate snippet to 160 chars at word boundary
    if len(snippet) > 160:
        snippet = snippet[:157] + "..."

    return {"year": target_year, "sentence": snippet}

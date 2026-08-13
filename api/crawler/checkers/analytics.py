"""Analytics & Measurement checks (``analytics`` category).

Per-page measurement-integrity detection from crawl-time HTML — **no GSC/GA4/GTM
API involved**. Emits MI1 (tag missing), MI2 (duplicate tag), MI4 (consent mode
missing), MI5 (self-referencing UTM) and MI6 (untrackable outbound link). The
site-level MI3 (inconsistent ID) lives in ``checkers/cross_page.py`` because it
needs the whole page set.

Signatures/vocabulary live in ``api/crawler/analytics_patterns.py`` (config, not
logic — global rule #9 / P4). Presence is detected in markup only: a passing
result means the tag is *on the page*, not that it *fires*.

Spec: docs/pending/2026-08-06_measurement-integrity-checks.md
"""

from urllib.parse import urlparse, parse_qs

from api.crawler.parser import ParsedPage
import re

from api.crawler.analytics_patterns import (
    CAMPAIGN_PARAM_NAMES,
    CTA_INTENT_TERMS,
    CTA_ONCLICK_MARKERS,
    CTA_TRACKING_CLASS_MARKERS,
    CTA_TRACKING_DATA_PREFIXES,
    CURRENT_TAG_TYPES,
    DIRECT_MEASUREMENT_TYPES,
    UTM_PARAM_PREFIXES,
)

# Conversion-intent match, word-boundary anchored so "give" doesn't match
# "caregiver" and "order" doesn't match "border". Multi-word terms (sign up)
# work in the alternation.
_CTA_INTENT_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in CTA_INTENT_TERMS) + r")\b", re.I
)


def _cta_is_tracked(cta: dict) -> bool:
    """True when the CTA carries a detectable click-tracking marker (a
    convention class, a data-* tracking attr, or an inline gtag/dataLayer call)."""
    cls = (cta.get("class") or "").lower()
    if any(m in cls for m in CTA_TRACKING_CLASS_MARKERS):
        return True
    if any(d.lower().startswith(CTA_TRACKING_DATA_PREFIXES) for d in (cta.get("data_attrs") or [])):
        return True
    onclick = (cta.get("onclick") or "").lower()
    return any(m in onclick for m in CTA_ONCLICK_MARKERS)


def _cta_is_conversion(cta: dict) -> bool:
    return bool(_CTA_INTENT_RE.search(cta.get("text") or ""))


def _check_cta_tracking(page: ParsedPage, issues: list[Issue]) -> None:
    """MI7 — flag conversion CTAs missing the site's click-tracking convention.

    Fires ONLY when the page demonstrably uses a marker convention (≥1 tracked
    CTA), then lists the conversion CTAs that lack it. A GTM-only site (no HTML
    markers) is silent — GTM click triggers aren't visible in static HTML, so we
    don't guess (no false positives). Advisory / info.
    """
    ctas = page.cta_elements or []
    if not any(_cta_is_tracked(c) for c in ctas):
        return  # no tracking convention in use on this page → don't guess
    untracked = [c["text"] for c in ctas if _cta_is_conversion(c) and not _cta_is_tracked(c)]
    if not untracked:
        return
    tracked_count = sum(1 for c in ctas if _cta_is_tracked(c))
    issues.append(make_issue(
        "CTA_TRACKING_MISSING", page.url,
        extra={"untracked_ctas": untracked[:10],
               "untracked_count": len(untracked),
               "tracked_count": tracked_count}))
from api.crawler.checkers.registry import Issue, make_issue


def _check_analytics(page: ParsedPage, issues: list[Issue]) -> None:
    """Emit MI1/MI2/MI4/MI5/MI6 for a single page.

    Purpose: detect measurement-integrity problems from page HTML.
    Spec:    docs/pending/2026-08-06_measurement-integrity-checks.md
    Tests:   tests/test_analytics_checks.py
    """
    tags = page.analytics_tags or []
    # Direct (non-GTM) measurement tags: GA4 (G-) and the Google tag (GT-).
    direct = [t for t in tags if t.get("type") in DIRECT_MEASUREMENT_TYPES]
    gtm = [t for t in tags if t.get("type") == "gtm"]
    current = [t for t in tags if t.get("type") in CURRENT_TAG_TYPES]

    if not current:
        # MI1 — no current (GA4 / Google tag / GTM) tag anywhere on the page.
        issues.append(make_issue("ANALYTICS_TAG_MISSING", page.url))
    else:
        # MI2 — duplicate measurement delivery. The standard install is one
        # gtag.js loader (via="src") + one gtag('config') call (via="call") for a
        # single G-/GT- id — NOT a duplicate. A duplicate is a direct tag
        # configured in two+ separate <script> blocks (detection is
        # script-granular, so two config calls in ONE script read as one), or a
        # direct GA4/Google tag co-existing with a GTM container (plugin + GTM
        # double-tag). Ads/Floodlight gtag calls are excluded upstream (no
        # G-/GT- id → not a direct type).
        direct_config_calls = [t for t in direct if t.get("via") == "call"]
        direct_present = bool(direct)
        if len(direct_config_calls) >= 2 or (direct_present and bool(gtm)):
            ids = sorted({t["id"] for t in tags if t.get("id")})
            issues.append(make_issue(
                "ANALYTICS_TAG_DUPLICATE", page.url,
                extra={"ga4_config_calls": len(direct_config_calls),
                       "has_gtm": bool(gtm), "ids": ids}))

        # MI4 — consent mode missing (only meaningful when a tag exists; when MI1
        # fired we skip this entirely, so no-tag pages don't double-flag).
        if page.has_consent_mode is False:
            issues.append(make_issue("CONSENT_MODE_MISSING", page.url))

        # MI7 — CTA measurement coverage (only when a tag exists; else MI1 covers it).
        _check_cta_tracking(page, issues)

    # MI5 — self-referencing UTM / campaign params on INTERNAL links only.
    utm_links: list[str] = []
    for link in (page.links or []):
        if not link.is_internal:
            continue
        # keep_blank_values so `?utm_source=` (empty value) still counts; lower-
        # case the keys so UTM_Source / GCLID are caught too — both still reset
        # the GA4 session source.
        keys = {k.lower() for k in parse_qs(urlparse(link.url).query, keep_blank_values=True)}
        if any(k.startswith(UTM_PARAM_PREFIXES) for k in keys) or (keys & CAMPAIGN_PARAM_NAMES):
            utm_links.append(link.url)
    if utm_links:
        issues.append(make_issue(
            "SELF_REFERENCING_UTM", page.url,
            extra={"links": utm_links[:20], "count": len(utm_links)}))

    # MI6 — external image/icon links with no identifiable label (parser-computed).
    if page.untrackable_outbound_hrefs:
        issues.append(make_issue(
            "OUTBOUND_LINK_UNTRACKABLE", page.url,
            extra={"links": page.untrackable_outbound_hrefs[:20],
                   "count": len(page.untrackable_outbound_hrefs)}))

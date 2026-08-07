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
from api.crawler.analytics_patterns import (
    CAMPAIGN_PARAM_NAMES,
    CURRENT_TAG_TYPES,
    UTM_PARAM_PREFIXES,
)
from api.crawler.checkers.registry import Issue, make_issue


def _check_analytics(page: ParsedPage, issues: list[Issue]) -> None:
    """Emit MI1/MI2/MI4/MI5/MI6 for a single page.

    Purpose: detect measurement-integrity problems from page HTML.
    Spec:    docs/pending/2026-08-06_measurement-integrity-checks.md
    Tests:   tests/test_analytics_checks.py
    """
    tags = page.analytics_tags or []
    ga4 = [t for t in tags if t.get("type") == "ga4"]
    gtm = [t for t in tags if t.get("type") == "gtm"]
    current = [t for t in tags if t.get("type") in CURRENT_TAG_TYPES]

    if not current:
        # MI1 — no current (GA4/GTM) tag anywhere on the page.
        issues.append(make_issue("ANALYTICS_TAG_MISSING", page.url))
    else:
        # MI2 — duplicate GA4 delivery. The standard install is one gtag.js
        # loader (via="src") + one gtag('config') call (via="call") for a G- id
        # — that is NOT a duplicate. A duplicate is GA4 configured in two+
        # separate <script> blocks (detection is script-granular, so two config
        # calls in ONE script read as one), or a direct GA4 tag co-existing with
        # a GTM container (plugin + GTM double-tag). Ads/Floodlight gtag calls
        # are already excluded upstream (they carry no G- id → not type "ga4").
        ga4_config_calls = [t for t in ga4 if t.get("via") == "call"]
        ga4_direct = bool(ga4)
        if len(ga4_config_calls) >= 2 or (ga4_direct and bool(gtm)):
            ids = sorted({t["id"] for t in tags if t.get("id")})
            issues.append(make_issue(
                "ANALYTICS_TAG_DUPLICATE", page.url,
                extra={"ga4_config_calls": len(ga4_config_calls),
                       "has_gtm": bool(gtm), "ids": ids}))

        # MI4 — consent mode missing (only meaningful when a tag exists; when MI1
        # fired we skip this entirely, so no-tag pages don't double-flag).
        if page.has_consent_mode is False:
            issues.append(make_issue("CONSENT_MODE_MISSING", page.url))

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

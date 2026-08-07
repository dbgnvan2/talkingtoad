"""Analytics & Measurement tag signatures — editorial config, not logic.

Vendor/consent signatures for the ``analytics`` category checkers
(``api/crawler/checkers/analytics.py``). Adding a new analytics vendor or a new
consent-mode signal is a **data edit here**, never a logic change in the checker
(global rule #9 / P4 — keep editorial/vocabulary content out of source).

Spec: docs/pending/2026-08-06_measurement-integrity-checks.md
"""

from __future__ import annotations

import re

# Measurement-ID shapes. Word-boundary anchored so a bare id in prose is only
# treated as a tag when it co-occurs with a vendor call anchor (see the checker).
GA4_ID_RE = re.compile(r"\bG-[A-Z0-9]{6,12}\b")
GTM_ID_RE = re.compile(r"\bGTM-[A-Z0-9]{4,10}\b")
UA_ID_RE = re.compile(r"\bUA-\d{4,10}-\d{1,4}\b")

# One signature per vendor. A tag is detected on a <script> when EITHER a
# ``src`` substring matches (external loader) OR an inline ``call`` substring
# matches (inline snippet). The measurement id is best-effort extracted with
# ``id_re`` from whichever text matched; it may be None.
#
#   type        — vendor slug stored on ParsedPage.analytics_tags
#   id_re       — compiled measurement-id pattern
#   src_substrings   — matched against the <script src> attribute
#   call_substrings  — matched against inline <script> text (a real vendor CALL,
#                      never a bare id, to avoid false positives from prose)
#   require_id  — only record a detection when id_re actually matches an id.
#                 CRITICAL for GA4: the same `gtag('config',…)` call and
#                 `gtag/js` loader serve Google Ads (AW-…) and Floodlight (DC-…)
#                 too. Without this gate an Ads-only page would be mis-typed as
#                 GA4 — mis-firing MI2 on the very common "GA4 via GTM + Google
#                 Ads via gtag" setup, and hiding a truly-untagged page from MI1.
TAG_SIGNATURES: list[dict] = [
    {
        "type": "ga4",
        "id_re": GA4_ID_RE,
        "src_substrings": ["googletagmanager.com/gtag/js"],
        "call_substrings": ["gtag('config'", 'gtag("config"'],
        "require_id": True,   # a G- id must be present — AW-/DC- gtag calls are NOT GA4
    },
    {
        "type": "gtm",
        "id_re": GTM_ID_RE,
        "src_substrings": ["googletagmanager.com/gtm.js"],
        # The standard GTM container snippet is an inline IIFE that contains
        # both the gtm.js loader URL and the GTM-XXXX id as an argument.
        "call_substrings": ["googletagmanager.com/gtm.js", "'gtm.start'", '"gtm.start"'],
        "require_id": True,
    },
    {
        # Legacy Universal Analytics — dead since 2023-07. Informational only:
        # its presence never satisfies MI1 "has a working tag" on its own, but
        # we record it so a future "you still reference dead UA" note is cheap.
        "type": "ua",
        "id_re": UA_ID_RE,
        "src_substrings": ["google-analytics.com/analytics.js", "google-analytics.com/ga.js"],
        "call_substrings": ["GoogleAnalyticsObject", "ga('create'", 'ga("create"'],
        "require_id": True,
    },
]

# Vendor slugs that count as a live, current analytics tag for MI1 (tag-missing).
# UA is deliberately excluded — a page whose ONLY tag is dead UA is still
# effectively unmeasured for current GA4 reporting.
CURRENT_TAG_TYPES: frozenset[str] = frozenset({"ga4", "gtm"})

# Google Consent Mode v2 signals — any present ⇒ consent mode is configured.
# Deliberately precise: only real `gtag('consent', …)` / `dataLayer` consent
# defaults count. Bare substrings like "consent_mode" were removed — a
# cookie-banner variable or comment containing them would falsely suppress the
# (info-level) MI4 even when GA4 Consent Mode isn't actually wired.
CONSENT_MODE_SIGNALS: tuple[str, ...] = (
    "gtag('consent'",
    'gtag("consent"',
    "'consent', 'default'",
    '"consent", "default"',
    "'consent','default'",
    '"consent","default"',
)

# Query-parameter prefixes that carry campaign attribution. A self-referencing
# internal link with any of these restarts the GA4 session source.
UTM_PARAM_PREFIXES: tuple[str, ...] = ("utm_",)
# Non-utm campaign params that also break/override attribution when placed on an
# internal link (Google Ads / Meta / Mailchimp click ids).
CAMPAIGN_PARAM_NAMES: frozenset[str] = frozenset({"gclid", "gbraid", "wbraid", "fbclid", "mc_eid", "msclkid"})

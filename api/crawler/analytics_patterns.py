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
# Google's newer unified "Google tag" id — distinct from GA4's G- (it routes to
# GA4 and/or Google Ads). Increasingly Google's default hand-out for GA4, so it
# MUST count as a present measurement tag or MI1 false-fires (2026-08-08).
GT_ID_RE = re.compile(r"\bGT-[A-Z0-9]{6,12}\b")
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
        # Google's unified "Google tag" (GT-…). Shares gtag.js delivery with GA4;
        # each signature searches the SAME script for its own id, so a GT- script
        # records here (require_id keeps AW-/DC- out) while a G- script records as
        # ga4. Counts as a present measurement tag (CURRENT_TAG_TYPES) so MI1
        # doesn't false-fire on the increasingly-common Google tag.
        "type": "google_tag",
        "id_re": GT_ID_RE,
        "src_substrings": ["googletagmanager.com/gtag/js"],
        "call_substrings": ["gtag('config'", 'gtag("config"'],
        "require_id": True,
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
CURRENT_TAG_TYPES: frozenset[str] = frozenset({"ga4", "gtm", "google_tag"})

# Direct (non-GTM) measurement tags. MI2's duplicate check reads across these so a
# Google tag (GT-) behaves like GA4 (G-): two config calls, or one direct tag
# co-existing with a GTM container, is a double-tag.
DIRECT_MEASUREMENT_TYPES: frozenset[str] = frozenset({"ga4", "google_tag"})

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

# ── MI7 — CTA measurement-coverage (2026-08-09) ─────────────────────────────
# Conversion-intent terms: a CTA whose accessible text contains one of these is a
# "conversion CTA" worth measuring. Nav toggles / "read more" are excluded on
# purpose (low value, high noise). Editorial vocabulary (global rule #9).
CTA_INTENT_TERMS: tuple[str, ...] = (
    "donate", "give", "pledge", "book", "schedule", "appointment", "contact",
    "register", "sign up", "signup", "subscribe", "apply", "join", "volunteer",
    "get started", "enrol", "enroll", "rsvp", "reserve", "buy", "shop",
    "checkout", "purchase", "order",
    # Service/consultation conversions (counselling, therapy, coaching, etc.)
    "counselling", "counseling", "intake", "consultation", "consult", "request",
)

# A CTA counts as "tracked" when a click-tracking marker is detected on it:
#   - its class contains any CTA_TRACKING_CLASS_MARKERS substring, OR
#   - it has a data-* attribute whose name starts with any CTA_TRACKING_DATA_PREFIXES, OR
#   - its onclick contains any CTA_ONCLICK_MARKERS call.
# Defaults cover the common `track-*` class convention (a JS listener fires a GA4
# event on click). Config-editable to match a site's own convention.
CTA_TRACKING_CLASS_MARKERS: tuple[str, ...] = (
    # both hyphen and underscore conventions (track-donate / track_donate)
    "track-", "track_", "-track", "_track",
    "ga-event", "ga4-event", "gtm-track", "analytics-event",
)
CTA_TRACKING_DATA_PREFIXES: tuple[str, ...] = (
    "data-track", "data-ga", "data-gtm", "data-event", "data-analytics",
)
CTA_ONCLICK_MARKERS: tuple[str, ...] = ("gtag(", "datalayer.push", "ga(")

# Builder button classes that mark an <a>/<input> as a button-like CTA, on top of
# the generic \b(btn|button|cta)\b already used elsewhere in the parser.
CTA_BUTTON_CLASS_HINTS: tuple[str, ...] = (
    "elementor-button", "wp-block-button__link", "wp-element-button",
)

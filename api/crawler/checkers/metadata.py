"""Metadata-related checks: canonical tag validation.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function body is byte-identical to the original
_check_canonical().
"""

from urllib.parse import urlparse

from api.crawler.normaliser import is_same_domain
from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue

# Schema.org types that identify an organisation (homepage identity anchor).
# Matched case-insensitively; any type ending in "Organization" or "Business"
# (LocalBusiness subtypes) also qualifies.
_ORG_SCHEMA_TYPES = frozenset({
    "organization", "ngo", "nonprofitorganization", "corporation",
    "localbusiness", "educationalorganization", "governmentorganization",
    "medicalorganization", "sportsorganization", "performinggroup",
})


def _has_org_schema(schema_types: list[str] | None) -> bool:
    """Return True if any schema type identifies an organisation."""
    for t in (schema_types or []):
        tl = str(t).strip().lower()
        if tl in _ORG_SCHEMA_TYPES or tl.endswith("organization") or tl.endswith("business"):
            return True
    return False


def check_homepage_agent_readiness(page: ParsedPage, issues: list[Issue]) -> None:
    """Homepage-scoped agent-readiness checks (WP5): Organization schema + contact info."""
    if not page.is_homepage:
        return

    # SCHEMA_ORG_MISSING — homepage has no Organization/LocalBusiness schema.
    if page.is_indexable and not _has_org_schema(page.schema_types):
        issues.append(make_issue("SCHEMA_ORG_MISSING", page.url))

    # CONTACT_INFO_NOT_IN_HTML — no machine-readable contact info as text.
    # contact_info_in_text is None on non-homepages and when computation failed;
    # only emit on an explicit False (parser confirmed nothing readable found).
    if page.contact_info_in_text is False:
        issues.append(make_issue("CONTACT_INFO_NOT_IN_HTML", page.url))


def _check_canonical(page: ParsedPage, issues: list[Issue]) -> None:
    url = page.url
    parsed_page = urlparse(url)

    # Defensive normalisation:
    #   V2: <link rel="canonical" href=""> yields canonical_url="". The
    #       pre-fix `is not None` guard let "" through to is_same_domain,
    #       which returned False, falsely emitting CANONICAL_EXTERNAL. An
    #       empty href is functionally equivalent to a missing tag and
    #       must fall through to the missing-canonical branch below.
    #   V3: sloppy CMSes / templaters can leave leading or trailing
    #       whitespace on the href. Python's stdlib urlparse happens to
    #       tolerate leading whitespace before the scheme, so the bug
    #       does not currently manifest — but stripping here makes the
    #       code robust against future urlparse changes and ensures the
    #       canonical_url stored in issue.extra is the clean form.
    clean_canonical = (page.canonical_url or "").strip()

    if clean_canonical:
        # Has a (non-empty, stripped) canonical tag
        if not is_same_domain(clean_canonical, url):
            issue = make_issue("CANONICAL_EXTERNAL", url)
            issue.extra = {"canonical_url": clean_canonical}
            issues.append(issue)
        # Self-referencing canonical → OK, no issue
    else:
        # No canonical tag (or empty/whitespace-only one) — check the
        # two scoping conditions.
        # Condition 1: has query string parameters
        if parsed_page.query:
            issues.append(make_issue("CANONICAL_MISSING", url))
        # Condition 2 (near-duplicate): handled in check_cross_page after all pages crawled

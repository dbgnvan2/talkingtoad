"""
Outbound link authority classifier for GEO analysis.

Spec: docs/implementation_plan_geo_analyzer_2026-05-03.md#GEO.4.1
"""

import re
from urllib.parse import urlparse

# Domains treated as authoritative sources (government, academic, standards bodies,
# major documentation hubs). Checked via suffix match on netloc.
_AUTHORITY_SUFFIXES = (
    ".gov", ".edu", ".ac.uk", ".ac.au", ".ac.nz", ".ac.za",
)

_AUTHORITY_DOMAINS = frozenset([
    # Health / science
    "nih.gov", "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov",
    "who.int", "cdc.gov",
    # Research / preprints
    "arxiv.org", "doi.org", "ssrn.com", "researchgate.net",
    "scholar.google.com", "semanticscholar.org",
    # Standards / specs
    "w3.org", "ietf.org", "iana.org", "rfc-editor.org",
    "ecma-international.org", "iso.org",
    # Documentation / developer hubs
    "developer.mozilla.org", "mdn.mozilla.org",
    "pypi.org", "npmjs.com", "crates.io",
    "docs.python.org", "docs.rs",
    "developer.apple.com", "developer.android.com",
    "learn.microsoft.com", "docs.microsoft.com",
    "cloud.google.com", "aws.amazon.com", "docs.aws.amazon.com",
    # Version control / code
    "github.com", "gitlab.com",
    # News / journalism (major outlets used for citation)
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
])

_REFERENCE_DOMAINS = frozenset([
    "wikipedia.org", "en.wikipedia.org",
    "britannica.com", "merriam-webster.com",
])

# Patterns for promotional / affiliate links
_PROMO_PATTERNS = [
    re.compile(r"[?&](ref|aff|affiliate|utm_source|partner)=", re.I),
    re.compile(r"/(ref|aff|go)/", re.I),
]


def classify_link(url: str, page_origin: str) -> str:
    """Return 'authority', 'reference', 'promotional', 'internal', or 'other'.

    Args:
        url: The href to classify.
        page_origin: The origin of the page (scheme + netloc) — used to detect internal links.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return "other"

    if not parsed.scheme or not parsed.netloc:
        return "other"

    page_parsed = urlparse(page_origin)
    page_netloc = page_parsed.netloc.removeprefix("www.")
    link_netloc = parsed.netloc.removeprefix("www.")

    if link_netloc == page_netloc:
        return "internal"

    # Promotional check first (URLs can be .gov but also have affiliate params)
    for pat in _PROMO_PATTERNS:
        if pat.search(url):
            return "promotional"

    # Authority: TLD suffix or known domain
    for suffix in _AUTHORITY_SUFFIXES:
        if link_netloc.endswith(suffix):
            return "authority"
    if link_netloc in _AUTHORITY_DOMAINS:
        return "authority"
    # Also match subdomains of authority domains
    for domain in _AUTHORITY_DOMAINS:
        if link_netloc.endswith("." + domain):
            return "authority"

    if link_netloc in _REFERENCE_DOMAINS:
        return "reference"
    for domain in _REFERENCE_DOMAINS:
        if link_netloc.endswith("." + domain):
            return "reference"

    return "other"


def classify_body_links(links: list, page_url: str) -> dict:
    """Classify a list of ParsedLink objects and return a summary dict.

    Returns:
        {
            "authority": int,
            "reference": int,
            "promotional": int,
            "internal": int,
            "other": int,
            "external_body_total": int,  # authority + reference + promotional + other
        }
    """
    from urllib.parse import urlparse as _up
    origin = "{0.scheme}://{0.netloc}".format(_up(page_url))

    counts = {"authority": 0, "reference": 0, "promotional": 0, "internal": 0, "other": 0}
    for link in links:
        href = getattr(link, "url", None) or (link.get("url") if isinstance(link, dict) else None)
        if not href:
            continue
        classification = classify_link(href, origin)
        counts[classification] = counts.get(classification, 0) + 1

    external = counts["authority"] + counts["reference"] + counts["promotional"] + counts["other"]
    counts["external_body_total"] = external
    return counts

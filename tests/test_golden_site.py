"""End-to-end golden-fixture detection test.

Serves the local golden site (tests/golden_site/) and runs the REAL crawl engine
against it, then asserts each page surfaces the issue codes it was built to
demonstrate (false negatives / regressions) and that targeted false-positive
guards hold. This exercises the whole pipeline — fetch → parse → check →
cross-page → score → aggregate — which per-checker unit tests can't.

See docs/golden-fixture-plan.md. To browse the site by hand:
    python tests/golden_site/build_pages.py   # (re)generate pages
    python tests/golden_site/server.py        # serve on a localhost port

Environment artifacts (present everywhere, NOT bugs — excluded from assertions):
  * HTTP_PAGE            — the fixture is served over http://
  * WRONG_PLACEHOLDER_LINK — internal links resolve to 127.0.0.1, which the app
    (correctly, for a real site) treats as a localhost/wrong-domain placeholder.
"""

import asyncio
import collections

import pytest

import api.crawler.fetcher as fetcher
from api.crawler.engine import run_crawl, CrawlSettings
from tests.golden_site.build_pages import main as build_pages
from tests.golden_site.server import GoldenSiteServer

ENV_ARTIFACTS = {"HTTP_PAGE", "WRONG_PLACEHOLDER_LINK"}

# page path -> codes that MUST be present (the page's reason for existing).
EXPECT = {
    "/": {"FAVICON_MISSING", "SCHEMA_ORG_MISSING", "LLMS_TXT_MISSING", "AI_TXT_MISSING",
          "AI_BOT_TRAINING_DISALLOWED", "CONTACT_INFO_NOT_IN_HTML", "ENTITY_NAME_INCONSISTENT"},
    "/title-missing.html": {"TITLE_MISSING"},
    "/title-short.html": {"TITLE_TOO_SHORT"},
    "/title-long.html": {"TITLE_TOO_LONG"},
    "/meta-missing.html": {"META_DESC_MISSING"},
    "/meta-short.html": {"META_DESC_TOO_SHORT"},
    "/meta-long.html": {"META_DESC_TOO_LONG"},
    "/lang-missing.html": {"LANG_MISSING"},
    "/social-missing.html": {"SOCIAL_PREVIEW_METADATA_MISSING"},
    "/headings-none.html": {"H1_MISSING"},
    "/headings-multi.html": {"H1_MULTIPLE"},
    "/headings-skip.html": {"HEADING_SKIP"},
    "/headings-empty.html": {"HEADING_EMPTY", "CONVERSATIONAL_H2_MISSING"},
    "/links-bad.html": {"ANCHOR_TEXT_GENERIC", "LINK_EMPTY_ANCHOR"},
    "/thin.html": {"THIN_CONTENT", "CONTENT_THIN"},
    "/noindex-meta.html": {"NOINDEX_META"},
    "/noindex-header.html": {"NOINDEX_HEADER"},
    "/no-viewport.html": {"MISSING_VIEWPORT_META"},
    "/orphan.html": {"ORPHAN_PAGE"},
    "/semantic-bad.html": {"NON_SEMANTIC_BUTTON", "LANDMARK_MAIN_MISSING",
                           "INTERACTIVE_NO_ACCESSIBLE_NAME"},
    "/article-noauthor.html": {"AUTHOR_BYLINE_MISSING", "DATE_PUBLISHED_MISSING",
                               "DATE_MODIFIED_MISSING"},
    "/article-bare-author.html": {"AUTHOR_CREDENTIALS_MISSING", "CONTENT_DATE_STALE_VISIBLE"},
    "/howto-incomplete.html": {"HOWTO_SCHEMA_INCOMPLETE"},
    "/product-norating.html": {"PRODUCT_REVIEW_SCHEMA_MISSING", "SCHEMA_VISIBLE_MISMATCH"},
    "/jsonld-invalid.html": {"JSON_LD_INVALID"},
    "/faq-noschema.html": {"FAQ_SCHEMA_MISSING"},
    "/dup-a.html": {"TITLE_DUPLICATE", "META_DESC_DUPLICATE"},
    "/dup-b.html": {"TITLE_DUPLICATE", "META_DESC_DUPLICATE"},
    # NEAR_DUPLICATE_BODY is site-scoped — emitted once on the cluster
    # representative (sorted-first member = neardup-a.html), not on both.
    "/neardup-a.html": {"NEAR_DUPLICATE_BODY"},
    "/entity-b.html": {"ENTITY_SAMEAS_MISSING"},
    "/URL_Uppercase.html": {"URL_UPPERCASE", "URL_HAS_UNDERSCORES"},
    "/has_underscores.html": {"URL_HAS_UNDERSCORES"},
    "/chain-a": {"REDIRECT_CHAIN", "INTERNAL_REDIRECT_301"},
    "/redirect-302": {"REDIRECT_302"},
    "/loop-a": {"REDIRECT_LOOP"},
    "/secret-area": {"LOGIN_REDIRECT"},
}

# page path -> codes that must be ABSENT (targeted false-positive guards).
FORBID = {
    "/article-bare-author.html": {"AUTHOR_BYLINE_MISSING"},  # byline IS present
    "/entity-a.html": {"ENTITY_SAMEAS_MISSING"},             # sameAs IS present
}

# Floor for total distinct codes exercised — guards against a whole category
# silently going dark (observed ~58; floored below with headroom).
MIN_DISTINCT_CODES = 55


@pytest.fixture(scope="module")
def golden():
    """Run the real crawl once against the served golden site."""
    build_pages()
    orig = fetcher.is_ssrf_safe
    fetcher.is_ssrf_safe = lambda url: True  # allow the loopback fixture host
    try:
        with GoldenSiteServer() as srv:
            base = srv.base_url.rstrip("/")
            res = asyncio.run(run_crawl(
                "golden", srv.base_url,
                CrawlSettings(crawl_delay_ms=0, max_pages=100)))
    finally:
        fetcher.is_ssrf_safe = orig

    by_page = collections.defaultdict(set)
    for iss in res.issues:
        key = (iss.page_url or "").replace(base, "") or "/"
        by_page[key].add(iss.code)
    all_codes = {c for codes in by_page.values() for c in codes}
    return dict(by_page), all_codes


@pytest.mark.parametrize("path", sorted(EXPECT))
def test_expected_codes_are_detected(golden, path):
    """Each fixture page surfaces the codes it was built to demonstrate."""
    by_page, _ = golden
    detected = by_page.get(path, set())
    missing = EXPECT[path] - detected
    assert not missing, (
        f"{path}: expected codes not surfaced: {sorted(missing)}.\n"
        f"  detected: {sorted(detected)}")


@pytest.mark.parametrize("path", sorted(FORBID))
def test_forbidden_codes_absent(golden, path):
    """Targeted false-positive guards — a correct page must not trip the code."""
    by_page, _ = golden
    detected = by_page.get(path, set())
    tripped = FORBID[path] & detected
    assert not tripped, f"{path}: false positive — should NOT surface {sorted(tripped)}"


def test_coverage_floor(golden):
    """The golden run must exercise a broad swath of the catalogue end-to-end."""
    _, all_codes = golden
    real = all_codes - ENV_ARTIFACTS
    assert len(real) >= MIN_DISTINCT_CODES, (
        f"only {len(real)} distinct codes exercised (floor {MIN_DISTINCT_CODES}) — "
        f"a detection category may have gone dark. Got: {sorted(real)}")

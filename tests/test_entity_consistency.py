"""E1 — Brand-entity consistency checks (cross-page).

Spec: docs/pending/2026-07-22_p1-entity-consistency-near-duplicate.md
Codes: ENTITY_NAME_INCONSISTENT (site), ENTITY_SAMEAS_MISSING (page),
       AUTHOR_IDENTITY_INCONSISTENT (site)

Adversarial guards (P7) are written FIRST (test_e1_2…): normalisation must not
turn a casing/legal-suffix difference into a false "inconsistent" verdict.
"""

import dataclasses as dc

import pytest

from api.crawler.parser import ParsedPage
from api.crawler.checkers.cross_page import check_cross_page


def _pp(url, *, schema_blocks=None, first_1500_words=None, title="Title",
        canonical_url=None, status_code=200, redirect_url=None):
    return ParsedPage(
        url=url, final_url=url, status_code=status_code, response_size_bytes=1000,
        title=title, meta_description="A sufficiently long meta description text.",
        og_title=None, og_description=None, og_image=None, twitter_card=None,
        canonical_url=canonical_url, h1_tags=["H1"],
        headings_outline=[{"level": 1, "text": "H1"}], is_indexable=True,
        robots_directive=None, links=[], has_favicon=None, has_viewport_meta=True,
        schema_types=[], external_script_count=0, external_stylesheet_count=0,
        schema_blocks=schema_blocks, first_1500_words=first_1500_words,
        redirect_url=redirect_url,
    )


def _org(name, sameas=None):
    b = {"@type": "Organization", "name": name}
    if sameas is not None:
        b["sameAs"] = sameas
    return b


def _codes(issues):
    return [i.code for i in issues]


# ── Adversarial guard FIRST (P7 / P10) ─────────────────────────────────────
class TestNameNormalisationGuard:
    def test_e1_2_normalised_no_false_positive(self):
        """Casing + legal-suffix-only differences must NOT fire
        ENTITY_NAME_INCONSISTENT. 'Living Systems Counselling Society',
        'Living Systems Counselling' and 'LIVING SYSTEMS  counselling' are one
        entity — a wrong flag here is the failure mode this whole design guards."""
        pages = [
            _pp("https://x.org/a", schema_blocks=[_org("Living Systems Counselling Society")]),
            _pp("https://x.org/b", schema_blocks=[_org("Living Systems Counselling")]),
            _pp("https://x.org/c", schema_blocks=[_org("LIVING SYSTEMS  counselling")]),
        ]
        assert "ENTITY_NAME_INCONSISTENT" not in _codes(check_cross_page(pages))


class TestEntityNameInconsistent:
    def test_e1_1_name_variants(self):
        """Two genuinely different org names across the site ⇒ exactly one
        site-scoped issue listing the variants."""
        pages = [
            _pp("https://x.org/a", schema_blocks=[_org("Acme Society")]),
            _pp("https://x.org/b", schema_blocks=[_org("Acme Society")]),
            _pp("https://x.org/c", schema_blocks=[_org("Beta Foundation")]),
        ]
        issues = [i for i in check_cross_page(pages) if i.code == "ENTITY_NAME_INCONSISTENT"]
        assert len(issues) == 1, "site-scoped: emit once, not per page"
        variants = issues[0].extra.get("variants") or []
        names = {v.get("name") for v in variants}
        assert {"Acme Society", "Beta Foundation"} <= names

    def test_e1_partners_page_no_false_positive(self):
        """Regression (learning-qa finding): a page listing multiple third-party
        Organizations (funders/partners) must NOT be read as the site naming
        itself inconsistently. Self-identity comes from publisher/provider or a
        page's single Organization node — not a multi-org listing."""
        partners_page = _pp("https://x.org/partners", schema_blocks=[
            {"@type": "Organization", "name": "Rotary Club"},
            {"@type": "Organization", "name": "United Way"},
            {"@type": "Organization", "name": "Local Foundation"},
        ])
        pages = [
            _pp("https://x.org/a", schema_blocks=[_org("Acme Society")]),
            _pp("https://x.org/b", schema_blocks=[_org("Acme Society")]),
            partners_page,
        ]
        assert "ENTITY_NAME_INCONSISTENT" not in _codes(check_cross_page(pages))

    def test_e1_single_name_silent(self):
        pages = [
            _pp("https://x.org/a", schema_blocks=[_org("Acme Society")]),
            _pp("https://x.org/b", schema_blocks=[_org("Acme Society")]),
            _pp("https://x.org/c", schema_blocks=[_org("Acme Society")]),
        ]
        assert "ENTITY_NAME_INCONSISTENT" not in _codes(check_cross_page(pages))


class TestSameAsMissing:
    def test_e1_3_sameas_boundary(self):
        pages = [
            _pp("https://x.org/a", schema_blocks=[_org("Acme", sameas=["https://en.wikipedia.org/Acme"])]),
            _pp("https://x.org/b", schema_blocks=[_org("Acme")]),           # missing sameAs → fires
            _pp("https://x.org/c", schema_blocks=[{"@type": "WebPage"}]),   # no entity block → never fires
        ]
        issues = check_cross_page(pages)
        sameas = [i for i in issues if i.code == "ENTITY_SAMEAS_MISSING"]
        urls = {i.page_url for i in sameas}
        assert urls == {"https://x.org/b"}


class TestAuthorIdentity:
    def test_e1_4_author_identity(self):
        """Same author name under two different URLs ⇒ AUTHOR_IDENTITY_INCONSISTENT."""
        def art(author_name, author_url):
            return {"@type": "BlogPosting",
                    "author": {"@type": "Person", "name": author_name, "url": author_url}}
        pages = [
            _pp("https://x.org/p1", schema_blocks=[art("Jane Doe", "https://x.org/author/jane")]),
            _pp("https://x.org/p2", schema_blocks=[art("Jane Doe", "https://x.org/author/j-doe")]),
            _pp("https://x.org/p3", schema_blocks=[art("Jane Doe", "https://x.org/author/jane")]),
        ]
        issues = [i for i in check_cross_page(pages) if i.code == "AUTHOR_IDENTITY_INCONSISTENT"]
        assert len(issues) == 1

    def test_e1_4_consistent_author_silent(self):
        def art(u):
            return {"@type": "BlogPosting",
                    "author": {"@type": "Person", "name": "Jane Doe", "url": u}}
        pages = [
            _pp("https://x.org/p1", schema_blocks=[art("https://x.org/author/jane")]),
            _pp("https://x.org/p2", schema_blocks=[art("https://x.org/author/jane")]),
            _pp("https://x.org/p3", schema_blocks=[art("https://x.org/author/jane")]),
        ]
        assert "AUTHOR_IDENTITY_INCONSISTENT" not in _codes(check_cross_page(pages))


class TestSmallSiteAndDirtyState:
    def test_g1_small_site_skips(self, monkeypatch):
        """Below min_pages_for_site_checks, site-scoped entity checks are skipped."""
        import api.crawler.checkers.cross_page as cp
        monkeypatch.setattr(cp, "_MIN_PAGES_SITE_CHECKS", 3)
        pages = [
            _pp("https://x.org/a", schema_blocks=[_org("Acme")]),
            _pp("https://x.org/b", schema_blocks=[_org("Beta")]),
        ]
        assert "ENTITY_NAME_INCONSISTENT" not in _codes(check_cross_page(pages))

    def test_g2_missing_fields(self):
        """Old crawl rows: schema_blocks=None / first_1500_words=None must not crash."""
        pages = [_pp("https://x.org/a"), _pp("https://x.org/b"), _pp("https://x.org/c")]
        # Should simply produce no entity/near-dup issues, no exception.
        codes = _codes(check_cross_page(pages))
        assert "ENTITY_NAME_INCONSISTENT" not in codes
        assert "NEAR_DUPLICATE_BODY" not in codes

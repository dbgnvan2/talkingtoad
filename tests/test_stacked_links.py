"""E6 — stacked overlay links: several <a> to one destination in one card.

Purpose: catch the pattern `LINK_EMPTY_ANCHOR` structurally cannot see (every
         anchor in the group has an accessible name), without flagging the
         header logo + brand-name pattern that exists on nearly every website.
Spec:    docs/pending/2026-08-29_E6-stacked-duplicate-links.md
Tests:   this file

The false-positive test comes first (P10). A header logo link and a "Home" text
link both point at "/" almost everywhere; a naive implementation flags all of
them and the check is worthless. The card-container requirement exists solely to
prevent that, so that is the test written first.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from api.crawler.checkers.registry import _CATALOGUE, _ISSUE_SCORING
from api.crawler.parser import _find_stacked_links
from api.services.job_store_base import _CLUSTER_SUPPRESSION

PAGE = "https://example.com/"
FIXTURES = Path(__file__).parent / "fixtures" / "lazy_images"


def _groups(html: str, page_url: str = PAGE) -> list[dict]:
    return _find_stacked_links(BeautifulSoup(html, "lxml"), page_url)


# ── E6.4a — the false positive that would sink the check (written first) ────


class TestNoFalsePositives:
    def test_e6_4a_header_logo_and_home_link_clean(self):
        """Two anchors, one href, not in a card. Must NOT fire."""
        html = (
            '<header class="site-header">'
            '  <a href="/"><img src="/logo.png" alt="Acme"></a>'
            '  <a href="/">Home</a>'
            "</header>"
        )
        assert _groups(html) == []

    def test_e6_4a_nav_menu_repeat_clean(self):
        html = (
            '<nav><ul class="menu">'
            '  <li><a href="/about">About</a></li>'
            '  <li><a href="/contact">Contact</a></li>'
            "</ul></nav>"
        )
        assert _groups(html) == []

    def test_e6_4a_footer_duplicate_of_header_link_clean(self):
        """The same href in two DIFFERENT containers is not a stacked group."""
        html = (
            '<header><a href="/donate">Donate</a></header>'
            '<footer><a href="/donate">Donate</a></footer>'
        )
        assert _groups(html) == []

    def test_e6_1c_different_hrefs_in_one_card_clean(self):
        html = (
            '<li class="card">'
            '  <a href="/a">A</a><a href="/b">B</a>'
            "</li>"
        )
        assert _groups(html) == []

    def test_e6_4a_real_homepage_produces_no_spurious_groups(self):
        """Real artifact: whatever this returns must be defensible, and every
        group it reports must genuinely be 2+ anchors to one href."""
        soup = BeautifulSoup((FIXTURES / "livingsystems_home.html").read_text(), "lxml")
        for g in _find_stacked_links(soup, "https://livingsystems.ca/"):
            assert g["count"] >= 2
            assert len(g["accessible_names"]) == g["count"]
            assert g["href"].startswith("http")


# ── E6.1 — grouping ────────────────────────────────────────────────────────


class TestGrouping:
    OVERLAY_CARD = (
        '<ul><li class="card">'
        '  <a href="/x" class="overlay" aria-label="Read X"></a>'
        "  <a href=\"/x\"><h3>X title</h3></a>"
        '  <a href="/x"><img src="/x.jpg" alt="X image"></a>'
        "</li></ul>"
    )

    def test_e6_1a_three_anchors_one_group(self):
        groups = _groups(self.OVERLAY_CARD)
        assert len(groups) == 1
        assert groups[0]["count"] == 3
        assert groups[0]["href"] == "https://example.com/x"

    def test_e6_2a_issue_carries_accessible_names(self):
        """The operator needs to see which anchor to keep."""
        names = _groups(self.OVERLAY_CARD)[0]["accessible_names"]
        assert "X title" in names and "Read X" in names and "X image" in names

    def test_e6_1b_separate_containers_not_grouped(self):
        html = (
            '<ul><li class="card"><a href="/x">X</a><a href="/x">X again</a></li>'
            '<li class="card"><a href="/y">Y</a></li></ul>'
        )
        groups = _groups(html)
        assert len(groups) == 1
        assert groups[0]["href"] == "https://example.com/x"

    def test_e6_1d_href_normalised_before_grouping(self):
        """Relative and absolute forms of one destination group together."""
        html = (
            '<li class="card">'
            '  <a href="/x">Rel</a>'
            '  <a href="https://example.com/x">Abs</a>'
            "</li>"
        )
        assert len(_groups(html)) == 1

    def test_e6_1a_article_tag_is_a_container(self):
        html = '<article><a href="/x">A</a><a href="/x">B</a></article>'
        assert len(_groups(html)) == 1

    @pytest.mark.parametrize(
        "cls", ["elementor-post", "jet-listing-grid__item", "wp-block-post", "teaser"]
    )
    def test_e6_1a_builder_classes_recognised(self, cls):
        html = f'<div class="{cls}"><a href="/x">A</a><a href="/x">B</a></div>'
        assert len(_groups(html)) == 1

    def test_e6_1a_unknown_container_class_not_matched(self):
        html = '<div class="totally-custom-wrapper"><a href="/x">A</a><a href="/x">B</a></div>'
        assert _groups(html) == []

    @pytest.mark.parametrize("href", ["#", "javascript:void(0)", "mailto:a@b.c", "tel:+1"])
    def test_e6_1a_non_navigational_hrefs_ignored(self, href):
        html = f'<li class="card"><a href="{href}">A</a><a href="{href}">B</a></li>'
        assert _groups(html) == []

    def test_e6_1a_single_link_card_clean(self):
        html = '<li class="card"><a href="/x"><h3>X</h3></a></li>'
        assert _groups(html) == []


# ── E6.2 — the emitted issue ───────────────────────────────────────────────


class TestIssueEmission:
    def _page_with(self, html: str):
        from api.crawler.fetcher import FetchResult
        from api.crawler.parser import parse_page

        full = (
            "<!DOCTYPE html><html><head><title>A Card Page With A Long Title</title>"
            '<meta name="description" content="A description long enough to pass checks here.">'
            f"</head><body><h1>Cards</h1>{html}</body></html>"
        )
        result = FetchResult(
            url=PAGE, final_url=PAGE, status_code=200, first_status_code=200,
            headers={"content-type": "text/html"}, html=full,
            content_type="text/html", response_size_bytes=len(full),
        )
        return parse_page(result, PAGE, is_homepage=True)

    def test_e6_2a_emits_the_code(self):
        from api.crawler.issue_checker import check_page

        page = self._page_with(TestGrouping.OVERLAY_CARD)
        issues = check_page(page)
        issue = next((i for i in issues if i.code == "LINK_STACKED_DUPLICATE"), None)
        assert issue is not None
        assert issue.extra["groups_total"] == 1
        assert issue.extra["groups"][0]["count"] == 3
        assert "point to" in issue.description

    def test_e6_2b_group_cap_announced(self):
        """Rule 6: a capped list must carry the true total."""
        from api.crawler.issue_checker import check_page

        cards = "".join(
            f'<li class="card"><a href="/p{i}">A</a><a href="/p{i}">B</a></li>'
            for i in range(25)
        )
        page = self._page_with(f"<ul>{cards}</ul>")
        issue = next(i for i in check_page(page) if i.code == "LINK_STACKED_DUPLICATE")
        assert len(issue.extra["groups"]) == 10
        assert issue.extra["groups_total"] == 25

    def test_e6_2a_clean_page_emits_nothing(self):
        from api.crawler.issue_checker import check_page

        page = self._page_with('<li class="card"><a href="/x"><h3>X</h3></a></li>')
        assert not any(i.code == "LINK_STACKED_DUPLICATE" for i in check_page(page))


# ── E6.3 — suppression and calibration ─────────────────────────────────────


class TestSuppressionAndCalibration:
    def test_e6_3a_suppresses_empty_anchor(self):
        """One template defect must not be charged twice."""
        assert "LINK_EMPTY_ANCHOR" in _CLUSTER_SUPPRESSION["LINK_STACKED_DUPLICATE"]

    def test_e6_3c_scores_once_when_both_present(self):
        from api.services.job_store_base import compute_page_health

        both = compute_page_health([
            ("LINK_STACKED_DUPLICATE", _ISSUE_SCORING["LINK_STACKED_DUPLICATE"][0], "metadata"),
            ("LINK_EMPTY_ANCHOR", _ISSUE_SCORING["LINK_EMPTY_ANCHOR"][0], "metadata"),
        ])
        stacked_only = compute_page_health([
            ("LINK_STACKED_DUPLICATE", _ISSUE_SCORING["LINK_STACKED_DUPLICATE"][0], "metadata"),
        ])
        assert both == stacked_only

    def test_e6_3b_standalone_empty_anchor_unaffected(self):
        from api.services.job_store_base import compute_page_health

        alone = compute_page_health([
            ("LINK_EMPTY_ANCHOR", _ISSUE_SCORING["LINK_EMPTY_ANCHOR"][0], "metadata"),
        ])
        assert alone < 100, "an empty anchor on its own must still cost something"

    def test_e6_2_registry_entry_is_consistent(self):
        spec = _CATALOGUE["LINK_STACKED_DUPLICATE"]
        assert spec.category == "metadata", "sibling of ANCHOR_TEXT_GENERIC / LINK_EMPTY_ANCHOR"
        assert spec.severity == "info"
        assert spec.fixability == "developer_needed"

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
        group it reports must genuinely be 2+ anchors to one href.

        The container assertions were added 2026-09-01. Without them this test
        passed while the fixture produced TWO groups whose container was
        ``<main class="site-main post-8 … hentry">`` — the whole page. Internal
        consistency was never the thing in doubt; WHAT was called a card was.
        """
        soup = BeautifulSoup((FIXTURES / "livingsystems_home.html").read_text(), "lxml")
        for g in _find_stacked_links(soup, "https://livingsystems.ca/"):
            assert g["count"] >= 2
            assert len(g["accessible_names"]) == g["count"]
            assert g["href"].startswith("http")
            assert g["container_tag"] not in {"main", "body", "html"}
            assert "hentry" not in g["container_class"]


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

    def test_e6_1a_article_in_a_listing_is_a_container(self):
        """S3: <article> is a card when the page is a LISTING of them."""
        html = (
            '<article><a href="/x">A</a><a href="/x">B</a></article>'
            '<article><a href="/y">C</a></article>'
        )
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


# ── 2026-09-01 — the container over-match regression ───────────────────────
#
# The check shipped with a documented, load-bearing container requirement and a
# config entry ("entry") that defeated it: WordPress's post_class() puts `hentry`
# on the wrapper of essentially every page, `"entry" in "hentry"` is True under a
# substring test, and <main> became a card. E6 then meant "any URL linked twice
# anywhere on the page" — 28 of 31 findings on livingsystems.ca were that.
#
# The 21 tests above did not catch it because every fixture was hand-written
# minimal markup: not one contained a real WordPress wrapper. So these fixtures
# are copied from the live markup instead of invented to suit the design.
#
# Spec: docs/pending/2026-09-01_stacked-links-container-overmatch.md

# A page has to have a page around the card for the text-share guard to mean
# anything (S1.3). Real body copy, not lorem, so the length is honest.
_FILLER = "<p>" + ("Bowen family systems theory content for this page. " * 40) + "</p>"

# Verbatim from livingsystems.ca/clinical-training, job fe38deb8.
_WP_MAIN = "site-main post-350 page type-page status-publish hentry"
_ELEMENTOR_SINGLE = (
    "elementor elementor-12156 elementor-location-single post-12163 "
    "conference type-conference status-publish hentry"
)
_JET_CARD = (
    "jet-listing-grid__item jet-listing-dynamic-post-12168 "
    "jet-listing-grid__list_item elementor-dcss-6558074663865184"
)


def _page(inner: str) -> str:
    return f"<html><body>{inner}{_FILLER}</body></html>"


class TestPageLevelContainersAreNotCards:
    def test_wordpress_hentry_wrapper_is_not_a_card(self):
        """THE regression. Two DIFFERENT cards sharing a destination, inside
        <main class="... hentry"> — the exact shape the user could not find."""
        html = _page(
            f'<main class="{_WP_MAIN}">'
            '  <div class="x"><a href="/training/application-seminar/">'
            '      Application Seminar Learn more</a></div>'
            '  <div class="x"><a href="/training/application-seminar/">'
            '      Application of Bowen Family Systems Theory Learn more</a></div>'
            "</main>"
        )
        assert _groups(html) == []

    def test_entry_content_wrapper_is_not_a_card(self):
        """The second route in: `entry-content` survives token matching."""
        html = _page(
            '<div class="entry-content">'
            '  <a href="/x">One</a><a href="/x">Two</a>'
            "</div>"
        )
        assert _groups(html) == []

    def test_elementor_single_post_wrapper_is_not_a_card(self):
        html = _page(
            f'<div class="{_ELEMENTOR_SINGLE}">'
            '  <a href="/x">One</a><a href="/x">Two</a>'
            "</div>"
        )
        assert _groups(html) == []

    def test_lone_article_is_not_a_card(self):
        """S3: on a single-post template <article> wraps the whole post."""
        html = _page(
            '<article class="post"><a href="/x">One</a><a href="/x">Two</a></article>'
        )
        assert _groups(html) == []

    def test_container_over_link_budget_is_not_a_card(self):
        """S1.2: a 'card' holding 16 links is a page."""
        links = "".join(f'<a href="/p{i}">L{i}</a>' for i in range(14))
        html = _page(
            f'<li class="card">{links}<a href="/x">One</a><a href="/x">Two</a></li>'
        )
        assert _groups(html) == []

    def test_container_holding_half_the_page_text_is_not_a_card(self):
        """S1.3: a container that IS most of the page's text is not a card."""
        bulk = "Substantial card body copy repeated to dominate the page. " * 40
        html = (
            "<html><body>"
            f'<div class="card"><a href="/x">One</a><a href="/x">Two</a><p>{bulk}</p></div>'
            "<p>A short outer paragraph.</p>"
            "</body></html>"
        )
        assert _groups(html) == []

    def test_main_is_never_a_card_whatever_its_classes(self):
        """S1.1 holds even if a theme puts a card class on <main>."""
        html = _page(
            '<main class="card"><a href="/x">One</a><a href="/x">Two</a></main>'
        )
        assert _groups(html) == []

    def test_role_main_is_never_a_card(self):
        html = _page(
            '<div role="main" class="card"><a href="/x">A</a><a href="/x">B</a></div>'
        )
        assert _groups(html) == []


class TestTruePositivesSurvive:
    """A fix that silenced the check entirely would pass every test above."""

    def test_genuine_jet_listing_card_still_flagged(self):
        """The 3 real findings in job fe38deb8, on their real class string."""
        html = _page(
            f'<main class="{_WP_MAIN}"><ul>'
            f'  <li class="{_JET_CARD}">'
            '     <a href="/events/1">Overlay</a><a href="/events/1">Title</a>'
            "  </li></ul></main>"
        )
        groups = _groups(html)
        assert len(groups) == 1
        assert groups[0]["href"] == "https://example.com/events/1"
        assert groups[0]["container_tag"] == "li"

    def test_page_level_match_does_not_mask_inner_card_groups(self):
        """The suppression half of the defect.

        `seen_containers` de-duplicates by container, so when <main> matched it
        consumed every anchor on the page and the genuine card inside it was
        never reported. A count-based assertion would not catch this: the old
        code returned ONE group here too — the wrong one.
        """
        html = _page(
            f'<main class="{_WP_MAIN}">'
            '  <div class="other"><a href="/shared">Elsewhere on the page</a></div>'
            f'  <li class="{_JET_CARD}">'
            '     <a href="/shared">Overlay</a><a href="/shared">Title</a>'
            "  </li></main>"
        )
        groups = _groups(html)
        assert len(groups) == 1
        assert groups[0]["container_tag"] == "li", "the CARD group, not the page group"
        assert groups[0]["count"] == 2, "the third anchor is outside the card"


class TestClassMatchingIsTokenBounded:
    @pytest.mark.parametrize(
        "cls,pattern,expected",
        [
            ("hentry", "entry", False),        # the bug
            ("entry", "entry", True),
            ("entry-card", "entry", True),
            ("entry__wrap", "entry", True),
            ("elementor-posts", "elementor-post", False),   # the grid, not a card
            ("elementor-post__card", "elementor-post", True),
            ("placard", "card", False),
            ("card", "card", True),
        ],
    )
    def test_class_matches_pattern(self, cls, pattern, expected):
        from api.crawler.parser import _class_matches_pattern

        assert _class_matches_pattern(cls, pattern) is expected

    def test_elementor_posts_grid_is_not_matched_as_a_single_card(self):
        """The grid wrapper holds all the cards; it is not one of them."""
        html = _page(
            '<div class="elementor-posts">'
            '  <div class="p"><a href="/x">One</a></div>'
            '  <div class="p"><a href="/x">Two</a></div>'
            "</div>"
        )
        assert _groups(html) == []

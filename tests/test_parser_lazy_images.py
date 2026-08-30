"""E1 — lazy-loaded image extraction.

Purpose: prove the parser sees images whose real URL lives in a data-* attribute
         because `src` holds a data: placeholder (Smush / Elementor / WP Rocket).
Spec:    docs/pending/2026-08-29_E1-lazy-loaded-image-extraction.md
Tests:   this file

The real-artifact tests come first on purpose (P10/P19). A synthetic fixture
written as `<img src="https://example.com/a.jpg">` uses the idealised shape and
is exactly what let this bug ship — every consumer read `src`, every test
supplied one, and on a real Smush site the parser saw nothing at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from api.crawler.parser import (
    _count_img_missing_alt,
    _extract_image_data,
    _extract_image_urls,
    _find_img_missing_alt_srcs,
    _img_has_srcset,
    _resolve_img_src,
)

FIXTURES = Path(__file__).parent / "fixtures" / "lazy_images"
PAGE_URL = "https://livingsystems.ca/emotional-pain-and-suffering/"
HOME_URL = "https://livingsystems.ca/"


def _soup(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(), "lxml")


def _tag(html: str):
    return BeautifulSoup(html, "lxml").find("img")


# ── E1.2a / E1.3b — real artifacts (written first, P10) ─────────────────────


class TestRealSmushArtifacts:
    """The counts here were measured against the live pages on 2026-08-29 and
    are recorded in tests/fixtures/lazy_images/README.md."""

    def test_e1_2a_real_smush_page_yields_nine_images(self):
        soup = _soup("livingsystems_emotional_pain.html")
        images = _extract_image_data(soup, PAGE_URL)
        assert len(images) == 9, (
            "Pre-E1 this returned 0: every <img> on this page carries a data: "
            "placeholder in src with the real URL in data-src."
        )
        for img in images:
            assert img["url"].startswith("http"), img["url"]
            assert not img["url"].startswith("data:")

    def test_e1_2a_real_homepage_yields_eleven_images(self):
        soup = _soup("livingsystems_home.html")
        assert len(_extract_image_data(soup, HOME_URL)) == 11

    def test_e1_2a_image_urls_match_image_data(self):
        """_extract_image_urls (broken-image checks) sees the same set."""
        soup = _soup("livingsystems_emotional_pain.html")
        assert len(_extract_image_urls(soup, PAGE_URL)) == 9

    def test_e1_3b_real_pages_have_no_unusable_alt(self):
        """Neither real page has an image without usable alt text.

        These assertions read 10 and 8 until 2026-08-30, counting every
        ``alt=""`` as missing. WCAG 2.2 §1.1.1 makes ``alt=""`` the PRESCRIBED
        decorative signal, so those pages were correct and the crawler reported
        156 findings against a site whose alt text was complete.

        Expected values were re-derived independently of the parser — a regex
        over the raw fixture — never from crawler output (P32). Homepage: 11
        images, 10 ``alt=""``, 1 with text, 0 absent, 0 whitespace-only.
        Article: 9 images, 8 ``alt=""``, 1 with text.
        """
        assert _count_img_missing_alt(_soup("livingsystems_home.html")) == 0
        assert _count_img_missing_alt(_soup("livingsystems_emotional_pain.html")) == 0

    def test_e1_3b_lazy_image_without_alt_still_resolves_its_url(self):
        """The E1 regression this class exists for, kept alive.

        Pre-E1, ``_find_img_missing_alt_srcs`` read only ``src`` — a data: URI on
        a lazy-loaded image — so it returned [] and the finding was silenced with
        no evidence. The real fixtures can no longer exercise that path (they
        have no unusable-alt images), so the guard uses the same Smush shape with
        the alt attribute genuinely absent.
        """
        soup = BeautifulSoup(
            '<img src="data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=" '
            'data-src="/wp-content/uploads/2026/04/real.jpg" class="lazyload">',
            "lxml",
        )
        assert _count_img_missing_alt(soup) == 1
        srcs = _find_img_missing_alt_srcs(soup, HOME_URL)
        assert srcs == ["https://livingsystems.ca/wp-content/uploads/2026/04/real.jpg"], (
            "pre-E1 this was [] and the finding was dropped"
        )

    def test_e1_2b_real_lazy_images_marked_lazy(self):
        soup = _soup("livingsystems_emotional_pain.html")
        images = _extract_image_data(soup, PAGE_URL)
        assert all(i["is_lazy_loaded"] for i in images), (
            "a data: placeholder in src IS a lazy-load marker"
        )


# ── E1.1 — the resolver ─────────────────────────────────────────────────────


class TestResolveImgSrc:
    def test_e1_1a_data_src_resolved_over_data_uri(self):
        tag = _tag('<img src="data:image/svg+xml;base64,AAA" data-src="/real.jpg">')
        assert _resolve_img_src(tag, HOME_URL) == "https://livingsystems.ca/real.jpg"

    def test_e1_1b_real_src_wins(self):
        tag = _tag('<img src="/actual.jpg" data-src="/lazy.jpg">')
        assert _resolve_img_src(tag, HOME_URL) == "https://livingsystems.ca/actual.jpg"

    @pytest.mark.parametrize(
        "attr", ["data-src", "data-lazy-src", "data-original", "data-lazy", "data-echo"]
    )
    def test_e1_1a_every_lazy_attribute_supported(self, attr):
        tag = _tag(f'<img src="data:image/gif;base64,R0lGOD" {attr}="/x.jpg">')
        assert _resolve_img_src(tag, HOME_URL) == "https://livingsystems.ca/x.jpg"

    def test_e1_1c_srcset_fallback(self):
        tag = _tag('<img src="data:image/gif;base64,R0" srcset="/small.jpg 300w, /big.jpg 800w">')
        assert _resolve_img_src(tag, HOME_URL) == "https://livingsystems.ca/small.jpg"

    def test_e1_1c_data_srcset_fallback(self):
        tag = _tag('<img src="data:image/gif;base64,R0" data-srcset="/s.jpg 300w">')
        assert _resolve_img_src(tag, HOME_URL) == "https://livingsystems.ca/s.jpg"

    @pytest.mark.parametrize(
        "html",
        [
            '<img alt="no url at all">',
            '<img src="data:image/gif;base64,R0lGOD">',
            '<img src="">',
            '<img src="data:x" data-src="data:y">',
            '<img src="mailto:someone@example.com">',
            '<img src="javascript:void(0)">',
        ],
    )
    def test_e1_1d_unresolvable_returns_none(self, html):
        assert _resolve_img_src(_tag(html), HOME_URL) is None

    def test_e1_1d_never_raises_on_malformed(self):
        tag = _tag('<img src="ht tp://bad url" data-src="::::">')
        assert _resolve_img_src(tag, HOME_URL) is None or isinstance(
            _resolve_img_src(tag, HOME_URL), str
        )

    def test_e1_1d_relative_without_page_url_is_dropped(self):
        """No base URL means no absolute URL — dropped, not emitted relative."""
        assert _resolve_img_src(_tag('<img src="/x.jpg">'), "") is None


class TestSrcsetDetection:
    def test_e1_2b_data_srcset_counts_as_srcset(self):
        assert _img_has_srcset(_tag('<img data-srcset="/a.jpg 1x">')) is True

    def test_e1_2b_plain_srcset_still_counts(self):
        assert _img_has_srcset(_tag('<img srcset="/a.jpg 1x">')) is True

    def test_e1_2b_no_srcset_is_false(self):
        assert _img_has_srcset(_tag('<img src="/a.jpg">')) is False


# ── E1.3c — adversarial (P7) ────────────────────────────────────────────────


class TestAdversarial:
    def test_e1_3c_decorative_images_do_not_inflate_missing_alt(self):
        """A decorative image carries alt="" by design and must NOT be counted.

        This test asserted ``== 1`` until 2026-08-30 — under an "adversarial"
        heading, on the hardest possible input, with a docstring saying the
        behaviour was deliberate. It was wrong, and pinning it made the defect a
        defended invariant (P32). ``role="presentation"`` is the W3C's explicit
        "ignore this image"; ``alt=""`` is WCAG 2.2 §1.1.1's decorative signal.
        Both say: not a finding.

        The oracle here is the standard, not this codebase.
        """
        soup = BeautifulSoup(
            '<img src="data:image/gif;base64,R0" data-src="/spacer.gif" alt="" '
            'role="presentation">',
            "lxml",
        )
        assert _count_img_missing_alt(soup) == 0
        assert _find_img_missing_alt_srcs(soup, HOME_URL) == []

    def test_e1_3c_whitespace_only_alt_is_still_a_finding(self):
        """Adversarial in the other direction: ``alt=" "`` is a non-empty string,
        so it is neither an accessible name nor the empty-string decorative
        signal. Screen readers announce it inconsistently and accessibility
        tooling flags it. The fix for alt="" must not sweep this in with it."""
        soup = BeautifulSoup('<img src="/a.jpg" alt=" ">', "lxml")
        assert _count_img_missing_alt(soup) == 1

    def test_e1_3c_image_with_alt_never_reported(self):
        soup = BeautifulSoup(
            '<img src="data:image/gif;base64,R0" data-src="/a.jpg" alt="A described image">',
            "lxml",
        )
        assert _count_img_missing_alt(soup) == 0
        assert _find_img_missing_alt_srcs(soup, HOME_URL) == []

    def test_e1_3c_svg_and_picture_sources_not_double_counted(self):
        """<picture><source> siblings must not create phantom image records —
        only the <img> itself is extracted."""
        soup = BeautifulSoup(
            '<picture><source srcset="/a.webp" type="image/webp">'
            '<img src="data:image/gif;base64,R0" data-src="/a.jpg" alt="x"></picture>',
            "lxml",
        )
        assert len(_extract_image_data(soup, HOME_URL)) == 1


class TestInlineDataImagesAreNotFlagged:
    """F9 (review) — an inline `data:` image is decorative, not "unresolvable".

    The E1.3 count-only branch fires when no URL could be resolved. A base64
    spacer or inline SVG icon has no URL by design, so it landed in that branch —
    where `ignored_image_patterns` operates on a URL list that is empty and
    therefore cannot suppress it. That is an unfixable, unsuppressible finding (P7).
    """

    def test_f9_inline_only_images_do_not_count(self):
        soup = BeautifulSoup(
            '<img src="data:image/svg+xml;base64,AAA">'
            '<img src="data:image/gif;base64,R0lGOD">',
            "lxml",
        )
        assert _count_img_missing_alt(soup) == 0

    def test_f9_lazy_image_with_a_real_data_src_still_counts(self):
        """The placeholder is inline but the real URL is not — still a finding."""
        soup = BeautifulSoup(
            '<img src="data:image/gif;base64,R0" data-src="/real.jpg">', "lxml"
        )
        assert _count_img_missing_alt(soup) == 1

    def test_f9_plain_image_without_alt_still_counts(self):
        soup = BeautifulSoup('<img src="/a.jpg">', "lxml")
        assert _count_img_missing_alt(soup) == 1

    def test_f9_inline_image_with_alt_is_irrelevant_either_way(self):
        soup = BeautifulSoup('<img src="data:image/gif;base64,R0" alt="A chart">', "lxml")
        assert _count_img_missing_alt(soup) == 0

    def test_f9_real_fixture_counts_unchanged(self):
        """The real pages carry no inline-only images, so the F9 inline-data fix
        must not move their numbers. Both are 0 unusable-alt images — see the
        fixture README table and test_e1_3b_real_pages_have_no_unusable_alt."""
        assert _count_img_missing_alt(_soup("livingsystems_home.html")) == 0
        assert _count_img_missing_alt(_soup("livingsystems_emotional_pain.html")) == 0


class TestConfigFailureIsLogged:
    def test_f13_stacked_link_config_failure_warns(self, caplog, monkeypatch):
        """F13 (review) — a silent `except: return []` would disable E6 site-wide
        and be indistinguishable from "no stacked links found" (P2). Matches the
        sibling handler in cross_page._check_entity_values."""
        import logging

        from api.crawler import parser as parser_mod

        monkeypatch.setattr(
            parser_mod, "_link_patterns_cfg",
            lambda: (_ for _ in ()).throw(RuntimeError("config gone")),
        )
        with caplog.at_level(logging.WARNING):
            groups = parser_mod._find_stacked_links(
                BeautifulSoup('<li class="card"><a href="/x">A</a><a href="/x">B</a></li>', "lxml"),
                "https://x/",
            )
        assert groups == []
        assert "link_patterns_config_unavailable" in caplog.text

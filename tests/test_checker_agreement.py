"""V5 — implementations of the same predicate must agree.

Purpose: catch the failure class where two code paths in the same crawl compute
         the same fact and reach opposite conclusions. Needs no external oracle,
         so it is the cheapest correctness check available — and it catches the
         cases where one path already knows the right rule.
Spec:    docs/pending/2026-08-30_check-validation-program.md#V5
Tests:   this file

Both false-positive classes found in 2026-08 were of exactly this shape:

  * ORPHAN_PAGE vs HIGH_CRAWL_DEPTH disagreed about what to do with incomplete
    input — one skipped, one guessed (fixed in cb421cf).
  * The page path called `alt=""` "missing alt" (156 findings on livingsystems.ca)
    while the image path called the same 15 images decorative (0 findings).

A registry of duplicate predicates is maintained below. Adding a second
implementation of an existing predicate without adding it here is the drift this
file exists to prevent (P32: the suite must not merely agree with itself — but
where two implementations exist, disagreement is a defect in at least one).
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from api.crawler.parser import (
    _count_img_missing_alt,
    _detect_decorative,
    _find_img_missing_alt_srcs,
)

HOME = "https://example.com/"


def _tag(html: str):
    return BeautifulSoup(html, "lxml").find("img")


def _soup(html: str):
    return BeautifulSoup(html, "lxml")


# ── Predicate: "does this image lack usable alt text?" ──────────────────────
# Implementations:
#   A. parser._count_img_missing_alt / _find_img_missing_alt_srcs  (page path)
#   B. parser._detect_decorative -> image_analyzer._check_alt_text (image path)
#
# WCAG 2.2 §1.1.1: alt="" is the PRESCRIBED markup for a decorative image, not a
# defect. Implementation B already encodes this; A did not.

ALT_CASES = [
    # (html, alt_is_genuinely_missing, description)
    ('<img src="/a.jpg">', True, "no alt attribute at all"),
    # HTML Living Standard: an empty attribute value IS the empty string, so
    # `<img alt>` is identical to alt="" and means decorative. Verified: bs4
    # parses both to ''.
    ('<img src="/a.jpg" alt>', False, "valueless alt attribute == alt=\"\""),
    ('<img src="/a.jpg" alt=" ">', True, "whitespace-only alt"),
    ('<img src="/a.jpg" alt="">', False, 'empty alt="" — WCAG decorative'),
    ('<img src="/a.jpg" alt="" role="presentation">', False, "empty alt + role=presentation"),
    ('<img src="/a.jpg" alt="" aria-hidden="true">', False, "empty alt + aria-hidden"),
    ('<img src="/a.jpg" alt="A described image">', False, "real alt text"),
]


class TestAltPredicateAgreement:
    @pytest.mark.parametrize("html,missing,desc", ALT_CASES)
    def test_v5_1_alt_paths_agree(self, html, missing, desc):
        """The page path and the image path must reach the same verdict.

        The image path flags an image only when it is NOT decorative, so its
        verdict is `not _detect_decorative(tag)` combined with an empty alt.
        """
        tag = _tag(html)
        alt = tag.get("alt")
        alt_is_blank = alt is None or (isinstance(alt, str) and not alt.strip())

        page_path_flags = _count_img_missing_alt(_soup(html)) == 1
        # image_analyzer._check_alt_text: `if not img.is_decorative:` then blank-alt
        image_path_flags = alt_is_blank and not _detect_decorative(tag)

        assert page_path_flags == image_path_flags, (
            f"paths disagree on {desc!r}: page={page_path_flags} image={image_path_flags}"
        )

    @pytest.mark.parametrize("html,missing,desc", ALT_CASES)
    def test_v5_1_page_path_matches_the_standard(self, html, missing, desc):
        """Oracle is WCAG 2.2 §1.1.1, not our own output (P32)."""
        assert _count_img_missing_alt(_soup(html)) == (1 if missing else 0), desc

    @pytest.mark.parametrize("html,missing,desc", ALT_CASES)
    def test_v5_1_srcs_list_matches_the_count(self, html, missing, desc):
        """The count and the evidence list are a third pair that must agree —
        a page reporting `missing_alt_count: 8` with a list naming other images
        is the same drift one layer down."""
        srcs = _find_img_missing_alt_srcs(_soup(html), HOME)
        assert (len(srcs) == 1) == missing, f"{desc}: srcs={srcs}"


class TestDuplicatePredicateRegistry:
    """Every predicate with more than one implementation needs an agreement
    test above. This guard fails when the registry and the tests drift."""

    REGISTERED = {
        "image_alt_missing": "TestAltPredicateAgreement",
    }

    def test_v5_2_every_registered_predicate_has_an_agreement_test(self):
        import inspect
        import sys

        module = sys.modules[__name__]
        classes = {name for name, _ in inspect.getmembers(module, inspect.isclass)}
        missing = {p: c for p, c in self.REGISTERED.items() if c not in classes}
        assert not missing, f"registered predicates with no agreement test: {missing}"

"""IMG_DUPLICATE_CONTENT asks about the asset, not the request.

Spec:  docs/functional-specification.md (IM1)#IM1
Tests: this file

Images are queued by exact URL string, so `logo.png` and `logo.png?ver=6.4`
are two entries. Before IM1 nothing hashed the bodies, so the check could not
fire on them; once the dimension pass started hashing, they hash identically
and the check reported a duplicate the user cannot act on. The reference
site's own media library serves Photon URLs (`?fit=300%2C300`) of exactly
this shape.
"""
from __future__ import annotations

import pytest

from api.crawler.image_analyzer import _check_duplicates, _image_identity
from api.models.image import ImageInfo


def _img(url, h="abc123"):
    return ImageInfo(url=url, page_url="https://e.test/p", job_id="j",
                     content_hash=h)


class TestIdentity:
    @pytest.mark.parametrize("a,b", [
        ("https://e.test/logo.png", "https://e.test/logo.png?ver=6.4"),
        ("https://e.test/logo.png?v=2", "https://e.test/logo.png?v=9"),
        ("https://i1.wp.com/e/l.png?fit=300%2C300", "https://i1.wp.com/e/l.png"),
        ("https://e.test/a.png?w=300&h=200", "https://e.test/a.png"),
    ])
    def test_noise_params_do_not_change_identity(self, a, b):
        assert _image_identity(a) == _image_identity(b)

    @pytest.mark.parametrize("a,b", [
        ("https://e.test/one.png", "https://e.test/two.png"),
        ("https://e.test/a.png?id=7", "https://e.test/a.png?id=8"),
        ("https://e.test/x/a.png", "https://e.test/y/a.png"),
        ("https://one.test/a.png", "https://two.test/a.png"),
    ])
    def test_meaningful_differences_are_kept(self, a, b):
        assert _image_identity(a) != _image_identity(b), (
            "two genuinely different assets were collapsed to one identity, "
            "which would hide a real duplicate")


class TestCheck:
    def test_cache_busted_variant_is_not_a_duplicate(self):
        issues = _check_duplicates(
            [_img("https://e.test/logo.png"),
             _img("https://e.test/logo.png?ver=6.4")], "j")
        assert issues == [], (
            "the same file requested twice under a cache-busted URL was "
            "reported as a duplicate upload")

    def test_photon_resize_variant_is_not_a_duplicate(self):
        issues = _check_duplicates(
            [_img("https://i1.wp.com/e/l.png?fit=300%2C300"),
             _img("https://i1.wp.com/e/l.png?fit=150%2C150")], "j")
        assert issues == []

    def test_a_real_duplicate_still_reports(self):
        """The normalisation must not disable the check it bounds."""
        issues = _check_duplicates(
            [_img("https://e.test/hero.png"),
             _img("https://e.test/copies/hero-2.png")], "j")
        assert len(issues) == 1
        assert issues[0].code == "IMG_DUPLICATE_CONTENT"

    def test_occurrence_count_reflects_distinct_assets(self):
        issues = _check_duplicates(
            [_img("https://e.test/a.png"),
             _img("https://e.test/a.png?ver=2"),
             _img("https://e.test/b.png")], "j")
        assert len(issues) == 1, "three URLs, two assets, one duplicate"
        assert issues[0].extra["total_occurrences"] == 2, (
            "the count included a cache-busted variant of the same asset")

    def test_different_content_is_never_a_duplicate(self):
        issues = _check_duplicates(
            [_img("https://e.test/a.png", h="aaa"),
             _img("https://e.test/b.png", h="bbb")], "j")
        assert issues == []

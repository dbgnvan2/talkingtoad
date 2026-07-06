"""R2.x detection-precision fixes (audit remediation, 2026-07-04).

Spec: docs/pending/OLD/2026-07-04_r2x-detection-precision.md
No scoring changes — these verify what fires / what's reported.
"""

from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from api.crawler.parser import (
    _AI_BOT_NAMES,
    _count_mixed_content_active,
    _count_mixed_content_passive,
    _find_empty_anchors,
)
from api.crawler.normaliser import is_expected_disallow, looks_like_production
from api.crawler.checkers.security import _check_security
from api.crawler.checkers.cross_page import check_cross_page
from api.crawler.image_analyzer import _check_performance, analyze_batch
from api.services.ai_bots import AI_BOTS, normalize_user_agent
from api.models.image import ImageInfo


# ── #1 LINK_EMPTY_ANCHOR accessible name ──────────────────────────────────────
def test_anchor_with_aria_labelledby_not_flagged():
    soup = BeautifulSoup('<a href="/x" aria-labelledby="lbl"><svg></svg></a>', "lxml")
    assert _find_empty_anchors(soup, "https://e.com") == []


def test_anchor_with_title_not_flagged():
    soup = BeautifulSoup('<a href="/x" title="Home"><svg></svg></a>', "lxml")
    assert _find_empty_anchors(soup, "https://e.com") == []


def test_bare_icon_anchor_still_flagged():
    soup = BeautifulSoup('<a href="/z"><svg></svg></a>', "lxml")
    flagged = _find_empty_anchors(soup, "https://e.com")
    assert [f["href"] for f in flagged] == ["https://e.com/z"]


# ── #2 MIXED_CONTENT active/passive split ─────────────────────────────────────
def test_mixed_content_active_passive_counts():
    soup = BeautifulSoup(
        '<script src="http://x/a.js"></script><iframe src="http://x/f"></iframe>'
        '<link rel="stylesheet" href="http://x/s.css"><img src="http://x/i.png">',
        "lxml",
    )
    assert _count_mixed_content_active(soup, "https://e.com") == 3  # script+iframe+css
    assert _count_mixed_content_passive(soup, "https://e.com") == 1  # img


def test_mixed_content_extra_reports_breakdown():
    page = SimpleNamespace(
        url="https://e.com/p", mixed_content_count=4,
        mixed_content_active_count=3, mixed_content_passive_count=1,
        has_hsts=True, unsafe_cross_origin_count=0,
    )
    issues: list = []
    _check_security(page, issues, hsts_checked_hosts=set())
    mc = next(i for i in issues if i.code == "MIXED_CONTENT")
    assert mc.extra["active_count"] == 3
    assert mc.extra["passive_count"] == 1
    assert mc.extra["has_active"] is True


# ── #3 image consequence-precedence ───────────────────────────────────────────
_CFG = {"max_image_size_kb": 100, "slow_load_threshold_ms": 500,
        "overscale_ratio": 2.0, "bpp_threshold": 1.0}


def test_oversized_suppresses_slow_and_compression():
    # one bad hero: oversized + slow + poor bpp all "true" — only OVERSIZED fires
    img = ImageInfo(url="https://e.com/hero.png", page_url="https://e.com/p", job_id="job",
                    file_size_bytes=500 * 1024, load_time_ms=2000,
                    width=4000, height=3000)
    codes = [i.code for i in _check_performance(img, _CFG, "job")]
    assert "IMG_OVERSIZED" in codes
    assert "IMG_SLOW_LOAD" not in codes
    assert "IMG_POOR_COMPRESSION" not in codes


def test_slow_load_fires_when_no_root_cause():
    img = ImageInfo(url="https://e.com/ok.png", page_url="https://e.com/p", job_id="job",
                    file_size_bytes=10 * 1024, load_time_ms=2000)
    codes = [i.code for i in _check_performance(img, _CFG, "job")]
    assert "IMG_SLOW_LOAD" in codes


def test_likely_lcp_marks_heaviest_image():
    imgs = [
        ImageInfo(url="https://e.com/small.png", page_url="https://e.com/p", job_id="job", file_size_bytes=300 * 1024),
        ImageInfo(url="https://e.com/big.png", page_url="https://e.com/p", job_id="job", file_size_bytes=900 * 1024),
    ]
    _, issues = analyze_batch(imgs, config=_CFG, job_id="job")
    lcp = [i for i in issues if i.extra and i.extra.get("likely_lcp")]
    assert lcp and all(i.extra["image_url"] == "https://e.com/big.png" for i in lcp)


# ── #4 ORPHAN_PAGE caveat ─────────────────────────────────────────────────────
def test_orphan_page_carries_dynamic_caveat():
    pages = [
        SimpleNamespace(url="https://e.com/", title="Home", links=[],
                        redirect_url=None, status_code=200, canonical_url=None,
                        meta_description=None),
        SimpleNamespace(url="https://e.com/lonely", title="Lonely", links=[],
                        redirect_url=None, status_code=200, canonical_url=None,
                        meta_description=None),
    ]
    issues = check_cross_page(pages, start_url="https://e.com")
    orphan = next(i for i in issues if i.code == "ORPHAN_PAGE")
    assert "caveat" in orphan.extra and "JavaScript" in orphan.extra["caveat"]


# ── #5 staging awareness (helper) ─────────────────────────────────────────────
@pytest.mark.parametrize("url,prod", [
    ("https://livingsystems.ca/x", True),
    ("https://www.example.org/", True),
    ("https://staging.example.com/", False),
    ("https://dev.example.com/", False),
    ("https://example.test/", False),
    ("http://localhost:8000/", False),
])
def test_looks_like_production(url, prod):
    assert looks_like_production(url) is prod


# ── #7 AI-bot table unified ───────────────────────────────────────────────────
def test_x_robots_ai_bot_names_derived_from_ai_bots():
    for name in AI_BOTS:
        assert normalize_user_agent(name) in _AI_BOT_NAMES
    assert "claude-user" in _AI_BOT_NAMES  # was missing from the old hand-list


# ── #8 ROBOTS_BLOCKED expected-disallow allow-list (helper) ───────────────────
@pytest.mark.parametrize("url,expected", [
    ("https://x.com/cart/", True),
    ("https://x.com/checkout", True),
    ("https://x.com/my-account/orders", True),
    ("https://x.com/shop?add-to-cart=42", True),
    ("https://x.com/products?orderby=price", True),
    ("https://x.com/?s=hello", True),
    ("https://x.com/about", False),
    ("https://x.com/services/counselling", False),
])
def test_is_expected_disallow(url, expected):
    assert is_expected_disallow(url) is expected


# ── #6 freshness page-type awareness ──────────────────────────────────────────
from api.crawler.issue_checker import check_page  # noqa: E402
from tests.test_issue_checker import _page  # noqa: E402

_OLD_LM = "Mon, 01 Jan 2018 00:00:00 GMT"  # ~8 years before the test's "now"


def test_content_stale_exempts_evergreen_page(monkeypatch):
    monkeypatch.setattr("api.crawler.issue_checker.infer_page_type", lambda p: "team_member")
    page = _page(url="https://e.com/team/jane", last_modified=_OLD_LM)
    codes = {i.code for i in check_page(page)}
    assert "CONTENT_STALE" not in codes  # team_member = never stale


def test_content_stale_fires_on_old_article(monkeypatch):
    monkeypatch.setattr("api.crawler.issue_checker.infer_page_type", lambda p: "article")
    page = _page(url="https://e.com/blog/post", last_modified=_OLD_LM)
    codes = {i.code for i in check_page(page)}
    assert "CONTENT_STALE" in codes  # article cadence 12mo, page is years old


def test_content_stat_outdated_exempts_team_member(monkeypatch):
    monkeypatch.setattr("api.crawler.issue_checker.infer_page_type", lambda p: "team_member")
    page = _page(url="https://e.com/team/jane", word_count=800)
    page.first_1500_words = "Jane joined us in 2018 and has led the program since."
    codes = {i.code for i in check_page(page)}
    assert "CONTENT_STAT_OUTDATED" not in codes

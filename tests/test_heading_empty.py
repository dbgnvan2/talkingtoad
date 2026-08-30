"""AF3 — lxml's non-spec block-in-heading split must not invent empty headings.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF3
Audit: docs/audit/2026-08-30_full-check-audit.md (F14)

Page builders emit `<h3><p>Text</p></h3>` routinely. lxml (libxml2, a pre-HTML5
parser) closes the heading at the `<p>`, producing an empty `<h3>`. The HTML5
parsing algorithm does NOT close a heading on a `<p>` start tag, so browsers and
Google see the text. Measured on the identical fragment:

    lxml         -> ''
    html.parser  -> 'Practicum Student'

17 findings on livingsystems.ca; 12 of 182 cached pages carry the nesting.
"""
from __future__ import annotations

import pathlib

from bs4 import BeautifulSoup

from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import check_page
from api.crawler.parser import parse_page

BASE = "https://example.com/"
FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "lazy_images"


def _page(body: str):
    html = ("<!DOCTYPE html><html lang='en'><head>"
            "<title>A Reasonably Long Page Title Here</title>"
            "<meta name='description' content='A description long enough to pass the checks here.'>"
            f"</head><body>{body}<p>" + " ".join(["word"] * 400) + "</p></body></html>")
    return parse_page(
        FetchResult(url=BASE, final_url=BASE, status_code=200, headers={},
                    html=html, content_type="text/html"),
        BASE, is_homepage=True)


def _outline(body):
    return _page(body).headings_outline


def test_af3_lxml_really_does_drop_the_text():
    """Pin the upstream behaviour this fix exists for, so the fix is not
    silently redundant if the parser is ever changed."""
    frag = '<h3 class="t"><p>Practicum Student</p></h3>'
    assert BeautifulSoup(frag, "lxml").find("h3").get_text(strip=True) == ""
    assert BeautifulSoup(frag, "html.parser").find("h3").get_text(strip=True) == "Practicum Student"


def test_af3_heading_wrapping_a_paragraph_is_not_empty():
    outline = _outline('<h3 class="elementor-heading-title"><p>Practicum Student</p></h3>')
    assert [e["text"] for e in outline] == ["Practicum Student"]


def test_af3_heading_wrapping_a_list_is_not_empty():
    assert [e["text"] for e in _outline("<h2><ul><li>Our Services</li></ul></h2>")] == ["Our Services"]


def test_af3_genuinely_empty_heading_is_still_flagged():
    """Adversarial: the fix must not amount to disabling the check."""
    assert [e["text"] for e in _outline('<h3 class="t"></h3>')] == [""]
    assert any(i.code == "HEADING_EMPTY" for i in check_page(_page('<h1>Real</h1><h3 class="t"></h3>')))


def test_af3_recovered_text_is_matched_to_the_right_level_in_order():
    outline = _outline("<h2>Real</h2><h3><p>Wrapped</p></h3><h4></h4>")
    assert [(e["level"], e["text"]) for e in outline] == [(2, "Real"), (3, "Wrapped"), (4, "")]


def test_af3_normal_headings_are_unchanged():
    assert [e["text"] for e in _outline("<h2>Real Heading</h2>")] == ["Real Heading"]


def test_af3_real_fixture_page_reports_no_empty_heading():
    """Regression on a real saved page from the customer's site."""
    html = (FIXTURES / "livingsystems_home.html").read_text()
    page = parse_page(
        FetchResult(url="https://livingsystems.ca/", final_url="https://livingsystems.ca/",
                    status_code=200, headers={}, html=html, content_type="text/html"),
        "https://livingsystems.ca/", is_homepage=True)
    empty = [e for e in page.headings_outline if not e["text"]]
    assert empty == [], f"phantom empty headings from parser repair: {empty}"

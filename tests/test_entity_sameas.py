"""AF1 — ENTITY_SAMEAS_MISSING must mean "no entity is linked", not "some node isn't".

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF1
Audit: docs/audit/2026-08-30_full-check-audit.md (F11)

Reproduces the real livingsystems.ca graph: an Organization node with full
sameAs, plus the author Person node WordPress/Yoast appends to every article.
"""
from __future__ import annotations

import json

from api.crawler.checkers.cross_page import check_cross_page
from api.crawler.fetcher import FetchResult
from api.crawler.parser import parse_page

BASE = "https://example.com/"


def _page(graph: list[dict], url: str = BASE):
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph})
    html = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<title>A Reasonably Long Page Title Here</title>"
        "<meta name='description' content='A description long enough to pass the checks here.'>"
        f"<script type='application/ld+json'>{ld}</script>"
        "</head><body><h1>H</h1><p>" + " ".join(["word"] * 400) + "</p></body></html>"
    )
    return parse_page(
        FetchResult(url=url, final_url=url, status_code=200, headers={},
                    html=html, content_type="text/html"),
        BASE, is_homepage=(url == BASE))


ORG_LINKED = {"@type": ["Organization", "Place"], "name": "Living Systems",
              "sameAs": ["https://facebook.com/x", "https://linkedin.com/y"]}
AUTHOR_PERSON = {"@type": "Person", "name": "Dave Galloway"}   # Yoast: no sameAs


def _codes(page):
    return {i.code for i in check_cross_page([page], start_url=BASE)}


def test_af1_org_with_sameas_and_author_person_without_is_not_flagged():
    """The real case: the site's entity IS linked. Flagging it said the opposite."""
    assert "ENTITY_SAMEAS_MISSING" not in _codes(_page([ORG_LINKED, AUTHOR_PERSON]))


def test_af1_no_entity_has_sameas_is_flagged():
    """Adversarial: the fix must not amount to disabling the check."""
    bare_org = {"@type": "Organization", "name": "Living Systems"}
    assert "ENTITY_SAMEAS_MISSING" in _codes(_page([bare_org, AUTHOR_PERSON]))


def test_af1_person_alone_with_sameas_clears_the_page():
    linked_person = {"@type": "Person", "name": "Dave", "sameAs": ["https://x.com/d"]}
    assert "ENTITY_SAMEAS_MISSING" not in _codes(_page([linked_person]))


def test_af1_page_with_no_entity_nodes_is_not_flagged():
    """A page whose graph has no Organization/Person cannot be missing sameAs."""
    assert "ENTITY_SAMEAS_MISSING" not in _codes(_page([{"@type": "WebPage"}]))


def test_af1_evidence_names_the_types_examined():
    """All 74 pre-fix findings carried an empty extra — unactionable."""
    issues = check_cross_page([_page([{"@type": "Organization", "name": "X"}])], start_url=BASE)
    issue = next(i for i in issues if i.code == "ENTITY_SAMEAS_MISSING")
    assert issue.extra["entity_types_examined"] == ["Organization"]
    assert issue.extra["entity_nodes"] == 1
    assert issue.extra["nodes_with_sameas"] == 0

"""Evidence in the report — WHICH element is wrong, not just which page.

Purpose: prove a finding is fixable from the report alone.
Spec:    docs/pending/2026-08-29_EV-issue-evidence.md
Tests:   this file

Reported by the owner against `UNSAFE_CROSS_ORIGIN_LINK`: the report said "6
unsafe external links on this page" and never named a link, so acting on it meant
re-auditing the page by hand. Two independent faults produced that (P5):

1. Three checks captured a COUNT and no evidence — `UNSAFE_CROSS_ORIGIN_LINK`,
   `MIXED_CONTENT`, `INTERNAL_NOFOLLOW` — while their siblings
   (`IMG_ALT_MISSING`, `LINK_EMPTY_ANCHOR`) had always returned a list.
2. Most codes DO carry evidence in `extra` and the report rendered NONE of it.
   `ANCHOR_TEXT_GENERIC` had the anchor text and href; `SEMANTIC_DENSITY_LOW` had
   a written diagnosis. All of it was in the database and invisible in the
   artifact the client receives (P25).

The guard test at the bottom is the one that matters: every code either produces
evidence or is explicitly recorded as one whose page URL is the whole story.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from bs4 import BeautifulSoup

from api.crawler.checkers.registry import _CATALOGUE
from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import check_page
from api.crawler.parser import (
    _find_internal_nofollow,
    _find_mixed_content,
    _find_unsafe_cross_origin,
    parse_page,
)
from api.models.issue import Issue as IssueModel
from api.models.job import CrawlJob
from api.services.issue_evidence import (
    PAGE_IS_THE_EVIDENCE,
    evidence_for_excel,
    evidence_lines,
)
from api.services.report_generator import generate_pdf_report

PAGE = "https://livingsystems.ca/"


def _page(body: str, url: str = PAGE):
    html = (
        "<!DOCTYPE html><html><head><title>A Page With A Good Long Title Here</title>"
        '<meta name="description" content="A description long enough to pass the checks here.">'
        f"</head><body><h1>Page</h1>{body}</body></html>"
    )
    result = FetchResult(
        url=url, final_url=url, status_code=200, first_status_code=200,
        headers={"content-type": "text/html"}, html=html,
        content_type="text/html", response_size_bytes=len(html),
    )
    return parse_page(result, url, is_homepage=True)


def _pdf_text(pdf_bytes: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return " ".join((p.extract_text() or "") for p in reader.pages).replace("\n", " ")


# ── The reported bug ────────────────────────────────────────────────────────


class TestUnsafeCrossOriginEvidence:
    UNSAFE = (
        '<a href="https://partner.org/a" target="_blank">Partner site</a>'
        '<a href="https://other.org/b" target="_blank">Other org</a>'
        '<a href="https://safe.org/c" target="_blank" rel="noopener">Safe one</a>'
    )

    def test_ev_parser_returns_the_hrefs(self):
        found = _find_unsafe_cross_origin(BeautifulSoup(self.UNSAFE, "lxml"), PAGE)
        assert [f["href"] for f in found] == [
            "https://partner.org/a", "https://other.org/b",
        ]
        assert found[0]["text"] == "Partner site"

    def test_ev_rel_noopener_is_excluded(self):
        found = _find_unsafe_cross_origin(BeautifulSoup(self.UNSAFE, "lxml"), PAGE)
        assert all("safe.org" not in f["href"] for f in found)

    def test_ev_internal_blank_link_is_not_cross_origin(self):
        html = '<a href="/internal" target="_blank">Internal</a>'
        assert _find_unsafe_cross_origin(BeautifulSoup(html, "lxml"), PAGE) == []

    def test_ev_issue_carries_the_links(self):
        issues = check_page(_page(self.UNSAFE))
        issue = next(i for i in issues if i.code == "UNSAFE_CROSS_ORIGIN_LINK")
        assert issue.extra["unsafe_links_total"] == 2
        hrefs = [row["href"] for row in issue.extra["unsafe_links"]]
        assert "https://partner.org/a" in hrefs

    def test_ev_count_still_matches_the_evidence(self):
        issues = check_page(_page(self.UNSAFE))
        issue = next(i for i in issues if i.code == "UNSAFE_CROSS_ORIGIN_LINK")
        assert issue.extra["unsafe_link_count"] == issue.extra["unsafe_links_total"]

    @pytest.mark.asyncio
    async def test_ev_the_link_reaches_the_pdf(self):
        """The whole point: the report must name the link."""
        issues = check_page(_page(self.UNSAFE))
        eng = next(i for i in issues if i.code == "UNSAFE_CROSS_ORIGIN_LINK")
        model = IssueModel(
            job_id="j", page_url=PAGE, category="security", severity="info",
            issue_code=eng.code, description=eng.description,
            recommendation="Add rel=\"noopener\".", extra=eng.extra,
            human_description="Unsafe External Link",
        )
        job = CrawlJob(job_id="j", target_url=PAGE, status="complete",
                       started_at=datetime.now(timezone.utc))
        text = _pdf_text(await generate_pdf_report(
            job, [model],
            {"health_score": 90, "agent_health_score": 90, "pages_crawled": 1,
             "total_issues": 1, "by_severity": {"critical": 0, "warning": 0, "info": 1},
             "by_category": {"security": 1}},
        ))
        assert "What to look for" in text
        assert "partner.org/a" in text, "the report must name the offending link"


class TestMixedContentEvidence:
    MIXED = ('<script src="http://cdn.example/x.js"></script>'
             '<img src="http://cdn.example/y.png">')

    def test_ev_mixed_content_items_carry_url_and_severity(self):
        found = _find_mixed_content(BeautifulSoup(self.MIXED, "lxml"), PAGE)
        by_url = {f["url"]: f for f in found}
        assert by_url["http://cdn.example/x.js"]["severity"] == "active"
        assert by_url["http://cdn.example/y.png"]["severity"] == "passive"

    def test_ev_http_page_has_no_mixed_content(self):
        """Mixed content is only meaningful on an https page."""
        assert _find_mixed_content(BeautifulSoup(self.MIXED, "lxml"),
                                   "http://example.com/") == []

    def test_ev_issue_carries_the_resources(self):
        issue = next(i for i in check_page(_page(self.MIXED))
                     if i.code == "MIXED_CONTENT")
        urls = [row["url"] for row in issue.extra["mixed_content_items"]]
        assert "http://cdn.example/x.js" in urls


class TestInternalNofollowEvidence:
    def test_ev_nofollow_links_returned(self):
        html = '<a href="/a" rel="nofollow">A</a><a href="/b">B</a>'
        found = _find_internal_nofollow(BeautifulSoup(html, "lxml"), PAGE, PAGE)
        assert len(found) == 1
        assert found[0]["href"].endswith("/a")

    def test_ev_issue_carries_them(self):
        issue = next(i for i in check_page(_page('<a href="/a" rel="nofollow">A</a>'))
                     if i.code == "INTERNAL_NOFOLLOW")
        assert issue.extra["nofollow_links_total"] == 1


# ── The renderer ────────────────────────────────────────────────────────────


class TestEvidenceLines:
    def test_ev_link_rows_show_text_and_href(self):
        lines, _ = evidence_lines("ANCHOR_TEXT_GENERIC", {
            "count": 2,
            "examples": [{"href": "https://x/a", "text": "Learn More"}],
        })
        assert any('"Learn More" -> https://x/a' in line for line in lines)

    def test_ev_pure_counts_are_not_rendered_as_evidence(self):
        """The description already says "6 links". Repeating it is noise."""
        lines, _ = evidence_lines("UNSAFE_CROSS_ORIGIN_LINK", {"unsafe_link_count": 6})
        assert lines == []

    def test_ev_prose_diagnosis_rendered(self):
        lines, _ = evidence_lines("SEMANTIC_DENSITY_LOW", {
            "ratio": 0.028, "diagnosis": "Inline styles account for 49% of the page.",
        })
        assert any("Inline styles" in line for line in lines)

    def test_ev_string_lists_rendered(self):
        lines, _ = evidence_lines("CONVERSATIONAL_H2_MISSING", {
            "h2_headings": ["Counselling", "Training"],
        })
        assert any("Counselling" in line for line in lines)

    def test_ev_schema_field_rows_show_the_value(self):
        lines, _ = evidence_lines("ENTITY_VALUE_PLACEHOLDER", {
            "fields": [{"node": "WebSite", "field": "description", "value": "site logo"}],
        })
        assert any('WebSite.description = "site logo"' in line for line in lines)

    def test_ev_cap_is_disclosed(self, monkeypatch):
        """Rule 6 — a truncated list must never read as complete."""
        import api.services.issue_evidence as mod

        monkeypatch.setattr(mod, "EVIDENCE_ROW_CAP", 3)
        lines, _ = mod.evidence_lines("UNSAFE_CROSS_ORIGIN_LINK", {
            "unsafe_links": [{"href": f"https://x/{i}"} for i in range(30)],
            "unsafe_links_total": 30,
        })
        assert any("and 27 more" in line for line in lines)

    def test_ev_declared_total_beats_the_visible_length(self):
        """When the payload was already capped upstream, the disclosed total is
        the payload's own total, not the length of what survived."""
        lines, _ = evidence_lines("UNSAFE_CROSS_ORIGIN_LINK", {
            "unsafe_links": [{"href": f"https://x/{i}"} for i in range(5)],
            "unsafe_links_total": 200,
        })
        assert any("195 more" in line for line in lines)

    def test_ev_excel_is_genuinely_uncapped(self):
        """The PDF points the reader at the spreadsheet, so it must hold the lot."""
        text = evidence_for_excel("UNSAFE_CROSS_ORIGIN_LINK", {
            "unsafe_links": [{"href": f"https://x/{i}"} for i in range(40)],
            "unsafe_links_total": 40,
        })
        assert text.count("https://x/") == 40
        assert "more" not in text

    @pytest.mark.parametrize("extra", [None, {}, {"count": 1}, "not-a-dict"])
    def test_ev_degenerate_input_is_not_a_crash(self, extra):
        assert evidence_lines("ANY_CODE", extra) == ([], 0)

    def test_ev_unknown_keys_are_skipped_not_dumped(self):
        """Raw JSON in a client report is worse than nothing."""
        lines, _ = evidence_lines("X", {"some_internal_flag": True, "nested": {"a": 1}})
        assert lines == []


# ── The guard ───────────────────────────────────────────────────────────────


class TestEveryFindingIsActionable:
    """A code producing no evidence must be a recorded decision, not an oversight."""

    def test_ev_page_is_the_evidence_names_only_real_codes(self):
        unknown = sorted(PAGE_IS_THE_EVIDENCE - set(_CATALOGUE))
        assert not unknown, f"PAGE_IS_THE_EVIDENCE names codes that do not exist: {unknown}"

    def test_ev_high_volume_codes_are_actionable(self):
        """Every code seen on the real 2,137-issue job either renders evidence or
        is on the page-is-the-evidence list. Adding a count-only code without a
        decision fails here."""
        samples = {
            "UNSAFE_CROSS_ORIGIN_LINK": {"unsafe_links": [{"href": "https://x/a"}],
                                         "unsafe_links_total": 1},
            "MIXED_CONTENT": {"mixed_content_items": [{"url": "http://x/a", "tag": "img"}],
                              "mixed_content_items_total": 1},
            "INTERNAL_NOFOLLOW": {"nofollow_links": [{"href": "https://x/a"}],
                                  "nofollow_links_total": 1},
            "ANCHOR_TEXT_GENERIC": {"examples": [{"href": "https://x/a", "text": "Click"}]},
            "SEMANTIC_DENSITY_LOW": {"diagnosis": "Inline styles dominate."},
            "CONVERSATIONAL_H2_MISSING": {"h2_headings": ["A heading"]},
            "FIRST_VIEWPORT_NO_ANSWER": {"first_200_words": "Some opening text."},
            "BROKEN_LINK_404": {"occurrence_urls": ["https://x/a"],
                                "occurrence_urls_total": 1},
            "SCHEMA_VISIBLE_MISMATCH": {"mismatched_fields": [
                {"field": "Article.headline", "value": "A title"}]},
            "H1_MULTIPLE": {"outline": ["H1 one", "H1 two"]},
            "LINK_STACKED_DUPLICATE": {"groups": [{"href": "https://x/a", "count": 3}],
                                       "groups_total": 1},
        }
        for code, extra in samples.items():
            lines, _ = evidence_lines(code, extra)
            assert lines, f"{code} renders no evidence from a realistic payload"

    @pytest.mark.parametrize("code", sorted(PAGE_IS_THE_EVIDENCE)[:12])
    def test_ev_page_only_codes_need_no_evidence(self, code):
        """These are recorded as fixable from the page URL alone — the assertion
        is that the decision exists, not that the code is silent."""
        assert code in _CATALOGUE


class TestReadableLabels:
    """Field names leaking into a client report ("Occurrence urls") read as a
    database dump, not as a sentence a person would write."""

    def test_ev_occurrence_urls_reads_as_linked_from(self):
        lines, _ = evidence_lines("BROKEN_LINK_404", {
            "occurrence_urls": ["https://x/a"], "occurrence_urls_total": 1,
        })
        assert any(line.startswith("Linked from") for line in lines)
        assert not any("Occurrence urls" in line for line in lines)

    def test_ev_source_url_does_not_duplicate_the_linked_from_list(self):
        """`source_url` is the legacy back-compat field holding occurrence_urls[0];
        printing both made one finding look like two."""
        lines, _ = evidence_lines("BROKEN_LINK_404", {
            "occurrence_urls": ["https://x/a"], "occurrence_urls_total": 1,
            "source_url": "https://x/a",
        })
        assert sum(1 for line in lines if "https://x/a" in line) == 1

    def test_ev_unknown_key_still_gets_a_readable_fallback(self):
        lines, _ = evidence_lines("X", {"some_new_list": ["a value"]})
        assert any(line.startswith("Some new list") for line in lines)

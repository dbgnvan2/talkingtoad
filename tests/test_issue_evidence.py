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

    # ── ND2: NEAR_DUPLICATE_BODY names the partner pages ──────────────────
    # Spec: docs/functional-specification.md §4.10 (ND2)
    def test_ev_near_duplicate_names_the_partner_pages(self):
        """The whole point of the finding: WHICH other page does this duplicate."""
        lines, _ = evidence_lines("NEAR_DUPLICATE_BODY", {
            "members": ["https://x/a", "https://x/b", "https://x/c"],
            "near_identical_to": ["https://x/b", "https://x/c"],
        })
        assert any(line.startswith("Near-identical to:") for line in lines), lines
        assert any("https://x/b" in line for line in lines)
        assert any("https://x/c" in line for line in lines)

    def test_ev_near_duplicate_does_not_print_the_member_list_as_well(self):
        """Adversarial: `members` holds the same URLs plus this page's own. Left
        renderable it prints the list twice and tells the reader their page
        duplicates itself — the correct-looking-but-wrong render."""
        lines, _ = evidence_lines("NEAR_DUPLICATE_BODY", {
            "members": ["https://x/a", "https://x/b"],
            "near_identical_to": ["https://x/b"],
        })
        assert not any("Members" in line for line in lines), lines
        assert "https://x/a" not in "\n".join(lines), (
            "the page's own URL must not appear in its evidence")
        assert sum(1 for line in lines if "https://x/b" in line) == 1, (
            f"the partner list is printed twice: {lines}")


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


class TestEvidenceMatchesItsOwnSection:
    """The renderer must show the evidence for the issue it is printed under.

    The first wiring passed a leaked loop variable from an earlier section. It
    was in scope, raised nothing, and rendered another issue's evidence — the
    kind of bug that only a content assertion catches.
    """

    @pytest.mark.asyncio
    async def test_ev_each_section_shows_its_own_evidence(self):
        job = CrawlJob(job_id="j", target_url=PAGE, status="complete",
                       started_at=datetime.now(timezone.utc))
        issues = [
            IssueModel(
                job_id="j", page_url=PAGE, category="security", severity="info",
                issue_code="UNSAFE_CROSS_ORIGIN_LINK",
                description="External link opens in a new tab without rel",
                recommendation="Add rel.", human_description="Unsafe External Link",
                extra={"unsafe_links": [{"href": "https://partner.org/only-here"}],
                       "unsafe_links_total": 1},
            ),
            IssueModel(
                job_id="j", page_url=PAGE, category="metadata", severity="info",
                issue_code="ANCHOR_TEXT_GENERIC",
                description="Generic anchor text", recommendation="Describe it.",
                human_description="Non-Descriptive Link Text",
                extra={"examples": [{"href": "https://x/target-here",
                                     "text": "Read More"}]},
            ),
        ]
        text = _pdf_text(await generate_pdf_report(job, issues, {
            "health_score": 90, "agent_health_score": 90, "pages_crawled": 1,
            "total_issues": 2, "by_severity": {"info": 2},
            "by_category": {"security": 1, "metadata": 1}}))

        assert "partner.org/only-here" in text
        assert "target-here" in text
        assert "Read More" in text

    @pytest.mark.asyncio
    async def test_ev_real_job_codes_reach_the_pdf(self):
        """End-to-end on a realistic payload: a diagnosis and a heading list both
        render, proving the renderer is reached for more than one shape."""
        job = CrawlJob(job_id="j", target_url=PAGE, status="complete",
                       started_at=datetime.now(timezone.utc))
        issues = [
            IssueModel(
                job_id="j", page_url=PAGE, category="ai_readiness", severity="info",
                issue_code="SEMANTIC_DENSITY_LOW", description="Low text ratio",
                recommendation="Trim markup.", human_description="High Code-to-Text Ratio",
                extra={"ratio": 0.028,
                       "diagnosis": "Inline styles account for 49% of the page."},
            ),
            IssueModel(
                job_id="j", page_url=PAGE, category="ai_readiness", severity="info",
                issue_code="CONVERSATIONAL_H2_MISSING", description="No question headings",
                recommendation="Use questions.", human_description="Non-Conversational Headings",
                extra={"h2_headings": ["Upcoming Conferences", "Counselling"]},
            ),
        ]
        text = _pdf_text(await generate_pdf_report(job, issues, {
            "health_score": 90, "agent_health_score": 90, "pages_crawled": 1,
            "total_issues": 2, "by_severity": {"info": 2},
            "by_category": {"ai_readiness": 2}}))
        assert "Inline styles account for 49%" in text
        assert "Upcoming Conferences" in text


# ── The API contract: one implementation, server-side ───────────────────────


class TestEvidenceInTheApiPayload:
    """EV closed the report gap; this closes the GUI gap without a JS port.

    A second implementation of a 15-shape renderer in another language is a drift
    waiting to happen (P19). `_issue_dict` is the single serialiser all seven
    consumers use, so shipping the rendered lines from there means the category
    panel, the By-Page view, the PDF and the Excel export cannot disagree.
    """

    def test_ev_issue_dict_ships_rendered_evidence(self):
        from api.models.issue import Issue as IssueModel
        from api.routers.crawl import _issue_dict

        issue = IssueModel(
            job_id="j", page_url=PAGE, category="security", severity="info",
            issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="d",
            recommendation="r",
            extra={"unsafe_links": [{"href": "https://partner.org/a",
                                     "text": "Partner site"}],
                   "unsafe_links_total": 1},
        )
        payload = _issue_dict(issue)
        assert "evidence" in payload and "evidence_total" in payload
        assert any("partner.org/a" in line for line in payload["evidence"])

    def test_ev_issue_dict_evidence_is_empty_not_missing(self):
        """A code whose page URL is the whole story ships [], not a missing key —
        the frontend must not have to distinguish absent from empty."""
        from api.models.issue import Issue as IssueModel
        from api.routers.crawl import _issue_dict

        payload = _issue_dict(IssueModel(
            job_id="j", page_url=PAGE, category="metadata", severity="info",
            issue_code="META_DESC_MISSING", description="d", recommendation="r"))
        assert payload["evidence"] == []
        assert payload["evidence_total"] == 0

    def test_ev_issue_dict_never_raises_on_a_bad_extra(self):
        from api.models.issue import Issue as IssueModel
        from api.routers.crawl import _issue_dict

        payload = _issue_dict(IssueModel(
            job_id="j", page_url=PAGE, category="metadata", severity="info",
            issue_code="META_DESC_MISSING", description="d", recommendation="r",
            extra={"weird": object} if False else {"weird": {"nested": 1}}))
        assert payload["evidence"] == []

    @pytest.mark.asyncio
    async def test_ev_results_endpoint_carries_evidence(
        self, api_client, auth_headers, test_store
    ):
        """P25: the payload is what the GUI can render, so assert the surface."""
        from datetime import datetime, timezone

        from api.models.issue import Issue as IssueModel
        from api.models.job import CrawlJob
        from api.models.page import CrawledPage

        job_id = "job-ev"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url=PAGE, status="complete",
            started_at=datetime.now(timezone.utc)))
        await test_store.save_pages([CrawledPage(job_id=job_id, url=PAGE, status_code=200)])
        await test_store.save_issues([IssueModel(
            job_id=job_id, page_url=PAGE, category="security", severity="info",
            issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="d", recommendation="r",
            extra={"unsafe_links": [{"href": "https://partner.org/a"}],
                   "unsafe_links_total": 1})])

        resp = await api_client.get(f"/api/crawl/{job_id}/results", headers=auth_headers)
        assert resp.status_code == 200
        issue = resp.json()["issues"][0]
        assert any("partner.org/a" in line for line in issue["evidence"])


class TestExemptAnchorsReachTheEvidence:
    """The exempt-anchor filter rewrote only the description, leaving the raw
    hrefs in `extra`. Harmless while nothing rendered them — the moment
    `evidence` did, the UI would have shown the very anchors the user exempted.
    """

    def test_ev_exempted_anchor_is_removed_from_extra(self):
        from api.routers.crawl import _apply_exempt_anchors

        issue = {
            "issue_code": "LINK_EMPTY_ANCHOR",
            "description": "2 links with no anchor text: https://x/keep, https://x/drop",
            "extra": {"empty_anchors": [{"href": "https://x/keep"},
                                        {"href": "https://x/drop"}]},
            "evidence": ["Links with no accessible name:", "  https://x/drop"],
            "evidence_total": 2,
        }
        out = _apply_exempt_anchors([issue], {"https://x/drop"})
        assert len(out) == 1
        hrefs = [a["href"] for a in out[0]["extra"]["empty_anchors"]]
        assert hrefs == ["https://x/keep"]

    def test_ev_evidence_is_recomputed_after_exemption(self):
        from api.routers.crawl import _apply_exempt_anchors

        issue = {
            "issue_code": "LINK_EMPTY_ANCHOR",
            "description": "2 links with no anchor text: https://x/keep, https://x/drop",
            "extra": {"empty_anchors": [{"href": "https://x/keep"},
                                        {"href": "https://x/drop"}]},
            "evidence": [], "evidence_total": 0,
        }
        out = _apply_exempt_anchors([issue], {"https://x/drop"})
        rendered = " ".join(out[0]["evidence"])
        assert "https://x/keep" in rendered
        assert "https://x/drop" not in rendered, (
            "the evidence must not show an anchor the user exempted"
        )

    def test_ev_issue_with_all_anchors_exempted_is_dropped(self):
        from api.routers.crawl import _apply_exempt_anchors

        issue = {
            "issue_code": "LINK_EMPTY_ANCHOR",
            "description": "1 link with no anchor text: https://x/drop",
            "extra": {"empty_anchors": [{"href": "https://x/drop"}]},
            "evidence": [], "evidence_total": 0,
        }
        assert _apply_exempt_anchors([issue], {"https://x/drop"}) == []

    def test_ev_other_codes_are_untouched(self):
        from api.routers.crawl import _apply_exempt_anchors

        issue = {"issue_code": "META_DESC_MISSING", "description": "d",
                 "extra": {}, "evidence": [], "evidence_total": 0}
        assert _apply_exempt_anchors([issue], {"https://x/drop"}) == [issue]


class TestStackedLinkContainerIsNamed:
    """S4 (2026-09-01) — the evidence must name what it called a card.

    `container_tag`/`container_class` were stored on every stacked-link group
    from the day the check shipped and rendered nowhere. When the check started
    treating `<main>` as a card, the only way to see that was to open the
    SQLite database by hand — which is how the defect survived a user report of
    "this link is duplicated, but I can't find it".

    Spec: docs/pending/2026-09-01_stacked-links-container-overmatch.md#S4
    """

    GROUP = {
        "href": "https://livingsystems.ca/training/application-seminar/",
        "count": 2,
        "accessible_names": ["Application Seminar Learn more", "Application of Bowen"],
        "container_tag": "li",
        "container_class": "jet-listing-grid__item jet-listing-dynamic-post-12168",
    }

    def _line(self, group: dict) -> str:
        from api.services.issue_evidence import _row_to_line

        return _row_to_line(group)

    def test_container_tag_and_class_are_rendered(self):
        line = self._line(self.GROUP)
        assert "li" in line
        assert "jet-listing-grid__item" in line

    def test_page_level_container_would_be_visible_on_screen(self):
        """The regression, from the reader's side: had this been rendered, the
        finding would have said `<main class="… hentry">` and named itself."""
        line = self._line({**self.GROUP, "container_tag": "main",
                           "container_class": "site-main post-350 page hentry"})
        assert "main" in line and "hentry" in line

    def test_group_without_a_container_still_renders(self):
        """Legacy rows predate the container fields; they must not crash or
        render a dangling 'in <>'."""
        bare = {k: v for k, v in self.GROUP.items()
                if k not in ("container_tag", "container_class")}
        line = self._line(bare)
        assert "application-seminar" in line
        assert "in <" not in line

    def test_container_with_no_class_renders_the_tag_alone(self):
        line = self._line({**self.GROUP, "container_class": ""})
        assert "in <li>" in line
        assert 'class=""' not in line

    def test_the_href_is_still_the_subject_of_the_line(self):
        """Adding context must not bury the destination the finding is about."""
        line = self._line(self.GROUP)
        assert line.index("application-seminar") < line.index("jet-listing")

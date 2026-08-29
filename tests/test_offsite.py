"""D1 — off-site authority, joined to the crawl.

Purpose: prove the three joins work, that the join key cannot silently drift, and
         that "no links supplied" never renders as "nobody links to you".
Spec:    docs/pending/2026-08-29_D1-off-site-authority.md
Tests:   this file

`test_d1_external_links_to_broken_target` comes first (P10). "Another site links
to a page of yours that 404s" is the finding that justifies the whole item, and
it is the one neither a backlink tool nor an analytics export can produce alone —
it needs the crawl's broken-link set.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest

from api.models.job import CrawlJob
from api.services.offsite import build_offsite, to_dict
from api.services.report_generator import generate_pdf_report

SITE = "https://livingsystems.ca"
GOOD = f"{SITE}/emotional-pain-and-suffering"
BROKEN = f"{SITE}/dontation_form"
ORPHAN = f"{SITE}/the-maturity-point"


def _links(**kw) -> dict:
    base = {
        "referring_domains": 187,
        "total_external_links": 707,
        "top_linking_sites": [{"domain": "example.edu", "linking_pages": 14,
                               "target_pages": 3}],
        "top_linked_pages": [],
        "top_linking_text": [],
    }
    base.update(kw)
    return base


def _ranked(*pages) -> list[dict]:
    return [{"url": u, "health_score": h} for u, h in pages]


def _summary() -> dict:
    return {"health_score": 90, "agent_health_score": 90, "pages_crawled": 3,
            "total_issues": 0, "by_severity": {}, "by_category": {}}


def _pdf_text(pdf_bytes: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return " ".join((p.extract_text() or "") for p in reader.pages).replace("\n", " ")


def _job() -> CrawlJob:
    return CrawlJob(job_id="j", target_url=SITE, status="complete",
                    started_at=datetime.now(timezone.utc))


# ── The join that justifies the feature (P10) ───────────────────────────────


class TestLinksToBrokenTargets:
    def test_d1_external_links_to_broken_target(self):
        """Link equity being thrown away. Needs BOTH the link data and the
        crawl's broken-link set — no other tool in the stack holds both."""
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": BROKEN + "/", "incoming_links": 41, "linking_sites": 12}]),
            _ranked((GOOD, 85)),
            broken_target_urls={BROKEN},
        )
        assert [r["url"] for r in report.links_to_broken_targets] == [BROKEN + "/"]
        assert report.links_to_broken_targets[0]["incoming_links"] == 41

    def test_d1_broken_target_is_not_also_counted_as_earned_authority(self):
        """A broken page is one finding, not two — and 'fix the redirect' is a
        different action from 'improve the page'."""
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": BROKEN, "incoming_links": 41, "linking_sites": 12}]),
            _ranked((BROKEN, 10)),
            broken_target_urls={BROKEN},
        )
        assert report.links_to_broken_targets
        assert report.earned_authority_poor_health == []

    def test_d1_working_page_is_not_reported_as_broken(self):
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": GOOD, "incoming_links": 41, "linking_sites": 12}]),
            _ranked((GOOD, 95)),
            broken_target_urls=set(),
        )
        assert report.links_to_broken_targets == []


# ── The other two joins ─────────────────────────────────────────────────────


class TestEarnedAuthority:
    def test_d1_earned_authority_low_health_ranks_first(self):
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": GOOD, "incoming_links": 41, "linking_sites": 12}]),
            _ranked((GOOD, 62)),
        )
        assert [r["url"] for r in report.earned_authority_poor_health] == [GOOD]
        assert report.earned_authority_poor_health[0]["health_score"] == 62

    def test_d1_healthy_linked_page_is_not_leverage(self):
        """A well-linked page that is already fine is not work to do."""
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": GOOD, "incoming_links": 41, "linking_sites": 12}]),
            _ranked((GOOD, 96)),
        )
        assert report.earned_authority_poor_health == []

    def test_d1_a_single_stray_link_is_not_authority(self):
        """Adversarial (P7). One link from a scraper is not earned authority, and
        surfacing it would fill the section with noise."""
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": GOOD, "incoming_links": 1, "linking_sites": 1}]),
            _ranked((GOOD, 40)),
        )
        assert report.earned_authority_poor_health == []

    def test_d1_results_are_ordered_by_incoming_links(self):
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": f"{SITE}/a", "incoming_links": 3},
                {"url": f"{SITE}/b", "incoming_links": 40},
            ]),
            _ranked((f"{SITE}/a", 50), (f"{SITE}/b", 50)),
        )
        assert [r["incoming_links"] for r in report.earned_authority_poor_health] == [40, 3]


class TestOrphanedAuthority:
    def test_d1_orphaned_authority(self):
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": ORPHAN, "incoming_links": 9, "linking_sites": 4}]),
            _ranked((ORPHAN, 88)),
            orphan_urls={ORPHAN},
        )
        assert [r["url"] for r in report.orphaned_authority] == [ORPHAN]

    def test_d1_internally_linked_page_is_not_orphaned(self):
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": GOOD, "incoming_links": 9}]),
            _ranked((GOOD, 88)),
            orphan_urls=set(),
        )
        assert report.orphaned_authority == []


# ── The join key (the E3 lesson, applied here) ──────────────────────────────


class TestJoinKey:
    def test_d1_link_join_tolerates_trailing_slash(self):
        """The exact-match join silently lost 96% of the Performance Ledger
        before E3 fixed it. Repeating it here would be the same bug in a new
        place (P5), so this uses the same `ledger_key`."""
        report = build_offsite(
            _links(top_linked_pages=[{"url": GOOD + "/", "incoming_links": 41}]),
            _ranked((GOOD, 62)),
        )
        assert report.pages_matched == 1
        assert report.earned_authority_poor_health

    def test_d1_link_join_tolerates_www(self):
        report = build_offsite(
            _links(top_linked_pages=[
                {"url": "https://www.livingsystems.ca/emotional-pain-and-suffering",
                 "incoming_links": 41}]),
            _ranked((GOOD, 62)),
        )
        assert report.pages_matched == 1

    def test_d1_unmatched_page_is_counted_not_silently_dropped(self):
        """`pages_in_report` vs `pages_matched` makes a join failure visible."""
        report = build_offsite(
            _links(top_linked_pages=[{"url": f"{SITE}/never-crawled",
                                      "incoming_links": 9}]),
            _ranked((GOOD, 62)),
        )
        assert report.pages_in_report == 1
        assert report.pages_matched == 0


# ── Caps and absence ────────────────────────────────────────────────────────


class TestCapsAndAbsence:
    def test_d1_no_links_returns_none_not_zeros(self):
        """P2: 'not supplied' must never render as 'nobody links to you'."""
        assert build_offsite(None, _ranked((GOOD, 90))) is None
        assert build_offsite({}, _ranked((GOOD, 90))) is None

    def test_d1_top_sites_cap_disclosed(self):
        """Real-scale (P9): 200 domains, a capped list, and the true total."""
        sites = [{"domain": f"site{i}.org", "linking_pages": i} for i in range(200)]
        report = build_offsite(_links(top_linking_sites=sites), _ranked((GOOD, 90)))
        assert len(report.top_linking_sites) == 20
        assert report.top_linking_sites_total == 200

    def test_d1_links_without_linked_pages_still_reports_totals(self):
        """A producer may send counts before it sends per-page data."""
        report = build_offsite(_links(top_linked_pages=[]), _ranked((GOOD, 90)))
        assert report.referring_domains == 187
        assert report.has_data


# ── The report surface ──────────────────────────────────────────────────────


class TestReportRendering:
    @pytest.mark.asyncio
    async def test_d1_offsite_section_renders_the_joins(self):
        report = to_dict(build_offsite(
            _links(top_linked_pages=[
                {"url": BROKEN, "incoming_links": 41, "linking_sites": 12},
                {"url": GOOD, "incoming_links": 22, "linking_sites": 8},
            ]),
            _ranked((GOOD, 62)),
            broken_target_urls={BROKEN},
        ))
        text = _pdf_text(await generate_pdf_report(
            _job(), [], _summary(), offsite=report))
        assert "Off-Site Authority" in text
        assert "External links pointing at broken pages" in text
        assert "dontation_form" in text
        assert "Earned authority on pages with fixable problems" in text
        assert "187" in text, "referring domains must be stated"

    @pytest.mark.asyncio
    async def test_d1_offsite_omission_disclosed(self):
        """No links supplied → section absent AND named in Caveats (E7.4)."""
        text = _pdf_text(await generate_pdf_report(_job(), [], _summary(), offsite=None))
        assert "Off-Site Authority" not in text
        assert "Search Console link data was not supplied" in text

    @pytest.mark.asyncio
    async def test_d1_caveats_distinguishes_the_two_gaps(self):
        """With links present, the caveat must say what IS included and what is
        still declined — not repeat a blanket 'off-site not checked'."""
        report = to_dict(build_offsite(_links(), _ranked((GOOD, 90))))
        text = _pdf_text(await generate_pdf_report(
            _job(), [], _summary(), offsite=report))
        assert "Search Console's own link data IS included" in text
        assert "commercial index TalkingToad does not license" in text
        assert "was not supplied for this site" not in text


# ── Ingest ──────────────────────────────────────────────────────────────────


class TestBundleIngest:
    def test_d1_links_section_is_optional_in_the_contract(self):
        """Every producer predating this contract must keep working."""
        from api.routers.performance import BundleSite

        assert BundleSite().links is None

    def test_d1_links_section_parses(self):
        from api.routers.performance import BundleSite

        site = BundleSite(links={
            "referring_domains": 187, "total_external_links": 707,
            "top_linking_sites": [{"domain": "example.edu", "linking_pages": 14}],
            "top_linked_pages": [{"url": GOOD, "incoming_links": 41}],
        })
        assert site.links.referring_domains == 187
        assert site.links.top_linked_pages[0].incoming_links == 41

    def test_d1_malformed_links_fails_loud(self):
        """P2: a malformed section must be rejected, never silently dropped."""
        import pydantic

        from api.routers.performance import BundleSite

        with pytest.raises(pydantic.ValidationError):
            BundleSite(links={"top_linking_sites": [{"linking_pages": "not-a-number"}]})

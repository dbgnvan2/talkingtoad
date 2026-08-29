"""E2 — every page that links to a broken target, not just the first.

Purpose: prove a broken target reports ALL its linking pages, that the target is
         still fetched once, that the evidence cap is disclosed, and that link
         records carry a derived link_type and a real status_code.
Spec:    docs/pending/2026-08-29_E2-broken-link-source-attribution.md
Tests:   this file

Job 05cd2496 reported 10 dead links where an independent audit reported 120
broken internal links. Both were right about WHICH targets were broken — the
same nine — but TalkingToad kept only the first page that linked to each, so a
single reusable-block edit read as nine unrelated chores.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
import respx

from api.crawler.checkers.links import collapse_per_target_occurrences
from api.crawler.engine import (
    BrokenLinkRef,
    CrawlSettings,
    _broken_link_extra,
    run_crawl,
)
from api.crawler.issue_checker import Issue, make_issue

BASE_URL = "https://example.com/"
ROBOTS_URL = "https://example.com/robots.txt"
SITEMAP_URL = "https://example.com/sitemap.xml"
_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"


def _html(title: str, body: str) -> str:
    return (
        f"<!DOCTYPE html><html><head><title>{title} With A Good Long Title</title>"
        '<meta name="description" content="A description long enough to pass the checks here.">'
        f"</head><body><h1>{title}</h1>{body}</body></html>"
    )


# ── E2.2 — the extra payload ────────────────────────────────────────────────


class TestBrokenLinkExtra:
    def test_e2_2a_evidence_is_source_pages(self):
        extra = _broken_link_extra(
            target_url="https://example.com/gone",
            sources=["https://example.com/a", "https://example.com/b"],
        )
        assert extra["occurrence_urls"] == [
            "https://example.com/a",
            "https://example.com/b",
        ]
        assert extra["target_url"] == "https://example.com/gone"
        assert extra["occurrence_urls_total"] == 2

    def test_e2_2a_occurrences_is_the_scoring_count_not_the_evidence_count(self):
        """`occurrences` drives `occurrence_multiplier`, which scales the
        deduction on the ONE page this issue is anchored to. Setting it to the
        site-wide linking-page count doubled that page's deduction for a defect
        it shares with 199 others, making per-page health crawl-order dependent
        (P7) and amplifying transient 503s / timeouts (P1)."""
        extra = _broken_link_extra(
            target_url="https://example.com/gone",
            sources=[f"https://example.com/p{i}" for i in range(200)],
        )
        assert extra["occurrences"] == 1
        assert extra["occurrence_urls_total"] == 200

    def test_e2_2b_source_cap_announced_at_scale(self, monkeypatch):
        """Real-scale (P9): 120 linking pages, a cap of 50, and the true total
        travels alongside so no surface can imply 50 is all of them."""
        import importlib

        monkeypatch.setenv("TT_BROKEN_LINK_SOURCE_CAP", "50")
        import api.crawler.engine as engine_mod

        importlib.reload(engine_mod)
        try:
            sources = [f"https://example.com/post-{i}" for i in range(120)]
            extra = engine_mod._broken_link_extra(
                target_url="https://example.com/dontation_form", sources=sources
            )
            assert extra["occurrence_urls_total"] == 120
            assert len(extra["occurrence_urls"]) == 50
            assert extra["occurrences"] == 1, "scoring count, not the evidence count"
        finally:
            monkeypatch.delenv("TT_BROKEN_LINK_SOURCE_CAP", raising=False)
            importlib.reload(engine_mod)

    def test_e2_2a_backwards_compatible_source_url_retained(self):
        extra = _broken_link_extra(
            target_url="https://example.com/gone",
            sources=["https://example.com/a", "https://example.com/b"],
            first_source="https://example.com/a",
        )
        assert extra["source_url"] == "https://example.com/a"

    def test_e2_2a_anchor_texts_carried_when_present(self):
        extra = _broken_link_extra(
            target_url="https://example.com/gone",
            sources=["https://example.com/a"],
            anchor_texts=["Donate now", None],
        )
        assert extra["anchor_texts"] == ["Donate now"]

    def test_e2_2a_no_sources_is_not_a_crash(self):
        extra = _broken_link_extra(target_url="https://example.com/gone", sources=[])
        assert extra["occurrence_urls_total"] == 0
        assert extra["occurrence_urls"] == []


# ── E2.1 — engine attribution ───────────────────────────────────────────────


class TestEngineAttribution:
    @pytest.mark.asyncio
    async def test_e2_1c_internal_404_lists_all_parents(self):
        """Three pages link to one internal 404. All three must be reported."""
        home = _html("Home", '<a href="/a">A</a><a href="/b">B</a><a href="/c">C</a>')
        linker = _html("Linker", '<a href="/gone">Donate</a>')
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(
                return_value=httpx.Response(200, text=home, headers={"content-type": "text/html"})
            )
            for path in ("a", "b", "c"):
                respx.get(f"https://example.com/{path}").mock(
                    return_value=httpx.Response(
                        200, text=linker, headers={"content-type": "text/html"}
                    )
                )
            respx.get("https://example.com/gone").mock(
                return_value=httpx.Response(404, text="nope", headers={"content-type": "text/html"})
            )
            result = await run_crawl(
                "job-e2-1", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=20)
            )

        broken = [i for i in result.issues if i.code == "BROKEN_LINK_404"]
        assert broken, "the 404 must be reported at all"
        issue = broken[0]
        assert issue.extra["occurrence_urls_total"] == 3, (
            f"pre-E2 only the first discoverer was kept; got {issue.extra}"
        )
        assert set(issue.extra["occurrence_urls"]) == {
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        }

    @pytest.mark.asyncio
    async def test_e2_1b_external_target_fetched_once(self):
        """Dedupe of the FETCH is preserved — attribution must not cost requests."""
        ext = "https://external-site.org/gone"
        home = _html("Home", '<a href="/a">A</a><a href="/b">B</a>')
        linker = _html("Linker", f'<a href="{ext}">Out</a>')
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(
                return_value=httpx.Response(200, text=home, headers={"content-type": "text/html"})
            )
            for path in ("a", "b"):
                respx.get(f"https://example.com/{path}").mock(
                    return_value=httpx.Response(
                        200, text=linker, headers={"content-type": "text/html"}
                    )
                )
            head_route = respx.head(ext).mock(return_value=httpx.Response(404))
            get_route = respx.get(ext).mock(return_value=httpx.Response(404))
            result = await run_crawl(
                "job-e2-2", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=20)
            )

        assert head_route.call_count + get_route.call_count <= 2, (
            "the target must be checked once, not once per linking page"
        )
        broken = [i for i in result.issues if i.code == "BROKEN_LINK_404"]
        assert broken
        assert broken[0].extra["occurrence_urls_total"] == 2
        assert set(broken[0].extra["occurrence_urls"]) == {
            "https://example.com/a",
            "https://example.com/b",
        }

    @pytest.mark.asyncio
    async def test_e2_1d_discovered_from_semantics_unchanged(self):
        """P12: the additive source map must not disturb depth/parent handling.
        A page reachable from two parents keeps its shallowest depth."""
        home = _html("Home", '<a href="/deep">Deep</a><a href="/mid">Mid</a>')
        mid = _html("Mid", '<a href="/deep">Deep</a>')
        deep = _html("Deep", "")
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(
                return_value=httpx.Response(200, text=home, headers={"content-type": "text/html"})
            )
            respx.get("https://example.com/mid").mock(
                return_value=httpx.Response(200, text=mid, headers={"content-type": "text/html"})
            )
            respx.get("https://example.com/deep").mock(
                return_value=httpx.Response(200, text=deep, headers={"content-type": "text/html"})
            )
            result = await run_crawl(
                "job-e2-3", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=20)
            )
        deep_page = next(p for p in result.pages if p.url.endswith("/deep"))
        assert deep_page.crawl_depth == 1, "shallowest depth wins, as before E2"


# ── E2.3 — link record fidelity ─────────────────────────────────────────────


class TestLinkRecordFidelity:
    @pytest.mark.asyncio
    async def test_e2_3a_same_host_broken_link_is_internal(self):
        """A same-host 404 must not be stored as 'external' (it was, always)."""
        home = _html("Home", '<a href="/gone">Donate</a>')
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(
                return_value=httpx.Response(200, text=home, headers={"content-type": "text/html"})
            )
            respx.get("https://example.com/gone").mock(
                return_value=httpx.Response(404, text="nope", headers={"content-type": "text/html"})
            )
            result = await run_crawl(
                "job-e2-4", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=20)
            )
        refs = [r for r in result.broken_link_sources if r.target_url.endswith("/gone")]
        assert refs, "the broken link must be recorded"
        assert all(r.link_type == "internal" for r in refs)

    @pytest.mark.asyncio
    async def test_e2_3b_status_code_persisted(self):
        home = _html("Home", '<a href="/gone">Gone</a>')
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(
                return_value=httpx.Response(200, text=home, headers={"content-type": "text/html"})
            )
            respx.get("https://example.com/gone").mock(
                return_value=httpx.Response(404, text="x", headers={"content-type": "text/html"})
            )
            result = await run_crawl(
                "job-e2-5", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=20)
            )
        refs = [r for r in result.broken_link_sources if r.target_url.endswith("/gone")]
        assert refs and all(r.status_code == 404 for r in refs), (
            "status_code was never written — a 503 was indistinguishable from a 404"
        )

    @pytest.mark.asyncio
    async def test_e2_3d_503_is_retryable_not_terminal(self):
        """P1: a transient 503 must be recorded as its own code and status, not
        collapsed into a permanent 404 verdict."""
        home = _html("Home", '<a href="/flaky">Flaky</a>')
        with respx.mock:
            respx.get(ROBOTS_URL).mock(return_value=httpx.Response(200, text=_ALLOW_ALL_ROBOTS))
            respx.get(SITEMAP_URL).mock(return_value=httpx.Response(404))
            respx.get(BASE_URL).mock(
                return_value=httpx.Response(200, text=home, headers={"content-type": "text/html"})
            )
            respx.get("https://example.com/flaky").mock(
                return_value=httpx.Response(503, text="busy", headers={"content-type": "text/html"})
            )
            result = await run_crawl(
                "job-e2-6", BASE_URL, CrawlSettings(crawl_delay_ms=0, max_pages=20)
            )
        codes = {i.code for i in result.issues}
        assert "BROKEN_LINK_503" in codes
        assert "BROKEN_LINK_404" not in codes
        refs = [r for r in result.broken_link_sources if r.target_url.endswith("/flaky")]
        assert refs and all(r.status_code == 503 for r in refs)

    def test_e2_3c_broken_link_ref_shape(self):
        ref = BrokenLinkRef(
            target_url="https://example.com/gone",
            source_url="https://example.com/a",
            link_text="Donate",
            status_code=404,
            link_type="internal",
        )
        assert (ref.target_url, ref.source_url, ref.status_code, ref.link_type) == (
            "https://example.com/gone",
            "https://example.com/a",
            404,
            "internal",
        )


# ── E2.2 — collapse must not clobber the richer payload ─────────────────────


class TestCollapsePreservesAttribution:
    def _issue(self, page_url: str, extra: dict) -> Issue:
        iss = make_issue("BROKEN_LINK_404", page_url)
        iss.extra = extra
        return iss

    def test_e2_2a_pre_set_source_list_survives_collapse(self):
        """One issue already representing 40 linking pages must not be reset to 1."""
        sources = [f"https://example.com/post-{i}" for i in range(40)]
        iss = self._issue(
            "https://example.com/post-0",
            _broken_link_extra(target_url="https://example.com/gone", sources=sources),
        )
        out = collapse_per_target_occurrences([iss])
        assert len(out) == 1
        assert out[0].extra["occurrence_urls_total"] == 40
        assert out[0].extra["occurrences"] == 1, "one page, one broken link"

    def test_e2_2a_group_sums_member_occurrences(self):
        a = self._issue(
            "https://example.com/p",
            _broken_link_extra(target_url="https://example.com/x", sources=["https://example.com/p"] * 1),
        )
        b = self._issue(
            "https://example.com/p",
            _broken_link_extra(
                target_url="https://example.com/y",
                sources=["https://example.com/p", "https://example.com/q"],
            ),
        )
        out = collapse_per_target_occurrences([a, b])
        assert len(out) == 1
        # Two distinct broken targets linked from this page -> §2 count of 2.
        assert out[0].extra["occurrences"] == 2
        assert out[0].extra["affected_targets_total"] == 2
        # Evidence unions the linking pages across both.
        assert out[0].extra["occurrence_urls_total"] == 3

    def test_e2_2d_redirect_evidence_unchanged(self):
        """Redirect codes carry no source list and must keep using redirect_to."""
        r1 = make_issue("REDIRECT_301", "https://example.com/p")
        r1.extra = {"redirect_to": "https://example.com/new-1"}
        r2 = make_issue("REDIRECT_301", "https://example.com/p")
        r2.extra = {"redirect_to": "https://example.com/new-2"}
        out = collapse_per_target_occurrences([r1, r2])
        assert len(out) == 1
        assert out[0].extra["occurrences"] == 2
        assert set(out[0].extra["occurrence_urls"]) == {
            "https://example.com/new-1",
            "https://example.com/new-2",
        }

    def test_e2_2d_non_per_target_issues_pass_through(self):
        other = make_issue("TITLE_TOO_LONG", "https://example.com/p")
        out = collapse_per_target_occurrences([other])
        assert out == [other]

    def test_e2_2b_collapse_caps_and_discloses(self, monkeypatch):
        import importlib

        monkeypatch.setenv("TT_BROKEN_LINK_SOURCE_CAP", "10")
        import api.crawler.checkers.links as links_mod

        importlib.reload(links_mod)
        try:
            sources = [f"https://example.com/post-{i}" for i in range(75)]
            iss = make_issue("BROKEN_LINK_404", "https://example.com/post-0")
            iss.extra = {
                "target_url": "https://example.com/gone",
                "occurrences": 75,
                "occurrence_urls": sources,
                "occurrence_urls_total": 75,
            }
            out = links_mod.collapse_per_target_occurrences([iss])
            assert len(out[0].extra["occurrence_urls"]) == 10
            # The pre-cap total must survive the merge. Recomputing it from the
            # already-truncated list collapsed "showing 10 of 75" to "10 of 10"
            # and made the disclosure unreachable on every surface (P9).
            assert out[0].extra["occurrence_urls_total"] == 75
        finally:
            monkeypatch.delenv("TT_BROKEN_LINK_SOURCE_CAP", raising=False)
            importlib.reload(links_mod)


# ── E2.3c — P22 guard: no call site may unpack the legacy 3-tuple ───────────


class TestNoLegacyTupleUnpack:
    def test_e2_3c_no_legacy_broken_link_tuple_unpack(self):
        """`broken_link_sources` changed from list[tuple] to list[BrokenLinkRef].
        A stale `for tgt, src, txt in ...` would silently mis-bind (P22)."""
        root = Path(__file__).resolve().parent.parent
        pattern = re.compile(r"for\s+\w+\s*,\s*\w+\s*,\s*\w+\s+in\s+.*broken_link_sources")
        offenders = []
        for path in (root / "api").rglob("*.py"):
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(root)}:{lineno}")
        assert not offenders, f"legacy 3-tuple unpack of broken_link_sources: {offenders}"

    def test_e2_3c_router_uses_ref_attributes(self):
        root = Path(__file__).resolve().parent.parent
        src = (root / "api" / "routers" / "crawl.py").read_text()
        assert "ref.link_type" in src and "ref.status_code" in src, (
            "the router must persist the derived link_type and the real status_code"
        )
        assert 'link_type="external",\n                is_broken=True' not in src, (
            "link_type must not be hardcoded"
        )

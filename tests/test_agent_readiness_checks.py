"""Tests for Agent-readiness checks (Phase 1, WP1–WP6).

Covers the parser-side detection of the new task-side signals (with the
mandatory "passes for the wrong reason" adversarial case per check), the WP1
named-AI-crawler robots logic, and the WP6 Agent Health score (serialization +
monotonicity) plus the API contract surfaces.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from api.crawler.fetcher import FetchResult
from api.crawler.parser import parse_page
from api.crawler.issue_checker import check_page
from api.crawler.robots import RobotsData
from api.services.ai_readiness import check_ai_bot_access

from api.models.issue import Issue
from api.models.job import CrawlJob
from api.models.page import CrawledPage
from api.services.job_store import SQLiteJobStore


BASE = "https://example.org"


def _parse(html: str, *, url: str = "https://example.org/page", is_homepage: bool = False):
    result = FetchResult(
        url=url,
        final_url=url,
        status_code=200,
        headers={},
        html=html,
        content_type="text/html",
        response_size_bytes=len(html.encode("utf-8")),
    )
    return parse_page(result, BASE, is_homepage=is_homepage)


def _check(html: str, *, url: str = "https://example.org/page", is_homepage: bool = False):
    page = _parse(html, url=url, is_homepage=is_homepage)
    return [i.code for i in check_page(page)]


# ---------------------------------------------------------------------------
# WP2 — JS_DEPENDENT_NAVIGATION
# ---------------------------------------------------------------------------

class TestJsDependentNavigation:
    def test_nav_with_no_links_flags(self):
        html = """<html><body>
          <nav><button class="hamburger">Menu</button><ul></ul></nav>
          <main><p>Some real content here.</p></main>
        </body></html>"""
        assert "JS_DEPENDENT_NAVIGATION" in _check(html)

    def test_nav_with_real_links_does_not_flag(self):
        html = """<html><body>
          <nav><a href="/services">Services</a><a href="/about">About</a></nav>
          <main><p>Content</p></main>
        </body></html>"""
        assert "JS_DEPENDENT_NAVIGATION" not in _check(html)

    def test_in_page_anchor_nav_does_not_flag(self):
        # Adversarial: a single-page site whose nav uses #section anchors — the
        # links ARE in the raw HTML, so this must not be mistaken for JS nav.
        html = """<html><body>
          <nav><a href="#about">About</a><a href="#contact">Contact</a></nav>
          <main><p>Content</p></main>
        </body></html>"""
        assert "JS_DEPENDENT_NAVIGATION" not in _check(html)

    def test_no_nav_region_does_not_flag(self):
        html = "<html><body><main><p>Just content, no nav region.</p></main></body></html>"
        assert "JS_DEPENDENT_NAVIGATION" not in _check(html)


# ---------------------------------------------------------------------------
# WP3 — semantic HTML
# ---------------------------------------------------------------------------

class TestNonSemanticButton:
    def test_div_with_onclick_no_role_flags(self):
        html = '<html><body><main><div class="btn" onclick="go()">Donate</div></main></body></html>'
        assert "NON_SEMANTIC_BUTTON" in _check(html)

    def test_div_with_role_button_does_not_flag(self):
        # Adversarial: a div that has been given role=button + aria-label is a
        # correctly-exposed control and must not be flagged.
        html = ('<html><body><main>'
                '<div role="button" tabindex="0" aria-label="Donate" onclick="go()">Donate</div>'
                '</main></body></html>')
        assert "NON_SEMANTIC_BUTTON" not in _check(html)

    def test_real_button_does_not_flag(self):
        html = '<html><body><main><button onclick="go()">Donate</button></main></body></html>'
        assert "NON_SEMANTIC_BUTTON" not in _check(html)


class TestInteractiveNoAccessibleName:
    def test_button_without_name_flags(self):
        html = '<html><body><main><button class="icon"></button></main></body></html>'
        assert "INTERACTIVE_NO_ACCESSIBLE_NAME" in _check(html)

    def test_icon_button_with_aria_label_does_not_flag(self):
        # Adversarial: icon-only button WITH aria-label is properly named.
        html = '<html><body><main><button aria-label="Search">🔍</button></main></body></html>'
        assert "INTERACTIVE_NO_ACCESSIBLE_NAME" not in _check(html)

    def test_input_with_label_does_not_flag(self):
        html = ('<html><body><main>'
                '<label for="q">Search</label><input id="q" type="text">'
                '</main></body></html>')
        assert "INTERACTIVE_NO_ACCESSIBLE_NAME" not in _check(html)

    def test_input_without_name_flags(self):
        html = '<html><body><main><input type="text"></main></body></html>'
        assert "INTERACTIVE_NO_ACCESSIBLE_NAME" in _check(html)


class TestLandmarks:
    def test_missing_main_flags(self):
        html = "<html><body><div><p>content</p></div></body></html>"
        assert "LANDMARK_MAIN_MISSING" in _check(html)

    def test_present_main_does_not_flag(self):
        html = "<html><body><main><p>content</p></main></body></html>"
        assert "LANDMARK_MAIN_MISSING" not in _check(html)

    def test_missing_nav_flags_on_homepage_only(self):
        html = "<html><body><main><p>content</p></main></body></html>"
        assert "LANDMARK_NAV_MISSING" in _check(html, is_homepage=True)
        # Non-homepage pages are not checked for the nav landmark.
        assert "LANDMARK_NAV_MISSING" not in _check(html, is_homepage=False)

    def test_present_nav_does_not_flag(self):
        html = '<html><body><nav><a href="/a">A</a></nav><main><p>c</p></main></body></html>'
        assert "LANDMARK_NAV_MISSING" not in _check(html, is_homepage=True)


# ---------------------------------------------------------------------------
# WP4 — placeholder links
# ---------------------------------------------------------------------------

class TestPlaceholderLinks:
    def test_cta_with_hash_href_flags(self):
        html = '<html><body><main><a class="btn" href="#">Donate now</a></main></body></html>'
        assert "PLACEHOLDER_LINK" in _check(html)

    def test_accordion_toggle_does_not_flag(self):
        # Adversarial: href="#" driving a JS accordion (role/aria-expanded) is a
        # legitimate in-page control, not a dead CTA.
        html = ('<html><body><main>'
                '<a href="#" role="button" aria-expanded="false">Toggle section</a>'
                '</main></body></html>')
        assert "PLACEHOLDER_LINK" not in _check(html)

    def test_in_page_anchor_does_not_flag(self):
        html = '<html><body><main><a href="#section-2">Jump to section 2</a></main></body></html>'
        assert "PLACEHOLDER_LINK" not in _check(html)

    def test_wrong_placeholder_domain_flags(self):
        html = '<html><body><main><a href="https://example.com">Contact us</a></main></body></html>'
        assert "WRONG_PLACEHOLDER_LINK" in _check(html)

    def test_legit_external_link_does_not_flag(self):
        # Adversarial: a real external reference must not be mistaken for a placeholder.
        html = '<html><body><main><a href="https://www.canada.ca/funding">Funding</a></main></body></html>'
        codes = _check(html)
        assert "WRONG_PLACEHOLDER_LINK" not in codes


# ---------------------------------------------------------------------------
# WP5 — homepage Organization schema + contact info
# ---------------------------------------------------------------------------

ORG_SCHEMA = (
    '<script type="application/ld+json">'
    '{"@context":"https://schema.org","@type":"Organization","name":"Acme NGO",'
    '"url":"https://example.org"}</script>'
)


class TestHomepageSchemaAndContact:
    def test_homepage_without_org_schema_flags(self):
        html = "<html><head></head><body><main><p>Welcome</p></main></body></html>"
        assert "SCHEMA_ORG_MISSING" in _check(html, is_homepage=True)

    def test_homepage_with_org_schema_does_not_flag(self):
        html = f"<html><head>{ORG_SCHEMA}</head><body><main><p>Welcome</p></main></body></html>"
        assert "SCHEMA_ORG_MISSING" not in _check(html, is_homepage=True)

    def test_non_homepage_not_checked_for_org_schema(self):
        html = "<html><head></head><body><main><p>Welcome</p></main></body></html>"
        assert "SCHEMA_ORG_MISSING" not in _check(html, is_homepage=False)

    def test_homepage_without_contact_flags(self):
        html = "<html><body><main><p>Welcome to our site.</p></main></body></html>"
        assert "CONTACT_INFO_NOT_IN_HTML" in _check(html, is_homepage=True)

    def test_homepage_with_text_contact_does_not_flag(self):
        # Adversarial: footer text contact (email + phone) must not flag.
        html = ('<html><body><main><p>Welcome.</p></main>'
                '<footer>Call 604-555-0100 or email hello@charity.org</footer>'
                '</body></html>')
        assert "CONTACT_INFO_NOT_IN_HTML" not in _check(html, is_homepage=True)

    def test_non_homepage_not_checked_for_contact(self):
        html = "<html><body><main><p>Welcome.</p></main></body></html>"
        assert "CONTACT_INFO_NOT_IN_HTML" not in _check(html, is_homepage=False)


# ---------------------------------------------------------------------------
# WP1 — named AI-crawler robots access (reused check_ai_bot_access)
# ---------------------------------------------------------------------------

def _robots(text: str) -> RobotsData:
    return RobotsData(parser=None, crawl_delay=None, sitemap_urls=[], raw_text=text)


class TestAiBotAccess:
    def test_blanket_disallow_flags(self):
        codes = [i.code for i in check_ai_bot_access(_robots("User-agent: *\nDisallow: /"), BASE)]
        assert "AI_BOT_BLANKET_DISALLOW" in codes

    def test_named_search_bot_blocked_flags(self):
        robots = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: PerplexityBot\nDisallow: /"
        codes = [i.code for i in check_ai_bot_access(_robots(robots), BASE)]
        assert "AI_BOT_SEARCH_BLOCKED" in codes or "AI_BOT_TRAINING_DISALLOWED" in codes

    def test_allow_override_not_blocked(self):
        # GPTBot explicitly allowed — must not be reported as blocked.
        robots = "User-agent: GPTBot\nAllow: /\nDisallow:"
        codes = [i.code for i in check_ai_bot_access(_robots(robots), BASE)]
        assert "AI_BOT_BLANKET_DISALLOW" not in codes

    def test_unreachable_robots_no_issues(self):
        # 5xx/404 → RobotsData.raw_text is None → permissive (no AI-bot issues).
        codes = [i.code for i in check_ai_bot_access(_robots(None), BASE)]
        assert codes == []


# ---------------------------------------------------------------------------
# WP6 — Agent Health score (serialization + monotonicity), store-level
# ---------------------------------------------------------------------------

@pytest.fixture
async def store():
    async with SQLiteJobStore(db_path=":memory:") as s:
        yield s


def _job(pages_crawled: int = 1) -> CrawlJob:
    return CrawlJob(job_id=str(uuid4()), target_url=BASE, status="complete",
                    pages_crawled=pages_crawled)


def _page_rec(job_id: str, url: str) -> CrawledPage:
    return CrawledPage(job_id=job_id, url=url, status_code=200, title="t",
                       meta_description="d", h1_tags=["h"],
                       headings_outline=[{"level": 1, "text": "h"}],
                       crawled_at=datetime.now(timezone.utc))


def _issue(job_id, url, *, category, code, severity="warning", impact=5) -> Issue:
    return Issue(job_id=job_id, page_url=url, category=category, severity=severity,
                 issue_code=code, description="x", recommendation="y", impact=impact)


class TestAgentHealthScore:
    async def test_summary_has_agent_readiness(self, store):
        job = _job()
        url = f"{BASE}/page"
        await store.create_job(job)
        await store.save_pages([_page_rec(job.job_id, url)])
        await store.save_issues([
            _issue(job.job_id, url, category="semantic_html", code="NON_SEMANTIC_BUTTON"),
        ])
        summary = await store.get_summary(job.job_id)
        assert isinstance(summary["agent_health_score"], int)
        assert 0 <= summary["agent_health_score"] <= 100
        assert "agent_readiness" in summary
        assert "breakdown" in summary["agent_readiness"]
        assert isinstance(summary["agent_readiness"]["breakdown"], list)

    async def test_only_agent_issues_affect_agent_score(self, store):
        """A non-agent issue lowers Health but not Agent Health."""
        job = _job()
        url = f"{BASE}/page"
        await store.create_job(job)
        await store.save_pages([_page_rec(job.job_id, url)])
        # A purely SEO issue (metadata) — not agent-relevant.
        await store.save_issues([
            _issue(job.job_id, url, category="metadata", code="TITLE_TOO_SHORT", impact=5),
        ])
        summary = await store.get_summary(job.job_id)
        assert summary["agent_health_score"] == 100  # untouched by the SEO issue
        assert summary["health_score"] < 100

    async def test_agent_score_monotonic_non_increasing(self, store):
        """More failing agent checks must never raise the Agent Health score."""
        job1 = _job()
        url = f"{BASE}/page"
        await store.create_job(job1)
        await store.save_pages([_page_rec(job1.job_id, url)])
        await store.save_issues([
            _issue(job1.job_id, url, category="rendering", code="JS_DEPENDENT_NAVIGATION", impact=5),
        ])
        score_one = (await store.get_summary(job1.job_id))["agent_health_score"]

        job2 = _job()
        await store.create_job(job2)
        await store.save_pages([_page_rec(job2.job_id, url)])
        await store.save_issues([
            _issue(job2.job_id, url, category="rendering", code="JS_DEPENDENT_NAVIGATION", impact=5),
            _issue(job2.job_id, url, category="semantic_html", code="NON_SEMANTIC_BUTTON", impact=4),
            _issue(job2.job_id, url, category="broken_link", code="PLACEHOLDER_LINK", impact=7),
        ])
        score_many = (await store.get_summary(job2.job_id))["agent_health_score"]
        assert score_many <= score_one

    async def test_placeholder_link_counts_toward_agent_score(self, store):
        """PLACEHOLDER_LINK lives in broken_link but must count as an agent issue."""
        job = _job()
        url = f"{BASE}/page"
        await store.create_job(job)
        await store.save_pages([_page_rec(job.job_id, url)])
        await store.save_issues([
            _issue(job.job_id, url, category="broken_link", code="PLACEHOLDER_LINK", impact=7),
        ])
        summary = await store.get_summary(job.job_id)
        assert summary["agent_health_score"] < 100

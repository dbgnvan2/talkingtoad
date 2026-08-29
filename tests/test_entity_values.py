"""E5 — check what the Organization schema SAYS, not just that it exists.

Purpose: prove the four value checks fire on real misconfiguration and stay
         silent on correct data, including the false-positive shapes that would
         make them useless (an online-only org, a real 7-day business, a company
         legitimately called "Example Ltd.").
Spec:    docs/pending/2026-08-29_E5-entity-value-checks.md
Tests:   this file

The real-artifact tests come first (P10/P20). A checker calibrated only on
hand-authored ideal examples is an under-exercised checker — and the negative
case matters as much as the positive one, so both are asserted against markup
that a third-party tool rated "100% markup health".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.config import ConfigError, load_config
from api.crawler.checkers.cross_page import (
    _check_default_hours,
    _check_nap,
    _check_placeholder_values,
    _entity_cfg,
    _is_empty_value,
)
from api.crawler.checkers.registry import _CATALOGUE
from api.crawler.parser import parse_page
from api.crawler.fetcher import FetchResult
from api.crawler.issue_checker import check_cross_page

FIXTURES = Path(__file__).parent / "fixtures" / "entity"
HOME_URL = "https://livingsystems.ca/"


def _page_from_fixture(name: str, url: str = HOME_URL):
    html = (FIXTURES / name).read_text()
    return parse_page(_fetch_result(url, html), url, is_homepage=True)


def _fetch_result(url: str, html: str) -> FetchResult:
    return FetchResult(
        url=url, final_url=url, status_code=200, first_status_code=200,
        headers={"content-type": "text/html"}, html=html,
        content_type="text/html", response_size_bytes=len(html),
    )


def _page_from_graph(graph: list[dict] | dict, url: str = HOME_URL):
    """Build a page whose only JSON-LD is *graph*."""
    body = json.dumps(graph if isinstance(graph, dict) else {"@graph": graph})
    html = (
        "<!DOCTYPE html><html><head><title>A Page With A Good Long Title Here</title>"
        '<meta name="description" content="A description long enough to pass the checks here.">'
        f'<script type="application/ld+json">{body}</script>'
        "</head><body><h1>Page</h1><p>Some words here for the body.</p></body></html>"
    )
    return parse_page(_fetch_result(url, html), url, is_homepage=True)


def _codes(pages, start_url=HOME_URL) -> set[str]:
    return {i.code for i in check_cross_page(pages, start_url)}


def _pad(page, n: int = 3) -> list:
    """check_cross_page gates site checks on a minimum page count."""
    return [page] * n


# ── E5.5 — real artifacts (written first) ──────────────────────────────────


class TestRealHomepage:
    """Values verified against the live livingsystems.ca homepage on 2026-08-29:

        WebSite.description        "site logo"
        Organization.legalName     inconsistent casing
        telephone                  []
        openingHoursSpecification  7 days 09:00-17:00
        @type ["Organization","Place"] with no address node
    """

    @pytest.fixture
    def page(self):
        return _page_from_fixture("livingsystems_home.html")

    def test_e5_5a_real_homepage_expected_findings(self, page):
        codes = _codes(_pad(page))
        assert "ENTITY_HOURS_DEFAULT" in codes
        assert "ENTITY_VALUE_PLACEHOLDER" in codes
        assert "ENTITY_FIELD_EMPTY" in codes
        assert "ENTITY_NAP_INCOMPLETE" in codes

    def test_e5_2a_real_site_logo_description_caught(self, page):
        found = _check_placeholder_values(page, _entity_cfg())
        values = {f["value"].casefold() for f in found}
        assert "site logo" in values

    def test_e5_3a_real_seven_day_default_hours_caught(self, page):
        hours = _check_default_hours(page, _entity_cfg())
        assert hours
        assert hours[0]["days"] >= 7
        assert (hours[0]["opens"], hours[0]["closes"]) == ("09:00", "17:00")

    def test_e5_4a_real_empty_telephone_caught(self, page):
        _missing, empty = _check_nap(page, _entity_cfg())
        assert any(f["field"] == "telephone" for f in empty), (
            "telephone is published as [] — present but empty"
        )

    def test_e5_1a_real_place_without_address_caught(self, page):
        missing, _empty = _check_nap(page, _entity_cfg())
        assert any(m.endswith(".address") for m in missing), (
            "the node is typed Place and carries no address at all"
        )

    def test_e5_5d_site_scoped_deducts_once(self, page):
        """R5.1: 50 copies of the same page must still yield one of each code."""
        issues = check_cross_page(_pad(page, 50), HOME_URL)
        for code in ("ENTITY_HOURS_DEFAULT", "ENTITY_NAP_INCOMPLETE",
                     "ENTITY_FIELD_EMPTY", "ENTITY_VALUE_PLACEHOLDER"):
            assert sum(1 for i in issues if i.code == code) == 1, code


class TestCleanEntityGraph:
    """E5.5b — the negative case. A correctly configured graph must fire none of
    the four; without this the checks are just noise generators."""

    CLEAN = {
        "@type": ["Organization", "LocalBusiness"],
        "name": "Living Systems Counselling and Training",
        "legalName": "Living Systems Counselling and Training Society",
        "description": (
            "A Canadian nonprofit offering Bowen family systems counselling and "
            "training to individuals, families and professionals."
        ),
        "url": "https://livingsystems.ca/",
        "logo": "https://livingsystems.ca/logo.png",
        "telephone": "+1-604-239-2211",
        "email": "info@livingsystems.ca",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "252 Esplanade W Suite 201",
            "addressLocality": "North Vancouver",
            "addressRegion": "BC",
            "postalCode": "V7M 0E9",
            "addressCountry": "CA",
        },
        "openingHoursSpecification": [{
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens": "09:00", "closes": "17:00",
        }],
    }

    def test_e5_5b_clean_graph_no_findings(self):
        codes = _codes(_pad(_page_from_graph([self.CLEAN])))
        for code in ("ENTITY_HOURS_DEFAULT", "ENTITY_NAP_INCOMPLETE",
                     "ENTITY_FIELD_EMPTY", "ENTITY_VALUE_PLACEHOLDER"):
            assert code not in codes, code


# ── E5.1 — NAP completeness ────────────────────────────────────────────────


class TestNapCompleteness:
    def test_e5_1a_place_without_address(self):
        page = _page_from_graph([{"@type": ["Organization", "Place"], "name": "X",
                                  "url": "https://x/", "logo": "https://x/l.png"}])
        missing, _ = _check_nap(page, _entity_cfg())
        assert any(m.endswith(".address") for m in missing)
        assert any(m.endswith(".telephone") for m in missing)

    def test_e5_1a_hollow_address_subfields_reported(self):
        page = _page_from_graph([{
            "@type": "LocalBusiness", "name": "X", "url": "https://x/",
            "logo": "https://x/l.png", "telephone": "+1", "email": "a@x.com",
            "address": {"@type": "PostalAddress", "addressLocality": "Vancouver"},
        }])
        missing, _ = _check_nap(page, _entity_cfg())
        assert any(m.endswith("address.postalCode") for m in missing)
        assert not any(m.endswith("address.addressLocality") for m in missing)

    def test_e5_1b_complete_nap_clean(self):
        page = _page_from_graph([TestCleanEntityGraph.CLEAN])
        missing, empty = _check_nap(page, _entity_cfg())
        assert missing == [] and empty == []

    def test_e5_1c_online_only_org_not_flagged_for_address(self):
        """Adversarial (P7). An Organization with no premises must not be told to
        invent a street address — only a declared Place/LocalBusiness is."""
        page = _page_from_graph([{
            "@type": "Organization", "name": "Remote Co",
            "url": "https://x/", "logo": "https://x/l.png",
            "sameAs": ["https://linkedin.com/company/x"],
        }])
        missing, _ = _check_nap(page, _entity_cfg())
        assert not any("address" in m for m in missing)
        assert not any("telephone" in m for m in missing)

    def test_e5_1c_partners_page_not_flagged_for_third_party_gaps(self):
        """Adversarial (P7). A page listing several Organization nodes (partners,
        funders, a member directory) is a third-party context. Telling the
        operator that a partner's address is missing would be noise, and it is
        not theirs to fix. Only nodes whose url shares the page host count."""
        page = _page_from_graph([
            {"@type": "Organization", "name": "Partner A", "url": "https://partner-a.org/"},
            {"@type": "Organization", "name": "Partner B", "url": "https://partner-b.org/"},
            {"@type": "Organization", "name": "Partner C"},
        ], url="https://livingsystems.ca/partners/")
        missing, empty = _check_nap(page, _entity_cfg())
        assert missing == [] and empty == []

    def test_e5_1c_own_node_still_checked_among_partners(self):
        """The guard must not silence the site's OWN incomplete node just because
        partners are listed alongside it."""
        page = _page_from_graph([
            {"@type": "Organization", "name": "Partner A", "url": "https://partner-a.org/"},
            {"@type": ["Organization", "Place"], "name": "Us",
             "url": "https://livingsystems.ca/"},
        ], url="https://livingsystems.ca/partners/")
        missing, _ = _check_nap(page, _entity_cfg())
        assert any(m.endswith(".address") for m in missing)
        assert not any("partner" in m.casefold() for m in missing)

    def test_e5_1c_single_node_needs_no_url_match(self):
        """With exactly one entity node there is nothing to disambiguate, so a
        node without a url is still checked."""
        page = _page_from_graph([{"@type": ["Organization", "Place"], "name": "Us"}])
        missing, _ = _check_nap(page, _entity_cfg())
        assert missing, "a lone entity node is the site's own"

    def test_e5_1c_online_only_org_emits_nothing(self):
        codes = _codes(_pad(_page_from_graph([{
            "@type": "Organization", "name": "Remote Co",
            "url": "https://x/", "logo": "https://x/l.png",
        }])))
        assert "ENTITY_NAP_INCOMPLETE" not in codes


# ── E5.2 — placeholder values ──────────────────────────────────────────────


class TestPlaceholderValues:
    def test_e5_2a_site_logo_description(self):
        page = _page_from_graph([{"@type": "WebSite", "name": "X",
                                  "description": "site logo"}])
        found = _check_placeholder_values(page, _entity_cfg())
        assert any(f["field"] == "description" for f in found)

    def test_e5_2a_default_wordpress_tagline(self):
        page = _page_from_graph([{"@type": "WebSite", "name": "X",
                                  "description": "Just another WordPress site"}])
        assert _check_placeholder_values(page, _entity_cfg())

    def test_e5_2b_real_description_clean(self):
        page = _page_from_graph([{
            "@type": "WebSite", "name": "Living Systems",
            "description": ("A Canadian nonprofit offering Bowen family systems "
                            "counselling and training."),
        }])
        assert _check_placeholder_values(page, _entity_cfg()) == []

    def test_e5_2b_short_description_flagged_with_reason(self):
        page = _page_from_graph([{"@type": "WebSite", "name": "X",
                                  "description": "Counselling services"}])
        found = _check_placeholder_values(page, _entity_cfg())
        assert found and "under" in found[0]["reason"]

    def test_e5_2c_legitimate_name_containing_example(self):
        """Adversarial (P7). "Example Ltd." is a real company name; matching is
        on the whole trimmed value, not a substring."""
        page = _page_from_graph([{"@type": "Organization", "name": "Example Ltd.",
                                  "url": "https://x/", "logo": "https://x/l.png"}])
        found = _check_placeholder_values(page, _entity_cfg())
        assert not any(f["field"] == "name" for f in found)

    def test_e5_2c_bare_example_still_caught(self):
        page = _page_from_graph([{"@type": "Organization", "name": "Example",
                                  "url": "https://x/", "logo": "https://x/l.png"}])
        found = _check_placeholder_values(page, _entity_cfg())
        assert any(f["field"] == "name" for f in found)

    def test_e5_2a_matching_is_case_insensitive(self):
        page = _page_from_graph([{"@type": "WebSite", "name": "X",
                                  "description": "  Site Logo  "}])
        assert _check_placeholder_values(page, _entity_cfg())


# ── E5.3 — default opening hours ───────────────────────────────────────────


class TestDefaultHours:
    def _hours(self, days, opens="09:00", closes="17:00"):
        return _page_from_graph([{
            "@type": "LocalBusiness", "name": "X",
            "openingHoursSpecification": [{
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": days, "opens": opens, "closes": closes,
            }],
        }])

    ALL_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday"]
    WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    def test_e5_3a_seven_day_default_hours(self):
        assert _check_default_hours(self._hours(self.ALL_DAYS), _entity_cfg())

    def test_e5_3b_weekday_hours_clean(self):
        assert _check_default_hours(self._hours(self.WEEKDAYS), _entity_cfg()) == []

    def test_e5_3c_seven_day_non_default_clean(self):
        """A genuine seven-day business at real hours must not be flagged."""
        assert _check_default_hours(
            self._hours(self.ALL_DAYS, "08:00", "20:00"), _entity_cfg()
        ) == []

    def test_e5_3b_no_hours_at_all_clean(self):
        page = _page_from_graph([{"@type": "LocalBusiness", "name": "X"}])
        assert _check_default_hours(page, _entity_cfg()) == []


# ── E5.4 — empty vs missing ────────────────────────────────────────────────


class TestEmptyVersusMissing:
    def test_e5_4a_empty_array_is_empty_not_missing(self):
        page = _page_from_graph([{
            "@type": "LocalBusiness", "name": "X", "url": "https://x/",
            "logo": "https://x/l.png", "telephone": [], "email": "a@x.com",
            "address": {"@type": "PostalAddress", "streetAddress": "1 St",
                        "addressLocality": "V", "addressRegion": "BC",
                        "postalCode": "V0V", "addressCountry": "CA"},
        }])
        missing, empty = _check_nap(page, _entity_cfg())
        assert any(f["field"] == "telephone" for f in empty)
        assert not any(m.endswith(".telephone") for m in missing)

    @pytest.mark.parametrize("value", [[], "", "   ", {}, None])
    def test_e5_4a_empty_value_shapes(self, value):
        assert _is_empty_value(value) is True

    @pytest.mark.parametrize("value", ["+1-604-555-0100", ["a"], {"k": "v"}, 0, False])
    def test_e5_4a_non_empty_value_shapes(self, value):
        assert _is_empty_value(value) is False


# ── E5.5 — registry parity and config integrity ────────────────────────────


class TestRegistryAndConfig:
    CODES = ["ENTITY_HOURS_DEFAULT", "ENTITY_NAP_INCOMPLETE",
             "ENTITY_FIELD_EMPTY", "ENTITY_VALUE_PLACEHOLDER"]

    @pytest.mark.parametrize("code", CODES)
    def test_e5_5c_code_in_catalogue_and_site_scoped(self, code):
        spec = _CATALOGUE[code]
        assert spec.category == "ai_readiness"
        assert spec.scope == "site"
        assert spec.fixability == "developer_needed", (
            "these are SEO-plugin settings; the WordPress-safety constraint "
            "forbids TalkingToad writing them"
        )

    def test_e5_2a_config_loads_with_required_keys(self):
        cfg = _entity_cfg()
        assert cfg["placeholder_values"] and cfg["placeholder_fields"]
        assert cfg["default_hours"]["days"] == 7

    def test_e5_2c_bad_config_fails_loud(self):
        """P2: a malformed config must raise, not silently default."""
        with pytest.raises(ConfigError):
            load_config("entity_values", required_keys=("a_key_that_does_not_exist",))

    def test_e5_2c_missing_config_fails_loud(self):
        with pytest.raises(ConfigError):
            load_config("no_such_config_file_exists")

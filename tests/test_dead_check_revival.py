"""AF7 — the four dead checks must be able to fire (or be honestly inert).

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF7
Audit: docs/audit/2026-08-30_full-check-audit.md (F1, F2, F3, F18)
"""
from __future__ import annotations

import datetime
import json
import pathlib
from types import SimpleNamespace
from unittest.mock import patch

from api.crawler.robots import RobotsData, _parse_robots
from api.services.ai_readiness import check_ai_bot_access
from api.services.extractability import diagnose_extractability

ORIGIN = "https://example.com"


def _robots(text="User-agent: *\nAllow: /\n"):
    parser, delay, sitemaps = _parse_robots(f"{ORIGIN}/robots.txt", text)
    return RobotsData(parser, delay, sitemaps, text)


def _codes(rd):
    return {i.code for i in check_ai_bot_access(rd, ORIGIN)}


class TestAiBotTableStale:
    def test_af7a_stale_table_emits_the_code(self):
        """validate_table_freshness() had a full implementation, a catalogue
        entry, help text, a spec line calling it shipped — and zero callers."""
        with patch("api.services.ai_bots.LAST_REVIEWED", datetime.datetime(2020, 1, 1)):
            assert "AI_BOT_TABLE_STALE" in _codes(_robots())

    def test_af7a_fresh_table_does_not_emit(self):
        """Adversarial: wiring it must not make it fire always."""
        with patch("api.services.ai_bots.LAST_REVIEWED", datetime.datetime.now()):
            assert "AI_BOT_TABLE_STALE" not in _codes(_robots())

    def test_af7a_cadence_is_one_source_of_truth(self):
        """The docstring promised 6 months while the constant enforced 365 days,
        so the review date the file advertised was not the one it checked."""
        from api.services import ai_bots

        assert ai_bots.REVIEW_CADENCE_DAYS == 180
        assert "every 6 months" not in (ai_bots.__doc__ or "")


class TestSchemaDeprecations:
    def test_af7c_deprecated_list_lives_in_config(self):
        path = pathlib.Path("api/config/schema_deprecations.json")
        assert path.exists()
        assert "deprecated_types" in json.loads(path.read_text())

    def test_af7c_breadcrumblist_is_not_reported_deprecated(self):
        """The real type, on 156 pages of a customer site. The old hardcoded
        {'Breadcrumb'} could not match it, and its own comment admitted the
        entry was not actually deprecated."""
        from api.services.schema_typing import _check_deprecated_schemas

        assert _check_deprecated_schemas(["BreadcrumbList"]) is None

    def test_af7c_config_drives_the_check(self):
        """Adversarial: the check must still work when the config has entries."""
        import api.services.schema_typing as st

        with patch.object(st, "_DEPRECATED_SCHEMAS", {"SomeRetiredType"}):
            assert st._check_deprecated_schemas(["SomeRetiredType"]) == "SomeRetiredType"


class TestContentImageHeavy:
    @staticmethod
    def _page(word_count, headings, images):
        return SimpleNamespace(
            word_count=word_count, headings_outline=[{"level": 2}] * headings,
            links=[], image_urls=[f"/i{n}.jpg" for n in range(images)],
            has_json_ld=True, has_viewport_meta=True, text_to_html_ratio=None)

    def test_af7c_image_heavy_page_is_diagnosed(self):
        """Unreachable before: max 20 deductions against a 50-point threshold.
        Proven over 900 input combinations, and 0 firings in 156 jobs."""
        assert diagnose_extractability(self._page(300, 1, 20)) == "CONTENT_IMAGE_HEAVY"

    def test_af7c_ordinary_page_is_not_diagnosed(self):
        """Adversarial: raising the weight must not flag normal pages."""
        assert diagnose_extractability(self._page(300, 5, 2)) is None

    def test_af7c_higher_priority_diagnosis_still_wins(self):
        """The ladder order must survive the weight change."""
        assert diagnose_extractability(self._page(50, 1, 0)) == "CONTENT_THIN"

"""E4 — site-wide prevalence: how much of the estate one defect touches.

Purpose: prove the prevalence lens escalates template-wide defects, that it does
         NOT move any score, and that its thresholds cannot fire on a small site.
Spec:    docs/pending/2026-08-29_E4-site-prevalence-escalation.md
Tests:   this file

The scoring-invariance test comes first (P10). The single largest risk in E4 is
silently moving the health score while claiming not to; every other test here is
worth less than that one.
"""

from __future__ import annotations

import pytest

from api.config import ConfigError, load_config
from api.crawler.checkers.registry import _CATALOGUE, _ISSUE_SCORING
from api.services.job_store_base import compute_page_health
from api.services.prevalence import (
    Prevalence,
    as_dicts,
    compute_prevalence,
    count_indexable_pages,
    site_hygiene_score,
    systemic,
)


def _rows(code: str, n: int, prefix: str = "https://x/p") -> list[tuple]:
    """(code, url, impact, severity, category) — the shape build_prevalence passes.

    Impact and severity come from the catalogue HERE because these fixtures stand
    in for a freshly-crawled job, where stored and derived agree by construction.
    The point of P5.4 is what happens when they stop agreeing, and
    tests/test_prevalence_agreement.py is where that is pinned.
    """
    from api.crawler.checkers.registry import derive_impact, severity_from_impact

    spec = _CATALOGUE.get(code)
    impact = derive_impact(code) if spec else 0
    return [(code, f"{prefix}{i}", impact, severity_from_impact(impact),
             spec.category if spec else "metadata") for i in range(n)]


# ── E4.4a — scoring must not move (written first) ──────────────────────────


class TestScoringUnchanged:
    def test_e4_4a_health_unchanged_by_prevalence(self):
        """E4 must not touch any scoring input. Computing prevalence over a set
        of rows must leave the health those rows produce byte-identical."""
        rows = [
            ("META_DESC_MISSING", _ISSUE_SCORING["META_DESC_MISSING"][0], "metadata"),
            ("TITLE_TOO_LONG", _ISSUE_SCORING["TITLE_TOO_LONG"][0], "metadata"),
            ("H1_MISSING", _ISSUE_SCORING["H1_MISSING"][0], "heading"),
        ]
        before = compute_page_health(list(rows))
        compute_prevalence(_rows("META_DESC_MISSING", 56), 272)
        after = compute_page_health(list(rows))
        assert before == after

    def test_e4_4a_health_unchanged_across_many_codes(self):
        """A broader invariance check: computing prevalence over a realistic
        mixed finding set must not move any per-page health value."""
        pages = {
            "a": [("META_DESC_MISSING", 2, "metadata"), ("TITLE_TOO_LONG", 1, "metadata")],
            "b": [("H1_MISSING", 4, "heading"), ("CONTENT_THIN", 4, "ai_readiness")],
            "c": [("BROKEN_LINK_404", 2, "broken_link")],
        }
        before = {k: compute_page_health(list(v)) for k, v in pages.items()}
        rows = _rows("META_DESC_MISSING", 56) + _rows("CONSENT_MODE_MISSING", 170, "https://y/p")
        compute_prevalence(rows, 272)
        after = {k: compute_page_health(list(v)) for k, v in pages.items()}
        assert before == after

    def test_e4_4a_module_does_not_import_scoring_writers(self):
        """A grep-style guard: prevalence reads the catalogue, never mutates it."""
        import inspect

        from api.services import prevalence as mod

        src = inspect.getsource(mod)
        assert "_ISSUE_SCORING[" not in src.replace("_ISSUE_SCORING[code]", "")
        assert "_CATALOGUE[code] =" not in src
        assert ".severity =" not in src


# ── E4.1 — the denominator ─────────────────────────────────────────────────


class TestDenominator:
    def test_e4_1a_denominator_is_indexable_only(self):
        urls = [f"https://x/p{i}" for i in range(10)]
        hidden = [("NOINDEX_META", f"https://x/p{i}") for i in range(4)]
        assert count_indexable_pages(urls, hidden) == 6

    def test_e4_1a_trailing_slash_does_not_double_count(self):
        urls = ["https://x/a", "https://x/a/"]
        assert count_indexable_pages(urls, []) == 1

    @pytest.mark.parametrize("code", ["NOINDEX_META", "NOINDEX_HEADER", "ROBOTS_BLOCKED"])
    def test_e4_1a_every_hidden_code_reduces_denominator(self, code):
        assert count_indexable_pages(["https://x/a"], [(code, "https://x/a")]) == 0

    def test_e4_1c_noindex_archive_does_not_dilute_share(self):
        """Adversarial (P7). 200 noindex'd archive pages must not turn a
        56-of-60 defect into a 22% share."""
        real = [f"https://x/real{i}" for i in range(60)]
        archive = [f"https://x/tag/{i}" for i in range(200)]
        hidden = [("NOINDEX_META", u) for u in archive]
        indexable = count_indexable_pages(real + archive, hidden)
        assert indexable == 60

        rows = [("META_DESC_MISSING", u) for u in real[:56]] + hidden
        prev = compute_prevalence(rows, indexable)
        meta = next(p for p in prev if p.code == "META_DESC_MISSING")
        assert meta.share > 0.9
        assert meta.tier == "systemic"

    def test_e4_1a_zero_denominator_returns_nothing(self):
        assert compute_prevalence(_rows("META_DESC_MISSING", 5), 0) == []


# ── E4.1b — codes that fire once by design get no share ────────────────────


class TestExclusions:
    @pytest.mark.parametrize("code", ["ENTITY_NAME_INCONSISTENT", "MISSING_HSTS",
                                      "ENTITY_HOURS_DEFAULT"])
    def test_e4_1b_site_scoped_codes_excluded(self, code):
        prev = compute_prevalence([(code, "https://x/a")], 100)
        assert not any(p.code == code for p in prev), (
            "a site-scoped code fires once by design; a 1% share would be a lie"
        )

    @pytest.mark.parametrize("code", ["FAVICON_MISSING", "SITEMAP_MISSING",
                                      "LLMS_TXT_MISSING"])
    def test_e4_1b_job_level_codes_excluded(self, code):
        prev = compute_prevalence([(code, "https://x/a")], 100)
        assert not any(p.code == code for p in prev)

    def test_e4_1b_unknown_code_is_kept_not_dropped(self):
        """SUPERSEDED by P5.4 (2026-09-04). This asserted `prev == []` — that a
        code the catalogue does not know is silently ignored.

        That expectation was the defect. Six codes deleted in the §7 merge hold
        4,559 rows in the live database; those rows appear in the issue lists,
        are counted in `by_severity` and charge the health score, and prevalence
        dropped them without a word. A code the catalogue has forgotten is still
        a finding that was made.

        The half worth keeping — it must not crash — is kept.
        """
        prev = compute_prevalence(
            [("NOT_A_REAL_CODE", "https://x/a", 3, "info", "metadata")], 100)
        assert len(prev) == 1
        assert prev[0].code == "NOT_A_REAL_CODE"
        assert prev[0].impact == 3 and prev[0].severity == "info"

    def test_e4_2a_never_escalate_codes_stay_scattered(self):
        prev = compute_prevalence(_rows("EXTERNAL_LINK_SKIPPED", 90), 100)
        assert prev[0].tier == "scattered"


# ── E4.2 — tiers ───────────────────────────────────────────────────────────


class TestTiers:
    def test_e4_3a_real_job_tiers(self):
        """The real job-05cd2496 numbers: CONSENT_MODE_MISSING 170/272 (63%) is
        systemic; META_DESC_MISSING 56/272 (21%) is widespread."""
        rows = _rows("CONSENT_MODE_MISSING", 170) + _rows("META_DESC_MISSING", 56, "https://y/p")
        prev = {p.code: p for p in compute_prevalence(rows, 272)}
        assert prev["CONSENT_MODE_MISSING"].tier == "systemic"
        assert prev["META_DESC_MISSING"].tier == "widespread"

    def test_e4_2b_small_site_not_falsely_systemic(self):
        """3 of 8 pages is 38% — over the share gate, under the count gate."""
        prev = compute_prevalence(_rows("META_DESC_MISSING", 3), 8)
        assert prev[0].share > 0.30
        assert prev[0].tier == "scattered", "min_pages must also be satisfied"

    def test_e4_2b_high_count_low_share_not_systemic(self):
        """20 of 5,000 pages is a lot of pages and almost none of the site."""
        prev = compute_prevalence(_rows("META_DESC_MISSING", 20), 5000)
        assert prev[0].pages_affected == 20
        assert prev[0].tier == "scattered"

    def test_e4_2a_always_systemic_overrides_thresholds(self):
        """A handful of broken targets is still a template fix."""
        prev = compute_prevalence(_rows("BROKEN_LINK_404", 2), 272)
        assert prev[0].tier == "systemic"

    def test_e4_1a_ordering_is_most_prevalent_first(self):
        rows = (_rows("CONSENT_MODE_MISSING", 170)
                + _rows("META_DESC_MISSING", 56, "https://y/p")
                + _rows("TITLE_TOO_LONG", 29, "https://z/p"))
        prev = compute_prevalence(rows, 272)
        assert [p.code for p in prev][0] == "CONSENT_MODE_MISSING"
        weights = [p.tier_weight for p in prev]
        assert weights == sorted(weights, reverse=True)


# ── E4.4 — Site Hygiene ────────────────────────────────────────────────────


class TestSiteHygiene:
    def test_e4_4c_clean_site_scores_100(self):
        assert site_hygiene_score([]) == 100

    def test_e4_4b_hygiene_monotonic(self):
        """More pages affected must never RAISE hygiene."""
        previous = 101
        for n in (25, 60, 120, 200, 272):
            score = site_hygiene_score(compute_prevalence(_rows("CONSENT_MODE_MISSING", n), 272))
            assert score <= previous, f"{n} pages scored higher than fewer pages"
            previous = score

    def test_e4_4b_scattered_defects_cost_nothing(self):
        """Only escalated tiers carry weight — hygiene is a breadth measure."""
        assert site_hygiene_score(compute_prevalence(_rows("META_DESC_MISSING", 3), 272)) == 100

    def test_e4_4b_score_is_clamped(self):
        rows = []
        for i, code in enumerate(["CONSENT_MODE_MISSING", "SEMANTIC_DENSITY_LOW",
                                  "CONVERSATIONAL_H2_MISSING", "LANDMARK_MAIN_MISSING",
                                  "ANCHOR_TEXT_GENERIC"]):
            rows += _rows(code, 272, f"https://x{i}/p")
        score = site_hygiene_score(compute_prevalence(rows, 272))
        assert 0 <= score <= 100

    def test_e4_4a_hygiene_is_not_health(self):
        """They answer different questions and must be allowed to disagree."""
        prev = compute_prevalence(_rows("CONSENT_MODE_MISSING", 200), 272)
        assert site_hygiene_score(prev) < 100


# ── E4.2c — config integrity ───────────────────────────────────────────────


class TestConfig:
    def test_e4_2a_config_codes_exist_in_catalogue(self):
        cfg = load_config("prevalence", required_keys=("never_escalate", "always_systemic",
                                                       "job_level_codes", "tiers"))
        for key in ("never_escalate", "always_systemic", "job_level_codes"):
            for code in cfg[key]:
                assert code in _CATALOGUE, f"{key} names an unknown code: {code}"

    def test_e4_2a_tiers_have_required_fields(self):
        cfg = load_config("prevalence", required_keys=("tiers",))
        for tier in cfg["tiers"]:
            assert {"name", "min_share", "min_pages", "weight", "label"} <= set(tier)

    def test_e4_2a_a_scattered_fallback_tier_exists(self):
        cfg = load_config("prevalence", required_keys=("tiers",))
        assert any(float(t["min_share"]) == 0.0 and int(t["min_pages"]) == 0
                   for t in cfg["tiers"]), "every code must land in some tier"

    def test_e4_2c_bad_config_fails_loud(self):
        with pytest.raises(ConfigError):
            load_config("prevalence", required_keys=("a_key_that_does_not_exist",))


# ── E4.3 — serialisation ───────────────────────────────────────────────────


class TestSerialisation:
    def test_e4_3c_as_dicts_is_json_safe(self):
        import json

        prev = compute_prevalence(_rows("META_DESC_MISSING", 56), 272)
        json.dumps(as_dicts(prev))

    def test_e4_3c_dict_carries_the_reader_facing_fields(self):
        row = as_dicts(compute_prevalence(_rows("META_DESC_MISSING", 56), 272))[0]
        assert row["pages_affected"] == 56
        assert row["indexable_pages"] == 272
        assert row["human_description"]
        assert row["tier_label"]

    def test_e4_3a_systemic_filter(self):
        rows = _rows("CONSENT_MODE_MISSING", 170) + _rows("TITLE_TOO_LONG", 3, "https://y/p")
        assert [p.code for p in systemic(compute_prevalence(rows, 272))] == [
            "CONSENT_MODE_MISSING"
        ]

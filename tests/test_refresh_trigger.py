"""Tests for M6.3 — Automated Refresh Trigger (evaluate_refresh)."""

from datetime import date

import pytest

from api.services.refresh_trigger import evaluate_refresh, ReviewFlag
from api.models.performance import PerformanceRecord

TODAY = date(2026, 6, 1)


def _make_record(
    period: str,
    clicks: int = 0,
    impressions: int = 0,
    last_improvement: date | None = None,
    created: date | None = None,
) -> PerformanceRecord:
    return PerformanceRecord(
        url="https://example.com/page",
        period=period,
        created_at=created.isoformat() if created else None,
        last_technical_improvement_at=last_improvement.isoformat() if last_improvement else None,
        gsc_clicks_mo=clicks,
        gsc_impressions_mo=impressions,
        gsc_ctr_mo=0.0,
        gsc_avg_position_mo=10.0,
        recorded_at="2026-01-01T00:00:00",
    )


class TestStaleness:
    def test_stale(self):
        records = [_make_record("2026-01", last_improvement=date(2025, 10, 1))]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert result.flagged
        assert "Staleness" in result.reasons

    def test_not_stale(self):
        records = [_make_record("2026-05", last_improvement=date(2026, 5, 1))]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert "Staleness" not in result.reasons

    def test_stale_fallback_to_created(self):
        records = [_make_record("2026-01", last_improvement=None, created=date(2025, 9, 1))]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert result.flagged
        assert "Staleness" in result.reasons

    def test_no_dates_no_staleness(self):
        records = [_make_record("2026-01", last_improvement=None, created=None)]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert "Staleness" not in result.reasons


class TestTrafficDecay:
    def test_decayed(self):
        records = [
            _make_record("2026-01", clicks=100),
            _make_record("2026-02", clicks=100),
            _make_record("2026-03", clicks=50),
        ]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert result.flagged
        assert "Traffic Decay" in result.reasons

    def test_not_decayed(self):
        records = [
            _make_record("2026-01", clicks=100),
            _make_record("2026-02", clicks=100),
            _make_record("2026-03", clicks=100),
        ]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert "Traffic Decay" not in result.reasons

    def test_insufficient_history(self):
        records = [_make_record("2026-03", clicks=100)]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert "Traffic Decay" not in result.reasons

    def test_zero_clicks_no_divide_by_zero(self):
        records = [
            _make_record("2026-01", clicks=0),
            _make_record("2026-02", clicks=0),
            _make_record("2026-03", clicks=0),
        ]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert "Traffic Decay" not in result.reasons


class TestCombined:
    def test_both_stale_and_decayed(self):
        records = [
            _make_record("2026-01", clicks=100, last_improvement=date(2025, 9, 1)),
            _make_record("2026-02", clicks=100, last_improvement=date(2025, 9, 1)),
            _make_record("2026-03", clicks=50, last_improvement=date(2025, 9, 1)),
        ]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert "Staleness" in result.reasons
        assert "Traffic Decay" in result.reasons

    def test_fresh_and_stable(self):
        records = [
            _make_record("2026-05", clicks=100, last_improvement=date(2026, 5, 1)),
        ]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert not result.flagged
        assert result.reasons == []


class TestAdversarial:
    def test_empty_records(self):
        result = evaluate_refresh([], health_score=70, today=TODAY)
        assert not result.flagged
        assert result.reasons == []

    def test_single_record(self):
        records = [_make_record("2026-03", clicks=100)]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert "Traffic Decay" not in result.reasons


class TestMatrixTriggers:
    def test_vulnerable_star(self):
        records = [_make_record("2026-03", impressions=150)]
        result = evaluate_refresh(records, health_score=50, today=TODAY)
        assert "Vulnerable Star" in result.reasons

    def test_not_vulnerable_star_low_impressions(self):
        records = [_make_record("2026-03", impressions=50)]
        result = evaluate_refresh(records, health_score=50, today=TODAY)
        assert "Vulnerable Star" not in result.reasons

    def test_not_vulnerable_star_high_health(self):
        records = [_make_record("2026-03", impressions=150)]
        result = evaluate_refresh(records, health_score=70, today=TODAY)
        assert "Vulnerable Star" not in result.reasons

    def test_hidden_gem(self):
        records = [_make_record("2026-03", clicks=0, impressions=5)]
        result = evaluate_refresh(records, health_score=90, today=TODAY)
        assert "Hidden Gem" in result.reasons

    def test_not_hidden_gem_has_clicks(self):
        records = [_make_record("2026-03", clicks=1, impressions=5)]
        result = evaluate_refresh(records, health_score=90, today=TODAY)
        assert "Hidden Gem" not in result.reasons

    def test_not_hidden_gem_low_health(self):
        records = [_make_record("2026-03", clicks=0, impressions=5)]
        result = evaluate_refresh(records, health_score=50, today=TODAY)
        assert "Hidden Gem" not in result.reasons

    def test_not_hidden_gem_high_impressions(self):
        records = [_make_record("2026-03", clicks=0, impressions=15)]
        result = evaluate_refresh(records, health_score=90, today=TODAY)
        assert "Hidden Gem" not in result.reasons


class TestDeterminism:
    """Verify evaluate_refresh is a pure, deterministic function."""

    def test_unsorted_records_same_result(self):
        """Records passed in any order produce the same result."""
        records_asc = [
            _make_record("2026-01", clicks=100, last_improvement=date(2025, 9, 1)),
            _make_record("2026-02", clicks=100, last_improvement=date(2025, 9, 1)),
            _make_record("2026-03", clicks=50, last_improvement=date(2025, 9, 1)),
        ]
        records_desc = list(reversed(records_asc))
        result_asc = evaluate_refresh(records_asc, health_score=70, today=TODAY)
        result_desc = evaluate_refresh(records_desc, health_score=70, today=TODAY)
        assert result_asc.flagged == result_desc.flagged
        assert sorted(result_asc.reasons) == sorted(result_desc.reasons)

    def test_repeated_calls_identical(self):
        """Same inputs always produce the same output."""
        records = [_make_record("2026-03", clicks=50, impressions=150)]
        r1 = evaluate_refresh(records, health_score=50, today=TODAY)
        r2 = evaluate_refresh(records, health_score=50, today=TODAY)
        assert r1.flagged == r2.flagged
        assert r1.reasons == r2.reasons

    def test_review_flag_immutable(self):
        """ReviewFlag is frozen — cannot mutate after creation."""
        flag = ReviewFlag(flagged=True, reasons=["Staleness"])
        with pytest.raises(AttributeError):
            flag.flagged = False  # type: ignore[misc]

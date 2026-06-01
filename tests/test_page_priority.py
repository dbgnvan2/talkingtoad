"""Tests for the Page Priority Work Queue (ranking helper + endpoint).

The ranking helpers in api/services/refresh_trigger.py are pure/deterministic.
The endpoint GET /api/crawl/{job_id}/page-priority assembles health + GSC +
ReviewFlag and ranks. Spec: docs/pending/2026-06-01_page_priority_work_queue.md
"""

from api.services.refresh_trigger import (
    ReviewFlag,
    classify_page_bucket,
    rank_pages,
)


class TestClassifyBucket:
    def test_vulnerable_star_is_top_priority(self):
        w, label = classify_page_bucket(40, ReviewFlag(True, ["Vulnerable Star"]))
        assert label == "Vulnerable Star"
        assert w == 0

    def test_decay_outranks_stale(self):
        w_decay, _ = classify_page_bucket(70, ReviewFlag(True, ["Traffic Decay"]))
        w_stale, _ = classify_page_bucket(70, ReviewFlag(True, ["Staleness"]))
        assert w_decay < w_stale

    def test_no_flag_low_health_bucketed_by_health(self):
        # health below the vulnerable-star health threshold (60) but no GSC flag
        w, label = classify_page_bucket(45, ReviewFlag(False, []))
        assert label == "Low Health"

    def test_no_flag_healthy_is_ok(self):
        w, label = classify_page_bucket(95, ReviewFlag(False, []))
        assert label == "OK"

    def test_hidden_gem_is_low_urgency(self):
        w_gem, _ = classify_page_bucket(90, ReviewFlag(True, ["Hidden Gem"]))
        w_lowhealth, _ = classify_page_bucket(40, ReviewFlag(False, []))
        # Hidden Gem (opportunity) ranks AFTER a low-health page (urgent)
        assert w_lowhealth < w_gem


class TestRankPages:
    def test_ranks_vulnerable_star_first_then_worst_health(self):
        pages = [
            {"url": "https://x/ok", "health_score": 95, "review_flag": ReviewFlag(False, [])},
            {"url": "https://x/star", "health_score": 40, "review_flag": ReviewFlag(True, ["Vulnerable Star"])},
            {"url": "https://x/weak", "health_score": 30, "review_flag": ReviewFlag(False, [])},
            {"url": "https://x/weaker", "health_score": 10, "review_flag": ReviewFlag(False, [])},
        ]
        ranked = rank_pages(pages)
        # Vulnerable Star first
        assert ranked[0]["url"] == "https://x/star"
        assert ranked[0]["priority_rank"] == 1
        # then worst-health among the unflagged low-health pages
        assert ranked[1]["url"] == "https://x/weaker"
        assert ranked[2]["url"] == "https://x/weak"
        # healthy OK page last
        assert ranked[-1]["url"] == "https://x/ok"
        assert ranked[-1]["bucket"] == "OK"

    def test_priority_rank_is_1_based_and_contiguous(self):
        pages = [
            {"url": f"https://x/{i}", "health_score": 50 + i, "review_flag": ReviewFlag(False, [])}
            for i in range(5)
        ]
        ranked = rank_pages(pages)
        assert [p["priority_rank"] for p in ranked] == [1, 2, 3, 4, 5]

    def test_deterministic_tie_break_by_url(self):
        pages = [
            {"url": "https://x/b", "health_score": 50, "review_flag": ReviewFlag(False, [])},
            {"url": "https://x/a", "health_score": 50, "review_flag": ReviewFlag(False, [])},
        ]
        ranked = rank_pages(pages)
        assert [p["url"] for p in ranked] == ["https://x/a", "https://x/b"]

    def test_empty(self):
        assert rank_pages([]) == []

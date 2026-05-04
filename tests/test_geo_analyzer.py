"""
Tests for api/services/geo_analyzer.py.

Spec: docs/implementation_plan_geo_analyzer_2026-05-03.md#GEO.10

Uses mock LLM responses to avoid real API calls.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from api.services.geo_analyzer import (
    GEOReport,
    GEOFinding,
    _safe_json,
    _resolve_model,
    _extract_sections,
    _compute_scores,
    generate_geo_report,
)


# ---------------------------------------------------------------------------
# _safe_json
# ---------------------------------------------------------------------------

class TestSafeJson:
    def test_parses_plain_json(self):
        result = _safe_json('[{"key": "value"}]')
        assert result == [{"key": "value"}]

    def test_parses_fenced_json(self):
        result = _safe_json("```json\n[{\"key\": \"value\"}]\n```")
        assert result == [{"key": "value"}]

    def test_returns_none_on_invalid(self):
        result = _safe_json("this is not json at all")
        assert result is None


# ---------------------------------------------------------------------------
# _resolve_model
# ---------------------------------------------------------------------------

class TestResolveModel:
    def test_uses_openai_when_key_present(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": ""}):
            model, provider = _resolve_model(None)
            assert provider == "openai"
            assert model == "gpt-4o"

    def test_uses_gemini_when_only_gemini_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "", "GEMINI_API_KEY": "gm-test"}):
            model, provider = _resolve_model(None)
            assert provider == "gemini"

    def test_uses_preferred_openai_model(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": "gm-test"}):
            model, provider = _resolve_model("gpt-4o-mini")
            assert model == "gpt-4o-mini"
            assert provider == "openai"

    def test_raises_when_no_keys(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "", "GEMINI_API_KEY": ""}):
            with pytest.raises(RuntimeError, match="No AI API key"):
                _resolve_model(None)


# ---------------------------------------------------------------------------
# _compute_scores
# ---------------------------------------------------------------------------

class TestComputeScores:
    def test_all_pass_gives_high_score(self):
        report = GEOReport(url="https://example.com", model_used="gpt-4o")
        report.findings = [
            GEOFinding("QUERY_MATCH_SCORE", "Query Match", "Empirical", "pass", 1.0),
            GEOFinding("CHUNKS_NOT_SELF_CONTAINED", "Chunks", "Mechanistic", "pass", 1.0),
        ]
        _compute_scores(report)
        assert report.overall_score >= 0.9
        assert report.aggarwal_score >= 0.9

    def test_all_fail_gives_low_score(self):
        report = GEOReport(url="https://example.com", model_used="gpt-4o")
        report.findings = [
            GEOFinding("QUERY_MATCH_SCORE", "Query Match", "Empirical", "fail", 0.0),
            GEOFinding("CENTRAL_CLAIM_BURIED", "Claim", "Mechanistic", "fail", 0.0),
        ]
        _compute_scores(report)
        assert report.overall_score == 0.0

    def test_no_findings_gives_perfect_score(self):
        report = GEOReport(url="https://example.com", model_used="gpt-4o")
        _compute_scores(report)
        assert report.overall_score == 1.0
        assert report.aggarwal_score == 1.0

    def test_empirical_weighted_higher(self):
        """Empirical findings should outweigh Conventional findings."""
        report = GEOReport(url="https://example.com", model_used="gpt-4o")
        report.findings = [
            GEOFinding("QUERY_MATCH_SCORE", "Query Match", "Empirical", "pass", 1.0),
            GEOFinding("FAQ_SCHEMA_MISSING", "FAQ", "Conventional", "fail", 0.0),
        ]
        _compute_scores(report)
        # Empirical weight=3, Conventional weight=1 → (3×1 + 1×0)/4 = 0.75
        assert report.overall_score == 0.75


# ---------------------------------------------------------------------------
# GEOReport.to_dict
# ---------------------------------------------------------------------------

class TestGEOReportToDict:
    def test_to_dict_validates(self):
        report = GEOReport(url="https://example.com", model_used="gpt-4o")
        report.findings = [
            GEOFinding("QUERY_MATCH_SCORE", "Query Match", "Empirical", "pass", 0.8,
                       findings=["7/8 answered"], details={"answered": 7})
        ]
        _compute_scores(report)
        d = report.to_dict()
        assert d["url"] == "https://example.com"
        assert d["model_used"] == "gpt-4o"
        assert len(d["findings"]) == 1
        assert d["findings"][0]["code"] == "QUERY_MATCH_SCORE"
        assert d["findings"][0]["evidence_tier"] == "Empirical"
        assert "overall_score" in d


# ---------------------------------------------------------------------------
# generate_geo_report (mock LLM)
# ---------------------------------------------------------------------------

_SAMPLE_HTML = """
<html>
<body>
<h1>OpenBrain: Personal AI Memory Database</h1>
<p>OpenBrain is a personal AI memory database that stores and retrieves context
for AI assistants. It processes thousands of queries per day with 99.9% uptime.</p>
<h2>How Does It Work?</h2>
<p>The system uses vector embeddings to store semantic memories. Each memory is
indexed for fast retrieval using approximate nearest-neighbour search.</p>
<h2>Why Use OpenBrain?</h2>
<p>Traditional AI assistants forget context between sessions. OpenBrain solves this
by persisting memories across conversations, enabling continuity.</p>
</body>
</html>
"""

_MOCK_QUERY_TABLE = json.dumps([
    {"query": "What is OpenBrain?", "best_chunk": "OpenBrain is a personal AI memory database", "answered": "Yes", "reason": "Clear definition"},
    {"query": "How does AI memory work?", "best_chunk": "uses vector embeddings to store semantic memories", "answered": "Yes", "reason": "Explains mechanism"},
    {"query": "Why forget context?", "best_chunk": "Traditional AI assistants forget context between sessions", "answered": "Yes", "reason": "Direct answer"},
])

_MOCK_CHUNK = json.dumps({"self_contained": True, "reason": "Section opens with context"})
_MOCK_CLAIM = json.dumps({"central_claim": "OpenBrain is a personal AI memory database", "appears_in_first_150_words": True})
_MOCK_PROMO = json.dumps([
    {"heading": "How Does It Work?", "type": "main_content"},
    {"heading": "Why Use OpenBrain?", "type": "main_content"},
])


@pytest.mark.asyncio
async def test_geo_report_endpoint_returns_structured_result():
    """GEO.10.1: /api/ai/geo-report returns structured GEOReport."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": ""}), \
         patch("api.services.geo_analyzer._call_ai", new_callable=AsyncMock) as mock_ai, \
         patch("api.services.js_renderer.HAS_PLAYWRIGHT", False):
        # Return appropriate mock for each LLM call
        mock_ai.side_effect = [_MOCK_QUERY_TABLE, _MOCK_CHUNK, _MOCK_CHUNK, _MOCK_CLAIM, _MOCK_PROMO]

        report = await generate_geo_report(
            "https://example.com/page",
            _SAMPLE_HTML,
            preferred_model="gpt-4o",
        )

    assert report.url == "https://example.com/page"
    assert report.model_used == "gpt-4o"
    assert isinstance(report.overall_score, float)
    assert 0.0 <= report.overall_score <= 1.0


@pytest.mark.asyncio
async def test_geo_report_model_validates():
    """GEO.10.2: GEOReport to_dict has all required fields."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": ""}), \
         patch("api.services.geo_analyzer._call_ai", new_callable=AsyncMock) as mock_ai, \
         patch("api.services.js_renderer.HAS_PLAYWRIGHT", False):
        mock_ai.side_effect = [_MOCK_QUERY_TABLE, _MOCK_CHUNK, _MOCK_CHUNK, _MOCK_CLAIM, _MOCK_PROMO]

        report = await generate_geo_report(
            "https://example.com/page",
            _SAMPLE_HTML,
        )

    d = report.to_dict()
    required_keys = {
        "url", "model_used", "overall_score", "aggarwal_score",
        "findings", "js_rendering", "query_match_table",
        "chunk_containedness", "playwright_available", "error",
    }
    assert required_keys.issubset(d.keys())

    # Each finding must have required fields
    for finding in d["findings"]:
        assert "code" in finding
        assert "evidence_tier" in finding
        assert finding["evidence_tier"] in ("Empirical", "Mechanistic", "Conventional")


@pytest.mark.asyncio
async def test_query_generation_and_scoring():
    """GEO.3.2/GEO.7.1: Query match table is generated and scored correctly."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": ""}), \
         patch("api.services.geo_analyzer._call_ai", new_callable=AsyncMock) as mock_ai, \
         patch("api.services.js_renderer.HAS_PLAYWRIGHT", False):
        mock_ai.side_effect = [_MOCK_QUERY_TABLE, _MOCK_CHUNK, _MOCK_CHUNK, _MOCK_CLAIM, _MOCK_PROMO]

        report = await generate_geo_report("https://example.com/page", _SAMPLE_HTML)

    assert len(report.query_match_table) > 0
    for entry in report.query_match_table:
        assert "query" in entry
        assert "answered" in entry
        assert entry["answered"] in ("Yes", "Partial", "No")

    # Find the QUERY_MATCH_SCORE finding
    qm_finding = next((f for f in report.findings if f.code == "QUERY_MATCH_SCORE"), None)
    assert qm_finding is not None
    assert qm_finding.evidence_tier == "Empirical"


@pytest.mark.asyncio
async def test_geo_report_returns_error_without_api_keys():
    """generate_geo_report handles missing API keys gracefully."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "", "GEMINI_API_KEY": ""}):
        report = await generate_geo_report("https://example.com/page", _SAMPLE_HTML)

    assert report.error is not None
    assert "No AI API key" in report.error

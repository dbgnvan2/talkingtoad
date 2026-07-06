"""R8 — LLM-driven GEO checks (audit remediation, 2026-07-04).

Spec: docs/pending/OLD/2026-07-04_r8-geo-llm.md
No real LLM calls — the network layer is mocked. Focus: structured-verdict
parsing (L4) and the P14 error-as-content guard.
"""

import pytest

from api.services.ai_analyzer import AIAnalysisError
from api.services.geo_llm import (
    classify_geo_llm, geo_llm_issues, parse_geo_verdict,
)


# ── parse_geo_verdict (L4) ────────────────────────────────────────────────────
def test_parse_clean_json():
    raw = '{"central_claim_buried": true, "chunks_not_self_contained": false, "promotional_content_interrupts": true}'
    assert parse_geo_verdict(raw) == {
        "central_claim_buried": True,
        "chunks_not_self_contained": False,
        "promotional_content_interrupts": True,
    }


def test_parse_json_with_surrounding_prose():
    raw = 'Here is my analysis:\n{"central_claim_buried": true}\nHope that helps!'
    assert parse_geo_verdict(raw) == {"central_claim_buried": True}


def test_parse_malformed_returns_empty():
    assert parse_geo_verdict("not json at all") == {}
    assert parse_geo_verdict("{broken json") == {}


def test_parse_non_bool_values_ignored():
    assert parse_geo_verdict('{"central_claim_buried": "yes"}') == {}


# ── P14 error-as-content guard ────────────────────────────────────────────────
@pytest.mark.parametrize("s", ["", "   ", "not json at all", "{broken"])
def test_garbage_is_not_content(s):
    # parse_geo_verdict never turns empty/garbage into a verdict (L4).
    assert parse_geo_verdict(s) == {}


@pytest.mark.asyncio
async def test_call_llm_failure_raises_not_returns_sentinel(monkeypatch):
    """P14: on provider failure, _call_llm RAISES AIAnalysisError — it does not
    return an error string that could be parsed as a verdict."""
    from api.services import ai_analyzer
    from api.services.geo_llm import _call_llm

    async def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(ai_analyzer.ai_router, "call_text", boom)
    with pytest.raises(AIAnalysisError):
        await _call_llm("some page text")


@pytest.mark.asyncio
async def test_classify_returns_empty_on_llm_failure(monkeypatch):
    """P14 load-bearing: a raised AIAnalysisError must yield an EMPTY verdict —
    the error must never surface as a finding/content."""
    async def boom(text):
        raise AIAnalysisError("GEO LLM classification failed: no key")
    monkeypatch.setattr("api.services.geo_llm._call_llm", boom)
    v = await classify_geo_llm("some long page text")
    assert v == {}
    # And no issues are emitted from an empty verdict:
    assert geo_llm_issues("https://x.test/", v) == []


# ── classify_geo_llm (LLM layer mocked) ───────────────────────────────────────
@pytest.mark.asyncio
async def test_classify_maps_llm_output(monkeypatch):
    async def fake_call(text):
        return '{"central_claim_buried": true, "promotional_content_interrupts": true}'
    monkeypatch.setattr("api.services.geo_llm._call_llm", fake_call)
    v = await classify_geo_llm("some long page text")
    assert v == {"central_claim_buried": True, "promotional_content_interrupts": True}


@pytest.mark.asyncio
async def test_classify_llm_error_yields_no_verdict(monkeypatch):
    async def fake_call(text):
        return "AI analysis failed: provider down"
    monkeypatch.setattr("api.services.geo_llm._call_llm", fake_call)
    assert await classify_geo_llm("text") == {}


# ── geo_llm_issues emission ───────────────────────────────────────────────────
def test_issues_emitted_for_flagged_only():
    verdict = {"central_claim_buried": True, "chunks_not_self_contained": False,
               "promotional_content_interrupts": True}
    codes = {i.code for i in geo_llm_issues("https://e.com/p", verdict)}
    assert codes == {"CENTRAL_CLAIM_BURIED", "PROMOTIONAL_CONTENT_INTERRUPTS"}


def test_empty_verdict_no_issues():
    assert geo_llm_issues("https://e.com/p", {}) == []

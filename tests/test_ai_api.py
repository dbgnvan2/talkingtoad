import pytest
import httpx
from api.services import ai_analyzer

@pytest.mark.asyncio
async def test_ai_test_endpoint_no_key(api_client, auth_headers, monkeypatch):
    # Ensure no API keys are present in environment
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # ai_analyzer.analyze_with_ai calls load_dotenv() as a fallback when keys
    # are missing — which would re-load real keys from .env / .env-ttoad on a
    # developer machine. Patch to a no-op so the test actually exercises the
    # "no key" branch instead of silently using the user's real key.
    monkeypatch.setattr("api.services.ai_analyzer.load_dotenv", lambda *a, **kw: None)

    response = await api_client.get("/api/ai/test", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "No API key configured" in data["message"]

@pytest.mark.asyncio
async def test_ai_test_endpoint_mock_gemini(api_client, auth_headers, monkeypatch, respx_mock):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    
    # Mock Gemini API response using httpx.Response
    respx_mock.post("https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key=fake-key").mock(
        return_value=httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "MOCKED AI SUGGESTION"}]}}]
        })
    )
    
    response = await api_client.get("/api/ai/test", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "AI connection successful!"
    assert data["sample"] == "MOCKED AI SUGGESTION"


# ── P14: analyze_with_ai signals failure by RAISING, never a sentinel string ──
@pytest.mark.asyncio
async def test_analyze_with_ai_raises_on_provider_auth_error(monkeypatch):
    """No provider key -> analyze_with_ai RAISES AIAnalysisError (does not
    return an 'AI analysis skipped …' sentinel string)."""
    from api.services.ai_analyzer import AIAnalysisError, analyze_with_ai
    from api.services.ai_router import ProviderAuthError

    async def boom(*a, **kw):
        raise ProviderAuthError("no key")

    monkeypatch.setattr(ai_analyzer.ai_router, "call_text", boom)
    with pytest.raises(AIAnalysisError) as ei:
        await analyze_with_ai(
            "title_meta_optimize",
            {"title": "t", "meta_description": "m", "content_summary": "c"},
        )
    assert "No API key configured" in str(ei.value)


@pytest.mark.asyncio
async def test_analyze_with_ai_raises_on_provider_api_error(monkeypatch):
    """Any provider/runtime failure -> AIAnalysisError, not an
    'Error calling AI: …' sentinel string."""
    from api.services.ai_analyzer import AIAnalysisError, analyze_with_ai

    async def boom(*a, **kw):
        raise RuntimeError("timeout")

    monkeypatch.setattr(ai_analyzer.ai_router, "call_text", boom)
    with pytest.raises(AIAnalysisError):
        await analyze_with_ai(
            "title_meta_optimize",
            {"title": "t", "meta_description": "m", "content_summary": "c"},
        )


@pytest.mark.asyncio
async def test_analyze_with_ai_raises_on_missing_template_key(monkeypatch):
    """A prompt template missing a context key -> AIAnalysisError, not a
    sentinel string that could be rendered as content."""
    from api.services.ai_analyzer import AIAnalysisError, analyze_with_ai

    with pytest.raises(AIAnalysisError):
        await analyze_with_ai("title_meta_optimize", {})  # missing keys

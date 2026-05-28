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

"""API-contract tests for GET /api/ai/test (ConnectionsPanel).

Spec: docs/pending/2026-07-06_connections-panel.md

These lock the frontend contract for the Connections panel's "Test LLM
connection" button:
  - the response carries `success` (bool) and `message` (str),
  - `sample` is present on success,
  - `api_key_read` is NEVER present (removed 2026-07-06 — it leaked env-var
    state to the client and no consumer read it).

The AI provider is always mocked — no real LLM call is made (would burn credits
and be flaky on provider outages).
"""

import pytest


@pytest.mark.asyncio
async def test_ai_test_response_omits_api_key_read(api_client, auth_headers, monkeypatch):
    """Frontend contract: /api/ai/test must NOT return api_key_read.

    This is the load-bearing assertion — the ConnectionsPanel dropped the field,
    so the API must never send it (on success OR failure).
    """
    async def fake_analyze(prompt_key, context):
        return "A better test title suggestion"

    monkeypatch.setattr("api.routers.ai.analyze_with_ai", fake_analyze)

    response = await api_client.get("/api/ai/test", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "api_key_read" not in data, (
        "api_key_read was removed from the /api/ai/test contract (2026-07-06) "
        "and must never be returned to the client"
    )
    # Contract fields the frontend reads:
    assert "success" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_ai_test_success_shape_no_api_key_read(api_client, auth_headers, monkeypatch):
    """Success path: success:true, message, sample — and no api_key_read."""
    async def fake_analyze(prompt_key, context):
        return "MOCKED AI SUGGESTION"

    monkeypatch.setattr("api.routers.ai.analyze_with_ai", fake_analyze)

    response = await api_client.get("/api/ai/test", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "AI connection successful!"
    assert data["sample"] == "MOCKED AI SUGGESTION"
    assert "api_key_read" not in data


@pytest.mark.asyncio
async def test_ai_test_failure_shape_no_api_key_read(api_client, auth_headers, monkeypatch):
    """Failure path: provider returns an error sentinel string -> success:false
    with the message, and still no api_key_read.

    Note (P14): analyze_with_ai signals failure via a sentinel string matched by
    str.startswith rather than raising. The endpoint routes it correctly, but the
    mixed-mode str return is a latent error-as-content pattern — noted, not fixed.
    """
    async def fake_analyze(prompt_key, context):
        return "Error calling AI: provider unreachable"

    monkeypatch.setattr("api.routers.ai.analyze_with_ai", fake_analyze)

    response = await api_client.get("/api/ai/test", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Error calling AI" in data["message"]
    assert "sample" not in data
    assert "api_key_read" not in data

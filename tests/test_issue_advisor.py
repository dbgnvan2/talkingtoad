"""
Tests for the issue-aware AI Suggestion feature (issue_advisor analysis type).

Covers:
- issue_advisor returns structured JSON for text-rewritable issue codes
- image alt issue passes extra_context through to the prompt
- out-of-scope issue code is rejected with an error
- missing issue_code field is rejected
- _AI_TEXT_SUGGESTION_CODES set on backend matches the spec
"""

import json
import pytest
import httpx

from api.models.job import CrawlJob
from api.models.page import CrawledPage
from api.routers.ai import _AI_TEXT_SUGGESTION_CODES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_page(store, job_id: str, url: str):
    """Insert a minimal job + page so get_page_issues_by_url finds it."""
    await store.create_job(CrawlJob(
        job_id=job_id,
        target_url=url,
        status="complete",
        pages_crawled=1,
    ))
    await store.save_pages([CrawledPage(
        job_id=job_id,
        url=url,
        status_code=200,
        title="Living Systems Counselling | Home",
        meta_description="",
        h1_tags=["Counselling Services in Victoria BC"],
    )])


GEMINI_STUB = {
    "candidates": [{
        "content": {
            "parts": [{
                "text": json.dumps({
                    "suggested_text": "Nonprofit Counselling Victoria BC | Living Systems",
                    "why": "Entity-rich title helps AI Overviews surface the service area.",
                    "where_to_apply": "Paste into your CMS SEO plugin (Yoast / Rank Math) under SEO Title.",
                })
            }]
        }
    }]
}

ALT_STUB = {
    "candidates": [{
        "content": {
            "parts": [{
                "text": json.dumps({
                    "suggested_text": "Counsellor and client in session at Living Systems Counselling in Victoria BC",
                    "why": "Descriptive alt text with location entity improves GEO discoverability.",
                    "where_to_apply": "Update the alt attribute in WordPress Media Library for this image.",
                })
            }]
        }
    }]
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key=fake-key"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issue_advisor_title_missing(api_client, test_store, auth_headers, monkeypatch, respx_mock):
    """issue_advisor returns structured suggestion for TITLE_MISSING."""
    job_id = "job-advisor-title"
    url = "https://livingsystems.ca/"
    await _seed_page(test_store, job_id, url)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("api.services.ai_analyzer.load_dotenv", lambda *a, **kw: None)
    respx_mock.post(GEMINI_URL).mock(return_value=httpx.Response(200, json=GEMINI_STUB))

    response = await api_client.post(
        "/api/ai/analyze",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "page_url": url,
            "analysis_type": "issue_advisor",
            "issue_code": "TITLE_MISSING",
            "issue_description": "No title tag found on this page",
            "extra_context": "none",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["analysis_type"] == "issue_advisor"
    parsed = json.loads(data["suggestion"])
    assert "suggested_text" in parsed
    assert "why" in parsed
    assert "where_to_apply" in parsed
    assert len(parsed["suggested_text"]) > 0


@pytest.mark.asyncio
async def test_issue_advisor_img_alt_passes_extra_context(api_client, test_store, auth_headers, monkeypatch, respx_mock):
    """issue_advisor for IMG_ALT_MISSING forwards extra_context (image URL) into the prompt."""
    job_id = "job-advisor-alt"
    url = "https://livingsystems.ca/about/"
    await _seed_page(test_store, job_id, url)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("api.services.ai_analyzer.load_dotenv", lambda *a, **kw: None)

    captured_body: dict = {}

    def mock_gemini(request):
        captured_body["text"] = request.content.decode()
        return httpx.Response(200, json=ALT_STUB)

    respx_mock.post(GEMINI_URL).mock(side_effect=mock_gemini)

    image_url = "https://livingsystems.ca/wp-content/uploads/session.jpg"
    response = await api_client.post(
        "/api/ai/analyze",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "page_url": url,
            "analysis_type": "issue_advisor",
            "issue_code": "IMG_ALT_MISSING",
            "issue_description": "Image is missing alt text",
            "extra_context": f"image: {image_url}",
        },
    )

    assert response.status_code == 200
    # Image URL must have been forwarded in the prompt body
    assert image_url in captured_body["text"]
    parsed = json.loads(response.json()["suggestion"])
    assert "suggested_text" in parsed
    assert "where_to_apply" in parsed


@pytest.mark.asyncio
async def test_issue_advisor_rejects_out_of_scope_code(api_client, test_store, auth_headers):
    """issue_advisor returns an error for a non-text-rewritable issue code."""
    job_id = "job-advisor-bad"
    url = "https://livingsystems.ca/"
    await _seed_page(test_store, job_id, url)

    response = await api_client.post(
        "/api/ai/analyze",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "page_url": url,
            "analysis_type": "issue_advisor",
            "issue_code": "BROKEN_LINK_404",
            "issue_description": "Link returned 404",
            "extra_context": "link: https://example.com/gone",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "BROKEN_LINK_404" in data["error"]


@pytest.mark.asyncio
async def test_issue_advisor_rejects_missing_issue_code(api_client, test_store, auth_headers):
    """issue_advisor without issue_code returns a clear error."""
    job_id = "job-advisor-nocode"
    url = "https://livingsystems.ca/"
    await _seed_page(test_store, job_id, url)

    response = await api_client.post(
        "/api/ai/analyze",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "page_url": url,
            "analysis_type": "issue_advisor",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "issue_code" in data["error"]


# ---------------------------------------------------------------------------
# Eligibility set correctness (no HTTP calls)
# ---------------------------------------------------------------------------

def test_ai_text_suggestion_codes_includes_text_rewritable():
    """All expected text-rewritable codes are in the backend eligibility set."""
    expected = {
        "TITLE_MISSING", "TITLE_TOO_SHORT", "TITLE_TOO_LONG", "TITLE_DUPLICATE",
        "META_DESC_MISSING", "META_DESC_TOO_SHORT", "META_DESC_TOO_LONG", "META_DESC_DUPLICATE",
        "SOCIAL_PREVIEW_METADATA_MISSING",
        "H1_MISSING", "H1_MULTIPLE", "HEADING_EMPTY",
        "IMG_ALT_MISSING", "IMG_ALT_TOO_SHORT", "IMG_ALT_TOO_LONG",
        "IMG_ALT_GENERIC", "IMG_ALT_DUP_FILENAME", "IMG_ALT_MISUSED",
        "LINK_EMPTY_ANCHOR",
        "THIN_CONTENT",
        "SCHEMA_ORG_MISSING",
        "CONVERSATIONAL_H2_MISSING", "QUERY_COVERAGE_WEAK",
    }
    assert expected == _AI_TEXT_SUGGESTION_CODES


@pytest.mark.asyncio
async def test_issue_advisor_conversational_h2_passes_h2_list(api_client, test_store, auth_headers, monkeypatch, respx_mock):
    """CONVERSATIONAL_H2_MISSING forwards h2_headings list in extra_context to the AI."""
    job_id = "job-advisor-h2"
    url = "https://livingsystems.ca/services/"
    await _seed_page(test_store, job_id, url)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("api.services.ai_analyzer.load_dotenv", lambda *a, **kw: None)

    captured_body: dict = {}

    def mock_gemini(request):
        captured_body["text"] = request.content.decode()
        return httpx.Response(200, json=GEMINI_STUB)

    respx_mock.post(GEMINI_URL).mock(side_effect=mock_gemini)

    response = await api_client.post(
        "/api/ai/analyze",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "page_url": url,
            "analysis_type": "issue_advisor",
            "issue_code": "CONVERSATIONAL_H2_MISSING",
            "issue_description": "H2 headings do not use conversational interrogatives",
            "extra_context": "current H2s: See Our Case Studies | Paying it Forward | Let's build something",
        },
    )

    assert response.status_code == 200
    # The H2 list must have been forwarded to the AI
    assert "See Our Case Studies" in captured_body["text"]


@pytest.mark.asyncio
async def test_issue_advisor_query_coverage_passes_h1(api_client, test_store, auth_headers, monkeypatch, respx_mock):
    """QUERY_COVERAGE_WEAK forwards the H1 topic term in extra_context to the AI."""
    job_id = "job-advisor-qc"
    url = "https://livingsystems.ca/events/"
    await _seed_page(test_store, job_id, url)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("api.services.ai_analyzer.load_dotenv", lambda *a, **kw: None)

    captured_body: dict = {}

    def mock_gemini(request):
        captured_body["text"] = request.content.decode()
        return httpx.Response(200, json=GEMINI_STUB)

    respx_mock.post(GEMINI_URL).mock(side_effect=mock_gemini)

    h1_topic = "AI Event Planning for Non-Profits"
    response = await api_client.post(
        "/api/ai/analyze",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "page_url": url,
            "analysis_type": "issue_advisor",
            "issue_code": "QUERY_COVERAGE_WEAK",
            "issue_description": "H1 topic terms under-represented in intro or section headings",
            "extra_context": f"H1 topic: {h1_topic}",
        },
    )

    assert response.status_code == 200
    assert h1_topic in captured_body["text"]


@pytest.mark.asyncio
async def test_issue_advisor_wrong_shape_preserves_why_and_where(api_client, test_store, auth_headers, monkeypatch, respx_mock):
    """When AI returns JSON with wrong keys (no suggested_text), why/where_to_apply are preserved
    and any non-standard string values are collected into suggested_text."""
    job_id = "job-advisor-wrongshape"
    url = "https://livingsystems.ca/"
    await _seed_page(test_store, job_id, url)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr("api.services.ai_analyzer.load_dotenv", lambda *a, **kw: None)

    # Simulate AI returning h2_1/h2_2 keys instead of suggested_text
    wrong_shape_stub = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps({
                        "h2_1": "How does counselling help with anxiety?",
                        "h2_2": "What services does Living Systems offer?",
                        "why": "Conversational H2s improve AI retrieval.",
                        "where_to_apply": "Edit H2 headings in WordPress block editor.",
                    })
                }]
            }
        }]
    }
    respx_mock.post(GEMINI_URL).mock(return_value=httpx.Response(200, json=wrong_shape_stub))

    response = await api_client.post(
        "/api/ai/analyze",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "page_url": url,
            "analysis_type": "issue_advisor",
            "issue_code": "CONVERSATIONAL_H2_MISSING",
            "issue_description": "H2s are not in question form",
            "extra_context": "current H2s: About Us | Our Team",
        },
    )

    assert response.status_code == 200
    parsed = json.loads(response.json()["suggestion"])
    # why and where_to_apply must be preserved as separate fields, not jammed into suggested_text
    assert parsed["why"] == "Conversational H2s improve AI retrieval."
    assert parsed["where_to_apply"] == "Edit H2 headings in WordPress block editor."
    # Structural: suggested_text must be exactly the joined non-meta string values (h2_1 + h2_2)
    expected_suggested = "How does counselling help with anxiety?\nWhat services does Living Systems offer?"
    assert parsed["suggested_text"] == expected_suggested
    # why/where must NOT have leaked into suggested_text
    assert "Conversational H2s improve" not in parsed["suggested_text"]
    assert "WordPress" not in parsed["suggested_text"]


@pytest.mark.asyncio
async def test_issue_advisor_no_api_key_returns_error_not_suggestion(api_client, test_store, auth_headers, monkeypatch):
    """When no AI key is configured, the endpoint must return {error:...} not a 200 with
    the error string in suggestion — which would display the error as copy-ready text."""
    job_id = "job-advisor-nokey"
    url = "https://livingsystems.ca/"
    await _seed_page(test_store, job_id, url)

    # P14: analyze_with_ai raises AIAnalysisError when no key is configured.
    from api.services.ai_analyzer import AIAnalysisError

    async def mock_analyze(prompt_key, context):
        raise AIAnalysisError(
            "AI analysis skipped: No API key configured (GEMINI_API_KEY or OPENAI_API_KEY)."
        )

    monkeypatch.setattr("api.routers.ai.analyze_with_ai", mock_analyze)

    response = await api_client.post(
        "/api/ai/analyze",
        headers=auth_headers,
        json={
            "job_id": job_id,
            "page_url": url,
            "analysis_type": "issue_advisor",
            "issue_code": "TITLE_MISSING",
            "issue_description": "No title tag found",
            "extra_context": "none",
        },
    )

    assert response.status_code == 200
    data = response.json()
    # Must surface as an error, not as a suggestion the user would copy
    assert "error" in data, "Error string must return as {error:} not as suggestion content"
    # P14 load-bearing: the error text must NEVER appear as `suggestion` content.
    assert "suggestion" not in data, "error must not be rendered as a suggestion"
    assert "No API key configured" in data["error"]
    assert data.get("suggestion") is None, "suggestion field must be absent when AI call fails"
    assert "skipped" in data["error"] or "No API key" in data["error"]


@pytest.mark.asyncio
async def test_page_advisor_ai_error_routed_not_rendered(api_client, test_store, auth_headers, monkeypatch):
    """P14: when analyze_with_ai raises, /page-advisor returns {error:} and the
    error text never appears in `recommendations` as if it were AI content."""
    from api.services.ai_analyzer import AIAnalysisError
    job_id = "job-page-advisor-err"
    url = "https://livingsystems.ca/"
    await _seed_page(test_store, job_id, url)

    async def boom(prompt_key, context):
        raise AIAnalysisError("Error calling AI: provider unreachable")
    monkeypatch.setattr("api.routers.ai.analyze_with_ai", boom)

    response = await api_client.post(
        "/api/ai/page-advisor", headers=auth_headers,
        json={"job_id": job_id, "page_url": url},
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "provider unreachable" in data["error"]
    # Load-bearing: error must NOT be rendered as recommendations content.
    assert "recommendations" not in data


@pytest.mark.asyncio
async def test_site_advisor_ai_error_routed_not_rendered(api_client, test_store, auth_headers, monkeypatch):
    """P14: when analyze_with_ai raises, /site-advisor returns {error:} and the
    error text never appears in `recommendations` as if it were AI content."""
    from api.services.ai_analyzer import AIAnalysisError
    job_id = "job-site-advisor-err"
    url = "https://livingsystems.ca/"
    await _seed_page(test_store, job_id, url)

    async def boom(prompt_key, context):
        raise AIAnalysisError("Error calling AI: provider unreachable")
    monkeypatch.setattr("api.routers.ai.analyze_with_ai", boom)

    response = await api_client.post(
        "/api/ai/site-advisor", headers=auth_headers,
        json={"job_id": job_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "provider unreachable" in data["error"]
    assert "recommendations" not in data


def test_ai_text_suggestion_codes_excludes_non_text_issues():
    """Technical/structural issue codes are not in the suggestion eligibility set."""
    non_text = [
        "BROKEN_LINK_404", "BROKEN_LINK_410", "REDIRECT_LOOP", "REDIRECT_CHAIN",
        "HTTP_PAGE", "MIXED_CONTENT", "MISSING_HSTS",
        "IMG_OVERSIZED", "IMG_POOR_COMPRESSION", "IMG_FORMAT_LEGACY",
        "URL_TOO_LONG", "URL_UPPERCASE", "PAGE_TIMEOUT",
        "CANONICAL_MISSING", "NOINDEX_META", "ROBOTS_BLOCKED",
    ]
    for code in non_text:
        assert code not in _AI_TEXT_SUGGESTION_CODES, f"{code} should not be in _AI_TEXT_SUGGESTION_CODES"

"""
Tests for rewriter.py (Tool B — Content Rewriting).

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md

v2.6 M2.1 (Cycle Z): tests refactored to mock at the AIRouter boundary
instead of the (now-removed) private `_call_openai_rewriter` /
`_call_gemini_rewriter` functions. Provider-level mechanics (HTTP shape,
token extraction, finish-reason handling) live in the provider drivers
under `api/services/providers/` and are exercised by `test_ai_router.py`
plus their own driver tests. This file's job is narrower: verify that
`rewrite_page` adapts an AIResponse into a RewriterResult correctly and
preserves the contract the advisor router depends on.
"""

from unittest.mock import patch

import pytest

from api.models.advisor import RewriterRequest, RewriterResult
from api.services.ai_router import AIResponse, ModelConfig, SYSTEM_CONTEXT_ID
from api.services.rewriter import rewrite_page


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_ai_response(text: str, *, truncated: bool = False) -> AIResponse:
    return AIResponse(
        content=text,
        provider_id="openai",
        model="gpt-4o",
        input_token_count=10,
        output_token_count=20,
        cost_estimate_usd=0.0,
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Model contract tests (unchanged from pre-Cycle-Z)
# ---------------------------------------------------------------------------

class TestRewriterRequest:
    def test_request_requires_content(self):
        request = RewriterRequest(content="Some content", prompt="Rewrite this.")
        assert request.content == "Some content"
        assert request.prompt == "Rewrite this."

    def test_request_empty_content_allowed(self):
        request = RewriterRequest(content="", prompt="Rewrite this.")
        assert request.content == ""


class TestRewriterResult:
    def test_result_success(self):
        result = RewriterResult(rewrite="Rewritten content", stopped_by_limit=False)
        assert result.rewrite == "Rewritten content"
        assert result.stopped_by_limit is False

    def test_result_stopped(self):
        result = RewriterResult(rewrite="Incomplete...", stopped_by_limit=True)
        assert result.stopped_by_limit is True


# ---------------------------------------------------------------------------
# rewrite_page tests — mock at the AIRouter boundary
# ---------------------------------------------------------------------------

class TestRewritePageHappyPath:
    """rewrite_page must return a RewriterResult that mirrors the
    underlying AIResponse (text → rewrite, truncated → stopped_by_limit)."""

    @pytest.mark.asyncio
    async def test_rewrite_page_returns_ai_response_content(self):
        async def fake_call_text(**kwargs):
            return _fake_ai_response("Rewritten.")

        request = RewriterRequest(
            content="Original",
            prompt="Rewrite professionally.",
        )

        with patch("api.services.rewriter.ai_router.call_text", side_effect=fake_call_text):
            result = await rewrite_page(request)

        assert isinstance(result, RewriterResult)
        assert result.rewrite == "Rewritten."
        assert result.stopped_by_limit is False

    @pytest.mark.asyncio
    async def test_rewrite_page_surfaces_truncation_flag(self):
        """The truncated flag on AIResponse must propagate to
        stopped_by_limit on RewriterResult. Frontend UX depends on this
        to decide whether to show a 'response truncated' warning."""
        async def fake_call_text(**kwargs):
            return _fake_ai_response("Partial rewrite...", truncated=True)

        request = RewriterRequest(content="Original", prompt="Rewrite.")

        with patch("api.services.rewriter.ai_router.call_text", side_effect=fake_call_text):
            result = await rewrite_page(request)

        assert result.stopped_by_limit is True

    @pytest.mark.asyncio
    async def test_rewrite_page_passes_system_context_id(self):
        """rewrite_page must call AIRouter with customer_id=SYSTEM_CONTEXT_ID
        until per-customer identity flows in (M2.3). Without this, usage
        attribution rolls up to the wrong bucket."""
        captured = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _fake_ai_response("ok")

        request = RewriterRequest(content="Original", prompt="Rewrite.")

        with patch("api.services.rewriter.ai_router.call_text", side_effect=fake_call_text):
            await rewrite_page(request)

        assert captured["customer_id"] == SYSTEM_CONTEXT_ID
        # The user_prompt must contain the canonical lead-in phrase so
        # behaviour matches the pre-refactor rewriter.
        assert "Please rewrite the following content:" in captured["user_prompt"]
        # The system_prompt is the caller's prompt verbatim.
        assert captured["system_prompt"] == "Rewrite."
        # ModelConfig is passed (sparse 3-field shape).
        assert isinstance(captured["model_config"], ModelConfig)
        assert captured["model_config"].temperature == 0.2


class TestRewritePageErrorPath:
    """Errors raised inside AIRouter propagate out of rewrite_page
    unchanged — the calling router (advisor.py) catches them and maps
    to HTTP responses (402 for auth, 500 for hard provider errors)."""

    @pytest.mark.asyncio
    async def test_rewrite_page_propagates_provider_errors(self):
        from api.services.ai_router import ProviderAPIError

        async def boom(**kwargs):
            raise ProviderAPIError("openai HTTP 503: upstream timeout")

        request = RewriterRequest(content="Original", prompt="Rewrite.")

        with patch("api.services.rewriter.ai_router.call_text", side_effect=boom):
            with pytest.raises(ProviderAPIError):
                await rewrite_page(request)

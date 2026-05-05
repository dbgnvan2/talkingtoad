"""
Tests for rewriter.py (Tool B — Content Rewriting).

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md

Tests verify LLM call structure and response parsing.
Uses mocking to avoid actual API calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models.advisor import RewriterRequest, RewriterResult
from api.services.rewriter import _call_gemini_rewriter, _call_openai_rewriter, rewrite_page


class TestOpenAIRewriter:
    """Test OpenAI rewriter API calls."""

    def test_openai_rewriter_success(self):
        """OpenAI rewriter returns rewritten content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "This is a rewritten page."},
                    "finish_reason": "stop",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("api.services.rewriter.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result, stopped = _call_openai_rewriter(
                "Rewrite this content professionally.",
                "Original content here.",
            )

            assert result == "This is a rewritten page."
            assert stopped is False

    def test_openai_rewriter_token_limit(self):
        """OpenAI rewriter detects token limit."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Incomplete rewrite..."},
                    "finish_reason": "length",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("api.services.rewriter.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result, stopped = _call_openai_rewriter(
                "Rewrite this.",
                "Content",
            )

            assert stopped is True


class TestGeminiRewriter:
    """Test Gemini rewriter API calls."""

    def test_gemini_rewriter_success(self):
        """Gemini rewriter returns rewritten content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "This is a rewritten page."}]
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("api.services.rewriter.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result, stopped = _call_gemini_rewriter(
                "Rewrite this content professionally.",
                "Original content here.",
            )

            assert result == "This is a rewritten page."
            assert stopped is False

    def test_gemini_rewriter_token_limit(self):
        """Gemini rewriter detects token limit."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Incomplete rewrite..."}]
                    },
                    "finishReason": "MAX_TOKENS",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("api.services.rewriter.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result, stopped = _call_gemini_rewriter(
                "Rewrite this.",
                "Content",
            )

            assert stopped is True


class TestRewriterRequest:
    """Test RewriterRequest model."""

    def test_request_requires_content(self):
        """RewriterRequest requires content."""
        request = RewriterRequest(
            content="Some content",
            prompt="Rewrite this.",
        )
        assert request.content == "Some content"
        assert request.prompt == "Rewrite this."

    def test_request_empty_content_allowed(self):
        """RewriterRequest allows empty content (edge case)."""
        request = RewriterRequest(
            content="",
            prompt="Rewrite this.",
        )
        assert request.content == ""


class TestRewriterResult:
    """Test RewriterResult model."""

    def test_result_success(self):
        """RewriterResult indicates successful rewrite."""
        result = RewriterResult(
            rewrite="Rewritten content",
            stopped_by_limit=False,
        )
        assert result.rewrite == "Rewritten content"
        assert result.stopped_by_limit is False

    def test_result_stopped(self):
        """RewriterResult indicates if token limit hit."""
        result = RewriterResult(
            rewrite="Incomplete...",
            stopped_by_limit=True,
        )
        assert result.stopped_by_limit is True


@pytest.mark.asyncio
async def test_rewrite_page_uses_openai_when_key_present():
    """rewrite_page calls OpenAI when API key is present."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"content": "Rewritten."},
                "finish_reason": "stop",
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    request = RewriterRequest(
        content="Original",
        prompt="Rewrite professionally.",
    )

    with patch("api.services.rewriter._OPENAI_API_KEY", "test-key"):
        with patch("api.services.rewriter.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = await rewrite_page(request)

            assert result.rewrite == "Rewritten."
            assert result.stopped_by_limit is False


@pytest.mark.asyncio
async def test_rewrite_page_handles_error():
    """rewrite_page raises on API error."""
    request = RewriterRequest(
        content="Original",
        prompt="Rewrite.",
    )

    with patch("api.services.rewriter._OPENAI_API_KEY", "test-key"):
        with patch("api.services.rewriter.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = RuntimeError("API error")

            with pytest.raises(RuntimeError):
                await rewrite_page(request)

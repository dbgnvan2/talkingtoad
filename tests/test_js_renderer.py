"""
Tests for api/services/js_renderer.py.

Spec: docs/implementation_plan_geo_analyzer_2026-05-03.md#GEO.1.3b/c/d

Uses mock Playwright and httpx to avoid real network calls.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.js_renderer import (
    _tokenize,
    _tfidf_top_keywords,
    _jaccard,
    JSRenderResult,
    run_js_render_checks,
    _DIFF_THRESHOLD,
    _JACCARD_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_extracts_words_from_html(self):
        html = "<p>The quick brown fox jumps over the lazy dog</p>"
        tokens = _tokenize(html, is_html=True)
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens

    def test_strips_script_tags(self):
        html = "<script>var x = 1;</script><p>visible content here</p>"
        tokens = _tokenize(html, is_html=True)
        assert "visible" in tokens
        assert "content" in tokens
        # Script content should be excluded
        assert "var" not in tokens

    def test_minimum_word_length(self):
        html = "<p>AI is an amazing system</p>"
        tokens = _tokenize(html, is_html=True)
        # "AI" and "is" and "an" are < 3 chars — should be excluded
        assert "ai" not in tokens
        assert "amazing" in tokens

    def test_plain_text_mode(self):
        text = "This is plain text with several words"
        tokens = _tokenize(text, is_html=False)
        assert "plain" in tokens
        assert "text" in tokens


class TestJaccard:
    def test_identical_sets(self):
        a = {"dog", "cat", "bird"}
        assert _jaccard(a, a) == 1.0

    def test_disjoint_sets(self):
        a = {"dog", "cat"}
        b = {"table", "chair"}
        assert _jaccard(a, b) == 0.0

    def test_partial_overlap(self):
        a = {"dog", "cat", "bird"}
        b = {"dog", "cat", "fish"}
        # Intersection: {dog, cat} = 2, Union: {dog, cat, bird, fish} = 4
        assert abs(_jaccard(a, b) - 0.5) < 0.01

    def test_empty_sets(self):
        assert _jaccard(set(), set()) == 1.0


# ---------------------------------------------------------------------------
# JSRenderResult flag computation
# ---------------------------------------------------------------------------

class TestJSRenderResultFlags:
    def _make_tokens(self, words: list[str]) -> set[str]:
        return set(words)

    def test_js_rendered_content_differs_flag(self):
        """Should flag when rendered adds >20% new tokens."""
        raw = self._make_tokens(["apple", "banana", "cherry"])
        # 3 new tokens on top of 3 = 50% addition
        rendered = self._make_tokens(["apple", "banana", "cherry", "date", "elderberry", "fig"])
        result = JSRenderResult(url="https://example.com")
        result.raw_tokens = raw
        result.rendered_tokens = rendered

        added = rendered - raw
        rendered_size = len(rendered) or 1
        ratio = len(added) / rendered_size
        result.added_token_ratio = ratio
        result.js_rendered_content_differs = ratio > _DIFF_THRESHOLD

        assert result.js_rendered_content_differs is True

    def test_js_rendered_content_differs_not_flagged_small_diff(self):
        """Should NOT flag when rendered adds ≤20% new tokens."""
        raw = self._make_tokens(["apple", "banana", "cherry", "date", "elderberry",
                                  "fig", "grape", "honeydew", "kiwi", "lemon"])
        # 1 new token out of 11 = ~9% addition
        rendered = self._make_tokens(list(raw) + ["mango"])
        result = JSRenderResult(url="https://example.com")
        added = rendered - raw
        ratio = len(added) / len(rendered)
        result.js_rendered_content_differs = ratio > _DIFF_THRESHOLD
        assert result.js_rendered_content_differs is False

    def test_ua_content_differs_flag(self):
        """Should flag when AI bot gets >20% fewer tokens than rendered."""
        rendered = self._make_tokens([f"word{i}" for i in range(100)])
        # GPTBot only gets 70 tokens (30% less)
        gptbot = self._make_tokens([f"word{i}" for i in range(70)])
        result = JSRenderResult(url="https://example.com")
        result.rendered_tokens = rendered
        result.gptbot_tokens = gptbot
        result.claudebot_tokens = rendered  # Claude gets full content

        rendered_size = len(rendered)
        gptbot_ratio = len(gptbot) / rendered_size
        result.ua_content_differs = gptbot_ratio < (1 - _DIFF_THRESHOLD)
        assert result.ua_content_differs is True


# ---------------------------------------------------------------------------
# Integration test with mocked Playwright
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_js_rendered_content_differs_fires():
    """GEO.1.3b fires when rendered content is substantially larger than raw."""
    raw_html = "<html><body><div id='root'></div></body></html>"
    rendered_html = (
        "<html><body>"
        "<h1>OpenBrain Memory Database</h1>"
        "<p>OpenBrain is a personal AI memory database that stores context.</p>"
        "<p>It uses vector embeddings to retrieve relevant memories.</p>"
        "<p>The system processes thousands of requests per day.</p>"
        "</body></html>"
    )

    with patch("api.services.js_renderer.HAS_PLAYWRIGHT", True), \
         patch("api.services.js_renderer._fetch_raw", new_callable=AsyncMock) as mock_fetch, \
         patch("api.services.js_renderer._render_with_playwright", new_callable=AsyncMock) as mock_render:
        mock_fetch.return_value = raw_html
        mock_render.return_value = rendered_html

        result = await run_js_render_checks("https://example.com/page")

    assert result.js_rendered_content_differs is True
    assert result.rendered_token_count > result.raw_token_count


@pytest.mark.asyncio
async def test_content_cloaking_detected_on_topic_shift():
    """GEO.1.3c fires when rendered content has different topic than raw."""
    raw_html = (
        "<html><body>"
        "<p>Buy our product today! Sale ends soon!</p>"
        "<p>Discount offers available for limited time!</p>"
        "</body></html>"
    )
    # Rendered content is about a completely different topic
    rendered_html = (
        "<html><body>"
        "<h1>Machine Learning Tutorial</h1>"
        "<p>Neural networks learn patterns from training data using gradient descent.</p>"
        "<p>Deep learning models can classify images with high accuracy.</p>"
        "<p>Transformers have revolutionized natural language processing tasks.</p>"
        "<p>Attention mechanisms enable models to focus on relevant context.</p>"
        "<p>Fine-tuning pre-trained models reduces training time significantly.</p>"
        "<p>Embeddings represent semantic meaning in high-dimensional vector space.</p>"
        "<p>Backpropagation computes gradients through network layers efficiently.</p>"
        "</body></html>"
    )

    with patch("api.services.js_renderer.HAS_PLAYWRIGHT", True), \
         patch("api.services.js_renderer._fetch_raw", new_callable=AsyncMock) as mock_fetch, \
         patch("api.services.js_renderer._render_with_playwright", new_callable=AsyncMock) as mock_render:
        mock_fetch.return_value = raw_html
        mock_render.return_value = rendered_html

        result = await run_js_render_checks("https://example.com/page")

    assert result.js_rendered_content_differs is True
    assert result.content_cloaking_detected is True
    assert result.topic_jaccard < _JACCARD_THRESHOLD


@pytest.mark.asyncio
async def test_ua_content_differs_fires_on_ai_bot_stripping():
    """GEO.1.3d fires when AI bots get much less content than rendered."""
    # Rendered is large
    rendered_words = [f"word{i}" for i in range(200)]
    rendered_html = "<html><body>" + " ".join(
        f"<p>{' '.join(rendered_words[i:i+20])}</p>" for i in range(0, 200, 20)
    ) + "</body></html>"

    # GPTBot gets only 50 words (stripped)
    gptbot_words = rendered_words[:50]
    gptbot_html = "<html><body><p>" + " ".join(gptbot_words) + "</p></body></html>"
    claudebot_html = gptbot_html

    with patch("api.services.js_renderer.HAS_PLAYWRIGHT", True), \
         patch("api.services.js_renderer._fetch_raw", new_callable=AsyncMock) as mock_fetch, \
         patch("api.services.js_renderer._render_with_playwright", new_callable=AsyncMock) as mock_render:
        # Called 3 times: generic UA, GPTBot, ClaudeBot
        mock_fetch.side_effect = [rendered_html, gptbot_html, claudebot_html]
        mock_render.return_value = rendered_html

        result = await run_js_render_checks("https://example.com/page")

    assert result.ua_content_differs is True


@pytest.mark.asyncio
async def test_no_flags_when_content_matches():
    """No flags when rendered == raw content."""
    html = (
        "<html><body>"
        "<h1>Title</h1>"
        "<p>This is a well-formed page with good content already in the HTML.</p>"
        "<p>No JavaScript rendering needed because content is server-side rendered.</p>"
        "</body></html>"
    )

    with patch("api.services.js_renderer.HAS_PLAYWRIGHT", True), \
         patch("api.services.js_renderer._fetch_raw", new_callable=AsyncMock) as mock_fetch, \
         patch("api.services.js_renderer._render_with_playwright", new_callable=AsyncMock) as mock_render:
        mock_fetch.return_value = html
        mock_render.return_value = html

        result = await run_js_render_checks("https://example.com/page")

    assert result.js_rendered_content_differs is False
    assert result.content_cloaking_detected is False
    assert result.ua_content_differs is False


@pytest.mark.asyncio
async def test_graceful_when_playwright_unavailable():
    """When Playwright is not installed, returns result with error message."""
    with patch("api.services.js_renderer.HAS_PLAYWRIGHT", False):
        result = await run_js_render_checks("https://example.com/page")

    assert result.playwright_available is False
    assert result.error is not None
    assert result.js_rendered_content_differs is False

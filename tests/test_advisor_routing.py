"""Tests for advisor service's AIRouter integration (Cycle CC).

Positive-flow tests that prove ``evaluate_page`` actually routes through
``api.services.ai_router.AIRouter`` after the Cycle CC migration. The
architecture guard ``TestNoDirectProviderHTTPInServices`` is negative
(asserts no forbidden URLs); these tests are positive (assert the right
function was called with the right args).

Without this file, the migration could silently regress to direct
provider calls and only the architecture test would catch it — but that
test only fails if someone adds a URL literal. A regression that
introduces a different bypass (e.g. an SDK wrapper) wouldn't be caught.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.models.advisor import AdvisorRequest
from api.services.advisor import _run_critic, evaluate_page
from api.services.ai_router import (
    AIResponse,
    ModelConfig,
    ProviderAPIError,
    ProviderAuthError,
    SYSTEM_CONTEXT_ID,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ai_response(content: str, *, provider: str = "openai") -> AIResponse:
    return AIResponse(
        content=content,
        provider_id=provider,
        model="gpt-4o" if provider == "openai" else "gemini-2.0-flash",
        input_token_count=100,
        output_token_count=50,
        cost_estimate_usd=0.001,
        truncated=False,
    )


def _minimal_critic_json() -> str:
    """A minimal but valid critic JSON response — enough for
    _parse_critic_response to succeed without parse errors."""
    import json
    return json.dumps({
        "factual_grounding": {
            "is_critical": False,
            "specific_facts": [{"text": "claim 1", "is_specific": True}],
            "generalities": [],
            "verdict": "grounded",
        },
        "self_containment": {"sections": []},
        "structural_fitness": {"mismatches": [], "unnecessary_structure": []},
        "authority_signals": {
            "citations_present": [],
            "citations_missing": [],
            "placeholder_citations": [],
        },
        "honest_placeholders": {"at_real_gaps": [], "decorative": []},
        "strengths": ["minimum strength 1", "minimum strength 2"],
        "confidence_notes": [],
    })


# ---------------------------------------------------------------------------
# Acceptance criterion #8 — positive observability
# ---------------------------------------------------------------------------

class TestAdvisorRoutesThroughAIRouter:
    """Per Cycle CC acceptance criterion #8: the migrated evaluate_page
    must demonstrably call AIRouter (with the right customer_id and
    arguments). The architecture guard from Cycle BB only proves the
    absence of forbidden URLs — these tests prove the presence of the
    AIRouter call."""

    @pytest.mark.asyncio
    async def test_evaluate_page_calls_ai_router_call_text(self):
        """When evaluate_page runs successfully, it must invoke
        ai_router.call_text with customer_id=SYSTEM_CONTEXT_ID and a
        ModelConfig built by _pick_critic_model."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            request = AdvisorRequest(content="some test content", url=None)
            markdown, should_prompt = await evaluate_page(request)

        # AIRouter was called with the canonical migration shape.
        assert captured.get("customer_id") == SYSTEM_CONTEXT_ID, (
            "evaluate_page did not pass SYSTEM_CONTEXT_ID — usage rollups "
            "would attribute this call to the wrong (or no) tenant."
        )
        assert "system_prompt" in captured
        assert "user_prompt" in captured
        # Should contain the actual content to be evaluated.
        assert "some test content" in captured["user_prompt"]
        # ModelConfig is the right type with one of the known models.
        cfg = captured["model_config"]
        assert isinstance(cfg, ModelConfig)
        assert cfg.model in {"gpt-4o", "gemini-2.0-flash"}
        # Temperature preserved from pre-migration behaviour.
        assert cfg.temperature == 0.2

        # And a markdown report came back (positive end-to-end).
        assert markdown
        assert isinstance(should_prompt, bool)

    @pytest.mark.asyncio
    async def test_run_critic_passes_provider_neutral_arguments(self):
        """_run_critic must NOT pass any provider-specific knobs
        (response_format, top_p, etc.) — those would leak the
        abstraction. ModelConfig has exactly 3 fields by design."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            await _run_critic("test content", original=None)

        # The only kwargs that should appear are the AIRouter signature ones.
        expected_keys = {"customer_id", "system_prompt", "user_prompt", "model_config"}
        actual_keys = set(captured.keys())
        unexpected = actual_keys - expected_keys
        assert not unexpected, (
            f"_run_critic passed provider-specific args to AIRouter: "
            f"{sorted(unexpected)}. ModelConfig is sparse by design — "
            f"do not leak provider knobs through this path."
        )

    @pytest.mark.asyncio
    async def test_evaluate_page_degrades_gracefully_on_no_key(self):
        """No customer key + no env key → ProviderAuthError → degraded
        markdown, NOT a 500. Per Cycle CC strategic advisory: raw errors
        must not bubble to the client."""
        async def boom(**kwargs):
            raise ProviderAuthError("No keys configured")

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=boom,
        ):
            request = AdvisorRequest(content="x", url=None)
            markdown, should_prompt = await evaluate_page(request)

        assert "AI advisor unavailable" in markdown
        assert should_prompt is False
        # Message should be actionable.
        assert "API key" in markdown or "key" in markdown.lower()

    @pytest.mark.asyncio
    async def test_evaluate_page_degrades_gracefully_on_parse_failure(self):
        """LLM returned non-JSON → ValueError inside _run_critic →
        degraded markdown, NOT a 500. Per Cycle CC strategic advisory."""
        async def fake_call_text(**kwargs):
            # Return text that's emphatically not JSON.
            return _ai_response("I'm a chatbot. I'd love to evaluate that for you!")

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            request = AdvisorRequest(content="x", url=None)
            markdown, should_prompt = await evaluate_page(request)

        assert "could not be parsed" in markdown
        assert should_prompt is False

    @pytest.mark.asyncio
    async def test_evaluate_page_propagates_provider_api_error(self):
        """A genuine provider HTTP failure (ProviderAPIError) propagates
        — the advisor router maps this to 5xx with an error envelope.
        AIRouter has already logged success=False at this point, so
        observability is intact."""
        async def boom(**kwargs):
            raise ProviderAPIError("openai HTTP 503: upstream timeout")

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=boom,
        ):
            request = AdvisorRequest(content="x", url=None)
            with pytest.raises(ProviderAPIError):
                await evaluate_page(request)


# ---------------------------------------------------------------------------
# JSON-cleanup behaviour (option A — no response_format hint)
# ---------------------------------------------------------------------------

class TestCriticJSONCleanup:
    """Per the approved JSON-mode decision (option A): no
    ``response_format`` hint sent to providers. Drives instead by prompt
    + robust parsing. Lock the parsing rules so a future "helpful"
    edit doesn't break the cleanup."""

    @pytest.mark.asyncio
    async def test_strips_markdown_fence_around_json(self):
        """Some models wrap JSON in ```json ... ``` despite the prompt.
        _run_critic must strip the fence and still parse."""
        async def fake_call_text(**kwargs):
            return _ai_response(f"```json\n{_minimal_critic_json()}\n```")

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            parsed = await _run_critic("test content", original=None)

        assert isinstance(parsed, dict)
        assert "factual_grounding" in parsed

    @pytest.mark.asyncio
    async def test_strips_bare_fence_around_json(self):
        """``` (without language tag) is also common. Strip both."""
        async def fake_call_text(**kwargs):
            return _ai_response(f"```\n{_minimal_critic_json()}\n```")

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            parsed = await _run_critic("test content", original=None)

        assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_raises_value_error_on_json_array(self):
        """The downstream parser expects a dict. If the LLM returns a
        JSON array, we surface as ValueError so evaluate_page's
        graceful-degrade path catches it (instead of letting
        _parse_critic_response crash on .get() against a list)."""
        async def fake_call_text(**kwargs):
            return _ai_response('["not", "a", "dict"]')

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            with pytest.raises(ValueError, match="not as a JSON object"):
                await _run_critic("test content", original=None)

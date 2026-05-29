"""AIRouter unit tests (v2.6 M2.1 / Cycle Z).

Per docs/pending/2026-05-29_m2_airouter.md §The Evaluator, plus the
architectural test the user added in their approval directive.

Tests run synchronously where they don't touch the network and via
pytest-asyncio where they exercise the async dispatch path. We mock
the provider drivers — never make a real HTTP call from these tests
(every test would burn AI credits and become flaky on provider
outages).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api.services.ai_router import (
    AIResponse,
    AIRouter,
    ModelConfig,
    ProviderAPIError,
    ProviderAuthError,
    SYSTEM_CONTEXT_ID,
    _log_usage,
    _SAFE_METADATA_KEYS,
)


# ---------------------------------------------------------------------------
# Constants for tests
# ---------------------------------------------------------------------------

_CFG = ModelConfig(model="gpt-4o", max_tokens=100, temperature=0.2)


def _fake_response(provider: str = "openai", *, truncated: bool = False) -> AIResponse:
    return AIResponse(
        content="ok",
        provider_id=provider,
        model=_CFG.model,
        input_token_count=42,
        output_token_count=7,
        cost_estimate_usd=0.0,
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Unit Test 1 — Fallback to SYSTEM_CONTEXT_ID + system env key
# ---------------------------------------------------------------------------

class TestFallback:
    """Per QA spec Unit Test 1: customer has no key → system env key →
    usage logged with customer_id=SYSTEM_CONTEXT_ID."""

    @pytest.mark.asyncio
    async def test_no_customer_key_falls_back_to_env_and_logs_system_account(
        self, monkeypatch
    ):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-env-key")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        router = AIRouter()

        # Replace the openai driver with a mock that returns a known
        # AIResponse without making a real HTTP call.
        mock_driver = MagicMock()
        mock_driver.provider_id = "openai"

        async def fake_call_text(**kwargs):
            return _fake_response("openai")

        mock_driver.call_text = fake_call_text
        router._drivers = {"openai": mock_driver}

        captured = []

        def capture_log(metadata):
            captured.append(dict(metadata))

        with patch(
            "api.services.ai_router._log_usage", side_effect=capture_log
        ):
            response = await router.call_text(
                customer_id=SYSTEM_CONTEXT_ID,
                system_prompt="sys",
                user_prompt="hello",
                model_config=_CFG,
            )

        assert response.provider_id == "openai"
        assert response.content == "ok"

        # Usage was logged with SYSTEM_CONTEXT_ID
        assert len(captured) == 1
        assert captured[0]["customer_id"] == SYSTEM_CONTEXT_ID
        assert captured[0]["provider"] == "openai"
        assert captured[0]["success"] is True


# ---------------------------------------------------------------------------
# Unit Test 2 — Auth failure → ProviderAuthError → maps to 402
# ---------------------------------------------------------------------------

class TestAuthFailure:
    """Per QA spec Unit Test 2: customer key AND system env key missing
    → ProviderAuthError raised (which the calling router maps to 402)."""

    @pytest.mark.asyncio
    async def test_no_keys_anywhere_raises_provider_auth_error(
        self, monkeypatch
    ):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        # Also nuke any subprocess-inherited env via direct os.environ.
        for k in ("OPENAI_API_KEY", "GEMINI_API_KEY"):
            os.environ.pop(k, None)

        router = AIRouter()

        with pytest.raises(ProviderAuthError) as excinfo:
            await router.call_text(
                customer_id=SYSTEM_CONTEXT_ID,
                system_prompt="sys",
                user_prompt="hello",
                model_config=_CFG,
            )

        # Error message should name the env vars so a developer knows
        # what to set without grepping the codebase.
        assert "OPENAI_API_KEY" in str(excinfo.value)
        assert "GEMINI_API_KEY" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Unit Test 3 — log_usage fires even when the driver raises
# ---------------------------------------------------------------------------

class TestErrorPathStillLogs:
    """Per QA spec Unit Test 3: when a provider driver raises an API
    error mid-call, _log_usage must still be called (with success=False)
    so the failed attempt appears in the audit trail.

    Without this guarantee, billing/observability silently skips
    exactly the cases that matter most."""

    @pytest.mark.asyncio
    async def test_provider_api_error_still_logs_usage_with_success_false(
        self, monkeypatch
    ):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        router = AIRouter()

        mock_driver = MagicMock()
        mock_driver.provider_id = "openai"

        async def boom(**kwargs):
            raise ProviderAPIError("openai HTTP 503: upstream timeout")

        mock_driver.call_text = boom
        router._drivers = {"openai": mock_driver}

        captured = []

        def capture_log(metadata):
            captured.append(dict(metadata))

        with patch(
            "api.services.ai_router._log_usage", side_effect=capture_log
        ):
            with pytest.raises(ProviderAPIError):
                await router.call_text(
                    customer_id=SYSTEM_CONTEXT_ID,
                    system_prompt="sys",
                    user_prompt="hello",
                    model_config=_CFG,
                )

        # log_usage was called exactly once, with success=False and
        # the error message captured.
        assert len(captured) == 1
        assert captured[0]["success"] is False
        assert captured[0]["customer_id"] == SYSTEM_CONTEXT_ID
        assert captured[0]["provider"] == "openai"
        assert "503" in captured[0]["error_message"]


# ---------------------------------------------------------------------------
# Unit Test 4 — Cross-driver AIResponse contract consistency
# ---------------------------------------------------------------------------

class TestUnifiedResponseContract:
    """Per QA spec Unit Test 4: swap driver (openai → gemini) and the
    caller receives a same-shape AIResponse for identical inputs.

    Locks in the abstraction: callers must not be able to tell which
    provider answered by inspecting the response structure."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider_id,model", [
        ("openai", "gpt-4o"),
        ("gemini", "gemini-2.0-flash"),
    ])
    async def test_response_shape_uniform_across_providers(
        self, monkeypatch, provider_id, model
    ):
        # Set env var so credential resolution picks the right provider.
        env_var_for_provider = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}
        # Clear both then set just the one under test.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv(env_var_for_provider[provider_id], "test-key")

        router = AIRouter()

        mock_driver = MagicMock()
        mock_driver.provider_id = provider_id

        async def fake_call_text(**kwargs):
            # Echo the model from the ModelConfig so AIRouter's
            # post-PriceLookup overwrite (M2.2 / Cycle AA) hits a
            # valid pricing entry for whichever provider this
            # parametrisation is testing.
            return AIResponse(
                content="ok",
                provider_id=provider_id,
                model=kwargs["model_config"].model,
                input_token_count=42,
                output_token_count=7,
                cost_estimate_usd=0.0,
                truncated=False,
            )

        mock_driver.call_text = fake_call_text
        # Only register the driver we're testing — forces credential
        # resolution to actually find a key for this provider.
        router._drivers = {provider_id: mock_driver}

        # Use the provider-appropriate model so PriceLookup finds an
        # entry. (Pre-M2.2 / Cycle AA this didn't matter because cost
        # was hardcoded 0.0; now the router post-processes via
        # PriceLookup which raises UnknownModelError on a mismatched
        # provider+model pair.)
        cfg_for_provider = ModelConfig(model=model, max_tokens=100, temperature=0.2)

        with patch("api.services.ai_router._log_usage"):
            response = await router.call_text(
                customer_id=SYSTEM_CONTEXT_ID,
                system_prompt="sys",
                user_prompt="hello",
                model_config=cfg_for_provider,
            )

        # Same shape regardless of provider.
        assert isinstance(response, AIResponse)
        assert hasattr(response, "content")
        assert hasattr(response, "provider_id")
        assert hasattr(response, "model")
        assert hasattr(response, "input_token_count")
        assert hasattr(response, "output_token_count")
        assert hasattr(response, "cost_estimate_usd")
        assert hasattr(response, "truncated")
        assert response.provider_id == provider_id


# ---------------------------------------------------------------------------
# Architectural test — no provider SDK imports in api/services/
# ---------------------------------------------------------------------------

class TestNoProviderSDKImports:
    """User directive in M2.1 approval:

        Architectural Test: Assert grep -r "import openai" api/services/
        returns zero results.

    Generalized to all major LLM SDK imports — the abstraction-leak
    vector. Drivers use httpx.AsyncClient directly; no SDK should appear
    anywhere under api/services/."""

    @pytest.fixture
    def services_dir(self) -> Path:
        # Resolve relative to this test file: tests/ → ../api/services/
        return Path(__file__).parent.parent / "api" / "services"

    @pytest.mark.parametrize("forbidden_pattern", [
        "import openai",
        "from openai",
        "import anthropic",
        "from anthropic",
        # Google's Gemini SDK is `google.generativeai` — not currently
        # installed, but guarding against future drift.
        "import google.generativeai",
        "from google.generativeai",
    ])
    def test_no_sdk_imports_under_api_services(
        self, services_dir, forbidden_pattern
    ):
        # Use plain ripgrep-style search via Python so the test works
        # even where grep/rg isn't on PATH. Walk only .py files,
        # skip __pycache__.
        matches = []
        for path in services_dir.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), start=1):
                # Match imports only — ignore comments / docstrings
                # mentioning the pattern in prose.
                stripped = line.lstrip()
                if stripped.startswith(forbidden_pattern):
                    matches.append(f"{path.relative_to(services_dir)}:{lineno}: {line.strip()}")

        assert not matches, (
            f"Forbidden SDK import found in api/services/ — every LLM call "
            f"must go through AIRouter (M2.1 / Cycle Z constraint). "
            f"Use httpx.AsyncClient inside api/services/providers/* instead.\n"
            f"Pattern: {forbidden_pattern!r}\n"
            f"Matches:\n  " + "\n  ".join(matches)
        )


# ---------------------------------------------------------------------------
# _log_usage privacy / sanitisation tests
# ---------------------------------------------------------------------------

class TestLogUsageSanitisation:
    """Spec §Negative Constraints — _log_usage MUST NOT pass raw prompt
    or response text. Keys outside _SAFE_METADATA_KEYS are silently
    dropped. These tests lock that in."""

    def test_unsafe_keys_silently_dropped(self, caplog):
        import logging
        caplog.set_level(logging.INFO)

        _log_usage({
            "customer_id": "test",
            "provider": "openai",
            "model": "gpt-4o",
            # Forbidden keys below — privacy / PII risk
            "prompt": "this is a customer prompt with PII",
            "response": "this is the model response",
            "user_email": "alice@example.com",
        })

        # The structured log entry should have the safe keys, not the
        # unsafe ones. We check the record's extra dict directly.
        ai_records = [r for r in caplog.records if getattr(r, "message", "") == "ai_usage" or r.msg == "ai_usage"]
        assert ai_records, "Expected an 'ai_usage' log record"
        rec = ai_records[-1]
        # caplog records attach `extra` keys onto the record itself.
        assert getattr(rec, "customer_id", None) == "test"
        assert getattr(rec, "provider", None) == "openai"
        # The unsafe keys MUST NOT be present
        assert not hasattr(rec, "prompt"), (
            "Raw prompt leaked into ai_usage log — privacy guard failed."
        )
        assert not hasattr(rec, "response"), (
            "Raw response leaked into ai_usage log — privacy guard failed."
        )
        assert not hasattr(rec, "user_email"), (
            "Unknown key 'user_email' leaked — whitelist not enforced."
        )

    def test_safe_keys_whitelist_documents_intent(self):
        """The whitelist is the privacy contract — assert its members
        explicitly so any future addition is visible in a code review."""
        expected = {
            "customer_id", "provider", "model",
            "input_token_count", "output_token_count", "cost_estimate_usd",
            "task_type", "success", "error_message", "timestamp",
        }
        assert _SAFE_METADATA_KEYS == frozenset(expected), (
            f"_SAFE_METADATA_KEYS changed. If you intentionally added "
            f"or removed a key, update this test and document the privacy "
            f"reasoning. Current: {sorted(_SAFE_METADATA_KEYS)}"
        )

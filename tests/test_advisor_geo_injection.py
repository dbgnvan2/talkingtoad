"""Tests for advisor service's GeoConfig prompt injection (Cycle FF).

These tests verify the spec at
``docs/pending/2026-05-29_cycle_ff_geo_config_injection.md``:

- When ``AdvisorRequest.geo_config`` is provided, the system_prompt
  passed to AIRouter must contain the four whitelisted entity fields
  (``org_name``, ``primary_location``, ``location_pool``,
  ``topic_entities``).
- When ``AdvisorRequest.geo_config`` is None, the system_prompt must
  fall back to the legacy generic prompt — no ENTITY VALIDATION CONTEXT
  block, but the legacy core phrase MUST still be present (semantic
  continuity, not exact-string equivalence).
- Non-whitelisted GeoConfig fields (``client_name``, ``model``, etc.)
  must NOT leak into the prompt — privacy/correctness boundary.
- End-to-end ``evaluate_page`` with a populated GeoConfig must run
  without exceptions and produce non-empty markdown.

These tests pair with the Cycle CC ``test_advisor_routing.py`` tests
(which lock the AIRouter call shape). The Cycle FF change only modifies
``system_prompt`` content — it does NOT change the call signature, so
those tests should remain green.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from api.models.advisor import AdvisorRequest
from api.models.geo_config import GeoConfig
from api.services.advisor import _run_critic, evaluate_page
from api.services.ai_router import AIResponse


# ---------------------------------------------------------------------------
# Helpers (mirrors test_advisor_routing.py for consistency)
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
    """Minimal but valid critic JSON — enough for _parse_critic_response."""
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
# Cycle FF acceptance tests
# ---------------------------------------------------------------------------


class TestGeoConfigPromptInjection:
    """The four locked behaviours from the Cycle FF spec, plus the
    end-to-end smoke test."""

    # -- Test 1 (QA #1) — Prompt Interpolation -----------------------------

    @pytest.mark.asyncio
    async def test_prompt_includes_org_and_primary_location_when_geoconfig_provided(self):
        """A GeoConfig with org_name and primary_location set must
        result in both strings appearing inside the system_prompt that
        AIRouter receives. This is the core injection contract."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        geo = GeoConfig(
            domain="testcorp.example",
            org_name="TestCorp",
            primary_location="Springfield",
            topic_entities=["widgets"],
            location_pool=["Shelbyville"],
        )

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            await _run_critic("page content", original=None, geo_config=geo)

        system_prompt = captured["system_prompt"]
        assert "TestCorp" in system_prompt, (
            "org_name 'TestCorp' missing from system_prompt — GeoConfig "
            "injection broke. The critic will not be entity-aware."
        )
        assert "Springfield" in system_prompt, (
            "primary_location 'Springfield' missing from system_prompt — "
            "geographic anchor lost."
        )
        # And the entity-validation block header must be present so the
        # LLM knows this is special context, not just trivia.
        assert "ENTITY VALIDATION CONTEXT" in system_prompt

    # -- Test 2 (QA #2 revised) — Fallback Parity --------------------------

    @pytest.mark.asyncio
    async def test_fallback_prompt_when_geoconfig_is_none(self):
        """When geo_config is None (the legacy path), the system_prompt
        must NOT contain the ENTITY VALIDATION CONTEXT header, and the
        legacy core phrase must still be present. Semantic contract —
        not exact-string equivalence, so a future prompt-typo fix
        doesn't trip this test."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            # Both explicit-None and the default kwarg path; cover both.
            await _run_critic("page content", original=None, geo_config=None)

        system_prompt = captured["system_prompt"]
        assert "ENTITY VALIDATION CONTEXT" not in system_prompt, (
            "Legacy path leaked the ENTITY VALIDATION CONTEXT block — "
            "fallback parity broken. Callers without GeoConfig must see "
            "the unmodified legacy prompt."
        )
        # Legacy core phrase — semantic continuity.
        assert (
            "content quality reviewer for Generative Engine Optimization"
            in system_prompt
        ), (
            "Legacy core phrase missing from the fallback prompt — the "
            "generic critic prompt was unintentionally altered."
        )

    # -- Test 3 (QA #3) — End-to-End with GeoConfig ------------------------

    @pytest.mark.asyncio
    async def test_evaluate_page_with_geoconfig_runs_clean(self):
        """``evaluate_page`` with a populated GeoConfig must thread the
        config through to _run_critic, produce no exceptions, and return
        non-empty markdown. Catches a regression where the threading
        breaks (e.g. someone refactors evaluate_page and drops the
        geo_config kwarg)."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        geo = GeoConfig(
            domain="acme.example",
            org_name="Acme Corp",
            primary_location="Coyote Canyon",
            topic_entities=["roadrunners", "anvils"],
            location_pool=["Tumbleweed Flats", "Cactus Junction"],
        )
        request = AdvisorRequest(
            content="some page content here",
            url=None,
            geo_config=geo,
        )

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            markdown, should_prompt = await evaluate_page(request)

        # End-to-end smoke: markdown came back, no exceptions.
        assert markdown, "evaluate_page returned empty markdown"
        assert isinstance(should_prompt, bool)
        # Threading worked — the system_prompt actually contains the
        # entity strings, proving request.geo_config reached _run_critic.
        assert "Acme Corp" in captured["system_prompt"]
        assert "Coyote Canyon" in captured["system_prompt"]

    # -- Test 4 (supporting) — all four entity fields interpolated --------

    @pytest.mark.asyncio
    async def test_all_four_entity_fields_appear_in_prompt(self):
        """A refactor that drops one of the four whitelisted fields by
        accident must fail. Pass a GeoConfig with every entity field
        populated and assert each value lands in the prompt."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        geo = GeoConfig(
            domain="entity-test.example",
            org_name="Whitelist Org",
            primary_location="Whitelist Primary City",
            topic_entities=["TopicAlpha", "TopicBeta"],
            location_pool=["LocOne", "LocTwo"],
        )

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            await _run_critic("content", original=None, geo_config=geo)

        system_prompt = captured["system_prompt"]
        # All four entity-bearing values must appear.
        for value in (
            "Whitelist Org",
            "Whitelist Primary City",
            "TopicAlpha",
            "TopicBeta",
            "LocOne",
            "LocTwo",
        ):
            assert value in system_prompt, (
                f"Entity-whitelist field value {value!r} missing from "
                "system_prompt. _build_geo_context dropped a field."
            )

    # -- Test 5 (supporting) — non-whitelisted fields do not leak ---------

    # -- Cycle FF.1 supporting — HTTP boundary threading ------------------

    @pytest.mark.asyncio
    async def test_http_advisor_endpoint_threads_geo_config_dict_to_prompt(
        self, api_client, auth_headers
    ):
        """Cycle FF.1: POSTing geo_config (as a dict, the wire format)
        to /api/ai/advisor must reach the LLM prompt with the entity
        strings interpolated. This is the end-to-end UI Action
        Verification per CLAUDE.md — the router-payload field is not
        considered live until a real HTTP call is shown to flow through
        to the AIRouter system_prompt."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        body = {
            "content": "page body",
            "geo_config": {
                "domain": "http-test.example",
                "org_name": "HTTPRoutedOrg",
                "primary_location": "HTTPRoutedCity",
                "topic_entities": ["HTTPTopic"],
                "location_pool": ["HTTPLoc"],
            },
        }

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            response = await api_client.post(
                "/api/ai/advisor", json=body, headers=auth_headers
            )

        assert response.status_code == 200, response.text
        # AIRouter was actually called (proves request reached the service).
        assert "system_prompt" in captured, (
            "AIRouter.call_text was not invoked — request did not reach "
            "the advisor service layer."
        )
        system_prompt = captured["system_prompt"]
        # The HTTP-supplied entity strings must have flowed through.
        assert "HTTPRoutedOrg" in system_prompt, (
            "org_name from HTTP geo_config did not reach the LLM prompt — "
            "router-payload threading broken."
        )
        assert "HTTPRoutedCity" in system_prompt
        assert "HTTPTopic" in system_prompt
        assert "HTTPLoc" in system_prompt

    @pytest.mark.asyncio
    async def test_http_advisor_endpoint_without_geo_config_uses_legacy_prompt(
        self, api_client, auth_headers
    ):
        """Cycle FF.1 fallback parity at the HTTP boundary: a request
        with no ``geo_config`` field (or null) must produce the legacy
        generic prompt — no ENTITY VALIDATION CONTEXT block. Locks the
        contract that omitting the field is the documented opt-out."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        # geo_config absent from the body entirely — most common shape
        # for callers that don't opt in.
        body = {"content": "page body"}

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            response = await api_client.post(
                "/api/ai/advisor", json=body, headers=auth_headers
            )

        assert response.status_code == 200, response.text
        system_prompt = captured["system_prompt"]
        assert "ENTITY VALIDATION CONTEXT" not in system_prompt, (
            "HTTP request without geo_config still produced the entity "
            "block — fallback parity broken at the router boundary."
        )

    @pytest.mark.asyncio
    async def test_non_whitelisted_geoconfig_fields_do_not_leak(self):
        """Privacy / correctness boundary: client_name and model are
        NOT entity-validation context. They must not enter the prompt.
        ``client_name`` in particular is consultant-facing identifying
        info — leaking it to the LLM is a real boundary breach."""
        captured: dict = {}

        async def fake_call_text(**kwargs):
            captured.update(kwargs)
            return _ai_response(_minimal_critic_json())

        geo = GeoConfig(
            domain="leak-test.example",
            org_name="VisibleOrg",
            primary_location="VisibleCity",
            topic_entities=["VisibleTopic"],
            location_pool=["VisibleLoc"],
            # The fields that MUST stay out of the prompt:
            client_name="ConfidentialCo",
            prepared_by="ConfidentialConsultant",
            model="gemini-2.0-pro",
        )

        with patch(
            "api.services.advisor.ai_router.call_text",
            side_effect=fake_call_text,
        ):
            await _run_critic("content", original=None, geo_config=geo)

        system_prompt = captured["system_prompt"]
        # Whitelisted fields are present (control).
        assert "VisibleOrg" in system_prompt
        # Non-whitelisted fields must be absent.
        assert "ConfidentialCo" not in system_prompt, (
            "client_name leaked into the system_prompt — privacy boundary "
            "breach. Non-whitelisted GeoConfig fields must never enter "
            "the LLM context."
        )
        assert "ConfidentialConsultant" not in system_prompt, (
            "prepared_by leaked into the system_prompt — privacy boundary "
            "breach."
        )
        assert "gemini-2.0-pro" not in system_prompt, (
            "model leaked into the system_prompt — model selection is an "
            "internal concern, not entity-validation context."
        )

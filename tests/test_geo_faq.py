"""GA3 — GEO FAQ Schema Generator tests.

Tests:
- Template mode: >= 6-word questions, limit respected, round-robin coverage.
- AI mode: mocked call_text, valid questions pass, fallback on error.
- Schema validation: FAQPage structure.
- Endpoint contract: 200, 401, 422 (unknown domain, empty entities, fallback).
- Adversarial: degenerate 1-word entity/location still yields valid or drops.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from api.models.geo_config import GeoConfig
from api.services.geo_faq import (
    _build_faq_block,
    _build_template_questions,
    _parse_ai_questions,
    _passes_longtail,
    generate_faq_block,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def realistic_geo_config():
    """A realistic GeoConfig for a nonprofit counselling service."""
    return GeoConfig(
        domain="livingsystems.ca",
        org_name="Living Systems Counselling",
        topic_entities=["Bowen Theory", "Systems Thinking", "Grief Counselling"],
        primary_location="Vancouver",
        location_pool=["Burnaby", "Richmond", "North Vancouver"],
    )


@pytest.fixture
def minimal_geo_config():
    """Minimal valid GeoConfig — one entity, one location."""
    return GeoConfig(
        domain="example.org",
        org_name="Example Org",
        topic_entities=["Therapy"],
        primary_location="Seattle",
        location_pool=[],
    )


@pytest.fixture
def degenerate_geo_config():
    """Adversarial: 1-word entity and 1-word location."""
    return GeoConfig(
        domain="test.org",
        org_name="Test",
        topic_entities=["X"],
        primary_location="Y",
        location_pool=[],
    )


@pytest.fixture
def empty_entities_config():
    """GeoConfig with no topic_entities."""
    return GeoConfig(
        domain="empty.org",
        org_name="Empty Org",
        topic_entities=[],
        primary_location="Portland",
        location_pool=["Salem"],
    )


# ── _passes_longtail ─────────────────────────────────────────────────────


class TestPassesLongtail:
    def test_six_words_passes(self):
        assert _passes_longtail("What is grief counselling in Vancouver?") is True

    def test_exactly_six_words_passes(self):
        assert _passes_longtail("one two three four five six") is True

    def test_five_words_fails(self):
        assert _passes_longtail("one two three four five") is False

    def test_empty_fails(self):
        assert _passes_longtail("") is False

    def test_single_word_fails(self):
        assert _passes_longtail("counselling") is False


# ── Template engine ──────────────────────────────────────────────────────


class TestTemplateEngine:
    def test_all_questions_have_six_plus_words(self, realistic_geo_config):
        """Every generated question must have >= 6 words."""
        questions = _build_template_questions(realistic_geo_config, limit=20)
        for q in questions:
            word_count = len(q.split())
            assert word_count >= 6, f"Question has only {word_count} words: {q!r}"

    def test_limit_respected(self, realistic_geo_config):
        """Output never exceeds the requested limit."""
        for limit in [1, 4, 8, 12]:
            questions = _build_template_questions(realistic_geo_config, limit=limit)
            assert len(questions) <= limit

    def test_round_robin_multi_entity_coverage(self, realistic_geo_config):
        """Questions should cover multiple entities, not just the first."""
        questions = _build_template_questions(realistic_geo_config, limit=8)
        entities_mentioned = set()
        for q in questions:
            for entity in realistic_geo_config.topic_entities:
                if entity in q:
                    entities_mentioned.add(entity)
        # With 3 entities and 8 questions, all entities should appear
        assert len(entities_mentioned) >= 2

    def test_empty_topic_entities_returns_empty(self, empty_entities_config):
        """No topic entities -> no questions."""
        questions = _build_template_questions(empty_entities_config, limit=8)
        assert questions == []

    def test_minimal_config_still_works(self, minimal_geo_config):
        """One entity, one location should still produce questions."""
        questions = _build_template_questions(minimal_geo_config, limit=4)
        assert len(questions) > 0
        for q in questions:
            assert len(q.split()) >= 6

    def test_adversarial_degenerate_entity(self, degenerate_geo_config):
        """1-word entity + 1-word location: questions must still pass 6-word filter.

        The templates are designed to produce >= 6 words even with single-word
        interpolation. Verify no sub-6 results slip through.
        """
        questions = _build_template_questions(degenerate_geo_config, limit=8)
        for q in questions:
            word_count = len(q.split())
            assert word_count >= 6, f"Degenerate input produced {word_count}-word question: {q!r}"

    def test_no_duplicates(self, realistic_geo_config):
        """No duplicate questions in output."""
        questions = _build_template_questions(realistic_geo_config, limit=20)
        assert len(questions) == len(set(questions))


# ── Schema validation ────────────────────────────────────────────────────


class TestSchemaValidation:
    def test_faq_block_has_correct_structure(self, realistic_geo_config):
        """Output validates as a Schema.org FAQPage."""
        questions = _build_template_questions(realistic_geo_config, limit=4)
        block = _build_faq_block(questions, realistic_geo_config)

        assert block["@context"] == "https://schema.org"
        assert block["@type"] == "FAQPage"
        assert isinstance(block["mainEntity"], list)
        assert len(block["mainEntity"]) == len(questions)

        for item in block["mainEntity"]:
            assert item["@type"] == "Question"
            assert "name" in item
            assert item["acceptedAnswer"]["@type"] == "Answer"
            assert "text" in item["acceptedAnswer"]

    def test_faq_block_is_json_serializable(self, realistic_geo_config):
        """The output must serialize to valid JSON."""
        questions = _build_template_questions(realistic_geo_config, limit=4)
        block = _build_faq_block(questions, realistic_geo_config)
        serialized = json.dumps(block)
        parsed = json.loads(serialized)
        assert parsed["@type"] == "FAQPage"


# ── AI mode (mocked) ────────────────────────────────────────────────────


class TestAIMode:
    @pytest.mark.asyncio
    async def test_ai_mode_valid_questions(self, realistic_geo_config):
        """AI returns valid >= 6-word questions -> emitted with mode_used='ai'."""
        fake_response_content = json.dumps([
            "What is Bowen Theory and how does it help families in Vancouver?",
            "How does grief counselling support people dealing with loss in Burnaby?",
        ])

        mock_response = AsyncMock()
        mock_response.return_value = type("AIResponse", (), {
            "content": fake_response_content,
            "provider_id": "openai",
            "model": "gpt-4o-mini",
            "input_token_count": 100,
            "output_token_count": 50,
            "cost_estimate_usd": 0.001,
            "truncated": False,
        })()

        with patch("api.services.geo_faq.ai_router._resolve_credentials", return_value=("openai", "fake-key")):
            with patch("api.services.geo_faq.ai_router.call_text", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = mock_response.return_value
                result = await generate_faq_block(realistic_geo_config, mode="ai", limit=8)

        assert result["mode_used"] == "ai"
        assert len(result["questions"]) == 2
        assert result["token_usage"] is not None
        assert result["token_usage"]["input"] == 100
        assert result["token_usage"]["output"] == 50

    @pytest.mark.asyncio
    async def test_ai_mode_short_questions_fallback(self, realistic_geo_config):
        """AI returns only sub-6-word questions -> filtered out, fallback to template."""
        fake_response_content = json.dumps([
            "What is therapy?",
            "Grief help",
            "How to cope?",
        ])

        with patch("api.services.geo_faq.ai_router._resolve_credentials", return_value=("openai", "fake-key")):
            with patch("api.services.geo_faq.ai_router.call_text", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = type("AIResponse", (), {
                    "content": fake_response_content,
                    "provider_id": "openai",
                    "model": "gpt-4o-mini",
                    "input_token_count": 80,
                    "output_token_count": 30,
                    "cost_estimate_usd": 0.0005,
                    "truncated": False,
                })()
                result = await generate_faq_block(realistic_geo_config, mode="ai", limit=8)

        # Falls back to template because no AI questions passed the filter
        assert result["mode_used"] == "template"
        assert result["token_usage"] is None
        # Template questions are still valid
        for q in result["questions"]:
            assert len(q.split()) >= 6

    @pytest.mark.asyncio
    async def test_ai_mode_no_credentials_fallback(self, realistic_geo_config):
        """No AI credentials -> graceful fallback to template, no exception escapes."""
        from api.services.ai_router import ProviderAuthError

        with patch(
            "api.services.geo_faq.ai_router._resolve_credentials",
            side_effect=ProviderAuthError("No credentials"),
        ):
            result = await generate_faq_block(realistic_geo_config, mode="ai", limit=8)

        assert result["mode_used"] == "template"
        assert result["token_usage"] is None
        assert len(result["questions"]) > 0

    @pytest.mark.asyncio
    async def test_ai_mode_provider_error_fallback(self, realistic_geo_config):
        """Provider API error -> graceful fallback to template."""
        from api.services.ai_router import ProviderAPIError

        with patch("api.services.geo_faq.ai_router._resolve_credentials", return_value=("openai", "fake-key")):
            with patch(
                "api.services.geo_faq.ai_router.call_text",
                new_callable=AsyncMock,
                side_effect=ProviderAPIError("Connection refused"),
            ):
                result = await generate_faq_block(realistic_geo_config, mode="ai", limit=8)

        assert result["mode_used"] == "template"
        assert result["token_usage"] is None


# ── _parse_ai_questions ──────────────────────────────────────────────────


class TestParseAIQuestions:
    def test_valid_json_array(self):
        content = json.dumps(["What is therapy and how can it help in Vancouver?", "Short"])
        result = _parse_ai_questions(content, limit=10)
        assert len(result) == 1  # "Short" filtered out
        assert "therapy" in result[0]

    def test_markdown_code_fences_stripped(self):
        content = '```json\n["What is counselling and how does it work in Seattle?"]\n```'
        result = _parse_ai_questions(content, limit=10)
        assert len(result) == 1

    def test_invalid_json_returns_empty(self):
        result = _parse_ai_questions("not json at all", limit=10)
        assert result == []

    def test_not_array_returns_empty(self):
        result = _parse_ai_questions('{"questions": ["test"]}', limit=10)
        assert result == []

    def test_limit_enforced(self):
        questions = [f"What is entity number {i} doing in location {i}?" for i in range(20)]
        content = json.dumps(questions)
        result = _parse_ai_questions(content, limit=5)
        assert len(result) == 5


# ── generate_faq_block (integration-level) ───────────────────────────────


class TestGenerateFaqBlock:
    @pytest.mark.asyncio
    async def test_template_mode_returns_valid_structure(self, realistic_geo_config):
        result = await generate_faq_block(realistic_geo_config, mode="template", limit=4)

        assert result["mode_used"] == "template"
        assert result["token_usage"] is None
        assert len(result["questions"]) == 4
        assert result["faq_block"]["@type"] == "FAQPage"
        assert len(result["faq_block"]["mainEntity"]) == 4

    @pytest.mark.asyncio
    async def test_template_mode_empty_entities(self, empty_entities_config):
        result = await generate_faq_block(empty_entities_config, mode="template", limit=8)

        assert result["mode_used"] == "template"
        assert result["questions"] == []
        assert result["faq_block"]["mainEntity"] == []


# ── Endpoint contract tests ──────────────────────────────────────────────


class TestGeoFaqEndpoint:
    """Contract tests for POST /api/ai/geo-faq.

    Written BEFORE the frontend card per CLAUDE.md.
    """

    @pytest.mark.asyncio
    async def test_200_template_mode(self, api_client, test_store, auth_headers):
        """Happy path: configured domain, template mode -> 200 with schema."""
        # Set up GeoConfig in the store
        config = GeoConfig(
            domain="test.org",
            org_name="Test Org",
            topic_entities=["Family Therapy", "Grief Counselling"],
            primary_location="Vancouver",
            location_pool=["Burnaby", "Richmond"],
        )
        await test_store.save_geo_config(config)

        response = await api_client.post(
            "/api/ai/geo-faq",
            json={"domain": "test.org", "mode": "template", "limit": 4},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response shape
        assert "faq_block" in data
        assert "questions" in data
        assert "mode_used" in data
        assert "token_usage" in data

        assert data["mode_used"] == "template"
        assert data["token_usage"] is None
        assert len(data["questions"]) == 4
        assert data["faq_block"]["@context"] == "https://schema.org"
        assert data["faq_block"]["@type"] == "FAQPage"
        assert len(data["faq_block"]["mainEntity"]) == 4

        # Every question >= 6 words
        for q in data["questions"]:
            assert len(q.split()) >= 6

    @pytest.mark.asyncio
    async def test_401_without_auth(self, api_client, test_store):
        """Missing auth -> 401."""
        config = GeoConfig(
            domain="test.org",
            org_name="Test Org",
            topic_entities=["Therapy"],
            primary_location="Vancouver",
            location_pool=["Burnaby"],
        )
        await test_store.save_geo_config(config)

        response = await api_client.post(
            "/api/ai/geo-faq",
            json={"domain": "test.org"},
            # No auth headers
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_422_unknown_domain(self, api_client, auth_headers):
        """Unknown domain with no GeoConfig -> 422."""
        response = await api_client.post(
            "/api/ai/geo-faq",
            json={"domain": "nonexistent.org", "mode": "template"},
            headers=auth_headers,
        )
        assert response.status_code == 422
        data = response.json()
        assert "No GEO configuration found" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_422_empty_topic_entities(self, api_client, test_store, auth_headers):
        """Domain configured but topic_entities empty -> 422."""
        config = GeoConfig(
            domain="empty.org",
            org_name="Empty Org",
            topic_entities=[],
            primary_location="Portland",
            location_pool=["Salem"],
        )
        await test_store.save_geo_config(config)

        response = await api_client.post(
            "/api/ai/geo-faq",
            json={"domain": "empty.org", "mode": "template"},
            headers=auth_headers,
        )
        assert response.status_code == 422
        data = response.json()
        assert "topic_entities" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_422_malformed_body(self, api_client, auth_headers):
        """Malformed request body -> 422 (missing required 'domain' field)."""
        response = await api_client.post(
            "/api/ai/geo-faq",
            json={"not_a_field": "value"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ai_mode_no_key_fallback_200(self, api_client, test_store, auth_headers):
        """mode='ai' with no provider key -> 200 with mode_used='template' (graceful fallback)."""
        config = GeoConfig(
            domain="fallback.org",
            org_name="Fallback Org",
            topic_entities=["Art Therapy", "Play Therapy"],
            primary_location="Toronto",
            location_pool=["Mississauga"],
        )
        await test_store.save_geo_config(config)

        # Patch out AI credentials so it falls back
        from api.services.ai_router import ProviderAuthError

        with patch(
            "api.services.geo_faq.ai_router._resolve_credentials",
            side_effect=ProviderAuthError("No credentials"),
        ):
            response = await api_client.post(
                "/api/ai/geo-faq",
                json={"domain": "fallback.org", "mode": "ai", "limit": 4},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["mode_used"] == "template"
        assert len(data["questions"]) > 0


# ── Adversarial: no sub-6-word question ever emitted ─────────────────────


class TestAdversarialNoShortQuestions:
    """The one adversarial guarantee: no question in the output has < 6 words."""

    @pytest.mark.asyncio
    async def test_template_never_emits_short(self):
        """Even with the shortest possible entity/location, no short question."""
        config = GeoConfig(
            domain="a.org",
            org_name="A",
            topic_entities=["X"],
            primary_location="Y",
            location_pool=[],
        )
        result = await generate_faq_block(config, mode="template", limit=20)
        for q in result["questions"]:
            assert len(q.split()) >= 6, f"Short question emitted: {q!r}"

    @pytest.mark.asyncio
    async def test_ai_mode_filters_short(self):
        """AI producing a mix of valid and short questions: only valid pass."""
        config = GeoConfig(
            domain="mix.org",
            org_name="Mix",
            topic_entities=["CBT", "DBT"],
            primary_location="NYC",
            location_pool=["Brooklyn"],
        )

        mixed_response = json.dumps([
            "What is CBT therapy and how does it help patients in NYC?",  # 12 words - valid
            "CBT help",  # 2 words - invalid
            "How can DBT techniques support emotional regulation in Brooklyn?",  # 9 words - valid
            "therapy",  # 1 word - invalid
        ])

        with patch("api.services.geo_faq.ai_router._resolve_credentials", return_value=("openai", "key")):
            with patch("api.services.geo_faq.ai_router.call_text", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = type("AIResponse", (), {
                    "content": mixed_response,
                    "provider_id": "openai",
                    "model": "gpt-4o-mini",
                    "input_token_count": 90,
                    "output_token_count": 40,
                    "cost_estimate_usd": 0.0008,
                    "truncated": False,
                })()
                result = await generate_faq_block(config, mode="ai", limit=8)

        assert result["mode_used"] == "ai"
        assert len(result["questions"]) == 2
        for q in result["questions"]:
            assert len(q.split()) >= 6

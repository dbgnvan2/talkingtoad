"""GA4 — Authoritative Entity Schema Factory tests.

Tests:
- Schema validity: @context, @type, nested OfferCatalog, Service[], FAQPage.
- sameAs: present when entity_wikipedia_url set, ABSENT when blank.
- Adversarial: blank URL -> no sameAs key (never "", [""], null).
- Serialization: GeoConfig round-trips entity_wikipedia_url; older configs load.
- Endpoint contract: 200, 401, 422 (unknown domain, empty entities, malformed).
"""

import json

import pytest

from api.models.geo_config import GeoConfig
from api.services.geo_schema_factory import build_entity_schema


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def full_config():
    """Realistic GeoConfig with entity_wikipedia_url set."""
    return GeoConfig(
        domain="livingsystems.ca",
        org_name="Living Systems Counselling",
        topic_entities=["Bowen Theory", "Systems Thinking", "Grief Counselling"],
        primary_location="Vancouver",
        location_pool=["Burnaby", "Richmond", "North Vancouver"],
        entity_wikipedia_url="https://en.wikipedia.org/wiki/Living_Systems_Counselling",
    )


@pytest.fixture
def no_entity_url_config():
    """GeoConfig with blank entity_wikipedia_url."""
    return GeoConfig(
        domain="example.org",
        org_name="Example Org",
        topic_entities=["Therapy", "Counselling"],
        primary_location="Seattle",
        location_pool=["Tacoma"],
        entity_wikipedia_url="",
    )


@pytest.fixture
def minimal_config():
    """Minimal valid config — one entity, no entity URL."""
    return GeoConfig(
        domain="min.org",
        org_name="Min Org",
        topic_entities=["Coaching"],
        primary_location="Portland",
        location_pool=[],
    )


# ── Schema structure tests ──────────────────────────────────────────────


class TestSchemaStructure:
    def test_has_context_and_type(self, full_config):
        """Output has @context = schema.org and @type = Organization."""
        schema = build_entity_schema(full_config)
        assert schema["@context"] == "https://schema.org"
        assert schema["@type"] == "Organization"

    def test_has_org_name(self, full_config):
        """name field matches org_name."""
        schema = build_entity_schema(full_config)
        assert schema["name"] == "Living Systems Counselling"

    def test_has_offer_catalog(self, full_config):
        """Output contains hasOfferCatalog with OfferCatalog type."""
        schema = build_entity_schema(full_config)
        catalog = schema["hasOfferCatalog"]
        assert catalog["@type"] == "OfferCatalog"
        assert catalog["name"] == "Services"

    def test_services_from_topic_entities(self, full_config):
        """One Service per topic_entity with correct areaServed."""
        schema = build_entity_schema(full_config)
        services = schema["hasOfferCatalog"]["itemListElement"]
        assert len(services) == 3
        for svc in services:
            assert svc["@type"] == "Service"
            assert svc["areaServed"] == "Vancouver"
        names = {s["name"] for s in services}
        assert names == {"Bowen Theory", "Systems Thinking", "Grief Counselling"}

    def test_has_faq_page(self, full_config):
        """Output has subjectOf with FAQPage type and mainEntity questions."""
        schema = build_entity_schema(full_config)
        faq = schema["subjectOf"]
        assert faq["@type"] == "FAQPage"
        assert "mainEntity" in faq
        assert len(faq["mainEntity"]) > 0
        for q in faq["mainEntity"]:
            assert q["@type"] == "Question"
            assert "name" in q
            assert q["acceptedAnswer"]["@type"] == "Answer"

    def test_faq_does_not_duplicate_context(self, full_config):
        """The nested FAQPage should not have its own @context."""
        schema = build_entity_schema(full_config)
        assert "@context" not in schema["subjectOf"]


# ── sameAs tests ────────────────────────────────────────────────────────


class TestSameAs:
    def test_same_as_present_when_url_set(self, full_config):
        """sameAs is a list with the Wikipedia URL when set."""
        schema = build_entity_schema(full_config)
        assert "sameAs" in schema
        assert schema["sameAs"] == ["https://en.wikipedia.org/wiki/Living_Systems_Counselling"]

    def test_same_as_absent_when_blank(self, no_entity_url_config):
        """sameAs key must be ABSENT when entity_wikipedia_url is blank."""
        schema = build_entity_schema(no_entity_url_config)
        assert "sameAs" not in schema

    def test_same_as_absent_when_default(self, minimal_config):
        """sameAs absent when field uses its default empty string."""
        schema = build_entity_schema(minimal_config)
        assert "sameAs" not in schema

    def test_same_as_absent_when_whitespace_only(self):
        """Whitespace-only URL should be treated as blank -> no sameAs."""
        config = GeoConfig(
            domain="ws.org",
            org_name="WS Org",
            topic_entities=["Art"],
            primary_location="NYC",
            location_pool=[],
            entity_wikipedia_url="   ",
        )
        schema = build_entity_schema(config)
        assert "sameAs" not in schema

    def test_same_as_strips_whitespace(self):
        """URL with leading/trailing whitespace is stripped."""
        config = GeoConfig(
            domain="strip.org",
            org_name="Strip Org",
            topic_entities=["Music"],
            primary_location="LA",
            location_pool=[],
            entity_wikipedia_url="  https://en.wikipedia.org/wiki/StripOrg  ",
        )
        schema = build_entity_schema(config)
        assert schema["sameAs"] == ["https://en.wikipedia.org/wiki/StripOrg"]


# ── Adversarial: sameAs key must never appear with falsy values ────────


class TestAdversarialSameAs:
    """The key adversarial guarantee: blank entity URL -> sameAs ABSENT.

    Never empty string, never [""], never null.
    """

    def test_blank_url_no_sameas_key(self, no_entity_url_config):
        schema = build_entity_schema(no_entity_url_config)
        # Check the key literally does not exist
        assert "sameAs" not in schema.keys()

    def test_serialized_json_has_no_sameas_token(self, no_entity_url_config):
        """Even in the serialized JSON string, 'sameAs' must not appear."""
        schema = build_entity_schema(no_entity_url_config)
        json_str = json.dumps(schema)
        assert "sameAs" not in json_str


# ── GeoConfig serialization round-trip ──────────────────────────────────


class TestGeoConfigSerialization:
    def test_round_trip_with_entity_url(self):
        """entity_wikipedia_url survives to_dict -> from_dict."""
        config = GeoConfig(
            domain="rt.org",
            org_name="RT Org",
            topic_entities=["CBT"],
            primary_location="NYC",
            location_pool=["Brooklyn"],
            entity_wikipedia_url="https://en.wikipedia.org/wiki/RT_Org",
        )
        d = config.to_dict()
        assert d["entity_wikipedia_url"] == "https://en.wikipedia.org/wiki/RT_Org"
        restored = GeoConfig.from_dict(d)
        assert restored.entity_wikipedia_url == "https://en.wikipedia.org/wiki/RT_Org"

    def test_round_trip_blank_entity_url(self):
        """Blank entity_wikipedia_url round-trips correctly."""
        config = GeoConfig(
            domain="blank.org",
            org_name="Blank Org",
            topic_entities=["DBT"],
            primary_location="LA",
            location_pool=["Pasadena"],
            entity_wikipedia_url="",
        )
        d = config.to_dict()
        assert d["entity_wikipedia_url"] == ""
        restored = GeoConfig.from_dict(d)
        assert restored.entity_wikipedia_url == ""

    def test_old_config_without_entity_url_loads(self):
        """A stored config dict without entity_wikipedia_url still loads (default '')."""
        old_data = {
            "domain": "old.org",
            "org_name": "Old Org",
            "topic_entities": ["Therapy"],
            "primary_location": "Boston",
            "location_pool": ["Cambridge"],
        }
        config = GeoConfig.from_dict(old_data)
        assert config.entity_wikipedia_url == ""
        assert config.domain == "old.org"
        assert config.org_name == "Old Org"

    def test_is_configured_ignores_entity_url(self):
        """entity_wikipedia_url is optional — is_configured() must not require it."""
        config = GeoConfig(
            domain="opt.org",
            org_name="Optional Org",
            topic_entities=["Therapy"],
            primary_location="Denver",
            location_pool=["Boulder"],
            entity_wikipedia_url="",
        )
        assert config.is_configured() is True

    def test_validate_ignores_entity_url(self):
        """entity_wikipedia_url is optional — validate() must not flag it."""
        config = GeoConfig(
            domain="val.org",
            org_name="Valid Org",
            topic_entities=["Therapy"],
            primary_location="Austin",
            location_pool=["Round Rock"],
            entity_wikipedia_url="",
        )
        errors = config.validate()
        assert errors == []


# ── Edge cases ──────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_topic_entities_produces_empty_services(self):
        """No topic entities -> empty services array, still valid JSON."""
        config = GeoConfig(
            domain="noent.org",
            org_name="No Entities",
            topic_entities=[],
            primary_location="Miami",
            location_pool=[],
        )
        schema = build_entity_schema(config)
        assert schema["@type"] == "Organization"
        assert schema["hasOfferCatalog"]["itemListElement"] == []
        # JSON must be valid
        json_str = json.dumps(schema)
        assert json.loads(json_str) == schema

    def test_blank_org_name_uses_empty_string(self):
        """Blank org_name -> name is empty string, still valid."""
        config = GeoConfig(
            domain="noname.org",
            org_name="",
            topic_entities=["Art"],
            primary_location="Denver",
            location_pool=[],
        )
        schema = build_entity_schema(config)
        assert schema["name"] == ""


# ── Endpoint contract tests ─────────────────────────────────────────────


class TestEntitySchemaEndpoint:
    """Contract tests for POST /api/geo/entity-schema.

    Written BEFORE the frontend card per CLAUDE.md.
    """

    @pytest.mark.asyncio
    async def test_200_with_entity_url(self, api_client, test_store, auth_headers):
        """Happy path: configured domain with entity URL -> 200 with schema."""
        config = GeoConfig(
            domain="test.org",
            org_name="Test Org",
            topic_entities=["Family Therapy", "Grief Counselling"],
            primary_location="Vancouver",
            location_pool=["Burnaby", "Richmond"],
            entity_wikipedia_url="https://en.wikipedia.org/wiki/Test_Org",
        )
        await test_store.save_geo_config(config)

        response = await api_client.post(
            "/api/geo/entity-schema",
            json={"domain": "test.org"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response shape
        assert "jsonld" in data
        assert "schema" in data
        assert "valid" in data
        assert "warnings" in data

        assert data["valid"] is True
        assert data["warnings"] == []

        # Verify schema structure
        schema = data["schema"]
        assert schema["@context"] == "https://schema.org"
        assert schema["@type"] == "Organization"
        assert schema["name"] == "Test Org"
        assert schema["sameAs"] == ["https://en.wikipedia.org/wiki/Test_Org"]
        assert "hasOfferCatalog" in schema
        assert "subjectOf" in schema

        # Verify jsonld is valid JSON
        parsed = json.loads(data["jsonld"])
        assert parsed == schema

    @pytest.mark.asyncio
    async def test_200_without_entity_url_has_warning(self, api_client, test_store, auth_headers):
        """Domain without entity URL -> 200 with sameAs absent and warning."""
        config = GeoConfig(
            domain="nowiki.org",
            org_name="No Wiki Org",
            topic_entities=["CBT"],
            primary_location="Portland",
            location_pool=["Salem"],
        )
        await test_store.save_geo_config(config)

        response = await api_client.post(
            "/api/geo/entity-schema",
            json={"domain": "nowiki.org"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["warnings"]) == 1
        assert "sameAs omitted" in data["warnings"][0]

        # sameAs must be absent
        assert "sameAs" not in data["schema"]

    @pytest.mark.asyncio
    async def test_401_without_auth(self, api_client, test_store):
        """Missing auth -> 401."""
        config = GeoConfig(
            domain="auth.org",
            org_name="Auth Org",
            topic_entities=["Therapy"],
            primary_location="Vancouver",
            location_pool=["Burnaby"],
        )
        await test_store.save_geo_config(config)

        response = await api_client.post(
            "/api/geo/entity-schema",
            json={"domain": "auth.org"},
            # No auth headers
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_422_unknown_domain(self, api_client, auth_headers):
        """Unknown domain with no GeoConfig -> 422."""
        response = await api_client.post(
            "/api/geo/entity-schema",
            json={"domain": "nonexistent.org"},
            headers=auth_headers,
        )
        assert response.status_code == 422

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
            "/api/geo/entity-schema",
            json={"domain": "empty.org"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_422_malformed_body(self, api_client, auth_headers):
        """Malformed request body -> 422 (missing required 'domain' field)."""
        response = await api_client.post(
            "/api/geo/entity-schema",
            json={"not_a_field": "value"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_round_trip_save_then_generate(self, api_client, test_store, auth_headers):
        """Save GeoConfig with entity_wikipedia_url via settings, then generate -> URL in sameAs."""
        # Save via POST /api/geo/settings
        save_response = await api_client.post(
            "/api/geo/settings",
            json={
                "domain": "roundtrip.org",
                "org_name": "Roundtrip Org",
                "topic_entities": ["Mindfulness"],
                "primary_location": "Seattle",
                "location_pool": ["Bellevue"],
                "entity_wikipedia_url": "https://en.wikipedia.org/wiki/Roundtrip",
            },
            headers=auth_headers,
        )
        assert save_response.status_code == 200

        # Generate entity schema
        gen_response = await api_client.post(
            "/api/geo/entity-schema",
            json={"domain": "roundtrip.org"},
            headers=auth_headers,
        )
        assert gen_response.status_code == 200
        data = gen_response.json()
        assert data["schema"]["sameAs"] == ["https://en.wikipedia.org/wiki/Roundtrip"]
        assert data["warnings"] == []

    @pytest.mark.asyncio
    async def test_settings_response_includes_entity_url(self, api_client, test_store, auth_headers):
        """GET /api/geo/settings returns entity_wikipedia_url field."""
        config = GeoConfig(
            domain="gettest.org",
            org_name="Get Test Org",
            topic_entities=["Therapy"],
            primary_location="Chicago",
            location_pool=["Evanston"],
            entity_wikipedia_url="https://en.wikipedia.org/wiki/GetTest",
        )
        await test_store.save_geo_config(config)

        response = await api_client.get(
            "/api/geo/settings?domain=gettest.org",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["entity_wikipedia_url"] == "https://en.wikipedia.org/wiki/GetTest"

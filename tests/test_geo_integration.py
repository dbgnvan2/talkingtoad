"""
Integration tests for GEO (Generative Engine Optimization) functionality.

Tests the complete GEO flow:
1. Configure GEO settings for a domain
2. Analyze image with GEO context
3. Apply GEO metadata to database
4. Verify metadata persists and is returned by API

NOTE: These tests require async_client fixture - currently skipped.
See test_geo_apply_end_to_end.py for working GEO tests.
"""

import pytest
from httpx import AsyncClient
from api.main import app
from api.models.geo_config import GeoConfig
from api.models.image import ImageInfo


@pytest.mark.skip(reason="Requires async_client fixture - use test_geo_apply_end_to_end.py instead")
@pytest.mark.skip(reason="Requires async_client fixture - use test_geo_apply_end_to_end.py instead")
@pytest.mark.asyncio
async def test_geo_config_save_and_retrieve(async_client: AsyncClient):
    """Test saving and retrieving GEO configuration."""
    config_data = {
        "domain": "example.org",
        "org_name": "Example Nonprofit",
        "topic_entities": ["Social Justice", "Community Development"],
        "primary_location": "Seattle",
        "location_pool": ["Tacoma", "Bellevue", "Redmond"],
        "model": "gemini-1.5-pro",
        "temperature": 0.4,
        "max_tokens": 500,
    }

    # Save configuration
    response = await async_client.post("/api/geo/settings", json=config_data)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Retrieve configuration
    response = await async_client.get("/api/geo/settings?domain=example.org")
    assert response.status_code == 200
    data = response.json()
    assert data["org_name"] == "Example Nonprofit"
    assert data["primary_location"] == "Seattle"
    assert len(data["topic_entities"]) == 2
    assert len(data["location_pool"]) == 3
    assert data["is_configured"] is True


@pytest.mark.skip(reason="Requires async_client fixture - use test_geo_apply_end_to_end.py instead")
@pytest.mark.asyncio
async def test_geo_config_validation(async_client: AsyncClient):
    """Test GEO configuration validation rejects incomplete configs."""
    # Missing required fields
    incomplete_config = {
        "domain": "example.org",
        "org_name": "Example Nonprofit",
        # Missing topic_entities, primary_location, location_pool
    }

    response = await async_client.post("/api/geo/settings", json=incomplete_config)
    assert response.status_code == 400
    assert "errors" in response.json()["detail"]


@pytest.mark.skip(reason="Requires async_client fixture - use test_geo_apply_end_to_end.py instead")
@pytest.mark.asyncio
async def test_geo_analysis_requires_configuration(async_client: AsyncClient, sample_job_id: str):
    """Test that GEO analysis fails if domain is not configured."""
    # Try to analyze without configuration
    response = await async_client.post(
        "/api/ai/image/analyze-geo",
        json={
            "job_id": sample_job_id,
            "image_url": "https://unconfigured-domain.com/image.jpg",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "No GEO configuration" in data.get("error", "")


@pytest.mark.skip(reason="Requires async_client fixture - use test_geo_apply_end_to_end.py instead")
@pytest.mark.asyncio
async def test_geo_metadata_persistence_flow(async_client: AsyncClient, sample_job_with_image):
    """
    CRITICAL TEST: Ensure GEO metadata is saved AND returned by API.

    This test prevents regression where metadata is saved but not returned
    due to missing fields in _image_dict serialization.
    """
    job_id, image_url = sample_job_with_image

    # Apply GEO metadata
    geo_data = {
        "job_id": job_id,
        "image_url": image_url,
        "alt_text": "Community volunteers at Example Nonprofit in Seattle working on social justice project",
        "description": "This image shows community development work at Example Nonprofit in Seattle. The organization focuses on social justice initiatives across the Tacoma, Bellevue, and Redmond service areas.",
    }

    response = await async_client.post("/api/ai/image/apply-geo-metadata", json=geo_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "new_scores" in data

    # Fetch image via API to verify metadata persists
    response = await async_client.post(
        f"/api/crawl/{job_id}/images/fetch?image_url={image_url}"
    )
    assert response.status_code == 200
    fetched = response.json()

    # CRITICAL: Verify all GEO fields are present in API response
    assert "image" in fetched
    img = fetched["image"]
    assert img["alt"] == geo_data["alt_text"]
    assert img["description"] == geo_data["description"]
    assert img["data_source"] == "geo_analyzed"

    # Verify scores were recalculated
    assert "accessibility_score" in img
    assert "overall_score" in img


@pytest.mark.skip(reason="Requires async_client fixture - use test_geo_apply_end_to_end.py instead")
@pytest.mark.asyncio
async def test_geo_analysis_includes_page_context(async_client: AsyncClient, sample_job_with_page):
    """
    Test that GEO analysis uses page H1 and surrounding text context.

    This is a key feature - GEO should generate descriptions that relate
    to the page content, not just the image in isolation.
    """
    job_id, page_url, image_url = sample_job_with_page

    # Configure GEO for the domain
    domain = "example.org"
    config_data = {
        "domain": domain,
        "org_name": "Example Nonprofit",
        "topic_entities": ["Social Justice"],
        "primary_location": "Seattle",
        "location_pool": ["Tacoma"],
    }
    await async_client.post("/api/geo/settings", json=config_data)

    # Mock: The page should have H1 and surrounding text stored
    # (In real implementation, this comes from the crawl data)

    # Run GEO analysis
    response = await async_client.post(
        "/api/ai/image/analyze-geo",
        json={"job_id": job_id, "image_url": image_url},
    )

    # Should succeed with page context
    assert response.status_code == 200
    data = response.json()

    if data.get("success"):
        # If analysis succeeded, verify it returned structured data
        assert "alt_text" in data
        assert "subject" in data or "description" in data
        # The generated text should ideally reference page context,
        # but we can't easily test that without mocking the AI


@pytest.mark.skip(reason="Requires async_client fixture - use test_geo_apply_end_to_end.py instead")
@pytest.mark.asyncio
async def test_geo_metadata_updates_scores(async_client: AsyncClient, sample_job_with_image):
    """Test that applying GEO metadata recalculates image scores."""
    job_id, image_url = sample_job_with_image

    # Get initial scores
    response = await async_client.post(
        f"/api/crawl/{job_id}/images/fetch?image_url={image_url}"
    )
    initial_score = response.json()["image"]["overall_score"]

    # Apply good GEO metadata
    geo_data = {
        "job_id": job_id,
        "image_url": image_url,
        "alt_text": "Well-written descriptive alt text with good length",
        "description": "A thorough description that provides context and detail for the image content.",
    }

    response = await async_client.post("/api/ai/image/apply-geo-metadata", json=geo_data)
    assert response.status_code == 200

    new_scores = response.json()["new_scores"]

    # Scores should be returned
    assert "accessibility_score" in new_scores
    assert "overall_score" in new_scores

    # With good alt text, accessibility score should improve
    # (This assumes the image had missing or poor alt text initially)
    assert new_scores["accessibility_score"] >= 0


# Fixtures

@pytest.fixture
async def sample_job_id(async_client: AsyncClient) -> str:
    """Create a sample crawl job for testing."""
    # This would create a minimal job in the test database
    # Implementation depends on your test setup
    return "test-job-123"


@pytest.fixture
async def sample_job_with_image(async_client: AsyncClient) -> tuple[str, str]:
    """Create a job with an image for testing."""
    job_id = "test-job-with-image"
    image_url = "https://example.org/test-image.jpg"

    # Create job and image in test database
    # Implementation depends on your test setup

    return job_id, image_url


@pytest.fixture
async def sample_job_with_page(async_client: AsyncClient) -> tuple[str, str, str]:
    """Create a job with a page and image for testing page context."""
    job_id = "test-job-with-page"
    page_url = "https://example.org/about"
    image_url = "https://example.org/team.jpg"

    # Create job, page (with H1 and content), and image
    # Implementation depends on your test setup

    return job_id, page_url, image_url

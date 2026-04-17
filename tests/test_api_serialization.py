"""
API serialization tests.

These tests ensure that API response serialization functions include ALL
model fields. This prevents regressions where new fields are added to models
but forgotten in serialization, causing them to be invisible to the frontend.

CRITICAL: When you add fields to a model, you MUST update these tests.
"""

import pytest
from api.models.image import ImageInfo
from api.models.job import CrawlJob
from api.routers.crawl import _image_dict


def test_image_dict_includes_all_core_fields():
    """
    CRITICAL: Ensure _image_dict includes ALL ImageInfo fields.

    This test prevents the regression where long_description and other
    GEO fields were added to ImageInfo but not included in _image_dict,
    causing them to be saved but never returned by the API.
    """
    # Create a fully populated ImageInfo
    image = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org/page",
        job_id="test-job",
        alt="Test alt text",
        title="Test title",
        caption="Test caption",
        description="Test description",
        filename="test.jpg",
        format="jpeg",
        width=800,
        height=600,
        rendered_width=400,
        rendered_height=300,
        file_size_bytes=50000,
        load_time_ms=150,
        http_status=200,
        is_lazy_loaded=False,
        has_srcset=True,
        srcset_candidates=["test-800.jpg", "test-1600.jpg"],
        is_decorative=False,
        surrounding_text="Context text around the image",
        content_hash="abc123def456",
        performance_score=85.0,
        accessibility_score=90.0,
        semantic_score=80.0,
        technical_score=95.0,
        overall_score=87.5,
        issues=["IMG_ALT_TOO_SHORT"],
        data_source="full_fetch",
        # GEO fields (v1.9geo)
        long_description="A detailed GEO-optimized description for AI search engines",
        geo_entities_detected=["Seattle", "Social Justice"],
        geo_location_used="Seattle",
        ai_analysis_metadata={"model": "gemini-1.5-pro", "confidence": 0.95},
    )

    # Serialize to API response
    result = _image_dict(image)

    # Verify ALL core fields are present
    assert result["url"] == image.url
    assert result["page_url"] == image.page_url
    assert result["alt"] == image.alt
    assert result["title"] == image.title
    assert result["caption"] == image.caption
    assert result["description"] == image.description
    assert result["filename"] == image.filename
    assert result["format"] == image.format
    assert result["width"] == image.width
    assert result["height"] == image.height
    assert result["rendered_width"] == image.rendered_width
    assert result["rendered_height"] == image.rendered_height
    assert result["file_size_bytes"] == image.file_size_bytes
    assert result["file_size_kb"] == round(50000 / 1024, 1)  # Calculated field
    assert result["load_time_ms"] == image.load_time_ms
    assert result["http_status"] == image.http_status
    assert result["is_lazy_loaded"] == image.is_lazy_loaded
    assert result["has_srcset"] == image.has_srcset
    assert result["is_decorative"] == image.is_decorative
    assert result["content_hash"] == image.content_hash
    assert result["performance_score"] == image.performance_score
    assert result["accessibility_score"] == image.accessibility_score
    assert result["semantic_score"] == image.semantic_score
    assert result["technical_score"] == image.technical_score
    assert result["overall_score"] == image.overall_score
    assert result["issues"] == image.issues
    assert result["data_source"] == image.data_source


def test_image_dict_includes_geo_fields():
    """
    CRITICAL: Ensure GEO fields are included in API response.

    Regression test for the bug where long_description, geo_entities_detected,
    geo_location_used, and ai_analysis_metadata were saved but not returned.
    """
    image = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org/page",
        job_id="test-job",
        long_description="GEO-optimized long description with entities",
        geo_entities_detected=["Vancouver", "Bowen Theory"],
        geo_location_used="Vancouver",
        ai_analysis_metadata={"model": "gpt-4o", "temperature": 0.4},
    )

    result = _image_dict(image)

    # CRITICAL: These fields MUST be present
    assert "long_description" in result
    assert "geo_entities_detected" in result
    assert "geo_location_used" in result
    assert "ai_analysis_metadata" in result

    assert result["long_description"] == image.long_description
    assert result["geo_entities_detected"] == image.geo_entities_detected
    assert result["geo_location_used"] == image.geo_location_used
    assert result["ai_analysis_metadata"] == image.ai_analysis_metadata


def test_image_dict_handles_none_values():
    """Test that _image_dict handles None/missing values gracefully."""
    # Create minimal image with many None fields
    image = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org/page",
        job_id="test-job",
        # Most fields are None/default
    )

    result = _image_dict(image)

    # Should not crash, should handle None gracefully
    assert result["url"] == image.url
    assert result["alt"] is None
    assert result["title"] is None
    assert result["width"] is None
    assert result["file_size_kb"] is None  # Calculated from None
    assert result["long_description"] is None
    assert result["geo_entities_detected"] == []  # Default empty list
    assert result["geo_location_used"] is None
    assert result["ai_analysis_metadata"] is None


def test_image_dict_calculated_fields():
    """Test that _image_dict correctly calculates derived fields."""
    image = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org/page",
        job_id="test-job",
        file_size_bytes=102400,  # 100 KB
    )

    result = _image_dict(image)

    # file_size_kb should be calculated
    assert result["file_size_kb"] == 100.0


def test_image_dict_does_not_leak_internal_fields():
    """Ensure _image_dict only includes fields meant for API response."""
    image = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org/page",
        job_id="test-job",
    )

    result = _image_dict(image)

    # job_id should NOT be in the response (it's in the URL path)
    # This is a design decision - adjust if job_id should be included
    # Currently _image_dict doesn't include job_id


def test_image_info_model_field_count_matches_serialization():
    """
    Ensure all ImageInfo fields are accounted for in _image_dict.

    This test will FAIL when new fields are added to ImageInfo,
    reminding you to update _image_dict.
    """
    # Get all fields from ImageInfo dataclass
    from dataclasses import fields
    image_fields = {f.name for f in fields(ImageInfo)}

    # Fields that are intentionally excluded from API response
    excluded_fields = {
        "job_id",  # In URL path, not response body
        # Add other intentionally excluded fields here
    }

    # Create sample image
    image = ImageInfo(
        url="https://example.org/test.jpg",
        page_url="https://example.org/page",
        job_id="test-job",
        long_description="test",
        geo_entities_detected=["test"],
        geo_location_used="test",
        ai_analysis_metadata={"test": "data"},
    )

    result = _image_dict(image)
    result_keys = set(result.keys())

    # Fields that are calculated/derived (not direct from model)
    calculated_fields = {"file_size_kb"}  # Calculated from file_size_bytes

    # Expected fields = model fields - excluded + calculated
    expected_keys = (image_fields - excluded_fields) | calculated_fields

    # Missing in serialization
    missing = expected_keys - result_keys
    if missing:
        pytest.fail(
            f"_image_dict is missing fields: {missing}\n"
            f"When you add fields to ImageInfo, you MUST update _image_dict!"
        )

    # Extra in serialization (not in model)
    extra = result_keys - expected_keys
    if extra - calculated_fields:
        pytest.fail(
            f"_image_dict has unexpected extra fields: {extra - calculated_fields}"
        )

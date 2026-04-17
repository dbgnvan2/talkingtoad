"""
Tests for Image Optimization Module (v1.9.1)

Tests for:
- EXIF GPS injection
- SEO filename generation
- Pre-upload validation
- Image optimization workflow
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from PIL import Image

from api.services.exif_injector import (
    inject_gps_coordinates,
    get_gps_from_location,
    get_gps_from_geo_config,
    validate_has_gps,
    extract_gps_coordinates,
    LOCATION_COORDINATES,
)
from api.services.upload_validator import (
    validate_for_upload,
    estimate_optimized_size,
    ValidationResult,
)
from api.services.image_processor import (
    generate_seo_filename,
    suggest_seo_keyword,
)


# ---------------------------------------------------------------------------
# EXIF GPS Injection Tests
# ---------------------------------------------------------------------------

class TestExifInjector:
    """Tests for EXIF GPS coordinate injection."""

    def test_location_coordinates_has_common_locations(self):
        """Verify common locations are in the coordinate map."""
        assert "Vancouver" in LOCATION_COORDINATES
        assert "North Vancouver" in LOCATION_COORDINATES
        assert "West Vancouver" in LOCATION_COORDINATES

    def test_get_gps_from_location_valid(self):
        """Test getting GPS from a valid location name."""
        coords = get_gps_from_location("Vancouver")
        assert coords is not None
        assert len(coords) == 2
        lat, lon = coords
        assert 49.0 < lat < 50.0  # Vancouver latitude range
        assert -124.0 < lon < -122.0  # Vancouver longitude range

    def test_get_gps_from_location_invalid(self):
        """Test getting GPS from an invalid location returns None."""
        coords = get_gps_from_location("Nonexistent City")
        assert coords is None

    def test_get_gps_from_location_case_insensitive(self):
        """Test location lookup is case-insensitive."""
        coords1 = get_gps_from_location("vancouver")
        coords2 = get_gps_from_location("VANCOUVER")
        coords3 = get_gps_from_location("Vancouver")
        assert coords1 == coords2 == coords3

    def test_get_gps_from_geo_config_with_primary_location(self):
        """Test getting GPS from GeoConfig with primary_location."""
        geo_config = type('GeoConfig', (), {'primary_location': 'Vancouver'})()
        coords = get_gps_from_geo_config(geo_config)
        assert coords is not None
        assert coords == LOCATION_COORDINATES["Vancouver"]

    def test_get_gps_from_geo_config_object_like(self):
        """Test getting GPS from GeoConfig-like object."""
        geo_config = type('GeoConfig', (), {'primary_location': 'North Vancouver'})()
        coords = get_gps_from_geo_config(geo_config)
        assert coords is not None
        assert coords == LOCATION_COORDINATES["North Vancouver"]

    def test_inject_gps_into_jpeg(self):
        """Test injecting GPS into a JPEG image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test JPEG
            img_path = Path(tmpdir) / "test.jpg"
            img = Image.new('RGB', (100, 100), color='red')
            img.save(img_path, 'JPEG')

            # Inject GPS
            result_path = inject_gps_coordinates(img_path, 49.2827, -123.1207)

            assert result_path.exists()
            assert validate_has_gps(result_path)

            # Verify coordinates
            extracted = extract_gps_coordinates(result_path)
            assert extracted is not None
            lat, lon = extracted
            assert abs(lat - 49.2827) < 0.001
            assert abs(lon - (-123.1207)) < 0.001

    def test_inject_gps_into_webp(self):
        """Test injecting GPS into a WebP image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test WebP
            img_path = Path(tmpdir) / "test.webp"
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(img_path, 'WEBP')

            # Inject GPS
            result_path = inject_gps_coordinates(img_path, 49.3165, -123.0688)

            assert result_path.exists()
            assert validate_has_gps(result_path)

    def test_validate_has_gps_without_gps(self):
        """Test validation returns False for image without GPS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "no_gps.jpg"
            img = Image.new('RGB', (100, 100), color='green')
            img.save(img_path, 'JPEG')

            assert not validate_has_gps(img_path)


# ---------------------------------------------------------------------------
# SEO Filename Generation Tests
# ---------------------------------------------------------------------------

class TestSeoFilename:
    """Tests for SEO filename generation."""

    def test_generate_basic_seo_filename(self):
        """Test basic SEO filename generation."""
        result = generate_seo_filename(
            "IMG_1234.jpg",
            keyword="therapy",
            city="Vancouver"
        )
        assert result == "therapy-vancouver-small.webp"

    def test_generate_seo_filename_strips_screenshot(self):
        """Test that Screenshot prefix is stripped."""
        result = generate_seo_filename(
            "Screenshot 2024-01-15 at 10.30.45.png",
            keyword="counselling",
            city="North Vancouver"
        )
        assert "screenshot" not in result.lower()
        assert "counselling" in result
        assert "north-vancouver" in result

    def test_generate_seo_filename_strips_img_prefix(self):
        """Test that IMG_ prefix is stripped."""
        result = generate_seo_filename(
            "IMG_20240115_103045.jpg",
            keyword="family",
            city="Burnaby"
        )
        assert "img" not in result.lower()

    def test_generate_seo_filename_max_length(self):
        """Test filename respects max length for keyword-city part."""
        result = generate_seo_filename(
            "very_long_original_filename.jpg",
            keyword="this-is-a-very-long-keyword-that-should-be-truncated",
            city="North Vancouver",
            max_length=30
        )
        # max_length applies to keyword-city part, then suffix and extension added
        # So result should be: keyword-city (truncated to 30) + "-small" + ".webp"
        base_name = result.replace("-small.webp", "")
        assert len(base_name) <= 30

    def test_generate_seo_filename_slugifies(self):
        """Test special characters are slugified."""
        result = generate_seo_filename(
            "Test File (1).jpg",
            keyword="Mental Health",
            city="West Vancouver"
        )
        assert " " not in result
        assert "(" not in result
        assert result.islower() or "-" in result

    def test_suggest_seo_keyword_from_filename(self):
        """Test keyword suggestion from filename."""
        keyword = suggest_seo_keyword("family-therapy-session.jpg")
        assert keyword  # Should return something
        assert isinstance(keyword, str)

    def test_suggest_seo_keyword_from_alt(self):
        """Test keyword suggestion uses alt text."""
        keyword = suggest_seo_keyword(
            "IMG_1234.jpg",
            alt_text="Family therapy session in progress"
        )
        assert keyword
        assert "img" not in keyword.lower()


# ---------------------------------------------------------------------------
# Upload Validation Tests
# ---------------------------------------------------------------------------

class TestUploadValidator:
    """Tests for pre-upload validation."""

    def test_validate_valid_image(self):
        """Test validation passes for a valid image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create small valid image with GPS
            img_path = Path(tmpdir) / "valid.webp"
            img = Image.new('RGB', (800, 600), color='white')
            img.save(img_path, 'WEBP', quality=50)

            # Inject GPS
            inject_gps_coordinates(img_path, 49.2827, -123.1207)

            result = validate_for_upload(img_path, require_gps=True, max_size_kb=200)

            assert isinstance(result, ValidationResult)
            assert result.is_valid
            assert result.has_gps
            assert result.file_size_kb < 200
            assert result.format.lower() == "webp"

    def test_validate_rejects_large_file(self):
        """Test validation fails for oversized file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create large image
            img_path = Path(tmpdir) / "large.jpg"
            img = Image.new('RGB', (4000, 3000), color='red')
            img.save(img_path, 'JPEG', quality=95)

            result = validate_for_upload(img_path, require_gps=False, max_size_kb=100)

            assert not result.is_valid
            assert any("size" in e.lower() for e in result.errors)

    def test_validate_rejects_missing_gps(self):
        """Test validation fails when GPS required but missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "no_gps.webp"
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(img_path, 'WEBP')

            result = validate_for_upload(img_path, require_gps=True)

            assert not result.is_valid
            assert any("gps" in e.lower() for e in result.errors)

    def test_validate_allows_missing_gps_when_not_required(self):
        """Test validation passes without GPS when not required."""
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "no_gps.webp"
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(img_path, 'WEBP')

            result = validate_for_upload(img_path, require_gps=False, max_size_kb=200)

            assert result.is_valid
            assert not result.has_gps

    def test_estimate_optimized_size(self):
        """Test size estimation for optimization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a larger source image
            img_path = Path(tmpdir) / "source.png"
            img = Image.new('RGB', (2000, 1500), color='green')
            img.save(img_path, 'PNG')

            estimated_kb = estimate_optimized_size(img_path, target_width=1200)

            assert estimated_kb > 0
            assert estimated_kb < 500  # Should be reasonable size


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestImageOptimizationIntegration:
    """Integration tests for the full optimization pipeline."""

    def test_full_optimization_pipeline(self):
        """Test complete optimization: resize, convert, GPS inject, validate."""
        from api.services.image_processor import ImageOptimizer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source image
            src_path = Path(tmpdir) / "source.png"
            img = Image.new('RGB', (2000, 1500), color='purple')
            img.save(src_path, 'PNG')

            # Optimize
            optimizer = ImageOptimizer()
            output_path = optimizer.optimize(
                src_path,
                target_width=1200,
                delete_original=False,
            )

            assert output_path is not None
            assert output_path.exists()
            assert output_path.suffix == ".webp"

            # Check dimensions
            with Image.open(output_path) as optimized:
                assert optimized.width <= 1200
                assert optimized.height <= 900  # Proportional

            # Inject GPS
            inject_gps_coordinates(output_path, 49.2827, -123.1207)
            assert validate_has_gps(output_path)

            # Validate for upload
            result = validate_for_upload(output_path, require_gps=True, max_size_kb=200)
            assert result.is_valid

    def test_optimization_preserves_aspect_ratio(self):
        """Test that optimization preserves aspect ratio."""
        from api.services.image_processor import ImageOptimizer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create wide image (16:9)
            src_path = Path(tmpdir) / "wide.png"
            img = Image.new('RGB', (1920, 1080), color='cyan')
            img.save(src_path, 'PNG')

            optimizer = ImageOptimizer()
            output_path = optimizer.optimize(src_path, target_width=1200)

            assert output_path is not None
            with Image.open(output_path) as optimized:
                ratio = optimized.width / optimized.height
                assert abs(ratio - (16/9)) < 0.01  # Aspect ratio preserved

    def test_optimization_does_not_upscale(self):
        """Test that optimization never upscales images."""
        from api.services.image_processor import ImageOptimizer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create small image
            src_path = Path(tmpdir) / "small.png"
            img = Image.new('RGB', (400, 300), color='yellow')
            img.save(src_path, 'PNG')

            optimizer = ImageOptimizer()
            output_path = optimizer.optimize(src_path, target_width=1200)

            if output_path:  # May return None if no optimization needed
                with Image.open(output_path) as optimized:
                    assert optimized.width <= 400  # Not upscaled

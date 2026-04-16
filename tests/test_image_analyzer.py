"""
Tests for the Image Analysis module (v1.9image).

Tests cover:
- Alt text analysis (missing, short, long, generic, duplicate)
- Performance analysis (oversized, slow, compression, overscaled)
- Format analysis (legacy formats)
- Responsive image checks (srcset)
- Broken image detection
- Duplicate detection
- Scoring engine
"""

import pytest
from api.models.image import ImageInfo
from api.crawler.image_analyzer import (
    analyze_image,
    analyze_batch,
    _check_alt_text,
    _check_performance,
    _check_format,
    _check_responsive,
    _check_broken,
    _check_duplicates,
    _calculate_scores,
    DEFAULT_CONFIG,
)


# ---------------------------------------------------------------------------
# Helper to create test ImageInfo objects
# ---------------------------------------------------------------------------

def make_image(
    url: str = "https://example.com/image.jpg",
    page_url: str = "https://example.com/page",
    alt: str | None = "A descriptive alt text for this image",
    file_size_bytes: int | None = 50_000,
    width: int | None = 800,
    height: int | None = 600,
    rendered_width: int | None = 400,
    rendered_height: int | None = 300,
    load_time_ms: int | None = 200,
    http_status: int = 200,
    format: str = "jpeg",
    has_srcset: bool = True,
    is_decorative: bool = False,
    content_hash: str | None = None,
    filename: str = "",
    **kwargs,
) -> ImageInfo:
    """Create a test ImageInfo with sensible defaults."""
    return ImageInfo(
        url=url,
        page_url=page_url,
        job_id="test-job-123",
        alt=alt,
        filename=filename or url.split("/")[-1],
        file_size_bytes=file_size_bytes,
        width=width,
        height=height,
        rendered_width=rendered_width,
        rendered_height=rendered_height,
        load_time_ms=load_time_ms,
        http_status=http_status,
        format=format,
        has_srcset=has_srcset,
        is_decorative=is_decorative,
        content_hash=content_hash,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Alt Text Analysis Tests
# ---------------------------------------------------------------------------

class TestAltTextAnalysis:
    """Tests for alt text issue detection."""

    def test_missing_alt_flagged(self):
        """IMG_ALT_MISSING should be flagged when alt is None."""
        img = make_image(alt=None)
        issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_ALT_MISSING" in codes

    def test_empty_alt_flagged(self):
        """IMG_ALT_MISSING should be flagged when alt is empty string."""
        img = make_image(alt="")
        issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_ALT_MISSING" in codes

    def test_decorative_with_missing_alt_not_flagged(self):
        """Decorative images without alt should NOT be flagged for missing alt."""
        img = make_image(alt=None, is_decorative=True)
        issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_ALT_MISSING" not in codes

    def test_decorative_with_alt_flagged(self):
        """IMG_ALT_MISUSED should be flagged when decorative image has alt."""
        img = make_image(alt="Some text", is_decorative=True)
        issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_ALT_MISUSED" in codes

    def test_short_alt_flagged(self):
        """IMG_ALT_TOO_SHORT should be flagged when alt is < 5 chars."""
        img = make_image(alt="Hi")
        issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_ALT_TOO_SHORT" in codes

    def test_long_alt_flagged(self):
        """IMG_ALT_TOO_LONG should be flagged when alt is > 125 chars."""
        long_alt = "A" * 150
        img = make_image(alt=long_alt)
        issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_ALT_TOO_LONG" in codes

    def test_generic_alt_flagged(self):
        """IMG_ALT_GENERIC should be flagged for generic terms."""
        for generic in ["image", "photo", "picture", "icon", "logo"]:
            img = make_image(alt=generic)
            issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
            codes = [i.issue_code for i in issues]
            assert "IMG_ALT_GENERIC" in codes, f"'{generic}' should be flagged as generic"

    def test_duplicate_filename_alt_flagged(self):
        """IMG_ALT_DUP_FILENAME should be flagged when alt equals filename."""
        img = make_image(
            url="https://example.com/my-photo.jpg",
            alt="my-photo",
            filename="my-photo.jpg"
        )
        issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_ALT_DUP_FILENAME" in codes

    def test_good_alt_no_issues(self):
        """Valid alt text should not trigger any issues."""
        img = make_image(alt="A golden retriever playing fetch in the park")
        issues = _check_alt_text(img, DEFAULT_CONFIG, "test")
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Performance Analysis Tests
# ---------------------------------------------------------------------------

class TestPerformanceAnalysis:
    """Tests for performance issue detection."""

    def test_oversized_image_flagged(self):
        """IMG_OVERSIZED should be flagged for images > 200KB."""
        img = make_image(file_size_bytes=300_000)  # 300KB
        issues = _check_performance(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_OVERSIZED" in codes

    def test_normal_size_not_flagged(self):
        """Images under 200KB should not be flagged."""
        img = make_image(file_size_bytes=150_000)  # 150KB
        issues = _check_performance(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_OVERSIZED" not in codes

    def test_slow_load_flagged(self):
        """IMG_SLOW_LOAD should be flagged for images > 1000ms."""
        img = make_image(load_time_ms=1500)
        issues = _check_performance(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_SLOW_LOAD" in codes

    def test_fast_load_not_flagged(self):
        """Images loading under 1000ms should not be flagged."""
        img = make_image(load_time_ms=500)
        issues = _check_performance(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_SLOW_LOAD" not in codes

    def test_overscaled_flagged(self):
        """IMG_OVERSCALED should be flagged when intrinsic > 2x rendered."""
        img = make_image(width=2000, rendered_width=400)  # 5x ratio
        issues = _check_performance(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_OVERSCALED" in codes

    def test_not_overscaled(self):
        """Images with reasonable scaling should not be flagged."""
        img = make_image(width=800, rendered_width=600)  # 1.33x ratio
        issues = _check_performance(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_OVERSCALED" not in codes

    def test_poor_compression_flagged(self):
        """IMG_POOR_COMPRESSION should be flagged for high BPP."""
        # 500KB for 400x400 = 3.125 BPP (way over 0.5 threshold)
        img = make_image(file_size_bytes=500_000, width=400, height=400)
        issues = _check_performance(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_POOR_COMPRESSION" in codes

    def test_good_compression_not_flagged(self):
        """Well-compressed images should not be flagged."""
        # 50KB for 800x600 = 0.1 BPP (well under threshold)
        img = make_image(file_size_bytes=50_000, width=800, height=600)
        issues = _check_performance(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_POOR_COMPRESSION" not in codes


# ---------------------------------------------------------------------------
# Format Analysis Tests
# ---------------------------------------------------------------------------

class TestFormatAnalysis:
    """Tests for format issue detection."""

    def test_legacy_format_large_flagged(self):
        """IMG_FORMAT_LEGACY should be flagged for large JPEG/PNG files."""
        img = make_image(format="jpeg", file_size_bytes=100_000)  # 100KB > 50KB threshold
        issues = _check_format(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_FORMAT_LEGACY" in codes

    def test_legacy_format_small_not_flagged(self):
        """Small JPEG/PNG files should not be flagged."""
        img = make_image(format="png", file_size_bytes=30_000)  # 30KB < 50KB threshold
        issues = _check_format(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_FORMAT_LEGACY" not in codes

    def test_modern_format_not_flagged(self):
        """WebP and AVIF should not be flagged."""
        for fmt in ["webp", "avif"]:
            img = make_image(format=fmt, file_size_bytes=200_000)
            issues = _check_format(img, DEFAULT_CONFIG, "test")
            codes = [i.issue_code for i in issues]
            assert "IMG_FORMAT_LEGACY" not in codes


# ---------------------------------------------------------------------------
# Responsive Image Tests
# ---------------------------------------------------------------------------

class TestResponsiveAnalysis:
    """Tests for responsive image issue detection."""

    def test_no_srcset_overscaled_flagged(self):
        """IMG_NO_SRCSET should be flagged when image is scaled down without srcset."""
        img = make_image(has_srcset=False, width=1600, rendered_width=400)
        issues = _check_responsive(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_NO_SRCSET" in codes

    def test_has_srcset_not_flagged(self):
        """Images with srcset should not be flagged."""
        img = make_image(has_srcset=True, width=1600, rendered_width=400)
        issues = _check_responsive(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_NO_SRCSET" not in codes

    def test_no_srcset_not_scaled_not_flagged(self):
        """Images not being scaled down should not be flagged."""
        img = make_image(has_srcset=False, width=400, rendered_width=400)
        issues = _check_responsive(img, DEFAULT_CONFIG, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_NO_SRCSET" not in codes


# ---------------------------------------------------------------------------
# Broken Image Tests
# ---------------------------------------------------------------------------

class TestBrokenAnalysis:
    """Tests for broken image detection."""

    def test_404_flagged(self):
        """IMG_BROKEN should be flagged for 404 responses."""
        img = make_image(http_status=404)
        issues = _check_broken(img, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_BROKEN" in codes

    def test_500_flagged(self):
        """IMG_BROKEN should be flagged for 500 responses."""
        img = make_image(http_status=500)
        issues = _check_broken(img, "test")
        codes = [i.issue_code for i in issues]
        assert "IMG_BROKEN" in codes

    def test_200_not_flagged(self):
        """Successful responses should not be flagged."""
        img = make_image(http_status=200)
        issues = _check_broken(img, "test")
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Duplicate Detection Tests
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    """Tests for duplicate image detection."""

    def test_same_hash_different_urls_flagged(self):
        """Duplicate images with same hash but different URLs should be flagged."""
        images = [
            make_image(url="https://example.com/img1.jpg", content_hash="abc123"),
            make_image(url="https://example.com/img2.jpg", content_hash="abc123"),
            make_image(url="https://example.com/img3.jpg", content_hash="abc123"),
        ]
        issues = _check_duplicates(images, "test")
        codes = [i.issue_code for i in issues]
        assert codes.count("IMG_DUPLICATE_CONTENT") == 2  # First one is original

    def test_same_hash_same_url_not_flagged(self):
        """Same image appearing multiple times (same URL) should not be flagged."""
        images = [
            make_image(url="https://example.com/img1.jpg", content_hash="abc123"),
            make_image(url="https://example.com/img1.jpg", content_hash="abc123"),
        ]
        issues = _check_duplicates(images, "test")
        assert len(issues) == 0

    def test_different_hashes_not_flagged(self):
        """Different images should not be flagged."""
        images = [
            make_image(url="https://example.com/img1.jpg", content_hash="abc123"),
            make_image(url="https://example.com/img2.jpg", content_hash="def456"),
        ]
        issues = _check_duplicates(images, "test")
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Scoring Engine Tests
# ---------------------------------------------------------------------------

class TestScoringEngine:
    """Tests for the scoring calculation."""

    def test_perfect_score(self):
        """Image with no issues should have 100 score."""
        img = make_image()
        issues, scores = analyze_image(img)
        assert scores["overall_score"] == 100.0
        assert scores["performance_score"] == 100
        assert scores["accessibility_score"] == 100
        assert scores["technical_score"] == 100

    def test_missing_alt_reduces_accessibility(self):
        """Missing alt should reduce accessibility score by 50."""
        img = make_image(alt=None)
        issues, scores = analyze_image(img)
        assert scores["accessibility_score"] == 50

    def test_broken_image_reduces_technical(self):
        """Broken image should reduce technical score by 50."""
        img = make_image(http_status=404)
        issues, scores = analyze_image(img)
        assert scores["technical_score"] == 50

    def test_oversized_reduces_performance(self):
        """Oversized image should reduce performance score by 30."""
        img = make_image(file_size_bytes=300_000)
        issues, scores = analyze_image(img)
        assert scores["performance_score"] == 70

    def test_multiple_issues_stack(self):
        """Multiple issues should stack their penalties."""
        # Oversized (-30 perf) + slow (-25 perf)
        img = make_image(file_size_bytes=300_000, load_time_ms=1500)
        issues, scores = analyze_image(img)
        assert scores["performance_score"] == 45  # 100 - 30 - 25

    def test_scores_dont_go_negative(self):
        """Scores should bottom out at 0, not go negative."""
        # Everything wrong: oversized, slow, poor compression, overscaled, legacy, no alt
        img = make_image(
            alt=None,
            file_size_bytes=1_000_000,
            load_time_ms=5000,
            width=100,
            height=100,
            rendered_width=10,
            format="jpeg",
            has_srcset=False,
        )
        issues, scores = analyze_image(img)
        assert scores["performance_score"] >= 0
        assert scores["accessibility_score"] >= 0


# ---------------------------------------------------------------------------
# Batch Analysis Tests
# ---------------------------------------------------------------------------

class TestBatchAnalysis:
    """Tests for batch image analysis."""

    def test_batch_updates_scores(self):
        """analyze_batch should update image scores in place."""
        images = [
            make_image(url="https://example.com/good.jpg"),
            make_image(url="https://example.com/bad.jpg", alt=None, file_size_bytes=500_000),
        ]
        updated, all_issues = analyze_batch(images)

        assert updated[0].overall_score == 100.0
        assert updated[1].overall_score < 100.0

    def test_batch_detects_duplicates(self):
        """analyze_batch should detect duplicates across images."""
        images = [
            make_image(url="https://example.com/a.jpg", content_hash="same123"),
            make_image(url="https://example.com/b.jpg", content_hash="same123"),
        ]
        updated, all_issues = analyze_batch(images)

        codes = [i.issue_code for i in all_issues]
        assert "IMG_DUPLICATE_CONTENT" in codes
        assert "IMG_DUPLICATE_CONTENT" in updated[1].issues

    def test_batch_tracks_issue_codes(self):
        """analyze_batch should populate each image's issues list."""
        img = make_image(alt=None)
        updated, _ = analyze_batch([img])

        assert "IMG_ALT_MISSING" in updated[0].issues


# ---------------------------------------------------------------------------
# Integration: analyze_image Full Flow
# ---------------------------------------------------------------------------

class TestAnalyzeImageIntegration:
    """Integration tests for the full analyze_image flow."""

    def test_analyze_healthy_image(self):
        """Healthy image should have no issues and perfect score."""
        img = make_image(
            alt="A beautiful sunset over the mountains",
            file_size_bytes=80_000,
            width=800,
            height=600,
            rendered_width=800,
            load_time_ms=150,
            format="webp",
            has_srcset=True,
        )
        issues, scores = analyze_image(img)

        assert len(issues) == 0
        assert scores["overall_score"] == 100.0

    def test_analyze_problematic_image(self):
        """Image with multiple problems should have multiple issues."""
        img = make_image(
            alt=None,
            file_size_bytes=500_000,
            load_time_ms=2000,
            http_status=200,
        )
        issues, scores = analyze_image(img)

        codes = [i.issue_code for i in issues]
        assert "IMG_ALT_MISSING" in codes
        assert "IMG_OVERSIZED" in codes
        assert "IMG_SLOW_LOAD" in codes
        assert scores["overall_score"] < 60

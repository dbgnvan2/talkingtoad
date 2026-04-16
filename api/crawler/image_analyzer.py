"""
Image analysis and issue detection module (v1.9image).

Analyzes images for:
- Accessibility (alt text presence and quality)
- Performance (size, compression, load time)
- Technical (format, responsiveness, broken status)

Returns issues and computed scores for each image.
"""

from __future__ import annotations

import re
from typing import Any

from api.models.image import ImageInfo
from api.models.issue import Issue
from api.crawler.issue_checker import make_issue


# ---------------------------------------------------------------------------
# Configuration Defaults
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "max_image_size_kb": 200,
    "slow_load_threshold_ms": 1000,
    "bpp_threshold": 0.5,
    "alt_min_length": 5,
    "alt_max_length": 125,
    "overscale_ratio": 2.0,
    "legacy_format_threshold_kb": 50,
}

# Generic alt text terms that indicate poor quality
GENERIC_ALT_TERMS = {
    "image", "photo", "picture", "pic", "img", "graphic", "icon",
    "logo", "banner", "thumbnail", "placeholder", "untitled",
}


# ---------------------------------------------------------------------------
# Main Analysis Entry Point
# ---------------------------------------------------------------------------


def analyze_image(
    img: ImageInfo,
    config: dict | None = None,
    job_id: str = "",
) -> tuple[list[Issue], dict]:
    """
    Analyze a single image and return issues + scores.

    Args:
        img: The ImageInfo to analyze
        config: Optional configuration overrides
        job_id: The crawl job ID for issue creation

    Returns:
        (list of Issue objects, scores dict)
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    issues = []

    # ALT TEXT ANALYSIS
    issues.extend(_check_alt_text(img, cfg, job_id))

    # SIZE & PERFORMANCE
    issues.extend(_check_performance(img, cfg, job_id))

    # FORMAT ANALYSIS
    issues.extend(_check_format(img, cfg, job_id))

    # RESPONSIVE IMAGES
    issues.extend(_check_responsive(img, cfg, job_id))

    # BROKEN IMAGES
    issues.extend(_check_broken(img, job_id))

    # Calculate scores based on issues found
    scores = _calculate_scores(img, issues, cfg)

    return issues, scores


def analyze_batch(
    images: list[ImageInfo],
    config: dict | None = None,
    job_id: str = "",
) -> tuple[list[ImageInfo], list[Issue]]:
    """
    Analyze a batch of images and update their scores.

    Also checks for duplicates across the batch.

    Returns:
        (updated images list, all issues list)
    """
    all_issues = []

    # Analyze each image individually
    for img in images:
        issues, scores = analyze_image(img, config, job_id)
        all_issues.extend(issues)

        # Update image with scores
        img.performance_score = scores["performance_score"]
        img.accessibility_score = scores["accessibility_score"]
        img.semantic_score = scores["semantic_score"]
        img.technical_score = scores["technical_score"]
        img.overall_score = scores["overall_score"]

        # Track which issues affect this image
        img.issues = [i.code for i in issues]

    # Check for duplicates across all images
    duplicate_issues = _check_duplicates(images, job_id)
    all_issues.extend(duplicate_issues)

    # Update duplicate images with the new issue
    for issue in duplicate_issues:
        if issue.extra and "image_url" in issue.extra:
            for img in images:
                if img.url == issue.extra["image_url"]:
                    img.issues.append("IMG_DUPLICATE_CONTENT")
                    # Recalculate scores
                    _, scores = analyze_image(img, config, job_id)
                    img.technical_score = scores["technical_score"]
                    img.overall_score = scores["overall_score"]

    return images, all_issues


# ---------------------------------------------------------------------------
# ALT Text Analysis
# ---------------------------------------------------------------------------


def _check_alt_text(img: ImageInfo, cfg: dict, job_id: str) -> list[Issue]:
    """Check alt text issues."""
    issues = []
    alt = img.alt

    # IMG_ALT_MISSING - only for non-decorative images
    if not img.is_decorative:
        if alt is None or (isinstance(alt, str) and not alt.strip()):
            issues.append(make_issue(
                "IMG_ALT_MISSING", img.page_url,
                job_id=job_id,
                extra={"image_url": img.url, "filename": img.filename}
            ))
            return issues  # No point checking quality if missing

    # IMG_ALT_MISUSED - decorative image with meaningful alt
    if img.is_decorative and alt and alt.strip():
        issues.append(make_issue(
            "IMG_ALT_MISUSED", img.page_url,
            job_id=job_id,
            extra={
                "image_url": img.url,
                "reason": "decorative_with_alt",
                "alt": alt[:50],
            }
        ))

    if alt:
        alt_clean = alt.strip()

        # IMG_ALT_TOO_SHORT
        if 0 < len(alt_clean) < cfg["alt_min_length"]:
            issues.append(make_issue(
                "IMG_ALT_TOO_SHORT", img.page_url,
                job_id=job_id,
                extra={
                    "image_url": img.url,
                    "alt": alt_clean,
                    "length": len(alt_clean),
                    "min_length": cfg["alt_min_length"],
                }
            ))

        # IMG_ALT_TOO_LONG
        if len(alt_clean) > cfg["alt_max_length"]:
            issues.append(make_issue(
                "IMG_ALT_TOO_LONG", img.page_url,
                job_id=job_id,
                extra={
                    "image_url": img.url,
                    "alt": alt_clean[:50] + "...",
                    "length": len(alt_clean),
                    "max_length": cfg["alt_max_length"],
                }
            ))

        # IMG_ALT_GENERIC - alt is just a generic term
        if alt_clean.lower() in GENERIC_ALT_TERMS:
            issues.append(make_issue(
                "IMG_ALT_GENERIC", img.page_url,
                job_id=job_id,
                extra={
                    "image_url": img.url,
                    "alt": alt_clean,
                }
            ))

        # IMG_ALT_DUP_FILENAME - alt equals filename
        filename_base = img.filename.rsplit(".", 1)[0] if img.filename else ""
        if filename_base and _normalize_for_compare(alt_clean) == _normalize_for_compare(filename_base):
            issues.append(make_issue(
                "IMG_ALT_DUP_FILENAME", img.page_url,
                job_id=job_id,
                extra={
                    "image_url": img.url,
                    "alt": alt_clean,
                    "filename": img.filename,
                }
            ))

    return issues


# ---------------------------------------------------------------------------
# Performance Analysis
# ---------------------------------------------------------------------------


def _check_performance(img: ImageInfo, cfg: dict, job_id: str) -> list[Issue]:
    """Check performance issues."""
    issues = []

    # IMG_OVERSIZED
    if img.file_size_bytes:
        limit_bytes = cfg["max_image_size_kb"] * 1024
        if img.file_size_bytes > limit_bytes:
            issues.append(make_issue(
                "IMG_OVERSIZED", img.page_url,
                job_id=job_id,
                extra={
                    "image_url": img.url,
                    "size_kb": round(img.file_size_bytes / 1024, 1),
                    "limit_kb": cfg["max_image_size_kb"],
                }
            ))

    # IMG_SLOW_LOAD
    if img.load_time_ms and img.load_time_ms > cfg["slow_load_threshold_ms"]:
        issues.append(make_issue(
            "IMG_SLOW_LOAD", img.page_url,
            job_id=job_id,
            extra={
                "image_url": img.url,
                "load_time_ms": img.load_time_ms,
                "threshold_ms": cfg["slow_load_threshold_ms"],
            }
        ))

    # IMG_OVERSCALED
    if img.width and img.rendered_width and img.rendered_width > 0:
        ratio = img.width / img.rendered_width
        if ratio > cfg["overscale_ratio"]:
            issues.append(make_issue(
                "IMG_OVERSCALED", img.page_url,
                job_id=job_id,
                extra={
                    "image_url": img.url,
                    "intrinsic_width": img.width,
                    "rendered_width": img.rendered_width,
                    "ratio": round(ratio, 1),
                }
            ))

    # IMG_POOR_COMPRESSION
    if img.file_size_bytes and img.width and img.height:
        pixels = img.width * img.height
        if pixels > 0:
            bpp = img.file_size_bytes / pixels
            if bpp > cfg["bpp_threshold"]:
                issues.append(make_issue(
                    "IMG_POOR_COMPRESSION", img.page_url,
                    job_id=job_id,
                    extra={
                        "image_url": img.url,
                        "bpp": round(bpp, 2),
                        "threshold": cfg["bpp_threshold"],
                    }
                ))

    return issues


# ---------------------------------------------------------------------------
# Format Analysis
# ---------------------------------------------------------------------------


def _check_format(img: ImageInfo, cfg: dict, job_id: str) -> list[Issue]:
    """Check format issues."""
    issues = []

    legacy_formats = {"jpeg", "jpg", "png", "gif"}
    img_format = img.format.lower() if img.format else ""

    if img_format in legacy_formats:
        threshold_bytes = cfg["legacy_format_threshold_kb"] * 1024
        if img.file_size_bytes and img.file_size_bytes > threshold_bytes:
            issues.append(make_issue(
                "IMG_FORMAT_LEGACY", img.page_url,
                job_id=job_id,
                extra={
                    "image_url": img.url,
                    "format": img.format,
                    "size_kb": round(img.file_size_bytes / 1024, 1),
                }
            ))

    return issues


# ---------------------------------------------------------------------------
# Responsive Image Analysis
# ---------------------------------------------------------------------------


def _check_responsive(img: ImageInfo, cfg: dict, job_id: str) -> list[Issue]:
    """Check responsive image issues."""
    issues = []

    # IMG_NO_SRCSET - only flag if image is being scaled down
    if not img.has_srcset:
        if img.width and img.rendered_width and img.width > img.rendered_width:
            issues.append(make_issue(
                "IMG_NO_SRCSET", img.page_url,
                job_id=job_id,
                extra={
                    "image_url": img.url,
                    "intrinsic_width": img.width,
                    "rendered_width": img.rendered_width,
                }
            ))

    return issues


# ---------------------------------------------------------------------------
# Broken Image Analysis
# ---------------------------------------------------------------------------


def _check_broken(img: ImageInfo, job_id: str) -> list[Issue]:
    """Check for broken images."""
    issues = []

    if img.http_status >= 400:
        issues.append(make_issue(
            "IMG_BROKEN", img.page_url,
            job_id=job_id,
            extra={
                "image_url": img.url,
                "status_code": img.http_status,
            }
        ))

    return issues


# ---------------------------------------------------------------------------
# Duplicate Detection (Batch Level)
# ---------------------------------------------------------------------------


def _check_duplicates(images: list[ImageInfo], job_id: str) -> list[Issue]:
    """Check for duplicate images across the site (same content hash)."""
    issues = []
    hash_to_images: dict[str, list[ImageInfo]] = {}

    for img in images:
        if img.content_hash:
            if img.content_hash not in hash_to_images:
                hash_to_images[img.content_hash] = []
            hash_to_images[img.content_hash].append(img)

    for hash_val, imgs in hash_to_images.items():
        if len(imgs) > 1:
            # Check if URLs are different (same hash but different URLs = true duplicate)
            unique_urls = set(img.url for img in imgs)
            if len(unique_urls) > 1:
                # Skip the first occurrence, flag the rest
                for img in imgs[1:]:
                    issues.append(make_issue(
                        "IMG_DUPLICATE_CONTENT", img.page_url,
                        job_id=job_id,
                        extra={
                            "image_url": img.url,
                            "duplicate_of": imgs[0].url,
                            "total_occurrences": len(imgs),
                        }
                    ))

    return issues


# ---------------------------------------------------------------------------
# Scoring Engine
# ---------------------------------------------------------------------------


def _calculate_scores(img: ImageInfo, issues: list[Issue], cfg: dict) -> dict:
    """Calculate image scores based on issues found.

    Returns dict with:
    - performance_score (0-100, or 0 if insufficient data)
    - accessibility_score (0-100)
    - semantic_score (0-100, or 0 if no AI analysis)
    - technical_score (0-100, or 0 if insufficient data)
    - overall_score (0-100, weighted average of available scores)

    IMPORTANT: Scores default to 0 if we don't have the required data to evaluate.
    """
    issue_codes = {i.code for i in issues}

    # Performance score requires file_size_bytes and load_time_ms
    # If we don't have this data, we can't evaluate performance → score = 0
    has_perf_data = img.file_size_bytes is not None and img.load_time_ms is not None
    if has_perf_data:
        perf = 100
        if "IMG_OVERSIZED" in issue_codes:
            perf -= 30
        if "IMG_SLOW_LOAD" in issue_codes:
            perf -= 25
        if "IMG_POOR_COMPRESSION" in issue_codes:
            perf -= 20
        if "IMG_OVERSCALED" in issue_codes:
            perf -= 15
        if "IMG_FORMAT_LEGACY" in issue_codes:
            perf -= 10
        perf = max(0, perf)
    else:
        perf = 0  # No data = no score

    # Accessibility score - always calculable (based on alt text)
    access = 100
    if "IMG_ALT_MISSING" in issue_codes:
        access -= 50
    if "IMG_ALT_MISUSED" in issue_codes:
        access -= 30
    if "IMG_ALT_TOO_SHORT" in issue_codes:
        access -= 15
    if "IMG_ALT_TOO_LONG" in issue_codes:
        access -= 10
    if "IMG_ALT_GENERIC" in issue_codes:
        access -= 20
    if "IMG_ALT_DUP_FILENAME" in issue_codes:
        access -= 15
    access = max(0, access)

    # Technical score requires at least dimensions (width/height)
    # If we don't have this data, we can't evaluate technical quality → score = 0
    has_tech_data = img.width is not None and img.height is not None
    if has_tech_data:
        tech = 100
        if "IMG_BROKEN" in issue_codes:
            tech -= 50
        if "IMG_NO_SRCSET" in issue_codes:
            tech -= 20
        if "IMG_DUPLICATE_CONTENT" in issue_codes:
            tech -= 15
        tech = max(0, tech)
    else:
        tech = 0  # No data = no score

    # Semantic score - defaults to 100 (placeholder for AI analysis)
    # Will be updated when AI analysis is run
    semantic = 100

    # Overall weighted score - only include scores where we have data
    # Accessibility (30%) - always included
    # Performance (30%) - only if we have file size/load time data
    # Semantic (20%) - always 100 for now (placeholder)
    # Technical (20%) - only if we have dimensions
    weights = [0.30]  # Accessibility always included
    scores = [access]

    if has_perf_data:
        weights.append(0.30)
        scores.append(perf)

    weights.append(0.20)  # Semantic always included (100 by default)
    scores.append(semantic)

    if has_tech_data:
        weights.append(0.20)
        scores.append(tech)

    total_weight = sum(weights)
    overall = sum(w * s for w, s in zip(weights, scores)) / total_weight if total_weight > 0 else 0

    return {
        "performance_score": perf,
        "accessibility_score": access,
        "semantic_score": semantic,
        "technical_score": tech,
        "overall_score": round(overall, 1),
    }


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _normalize_for_compare(s: str) -> str:
    """Normalize string for comparison (remove non-alphanumeric, lowercase)."""
    return re.sub(r'[^a-z0-9]', '', s.lower())

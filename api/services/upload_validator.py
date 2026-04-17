"""
Pre-upload validation for image optimization workflow.

Validates images before WordPress upload to catch issues early:
- File size limits (< 200KB)
- GPS EXIF presence
- Format validation
- Corruption detection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from api.services.exif_injector import validate_has_gps

logger = logging.getLogger(__name__)

# Default validation thresholds
DEFAULT_MAX_SIZE_KB = 200  # Images must be < 200KB after optimization
ALLOWED_FORMATS = {"webp", "jpeg", "jpg", "png"}


@dataclass
class ValidationResult:
    """Result of pre-upload validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file_size_kb: float = 0.0
    has_gps: bool = False
    format: str = ""
    dimensions: tuple[int, int] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "file_size_kb": round(self.file_size_kb, 2),
            "has_gps": self.has_gps,
            "format": self.format,
            "dimensions": self.dimensions,
        }


def validate_for_upload(
    image_path: Path,
    require_gps: bool = True,
    max_size_kb: float = DEFAULT_MAX_SIZE_KB,
    allowed_formats: set[str] | None = None,
) -> ValidationResult:
    """
    Comprehensive pre-upload validation for an optimized image.

    Checks:
    - File exists and is readable
    - File size < max_size_kb (default 200KB)
    - Format is in allowed_formats
    - GPS EXIF present (if require_gps=True)
    - Image can be opened by Pillow (not corrupted)

    Args:
        image_path: Path to the image file
        require_gps: Whether GPS EXIF is required (default True)
        max_size_kb: Maximum allowed file size in KB (default 200)
        allowed_formats: Set of allowed format extensions (default: webp, jpeg, jpg, png)

    Returns:
        ValidationResult with is_valid flag and any errors/warnings
    """
    if allowed_formats is None:
        allowed_formats = ALLOWED_FORMATS

    image_path = Path(image_path)
    errors: list[str] = []
    warnings: list[str] = []

    # Check file exists
    if not image_path.exists():
        return ValidationResult(
            is_valid=False,
            errors=[f"File not found: {image_path}"],
        )

    # Check file size
    file_size_bytes = image_path.stat().st_size
    file_size_kb = file_size_bytes / 1024

    if file_size_kb > max_size_kb:
        errors.append(
            f"File size {file_size_kb:.1f}KB exceeds limit of {max_size_kb}KB"
        )

    # Check format
    suffix = image_path.suffix.lower().lstrip(".")
    if suffix not in allowed_formats:
        errors.append(
            f"Format '{suffix}' not allowed. Allowed: {', '.join(sorted(allowed_formats))}"
        )

    # Try to open image (corruption check)
    dimensions: tuple[int, int] | None = None
    detected_format = suffix
    try:
        with Image.open(image_path) as img:
            img.verify()  # Verify image integrity

        # Re-open to get dimensions (verify() closes the image)
        with Image.open(image_path) as img:
            dimensions = img.size
            detected_format = img.format.lower() if img.format else suffix

    except Exception as e:
        errors.append(f"Image is corrupted or unreadable: {str(e)}")
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            file_size_kb=file_size_kb,
            format=suffix,
        )

    # Check GPS EXIF
    has_gps = validate_has_gps(image_path)
    if require_gps and not has_gps:
        errors.append("GPS EXIF data is required but not present")

    # Warnings for suboptimal but valid conditions
    if file_size_kb > max_size_kb * 0.9:
        warnings.append(
            f"File size {file_size_kb:.1f}KB is close to limit ({max_size_kb}KB)"
        )

    if detected_format != "webp" and detected_format not in ("jpeg", "jpg"):
        warnings.append(
            f"Format '{detected_format}' is not optimal. WebP recommended."
        )

    is_valid = len(errors) == 0

    result = ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        file_size_kb=file_size_kb,
        has_gps=has_gps,
        format=detected_format,
        dimensions=dimensions,
    )

    if is_valid:
        logger.info(f"Validation passed for {image_path}: {file_size_kb:.1f}KB, GPS={has_gps}")
    else:
        logger.warning(f"Validation failed for {image_path}: {errors}")

    return result


def estimate_optimized_size(
    image_path: Path,
    target_width: int = 1200,
    webp_quality: int = 80,
) -> float:
    """
    Estimate the file size after optimization.

    Uses heuristics based on dimensions and format to estimate
    what the optimized size will be without actually optimizing.

    Args:
        image_path: Path to the original image
        target_width: Target width after resize (default 1200)
        webp_quality: WebP quality setting (default 80)

    Returns:
        Estimated size in KB
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return 0.0

    try:
        with Image.open(image_path) as img:
            width, height = img.size

            # Calculate target dimensions
            if width > target_width:
                scale = target_width / width
                target_height = int(height * scale)
            else:
                target_width = width
                target_height = height

            # Estimate WebP size based on pixels and quality
            # Empirical formula: ~0.1-0.3 bytes per pixel at quality 80
            total_pixels = target_width * target_height
            bytes_per_pixel = 0.15 + (100 - webp_quality) * 0.003

            estimated_bytes = total_pixels * bytes_per_pixel
            estimated_kb = estimated_bytes / 1024

            # Apply some safety margin
            return estimated_kb * 1.2

    except Exception as e:
        logger.debug(f"Error estimating size for {image_path}: {e}")
        return 0.0


def validate_batch(
    image_paths: list[Path],
    require_gps: bool = True,
    max_size_kb: float = DEFAULT_MAX_SIZE_KB,
) -> dict[str, ValidationResult]:
    """
    Validate multiple images for batch upload.

    Args:
        image_paths: List of image paths to validate
        require_gps: Whether GPS EXIF is required
        max_size_kb: Maximum allowed file size in KB

    Returns:
        Dictionary mapping path string to ValidationResult
    """
    results: dict[str, ValidationResult] = {}

    for path in image_paths:
        path = Path(path)
        results[str(path)] = validate_for_upload(
            path,
            require_gps=require_gps,
            max_size_kb=max_size_kb,
        )

    valid_count = sum(1 for r in results.values() if r.is_valid)
    logger.info(
        f"Batch validation: {valid_count}/{len(results)} images passed"
    )

    return results

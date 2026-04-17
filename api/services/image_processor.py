"""
Image Intelligence & Optimization Engine (spec §1.7.2).

Handles resizing, compression, and WebP conversion with high-quality LANCZOS resampling.
Includes safety guards for negative compression and upscaling.
"""

import logging
import os
from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Inclusion Criteria
_SIZE_TRIGGER_KB = 150
_DIMENSION_TRIGGER_PX = 1920
_DEFAULT_QUALITY = 80
_WEBP_METHOD = 6  # Highest compression quality method


class ImageOptimizer:
    """Utility for identifying and optimizing web images."""

    def __init__(self, archive_path: str | Path | None = None):
        self.archive_path = Path(archive_path) if archive_path else None
        if self.archive_path:
            (self.archive_path / "originals").mkdir(parents=True, exist_ok=True)
            (self.archive_path / "optimized").mkdir(parents=True, exist_ok=True)

    def should_process(self, file_path: str | Path) -> bool:
        """Return True if the file meets size or dimension triggers."""
        path = Path(file_path)
        if not path.exists():
            return False

        # Size Trigger
        size_kb = path.stat().st_size / 1024
        if size_kb > _SIZE_TRIGGER_KB:
            return True

        # Dimension Trigger (requires opening header)
        try:
            with Image.open(path) as img:
                width, height = img.size
                if width > _DIMENSION_TRIGGER_PX:
                    return True
        except (UnidentifiedImageError, OSError):
            return False

        return False

    def optimize(
        self,
        input_path: str | Path,
        target_width: int | None = None,
        target_height: int | None = None,
        mode: Literal["scale", "crop"] = "scale",
        delete_original: bool = True
    ) -> Path | None:
        """
        Process an image: Resize, Convert to WebP, and Compress.
        Only saves if the result is smaller than the original.
        """
        input_path = Path(input_path)
        if not input_path.exists():
            return None

        # Determine output filename (with -small suffix per spec §4)
        output_name = f"{input_path.stem}-small.webp"
        output_path = input_path.with_name(output_name)
        
        if self.archive_path:
            archive_output = self.archive_path / "optimized" / output_name
        else:
            archive_output = None

        try:
            with Image.open(input_path) as img:
                original_size = input_path.stat().st_size
                curr_w, curr_h = img.size

                # 1. Initialize: Smart RGBA
                if img.mode != "RGBA" and (input_path.suffix.lower() in [".png", ".bmp"] or "transparency" in img.info):
                    img = img.convert("RGBA")
                elif img.mode != "RGB" and img.mode != "RGBA":
                    img = img.convert("RGB")

                # 2. Standardize: Resize or Crop
                if target_width and (target_width < curr_w or (target_height and target_height < curr_h)):
                    if mode == "crop" and target_height:
                        img = ImageOps.fit(img, (target_width, target_height), Image.Resampling.LANCZOS)
                    else:
                        img.thumbnail((target_width, target_height or curr_h), Image.Resampling.LANCZOS)

                # 3. Optimize & Save to temporary file
                tmp_path = input_path.with_suffix(".tmp.webp")
                img.save(tmp_path, "WEBP", quality=_DEFAULT_QUALITY, method=_WEBP_METHOD)

                new_size = tmp_path.stat().st_size

                # 4. Guardrails: Negative Compression
                if new_size >= original_size:
                    logger.info("optimization_skipped_negative_gain", extra={
                        "file": input_path.name,
                        "original": original_size,
                        "new": new_size
                    })
                    tmp_path.unlink()
                    return None

                # 5. Dual-Destination Saving
                if output_path.exists():
                    output_path.unlink()
                tmp_path.rename(output_path)

                if archive_output:
                    import shutil
                    shutil.copy2(output_path, archive_output)

                # 6. Server-Side Cleanup (spec §9)
                if delete_original and output_path.stat().st_size > 0:
                    input_path.unlink()
                    logger.info("original_deleted", extra={"file": input_path.name})

                reduction = 100 - (new_size / original_size * 100)
                logger.info("image_optimized", extra={
                    "file": input_path.name,
                    "reduction_pct": round(reduction, 1),
                    "final_kb": round(new_size / 1024, 1)
                })

                return output_path

        except Exception as exc:
            logger.error("image_optimization_failed", extra={"file": input_path.name, "error": str(exc)})
            if 'tmp_path' in locals() and tmp_path.exists():
                tmp_path.unlink()
            return None

    def bulk_optimize(
        self,
        root_path: str | Path,
        target_width: int | None = None,
        target_height: int | None = None,
        mode: Literal["scale", "crop"] = "scale"
    ) -> list[Path]:
        """
        Recursively identify and optimize all assets meeting inclusion criteria.
        Returns a list of successfully optimized file paths.
        """
        root = Path(root_path)
        optimized_paths = []
        
        # Supported extensions for optimization
        extensions = {".jpg", ".jpeg", ".png", ".bmp"}
        
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                # Skip already optimized files
                if path.stem.endswith("-small"):
                    continue
                    
                if self.should_process(path):
                    result = self.optimize(path, target_width, target_height, mode)
                    if result:
                        optimized_paths.append(result)

        return optimized_paths


# ---------------------------------------------------------------------------
# SEO Filename Generation (v1.9.1 Image Optimization Module)
# ---------------------------------------------------------------------------

import re
import unicodedata


def generate_seo_filename(
    original: str,
    keyword: str,
    city: str,
    suffix: str = "-small",
    extension: str = ".webp",
    max_length: int = 50,
) -> str:
    """
    Generate an SEO-optimized filename for WordPress upload.

    Pattern: {keyword}-{city}{suffix}{extension}
    Example: "therapy-services-vancouver-small.webp"

    Transformations:
    - Strip common non-descriptive prefixes (Screenshot, IMG_, DSC_, etc.)
    - Convert to lowercase
    - Replace spaces/underscores with hyphens
    - Remove special characters except hyphens
    - Normalize Unicode to ASCII
    - Truncate to max_length (before suffix)

    Args:
        original: Original filename (used as fallback if keyword empty)
        keyword: SEO keyword/topic for the image
        city: Geographic location (city name)
        suffix: Filename suffix (default "-small")
        extension: File extension (default ".webp")
        max_length: Maximum length for keyword-city part (default 50)

    Returns:
        SEO-optimized filename string
    """
    # Use keyword if provided, otherwise derive from original
    if keyword and keyword.strip():
        base = keyword.strip()
    else:
        # Clean up original filename as fallback
        base = Path(original).stem if original else "image"
        base = _clean_filename_base(base)

    # Clean city name
    city_clean = _slugify(city) if city else ""

    # Slugify the keyword
    keyword_clean = _slugify(base)

    # Combine keyword and city
    if city_clean:
        combined = f"{keyword_clean}-{city_clean}"
    else:
        combined = keyword_clean

    # Truncate to max length
    if len(combined) > max_length:
        combined = combined[:max_length].rstrip("-")

    # Add suffix and extension
    filename = f"{combined}{suffix}{extension}"

    return filename


def _clean_filename_base(filename: str) -> str:
    """
    Remove common non-descriptive prefixes and patterns from filenames.

    Strips: Screenshot, IMG_, DSC_, date patterns (2024-01-15), etc.
    """
    # Patterns to remove
    patterns_to_strip = [
        r"^screenshot[_\-\s]*",
        r"^img[_\-\s]*\d*[_\-\s]*",
        r"^dsc[_\-\s]*\d*[_\-\s]*",
        r"^photo[_\-\s]*\d*[_\-\s]*",
        r"^image[_\-\s]*\d*[_\-\s]*",
        r"^pic[_\-\s]*\d*[_\-\s]*",
        r"^\d{4}[\-_]\d{2}[\-_]\d{2}[_\-\s]*",  # Date: 2024-01-15
        r"^\d{8}[_\-\s]*",  # Date: 20240115
        r"^screen\s*shot[_\-\s]*",
        r"^capture[_\-\s]*",
        r"^untitled[_\-\s]*",
    ]

    result = filename.lower()
    for pattern in patterns_to_strip:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)

    return result.strip() or "image"


def _slugify(text: str) -> str:
    """
    Convert text to URL-safe slug.

    - Normalize Unicode to ASCII
    - Convert to lowercase
    - Replace spaces/underscores with hyphens
    - Remove non-alphanumeric characters except hyphens
    - Collapse multiple hyphens
    """
    if not text:
        return ""

    # Normalize Unicode (é → e, etc.)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)

    # Remove anything that's not alphanumeric or hyphen
    text = re.sub(r"[^a-z0-9\-]", "", text)

    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)

    # Strip leading/trailing hyphens
    text = text.strip("-")

    return text


def suggest_seo_keyword(original_filename: str, alt_text: str = "") -> str:
    """
    Suggest an SEO keyword based on filename and alt text.

    Prioritizes alt text if available, otherwise cleans up filename.

    Args:
        original_filename: Original image filename
        alt_text: Image alt text (if available)

    Returns:
        Suggested keyword string
    """
    if alt_text and len(alt_text) > 5:
        # Use first few words of alt text
        words = alt_text.split()[:4]
        return " ".join(words)

    # Fall back to cleaned filename
    return _clean_filename_base(Path(original_filename).stem)

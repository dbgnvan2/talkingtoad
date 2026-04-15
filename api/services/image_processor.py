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

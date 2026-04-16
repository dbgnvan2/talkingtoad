"""
ImageInfo data model for the Image Intelligence Engine (v1.9image).

Represents a single image discovered during a crawl, with metadata
for accessibility, performance, and semantic analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ImageInfo:
    """Data model for a crawled image with full analysis metadata."""

    # ── Core identifiers ────────────────────────────────────────────────────
    url: str  # Fully resolved image URL
    page_url: str  # Page where the image was found
    job_id: str  # Parent crawl job

    # ── HTML-level metadata (from parser) ───────────────────────────────────
    alt: str | None = None  # alt attribute (None = missing, "" = empty/decorative)
    title: str | None = None  # title attribute
    caption: str | None = None  # WordPress caption (fetched from WP Media Library)
    description: str | None = None  # WordPress description (fetched from WP Media Library)
    filename: str = ""  # Extracted from URL path
    rendered_width: int | None = None  # from width HTML attribute
    rendered_height: int | None = None  # from height HTML attribute
    is_lazy_loaded: bool = False  # loading="lazy"
    has_srcset: bool = False  # srcset attribute present
    srcset_candidates: list[str] = field(default_factory=list)  # URLs from srcset
    is_decorative: bool = False  # Detected as decorative (role=presentation, aria-hidden, etc.)
    surrounding_text: str = ""  # Text context around the image (±200 chars)

    # ── Fetched metadata (from GET request) ─────────────────────────────────
    format: str = "unknown"  # jpeg, png, webp, avif, svg, gif, unknown
    width: int | None = None  # Intrinsic width (from Pillow)
    height: int | None = None  # Intrinsic height (from Pillow)
    file_size_bytes: int | None = None  # Actual file size
    load_time_ms: int | None = None  # Time to fetch image
    http_status: int = 0  # HTTP response status
    content_hash: str | None = None  # MD5 hash for duplicate detection

    # ── Computed scores (0-100) ─────────────────────────────────────────────
    performance_score: float = 100.0
    accessibility_score: float = 100.0
    semantic_score: float = 100.0
    technical_score: float = 100.0
    overall_score: float = 100.0

    # ── Issue tracking ──────────────────────────────────────────────────────
    issues: list[str] = field(default_factory=list)  # Issue codes flagged for this image

    # ── Analysis metadata ───────────────────────────────────────────────────
    data_source: str = "html_only"  # html_only, crawl_meta, or full_fetch

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageInfo":
        """Reconstruct from dict."""
        # Handle list fields that may be stored as None
        data = data.copy()
        if data.get("srcset_candidates") is None:
            data["srcset_candidates"] = []
        if data.get("issues") is None:
            data["issues"] = []
        return cls(**data)

    @property
    def bpp(self) -> float | None:
        """Calculate Bytes Per Pixel (compression efficiency metric)."""
        if self.file_size_bytes and self.width and self.height:
            pixels = self.width * self.height
            if pixels > 0:
                return self.file_size_bytes / pixels
        return None

    @property
    def is_oversized(self) -> bool:
        """Check if image file size exceeds typical threshold (200KB)."""
        return self.file_size_bytes is not None and self.file_size_bytes > 200 * 1024

    @property
    def is_overscaled(self) -> bool:
        """Check if intrinsic size is >2x rendered size."""
        if self.width and self.rendered_width and self.rendered_width > 0:
            return self.width / self.rendered_width > 2.0
        return False

    @property
    def size_kb(self) -> float | None:
        """File size in KB."""
        if self.file_size_bytes is not None:
            return round(self.file_size_bytes / 1024, 1)
        return None

    @property
    def dimensions(self) -> str:
        """Intrinsic dimensions as WxH string."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "unknown"

    @property
    def rendered_dimensions(self) -> str:
        """Rendered dimensions as WxH string."""
        if self.rendered_width and self.rendered_height:
            return f"{self.rendered_width}x{self.rendered_height}"
        return "unknown"

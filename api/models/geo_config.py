"""
GEO Configuration data model for domain-specific image analysis settings.

Used for Generative Engine Optimization (GEO) of image metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class GeoConfig:
    """GEO settings for a specific domain/organization."""

    # ── Core identifiers ────────────────────────────────────────────────────
    domain: str  # Base domain (e.g., "livingsystems.ca")

    # ── Organization Identity ───────────────────────────────────────────────
    org_name: str = ""  # Organization name (e.g., "Living Systems Counselling")
    topic_entities: list[str] = field(default_factory=list)  # e.g., ["Bowen Theory", "Systems Thinking"]

    # ── Geographic Matrix ───────────────────────────────────────────────────
    primary_location: str = ""  # Primary location (e.g., "Vancouver")
    location_pool: list[str] = field(default_factory=list)  # Secondary locations for distribution

    # ── API Preferences ─────────────────────────────────────────────────────
    model: str = "gemini-1.5-pro"  # AI model for GEO analysis
    temperature: float = 0.4  # Temperature for AI generation
    max_tokens: int = 500  # Max tokens for response

    # ── Report Preferences ──────────────────────────────────────────────────
    client_name: str = ""  # Client/company name for PDF reports
    prepared_by: str = ""  # Consultant/agency name for PDF reports

    # ── Metadata ────────────────────────────────────────────────────────────
    created_at: str = ""  # ISO timestamp
    updated_at: str = ""  # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeoConfig":
        """Reconstruct from dict."""
        data = data.copy()
        # Handle list fields that may be stored as None
        if data.get("topic_entities") is None:
            data["topic_entities"] = []
        if data.get("location_pool") is None:
            data["location_pool"] = []
        return cls(**data)

    def is_configured(self) -> bool:
        """Check if essential fields are configured."""
        return bool(
            self.org_name
            and self.topic_entities
            and self.primary_location
            and self.location_pool
        )

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.org_name or not self.org_name.strip():
            errors.append("Organization name is required")

        if not self.topic_entities or len(self.topic_entities) == 0:
            errors.append("At least one topic entity is required")

        if not self.primary_location or not self.primary_location.strip():
            errors.append("Primary location is required")

        if not self.location_pool or len(self.location_pool) == 0:
            errors.append("At least one location in the pool is required")

        if self.temperature < 0 or self.temperature > 1:
            errors.append("Temperature must be between 0 and 1")

        if self.max_tokens < 100 or self.max_tokens > 4000:
            errors.append("Max tokens must be between 100 and 4000")

        return errors

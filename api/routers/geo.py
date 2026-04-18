"""
Router for GEO (Generative Engine Optimization) configuration management.

Provides endpoints to manage domain-specific settings for GEO-optimized
image metadata generation.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.models.geo_config import GeoConfig
from api.routers.crawl import get_store
from api.services.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/geo", dependencies=[Depends(require_auth)])


# ── Request/Response Models ────────────────────────────────────────────────


class GeoConfigRequest(BaseModel):
    """Request model for saving GEO configuration."""

    domain: str = Field(..., description="Base domain (e.g., 'livingsystems.ca')")
    org_name: str = Field(..., description="Organization name")
    topic_entities: list[str] = Field(..., description="Topic entities for GEO")
    primary_location: str = Field(..., description="Primary location")
    location_pool: list[str] = Field(..., description="Secondary locations for distribution")
    model: str = Field(default="gemini-1.5-pro", description="AI model preference")
    temperature: float = Field(default=0.4, ge=0, le=1, description="Temperature for AI generation")
    max_tokens: int = Field(default=500, ge=100, le=4000, description="Max tokens for response")
    client_name: str = Field(default="", description="Client/company name for PDF reports")
    prepared_by: str = Field(default="", description="Consultant/agency name for PDF reports")


class GeoConfigResponse(BaseModel):
    """Response model for GEO configuration."""

    domain: str
    org_name: str
    topic_entities: list[str]
    primary_location: str
    location_pool: list[str]
    model: str
    temperature: float
    max_tokens: int
    client_name: str
    prepared_by: str
    created_at: str
    updated_at: str
    is_configured: bool


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/settings")
async def get_geo_settings(
    domain: str = Query(..., description="Domain to retrieve settings for"),
    store=Depends(get_store),
) -> GeoConfigResponse:
    """
    Retrieve GEO configuration for a specific domain.

    Returns default configuration if not found.
    """
    config = await store.get_geo_config(domain)

    if config is None:
        # Return default configuration
        now = datetime.now(timezone.utc).isoformat()
        config = GeoConfig(
            domain=domain,
            org_name="",
            topic_entities=[],
            primary_location="",
            location_pool=[],
            model="gemini-1.5-pro",
            temperature=0.4,
            max_tokens=500,
            client_name="",
            prepared_by="",
            created_at=now,
            updated_at=now,
        )

    return GeoConfigResponse(
        domain=config.domain,
        org_name=config.org_name,
        topic_entities=config.topic_entities,
        primary_location=config.primary_location,
        location_pool=config.location_pool,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        client_name=config.client_name,
        prepared_by=config.prepared_by,
        created_at=config.created_at,
        updated_at=config.updated_at,
        is_configured=config.is_configured(),
    )


@router.post("/settings")
async def save_geo_settings(
    request: GeoConfigRequest,
    store=Depends(get_store),
) -> dict[str, Any]:
    """
    Save GEO configuration for a specific domain.

    Validates the configuration before saving.
    """
    # Create GeoConfig from request
    now = datetime.now(timezone.utc).isoformat()
    config = GeoConfig(
        domain=request.domain,
        org_name=request.org_name,
        topic_entities=request.topic_entities,
        primary_location=request.primary_location,
        location_pool=request.location_pool,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        client_name=request.client_name,
        prepared_by=request.prepared_by,
        created_at=now,
        updated_at=now,
    )

    # Validate configuration
    errors = config.validate()
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid GEO configuration", "errors": errors},
        )

    # Save to config table
    await store.save_geo_config(config)

    return {
        "success": True,
        "message": "GEO configuration saved successfully",
        "domain": config.domain,
        "is_configured": config.is_configured(),
    }


@router.delete("/settings")
async def delete_geo_settings(
    domain: str = Query(..., description="Domain to delete settings for"),
    store=Depends(get_store),
) -> dict[str, Any]:
    """
    Delete GEO configuration for a specific domain.
    """
    deleted = await store.delete_geo_config(domain)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"message": f"No GEO configuration found for domain: {domain}"},
        )

    return {
        "success": True,
        "message": "GEO configuration deleted successfully",
        "domain": domain,
    }


@router.get("/test")
async def test_geo_config(
    domain: str = Query(..., description="Domain to test configuration for"),
    store=Depends(get_store),
) -> dict[str, Any]:
    """
    Test GEO configuration for a domain.

    Returns validation status and any errors.
    """
    config = await store.get_geo_config(domain)

    if config is None:
        return {
            "configured": False,
            "domain": domain,
            "message": "No configuration found for this domain",
        }

    errors = config.validate()
    is_valid = len(errors) == 0

    return {
        "configured": True,
        "valid": is_valid,
        "domain": config.domain,
        "org_name": config.org_name,
        "topic_entities_count": len(config.topic_entities),
        "location_pool_count": len(config.location_pool),
        "errors": errors,
        "message": "Configuration is valid" if is_valid else "Configuration has errors",
    }

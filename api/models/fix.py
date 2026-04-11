"""Pydantic models for the v2.0 WordPress Fix Manager."""

from pydantic import BaseModel


class Fix(BaseModel):
    id: str
    job_id: str
    issue_code: str
    page_url: str
    wp_post_id: int | None = None
    wp_post_type: str | None = None   # "page" | "post"
    field: str                         # "seo_title" | "meta_description" | etc.
    label: str                         # human-readable field name
    current_value: str | None = None   # what's there now (from WP)
    proposed_value: str = ""           # what the user wants to set
    status: str = "pending"            # pending | approved | applied | failed | skipped
    error: str | None = None
    applied_at: str | None = None


class FixPatch(BaseModel):
    """Fields the user can update on a fix."""
    proposed_value: str | None = None
    status: str | None = None          # approved | skipped | pending


class GenerateFixesResponse(BaseModel):
    fixes: list[Fix]
    seo_plugin: str | None            # "yoast" | "rank_math" | None
    skipped_urls: list[str]           # URLs where WP post could not be resolved
    message: str


class ApplyFixesResponse(BaseModel):
    applied: int
    failed: int
    skipped: int
    stopped_at: str | None = None     # fix_id that caused a stop
    results: list[dict]               # per-fix outcome

"""
Link Pydantic model (spec §5.3).
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


LinkType = Literal["internal", "external"]


class Link(BaseModel):
    """A hyperlink discovered during a crawl (spec §5.3)."""

    link_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    source_url: str
    target_url: str
    link_text: str | None = None
    link_type: LinkType
    status_code: int | None = None   # null when external cap reached before check
    is_broken: bool = False
    check_skipped: bool = False      # true when external link cap was reached

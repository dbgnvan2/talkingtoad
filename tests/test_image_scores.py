"""AF6 — "not measured" must not be rendered as a score of 0.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF6
Audit: docs/audit/2026-08-30_full-check-audit.md (F6)

The scan is HEAD-only, so intrinsic dimensions are never collected and every
image stored technical_score 0.0 — drawn by the UI as an empty bar. The reader
sees "technically terrible"; the truth is "never looked at" (P31).
"""
from __future__ import annotations

from api.crawler import image_analyzer as IA
from api.models.image import ImageInfo

BASE = "https://example.com/"


def _img(**kw):
    base = dict(url="https://example.com/a.jpg", page_url=BASE, job_id="j",
                filename="a.jpg", alt="A described image", http_status=200)
    base.update(kw)
    return ImageInfo(**base)


def test_af6_technical_score_is_none_without_dimensions():
    assert IA.analyze_image(_img(), job_id="j")[1]["technical_score"] is None


def test_af6_technical_score_is_scored_when_dimensions_exist():
    """Adversarial: the fix must not blank out a score we CAN compute."""
    scores = IA.analyze_image(_img(width=800, height=600, file_size_bytes=50_000), job_id="j")[1]
    assert isinstance(scores["technical_score"], (int, float))
    assert scores["technical_score"] > 0


def test_af6_overall_score_ignores_the_unmeasured_component():
    """The overall score already renormalises — that behaviour must survive."""
    without = IA.analyze_image(_img(), job_id="j")[1]["overall_score"]
    with_dims = IA.analyze_image(_img(width=800, height=600, file_size_bytes=50_000),
                                 job_id="j")[1]["overall_score"]
    assert without == with_dims == 100.0

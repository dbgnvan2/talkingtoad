"""R5.6 — scoring_model_version stamp (external spec §8.4).

Every saved audit is stamped with the scoring-model version from a single
module-level constant, so a stored report records which scoring model produced
it. Old audits saved before this field existed must read back as ``None`` (not
crash) in both the SQLite (dev) and Redis (prod) read paths.

Spec: docs/pending/2026-07-06_scoring-change-remainder.md §R5.6
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.crawler.checkers.registry import SCORING_MODEL_VERSION
from api.models.job import CrawlJob


@pytest.mark.asyncio
async def test_audit_carries_scoring_model_version(store):
    """R5.6.1 — a created+saved+reloaded job carries the constant version.

    The stamp comes from a single source of truth (the module-level constant),
    not a copied literal, so this asserts equality with that constant.
    """
    job_id = str(uuid4())
    await store.create_job(CrawlJob(
        job_id=job_id,
        target_url="https://example.com",
        status="complete",
    ))
    loaded = await store.get_job(job_id)
    assert loaded is not None
    assert loaded.scoring_model_version == SCORING_MODEL_VERSION


@pytest.mark.asyncio
async def test_summary_exposes_scoring_model_version(api_client, auth_headers, test_store):
    """R5.6.1 / API-contract — the results/summary endpoint exposes the version
    stamp so a rendered report can show which scoring model produced it."""
    job_id = str(uuid4())
    await test_store.create_job(CrawlJob(
        job_id=job_id,
        target_url="https://example.com",
        status="complete",
        pages_crawled=1,
    ))

    resp = await api_client.get(f"/api/crawl/{job_id}/results", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert "scoring_model_version" in body, "results payload omitted scoring_model_version"
    assert body["scoring_model_version"] == SCORING_MODEL_VERSION


@pytest.mark.asyncio
async def test_legacy_audit_without_version_reads_none(store):
    """R5.6.1 — an audit stored before the field existed must read back as None,
    never crash. Simulate a legacy record whose stored form lacks the version
    (NULL SQLite column) and assert the read path tolerates it."""
    job_id = str(uuid4())
    await store.create_job(CrawlJob(
        job_id=job_id,
        target_url="https://example.com",
        status="complete",
    ))
    # Simulate the pre-migration state: blank out the stored version so the read
    # path sees a record with no version (the legacy shape).
    await store._db.execute(
        "UPDATE crawl_jobs SET scoring_model_version = NULL WHERE job_id = ?",
        (job_id,),
    )
    await store._db.commit()

    loaded = await store.get_job(job_id)
    assert loaded is not None
    assert loaded.scoring_model_version is None

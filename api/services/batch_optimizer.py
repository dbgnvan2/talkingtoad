"""
Batch Image Optimizer (v1.9.1)

Manages batch optimization jobs with:
- Parallel processing with configurable concurrency
- Pause/resume/cancel controls
- Progress tracking
- Per-image results with page URLs
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result for a single image in a batch."""
    image_url: str
    success: bool
    new_url: str | None = None
    new_media_id: int | None = None
    file_size_kb: float = 0
    page_urls: list[str] = field(default_factory=list)
    error: str | None = None
    geo_metadata: dict | None = None


@dataclass
class BatchJob:
    """Tracks state of a batch optimization job."""
    batch_id: str
    job_id: str
    image_urls: list[str]
    status: str = "pending"  # pending, running, paused, completed, cancelled
    results: list[BatchResult] = field(default_factory=list)
    current_index: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Options
    target_width: int = 1200
    apply_gps: bool = True
    generate_geo_metadata: bool = True
    parallel_limit: int = 3

    @property
    def total(self) -> int:
        return len(self.image_urls)

    @property
    def completed_count(self) -> int:
        return len([r for r in self.results if r.success])

    @property
    def failed_count(self) -> int:
        return len([r for r in self.results if not r.success])

    @property
    def progress_percent(self) -> int:
        if self.total == 0:
            return 100
        return int((len(self.results) / self.total) * 100)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "batch_id": self.batch_id,
            "job_id": self.job_id,
            "status": self.status,
            "total": self.total,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "progress_percent": self.progress_percent,
            "current_index": self.current_index,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "results": [
                {
                    "image_url": r.image_url,
                    "success": r.success,
                    "new_url": r.new_url,
                    "new_media_id": r.new_media_id,
                    "file_size_kb": r.file_size_kb,
                    "page_urls": r.page_urls,
                    "error": r.error,
                    "geo_metadata": r.geo_metadata,
                }
                for r in self.results
            ],
        }


# In-memory batch job store
_BATCH_JOBS: dict[str, BatchJob] = {}
_BATCH_TASKS: dict[str, asyncio.Task] = {}


def create_batch(
    job_id: str,
    image_urls: list[str],
    target_width: int = 1200,
    apply_gps: bool = True,
    generate_geo_metadata: bool = True,
    parallel_limit: int = 3,
) -> BatchJob:
    """Create a new batch job (does not start processing)."""
    batch_id = str(uuid4())[:8]
    batch = BatchJob(
        batch_id=batch_id,
        job_id=job_id,
        image_urls=image_urls,
        target_width=target_width,
        apply_gps=apply_gps,
        generate_geo_metadata=generate_geo_metadata,
        parallel_limit=parallel_limit,
    )
    _BATCH_JOBS[batch_id] = batch
    logger.info("batch_created", extra={"batch_id": batch_id, "total": len(image_urls)})
    return batch


async def start_batch(
    batch_id: str,
    creds_path: Path,
    geo_config: Any,
    store: Any,
) -> BatchJob | None:
    """Start processing a batch job in the background."""
    batch = _BATCH_JOBS.get(batch_id)
    if not batch:
        return None

    if batch.status == "running":
        return batch  # Already running

    batch.status = "running"
    batch.started_at = datetime.now()

    # Start background task with credentials path (not client instance)
    task = asyncio.create_task(
        _process_batch(batch, creds_path, geo_config, store)
    )
    _BATCH_TASKS[batch_id] = task

    logger.info("batch_started", extra={"batch_id": batch_id})
    return batch


async def _process_batch(
    batch: BatchJob,
    creds_path: Path,
    geo_config: Any,
    store: Any,
) -> None:
    """Process all images in the batch with concurrency control."""
    from api.services.wp_fixer import optimize_existing_image
    from api.services.wp_client import WPClient

    semaphore = asyncio.Semaphore(batch.parallel_limit)
    archive_path = Path("archive") / batch.job_id

    # Create WP client that stays open for the batch
    async with WPClient.from_credentials_file(creds_path) as wp_client:

        async def optimize_one(image_url: str, index: int) -> BatchResult:
            """Optimize a single image with semaphore."""
            async with semaphore:
                # Check for pause/cancel before processing
                if batch.status == "paused":
                    # Wait until resumed or cancelled
                    while batch.status == "paused":
                        await asyncio.sleep(0.5)
                    if batch.status == "cancelled":
                        return BatchResult(image_url=image_url, success=False, error="Cancelled")

                if batch.status == "cancelled":
                    return BatchResult(image_url=image_url, success=False, error="Cancelled")

                batch.current_index = index

                # Get image info for page URLs and context
                image_info = await store.get_image_by_url(batch.job_id, image_url)
                page_urls = [image_info.page_url] if image_info else []
                page_h1 = getattr(image_info, 'context', {}).get('h1', '') if image_info else ''
                surrounding_text = getattr(image_info, 'surrounding_text', '') if image_info else ''

                try:
                    result = await optimize_existing_image(
                        wp=wp_client,
                        image_url=image_url,
                        page_urls=page_urls,
                        geo_config=geo_config,
                        target_width=batch.target_width,
                        apply_gps=batch.apply_gps,
                        archive_path=archive_path,
                        generate_geo_metadata=batch.generate_geo_metadata,
                        page_h1=page_h1,
                        surrounding_text=surrounding_text,
                    )

                    return BatchResult(
                        image_url=image_url,
                        success=result.get("success", False),
                        new_url=result.get("new_url"),
                        new_media_id=result.get("new_media_id"),
                        file_size_kb=result.get("file_size_kb", 0),
                        page_urls=result.get("page_urls", []),
                        error=result.get("error"),
                        geo_metadata=result.get("geo_metadata"),
                    )
                except Exception as exc:
                    logger.error("batch_image_error", extra={"url": image_url, "error": str(exc)})
                    return BatchResult(
                        image_url=image_url,
                        success=False,
                        error=str(exc),
                    )

        # Process all images
        tasks = [
            optimize_one(url, i)
            for i, url in enumerate(batch.image_urls)
        ]

        # Gather results as they complete
        for coro in asyncio.as_completed(tasks):
            result = await coro
            batch.results.append(result)

            if batch.status == "cancelled":
                break

    # Mark as completed
    if batch.status != "cancelled":
        batch.status = "completed"
    batch.completed_at = datetime.now()

    logger.info(
        "batch_finished",
        extra={
            "batch_id": batch.batch_id,
            "status": batch.status,
            "completed": batch.completed_count,
            "failed": batch.failed_count,
        }
    )


def pause_batch(batch_id: str) -> bool:
    """Pause a running batch job."""
    batch = _BATCH_JOBS.get(batch_id)
    if not batch or batch.status != "running":
        return False

    batch.status = "paused"
    logger.info("batch_paused", extra={"batch_id": batch_id})
    return True


def resume_batch(batch_id: str) -> bool:
    """Resume a paused batch job."""
    batch = _BATCH_JOBS.get(batch_id)
    if not batch or batch.status != "paused":
        return False

    batch.status = "running"
    logger.info("batch_resumed", extra={"batch_id": batch_id})
    return True


def cancel_batch(batch_id: str) -> bool:
    """Cancel a batch job."""
    batch = _BATCH_JOBS.get(batch_id)
    if not batch or batch.status in ("completed", "cancelled"):
        return False

    batch.status = "cancelled"

    # Cancel the background task if running
    task = _BATCH_TASKS.get(batch_id)
    if task and not task.done():
        task.cancel()

    logger.info("batch_cancelled", extra={"batch_id": batch_id})
    return True


def get_batch(batch_id: str) -> BatchJob | None:
    """Get batch job by ID."""
    return _BATCH_JOBS.get(batch_id)


def get_batch_status(batch_id: str) -> dict | None:
    """Get batch job status as dict."""
    batch = _BATCH_JOBS.get(batch_id)
    if not batch:
        return None
    return batch.to_dict()


def list_batches(job_id: str | None = None) -> list[dict]:
    """List all batch jobs, optionally filtered by job_id."""
    batches = _BATCH_JOBS.values()
    if job_id:
        batches = [b for b in batches if b.job_id == job_id]
    return [b.to_dict() for b in batches]


def cleanup_old_batches(max_age_hours: int = 24) -> int:
    """Remove completed/cancelled batches older than max_age_hours."""
    cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
    to_remove = []

    for batch_id, batch in _BATCH_JOBS.items():
        if batch.status in ("completed", "cancelled"):
            if batch.completed_at and batch.completed_at.timestamp() < cutoff:
                to_remove.append(batch_id)

    for batch_id in to_remove:
        del _BATCH_JOBS[batch_id]
        if batch_id in _BATCH_TASKS:
            del _BATCH_TASKS[batch_id]

    return len(to_remove)

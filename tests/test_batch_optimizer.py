"""
Tests for Batch Optimizer Module (v1.9.1)

Tests for:
- Batch job creation
- Progress tracking
- Pause/resume/cancel controls
- Parallel execution limits
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from api.services.batch_optimizer import (
    create_batch,
    get_batch,
    get_batch_status,
    pause_batch,
    resume_batch,
    cancel_batch,
    list_batches,
    cleanup_old_batches,
    BatchJob,
    BatchResult,
    _BATCH_JOBS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_batch_jobs():
    """Clear batch jobs before and after each test."""
    _BATCH_JOBS.clear()
    yield
    _BATCH_JOBS.clear()


# ---------------------------------------------------------------------------
# Batch Creation Tests
# ---------------------------------------------------------------------------

class TestBatchCreation:
    """Tests for batch job creation."""

    def test_create_batch_returns_batch_job(self):
        """Test creating a batch returns a BatchJob instance."""
        batch = create_batch(
            job_id="test-job-123",
            image_urls=["https://example.com/img1.png", "https://example.com/img2.png"],
        )

        assert isinstance(batch, BatchJob)
        assert batch.job_id == "test-job-123"
        assert len(batch.image_urls) == 2
        assert batch.status == "pending"

    def test_create_batch_generates_unique_id(self):
        """Test each batch gets a unique ID."""
        batch1 = create_batch(job_id="job1", image_urls=["url1"])
        batch2 = create_batch(job_id="job2", image_urls=["url2"])

        assert batch1.batch_id != batch2.batch_id

    def test_create_batch_stores_in_registry(self):
        """Test batch is stored in the registry."""
        batch = create_batch(job_id="job", image_urls=["url"])

        assert batch.batch_id in _BATCH_JOBS
        assert _BATCH_JOBS[batch.batch_id] is batch

    def test_create_batch_with_custom_options(self):
        """Test batch creation with custom options."""
        batch = create_batch(
            job_id="job",
            image_urls=["url1", "url2"],
            target_width=800,
            apply_gps=False,
            generate_geo_metadata=False,
            parallel_limit=5,
        )

        assert batch.target_width == 800
        assert batch.apply_gps is False
        assert batch.generate_geo_metadata is False
        assert batch.parallel_limit == 5


# ---------------------------------------------------------------------------
# Batch Properties Tests
# ---------------------------------------------------------------------------

class TestBatchProperties:
    """Tests for BatchJob properties."""

    def test_total_property(self):
        """Test total count property."""
        batch = create_batch(job_id="job", image_urls=["a", "b", "c"])
        assert batch.total == 3

    def test_completed_count_property(self):
        """Test completed count property."""
        batch = create_batch(job_id="job", image_urls=["a", "b", "c"])
        batch.results = [
            BatchResult(image_url="a", success=True),
            BatchResult(image_url="b", success=True),
            BatchResult(image_url="c", success=False, error="failed"),
        ]

        assert batch.completed_count == 2  # Only successful ones
        assert batch.failed_count == 1

    def test_progress_percent_property(self):
        """Test progress percentage calculation."""
        batch = create_batch(job_id="job", image_urls=["a", "b", "c", "d"])
        batch.results = [
            BatchResult(image_url="a", success=True),
            BatchResult(image_url="b", success=False),
        ]

        assert batch.progress_percent == 50  # 2/4 = 50%

    def test_progress_percent_empty_batch(self):
        """Test progress for empty batch."""
        batch = create_batch(job_id="job", image_urls=[])
        assert batch.progress_percent == 100  # Empty is complete


# ---------------------------------------------------------------------------
# Batch Status Tests
# ---------------------------------------------------------------------------

class TestBatchStatus:
    """Tests for batch status retrieval."""

    def test_get_batch_existing(self):
        """Test getting an existing batch."""
        batch = create_batch(job_id="job", image_urls=["url"])
        retrieved = get_batch(batch.batch_id)

        assert retrieved is batch

    def test_get_batch_nonexistent(self):
        """Test getting a nonexistent batch returns None."""
        result = get_batch("nonexistent-id")
        assert result is None

    def test_get_batch_status_returns_dict(self):
        """Test get_batch_status returns serializable dict."""
        batch = create_batch(job_id="job", image_urls=["url1", "url2"])
        status = get_batch_status(batch.batch_id)

        assert isinstance(status, dict)
        assert status["batch_id"] == batch.batch_id
        assert status["job_id"] == "job"
        assert status["total"] == 2
        assert status["status"] == "pending"
        assert "results" in status

    def test_get_batch_status_nonexistent(self):
        """Test status of nonexistent batch returns None."""
        status = get_batch_status("nonexistent")
        assert status is None


# ---------------------------------------------------------------------------
# Batch Control Tests
# ---------------------------------------------------------------------------

class TestBatchControls:
    """Tests for pause/resume/cancel controls."""

    def test_pause_running_batch(self):
        """Test pausing a running batch."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "running"

        result = pause_batch(batch.batch_id)

        assert result is True
        assert batch.status == "paused"

    def test_pause_nonrunning_batch_fails(self):
        """Test pausing a non-running batch fails."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "pending"

        result = pause_batch(batch.batch_id)

        assert result is False
        assert batch.status == "pending"

    def test_resume_paused_batch(self):
        """Test resuming a paused batch."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "paused"

        result = resume_batch(batch.batch_id)

        assert result is True
        assert batch.status == "running"

    def test_resume_nonpaused_batch_fails(self):
        """Test resuming a non-paused batch fails."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "running"

        result = resume_batch(batch.batch_id)

        assert result is False
        assert batch.status == "running"

    def test_cancel_running_batch(self):
        """Test cancelling a running batch."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "running"

        result = cancel_batch(batch.batch_id)

        assert result is True
        assert batch.status == "cancelled"

    def test_cancel_paused_batch(self):
        """Test cancelling a paused batch."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "paused"

        result = cancel_batch(batch.batch_id)

        assert result is True
        assert batch.status == "cancelled"

    def test_cancel_completed_batch_fails(self):
        """Test cancelling a completed batch fails."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "completed"

        result = cancel_batch(batch.batch_id)

        assert result is False
        assert batch.status == "completed"

    def test_cancel_nonexistent_batch_fails(self):
        """Test cancelling a nonexistent batch fails."""
        result = cancel_batch("nonexistent")
        assert result is False


# ---------------------------------------------------------------------------
# Batch Listing Tests
# ---------------------------------------------------------------------------

class TestBatchListing:
    """Tests for listing batches."""

    def test_list_all_batches(self):
        """Test listing all batches."""
        create_batch(job_id="job1", image_urls=["url1"])
        create_batch(job_id="job2", image_urls=["url2"])
        create_batch(job_id="job1", image_urls=["url3"])

        all_batches = list_batches()

        assert len(all_batches) == 3

    def test_list_batches_filtered_by_job_id(self):
        """Test filtering batches by job_id."""
        create_batch(job_id="job1", image_urls=["url1"])
        create_batch(job_id="job2", image_urls=["url2"])
        create_batch(job_id="job1", image_urls=["url3"])

        job1_batches = list_batches(job_id="job1")

        assert len(job1_batches) == 2
        assert all(b["job_id"] == "job1" for b in job1_batches)

    def test_list_batches_returns_dicts(self):
        """Test list returns serializable dicts."""
        create_batch(job_id="job", image_urls=["url"])
        batches = list_batches()

        assert all(isinstance(b, dict) for b in batches)


# ---------------------------------------------------------------------------
# Cleanup Tests
# ---------------------------------------------------------------------------

class TestBatchCleanup:
    """Tests for batch cleanup."""

    def test_cleanup_removes_old_completed_batches(self):
        """Test cleanup removes old completed batches."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "completed"
        batch.completed_at = datetime(2020, 1, 1)  # Old date

        removed = cleanup_old_batches(max_age_hours=1)

        assert removed == 1
        assert batch.batch_id not in _BATCH_JOBS

    def test_cleanup_keeps_running_batches(self):
        """Test cleanup keeps running batches."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "running"

        removed = cleanup_old_batches(max_age_hours=0)

        assert removed == 0
        assert batch.batch_id in _BATCH_JOBS

    def test_cleanup_keeps_recent_completed_batches(self):
        """Test cleanup keeps recently completed batches."""
        batch = create_batch(job_id="job", image_urls=["url"])
        batch.status = "completed"
        batch.completed_at = datetime.now()

        removed = cleanup_old_batches(max_age_hours=24)

        assert removed == 0
        assert batch.batch_id in _BATCH_JOBS


# ---------------------------------------------------------------------------
# BatchResult Tests
# ---------------------------------------------------------------------------

class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_batch_result_success(self):
        """Test creating a successful result."""
        result = BatchResult(
            image_url="https://example.com/img.png",
            success=True,
            new_url="https://example.com/optimized.webp",
            new_media_id=12345,
            file_size_kb=50.5,
            page_urls=["https://example.com/page"],
        )

        assert result.success
        assert result.new_url == "https://example.com/optimized.webp"
        assert result.error is None

    def test_batch_result_failure(self):
        """Test creating a failed result."""
        result = BatchResult(
            image_url="https://example.com/img.png",
            success=False,
            error="Download failed",
        )

        assert not result.success
        assert result.error == "Download failed"
        assert result.new_url is None


# ---------------------------------------------------------------------------
# Serialization Tests
# ---------------------------------------------------------------------------

class TestBatchSerialization:
    """Tests for batch serialization."""

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all required fields."""
        batch = create_batch(
            job_id="job-123",
            image_urls=["url1", "url2"],
            target_width=1000,
        )
        batch.results.append(BatchResult(
            image_url="url1",
            success=True,
            new_url="new_url1",
            file_size_kb=25.5,
        ))

        data = batch.to_dict()

        assert data["batch_id"] == batch.batch_id
        assert data["job_id"] == "job-123"
        assert data["total"] == 2
        assert data["completed"] == 1
        assert data["failed"] == 0
        assert data["progress_percent"] == 50
        assert len(data["results"]) == 1
        assert data["results"][0]["success"] is True

    def test_to_dict_is_json_serializable(self):
        """Test to_dict output is JSON serializable."""
        import json

        batch = create_batch(job_id="job", image_urls=["url"])
        batch.started_at = datetime.now()

        data = batch.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

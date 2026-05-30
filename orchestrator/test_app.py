import json
import os
import time
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Import the app but we'll mock the state file path
from orchestrator.app import (
    app, STATE_FILE, CYCLES_DIR, get_directory_size, format_size,
    format_uptime, is_spec_file,
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_state(tmp_path):
    """Override state and cycles directory for isolation."""
    test_cycles_dir = tmp_path / "cycles"
    test_cycles_dir.mkdir()
    test_state_file = test_cycles_dir / "state.json"
    
    # Patch the constants in the app module
    with patch("orchestrator.app.STATE_FILE", test_state_file), \
         patch("orchestrator.app.CYCLES_DIR", test_cycles_dir):
        # Initialize state
        test_state_file.write_text(json.dumps({
            "phase": "IDLE",
            "goal": "",
            "spec_path": "",
            "chat_history": [],
            "event_log": []
        }))
        yield test_state_file

def test_get_state():
    response = client.get("/api/state")
    assert response.status_code == 200
    assert response.json()["phase"] == "IDLE"

def test_reset_state():
    # Set to non-idle first
    client.post("/api/chat", json={"message": "Test goal"})
    
    response = client.post("/api/reset")
    assert response.status_code == 200
    
    state_resp = client.get("/api/state")
    assert state_resp.json()["phase"] == "IDLE"
    assert state_resp.json()["goal"] == ""

@pytest.mark.asyncio
async def test_full_cycle_transition():
    """Verify that sending a goal triggers the transition from IDLE to ARCHITECT_SPEC."""
    # Mock call_model
    with patch("orchestrator.app.call_model", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = [
            "# Test Spec", # Architect Drafting
            "[APPROVED] This is good.", # Senior Dev Review
            "[APPROVED] Testable", # QA Spec Review
            "[AGREE] Implement it." # Dev Review
        ]
        
        # Start the cycle
        response = client.post("/api/chat", json={"message": "Build a test app"})
        assert response.status_code == 200
        
        # Give it a moment to run the background task
        await asyncio.sleep(0.5)
        
        # Check if state progressed to IMPLEMENTATION
        state_resp = client.get("/api/state")
        state = state_resp.json()
        assert state["phase"] == "IMPLEMENTATION"
        assert state["goal"] == "Build a test app"
        assert mock_call.call_count == 4

# ── Health & Diagnostics Tests ───────────────────────────────────────────────

class TestGetDirectorySize:
    def test_known_directory(self, tmp_path):
        """Test directory size calculation with known file sizes."""
        d = tmp_path / "sized"
        d.mkdir()
        (d / "a.txt").write_text("hello")  # 5 bytes
        (d / "b.txt").write_text("world!")  # 6 bytes
        total = get_directory_size(str(d))
        assert total == 11

    def test_nested_directories(self, tmp_path):
        """Test recursive size calculation through subdirectories."""
        d = tmp_path / "nested"
        d.mkdir()
        sub = d / "sub"
        sub.mkdir()
        (d / "top.txt").write_text("ab")  # 2 bytes
        (sub / "deep.txt").write_text("cde")  # 3 bytes
        total = get_directory_size(str(d))
        assert total == 5

    def test_empty_directory(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert get_directory_size(str(empty)) == 0


class TestFormatSize:
    def test_bytes(self):
        assert format_size(500) == "500.0 B"

    def test_kilobytes(self):
        assert format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_size(1048576) == "1.0 MB"


class TestHealthEndpoint:
    def test_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_response_schema(self):
        data = client.get("/health").json()
        assert data["status"] == "healthy"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert "uptime_formatted" in data
        assert "cycles_directory_size_bytes" in data
        assert "cycles_directory_size_human" in data
        assert "start_time" in data
        assert "timestamp" in data

    def test_uptime_is_positive(self):
        data = client.get("/health").json()
        assert data["uptime_seconds"] >= 0
        assert data["cycles_directory_size_bytes"] >= 0

    def test_uptime_increases(self):
        response1 = client.get("/health")
        time.sleep(0.1)
        response2 = client.get("/health")
        assert response2.json()["uptime_seconds"] > response1.json()["uptime_seconds"]


class TestDiagnosticsEndpoint:
    def test_returns_200(self):
        response = client.get("/api/diagnostics")
        assert response.status_code == 200

    def test_response_schema(self):
        data = client.get("/api/diagnostics").json()
        assert "total_spec_files" in data
        assert "spec_files" in data
        assert isinstance(data["spec_files"], list)
        assert "total_size_bytes" in data
        assert "total_size_human" in data
        assert "timestamp" in data

    def test_spec_file_metadata(self):
        """Verify each spec file has all required metadata fields."""
        data = client.get("/api/diagnostics").json()
        for spec in data["spec_files"]:
            assert "path" in spec
            assert "filename" in spec
            assert "extension" in spec
            assert "size_bytes" in spec
            assert "size_human" in spec
            assert "last_modified" in spec
            assert "created" in spec
            assert "directory" in spec
            assert "is_spec" in spec

    def test_metadata_values(self):
        """Verify metadata values are valid types and formats."""
        data = client.get("/api/diagnostics").json()
        for spec in data["spec_files"]:
            assert spec["size_bytes"] >= 0
            assert "T" in spec["last_modified"]
            assert "T" in spec["created"]
            assert isinstance(spec["is_spec"], bool)

    def test_empty_directory(self, tmp_path):
        """Test diagnostics with empty directory (no spec files found)."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch("orchestrator.app.PROJECT_ROOT", str(tmp_path)):
                response = client.get("/api/diagnostics")
                assert response.status_code == 200
                data = response.json()
                assert data["total_spec_files"] == 0
                assert data["spec_files"] == []
                assert data["total_size_bytes"] == 0
        finally:
            os.chdir(original_cwd)

    def test_sorted_by_path(self):
        """Test that spec files are sorted by path."""
        data = client.get("/api/diagnostics").json()
        if len(data["spec_files"]) > 1:
            paths = [f["path"] for f in data["spec_files"]]
            assert paths == sorted(paths)


class TestFormatUptime:
    def test_seconds_only(self):
        assert format_uptime(30) == "30s"

    def test_minutes_and_seconds(self):
        result = format_uptime(120)
        assert "2m" in result
        assert "0s" in result

    def test_hours(self):
        result = format_uptime(3600)
        assert "1h" in result

    def test_days(self):
        result = format_uptime(86400)
        assert "1d" in result

    def test_combined(self):
        formatted = format_uptime(90061)  # 1d 1h 1m 1s
        assert "1d" in formatted
        assert "1h" in formatted
        assert "1m" in formatted
        assert "1s" in formatted


class TestIsSpecFile:
    def test_positive_cases(self):
        assert is_spec_file(Path("spec_file.md"))
        assert is_spec_file(Path("specification.txt"))
        assert is_spec_file(Path("requirements.md"))
        assert is_spec_file(Path("design_doc.md"))
        assert is_spec_file(Path("architecture.md"))
        assert is_spec_file(Path("api_spec.yaml"))

    def test_negative_cases(self):
        assert not is_spec_file(Path("readme.md"))
        assert not is_spec_file(Path("main.py"))
        assert not is_spec_file(Path("config.json"))
        assert not is_spec_file(Path("index.html"))

"""The PDF's help copy is generated from the authored JSON and must not drift.

Spec:  docs/pending/2026-09-02_phase2-education-layer.md#E2.1
Tests: this file
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_issue_help_data_py_is_in_sync_with_the_json():
    r = subprocess.run([sys.executable, "scripts/generate_issue_help_py.py", "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout


def test_generated_module_has_every_code():
    import json
    from api.crawler.checkers.registry import _CATALOGUE
    from api.services.issue_help_data import ISSUE_HELP
    data = json.loads((ROOT / "frontend/src/data/issueHelp.json").read_text())
    assert set(ISSUE_HELP) == set(data) == set(_CATALOGUE)

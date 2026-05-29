---
status: pending
proposed: 2026-05-28
author: QA Auditor
source: Formal Adversarial Review (Cycle 4)
---

# Adversarial Hardening: Headings Domain

## Why
A forensic QA audit of `api/crawler/checkers/headings.py` revealed two execution crashes caused by unsafe dictionary access on parsed HTML heading objects. Malformed HTML or unexpected parser output will instantly crash the crawl job for the affected domain.

## Vulnerabilities

### V1 — NoneType Strip Crash (HEADING_EMPTY)
* **Code:** `[h for h in outline if not h.get("text", "").strip()]`
* **Flaw:** If the `"text"` key is present but its value is `None`, `.get()` returns `None`. `None.strip()` throws an `AttributeError`.

### V2 — KeyError Crash (Diagnostic Data)
* **Code:** List comprehensions formatting the outline use strict bracket notation, e.g., `[f"H{h['level']}: {h['text']}" for h in outline[:5]]`.
* **Flaw:** If the parser omits the `"text"` key for a malformed tag, `h['text']` throws a `KeyError: 'text'`, crashing the crawl during issue emission.

## Proposed Fixes

### F1 — Safely Coerce `None` before `.strip()`
`api/crawler/checkers/headings.py`
```python
# BEFORE
empty_headings = [h for h in outline if not h.get("text", "").strip()]

# AFTER
empty_headings = [h for h in outline if not (h.get("text") or "").strip()]
```

### F2 — Safely Extract Diagnostic Text
`api/crawler/checkers/headings.py` — update the comprehensions in both the `H1_MISSING` block and the `HEADING_SKIP` block to use `.get("text")` with a fallback.

```python
# BEFORE (H1_MISSING block)
top_headings = [f"H{h['level']}: {h['text']}" for h in outline[:5]]

# AFTER (H1_MISSING block)
top_headings = [f"H{h['level']}: {h.get('text') or ''}" for h in outline[:5]]


# BEFORE (HEADING_SKIP block)
"outline": [f"H{h['level']}: {h['text']}" for h in outline],

# AFTER (HEADING_SKIP block)
"outline": [f"H{h['level']}: {h.get('text') or ''}" for h in outline],
```

## Tests (Adversarial)
Inject these into the appropriate test file (e.g., `tests/test_headings.py` or the merged equivalent).

```python
# ---------------------------------------------------------------------------
# Adversarial Boundaries: Heading Checks
# ---------------------------------------------------------------------------
import pytest
from api.crawler.checkers.headings import _check_headings

class TestHeadingsAdversarial:
    def test_empty_headings_none_value_does_not_crash(self):
        """Vulnerability: h.get('text', '') returns None if value is None. None.strip() raises AttributeError."""
        page = _page(headings_outline=[{"level": 2, "text": None}])
        issues = []
        # This will raise AttributeError if not patched
        _check_headings(page, issues)
        codes = [i.code for i in issues]
        assert "HEADING_EMPTY" in codes

    def test_missing_text_key_does_not_cause_keyerror(self):
        """Vulnerability: strict h['text'] bracket access in diagnostic formatters throws KeyError."""
        page = _page(
            h1_tags=[],  # Triggers H1_MISSING
            headings_outline=[
                {"level": 1},  # Missing 'text' key
                {"level": 3, "text": "Skip"}  # Skips from H1 to H3 to trigger HEADING_SKIP
            ]
        )
        issues = []
        # This will raise KeyError: 'text' if not patched
        _check_headings(page, issues)
        assert isinstance(issues, list)
```

## Acceptance Criteria

1. The 2 adversarial tests must be added to the test suite and fail on `main`.
2. The logic in `headings.py` must be patched.
3. The test suite must pass with 0 regressions.

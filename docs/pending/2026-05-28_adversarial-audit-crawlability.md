---
status: pending
proposed: 2026-05-28
author: QA Auditor
source: Formal Adversarial Review (Cycle 2)
---

# Adversarial Hardening: Crawlability Domain

## Why
A forensic QA audit of `api/crawler/checkers/crawlability.py` revealed two logic vulnerabilities. One causes an execution crash on malformed data, and the other creates a silent, high-impact false positive that misdirects users trying to fix indexing issues.

## Vulnerabilities

### V1 — NoneType Comparison Crash
* **Code:** `long_para = getattr(page, "long_paragraph_count", 0)` followed by `if long_para > 0:`
* **Flaw:** If the attribute exists but is explicitly `None`, `getattr` returns `None`. `None > 0` throws a `TypeError`, crashing the crawl.

### V2 — Case-Sensitive String Evasion (Misdirection)
* **Code:** `if page.robots_source == "header":`
* **Flaw:** Strict case-sensitive matching means values like `"HEADER"` or `"Header"` fall through to the `else` block, incorrectly emitting `NOINDEX_META` instead of `NOINDEX_HEADER`. This sends users looking for HTML tags when the issue is in their server config.

## Proposed Fixes

### F1 — Safely Coerce `None` to `0`
```python
# BEFORE
long_para = getattr(page, "long_paragraph_count", 0)
if long_para > 0:

# AFTER
long_para = getattr(page, "long_paragraph_count", 0) or 0
if long_para > 0:
```

### F2 — Case-Insensitive Matching
```python
# BEFORE
if page.robots_source == "header":

# AFTER
if page.robots_source and str(page.robots_source).strip().lower() == "header":
```

## Tests (Adversarial)
Inject these into the appropriate test file (e.g., `tests/test_crawlability.py` or the merged equivalent).

```python
# ---------------------------------------------------------------------------
# Adversarial Boundaries: Crawlability Checks
# ---------------------------------------------------------------------------
import pytest
from api.crawler.checkers.crawlability import _check_crawlability

class TestCrawlabilityAdversarial:
    def test_long_paragraph_count_none_does_not_crash(self):
        """Vulnerability: getattr returns None if key exists with None value. None > 0 throws TypeError."""
        page = _page()
        page.long_paragraph_count = None  # Explicitly None
        issues = []
        # This will raise TypeError: '>' not supported between instances of 'NoneType' and 'int'
        _check_crawlability(page, issues)
        assert isinstance(issues, list)

    def test_robots_source_case_insensitivity(self):
        """Vulnerability: 'HEADER' falls through to NOINDEX_META due to strict == 'header' check."""
        page = _page(is_indexable=False)
        page.robots_source = "HEADER"  # Uppercase
        page.robots_directive = "noindex"
        issues = []
        _check_crawlability(page, issues)
        codes = [i.code for i in issues]

        # Should be NOINDEX_HEADER. Pre-fix, this falsely emits NOINDEX_META.
        assert "NOINDEX_HEADER" in codes
        assert "NOINDEX_META" not in codes
```

## Acceptance Criteria

1. The 2 adversarial tests must be added to the test suite and fail on `main`.
2. The logic in `crawlability.py` must be patched.
3. The test suite must pass with 0 regressions.

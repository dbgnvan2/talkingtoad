---
status: pending
proposed: 2026-05-28
author: QA Auditor
source: Formal Adversarial Review (Cycle Q)
---

# Adversarial Hardening: Images & Metadata Domains

## Why
A combined forensic QA audit of `api/crawler/checkers/images.py` and `api/crawler/checkers/metadata.py` revealed vulnerabilities related to upstream data leakage. Missing HTTP headers cause a `NoneType` execution crash, while empty strings and whitespace in canonical tags cause severe misclassification of SEO issues.

## Vulnerabilities

### V1 — NoneType Crash (Images)
* **Code:** `ct = result.content_type` followed by `"pdf" in ct`
* **Flaw:** If the server omits the Content-Type header, `ct` is `None`. `"pdf" in None` raises a `TypeError`, crashing the asset checker.

### V2 — Empty String Misdirection (Metadata)
* **Code:** `if page.canonical_url is not None:`
* **Flaw:** An empty tag (`href=""`) yields `""`. It passes the `is not None` check, fails `is_same_domain`, and is falsely reported as `CANONICAL_EXTERNAL` instead of falling through to the missing/query-string logic.

### V3 — Whitespace Evasion (Metadata)
* **Code:** `is_same_domain(page.canonical_url, url)`
* **Flaw:** Leading or trailing whitespace in the canonical URL string causes `is_same_domain` to fail, falsely flagging a self-referencing canonical as an external canonical error.

## Proposed Fixes

### F1 — Safely Coerce Content-Type (Images)
`api/crawler/checkers/images.py`
```python
# BEFORE
ct = result.content_type

# AFTER
ct = result.content_type or ""
```

### F2 & F3 — Normalise Canonical URL (Metadata)

`api/crawler/checkers/metadata.py`

```python
# BEFORE
if page.canonical_url is not None:
    if not is_same_domain(page.canonical_url, url):
        issue = make_issue("CANONICAL_EXTERNAL", url)
        issue.extra = {"canonical_url": page.canonical_url}
        issues.append(issue)

# AFTER
clean_canonical = (page.canonical_url or "").strip()
if clean_canonical:
    if not is_same_domain(clean_canonical, url):
        issue = make_issue("CANONICAL_EXTERNAL", url)
        issue.extra = {"canonical_url": clean_canonical}
        issues.append(issue)
```

## Tests (Adversarial)

Inject these tests into the appropriate test files.

```python
# ---------------------------------------------------------------------------
# Adversarial Boundaries: Images
# ---------------------------------------------------------------------------
from api.crawler.checkers.images import check_asset
from api.crawler.fetcher import FetchResult

class TestImagesAdversarial:
    def test_missing_content_type_does_not_crash(self):
        """Vulnerability: 'pdf' in None raises TypeError if content_type is None."""
        result = FetchResult(
            url="https://example.com/asset",
            final_url="https://example.com/asset",
            status_code=200,
            content_type=None,  # Missing header
            headers={"content-length": "500000"}
        )
        # Will raise TypeError if not patched
        issues = check_asset(result)
        assert isinstance(issues, list)

# ---------------------------------------------------------------------------
# Adversarial Boundaries: Metadata
# ---------------------------------------------------------------------------
from api.crawler.checkers.metadata import _check_canonical

class TestMetadataAdversarial:
    def test_empty_string_canonical_not_flagged_as_external(self):
        """Vulnerability: href="" parses as empty string, misclassified as CANONICAL_EXTERNAL."""
        page = _page(url="https://example.com/page?query=1", canonical_url="")
        issues = []
        _check_canonical(page, issues)
        codes = [i.code for i in issues]
        assert "CANONICAL_EXTERNAL" not in codes
        assert "CANONICAL_MISSING" in codes

    def test_whitespace_padded_canonical_not_flagged_as_external(self):
        """Vulnerability: '  https://example.com  ' fails is_same_domain parsing."""
        page = _page(
            url="https://example.com/page",
            canonical_url="  https://example.com/page  "
        )
        issues = []
        _check_canonical(page, issues)
        codes = [i.code for i in issues]
        assert "CANONICAL_EXTERNAL" not in codes
```

## Acceptance Criteria

1. The 3 adversarial tests must be added to the test suite and fail on `main`.
2. The logic in `images.py` and `metadata.py` must be patched.
3. The test suite must pass with 0 regressions.

---
status: pending
proposed: 2026-05-28
author: QA Auditor
source: Formal Adversarial Review (Cycle R)
---

# Adversarial Hardening: Links, Security, & URL Structure Domains

## Why
A combined forensic QA audit revealed three logic evasions across the link routing, URL hygiene, and security domains. These flaws cause the crawler to falsely forgive multi-hop redirect chains, ignore literal spaces in URLs, and misclassify unencrypted HTTP pages due to case-sensitivity.

## Vulnerabilities

### V1 — Multi-Hop Evasion (Redirect Chains)
* **Code:** `if final_url and first_status == 301 and len(redirect_chain) <= 1:`
* **Flaw:** A `redirect_chain` length of `1` indicates an intermediate hop (a 2-hop chain). Allowing `<= 1` permits true redirect chains to masquerade as harmless trailing-slash or casing normalizations, suppressing the `REDIRECT_CHAIN` warning.

### V2 — Literal Space Evasion (URL Structure)
* **Code:** `if "%20" in urlparse(url).path:`
* **Flaw:** Fails to catch literal, unencoded spaces (`" "`) in the URL path, allowing malformed URLs to evade the `URL_HAS_SPACES` warning.

### V3 — Case-Sensitive Scheme Evasion (Security)
* **Code:** `if url.startswith("http://"):`
* **Flaw:** Fails to catch `HTTP://` or `Http://`. The URL bypasses the critical `HTTP_PAGE` check and falls into HTTPS-only checks.

## Proposed Fixes

### F1 — Strictly Require Zero Intermediate Hops
`api/crawler/checkers/links.py`
```python
# BEFORE
if final_url and first_status == 301 and len(redirect_chain) <= 1:

# AFTER
if final_url and first_status == 301 and len(redirect_chain) == 0:
```

### F2 — Catch Encoded and Literal Spaces
`api/crawler/checkers/url_structure.py`
```python
# BEFORE
if "%20" in urlparse(url).path:

# AFTER
if "%20" in path or " " in path:
```

### F3 — Case-Insensitive Scheme Check
`api/crawler/checkers/security.py`
```python
# BEFORE
if url.startswith("http://"):

# AFTER
if url.lower().startswith("http://"):
```

## Tests (Adversarial)
Inject these tests into the appropriate test file.

```python
# ---------------------------------------------------------------------------
# Adversarial Boundaries: Links
# ---------------------------------------------------------------------------
from api.crawler.checkers.links import issues_for_redirect

class TestLinksAdversarial:
    def test_two_hop_trailing_slash_redirect_emits_chain(self):
        """Vulnerability: len(redirect_chain) <= 1 allows a 2-hop chain to hide as a trailing slash fix."""
        issues = issues_for_redirect(
            url="https://example.com/a",
            first_status=301,
            redirect_chain=["https://example.com/b"],  # 1 intermediate hop
            final_url="https://example.com/a/"
        )
        codes = [i.code for i in issues]
        assert "REDIRECT_CHAIN" in codes
        assert "REDIRECT_TRAILING_SLASH" not in codes

# ---------------------------------------------------------------------------
# Adversarial Boundaries: URL Structure
# ---------------------------------------------------------------------------
from api.crawler.checkers.url_structure import check_url_structure

class TestUrlStructureAdversarial:
    def test_literal_space_in_url_emits_has_spaces(self):
        """Vulnerability: strict '%20' check ignores literal ' ' characters."""
        issues = check_url_structure("https://example.com/about us")
        codes = [i.code for i in issues]
        assert "URL_HAS_SPACES" in codes

# ---------------------------------------------------------------------------
# Adversarial Boundaries: Security
# ---------------------------------------------------------------------------
from api.crawler.checkers.security import _check_security

class TestSecurityAdversarial:
    def test_uppercase_http_scheme_flagged_as_http_page(self):
        """Vulnerability: case-sensitive startswith('http://') bypasses HTTP_PAGE check."""
        page = _page(url="HTTP://example.com/page", has_hsts=False)
        issues = []
        _check_security(page, issues, hsts_checked_hosts=set())
        codes = [i.code for i in issues]
        assert "HTTP_PAGE" in codes
```

## Acceptance Criteria

1. The 3 adversarial tests must be added to the test suite and fail on `main`.
2. The logic in `links.py`, `url_structure.py`, and `security.py` must be patched.
3. The test suite must pass with 0 regressions.

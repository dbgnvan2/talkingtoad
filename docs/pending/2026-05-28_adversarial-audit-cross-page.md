---
status: pending
proposed: 2026-05-28
author: QA Auditor
source: Formal Adversarial Review (Cycle 3)
---

# Adversarial Hardening: Cross-Page Domain

## Why
A forensic QA audit of `api/crawler/checkers/cross_page.py` revealed two logic evasions. Both vulnerabilities cause the crawler to silently under-report critical SEO issues (orphan pages and duplicate metadata) due to flawed heuristics.

## Vulnerabilities

### V1 — The Self-Link Evasion (Orphan Pages)
* **Code:** The link aggregator indiscriminately adds all internal `link.url` to the `linked_urls` set.
* **Flaw:** If a page links to itself (e.g., "Back to Top", or a logo link), it puts its own URL into the "discovered" bucket. It then evades the `ORPHAN_PAGE` check, even though no *other* page links to it. A page linking to itself does not make it discoverable.

### V2 — Case-Sensitive Grouping (Duplicate Metadata)
* **Code:** `title_map` and `desc_map` use the exact, case-sensitive string as the grouping key.
* **Flaw:** "About Us" and "about us" are bucketed separately and evade the `TITLE_DUPLICATE` and `META_DESC_DUPLICATE` checks.

## Proposed Fixes

### F1 — Filter Self-Links from the Discovered Bucket
`api/crawler/checkers/cross_page.py`
```python
# BEFORE
    linked_urls: set[str] = set()
    for page in pages:
        for link in page.links:
            if link.is_internal:
                try:
                    linked_urls.add(normalise_url(link.url))
                except Exception:
                    pass

# AFTER
    linked_urls: set[str] = set()
    for page in pages:
        try:
            page_norm = normalise_url(page.url)
        except Exception:
            page_norm = None

        for link in page.links:
            if link.is_internal:
                try:
                    link_norm = normalise_url(link.url)
                    # A page linking to itself does not make it discoverable
                    if link_norm and link_norm != page_norm:
                        linked_urls.add(link_norm)
                except Exception:
                    pass
```

### F2 — Casefold Keys for Semantic Deduplication

`api/crawler/checkers/cross_page.py` — change the grouping logic to use `.casefold()` for the grouping keys, while preserving the original string for the issue report extra data. This requires a minor refactor of how the maps store the original strings.

```python
# BEFORE
        t = (page.title or "").strip()
        if t:
            title_map.setdefault(t, []).append(page.url)

# AFTER
        t_orig = (page.title or "").strip()
        t_key = t_orig.casefold()
        # Store as: map[key] = (original_string, [urls])
        if t_key:
            if t_key not in title_map:
                title_map[t_key] = (t_orig, [])
            title_map[t_key][1].append(page.url)

# NOTE: Apply this same structure to desc_map and pair_map, and update
# the emission loops below to unpack the tuple.
```

## Tests (Adversarial)

Inject these into the appropriate test file (e.g., `tests/test_cross_page.py` or the merged equivalent).

```python
# ---------------------------------------------------------------------------
# Adversarial Boundaries: Cross-Page Checks
# ---------------------------------------------------------------------------
import pytest
from api.crawler.checkers.cross_page import check_cross_page
from api.crawler.parser import ParsedLink

class TestCrossPageAdversarial:
    def test_orphan_page_self_link_evasion(self):
        """Vulnerability: A page that links to itself evades orphan detection."""
        home = _page(url="https://example.com/", links=[
            ParsedLink(url="https://example.com/about", text="About", is_internal=True)
        ])
        about = _page(url="https://example.com/about", links=[])

        # The orphan page only has a link to itself
        orphan = _page(url="https://example.com/orphan", links=[
            ParsedLink(url="https://example.com/orphan", text="Back to top", is_internal=True)
        ])

        issues = check_cross_page([home, about, orphan], start_url="https://example.com/")
        codes = [i.code for i in issues if i.page_url == "https://example.com/orphan"]
        assert "ORPHAN_PAGE" in codes

    def test_duplicate_titles_case_insensitivity(self):
        """Vulnerability: 'About Us' and 'ABOUT US' fail to trigger duplicate warnings."""
        pages = [
            _page(url="https://example.com/a", title="About Us"),
            _page(url="https://example.com/b", title="ABOUT US"),
        ]
        issues = check_cross_page(pages)
        codes = [i.code for i in issues]
        assert "TITLE_DUPLICATE" in codes
```

## Acceptance Criteria

1. The 2 adversarial tests must be added to the test suite and fail on `main`.
2. The logic in `cross_page.py` must be patched.
3. The test suite must pass with 0 regressions.

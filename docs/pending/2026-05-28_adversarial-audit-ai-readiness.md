---
status: pending
proposed: 2026-05-28
author: QA Auditor
source: Formal Adversarial Review (Cycle 1)
---

# Adversarial Hardening: AI Readiness Domain

## Why
A forensic QA audit of the newly isolated `api/crawler/checkers/ai_readiness.py` revealed four critical logic vulnerabilities. Two cause execution crashes (`TypeError` and `AttributeError`), and two are logical evasions that disable their respective checks via improper regex flags and string matching.

## Vulnerabilities

### V1 — NoneType Iterable Crash (Statistics Counter)
* **Code:** `_count_statistics` appends `h.get("text", "")`.
* **Flaw:** If the text key exists but is explicitly `None`, `.get()` returns `None`. The subsequent `" ".join(all_text_sources)` raises a `TypeError`, crashing the crawl.

### V2 — Regex Flag Contradiction (Answer Signal)
* **Code:** `_has_answer_signal` uses `re.I` (case-insensitive).
* **Flaw:** The regex intends to enforce a capitalized subject (`[A-Z]\w{2,}`). Applying `re.I` causes `[A-Z]` to match lowercase letters, destroying the constraint and flooding the system with false positives.

### V3 — Schema Array AttributeError (JSON-LD)
* **Code:** `_run_geo_checks` executes `[b for b in page.schema_blocks if not (b.get("@type") ...)]`
* **Flaw:** JSON-LD allows the root element to be an array of objects. If `b` is a list, `b.get()` raises an immediate `AttributeError`.

### V4 — Whitespace Evasion (External Citations)
* **Code:** `_count_external_body_links` uses `href.startswith("http")`.
* **Flaw:** A single leading space, tab, or newline in the href attribute causes `.startswith()` to return `False`, silently dropping valid external links.

## Tests (Adversarial)
Inject the following test class into the appropriate test file (e.g., `tests/test_ai_readiness.py` or `tests/test_issue_checker.py` depending on how the tests were organized during the facade split).

```python
class TestAiReadinessAdversarial:
    def test_statistics_none_heading_text_does_not_crash(self):
        from api.crawler.checkers.ai_readiness import _count_statistics
        page = _page(headings_outline=[{"level": 2, "text": None}])
        count = _count_statistics("Some intro text", [], page)
        assert isinstance(count, int)

    def test_answer_signal_case_insensitivity_bug(self):
        from api.crawler.checkers.ai_readiness import _has_answer_signal
        text_that_should_fail = "dog is a good boy"
        assert _has_answer_signal(text_that_should_fail) is False
        text_that_should_pass = "Photosynthesis is a process used by plants"
        assert _has_answer_signal(text_that_should_pass) is True

    def test_schema_blocks_list_does_not_crash(self):
        from api.crawler.checkers.ai_readiness import _run_geo_checks
        page = _page(is_indexable=True)
        page.schema_blocks = [[{"@type": "Article"}, {"@type": "Organization"}]]
        issues = []
        _run_geo_checks(page, "https://example.com", issues)
        assert isinstance(issues, list)

    def test_external_links_with_whitespace_are_counted(self):
        from api.crawler.checkers.ai_readiness import _count_external_body_links
        from api.crawler.parser import ParsedLink
        links = [
            ParsedLink(url="  https://external.com/article", text="Read", is_internal=False),
            ParsedLink(url="\nhttp://another.com", text="More", is_internal=False),
        ]
        count = _count_external_body_links(links, "https://example.com")
        assert count == 2
```

## Acceptance Criteria

1. The adversarial tests must be added to the test suite and run. They will fail.
2. The logic in `api/crawler/checkers/ai_readiness.py` must be patched to resolve V1, V2, V3, and V4.
3. The test suite must pass with 0 regressions.

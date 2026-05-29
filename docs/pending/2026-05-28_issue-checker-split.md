---
status: pending
proposed: 2026-05-28
author: User / System Architect
source: v2.6 M9 Technical Debt Register
---

# Issue Checker Monolith Split (Zero-Logic Extraction)

## Why
`api/crawler/issue_checker.py` has grown to ~1,500 lines. It currently handles the issue data models, the scoring registry, and the procedural checking logic for over 130 SEO, accessibility, and AI-readiness issue codes. 

This monolithic structure induces context exhaustion for AI coding agents, making it increasingly dangerous to add new checks or modify existing ones without introducing regressions. It must be modularized before any further QA audits or v3.0 features are implemented.

## Architectural Mandate: Zero-Logic Extraction
This is a strict structural refactor. **You are explicitly forbidden from altering, optimizing, or fixing the business logic of the checks themselves during this cycle.** 

The goal is exclusively to cut existing logic out of the monolith, paste it into domain-specific modules, and wire the imports back together so the test suite passes. If a function is currently poorly written but passes tests, you must move it exactly as it is.

## Implementation Plan

### 1. Create the New Package
Create a new directory at `api/crawler/checkers/` with an empty `__init__.py`.

### 2. Extract the Data Models & Registry (`registry.py`)
Create `api/crawler/checkers/registry.py`.
* Move the `Issue` dataclass and the `_IssueSpec` dataclass here.
* Move `_ISSUE_SCORING`, `_CATALOGUE`, and `_AI_READINESS_CONFIDENCE` here.
* Move the `make_issue()` factory function here.

### 3. Extract the Domain Logic
Split the remaining logic into the following targeted files inside `api/crawler/checkers/`. Move the corresponding helper functions, regex patterns, and `_check_*` blocks into their respective files.

* **`metadata.py`**: Title, meta description, canonical, lang, H1 mismatch, OG tags, Twitter cards.
* **`headings.py`**: H1 presence, multiple H1s, skips, empty headings.
* **`links.py`**: Broken links (4xx/5xx), empty anchors, generic anchors, internal nofollow, redirects.
* **`images.py`**: Alt text checks, sizes, scaling, compression, legacy formats.
* **`security.py`**: HTTP, mixed content, HSTS, cross-origin links, www-canonicalization.
* **`crawlability.py`**: Robots, noindex, sitemap, thin content, page size, stale content, pagination, AMP.
* **`ai_readiness.py`**: schema checks, LLMs.txt, semantic density, bot access, and all GEO static checks (extracting `_run_geo_checks` and its Aggarwal/mechanistic helpers).
* **`cross_page.py`**: The `check_cross_page` function (duplicates, orphans).

### 4. Convert `issue_checker.py` into a Facade
Do not delete `api/crawler/issue_checker.py`. Instead, rewrite it to act as an orchestrator (a Facade pattern).
* It should import the extracted domain functions from `api/crawler/checkers/*`.
* Its `check_page()` function should simply delegate execution to the domain checkers and aggregate the resulting `Issue` lists into a single flat list to return.
* Its `check_asset()`, `check_url_structure()`, and `issues_for_redirect()` functions should delegate to the appropriate domain module.
* This ensures that `engine.py` and `tests/test_issue_checker.py` do not require massive import rewrites.

## Acceptance Criteria
1. `api/crawler/issue_checker.py` is reduced from ~1,500 lines to a thin routing facade. **Goal: under 200 lines.** This is an aspiration, not a hard rule — if back-compat re-export shims (`Issue`, `_IssueSpec`, `make_issue`, `_CATALOGUE`, `_ISSUE_SCORING`, `_AI_READINESS_CONFIDENCE`, plus any other names imported by name elsewhere in the codebase) push the facade slightly past 200 lines, that is acceptable. The intent is "obviously a facade, not a monolith."
2. `api/crawler/checkers/` contains the specified modular files.
3. **Absolute requirement:** The command `pytest tests/test_issue_checker.py` passes with 100% success.
4. The global test suite (`pytest tests/`) passes with 0 regressions.

## Clarifications (added at approval time, 2026-05-28)

1. **Facade line count is a goal, not a rule.** See Acceptance Criteria #1 above. Re-export shims for back-compat may push the facade slightly past 200 lines; that is acceptable.

2. **`_CATALOGUE` stays monolithic in `registry.py`.** Do not split the catalogue per-domain. The architecture parity tests (`tests/test_architecture_constraints.py`, `tests/test_issue_codes_doc_in_sync.py`) and the auto-generator for `docs/issue-codes.md` all depend on `_CATALOGUE` being a single source of truth. Same applies to `_ISSUE_SCORING` and `_AI_READINESS_CONFIDENCE` — one home in `registry.py`, imported by every domain checker.

3. **GEO logic migration is a verification pass, not a guess.** `_run_geo_checks` and its mechanistic helpers are nominally headed for `ai_readiness.py`, but some GEO scoring is currently inline inside `check_page` (buffer reads, scoring math). The extractor must:
   - Audit every line in the current `check_page` for GEO-related state reads and helper calls.
   - Move them to `ai_readiness.py` *along with* `_run_geo_checks`.
   - Leave nothing GEO-related inline in the facade.

4. **Back-compat re-exports are explicit, not implicit.** The facade must re-export every public *and* underscore-prefixed name that existing code imports from `api.crawler.issue_checker`. Before declaring done, run `grep -rn "from api.crawler.issue_checker import" .` (excluding `venv/`, `node_modules/`, `__pycache__/`) and confirm every imported name resolves through the facade. Missing names break callers silently — `engine.py`, the routers, the help-data builder, and several tests all reach into this module.

5. **Zero behaviour change verification.** After extraction, run the full suite (`pytest tests/`). The only acceptable diff in pass/fail counts versus pre-refactor `main` (`d869d21`) is zero. Pre-existing live-integration failures (`test_geo_apply_end_to_end`) carry over unchanged.

6. **Test file imports unchanged.** `tests/test_issue_checker.py` continues to import from `api.crawler.issue_checker`. No test file rewrites in this cycle — that's a follow-up if/when desired.

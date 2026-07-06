---
status: IMPLEMENTED 2026-07-04 (audit remediation R6)
author: Claude Code (Opus 4.8)
scope: real citation parser + source-accessibility check; re-enable the quarantined citation codes
companion: docs/review/OLD/2026-07-03_remediation-plan.md (R6) · code-audit-report §2.2
---

# R6 — real citation parser (un-quarantine)

The citation check was quarantined (audit R0.1) because it built `PageCitations(citations=[])` with
hardcoded-empty data, so `CITATIONS_MISSING_SUBSTANTIAL_CONTENT` misfired on every >200-word page
and `CITATIONS_ORPHANED` / `CITATIONS_SOURCES_INACCESSIBLE` could never fire.

## What changed
1. **`build_page_citations(page)`** (`issue_checker.py`) — extracts real citations: external body
   links to **non-social** sources (facebook/x/instagram/… excluded), anchor text as context; a
   bare-URL link (no anchor text) → orphan. Attribution style inferred from the visible text.
2. **`assess_citation_readiness(..., inaccessible_urls=None)`** (`citation_model.py`) — now derives
   `has_inaccessible_sources` from the intersection of cited URLs and a precomputed inaccessible set.
3. **`check_source_accessibility(urls, client, cap=30)`** (`citation_model.py`) — async HEAD-checks
   citation sources, **reusing `fetch_page`** (retry + backoff + SSRF guard); returns the broken/
   blocked set. Capped per job.
4. **Re-enabled** the `check_page` citation block (removed the `if False:` quarantine) → emits
   `CITATIONS_MISSING_SUBSTANTIAL_CONTENT` / `CITATIONS_ORPHANED` from real data.
5. **`citation_source_issues(pages, inaccessible)`** + engine wiring (step 7b) — post-crawl,
   HEAD-checks the collected citation URLs and emits `CITATIONS_SOURCES_INACCESSIBLE` for affected
   pages (literal `make_issue`, so it's removed from the dead-code allowlist).

No scoring changes (impact derived via `_CALIBRATION`).

## Acceptance criteria → test (`tests/test_r6_citations.py`)
- Well-cited >200-word page NOT flagged missing — `test_well_cited_page_not_flagged_missing`.
- Genuinely uncited >200-word page fires missing — `test_uncited_page_fires_missing`.
- Bare-URL citation → orphan — `test_bare_url_citation_is_orphan`.
- Social/internal links are not citations — `test_social_and_internal_not_citations`.
- Broken source → `CITATIONS_SOURCES_INACCESSIBLE` — `test_broken_source_flagged` + `test_check_source_accessibility`.
- Accessible sources → no inaccessible flag — `test_accessible_sources_not_flagged`.

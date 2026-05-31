---
status: pending
proposed: 2026-05-31
author: Architect (M3.5 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 3.5 (Google-validated extensions)
---

# M3.5 — `AI_MAIN_CONTENT_LOW_RATIO` (Heuristic)

> **Cycle 5 of M3.** Catalogue source of truth: `api/crawler/checkers/registry.py`.

## Goal
Flag pages where the main content is a small fraction of total visible text — i.e. nav,
sidebar, and footer dominate. Google: *"Whether visitors can easily distinguish main
content from other content"* — [Top ways to succeed in AI search](https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search).
Tier **Heuristic** (DOM-region heuristic; chrome boundaries are inferred).

## Relationship to existing checks
Complements `AI_NO_MAIN_LANDMARK` (which flags the *absence* of a `<main>`). M3.5 flags a
*present-but-thin* main region. Only run M3.5 when a main-content region can be identified —
do NOT double-flag pages already caught by `AI_NO_MAIN_LANDMARK`.

## Design — pre-compute at parse time (soup needed for region text)
- **Helper** in `api/crawler/parser.py` (or `extractability.py`):
  `_main_content_ratio(soup) -> float | None`:
  - Identify the main region: first of `<main>`, `[role=main]`, `<article>`. If none →
    return `None` (no signal; AI_NO_MAIN_LANDMARK owns that case).
  - `main_text_len = len(main.get_text(strip=True))`.
  - `total_text_len = len(soup.body.get_text(strip=True))` (fallback to `soup`).
  - Subtract decorative/script text the same way the parser already excludes `<script>`/
    `<style>` for word_count (reuse existing helper if present).
  - Return `main_text_len / total_text_len` (0.0–1.0); `None` if `total_text_len == 0`.
- **Threshold (code constant, NOT thresholds.md):**
  `_MAIN_CONTENT_LOW_RATIO = 0.40` in the module. Flag when `ratio < 0.40`.
- **New `ParsedPage` field:** `main_content_ratio: float | None = None`.
- **Emission** (`issue_checker.py`, indexable-only): when `main_content_ratio is not None
  and main_content_ratio < _MAIN_CONTENT_LOW_RATIO` →
  `make_issue("AI_MAIN_CONTENT_LOW_RATIO", url, extra={"ratio": round(main_content_ratio, 2)})`.
  impact 2.

## Registration (all 3 registries in `checkers/registry.py`)
- `_ISSUE_SCORING`: `"AI_MAIN_CONTENT_LOW_RATIO": (2, 1)`.
- `_CATALOGUE`: `_IssueSpec(category="ai_readiness", severity="warning",
  description="The main content is a small share of the page's visible text — navigation,
  sidebar, or footer dominate", recommendation="Make the main content the clear bulk of the
  page. Reduce boilerplate chrome or move it out of the main reading flow so AI systems and
  readers can identify the primary content.", human_description="Main Content Crowded Out",
  fixability="content_edit")`.
- `_AI_READINESS_CONFIDENCE`: `"AI_MAIN_CONTENT_LOW_RATIO": "Heuristic"`.

## Parity (mandatory)
- `issueHelp.js` entry — `confidence: "Heuristic"` + full V4 fields (template:
  `SCHEMA_VISIBLE_MISMATCH`; the `how_it_can_mislead` field should note this is a DOM-region
  heuristic and a content-rich page with a large legitimate footer could be flagged).
  Regenerate `docs/issue-codes.md`.

## Files
| File | Change |
|---|---|
| `api/crawler/parser.py` (or extractability.py) | `_main_content_ratio()` + `main_content_ratio` field + wiring + constant |
| `api/crawler/checkers/registry.py` | code × 3 registries |
| `api/crawler/issue_checker.py` | emit (indexable-only) with `extra.ratio` |
| `frontend/src/data/issueHelp.js` | entry + V4 fields |
| `docs/issue-codes.md` | regenerate |

## Test plan (`tests/test_main_content_low_ratio.py`)
- `<main>` with 100 chars inside a body of 1000 chars (ratio 0.1) → flagged.
- `<main>` that is 80% of body text → not flagged.
- **Adversarial:** no `<main>`/`article`/`role=main` → `None`, not flagged (AI_NO_MAIN_LANDMARK
  territory; no double-flag); empty body (total 0) → `None`, not flagged; a page at exactly
  0.40 → not flagged (boundary: strictly `< 0.40`); 0.39 → flagged.
- Non-indexable → not emitted. Contract: results endpoint includes `extra.ratio`.

## Security check
SSRF No · Auth N/A · WordPress No · XSS No.

## Documentation impact
`docs/issue-codes.md` regenerated; `docs/thresholds.md` (READ-ONLY) **untouched** — the 0.40
constant lives in code, noted here for the compiler. `PLAN-V3.0-UNIFIED.md` note when merged.

## Acceptance criteria
1. Ratio computed only when a main region exists; flag strictly `< 0.40`.
2. Adversarial guards pass (no-main → no flag/no double-flag; empty body; 0.40 boundary).
3. Registered in all 3 registries; issueHelp (V4) + issue-codes.md parity passes.
4. `extra.ratio` present; emitted indexable-only. `thresholds.md` untouched. Full suite green.

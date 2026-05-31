---
status: pending
proposed: 2026-05-31
author: Architect (M3.6 cycle, TalkingToad session)
type: bug-fix
source: PLAN-V3.0.md Milestone 3.6 (scoring-scope bugs, Agent 1 review)
---

# M3.6 — Fix scoring-scope bugs (`_count_statistics`, `_count_inline_quotations`)

> **Cycle 6 of M3 (final M3 item).** Bug fix, not a new code. Lives in
> `api/crawler/checkers/ai_readiness.py`.

## Classification: BUG FIX
Two GEO scoring counters only inspect a truncated window of the page, so statistics or
quotations appearing later in the body are invisible to the check — producing false
"low count" issues on pages that actually have plenty further down.

## Current state (VERIFIED in `api/crawler/checkers/ai_readiness.py`)
- `_count_statistics(first_words, links, page)` is **defined at line 220** and called at
  **line 43** as `_count_statistics(page.first_600_words or page.first_200_words or "", ...)`.
  So a prior cycle (Cycle E) already widened it from 200→600. It is **still capped at the
  first 600 words** — statistics at word ~1000/1500 are missed → false `STATISTICS_COUNT_LOW`.
- `_count_inline_quotations(page)` is **defined at line 261** and reads
  `page.first_600_words or page.first_200_words` (line 263). Same 600-word cap → later
  quotations missed.

So this is **not** "still on first_200" — both are on first_600. The fix widens both to a
new **`first_1500_words`** window.

## Fix
Add a `first_1500_words` window and feed both counters from it (fallback to narrower
windows so nothing crashes on thin pages):
- **Add `ParsedPage.first_1500_words: str | None = None`** (parser.py), computed via the
  existing `_extract_first_n_words(soup, 1500)` alongside the current
  `first_200_words`/`first_600_words` extraction (lines 373–374).
- **Call site line 43:** `_count_statistics(page.first_1500_words or page.first_600_words or page.first_200_words or "", links, page)`.
- **`_count_inline_quotations` (line 263):** read
  `page.first_1500_words or page.first_600_words or page.first_200_words or ""`.
- Keep both as pure functions; only the *input window* widens. Do **not** change the emission
  thresholds for `STATISTICS_COUNT_LOW` / `QUOTATIONS_MISSING` (scope fix only).
- The 1500-word cap is the documented upper bound (prevents unbounded over-count from
  appendices/footers); note it for the compiler — `docs/thresholds.md` stays untouched.

## Files
| File | Change |
|---|---|
| `api/crawler/checkers/ai_readiness.py` | widen window inputs for both counters |
| `api/crawler/parser.py` | (if needed) add `first_1500_words` field + extraction |
| `tests/test_ai_readiness.py` (or new `tests/test_m3_6_scoring_scope.py`) | adversarial tests |

## Test plan (ADVERSARIAL — the whole point)
- **`_count_statistics`:** a page whose statistics appear at word ~250, ~1000, and ~1500
  (NOT in the first 200 words) must be COUNTED → `STATISTICS_COUNT_LOW` must NOT fire.
  "Correct-looking but wrong": the pre-fix code returns 0 here and wrongly flags.
- **`_count_inline_quotations`:** a quotation at word ~1000 (beyond first_600) must be counted.
- **Regression:** statistics/quotations in the first 200/600 words still counted (no change).
- **No over-count:** content beyond the new window (e.g. a giant appendix) is still excluded —
  document the new window boundary and assert a stat past it is not counted (prevents the
  opposite bug).

## Security check
SSRF No · Auth N/A · WordPress No · XSS No.

## Documentation impact
No new issue code → no catalogue/issueHelp/issue-codes.md change unless a field is added
(then no code-doc change either; it's a parser field). `docs/thresholds.md` (READ-ONLY)
untouched — emission thresholds unchanged; only the measurement window widens (a code
constant). `PLAN-V3.0-UNIFIED.md` note when merged → **M3 complete**.

## Acceptance criteria
1. Statistics/quotations beyond the old truncated windows are now counted.
2. Adversarial tests prove the false `STATISTICS_COUNT_LOW` no longer fires on
   later-in-body statistics; regression tests prove early stats still count.
3. A documented upper window boundary prevents unbounded over-counting.
4. Full pytest suite green, 0 regressions. (Parity unaffected — no new code.)

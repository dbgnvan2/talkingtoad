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

## Defects (verified locations)
1. **`_count_statistics(intro_text, headings, page=None)`** (≈ line 1944) — counts over
   `intro_text` (the `first_200_words` window) + heading text only. A page with statistics
   at word 250/1000 is scored as having none → false `STATISTICS_COUNT_LOW`.
2. **`_count_inline_quotations`** (≈ line 1980) — measures only `first_600_words`. Quotations
   later in the body are missed.

## Fix
Widen the measurement window for both, without storing full page text:
- **Preferred:** add a wider pre-extracted window the parser already produces, or extend the
  existing extraction to a `first_1500_words` window and pass it to these counters. If a
  `first_1500_words`-style field doesn't exist, add one to `ParsedPage`
  (`first_1500_words: str | None = None`) computed via the existing `_extract_first_n_words`
  helper, and feed it to both counters.
- `_count_statistics`: measure the wider window (first ~600–1500 words) + headings, not just
  first_200.
- `_count_inline_quotations`: measure the wider window (first ~1500 words) instead of first_600.
- Keep the counters pure functions; only the *input window* changes. Do not change the
  emission thresholds for `STATISTICS_COUNT_LOW` / the quotation code (scope fix only).

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

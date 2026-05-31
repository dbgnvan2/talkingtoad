---
status: pending
proposed: 2026-05-31
author: Architect (M4.2 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 4.2 (Content Freshness suite)
---

# M4.2 — `CONTENT_STAT_OUTDATED` (Heuristic)

> **Cycle 2 of M4.** Catalogue: `api/crawler/checkers/registry.py`. Net-new code.

## Goal
Flag body text that cites an **old year as if current** — e.g. "the best options in 2021"
on a page with no mention of the current year. AI systems and readers treat such pages as
out-of-date. Tier **Heuristic** (year-in-prose is a noisy signal).

## Determinism (critical)
Same as M4.1: take an explicit `current_year: int` param; caller passes the runtime year,
tests pass `current_year=2026`. Do NOT call `datetime.now()` inside the detector.

## Logic
- Helper `detect_outdated_stat(text: str, *, current_year: int) -> dict | None` over the
  page's available body text window (reuse `page.first_1500_words` from M3.6, fallback
  `first_600_words`/`first_200_words` — do NOT store full text).
- Regex-scan for 4-digit years in a plausible range (`2000`–`current_year+1`) appearing in
  factual/temporal phrasing. Keep it conservative to avoid noise:
  - Match a year token `\b(20\d{2})\b`.
  - **Trigger only when** the matched year is `<= current_year - 2` (≥24 months old) AND
    the **current year does not also appear** anywhere in the scanned window (if the page
    also says 2026, it's likely already contextualized/updated → skip).
- Exclude obvious non-staleness contexts where cheap to do so: a year immediately preceded
  by `©`/`copyright` (footer), or part of a date range `20xx–20yy`/`20xx-20yy` (historical
  span). If excluding is hard, at least the "current year also present → skip" guard must hold.
- Return `{"year": <int>, "sentence": <≤160 char snippet around the match>}` or None.
- impact 2, **Heuristic**.
- Emit `make_issue("CONTENT_STAT_OUTDATED", url, extra={"year": ..., "sentence": ...})`.

## Registration (all 3 registries)
- `_ISSUE_SCORING`: `"CONTENT_STAT_OUTDATED": (2, 1)`.
- `_CATALOGUE`: `_IssueSpec(category="ai_readiness", severity="info",
  description="The page states an old year in a way that reads as current, with no mention
  of the present year", recommendation="Update time-sensitive statements to the current year
  or add an 'as of <year>' qualifier. AI systems discount content that appears out of date.",
  human_description="Outdated Year Reference", fixability="content_edit")`.
- `_AI_READINESS_CONFIDENCE`: `"CONTENT_STAT_OUTDATED": "Heuristic"`.

## Parity (mandatory)
- `issueHelp.js` entry: confidence "Heuristic" + full V4 fields; `how_it_can_mislead` must
  note this is a noisy heuristic (historical references, copyright years, date ranges can
  trip it) — which is exactly why the current-year-present guard and the ≥24mo rule exist.
  Regenerate `docs/issue-codes.md`.

## Files
| File | Change |
|---|---|
| `api/crawler/checkers/ai_readiness.py` | `detect_outdated_stat(text, *, current_year)` |
| `api/crawler/issue_checker.py` | call it (indexable-only), pass runtime year, emit `extra` |
| `api/crawler/checkers/registry.py` | code × 3 registries |
| `frontend/src/data/issueHelp.js` | entry + V4 fields |
| `docs/issue-codes.md` | regenerate |

## Test plan (`tests/test_content_stat_outdated.py`) — fixed `current_year=2026`
- "the best options in 2021" (no 2026 anywhere) → flagged, `extra.year == 2021`.
- **Adversarial — "correct-looking but wrong":**
  - "In 2023 we found X, and as of 2026 it still holds" → NOT flagged (current year present).
  - "© 2021 Living Systems" (copyright footer) → NOT flagged.
  - "from 2019–2024" (date range) → NOT flagged.
  - "In 1900, the field began" (historical, but year < 2000 range floor) → NOT flagged.
  - year exactly `current_year - 1` (2025) → NOT flagged (only ≥24mo, i.e. ≤2024).
  - empty/no-year text → None, no crash.
- Non-indexable → not emitted. Contract: results endpoint surfaces `extra.year`/`extra.sentence`.

## Security check
SSRF No · Auth N/A · WordPress No · XSS No (snippet is data; render as text).

## Documentation impact
`docs/issue-codes.md` regenerated; `docs/thresholds.md` (READ-ONLY) untouched (the 24-month
rule is a code constant). `PLAN-V3.0-UNIFIED.md` note when merged → **M4 complete** (with M4.1).

## Acceptance criteria
1. Deterministic (explicit `current_year`); flags only years ≥24mo old with NO current-year
   mention in the window.
2. All adversarial guards pass (current-year-present, copyright, date-range, pre-2000,
   off-by-one 2025, empty).
3. 3 registries + issueHelp (V4) + issue-codes.md parity passes; `extra` carries year + sentence.
4. `thresholds.md` untouched. Full suite green, 0 regressions.

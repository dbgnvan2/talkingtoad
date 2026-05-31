---
status: pending
proposed: 2026-05-31
author: Architect (M4.1 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 4.1 + 4.3 (Content Freshness suite)
---

# M4.1 — `CONTENT_DATE_STALE_VISIBLE` (Reasonable proxy) + page-type cadence

> **Cycle 1 of M4 (Content Freshness).** Catalogue: `api/crawler/checkers/registry.py`.
> Builds ALONGSIDE the existing `CONTENT_STALE` (crawlability, >12mo by Last-Modified) —
> does NOT replace it. This code is about the **visible, on-page date** being old.

## Goal
Flag pages that *show* an old date to readers/AI (e.g. "Last updated: Jan 2023") while
the server's `Last-Modified` is recent — the page looks stale to a human/AI scanning it
even though it was technically touched. Fold in **page-type-aware cadence** (M4.3) as a
recommendation in `extra`.

## Existing building blocks (verified)
- `ParsedPage.date_published`, `ParsedPage.date_modified` (from JSON-LD / `<meta>` /
  `<time datetime=...>`, via `_extract_date_published/_modified`), `ParsedPage.last_modified`
  (HTTP header). Reuse these — do NOT add new extraction unless a visible-text date pattern
  is needed beyond what `_extract_date_modified` already captures.
- `infer_page_type(page)` → `home, article, team_member, service, faq, contact, about, unknown`.

## Determinism requirement (critical for headless tests)
Do **NOT** call `datetime.now()` directly inside the check (non-deterministic; breaks
reproducible tests and orche's headless runs). Instead:
- Add a helper `check_content_date_stale_visible(page, *, today: date) -> dict | None`
  that takes an explicit `today`.
- The caller in `issue_checker.py` passes `today=datetime.now(timezone.utc).date()` at
  runtime; tests pass a fixed `today=date(2026, 5, 31)`.

## Logic
- Parse the page's **visible/declared modified date** from `page.date_modified` (already
  extracted). If absent → no signal (return None). (`DATE_MODIFIED_MISSING` already covers
  the absent case — no double-flag.)
- Parse robustly: accept ISO `YYYY-MM-DD`, ISO datetime, and year-month; on parse failure
  return None (never crash).
- Compute `age_months = (today - visible_date) in months`.
- **Page-type cadence (M4.3)** — the max age before "stale":
  - `article` → 12 months
  - `service`, `about`, `home` → 24 months
  - `team_member` → no limit (return None — staff bios don't go stale)
  - others (`faq`, `contact`, `unknown`) → 24 months default
- Flag `CONTENT_DATE_STALE_VISIBLE` when `age_months > cadence_for_type`.
- impact 4, **Reasonable proxy**.
- `extra = {"visible_date": <iso>, "age_months": <int>, "page_type": <type>, "recommended_refresh_months": <cadence>}`.

## New ParsedPage field?
Not required — the check runs at check time from existing `date_modified` + `infer_page_type`.
Keep it in `issue_checker.py` (or `ai_readiness.py` checker) like M3.4. No parse-time field.

## Registration (all 3 registries in `checkers/registry.py`)
- `_ISSUE_SCORING`: `"CONTENT_DATE_STALE_VISIBLE": (4, 2)`.
- `_CATALOGUE`: `_IssueSpec(category="ai_readiness", severity="warning",
  description="The date shown on this page is old enough that the content reads as stale for
  its page type", recommendation="Review and refresh the content, then update the visible
  date. AI systems and readers weight recency — a visibly old date reduces the chance the
  page is cited.", human_description="Visible Date Is Stale", fixability="content_edit")`.
- `_AI_READINESS_CONFIDENCE`: `"CONTENT_DATE_STALE_VISIBLE": "Reasonable proxy"`.

## Parity (mandatory)
- `issueHelp.js` entry: confidence "Reasonable proxy" + full V4 fields (template:
  `SCHEMA_VISIBLE_MISMATCH`); `how_it_can_mislead` notes cadence is heuristic and some
  evergreen pages legitimately carry old dates. Regenerate `docs/issue-codes.md`.

## Files
| File | Change |
|---|---|
| `api/crawler/checkers/ai_readiness.py` (or a small new helper near date logic) | `check_content_date_stale_visible(page, *, today)` |
| `api/crawler/issue_checker.py` | call it (indexable-only), pass runtime `today`, emit with `extra` |
| `api/crawler/checkers/registry.py` | code × 3 registries |
| `frontend/src/data/issueHelp.js` | entry + V4 fields |
| `docs/issue-codes.md` | regenerate |

## Test plan (`tests/test_content_date_stale_visible.py`) — all pass fixed `today=date(2026,5,31)`
- article, date_modified 2023-01-01 → age ~28mo > 12 → flagged; `extra.recommended_refresh_months == 12`.
- service, date_modified 2025-01-01 → ~16mo < 24 → NOT flagged.
- **Adversarial:** team_member with a 2019 date → NOT flagged (no cadence); date_modified
  absent → NOT flagged (no double-flag with DATE_MODIFIED_MISSING); unparseable date → NOT
  flagged, no crash; article exactly 12mo old → NOT flagged (strictly `>`), 13mo → flagged.
- Non-indexable → not emitted. Contract: results endpoint surfaces the code with `extra.visible_date`.

## Security check
SSRF No · Auth N/A · WordPress No · XSS No.

## Documentation impact
`docs/issue-codes.md` regenerated; `docs/thresholds.md` (READ-ONLY) untouched — cadence
constants live in code (note for compiler). `PLAN-V3.0-UNIFIED.md` note when merged.

## Acceptance criteria
1. Deterministic (explicit `today` param); flags only when visible date age exceeds the
   page-type cadence; `>` boundary strict.
2. Adversarial guards pass (team_member exempt, absent date no-double-flag, unparseable safe, boundary).
3. 3 registries + issueHelp (V4) + issue-codes.md parity passes; `extra` carries
   visible_date/age_months/page_type/recommended_refresh_months.
4. `thresholds.md` untouched. Full suite green, 0 regressions.

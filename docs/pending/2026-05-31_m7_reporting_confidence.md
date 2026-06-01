---
status: pending
proposed: 2026-05-31
author: Architect (M7 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 7 (Reporting & confidence surfacing)
---

# M7 — Reporting & Confidence Surfacing (PDF + Excel)

> Reporting only. No new issue codes → **no registry/catalogue/parity change.**
> Surfaces the `confidence_label` already on the Issue model into the exports.

## Goal
The new M3/M4/M5 AI-readiness codes already appear in the PDF/Excel "AI Readiness"
grouping (all are `category="ai_readiness"`). The gap (per PLAN-V3.0 §M7): the
**evidence-strength `confidence_label`** (Established / Reasonable proxy / Heuristic) is
on `Issue.confidence_label` and in API responses but is **NOT rendered** in either export.

## Verified facts
- `Issue.confidence_label: str | None` exists (`api/models/issue.py:71`) and is populated
  in the crawl summary path (`crawl.py:140`).
- PDF: `api/services/report_generator.py` — issues grouped by category/code; per-code render
  block ~L478–490 prints description + optional help. **Insertion point: after the
  description multi_cell (~L481), before the help section.**
- Excel: `api/services/excel_generator.py` — the "AI Readiness" sheet (L67) is currently only
  an llms.txt placeholder; there is **no per-issue table with a confidence column**.

## Scope (3 small pieces)

### M7.a — PDF confidence pill on AI-readiness issues
- In the per-code render block, when `first.confidence_label` is set, print a short
  evidence-tier line under the code title, e.g. `Evidence: Established` — colour-coded:
  Established → green (`COLOR_*` already defined), Reasonable proxy → amber/gray,
  Heuristic → gray. Use existing `set_text_color` + a small helper; keep Latin-1-safe
  `clean_text`.
- Add a **one-paragraph intro** to the existing "AI Readiness" category section explaining
  the three tiers (only when that section has ≥1 issue).

### M7.b — Excel: AI-readiness issue table with a Confidence column
- Extend the "AI Readiness" sheet (after the llms.txt block, starting ~row 23): add a
  header row `Code | Severity | Confidence | Page URL | Description` and one row per
  AI-readiness issue (`i.category == "ai_readiness"`), reading `i.confidence_label or ""`.
- Keep the existing llms.txt block intact above it.

### M7.c — Tests
- `tests/test_report_generator.py` (extend): a job whose issues include an AI-readiness code
  with `confidence_label="Established"` → the generated PDF bytes are non-empty and the
  generation path runs without error with confidence present. (PDF is binary; assert it
  builds + that the code path handling confidence is exercised — mirror existing PDF tests.)
- `tests/test_excel_generator.py` (extend or create): the "AI Readiness" sheet contains a
  "Confidence" header cell and a row whose Confidence cell == "Established" for a seeded
  AI-readiness issue. Use openpyxl to read back the produced workbook.
- **Adversarial:** an issue with `confidence_label=None` (e.g. a non-AI-readiness code that
  somehow reaches the AI sheet, or an older issue) → renders an empty Confidence cell / no
  crash; PDF skips the evidence line cleanly.

## Files
| File | Change |
|---|---|
| `api/services/report_generator.py` | confidence pill + tier intro paragraph (M7.a) |
| `api/services/excel_generator.py` | AI-readiness issue table w/ Confidence column (M7.b) |
| `tests/test_report_generator.py` | confidence-present test + None-safe test |
| `tests/test_excel_generator.py` | Confidence column test (create file if absent) |

## Security check
SSRF No · Auth N/A (export goes through existing authed routes) · WordPress No · XSS No
(PDF/Excel, not HTML).

## Documentation impact
None to issue-codes.md (no code change). `docs/thresholds.md` (READ-ONLY) untouched.
`PLAN-V3.0-UNIFIED.md` note when merged.

## Acceptance criteria
1. PDF renders an evidence-tier line for AI-readiness issues that carry a `confidence_label`,
   colour-coded, with a tier-explainer intro paragraph in the AI Readiness section.
2. Excel "AI Readiness" sheet has a Confidence column populated from `confidence_label`.
3. None/absent confidence is handled safely in both (no crash, blank rendering).
4. New/extended tests pass; full suite green, 0 regressions. **No registry/parity change.**

## Note for architect/dev
This is the FIRST cycle that does NOT touch the issue catalogue — do not add a code, do not
regenerate issue-codes.md, do not edit issueHelp.js. If the parity tests run, they should be
unaffected. Keep PDF text Latin-1-safe via the existing `clean_text`.

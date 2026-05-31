---
status: pending
proposed: 2026-05-31
author: Architect (M3.1 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 3.1 (Google-validated extensions)
---

# M3.1 — `SCHEMA_VISIBLE_MISMATCH` (Established)

> **First cycle of M3.** M3 adds several codes; it is sequenced into small
> per-code orche cycles (parity surface + headless risk). This is cycle 1 of that
> sequence. Subsequent: M3.2 `AI_CONTENT_NOT_IN_TEXT`, M3.3 X-Robots-Tag,
> M3.4 `AI_NO_VISUAL_COMPANION`, M3.5 `AI_MAIN_CONTENT_LOW_RATIO`, M3.6 scoring-scope fixes.

## Goal
Flag pages where a value declared in JSON-LD structured data does **not** appear in
the page's visible text. Google is explicit: *"all the content in your markup is also
visible on your web page"* — [Top ways to succeed in AI search](https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search).
Because this is a direct Google directive, the confidence tier is **Established**.

## Design — pre-compute at parse time (Cycle GG precedent)
There is **no** full visible-text field on `ParsedPage` (only truncated
`first_200_words`/`first_600_words`), and we must NOT store the entire page text
(storage bloat). So, exactly like `GEO_SUMMARY_BURIED`: compute the comparison in the
parser where `soup` is in scope, and persist only a small list of mismatched field
labels.

- **New `ParsedPage` field:** `schema_visible_mismatch_fields: list[str] | None = None`
  - `None` → no JSON-LD on the page, or not computed (legacy) → **no signal**.
  - `[]` → schema present, every checked value is visible → no issue.
  - `["Article.headline", ...]` → these declared values are missing from visible text.
- **Comparison helper** (add to the existing schema service
  `api/services/schema_typing.py`):
  `check_schema_visible_mismatch(schema_blocks: list[dict], visible_text: str) -> list[str]`
  - Normalize both sides: lowercase, collapse runs of whitespace to a single space,
    strip. Compare by **substring containment** (declared value ⊆ visible text).
  - Walk `@graph` nesting and arrays of objects.
  - **Fields checked** (per PLAN-V3.0 M3.1):
    `Article.headline`, `Product.name`, `FAQPage.mainEntity[*].name` and
    `.acceptedAnswer.text`, `Person.name`, `Organization.name`,
    `LocalBusiness.address` (compare the assembled address string).
  - **Skip empty/missing values** — a field that isn't present, or is an empty string,
    is NOT a mismatch (it's just absent). Only a *non-empty declared value that is not
    visible* counts.
  - Label format: `"<Type>.<field>"`, with index for arrays
    (`"FAQPage.mainEntity[1].acceptedAnswer.text"`).
- **Parser wiring** (`api/crawler/parser.py`): after `schema_blocks` and
  `visible_text = soup.get_text()` are available, set
  `schema_visible_mismatch_fields = check_schema_visible_mismatch(schema_blocks, visible_text)`
  when `schema_blocks` is truthy, else `None`. Wrap in try/except → `None` on any error
  (never abort the parse), mirroring the Cycle GG defensive block.
- **Emission** (`api/crawler/issue_checker.py`): when
  `page.schema_visible_mismatch_fields` is a non-empty list, append
  `make_issue("SCHEMA_VISIBLE_MISMATCH", url, extra={"mismatched_fields": page.schema_visible_mismatch_fields})`.

## Issue-code registration (all three registries in `api/crawler/checkers/registry.py`)
- **`_ISSUE_SCORING`:** `"SCHEMA_VISIBLE_MISMATCH": (5, 2)` — default impact 5 (per
  PLAN-V3.0 M3.1); second number per the existing weight convention used by peer
  schema codes (`SCHEMA_TYPE_MISMATCH` is `(4, 2)`).
- **`_CATALOGUE`:** `_IssueSpec(category="ai_readiness", severity="warning",
  description="A value declared in JSON-LD structured data does not appear in the page's
  visible text", recommendation="Make sure every value in your structured data (headline,
  name, FAQ answers, address) is also present in the visible page content — Google
  requires markup to match what users see.", human_description="Schema Not in Visible
  Text", fixability="content_edit")`.
- **`_AI_READINESS_CONFIDENCE`:** `"SCHEMA_VISIBLE_MISMATCH": "Established"`.

## Parity (mandatory — these tests fail otherwise)
- **`frontend/src/data/issueHelp.js`:** add a `SCHEMA_VISIBLE_MISMATCH` entry with
  `confidence: "Established"` and the **V4 explainer fields** (what it is / why useful /
  good vs bad / how it can mislead / how to fix).
- **`docs/issue-codes.md`:** regenerate via `python scripts/generate_issue_codes_doc.py`.
- The catalogue ↔ issueHelp ↔ scoring ↔ confidence parity tests in
  `tests/test_architecture_constraints.py` must pass.

## Files to add / modify
| File | Change |
|---|---|
| `api/services/schema_typing.py` | **add** `check_schema_visible_mismatch(schema_blocks, visible_text) -> list[str]` |
| `api/crawler/parser.py` | **add** `schema_visible_mismatch_fields` field + pre-compute block |
| `api/crawler/checkers/registry.py` | **add** code to all 3 registries |
| `api/crawler/issue_checker.py` | **emit** `SCHEMA_VISIBLE_MISMATCH` with `extra.mismatched_fields` |
| `frontend/src/data/issueHelp.js` | **add** entry (confidence + V4 explainer) |
| `docs/issue-codes.md` | regenerate |

## Test plan (`tests/test_schema_visible_mismatch.py`)
**Unit — the helper:**
- `Article.headline` present in visible text → not flagged.
- `Article.headline` absent from visible text → flagged (`"Article.headline"` in list).
- `FAQPage` with one answer visible and one not → only the missing one is listed.
- `@graph`-nested `Organization.name` missing → flagged.
- `LocalBusiness.address` assembled string missing → flagged.

**Adversarial — "correct-looking but wrong":**
- **Whitespace/case differ but content matches** (schema `"Grief  Counselling"` vs
  visible `"grief counselling"`) → **NOT flagged** (normalization must absorb this).
- **Empty / missing field** (`headline: ""` or no headline key) → **NOT flagged**
  (absence ≠ mismatch).
- Malformed JSON-LD block (not a dict, or a list) → no crash, no false flag.

**Integration / contract:**
- `tests/test_issue_checker.py` — a page whose `schema_visible_mismatch_fields` is
  non-empty yields a `SCHEMA_VISIBLE_MISMATCH` issue carrying `extra.mismatched_fields`.
- Contract: `GET /api/crawl/{id}/pages/issues?url=...` (or the results endpoint the
  frontend reads) includes the code with `extra.mismatched_fields` when present
  (`test_pages_issues_includes_schema_visible_mismatch`).

## Security check
- **SSRF:** No — pure local comparison, no fetch.
- **Auth:** N/A — runs at crawl/parse time.
- **WordPress:** No.
- **XSS:** No.

## Documentation impact
- `docs/issue-codes.md` — regenerated (new code).
- `docs/thresholds.md` (READ-ONLY) — **untouched**; this check has no numeric threshold.
- `PLAN-V3.0-UNIFIED.md` — note M3.1 done when merged.

## Acceptance criteria
1. Helper flags only non-empty declared values that are absent from normalized visible text.
2. The two adversarial guards pass (whitespace/case match → no flag; empty field → no flag).
3. Code registered in all 3 registries; issueHelp.js + issue-codes.md parity tests pass.
4. Issue emitted with `extra.mismatched_fields`; contract test asserts the field.
5. Full pytest suite green, 0 regressions.

# Micro-spec: Make SCHEMA_VISIBLE_MISMATCH actionable — show the mismatched value

Date: 2026-07-06
Status: implemented (owner-approved)
Issue code: `SCHEMA_VISIBLE_MISMATCH` (category `ai_readiness`, severity `warning`)

## Problem

`check_schema_visible_mismatch` recorded only field LABELS (e.g. `"Article.headline"`),
so the emitted issue `extra={"mismatched_fields": [...]}` listed field names with no
value and no context. The frontend didn't render `mismatched_fields` at all, so the
user saw "Schema not in visible text" with no way to know WHICH schema value was
missing from the page.

## Change

For each mismatch, capture the actual schema VALUE that wasn't found in the visible
text and display it as:

> **Article.headline** — schema says "…" — not on the page

### Backend

- `api/services/schema_typing.py`: mismatch records changed from bare label strings to
  `{"field": <label>, "value": <schema value>}` dicts. The value is the exact schema
  string that failed the visible-text check (for `LocalBusiness.address` → the assembled
  address; for `FAQPage.mainEntity` → the question name / answer text). Each value is
  truncated to **120 chars** with a trailing `…` when longer (`_MISMATCH_VALUE_MAX_CHARS`,
  `_truncate_value`, `_record_mismatch`). `check_schema_visible_mismatch` return type is
  now `list[dict]`. The false-positive guards (`_is_author_publisher_node`,
  `_is_machine_identifier`) are unchanged — only WHAT is recorded changed, not WHICH
  fields are flagged.
- `api/crawler/parser.py`: `ParsedPage.schema_visible_mismatch_fields` is now `list[dict]`.
- `api/crawler/issue_checker.py`: no logic change — `extra={"mismatched_fields": ...}` now
  carries the richer list; truthiness guard (empty list = falsy) still holds.
- `api/crawler/checkers/registry.py`: `SCHEMA_VISIBLE_MISMATCH` recommendation/`how_to_fix`
  updated to tell the user the report lists the specific mismatched values and the two
  fixes (add the text to the page, or correct the schema). `docs/issue-codes.md`
  regenerated.

### Frontend

- `frontend/src/pages/Results.jsx`: `IssueCard` gained a renderer for
  `extra.mismatched_fields` (non-empty array). Each row renders
  `{field} — schema says "{value}" — not on the page`. React auto-escapes the value.
  Legacy plain-string items are handled defensively. `IssueCard` is now exported for unit
  testing.

## Tests

- `tests/test_schema_visible_mismatch.py`: assertions updated to the `list[dict]` shape;
  new `test_article_headline_captures_value`, FAQ/address value-capture assertions,
  `TestValueTruncation` (>120 chars → truncated with `…`; short values untouched), and
  `test_emitted_extra_is_list_of_field_value_dicts`.
- `tests/test_schema_typing.py`: FP-guard regression tests
  (`test_visible_mismatch_no_fp_theme_schema`, `test_visible_mismatch_still_fires_on_true_subject_person`)
  updated to the new shape; author-node / machine-identifier suppression intact.
- `tests/test_schema_accuracy_fixes.py`: membership assertions updated via a `_fields`
  helper.
- `frontend/src/pages/__tests__/IssueCardSchemaMismatch.test.jsx`: renders field + value,
  handles legacy string items, renders nothing for an empty list.

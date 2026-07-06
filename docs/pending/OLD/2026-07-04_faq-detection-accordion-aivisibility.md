---
status: pending — AWAITING APPROVAL (do not implement until approved)
proposed: 2026-07-04
author: Claude Code (Opus 4.8)
scope: Phase-1 detection precision + ONE new issue code (B). Impact is derived via _CALIBRATION — no hand-edited scores.
origin: Page-by-page accuracy audit of livingsystems.ca (/counselling/, /training-2/) + Gemini "AI agents finding FAQs" discussion
companion: docs/pending/OLD/2026-07-04_faq-schema-generator.md (feature C, separate proposal)
---

# FAQ detection hardening (accordion-aware) + AI-visibility check

> **IMPLEMENTED 2026-07-04.** A + B shipped with tests (`tests/test_faq_detection.py`, 13 cases
> incl. the adversarial non-FAQ-accordion case). New code `FAQ_ANSWERS_NOT_IN_HTML` (impact 4,
> derived) added to the registry + `issueHelp.js` + regenerated `docs/issue-codes.md` (152 codes);
> cluster-suppressed under `RAW_HTML_JS_DEPENDENT`. `question_headings` extra replaced by accurate
> `question_count`+`sources`. Verified end-to-end on livingsystems.ca/counselling/ (10 accordion
> questions detected, answers present → B correctly silent). Full suite 1858 passed; frontend 181
> passed. Folded into `docs/functional-specification.md` + `docs/thresholds.md`. Feature C
> (schema generator) tracked separately in `2026-07-04_faq-schema-generator.md`.

Two linked changes to how the tool reasons about FAQ content, both grounded in verified findings
on livingsystems.ca (WordPress + Elementor nested-accordion FAQ):

- **A — accordion-aware FAQ detection.** `FAQ_SCHEMA_MISSING` (GEO.5.2, `ai_readiness.py:188-198`)
  counts questions **only in `<h1>`–`<h6>`**. Real FAQs on Elementor/Gutenberg sites live in
  `<details>/<summary>` or `.e-n-accordion-item-title-text`, so `question_headings` reports `0` and
  the check fires **only if a literal "FAQ" heading happens to exist**. On `/counselling/` and
  `/training-2/` it fired by luck (an `<h5>FAQ</h5>` label); a page with an accordion FAQ and no
  "FAQ" heading is a **silent false negative** — the tool fails to give its own core advice.
- **B — new check: FAQ answers not present in raw HTML (AI-invisible).** Because the crawler fetches
  **raw HTML with no JS execution**, it sees exactly what a non-rendering AI crawler sees. If an
  accordion's question titles are in the source but the **answer bodies are absent** (JS-hydrated on
  click), the FAQ is invisible to AI. This is the failure mode Gemini describes; the tool is uniquely
  positioned to detect it. livingsystems.ca **passes** (all answers present, 170–579 chars each) — B
  exists to catch the sites that don't.

## Verified ground truth (livingsystems.ca/counselling/, raw no-JS fetch)

- FAQ = 10 `<details>/<summary>` + Elementor `.e-n-accordion-item-title-text`; **answers present in
  source** (real text, not JS-only). No `FAQPage` in JSON-LD (only Organization/WebSite/BreadcrumbList/Person).
- Current detector: `question_headings: 0` (wrong — 7 real questions), fired only via the `<h5>FAQ</h5>` label.

## A — Acceptance criteria → test

Parser (`api/crawler/parser.py`):

- **A1.** New extractor collects FAQ candidate Q&A pairs from, in priority order:
  (a) `<details>` with a child `<summary>` (native disclosure);
  (b) Elementor nested accordion `.e-n-accordion-item` (title `.e-n-accordion-item-title-text`, body the item content);
  (c) legacy `.elementor-toggle-item` / `.elementor-tab-title` + associated content;
  (d) heading-based: an `<h*>` whose text matches `_Q_RE`, answer = text of following siblings until the next heading.
  Dedupe candidates whose normalized question text is identical (Elementor emits mobile+desktop copies — this is why the raw scan saw each question twice).
  **AC:** `test_faq_extract_details_summary`, `test_faq_extract_elementor_nested_accordion`, `test_faq_dedupes_mobile_desktop_duplicates`.
- **A2.** Each candidate exposes `{question: str, answer_char_count: int, container: "details"|"accordion"|"toggle"|"heading"}`.
  Stored on `ParsedPage.faq_blocks: list[dict]` (new field; default `[]`, backfilled `None`-safe like other Phase-2 fields).
  **AC:** `test_parsedpage_faq_blocks_field_populated` + a **serialization test** asserting the field survives the model round-trip.

Checker (`api/crawler/checkers/ai_readiness.py` GEO.5.2):

- **A3.** Question count = distinct questions from `page.faq_blocks` **plus** heading `_Q_RE` matches (deduped),
  not headings alone. Trigger `FAQ_SCHEMA_MISSING` when `has_faq_heading OR question_count >= 3` and no `FAQPage` schema.
  Replace the misleading `question_headings` extra with `question_count` (accurate) + `sources` breakdown
  (e.g. `{"details": 6, "heading": 1}`). **AC:** `test_faq_schema_missing_fires_on_accordion_without_faq_heading`
  (the exact false-negative case), `test_faq_extra_reports_accurate_question_count`.
- **A4.** Adversarial: a non-FAQ accordion (feature list, product specs — titles NOT question-shaped and no FAQ heading)
  must **not** trigger `FAQ_SCHEMA_MISSING`. **AC:** `test_non_question_accordion_not_flagged` (P7).

## B — Acceptance criteria → test

New issue code **`FAQ_ANSWERS_NOT_IN_HTML`** (category `ai_readiness`):

- **B1.** Registry wiring in `api/crawler/checkers/registry.py` (SOURCE OF TRUTH):
  add to `_CATALOGUE` (title/description/recommendation), `_CALIBRATION` (proposed:
  confidence `"Reasonable proxy"`, effect_size `"moderate"`, measured `False` — heuristic detection via a
  raw-HTML body-length threshold, so not over-weighted; **final impact is derived, not hand-set**),
  and `_AI_READINESS_CONFIDENCE`. Sync `frontend/src/data/issueHelp.js` + regenerate `docs/issue-codes.md`.
  **AC:** existing parity tests (`test_architecture_constraints.py`: catalogue↔help↔scoring↔confidence)
  must pass; `test_issue_codes_md_in_sync`.
- **B2.** Detection: for each `page.faq_blocks` entry whose question is present but `answer_char_count < 40`
  (threshold → `docs/thresholds.md`), the answer is absent from server HTML. Emit `FAQ_ANSWERS_NOT_IN_HTML`
  **once per page** with `extra={"affected": n, "total": len(faq_blocks), "examples": [q1, q2]}`.
  Announce N-of-M (P2/P9), never silently. **AC:** `test_faq_answers_js_only_flagged` (titles present, bodies empty),
  `test_faq_answers_present_not_flagged` (livingsystems.ca-style: bodies present → no fire).
- **B3.** Cluster/overlap with R7: if `RAW_HTML_JS_DEPENDENT` already fires page-wide for the same root cause,
  suppress the narrower `FAQ_ANSWERS_NOT_IN_HTML` to avoid double-counting. Wire into the existing
  `_CLUSTER_SUPPRESSION` map (`job_store_base.py`). **AC:** `test_faq_js_suppressed_when_page_js_dependent`.
- **B4.** **Never fabricate (global rule):** B only reports absence — it must not synthesize or infer answer
  text. This field is also the gate for feature C: C may generate schema **only** from answers with
  `answer_char_count >= 40` (present in raw HTML). **AC:** asserted in C's spec.

## Constraints

- Impact for `FAQ_ANSWERS_NOT_IN_HTML` is **derived** by `derive_impact()` from its `_CALIBRATION` tuple —
  no entry written directly into `_ISSUE_SCORING`. A2/A3 change **what fires and what's reported**, not weights.
- `<details>` content is standard HTML text — no XSS surface (read-only extraction), but strip scripts/styles
  from `answer_char_count` so inline CSS (Elementor bloat) doesn't inflate the count.
- Tests-first; `pytest tests/ -q` green except the 3 pre-existing unrelated `test_usage_aggregation.py` failures.
- New threshold (40 chars) and any new numeric bound → `docs/thresholds.md` at completion.

## Open questions for approval

1. **New code vs reuse.** B adds `FAQ_ANSWERS_NOT_IN_HTML`. Alternative: fold into existing
   `RAW_HTML_JS_DEPENDENT` with a FAQ-specific `extra`. Recommendation: **new code** — it's a distinct,
   FAQ-scoped, directly-actionable finding and pairs with feature C. Confirm.
2. **Threshold.** 40 chars for "answer present" — reasonable for a one-sentence answer. Adjust?

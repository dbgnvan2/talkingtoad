---
status: pending — AWAITING APPROVAL (do not implement until approved)
proposed: 2026-07-04
author: Claude Code (Opus 4.8)
scope: New "generate & advise" feature — FAQPage JSON-LD generator. NO auto-inject via WP API (WP safety rule).
depends-on: docs/pending/2026-07-04_faq-detection-accordion-aivisibility.md (A+B — provides page.faq_blocks with real answer text)
origin: User question ("Perhaps a schema generation?") + Gemini "AI clarity via FAQ Schema" discussion
---

# FAQPage schema generator (generate-and-advise)

When a page has a real FAQ but no `FAQPage` structured data (`FAQ_SCHEMA_MISSING` fires), generate
**ready-to-paste FAQPage JSON-LD** from the Q&A pairs already extracted in feature A, and surface it as
advisor output the user copies into Rank Math / Yoast / a custom-HTML block. This is the "fix" side of the
`FAQ_SCHEMA_MISSING` finding.

**Precedent:** mirrors the existing **llms.txt generator** (`frontend/src/components/LLMSTxtGenerator.jsx`
+ its utility endpoint) — a generate-preview-copy flow, not an auto-apply flow.

## Hard constraints (load-bearing)

- **NO auto-inject via WordPress API.** Per `CLAUDE.md` WP-safety rules, the tool must not write schema
  into posts/pages. Output is **copy/export only**; the user pastes it into their SEO plugin's FAQ block.
- **Never fabricate (global rule + LEARNINGS P-class).** Schema is built **only** from answer text actually
  present in raw HTML — i.e. `faq_blocks` entries with `answer_char_count >= 40` (feature B's gate). If a
  page's answers are JS-only (B fired `FAQ_ANSWERS_NOT_IN_HTML`), the generator must **refuse** and tell the
  user to make answers visible in HTML first — it must never invent answer text to fill the schema.
- **Escape / validate.** Answer HTML is sanitized to plain text (strip tags/scripts) before embedding in
  JSON-LD; output is valid, minified, schema.org-compliant `FAQPage`.

## Acceptance criteria → test

Service (`api/services/faq_schema_generator.py`, new):

- **C1.** `build_faqpage_jsonld(faq_blocks) -> dict | None` produces a schema.org `FAQPage` with
  `mainEntity: [{"@type":"Question","name":Q,"acceptedAnswer":{"@type":"Answer","text":A}}, …]`.
  Returns `None` (not an empty shell) when fewer than 2 usable Q&A pairs. **AC:**
  `test_build_faqpage_from_blocks`, `test_build_faqpage_none_when_insufficient`.
- **C2.** Only pairs with `answer_char_count >= 40` are included; JS-only answers excluded, and if that
  leaves < 2 pairs the generator refuses with a reason. **AC:** `test_generator_excludes_js_only_answers`,
  `test_generator_refuses_when_answers_not_in_html`.
- **C3.** Output validates: every `name`/`text` is plain text (no `<script>`, no raw HTML), JSON round-trips,
  `@context` = `https://schema.org`. **AC:** `test_faqpage_output_is_sanitized_and_valid` (P14 adversarial:
  an answer containing `<script>` must be neutralized).

API (`api/routers/ai.py` or `utility.py`, under `require_auth`):

| Endpoint | Frontend expects | Test name | Status |
|---|---|---|---|
| POST `/api/ai/faq-schema` `{job_id, page_url}` | `{jsonld: str \| null, question_count: int, refused: bool, reason: str \| null}` | `test_faq_schema_endpoint_response_schema` | Pending |
| POST `/api/ai/faq-schema` (answers JS-only) | `refused: true`, `reason` names the visibility problem | `test_faq_schema_endpoint_refuses_js_only` | Pending |
| POST `/api/ai/faq-schema` (no FAQ on page) | `400`/`refused` with clear reason | `test_faq_schema_endpoint_no_faq` | Pending |

- **C4.** Endpoint reads `faq_blocks` from the stored crawl for `(job_id, page_url)` — no re-fetch, no
  fabrication. Domain-validate if the page is WP (`_validate_wp_domain_for_job`) per WP-touching-endpoint rule.
  **AC:** the three contract tests above, written **before** any frontend code (CLAUDE.md API-contract rule).

Frontend (`frontend/src/components/`, new `FaqSchemaGenerator.jsx`):

- **C5.** On a page where `FAQ_SCHEMA_MISSING` shows, a "Generate FAQ schema" action calls the endpoint and
  renders the JSON-LD in a copy box with explicit loading/error/refused states + paste instructions
  (Rank Math / Yoast / custom-HTML block). Mirrors `LLMSTxtGenerator.jsx`. When `refused`, show the
  reason (e.g. "answers aren't in your page's HTML — fix visibility first") instead of a schema box.
  **AC:** component test for the three states (success / refused / error).

## Explicitly out of scope (this proposal)

- Auto-inserting schema into WordPress (banned).
- **Validating** an *existing* `FAQPage`'s answers against visible text — already covered by
  `SCHEMA_VISIBLE_MISMATCH` (`FAQPage.mainEntity[i].acceptedAnswer.text`). No new validation code needed;
  note the overlap so we don't duplicate it.

## Constraints

- No scoring changes (C emits no issue codes; it consumes A/B output).
- Tests-first; contract tests before frontend. `pytest tests/ -q` green except the 3 pre-existing
  unrelated `test_usage_aggregation.py` failures.
- Sequencing: **A+B must ship first** (C depends on `page.faq_blocks` + the `answer_char_count` gate).

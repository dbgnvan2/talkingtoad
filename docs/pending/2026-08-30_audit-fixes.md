# Audit fixes — the 20 defects found by the full 170-code validation

**Date:** 2026-08-30
**Status:** Proposed — user approved implementation ("write the specs and implement")
**Source:** `docs/audit/2026-08-30_full-check-audit.md`

Implemented in the audit's ranked order. Each item states the defect, the fix,
and the test that fails without it.

---

## AF1 — `ENTITY_SAMEAS_MISSING`: any → all, plus evidence

**Defect.** Flags a page when **any** Organization/Person node lacks `sameAs`,
rather than when **no** entity carries it. WordPress/Yoast emits an author
`Person` node on every article; an author node is not expected to carry
`sameAs`. Result: 74 of 256 pages flagged while the site's `Organization` node
carries full `sameAs` (Facebook, LinkedIn, Instagram). Impact `(2,1)` — costs
score. All 74 findings have an **empty** `extra`.

**Fix.** Emit only when no matching entity node carries a non-empty `sameAs`.
Attach evidence: the `@type` values examined and how many carried `sameAs`.

**Tests** — `tests/test_entity_sameas.py`
- `test_af1_org_with_sameas_and_author_person_without_is_not_flagged` (the real case)
- `test_af1_no_entity_has_sameas_is_flagged` (adversarial: must still fire)
- `test_af1_evidence_names_the_types_examined`

## AF2 — `REDIRECT_TRAILING_SLASH`: stop reporting a redirect we cause

**Defect.** 147/147 findings differ only by a trailing slash. `normalise_url`
strips it, we fetch the stripped form, the server 301s back to its canonical
slashed form, and we report it. The site's sitemap and every internal link
already use the destination form. 3,590 lifetime findings, all self-inflicted.

**Fix.** Suppress a redirect whose source and target differ **only** by a
trailing slash **when no page on the site actually links to the pre-redirect
form**. The raw (un-normalised) href is available on `ParsedLink.url`, so this is
decidable: if some page really links to `/x` and the site redirects to `/x/`,
that is a genuine inconsistency and stays flagged.

**Tests** — `tests/test_redirect_trailing_slash.py`
- `test_af2_slash_only_redirect_not_linked_by_the_site_is_suppressed`
- `test_af2_slash_only_redirect_that_a_page_really_links_to_is_still_flagged` (adversarial)
- `test_af2_non_slash_redirect_unaffected`

## AF3 — `HEADING_EMPTY`: lxml's non-spec repair invents empty headings

**Defect.** `<h3><p>Text</p></h3>` — invalid but common (Elementor). lxml closes
the `h3` at the `<p>`, producing an empty heading. `html.parser` and the HTML5
spec keep the text inside. Browsers and Google see the text; we report it empty.
17 findings; 12 of 182 pages carry the nesting.

**Fix.** Before judging a heading empty, fall back to the raw HTML: if the
heading's source contains text that lxml relocated, treat it as non-empty. Do
not switch the whole parser to `html5lib` — that is a large behavioural change
across every check and needs its own spec.

**Tests** — `tests/test_heading_empty.py`
- `test_af3_heading_wrapping_a_paragraph_is_not_empty` (the real markup)
- `test_af3_genuinely_empty_heading_is_still_flagged` (adversarial)
- `test_af3_real_fixture_page_reports_no_empty_heading`

## AF4 — `HIGH_CRAWL_DEPTH`: sitemap seeding permanently pins depth to None

**Defect.** Sitemap URLs are seeded with depth `None`; link discovery then
refuses to overwrite (`if norm not in depth_map`). 255 of 256 pages end with
`crawl_depth = NULL`, so the check cannot fire. Dead on any site with a sitemap.

**Fix.** Let link discovery fill in a depth that is still unknown:
`if depth_map.get(norm) is None:`. First-arrival semantics for *known* depths are
unchanged.

**Tests** — `tests/test_crawl_depth.py`
- `test_af4_sitemap_seeded_page_gets_depth_from_link_discovery`
- `test_af4_shallowest_depth_still_wins` (adversarial: no regression)
- `test_af4_deep_page_emits_high_crawl_depth`

## AF5 — `DOCUMENT_PROPS_MISSING`: PDF branch sits below an early return

**Defect.** `parse_page` returns a minimal record when `result.html` is falsy.
PDFs carry `.content`, not `.html`, so the `pdf_metadata` branch 60 lines below
never runs. 552 PDFs crawled, 0 metadata, 0 firings — while the extractor works
when called directly.

**Fix.** Compute `pdf_metadata` (and a correct `response_size_bytes`) **before**
the early return, and carry both into the minimal record.

**Tests** — `tests/test_pdf_metadata.py`
- `test_af5_pdf_metadata_survives_the_non_html_path`
- `test_af5_pdf_response_size_is_recorded`
- `test_af5_document_props_missing_fires_for_a_pdf_without_title`

## AF6 — image `technical_score` of 0 means "not measured"

**Defect.** Dimensions are never collected, so `tech = 0` is stored and rendered
as an empty score bar for every image. The overall score correctly drops the
component; the raw 0 still reaches the UI.

**Fix.** Persist `technical_score = None` when `has_tech_data` is false; render
"not measured" rather than a zero bar.

**Tests** — `tests/test_image_scores.py` + `ImageAnalysisPanel.test.jsx`
- `test_af6_technical_score_is_none_without_dimensions`
- `test_af6_technical_score_is_scored_when_dimensions_exist` (adversarial)
- panel renders "not measured", not a 0 bar

## AF7 — the four dead checks: wire, fix, or delete

| Code | Action |
|---|---|
| `AI_BOT_TABLE_STALE` | Wire `validate_table_freshness()` into the site-level AI-readiness path and emit the code. Move the cadence to config; the docstring says 6 months while the constant says 365 days. |
| `CODE_BLOCK_MISSING_TECHNICAL` | `_has_numbered_steps` ignores its `headings` argument and greps a line-anchored regex against single-line text. Use the headings, and match numbered steps without requiring a line start. |
| `CONTENT_IMAGE_HEAVY` | Unreachable: max 20 deductions against a 50 threshold. Either raise `image_heavy` to a reachable weight or delete the code and its catalogue/help/doc entries. **Chosen: delete** — the signal is already covered by `AI_NO_VISUAL_COMPANION` and `AI_MAIN_CONTENT_LOW_RATIO`. |
| `SCHEMA_DEPRECATED_TYPE` | `_DEPRECATED_SCHEMAS = {"Breadcrumb"}` with a comment admitting it is not deprecated, and exact matching means the real `BreadcrumbList` never triggers. Move the list to config and populate it with genuinely deprecated types, or delete. **Chosen: move to config, empty by default**, so the check is honest rather than fake. |

**Tests** — one per row, each asserting the new behaviour and mutation-proved.

## Deferred, with reasons

- **Image download pipeline** (unblocks `IMG_NO_SRCSET`, `IMG_OVERSCALED`,
  `IMG_DUPLICATE_CONTENT`, `IMG_SLOW_LOAD`). Downloading every image is a
  crawl-time and bandwidth decision the owner should make, not a bug fix. AF6
  makes the current state honest. A follow-up spec should propose a bounded
  download (top-N by page weight, size-capped) behind a setting.
- **Switching the HTML parser to `html5lib`** — the correct long-term answer to
  AF3, but it changes the input to every check at once. Needs its own spec and a
  before/after diff on a real crawl.
- **`UNSAFE_CROSS_ORIGIN_LINK` rename, `BROKEN_LINK_503` shortener handling, and
  the three narrow checks** — fold into the V1 authority pass, where each code
  must cite the standard it enforces.

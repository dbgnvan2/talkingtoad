# Micro-spec E7: Give the report a remediation roadmap and an honest scope statement

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: `api/services/report_generator.py`, `api/services/excel_generator.py`,
new `api/config/remediation_owners.json`

## Problem

TalkingToad's PDF ends at findings. A client-facing audit has to answer three more questions,
and the external audit of the same site answered all three:

1. **Who does this, and when?** Every item there carried Owner / Impact / Effort / Confidence,
   a phase (0–30 / 31–60 / 61–90 days), and a testable **"done when"** criterion — for example
   *"done when all nine 4xx targets have an approved restore/remove/redirect decision and the
   crawl reports no internal 4xx links."* TalkingToad's "What to Do Next" is an unordered
   checklist of issue names with no owner, no sequence and no exit condition.
2. **What was not checked?** The external audit devoted a page to caveats — third-party
   estimates flagged as estimates, the crawl allowance stated, and an explicit list of what was
   never reviewed. TalkingToad states nothing, which invites the reader to assume the audit is
   complete. Section 22 of that report is the reason a reader trusts sections 1–21.
3. **How confident are you?** TalkingToad already computes an evidence tier per AI-readiness
   finding (Established / Reasonable proxy / Heuristic) — a genuinely better answer than the
   external audit's unexplained "58/100" — but it appears only as a paragraph of prose in the
   AI-readiness section, not against each finding.

TalkingToad already holds every input for (1): `impact`, `effort`, `priority_rank`,
`fixability`, `category`, plus prevalence from E4 and traffic from E3. Nothing needs to be
invented — only assembled.

## Change

### E7.1 — "Remediation Roadmap" section

Replaces "What to Do Next". Rows are grouped into three phases and each carries
Owner / Impact / Effort / Pages affected / Done when.

- **Phase 1 — Stabilise (0–30 days):** systemic defects (E4) and anything `fixability` marks
  as one template edit.
- **Phase 2 — Repair priority pages (31–60 days):** findings on pages in the top quartile of
  the E3 priority queue.
- **Phase 3 — Expand (61–90 days):** everything else, ordered by `priority_rank`.

Phase boundaries are derived, not decorative: an item is Phase 1 **because** it is systemic,
Phase 2 **because** the page earns traffic. If E4 and E3 are not both approved, phases collapse
to `priority_rank` order and the section says so rather than implying a weighting it did not
apply.

**Owner** maps from `category` + `fixability` via `api/config/remediation_owners.json`
(rule 9 — editorial):

```json
{
  "by_category": {
    "metadata": "SEO / content", "headings": "SEO / content",
    "broken_link": "Web administrator + content", "redirect": "Web administrator",
    "crawlability": "SEO + web administrator", "security": "Web administrator",
    "images": "Content + web administrator", "ai_readiness": "SEO / content",
    "analytics": "Analytics owner", "semantic_html": "Developer",
    "url_structure": "Web administrator", "sitemap": "SEO"
  },
  "default": "Web administrator"
}
```

**Done when** comes from a new `done_when` field on `_IssueSpec`, written as a
**countable, re-crawlable** condition — "a re-crawl reports 0 pages with `META_DESC_MISSING`",
not "descriptions improved". Codes without one fall back to "a re-crawl no longer reports this
code on the affected pages", which is countable by construction. This makes every criterion
verifiable by re-running the tool, which is the one thing TalkingToad can offer that a
consultant's PDF cannot.

### E7.2 — "Scope, Method and Caveats" section

Placed last, and always rendered — including when everything is clean.

- **Covered:** pages crawled, content types included, date, robots/sitemap status, whether
  JavaScript rendering was on, scoring model version (`scoring_model_version` on the job).
- **Every cap that bit**, with numbers, sourced from the counters E1.4 and E2.2 introduce:
  "analysed 150 of 1,284 images", "checked 500 of 812 external links", "listed 50 of 120
  linking pages". A cap that did not bite is not mentioned.
- **Not checked**, stated plainly: off-site authority, backlinks and directory listings;
  Core Web Vitals and field performance data; server logs; CMS/plugin configuration; WCAG
  conformance; anything requiring authenticated access. Each with one line on why, so the
  reader can decide whether they need it elsewhere.
- **Data sources and periods** for any performance figures (E3), naming GSC/GA4 and the
  period, so first-party data is never confused with an estimate.
- **What the scores mean**, in one sentence each: Health, Agent Health, Site Hygiene (E4),
  citability grade. Including that they are prioritisation aids and do not forecast rankings
  or traffic.

### E7.3 — Evidence tier against each finding

Every issue detail block prints its confidence tier inline. The tier is already computed
(`_AI_READINESS_CONFIDENCE`, `registry.py:418+`); today it is explained in a preamble and then
not shown per finding. Codes outside the AI-readiness set fall back to their severity, exactly
as `/pages/issues` already does for the agent-issue list — reusing that mapping rather than
inventing a parallel one.

### E7.4 — Never imply a section is empty because the site is clean

Where a section is omitted for lack of data (no ledger, no images collected), the Caveats
section records the omission by name. A missing section must never read as a passed check —
that is the P2 rule applied to the report surface.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| E7.1a | Roadmap groups into three phases; a systemic defect lands in Phase 1 | `tests/test_report_roadmap.py::test_e7_1a_systemic_in_phase_one` |
| E7.1b | A finding on a top-quartile traffic page lands in Phase 2 | `…::test_e7_1b_high_traffic_page_in_phase_two` |
| E7.1c | Without E3/E4 data, phases collapse to `priority_rank` and the section says so | `…::test_e7_1c_graceful_without_priority_data` |
| E7.1d | Every row has a non-empty Owner and a Done-when | `…::test_e7_1d_every_row_has_owner_and_done_when` |
| E7.1e | Every `done_when` is countable — matches the re-crawl-assertable grammar | `…::test_e7_1e_done_when_is_countable` |
| E7.1f | Owner config covers every category in `CATEGORY_DISPLAY` (no silent `default`) | `…::test_e7_1f_owner_map_covers_all_categories` |
| E7.2a | Caveats section present on a clean site with zero issues | `tests/test_report_generator.py::test_e7_2a_caveats_always_rendered` |
| E7.2b | A cap that bit is reported with both numbers | `…::test_e7_2b_caps_disclosed_with_counts` |
| E7.2c | A cap that did not bite is not mentioned | `…::test_e7_2c_unbitten_cap_silent` |
| E7.2d | "Not checked" list names off-site, CWV, server logs, CMS config, WCAG | `…::test_e7_2d_not_checked_list_complete` |
| E7.3a | Each issue block prints its tier; non-AI codes fall back to severity | `…::test_e7_3a_confidence_tier_per_finding` |
| E7.4a | Ledger absent → Performance section omitted **and** named in Caveats | `tests/test_report_integration.py::test_e7_4a_omission_recorded_in_caveats` |
| E7.4b | Zero images collected → Image Health omitted, named in Caveats, no "97%" printed | `…::test_e7_4b_no_image_score_without_images` |

Fix→test map (P10): **E7.4a and E7.4b first.** They are the honesty guarantees — the two
places where a silent omission would otherwise read to a client as a clean bill of health.
E7.4b is the direct report-surface consequence of the E1 bug and must not be able to recur.

## Frontend surfaces (P25)

| Surface | Must show | Test |
|---|---|---|
| PDF | Roadmap + Caveats | `tests/test_report_integration.py` (above) |
| Excel | Roadmap tab with the same columns | `tests/test_excel_generator.py::test_e7_excel_roadmap_tab` |
| Results GUI | phase grouping in Fix Focus | `frontend/src/components/__tests__/FixFocusPhases.test.jsx` |

## Adjacent issues found, not fixed (rule 10)

- `_IssueSpec` gains `done_when` for 152 codes. Writing all 152 well is editorial work; the
  spec's fallback makes a partial rollout safe, but a half-filled field will look like an
  oversight in the PDF. Recommend filling the ~40 codes that actually reach a client report
  first and tracking the rest.
- The PDF has no table of contents. At 52 pages today — and longer after E3/E4/E7 — that is
  a real usability problem. Flagged; not in this spec.

## Out of scope

Generating proposed replacement copy (titles, descriptions, H1s, lead paragraphs) for priority
pages. TalkingToad has `advisor.py` and `rewriter.py` and could do it, but drafting client-
facing copy inside an audit report is a product decision, not a reporting fix — see the
umbrella plan's deferred items.

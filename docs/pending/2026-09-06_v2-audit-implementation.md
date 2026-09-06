# v2 Audit Framework — IMPLEMENTATION SPEC (hand this to Claude Code)

**Date:** 2026-09-06
**Status:** APPROVED IN PRINCIPLE (owner, 2026-09-06). **Revised 2026-09-06 after a code-verified review — see "Revision r1" below.** Implement item-by-item per the repo workflow below.
**Spec IDs:** V2-PERF, V2-A11Y, V2-ENTITY, V2-LINK, V2-DECIDE, V2-AEO (P0); V2-A11Y-P1, V2-PERF-P1, V2-ANALYTICS (P1); V2-TYPO, V2-MOBILE (P2, deferred).

**Extends:** `api/crawler/checkers/registry.py` (source of truth), `api/crawler/parser.py`, the `checkers/` package, `frontend/src/data/issueHelp.json`, `api/models/issue.py`, `api/routers/crawl.py`, `api/services/job_store_base.py`.
**Relates to:** `V2-RESEARCH.md` (strategy), `docs/pending/2026-09-06_v2-audit-framework.md` (the approved umbrella).

> **Revision r1 (2026-09-06)** — every mechanical claim in §0 was checked against the code and holds. Six substantive corrections were folded in, each verified at a named file:
> 1. **`ORG_LOGO_MISSING` withdrawn** — already emitted as `ENTITY_NAP_INCOMPLETE` (`entity_values.json` → `nap_required_fields.organization: ["url", "logo"]`). P0 is now five codes, not six. (§1)
> 2. **`needs_full_crawl` corrected to `True`, and `scope="site"` added,** for the two entity codes — they are emitted from `cross_page.py`, and an AST-walking test binds that flag to that file. As drafted they would have turned the suite red on the first run. (§0.6, §1)
> 3. **The entity codes are site-scoped, emitted once** — not once per page. Per-page emission multiplies one settings error across the whole crawl (R5.1). (§1)
> 4. **`LOW_INBOUND_LINKS` gated on `link_graph_complete`**, with the suppression disclosed — it is an absence-inference over the same link graph as `ORPHAN_PAGE`, which is where this repo measured P31. (§1)
> 5. **`ORG_LEGAL_NAME_INCONSISTENT` → `ORG_LEGAL_NAME_MISSING`**, casing rule dropped — it contradicted `_normalise_org_name`, which strips casing deliberately. (§1)
> 6. **`IMG_MISSING_DIMENSIONS` reads the already-parsed signal** and defers to a measured CLS; its self-contradictory detection rule is resolved. (§1)
>
> Two owner decisions were confirmed unchanged: all P0 codes stay **info/Notable** (severity is a derived claim about SEO effect size, not about legal exposure — accessibility weight belongs in the explainer copy, and `_IMPACT_OVERRIDES` is the lever if that is ever revisited), and the **AEO relabel stays copy-only** (§4).

---

## 0. Read this first — invariants you must not break

The repo is extremely strict, and the CI/parity tests will reject a wrong registration. Before writing code:

1. **Read `CLAUDE.md`** (the rulebook) and **`LEARNINGS.md`** (failure-pattern checklist) — both in the repo root. They are binding.
2. **Source of truth is `api/crawler/checkers/registry.py`.** A code must be registered in all of:
   - `_CALIBRATION` (the `(confidence, effect_size, measured)` tuple — this **derives** the impact)
   - `_ISSUE_SCORING` (the `(impact, effort)` tuple — impact **must equal** `derive_impact(code)`)
   - `_CATALOGUE` (the `_IssueSpec` — category, description, recommendation, scope, `needs_full_crawl`, the four help text fields, fixability)
   `make_issue()` raises `KeyError` for an unregistered code. There is no silent fallback.
3. **Severity and impact are DERIVED, never hand-set to a different value.**
   - `derive_impact(code)` = `_IMPACT_OVERRIDES[code]` if present, else `_MEASURED_MATRIX[eff]` if `measured` else `_IMPACT_MATRIX[(confidence, eff)]`.
   - There is a fourth lane the draft omitted: `_PAGE_FATAL_10` returns 10 for a code in that frozenset with `("Established", "large")`. It holds three codes and none of the new ones qualify — noted so the formula above is not read as complete.
   - `_IMPACT_MATRIX` = Heuristic{0,1,2,3} / Reasonable proxy{0,2,4,6} / Established{0,2,6,9} for {none,small,moderate,large}.
   - `severity_from_impact(impact)` = critical ≥8, warning ≥4, else info.
   - `test_r5_severity.py` pins all codes' stored severity to `severity_from_impact(derive_impact(code))`.
   So: **pick the `_CALIBRATION` tuple, and let the impact fall out of the matrix.** The table in §1 gives the correct tuple and its resulting impact/severity — do not change the tuple without changing the spec.
4. **Four files stay in sync** (parity tests fail otherwise):
   - `_CATALOGUE` / `_ISSUE_SCORING` / `_CALIBRATION` (registry.py)
   - `frontend/src/data/issueHelp.json` (authored, seven-part explainer — style in `docs/explanation-style-guide.md`)
   - the generated Python help copy (`api/services/issue_help_data.py` — regenerate via its generator script)
   - `docs/issue-codes.md` (regenerate via `python scripts/generate_issue_codes_doc.py`)
   Also `frontend/src/data/categories.generated.json` (regenerate via `python scripts/generate_categories_json.py`) when categories change.
5. **`CATEGORY_DISPLAY`** in registry.py is the single source for category order+labels; its key set must equal the set of categories `_CATALOGUE` emits (`tests/test_frontend_backend_code_parity.py`). Adding a category ⇒ add it to BOTH `IssueCategory` (in `api/models/issue.py`) and `CATEGORY_DISPLAY`.
6. **`needs_full_crawl=True`** on any code that cannot be produced by a single-page scan. It is read by `tests/test_single_page_scan_discloses_inert_checks.py`; do not mirror the list anywhere else.
   **This is mechanically enforced, not a judgement call:** `test_registry_flag_matches_cross_page_emitters` **AST-walks `api/crawler/checkers/cross_page.py`** and asserts the flag matches what that file actually emits. Any code emitted from `cross_page.py` — which includes every `ENTITY_*` code and everything inside `check_cross_page` — **must** be `needs_full_crawl=True`, or that test turns red. The single-page path never calls `check_cross_page`.
   Separately, `scope` (`"page"` vs `"site"`) governs how a finding is **charged** once found. Every existing `ENTITY_*` code is `scope="site"`; new site-fact codes must match, or one settings error is charged on every page of the crawl.
7. **Tests are mandatory** (CLAUDE.md): unit tests for detection, an **adversarial test** per text/scoring function (an input that looks like a hit but is not), API-contract tests **before** frontend code. Run with `./venv/bin/python -m pytest tests/ -q` — both interpreters 3.11 and 3.14 in CI.
8. **Version bumps (both):** adding codes changes the scoring model AND which rows a crawl emits. Bump `SCORING_MODEL_VERSION` (→ `2026-09-06-r7`) and `ISSUE_EMISSION_VERSION` (→ `2026-09-06-e2`) in registry.py.
9. **Per-item completion** (CLAUDE.md): implement + test in one cycle → fold the approved spec into `docs/functional-specification.md` → add any numeric bounds to `docs/thresholds.md` → update `PLAN-V4.0.md` if a code ships a V4 explainer → `git push origin main`.
10. **WordPress safety constraints unchanged** (no URL changes via WP API, no automated image-link updates).

---

## 1. P0 — the five new issue codes

All five land at **impact 2 → severity info, tier "Notable"**. That is deliberate: these are "worth fixing" findings, not page-fatal faults, consistent with the repo's recalibration ("only page-fatal problems surface as Critical"). Do not inflate them.

> **`ORG_LOGO_MISSING` was withdrawn at review (2026-09-06) — do not implement it.**
> `api/config/entity_values.json` already sets `nap_required_fields.organization: ["url", "logo"]`, and `_check_nap` (`cross_page.py`) applies that set to **every** Organization/LocalBusiness/Place node unconditionally. A missing `logo` therefore already emits `ENTITY_NAP_INCOMPLETE` today, at impact 6 / warning. The withdrawn code's own rationale ("complements `ENTITY_NAP_INCOMPLETE`, which covers address/phone/name") was factually wrong: NAP covers address/telephone/email for *premises* **plus** url/logo for *every* org node. Adding a second, weaker (impact 2) code for the same fact would double-count it in the score and put two implementations of one predicate in the tree — the class `tests/test_checker_agreement.py` exists to prevent.
> If a dedicated logo finding is ever wanted, it is a **swap, not an addition**: remove `"logo"` from `nap_required_fields.organization` in the same change, and add an agreement test asserting exactly one of the two paths fires.

| # | Code | Category | `_CALIBRATION` tuple | Impact → Sev | Effort | Fixability | `needs_full_crawl` | `scope` |
|---|---|---|---|---|---|---|---|---|
| 1 | `IMG_MISSING_DIMENSIONS` | `performance` | (`"Reasonable proxy"`, `"small"`, `False`) | 2 → info | 1 | `content_edit` | False | `page` |
| 2 | `FORM_FIELD_NO_LABEL` | `accessibility` | (`"Established"`, `"small"`, `False`) | 2 → info | 1 | `content_edit` | False | `page` |
| 3 | `ORG_LEGAL_NAME_MISSING` | `ai_readiness` | (`"Reasonable proxy"`, `"small"`, `False`) | 2 → info | 2 | `content_edit` | **True** | **`site`** |
| 4 | `LOCAL_BUSINESS_FIELD_INCOMPLETE` | `ai_readiness` | (`"Reasonable proxy"`, `"small"`, `False`) | 2 → info | 1 | `content_edit` | **True** | **`site`** |
| 5 | `LOW_INBOUND_LINKS` | `crawlability` | (`"Reasonable proxy"`, `"small"`, `False`) | 2 → info | 2 | `content_edit` | **True** | `page` |

**Why 3, 4 and 5 are `needs_full_crawl=True`:** they are emitted from `cross_page.py`, which the single-page path never calls. `tests/test_single_page_scan_discloses_inert_checks.py::test_registry_flag_matches_cross_page_emitters` **AST-walks `cross_page.py`** and binds the flag to what that file actually emits — registering any of them `False` turns that test red on the first run. See §0.6.

**Why 3 and 4 are `scope="site"`:** every existing `ENTITY_*` code is `scope="site"` and emitted **once**, at the representative page. See the emission rule below.

### Site-scoped emission — codes 3 and 4 (mandatory)

`_check_entity_values` emits **one finding per site**, at the start URL's page (falling back to the shallowest page carrying an entity node). Its docstring states why: *"These are site facts, not page facts: charging them per page would multiply one settings error across the whole crawl (R5.1)."* A Yoast `Organization` node appears in the JSON-LD of **every** page, so per-page emission would turn one settings mistake into 272 findings on livingsystems.ca.

Codes 3 and 4 are site facts of exactly this kind. Emit them from inside `_check_entity_values`, at the same `rep` URL, alongside `ENTITY_NAP_INCOMPLETE` — **not** once per page. A test must assert this: a three-page fixture where all three pages carry the same incomplete `LocalBusiness` node yields **exactly one** finding of each code.

### Detection semantics (precise)

**1. `IMG_MISSING_DIMENSIONS`** — for every `<img>` that does not declare **both** a width and a height, emit one finding per page with `extra={"count": N, "examples": [src…][:5]}`. Skip pages with `status_code >= 400`. Do NOT read CSS; this is a static attribute check.

> **Contradiction in the pre-review draft, resolved here.** Its prose said "neither a non-empty `width` nor `height`" (an AND-condition: flag only when both are absent) while its own adversarial test said a half-declared image "must still count" (an OR-condition). The test is right and the prose was wrong: a browser needs **both** dimensions to derive an aspect ratio and reserve space, so `width` alone reserves nothing and shifts layout exactly as no attribute would. The condition is OR. The code name and description must say "does not declare both", not "has no dimensions".

*Read the signal that already exists — do not add a parallel one.* `api/crawler/parser.py` already stores `rendered_width` / `rendered_height` on each image record via `_parse_dimension`, which returns `None` for missing, empty and unparseable values alike. The check is `img["rendered_width"] is None or img["rendered_height"] is None` over `page.images`. Adding a new `images_missing_dimensions` field to `ParsedPage` would create a **third** reading of the same attributes — `_detect_decorative` already has its own `int(tag.get("width", 999))` — and the repo keeps `tests/test_checker_agreement.py` precisely because divergent duplicate predicates are a live defect class here. If a new field is genuinely unavoidable, it ships with an agreement test against `rendered_width`/`rendered_height`.

*Reconcile with measured CLS.* `CWV_CLS_POOR` already exists (Established/moderate → impact 6) and is a **measured** value from the performance bundle. `IMG_MISSING_DIMENSIONS` is a static proxy for the same outcome, so a page with a good measured CLS and undeclared dimensions is a known false positive. Required: when a measured CLS is available for the page **and** is not poor, suppress `IMG_MISSING_DIMENSIONS` for that page; state the suppression in the explainer ("the measured value wins"). Where no measurement exists, emit the proxy and name its tier. A test must cover both branches.

*Honest caveat for the explainer:* a theme may reserve space via CSS, so the finding means "no intrinsic dimensions declared in the markup", which *usually* causes layout shift — review, not certain CLS.

*Adversarial test:* an `<img>` with `width` set but `height` missing (or vice-versa) **must** count; an `<img>` with both present must not; an `<img>` with `width="" height=""` must count; an `<img>` with `width="100px"` and `height="60"` must not (both parse); a page with a good measured CLS must not emit.

**2. `FORM_FIELD_NO_LABEL`** — for every `<input>` (excluding `type` in `{submit, button, reset, image, hidden}`), `<select>` and `<textarea>` that has **no proper label**, emit one finding with `extra={"count": N, "examples": [{type, id or name}…][:5]}`. A *proper* label is: a `<label>` whose `for` equals the field's `id`, a wrapping `<label>`, `aria-label`, or `aria-labelledby`. **`placeholder` and `title` do NOT count** (WCAG 1.3.1 / 3.3.2).

This is the deliberate difference from `INTERACTIVE_NO_ACCESSIBLE_NAME`, which *does* accept `placeholder` and `title` as names (`api/crawler/parser.py`, the `unnamed_interactive` signal) because it targets agent operability, not WCAG label compliance. Two codes, two questions, answered differently on purpose. Document the relationship in **both** explainers so they are not read as duplicates, and add an agreement test in `tests/test_checker_agreement.py` pinning the intended divergence: an input carrying only `placeholder` fires `FORM_FIELD_NO_LABEL` and does **not** fire `INTERACTIVE_NO_ACCESSIBLE_NAME`.

Cite the WCAG clause in the explainer's evidence line. The `_IssueSpec` has no `authority` field today; adding one is out of scope here, so the citation lives in the seven-part explainer.

*Adversarial test:* an input with only `placeholder` must still flag; an input with a `<label for="…">` must not; a `type="hidden"` input must not; a submit button must not.

**3. `ORG_LEGAL_NAME_MISSING`** (renamed from `ORG_LEGAL_NAME_INCONSISTENT`) — when an `Organization`/`LocalBusiness` node has `name` present and `legalName` **absent**, emit one **site-scoped** finding. `extra={"name": …}`. Reasonable-proxy basis: schema.org recommends `legalName` where it differs from `name`.

> **The casing half of this check was withdrawn at review.** The draft would have flagged a `legalName` that is "a non-canonical casing of `name`". `cross_page.py` already normalises casing *and* legal suffixes away before comparing organisation names (`_normalise_org_name`, `_ENTITY_LEGAL_SUFFIXES`), annotated "so a casing/suffix-only difference is NOT a false 'inconsistent' (adversarial P7)". Shipping the casing rule would have had two checks give opposite answers about the same node — the shape where whoever implements it writes a test pinning whichever answer they happen to believe. `legalName` is also already in `placeholder_fields`, so its *content* is under E5's eye.
> The code is renamed to match what it now does. If a casing rule is wanted later it is a change to `_normalise_org_name`'s contract, argued on its own, with an agreement test — not a second opinion emitted beside the first.

*Adversarial test:* `legalName` present → no flag (whatever its casing); `legalName` absent → flag; `name` absent → no flag (nothing to compare); three pages carrying the same node → exactly one finding.

**4. `LOCAL_BUSINESS_FIELD_INCOMPLETE`** — when a node is a `LocalBusiness` (or `Organization`+`Place`), flag each **missing** field from a configured list. One **site-scoped** finding listing which are absent: `extra={"missing": ["areaServed", …]}`.

*The field list is config, not code.* Global rule 9 and the E5 precedent put editorial vocabularies in `api/config/entity_values.json`. Add a key beside `nap_required_fields` — e.g. `"local_business_recommended_fields": ["areaServed", "geo"]` — and read it through `_entity_cfg()` (extend `_ENTITY_CFG_KEYS`). `geo` counts as present only with both `latitude` and `longitude`.

*`priceRange` is excluded by default.* It is a Google LocalBusiness rich-result field with little meaning for a nonprofit, which is this tool's whole audience. It may be added to the config list by a site that wants it; it is not in the shipped default. Record this in `docs/thresholds.md` alongside the default list.

Complements — does not overlap — `ENTITY_NAP_INCOMPLETE`, whose required set (`url`, `logo`, `address`, `telephone`, `email`, address subfields) shares no member with this one. A test must assert the two sets are disjoint, so a later edit to either config list cannot silently create a double-count.

*Adversarial test:* all configured fields present → no flag; only `geo` missing → flag with `["geo"]`; `geo` present with `latitude` only → flag; a plain `Organization` (not a premises type) → no flag; three pages carrying the node → exactly one finding.

**5. `LOW_INBOUND_LINKS`** — a page with **exactly one** inbound internal link from the link graph (`ORPHAN_PAGE` = zero, and stays untouched). Emit on the weak page, `extra={"referring_url": …}`.

*This is an absence-inference and must carry its input's completeness (P31 — the pattern this repo measured on `ORPHAN_PAGE` itself).* "Exactly one inbound link" is decidable only over a complete link graph: the second link that would clear a page may live on a page the crawl never fetched, and a narrowed crawl makes the finding count go **up**, not down. The plumbing already exists and must be reused, not re-invented:

- `check_cross_page(..., link_graph_complete: bool = True)` (`cross_page.py`) — emit `LOW_INBOUND_LINKS` **inside the existing `if link_graph_complete:` block**, next to `_check_orphan_pages`. Do not add a second flag.
- `api/crawler/engine.py` sets it from `orphan_status`, which is `skipped_single_page` / `skipped_partial_scan` / `skipped_truncated` / `complete`.
- **Extend the disclosure.** The `orphan_detection` dict and its `orphan_detection_skipped` log event are orphan-only in name and in copy. A suppressed `LOW_INBOUND_LINKS` renders as zero findings, which every surface reads as a clean bill of health. Rename/extend the disclosure so it names **both** suppressed checks, and carry that through to whatever the results page and the PDF render from it. Ship the gate and the honest status in the same change: *"skipped: partial scan, covered N of M pages"*, never a silent zero.
- **Test at the boundary that narrows, not only at the checker** (P31 corollary / P25). A checker test proves the flag *works*; only an engine test proves the flag is *set*. Intercept `check_cross_page` and assert `link_graph_complete=False` arrives for a partial scan, a `max_pages` truncation, and single-page mode.

*Decide and record: `archives_skipped`.* `skip_wp_archives` is on by default and is **disclosed rather than gated** for orphans, because gating on a default-on setting would disable the check on every crawl. That trade-off is weaker here: a *second* inbound link is much more likely to live on a skipped archive than a *first* one, so `LOW_INBOUND_LINKS` is materially noisier under the same caveat. Before implementing, decide explicitly whether it additionally requires `archives_skipped == False`, and write the decision into the spec — do not leave it to the implementer.

*Adversarial test:* zero inbound → `ORPHAN_PAGE` only, never `LOW_INBOUND_LINKS`; two inbound → neither; one inbound → `LOW_INBOUND_LINKS`; a self-link is not an inbound link (mirror `_check_orphan_pages`); `link_graph_complete=False` → **no** finding **and** a stated suppression.

### Where each check is wired

- **1** reads `page.images` (already parsed — see above) from a new `check_performance(page, issues)` in `api/crawler/checkers/`, following `check_semantic_html`'s shape (read precomputed signals, never touch `soup`).
- **2** needs one new precomputed signal on `ParsedPage` (there is no existing WCAG-label signal — `unnamed_interactive` answers a different question). Compute it in `api/crawler/parser.py` where `soup` is in scope, then read it from a new `check_accessibility(page, issues)`. Register both new checker functions wherever the other per-page checkers are invoked.
- **3, 4** go inside `_check_entity_values` in `cross_page.py`, at the same `rep` URL as `ENTITY_NAP_INCOMPLETE`, reading the nodes `_entity_nodes` already yields.
- **5** goes inside the existing `if link_graph_complete:` block in `check_cross_page`, beside `_check_orphan_pages`.

---

## 2. Category changes

- **`accessibility` is the only new enum member.** Add `"accessibility"` to `IssueCategory` in `api/models/issue.py`. `performance` and `mobile` **already exist** in the enum — do not re-add. `schema` and `duplicate` exist too but stay unbuilt (out of scope here).
- Add both new emitted categories to `CATEGORY_DISPLAY` in registry.py, in a sensible position with a human label:
  - `("performance", "Performance")` — after `"rendering"`.
  - `("accessibility", "Accessibility")` — after `"semantic_html"`.
- Regenerate `frontend/src/data/categories.generated.json` (`python scripts/generate_categories_json.py`).
- **Update the stale comment above `PHASE_1_CATEGORIES`** in `api/models/issue.py`. It reads "Phase 2 (performance, mobile, schema) is unbuilt, so every emitted category is a Phase 1 one and the CSV's `phase` column is constant '1'". Shipping a `performance` code makes the first clause false. Behaviour is unaffected — `PHASE_1_CATEGORIES` is *derived* from `_CATALOGUE`, so `performance` simply joins it and the CSV column stays `"1"` — but the comment must not be left asserting something untrue.
- **No change** to `AGENT_READINESS_CATEGORIES` — `performance`/`accessibility` are SEO-side (page experience), so they default to the SEO focus bucket, which is correct. Do not add them to the GEO bucket.

---

## 3. V2-DECIDE — the "Decisions to resolve" surface

A first-class, non-crawl output enumerating facts only the organisation can decide. **Not scored, never a defect.**

**Model** (`api/models/`, mirror existing Pydantic patterns):
```
SiteDecision {
  key: str              # stable identifier, e.g. "legal_name"
  question: str         # the decision, one sentence, plain English
  why_it_matters: str   # one sentence
  derived_from: list[str]   # crawl facts / issue codes that triggered it (may be [])
  status: "open" | "resolved"
  resolved_at: str | None
}
```

**Question bank** — a curated static list, each with a trigger rule evaluated against the crawl. Seed (from the Living Systems audit §12–§13; keep plain-English, no jargon):
1. `legal_name` — "Confirm the exact legal organisation name and the public name to use in schema, footer and directories." Trigger: always (or when an Organization node exists).
2. `address_type` — "Confirm whether the street address is customer-facing, administrative, or mailing-only, and the service area to publish." Trigger: `LocalBusiness`/`Organization` node with an address.
3. `public_hours` — "Confirm real public/office hours, or suppress opening-hours schema." Trigger: `ENTITY_HOURS_DEFAULT` present.
4. `archive_indexability` — "Decide which archives (author, category, tag, event, training, team) should rank." Trigger: always.
5. `conversion_forms` — "Identify which forms/platforms represent a completed inquiry, registration or donation." Trigger: a form or outbound conversion link detected (`CTA_TRACKING_MISSING` / `OUTBOUND_LINK_UNTRACKABLE` present).
6. `content_reviewers` — "Name who reviews content before publish (clinical/training/editorial)." Trigger: always.
7. `legacy_links` — "Inventory legacy backlinks/listings pointing at old URLs (contact, donation, newsletter, removed articles)." Trigger: redirects detected (`REDIRECT_301`/`REDIRECT_CHAIN` present).
8. `hosting_backups` — "Confirm hosting provides offsite backups, object/opcode cache, WAF, and a documented restore process." Trigger: WordPress audit has been run (or always, marked as needing the audit).

**Endpoints** (auth required, like every `/api` route except `/health`):
- `GET /api/crawl/{job_id}/decisions` → `{decisions: [SiteDecision…], generated_at, …}` — returns all bank items with their trigger-flag and status (an item whose trigger is false still appears, with `derived_from: []` — "not triggered by this crawl" is stated, never hidden).
- `POST /api/crawl/{job_id}/decisions/{key}/resolve` → toggles `status`; persists. Reversible.

**Storage:** persist `status`/`resolved_at` in the job store (SQLite) — add a `decisions` table or a JSON column on the job; follow the store's existing patterns. Unresolved state must survive a rescan.

**Frontend:** a "Decisions" panel/tab on the results page (a sibling of the existing panels). Lists each decision with its trigger evidence and a resolve toggle. Explicitly labeled "Not part of your health score."

**Export:** a "Decisions to resolve" section in the PDF (`report_generator.py`) and a sheet/column in the Excel export.

**Tests (before any frontend code):** `tests/test_decisions_surface.py` — response schema (every field the frontend reads), empty-site case (all items present, none triggered), auth (401 without token), resolve→persist→survive-rescan round-trip, and the "untriggered item is stated, not hidden" assertion.

---

## 4. V2-AEO — honest engine-scope labels (copy only, no scoring change)

Google's AI-optimization guide (2026-07-10) explicitly states it does **not** use `llms.txt`, "chunking", or special AI markup/markdown. Those signals **do** matter to ChatGPT, Perplexity, and other agents.

- **Find the full set** by grepping the codebase for `llms.txt`, `ai.txt`, and `chunk`. The codes are at minimum: `LLMS_TXT_MISSING`, `LLMS_TXT_INVALID`, `CHUNKS_NOT_SELF_CONTAINED` (and `AI_TXT_MISSING` if it is an llms/ai.txt signal).
- For each, **edit the seven-part explainer in `issueHelp.json`** to add one honest sentence (in `impact` or `how_it_can_mislead`) to this effect: *"Google has stated it does not use this signal for its AI features; this matters for ChatGPT, Perplexity and other agents/answer engines."* Keep the code name, category, and scoring unchanged.
- Regenerate the Python help copy so the panel and the PDF carry the same wording (one source — the repo's own rule against two phrasings of one fact).
- **Do not** relabel the answer-engine-pattern codes (`CENTRAL_CLAIM_BURIED`, `GEO_SUMMARY_BURIED`, `CONVERSATIONAL_H2_MISSING`, etc.) — Google does not disavow clear structure/answer-first content; those stay.

---

## 5. P1 — summarized (implement after P0 is green and pushed)

- **`FORM_ERROR_NO_ANNOUNCE`** (`accessibility`) — `("Heuristic","small",False)` → 1 info/Low. Form with client-side validation attributes (`required`, `pattern`, etc.) but no `aria-describedby`/`role=alert` on the error path. Clearly heuristic.
- **`IMG_LAZYLOAD_MISSING`** (`performance`) — `("Reasonable proxy","small",False)` → 2 info. Non-first `<img>` (in document order) without `loading="lazy"`. Heuristic (below-fold is approximate). State the tier.
- **`CONTRAST_RATIO_LOW`** (`accessibility`) — `("Established","small",False)` → 2 info, effort 3. Text/background contrast < WCAG 4.5:1, **computed styles only** — post-crawl, opt-in (like the WordPress audit), never a silent skip; "not measured" renders as *not checked*.
- **`FOCUS_INDICATOR_REMOVED`** (`accessibility`) — `("Heuristic","small",False)` → 1 info. `outline:none`/`outline:0` without a replacement focus style. Heuristic.
- **`V2-ANALYTICS`** — an opt-in, read-only "Analytics configuration audit" (conversion events, cross-domain/outbound measurement, 404 event), mirroring `api/services/wp_audit.py`'s capability-probe + `not_inspected` boundary.

## 6. P2 — deferred (needs further design; do NOT implement in this pass)

- **`TYPO_SUSPECTED`** — dictionary spellcheck over URL slugs (item 7 `/dontation_form/`). High false-positive risk (names, loanwords). Default off via a scan setting. Requires a design decision on the dictionary + a measured FP rate before it ships.
- **`V2-MOBILE`** — tap-target size / mobile usability via the render path. Needs measurement infrastructure.

---

## 7. Acceptance criteria (all P0 must satisfy before "done")

1. Every P0 code is registered in `_CALIBRATION` + `_ISSUE_SCORING` + `_CATALOGUE`; `make_issue` emits it; impact equals `derive_impact(code)` (the `test_r5_severity` and catalogue-scoring parity tests pass).
2. `ORG_LOGO_MISSING` is **not** registered (withdrawn at review — §1). P0 ships **five** codes.
3. Every P0 code has a full seven-part `issueHelp.json` entry following `docs/explanation-style-guide.md`, the generated Python copy is regenerated, and `docs/issue-codes.md` + `categories.generated.json` are regenerated — all parity tests green.
4. Each P0 code ships its unit test **plus** the adversarial test specified in §1 (the input that looks like a hit but is not).
5. `LOW_INBOUND_LINKS`, `ORG_LEGAL_NAME_MISSING` and `LOCAL_BUSINESS_FIELD_INCOMPLETE` are all `needs_full_crawl=True`; `test_registry_flag_matches_cross_page_emitters` and the single-page-scan disclosure test both pass.
6. The two entity codes are `scope="site"` and emit **once** per crawl — proved by a multi-page fixture carrying the same node on every page, asserting exactly one finding of each.
7. `LOW_INBOUND_LINKS` emits only inside the existing `if link_graph_complete:` block. A partial scan, a `max_pages` truncation and single-page mode each yield **no** finding **and** a stated suppression that names the check — never a silent zero. An engine-level test intercepts `check_cross_page` and asserts `link_graph_complete=False` arrives in all three cases (P31 corollary: test the stage that narrows, not only the gate).
8. The `archives_skipped` decision for `LOW_INBOUND_LINKS` is written into this spec **before** implementation begins, not left to the implementer.
9. `IMG_MISSING_DIMENSIONS` reads `page.images`' existing `rendered_width`/`rendered_height`, and is suppressed on any page with an available, non-poor **measured** CLS. Both branches are tested.
10. `LOCAL_BUSINESS_FIELD_INCOMPLETE`'s field list lives in `api/config/entity_values.json` (not in Python), `priceRange` is absent from the shipped default, and the default list is recorded in `docs/thresholds.md`.
11. Three agreement tests exist in `tests/test_checker_agreement.py`: `IMG_MISSING_DIMENSIONS` against `rendered_width`/`rendered_height`; `FORM_FIELD_NO_LABEL` against `INTERACTIVE_NO_ACCESSIBLE_NAME` (pinning the intended placeholder divergence); and `LOCAL_BUSINESS_FIELD_INCOMPLETE`'s configured field set disjoint from `nap_required_fields`.
12. The stale `PHASE_1_CATEGORIES` comment in `api/models/issue.py` is corrected in the same change (§2).
13. The Decisions surface ships with `tests/test_decisions_surface.py` (contract) written and passing **before** its frontend panel exists; the panel is added only after.
14. Heuristic/lower-confidence findings name their evidence tier on screen and in the PDF; a measurement that could not be made renders *not checked*, never clean (repo P2 rule).
15. `SCORING_MODEL_VERSION` = `2026-09-06-r7` and `ISSUE_EMISSION_VERSION` = `2026-09-06-e2` are bumped; `docs/functional-specification.md` and `docs/thresholds.md` are folded; `PLAN-V4.0.md` tallies any shipped V4 explainer; `git push origin main` after each item.
16. Full suite green on **both** interpreters (3.11 and 3.14) via `./venv/bin/python -m pytest tests/ -q`.

## 8. Explicit non-goals

- No off-site authority (local listings, backlinks, outreach) — paid third-party data, declined in `docs/overview.md`.
- No crawl-budget/server-log analysis.
- No WordPress-specific checks in the crawl (WP stays in the opt-in audit).
- No content-*quality* scoring beyond the existing LLM advisory.
- No URL-changing or image-link-updating automation (standing WP safety constraints).
- No changes to `schema`, `mobile`, or `duplicate` categories in this pass (they remain reserved).

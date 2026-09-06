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


> **Revision r2 (2026-09-06)** — a second, independent failure-pattern sweep over r1 found nine more, three of them blocking. Two were introduced *by* r1's own fixes, which is why they are called out here rather than folded in silently:
> 1. **A fifth registration surface was missing, and r1 asserted it did not exist.** `api/crawler/checkers/data/authority.yaml` holds exactly 170 entries — one per catalogue code — enforced by `tests/test_authority.py`. r1's §1 said "the `_IssueSpec` has no `authority` field today, so the citation lives in the explainer": the field's absence is true, the conclusion was wrong, and following it would have turned the suite red and labelled the one standards-backed new check a heuristic. A **sixth** surface, `_AI_READINESS_CONFIDENCE`, is also required for the two `ai_readiness` codes. Both are now in §0. (§0.2, §0.4, §1.2)
> 2. **The measured-CLS suppression r1 added cannot exist where r1 wired it.** `CWV_CLS_POOR` is produced only by `api/services/web_vitals.py`, from opt-in post-crawl CrUX field data over the top-N pages; at per-page check time no CLS exists for any page, ever. r1 also made it an acceptance criterion, which would have forced a green test over a branch the run path cannot reach. Replaced with an honest limitation. (§1.1, §7)
> 3. **The Decisions surface's storage could not meet its own stated requirement** — "survive a rescan", keyed per job, when a rescan mints a new `job_id`. Now keyed on `domain`, with the test specified as a real rescan. (§3)
> 4. Decorative images are not addressed by `IMG_MISSING_DIMENSIONS` — the same class as this repo's 156-finding `IMG_ALT_MISSING` false positive. (§1.1)
> 5. `IMG_LAZYLOAD_MISSING` (P1) re-implemented a parser predicate one field away from the two r1 told it to reuse. (§5)
> 6. `LOW_INBOUND_LINKS`'s suppression has **four** disclosure homes, not two, none of which render a `crawlability` finding — and `orphan_detection` is a persisted column, so r1's "rename/extend" would blank historical jobs. (§1.5)
> 7. `CONTRAST_RATIO_LOW` has no computed-style producer and implies an undeclared dependency — moved to P2 beside `V2-MOBILE`, which was already deferred for the same reason. (§5, §6)
> 8. Codes 3 and 4 inherit a representative-page scope that silently no-ops when the entity node is not on the homepage. (§1.3, §1.4)
> 9. "measured" was used in two senses across §0.3 and §1. (§0.3)
>
> The distribution is worth recording: §1, the only section with prior review, still yielded three findings, and §3/§5, the least reviewed, yielded four. Read that as the review having been thorough, not those sections being clean.

---

## 0. Read this first — invariants you must not break

The repo is extremely strict, and the CI/parity tests will reject a wrong registration. Before writing code:

1. **Read `CLAUDE.md`** (the rulebook) and **`LEARNINGS.md`** (failure-pattern checklist) — both in the repo root. They are binding.
2. **Source of truth is `api/crawler/checkers/registry.py`.** A code must be registered in all of:
   - `_CALIBRATION` (the `(confidence, effect_size, measured)` tuple — this **derives** the impact)
   - `_ISSUE_SCORING` (the `(impact, effort)` tuple — impact **must equal** `derive_impact(code)`)
   - `_CATALOGUE` (the `_IssueSpec` — category, description, recommendation, scope, `needs_full_crawl`, the four help text fields, fixability)
   - `_AI_READINESS_CONFIDENCE` — **required for every `ai_readiness` code** (`Established` / `Reasonable proxy` / `Heuristic`), enforced by `tests/test_architecture_constraints.py::test_every_ai_readiness_code_has_confidence_label`. It covers 75 of 170 codes, so it is easy to miss; both new entity codes need an entry, and it must agree with the `_CALIBRATION` confidence. **It has a seventh home:** `frontend/src/data/issueHelp.json` carries its own `confidence` field for all 75, and `tests/test_confidence_help_parity.py` fails when the two disagree — but is silent when the field is simply **absent**, so omitting it ships a drawer with no tier and nothing goes red.
   `make_issue()` raises `KeyError` for an unregistered code. There is no silent fallback.
3. **Severity and impact are DERIVED, never hand-set to a different value.**
   - `derive_impact(code)` = `_IMPACT_OVERRIDES[code]` if present, else `_MEASURED_MATRIX[eff]` if `measured` else `_IMPACT_MATRIX[(confidence, eff)]`.
   - There is a fourth lane the draft omitted: `_PAGE_FATAL_10` returns 10 for a code in that frozenset with `("Established", "large")`. It holds three codes and none of the new ones qualify — noted so the formula above is not read as complete.
   - `_IMPACT_MATRIX` = Heuristic{0,1,2,3} / Reasonable proxy{0,2,4,6} / Established{0,2,6,9} for {none,small,moderate,large}.
   - `severity_from_impact(impact)` = critical ≥8, warning ≥4, else info.
   - `test_r5_severity.py` pins all codes' stored severity to `severity_from_impact(derive_impact(code))`.
   - **Do not confuse two senses of "measured".** In `_CALIBRATION` it is the third tuple element, selecting `_MEASURED_MATRIX` (which scores *lower* at the top end: moderate → 3, not 6). Elsewhere in this spec it means "derived from a real measurement of the live site". `CWV_CLS_POOR` is measured in the second sense and `False` in the first. All five new codes are `False`.
   So: **pick the `_CALIBRATION` tuple, and let the impact fall out of the matrix.** The table in §1 gives the correct tuple and its resulting impact/severity — do not change the tuple without changing the spec.
4. **Four files stay in sync** (parity tests fail otherwise):
   - `_CATALOGUE` / `_ISSUE_SCORING` / `_CALIBRATION` (registry.py)
   - `frontend/src/data/issueHelp.json` (authored, seven-part explainer — style in `docs/explanation-style-guide.md`)
   - the generated Python help copy (`api/services/issue_help_data.py` — regenerate via its generator script)
   - `docs/issue-codes.md` (regenerate via `python scripts/generate_issue_codes_doc.py`)
   - **`api/crawler/checkers/data/authority.yaml` — one entry per catalogue code, no exceptions.** It currently holds exactly 170, and `tests/test_authority.py::test_v1_every_catalogue_code_declares_a_basis` asserts `set(_CATALOGUE) - all_codes()` is empty. **Correction (r3):** an earlier revision said this file decides how a finding is labelled in the panel and the PDF. It does not — `authority_for` / `is_heuristic` have **no runtime consumer**; their only importers are `tests/`, `tests/test_issue_help_completeness.py` and `scripts/generate_issue_codes_doc.py`. The registration is still mandatory for two real reasons: the suite goes red without it, and `docs/issue-codes.md` is generated from it, so a missing entry publishes the check as unsourced. See §1.2 for where the *rendered* evidence tier actually comes from.
     Each entry declares `basis: citation | heuristic | observation`, and `test_v1_entry_is_well_formed` is parametrized over every code:
     - `citation` requires `source`, `source_type` (one of vendor / standard / industry / research), an `https://` `url`, and a `claim`. The URL must also appear in `data/url_verification.yaml` with a per-URL status 200. `checked_on` is a **single top-level key** for the whole file, bounded at 180 days by `test_v1_the_verification_is_not_indefinitely_old` — so adding one URL means re-stamping the file, which `python scripts/verify_authority_urls.py` does. Do not hand-edit a per-URL date; there is none.
     - `heuristic` requires a `rationale` of ≥ 60 characters and **must not** carry a `url`.
     - `observation` requires a `method` of ≥ 60 characters saying what was measured *and what it does not establish*, and must not carry a `url`.
     - A code labelled `Established` in `_AI_READINESS_CONFIDENCE` must have `basis: citation` with `source_type` vendor or standard (`test_v1_established_codes_carry_a_citation`). Where the threshold is ours rather than the source's, say so in `threshold_note` — `ORPHAN_PAGE`'s entry is the model, and it documents its own P31 suppression there.
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

*Do not attempt a measured-CLS suppression at check time — it is not buildable there.* r1 required suppressing this code when the page has a good measured CLS. That cannot work as wired: `CWV_CLS_POOR` is emitted only by `api/services/web_vitals.py::collect_web_vitals`, which runs **after** the crawl, behind an opt-in API-key-gated endpoint, over the top-N pages, from CrUX **field** data that exists only for URLs with enough traffic to anonymise. At per-page check time during a crawl, no CLS is available for any page — so the suppression branch would be permanently dead, and a test of it would be green over code the run path cannot reach (P27 / P21's conditionally-dead corollary). For a nonprofit site, CrUX coverage is close to zero regardless.

  Do this instead: **emit the proxy unconditionally and be honest in the explainer** — say that this is a markup check, that a measured Core Web Vitals score is the authority where one exists, and that the two can disagree. A post-hoc reconciliation (retracting stored `IMG_MISSING_DIMENSIONS` rows in the web-vitals persist path at `api/routers/crawl.py`, and moving the health score) is a real option but a **materially larger change** touching stored findings and scoring — it is out of scope here and belongs in its own spec.

*Decide and record: decorative images.* `parser.py` already computes `is_decorative` per image (`role="presentation"`, `aria-hidden`, `alt=""`, sub-32px). Tracking pixels, spacers and theme decorations routinely declare no dimensions and shift nothing. This is precisely the class that produced this repo's 156-finding `IMG_ALT_MISSING` false positive — where an "adversarial" test pinned the wrong answer because the expected value came from the implementation rather than the standard (P32). Decide **before implementing** whether `is_decorative` suppresses this code, write down where the decision came from, and put the case in the adversarial list either way.

*Honest caveat for the explainer:* a theme may reserve space via CSS, so the finding means "no intrinsic dimensions declared in the markup", which *usually* causes layout shift — review, not certain CLS.

*Adversarial test:* an `<img>` with `width` set but `height` missing (or vice-versa) **must** count; an `<img>` with both present must not; an `<img>` with `width="" height=""` must count; an `<img>` with `width="100px"` and `height="60"` must not (both parse); plus the decorative case, per the decision recorded above.

**2. `FORM_FIELD_NO_LABEL`** — for every `<input>` (excluding `type` in `{submit, button, reset, image, hidden}`), `<select>` and `<textarea>` that has **no proper label**, emit one finding with `extra={"count": N, "examples": [{type, id or name}…][:5]}`. A *proper* label is: a `<label>` whose `for` equals the field's `id`, a wrapping `<label>`, `aria-label`, or `aria-labelledby`. **`placeholder` and `title` do NOT count** (WCAG 1.3.1 / 3.3.2).

This is the deliberate difference from `INTERACTIVE_NO_ACCESSIBLE_NAME`, which *does* accept `placeholder` and `title` as names (`api/crawler/parser.py`, the `unnamed_interactive` signal) because it targets agent operability, not WCAG label compliance. Two codes, two questions, answered differently on purpose. Document the relationship in **both** explainers so they are not read as duplicates, and add an agreement test in `tests/test_checker_agreement.py` pinning the intended divergence: an input carrying only `placeholder` fires `FORM_FIELD_NO_LABEL` and does **not** fire `INTERACTIVE_NO_ACCESSIBLE_NAME`.

**Its authority entry is not optional and not free-text.** r1 said the citation "lives in the seven-part explainer" because `_IssueSpec` has no `authority` field. That was wrong — the record lives in `api/crawler/checkers/data/authority.yaml` (§0.4), and this is the one new code whose basis is a normative standard. Its entry is `basis: citation`, `source_type: standard`, W3C WAI / WCAG 2.2 SC 1.3.1 (and 3.3.2), with the URL added to `url_verification.yaml` via `scripts/verify_authority_urls.py`. `IMG_ALT_MISSING`'s existing entry is the model.

> **The rendered evidence tier is a different mechanism, and three of the five new codes cannot show one.** What the user sees comes from `Issue.confidence_label`, fed by `_AI_READINESS_CONFIDENCE` and rendered by `report_generator.py` (`Evidence: …`), `excel_generator.py` and the API. That dict is `ai_readiness`-only, enforced in both directions by `test_confidence_entries_only_for_ai_readiness_category` — measured: `make_issue("IMG_ALT_MISSING", …).confidence_label` is `None`, `ENTITY_NAP_INCOMPLETE`'s is `"Established"`.
> So codes 3 and 4 (`ai_readiness`) get a tier; `IMG_MISSING_DIMENSIONS` (performance), `LOW_INBOUND_LINKS` (crawlability) and — the awkward one — `FORM_FIELD_NO_LABEL`, the single new code resting on a normative standard, render **no tier at all**, on screen or in the PDF. Adding entries for them is not the workaround: that test turns red.
> This is pre-existing and not caused by the new codes, so **decide, do not drift**: either (a) accept it, and scope acceptance criterion 17 to codes 3 and 4, saying in the explainer copy for the other three what the tier cannot; or (b) make "wire `authority_for` into the issue serialiser so every code carries a tier" an explicit deliverable of this spec, with its own criterion. Do not mark criterion 17 done on the strength of criterion 12 — the authority file does not reach the product.

*Adversarial test:* an input with only `placeholder` must still flag; an input with a `<label for="…">` must not; a `type="hidden"` input must not; a submit button must not.

**3. `ORG_LEGAL_NAME_MISSING`** (renamed from `ORG_LEGAL_NAME_INCONSISTENT`) — when an `Organization`/`LocalBusiness` node has `name` present and `legalName` **absent**, emit one **site-scoped** finding. `extra={"name": …}`. Reasonable-proxy basis: schema.org recommends `legalName` where it differs from `name`.

> **The casing half of this check was withdrawn at review.** The draft would have flagged a `legalName` that is "a non-canonical casing of `name`". `cross_page.py` already normalises casing *and* legal suffixes away before comparing organisation names (`_normalise_org_name`, `_ENTITY_LEGAL_SUFFIXES`), annotated "so a casing/suffix-only difference is NOT a false 'inconsistent' (adversarial P7)". Shipping the casing rule would have had two checks give opposite answers about the same node — the shape where whoever implements it writes a test pinning whichever answer they happen to believe. `legalName` is also already in `placeholder_fields`, so its *content* is under E5's eye.
> The code is renamed to match what it now does. If a casing rule is wanted later it is a change to `_normalise_org_name`'s contract, argued on its own, with an agreement test — not a second opinion emitted beside the first.

*Adversarial test:* `legalName` present → no flag (whatever its casing); `legalName` absent → flag; `name` absent → no flag (nothing to compare); three pages carrying the same node → exactly one finding; **the entity node on `/about` and not on the homepage → see the representative-page caveat below.**

**4. `LOCAL_BUSINESS_FIELD_INCOMPLETE`** — when a node is a `LocalBusiness` (or `Organization`+`Place`), flag each **missing** field from a configured list. One **site-scoped** finding listing which are absent: `extra={"missing": ["areaServed", …]}`.

*The field list is config, not code.* Global rule 9 and the E5 precedent put editorial vocabularies in `api/config/entity_values.json`. Add a key beside `nap_required_fields` — e.g. `"local_business_recommended_fields": ["areaServed", "geo"]` — and read it through `_entity_cfg()` (extend `_ENTITY_CFG_KEYS`). `geo` counts as present only with both `latitude` and `longitude`.

*`priceRange` is excluded by default.* It is a Google LocalBusiness rich-result field with little meaning for a nonprofit, which is this tool's whole audience. It may be added to the config list by a site that wants it; it is not in the shipped default. Record this in `docs/thresholds.md` alongside the default list.

Complements — does not overlap — `ENTITY_NAP_INCOMPLETE`, whose required set (`url`, `logo`, `address`, `telephone`, `email`, address subfields) shares no member with this one. A test must assert the two sets are disjoint, so a later edit to either config list cannot silently create a double-count.

*Adversarial test:* all configured fields present → no flag; only `geo` missing → flag with `["geo"]`; `geo` present with `latitude` only → flag; a plain `Organization` (not a premises type) → no flag; three pages carrying the node → exactly one finding; **the entity node on `/about` and not on the homepage → see the representative-page caveat below.**

### Representative-page caveat — codes 3 and 4 (decide before implementing)

`_check_entity_values` picks `rep` as the page matching the start URL whenever one exists, and falls back to the **first page in list order** carrying an entity node, and only when no page matches the start URL (the code takes `candidates[0]`; "shallowest" is its docstring, true only if `pages` happens to be depth-ordered). So on a site whose `Organization`/`LocalBusiness` node lives on `/about` but not on the homepage, the representative page yields no entity nodes and codes 3 and 4 **silently never fire** — no finding, no disclosure, indistinguishable from a pass (P3/P31).

This is pre-existing behaviour that the new codes inherit rather than a defect they introduce, so fixing `_check_entity_values`'s fallback is optional and out of scope. What is **not** optional: decide whether "no entity node on the representative page" is *not applicable* or *not checked*, say which in the spec, and put the case in both adversarial lists. A silent nothing is the one answer that is not allowed.

**5. `LOW_INBOUND_LINKS`** — a page with **exactly one** inbound internal link from the link graph (`ORPHAN_PAGE` = zero, and stays untouched). Emit on the weak page, `extra={"referring_url": …}`.

*This is an absence-inference and must carry its input's completeness (P31 — the pattern this repo measured on `ORPHAN_PAGE` itself).* "Exactly one inbound link" is decidable only over a complete link graph: the second link that would clear a page may live on a page the crawl never fetched, and a narrowed crawl makes the finding count go **up**, not down. The plumbing already exists and must be reused, not re-invented:

- `check_cross_page(..., link_graph_complete: bool = True)` (`cross_page.py`) — emit `LOW_INBOUND_LINKS` **inside the existing `if link_graph_complete:` block**, next to `_check_orphan_pages`. Do not add a second flag.
- `api/crawler/engine.py` sets it from `orphan_status`, which is `skipped_single_page` / `skipped_partial_scan` / `skipped_truncated` / `complete`.
- **Extend the disclosure — and note it has four homes, not two, none of which will show this code.** A suppressed `LOW_INBOUND_LINKS` renders as zero findings, which every surface reads as a clean bill of health. The `orphan_detection` disclosure is currently authored in four independent places, all of them ORPHAN_PAGE-specific:
  - `api/services/coverage_notes.py::orphan_coverage_note` (`_ORPHAN_SKIP_WHY`) — the export surfaces, PDF and Excel;
  - `frontend/src/components/OrphanedPagesPanel.jsx` (`SKIP_REASONS`, `SkippedNotice`, `CompletenessFootnote`);
  - `frontend/src/pages/Results.jsx`;
  - `frontend/src/api.js`, which literally filters `i.issue_code === 'ORPHAN_PAGE'` and feeds the orphan panel.

  `LOW_INBOUND_LINKS` is a `crawlability` finding, so it renders in the ordinary category list (`CategoryPanel`) — which carries **no coverage disclosure at all**. Extending only the four above puts the honest status where this code is not shown, and leaves a silent zero where it is. `CategoryPanel` (or the crawlability list) is therefore a **required** disclosure surface for this change. Two things follow that the spec must settle rather than leave open:
- **`_ORPHAN_SKIP_WHY` in `api/services/coverage_notes.py` is the canonical wording** — it is the copy that already reaches the PDF and Excel. The three frontend copies are derivatives. Extend that one; do not author a fifth phrasing, which is the outcome this clause exists to prevent.
- **`CategoryPanel` receives no `detection` object today**, so "render the disclosure there" implies a new field on the category/issues API response. Name it, and give it an API-contract test before the frontend change, per the repo's standing rule.

The PDF needs no new home: `report_generator.py` already carries the orphan note at document level, with a comment naming the very problem of a crawlability section reading clean — extending `orphan_coverage_note` covers PDF and Excel together.
- **Do not rename `orphan_detection`.** It is a persisted SQLite column (`api/services/sqlite_store.py`), read back for stored jobs. Renaming it blanks the disclosure on every historical job unless a migration ships with it — and `cafdf6e`, two commits before this spec landed, is a migration incident. Extend the payload; leave the key alone.
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

**Storage: key on `domain`, not on `job_id`.** The requirement is that resolutions survive a rescan — and a rescan is a **new job**: `rescan_job` routes to the shared launch path, which mints `job_id=str(uuid4())`. A `decisions` table keyed on the job, or a JSON column on the job row, is discarded by definition and cannot meet the requirement, so neither of r1's two suggested options is usable.

"Follow the store's existing patterns" is ambiguous in the harmful direction here, so be explicit: the store's **job-keyed** tables (`issues`, `images`, `links`) are per-crawl, while its **durable** ones are domain- or globally-keyed — `domain_issue_filters` (on `domain`), `suppressed_issue_codes`, `exempt_anchor_urls`, `ignored_image_patterns` (`api/services/job_store_base.py`). Those are the pattern to follow — but note that only `domain_issue_filters` is domain-keyed; the other three are **globally** keyed, and an implementer who copies one of those from this list ships one organisation's resolved decisions into every other domain's audit. Key the decision state on `domain` + `key`, and follow `domain_issue_filters` specifically.

**Normalise the domain — `CrawlJob` has no `domain` field, so it is derived from `target_url`.** Use `normalise_filter_domain()` (`api/services/domain_filter.py`), which every `domain_issue_filters` call site already goes through. Its own docstring says why: without it, `example.com` and `https://WWW.Example.COM:443/` address different rule sets and an operator watches nothing happen. A bare `urlparse(...).netloc` is the defect this repo has already shipped twice.

The trap this leaves for the test is worth naming: whoever implements job-keyed storage also writes its round-trip test, and the natural way to write it is to resolve and re-read the **same** `job_id` — which passes while the requirement fails. The test must therefore be: resolve on job A → run a **real rescan** → assert the **new** job's `GET /decisions` reports it resolved. That test is still one-sided, so it needs two more assertions beside it, each aimed at a specific wrong implementation:
- **start the second scan from the other spelling of the domain** (`www.` vs bare, or a trailing `:443/`) and assert the resolution still carries — an unnormalised key passes the plain rescan test perfectly, because a rescan reuses the stored `target_url`;
- **assert a job on a different domain reports the same key `open`** — a globally-keyed table also passes the plain rescan test.

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
- **`IMG_LAZYLOAD_MISSING`** (`performance`) — `("Reasonable proxy","small",False)` → 2 info. Non-first `<img>` (in document order) that is **not lazy-loaded**. Heuristic (below-fold is approximate). State the tier.
  **Read `is_lazy_loaded`, do not re-derive it.** `api/crawler/parser.py` already computes it per image, and it is *broader* than `loading="lazy"`: it also accepts a `data:` placeholder in `src` and any of `_LAZY_SRC_ATTRS` (`data-src`, `data-lazy-src`, `data-original`, `data-lazy`, `data-echo`). A WordPress theme lazy-loading via `data-src` — common across this tool's entire audience, and the reason those attributes are handled at all — would otherwise be flagged as missing lazy-load while the parser record says it is lazy. `is_lazy_loaded` sits in the same dict literal as the `rendered_width`/`rendered_height` §1 tells you to reuse; the same agreement-test rule applies.
- **`FOCUS_INDICATOR_REMOVED`** (`accessibility`) — `("Heuristic","small",False)` → 1 info. `outline:none`/`outline:0` without a replacement focus style. Heuristic.
- **`V2-ANALYTICS`** — an opt-in, read-only "Analytics configuration audit" (conversion events, cross-domain/outbound measurement, 404 event), mirroring `api/services/wp_audit.py`'s capability-probe + `not_inspected` boundary.

## 6. P2 — deferred (needs further design; do NOT implement in this pass)

- **`TYPO_SUSPECTED`** — dictionary spellcheck over URL slugs (item 7 `/dontation_form/`). High false-positive risk (names, loanwords). Default off via a scan setting. Requires a design decision on the dictionary + a measured FP rate before it ships.
- **`V2-MOBILE`** — tap-target size / mobile usability via the render path. Needs measurement infrastructure.
- **`CONTRAST_RATIO_LOW`** (`accessibility`) — **moved here from P1 at review.** Text/background contrast < WCAG 4.5:1 needs computed styles, and nothing in the repo produces them: the only render capability is `api/services/js_renderer.py`, which returns rendered **HTML**, and nothing under `api/` reads CSS or calls `getComputedStyle`. It also implies `playwright`, which is **not in `requirements.txt`** — `js_renderer` guards it behind `HAS_PLAYWRIGHT`, while CI installs `requirements.txt` and nothing else on 3.11 and 3.14. That is the shape of this repo's most recent fix-log entry (2026-09-04), where a test needing an undeclared dependency was green locally and red in CI for a whole session. `V2-MOBILE` was already deferred for exactly this gap; keeping this in P1 gave one problem two answers in adjacent sections. Before it ships it needs: the measurement source, the `requirements.txt` change, and the skip-marker precedent (`requires_google` in `tests/test_gsc_integration.py`).

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
9. `IMG_MISSING_DIMENSIONS` reads `page.images`' existing `rendered_width`/`rendered_height`. **No measured-CLS suppression is implemented** (§1.1 — it cannot exist at check time); the explainer states that a measured Core Web Vitals score is the authority where one exists. This is an absence claim with no natural test: grade it by reading the code, and never record it as "done — tested".
10. The decorative-image decision (§1.1) and the representative-page decision (§1.3/§1.4) are recorded as **answers** in this spec, not as the instruction to decide — the instruction is what is there now, and it does not satisfy this criterion — and each answer appears in the relevant adversarial list.
11. `LOCAL_BUSINESS_FIELD_INCOMPLETE`'s field list lives in `api/config/entity_values.json` (not in Python), `priceRange` is absent from the shipped default, and the default list is recorded in `docs/thresholds.md`.
12. `api/crawler/checkers/data/authority.yaml` has an entry for each of the five new codes, well-formed per §0.4; `FORM_FIELD_NO_LABEL`'s is `basis: citation` / `source_type: standard` citing WCAG 1.3.1; `scripts/verify_authority_urls.py` has been run and `url_verification.yaml` updated; `tests/test_authority.py` is green. `_AI_READINESS_CONFIDENCE` has an entry for both `ai_readiness` codes, **and so does `issueHelp.json`'s `confidence` field** — its parity test is silent on an absent field, so this one is checked by hand (§0.2).
13. Three agreement tests exist in `tests/test_checker_agreement.py`: `IMG_MISSING_DIMENSIONS` against `rendered_width`/`rendered_height`; `FORM_FIELD_NO_LABEL` against `INTERACTIVE_NO_ACCESSIBLE_NAME` (pinning the intended placeholder divergence); and `LOCAL_BUSINESS_FIELD_INCOMPLETE`'s configured field set disjoint from `nap_required_fields`.
14. The stale `PHASE_1_CATEGORIES` comment in `api/models/issue.py` is corrected in the same change (§2).
15. Decision state is keyed on a `normalise_filter_domain()`-normalised domain, not on `job_id`, and its tests cover all three cases in §3: a real rescan carries the resolution; a rescan started from the other spelling of the domain also carries it; and a job on a different domain reports the same key `open`. The Decisions surface ships with `tests/test_decisions_surface.py` (contract) written and passing **before** its frontend panel exists; the panel is added only after.
16. `LOW_INBOUND_LINKS`'s suppression is disclosed on the surface that actually renders it (`CategoryPanel` / the crawlability list), sharing wording with the existing note; `orphan_detection` is **not** renamed (§1.5).
17. The evidence-tier decision in §1.2 is recorded, and this criterion is graded against whichever branch was chosen — **not** against criterion 12, which concerns a file that does not reach the product. Under branch (a) it covers codes 3 and 4 only; under branch (b) every new code carries a tier on screen and in the PDF. Either way, a measurement that could not be made renders *not checked*, never clean (repo P2 rule).
18. `SCORING_MODEL_VERSION` = `2026-09-06-r7` and `ISSUE_EMISSION_VERSION` = `2026-09-06-e2` are bumped; `docs/functional-specification.md` and `docs/thresholds.md` are folded; `PLAN-V4.0.md` tallies any shipped V4 explainer; `git push origin main` after each item.
19. Full suite green on **both** interpreters (3.11 and 3.14) via `./venv/bin/python -m pytest tests/ -q`.

## 8. Explicit non-goals

- No off-site authority (local listings, backlinks, outreach) — paid third-party data, declined in `docs/overview.md`.
- No crawl-budget/server-log analysis.
- No WordPress-specific checks in the crawl (WP stays in the opt-in audit).
- No content-*quality* scoring beyond the existing LLM advisory.
- No URL-changing or image-link-updating automation (standing WP safety constraints).
- No changes to `schema`, `mobile`, or `duplicate` categories in this pass (they remain reserved).

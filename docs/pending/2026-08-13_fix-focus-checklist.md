# Micro-spec: Fix Focus — curated priority-fix checklist (SEO + AI/GEO)

**Date:** 2026-08-13
**Status:** PROPOSAL — awaiting approval. No implementation code until this is approved.
**Type:** new feature (backend endpoints + persistence + one new frontend panel).
**Touches the GUI:** yes → the UI placement in §FF6 needs **explicit** sign-off at approval
time (project hard constraint: no GUI structure/nav change without explicit instruction).

---

## 1. Problem & goal

The report surfaces dozens–hundreds of issues. The existing **"Top 10 Pages to Fix"**
(`Top10Pages.jsx`, sorts pages by critical/warning counts) and **"Top 5 Priority Fixes"**
(`TopPriorityGroups.jsx`, groups by `issue_code`) are *read-only summaries* — they don't give a
person a finite, workable, tickable worklist.

**Goal:** a **Fix Focus** checklist — the highest-priority fixes, split into two focus areas
(**SEO** first, then **AI/GEO**), **grouped by page**, **capped at 10 pages per focus**, with
**checkboxes** a user ticks off as they work. The checklist is **saved with the crawl** and can be
**returned to without re-running the scan**, and each page can be **re-scanned to verify** its
fixes cleared.

## 2. Non-goals

- No new crawl/scoring engine — reuse `priority_rank` (`registry.py:2299`) and the existing
  single-page rescan (`crawl.py:899`).
- No WordPress writes (this is a worklist, not an auto-fixer; existing fix flows are unchanged).
- No change to the existing `Top10Pages` / `TopPriorityGroups` / `PagePriorityPanel` panels.
- Not a multi-user/shared-assignment tool — checked state is per crawl job.

---

## FF1 — Focus buckets (SEO vs AI/GEO): one source of truth

**FF1.A** Define the AI/GEO bucket by **promoting the existing private set** to a shared,
importable definition — do not duplicate it. Today `_AGENT_READINESS_CATEGORIES =
{ai_readiness, rendering, semantic_html}` and `_AGENT_READINESS_EXTRA_CODES =
{PLACEHOLDER_LINK, WRONG_PLACEHOLDER_LINK}` live privately in
`api/services/job_store_base.py:427-432`. Expose a single public helper (proposed:
`api/crawler/checkers/registry.py` → `focus_bucket(category, code) -> "geo" | "seo"`), and have
`job_store_base` import it so the "Agent Health" score and Fix Focus agree by construction.

**FF1.B** `focus == "geo"` ⇔ `category ∈ {ai_readiness, rendering, semantic_html}` **or**
`code ∈ {PLACEHOLDER_LINK, WRONG_PLACEHOLDER_LINK}`. Everything else is `"seo"`. Every one of the
162 catalogue codes resolves to exactly one bucket (total function, no "unknown").

**FF1.C** The bucket definition is **config, not scattered logic** (global rule #9 / P4): the two
sets live in one place; the SEO set is the complement (never a second hand-maintained list).

## FF2 — Selection & prioritisation (deterministic, from stored issues)

**FF2.A** Source = the issues already persisted for the job (`get_all_issues` /
`get_pages_with_issue_counts`) — **no re-crawl** to build the list.

**FF2.B** **Priority** uses the existing per-issue `priority_rank = (impact*10) − (effort*6)`
(`registry.py:2299`); the existing `quick_win` flag (`impact≥4 and effort≤1`, `registry.py:2300`)
is surfaced as a badge. No new scoring math.

**FF2.C** **"High priority" floor**: include only issues at or above a configurable impact floor
`FIX_FOCUS_MIN_IMPACT` (proposed default `4` = warning-and-above per
`severity_from_impact`, `registry.py:561-563`). Info-level issues are excluded from Fix Focus.
The floor is a named config constant (P4), added to `docs/thresholds.md` on completion.

**FF2.D** **Grouping & ordering**: within each focus, group items by `page_url`; order pages by
descending page-priority = **sum of `priority_rank` of that page's qualifying items** (tie-break:
critical count, then item count, then URL for stability); within a page, order items by
descending `priority_rank`. An item = one `(page_url, issue_code)` pair (matches `fixed_issues`
and `mark-fixed` granularity, `job_store_base.py:723-730`).

**FF2.E** **Cap = 10 pages per focus** (`FIX_FOCUS_MAX_PAGES`, config). When more qualify, the
response **announces the drop** (P2/P9): `pages_total`, `pages_shown`, `items_hidden` — never a
silent truncation.

## FF3 — Persistence (a saved, returnable snapshot)

**FF3.A** Persist the checklist as a **derived JSON blob on the job**, following the existing
`geo_report: dict | None` precedent (`models/job.py:98`), NOT the `fixed_issues` table (which is
insert-only and a **Redis no-op** — see Adjacent issues). New field: `fix_focus: dict | None`.

**FF3.B** Storage plumbing (mirror `geo_report` exactly):
- add `fix_focus` to `CrawlJob` (`models/job.py`);
- add `"fix_focus"` to the `update_job` allowlist `_ALLOWED` (`sqlite_store.py:240-249`);
- add the SQLite column + a migration (same pattern as `geo_report`);
- add the Redis equivalent (`redis_store.py`) so it is **not** a no-op on prod.

**FF3.C** **Snapshot semantics** (why a blob, not live recompute): the list is *frozen* when first
generated so it stays stable across per-page rescans and revisits. Each item carries a `status ∈
{open, checked, verified, still_present}` and `checked_at`. Regeneration is explicit (FF4.C).

**FF3.D** **Checked state is reversible** (a checkbox, not a one-way "fixed"): toggling writes the
item's `status`/`checked_at` in the blob. Because it's a job blob, toggle works identically on
SQLite and Redis (sidesteps the `fixed_issues` Redis gap).

## FF4 — API (new endpoints; contracts frozen before frontend)

**FF4.A** `GET /api/crawl/{job_id}/fix-focus?focus=all|seo|geo` → returns
`{seo: FocusList, geo: FocusList, generated_at, scoring_model_version}` where `FocusList =
{pages: [{url, page_priority, items: [{issue_code, human_description, severity, impact, effort,
priority_rank, quick_win, status, checked_at}]}], pages_total, pages_shown, items_hidden}`.
First call **generates and persists** the snapshot (FF3); later calls return the persisted snapshot.
Auth: bearer, like all `/api/*` (fail-closed in prod). Domain guard unchanged.

**FF4.B** `POST /api/crawl/{job_id}/fix-focus/check` body `{page_url, issue_code, checked: bool}`
→ toggles the item's checked state in the blob, returns the updated item. 404 if the item isn't in
the snapshot; 422 on missing fields.

**FF4.C** `POST /api/crawl/{job_id}/fix-focus/regenerate` → rebuilds the snapshot from current
stored issues (used after fixes change the issue set), **preserving checked/verified status for
items that persist by `(page_url, issue_code)`**. Returns the new snapshot.

**FF4.D** `POST /api/crawl/{job_id}/fix-focus/verify-page?url=...` → **reuses the existing
single-page rescan path** (`_fetch_and_check_page`, the internals behind
`crawl.py:899 rescan-url`), then reconciles the snapshot for that page: items whose code is in the
rescan's `resolved_codes` → `status=verified`; items still present → `status=still_present`; new
issues on the page are reported but do **not** silently enter the frozen list (surfaced as
`newly_found` for the user to regenerate). Returns `{url, verified: [...], still_present: [...],
newly_found: [...]}`. This is the "scan each fixed page to verify" capability.

## FF5 — Per-page verify status transitions

**FF5.A** `open` → user ticks → `checked`. `checked`/`open` → verify-page confirms cleared →
`verified`. `checked`/`open` → verify-page finds it still there → `still_present` (a visible "not
actually fixed" signal, not silently dropped — honesty rule, P14/P2).

**FF5.B** verify-page must reuse the rescan path's cache-bypass fetch so it sees the *live* page,
and must persist the page's updated issues exactly as `rescan-url` already does
(`save_pages`/`delete_issues_for_url`/`save_issues`, `crawl.py:959-967`) — no divergent second
code path (P5: one hardened fetch path, not a sibling).

## FF6 — Frontend (NEW panel — placement needs explicit approval)

**FF6.A (PROPOSED, pending your sign-off):** a new **"Fix Focus"** tab in `Results.jsx` alongside
the existing "Fix Manager" tab (`Results.jsx:183`), rendering a new `FixFocusPanel.jsx`. Two
sections, **SEO then AI/GEO**, each a list of page cards with tickable items, a quick-win badge,
and a per-page **"Verify page"** button (calls FF4.D). Checkbox and verify states come from the
persisted snapshot so a reload restores them. **I will not build this until you approve the
placement** (project GUI constraint).

**FF6.B** New frontend API wrappers in `api.js` (`getFixFocus`, `toggleFixFocusItem`,
`regenerateFixFocus`, `verifyFixFocusPage`), each with explicit loading/error states (React rule).

---

## Acceptance criteria → tests

| ID | Criterion | Test (to be written) | Type |
|---|---|---|---|
| FF1.B | Every catalogue code resolves to exactly one bucket; the 5 GEO members are geo, a sample SEO code is seo | `tests/test_fix_focus.py::test_ff1b_every_code_buckets_exactly_once` | unit |
| FF1.C | `job_store_base` agent set and Fix Focus share one definition (no drift) | `tests/test_architecture_constraints.py::test_ff1c_focus_bucket_single_source` | arch |
| FF2.C | Info-level issues (impact<floor) excluded; warning+ included | `tests/test_fix_focus.py::test_ff2c_min_impact_floor` | unit |
| FF2.D | Pages ordered by summed priority_rank; items by priority_rank desc; deterministic tie-break | `tests/test_fix_focus.py::test_ff2d_ordering_deterministic` | unit |
| FF2.E | >10 qualifying pages → 10 shown + `items_hidden`/`pages_total` reported (no silent drop) | `tests/test_fix_focus.py::test_ff2e_cap_announces_drop` | unit (real-scale fixture, P9) |
| FF3.A/B | Snapshot persists on the job and survives reload without recompute; present on SQLite **and** Redis | `tests/test_fix_focus.py::test_ff3_snapshot_persists`, `tests/test_redis_job_store.py::test_ff3_fix_focus_roundtrip` | integration |
| FF3.D | Toggle check then reload → state preserved; untoggle reverses it | `tests/test_fix_focus.py::test_ff3d_check_toggle_reversible` | integration |
| FF4.A | GET returns the frozen contract shape incl. `pages_total/pages_shown/items_hidden` | `tests/test_crawl_router_contracts.py::test_ff4a_fix_focus_schema` | contract |
| FF4.B | check endpoint: 404 unknown item, 422 missing field, 200 valid | `tests/test_crawl_router_contracts.py::test_ff4b_check_errors` | contract |
| FF4.C | regenerate preserves checked status for surviving items | `tests/test_fix_focus.py::test_ff4c_regenerate_preserves_status` | integration |
| FF4.D | verify-page marks resolved items `verified`, still-present `still_present`, reports `newly_found` | `tests/test_fix_focus.py::test_ff4d_verify_page_reconciles` (respx-mocked page) | integration |
| FF5.B | verify-page reuses the rescan fetch/persist path (no second crawl path) | `tests/test_fix_focus.py::test_ff5b_verify_reuses_rescan_path` | integration |
| FF5.A | An issue that did NOT clear is shown `still_present`, never silently dropped (adversarial) | `tests/test_fix_focus.py::test_ff5a_unfixed_stays_visible` | adversarial (P2/P14) |
| FF6.A | Panel renders SEO+GEO sections, restores checked/verified from snapshot, shows error state | `frontend/src/components/__tests__/FixFocusPanel.test.jsx` (mirror `PagePriorityPanel.test.jsx`) | component |
| FF6.B | Category parity still green (new helper doesn't break the catalogue) | existing `tests/test_frontend_backend_code_parity.py` | arch (regression) |

**Integration-test-first (API contract) table:**

| Endpoint | Frontend expects | Test | Status |
|---|---|---|---|
| GET `/api/crawl/{id}/fix-focus` | `seo`, `geo`, each `pages[].items[].{issue_code,priority_rank,quick_win,status}`, `pages_total`,`pages_shown`,`items_hidden` | `test_ff4a_fix_focus_schema` | Pending |
| POST `/api/crawl/{id}/fix-focus/check` | echoes updated item `{status,checked_at}` | `test_ff4b_check_errors` | Pending |
| POST `/api/crawl/{id}/fix-focus/regenerate` | full snapshot, status preserved | `test_ff4c_regenerate_preserves_status` | Pending |
| POST `/api/crawl/{id}/fix-focus/verify-page` | `{verified,still_present,newly_found}` | `test_ff4d_verify_page_reconciles` | Pending |

All rows above must be written and green **before** the `FixFocusPanel.jsx` frontend code (repo
API-contract rule).

---

## Open decisions (need your call at approval)

1. **Cap scope** — 10 pages **per focus** (SEO 10 + GEO 10), or 10 pages **total**? Spec assumes
   per-focus. (Your words: "limited to 10 pages" — clarify.)
2. **Impact floor** — default `4` (warning+). Include info-level if you'd rather see everything?
3. **GEO bucket membership** — confirm `{ai_readiness, rendering, semantic_html}` + the two
   placeholder-link codes is the right SEO/GEO line, or should `analytics` count as GEO?
4. **UI placement (FF6.A)** — new "Fix Focus" tab in Results: approve, or different location?

## Human-review-only criteria (not code-testable)

- "The list is genuinely the *right* fixes to focus on" is a judgement call on the bucket +
  floor + ordering choices above — validated by you against a real crawl (livingsystems.ca), not
  by an assertion.

## Adjacent issues found, not fixed (flagged per global rule #10)

- **`fixed_issues` is a Redis no-op** (`redis_store.py:453-458`) and **insert-only** (no
  unmark/delete). Fix Focus avoids depending on it by using a job blob. The Redis gap is a
  pre-existing bug for the `mark-fixed`/`fix-history` feature on production; logged in TODO, not
  fixed here.
- Two impact sources coexist (`_ISSUE_SCORING` raw vs the r5 `derive_impact`/`_CALIBRATION`,
  `registry.py:549-558`); Fix Focus sorts on the single derived `priority_rank`. No change proposed.

---

## Completion steps (after approval + green)

1. Fold this spec into `docs/functional-specification.md`; add `FIX_FOCUS_MIN_IMPACT`,
   `FIX_FOCUS_MAX_PAGES` to `docs/thresholds.md`; delete this pending file.
2. Update `docs/api.md` (4 new endpoints) and `docs/issue-codes.md` if any code metadata changes.
3. Record the V4 explainer entry in `PLAN-V4.0.md` (user-facing feature).
4. `git push origin main`.

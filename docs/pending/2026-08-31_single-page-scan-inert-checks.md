# Micro-spec — A single-page scan must declare the checks it cannot run

**Date:** 2026-08-31
**Cycle:** Bug-class elimination, Cycle 2
**Class:** Checks that are silently inert on the single-page path. One member was
disclosed (`ORPHAN_PAGE`); its eight siblings were not.

---

## 1. Problem (verified, not inferred)

`_fetch_and_check_page` (behind `POST /api/crawl/scan-page` and the per-page rescan
button) never calls `check_cross_page`, and calls `check_page` with `sitemap_urls=None`.
`check_page` guards that code with `if sitemap_urls is not None` (`issue_checker.py:425`),
so it cannot fire.

**Nine codes therefore cannot be produced by a single-page scan:**

| Code | Why inert on this path |
|---|---|
| `AUTHOR_IDENTITY_INCONSISTENT` | `check_cross_page` not called |
| `BOILERPLATE_RATIO_HIGH` | `check_cross_page` not called |
| `CANONICAL_MISSING` | `check_cross_page` not called |
| `ENTITY_NAME_INCONSISTENT` | `check_cross_page` not called |
| `META_DESC_DUPLICATE` | `check_cross_page` not called |
| `NEAR_DUPLICATE_BODY` | `check_cross_page` not called |
| `TITLE_DUPLICATE` | `check_cross_page` not called |
| `ORPHAN_PAGE` | `check_cross_page` not called — **already disclosed** |
| `NOT_IN_SITEMAP` | `sitemap_urls=None` ⇒ guard skipped |

Exactly one of the nine is disclosed. `crawl.py:1338` writes
`orphan_detection={"status": "skipped_single_page", ...}` — the 2026-08-29 fix. The
other eight return nothing at all: the response is `{job_id, status, url, issues}`.

The asymmetry is visible inside one function. On the **authenticated draft** branch the
same endpoint returns `suppressed_codes` and a caveat naming `ORPHAN_PAGE`,
`NOT_IN_SITEMAP` and `NOINDEX_META` as meaningless before publication. On the ordinary
branch, `NOT_IN_SITEMAP` is equally unevaluated and nothing says so. A page scanned with
zero findings reads as clean when nine checks never ran — the "suppressed check rendered
as a clean result" failure this repo has already fixed twice (P31/P24).

## 2. Why this is the class, not the instance

The 2026-08-29 orphan work gated the unsound inference and shipped the disclosure
together — correctly, for `ORPHAN_PAGE`. It did not ask which *other* checks the same
narrowing silences. Seven siblings sit in the same module behind the same uncalled
function. This is P5/P12: a defect in one path exists in the paths modelled on it.

## 3. Change

**3.1 One source of truth for the set.** `scope` cannot be reused — it marks
site-config codes that deduct once per site (13 codes) and identifies only 3 of the 9.
Add a new field to `_IssueSpec` in `api/crawler/checkers/registry.py`:

```python
requires_site_context: bool = False   # cannot be evaluated from a single page
```

Set `True` on the nine codes above. The registry is already the repo's declared source
of truth for issue metadata, so this puts the fact in the one place `CLAUDE.md` says it
belongs. **The router derives its disclosure from the registry — it must not carry a
literal list**, or this change would create exactly the mirrored enumeration the cycle
exists to remove.

**3.2 Bind the flag to reality.** New test asserts the set
`{code | spec.requires_site_context}` equals the codes `cross_page.py` actually emits
(extracted from the module by AST, not hardcoded) plus `NOT_IN_SITEMAP`. Adding a new
cross-page check without marking it turns the test red.

**3.3 Disclose it.** The unauthenticated `scan-page` and rescan responses gain:

```python
"checks_not_run": [...],          # derived from the registry, sorted
"checks_not_run_reason": "These checks compare a page against the rest of the "
                         "site, so a single-page scan cannot evaluate them. "
                         "Run a full crawl to see them.",
```

On the authenticated branch the existing `suppressed_codes` stays and the two are
reported side by side: *suppressed because pre-publication* vs *not run because
single-page* are different claims and must not be merged.

## 4. Open decision — the frontend (owner's call, blocks 4.1)

CLAUDE.md forbids changing GUI structure without explicit instruction, so this spec does
**not** touch the frontend. But shipping a disclosure nothing renders is the unwired-
disclosure trap logged on 2026-08-30, where `images_measured` reached no surface at all
while three documents claimed it was integrated. Two honest options:

- **(a) Wire it** — render `checks_not_run` beside the single-page result. Needs the
  owner's explicit go-ahead per the GUI rule.
- **(b) Ship backend-only, and say so** — the field is in the API contract and this spec
  records that no surface reads it yet, tracked as an open risk.

**Shipping it and describing it as integrated is not an option.**

## 5. Explicitly out of scope

- Making the single-page path actually *run* these checks (fetching the sitemap, building
  a link graph). That changes what a single-page scan costs and means; a separate spec.
- The duplicated `page_size_limit_kb = 300` (engine-local default vs checker default).
  Real duplication, no behavioural difference today; logged, not fixed here.

## 6. Test table (red before the fix)

| Test | Asserts | Red first? |
|---|---|---|
| `test_registry_site_context_flag_matches_cross_page_emitters` | flagged set == AST-extracted `cross_page` emitters ∪ `{NOT_IN_SITEMAP}` | **Yes** — field does not exist |
| `test_scan_page_declares_checks_it_did_not_run` | response carries all nine codes | **Yes** — key absent |
| `test_rescan_declares_checks_it_did_not_run` | same for the rescan endpoint | **Yes** |
| `test_draft_scan_keeps_suppressed_and_not_run_separate` | both keys present, distinct meanings, not merged | **Yes** |
| `test_adversarial_clean_single_page_scan_is_not_reported_as_clean` | a page with zero findings still declares the nine — a green scan must not be indistinguishable from a fully-audited one | **Yes** |
| `test_adversarial_new_cross_page_code_without_flag_fails` | add a fake emitter ⇒ 6.1 goes red, proving the binding is live and not a snapshot | No (guards the guard) |

Adversarial case per CLAUDE.md: *what would a correct-looking but wrong result look
like?* A scan returning `issues: 0` and HTTP 200 — indistinguishable from a page that
passed nine checks it never ran. Test 5 pins that. Test 6 pins that the registry↔emitter
binding detects drift rather than having frozen today's list.

## 7. Docs to update on completion

- `docs/functional-specification.md` — the single-page scan's disclosure contract.
- `docs/issue-codes.md` — regenerate (new `_IssueSpec` field).
- `LEARNINGS.md` — fix-log entry.
- `docs/thresholds.md` — no change (no numeric bound).

---

**Status:** awaiting owner approval, plus the §4 frontend decision. No files changed yet.

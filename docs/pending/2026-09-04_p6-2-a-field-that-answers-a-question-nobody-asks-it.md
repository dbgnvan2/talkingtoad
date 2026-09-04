# Micro-spec — P6.2: `rechecked` answers a question nobody asks it

**Date:** 2026-09-04
**TODO item:** Phase 6, P6.2
**Class:** P25 (a field computed and never read), P26 (a test whose message claims a
dependency that does not exist), P13 (one name, two meanings, two types).

---

## 1. Verified

### 1.1 Nothing reads it

`grep -rn "rechecked" frontend/src` returns exactly one non-test hit —
`FixFocusPanel.jsx:108`, and that reads a **different field**: `fix_focus.py:210` sets
`item["rechecked"] = "not_checked"`, a *string* on a Fix Focus item. The rescan response's
`rechecked` is a *boolean* on an issue row (`crawl.py:1921, 1927`). Two fields, one name,
different types, different payloads. The Phase-4 "Fix Focus third state" work shipped the
string one; the boolean has never had a consumer.

The rescan response reaches the UI through `toRecheckResult` → `RecheckResultBanner`, which
renders four **code lists** (`resolved`, `stillPresent`, `newlyFound`, `carriedOver`) and
never the per-issue rows. `Results.jsx:786`'s `by_category` is a different payload — the Page
Audit drawer's, from `/pages/issues`, which does not carry `rechecked` at all.

### 1.2 It is derivable, on every row, always

`carried_over` is defined as *existing findings whose code is in `unrunnable`*
(`crawl.py:1877-1882`), and `unrunnable = set(_checks_a_single_page_scan_cannot_run())` —
i.e. `needs_full_crawl`. Rows in `new_issues` get `True`, rows in `carried_over` get `False`,
and an unrunnable code can never be newly found (that is what "unrunnable on this path"
means). So on this response `rechecked == (code not in needs_full_crawl)`, without exception.
It is a **per-row copy of a code-level fact**, which is where drift starts, and this
particular copy has never been read.

### 1.3 A test asserts it *for* the consumer that does not exist

`tests/test_rescan_reports_what_it_checked.py:177`:

```python
assert returned[code].get("rechecked") is False, (
    f"{code} returned without rechecked=false, so the panel cannot "
    f"distinguish a re-checked finding from a carried-over one")
```

The panel distinguishes them from `carried_over_codes`. The failure message states a
dependency that has never held — the kind of sentence that becomes established fact on the
next read (the "past-tense consequence" lesson already in LEARNINGS' open risks).

## 2. The gap this field was gesturing at, which deleting does not close

Probed on the **persistent** view an operator returns to — `/pages/issues`, the Page Audit
drawer — after seeding a carried-over `ORPHAN_PAGE` beside a freshly-evaluated `H1_MISSING`:

```
H1_MISSING    distinguishing keys -> {'scored': True}
ORPHAN_PAGE   distinguishing keys -> {'scored': True}
```

Identical. The banner's carried-over disclosure is **transient**: dismiss it, or reopen the
drawer, and nothing says one of those findings was kept rather than re-verified.

**That gap cannot be closed by rendering `rechecked`, and it is not this item.** The drawer
serves full-crawl jobs too, where `needs_full_crawl` codes *were* checked — so "was this row
last evaluated, and by which kind of scan" is genuine per-row state that is stored nowhere.
Adding it is a schema change to the issues table, exactly the reasoning the archive already
applied to the Fix Focus third state ("a schema change to a persisted snapshot and so its own
item"). Recorded as **P6.2b**, not smuggled in here.

## 3. Change

1. **Delete `rechecked`** from the two `_issue_dict(...) | {...}` merges (`crawl.py:1921,
   1927`) and from the carried-over merge at `crawl.py:1828`.
2. **Delete the doc lines** that make it contract: `docs/api.md:47` and
   `docs/functional-specification.md:1644`. A documented field that no code produces is worse
   than an undocumented one.
3. **Fix the test.** `test_a_carried_over_finding_is_still_in_the_response` keeps its real
   assertion — a carried-over finding must still be **present** in the payload, which is what
   its name says and what actually matters — and loses the `rechecked` assertion and the
   message that claims a consumer.
4. **Add the guard that would have caught this**: a test asserting no rescan-response row
   carries `rechecked`, so re-adding an unread field fails rather than accumulating.

## 4. Tests

| # | Test | Goes red when |
|---|---|---|
| 4.1 | `test_a_carried_over_finding_is_still_in_the_response` (amended) | a carried-over finding is dropped from the payload |
| 4.2 | `test_the_rescan_response_carries_no_unread_rechecked_flag` | the field comes back |
| 4.3 | `test_carried_over_is_exactly_the_unrunnable_codes` | §1.2's premise stops holding |
| 4.4 | `test_fix_focus_rechecked_is_untouched` | the deletion reaches the wrong `rechecked` |
| 4.5 | `test_no_doc_documents_a_field_the_api_does_not_send` | the doc lines come back |

**Adversarial cases:**

- **4.3 is the load-bearing one.** Deleting a field is only safe if the information is
  genuinely elsewhere; this pins the equivalence the deletion rests on
  (`carried_over_codes == stored codes ∩ needs_full_crawl`) rather than assuming it. If a
  future change makes carry-over depend on something other than the code, this fails and says
  the deletion's premise has expired.
- **4.4 is the wrong-target guard.** Two fields share the name; a `grep -r rechecked` cleanup
  is the obvious way to do this work and would take out the Fix Focus string that
  `FixFocusPanel` genuinely reads. The test asserts the *string* form still arrives.
- **4.5 reads `docs/api.md` and the functional spec** for the field name and asserts a live
  rescan response does not contain it — one side read against the other's live output, per
  LEARNINGS item 13, rather than two assertions that agree with each other.

Every test verified red by reverting the change it guards.

## 5. Considered and rejected

- **Wire it into the per-issue row instead.** Rejected: there is no per-issue row rendering on
  this response to wire it into — the banner shows code lists — and building one to justify a
  field is backwards. The disclosure the operator needs is §2's, on a different payload.
- **Keep it because `docs/api.md` documents it.** Rejected: that is the documentation
  justifying the code rather than describing it. The doc line goes with the field.
- **Rename it (`evaluated`) and keep it.** Rejected: renaming a redundant unread field
  produces a better-named redundant unread field, and the name collision is the smaller
  problem.
- **Close P6.2 by fixing §2's drawer gap.** Rejected as scope: it needs stored per-row state
  and a migration. Recorded as P6.2b so the gap is a decision, not a casualty of closing this
  item.

## 6. Done when

- `rechecked` is gone from the rescan response, from `docs/api.md` and from the functional
  spec, with a test that fails if it returns.
- No test asserts a consumer that does not exist.
- The Fix Focus `rechecked` string — the one a panel really reads — is untouched and pinned.
- The persistent-view gap is recorded as P6.2b with the reason it is separate.

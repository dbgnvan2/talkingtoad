# Micro-spec — P8.1: a second tab silently un-does your ticks

**Date:** 2026-09-04
**TODO item:** Phase 8, P8.1
**Class:** the classic lost update — read-modify-write on one blob with no version and no
transaction. P8-adjacent (state that persists between operations, read as if this operation
owned it).

---

## 1. Verified

Every Fix Focus mutation is `snapshot = await _load_or_build_fix_focus(...)` → mutate in
memory → `await store.update_job(job_id, fix_focus=snapshot)` (`crawl.py:2612-2620`, and the
same shape in `verify-page`). The whole snapshot is one JSON column; nothing carries a
version, and nothing runs in a transaction.

Measured. Two panels open on one job, each ticking a different item:

```
sequential HTTP (each re-reads before writing):
  ticks = {'H1_MISSING': 'checked', 'TITLE_MISSING': 'checked'}      correct

two tabs (BOTH read, then BOTH write) — each un-ticks a different item:
  ticks = {'H1_MISSING': 'checked', 'TITLE_MISSING': 'open'}
```

Tab A un-ticked `H1_MISSING` and wrote. Tab B, holding a snapshot fetched before that write,
wrote its own copy and **restored `H1_MISSING` to `checked`**. The operator's un-tick is gone,
with no error and nothing on screen to notice.

**Why it is not hypothetical.** The TODO says "two browser tabs, or one operator and one
background job". The second is the likelier one: `verify-page` holds a snapshot across a
**live single-page re-crawl** — a network fetch taking seconds — and writes it afterwards.
Anything the operator ticks during that window is discarded when the verify lands.

## 2. Change

### 2.1 A tick is a per-item fact, so make the write per-item

`SQLiteJobStore.mutate_fix_focus(job_id, mutate)` — read the blob, apply `mutate(snapshot)`,
write it back, **all inside one transaction** (`BEGIN IMMEDIATE`), so a concurrent writer
waits and then re-reads rather than overwriting. Returns whatever `mutate` returns, so the
routers keep returning the mutated item.

Two tabs ticking *different* items then both succeed, which is the case that matters and is
today's silent failure. Two tabs ticking the *same* item still resolve last-write-wins, which
is correct: they are asserting the same fact about the same checkbox.

### 2.2 The slow work happens outside the lock

`verify-page` must not hold a transaction across a re-crawl. Its shape becomes:

1. rescan the page (network, seconds, no lock held);
2. compute the reconciliation from the result;
3. `mutate_fix_focus` to apply it — fast, and re-reading the current snapshot inside the
   lock, so ticks made during the crawl survive.

That ordering is the whole fix for the operator-vs-background case: today the snapshot is read
*before* the fetch, so anything ticked meanwhile is overwritten.

### 2.3 `_load_or_build_fix_focus` keeps its job

It still builds and persists a snapshot when none exists. Only the *mutating* callers change,
and the build path is unaffected — a first build has nothing to lose.

## 3. Tests

| # | Test | Goes red when |
|---|---|---|
| 3.1 | `test_two_tabs_ticking_different_items_both_survive` | the lost update returns |
| 3.2 | `test_a_tick_made_during_a_verify_is_not_discarded` | §2.2 regresses — the operator-vs-job case |
| 3.3 | `test_same_item_from_two_tabs_is_last_write_wins` | the fix is over-applied into a 409 |
| 3.4 | `test_the_mutation_re_reads_inside_the_lock` | `mutate` is handed a stale snapshot |
| 3.5 | `test_no_mutating_route_writes_a_whole_snapshot` | a future route reintroduces the blob write |
| 3.6 | `test_a_failing_mutation_leaves_the_snapshot_unchanged` | a partial write survives an exception |

**Adversarial cases:**

- **3.1 is the measurement above, turned into a test** — both reads before either write. A
  test doing sequential HTTP calls passes *today* and proves nothing; that is exactly the
  fixture that would have let this ship.
- **3.3 is the other direction.** The over-correction is to reject any write against a stale
  snapshot with a 409, which fixes 3.1 and turns two people ticking the same box into an
  error the panel has no handling for. It is written to hold the intended semantics, not just
  to forbid the bug.
- **3.2 fakes a slow rescan** (an `asyncio.sleep` inside the patched rescan) and ticks an item
  during it. Without it, 3.1 could pass while the operator-vs-background case — the likelier
  one — stayed broken, because that one is about *ordering*, not about locking.
- **3.5 is structural**: it reads `crawl.py` for `update_job(... fix_focus=` outside the store
  helper. The next mutating route is where this comes back.
- **3.6** pins that the transaction actually rolls back, rather than the helper merely wrapping
  the same read-modify-write in a function.

## 4. Considered and rejected

- **Optimistic concurrency (version stamp + 409).** Correct, and worse here: it needs the
  panel to handle a conflict and re-apply, and it turns the common case (two tabs, different
  items) into an error when it should simply work. A tick is not a claim about the whole
  snapshot.
- **Split the snapshot into per-item rows.** The right model, and a schema migration to a
  persisted structure for a bug with a contained fix — the trade `docs/TODO-ARCHIVE.md`
  already declined once for the Fix Focus third state.
- **Serialise with an in-process lock.** Works for one process and lies under the two the
  Dockerfile can run; the database is the only thing both writers share.
- **Leave it — "nothing breaks tomorrow".** That is the TODO's own framing and it is right
  about severity, not about cost: this is a ~40-line change with a measurable before/after,
  and the operator-vs-verify window makes it reachable without two tabs.

## 5. Not in scope

- Other blob columns written the same way (`geo_report`, `wp_audit`). They are produced by one
  generator, not edited by a person, so the lost update has no author to lose. Recorded rather
  than fixed.

## 6. Done when

- Two panels ticking different items both keep their ticks, proved by a test that reads twice
  before writing twice.
- A tick made while a verify-page re-crawl is in flight survives it.
- No mutating route writes a whole snapshot it read outside the store's transaction.

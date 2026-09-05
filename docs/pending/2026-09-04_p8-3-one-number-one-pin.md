# Micro-spec — P8.3: one number in four places, and a pin nobody chose

**Date:** 2026-09-04
**TODO item:** Phase 8, P8.3
**Class:** P4 (a number that belongs in `docs/thresholds.md` living somewhere else), P13
(one rule with several homes), and a dependency pin whose justification is "it matched the
venv".

---

## 1. Verified

### 1.1 `page_size_limit_kb` is stated four times, not twice

| Where | Form |
|---|---|
| `api/crawler/checkers/registry.py:2612` | `_DEFAULT_PAGE_SIZE_LIMIT_KB = 300` |
| `api/crawler/engine.py:277` | `page_size_limit_kb: int = 300` — a literal on the engine's `CrawlSettings` dataclass |
| `docs/api.md:562` | "default 300" in the settings table |
| `docs/fix-agent-spec.md:779` | "Page HTML exceeds 300 KB" |

`docs/thresholds.md:81` names the registry constant as the owner — and the engine's dataclass
does not read it. There is no behavioural difference today, which is exactly why this is
Phase 8 and not Phase 5: nothing is wrong on screen, and the next person to change the
threshold will change one of four places.

Note there are **two** `CrawlSettings` classes — `api/models/job.py:39` (Pydantic, persisted
on the job) and `api/crawler/engine.py:267` (a dataclass, the engine's own). Only the engine's
carries this field, so the fix touches one of them.

### 1.2 The `cryptography` pin was chosen by matching, not by deciding

`requirements.txt:43` pins `cryptography~=48.0.0`; the venv has 48.0.0. `docs/TODO-ARCHIVE.md`
records the reason in its own words: *"pinned to `~=48.0.0` to match the dev venv… the pin was
chosen to match what the suite was verified against"* — a security-sensitive library whose
version is a side effect of one machine's state.

`pip index versions cryptography` resolves: **50.0.1 is current**, and 49.0.0 and 48.0.1 sit
between. So this is decidable on evidence rather than left as a note.

Its whole use in this codebase is `Fernet` for the GSC credential file (`gsc.py:92,102`) —
symmetric encryption of a token at rest. Small surface, high consequence.

## 2. Change

### 2.1 The number has one home and a test that says so

`engine.CrawlSettings.page_size_limit_kb` defaults from
`registry._DEFAULT_PAGE_SIZE_LIMIT_KB` instead of repeating `300`. The two prose statements
stay (a doc may say the value) but a test reads them and asserts they match the constant, so a
change to the threshold fails the build rather than leaving three stale sentences — the
treatment `docs/issue-codes.md` already gets.

### 2.2 The pin moves to the current release, on evidence

Bump to `cryptography~=50.0` and **run the suite against it**. The bump is only justified if:

- the full suite is green on the installed version, and
- the GSC credential round-trip specifically is exercised — encrypt then decrypt through the
  real `_load_creds`/save path, not just an import.

If either fails, the pin stays where it is and the reason is recorded — a red suite is a
reason, "it matched the venv" is not. `tests/test_declared_environment.py` already fails when
the installed set stops satisfying `requirements.txt`, so the pin and the venv cannot silently
part company.

**This is the one item in Phase 8 that can break production**, so the acceptance is
behavioural, not "the version string changed".

## 3. Tests

| # | Test | Goes red when |
|---|---|---|
| 3.1 | `test_the_engine_default_is_the_registry_constant` | the literal comes back |
| 3.2 | `test_the_docs_state_the_same_page_size_limit` | a doc drifts from the constant |
| 3.3 | `test_changing_the_constant_moves_the_engine_default` | the link is by value, not reference |
| 3.4 | `test_gsc_credentials_round_trip_through_fernet` | the bumped library breaks the one thing it is used for |

**Adversarial cases:**

- **3.3 is the one that matters.** `page_size_limit_kb: int = _DEFAULT_PAGE_SIZE_LIMIT_KB`
  evaluated at import is a *copy*: 3.1 passes for a dataclass that read the constant once and
  a hand-written `300` alike, because both equal 300 today. 3.3 patches the constant and
  asserts a newly constructed `CrawlSettings` follows it, which distinguishes a reference from
  a coincidence. (If the dataclass genuinely cannot follow a patched module constant, that is
  the finding, and the test becomes the structural one instead — stated here so the outcome is
  reported either way rather than quietly weakened.)
- **3.4 exercises encrypt→decrypt through the real credential path**, because an import-only
  check passes against a library that loads and then fails on use — the exact shape of a
  dependency bump going wrong.
- **3.2 reads the docs and asserts against the constant**, one side against the other's live
  value (LEARNINGS item 13), rather than two assertions that agree with each other.

## 4. Considered and rejected

- **Move the number into `docs/thresholds.md` as the literal source.** Rejected: the doc is
  the *catalogue* of thresholds, not the runtime source; code reading values out of Markdown is
  worse than two constants. `thresholds.md` names the owner, which is its job.
- **Delete the engine's field and always use the registry constant.** Rejected: it is
  per-job-configurable by design (`docs/thresholds.md:81` says so), so the field is not
  duplication — only its default was.
- **Bump `cryptography` without running the suite.** Rejected on its face; that would replace
  one unexamined pin with another.
- **Leave the pin and record it.** Rejected because the index is reachable and the suite runs
  in three minutes: "we could not check" is not true here.
- **Bump every pin while in the file.** Rejected: one security-sensitive library with a
  4-line usage surface is a bounded change with a testable claim; a wholesale upgrade is not
  this item.

## 5. Not in scope

- Other numbers stated in both code and prose. If 3.2's approach works, generalising it is its
  own item; guessing at scope here would make an engineering-debt task open-ended.

## 6. Done when

- `300` appears once in code, and the docs that repeat it are pinned to it by a test.
- The engine default follows the constant by reference, proved by patching it.
- `cryptography` is either on the current release with a green suite and a working credential
  round-trip, or unchanged with the failure recorded as the reason.

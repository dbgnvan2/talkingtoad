# Micro-spec E2: Report every page that links to a broken target, not just the first

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: `api/crawler/engine.py`, `api/routers/crawl.py`, `api/crawler/checkers/links.py`
Codes affected: `BROKEN_LINK_404`, `BROKEN_LINK_410`, `BROKEN_LINK_503`, `BROKEN_LINK_5XX`,
`EXTERNAL_LINK_TIMEOUT`, `REDIRECT_301`, `REDIRECT_302`

## Problem (verified on job `05cd2496`, 2026-08-29)

TalkingToad reported **10 dead links**. An independent Semrush audit of the same site
reported **120 internal links pointing to broken targets** across nine 4xx destinations.

Both are right about *which* targets are broken — TalkingToad found all nine, exactly
matching the external audit's list. The difference is scope: TalkingToad reports one
**target**; the remediation job is 120 **links**.

The per-target occurrence machinery already exists and is correct
(`collapse_per_target_occurrences`, `links.py:34`, spec §2). It is simply never fed more
than one row per target, because both discovery paths discard the other source pages:

- `engine.py:432` / `:661` — `external_targets_seen: set[str]` skips a link whose target
  has already been queued. Correct as a *fetch* dedupe; wrong as *attribution* — the second
  and subsequent source pages are dropped on the floor.
- `engine.py:654` — `discovered_from.setdefault(norm, url)` keeps only the first
  discovering page for an internal URL that later turns out to be 4xx.

Result, from the database:

```
extra = {"source_url": "…/s3-special-family-life-cycle-monica-mcgoldrick",
         "occurrences": 1, "occurrence_urls": ["…/s3-special-family-life-cycle-monica-mcgoldrick"]}
```

for `/dontation_form` — a misspelled URL that the external audit found repeated across many
posts via a reusable Elementor block. Without the full source list the operator cannot see
that this is one template edit, so the finding reads as nine unrelated chores.

### Two data-fidelity bugs in the same path

- `routers/crawl.py:358` hardcodes `link_type="external"` for **every** broken link. Same-host
  URLs (`https://livingsystems.ca/dontation_form`) are stored as external. Any consumer that
  filters `link_type == "internal"` sees zero internal broken links.
- `status_code` is never written. Every one of the 16 stored rows has `is_broken=1` and
  `status_code=NULL`, so "which of these is a 404 vs a 503" is unanswerable from the table —
  a P1 concern, since a 503 is transient and a 404 is not.

## Change

### E2.1 — Keep all sources per target

Replace the dedupe set with a source map, in both paths:

```python
# engine.py — external path
external_target_sources: dict[str, list[dict]] = {}   # target -> [{source_url, link_text}]
# engine.py — internal path
discovered_from_all: dict[str, list[str]] = {}        # normalised url -> [source pages]
```

Fetch dedupe is preserved: a target is queued for checking on **first** sight; later sightings
append to the source list without re-queueing. `_EXTERNAL_LINK_CAP_PER_PAGE` still limits how
many *distinct targets* one page contributes; it no longer limits attribution.

`discovered_from.setdefault(...)` is kept as-is for the depth/parent semantics that other code
relies on — `discovered_from_all` is additive, so nothing that reads `discovered_from` changes
(guards against P12).

### E2.2 — Emit one issue per target carrying every source

When a target resolves broken, emit **one** issue with:

```python
extra = {
    "target_url": target,
    "source_url": sources[0]["source_url"],       # kept for backwards compat
    "occurrences": len(sources),                   # ← now the true link count
    "occurrence_urls": [s["source_url"] for s in sources[:_SOURCE_LIST_CAP]],
    "occurrence_urls_total": len(sources),         # ← so the UI can say "50 of 120"
    "anchor_texts": [s["link_text"] for s in sources[:_SOURCE_LIST_CAP] if s["link_text"]],
}
```

`_SOURCE_LIST_CAP = int(os.getenv("TT_BROKEN_LINK_SOURCE_CAP", "50"))` (rule 8). Whenever
`occurrence_urls_total > len(occurrence_urls)` every surface prints **"showing 50 of 120
linking pages"** (rule 6 — a cap must announce what it drops). The Excel export carries the
uncapped list.

`collapse_per_target_occurrences` needs no logic change, but its `_evidence` helper currently
prefers `target_url`, which for a broken-link row is the target the issue is *about*, not the
evidence the operator needs. For the `BROKEN_LINK_*` / `EXTERNAL_LINK_TIMEOUT` codes the
evidence list becomes the **source pages**. Redirect codes keep `redirect_to`.

Note the impact multiplier: `occurrence_multiplier` caps at 2.0 at n=5
(`min(1 + 0.25·(n−1), 2.0)`). A target linked from 120 pages and one linked from 5 score
identically. That is deliberate (§2, anti-domination) and E2 does **not** change it — but it
means the *count* must be visible in the text even though it is flat in the score.

### E2.3 — Store link records faithfully

`routers/crawl.py:353` builds one `Link` per (target, source) pair with:

- `link_type` derived by the existing same-registrable-domain logic
  (`normaliser.is_same_domain`), not hardcoded.
- `status_code` carried through from the check. `CrawlResult.broken_link_sources` widens from
  `tuple[str, str, str | None]` to a `BrokenLinkRef` dataclass
  (`target`, `source`, `link_text`, `status_code`, `link_type`) — a **return-contract change**,
  so per P22 every call site is updated in the same change (`engine.py:602`, `:752`, `:760`,
  `:1018`, `routers/crawl.py:353`) and a test asserts no caller still unpacks a 3-tuple.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| E2.1a | Three pages linking to one broken target → one issue with `occurrences == 3` | `tests/test_per_target_occurrences.py::test_e2_1a_three_sources_one_issue` |
| E2.1b | The broken target is fetched **once** despite three sources | `…::test_e2_1b_target_fetched_once` |
| E2.1c | Internal 4xx discovered from two parents lists both | `tests/test_crawl_engine.py::test_e2_1c_internal_404_lists_all_parents` |
| E2.1d | `discovered_from` (depth/parent) semantics unchanged (P12) | `…::test_e2_1d_discovered_from_unchanged` |
| E2.2a | `occurrence_urls` holds source pages, not the target | `tests/test_per_target_occurrences.py::test_e2_2a_evidence_is_source_pages` |
| E2.2b | **Real-scale (P9):** 120 sources → `occurrence_urls` capped at 50, `occurrence_urls_total == 120` | `…::test_e2_2b_source_cap_announced_at_scale` |
| E2.2c | PDF and Excel print "showing 50 of 120 linking pages" | `tests/test_report_integration.py::test_e2_2c_cap_disclosed_in_report` |
| E2.2d | Redirect codes still use `redirect_to` as evidence (no regression) | `tests/test_per_target_occurrences.py::test_e2_2d_redirect_evidence_unchanged` |
| E2.3a | Same-host broken target stored `link_type == "internal"` | `tests/test_link_classifier.py::test_e2_3a_same_host_broken_link_is_internal` |
| E2.3b | `status_code` persisted (404 vs 503 distinguishable) | `tests/test_job_store.py::test_e2_3b_broken_link_status_code_persisted` |
| E2.3c | **P22 guard:** no call site unpacks the old 3-tuple | `tests/test_architecture_constraints.py::test_e2_3c_no_legacy_broken_link_tuple_unpack` |
| E2.3d | **P1:** a 503 target is recorded retryable, not as a permanent 404 | `tests/test_crawl_engine.py::test_e2_3d_503_is_retryable_not_terminal` |

Fix→test map (P10): **E2.2b first** — the real-scale test is the one that proves the bug is
gone; E2.1a alone would pass on a 3-page toy fixture that never exercises the cap.

## Frontend surfaces (P25 — every entry point, not just the library)

| Surface | Must show | Test |
|---|---|---|
| Results issue card | full source list + "N of M" | `frontend/src/pages/__tests__/IssueCardBrokenLink.test.jsx` |
| `GET /api/crawl/{job_id}/pages/issues` | `occurrence_urls_total` in `extra` | `tests/test_crawl_router_contracts.py::test_e2_broken_link_extra_contract` |
| PDF export | source list, capped and disclosed | `tests/test_report_integration.py::test_e2_2c_cap_disclosed_in_report` |
| Excel export | uncapped source list | `tests/test_excel_generator.py::test_e2_excel_lists_all_sources` |
| Fix Manager | groups by target, offers the template fix | `tests/test_fix_focus.py::test_e2_broken_link_grouped_by_target` |

## Adjacent issues found, not fixed (rule 10)

- `_EXTERNAL_LINK_CAP_PER_JOB` and `_EXTERNAL_LINK_CAP_PER_PAGE` do not announce what they
  drop. Same class as E1.4 but on a different data path — flagged, not changed here.
- `EXTERNAL_LINK_SKIPPED` (bot-blocking domains) is recorded as a finding but never re-checked;
  a P1 transient-vs-terminal question worth its own spec.

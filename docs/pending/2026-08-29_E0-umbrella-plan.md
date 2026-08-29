# Umbrella plan E0: seven enhancements from the external-audit comparison

Date: 2026-08-29
Status: **proposal — awaiting approval. No source code has been modified.**
Trigger: comparison of the TalkingToad report for job `05cd2496` (272 pages, 2026-08-29)
against an independent Semrush + GSC + GA4 + WordPress audit of livingsystems.ca dated
2026-08-21.

## The seven specs

| ID | Spec | Kind | Evidence |
|---|---|---|---|
| **E1** | [Lazy-loaded image extraction](2026-08-29_E1-lazy-loaded-image-extraction.md) | **bug** | 9 of 9 images on a live page invisible to the parser; 13 images stored across 272 pages; a real alt-text finding silenced |
| **E2** | [Broken-link source attribution](2026-08-29_E2-broken-link-source-attribution.md) | **bug** | 10 reported vs 120 actual linking pages; `link_type` hardcoded; `status_code` never stored |
| **E3** | [Performance data in the report](2026-08-29_E3-performance-data-in-report.md) | wiring (P25) | 555 ledger rows held, zero used by the PDF |
| **E4** | [Site prevalence escalation](2026-08-29_E4-site-prevalence-escalation.md) | feature | health 89 / 0 critical vs an independent 58/100 |
| **E5** | [Entity value checks](2026-08-29_E5-entity-value-checks.md) | feature | live schema: `"site logo"`, `telephone: []`, 7-day default hours, `Place` with no address |
| **E6** | [Stacked duplicate links](2026-08-29_E6-stacked-duplicate-links.md) | feature | the one real pattern behind an 83-vs-1 discrepancy |
| **E7** | [Report roadmap and caveats](2026-08-29_E7-report-roadmap-and-caveats.md) | feature | no owners, no phases, no exit criteria, no scope statement |

Every number above was verified against the live site or the database on 2026-08-29, not
inferred from the external report.

## Order and dependencies

```
E1 ──────────────────────────────┐
E2 ──────────────────────────────┤
E5 ──────────────────────────────┼──► E4 ──┐
E6 ──────────────────────────────┘         ├──► E7
E3 ────────────────────────────────────────┘
```

1. **E1** — first. It is a silent data loss behind a reassuring 97% score, and it changes what
   every later section reports on. Nothing else should be measured until the crawler sees the
   site.
2. **E2** — second. Same class (under-reported scope), independent of E1, and it is what turns
   nine findings into one template fix.
3. **E3** — third. Pure wiring of shipped code; no detection change, so it can land in parallel
   with E5/E6 if capacity allows.
4. **E5**, **E6** — new checks. Independent of each other.
5. **E4** — after E1/E2/E5/E6, because prevalence should be computed over the corrected and
   complete finding set. Running it earlier would bake in today's undercounts.
6. **E7** — last. It consumes E3's traffic data, E4's tiers, and E1/E2's cap counters.

E1 and E2 are bug fixes and are worth landing on their own even if the rest is deferred.
E4 and E7 are the two that change how the report *reads*, and they should ship together or not
at all — E7's phases are meaningless without E4's tiers.

## Per-item completion (CLAUDE.md standing rules)

Each of the seven, on completion: fold its pending file into
`docs/functional-specification.md`, add any new numeric bounds to `docs/thresholds.md`,
regenerate `docs/issue-codes.md` where codes changed, delete the pending file, record the V4
explainer in `PLAN-V4.0.md`, run `learning-qa` over the diff, then `git push origin main`.

New thresholds arriving: `TT_IMAGE_URL_CAP_PER_JOB` (E1), `TT_BROKEN_LINK_SOURCE_CAP` (E2),
`TT_PERF_STALE_DAYS` (E3), the two prevalence tier bounds (E4).

New config files, all JSON — the repo has no PyYAML dependency and adding one for four small
files is not justified: `api/config/prevalence.json` (E4),
`api/config/entity_values.json` (E5), `api/config/link_patterns.json` (E6),
`api/config/remediation_owners.json` (E7). Each gets a loader with a schema check that fails
loudly at import, and a test asserting every issue code it names exists in `_CATALOGUE`.

## Test totals

Roughly 70 new tests across the seven specs. The ones written **first** in each, per P10:

| Spec | First test | Why |
|---|---|---|
| E1 | real Smush page yields 9 images, not 0 | a synthetic `<img src>` fixture is what let the bug live |
| E2 | 120 sources → capped at 50, total 120 | a 3-source toy fixture never exercises the cap |
| E3 | zero-traffic page with 40 notices must not outrank a 15,000-impression page | states the point of the change |
| E4 | health score byte-identical to pre-E4 | the largest risk is silently moving the score |
| E5 | real homepage fires exactly four codes; a real clean site fires none | P20 — ideal examples are not calibration |
| E6 | header logo + "Home" link must not fire | present on every site; a naive version flags them all |
| E7 | omitted section is named in Caveats | a silent omission must never read as a pass |

Five real saved artifacts are checked in as fixtures (two shared between E1 and E5). No test
makes a live HTTP call.

## Deferred — needs your decision, not silently dropped

These were named in the comparison as things the external audit has and TalkingToad does not.
Each needs a decision I should not make alone.

**D1 — Off-site authority, backlinks, directory listings.** The external audit reported
Authority Score 22, 187 referring domains, 707 backlinks, and 42 of 47 listings flagged. Every
one of those requires a paid third-party API (Semrush, Ahrefs, Moz) with a recurring cost and
a per-customer key — which lands squarely in the parked multi-tenant work
(`docs/TODO-MULTITENANT.md`). **Recommendation: do not build.** State it in E7's "not checked"
list and let the client's agency supply it.

**D2 — Core Web Vitals / field performance.** Buildable on Google's free PageSpeed Insights
API (lab data) or the CrUX API (field data). Needs an API key, has a hard rate limit that a
272-page crawl would exhaust, and would add minutes to every run. **Recommendation: build it,
but scoped to the E3 priority queue's top 10–20 pages only, as its own spec.** Say the word
and I will write it.

**D3 — WordPress plugin and settings audit.** The external audit's most operationally useful
material — 22 plugins, five pending updates, Duplicator installed with zero backups ever
taken, Security Optimizer inactive. `wp_client.py` already authenticates and could read
`/wp/v2/plugins`. But `engine.py` carries an explicit architectural constraint —
*"the SCAN process must NEVER call WordPress API"* — enforced by
`test_architecture_constraints.py`. **Recommendation: build it as a separate opt-in
post-scan step with its own endpoint, never inside the crawl**, so the constraint holds. Needs
your approval on the architecture before a spec.

**D4 — Proposed replacement copy per priority page.** The external audit drafted a title,
description, H1 and lead paragraph for six pages. `advisor.py` and `rewriter.py` could
generate these for the E3 top pages. **Recommendation: decide deliberately.** Putting
AI-drafted client-facing copy inside an audit PDF changes what the document is, and the
external audit itself required human review of its drafts before publication. If you want it,
it needs a review/approval gate in the UI, not a straight-to-PDF path.

## What I am asking for

Approval to implement — all seven, a subset, or one at a time. And a decision on D1–D4.

Per CLAUDE.md I have written no source code and touched no protected file. The only changes
in this commit are these eight documents under `docs/pending/`.

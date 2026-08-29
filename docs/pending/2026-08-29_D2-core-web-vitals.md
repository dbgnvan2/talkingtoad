# Micro-spec D2: Core Web Vitals — field data first, lab data as the fallback

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: new `api/services/web_vitals.py`, new `api/config/web_vitals.json`,
`api/routers/crawl.py` (new opt-in endpoint), report §7.4, registry
New codes: `CWV_LCP_POOR`, `CWV_INP_POOR`, `CWV_CLS_POOR`
Origin: D2 in the E-series umbrella plan.

## The architectural question, answered first

The producer contract states:

> *"It does not do OAuth to Google — the producer owns acquisition; TalkingToad
> owns consumption."*

That rule is about **OAuth- and property-scoped** data: GSC and GA4 require a
human to authorise access to *their* account. The PageSpeed Insights and CrUX
APIs are a different class — **API-key gated, public, and callable for any URL**
without account access. Reading them does not violate the principle; it does not
touch anyone's account.

So D2 is TalkingToad's to build. That is a deliberate reading of the rule, not a
workaround of it, and it is recorded here so the next person does not re-litigate it.

## Field and lab are different measurements and must never be conflated

| | CrUX API (field) | PSI API (lab) |
|---|---|---|
| What it is | 28-day rolling aggregate of **real Chrome users** | One synthetic Lighthouse run in a Google datacentre |
| Coverage | Only URLs/origins with enough traffic to anonymise | Any URL |
| Answers | "Is this slow **for people**?" | "Why might this be slow?" |

Google is **discontinuing CrUX field data in the PSI API response**, so field data
comes from the CrUX API directly and lab data from PSI. Two calls, two meanings.

The honesty requirement follows from that table: **every number rendered must be
labelled field or lab.** A lab LCP presented as a user experience is the P2 shape —
a plausible number standing in for a measurement nobody took. Only field data
drives a finding; lab data is diagnostic context.

## D2.1 — Scope: opt-in, post-scan, top-N only

Never inside the crawl. The engine's speed and universality are load-bearing, and
the binding PSI/CrUX constraint is **100 queries per 100 seconds** (the daily
25,000 is not the limit that bites). At ~1 req/s, a 272-page site would add ~4.5
minutes to every run for data that only matters on the pages that earn traffic.

- New endpoint `POST /api/crawl/{job_id}/web-vitals`, user-triggered, mirroring
  the existing Verify-All / Orphaned-Media pattern.
- Targets the **top N pages of the §6.9 priority queue** (`TT_CWV_TOP_N`, default
  10, hard max 25) — the pages E3 already established are worth the work.
- Results persist on the job so a re-export does not re-fetch (P8: the second run
  reads stored results, and a test covers it).
- Rate-limited client-side to stay inside the published quota, with the ceiling in
  config rather than a literal (rule 8).

## D2.2 — Acquisition

`api/services/web_vitals.py`:

```python
async def fetch_field_vitals(urls: list[str]) -> dict[str, FieldVitals | None]
async def fetch_lab_vitals(url: str) -> LabVitals | None
async def collect_web_vitals(store, job_id, *, top_n: int) -> WebVitalsReport
```

Order per URL: **CrUX first**. If CrUX has no record (the common case for a
low-traffic nonprofit page), fall back to PSI lab and mark the row `source: "lab"`.
If both fail, the row is `source: "unavailable"` with the reason — never a zero.

Hardened as a class (P5), matching every other external call in the repo: timeout,
retry with backoff, and a typed error. A 429 is **retryable, never a terminal
"no data"** (P1) — that distinction is the whole reason this section can be
trusted, since quota exhaustion on page 9 of 10 would otherwise silently look
like "page 9 is fine".

`TT_PSI_API_KEY` is optional. Absent → the section is omitted and the omission is
named in Caveats (E7.4), exactly as the performance section behaves. The key is
read from env only; it is never logged and never written to the DB
(`standards/security.md`).

## D2.3 — Findings, and their limits

Three codes, all **field-data only**. A lab measurement must never raise a finding
about real-user experience.

| Code | Fires when (field, p75) | Severity |
|---|---|---|
| `CWV_LCP_POOR` | LCP > 4.0s | warning |
| `CWV_INP_POOR` | INP > 500ms | warning |
| `CWV_CLS_POOR` | CLS > 0.25 | warning |

Thresholds are Google's own "poor" boundaries and live in
`api/config/web_vitals.json` (rule 8/9), not in Python. Only the **poor** band
fires — "needs improvement" is reported as a number, not as a defect, because a
report that flags two thirds of the web as broken is noise.

These are page-scoped, `developer_needed`, and carry `Established` confidence:
Core Web Vitals are a confirmed Google ranking input, which is a stronger evidence
tier than most of the AI-readiness catalogue.

**What this cannot tell you**, stated in the code help text and in Caveats: CrUX
is a 28-day rolling window, so a fix made yesterday will not show for weeks; and a
page with no CrUX record is not a fast page, it is an unmeasured one.

## D2.4 — Surfaces (P25)

| Surface | Shows | Test |
|---|---|---|
| `POST /api/crawl/{id}/web-vitals` | the report payload | `tests/test_web_vitals.py::TestEndpoint` |
| PDF §7.4 | a Core Web Vitals block under Search Performance, each row labelled field/lab | `tests/test_web_vitals_report.py` |
| Excel | a Web Vitals tab | `…::test_d2_excel_tab` |
| Results GUI | a button beside Verify All, and CWV columns on Priority Pages | `frontend`: `WebVitalsPanel.test.jsx` |
| Caveats | "Core Web Vitals" moves out of the *not checked* list **only when the section actually ran** | `tests/test_report_roadmap.py::test_d2_caveats_tracks_whether_cwv_ran` |

That last row matters: E7's Caveats currently promises Core Web Vitals are not
checked. Shipping D2 without updating it would make the report lie in the other
direction.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| D2.1a | Only the top N priority pages are fetched; N is config-capped at 25 | `tests/test_web_vitals.py::test_d2_1a_top_n_only` |
| D2.1b | The crawl engine never calls PSI or CrUX — architecture guard, same shape as the WP-in-scan test | `tests/test_architecture_constraints.py::test_d2_1b_scan_never_calls_web_vitals_apis` |
| D2.1c | **Dirty-state (P8):** a second export reads stored results and issues no new API calls | `…::test_d2_1c_second_export_does_not_refetch` |
| D2.2a | CrUX hit → `source == "field"`; CrUX miss → PSI lab → `source == "lab"` | `…::test_d2_2a_field_preferred_lab_fallback` |
| D2.2b | **P1:** a 429 is retried and, if still failing, recorded as retryable-unavailable — never as "no data" or a zero | `…::test_d2_2b_quota_exhaustion_is_retryable_not_terminal` |
| D2.2c | Every external call has a timeout and bounded retries (P5) | `…::test_d2_2c_calls_are_hardened` |
| D2.2d | No API key → section omitted, omission named in Caveats, no crash | `…::test_d2_2d_no_key_degrades_cleanly` |
| D2.2e | The API key never appears in a log record or a stored row | `…::test_d2_2e_key_never_logged_or_persisted` |
| D2.3a | Field LCP 4.5s fires `CWV_LCP_POOR`; field LCP 3.0s does not | `…::test_d2_3a_poor_band_only` |
| D2.3b | **Adversarial (P7):** a *lab* LCP of 6s must NOT fire a finding — lab is diagnostic only | `…::test_d2_3b_lab_data_never_raises_a_finding` |
| D2.3c | A URL with no CrUX record is reported "not measured", never "good" | `…::test_d2_3c_unmeasured_is_not_good` |
| D2.3d | Catalogue ↔ issueHelp ↔ scoring ↔ confidence parity for the three codes | `tests/test_issue_codes_doc_in_sync.py` (existing) |
| D2.4a | Every rendered row states field or lab | `tests/test_web_vitals_report.py::test_d2_4a_source_always_labelled` |
| D2.4b | Caveats stops claiming CWV are unchecked once they are, and resumes when the section is skipped | `tests/test_report_roadmap.py::test_d2_caveats_tracks_whether_cwv_ran` |

Fix→test map (P10): **D2.3b first.** Conflating a synthetic lab number with real
user experience is the one mistake that would make this section actively
misleading rather than merely incomplete.

## Fixtures

Recorded real CrUX and PSI responses for two livingsystems.ca URLs — one with a
CrUX record and one without — checked in under `tests/fixtures/web_vitals/`. Per
P19/P20, calibrating against hand-authored ideal payloads is what lets a parser
drift from what the API actually emits. No test makes a live call.

## Adjacent issues found, not fixed (rule 10)

- `PAGE_SIZE_LARGE` and the `IMG_*` weight codes are TalkingToad's current
  performance proxies. Once real field data exists, they should be re-examined —
  a page flagged heavy that has good field LCP is a false positive worth
  suppressing. Flagged; not changed here.
- `avg_load_time_ms` in the image summary reads 0 on every crawl inspected. It
  looks unpopulated. Not in scope, but it is printed in the PDF today.

## Out of scope

Running Lighthouse locally. PSI is Google's own runner on Google's hardware; a
local Playwright Lighthouse would produce numbers that disagree with Search
Console for reasons no client should have to care about.

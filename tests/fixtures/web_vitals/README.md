# Core Web Vitals fixtures — mixed provenance, read before trusting a test

| File | Provenance | Verified against the live API |
|---|---|---|
| `psi_lab_slow.json` | **RECORDED** from PageSpeed Insights, 2026-08-29 | **Yes** — `TestLiveApiContract` |
| `crux_record_poor.json` | **CONSTRUCTED** from the documented contract | No — see below |
| `crux_no_record.json` | **CONSTRUCTED** from the documented contract | No — see below |

## The PSI fixture is real

Recorded 2026-08-29 from:

```
https://www.googleapis.com/pagespeedonline/v5/runPagespeed
  ?url=https://livingsystems.ca/emotional-pain-and-suffering/&strategy=mobile
```

Values as recorded: **LCP 5.3s · CLS 0.012 · TBT 430ms · Lighthouse 61/100**.
Those are asserted in `test_d2_2a_psi_parsed_as_lab`. They are an artifact, not a
target — if the page changes, re-record and update the assertions.

**Trim applied.** The raw response was 645,853 bytes; almost all of it is
Lighthouse detail the parser never reads. Kept: `id`, `analysisUTCTimestamp`,
`captchaResult`, `lighthouseResult.requestedUrl` / `finalUrl` /
`lighthouseVersion`, the `performance` category, and five audits
(`largest-contentful-paint`, `cumulative-layout-shift`, `total-blocking-time`,
`first-contentful-paint`, `speed-index`). No value was altered. A megabyte
fixture nobody opens is not a better artifact than a 3 KB one somebody reads.

## The CrUX fixtures are still constructed

The Chrome UX Report API is **not enabled** on the key's Google Cloud project, so
no live CrUX response could be recorded:

```
HTTP 403 — Chrome UX Report API has not been used in project 117002993725
           before or it is disabled.
```

That is one click to fix — enable **Chrome UX Report API** on that project. Until
then these two payloads are built from the documented response contract, which is
exactly the setup P19/P20 warn about: a parser calibrated against an idealised
payload rather than what the producer emits.

Two things hold the line meanwhile. `parse_crux` returns `None` on any shape it
does not recognise, so a contract drift degrades to "not measured" rather than a
wrong number. And field data is the **only** source allowed to raise a finding —
so a CrUX parsing gap can cost a finding, but can never invent one.

## When CrUX is enabled

```bash
python -m pytest tests/test_web_vitals.py::TestLiveApiContract -v
```

Then record a real CrUX record and a real 404 ("no record" — use a URL with too
little traffic to report), replace both files, and update the table above.

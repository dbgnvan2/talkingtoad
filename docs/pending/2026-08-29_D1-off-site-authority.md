# Micro-spec D1: Off-site authority — decline the vendor index, extend the bundle

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: `docs/pending/2026-08-11_performance-bundle-producer-contract.md` (producer side),
`api/models/performance.py`, `api/services/page_priority.py`, report §7.4
Origin: D1 in the E-series umbrella plan.

## What the external audit had that TalkingToad does not

> Authority Score 22 · 187 referring domains · 707 backlinks · 42 of 47 local
> listings flagged for correction · "Listing Management rates local listings Bad"

Every one of those numbers came from Semrush's own crawl index.

## The decision: do not buy a backlink index

**Recommendation: decline.** Not because off-site data is unimportant — it is one
of the two real gaps in TalkingToad's coverage — but because the only way to get
it is to rent someone else's index, and the cost lands in exactly the wrong place.

| Source | Reality |
|---|---|
| Semrush / Ahrefs / Majestic | Paid API, priced in credits. An entry API tier is a recurring cost per deployment, and every audited domain consumes credits. |
| Moz | Cheaper, materially thinner link graph. Buying weaker data to fill a checkbox is worse than declaring the gap. |
| Common Crawl | Free, but building a backlink index from it is a data-engineering project with its own storage and refresh problem. Not a feature. |

Worse, a paid key is **per-deployment or per-customer**, which is the parked
multi-tenant work (`docs/TODO-MULTITENANT.md`). D1 as a vendor integration cannot
ship without first un-parking a decision the owner deliberately deferred.

So the honest answer is not "off-site is out of scope." It is: **stop trying to
buy the third-party estimate, and take the first-party data that is already free.**

## D1.1 — Google already reports your links, and the producer can already fetch them

Search Console has a Links report: top linking sites, top linked pages, top
linking text, and total external link count. It is first-party, free, requires no
vendor, and covers the same question the Authority Score was a proxy for.

It is OAuth- and property-scoped, which puts it squarely on the producer side of
the existing architectural line:

> *"It does not do OAuth to Google — the producer owns acquisition; TalkingToad
> owns consumption."* — `2026-08-11_performance-bundle-producer-contract.md`

So D1 is a **contract extension, not a new integration**. Add a `links` section to
the Performance Bundle:

```jsonc
"links": {
  "generated_at": "2026-08-29T00:00:00Z",
  "total_external_links": 707,          // GSC Links > External links > total
  "referring_domains": 187,             // distinct linking sites
  "top_linking_sites": [                // GSC "Top linking sites"
    {"domain": "example.edu", "linking_pages": 14, "target_pages": 3}
  ],
  "top_linked_pages": [                 // GSC "Top linked pages" — joins to the crawl
    {"url": "https://livingsystems.ca/emotional-pain-and-suffering/",
     "incoming_links": 41, "linking_sites": 12}
  ],
  "top_linking_text": [{"text": "bowen theory", "count": 22}]
}
```

Acquisition source for every field: the GSC **Search Console API** links data the
producer already authenticates for. No new vendor, no new key, no multi-tenant
prerequisite.

## D1.2 — What TalkingToad does with it (consumption)

The value is not the number; it is the **join to the crawl**, which no SEO tool
that lacks your crawl can do:

- **Authority vs health.** A page with 41 incoming links and a health score of 62
  is the highest-leverage fix on the site: earned authority pointing at a page
  with fixable defects. This becomes a bucket in the §6.9 Authority Matrix and a
  column in Priority Pages.
- **Earned links pointing at broken targets.** `top_linked_pages` joined against
  the E2 broken-link set finds external sites linking to URLs that 404 — link
  equity being thrown away, and a redirect fixes it. This is the single most
  actionable off-site finding and it is *only* available to a tool that has both
  halves.
- **Orphaned authority.** A page with incoming links that the crawl found
  disconnected (`ORPHAN_PAGE`) is authority the site is not circulating.
- Report §7.4 gains an **Off-Site** block: referring domains, total external
  links, top linking sites, and the three joins above.

All of it degrades cleanly: no `links` section in the bundle → the block is
omitted and named in Caveats (E7.4), exactly as the performance section does.

## D1.3 — What stays out, and stays declared

Local listings (the "42 of 47" number) needs Google Business Profile plus a
listings aggregator. GBP is OAuth-scoped, so a future bundle extension could
carry NAP fields from GBP for E5 to reconcile against — but the *aggregator*
half is a paid vendor and is declined for the same reason as the backlink index.

The E7 Caveats "not checked" list changes from a blanket "off-site authority"
line to a precise one: link data from Search Console is included when supplied;
third-party authority scores, full backlink graphs and directory-listing
consistency are not, and here is why.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| D1.1a | Bundle ingest accepts and persists the `links` section; absent section is not an error | `tests/test_performance_ingest.py::test_d1_links_section_ingested` |
| D1.1b | A malformed `links` section is rejected with a named error, never silently dropped | `…::test_d1_malformed_links_fails_loud` |
| D1.2a | A page with high incoming links and low health is surfaced above a high-health page with the same link count | `tests/test_page_priority.py::test_d1_earned_authority_low_health_ranks_first` |
| D1.2b | An externally-linked URL that is in the broken-link set is reported as lost link equity | `tests/test_offsite.py::test_d1_external_links_to_broken_target` |
| D1.2c | An externally-linked page flagged `ORPHAN_PAGE` is reported as uncirculated authority | `…::test_d1_orphaned_authority` |
| D1.2d | The link join uses `ledger_key`, so a trailing-slash mismatch cannot silently drop rows (the E3 bug, same class) | `…::test_d1_link_join_tolerates_trailing_slash` |
| D1.2e | **Real-scale (P9):** a 200-domain fixture caps the displayed list and discloses the total | `…::test_d1_top_sites_cap_disclosed` |
| D1.3a | No `links` section → the Off-Site block is omitted **and named in Caveats** | `tests/test_report_roadmap.py::test_d1_offsite_omission_disclosed` |
| D1.3b | Caveats distinguishes "GSC link data not supplied" from "third-party authority scores are never included" | `…::test_d1_caveats_distinguishes_the_two_gaps` |

Fix→test map (P10): **D1.2b first.** "An external site links to a page of yours
that 404s" is the finding that justifies the whole item, and it is the one a
crawler-only or an analytics-only tool cannot produce.

## Cost

Producer-side work to add one API call and one bundle section. Zero recurring
cost, no new dependency, no multi-tenant prerequisite. TalkingToad-side is a
model field, a join, and a report block.

## Adjacent issues found, not fixed (rule 10)

- The bundle has no schema version. Adding a section is safe today because
  ingest is additive, but a producer/consumer contract with no version is a P19
  waiting to happen. Worth its own small spec.

## Open question for the owner

Does the sibling reporting app currently pull the GSC Links report at all? If
not, D1 is blocked on producer work and should be sequenced behind D2. If it
already has the API scope, this is a small change on both sides.

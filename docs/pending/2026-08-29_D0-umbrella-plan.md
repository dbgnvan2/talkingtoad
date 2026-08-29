# Umbrella plan D0: the four deferred items from the external-audit comparison

Date: 2026-08-29
Status: **proposal — awaiting approval. No source code has been modified.**
Follows: the E-series (E1–E7), shipped 2026-08-29, specs folded into
`docs/functional-specification.md` §4.15 and §7.4–7.7.

These are the four capabilities the external Semrush + GSC + GA4 + WordPress audit
of livingsystems.ca had that TalkingToad does not. Each was flagged during the
E-series as needing an owner decision rather than a unilateral call.

## The four

| ID | Spec | Recommendation | Blocked on |
|---|---|---|---|
| **D1** | [Off-site authority](2026-08-29_D1-off-site-authority.md) | **Decline the vendor index. Extend the Performance Bundle with GSC's own Links report instead.** | Whether the producer app already has the GSC links scope |
| **D2** | [Core Web Vitals](2026-08-29_D2-core-web-vitals.md) | **Build.** Field data from CrUX, lab from PSI, top-N pages only, opt-in | A PSI API key |
| **D3** | [WordPress configuration audit](2026-08-29_D3-wordpress-configuration-audit.md) | **Build — but this one needs a scope decision, not just approval** | Your call on whether TalkingToad becomes partly a WP config reviewer |
| **D4** | [Page blueprints](2026-08-29_D4-page-blueprints.md) | **Build as a tool with a review gate, not as a report section** | Whether approved drafts belong in the client PDF |

## What changed from the E0 recommendations

Two of the four moved once I looked properly.

**D1 was "don't build". It is now "build a different thing."** The recommendation
against renting a backlink index stands — it is a recurring cost, it needs a
per-customer key, and that key drags in the parked multi-tenant work. But Search
Console has its own Links report: referring domains, top linking sites, top linked
pages. It is first-party, free, and already inside the OAuth scope the producer
app holds. So the honest answer was never "off-site is out of reach"; it was
"stop trying to buy the third-party estimate."

And the *join* is worth more than the number ever was. An external site linking to
a URL that 404s is link equity being thrown away — a finding available only to a
tool that holds both the link data and the crawl. Neither Semrush nor GA4 can
produce it alone.

**D2's architecture question resolved cleanly.** The producer contract locks in
"TalkingToad does not do OAuth to Google — the producer owns acquisition." That
rule is about account-scoped data. PSI and CrUX are API-key gated and callable for
any URL without touching anyone's account, so they are a different class and this
is TalkingToad's to build. Recorded in the spec so nobody re-litigates it.

One material fact: Google is **discontinuing CrUX field data in the PSI API
response**. Field data must come from the CrUX API directly. A design that reads
field vitals out of PSI would have been built against an API that is going away.

## Order and dependencies

```
D2 ──────────────────────────────┐
D3 ──────────────────────────────┼──► (independent, ship in any order)
D4 ──────────────────────────────┘
D1 ──► blocked on producer-side work
```

1. **D2 first.** Self-contained, no new architecture, closes a real gap the
   Caveats section currently has to declare. The riskiest part is honesty about
   field vs lab, and that is a test, not a design problem.
2. **D3 second**, if you approve the scope widening. Highest value per line of the
   four — "your backup plugin has never taken a backup" is not something a crawler
   will ever find — but it is the one that changes what the product is.
3. **D4 third.** The gate makes it safe; the grounding check makes it useful. It
   is also the one with the most ways to be subtly wrong, which is why its tests
   lean on P20 and P23 rather than on a single recorded output.
4. **D1 whenever the producer side is ready.** TalkingToad's half is small.

## Shared obligations

Each spec inherits the standards the E-series established, because most of the
E-series bugs came from breaking exactly these:

- **Every cap announces what it drops** (rule 6, P9). D2 caps at top-N; D1 caps
  the linking-sites list. Both disclose.
- **Every omitted section is named in Caveats** (E7.4). D2, D3 and D4 each add a
  section that can be absent, and each must say so rather than letting absence
  read as a pass. D2 and D3 additionally have to *remove* their line from the
  "not checked" list when they do run — E7 currently promises both are unchecked,
  and shipping either without that change would make the report lie in the other
  direction.
- **Unknown is never zero** (P2). The E3 review found `ctr or 0.0` fabricating an
  underperformer; D2 has the same shape waiting in "no CrUX record", which is an
  unmeasured page, not a fast one.
- **Real artifacts as fixtures** (P19/P20). Recorded API responses and real page
  content, never hand-authored ideal payloads — that is what let E1 ship.
- **Editorial content in config** (rule 9). D2's thresholds, D3's plugin-overlap
  map, D1's display caps.
- **New external calls hardened as a class** (P5): timeout, bounded retry,
  backoff, and a transient failure recorded as retryable rather than terminal (P1).

## Cost

| | Recurring cost | New dependency | Multi-tenant prerequisite |
|---|---|---|---|
| D1 | none | none | no |
| D2 | none (free quota) | a PSI API key | no |
| D3 | none | none (credentials exist) | no — but see its adjacent-issues note |
| D4 | LLM tokens per draft | none (AIRouter exists) | no |

None of the four un-parks the multi-tenant work. That was the main reason D1 was
declined in its original form, and the redesign avoids it.

## What I am asking for

Approval to implement — all four, a subset, or one at a time. Plus three decisions
the specs cannot make on their own:

1. **D3's scope.** Does TalkingToad become partly a WordPress configuration
   reviewer? I think yes, and I have said why, but it widens the product.
2. **D4's placement.** Should approved drafts appear in the client PDF, or only in
   an internal export? My recommendation is internal by default with a per-report
   opt-in.
3. **D1's sequencing.** Does the sibling reporting app already hold the GSC links
   scope? If not, D1 is producer work first.

Per CLAUDE.md I have written no source code and touched no protected file. The
only changes in this commit are these five documents under `docs/pending/`.

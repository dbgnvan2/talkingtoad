# Micro-spec D4: Page blueprints — a drafting tool with a review gate, not a report section

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: new `api/services/blueprints.py`, `api/routers/ai.py` (new route),
new `frontend/src/components/BlueprintPanel.jsx`, report §7.9 (approved drafts only)
Origin: D4 in the E-series umbrella plan.

## What the external audit did

It drafted a title, meta description, H1 and lead paragraph for six pages —
homepage, counselling, Bowen theory, Emotional Pain, What Kind of Help Is Helpful,
contact. That is the most immediately usable part of the whole document.

And it carried this, in its own caveats:

> *"Draft page copy must be reviewed for factual accuracy, professional standards,
> accessibility, privacy, crisis-language requirements and brand voice before
> publication."*

A human consultant, writing for a counselling nonprofit, would not let their own
drafts go out unreviewed. Neither should we.

## The decision: build it as a tool, not as a report section

The umbrella plan flagged this as needing a deliberate decision. Here it is, with
the reasoning, because it is the whole shape of the item.

**Recommendation: a drafting panel with an explicit approval step. AI-drafted copy
never reaches the client PDF unapproved.**

Why not straight into the report:

1. **It changes what the document is.** Today the report is a record of
   observations — every line traces to something measured. Dropping generated
   prose into it makes it partly a record and partly a draft, and the reader
   cannot tell which is which. E7 spent its whole budget making that document
   honest about what it knows.
2. **The subject matter.** livingsystems.ca is a counselling nonprofit. Generated
   copy could imply clinical outcomes, misstate sliding-fee eligibility, or soften
   crisis-resource language. TalkingToad has no way to check any of that.
3. **Rule 1.** Never invent content. A draft grounded in the page is fine; a draft
   that invents a service the organisation does not offer is a fabrication with
   the site owner's name on it.

As a tool with a gate, all three resolve: the copy is clearly a draft, a human
approves each one, and only approved text can appear in an export.

## D4.1 — Reuse, don't rebuild

Everything needed exists:

- `api/services/ai_router.py` — provider selection, credentials, usage tracking,
  cost accounting. Every LLM call goes through it (Cycle Z); D4 adds no direct
  provider HTTP.
- `api/services/advisor.py` — page fetch, HTML→markdown, GEO-context injection.
- `api/services/rewriter.py` — the existing low-temperature (0.2) faithful-rewrite
  path, and its `stopped_by_limit` handling.
- `api/models/advisor.py` — request/result shapes and the `GeoConfig` plumbing.
- E3's priority queue — which pages are worth drafting for.
- E5's entity config — the organisation's verified name, location and entities,
  so a draft uses the real ones rather than inferring them.

D4 is a prompt, a grounding check, a persistence table and a panel.

## D4.2 — What it produces

For one page at a time, chosen from the E3 priority queue:

```jsonc
{
  "url": "https://livingsystems.ca/emotional-pain-and-suffering",
  "proposed_title": "...",           // <= 60 chars
  "proposed_meta_description": "...",// 70-160 chars
  "proposed_h1": "...",
  "proposed_lead": "...",            // 40-80 words, answer-first
  "rationale": "...",                // which findings this addresses
  "grounding": {                     // D4.3
    "status": "grounded" | "unverified",
    "unsupported_claims": []
  },
  "source_findings": ["META_DESC_MISSING", "FIRST_VIEWPORT_NO_ANSWER"],
  "status": "draft" | "approved" | "rejected",
  "approved_by": null, "approved_at": null
}
```

Length bounds come from `docs/thresholds.md` — the same numbers
`META_DESC_TOO_LONG` and `TITLE_TOO_LONG` already enforce, so a draft cannot be
generated that the tool would then flag.

## D4.3 — The grounding check is the whole feature

Without it this is a plausible-text generator. With it, it is a drafting aid.

Every draft is checked back against the page it was written from:

- **Verbatim floor.** Proper nouns, numbers, dates, prices and named services in
  the draft must appear in the source page text. Anything that does not is listed
  in `unsupported_claims` and the draft is marked `unverified`.
- **Topical overlap** on the paraphrased parts (the lead), which is necessarily
  looser — but the verbatim floor is never relaxed to compensate. P19's corollary
  is explicit about this: relaxing a grounding check on a paraphrased field while
  dropping the hard floor on the verbatim one lets a hallucination ride through
  on the loosened tier.
- An `unverified` draft is **shown with its unsupported claims listed** and cannot
  be approved until a human clears it. It is never silently discarded — the
  operator needs to see what the model tried to assert.
- **A refusal is not content (P14).** A provider error surfaces as an error state,
  never as a draft.

## D4.4 — The gate

- Drafts persist with `status: "draft"`.
- Approval is an explicit user action per draft, recording who and when.
- **Only `approved` drafts can appear in an export**, in report §7.9, under a
  heading that says they are proposals requiring review before publication.
- No draft is ever written to WordPress. The existing WordPress-safety constraints
  are untouched; this produces text for a human to paste.
- The AI-drafted section carries the same "reviewed by" framing the external audit
  used on its own drafts.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| D4.1a | Every LLM call routes through `AIRouter`; no direct provider HTTP in `blueprints.py` | `tests/test_blueprints.py::test_d4_1a_routes_through_ai_router` |
| D4.1b | Usage and cost are recorded like every other AI path | `…::test_d4_1b_usage_tracked` |
| D4.2a | A generated draft satisfies the same length bounds the catalogue enforces | `…::test_d4_2a_draft_within_thresholds` |
| D4.2b | Drafts can only be generated for pages in the crawl | `…::test_d4_2b_unknown_url_rejected` |
| D4.3a | A draft asserting a service absent from the page is marked `unverified` and the claim listed | `…::test_d4_3a_invented_service_is_caught` |
| D4.3b | **Adversarial (P20):** a fabricated claim with **no proper noun** — an invented stance or causal assertion — is still caught, not just invented names and dates | `…::test_d4_3b_non_specific_fabrication_is_caught` |
| D4.3c | A faithful draft on a real page passes | `…::test_d4_3c_faithful_draft_passes` |
| D4.3d | **P23:** grounding is judged over N independent draws, not one recorded output, and the recurrence rate is reported rather than a binary | `…::test_d4_3d_consensus_over_draws` |
| D4.3e | A provider error surfaces as an error, never as draft text (P14) | `…::test_d4_3e_provider_error_is_not_content` |
| D4.4a | An unapproved draft **cannot** reach the PDF | `tests/test_report_roadmap.py::test_d4_4a_only_approved_drafts_export` |
| D4.4b | An approved draft appears under a heading marking it a proposal for review | `…::test_d4_4b_drafts_labelled_as_proposals` |
| D4.4c | Approval records who and when | `tests/test_blueprints.py::test_d4_4c_approval_audited` |
| D4.4d | **Architecture guard:** nothing in the blueprint path writes to WordPress | `tests/test_architecture_constraints.py::test_d4_4d_blueprints_never_write_to_wp` |
| D4.4e | GUI: the approve control's value actually reaches the export (P25 — not just that the button renders) | `frontend`: `BlueprintPanel.test.jsx` |

Fix→test map (P10): **D4.4a first, then D4.3b.** The gate is the safety property;
the non-proper-noun fabrication case is the one a naive grounding check misses,
and per P20 it is exactly the class an idealised gold set never contains.

## Fixtures

Real page content from the crawl, and recorded model outputs across **N ≥ 5
independent draws** per case (P23) — a single recorded draw is a sample, not
behaviour, and a "locked" regression floor built on one lucky output flips with no
code change. Temperature and model are folded into the fixture staleness key.

## Adjacent issues found, not fixed (rule 10)

- The AI executive summary (`routers/crawl.py`) has no grounding check at all. It
  is generated from issue counts so its fabrication surface is small, but it is
  the same class and currently unguarded. Worth its own spec.
- `advisor.py`'s `_fetch_page` is synchronous inside an async service. Pre-existing.

## Out of scope

Full page rewrites (that is `rewriter.py`'s existing job, and a different
risk profile). Publishing anything. Generating copy for pages outside the crawl.

## Open question for the owner

Should an approved draft appear in the **client** PDF at all, or only in an
internal working export? The external audit put its drafts in the client
document — but a named consultant signed that document. Recommendation: internal
export by default, with a per-report opt-in to include them.

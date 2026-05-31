---
status: draft-future
created: 2026-05-31
scheduled: no
depends_on: v3.0 (issue catalogue + issueHelp.js + report generator stable)
references_readonly: [docs/functional-specification.md, docs/thresholds.md]
---

# TalkingToad v4.0 — Full Feature Explanation Layer

> **Status: future / draft. Not scheduled.** This file exists to *save the idea*
> while it's fresh. Do not implement until v3.0 features have shipped and the user
> explicitly schedules v4. Editable (not `status: current`).

## The idea (one sentence)

Every feature and every issue code should ship with a **plain-language, educational
explanation** — *what it is, why it's useful, what good vs. bad looks like, and how
it can mislead* — so a non-technical nonprofit user understands not just *that* something
is flagged, but *why it matters and what to do*.

## Why this is worth a milestone

TalkingToad's audience is **nonprofit staff, not SEO professionals.** The product's
real value isn't the list of issues — it's making the user *understand their site well
enough to act*. A flagged code with a one-line tooltip teaches nothing; a flagged code
with a short, honest explanation turns the tool into a coach.

The trigger for this spec: during GA1 development, the explanation of
`GEO_SUMMARY_BURIED` (what "answer buried" means, why AI citation depends on it, how a
good section differs from a bad one, and how the check itself could be wrong) was judged
**exactly the level of teaching every feature should provide.** That explanation is
preserved below as the gold-standard template.

---

## The explanation template (derived from the GA1 worked example)

Every feature/issue code's help content should answer these, in this order, in
accessible language (target: an intelligent reader with **no SEO background**):

1. **What it is** — what the check/feature looks at, in one or two plain sentences.
2. **Why it's useful / what's at stake** — the real-world consequence (e.g. "AI engines
   skim for an answer; if it's buried, your page is less likely to be cited").
3. **What it measures** — the mechanism, demystified (no jargon, or jargon defined inline).
4. **Good vs. bad — concrete** — a small comparison (table or 2–3 examples) showing a
   passing case beside a failing case. Show, don't just assert.
5. **How it can mislead** — the honest caveat: false positives/negatives, the evidence
   tier ("Established" / "Reasonable proxy" / "Heuristic"), and *what a correct-looking-
   but-wrong result would look like*. This is the trust-builder.
6. **How to fix** — the concrete action the user takes.

> This **extends** the existing `issueHelp.js` shape (`title`, `definition`, `impact`,
> `fix`, `confidence`) rather than replacing it — fields 4 and 5 (concrete good/bad +
> "how it can mislead") are the new, higher bar.

---

## Gold-standard worked example — `GEO_SUMMARY_BURIED` (verbatim, preserve)

*(This is the explanation that prompted the spec. Use it as the quality bar and the
template's reference implementation.)*

**What it is.** In the citation era, AI engines (ChatGPT, Google AI Overviews, Perplexity)
skim a page and lift a short *answer* to quote or summarize. This check flags pages where
the key answer under a heading isn't easy to find — prompting the user to move the answer up.

**Why it's useful.** If the answer to "what is this section about" isn't immediately under
the heading, the page is less likely to get cited by an AI engine — and skimming humans
miss it too.

**What it measures.** Under each `H2`/`H3`, the first real content (a paragraph, list, or
table) should lead the section. If it's pushed below images, media, or preamble, the answer
is "buried."

**Good vs. bad — concrete.**

| Section shape | Verdict |
|---|---|
| Heading, then the answer paragraph leads → 4 more paragraphs follow | ✅ Not buried (length is fine; the answer leads) |
| Heading, then hero image + video + figure, *then* the answer | ❌ Buried (answer pushed to depth 4) |
| FAQ answer pushed down under an `H3` | ❌ Buried (and the old version missed this) |

**How it can mislead.** Evidence tier: **Heuristic** — no AI vendor has confirmed exact
ranking behaviour, so treat it as a nudge, not a verdict. A *correct-looking-but-wrong*
result would be flagging a perfectly good, content-rich section just for being long — which
the earlier count-based version actually did, and the positional fix removed.

**How to fix.** Reorder each `H2`/`H3` section so the core answer leads in 1–2 sentences,
with supporting detail following. Avoid front-loading sections with hero images or preamble.

---

## Scope (when scheduled)

### In scope
- A **content pass** over all ~132 issue codes: bring each `issueHelp.js` entry up to the
  6-part template, especially fields 4 (good/bad) and 5 (how it can mislead).
- The same for **non-issue features** (FAQ generator, schema factory, GEO report, image
  optimization, etc.) — a short "what it is / what it's useful for" for each major panel.
- **Surfacing:** an expandable "Learn more" / "Why this matters" affordance in the UI
  wherever a code or feature appears (extends existing help tooltips — no nav restructure).
- **Reports:** the PDF/Excel exports include the explanation (or a condensed form) so the
  audit is self-teaching offline.
- **Honesty guard:** the "how it can mislead" + evidence-tier field is **mandatory** — a
  help entry without it is incomplete (candidate for a parity/lint test).

### Out of scope (v4)
- Video/interactive tutorials.
- Per-customer/localized explanation variants.
- AI-generated explanations (these should be human-reviewed canonical copy, not generated
  per request).

## Possible acceptance criteria (draft — refine when scheduled)
1. Every issue code in `_CATALOGUE` has an `issueHelp.js` entry covering all 6 template parts.
2. Every entry has a non-empty evidence-tier + "how it can mislead" field (enforced by a
   parity test alongside the existing catalogue↔help checks).
3. Each major UI panel has a one-paragraph "what it is / why it's useful" explainer.
4. PDF export renders the explanation layer for every flagged code.
5. A documented **style guide** for explanation copy (reading level, no-jargon rule,
   the show-don't-assert rule for good/bad examples).

## Notes for the future author
- This is **content + light UI**, not deep engineering — most of the work is careful writing
  at the right reading level, plus a help-completeness parity test and a render surface.
- The GA1 example above is the bar. If a new explanation isn't as clear as that one, it isn't done.
- Keep it honest: the "how it can mislead" field is what separates a coach from a black box.

---

*Created 2026-05-31 from the GA1 / `GEO_SUMMARY_BURIED` explanation, judged the model for
how every TalkingToad feature should teach the user. Save for future work; not scheduled.*

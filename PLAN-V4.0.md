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

## Additional worked examples (shipped 2026-05-31)

These are the explainers actually shipped with the GEO Authority cycles (GA3, GA4) and
the first M3 audit code (M3.1). They prove the V4 standard is **already being applied
per-cycle** — every new feature now ships its explainer. Two shapes are represented:
*tools* (GA3/GA4 — a card the user operates) and *audit codes* (M3.1 — a diagnostic
`issueHelp.js` entry). Use whichever shape matches the thing being explained.

> **Running tally — every code/feature shipped this run carries a full V4 explainer**
> (`confidence` + `definition` + `impact` + `fix` + `good_vs_bad` + `how_it_can_mislead`),
> verified during review. So the eventual v4 content pass is **already done for these**;
> the remaining work is backfilling the ~120 OLDER codes that predate the standard.
>
> | Cycle | Code(s) / feature | V4 explainer shipped |
> |---|---|---|
> | M3.1 | `SCHEMA_VISIBLE_MISMATCH` | ✅ (the field-shape template) |
> | M3.2 | `AI_CONTENT_NOT_IN_TEXT` | ✅ |
> | M3.3 | `AI_PREVIEW_SUPPRESSED`, `AI_PREVIEW_BLOCKED_AT_BOT` | ✅ |
> | M3.4 | `AI_NO_VISUAL_COMPANION` | ✅ |
> | M3.5 | `AI_MAIN_CONTENT_LOW_RATIO` | ✅ |
> | M4.1 | `CONTENT_DATE_STALE_VISIBLE` | ✅ |
> | M4.2 | `CONTENT_STAT_OUTDATED` | ✅ |
> | M5 | `AI_CITED_PAGE`, `AI_HIGH_VALUE_UNCITED` | ✅ |
> | M7 | (reporting — surfaces the confidence tiers in PDF/Excel, which is V4's "how it can mislead" made visible) | ✅ |
> | GA3 | FAQ Schema Generator (tool) | ✅ |
> | GA4 | Entity Schema Factory (tool) | ✅ |
> | M6 | GSC Performance-Health loop (tool: Authority Matrix + Review-for-Improvements flag) | ✅ (GSCInsightsPanel 5-part explainer shipped in M6.4) |
> | Agent-readiness P1 | `JS_DEPENDENT_NAVIGATION`, `NON_SEMANTIC_BUTTON`, `LANDMARK_MAIN_MISSING`, `LANDMARK_NAV_MISSING`, `INTERACTIVE_NO_ACCESSIBLE_NAME`, `PLACEHOLDER_LINK`, `WRONG_PLACEHOLDER_LINK`, `SCHEMA_ORG_MISSING`, `CONTACT_INFO_NOT_IN_HTML` | ✅ (all 9 ship full 6-part explainers in issueHelp.js) |
> | R5 (scoring model `2026-07-06-r5`) | *No new codes* — scoring-behavior change: unified page-health path (R5.0), `scope: page\|site` + site-scoped single deduction (R5.1), extended suppression clusters + noindex scope-reduction (R5.2/R5.3), Quick-Wins list + `quick_win`/`scope` serialized (R5.4), runtime-derived severity (R5.5), `scoring_model_version` stamp (R5.6). No V4 explainer needed (existing codes keep their explainers; the "how it can mislead" surface is the before/after crawl deploy gate). See functional-specification §4.0.1. | n/a (no new code) |
> | V-series (deploy-gate validation, 2026-07-06) | *No new codes.* V1 closed R3.4 (blanket-robots suppression parent confirmed + tested). V2 fixed a `SCHEMA_VISIBLE_MISMATCH` **false positive** (WP SEO-plugin author-byline `Person` graph node — detector fix in `schema_typing.py`, weight unchanged). V3 real full-crawl before/after: site health **73 → 88 (+15)**, severity shifted warning→info (validates the R3 calibration on live data). V4 GSC Authority-Matrix tooling built + unit-tested; live run blocked-on-connection (owner connects GSC). Spec: `docs/pending/2026-07-06_deploy-gate-validation.md`; artifacts under `docs/review/2026-07-06_*`. | n/a (no new code) |
> | Analytics & Measurement (2026-08-06) | New `analytics` category — `ANALYTICS_TAG_MISSING`, `ANALYTICS_TAG_DUPLICATE`, `ANALYTICS_ID_INCONSISTENT`, `CONSENT_MODE_MISSING`, `SELF_REFERENCING_UTM`, `OUTBOUND_LINK_UNTRACKABLE` (no-API, crawl-time). Spec folded into functional-specification §4.13. | ✅ (all 6 ship full 6-part explainers in issueHelp.js, `mission_impact` + definition/impact/fix) |
> | Fix Focus (2026-08-13) | *No new codes* — new workflow feature: curated priority-fix checklist (SEO + AI/GEO), grouped-by-page, per-page verify. Spec folded into functional-specification §6.11. | ✅ (`FixFocusPanel` ships a 5-part V4 help block: what / why / good-vs-bad / how-it-can-mislead / how-to-use) |
> | E-series (report + crawl fidelity, 2026-08-29) | 5 new codes — `ENTITY_HOURS_DEFAULT`, `ENTITY_NAP_INCOMPLETE`, `ENTITY_FIELD_EMPTY`, `ENTITY_VALUE_PLACEHOLDER` (E5), `LINK_STACKED_DUPLICATE` (E6). Plus report/crawl work with no new codes: E1 lazy-loaded image extraction, E2 broken-link source attribution, E3 performance data in exports, E4 site prevalence + Site Hygiene, E7 remediation roadmap + Scope & Caveats. Specs folded into functional-specification §4.15 and §7.4–7.7. | ✅ (all 5 ship full 6-part explainers in issueHelp.js) |
> | E4/E7 report surfaces (2026-08-29) | *No new codes* — but the **Scope, Method and Caveats** section is V4's "how it can mislead" applied to the report as a whole: it names every cap that bit, every section omitted for lack of data, and everything the audit did not check. The Site Hygiene figure ships with its formula and its distinction from Health printed beside it, so a reader cannot mistake breadth for quality. | ✅ (report-level explainer, always rendered) |
> | D-series (deferred items from the external-audit comparison, 2026-08-29) | 3 new codes — `CWV_LCP_POOR`, `CWV_INP_POOR`, `CWV_CLS_POOR` (D2). Plus three capabilities with no new codes: D1 off-site authority joined to the crawl, D3 read-only WordPress configuration audit, D4 page blueprints behind a review gate. Specs folded into functional-specification §7.4b, §7.8, §7.9, §7.10. | ✅ (all 3 CWV codes ship full 6-part explainers; each explainer's "how it can mislead" carries the field-vs-lab distinction and the 28-day window, which is the single thing a reader could most easily misread) |
> | D2/D4 honesty surfaces (2026-08-29) | *No new codes* — but two V4-shaped guarantees. Core Web Vitals rows state FIELD or LAB on every line, because a synthetic run presented as real-user experience is the clearest "how it can mislead" case in the product. Page blueprints render only after human approval and are labelled as drafts needing review, so generated copy can never be mistaken for a measurement. | ✅ (surface-level explainers, always rendered) |
> | O-series (orphan-detection coverage, 2026-08-29) | *No new codes* — but a V4-shaped honesty surface on an existing one. `ORPHAN_PAGE` is now suppressed when the crawl did not cover the whole site, and the Orphaned Pages panel renders **why** instead of a zero: a partial scan's zero orphans is "not checked", not "none found". This is "how it can mislead" applied to the *absence* of a finding — the case a reader is least equipped to question, because nothing is on screen to doubt. The `ORPHAN_PAGE` caveat also now names the ways a link can be real but unseen (JavaScript, query-driven listings, skipped WordPress archives, pages that failed to fetch). | ✅ for the panel/tile/PDF/Excel disclosures, which always render when coverage was short. ⚠️ the code's new `how_it_can_mislead` field in `issueHelp.js` is **data only** — no component reads that field yet, here or on the ~30 pre-existing entries that carry it. Wiring it is v4 content-pass work. |
> | IM1 (image dimensions, 2026-08-30) | *No new codes* — but four existing ones stop being silently dead: `IMG_OVERSCALED`, `IMG_NO_SRCSET`, `IMG_DUPLICATE_CONTENT`, `IMG_SLOW_LOAD` had no pixel data and could not fire in 156 jobs. `images_measured` / `images_measurable` disclose the shortfall, so an unmeasured image renders as *not checked*, never *clean*. | ✅ (disclosure surface; the four codes' own explainers are v4 content-pass work) |
> | **V1 — evidence basis (2026-08-30)** | *No new codes* — and the most V4-shaped change in the product so far. Every one of the 170 codes now declares whether it rests on a published source (107), on TalkingToad's own judgement (57), or on a measurement made during the crawl (6). `docs/issue-codes.md` renders each basis, and a citation whose check fires on a number the source does not publish must carry **What the source does not say**. This *is* "how it can mislead", written once per code and enforced by tests rather than by good intentions — and it settles the question the v4 content pass would otherwise have had to answer 170 times: what may this explainer claim? | ✅ (all 170 codes; rendered in the generated docs. The v4 content pass should treat `authority.yaml` as the source for each explainer's confidence/mislead sections rather than re-deriving them.) |
> | **D5 — the re-check reports what it checked (2026-09-01)** | *No new codes* — a V4 honesty surface on an **action** rather than on a finding, and the first one prompted by a user saying the feature "doesn't seem to do anything". The Page Audit re-check discarded its whole response, so success, no-change and outright failure all rendered identically; a page blocked by Cloudflare (returned as HTTP 200 with a caveat) looked like a plain reload. Worse, it *resolved* the 24 `needs_full_crawl` codes it had simultaneously declared it could not run — deleting them, dropping them from the health score, and ledgering them as fixed. Those findings are now carried over unchecked and **named as not re-checked**, and the panel states resolved / still present / newly found. "How it can mislead" applied to a verification step: the operator's question is *did my fix land*, and the honest answer is sometimes *this screen cannot tell you — run a full crawl*. | ✅ (action-level explainer, always rendered; the carried-over block names the codes and the reason. The 24 codes' own `how_it_can_mislead` entries remain v4 content-pass work.) |

> | **D6 — the Page Audit names the offending items (2026-09-01)** | *No new codes* — V4's **good vs bad, concrete** applied to the operator's own page. "25 external links open in a new tab without rel=noopener" is a diagnosis; *these twenty-five links, by anchor text and href* is something a nonprofit staffer can act on without knowing what `rel=noopener` means. The evidence had existed since 2026-08-29 and reached one screen only. Now on both, plus a live "Get full details" read that stores nothing — and, in the V4 spirit, it states what it still cannot show (`truncated_at_capture`) and distinguishes "nothing to list" from "nothing recorded" (`evidence_basis`), so a short list never reads as a complete one and an empty one never reads as clean. | ✅ (rendered on every issue; the per-code explainers for these codes remain v4 content-pass work) |

> | **E6.1 — what counts as a card (2026-09-01)** | *No new codes* — a V4 **"how it can mislead"** failure caught in the wild, on a check that already had an explainer. `LINK_STACKED_DUPLICATE` said *"2 links in one card"* while grouping by `<main>`, so 90% of its output on a real site described something that did not exist. The user's report was *"I can't find it"* — the correct response to a confident, specific, false claim, and the hardest kind for a reader to challenge, because the finding named a real URL on a real page. The fix is structural (a card is never the page's content region, is bounded in links and text, and matches classes on token boundaries), and the V4-shaped part is that the evidence now **names the container it grouped by**: a reader can see *what the tool called a card* and disagree with it. | ✅ (evidence-level explainer, always rendered; the code's own 6-part entry was already shipped with E6) |
> | **Phase 2 — the education layer shipped (2026-09-02)** | *No new codes* — **the v4 content pass itself, for all 170 codes.** Every entry now carries the seven parts in reading order, the caveat opens with its evidence tier and names a correct-looking-but-wrong result, and a substance guard rejects a vacuous one. Two lessons worth keeping: (1) a cold factual review found the only defects clustered in the three LLM-judged GEO checks, where the copy had invented statically-verifiable precision ("150 words", "more than half") that no constant backs — an explainer must describe the check that ran, and a language-model judgement must be called one; (2) the PDF printed every em dash in the new copy as `?`, so "teaches offline" was false until the cleaner transliterated. Backfilling the ~120 older codes, which this plan expected to be the bulk of the work, is done. | ✅ (all 170; `tests/test_issue_help_completeness.py` is the parity/lint test acceptance criterion 2 asked for) |
> | **Info tiers + `info_detail` (2026-09-01)** | *No new codes* — the info band (123 of 170 codes) is now graded Key / Notable / Low from the impact each code already carries, and a scan chooses which tiers it shows **and scores**. The V4-shaped part is the discipline around a score that the operator can legitimately raise: the level is printed under the number, the Info card shows scored beside excluded, revealed rows are dimmed as "not counted", exports carry the caveat, and two scans at different levels are declared not comparable. It is "how it can mislead" applied to a *setting* — the first case where the misleading artifact would be one the user chose on purpose, which is exactly when a reader stops questioning it. | ✅ (setting-level explainer on the home page and under the score; the tier label rides on every info badge) |
> | **Rescan (2026-09-01)** | *No new codes* — a V4 explainer attached to an **action**, like D5. Re-running a scan by hand meant re-selecting every setting from memory, which quietly produced the most misleading artifact the product can make: a before/after health-score delta where part of the change is a change in *what was measured*, not in the site. The Rescan button reuses the original job's settings precisely so the comparison means what a reader will assume it means, and the user guide says so in those words. The single-page arm is the same lesson in miniature — a one-page audit that silently rescanned as a 500-page crawl would have been a "successful" 202 describing a different thing entirely. | ✅ (user-guide explainer covering what is reused and why comparability depends on it) |
>
> **Takeaway for the v4 content pass:** newer codes are the proof-of-concept; scope the
> pass as "bring the ~120 pre-2026-05 codes up to the M3.1 entry shape," not "write all
> from scratch."
>
> **And one shape the tally did not have until D5:** every row above explains a
> *finding*. D5 explains an *action* — what a button did, what it could not do, and
> what its silence meant. Verification controls need V4 treatment as much as codes do,
> because a control that reports nothing is read as a control that found nothing.

### GA3 — FAQ Schema Generator (a *tool*)
- **What it is:** generates ready-to-paste FAQ schema (JSON-LD) built from your
  organisation's topics and locations.
- **Why it's useful:** long-tail FAQ questions are exactly what AI engines and search
  match against; structured FAQ markup makes your answers eligible for rich results and
  AI citation.
- **Good vs bad:** a 6+-word specific question ("What should I expect from grief
  counselling in Vancouver?") vs a short head term ("counselling") everyone competes for
  and AI can't anchor to.
- **How it can mislead:** the tool generates *anchors*, not verified answers — you must
  write accurate answers; schema for content you can't honestly answer can hurt trust.
- **How to use:** paste the JSON-LD into the page, then replace the draft answers with real ones.

### GA4 — Authoritative Entity Schema Factory (a *tool*)
- **What it is:** builds JSON-LD that tells search and AI engines who your organisation
  is, what services it offers, and which authoritative entity (Wikipedia/Wikidata page)
  it corresponds to.
- **Why it's useful:** a `sameAs` link to an authoritative entity is a strong
  disambiguation signal — it helps AI engines confidently identify and cite your org.
- **Good vs bad:** linking to your real Wikipedia/Wikidata entity vs leaving it blank
  (no disambiguation) or pointing at an unrelated page (actively misleading).
- **How it can mislead:** schema must match what's visibly on your page and be truthful;
  claiming services or an identity you can't back up can hurt trust and eligibility.
- **How to use:** set your entity URL in GEO settings, generate, paste the JSON-LD into the page.

### M3.1 — `SCHEMA_VISIBLE_MISMATCH` (an *audit code* — the issueHelp.js shape)
This is the **first `issueHelp.js` entry shipped with the new `good_vs_bad` and
`how_it_can_mislead` fields** — i.e. the concrete template for the eventual content pass
over all ~132 codes. Verbatim:
- **What it is (`definition`):** one or more values declared in this page's JSON-LD
  (headline, name, FAQ answer, address) do not appear anywhere in the visible text.
  Google explicitly requires markup content to also be visible.
- **Why it matters (`impact`):** *Evidence tier: Established.* Mismatched structured data
  risks losing rich-result eligibility and may be viewed as deceptive by AI search
  systems — directly affecting whether the page is cited.
- **Good vs bad (`good_vs_bad`):** Good — JSON-LD headline "Grief Counselling Services"
  and the H1 reads the same. Bad — JSON-LD says "Best Therapy in Vancouver" but no such
  text appears: invisible keyword stuffing in markup.
- **How it can mislead (`how_it_can_mislead`):** a page can have valid JSON-LD that passes
  syntax validators yet declares content the user never sees; this catches that specific
  gap. It does *not* flag missing fields — only present fields whose values are absent.
- **How to fix (`fix`):** add the declared value to the visible content, or update the
  structured data to match what's shown (check your SEO plugin's schema settings).

> **Implication for the content pass:** the `issueHelp.js` schema already tolerates the
> richer `good_vs_bad` / `how_it_can_mislead` fields (parity tests pass). So the v4 content
> pass can adopt M3.1's entry as the literal field template and extend codes incrementally.

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

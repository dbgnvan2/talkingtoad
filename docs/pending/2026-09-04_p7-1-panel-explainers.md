# Micro-spec — P7.1: the four tools that teach a nonprofit nothing

**Date:** 2026-09-04
**TODO item:** Phase 7, P7.1 (the whole phase)
**Class:** P16 (a capability on some surfaces only), P13 (three copies of one markup, in two
different forms, about to become seven).

---

## 1. Verified

Counted rather than trusted:

| Panel | `What it is:` blocks | affordance |
|---|---|---|
| `GEOReportPanel` | 2 | `showHelp` toggle, copy inline in JSX |
| `GSCInsightsPanel` | 1 | always rendered, copy in a `V4_EXPLAINER` object |
| `FaqSchemaModal` | **0** | — |
| `GeoSettingsModal` | **0** | — |
| `ImageAnalysisPanel` | **0** | — |
| `BatchOptimizePanel` | **0** | — |

So the app explains what `META_DESC_TOO_LONG` means in seven parts, for all 170 codes, and
says nothing at all about the four tools that *change a nonprofit's site*.

**And the markup is already duplicated three times in two forms.** Writing four more inline
copies makes seven, which is the shape the P5.2 gate flagged ("N scored / N not scored"
triplicated) and the P6.1 gate caught twice more. The five labels are a contract; they should
have one home.

## 2. Change

### 2.1 One component, one data module

- `frontend/src/data/panelHelp.js` — `PANEL_HELP`, keyed by panel id, each entry
  `{title, what, why, goodVsBad, misleading, howToUse}`.
- `frontend/src/components/PanelExplainer.jsx` — renders the five labelled blocks from an id.
  The five label strings exist **once**.
- The three existing copies migrate to it. `GEOReportPanel`'s two sub-panels keep their
  `showHelp` toggle; `GSCInsightsPanel` keeps rendering always. The component takes the copy,
  not the affordance — how a panel reveals help is a UI choice, what it says is not.

### 2.2 The four panels get entries and the affordance

Each of the four renders `PanelExplainer` behind a "What is this?" toggle, matching
`GEOReportPanel`'s existing pattern (a modal that always shows five paragraphs before the
user has done anything is a wall, and this phase is about being read).

### 2.3 The copy

Written from what each tool actually does, with the "how it can mislead" drawn from a real
property of the implementation rather than a generic caution. The four, in outline — full
copy in the implementation:

- **FAQ schema generator.** Builds `FAQPage` JSON-LD **only from answers already in the page
  HTML**, and refuses when the answers are JavaScript-only. *Misleads:* a refusal is not "this
  page has no FAQs" — it usually means the answers are rendered by script and Google's parser
  cannot see them either. And it is **copy/export only**: nothing reaches WordPress until the
  operator pastes it.
- **GEO settings.** Organisation identity, locations and topics that **feed AI image-metadata
  generation**. *Misleads:* these are *inputs*, not verified facts — a wrong location here
  propagates into every image's alt text and, with GPS injection on, into the EXIF of every
  optimised file. The tool cannot tell a wrong answer from a right one.
- **Image analysis.** Per-image health scores over metadata and file hygiene. *Misleads:* the
  score is about the image's **metadata and weight, not whether the picture is any good or
  belongs on the page** — a decorative spacer with perfect alt text scores well. And the
  dimension pass measures at most 150 images per crawl (`TT_IMAGE_DIMENSION_MAX_COUNT`), so
  beyond that a file-size finding is *not measured* rather than *absent*; rows carry
  `data_source` for exactly this reason.
- **Batch optimisation.** Converts to WebP, resizes, and can write GPS/GEO metadata.
  *Misleads:* **it uploads a new file; your pages keep serving the old one until you replace
  the image by hand.** That is a hard constraint of this product (`CLAUDE.md`: "DO NOT
  AUTOMATE IMAGE LINK UPDATES IN POSTS/PAGES"), and without it an operator watching a green
  progress bar will reasonably believe their site is now faster. It is the single most
  important sentence in this item.

## 3. Tests

| # | Test | Goes red when |
|---|---|---|
| 3.1 | `test_every_registered_panel_has_all_five_parts` | a part is empty or missing |
| 3.2 | `test_the_four_named_panels_are_registered` | one of the four is dropped |
| 3.3 | `test_misleading_has_substance` | a caveat becomes a generic caution |
| 3.4 | `test_the_adversarial_caveat_fails` | the substance check stops rejecting |
| 3.5 | `test_no_panel_hand_writes_the_five_labels` | a seventh copy appears |
| 3.6 | `test_every_panel_that_renders_the_explainer_uses_a_registered_id` | a typo'd id renders blank |
| vitest | each of the four renders its explainer behind the toggle | §2.2 regresses |

**Adversarial cases:**

- **3.3 + 3.4 are a pair, copied from `test_issue_help_completeness`'s best idea.** A
  substance check nobody has proved *can* fail is a green light, not a guard — 3.4 feeds it a
  deliberately vapid caveat ("Results may vary; always review the output") and asserts it is
  rejected. Without 3.4, 3.3 could be `len(text) > 0` and read as rigour.
- **3.5 is the P13 guard and the reason the component exists.** Three copies were already
  there; the way this reaches seven is the next author adding a panel and copying the JSX.
- **3.6 catches the failure mode a shared component introduces** that inline copy did not:
  `<PanelExplainer id="batch-optimise" />` against a key spelled `batch_optimize` renders
  nothing, silently, and no completeness test over the data notices. It reads the ids out of
  the JSX and asserts each is in `PANEL_HELP`.
- **vitest** asserts the *specific* sentence for BatchOptimize — that the old image keeps
  being served — not merely that some explainer rendered. It is the one line whose absence
  would let an operator believe their site changed when it did not.

## 4. Considered and rejected

- **Four inline copies, matching what is there.** Rejected: seven copies of a five-label
  contract, in a repo that has been bitten three times this week by duplicated phrasing.
- **One shared affordance too** (force every panel to a toggle, or to always-on). Rejected:
  `GSCInsightsPanel` renders always because it is a connect-first screen where the user has
  nothing else to look at; a modal like `FaqSchemaModal` opens onto a result and should not
  bury it. The copy is the contract; the affordance is a per-panel judgement.
- **Reuse `issueHelp.json`.** Rejected: that file is keyed by issue code, has a seven-part
  shape, and is pinned to `_CATALOGUE` by parity tests. Panels are not codes and would have to
  be excluded from every one of those tests — an exclusion list is what hid P5.1.
- **Generate the copy with the AI advisor.** Rejected, and `PLAN-V4.0.md` rejects it in
  advance: *"AI-generated explanations… should be human-reviewed canonical copy, not generated
  per request."*

## 5. Not in scope

- The PDF/Excel exports rendering panel explainers (V4 lists it separately; these four tools
  do not appear in the report).
- Any change to what the four panels *do*.

## 6. Done when

- Each of `FaqSchemaModal`, `GeoSettingsModal`, `ImageAnalysisPanel` and `BatchOptimizePanel`
  carries all five parts, from one shared component reading one data module.
- The three pre-existing copies read from that module too, and a test fails on the seventh.
- Every caveat names a concrete way *that tool* misleads, proven by a substance check that is
  itself proven able to fail.

# Micro-spec: Fix Focus on the Summary dashboard + Fix Focus Items Help

**Date:** 2026-08-13
**Status:** approved by direct user instruction ("put Fix Focus on the Summary screen beside the
Top 5 Priority Fixes; add a deduped Fix Focus Items Help beside it"). GUI change authorized.
**Type:** enhancement (frontend only — no backend/API change; reuses the shipped Fix Focus
endpoints and `issueHelp.js`).
**Builds on:** functional-specification.md §6.11 (Fix Focus).

## Goal
Surface Fix Focus on the main **Summary** dashboard and add a companion help panel.

## FFS1 — Fix Focus on the Summary screen
- Render `FixFocusPanel` on the Summary (`SummaryPanel.jsx`), in a responsive row placed
  immediately after the **Top 5 Priority Fixes** panel (`TopPriorityGroups`), beside a new
  **Fix Focus Items Help** panel (FFS2). Row: `grid-cols-1 lg:grid-cols-2` (stacks on narrow).
- The standalone "Fix Focus" tab in `Results.jsx` is **kept** (no nav removed).

## FFS2 — Fix Focus Items Help (new panel, `FixFocusItemsHelp.jsx`)
- Title: **"Fix Focus Items Help"**. Sits beside `FixFocusPanel` (FFS1).
- Loads the persisted snapshot (`getFixFocus(jobId, 'all')`), collects the **distinct**
  `issue_code`s across BOTH focuses (SEO + GEO), and renders each **once** — a repeated item
  (e.g. an orphaned/"disconnect page" issue on several pages) appears a single time.
- Per item, from `getIssueHelp(code)` (`issueHelp.js`): the **title**, the plain-English
  **"what it is"** (`definition`), and the **fix** steps. Codes with no `issueHelp` entry fall
  back to the snapshot item's `human_description` (never blank).
- Order: by descending max `priority_rank` across the item's occurrences (highest-priority help
  first), stable by code.
- Standard loading / error / empty states (empty = "No Fix Focus items yet").

## Acceptance criteria → tests
| ID | Criterion | Test |
|---|---|---|
| FFS2.dedup | A code appearing on N pages / both focuses renders exactly ONE help entry | `FixFocusItemsHelp.test.jsx` "dedupes repeated items" |
| FFS2.content | Each entry shows title + what-it-is + fix from issueHelp | `FixFocusItemsHelp.test.jsx` "renders help fields" |
| FFS2.fallback | A code missing from issueHelp falls back to human_description | `FixFocusItemsHelp.test.jsx` "falls back when no help entry" |
| FFS2.error | Request failure shows an error state | `FixFocusItemsHelp.test.jsx` "shows an error state" |
| FFS1 | Summary renders Fix Focus + Fix Focus Items Help beside Top 5 Priority Fixes | covered by the panel tests + a SummaryPanel render smoke check if present |

## Non-goals
- No backend change; no new endpoint. No change to the Fix Focus checklist logic.
- No change to `TopPriorityGroups` / `Top10Pages`.

## Completion
Fold into functional-specification.md §6.11 (add the Summary-placement + Items-Help note);
delete this pending file; push.

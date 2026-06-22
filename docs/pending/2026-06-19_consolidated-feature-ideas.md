---
status: draft-capture
created: 2026-06-19
purpose: Single landing place to consolidate scattered TalkingToad feature ideas from across chats/Cowork sessions before triaging into PLAN-V4.0.md / TODO.md / a micro-spec.
note: This is a capture buffer, NOT an approved spec. Per CLAUDE.md, real features still need a micro-spec in docs/pending/ + explicit approval before any code.
---

# Consolidated Feature Ideas — Capture Buffer

> **What this is.** One place to drop new-feature ideas for TalkingToad that are
> currently scattered across desktop chats and Cowork sessions on mini1/mini2.
> Fill in an entry per idea, then triage: promote to a `docs/pending/` micro-spec,
> add to `PLAN-V4.0.md`, add to `TODO.md`, or discard.

---

## How to use this file

1. Find a scattered idea (see the **search checklist** below).
2. Add an entry under **Captured ideas** using the template.
3. When an idea is real, triage it (see **Triage targets**) and tick it off.

### Entry template (copy this block per idea)

```
### <short idea name>
- **What:** <one or two sentences — what the feature does>
- **Why / value:** <the user-facing benefit or problem it solves>
- **Source:** <where you found it — e.g. "desktop chat 'X', mini1" / "Cowork 'Y'">
- **Already in repo?:** <no / partial — names the file if partial>
- **Triage target:** <micro-spec | PLAN-V4.0 | TODO | discard>
- **Status:** captured
```

---

## Captured ideas

<!-- Add entries here. None captured yet — see sweep findings below. -->

_(empty — paste ideas from your desktop-chat search here)_

---

## Search checklist — where the ideas actually are

> **Sweep result (2026-06-19):** every TalkingToad-related **mini2 Cowork** session was
> read or sampled. **None held net-new TalkingToad-app feature ideas** not already in the
> repo. So the remaining ideas are most likely in **desktop chats** (account-synced, not
> machine-readable by an agent) or **mini1 Cowork** sessions. Work the unchecked boxes:

- [ ] **Desktop / claude.ai chat search** — same account, synced across mini1 + mini2, so
      do this once on either machine. Use the conversation **search box**; search:
      `TalkingToad`, then `feature`, `add`, `idea`, `should`, `v4`, `issue code`,
      `GEO`, `crawler`. Paste hits into **Captured ideas** above.
- [ ] **mini1 Cowork sweep** — unreachable from a mini2 session. Run a Cowork session
      *on mini1*, connect this repo (or a clone), and have it list local sessions +
      read transcripts for TalkingToad mentions (same method used for the mini2 sweep).

---

## Sweep findings — mini2 Cowork (2026-06-19), for the record

These are what the mini2 sessions actually contained, so they don't get re-checked:

| Session title | Verdict |
|---|---|
| Talking-toad repo | Client-facing **description** write-up (referenced old v2.1 state). No new features. |
| SERP Discover and Compete benefits | **Separate project** (`serp-discover` repo). Out of TalkingToad scope. |
| SEO strategy for new coaching course | **SERP-Discover** report-clarity spec. Separate project. |
| Local and GitHub repo sync | **Different app** (GetMoreDone, a desktop Tkinter app). Not TalkingToad. |
| Find RAG app creation session / RAG sessions | **Separate** `rag-document-search` tool (Bowen materials). |
| Website FAQ comparison | livingsystems.ca **meeting action items** (the subject site). Not the app. |
| Elementor / Website / WordPress / CPT sessions (many) | livingsystems.ca **site-editing** work. Not the app. |

**Takeaway:** mini2 Cowork is exhausted as a source. Focus the remaining hunt on
desktop chats and mini1.

---

## Triage targets (where a captured idea goes once it's real)

- **`docs/pending/YYYY-MM-DD_<feature>.md`** — a micro-spec, required before any code
  (per CLAUDE.md spec-change rules). This is the path for anything you'll actually build.
- **`PLAN-V4.0.md`** — if it belongs to the v4 "Full Feature Explanation Layer" theme,
  or is a larger roadmap item.
- **`TODO.md`** — smaller tech-debt / UX / polish items.
- **discard** — duplicate of something already shipped or planned.

> Already-recorded baseline (don't re-capture these):
> - `PLAN-V4.0.md` — v4 "Full Feature Explanation Layer" (6-part explainer for every issue code).
> - `TODO.md` — frontend testing (Vitest), error boundaries, E2E (Playwright), WP integration
>   tests, Rescan-All button, persistent PDF settings, live log streaming, TS migration, CSS refactor.

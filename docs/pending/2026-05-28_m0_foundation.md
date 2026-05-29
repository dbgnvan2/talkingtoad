---
status: pending
proposed: 2026-05-28
revised: 2026-05-28 (post-architect review)
author: User / System Architect
source: PLAN-V3.0.md
---

# Milestone 0.1–0.5: Foundation & Security Hardening

## Goal
Establish a rock-solid security and deployment baseline before any v3.0 feature work begins. After the v2.6 stabilization phase (Cycles J–U, tag `v2.6-stabilized`), several items originally listed in PLAN-V3.0.md have either already been completed or have stale target values. This revision aligns each milestone with the **current** state of the code.

## Requirements

### M0.1 — Doc Version Sync (revised)

Original spec called for bumping versions to `v2.2`. **Stale.** Current code/tag is post-stabilization (`v2.6-stabilized`); v3.0 feature work is the next phase.

- **Unify all version strings to `v2.6.0`** across the codebase:
  - `CLAUDE.md` header / project version statement
  - `api/routers/utility.py` (was line 107 — verify and fix wherever the version string lives)
  - `api/main.py` (was line 84 — same)
  - Any other `version: "2.x"` strings discovered during the audit
- Add a note in `CLAUDE.md` stating that v3.0 planning / feature implementation is now active (the stabilization phase is complete).
- **Method:** the agent should grep for `version` / `2\.\d` patterns to find all sites dynamically rather than relying on the (likely stale) line numbers from the original spec.

### M0.2 — Confidence Labels (AI Readiness) — revised to AUDIT

Original spec called for *implementing* `confidence_label` on `_IssueSpec` + applying labels + adding a parity guard. **All of this already exists** as of Cycle K + S:
- `_IssueSpec` already has the `confidence_label` field.
- `_AI_READINESS_CONFIDENCE` already populates 49 labels.
- `TestAIReadinessConfidenceLabels::test_every_ai_readiness_code_has_confidence_label` already enforces the parity guard.
- `make_issue()` already propagates the label onto the `Issue` instance.

**The remaining work is a verification audit:**
- Confirm `confidence_label` is serialized into the `/api/crawl/{id}/results` API response (i.e., the response schema includes the field for every `ai_readiness` issue, not just the `Issue` dataclass internally).
- Confirm `frontend/src/data/issueHelp.js` exposes a `confidence` field (or equivalent) so the frontend can render the label.
- If either is missing, patch it. If both are present, simply record the audit result.

### M0.3 — Documentation Reconciliation — revised to AUDIT

Original spec hardcoded `Results.jsx (1,831 lines)` and `wp_heading_fixer.py (525 lines)`. The 525 number is **stale** — `CLAUDE.md`'s current directory structure entry says `~1031 lines incl. v2.3 M0.12.2 additions`.

**Method:**
- Audit current line counts on the filesystem dynamically (`wc -l`).
- Cross-check against the numbers cited in `CLAUDE.md` directory structure.
- Patch any mismatches in `CLAUDE.md`; report the actual sizes.
- Prune satisfied items from `REVIEW_SPEC.md` and `REVIEW.md` based on the post-stabilization state.

### M0.4 — v2.0 Spec Open Questions
- Resolve the 4 open questions listed in the V3.0 plan discovery findings (e.g., formalize JSON-LD block extraction and GEO image-alt wiring).
- If the questions are no longer pending after the v2.6 stabilization, record the resolutions.

### M0.5 — Critical Security: Advisor Auth — revised to AUDIT first

Original spec assumed `Depends(require_auth)` was missing from all five Advisor routes. After Cycle K (routers refactor) the auth state needs verification.

- **Audit** each of these five routes in `api/routers/advisor.py` for `Depends(require_auth)` presence:
  - `POST /api/ai/advisor`
  - `POST /api/ai/rewriter`
  - `POST /api/ai/rewrite-url`
  - `POST /api/ai/geo-report`
  - `GET /api/ai/geo-report/pages`
- For each route:
  - **If `require_auth` is missing:** apply it. Add a contract test asserting `401 Unauthorized` when accessed without a bearer token.
  - **If `require_auth` is present:** confirm that a contract test already asserts the `401` behaviour. If not, add one.
- Report which routes were already protected vs. which needed patching.

## Acceptance Criteria
1. Every version-string site in the codebase reads `2.6.0` (or `v2.6.0`).
2. `confidence_label` is verifiably surfaced in the `/api/crawl/{id}/results` JSON response for every `ai_readiness` issue.
3. `CLAUDE.md` directory-structure line counts match the actual filesystem.
4. The five critical Advisor endpoints return `401` when accessed without a valid bearer token, with a contract test proving it for each.
5. No regressions in the existing green test suite (1,276 passing / 12 skipped / 0 failed baseline).

---
status: pending
proposed: 2026-05-31
author: Architect (M3.3 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 3.3 (Google-validated extensions)
---

# M3.3 — X-Robots-Tag AI-preview controls (`AI_PREVIEW_SUPPRESSED`, `AI_PREVIEW_BLOCKED_AT_BOT`)

> **Cycle 3 of M3.** Adds TWO tightly-coupled codes from one header inspection.
> Catalogue source of truth: `api/crawler/checkers/registry.py` (facade:
> `issue_checker.py`).

## Goal
Inspect each page's `X-Robots-Tag` **HTTP response header** for directives that
suppress search/AI previews. Google: *"use `nosnippet`, `max-snippet`, or `noindex`
controls"* — [AI Features and Your Website](https://developers.google.com/search/docs/appearance/ai-features).

Two codes (both **Established** — literal header facts):
- **`AI_PREVIEW_SUPPRESSED`** — a general directive that suppresses the snippet/preview
  (`nosnippet` or `max-snippet:0`). The page may still be indexed, but AI engines are told
  not to show a preview — which removes it from AI citation.
- **`AI_PREVIEW_BLOCKED_AT_BOT`** — a **bot-specific** directive targeting an AI crawler
  (e.g. `X-Robots-Tag: GPTBot: noindex`, `Google-Extended: noindex`).

Both are **informational** (often intentional) — surface the directive so the user knows
it's affecting AI visibility.

## Data availability (verified)
Response headers are carried end-to-end: `FetchResult.headers` (dict, lowercased keys);
`parser._parse_robots_signals(soup, result.headers)` already reads
`headers.get("x-robots-tag", "")`. No new plumbing needed.

## Design — parse at parse time
- **Helper** in `api/crawler/parser.py`:
  `_parse_x_robots_ai_directives(headers: dict) -> tuple[str | None, str | None]`
  returning `(preview_suppressed_directive, ai_bot_blocked_directive)`.
  - Read `headers.get("x-robots-tag", "")` (httpx joins repeated headers with commas).
  - Split on commas; for each part, trim. Match case-insensitively but keep the original
    token for `extra`.
  - **Bot-specific** part = matches `^<bot>:\s*<directive>`. If `<bot>` is an AI crawler
    (`gptbot`, `google-extended`, `claudebot`, `anthropic-ai`, `ccbot`, `perplexitybot`,
    `bytespider`, `cohere-ai`) AND `<directive>` contains `noindex`/`nosnippet` →
    `ai_bot_blocked_directive = <original part>`.
  - **General** part (no bot prefix, or a non-AI bot like `robots`/`googlebot`): if it
    contains `nosnippet` or `max-snippet:0` (allow optional space, `max-snippet: 0`) →
    `preview_suppressed_directive = <original token>`.
  - `max-snippet:-1` / positive values do **not** suppress (only `0`).
  - General `noindex` is intentionally **excluded** — it already makes the page
    non-indexable and is covered by existing crawlability checks (no double-flag).
- **New `ParsedPage` fields:**
  `x_robots_preview_suppressed: str | None = None`,
  `x_robots_ai_bot_blocked: str | None = None`.
- **Parser wiring:** set both from the helper (the parser already has `result.headers`).
- **Emission** (`issue_checker.py`, **indexable pages only** — these matter for pages meant
  to be seen):
  - `x_robots_preview_suppressed` → `make_issue("AI_PREVIEW_SUPPRESSED", url, extra={"directive": ...})`
  - `x_robots_ai_bot_blocked` → `make_issue("AI_PREVIEW_BLOCKED_AT_BOT", url, extra={"directive": ...})`

## Issue-code registration (all three registries in `api/crawler/checkers/registry.py`)
- **`_ISSUE_SCORING`:** `"AI_PREVIEW_SUPPRESSED": (3, 1)`, `"AI_PREVIEW_BLOCKED_AT_BOT": (3, 1)`.
- **`_CATALOGUE`:** two `_IssueSpec(category="ai_readiness", severity="info", ...)` entries:
  - `AI_PREVIEW_SUPPRESSED` — description: "An X-Robots-Tag response header suppresses this
    page's search/AI preview (nosnippet or max-snippet:0)"; recommendation: "If you want this
    page to be eligible for AI Overviews and citations, remove the nosnippet / max-snippet:0
    directive from the X-Robots-Tag header (often set in server config or an SEO plugin)."
    human_description: "AI Preview Suppressed".
  - `AI_PREVIEW_BLOCKED_AT_BOT` — description: "An X-Robots-Tag directive specifically blocks
    an AI crawler (e.g. GPTBot, Google-Extended) from indexing this page"; recommendation:
    "This is intentional if you don't want AI engines using this page. If you DO want AI
    citation, remove the AI-bot-specific directive."; human_description: "AI Bot Blocked".
- **`_AI_READINESS_CONFIDENCE`:** both `"Established"`.

## Parity (mandatory)
- `frontend/src/data/issueHelp.js`: two entries, each with `confidence: "Established"` and the
  full V4 fields (`definition`, `impact`, `fix`, `good_vs_bad`, `how_it_can_mislead`) — follow
  the `SCHEMA_VISIBLE_MISMATCH` entry as the template.
- Regenerate `docs/issue-codes.md` via `python scripts/generate_issue_codes_doc.py`.
- Parity tests in `tests/test_architecture_constraints.py` must pass.

## Files to modify
| File | Change |
|---|---|
| `api/crawler/parser.py` | `_parse_x_robots_ai_directives()` + two fields + wiring |
| `api/crawler/checkers/registry.py` | two codes × 3 registries |
| `api/crawler/issue_checker.py` | emit both (indexable-only) with `extra.directive` |
| `frontend/src/data/issueHelp.js` | two entries (confidence + V4 fields) |
| `docs/issue-codes.md` | regenerate |

## Test plan (`tests/test_x_robots_ai_preview.py`)
- `X-Robots-Tag: nosnippet` → `AI_PREVIEW_SUPPRESSED` (extra.directive == "nosnippet").
- `X-Robots-Tag: max-snippet:0` → `AI_PREVIEW_SUPPRESSED`.
- `X-Robots-Tag: GPTBot: noindex` → `AI_PREVIEW_BLOCKED_AT_BOT`.
- `X-Robots-Tag: Google-Extended: noindex` → `AI_PREVIEW_BLOCKED_AT_BOT`.
- **Adversarial:** no header → neither; `index, follow` → neither;
  `max-snippet:-1` → NOT suppressed (only `:0`); `googlebot: noindex` → NOT bot-blocked
  (general search bot, not an AI crawler; handled by existing noindex logic);
  header matching is case-insensitive; comma-joined multi-directive header parsed correctly.
- Non-indexable page does not emit; contract: results/pages-issues endpoint surfaces both
  codes with `extra.directive`.

## Security check
- **SSRF:** No — inspects already-fetched response headers; no new fetch.
- **Auth:** N/A (crawl/parse time).  **WordPress:** No.  **XSS:** No.

## Documentation impact
- `docs/issue-codes.md` regenerated. `docs/thresholds.md` (READ-ONLY) **untouched** (no numeric bound).
- `PLAN-V3.0-UNIFIED.md` — note M3.3 done when merged.

## Acceptance criteria
1. `nosnippet` / `max-snippet:0` → `AI_PREVIEW_SUPPRESSED`; AI-bot-specific noindex/nosnippet
   → `AI_PREVIEW_BLOCKED_AT_BOT`.
2. Adversarial guards pass (no header, `max-snippet:-1`, generic `googlebot:` → no false flag;
   general `noindex` not double-flagged).
3. Both codes registered in all 3 registries; issueHelp (V4 fields) + issue-codes.md parity passes.
4. Emitted indexable-only with `extra.directive`.
5. `docs/thresholds.md` untouched. Full suite green, 0 regressions.

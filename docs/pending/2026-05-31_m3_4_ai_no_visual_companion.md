---
status: pending
proposed: 2026-05-31
author: Architect (M3.4 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 3.4 (Google-validated extensions)
---

# M3.4 — `AI_NO_VISUAL_COMPANION` (Reasonable proxy, info)

> **Cycle 4 of M3.** Catalogue source of truth: `api/crawler/checkers/registry.py`.

## Goal
For substantial text pages of a content type that benefits from visuals, suggest adding
images/video. Google: *"support your textual content with high-quality images and videos"*
— [Top ways to succeed in AI search](https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search).
Informational nudge, tier **Reasonable proxy** (we infer "would benefit from a visual").

## Trigger (exact) — VERIFIED symbols
Emit `AI_NO_VISUAL_COMPANION` when ALL hold (indexable pages only):
- `infer_page_type(page)` ∈ {`"article"`, `"service"`, `"faq"`} — from
  `api.services.page_classifier.infer_page_type(parsed_page) -> str` (returns one of
  `home, article, team_member, service, faq, contact, about, unknown`). **Confirmed: the
  label is `service` (singular), and `faq` exists.**
- `word_count` (body) `> 300`,
- image count `== 0` — count from `page.image_urls` (the list[str] used by the image checks;
  `image_data` is the richer parallel field). Use `len(page.image_urls or [])`.
- impact 1, severity **info**.

## Design
- Compute in `issue_checker.py` (`infer_page_type` takes a `ParsedPage`, no parse-time soup
  needed). No new `ParsedPage` field required — derive at check time.
- Emit `make_issue("AI_NO_VISUAL_COMPANION", url, extra={"page_type": <type>, "word_count": page.word_count})`.

## Registration (all 3 registries in `checkers/registry.py`)
- `_ISSUE_SCORING`: `"AI_NO_VISUAL_COMPANION": (1, 1)`.
- `_CATALOGUE`: `_IssueSpec(category="ai_readiness", severity="info",
  description="A substantial text page (article/service/FAQ) has no images or video to
  support its content", recommendation="Add at least one relevant, high-quality image or
  video. Visuals help both readers and AI systems understand and surface your content.",
  human_description="No Supporting Visual", fixability="content_edit")`.
- `_AI_READINESS_CONFIDENCE`: `"AI_NO_VISUAL_COMPANION": "Reasonable proxy"`.

## Parity (mandatory)
- `issueHelp.js` entry — `confidence: "Reasonable proxy"` + full V4 fields (template:
  `SCHEMA_VISIBLE_MISMATCH`). Regenerate `docs/issue-codes.md`.

## Files
| File | Change |
|---|---|
| `api/crawler/issue_checker.py` | classify + emit (indexable-only) |
| `api/crawler/checkers/registry.py` | code × 3 registries |
| `frontend/src/data/issueHelp.js` | entry + V4 fields |
| `docs/issue-codes.md` | regenerate |

## Test plan (`tests/test_ai_no_visual_companion.py`)
- article, 400 words, 0 images → flagged.
- service, 350 words, 0 images → flagged.
- **Adversarial:** article 400 words WITH 1 image → not flagged; article only 120 words,
  0 images → not flagged (under 300); `about`/`home`/`unknown` type, 0 images → not flagged
  (wrong type); non-indexable page → not emitted.
- Contract: results endpoint surfaces the code with `extra.page_type`.

## Security check
SSRF No · Auth N/A · WordPress No · XSS No.

## Documentation impact
`docs/issue-codes.md` regenerated; `docs/thresholds.md` (READ-ONLY) untouched (the 300-word
bound is the existing `word_count`; the constant lives inline). `PLAN-V3.0-UNIFIED.md` note when merged.

## Acceptance criteria
1. Fires only for {article, service_area, faq} with `word_count > 300` and zero images.
2. All adversarial guards pass (has-image, under-300, wrong-type, non-indexable).
3. Registered in all 3 registries; issueHelp (V4) + issue-codes.md parity passes.
4. `extra.page_type` present. Full suite green, 0 regressions.

## Verified (no further lookup needed)
`infer_page_type` labels confirmed: `home, article, team_member, service, faq, contact,
about, unknown`. Image count source confirmed: `page.image_urls` (list[str]).

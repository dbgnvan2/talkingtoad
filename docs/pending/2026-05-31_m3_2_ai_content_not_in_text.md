---
status: pending
proposed: 2026-05-31
author: Architect (M3.2 cycle, TalkingToad session)
type: feature
source: PLAN-V3.0.md Milestone 3.2 (Google-validated extensions)
---

# M3.2 — `AI_CONTENT_NOT_IN_TEXT` (Reasonable proxy)

> **Cycle 2 of M3.** Follows M3.1 (`SCHEMA_VISIBLE_MISMATCH`, shipped `345c935`).

## Goal
Flag pages whose **important content is not available in textual form** — the meaning
is carried by images/video or locked inside an embed (iframe/PDF), not text an AI can
read. Google: *"Making sure that important content is available in textual form"* —
[AI Features and Your Website](https://developers.google.com/search/docs/appearance/ai-features).
Tier: **Reasonable proxy** (we infer non-textual content structurally; we can't render px).

## The distinction that keeps this from double-flagging thin-content codes
Existing codes already cover *not enough content*: `THIN_CONTENT`, `CONTENT_THIN`,
`CONTENT_NOT_EXTRACTABLE_NO_TEXT` (no text at all). **M3.2 is different — content
*exists* but isn't *textual*.** So the trigger **requires non-text content to be
present** (image/video, or an embed). A thin page with no media is NOT an M3.2 hit
(it's a thin-content hit). This non-text-present requirement is the whole point — do
not relax it.

## Design — pre-compute at parse time (M3.1/Cycle GG precedent)
- **New `ParsedPage` field:** `content_not_in_text_reason: str | None = None`
  - `None` → not flagged / not computed (legacy).
  - `"media_dominated"` → H1 present, text-starved, but image/video present.
  - `"answer_in_embed"` → primary content sits inside an iframe/embed/object and there's
    little surrounding text.
- **Helper** (add to `api/services/extractability.py`):
  `detect_content_not_in_text(soup, word_count: int | None) -> str | None`:
  ```python
  _MIN_TEXTUAL_WORDS = 50    # below this the page is text-starved
  _EMBED_TEXT_WORDS  = 100   # below this, an embed is likely carrying the answer

  def detect_content_not_in_text(soup, word_count):
      if soup is None or soup.find("h1") is None:
          return None                      # require an H1 — a real content page
      wc = word_count or 0
      if soup.find(["iframe", "embed", "object"]) is not None and wc < _EMBED_TEXT_WORDS:
          return "answer_in_embed"
      if wc < _MIN_TEXTUAL_WORDS and soup.find(["img", "video"]) is not None:
          return "media_dominated"
      return None
  ```
- **Parser wiring** (`api/crawler/parser.py`): after `word_count` is computed, set
  `content_not_in_text_reason = detect_content_not_in_text(soup, word_count)` inside a
  try/except → `None` on error (never abort the parse), mirroring M3.1.
- **Emission** (`api/crawler/issue_checker.py`): **only for indexable pages** (consistent
  with `GEO_SUMMARY_BURIED`), when `page.content_not_in_text_reason` is not None:
  `make_issue("AI_CONTENT_NOT_IN_TEXT", url, extra={"reason": page.content_not_in_text_reason, "word_count": page.word_count})`.

### Threshold handling (thresholds.md is READ-ONLY)
`_MIN_TEXTUAL_WORDS` and `_EMBED_TEXT_WORDS` are **module constants in
`extractability.py`**. Do **NOT** edit `docs/thresholds.md` (status: current → read-only);
the Gemini compiler syncs it from the canonical spec later. Document the two constants
and their rationale in the spec/PR description so the compiler pass can pick them up.

## Issue-code registration (all three registries in `api/crawler/checkers/registry.py`)
- **`_ISSUE_SCORING`:** `"AI_CONTENT_NOT_IN_TEXT": (4, 2)` — default impact 4 (PLAN-V3.0 M3.2).
- **`_CATALOGUE`:** `_IssueSpec(category="ai_readiness", severity="warning",
  description="Important content on this page is not in textual form — it is carried by
  images/video or locked inside an embed (iframe/PDF) that AI systems cannot read as text",
  recommendation="Provide the key information as real on-page text. Add a textual summary
  or transcript alongside any image, video, or embedded document so AI systems and screen
  readers can access it.", human_description="Content Not Available as Text",
  fixability="content_edit")`.
- **`_AI_READINESS_CONFIDENCE`:** `"AI_CONTENT_NOT_IN_TEXT": "Reasonable proxy"`.

## Parity (mandatory)
- **`frontend/src/data/issueHelp.js`:** add `AI_CONTENT_NOT_IN_TEXT` with
  `confidence: "Reasonable proxy"` and the **full V4 fields** — `definition`, `impact`,
  `fix`, **`good_vs_bad`**, **`how_it_can_mislead`** (follow the M3.1 entry as the literal
  template; the schema tolerates these fields and parity passes).
- **`docs/issue-codes.md`:** regenerate via `python scripts/generate_issue_codes_doc.py`.
- Catalogue/help/scoring/confidence parity tests in `tests/test_architecture_constraints.py`
  must pass.

## Files to add / modify
| File | Change |
|---|---|
| `api/services/extractability.py` | **add** `detect_content_not_in_text()` + the two constants |
| `api/crawler/parser.py` | **add** `content_not_in_text_reason` field + pre-compute block |
| `api/crawler/checkers/registry.py` | **add** code to all 3 registries |
| `api/crawler/issue_checker.py` | **emit** under `is_indexable` with `extra.reason`/`extra.word_count` |
| `frontend/src/data/issueHelp.js` | **add** entry (confidence + V4 fields) |
| `docs/issue-codes.md` | regenerate |

## Test plan (`tests/test_ai_content_not_in_text.py`)
**Unit — the helper:**
- H1 + 10 words + one `<img>` → `"media_dominated"`.
- H1 + 30 words + one `<iframe>` → `"answer_in_embed"`.
- H1 + `<object>`/`<embed>` + low text → `"answer_in_embed"`.

**Adversarial — "correct-looking but wrong":**
- **Text-rich page WITH images** (H1 + 800 words + 5 `<img>`) → **NOT flagged** (the key
  false positive: a normal illustrated article is fine).
- **Embedded video on a real article** (H1 + 600 words + `<iframe>`) → **NOT flagged**
  (text carries the content; `wc >= 100`).
- **Thin page with NO media** (H1 + 20 words, no img/video/iframe) → **NOT flagged by
  M3.2** (that's a thin-content code, not this one — proves no double-flagging).
- **No H1** (media-only splash, no heading) → **NOT flagged** (require an H1).

**Integration / contract:**
- `tests/test_issue_checker.py` — a page with `content_not_in_text_reason` set yields
  `AI_CONTENT_NOT_IN_TEXT` with `extra.reason`; a non-indexable page does NOT emit it.
- Contract: the results/pages-issues endpoint the frontend reads includes the code with
  `extra.reason` when present.

## Security check
- **SSRF:** No — pure local DOM inspection, no fetch (embeds are detected, never fetched).
- **Auth:** N/A (crawl/parse time).
- **WordPress:** No.
- **XSS:** No.

## Documentation impact
- `docs/issue-codes.md` — regenerated.
- `docs/thresholds.md` (READ-ONLY) — **untouched**; the two new constants live in code and
  are noted for the compiler.
- `PLAN-V3.0-UNIFIED.md` — note M3.2 done when merged.

## Acceptance criteria
1. Helper returns a reason ONLY when text is below threshold AND non-text content is
   present (or an embed with low surrounding text); requires an H1.
2. All four adversarial guards pass — especially "text-rich page with images → not flagged"
   and "thin page with no media → not flagged" (no double-flag with thin-content codes).
3. Code registered in all 3 registries; issueHelp.js (with V4 fields) + issue-codes.md
   parity passes.
4. Emitted only for indexable pages, with `extra.reason`.
5. `docs/thresholds.md` untouched. Full pytest suite green, 0 regressions.

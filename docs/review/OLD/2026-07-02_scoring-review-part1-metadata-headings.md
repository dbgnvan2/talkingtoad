---
status: draft-review
proposed: 2026-07-02
author: Hermes Agent
type: review
source: User insight — "the weights may be wrong; Google doesn't care that much about H1s but AI GEO cares about heading structure"
scope: metadata + heading issue codes (part 1 of 5)
---

# Scoring Weight Review — Part 1: Metadata + Headings

> **Purpose of this document:** A systematic review of every issue code's (impact, effort) scoring in `_ISSUE_SCORING` (`api/crawler/checkers/registry.py`). Each entry shows the current weight, my assessment of whether it's correct for today's SEO + AI GEO reality, and a specific recommendation.
>
> **How to use this for independent review:** Read each entry below. For each one, note whether you AGREE or DISAGREE with the assessment and recommendation. Your independent assessment is welcome — this is meant to converge on a calibrated scoring system.
>
> **Priority formula:** `priority_rank = (impact × 10) − (effort × 2)` — higher rank = more urgent to fix.
>
> **Severity scale used by the app:** critical > warning > info (independent of numeric impact).

---

## Current Scoring Reference

| Code | Current (impact, effort) | Priority rank | Severity |
|------|--------------------------|---------------|----------|
| TITLE_MISSING | (9, 1) | 88 | critical |
| TITLE_DUPLICATE | (5, 2) | 46 | warning |
| TITLE_TOO_SHORT | (5, 1) | 48 | warning |
| TITLE_TOO_LONG | (4, 1) | 38 | warning |
| META_DESC_MISSING | (7, 1) | 68 | critical |
| META_DESC_DUPLICATE | (4, 2) | 36 | warning |
| META_DESC_TOO_SHORT | (4, 1) | 38 | warning |
| META_DESC_TOO_LONG | (3, 1) | 28 | warning |
| OG_TITLE_MISSING | (4, 1) | 38 | info |
| OG_DESC_MISSING | (3, 1) | 28 | info |
| OG_IMAGE_MISSING | (3, 1) | 28 | info |
| TWITTER_CARD_MISSING | (3, 1) | 28 | info |
| CANONICAL_MISSING | (6, 2) | 56 | warning |
| CANONICAL_EXTERNAL | (5, 2) | 46 | warning |
| CANONICAL_SELF_MISSING | (5, 1) | 48 | info |
| FAVICON_MISSING | (3, 2) | 26 | info |
| TITLE_META_DUPLICATE_PAIR | (6, 2) | 56 | warning |
| TITLE_H1_MISMATCH | (6, 2) | 56 | warning |
| H1_MISSING | (8, 1) | 78 | critical |
| H1_MULTIPLE | (6, 2) | 56 | warning |
| HEADING_SKIP | (4, 3) | 34 | warning |
| HEADING_EMPTY | (4, 1) | 38 | warning |
| LANG_MISSING | (6, 1) | 58 | warning |

---

## Metadata Checks

### TITLE_MISSING — (9, 1) → 88

**Assessment:** Impact 9 is correct. The `<title>` tag remains one of the most important on-page SEO elements. Google uses it heavily for ranking, CTR, and snippet generation. AI GEO systems also use title tags for entity recognition and citation labels. This is well-established.

**Recommendation:** KEEP AS-IS (9, 1)

---

### TITLE_DUPLICATE — (5, 2) → 46

**Assessment:** Impact 5 feels slightly high. Google has said duplicate titles across pages are handled gracefully — they rewrite the snippet title in search results. It doesn't meaningfully harm rankings on individual pages. For AI GEO, duplicate titles also don't matter much since AI citation engines work per-page. Impact 3-4 would be more realistic.

**Recommendation:** LOWER impact from 5 to 3. (3, 2) → 26

---

### TITLE_TOO_SHORT — (5, 1) → 48

**Assessment:** An under-30-character title is a missed opportunity for descriptive keywords, but it's not harming the page directly. Google will still index and rank it. Impact 5 overstates the problem. The effort is right (trivial to fix).

**Recommendation:** LOWER impact from 5 to 3. (3, 1) → 28

---

### TITLE_TOO_LONG — (4, 1) → 38

**Assessment:** Impact 4 is reasonable. Long titles get truncated in SERPs (Google caps at ~60 characters on desktop, ~78 on mobile). This is a real CTR problem, not a ranking penalty. For AI GEO, the full text is still readable by AI systems. Keep as-is.

**Recommendation:** KEEP AS-IS (4, 1)

---

### META_DESC_MISSING — (7, 1) → 68

**Assessment:** Impact 7 is **too high** for today's reality. Google confirmed years ago that meta descriptions are NOT a ranking factor at all. They only affect CTR (by showing auto-generated snippets instead of your chosen text). A missing description is an opportunity cost, not a 7/10 problem. For AI GEO, meta descriptions do help as summary signals for extraction. Impact 4-5 would be more appropriate.

**Recommendation:** LOWER impact from 7 to 5. (5, 1) → 48

---

### META_DESC_DUPLICATE — (4, 2) → 36

**Assessment:** Impact 4 is about right. Same logic as TITLE_DUPLICATE — Google handles it gracefully. Not harmful, just a missed opportunity. Effort 2 is correct (wordpress-fixable across multiple pages).

**Recommendation:** KEEP AS-IS (4, 2)

---

### META_DESC_TOO_SHORT — (4, 1) → 38

**Assessment:** Over-weighted. Google's snippet length is flexible (pixel-based, not character-count). A 50-character description can still produce a good result snippet. Impact 2-3 feels right.

**Recommendation:** LOWER impact from 4 to 2. (2, 1) → 18

---

### META_DESC_TOO_LONG — (3, 1) → 28

**Assessment:** Reasonable. Google truncates long descriptions. Impact 3 is about right — it means the description won't show in full, but it's minor. Keep.

**Recommendation:** KEEP AS-IS (3, 1)

---

### OG_TITLE_MISSING — (4, 1) → 38

**Assessment:** Impact 4 is too high for SEO. Open Graph tags affect social media previews — they have zero direct impact on search rankings. They matter for social sharing CTR, which is indirect. For AI GEO, some engines may use OG data as additional context. Impact 2 would be more honest.

**Recommendation:** LOWER impact from 4 to 2. (2, 1) → 18

---

### OG_DESC_MISSING — (3, 1) → 28

**Assessment:** Same as OG_TITLE — social sharing only, not a ranking signal. Impact 3 is over-weighted.

**Recommendation:** LOWER impact from 3 to 2. (2, 1) → 18

---

### OG_IMAGE_MISSING — (3, 1) → 28

**Assessment:** Social sharing preview image. Missing OG image means a poor-looking social card. Impact 3 is slightly high but defensible — a missing OG image is arguably more harmful than missing OG description. Still, 2 is more honest.

**Recommendation:** LOWER impact from 3 to 2. (2, 1) → 18

---

### TWITTER_CARD_MISSING — (3, 1) → 28

**Assessment:** Twitter/X cards specifically. With Twitter being a less prominent traffic driver for nonprofits, impact 3 is over-weighted. Zero SEO impact. Impact 1-2.

**Recommendation:** LOWER impact from 3 to 1. (1, 1) → 8

---

### CANONICAL_MISSING — (6, 2) → 56

**Assessment:** Impact 6 is reasonable. Missing canonical tags on pages with query strings or near-duplicate content can cause duplicate content issues and diluted link equity. Google explicitly relies on canonical tags for consolidation. AI GEO also benefits from clean canonical URLs for citation. Keep.

**Recommendation:** KEEP AS-IS (6, 2)

---

### CANONICAL_EXTERNAL — (5, 2) → 46

**Assessment:** Impact 5 is reasonable — this is a more specific version of the canonical problem. A canonical pointing to a different domain can cause Google to index the wrong page entirely. However, the effort (2) understates this — fixing an external canonical usually requires developer intervention to change CMS templates. Effort should be higher.

**Recommendation:** KEEP impact 5, RAISE effort from 2 to 3. (5, 3) → 44

---

### CANONICAL_SELF_MISSING — (5, 1) → 48

**Assessment:** Impact 5 is too high. A self-referencing canonical is a best practice, not a requirement. Google can handle pages without it fine — it's insurance, not a necessity. Impact 3 is more appropriate.

**Recommendation:** LOWER impact from 5 to 3. (3, 1) → 28

---

### FAVICON_MISSING — (3, 2) → 26

**Assessment:** Impact 3 is correct. Zero SEO or AI GEO impact. It's a brand-signal and browser convenience. Effort 2 is appropriate (requires image creation + upload). Keep.

**Recommendation:** KEEP AS-IS (3, 2)

---

### TITLE_META_DUPLICATE_PAIR — (6, 2) → 56

**Assessment:** Impact 6 is reasonable. Identical titles AND descriptions on multiple pages is a stronger duplicate signal than either alone. It signals low-quality or template-driven pages. Keep.

**Recommendation:** KEEP AS-IS (6, 2)

---

### TITLE_H1_MISMATCH — (6, 2) → 56

**Assessment:** Impact 6 is fair. A significant mismatch between title and H1 creates a jarring user experience (user clicks search result, sees a different topic in the heading). Google has confirmed this can hurt. For AI GEO, mismatch confuses extractors about the page's main topic. This is well-justified.

**Recommendation:** KEEP AS-IS (6, 2)

---

### LANG_MISSING — (6, 1) → 58

**Assessment:** Impact 6 is **too high**. A missing `lang` attribute is an accessibility concern (screen readers) and a minor SEO signal for multilingual sites. For English-only nonprofit sites, this has near-zero impact. Google detects language from content automatically. Impact 3-4 is more realistic.

**Recommendation:** LOWER impact from 6 to 3. (3, 1) → 28

---

## Heading Checks

### H1_MISSING — (8, 1) → 78

**Assessment:** IMPACT 8 IS TOO HIGH FOR TODAY'S REALITY. This is the most important code to recalibrate.

**For traditional SEO:** Google's John Mueller said explicitly (2021, confirmed multiple times): *"If you have multiple H1s or no H1, that's fine — the HTML spec allows it, and Google handles it."* Google doesn't require an H1 tag. They infer the page's main heading from layout, font size, and proximity. The SEO damage from a missing H1 is near zero.

**For AI GEO:** Headings matter for AI extraction, but AI systems look at the entire heading hierarchy (H1-H6), not just H1. A missing H1 is a structural weakness for AI citation, not a crisis.

**For accessibility:** Screen reader users rely on heading structure for navigation. A missing H1 is a real WCAG concern, but that's a separate concern from SEO scoring.

Impact 5-6 is more appropriate — it's a real signal of poor semantic structure but not a critical SEO problem.

**Recommendation:** LOWER impact from 8 to 5. (5, 1) → 48

---

### H1_MULTIPLE — (6, 2) → 56

**Assessment:** Impact 6 is TOO HIGH. Google explicitly confirmed multiple H1s are fine. The HTML5 spec allows multiple H1s per page (each within its sectioning element). The SEO penalty is zero. For AI GEO, multiple H1s don't hurt extraction. This should be an info-level check at most.

**Recommendation:** LOWER impact from 6 to 2. Change severity from warning to info. (2, 2) → 16

---

### HEADING_SKIP — (4, 3) → 34

**Assessment:** Impact 4 is defensible but effort 3 is too high. Heading skips (H1 → H3) are an accessibility concern (screen reader users navigating by heading level may miss content), and they indicate poor content structure for AI extraction. However, for SEO impact alone, this is minimal — Google doesn't penalize heading skip patterns. Effort 3 implies "significant developer work" to fix, but often it's a content-edit task (re-tag a heading). Effort 1-2.

**Recommendation:** KEEP impact 4, LOWER effort from 3 to 2. (4, 2) → 36

---

### HEADING_EMPTY — (4, 1) → 38

**Assessment:** Impact 4 is about right. Empty headings waste the semantic structure and confuse screen readers and AI extractors. Effort 1 is correct (trivial edit). Keep.

**Recommendation:** KEEP AS-IS (4, 1)

---

## Part 1 Summary

| Code | Current | Proposed | Delta |
|------|---------|----------|-------|
| TITLE_DUPLICATE | (5, 2) | (3, 2) | -2 impact |
| TITLE_TOO_SHORT | (5, 1) | (3, 1) | -2 impact |
| META_DESC_MISSING | (7, 1) | (5, 1) | -2 impact |
| META_DESC_TOO_SHORT | (4, 1) | (2, 1) | -2 impact |
| OG_TITLE_MISSING | (4, 1) | (2, 1) | -2 impact |
| OG_DESC_MISSING | (3, 1) | (2, 1) | -1 impact |
| OG_IMAGE_MISSING | (3, 1) | (2, 1) | -1 impact |
| TWITTER_CARD_MISSING | (3, 1) | (1, 1) | -2 impact |
| CANONICAL_EXTERNAL | (5, 2) | (5, 3) | +1 effort |
| CANONICAL_SELF_MISSING | (5, 1) | (3, 1) | -2 impact |
| LANG_MISSING | (6, 1) | (3, 1) | -3 impact |
| H1_MISSING | (8, 1) | (5, 1) | -3 impact |
| H1_MULTIPLE | (6, 2) | (2, 2) | -4 impact |
| HEADING_SKIP | (4, 3) | (4, 2) | -1 effort |

**Priority rank drops (most improved):**
- H1_MULTIPLE: 56 → 16 (no longer a priority)
- H1_MISSING: 78 → 48 (still worth addressing, but not critical)
- LANG_MISSING: 58 → 28

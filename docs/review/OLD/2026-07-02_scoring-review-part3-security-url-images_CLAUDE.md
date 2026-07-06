---
status: draft-review + claude-overlay
proposed: 2026-07-02
authors: Hermes Agent (original) + Claude Opus 4.8 (overlay)
type: review
scope: security + URL structure + image checks (part 3 of 5)
---

# Scoring Weight Review — Part 3: Security, URL Structure, Image Checks
### (with Claude assessment blocks interleaved)

> Hermes's original text is unchanged. After each code, a block marked **◆ CLAUDE — Confidence: …** gives an independent second opinion.

---

## Security Checks

### HTTP_PAGE — (9, 2) → 86

**Assessment:** Impact 9 is absolutely correct. HTTP pages are marked "not secure" by browsers, Google uses HTTPS as a ranking signal, and HTTP pages lose referral data. This is a fundamental baseline. Effort 2 is reasonable for nonprofits (many hosts offer free Let's Encrypt SSL). Keep.

**Recommendation:** KEEP AS-IS (9, 2)

> **◆ CLAUDE — Confidence: High**
> Agree, (9, 2). HTTPS as a (lightweight) ranking signal is confirmed since 2014; the browser "Not secure" label is the bigger real-world cost. SiteGround provides free Let's Encrypt, so effort 2 is right. No change.

---

### HTTPS_REDIRECT_MISSING — (9, 2) → 86

**Assessment:** Impact 9 is correct. If HTTP doesn't redirect to HTTPS, both versions exist — visitors who type the bare domain reach an insecure version, and Google treats HTTP and HTTPS as separate URLs. Effort 2 is right (server config change). Keep.

**Recommendation:** KEEP AS-IS (9, 2)

> **◆ CLAUDE — Confidence: High**
> Agree, (9, 2). Duplicate HTTP/HTTPS URL sets also split signals until canonicalized. Directly relevant to your migration — verify the SiteGround HTTP→HTTPS redirect fires at cutover. Correct.

---

### MIXED_CONTENT — (6, 2) → 56

**Assessment:** Impact 6 is reasonable. Mixed content (HTTPS page loading HTTP resources) causes the browser to show a mixed security warning and potentially block the insecure resources. This can break page functionality and erode user trust. However, many mixed-content issues are with third-party embeds that the site owner can't easily change (YouTube, Twitter). Impact 5-6 is defensible. Keep.

**Recommendation:** KEEP AS-IS (6, 2)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (6, 2), with an update: modern browsers now **auto-upgrade** passive mixed content (images, media) to HTTPS and **block** active mixed content (scripts, iframes) outright. So the practical failure mode is narrower than it used to be — active resources break, passive ones silently upgrade. Distinguish the two if you can; active mixed content deserves the 6, passive is closer to 3. Vimeo (your video host) serves HTTPS, so this should be rare for you.

---

### MISSING_HSTS — (4, 2) → 36

**Assessment:** Impact 4 is reasonable for an info-level check. HSTS is a security best practice (forces browser to always use HTTPS), but its absence doesn't harm the current connection — only future connections from the same browser SSL-stripping attacks. For a nonprofit, this is a nice-to-have, not a priority. Keep.

**Recommendation:** KEEP AS-IS (4, 2)

> **◆ CLAUDE — Confidence: Medium**
> Slightly high; I'd consider 3. HSTS only matters once a correct HTTPS redirect already exists (which HTTPS_REDIRECT_MISSING covers), and it protects against a narrow SSL-stripping scenario. Zero SEO impact. For a nonprofit with no login/PII beyond contact forms, it's genuinely optional. (3, 2) or keep 4 — low stakes.

---

### UNSAFE_CROSS_ORIGIN_LINK — (3, 1) → 28

**Assessment:** Impact 3 is reasonable. Links opening in new tabs without `rel="noopener"` create a minor security vulnerability (reverse tabnapping). However, this is a low-likelihood exploit for most sites. Impact 3 is fine for info level.

**Recommendation:** KEEP AS-IS (3, 1)

> **◆ CLAUDE — Confidence: High**
> Lower to (2, 1). Since ~2021, Chrome, Firefox, and Safari set `rel="noopener"` **implicitly** for any `target="_blank"`, so the reverse-tabnabbing vector is neutralized by the browser regardless of markup. The check now flags a mostly-theoretical issue against modern browsers. Also: WordPress adds `noopener` automatically when you set a link to open in a new tab in the editor. Drop to 2.

---

### WWW_CANONICALIZATION — (5, 2) → 46

**Assessment:** Impact 5 is reasonable. Both www and non-www versions serving content without redirect means potential duplicate content and split link equity. This is a real structural issue. Effort 2 is right (server config). Keep.

**Recommendation:** KEEP AS-IS (5, 2)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (5, 2). Directly relevant: livingsystems.ca resolves at `www` per your earlier note — confirm one host 301-redirects to the other after the SiteGround move so you don't end up with both indexed. Correct.

---

## URL Structure Checks

### URL_TOO_LONG — (2, 4) → 12

**Assessment:** Impact 2 is correct. Long URLs (over 200 chars) are a minor detriment — they get truncated in SERPs and are harder to share. They don't affect ranking significantly. However, effort 4 (major dev work) is WAY too high for a URL slug edit. Changing a URL is a content-edit task in most CMSs (WordPress slug field, etc.). Effort should be 1.

**Recommendation:** KEEP impact 2, LOWER effort from 4 to 1. (2, 1) → 18

> **◆ CLAUDE — Confidence: High**
> Agree on (2, ~1), with one caution: changing a slug on a *published, indexed* page means creating a redirect and losing a little equity — so "effort 1" is right for drafts but understates the care needed on live URLs. Net effort 1–2. Impact 2 is correct.

---

### URL_UPPERCASE — (3, 2) → 26

**Assessment:** Impact 3 is too high. Uppercase URLs are automatically corrected to lowercase by most web servers (via redirect). This check flags a theoretical issue that mainly exists on case-sensitive servers. The extra redirect is minor. Impact 2 is more appropriate.

**Recommendation:** LOWER impact from 3 to 2. (2, 2) → 16

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 2). Minor correction: Linux/Apache paths *are* case-sensitive by default, so uppercase URLs aren't universally auto-corrected — but WordPress permalinks are lowercased at creation, so real occurrences are rare. Low impact is right.

---

### URL_HAS_SPACES — (5, 3) → 44

**Assessment:** Impact 5 is too high. URLs with encoded spaces (%20) are ugly and non-standard but they work. Google handles them fine in modern crawlers. They're a best-practice violation, not a 5/10 problem. Impact 3 is more appropriate. Effort 3 is also too high — fixing a URL slug is a content edit.

**Recommendation:** LOWER impact from 5 to 3, LOWER effort from 3 to 1. (3, 1) → 28

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (3, 1). WordPress replaces spaces with hyphens in slugs automatically, so this mostly appears in uploaded file names (e.g., PDF/image URLs), not page slugs. That makes it more of a media-hygiene flag. 3 is right.

---

### URL_HAS_UNDERSCORES — (2, 4) → 12

**Assessment:** Impact 2 is correct. Underscores in URLs are a minor issue — Google treats them as word-joiners (unlike hyphens which separate words). This matters for URL readability and keyword matching. But effort 4 is too high — changing underscores to hyphens in a slug is a content-edit task, effort 1.

**Recommendation:** KEEP impact 2, LOWER effort from 4 to 1. (2, 1) → 18

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 1). Update the rationale: the "underscore = joiner, hyphen = separator" distinction is legacy (Matt Cutts era). Google has since said word separators in URLs barely matter for ranking. So the residual value is readability, not keyword parsing. Impact 2 (arguably 1) is right.

---

## Image Checks

### IMG_OVERSIZED — (5, 2) → 46

**Assessment:** Impact 5 is reasonable. Oversized images (>200KB) slow page load, hurt Core Web Vitals, and waste bandwidth. For mobile users this is a real UX issue. Effort 2 is right (compress and re-upload). Keep.

**Recommendation:** KEEP AS-IS (5, 2)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (5, 2). The 200KB threshold is reasonable for a hero/full-width image but strict for a genuine full-bleed background. Consider making the threshold role-aware (thumbnail vs hero) to cut false positives. Score fine.

---

### IMG_ALT_MISSING — (5, 2) → 46

**Assessment:** Impact 5 is reasonable. Missing alt text hurts accessibility for screen reader users and is a missed opportunity for image SEO (Google uses alt text for image search ranking). For AI GEO, alt text helps AI engines understand image content. However, impact 5 feels slightly low given that alt text serves both SEO and accessibility — impact 6-7 could be argued. Impact 5 is defensible.

**Recommendation:** KEEP AS-IS (5, 2)

> **◆ CLAUDE — Confidence: High**
> Agree, (5, 2). This is the one image check I'd let drift *up* to 6 rather than down, because it's a WCAG 1.1.1 Level A failure (the most basic conformance tier) *and* an image-SEO signal — dual justification. But 5 is defensible. Note: purely decorative images should have empty `alt=""`, which is correct, not "missing" — make sure the check treats intentional empty alt on decorative images as a pass (this is the flip side of IMG_ALT_MISUSED below).

---

### IMG_ALT_TOO_SHORT — (3, 1) → 28

**Assessment:** Impact 3 is reasonable. Very short alt text (<5 chars) like "img001" or "logo" is essentially meaningless. This is a missed opportunity but not a penalty-worthy issue. Keep.

**Recommendation:** KEEP AS-IS (3, 1)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 1). Caveat: "logo" is actually acceptable alt for a logo, and short alt is often correct (a checkmark icon → "included"). Length is a weak proxy for quality; expect false positives. Score fine, but don't over-trust the signal.

---

### IMG_ALT_TOO_LONG — (2, 1) → 18

**Assessment:** Impact 2 is reasonable. Long alt text (>125 chars) gets truncated by screen readers. Shortening it is a best practice. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 1). Correction: the 125-char figure is a rule of thumb, not a hard screen-reader truncation limit — most readers announce the full alt. Long alt is a style smell (often a caption crammed into alt), not a functional break. 2 is right.

---

### IMG_ALT_GENERIC — (4, 1) → 38

**Assessment:** Impact 4 is slightly high. Generic alt text like "image", "photo", "picture" is better than nothing but poor quality. It's a content quality concern, not an SEO problem. Impact 3 is more accurate.

**Recommendation:** LOWER impact from 4 to 3. (3, 1) → 28

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 1). Arguably generic alt is *worse* than empty alt for a screen-reader user (it announces "image" for no benefit), but the fix and severity are the same tier. 3 is right.

---

### IMG_ALT_DUP_FILENAME — (3, 1) → 28

**Assessment:** Impact 3 is reasonable. When alt text matches the filename (e.g., "sunset-beach.jpg"), it's lazy but not harmful — at least it's descriptive. Keep.

**Recommendation:** KEEP AS-IS (3, 1)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 1). This is the WordPress default behavior (media library auto-fills alt/title from filename on some setups), so expect it to fire broadly. Low impact is correct precisely because it's usually harmless-but-lazy.

---

### IMG_ALT_MISUSED — (3, 2) → 26

**Assessment:** Impact 3 is reasonable. Decorative images with descriptive alt text create unnecessary screen reader noise (they should have empty alt text). This is an accessibility quality concern. Effort 2 is appropriate (may require template changes).

**Recommendation:** KEEP AS-IS (3, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (3, 2). This is the correct complement to IMG_ALT_MISSING: decorative images *should* have `alt=""`. The hard part is detection — deciding what's "decorative" is a judgment call your crawler can only heuristically make (e.g., spacer images, background-role images). Expect low precision; keep impact modest. 3 is right.

---

### IMG_SLOW_LOAD — (4, 2) → 36

**Assessment:** Impact 4 is reasonable. Slow-loading images (>1s) directly affect Core Web Vitals (LCP), which is a Google ranking factor. Effort 2 is right (compress, CDN, lazy load). Keep.

**Recommendation:** KEEP AS-IS (4, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 2). Precision note: only the LCP image matters for the Core Web Vitals ranking signal — a slow below-the-fold image shouldn't be scored like a slow hero. And lazy-loading the LCP image *hurts* LCP, so "lazy load" is the wrong fix for the one image that matters. If the check can identify the LCP element, weight it higher and everything else lower.

---

### IMG_OVERSCALED — (4, 3) → 34

**Assessment:** Impact 4 is reasonable. Overscaled images (intrinsic size > 2x display size) waste bandwidth and slow load. Effort 3 is slightly high — many CMSs handle responsive images automatically. Effort 2 is more appropriate.

**Recommendation:** KEEP impact 4, LOWER effort from 3 to 2. (4, 2) → 36

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 2). WordPress generates multiple sizes and `srcset` automatically, so overscaling usually comes from a theme/Elementor setting forcing a full-size source. Fix is a settings change, so effort 2 is right.

---

### IMG_POOR_COMPRESSION — (4, 2) → 36

**Assessment:** Impact 4 is reasonable. Poor compression means excessive file size for the quality level, which slows page load. Effort 2 is right (re-compress and upload). Keep.

**Recommendation:** KEEP AS-IS (4, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (4, 2). Overlaps conceptually with IMG_OVERSIZED and IMG_POOR_COMPRESSION/OVERSCALED — three checks all pointing at "image payload too big for what's displayed." Make sure they don't stack into three findings for one oversized hero. Score fine.

---

### IMG_FORMAT_LEGACY — (2, 2) → 16

**Assessment:** Impact 2 is correct. Using JPEG/PNG instead of WebP is a missed optimization but not a critical issue — JPEG still works fine. Keep.

**Recommendation:** KEEP AS-IS (2, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 2). By 2026 AVIF is the more aggressive target than WebP, but WebP has universal support and is the safe recommendation. A SiteGround-hosted WordPress site can auto-convert to WebP via a plugin or SiteGround Optimizer, making this near-zero effort. 2 is right.

---

### IMG_NO_SRCSET — (2, 3) → 14

**Assessment:** Impact 2 is correct. Missing `srcset` means mobile users download the same large image as desktop. This hurts mobile performance but doesn't break anything. Effort 3 is reasonable (template/theme change needed). Keep.

**Recommendation:** KEEP AS-IS (2, 3)

> **◆ CLAUDE — Confidence: Medium-High**
> Agree, (2, 3). WordPress adds `srcset` automatically for library images since 4.4, so a *missing* srcset usually means a hand-coded `<img>` or a page-builder element bypassing the media API — worth surfacing precisely because it's non-default. 2 is right.

---

### IMG_DUPLICATE_CONTENT — (2, 2) → 16

**Assessment:** Impact 2 is correct. Same image at multiple URLs wastes storage and caching but has no direct SEO impact. Keep.

**Recommendation:** KEEP AS-IS (2, 2)

> **◆ CLAUDE — Confidence: Medium**
> Agree, (2, 2). Common and benign (WordPress generating multiple crops of one upload). Observational. Correct.

---

### IMG_BROKEN — (8, 2) → 76

**Assessment:** Impact 8 is correct. A broken image (4xx/5xx src) creates a broken visual in the page. It's a visible problem for users. However, impact 8 is slightly lower than a broken link (10) — images don't pass link equity, and the UX impact is visual rather than navigational. This weighting is reasonable. Keep.

**Recommendation:** KEEP AS-IS (8, 2)

> **◆ CLAUDE — Confidence: High**
> Agree, (8, 2). Highly relevant to your blog migration: your saved process keeps image URLs pointing at livingsystems.ca for later download, so during migration staging posts will legitimately show "broken" images until attachments are pulled in. Make sure this check is run *after* the "Download attachments" import step, or it will fire on every migrated post. Correct positioning just below broken-link.

---

## Part 3 Summary — Claude deltas vs Hermes

| Code | Hermes proposed | Claude | Why |
|------|-----------------|--------|-----|
| UNSAFE_CROSS_ORIGIN_LINK | keep (3, 1) | (2, 1) | Browsers set `noopener` by default since ~2021; near-theoretical now |
| MISSING_HSTS | keep (4, 2) | (3, 2) | Narrow SSL-strip scenario, zero SEO; optional for a nonprofit |
| IMG_ALT_MISSING | keep (5, 2) | (5–6, 2) | WCAG 1.1.1 Level A + image SEO; the one to let drift up, not down |

All other Part 3 items: **agree with Hermes.** Detection/precision cautions logged for MIXED_CONTENT (active vs passive), IMG_SLOW_LOAD (LCP element only), the three overlapping image-payload checks, and IMG_BROKEN (run after migration attachment import).

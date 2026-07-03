---
status: draft-review
proposed: 2026-07-02
author: Hermes Agent
type: review
scope: security + URL structure + image checks (part 3 of 5)
---

# Scoring Weight Review — Part 3: Security, URL Structure, Image Checks

> Each entry shows current weight, assessment, and recommendation.

---

## Current Scoring Reference

| Code | Current (impact, effort) | Priority rank | Severity |
|------|--------------------------|---------------|----------|
| HTTP_PAGE | (9, 2) | 86 | critical |
| HTTPS_REDIRECT_MISSING | (9, 2) | 86 | critical |
| MIXED_CONTENT | (6, 2) | 56 | warning |
| MISSING_HSTS | (4, 2) | 36 | info |
| UNSAFE_CROSS_ORIGIN_LINK | (3, 1) | 28 | info |
| WWW_CANONICALIZATION | (5, 2) | 46 | warning |
| URL_TOO_LONG | (2, 4) | 12 | info |
| URL_UPPERCASE | (3, 2) | 26 | warning |
| URL_HAS_SPACES | (5, 3) | 44 | warning |
| URL_HAS_UNDERSCORES | (2, 4) | 12 | info |
| IMG_OVERSIZED | (5, 2) | 46 | warning |
| IMG_ALT_MISSING | (5, 2) | 46 | warning |
| IMG_ALT_TOO_SHORT | (3, 1) | 28 | warning |
| IMG_ALT_TOO_LONG | (2, 1) | 18 | warning |
| IMG_ALT_GENERIC | (4, 1) | 38 | warning |
| IMG_ALT_DUP_FILENAME | (3, 1) | 28 | warning |
| IMG_ALT_MISUSED | (3, 2) | 26 | warning |
| IMG_SLOW_LOAD | (4, 2) | 36 | warning |
| IMG_OVERSCALED | (4, 3) | 34 | warning |
| IMG_POOR_COMPRESSION | (4, 2) | 36 | warning |
| IMG_FORMAT_LEGACY | (2, 2) | 16 | info |
| IMG_NO_SRCSET | (2, 3) | 14 | info |
| IMG_DUPLICATE_CONTENT | (2, 2) | 16 | info |
| IMG_BROKEN | (8, 2) | 76 | critical |

---

## Security Checks

### HTTP_PAGE — (9, 2) → 86

**Assessment:** Impact 9 is absolutely correct. HTTP pages are marked "not secure" by browsers, Google uses HTTPS as a ranking signal, and HTTP pages lose referral data. This is a fundamental baseline. Effort 2 is reasonable for nonprofits (many hosts offer free Let's Encrypt SSL). Keep.

**Recommendation:** KEEP AS-IS (9, 2)

---

### HTTPS_REDIRECT_MISSING — (9, 2) → 86

**Assessment:** Impact 9 is correct. If HTTP doesn't redirect to HTTPS, both versions exist — visitors who type the bare domain reach an insecure version, and Google treats HTTP and HTTPS as separate URLs. Effort 2 is right (server config change). Keep.

**Recommendation:** KEEP AS-IS (9, 2)

---

### MIXED_CONTENT — (6, 2) → 56

**Assessment:** Impact 6 is reasonable. Mixed content (HTTPS page loading HTTP resources) causes the browser to show a mixed security warning and potentially block the insecure resources. This can break page functionality and erode user trust. However, many mixed-content issues are with third-party embeds that the site owner can't easily change (YouTube, Twitter). Impact 5-6 is defensible. Keep.

**Recommendation:** KEEP AS-IS (6, 2)

---

### MISSING_HSTS — (4, 2) → 36

**Assessment:** Impact 4 is reasonable for an info-level check. HSTS is a security best practice (forces browser to always use HTTPS), but its absence doesn't harm the current connection — only future connections from the same browser SSL-stripping attacks. For a nonprofit, this is a nice-to-have, not a priority. Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

### UNSAFE_CROSS_ORIGIN_LINK — (3, 1) → 28

**Assessment:** Impact 3 is reasonable. Links opening in new tabs without `rel="noopener"` create a minor security vulnerability (reverse tabnapping). However, this is a low-likelihood exploit for most sites. Impact 3 is fine for info level.

**Recommendation:** KEEP AS-IS (3, 1)

---

### WWW_CANONICALIZATION — (5, 2) → 46

**Assessment:** Impact 5 is reasonable. Both www and non-www versions serving content without redirect means potential duplicate content and split link equity. This is a real structural issue. Effort 2 is right (server config). Keep.

**Recommendation:** KEEP AS-IS (5, 2)

---

## URL Structure Checks

### URL_TOO_LONG — (2, 4) → 12

**Assessment:** Impact 2 is correct. Long URLs (over 200 chars) are a minor detriment — they get truncated in SERPs and are harder to share. They don't affect ranking significantly. However, effort 4 (major dev work) is WAY too high for a URL slug edit. Changing a URL is a content-edit task in most CMSs (WordPress slug field, etc.). Effort should be 1.

**Recommendation:** KEEP impact 2, LOWER effort from 4 to 1. (2, 1) → 18

---

### URL_UPPERCASE — (3, 2) → 26

**Assessment:** Impact 3 is too high. Uppercase URLs are automatically corrected to lowercase by most web servers (via redirect). This check flags a theoretical issue that mainly exists on case-sensitive servers. The extra redirect is minor. Impact 2 is more appropriate.

**Recommendation:** LOWER impact from 3 to 2. (2, 2) → 16

---

### URL_HAS_SPACES — (5, 3) → 44

**Assessment:** Impact 5 is too high. URLs with encoded spaces (%20) are ugly and non-standard but they work. Google handles them fine in modern crawlers. They're a best-practice violation, not a 5/10 problem. Impact 3 is more appropriate. Effort 3 is also too high — fixing a URL slug is a content edit.

**Recommendation:** LOWER impact from 5 to 3, LOWER effort from 3 to 1. (3, 1) → 28

---

### URL_HAS_UNDERSCORES — (2, 4) → 12

**Assessment:** Impact 2 is correct. Underscores in URLs are a minor issue — Google treats them as word-joiners (unlike hyphens which separate words). This matters for URL readability and keyword matching. But effort 4 is too high — changing underscores to hyphens in a slug is a content-edit task, effort 1.

**Recommendation:** KEEP impact 2, LOWER effort from 4 to 1. (2, 1) → 18

---

## Image Checks

### IMG_OVERSIZED — (5, 2) → 46

**Assessment:** Impact 5 is reasonable. Oversized images (>200KB) slow page load, hurt Core Web Vitals, and waste bandwidth. For mobile users this is a real UX issue. Effort 2 is right (compress and re-upload). Keep.

**Recommendation:** KEEP AS-IS (5, 2)

---

### IMG_ALT_MISSING — (5, 2) → 46

**Assessment:** Impact 5 is reasonable. Missing alt text hurts accessibility for screen reader users and is a missed opportunity for image SEO (Google uses alt text for image search ranking). For AI GEO, alt text helps AI engines understand image content. However, impact 5 feels slightly low given that alt text serves both SEO and accessibility — impact 6-7 could be argued. Impact 5 is defensible.

**Recommendation:** KEEP AS-IS (5, 2)

---

### IMG_ALT_TOO_SHORT — (3, 1) → 28

**Assessment:** Impact 3 is reasonable. Very short alt text (<5 chars) like "img001" or "logo" is essentially meaningless. This is a missed opportunity but not a penalty-worthy issue. Keep.

**Recommendation:** KEEP AS-IS (3, 1)

---

### IMG_ALT_TOO_LONG — (2, 1) → 18

**Assessment:** Impact 2 is reasonable. Long alt text (>125 chars) gets truncated by screen readers. Shortening it is a best practice. Keep.

**Recommendation:** KEEP AS-IS (2, 1)

---

### IMG_ALT_GENERIC — (4, 1) → 38

**Assessment:** Impact 4 is slightly high. Generic alt text like "image", "photo", "picture" is better than nothing but poor quality. It's a content quality concern, not an SEO problem. Impact 3 is more accurate.

**Recommendation:** LOWER impact from 4 to 3. (3, 1) → 28

---

### IMG_ALT_DUP_FILENAME — (3, 1) → 28

**Assessment:** Impact 3 is reasonable. When alt text matches the filename (e.g., "sunset-beach.jpg"), it's lazy but not harmful — at least it's descriptive. Keep.

**Recommendation:** KEEP AS-IS (3, 1)

---

### IMG_ALT_MISUSED — (3, 2) → 26

**Assessment:** Impact 3 is reasonable. Decorative images with descriptive alt text create unnecessary screen reader noise (they should have empty alt text). This is an accessibility quality concern. Effort 2 is appropriate (may require template changes).

**Recommendation:** KEEP AS-IS (3, 2)

---

### IMG_SLOW_LOAD — (4, 2) → 36

**Assessment:** Impact 4 is reasonable. Slow-loading images (>1s) directly affect Core Web Vitals (LCP), which is a Google ranking factor. Effort 2 is right (compress, CDN, lazy load). Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

### IMG_OVERSCALED — (4, 3) → 34

**Assessment:** Impact 4 is reasonable. Overscaled images (intrinsic size > 2x display size) waste bandwidth and slow load. Effort 3 is slightly high — many CMSs handle responsive images automatically. Effort 2 is more appropriate.

**Recommendation:** KEEP impact 4, LOWER effort from 3 to 2. (4, 2) → 36

---

### IMG_POOR_COMPRESSION — (4, 2) → 36

**Assessment:** Impact 4 is reasonable. Poor compression means excessive file size for the quality level, which slows page load. Effort 2 is right (re-compress and upload). Keep.

**Recommendation:** KEEP AS-IS (4, 2)

---

### IMG_FORMAT_LEGACY — (2, 2) → 16

**Assessment:** Impact 2 is correct. Using JPEG/PNG instead of WebP is a missed optimization but not a critical issue — JPEG still works fine. Keep.

**Recommendation:** KEEP AS-IS (2, 2)

---

### IMG_NO_SRCSET — (2, 3) → 14

**Assessment:** Impact 2 is correct. Missing `srcset` means mobile users download the same large image as desktop. This hurts mobile performance but doesn't break anything. Effort 3 is reasonable (template/theme change needed). Keep.

**Recommendation:** KEEP AS-IS (2, 3)

---

### IMG_DUPLICATE_CONTENT — (2, 2) → 16

**Assessment:** Impact 2 is correct. Same image at multiple URLs wastes storage and caching but has no direct SEO impact. Keep.

**Recommendation:** KEEP AS-IS (2, 2)

---

### IMG_BROKEN — (8, 2) → 76

**Assessment:** Impact 8 is correct. A broken image (4xx/5xx src) creates a broken visual in the page. It's a visible problem for users. However, impact 8 is slightly lower than a broken link (10) — images don't pass link equity, and the UX impact is visual rather than navigational. This weighting is reasonable. Keep.

**Recommendation:** KEEP AS-IS (8, 2)

---

## Part 3 Summary

| Code | Current | Proposed | Delta |
|------|---------|----------|-------|
| URL_TOO_LONG | (2, 4) | (2, 1) | -3 effort |
| URL_UPPERCASE | (3, 2) | (2, 2) | -1 impact |
| URL_HAS_SPACES | (5, 3) | (3, 1) | -2 impact, -2 effort |
| URL_HAS_UNDERSCORES | (2, 4) | (2, 1) | -3 effort |
| IMG_ALT_GENERIC | (4, 1) | (3, 1) | -1 impact |
| IMG_OVERSCALED | (4, 3) | (4, 2) | -1 effort |

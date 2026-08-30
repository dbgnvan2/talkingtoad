# `alt=""` is reported as "missing alt text", contradicting the crawler's own image path

**Date:** 2026-08-30
**Status:** Proposed — awaiting approval
**Reported by:** user — "I fixed ALL of my Alt Text with other tools, why are you
reporting so much missing?"

## Problem

Job `a87e2d61` (livingsystems.ca, 256 pages, all analyses) reports **156
`IMG_ALT_MISSING` issues**. The user had already fixed every alt attribute using
other tools, and those tools were right.

Ground truth — raw HTML, browser UA, 7 pages sampled across the site:

| Page | `<img>` | **no `alt` attribute** | `alt=""` | `alt` with text |
|---|---|---|---|---|
| `/` | 11 | **0** | 10 | 1 |
| `/about/` | 16 | **0** | 12 | 4 |
| `/counselling/` | 22 | **0** | 9 | 13 |
| `/clinical-training/` | 10 | **0** | 8 | 2 |
| `/bowen_family_systems_blog/` | 9 | **0** | 8 | 1 |
| `/team_members/dave-galloway/` | 10 | **0** | 8 | 2 |
| `/training-2/` | 22 | **0** | 8 | 14 |

**No image on any sampled page is missing its `alt` attribute.** Every one of the
156 findings is an image with `alt=""`.

Scale of the report vs. the reality:

- 156 issues = **one per page**, not one per image.
- They name only **15 distinct images**, of which **4 theme/footer logos**
  (`white-logo.svg`, `bc_logo.svg`, `city_of_nv.svg`, `district_of_nv.svg`)
  account for **1,244 of 1,265 instances (98%)** — they sit in the template on
  every page, twice each.
- The remainder: 6 images on 2 pages each, and 5 one-offs including a PayPal
  tracking pixel and a placeholder URL `http://TEST_headshot`.

## Root cause — two contradictory definitions in the same crawl

`api/crawler/parser.py:1495 _detect_decorative()` states the correct rule
explicitly:

```python
# Empty alt (intentionally decorative) - but NOT missing alt (None)
if alt is not None and isinstance(alt, str) and alt.strip() == "":
    return True
```

Two consumers then disagree about it:

| Path | Code | `alt=""` verdict | Findings in job `a87e2d61` |
|---|---|---|---|
| **Image analysis** | `image_analyzer.py:160` — `if not img.is_decorative:` | decorative, **not** flagged | **0** |
| **Per-page check** | `parser.py:1121 _count_img_missing_alt` + `:1216 _find_img_missing_alt_srcs` → `issue_checker.py:482` | flagged as missing | **156** |

Confirmed against the stored data: the `images` table marks exactly **15** images
`is_decorative=1`, and those are **the same 15 images** the page path reports as
missing alt — a perfect intersection, opposite verdicts, same crawl.

`_count_img_missing_alt`'s docstring makes the divergence deliberate ("Both
missing alt and empty `alt=""` are flagged"), so this is a design decision rather
than a typo — but it is the wrong one on three counts:

1. **The label asserts something false.** `alt=""` is not a missing attribute.
   Under WCAG 1.1.1 it is the *prescribed* markup for a decorative image; a
   screen reader skips it, which is the intended behaviour. Reporting correct
   markup as an absence tells the user to "fix" something already right.
2. **It contradicts the sibling path** in the same crawl, so the product holds
   two answers to one question and surfaces the harsher one.
3. **It disagrees with every other tool**, which is exactly how the user found
   it — our report is the outlier, and the outlier is wrong.

## Fix

### A1 — align the page path with `_detect_decorative` (the correctness fix)

`_count_img_missing_alt` and `_find_img_missing_alt_srcs` flag an image only when
the `alt` attribute is **absent** (`tag.get("alt") is None`). A present-but-empty
`alt` is decorative and is not `IMG_ALT_MISSING`. Whitespace-only `alt=" "` stays
flagged — that is neither valid decorative markup nor descriptive text.

Expected effect on job `a87e2d61`: **156 → 0** `IMG_ALT_MISSING`, matching the
image-analysis path's existing verdict of 0.

### A2 — a separate, honest code for the real observation (decide before build)

The four funder/partner logos arguably *should* carry alt text — a logo naming a
funder conveys meaning, so `alt="Province of British Columbia"` beats `alt=""`.
That is a legitimate finding, but it is **"empty alt on an image that looks
meaningful"**, not "missing alt". No existing code covers it: `IMG_ALT_MISUSED`
is the inverse (decorative image *with* alt text).

Proposed `IMG_ALT_EMPTY_MEANINGFUL` — severity `info`, impact ≤ `IMG_ALT_MISUSED`
(1, 2), fires only when `alt=""` **and** the image is not otherwise marked
decorative (`role="presentation"`, `aria-hidden="true"`, dimensions < 32px)
**and** it is not a known tracking pixel. Catalogue + `issueHelp.js` +
`issue_help_data.py` + `docs/issue-codes.md` parity required.

**This needs your decision:** ship A1 alone (the false positives go away), or A1
plus A2 (they come back as 4 accurate, low-severity, actionable findings). I
recommend **A1 + A2** — the underlying observation about the funder logos is
worth keeping, it just needs a name that is true.

### A3 — report distinct images, not page instances

Whichever of the above ships, the finding should say *"4 images, on 312 pages"*
rather than emitting 156 near-identical page-level issues naming the same 15
files. The E4 site-prevalence machinery already exists for this; wire the alt
codes into it. Out of scope for the correctness fix; recorded so it is not lost.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| A1.1 | `alt=""` does **not** produce `IMG_ALT_MISSING` | `tests/test_image_alt.py::test_a1_empty_alt_is_decorative_not_missing` |
| A1.2 | Adversarial: a genuinely absent `alt` **is** still flagged | `…::test_a1_absent_alt_attribute_still_flagged` |
| A1.3 | Whitespace-only `alt=" "` is still flagged | `…::test_a1_whitespace_alt_still_flagged` |
| A1.4 | The two paths agree: same fixture, page path and image path return the same verdict | `…::test_a1_page_and_image_paths_agree_on_empty_alt` |
| A1.5 | Real-artifact regression: the actual footer-logo markup from livingsystems.ca (`data-src` + `title="" alt=""` + `class="lazyload"`) yields no `IMG_ALT_MISSING` | `…::test_a1_real_lazyload_footer_logo_not_flagged` |
| A2.1 | *(if approved)* `alt=""` on a meaningful image emits `IMG_ALT_EMPTY_MEANINGFUL` | `…::test_a2_empty_alt_on_meaningful_image` |
| A2.2 | *(if approved)* `role="presentation"` / `aria-hidden` / tiny images do **not** | `…::test_a2_explicitly_decorative_not_flagged` |
| A2.3 | *(if approved)* catalogue ↔ help ↔ scoring ↔ confidence parity | existing parity tests in `tests/test_architecture_constraints.py` |

A1.4 is the load-bearing one: it binds the two paths together so they cannot
drift apart again.

## Adjacent issues found, not fixed

1. **`http://TEST_headshot`** is referenced as an image `src` somewhere on the
   site — a placeholder that escaped into production content. Not a crawler bug;
   worth telling the site owner.
2. **The PayPal tracking pixel** (`paypalobjects.com/en_US/i/scr/pixel.gif`) is
   counted as a content image. A 1×1 tracking pixel is neither decorative-by-
   markup nor meaningful; `_detect_decorative`'s <32px rule should catch it but
   evidently did not, because the dimensions are not in the markup. Low priority.
3. **`IMG_ALT_MISSING` impact is `(3, 2)`** and it is labelled confidence
   "Established". Both are defensible for genuinely missing alt; neither is
   defensible for the current over-broad trigger. A1 resolves this without a
   scoring change.

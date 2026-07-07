# Canonical-respecting duplicate detection

**Date:** 2026-07-07
**Status:** Implemented (tests green; not committed)

## Problem
Paginated listing pages (page 2/3/4 of an archive) that set `rel=canonical`
to page 1 were flagged `TITLE_DUPLICATE` / `META_DESC_DUPLICATE` /
`TITLE_META_DUPLICATE_PAIR`. Confirmed on livingsystems.ca:
`/bowen_systems_podcast/` (self-canonical) plus `/2/` and `/3/` (both
canonical → page 1) share the title "Podcasts | Living Systems" and were
flagged as duplicates of the very page they canonical to.

## Root cause
`api/crawler/checkers/cross_page.py` grouped pages by identical title/meta and
skipped redirects but ignored `ParsedPage.canonical_url`.

## Fix
In `check_cross_page`, when building the title/meta/pair grouping maps, skip
any page whose `canonical_url` is set and normalises to a URL different from
the page's own (compared via `normalise_url`). Such pages have self-declared
as a secondary view: they are neither flagged nor listed in another page's
`duplicate_urls`. A page with `canonical_url is None` or a self-referencing
canonical stays in the grouping — `CANONICAL_MISSING` / `CANONICAL_EXTERNAL`
behaviour is unchanged.

## Tests
`tests/test_issue_checker.py::TestCanonicalRespectingDuplicates`
- `test_pagination_canonical_to_page1_not_flagged_duplicate`
- `test_real_duplicate_still_flagged_no_canonical` (adversarial)
- `test_real_duplicate_still_flagged_self_canonical` (adversarial)
- `test_canonicaling_page_not_in_others_duplicate_urls`

## Follow-up (out of scope)
Paginated pages may still receive per-page content flags (e.g. `THIN_CONTENT`).
The same canonical-respecting principle could extend there, analogous to the
R5.3 noindex scope-reduction — not changed in this pass.

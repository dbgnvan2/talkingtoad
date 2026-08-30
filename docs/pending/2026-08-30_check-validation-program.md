# Cross-validating all 170 issue codes against oracles we did not write

**Date:** 2026-08-30
**Status:** Proposed — awaiting approval
**Reported by:** user — "I fear a pattern of bugs. How can every issue you look
for be cross validated like you have done for the alt text?"

## The problem is not missing tests

Measured on this repo, today:

| | |
|---|---|
| Issue codes in `_CATALOGUE` | **170** |
| Codes referenced by at least one test | **168** |
| Codes with a must-NOT-fire assertion | **119** |
| Backend tests passing | **2,727** |

Both false-positive classes found this week shipped **through** that. Coverage is
not the discriminator, and more tests of the same kind cannot be the fix.

Here is why, from `tests/test_parser_lazy_images.py:158` — the existing test for
the alt behaviour, filed under a heading that reads `── E1.3c — adversarial (P7) ──`:

```python
def test_e1_3c_decorative_images_do_not_inflate_missing_alt(self):
    """A genuinely decorative image carries alt="" by design. It still counts
    toward img_missing_alt_count (unchanged, deliberate — ...), but this test
    pins the behaviour so a future change ... is a decision, not an accident."""
    soup = BeautifulSoup(
        '<img src="data:image/gif;base64,R0" data-src="/spacer.gif" alt="" '
        'role="presentation">', "lxml")
    assert _count_img_missing_alt(soup) == 1
```

Everything about this test's *process* was right. It is labelled adversarial. It
picks the hardest possible input — `alt=""` **and** `role="presentation"`, the
W3C's explicit "this image is decorative, ignore it". It was written
deliberately, and it says so.

And it asserts the wrong answer, then pins it.

The test did not fail to catch the bug. **The test was the bug**, made permanent
and given a name that implied it had been challenged. This is a strictly worse
failure than P27's untestable test: this one runs, can fail, and enforces a
misconception. The author of the code and the author of the test held the same
belief, so the suite agreed with itself — 2,727 times.

The ground truth was in the repo the whole time:
`tests/fixtures/lazy_images/livingsystems_home.html` is a real saved copy of the
customer's homepage containing the exact `white-logo.svg` / `bc_logo.svg` /
`city_of_nv.svg` markup with `alt=""`. We had the evidence and the wrong ruler.

**The missing discipline is an oracle independent of the implementation** — a
definition of "correct" that does not come from the same mind that wrote the
check. Everything below is a way to obtain one.

## The method that actually worked, generalised

The alt investigation succeeded by doing five things. Each generalises:

| Step | What it was for alt | General form |
|---|---|---|
| 1 | 156 issues → 15 distinct images → 4 template files (98%) | **Collapse findings to distinct entities.** A count that collapses is a template artifact, not N defects. |
| 2 | Fetched raw HTML and counted with a regex, not our parser | **Re-derive the fact with an independent implementation.** |
| 3 | WCAG 1.1.1 says `alt=""` is prescribed for decorative | **Check the finding against the published standard.** |
| 4 | Image path said "decorative, 0 findings"; page path said 156 | **Make code paths that compute the same predicate agree.** |
| 5 | The user's other tools disagreed with us | **Diff against a tool we did not write.** |

Steps 3, 4 and 5 are oracles. Steps 1 and 2 are cheap lead-generators. Both of
this week's bugs were catchable by **step 4 alone**, which is fully mechanical:
`ORPHAN_PAGE` vs `HIGH_CRAWL_DEPTH` disagreed about missing input; the alt paths
disagreed about `alt=""`.

## Proposal

### V1 — Every code names the authority it enforces, or admits it is a heuristic

Add a required `authority` field to `_IssueSpec`: a citation (WCAG clause, Google
Search Central page, RFC, schema.org type) **or** the literal `HEURISTIC:
<rationale>`. A parity test fails when a code carries impact ≥ 2 without a
citation.

This alone would have caught the alt bug at authoring time: the moment someone
must write `WCAG 2.2 §1.1.1` next to `IMG_ALT_MISSING`, they read it, and it says
`alt=""` is correct for decorative images.

It also surfaces an existing mislabel — `IMG_ALT_MISSING` is currently tagged
confidence **"Established"**, which asserts external backing for a rule we
invented. Its catalogue description ("*missing an alt attribute **or have
empty/blank alt text***") documents the defect as intended behaviour.

### V2 — Differential oracle: diff against the tools the user already owns

A `scripts/differential_audit.py` that ingests a findings export from another
tool (Screaming Frog, Sitebulb, Ahrefs, axe-core / Lighthouse for accessibility),
normalises to `(url, finding-class)`, and reports three buckets:

- **We flag, they don't** → false-positive candidates *(this is the alt bug)*
- **They flag, we don't** → coverage gaps
- **Both** → corroborated

Highest-yield item in this spec, because the oracle is one we did not write —
and it is exactly what found this bug: the user was the differential oracle.
Mapping tables live in config, not code (rule 9). One-off manual runs first; no
automation until the mapping proves stable.

### V3 — A real-artifact corpus with labels from the standard, not from us

`tests/fixtures/validation/` — real saved pages (starting with the ones already
in `tests/fixtures/lazy_images/`) plus a per-page manifest of expected findings.

**Hard rule: manifests are never generated from our crawler's output.** They are
written by a human reading the page against the cited authority. A manifest
generated from our own output would re-pin whatever we currently believe — which
is precisely how we got here. Every confirmed false positive becomes a permanent
case, the way the ORPHAN_PAGE fix drew its fixture from the real
`/training-2/` case.

### V4 — Prevalence triage, run on every crawl

Automate the report already prototyped in this investigation. Flag any code where:

- findings fire on **≥ 90 % of pages** (a site-wide template artifact, not a
  per-page defect), or
- evidence **collapses**: distinct entities × 4 ≤ issue count, or
- the code has **never fired** on any real crawl (dead check, P21 shape).

Run against job `a87e2d61` (256 pages, all analyses), it produced 7 leads from 68
firing codes in seconds — including `IMG_ALT_MISSING` (15 distinct → 156 issues).

It is a **lead generator, not a verdict**, and must be labelled as such: in the
same run it flagged `SOCIAL_PREVIEW_METADATA_MISSING` (73 issues, apparently 1
entity), which manual checking confirmed is a **correct** finding — those pages
genuinely lack `og:image`; the heuristic had misread a URL inside the title
field. A triage tool that is trusted as a verdict just relocates the problem.

### V5 — Internal-agreement audit (mechanical; catches both of this week's bugs)

Enumerate every predicate computed in more than one place and assert the
implementations agree on shared fixtures. Known duplicates today:

| Predicate | Sites | Status |
|---|---|---|
| "is this image's alt missing?" | `parser._count_img_missing_alt` vs `parser._detect_decorative` + `image_analyzer._check_alt_text` | **disagree** — this week's bug |
| "is this input incomplete?" | `ORPHAN_PAGE` vs `HIGH_CRAWL_DEPTH` | **disagreed** — fixed in `cb421cf` |
| "is this page an orphan?" | `check_cross_page` vs `find_orphaned_media` | aligned in `cb421cf` |

Ships as `tests/test_checker_agreement.py`. Cheap, needs no external oracle, and
is the highest ratio of bugs-caught to effort in this spec.

### V6 — When a false positive is found, indict the test

Add to the review checklist: on fixing any false positive, locate the test that
permitted it and record **why it passed**. Both this week's bugs had tests. If a
post-mortem does not name the test that agreed with the bug, the post-mortem is
not finished.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| V1.1 | Every code with impact ≥ 2 has an `authority` citation or an explicit `HEURISTIC:` rationale | `tests/test_architecture_constraints.py::test_v1_every_scored_code_cites_an_authority` |
| V1.2 | Confidence labels cover all codes, not only `ai_readiness` | `…::test_v1_confidence_table_covers_catalogue` |
| V3.1 | Every corpus page's findings match its manifest exactly (not a superset) | `tests/test_validation_corpus.py::test_v3_findings_match_manifest` |
| V3.2 | Manifests contain no field derived from crawler output | `…::test_v3_manifest_is_hand_labelled` |
| V4.1 | Triage flags a synthetic template artifact (one image, every page) | `tests/test_prevalence_triage.py::test_v4_flags_template_artifact` |
| V4.2 | Adversarial: a genuine per-page defect on many pages is **not** flagged | `…::test_v4_real_widespread_defect_not_flagged` |
| V5.1 | The two alt paths agree on `alt=""`, `alt` absent, `alt=" "`, `role="presentation"` | `tests/test_checker_agreement.py::test_v5_alt_paths_agree` |
| V5.2 | Every registered duplicate predicate has an agreement test | `…::test_v5_all_duplicate_predicates_covered` |

V5.1 is the one to build first — it is the smallest change that would have caught
this week's headline bug, and it fails today.

## Scope and honesty about limits

- **This does not prove the checks correct.** It replaces "we agree with
  ourselves" with "we agree with a standard, another tool, and our other code
  path". Those can all still be wrong together, and 170 codes cannot each receive
  the depth the alt investigation got.
- **Sequencing:** V5 and V4 first (mechanical, no oracle needed, immediate).
  Then V1 across the catalogue in batches, highest-impact codes first. V2 and V3
  need your input — which tools you own, and which pages belong in the corpus.
- **V2 needs a decision from you:** which tool's export should be the first
  differential oracle? The alt case suggests an accessibility checker
  (axe-core / Lighthouse) would pay back fastest.

## Adjacent findings from this investigation, not fixed

1. **`UNSAFE_CROSS_ORIGIN_LINK`** — 156 issues from 4 distinct links (the
   Elementor social icons in the template). The detection is **factually
   correct**: those links do carry `target="_blank"` with no `rel`. But all major
   browsers have implied `rel="noopener"` since 2021, so the name "UNSAFE" and
   the security category overstate a risk that no longer exists. Severity is
   `info` and impact is `0`, so it distorts no score — a **wording** correction,
   not a bug. Fold into the V1 pass, where it will fail to find an authority.
2. **`REDIRECT_TRAILING_SLASH`** — 147 issues on 57% of pages, unverified. Next
   candidate for the same treatment.
3. The catalogue count is **170**, but `CLAUDE.md` states **152**. Stale doc.

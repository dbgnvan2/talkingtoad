# Micro-spec E6: Detect stacked overlay links — several `<a>` to one destination in one card

Date: 2026-08-29
Status: **proposal — awaiting approval**
Area: `api/crawler/parser.py`, `api/crawler/issue_checker.py`, `api/crawler/checkers/registry.py`
New code: `LINK_STACKED_DUPLICATE`

## Problem

An independent audit of livingsystems.ca reported **83 links with no anchor text** and
recommended: "ensure cards expose one accessible, descriptive link rather than stacked empty
overlay links." TalkingToad reported `LINK_EMPTY_ANCHOR` on **1 page** out of 272.

TalkingToad is not wrong. `_find_empty_anchors` (`parser.py:1104`) skips any anchor with an
accessible name from **any** source — visible text, `aria-label`, `title`, `aria-labelledby`,
or a child `img[alt]` — via the shared `_accessible_name` helper. That is the correct
accessibility test, and it was a deliberate fix (audit R2.x #1) for icon-link false positives.
Semrush counts links with no *visible text*, which flags an image link that is perfectly
accessible.

So the two tools measure different things and TalkingToad measures the better one. But the
pattern the external audit actually named is real and neither code catches it: an Elementor
card that emits a full-card overlay `<a href="/x">` **plus** a title `<a href="/x">` **plus**
an image `<a href="/x">`. Every one has an accessible name, so `LINK_EMPTY_ANCHOR` stays
silent — while a screen-reader user hears the same destination three times and a crawler sees
three links where the editor intended one.

## Change

### E6.1 — Parser: collect stacked link groups

```python
def _find_stacked_links(soup, page_url: str = "") -> list[dict]:
    """Groups of 2+ <a> with the same resolved href inside one container."""
```

A group is reported when, within a single **container** — the nearest common ancestor that is
an `<li>`, `<article>`, or an element whose class list matches a card pattern — two or more
anchors resolve to the same absolute href. Recorded per group: `href`, `count`,
`accessible_names` (each anchor's computed name, so the operator can see which one to keep),
and `container_tag`/`container_class`.

Card-class patterns live in `api/config/link_patterns.json` (rule 9 — these are
builder-specific editorial strings, not logic):

```json
{
  "card_container_classes": ["card", "elementor-post", "jet-listing-grid__item",
                             "wp-block-post", "entry", "post-item", "grid-item"],
  "card_container_tags": ["li", "article"],
  "min_group_size": 2
}
```

New `ParsedPage` field: `stacked_link_groups: list | None`.

### E6.2 — Emit `LINK_STACKED_DUPLICATE`

One issue per page carrying up to 10 groups in `extra`, plus `groups_total` so a capped list
announces what it dropped (rule 6). Description names the destination and the count:
*"3 links in one card all point to /counselling/ — expose one descriptive link."*

Category `links`, severity `info`, confidence `Reasonable proxy`, effect `small`,
scoring `(2, 2)` — matching `ANCHOR_TEXT_GENERIC`, which is the closest existing sibling.
It is an accessibility and crawl-clarity nuisance, not a ranking defect, and E4's prevalence
lens is what escalates it when it is on 87 pages rather than 2.

### E6.3 — Do not double-count with `LINK_EMPTY_ANCHOR`

When a group contains an anchor that already fired `LINK_EMPTY_ANCHOR`, only
`LINK_STACKED_DUPLICATE` is emitted for that group — the stacked finding subsumes it and
names the better fix. Implemented as a suppression entry in `_CLUSTER_SUPPRESSIONS`
(`job_store_base.py:130`), consistent with how the codebase already handles overlapping
findings, so scoring is not double-charged.

### E6.4 — Record the definitional difference in the docs

`docs/issue-codes.md` gains a note under `LINK_EMPTY_ANCHOR` stating that TalkingToad tests
for an **accessible name**, not visible text, and that a third-party tool reporting a much
higher "links without anchor text" count is measuring something different rather than finding
a bug. This is the kind of discrepancy that costs an afternoon every time someone re-discovers
it.

## Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| E6.1a | Card with overlay + title + image anchors to one href → one group, `count == 3` | `tests/test_stacked_links.py::test_e6_1a_three_anchors_one_group` |
| E6.1b | Two anchors to the **same** href in **different** cards → no group | `…::test_e6_1b_separate_containers_not_grouped` |
| E6.1c | Two anchors to **different** hrefs in one card → no group | `…::test_e6_1c_different_hrefs_not_grouped` |
| E6.1d | Relative and absolute forms of one href group together | `…::test_e6_1d_href_normalised_before_grouping` |
| E6.2a | Emits `LINK_STACKED_DUPLICATE` with `accessible_names` populated | `…::test_e6_2a_issue_carries_accessible_names` |
| E6.2b | More than 10 groups → capped list plus `groups_total` | `…::test_e6_2b_group_cap_announced` |
| E6.3a | A group containing an empty anchor emits only the stacked code | `…::test_e6_3a_suppresses_empty_anchor_in_group` |
| E6.3b | An empty anchor **outside** any group still emits `LINK_EMPTY_ANCHOR` | `…::test_e6_3b_standalone_empty_anchor_unaffected` |
| E6.3c | Scoring is not double-charged for a suppressed pair | `tests/test_r4_cluster_suppression.py::test_e6_3c_stacked_suppression_scores_once` |
| E6.4a | **Adversarial (P7):** a nav menu with a logo link and a "Home" text link to `/` — two anchors, one href, but not in a card container — must NOT fire | `tests/test_stacked_links.py::test_e6_4a_header_logo_and_home_link_clean` |
| E6.4b | **Real-artifact:** the saved livingsystems homepage produces groups matching what the rendered page actually shows | `…::test_e6_4b_real_homepage_groups` |

Fix→test map (P10): **E6.4a first.** The header logo + brand-name pattern is on essentially
every site on the web; a naive implementation flags all of them and the check is worthless.
The container requirement exists solely to prevent that, and this is the test that proves it.

## Adjacent issues found, not fixed (rule 10)

- `_accessible_name` accepts `title` as an accessible name. Screen readers treat `title` as a
  weak fallback and some announce it not at all, so an anchor named only by `title` is
  arguably still a defect. Pre-existing and deliberate; flagged, not changed.
- `INTERACTIVE_NO_ACCESSIBLE_NAME` uses the same helper and inherits the same question.

## Out of scope

A WCAG conformance pass. E6 detects one specific structural pattern; the report must not imply
accessibility coverage it does not have, and E7's caveats section says so explicitly.

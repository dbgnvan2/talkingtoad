# Micro-spec — P8.2: the walk stops at the first card, not the right one

**Date:** 2026-09-04
**TODO item:** Phase 8, P8.2
**Class:** an implicit choice made by control flow rather than by a rule (the `break` in an
upward walk), whose failure mode is a finding that silently disappears (P31/P24).

---

## 1. Verified

`_find_stacked_links` (`parser.py:1614-1628`) walks each anchor's ancestors and takes the
**first** container that looks like a card:

```python
for parent in anchor.parents:
    if _is_card_container(parent, ...):
        container = parent
        break
```

Innermost wins, because `.parents` walks outward. Nothing states that as a rule; it is what
`break` does.

Measured, same two anchors to one href either side:

```
flat card (control)           [{'href': '.../a', 'count': 2, 'container_class': 'card'}]
group split by nested cards   []
```

In the second, a `card` contains two `entry-card` divs holding one anchor each. Every
anchor's walk halts at its own inner card, neither inner card holds a group, and **the
finding disappears entirely** — not misreported, absent.

**This is a known failure with a hand-maintained defence.** The comment at `parser.py:1500`
says so: *"Left unlisted, the walk halts at a card's own title block: a default WordPress
block theme reported ZERO stacked links, and the Elementor Posts widget reported each defect
twice with two different counts."* The mitigation is `non_card_classes`, an editorial list —
and the module's own docstring concedes *"class patterns are editorial strings and the next
theme will always defeat them."* So the correctness of a check currently depends on a list
someone must extend for each new theme.

## 2. Change

### 2.1 Choose by the property being detected, not by walk order

The check is *"2+ anchors to one href inside one card"*. So the container should be **the
innermost card that actually contains such a group** — not the innermost card, full stop.

Replace the per-anchor upward walk with a pass over containers:

1. collect the page's card containers (`_is_card_container`, the existing predicate and
   guards, unchanged);
2. for each, compute its same-href groups of ≥ `min_group_size`;
3. where one card is an ancestor of another and both report the same `(href, anchors)` group,
   keep the **innermost** — the outer one is reporting its descendant's finding.

Nested case: the inner cards hold one anchor each and report nothing, the outer card holds
two and reports. Flat case: unchanged. The Elementor double-report the comment describes:
the outer copy is dropped as a duplicate of the inner one, by rule rather than by list.

### 2.2 `non_card_classes` keeps its real job

It still excludes page-level wrappers (`entry-content`, `elementor-location-single`) from
being treated as cards at all, which is a different question from which of two nested cards
to report. What it stops carrying is the correctness of the group-splitting case — that
becomes structural.

### 2.3 The evidence still names the container it grouped by

Unchanged, and load-bearing: E6.1's lesson was that a reader must be able to see *what the
tool called a card* and disagree. The container reported is now the one the rule chose.

## 3. Tests

| # | Test | Goes red when |
|---|---|---|
| 3.1 | `test_a_group_split_across_nested_cards_is_still_found` | §2.1 regresses — the measured `[]` |
| 3.2 | `test_a_flat_card_is_unchanged` | the container choice moves outward for everyone |
| 3.3 | `test_the_innermost_card_holding_the_group_is_reported` | the outer card is reported instead |
| 3.4 | `test_a_nested_group_is_reported_once_not_twice` | the Elementor double-report returns |
| 3.5 | `test_two_sibling_cards_are_not_merged` | the fix over-reaches to the page |
| 3.6 | `test_it_still_works_with_non_card_classes_emptied` | correctness slides back onto the list |

**Adversarial cases:**

- **3.5 is the one that matters.** The wrong fix is "walk further out", which finds the split
  group *and* merges two sibling cards that legitimately link to the same href — the header
  logo plus "Home" case the function's own docstring says the container requirement exists to
  prevent. It asserts two separate cards each linking `/a` once produce **nothing**.
- **3.6 is the point of the item.** It empties `non_card_classes` and asserts the nested case
  still resolves correctly. Today that list is what stands between this check and a wrong
  answer; afterwards it should be an optimisation and a wrapper exclusion, not the mechanism.
  If 3.6 cannot pass, the change has not actually moved the correctness anywhere.
- **3.4** distinguishes "found" from "found once". A rule that reports every ancestor card
  satisfies 3.1 and reintroduces the measured Elementor defect.

## 4. Considered and rejected

- **Always take the outermost card.** Fails 3.5 and merges sibling cards; it is the mirror of
  today's bug rather than a fix.
- **Extend `non_card_classes` for the themes we have seen.** What the code does now, and the
  module already says why it does not hold: the next theme defeats it. It also cannot be
  tested except against the themes already known.
- **Report from every card ancestor and de-duplicate downstream.** Moves the choice to the
  consumer, and the consumers are a panel, a PDF and an Excel sheet — three chances to
  disagree, which is the P16 shape this repo keeps paying for.
- **Drop the container requirement.** Explicitly refused by the function's docstring: a header
  logo and a "Home" link point at `/` on essentially every site, and this check would flag all
  of them.

## 5. Not in scope

- The class/tag pattern lists themselves, and the S1 structural guards
  (`max_card_links`, the text-share rule). Untouched — this item is only about which of
  several qualifying containers is chosen.

## 6. Done when

- A stacked pair split across nested cards is reported, and reported once.
- Two sibling cards linking to the same href are still not merged.
- The nested case resolves correctly with `non_card_classes` emptied, so the list is no longer
  what makes the check right.

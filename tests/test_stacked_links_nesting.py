"""P8.2 — which of several nested cards a stacked-link group is reported from.

`_find_stacked_links` walked each anchor's ancestors and took the FIRST container
that looked like a card. Innermost wins, because `.parents` walks outward — and
nothing stated that as a rule; it is what `break` does.

Measured before the fix, the same two anchors to one href either side:

    flat card (control)           [{'count': 2, 'container_class': 'card'}]
    group split by nested cards   []

In the second, a `card` contains two `entry-card` divs holding one anchor each.
Every anchor's walk halts at its own inner card, neither holds a group, and the
finding disappears entirely — not misreported, absent.

The module already knew: parser.py's comment records that a default WordPress
block theme reported ZERO stacked links and the Elementor Posts widget reported
each defect twice. The defence was `non_card_classes`, an editorial list, and the
same module concedes "the next theme will always defeat them". Hence 3.6, which
empties that list: if the nested case does not resolve without it, correctness
has not moved off the list and this item is not done.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from api.crawler.parser import _find_stacked_links, _link_patterns_cfg

URL = "https://e.com/"


def _groups(html: str) -> list[dict]:
    return _find_stacked_links(BeautifulSoup(html, "lxml"), URL)


def _page(inner: str) -> str:
    return f"<html><body><main><div>{inner}</div></main></body></html>"


FLAT = _page("""
 <div class="card"><a href="/a">Title</a><a href="/a">Read more</a></div>
 <div class="card"><a href="/b">Other</a></div>
""")

NESTED = _page("""
 <div class="card">
   <div class="entry-card"><a href="/a">Title</a></div>
   <div class="entry-card"><a href="/a">Read more</a></div>
 </div>
 <div class="card"><a href="/b">Other</a></div>
""")

# Two SEPARATE cards each linking /a once. Not a stacked pair: this is the
# header-logo-plus-Home shape the container requirement exists to reject.
SIBLINGS = _page("""
 <div class="card"><a href="/a">One</a></div>
 <div class="card"><a href="/a">Two</a></div>
""")

# A stacked pair inside an inner card, itself inside an outer card. The group is
# genuinely the inner card's; the outer must not report it a second time.
INNER_HOLDS_THE_GROUP = _page("""
 <div class="card">
   <div class="entry-card"><a href="/a">Title</a><a href="/a">Read more</a></div>
   <div class="entry-card"><a href="/c">Elsewhere</a></div>
 </div>
""")


class TestNestedCards:
    def test_a_flat_card_is_unchanged(self):
        """3.2 — the control. The container choice must not move outward for
        everyone just to fix the nested case."""
        g = _groups(FLAT)
        assert len(g) == 1
        assert g[0]["count"] == 2
        assert g[0]["container_class"] == "card"

    def test_a_group_split_across_nested_cards_is_still_found(self):
        """3.1 — the measured `[]`."""
        g = _groups(NESTED)
        assert len(g) == 1, f"the split group was lost or duplicated: {g}"
        assert g[0]["count"] == 2
        assert sorted(g[0]["accessible_names"]) == ["Read more", "Title"]

    def test_the_innermost_card_holding_the_group_is_reported(self):
        """3.3 — the rule is "the innermost card that CONTAINS the group", so
        where an inner card does hold it, that is what the reader is shown.

        E6.1's lesson was that a reader must be able to see what the tool called
        a card and disagree with it; naming the outer wrapper when the defect is
        in one item of a listing makes that impossible.
        """
        g = _groups(INNER_HOLDS_THE_GROUP)
        assert len(g) == 1, g
        assert g[0]["container_class"] == "entry-card", (
            f"reported the outer wrapper instead of the card holding the pair: {g}"
        )

    def test_a_nested_group_is_reported_once_not_twice(self):
        """3.4 — "found" is not "found once".

        A rule that reports from every qualifying ancestor satisfies 3.1 and
        reintroduces the measured Elementor defect: each stacked pair reported
        twice, with two different counts.
        """
        for label, html in (("nested", NESTED), ("inner-holds", INNER_HOLDS_THE_GROUP)):
            hrefs = [g["href"] for g in _groups(html)]
            assert len(hrefs) == len(set(hrefs)), f"{label}: {hrefs} reported twice"

    def test_two_sibling_cards_are_not_merged(self):
        """3.5 — the over-reach guard, and the one that matters.

        The wrong fix is "walk further out": it finds the split group AND merges
        two sibling cards that legitimately link to the same href. A header logo
        plus a "Home" link point at "/" on essentially every site on the web,
        which is why the container requirement exists at all.
        """
        assert _groups(SIBLINGS) == [], (
            "two separate cards linking to one href were merged into a stacked pair"
        )

    def test_it_still_works_with_non_card_classes_emptied(self):
        """3.6 — the point of the item.

        `non_card_classes` is an editorial list, and parser.py's own docstring
        says the next theme will always defeat it. Today it is what stands
        between this check and a wrong answer on nested markup. Afterwards it
        should be a wrapper exclusion and an optimisation — so the nested case
        must resolve with it empty. If this cannot pass, correctness has not
        moved anywhere.
        """
        cfg = dict(_link_patterns_cfg())
        cfg["non_card_classes"] = []
        with patch("api.crawler.parser._link_patterns_cfg", return_value=cfg):
            g = _groups(NESTED)
            assert len(g) == 1 and g[0]["count"] == 2, (
                f"with non_card_classes emptied the nested group was lost: {g}"
            )
            assert _groups(SIBLINGS) == [], "siblings merged once the list was emptied"


class TestTheGuardsAreUntouched:
    def test_a_page_wrapper_is_still_not_a_card(self):
        """3.7 — `non_card_classes`'s real job survives.

        Excluding card INNER elements is a different question from choosing
        between two nested cards, and this item must not quietly drop it.

        Uses `elementor-post__title`, which genuinely matches the
        `elementor-post` card pattern on a token boundary and is excluded only
        by name. My first version used `entry-content`, which matches no card
        pattern in the first place — so deleting the whole exclusion left that
        test green, and it was pinning nothing. Found by mutation.
        """
        html = _page("""
         <div class="elementor-post">
           <div class="elementor-post__title">
             <a href="/a">One</a><a href="/a">Two</a>
           </div>
         </div>
        """)
        g = _groups(html)
        assert len(g) == 1, g
        assert g[0]["container_class"] == "elementor-post", (
            f"the card's own title block was treated as the card: {g}"
        )

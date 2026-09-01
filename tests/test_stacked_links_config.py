"""E6 config guard — no card pattern may match a standard WordPress wrapper.

Purpose: the 2026-09-01 defect was not a logic error, it was a config entry.
         `"entry"` was added to `card_container_classes` and, under the
         substring matching of the day, it matched WordPress's `hentry` — so
         `<main>` became a "card" and the check degenerated into "any URL
         linked twice anywhere on the page".
Spec:    docs/pending/2026-09-01_stacked-links-container-overmatch.md#S2
Tests:   this file

The logic fix stops today's pattern. THIS file is what stops the next one: it
fails the moment someone adds a pattern that swallows a wrapper class every
WordPress page carries, which is the only durable defence for a list of
editorial strings that people will keep appending to.
"""

from __future__ import annotations

import pytest

from api.config import load_config
from api.crawler.parser import _STACKED_CFG_KEYS, _class_matches_pattern

# Standard `post_class()` / theme output present on essentially every
# WordPress page. None of these is a card.
WORDPRESS_WRAPPER_CLASSES = [
    "hentry",
    "entry-content",
    "entry-header",
    "entry-title",
    "site-main",
    "site-content",
    "post-350",
    "page",
    "type-page",
    "status-publish",
    "elementor-location-single",
    "elementor-posts",
    "wp-site-blocks",
]


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config("link_patterns", required_keys=_STACKED_CFG_KEYS)


class TestNoPatternSwallowsAWordPressWrapper:
    @pytest.mark.parametrize("wrapper", WORDPRESS_WRAPPER_CLASSES)
    def test_no_card_pattern_matches(self, cfg, wrapper):
        matched = [
            p for p in cfg["card_container_classes"]
            if _class_matches_pattern(wrapper, p.casefold())
        ]
        # `entry-content` / `entry-header` legitimately start with `entry-`, so
        # the denylist is what excludes them. Either defence is acceptable;
        # having neither is not.
        if matched:
            denied = [
                d for d in cfg["non_card_classes"]
                if _class_matches_pattern(wrapper, d.casefold())
            ]
            assert denied, (
                f'"{wrapper}" is matched by card pattern(s) {matched} and is not '
                f"in non_card_classes. Every WordPress page carries it, so this "
                f"turns the whole page into a card."
            )


class TestConfigIsUsable:
    def test_every_required_key_present(self, cfg):
        for key in _STACKED_CFG_KEYS:
            assert key in cfg

    def test_numeric_bounds_are_sane(self, cfg):
        assert cfg["min_group_size"] >= 2, "a 'group' of one is not a group"
        assert cfg["max_card_links"] >= cfg["min_group_size"]
        assert 0 < cfg["max_card_text_fraction"] <= 1
        assert cfg["min_page_text_for_fraction"] > 0

    def test_patterns_are_lowercase(self, cfg):
        """Matching casefolds the CLASS; a capitalised pattern silently never
        matches, which reads as 'this builder is supported' and is not."""
        for key in ("card_container_classes", "card_container_tags", "non_card_classes"):
            for p in cfg[key]:
                assert p == p.casefold(), f"{key}: {p!r} must be lowercase"

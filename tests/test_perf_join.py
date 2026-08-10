"""CLN4 — shared performance-ledger join key.

`match_key` must fold www / scheme / trailing-slash so a GSC or bundle URL joins
to the crawled page it belongs to, and it must be the SINGLE definition used by
both the /api/gsc and /api/performance ingest paths.

Spec: docs/pending/2026-08-08_debt-cleanup-batch.md#CLN4
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.services.perf_join import build_crawled_key_map, match_key


def test_match_key_folds_www_scheme_and_trailing_slash():
    k = match_key("https://example.org/a")
    assert match_key("https://www.example.org/a") == k      # www folded
    assert match_key("http://example.org/a") == k           # scheme folded
    assert match_key("https://example.org/a/") == k         # trailing slash
    assert match_key("https://EXAMPLE.org/a") == k          # host case


def test_match_key_keeps_real_distinctions():
    assert match_key("https://example.org/a") != match_key("https://example.org/b")
    # a non-www subdomain is a genuinely different host, not folded
    assert match_key("https://donate.example.org/a") != match_key("https://example.org/a")


def test_match_key_raises_on_schemeless_url():
    with pytest.raises(ValueError):
        match_key("not-a-url")


def test_build_crawled_key_map_skips_unnormalisable():
    pages = [SimpleNamespace(url="https://example.org/a"), SimpleNamespace(url="bad")]
    m = build_crawled_key_map(pages)
    assert m == {match_key("https://example.org/a"): "https://example.org/a"}


def test_cln4_3_match_key_is_a_single_shared_definition():
    """Both ingest routers must reference the one perf_join.match_key — no
    per-router copy (the F4 drift that let GSC key rows differently)."""
    import api.routers.gsc as gsc
    import api.routers.performance as perf

    assert perf.match_key is match_key
    assert gsc.match_key is match_key

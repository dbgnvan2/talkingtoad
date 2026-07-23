"""G.4 — the 5 P1 codes serialize cleanly for the results endpoint.

The results API JSON-encodes each issue (code, page_url, severity,
confidence_label, extra). This guards against a non-JSON type (e.g. a set)
leaking into an ``extra`` payload — the members list, name variants, and
name→urls map must all round-trip.
"""

import dataclasses as dc
import json

from api.crawler.parser import ParsedPage
from api.crawler.checkers.cross_page import check_cross_page
import api.crawler.checkers.cross_page as cp


def _pp(url, *, schema_blocks=None, first_1500_words=None):
    return ParsedPage(
        url=url, final_url=url, status_code=200, response_size_bytes=1000,
        title="Title", meta_description="A sufficiently long meta description text.",
        og_title=None, og_description=None, og_image=None, twitter_card=None,
        canonical_url=None, h1_tags=["H1"], headings_outline=[{"level": 1, "text": "H1"}],
        is_indexable=True, robots_directive=None, links=[], has_favicon=None,
        has_viewport_meta=True, schema_types=[], external_script_count=0,
        external_stylesheet_count=0, schema_blocks=schema_blocks,
        first_1500_words=first_1500_words,
    )


def test_p1_codes_serialized(monkeypatch):
    monkeypatch.setattr(cp, "_SHINGLE_SIZE", 3)
    monkeypatch.setattr(cp, "_MIN_WORDS_FOR_DUP", 5)
    monkeypatch.setattr(cp, "_MIN_PAGES_SITE_CHECKS", 3)

    footer = "home about contact privacy terms copyright newsletter signup follow social "
    dup = ("our grief counselling service supports you through loss with weekly sessions led by a "
           "registered clinical counsellor in a safe confidential space where you can process "
           "difficult emotions and rebuild meaning after bereavement over time with care")

    def art(name, url):
        return {"@type": "BlogPosting", "author": {"@type": "Person", "name": name, "url": url}}

    pages = [
        # Two org names → ENTITY_NAME_INCONSISTENT; missing sameAs → ENTITY_SAMEAS_MISSING;
        # conflicting author URLs → AUTHOR_IDENTITY_INCONSISTENT.
        _pp("https://x.org/a",
            schema_blocks=[{"@type": "Organization", "name": "Acme Society"}, art("Jane Doe", "https://x.org/u/jane")],
            first_1500_words=footer + dup + " vancouver " + footer),
        _pp("https://x.org/b",
            schema_blocks=[{"@type": "Organization", "name": "Beta Foundation"}, art("Jane Doe", "https://x.org/u/j-doe")],
            first_1500_words=footer + dup + " burnaby " + footer),
        # Thin page → BOILERPLATE_RATIO_HIGH.
        _pp("https://x.org/c",
            schema_blocks=[{"@type": "Organization", "name": "Acme Society"}],
            first_1500_words="welcome " + footer * 3),
    ]

    issues = check_cross_page(pages)
    codes = {i.code for i in issues}
    for expected in ("ENTITY_NAME_INCONSISTENT", "ENTITY_SAMEAS_MISSING",
                     "AUTHOR_IDENTITY_INCONSISTENT", "NEAR_DUPLICATE_BODY",
                     "BOILERPLATE_RATIO_HIGH"):
        assert expected in codes, f"{expected} not emitted; got {sorted(codes)}"

    # Every new issue must JSON-serialize (proves extra carries only JSON types).
    for i in issues:
        if i.code.startswith(("ENTITY_", "AUTHOR_IDENTITY", "NEAR_DUP", "BOILERPLATE")):
            payload = {
                "code": i.code, "page_url": i.page_url, "severity": i.severity,
                "confidence_label": i.confidence_label, "extra": i.extra,
            }
            json.dumps(payload)  # raises TypeError if a set/other non-JSON leaked
            assert i.confidence_label in ("Reasonable proxy", "Heuristic")

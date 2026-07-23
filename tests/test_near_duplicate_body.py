"""E2 — Body near-duplicate + boilerplate checks (cross-page).

Spec: docs/pending/2026-07-22_p1-entity-consistency-near-duplicate.md
Codes: NEAR_DUPLICATE_BODY (site), BOILERPLATE_RATIO_HIGH (page)

Adversarial guard FIRST (test_e2_2…): pages that share only nav/footer
boilerplate must NOT be flagged as near-duplicates — boilerplate is stripped
before the body comparison.
"""

import pytest

from api.crawler.parser import ParsedPage
from api.crawler.checkers.cross_page import check_cross_page
import api.crawler.checkers.cross_page as cp


FOOTER = ("home about services contact privacy policy terms of use copyright "
          "all rights reserved follow us on social media newsletter signup ")
NAV = "home services team blog contact donate volunteer events resources "


def _pp(url, first_1500_words):
    return ParsedPage(
        url=url, final_url=url, status_code=200, response_size_bytes=1000,
        title="Title", meta_description="A sufficiently long meta description text.",
        og_title=None, og_description=None, og_image=None, twitter_card=None,
        canonical_url=None, h1_tags=["H1"], headings_outline=[{"level": 1, "text": "H1"}],
        is_indexable=True, robots_directive=None, links=[], has_favicon=None,
        has_viewport_meta=True, schema_types=[], external_script_count=0,
        external_stylesheet_count=0, first_1500_words=first_1500_words,
        schema_blocks=None,
    )


def _codes(issues):
    return [i.code for i in issues]


@pytest.fixture(autouse=True)
def _small_shingles(monkeypatch):
    # Short test fixtures: use 3-word shingles and a low min-word gate so the
    # sets are meaningful without 150-word fixtures.
    monkeypatch.setattr(cp, "_SHINGLE_SIZE", 3)
    monkeypatch.setattr(cp, "_MIN_WORDS_FOR_DUP", 5)
    monkeypatch.setattr(cp, "_MIN_PAGES_SITE_CHECKS", 3)


# ── Adversarial guard FIRST (P7 / P10) ─────────────────────────────────────
class TestBoilerplateExcludedFromNearDup:
    def test_e2_2_boilerplate_excluded(self):
        """Four genuinely-distinct pages that share the SAME nav+footer must not
        fire NEAR_DUPLICATE_BODY — the shared template is stripped before compare."""
        uniq = [
            "grief counselling helps you process loss with a trained therapist over several sessions",
            "anxiety therapy teaches practical tools to calm a racing mind and regain daily control",
            "couples counselling rebuilds communication trust and connection between two partners",
            "youth mental health support for teenagers navigating school stress and identity questions",
        ]
        pages = [_pp(f"https://x.org/{i}", NAV + u + " " + FOOTER) for i, u in enumerate(uniq)]
        assert "NEAR_DUPLICATE_BODY" not in _codes(check_cross_page(pages))


class TestNearDuplicateBody:
    def test_e2_1_body_shingle(self):
        """Two pages whose lead content is near-identical ⇒ one clustered
        NEAR_DUPLICATE_BODY naming both members (third distinct page not flagged).

        Realistic doorway-page pattern: same body, one differing location word."""
        dup = ("our grief counselling service supports you through loss with weekly sessions "
               "led by a registered clinical counsellor in a safe confidential space where you "
               "can talk openly process difficult emotions and rebuild a sense of meaning after "
               "bereavement at a pace that feels right for you and your family over time")
        pages = [
            _pp("https://x.org/loc-vancouver", NAV + dup + " vancouver " + FOOTER),
            _pp("https://x.org/loc-burnaby", NAV + dup + " burnaby " + FOOTER),
            _pp("https://x.org/anxiety",
                NAV + "anxiety therapy uses evidence based cognitive behavioural tools to manage "
                "worry panic and intrusive thoughts through structured exposure and practical "
                "coping strategies tailored to each person unique situation and goals " + FOOTER),
        ]
        issues = [i for i in check_cross_page(pages) if i.code == "NEAR_DUPLICATE_BODY"]
        assert len(issues) == 1, "one issue per cluster, not per pair/page"
        members = set(issues[0].extra.get("members") or [])
        assert members == {"https://x.org/loc-vancouver", "https://x.org/loc-burnaby"}

    def test_e2_3_config_threshold(self, monkeypatch):
        """Threshold is config-driven: a strict threshold that the pair no longer
        clears flips the result off."""
        dup = ("our grief counselling service supports you through loss with weekly sessions "
               "led by a registered clinical counsellor in a safe confidential space")
        pages = [
            _pp("https://x.org/a", NAV + dup + " alpha content here " + FOOTER),
            _pp("https://x.org/b", NAV + dup + " beta different tail words here now " + FOOTER),
            _pp("https://x.org/c", NAV + "wholly different subject about tax filing deadlines " + FOOTER),
        ]
        monkeypatch.setattr(cp, "_NEAR_DUP_JACCARD", 0.999)
        assert "NEAR_DUPLICATE_BODY" not in _codes(check_cross_page(pages))
        monkeypatch.setattr(cp, "_NEAR_DUP_JACCARD", 0.50)
        assert "NEAR_DUPLICATE_BODY" in _codes(check_cross_page(pages))


class TestBoilerplateRatio:
    def test_e2_4_boilerplate_ratio(self, monkeypatch):
        """A page that is almost entirely shared template fires
        BOILERPLATE_RATIO_HIGH; content-rich pages with the same footer do not."""
        # Each rich page has DISTINCT substantial content; all four share the
        # same footer. Footer becomes boilerplate; the thin page is almost all
        # footer, the rich pages are mostly unique content.
        rich1 = ("first hand research into local food security surveyed forty households across "
                 "three neighbourhoods documenting barriers to fresh produce and proposing a "
                 "community garden pilot with measurable outcomes over the coming year here")
        rich2 = ("our counsellors describe evidence based approaches to adolescent anxiety drawing "
                 "on cognitive behavioural therapy mindfulness and family systems work with case "
                 "examples that illustrate progress across a typical twelve week treatment plan")
        rich3 = ("a detailed history of the society founding in nineteen seventy two traces the "
                 "volunteers original mission the early funding struggles and the milestones that "
                 "shaped decades of counselling services offered to the wider regional community")
        pages = [
            _pp("https://x.org/rich1", rich1 + " " + FOOTER),
            _pp("https://x.org/rich2", rich2 + " " + FOOTER),
            _pp("https://x.org/rich3", rich3 + " " + FOOTER),
            _pp("https://x.org/thin", "welcome " + FOOTER),   # almost all footer
        ]
        monkeypatch.setattr(cp, "_BOILERPLATE_RATIO", 0.60)
        issues = check_cross_page(pages)
        flagged = {i.page_url for i in issues if i.code == "BOILERPLATE_RATIO_HIGH"}
        assert "https://x.org/thin" in flagged
        assert not (flagged & {"https://x.org/rich1", "https://x.org/rich2", "https://x.org/rich3"})


class TestClusterMonotonicity:
    def test_large_identical_cluster_still_flagged(self):
        """Regression (learning-qa finding): N identical pages must produce ONE
        NEAR_DUPLICATE_BODY cluster of all N. Earlier boilerplate-subtraction
        erased a cluster's shared content once it appeared on >=3 pages, hiding
        exactly the most blatant duplication (anti-monotonic bug)."""
        body = ("our grief counselling service supports you through loss with weekly sessions led "
                "by a registered clinical counsellor in a safe confidential space where you can "
                "process difficult emotions and rebuild a sense of meaning after bereavement here")
        pages = [_pp(f"https://x.org/dup{i}", NAV + body + " " + FOOTER) for i in range(5)]
        pages.append(_pp("https://x.org/distinct",
                         NAV + "tax clinic volunteers help low income families file returns each "
                         "spring with free confidential appointments booked online in advance " + FOOTER))
        issues = [i for i in check_cross_page(pages) if i.code == "NEAR_DUPLICATE_BODY"]
        assert len(issues) == 1
        members = set(issues[0].extra.get("members") or [])
        assert members == {f"https://x.org/dup{i}" for i in range(5)}


class TestScale:
    def test_e2_5_scale(self, monkeypatch):
        """Real-scale: 26 pages (25 distinct + 1 duplicate of #0) completes and
        finds exactly the planted duplicate — exercises the pairwise path (P9)."""
        pages = []
        for i in range(25):
            body = (NAV + f"unique page number {i} about distinct subject {i} with its own "
                    f"vocabulary term{i} and specific detail sentence {i} here " + FOOTER)
            pages.append(_pp(f"https://x.org/p{i}", body))
        # Plant a near-duplicate of page 0.
        dup0 = pages[0].first_1500_words + " nearly identical tail"
        pages.append(_pp("https://x.org/dup0", dup0))
        issues = [i for i in check_cross_page(pages) if i.code == "NEAR_DUPLICATE_BODY"]
        assert len(issues) == 1
        members = set(issues[0].extra.get("members") or [])
        assert members == {"https://x.org/p0", "https://x.org/dup0"}

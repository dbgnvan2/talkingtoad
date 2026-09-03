"""Tests for M3.1 SCHEMA_VISIBLE_MISMATCH — JSON-LD values vs visible text.

Spec: docs/pending/2026-05-31_m3_1_schema_visible_mismatch.md
"""

import pytest
from api.services.schema_typing import check_schema_visible_mismatch
from api.crawler.parser import ParsedPage
from api.crawler.issue_checker import check_page, make_issue


def _fields(result):
    """Extract the field labels from the list[dict] mismatch result."""
    return [item["field"] for item in result]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_page(url="https://example.com/page", *, schema_blocks=None,
               schema_visible_mismatch_fields=None, schema_types=None,
               **kw):
    """Construct a minimal ParsedPage for testing."""
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=200,
        response_size_bytes=5000,
        title="Test Page",
        meta_description="A test page",
        og_title="Test Page",
        og_description="A test page",
        og_image="https://example.com/img.jpg",
        twitter_card="summary",
        canonical_url=url,
        h1_tags=["Test Page"],
        headings_outline=[{"level": 1, "text": "Test Page"}],
        is_indexable=True,
        robots_directive=None,
        links=[],
        has_favicon=None,
        has_viewport_meta=True,
        schema_types=schema_types or [],
        schema_blocks=schema_blocks,
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=500,
        lang_attr="en",
        schema_visible_mismatch_fields=schema_visible_mismatch_fields,
        **kw,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests — the check_schema_visible_mismatch helper
# ═══════════════════════════════════════════════════════════════════════════


class TestVisibleValueNotFlagged:
    """Values that appear in visible text should NOT be flagged."""

    def test_article_headline_visible(self):
        blocks = [{"@type": "Article", "headline": "Grief Counselling Services"}]
        visible = "Welcome to our Grief Counselling Services page."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_product_name_visible(self):
        blocks = [{"@type": "Product", "name": "Wellness Toolkit"}]
        visible = "Order the Wellness Toolkit today."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_person_name_visible(self):
        blocks = [{"@type": "Person", "name": "Dr. Jane Smith"}]
        visible = "Meet Dr. Jane Smith, our lead therapist."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_organization_name_visible(self):
        blocks = [{"@type": "Organization", "name": "Living Systems"}]
        visible = "About Living Systems Counselling Society"
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_faq_question_and_answer_visible(self):
        blocks = [{
            "@type": "FAQPage",
            "mainEntity": [{
                "name": "What is grief counselling?",
                "acceptedAnswer": {"text": "Grief counselling helps people process loss."},
            }],
        }]
        visible = "What is grief counselling? Grief counselling helps people process loss."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []


class TestAbsentValueFlagged:
    """Values NOT in visible text should be flagged with the correct label."""

    def test_article_headline_absent(self):
        blocks = [{"@type": "Article", "headline": "SEO Tips for Nonprofits"}]
        visible = "Welcome to our charity website. We offer many services."
        result = check_schema_visible_mismatch(blocks, visible)
        assert "Article.headline" in _fields(result)

    def test_article_headline_captures_value(self):
        """The mismatch record carries the exact schema value, not just the label."""
        blocks = [{"@type": "Article", "headline": "SEO Tips for Nonprofits"}]
        visible = "Welcome to our charity website. We offer many services."
        result = check_schema_visible_mismatch(blocks, visible)
        assert {"field": "Article.headline",
                "value": "SEO Tips for Nonprofits"} in result

    def test_product_name_absent(self):
        blocks = [{"@type": "Product", "name": "Premium SEO Package"}]
        visible = "We provide great services for your organisation."
        result = check_schema_visible_mismatch(blocks, visible)
        assert "Product.name" in _fields(result)

    def test_person_name_absent(self):
        blocks = [{"@type": "Person", "name": "Dr. John Doe"}]
        visible = "Our team of experts is here to help you."
        result = check_schema_visible_mismatch(blocks, visible)
        assert "Person.name" in _fields(result)

    def test_organization_name_absent(self):
        blocks = [{"@type": "Organization", "name": "Invisible Corp"}]
        visible = "Welcome to our website about counselling."
        result = check_schema_visible_mismatch(blocks, visible)
        assert "Organization.name" in _fields(result)

    def test_faq_partial_mismatch(self):
        """One FAQ answer visible, another not — only the missing one is listed."""
        blocks = [{
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "name": "What is therapy?",
                    "acceptedAnswer": {"text": "Therapy is a treatment process."},
                },
                {
                    "name": "How much does it cost?",
                    "acceptedAnswer": {"text": "Sessions start at $150."},
                },
            ],
        }]
        visible = "What is therapy? Therapy is a treatment process. Contact us for pricing."
        result = check_schema_visible_mismatch(blocks, visible)
        fields = _fields(result)
        assert "FAQPage.mainEntity[0].name" not in fields
        assert "FAQPage.mainEntity[0].acceptedAnswer.text" not in fields
        assert "FAQPage.mainEntity[1].name" in fields
        assert "FAQPage.mainEntity[1].acceptedAnswer.text" in fields
        # The captured value is the actual missing question/answer text.
        assert {"field": "FAQPage.mainEntity[1].name",
                "value": "How much does it cost?"} in result
        assert {"field": "FAQPage.mainEntity[1].acceptedAnswer.text",
                "value": "Sessions start at $150."} in result

    def test_localbusiness_address_absent(self):
        blocks = [{
            "@type": "LocalBusiness",
            "name": "Test Clinic",
            "address": {
                "streetAddress": "123 Main St",
                "addressLocality": "Vancouver",
                "addressRegion": "BC",
                "postalCode": "V5K 1A1",
            },
        }]
        visible = "Test Clinic is a great place. Come visit us!"
        result = check_schema_visible_mismatch(blocks, visible)
        fields = _fields(result)
        assert "LocalBusiness.address" in fields
        assert "LocalBusiness.name" not in fields  # name IS visible
        # The captured value is the assembled address string.
        assert {"field": "LocalBusiness.address",
                "value": "123 Main St Vancouver BC V5K 1A1"} in result

    def test_graph_nested_organization(self):
        """Organization nested inside @graph should also be checked."""
        blocks = [
            {"@type": "WebSite", "name": "My Site"},
            {"@type": "Organization", "name": "Secret Org Name"},
        ]
        visible = "Welcome to My Site. We do good things."
        result = check_schema_visible_mismatch(blocks, visible)
        assert "Organization.name" in _fields(result)


class TestValueTruncation:
    """Long schema values are truncated to 120 chars with a trailing ellipsis."""

    def test_long_value_truncated(self):
        long_answer = "A" * 200
        blocks = [{
            "@type": "FAQPage",
            "mainEntity": [{
                "name": "Long question?",
                "acceptedAnswer": {"text": long_answer},
            }],
        }]
        visible = "Nothing relevant on this page."
        result = check_schema_visible_mismatch(blocks, visible)
        rec = next(r for r in result
                   if r["field"] == "FAQPage.mainEntity[0].acceptedAnswer.text")
        assert rec["value"] == "A" * 120 + "…"
        assert len(rec["value"]) == 121  # 120 chars + the ellipsis

    def test_short_value_not_truncated(self):
        blocks = [{"@type": "Article", "headline": "Short Headline"}]
        result = check_schema_visible_mismatch(blocks, "Unrelated content.")
        assert result[0]["value"] == "Short Headline"
        assert "…" not in result[0]["value"]


class TestAdversarialNormalization:
    """Whitespace/case differences should NOT cause false flags."""

    def test_whitespace_case_normalization(self):
        """Schema 'Grief  Counselling' vs visible 'grief counselling' → NOT flagged."""
        blocks = [{"@type": "Article", "headline": "Grief  Counselling"}]
        visible = "our grief counselling services are available"
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_leading_trailing_whitespace(self):
        blocks = [{"@type": "Article", "headline": "  Therapy Services  "}]
        visible = "We offer Therapy Services for all ages."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_mixed_case_with_extra_spaces(self):
        blocks = [{"@type": "Person", "name": "DR.  JANE   SMITH"}]
        visible = "Meet dr. jane smith, our lead therapist."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []


class TestHtmlEntitiesInTheSchemaValue:
    """SV1 (2026-09-03) — the two sides came through different decoders.

    Owner report on livingsystems.ca/emotional-process-on-vacation: *"schema says
    'Emotions don&#8217;t take a vacation' — not on the page."* It is on the page.

    Visible text comes from `soup.get_text()`, so entities are already decoded.
    The schema value comes from inside `<script type="application/ld+json">`, and
    script content is RAW TEXT — an HTML parser does not decode entities there.
    Yoast writes `&#8217;`, so the parsed JSON string literally contains it, and
    the substring test fails on text that is identical to a reader.

    Every one of the 98 `Article.headline` findings in the development database
    carried an entity — a 100% false-positive rate on an impact-6 check that
    cites Google.

    Spec: docs/functional-specification.md §4.6 (SV1-SV2, folded 2026-09-03)
    """

    # Captured verbatim from the live page, not written to suit the normaliser
    # (P32 — the existing fixtures all pass because they use one encoding).
    REAL_HEADLINE = "Emotions don&#8217;t take a vacation"
    REAL_VISIBLE = (
        "Skip to content Emotions don\u2019t take a vacation "
        "Family systems do not pause for the summer."
    )

    def test_the_reported_page_is_not_flagged(self):
        blocks = [{"@type": "Article", "headline": self.REAL_HEADLINE}]
        assert check_schema_visible_mismatch(blocks, self.REAL_VISIBLE) == []

    @pytest.mark.parametrize("entity,char", [
        ("&#8217;", "\u2019"),   # right single quote — the reported case
        ("&#038;", "&"),         # ampersand, as Yoast writes it
        ("&#8211;", "\u2013"),   # en dash
        ("&amp;", "&"),          # named forms
        ("&rsquo;", "\u2019"),
        ("&ndash;", "\u2013"),
        ("&#x2019;", "\u2019"),  # hex numeric
    ])
    def test_every_entity_seen_in_the_field(self, entity, char):
        blocks = [{"@type": "Article", "headline": f"Bowen Theory {entity} Relationships"}]
        visible = f"Article: Bowen Theory {char} Relationships, a discussion."
        assert check_schema_visible_mismatch(blocks, visible) == []

    def test_entities_on_the_visible_side_too(self):
        """Both sides normalise the same way, so an entity in either is fine."""
        blocks = [{"@type": "Article", "headline": "Fathers &amp; Sons"}]
        assert check_schema_visible_mismatch(blocks, "About Fathers &#038; Sons here") == []

    # ── The point of the check has to survive (adversarial) ─────────────────

    def test_a_genuinely_absent_headline_is_still_flagged(self):
        """Decoding must not become 'match anything'. This is the true positive
        the check exists for, and it must fail before AND after the change."""
        blocks = [{"@type": "Article", "headline": "Emotions don&#8217;t take a vacation"}]
        visible = "An entirely different page about tax clinic opening hours."
        assert _fields(check_schema_visible_mismatch(blocks, visible)) == ["Article.headline"]

    def test_decoding_does_not_match_a_different_word(self):
        """`&#038;` decodes to '&', not to the word 'and' — the check must not
        start passing on a paraphrase."""
        blocks = [{"@type": "Article", "headline": "Fathers &#038; Sons"}]
        visible = "A page about Fathers and Sons."
        assert _fields(check_schema_visible_mismatch(blocks, visible)) == ["Article.headline"]

    def test_a_partial_overlap_is_still_a_mismatch(self):
        blocks = [{"@type": "Article", "headline": "Emotions don&#8217;t take a holiday"}]
        visible = "Emotions don\u2019t take a vacation."
        assert _fields(check_schema_visible_mismatch(blocks, visible)) == ["Article.headline"]


class TestTheReportedValueIsReadable:
    """SV2 — the report printed `Emotions don&#8217;t take a vacation`. Even on a
    true positive that is markup leaking into a client report, and the operator
    cannot match it against what they see in the WordPress editor."""

    def test_the_stored_value_is_decoded(self):
        blocks = [{"@type": "Article", "headline": "Grief &amp; Loss &#8211; A Guide"}]
        result = check_schema_visible_mismatch(blocks, "A page about something else.")
        assert result, "the adversarial value should still be flagged"
        value = result[0]["value"]
        assert value == "Grief & Loss \u2013 A Guide", value
        assert "&" in value and "&amp;" not in value and "&#" not in value

    def test_truncation_counts_decoded_characters(self):
        """The 120-char cap must not be spent on `&#8217;`. Eight entities cost
        56 raw characters and 8 real ones."""
        from api.services.schema_typing import _MISMATCH_VALUE_MAX_CHARS

        headline = "A" * 115 + "&#8217;" * 8          # 115 real + 8 real = 123 decoded
        blocks = [{"@type": "Article", "headline": headline}]
        result = check_schema_visible_mismatch(blocks, "unrelated visible text")
        value = result[0]["value"]
        assert "&#" not in value, f"raw entity survived truncation: {value!r}"
        assert len(value) == _MISMATCH_VALUE_MAX_CHARS + 1, len(value)  # + the ellipsis
        assert value.endswith("\u2026")


class TestEmptyMissingFields:
    """Empty or missing field values should NOT be flagged (absence ≠ mismatch)."""

    def test_empty_headline(self):
        blocks = [{"@type": "Article", "headline": ""}]
        visible = "Some page content here."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_whitespace_only_headline(self):
        blocks = [{"@type": "Article", "headline": "   "}]
        visible = "Some page content here."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_missing_headline_key(self):
        blocks = [{"@type": "Article", "author": "Someone"}]
        visible = "Some page content here."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_none_headline(self):
        blocks = [{"@type": "Article", "headline": None}]
        visible = "Some page content here."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []


class TestMalformedInput:
    """Malformed JSON-LD should not crash — graceful handling."""

    def test_non_dict_block(self):
        """A list or string instead of a dict block → no crash."""
        blocks = ["not a dict", 42, None]
        visible = "Some page content."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_empty_blocks(self):
        result = check_schema_visible_mismatch([], "Some text")
        assert result == []

    def test_empty_visible_text(self):
        blocks = [{"@type": "Article", "headline": "Test"}]
        result = check_schema_visible_mismatch(blocks, "")
        assert result == []

    def test_type_as_list(self):
        """@type can be a list — should still work."""
        blocks = [{"@type": ["Article", "BlogPosting"], "headline": "My Post"}]
        visible = "Read My Post about gardening."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_type_as_list_with_mismatch(self):
        blocks = [{"@type": ["Article", "BlogPosting"], "headline": "Invisible Headline"}]
        visible = "This page has different content."
        result = check_schema_visible_mismatch(blocks, visible)
        # Article.headline should appear (only once, not duplicated)
        assert "Article.headline" in _fields(result)

    def test_faq_main_entity_not_list(self):
        """mainEntity as a non-list → no crash."""
        blocks = [{"@type": "FAQPage", "mainEntity": "not a list"}]
        visible = "Some content."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_faq_accepted_answer_not_dict(self):
        """acceptedAnswer as a string instead of dict → no crash."""
        blocks = [{
            "@type": "FAQPage",
            "mainEntity": [{"name": "Question?", "acceptedAnswer": "just a string"}],
        }]
        visible = "Question? And answer."
        result = check_schema_visible_mismatch(blocks, visible)
        # name is visible, acceptedAnswer is not a dict so it's skipped
        assert result == []


class TestLocalBusinessAddress:
    """Address assembly and comparison edge cases."""

    def test_address_as_string(self):
        blocks = [{
            "@type": "LocalBusiness",
            "address": "123 Main St, Vancouver, BC",
        }]
        visible = "Visit us at 123 Main St, Vancouver, BC."
        result = check_schema_visible_mismatch(blocks, visible)
        assert "LocalBusiness.address" not in _fields(result)

    def test_address_as_string_missing(self):
        blocks = [{
            "@type": "LocalBusiness",
            "address": "789 Oak Drive, Toronto, ON",
        }]
        visible = "We are located somewhere nice."
        result = check_schema_visible_mismatch(blocks, visible)
        assert "LocalBusiness.address" in _fields(result)

    def test_address_empty_string(self):
        blocks = [{"@type": "LocalBusiness", "address": ""}]
        visible = "Some content."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []

    def test_address_missing_key(self):
        blocks = [{"@type": "LocalBusiness", "name": "My Clinic"}]
        visible = "My Clinic is great."
        result = check_schema_visible_mismatch(blocks, visible)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# Integration — issue_checker emits SCHEMA_VISIBLE_MISMATCH
# ═══════════════════════════════════════════════════════════════════════════


class TestIssueCheckerIntegration:
    """check_page should emit SCHEMA_VISIBLE_MISMATCH when mismatch fields present."""

    def test_emits_when_mismatched(self):
        page = _make_page(
            schema_visible_mismatch_fields=[
                {"field": "Article.headline", "value": "SEO Tips for Nonprofits"}
            ],
            schema_types=["Article"],
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "SCHEMA_VISIBLE_MISMATCH" in codes
        mismatch_issue = next(i for i in issues if i.code == "SCHEMA_VISIBLE_MISMATCH")
        assert mismatch_issue.extra["mismatched_fields"] == [
            {"field": "Article.headline", "value": "SEO Tips for Nonprofits"}
        ]

    def test_emitted_extra_is_list_of_field_value_dicts(self):
        """The emitted issue's extra.mismatched_fields is a list of {field, value}."""
        page = _make_page(
            schema_visible_mismatch_fields=[
                {"field": "Article.headline", "value": "Hidden Headline"},
                {"field": "Person.name", "value": "Dr. Jane Doe"},
            ],
            schema_types=["Article", "Person"],
        )
        issues = check_page(page)
        mismatch_issue = next(i for i in issues if i.code == "SCHEMA_VISIBLE_MISMATCH")
        fields = mismatch_issue.extra["mismatched_fields"]
        assert isinstance(fields, list) and len(fields) == 2
        for item in fields:
            assert set(item.keys()) == {"field", "value"}
            assert isinstance(item["field"], str) and isinstance(item["value"], str)

    def test_not_emitted_when_empty_list(self):
        """Empty list means all values are visible — no issue."""
        page = _make_page(
            schema_visible_mismatch_fields=[],
            schema_types=["Article"],
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "SCHEMA_VISIBLE_MISMATCH" not in codes

    def test_not_emitted_when_none(self):
        """None means no JSON-LD or not computed — no issue."""
        page = _make_page(
            schema_visible_mismatch_fields=None,
            schema_types=[],
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "SCHEMA_VISIBLE_MISMATCH" not in codes

    def test_issue_has_correct_category_and_severity(self):
        page = _make_page(
            schema_visible_mismatch_fields=[
                {"field": "Product.name", "value": "Premium Package"}
            ],
            schema_types=["Product"],
        )
        issues = check_page(page)
        mismatch_issue = next(i for i in issues if i.code == "SCHEMA_VISIBLE_MISMATCH")
        assert mismatch_issue.category == "ai_readiness"
        assert mismatch_issue.severity == "warning"

    def test_issue_has_confidence_label(self):
        page = _make_page(
            schema_visible_mismatch_fields=[
                {"field": "Person.name", "value": "Dr. Jane Smith"}
            ],
            schema_types=["Person"],
        )
        issues = check_page(page)
        mismatch_issue = next(i for i in issues if i.code == "SCHEMA_VISIBLE_MISMATCH")
        assert mismatch_issue.confidence_label == "Established"

    def test_multiple_mismatched_fields(self):
        page = _make_page(
            schema_visible_mismatch_fields=[
                {"field": "Article.headline", "value": "Hidden Headline"},
                {"field": "FAQPage.mainEntity[0].name", "value": "A question?"},
            ],
            schema_types=["Article", "FAQPage"],
        )
        issues = check_page(page)
        mismatch_issue = next(i for i in issues if i.code == "SCHEMA_VISIBLE_MISMATCH")
        assert len(mismatch_issue.extra["mismatched_fields"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Registration parity sanity check
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistration:
    """SCHEMA_VISIBLE_MISMATCH must be in all three registries."""

    def test_in_scoring(self):
        from api.crawler.checkers.registry import _ISSUE_SCORING
        assert "SCHEMA_VISIBLE_MISMATCH" in _ISSUE_SCORING
        assert _ISSUE_SCORING["SCHEMA_VISIBLE_MISMATCH"] == (6, 2)  # R3: Established/moderate

    def test_in_catalogue(self):
        from api.crawler.checkers.registry import _CATALOGUE
        assert "SCHEMA_VISIBLE_MISMATCH" in _CATALOGUE
        spec = _CATALOGUE["SCHEMA_VISIBLE_MISMATCH"]
        assert spec.category == "ai_readiness"
        assert spec.severity == "warning"

    def test_in_confidence(self):
        from api.crawler.checkers.registry import _AI_READINESS_CONFIDENCE
        assert "SCHEMA_VISIBLE_MISMATCH" in _AI_READINESS_CONFIDENCE
        assert _AI_READINESS_CONFIDENCE["SCHEMA_VISIBLE_MISMATCH"] == "Established"

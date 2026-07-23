"""Golden-site ground truth — the SINGLE source of the planted issues.

Both the automated test (tests/test_golden_site.py) and the human-readable
report (tests/golden_site/report.py) import from here, so the report you can
read and the test that gates CI check the exact same list.
"""

# Present everywhere as artifacts of local http hosting — NOT bugs, not asserted:
#   HTTP_PAGE            — the fixture is served over http://
#   WRONG_PLACEHOLDER_LINK — internal links resolve to 127.0.0.1, which the app
#     (correctly, for a real site) treats as a localhost/wrong-domain placeholder.
ENV_ARTIFACTS = {"HTTP_PAGE", "WRONG_PLACEHOLDER_LINK"}

# page path -> codes that MUST be present (the page's reason for existing).
EXPECT = {
    "/": {"FAVICON_MISSING", "SCHEMA_ORG_MISSING", "LLMS_TXT_MISSING", "AI_TXT_MISSING",
          "AI_BOT_TRAINING_DISALLOWED", "CONTACT_INFO_NOT_IN_HTML", "ENTITY_NAME_INCONSISTENT"},
    "/title-missing.html": {"TITLE_MISSING"},
    "/title-short.html": {"TITLE_TOO_SHORT"},
    "/title-long.html": {"TITLE_TOO_LONG"},
    "/meta-missing.html": {"META_DESC_MISSING"},
    "/meta-short.html": {"META_DESC_TOO_SHORT"},
    "/meta-long.html": {"META_DESC_TOO_LONG"},
    "/lang-missing.html": {"LANG_MISSING"},
    "/social-missing.html": {"SOCIAL_PREVIEW_METADATA_MISSING"},
    "/headings-none.html": {"H1_MISSING"},
    "/headings-multi.html": {"H1_MULTIPLE"},
    "/headings-skip.html": {"HEADING_SKIP"},
    "/headings-empty.html": {"HEADING_EMPTY", "CONVERSATIONAL_H2_MISSING"},
    "/links-bad.html": {"ANCHOR_TEXT_GENERIC", "LINK_EMPTY_ANCHOR"},
    "/thin.html": {"THIN_CONTENT", "CONTENT_THIN"},
    "/noindex-meta.html": {"NOINDEX_META"},
    "/noindex-header.html": {"NOINDEX_HEADER"},
    "/no-viewport.html": {"MISSING_VIEWPORT_META"},
    "/orphan.html": {"ORPHAN_PAGE"},
    "/semantic-bad.html": {"NON_SEMANTIC_BUTTON", "LANDMARK_MAIN_MISSING",
                           "INTERACTIVE_NO_ACCESSIBLE_NAME"},
    "/article-noauthor.html": {"AUTHOR_BYLINE_MISSING", "DATE_PUBLISHED_MISSING",
                               "DATE_MODIFIED_MISSING"},
    "/article-bare-author.html": {"AUTHOR_CREDENTIALS_MISSING", "CONTENT_DATE_STALE_VISIBLE"},
    "/howto-incomplete.html": {"HOWTO_SCHEMA_INCOMPLETE"},
    "/product-norating.html": {"PRODUCT_REVIEW_SCHEMA_MISSING", "SCHEMA_VISIBLE_MISMATCH"},
    "/jsonld-invalid.html": {"JSON_LD_INVALID"},
    "/faq-noschema.html": {"FAQ_SCHEMA_MISSING"},
    "/dup-a.html": {"TITLE_DUPLICATE", "META_DESC_DUPLICATE"},
    "/dup-b.html": {"TITLE_DUPLICATE", "META_DESC_DUPLICATE"},
    # NEAR_DUPLICATE_BODY is site-scoped — emitted once on the cluster
    # representative (sorted-first member = neardup-a.html), not on both.
    "/neardup-a.html": {"NEAR_DUPLICATE_BODY"},
    "/entity-b.html": {"ENTITY_SAMEAS_MISSING"},
    "/URL_Uppercase.html": {"URL_UPPERCASE", "URL_HAS_UNDERSCORES"},
    "/has_underscores.html": {"URL_HAS_UNDERSCORES"},
    "/chain-a": {"REDIRECT_CHAIN", "INTERNAL_REDIRECT_301"},
    "/redirect-302": {"REDIRECT_302"},
    "/loop-a": {"REDIRECT_LOOP"},
    "/secret-area": {"LOGIN_REDIRECT"},
}

# page path -> codes that must be ABSENT (targeted false-positive guards).
FORBID = {
    "/article-bare-author.html": {"AUTHOR_BYLINE_MISSING"},  # byline IS present
    "/entity-a.html": {"ENTITY_SAMEAS_MISSING"},             # sameAs IS present
}

# Floor for total distinct codes exercised — guards against a whole category
# silently going dark (observed ~58).
MIN_DISTINCT_CODES = 55

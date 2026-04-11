"""
Tests for api/crawler/normaliser.py

Covers all URL normalisation rules from spec §2.7 and admin path skipping from §2.9.
"""

import pytest
from api.crawler.normaliser import (
    normalise_url,
    is_same_domain,
    is_admin_path,
    is_wp_noise_path,
    QueryVariantTracker,
    QUERY_VARIANT_CAP,
)


class TestNormaliseUrl:
    def test_trailing_slash_stripped(self):
        assert normalise_url("https://example.com/about/") == "https://example.com/about"

    def test_trailing_slash_on_root_kept(self):
        # Root path "/" should not be stripped to empty string
        result = normalise_url("https://example.com/")
        assert result in ("https://example.com/", "https://example.com")

    def test_fragment_removed(self):
        assert normalise_url("https://example.com/page#section") == "https://example.com/page"

    def test_fragment_removed_with_query(self):
        result = normalise_url("https://example.com/page?foo=bar#anchor")
        assert "#" not in result
        assert "foo=bar" in result

    def test_scheme_lowercased(self):
        assert normalise_url("HTTPS://example.com/page") == "https://example.com/page"

    def test_host_lowercased(self):
        assert normalise_url("https://EXAMPLE.COM/page") == "https://example.com/page"

    def test_utm_source_stripped(self):
        result = normalise_url("https://example.com/page?utm_source=google")
        assert "utm_source" not in result

    def test_utm_medium_stripped(self):
        result = normalise_url("https://example.com/page?utm_medium=cpc")
        assert "utm_medium" not in result

    def test_utm_campaign_stripped(self):
        result = normalise_url("https://example.com/page?utm_campaign=summer")
        assert "utm_campaign" not in result

    def test_utm_term_stripped(self):
        result = normalise_url("https://example.com/page?utm_term=seo")
        assert "utm_term" not in result

    def test_utm_content_stripped(self):
        result = normalise_url("https://example.com/page?utm_content=banner")
        assert "utm_content" not in result

    def test_ref_stripped(self):
        result = normalise_url("https://example.com/page?ref=homepage")
        assert "ref" not in result

    def test_session_id_stripped(self):
        result = normalise_url("https://example.com/page?session_id=abc123")
        assert "session_id" not in result

    def test_sid_stripped(self):
        result = normalise_url("https://example.com/page?sid=abc")
        assert "sid" not in result

    def test_fbclid_stripped(self):
        result = normalise_url("https://example.com/page?fbclid=xyz")
        assert "fbclid" not in result

    def test_gclid_stripped(self):
        result = normalise_url("https://example.com/page?gclid=xyz")
        assert "gclid" not in result

    def test_non_tracking_param_preserved(self):
        result = normalise_url("https://example.com/page?page=2")
        assert "page=2" in result

    def test_multiple_non_tracking_params_preserved(self):
        result = normalise_url("https://example.com/search?q=dogs&sort=date")
        assert "q=dogs" in result
        assert "sort=date" in result

    def test_mixed_params_tracking_stripped_others_kept(self):
        result = normalise_url("https://example.com/page?utm_source=google&page=3")
        assert "utm_source" not in result
        assert "page=3" in result

    def test_invalid_url_raises_value_error(self):
        with pytest.raises(ValueError):
            normalise_url("not-a-url")

    def test_url_without_scheme_raises_value_error(self):
        with pytest.raises(ValueError):
            normalise_url("example.com/page")


class TestIsSameDomain:
    def test_identical_domain_is_same(self):
        assert is_same_domain("https://example.com/page", "https://example.com/") is True

    def test_www_prefix_is_same_domain(self):
        assert is_same_domain("https://www.example.com/page", "https://example.com/") is True

    def test_www_prefix_reversed_is_same_domain(self):
        assert is_same_domain("https://example.com/page", "https://www.example.com/") is True

    def test_different_subdomain_is_external(self):
        assert is_same_domain("https://blog.example.com/page", "https://example.com/") is False

    def test_completely_different_domain_is_external(self):
        assert is_same_domain("https://other.org/page", "https://example.com/") is False

    def test_http_and_https_same_domain(self):
        assert is_same_domain("http://example.com/page", "https://example.com/") is True

    def test_both_www_same_domain(self):
        assert is_same_domain("https://www.example.com/a", "https://www.example.com/b") is True


class TestIsAdminPath:
    def test_wp_admin_prefix_skipped(self):
        assert is_admin_path("https://example.com/wp-admin/edit.php") is True

    def test_wp_admin_root_skipped(self):
        assert is_admin_path("https://example.com/wp-admin/") is True

    def test_wp_login_skipped(self):
        assert is_admin_path("https://example.com/wp-login.php") is True

    def test_admin_prefix_skipped(self):
        assert is_admin_path("https://example.com/admin/users") is True

    def test_login_path_skipped(self):
        assert is_admin_path("https://example.com/login") is True

    def test_logout_path_skipped(self):
        assert is_admin_path("https://example.com/logout") is True

    def test_signin_path_skipped(self):
        assert is_admin_path("https://example.com/signin") is True

    def test_signout_path_skipped(self):
        assert is_admin_path("https://example.com/signout") is True

    def test_user_login_path_skipped(self):
        assert is_admin_path("https://example.com/user/login") is True

    def test_user_logout_path_skipped(self):
        assert is_admin_path("https://example.com/user/logout") is True

    def test_normal_page_not_skipped(self):
        assert is_admin_path("https://example.com/about") is False

    def test_page_with_admin_in_name_not_skipped(self):
        # /administration/ is not in the skip list
        assert is_admin_path("https://example.com/administration/") is False


class TestQueryVariantTracker:
    def test_first_variant_allowed(self):
        tracker = QueryVariantTracker()
        assert tracker.record("https://example.com/news?page=1") is True

    def test_different_variants_allowed_under_cap(self):
        tracker = QueryVariantTracker(cap=50)
        for i in range(50):
            assert tracker.record(f"https://example.com/news?page={i}") is True

    def test_variant_over_cap_rejected(self):
        tracker = QueryVariantTracker(cap=3)
        tracker.record("https://example.com/news?page=1")
        tracker.record("https://example.com/news?page=2")
        tracker.record("https://example.com/news?page=3")
        assert tracker.record("https://example.com/news?page=4") is False

    def test_same_query_string_not_double_counted(self):
        tracker = QueryVariantTracker(cap=2)
        tracker.record("https://example.com/news?page=1")
        tracker.record("https://example.com/news?page=2")
        # Exact duplicate — should not count against cap
        assert tracker.record("https://example.com/news?page=1") is True

    def test_no_query_string_always_allowed(self):
        tracker = QueryVariantTracker(cap=0)
        assert tracker.record("https://example.com/news") is True

    def test_different_paths_have_separate_caps(self):
        tracker = QueryVariantTracker(cap=1)
        tracker.record("https://example.com/news?page=1")
        tracker.record("https://example.com/events?page=1")
        # First path is capped, second path should still be at cap
        assert tracker.record("https://example.com/news?page=2") is False
        assert tracker.record("https://example.com/events?page=2") is False

    def test_variant_count_reported(self):
        tracker = QueryVariantTracker()
        tracker.record("https://example.com/news?page=1")
        tracker.record("https://example.com/news?page=2")
        assert tracker.variant_count("/news") == 2

    def test_default_cap_is_spec_value(self):
        assert QUERY_VARIANT_CAP == 50


class TestIsWpNoisePath:
    # ── Taxonomy archives ──────────────────────────────────────────────────
    def test_author_archive_skipped(self):
        assert is_wp_noise_path("https://example.com/author/dave/") is True

    def test_category_archive_skipped(self):
        assert is_wp_noise_path("https://example.com/category/counselling/") is True

    def test_tag_archive_skipped(self):
        assert is_wp_noise_path("https://example.com/tag/anxiety/") is True

    def test_query_style_author_skipped(self):
        assert is_wp_noise_path("https://example.com/?author=1") is True

    def test_query_author_non_numeric_not_skipped(self):
        assert is_wp_noise_path("https://example.com/?author=dave") is False

    # ── Date archives ──────────────────────────────────────────────────────
    def test_year_archive_skipped(self):
        assert is_wp_noise_path("https://example.com/2024/") is True

    def test_month_archive_skipped(self):
        assert is_wp_noise_path("https://example.com/2024/03/") is True

    def test_day_archive_skipped(self):
        assert is_wp_noise_path("https://example.com/2024/03/15/") is True

    def test_blog_post_with_date_prefix_not_skipped(self):
        # A post slug after the date should NOT be skipped
        assert is_wp_noise_path("https://example.com/2024/03/15/my-post/") is False

    # ── Pagination ─────────────────────────────────────────────────────────
    def test_paginated_archive_skipped(self):
        assert is_wp_noise_path("https://example.com/blog/page/2/") is True

    def test_paginated_category_skipped(self):
        assert is_wp_noise_path("https://example.com/category/news/page/3/") is True

    # ── Feeds ──────────────────────────────────────────────────────────────
    def test_feed_path_skipped(self):
        assert is_wp_noise_path("https://example.com/feed/") is True

    def test_post_feed_suffix_skipped(self):
        assert is_wp_noise_path("https://example.com/blog/my-post/feed/") is True

    def test_query_feed_skipped(self):
        assert is_wp_noise_path("https://example.com/?feed=rss2") is True

    # ── Search results ─────────────────────────────────────────────────────
    def test_search_results_skipped(self):
        assert is_wp_noise_path("https://example.com/?s=anxiety+counselling") is True

    def test_empty_search_skipped(self):
        assert is_wp_noise_path("https://example.com/?s=") is True

    # ── Real pages — must NOT be skipped ──────────────────────────────────
    def test_normal_page_not_skipped(self):
        assert is_wp_noise_path("https://example.com/about/") is False

    def test_blog_post_not_skipped(self):
        assert is_wp_noise_path("https://example.com/blog/my-post/") is False

    def test_page_with_author_in_slug_not_skipped(self):
        assert is_wp_noise_path("https://example.com/about/our-authors/") is False

    def test_homepage_not_skipped(self):
        assert is_wp_noise_path("https://example.com/") is False

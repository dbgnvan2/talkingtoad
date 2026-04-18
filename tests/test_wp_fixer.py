"""
Unit tests for WordPress fix generation and application (api/services/wp_fixer.py).

Tests cover:
- change_heading_text(): heading replacement in post content, inline HTML,
  HTML entities, whitespace normalization, attribute preservation, XSS escaping,
  post-title-as-H1 path, and error cases.
- find_post_by_url(): exact slug match, single-slug fallback, search fallback,
  relative URL rejection, and error handling.
- find_attachment_by_url(): slug-based lookup, size-suffix stripping,
  search fallback, directory+basename matching, and no-match case.

All WordPress REST API calls are mocked via AsyncMock on the WPClient instance.
"""

from __future__ import annotations

import html as html_module
import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.wp_fixer import (
    change_heading_text,
    find_attachment_by_url,
    find_post_by_url,
)


# ---------------------------------------------------------------------------
# Helpers for building mock WP API responses
# ---------------------------------------------------------------------------

def _mock_response(status_code: int = 200, json_data=None):
    """Create a mock httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


def _make_wp_client(site_url: str = "https://example.org") -> MagicMock:
    """Return a mock WPClient with .get and .patch as AsyncMock."""
    wp = MagicMock()
    wp.site_url = site_url
    wp.get = AsyncMock()
    wp.patch = AsyncMock()
    return wp


# ===================================================================
# find_post_by_url
# ===================================================================

class TestFindPostByUrl:

    async def test_exact_url_match_page(self):
        """Exact URL match in the pages endpoint returns the post."""
        wp = _make_wp_client("https://example.org")
        wp.get.return_value = _mock_response(200, [
            {"id": 42, "link": "https://example.org/about/"},
        ])

        result = await find_post_by_url(wp, "https://example.org/about/")

        assert result == {"id": 42, "type": "page"}
        # Should have called the pages endpoint with slug=about
        first_call_arg = wp.get.call_args_list[0][0][0]
        assert "pages?" in first_call_arg
        assert "slug=about" in first_call_arg

    async def test_exact_url_match_strips_trailing_slash(self):
        """Trailing slashes are normalized for comparison."""
        wp = _make_wp_client("https://example.org")
        wp.get.return_value = _mock_response(200, [
            {"id": 10, "link": "https://example.org/services"},
        ])

        result = await find_post_by_url(wp, "https://example.org/services/")
        assert result == {"id": 10, "type": "page"}

    async def test_single_slug_fallback(self):
        """When one result is returned but link doesn't match exactly, trust it."""
        wp = _make_wp_client("https://example.org")
        # WP returns one result whose link differs (parent path mismatch)
        wp.get.return_value = _mock_response(200, [
            {"id": 99, "link": "https://example.org/old-parent/contact/"},
        ])

        result = await find_post_by_url(wp, "https://example.org/new-parent/contact/")
        assert result == {"id": 99, "type": "page"}

    async def test_multiple_slugs_no_exact_match_returns_none_then_tries_posts(self):
        """When multiple results are returned but none match, fall through to posts."""
        wp = _make_wp_client("https://example.org")

        # Pages returns 2 items — neither matches exactly → skip
        pages_resp = _mock_response(200, [
            {"id": 1, "link": "https://example.org/a/contact/"},
            {"id": 2, "link": "https://example.org/b/contact/"},
        ])
        # Posts returns exact match
        posts_resp = _mock_response(200, [
            {"id": 77, "link": "https://example.org/blog/contact/"},
        ])
        # Search should not be needed
        wp.get.side_effect = [pages_resp, posts_resp]

        result = await find_post_by_url(wp, "https://example.org/blog/contact/")
        assert result == {"id": 77, "type": "post"}

    async def test_search_fallback(self):
        """When slug queries fail, fall back to the search API."""
        wp = _make_wp_client("https://example.org")

        # Pages and posts return empty
        empty = _mock_response(200, [])
        search_resp = _mock_response(200, [
            {"id": 55, "url": "https://example.org/team/", "subtype": "page"},
        ])
        wp.get.side_effect = [empty, empty, search_resp]

        result = await find_post_by_url(wp, "https://example.org/team/")
        assert result == {"id": 55, "type": "page"}

    async def test_returns_none_for_relative_url(self):
        """Relative URLs (no scheme) are rejected immediately."""
        wp = _make_wp_client()
        result = await find_post_by_url(wp, "/about")
        assert result is None
        wp.get.assert_not_called()

    async def test_returns_none_for_empty_url(self):
        wp = _make_wp_client()
        result = await find_post_by_url(wp, "")
        assert result is None

    async def test_homepage_uses_slash_slug(self):
        """Homepage (path = '') uses slug '/' for lookup."""
        wp = _make_wp_client("https://example.org")
        wp.get.return_value = _mock_response(200, [
            {"id": 1, "link": "https://example.org/"},
        ])

        result = await find_post_by_url(wp, "https://example.org/")
        assert result == {"id": 1, "type": "page"}
        # slug should be "/" for homepage
        first_call_arg = wp.get.call_args_list[0][0][0]
        assert "slug=/" in first_call_arg

    async def test_api_error_continues_to_next_type(self):
        """Non-200 from pages endpoint → tries posts endpoint."""
        wp = _make_wp_client("https://example.org")
        error_resp = _mock_response(500)
        ok_resp = _mock_response(200, [
            {"id": 8, "link": "https://example.org/news/"},
        ])
        wp.get.side_effect = [error_resp, ok_resp]

        result = await find_post_by_url(wp, "https://example.org/news/")
        assert result == {"id": 8, "type": "post"}

    async def test_exception_in_get_continues(self):
        """Exception during .get() is caught and function continues."""
        wp = _make_wp_client("https://example.org")
        # pages raises, posts returns empty, search returns empty
        wp.get.side_effect = [
            Exception("network error"),
            _mock_response(200, []),
            _mock_response(200, []),
        ]

        result = await find_post_by_url(wp, "https://example.org/broken/")
        assert result is None

    async def test_returns_none_when_nothing_found(self):
        """All queries fail → returns None."""
        wp = _make_wp_client("https://example.org")
        empty = _mock_response(200, [])
        wp.get.return_value = empty

        result = await find_post_by_url(wp, "https://example.org/nonexistent/")
        assert result is None


# ===================================================================
# change_heading_text
# ===================================================================

class TestChangeHeadingText:

    # -- Helpers --

    def _setup_wp_for_content(
        self, wp, post_content: str, post_title: str = "Page Title"
    ):
        """Configure mock wp so find_post_by_url succeeds and content is returned."""
        # find_post_by_url calls wp.get with pages?slug=...
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        # change_heading_text then fetches content
        content_resp = _mock_response(200, {
            "content": {"raw": post_content},
            "title": {"raw": post_title},
        })
        # patch to save updated content
        patch_resp = _mock_response(200, {})

        wp.get.side_effect = [find_resp, content_resp]
        wp.patch.return_value = patch_resp

    async def test_simple_h1_replacement(self):
        """Replace simple H1 text."""
        wp = _make_wp_client("https://example.org")
        self._setup_wp_for_content(wp, '<h1>Old Heading</h1><p>Body text.</p>')

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Old Heading", "New Heading"
        )

        assert result["success"] is True
        assert result["changed"] == 1
        # Verify the PATCH payload contains the new heading
        patch_call = wp.patch.call_args
        updated = patch_call.kwargs.get("json", {}).get("content", "")
        assert "<h1>New Heading</h1>" in updated
        assert "Old Heading" not in updated

    async def test_inline_html_tags_in_heading(self):
        """H1 with <strong>/<em> tags is matched by stripping tags for comparison."""
        wp = _make_wp_client("https://example.org")
        html_content = '<h1><strong>Bold</strong> &amp; <em>Italic</em></h1><p>text</p>'
        self._setup_wp_for_content(wp, html_content)

        # The crawler sees the heading as "Bold & Italic" (tags stripped, entities decoded)
        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Bold & Italic", "New Title"
        )

        assert result["success"] is True
        assert result["changed"] == 1
        updated = wp.patch.call_args.kwargs["json"]["content"]
        assert "New Title" in updated

    async def test_html_entities_in_old_text(self):
        """HTML entities like &amp; in the content match decoded old_text."""
        wp = _make_wp_client("https://example.org")
        html_content = '<h1>Tom &amp; Jerry</h1>'
        self._setup_wp_for_content(wp, html_content)

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Tom & Jerry", "Updated Title"
        )

        assert result["success"] is True
        assert result["changed"] == 1

    async def test_whitespace_normalization(self):
        """Extra whitespace in heading is normalized for matching."""
        wp = _make_wp_client("https://example.org")
        html_content = '<h1>  Lots   of    spaces  </h1>'
        self._setup_wp_for_content(wp, html_content)

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Lots of spaces", "Clean Title"
        )

        assert result["success"] is True
        assert result["changed"] == 1

    async def test_preserves_h1_attributes(self):
        """H1 tag attributes (class, id) are preserved after replacement."""
        wp = _make_wp_client("https://example.org")
        html_content = '<h1 class="entry-title" id="main">Old Title</h1>'
        self._setup_wp_for_content(wp, html_content)

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Old Title", "New Title"
        )

        assert result["success"] is True
        updated = wp.patch.call_args.kwargs["json"]["content"]
        assert 'class="entry-title"' in updated
        assert 'id="main"' in updated
        assert "New Title" in updated

    async def test_heading_not_found_returns_error(self):
        """Return error when the old heading text is not in the content."""
        wp = _make_wp_client("https://example.org")
        self._setup_wp_for_content(wp, '<h1>Actual Heading</h1>')

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Nonexistent Heading", "New"
        )

        assert result["success"] is False
        assert result["changed"] == 0
        assert "not found" in result["error"].lower()

    async def test_new_text_is_html_escaped_xss(self):
        """New heading text is HTML-escaped to prevent XSS injection."""
        wp = _make_wp_client("https://example.org")
        self._setup_wp_for_content(wp, '<h1>Original</h1>')

        xss_payload = '<script>alert("xss")</script>'
        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Original", xss_payload
        )

        assert result["success"] is True
        updated = wp.patch.call_args.kwargs["json"]["content"]
        # The script tags must be escaped, not raw HTML
        assert "<script>" not in updated
        assert html_module.escape(xss_payload) in updated

    async def test_new_text_escapes_ampersand(self):
        """Ampersands in new text are escaped to &amp;."""
        wp = _make_wp_client("https://example.org")
        self._setup_wp_for_content(wp, '<h1>Old</h1>')

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Old", "Tom & Jerry"
        )

        assert result["success"] is True
        updated = wp.patch.call_args.kwargs["json"]["content"]
        assert "Tom &amp; Jerry" in updated

    async def test_empty_new_text_rejected(self):
        """Empty or whitespace-only new text returns an error immediately."""
        wp = _make_wp_client("https://example.org")

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Old", "   "
        )

        assert result["success"] is False
        assert "empty" in result["error"].lower()
        wp.get.assert_not_called()

    async def test_post_not_found_returns_error(self):
        """When the URL doesn't resolve to a WP post, return error."""
        wp = _make_wp_client("https://example.org")
        empty = _mock_response(200, [])
        wp.get.return_value = empty

        result = await change_heading_text(
            wp, "https://example.org/nonexistent/", "Old", "New"
        )

        assert result["success"] is False
        assert "could not find" in result["error"].lower()

    async def test_h1_matches_post_title_updates_title_field(self):
        """When the H1 text matches the post title, update the title field instead."""
        wp = _make_wp_client("https://example.org")
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        content_resp = _mock_response(200, {
            "content": {"raw": "<p>Body only, no H1 in content.</p>"},
            "title": {"raw": "Theme-Rendered H1"},
        })
        patch_resp = _mock_response(200, {})

        wp.get.side_effect = [find_resp, content_resp]
        wp.patch.return_value = patch_resp

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Theme-Rendered H1", "Updated Title"
        )

        assert result["success"] is True
        assert result["changed"] == 1
        assert result["location"] == "post_title"
        # Verify PATCH sent the title, not content
        patch_call = wp.patch.call_args
        assert patch_call.kwargs["json"] == {"title": "Updated Title"}

    async def test_post_title_match_with_html_entities(self):
        """Post title with HTML entities matches decoded old_text."""
        wp = _make_wp_client("https://example.org")
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        content_resp = _mock_response(200, {
            "content": {"raw": "<p>Body</p>"},
            "title": {"raw": "Tom &amp; Jerry"},
        })
        patch_resp = _mock_response(200, {})

        wp.get.side_effect = [find_resp, content_resp]
        wp.patch.return_value = patch_resp

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Tom & Jerry", "Updated"
        )

        assert result["success"] is True
        assert result["location"] == "post_title"

    async def test_content_fetch_http_error(self):
        """Non-200 status when fetching content returns error."""
        wp = _make_wp_client("https://example.org")
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        error_resp = _mock_response(403, {"message": "Forbidden"})
        wp.get.side_effect = [find_resp, error_resp]

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Old", "New"
        )

        assert result["success"] is False
        assert "Forbidden" in result["error"]

    async def test_patch_failure_returns_error(self):
        """When the PATCH to save content fails, return error."""
        wp = _make_wp_client("https://example.org")
        self._setup_wp_for_content(wp, '<h1>Old</h1>')
        # Override the patch to return an error
        wp.patch.return_value = _mock_response(500, {"message": "Internal Server Error"})

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Old", "New"
        )

        assert result["success"] is False
        assert "Internal Server Error" in result["error"]

    async def test_h2_replacement_with_level_parameter(self):
        """Passing level=2 targets H2 headings, not H1."""
        wp = _make_wp_client("https://example.org")
        html_content = '<h1>Keep This</h1><h2>Replace This</h2>'
        self._setup_wp_for_content(wp, html_content, post_title="Keep This")
        # Override: post title doesn't match "Replace This", so it goes to content replacement
        # Actually, _norm(post_title) != _norm(old_text) since "Keep This" != "Replace This"

        # Re-setup because the title is "Keep This" which won't match
        wp_2 = _make_wp_client("https://example.org")
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        content_resp = _mock_response(200, {
            "content": {"raw": '<h1>Keep This</h1><h2>Replace This</h2>'},
            "title": {"raw": "Keep This"},
        })
        patch_resp = _mock_response(200, {})
        wp_2.get.side_effect = [find_resp, content_resp]
        wp_2.patch.return_value = patch_resp

        result = await change_heading_text(
            wp_2, "https://example.org/test-page/", "Replace This", "New H2", level=2
        )

        assert result["success"] is True
        assert result["changed"] == 1
        updated = wp_2.patch.call_args.kwargs["json"]["content"]
        assert "<h2>New H2</h2>" in updated
        # H1 should be untouched
        assert "<h1>Keep This</h1>" in updated

    async def test_crawler_strips_tags_whitespace_collapse(self):
        """Crawler sees 'Reactivity& Relationships' from '<strong>Reactivity</strong> &amp; Relationships'."""
        wp = _make_wp_client("https://example.org")
        html_content = '<h1><strong>Reactivity</strong> &amp; Relationships</h1>'
        self._setup_wp_for_content(wp, html_content)

        # The crawler collapses whitespace around tag boundaries, so the old_text
        # may be "Reactivity& Relationships" (no space before &)
        result = await change_heading_text(
            wp, "https://example.org/test-page/",
            "Reactivity& Relationships", "New Heading"
        )

        assert result["success"] is True
        assert result["changed"] == 1

    async def test_content_fetch_exception(self):
        """Exception during content fetch returns structured error."""
        wp = _make_wp_client("https://example.org")
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        wp.get.side_effect = [find_resp, Exception("Connection reset")]

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Old", "New"
        )

        assert result["success"] is False
        assert "Connection reset" in result["error"]

    async def test_patch_exception_returns_error(self):
        """Exception during the PATCH call returns structured error."""
        wp = _make_wp_client("https://example.org")
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        content_resp = _mock_response(200, {
            "content": {"raw": "<h1>Old</h1>"},
            "title": {"raw": "Different Title"},
        })
        wp.get.side_effect = [find_resp, content_resp]
        wp.patch.side_effect = Exception("Timeout")

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "Old", "New"
        )

        assert result["success"] is False
        assert "Timeout" in result["error"]

    async def test_post_title_patch_failure(self):
        """When PATCH of title field fails, return error from WP."""
        wp = _make_wp_client("https://example.org")
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        content_resp = _mock_response(200, {
            "content": {"raw": "<p>body</p>"},
            "title": {"raw": "My Title"},
        })
        wp.get.side_effect = [find_resp, content_resp]
        wp.patch.return_value = _mock_response(403, {"message": "Cannot edit"})

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "My Title", "New Title"
        )

        assert result["success"] is False
        assert "Cannot edit" in result["error"]

    async def test_post_title_patch_exception(self):
        """Exception during post title PATCH returns structured error."""
        wp = _make_wp_client("https://example.org")
        find_resp = _mock_response(200, [
            {"id": 10, "link": "https://example.org/test-page/"},
        ])
        content_resp = _mock_response(200, {
            "content": {"raw": "<p>body</p>"},
            "title": {"raw": "My Title"},
        })
        wp.get.side_effect = [find_resp, content_resp]
        wp.patch.side_effect = Exception("Connection refused")

        result = await change_heading_text(
            wp, "https://example.org/test-page/", "My Title", "New Title"
        )

        assert result["success"] is False
        assert "Connection refused" in result["error"]


# ===================================================================
# find_attachment_by_url
# ===================================================================

class TestFindAttachmentByUrl:

    def _media_item(
        self,
        att_id: int = 100,
        source_url: str = "https://example.org/wp-content/uploads/2024/01/photo.jpg",
        alt_text: str = "A photo",
        title: str = "photo",
        caption: str = "",
        description: str = "",
    ) -> dict:
        """Build a mock WP media API response item."""
        return {
            "id": att_id,
            "source_url": source_url,
            "alt_text": alt_text,
            "title": {"rendered": title},
            "caption": {"rendered": caption},
            "description": {"rendered": description},
        }

    async def test_exact_url_match_via_slug(self):
        """Image found by slug query with exact URL match."""
        wp = _make_wp_client("https://example.org")
        img_url = "https://example.org/wp-content/uploads/2024/01/photo.jpg"

        wp.get.return_value = _mock_response(200, [
            self._media_item(att_id=100, source_url=img_url),
        ])

        result = await find_attachment_by_url(wp, img_url)

        assert result is not None
        assert result["id"] == 100
        assert result["source_url"] == img_url
        assert result["alt_text"] == "A photo"

    async def test_size_suffix_stripping(self):
        """Image URL with WP size suffix (e.g. -600x403) is matched to base image."""
        wp = _make_wp_client("https://example.org")
        sized_url = "https://example.org/wp-content/uploads/2024/01/photo-600x403.jpg"
        base_url = "https://example.org/wp-content/uploads/2024/01/photo.jpg"

        # WordPress returns the base image (no size suffix in source_url)
        wp.get.return_value = _mock_response(200, [
            self._media_item(att_id=200, source_url=base_url),
        ])

        result = await find_attachment_by_url(wp, sized_url)

        assert result is not None
        assert result["id"] == 200

    async def test_slug_with_size_suffix_tried_second(self):
        """When base slug returns nothing, the slug-with-size is tried."""
        wp = _make_wp_client("https://example.org")
        sized_url = "https://example.org/wp-content/uploads/2024/01/hero-1024x683.jpg"
        base_url = "https://example.org/wp-content/uploads/2024/01/hero.jpg"

        # First call (slug=hero) returns empty, second (slug=hero-1024x683) returns match
        empty_resp = _mock_response(200, [])
        match_resp = _mock_response(200, [
            self._media_item(att_id=300, source_url=base_url),
        ])
        wp.get.side_effect = [empty_resp, match_resp]

        result = await find_attachment_by_url(wp, sized_url)

        assert result is not None
        assert result["id"] == 300

    async def test_directory_basename_match(self):
        """Matches when directory + base filename match even if URL encoding differs."""
        wp = _make_wp_client("https://example.org")
        img_url = "https://example.org/wp-content/uploads/2024/01/my-photo-600x400.jpg"
        wp_source = "https://example.org/wp-content/uploads/2024/01/my-photo.jpg"

        wp.get.return_value = _mock_response(200, [
            self._media_item(att_id=400, source_url=wp_source),
        ])

        result = await find_attachment_by_url(wp, img_url)

        assert result is not None
        assert result["id"] == 400

    async def test_search_fallback_exact_match(self):
        """When slug queries return nothing, search API finds the image."""
        wp = _make_wp_client("https://example.org")
        img_url = "https://example.org/wp-content/uploads/2024/01/renamed-image.jpg"

        # All slug queries return empty
        empty = _mock_response(200, [])
        # Search returns exact match
        search_resp = _mock_response(200, [
            self._media_item(att_id=500, source_url=img_url),
        ])
        # Two slug attempts (base slug, same slug since no size suffix) + search
        wp.get.side_effect = [empty, search_resp]

        result = await find_attachment_by_url(wp, img_url)

        assert result is not None
        assert result["id"] == 500

    async def test_search_fallback_size_variant_match(self):
        """Search fallback matches via size-variant URL."""
        wp = _make_wp_client("https://example.org")
        sized_url = "https://example.org/wp-content/uploads/2024/01/banner-800x600.png"
        base_url = "https://example.org/wp-content/uploads/2024/01/banner.png"

        # Slug queries return empty
        empty = _mock_response(200, [])
        # Search returns base URL
        search_resp = _mock_response(200, [
            self._media_item(att_id=600, source_url=base_url),
        ])
        # slug=banner (empty), slug=banner-800x600 (empty), search
        wp.get.side_effect = [empty, empty, search_resp]

        result = await find_attachment_by_url(wp, sized_url)

        assert result is not None
        assert result["id"] == 600

    async def test_no_match_returns_none(self):
        """When no WordPress media matches, return None."""
        wp = _make_wp_client("https://example.org")
        empty = _mock_response(200, [])
        wp.get.return_value = empty

        result = await find_attachment_by_url(
            wp, "https://example.org/wp-content/uploads/2024/01/ghost.jpg"
        )

        assert result is None

    async def test_api_error_returns_none(self):
        """Non-200 from the media API returns None gracefully."""
        wp = _make_wp_client("https://example.org")
        error_resp = _mock_response(500)
        wp.get.return_value = error_resp

        result = await find_attachment_by_url(
            wp, "https://example.org/wp-content/uploads/2024/01/error.jpg"
        )

        assert result is None

    async def test_exception_returns_none(self):
        """Exception during API call returns None."""
        wp = _make_wp_client("https://example.org")
        wp.get.side_effect = Exception("network failure")

        result = await find_attachment_by_url(
            wp, "https://example.org/wp-content/uploads/2024/01/fail.jpg"
        )

        assert result is None

    async def test_html_stripped_from_title_and_caption(self):
        """Title and caption have HTML stripped in the returned dict."""
        wp = _make_wp_client("https://example.org")
        img_url = "https://example.org/wp-content/uploads/2024/01/photo.jpg"

        wp.get.return_value = _mock_response(200, [{
            "id": 700,
            "source_url": img_url,
            "alt_text": "Clean alt",
            "title": {"rendered": "<strong>Bold Title</strong>"},
            "caption": {"rendered": "<p>A <em>nice</em> caption</p>"},
            "description": {"rendered": "<p>Full description &amp; details</p>"},
        }])

        result = await find_attachment_by_url(wp, img_url)

        assert result is not None
        assert result["title"] == "Bold Title"
        assert result["caption"] == "A nice caption"
        assert result["description"] == "Full description & details"

    async def test_admin_url_constructed(self):
        """The admin_url field is correctly constructed from site_url and attachment id."""
        wp = _make_wp_client("https://example.org")
        img_url = "https://example.org/wp-content/uploads/2024/01/photo.jpg"

        wp.get.return_value = _mock_response(200, [
            self._media_item(att_id=42, source_url=img_url),
        ])

        result = await find_attachment_by_url(wp, img_url)

        assert result["admin_url"] == "https://example.org/wp-admin/post.php?post=42&action=edit"

    async def test_cache_bust_parameter(self):
        """cache_bust=True adds a _nocache parameter to the query."""
        wp = _make_wp_client("https://example.org")
        img_url = "https://example.org/wp-content/uploads/2024/01/photo.jpg"

        wp.get.return_value = _mock_response(200, [
            self._media_item(att_id=100, source_url=img_url),
        ])

        result = await find_attachment_by_url(wp, img_url, cache_bust=True)

        assert result is not None
        # Verify the get call included _nocache parameter
        call_arg = wp.get.call_args_list[0][0][0]
        assert "_nocache=" in call_arg

    async def test_encoded_filename_in_url(self):
        """URL-encoded filenames are decoded for slug generation."""
        wp = _make_wp_client("https://example.org")
        # URL with encoded spaces
        img_url = "https://example.org/wp-content/uploads/2024/01/my%20photo.jpg"
        source_url = "https://example.org/wp-content/uploads/2024/01/my%20photo.jpg"

        wp.get.return_value = _mock_response(200, [
            self._media_item(att_id=800, source_url=source_url),
        ])

        result = await find_attachment_by_url(wp, img_url)

        assert result is not None
        assert result["id"] == 800

    async def test_multiple_size_suffixes_stripped(self):
        """Common WP size suffixes like -150x150, -1024x683 are correctly stripped."""
        wp = _make_wp_client("https://example.org")
        base_url = "https://example.org/wp-content/uploads/2024/01/thumbnail.jpg"

        for suffix in ["-150x150", "-300x200", "-1024x683", "-1536x1024"]:
            sized_url = f"https://example.org/wp-content/uploads/2024/01/thumbnail{suffix}.jpg"
            wp.get.return_value = _mock_response(200, [
                self._media_item(att_id=900, source_url=base_url),
            ])

            result = await find_attachment_by_url(wp, sized_url)
            assert result is not None, f"Failed for suffix {suffix}"
            assert result["id"] == 900

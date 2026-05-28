---
status: current
last_reviewed: 2026-05-27
---

# WordPress Integration Specifications

One-click remediation of SEO issues via WordPress REST API.

## Features

- **Fix Manager** — generate + apply fixes via 6 domain routers (v2.3 split)
- **Media Library integration** — query and update WordPress image
  metadata (alt text, title, caption, description)
- **Cross-site protection** — every WP-touching endpoint validates that
  the credentials' `site_url` domain matches the crawl job's target
  domain. Mismatch → 403 `DOMAIN_MISMATCH` (v1.9.4).
- **Auto-Rescan** — page auto-rescans after a fix is applied so the
  health score reflects post-fix state
- **Empty-write guard** — refuses to write empty strings to text fields,
  preventing accidental clearing of live SEO content (verified docs-review
  Defect #5)

## Domain Router Layout (v2.3)

The v2.3 split into focused router modules:

| Router | Path prefix | Endpoints |
|---|---|---|
| `fix_manager_router.py` | `/api/fixes/` | `generate/{id}`, `{id}` (list), `{fix_id}` (patch), `apply/{id}`, `{id}` (delete) |
| `title_router.py` | `/api/fixes/` | `predefined-codes`, `bulk-trim-titles`, `trim-title-one` |
| `heading_router.py` | `/api/fixes/` | `find-heading`, `analyze-heading-sources`, `change-heading-level`, `change-heading-text`, `bulk-replace-heading`, `heading-to-bold` |
| `image_router.py` | `/api/fixes/` | `image-info`, `update-image-meta`, `refresh-image-from-wp`, `optimize-image`, `optimize-existing-preview`, `optimize-existing`, `optimize-upload-preview`, `optimize-upload` |
| `orphaned_media_router.py` | `/api/fixes/` | `orphaned-media/{id}` |
| `batch_optimizer_router.py` | `/api/fixes/` | `batch-optimize/start`, `batch-optimize/{batch_id}/status`, `.../pause`, `.../resume`, `.../cancel`, `batch-optimize/list` |
| `link_router.py` | `/api/fixes/` | `link-sources`, `replace-link`, `verify-broken-links/{id}`, `mark-broken-link-fixed`, `mark-anchor-fixed`, `mark-issue-fixed`, `apply-one`, `wp-value` |

Full HTTP contracts (request shape, response shape, error codes) are in
[`../../api.md`](../../api.md). Acceptance criteria for each are in
[`../../functional-specification.md`](../../functional-specification.md) §5.

## Credentials Configuration

The shipped implementation uses **cookie-based** WordPress authentication.
`wp-credentials.json` at the project root:

```json
{
  "site_url": "https://example.com",
  "login_url": "https://example.com/wp-login.php",
  "username": "admin_user",
  "password": "your-password-here"
}
```

The `WPClient` class (see `api/services/wp_client.py`) logs in via
the standard WordPress login endpoint and reuses the resulting cookie
session for all REST calls.

> **Note:** earlier draft documentation proposed an "Application
> Password" shape (`{ domain, url, username, app_password }`). That
> shape is **not** what the code reads — `WPClient.from_credentials_file`
> expects the cookie-shape above. Application Passwords could be added
> in v3.0 as an alternative auth path if a customer requires it; today
> they are not supported.

## Supported Fixes (by issue code)

The full list of automatable codes lives in `_CODE_TO_FIELD` in
`api/services/wp_shared.py`. As of v2.3, fixable codes include:

- Title: `TITLE_MISSING`, `TITLE_TOO_SHORT`, `TITLE_TOO_LONG`, `TITLE_H1_MISMATCH`
- Meta: `META_DESC_MISSING`, `META_DESC_TOO_SHORT`, `META_DESC_TOO_LONG`
- Indexability: `NOINDEX_META` (re-enable indexing)
- Heading: H1/H2/H3/H4/H5/H6 text changes, level changes, to-bold conversion
- Image: alt / title / caption / description updates; optimization (Workflow A and B)
- Link: replace URL in WP post content; remove empty anchor href; mark fixed

Frontend calls `GET /api/fixes/predefined-codes` to discover this list
dynamically — so the frontend stays in sync without hardcoding.

## Implementation Status

- ✅ All 6 domain routers (v2.3 M0.12.1–6)
- ✅ Cross-site domain validation on all 22+ WP-touching endpoints (v1.9.4)
- ✅ Empty-write guard against silent data loss (verified)
- ✅ SSRF guards on WP image fetches (v2.3 M0.6.7)
- ✅ Contract tests (v2.3 M0.12.8 + M8 backfill) — auth, validation, NO_CREDENTIALS, DOMAIN_MISMATCH

## Related Documentation

- Architecture: [`../../architecture.md`](../../architecture.md)
- API: [`../../api.md`](../../api.md)
- Functional spec: [`../../functional-specification.md`](../../functional-specification.md)
- Issue codes: [`../../issue-codes.md`](../../issue-codes.md)
- Deployment: [`../../deployment-railway.md`](../../deployment-railway.md)

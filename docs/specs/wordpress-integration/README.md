# WordPress Integration Specifications

One-click remediation of SEO issues via WordPress REST API.

## Features

- **Fix Manager** — Apply fixes directly to WordPress (titles, meta descriptions, headings, image metadata)
- **Media Library Integration** — Query and update WordPress image metadata (alt text, title, caption, description)
- **Domain Validation** — Prevent cross-site data leakage and accidental writes to wrong WordPress site
- **Auto-Rescan** — Automatically rescans page after fix to update health score

## Supported Fixes

| Issue Code | Fix Type | Endpoint |
|---|---|---|
| `TITLE_MISSING`, `TITLE_TOO_SHORT`, `TITLE_TOO_LONG` | Edit post title | `POST /api/fixes/change-title` |
| `TITLE_H1_MISMATCH` | Edit H1 heading | `POST /api/fixes/change-heading-text` |
| `META_DESC_MISSING`, `META_DESC_TOO_SHORT`, `META_DESC_TOO_LONG` | Edit meta description | `POST /api/fixes/change-meta` |
| `LINK_EMPTY_ANCHOR` | Remove empty hrefs | `POST /api/fixes/mark-anchor-fixed` |
| Image metadata | Update WordPress Media Library | `PUT /api/fixes/wp-image-metadata` |

## Configuration

WordPress credentials stored in `wp-credentials.json`:

```json
{
  "domain": "livingsystems.ca",
  "url": "https://livingsystems.ca",
  "username": "admin_user",
  "app_password": "xxxx xxxx xxxx xxxx xxxx xxxx"
}
```

## Related Documentation

- Architecture: `../../architecture/architecture.md`
- API: `../../api/api.md`
- Local Setup: `../../guides/wordpress-config.md`

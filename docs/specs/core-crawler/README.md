# Core Crawler Specifications

The crawler engine and core SEO audit functionality for TalkingToad.

## Specifications

| Version | Status | File | Description |
|---------|--------|------|-------------|
| v1.4 | Implemented | [v1.4-nonprofit-crawler.md](v1.4-nonprofit-crawler.md) | Foundation spec. Defines crawler architecture, data model, issue codes (Phase 1 & 2), API endpoints, frontend pages |
| v1.5 | Implemented | [v1.5-extensions.md](v1.5-extensions.md) | Extensions spec. Adds security checks, WordPress integration, new issue codes, image intelligence baseline |

## Key Features

- **Async BFS crawler** with robots.txt and sitemap support
- **50+ SEO issue checks** across 10 categories (metadata, headings, links, security, etc.)
- **Health score** calculation (0–100, based on issue impacts)
- **WordPress REST API integration** for one-click fixes
- **PDF and Excel export** with action checklists
- **Image Intelligence** (Level 1 scan in v1.5; expanded in v1.9)

## Implementation Status

✅ Core crawler (v1.4)  
✅ Security checks (v1.5)  
✅ WordPress fixes (v1.5)  
✅ Image scanning (v1.9 — see `../image-analysis/`)

## Related Documentation

- Architecture: `../../architecture/architecture.md`
- API Reference: `../../api/api.md`
- Issue Codes: `../../reference/issue-codes.md`

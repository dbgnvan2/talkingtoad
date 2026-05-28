---
status: current
last_reviewed: 2026-05-27
---

# Core Crawler Specifications

The crawler engine and core SEO audit functionality for TalkingToad.

## Specifications

| Version | Status | File | Description |
|---|---|---|---|
| v1.4 | Implemented | [v1.4-nonprofit-crawler.md](v1.4-nonprofit-crawler.md) | Foundation spec. Crawler architecture, data model, issue codes (Phase 1 & 2), API endpoints, frontend pages. |
| v1.5 | Implemented | [v1.5-extensions.md](v1.5-extensions.md) | Extensions: security checks, WordPress integration, new issue codes, image intelligence baseline. |

## Key Features

- **Async BFS crawler** with robots.txt and sitemap support
- **133 SEO issue checks** across 10 categories (metadata, headings, links, security, AI-readiness, etc.)
- **Health score** calculation `max(0, 100 − Σ impact)`
- **WordPress REST integration** for one-click fixes (split across 6 domain routers in v2.3)
- **PDF and Excel export** with action checklists
- **Image Intelligence** (Level 1 scan in v1.5; expanded in v1.9)
- **AI-Readiness audit** (49 checks with Established / Reasonable proxy / Heuristic confidence labels — v2.3 M0.2)

## Implementation Status

- ✅ Core crawler (v1.4)
- ✅ Security checks (v1.5)
- ✅ WordPress fixes (v1.5; v2.3 split into title/heading/image/orphaned-media/batch-optimizer/link routers)
- ✅ Image scanning (v1.9 — see `../image-analysis/`)
- ✅ AI-Readiness with confidence labels (v2.3 M0.2)
- ✅ Production-safe deployment (v2.3 M0.7 — Railway container, see `../../deployment-railway.md`)

## Related Documentation

- Architecture: [`../../architecture.md`](../../architecture.md)
- API Reference: [`../../api.md`](../../api.md)
- Issue Codes: [`../../issue-codes.md`](../../issue-codes.md)
- Functional Specification: [`../../functional-specification.md`](../../functional-specification.md)
- Project Plan: [`../../../PLAN-V3.0.md`](../../../PLAN-V3.0.md)

# TalkingToad Specifications

Complete specification index organized by feature domain. Each domain folder contains version history, status, and cross-references.

## By Feature Domain

| Domain | Status | Latest Version | Quick Link |
|--------|--------|---|---|
| **Core Crawler** | ✅ Implemented | v1.5 (extensions) | [core-crawler/README.md](core-crawler/README.md) |
| **Image Analysis** | ✅ Implemented | v1.9.1 (GEO optimization) | [image-analysis/README.md](image-analysis/README.md) |
| **AI-Readiness** | ⏳ Draft (v2) | v1.7 (implemented) + v2.0 (pending) | [ai-readiness/README.md](ai-readiness/README.md) |
| **WordPress Integration** | ✅ Implemented | v1.0 | [wordpress-integration/README.md](wordpress-integration/README.md) |

## All Specification Files

### Core Crawler
- [v1.4-nonprofit-crawler.md](core-crawler/v1.4-nonprofit-crawler.md) — Foundation spec
- [v1.5-extensions.md](core-crawler/v1.5-extensions.md) — Security, WordPress, image baseline

### Image Analysis
- [v1.9-image-intelligence-engine.md](image-analysis/v1.9-image-intelligence-engine.md) — 3-level architecture
- [v1.9.1-geo-optimization-spec.md](image-analysis/v1.9.1-geo-optimization-spec.md) — GEO metadata
- [v1.9.1-geo-optimization-prompt.md](image-analysis/v1.9.1-geo-optimization-prompt.md) — AI prompt

### AI-Readiness
- [v2-extended-module.md](ai-readiness/v2-extended-module.md) — AI bot access, schema typing, citations

## Reference Documentation

For implementation guidance and architecture decisions, see:

| Document | Purpose |
|----------|---------|
| `../architecture/architecture.md` | System design, data flow, design decisions |
| `../api/api.md` | Full API endpoint reference |
| `../reference/issue-codes.md` | All issue codes with severity and category |
| `../CLAUDE.md` | Project overview and tech stack |

## Version Legend

| Icon | Meaning |
|------|---------|
| ✅ | Fully implemented and tested |
| ⏳ | Drafted, pending implementation review |
| 🔄 | In active development |
| 📋 | Planned for future release |

## How to Use These Specs

1. **Planning:** Start with the domain README (e.g., `ai-readiness/README.md`) for overview
2. **Implementation:** Read the full specification in the domain folder
3. **Reference:** Check `../architecture/` or `../api/` for cross-cutting concerns
4. **Updates:** When implementing a spec version, create a new file with `vX.Y-` prefix and update the domain README

---

**Last updated:** May 3, 2026  
**Project:** TalkingToad v1.9.1

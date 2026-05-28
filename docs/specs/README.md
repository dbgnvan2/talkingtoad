---
status: current
last_reviewed: 2026-05-27
---

# TalkingToad Specifications

Complete specification index organised by feature domain.

## By Feature Domain

| Domain | Status | Latest Version | Spec |
|---|---|---|---|
| **Core Crawler** | ✅ Implemented | v1.5 extensions | [core-crawler/README.md](core-crawler/README.md) |
| **Image Analysis** | ✅ Implemented | v1.9.1 GEO optimization | [image-analysis/README.md](image-analysis/README.md) |
| **AI-Readiness** | ✅ Implemented (v2.0 confidence-labelled in v2.3) | v2.0 extended module | [ai-readiness/README.md](ai-readiness/README.md) |
| **WordPress Integration** | ✅ Implemented (v2.3 split into 6 domain routers) | v1.0 | [wordpress-integration/README.md](wordpress-integration/README.md) |

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

### WordPress Integration

- See the domain README — implementation is captured in
  [`../api.md`](../api.md) (HTTP contracts) and the source files
  (`api/routers/title_router.py`, `heading_router.py`, `image_router.py`,
  `orphaned_media_router.py`, `batch_optimizer_router.py`,
  `link_router.py`).

## Reference Documentation

Cross-cutting docs. Note: `docs/` is **flat** — earlier path conventions
that referenced subdirectories like `../architecture/architecture.md`
were incorrect and are fixed below.

| Document | Purpose |
|---|---|
| [`../architecture.md`](../architecture.md) | System design, data flow, design decisions |
| [`../api.md`](../api.md) | Full API endpoint reference |
| [`../issue-codes.md`](../issue-codes.md) | Issue codes with descriptions |
| [`../functional-specification.md`](../functional-specification.md) | What the app does, for QA review |
| [`../deployment-railway.md`](../deployment-railway.md) | Production deployment guide |
| [`../docs-review-response.md`](../docs-review-response.md) | Triage of external docs-folder review |
| [`../../CLAUDE.md`](../../CLAUDE.md) | Project overview, tech stack, conventions |
| [`../../PLAN-V3.0.md`](../../PLAN-V3.0.md) | v3.0 roadmap and milestones |

## Version Legend

| Icon | Meaning |
|---|---|
| ✅ | Fully implemented and tested |
| ⏳ | Drafted, pending implementation |
| 🔄 | In active development |
| 📋 | Planned for future release |

## How to Use These Specs

1. **Planning:** Start with the domain README for an overview.
2. **Implementation:** Read the full specification file in the domain folder.
3. **Reference:** Cross-cutting docs are listed above.
4. **Updates:** When implementing a spec version, add a new file with the
   `vX.Y-` prefix and update both the domain README and this index.

---

**Last updated:** 2026-05-27
**Project version:** v2.3 (v3.0 in progress — see `../../PLAN-V3.0.md`)

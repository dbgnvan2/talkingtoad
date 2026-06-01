# TalkingToad Documentation

Complete documentation for TalkingToad — an SEO crawler with WordPress integration. Currently used by nonprofit organizations; v3.0 plan expands to a paid customer base.

## Getting Started

**New to TalkingToad?** Start with [CLAUDE.md](../CLAUDE.md) in the project root for an overview of features, tech stack, and coding standards.

**Setting up for deploy?** See [deployment-railway.md](deployment-railway.md) for the v2.3 architecture (Vercel frontend + Railway backend).

**Planning v3.0?** See [../PLAN-V3.0.md](../PLAN-V3.0.md) for the full plan: 11 milestones, release phasing, strategic decisions on AI providers and deployment.

## Core Documentation

| Document | Purpose |
|---|---|
| [architecture.md](architecture.md) | Full system architecture, crawler pipeline, data models |
| [api.md](api.md) | API endpoint reference (request/response schemas, auth) |
| [issue-codes.md](issue-codes.md) | Issue codes with descriptions, severity, category (auto-generated from `_CATALOGUE`) |
| [thresholds.md](thresholds.md) | Canonical table of every numeric threshold the app uses |
| [user-guide.md](user-guide.md) | End-user guide to running audits and fixes |
| [overview.md](overview.md) | High-level project overview |
| [deployment-railway.md](deployment-railway.md) | Production deployment: Vercel frontend + Railway backend |
| [ai-readiness.md](ai-readiness.md) | Confidence label scheme and citation ingestion contract |
| [security-model.md](security-model.md) | OAuth token storage, SSRF protection, auth model |
| [ai-routing.md](ai-routing.md) | Task-to-model routing, pricing, provider notes |

## Specifications

| Spec | File |
|---|---|
| All feature specs index | [specs/README.md](specs/README.md) |
| Core Crawler (v1.5) | [specs/core-crawler/README.md](specs/core-crawler/README.md) |
| Image Analysis (v1.9.1) | [specs/image-analysis/README.md](specs/image-analysis/README.md) |
| AI-Readiness (v2.0 — in progress for v3.0) | [specs/ai-readiness/README.md](specs/ai-readiness/README.md) |
| WordPress Integration (v1.0) | [specs/wordpress-integration/README.md](specs/wordpress-integration/README.md) |

## Status & Review Documents

| Document | Purpose |
|---|---|
| [REMEDIATION_STATUS.md](REMEDIATION_STATUS.md) | Status report from the pre-v2.0 codebase remediation work |
| [REVIEW.md](REVIEW.md) | Critical-review document for external code-review sessions |
| [STATUS_GEO_ADVISOR_REWRITER.md](STATUS_GEO_ADVISOR_REWRITER.md) | Status of GEO Advisor + Rewriter shipped in v2.2 |

## Implementation Plan Documents

Several implementation-plan markdown files live in this directory for in-progress or completed work. They're useful for understanding why specific changes landed:

- `implementation_plan_geo_*.md` — GEO analyzer/rewriter milestone plans
- `image-scan-spec.md`, `image-scan-implementation-plan.md` — Image scan architecture
- `image-optimization-spec.md` — v1.9.1 image optimization
- `fix-agent-spec.md`, `geo-frontend-integration.md`, `ROUTER_IMPLEMENTATION_GUIDE.md` — Implementation guides
- `geo_image_ai_spec.md`, `geo_image_ai_prompt.md` (under specs/) — Vision AI prompts

## Project Management

| File | Purpose |
|---|---|
| [../PLAN-V3.0.md](../PLAN-V3.0.md) | Full v3.0 plan: 11 milestones, 15-17 weeks, release phasing |
| [../PLAN.md](../PLAN.md) | Original implementation plan (pre-v3) |
| [../TODO.md](../TODO.md) | Project TODO and technical debt |
| [../REVIEW_SPEC.md](../REVIEW_SPEC.md) | Code review specification |

## Parked Features

- [Multi-Tenant TODO](TODO-MULTITENANT.md) — Planned multi-tenant AI key management
- [SERP Discovery](PARKED-SERP-DISCOVERY.md) — Separate repository for SERP analysis

---

**Project Version:** 2.6.0 (tag `v2.6-stabilized`, v3.0 feature work active)
**Last Updated:** 2026-05-27
**GitHub:** https://github.com/dbgnvan2/talkingtoad

> **Doc structure note (v2.3 M0.10):** Earlier versions of this README
> linked to subdirectories like `architecture/`, `api/`, `reference/`,
> `guides/` that never existed. All docs live flat in `docs/` and `docs/specs/`.
> Broken links are fixed in this rewrite. See PLAN-V3.0.md M0.10.

> **Workflow note:** The day-to-day proposal → approval → implementation
> cycle and the per-milestone Gemini Compiler step are documented in
> `CLAUDE.md` under "Specification Change Management". This README is the
> documentation index only.

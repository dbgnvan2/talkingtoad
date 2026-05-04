# TalkingToad Documentation

Complete documentation for TalkingToad — a free, zero-installation SEO crawler for nonprofit organizations.

## Getting Started

**New to TalkingToad?** Start with [CLAUDE.md](../CLAUDE.md) in the project root for an overview of features and tech stack.

## Documentation Structure

### 📋 Specifications
All formal specifications organized by feature domain.

→ **[specs/README.md](specs/README.md)** — Browse specs by feature (Core Crawler, Image Analysis, AI-Readiness, WordPress)

### 🏗️ Architecture & Design
System design, data flow, and architectural decisions.

- [architecture.md](architecture/architecture.md) — Full system architecture, crawler pipeline, data models
- [design-decisions.md](architecture/design-decisions.md) — Why we chose Redis over SQLite, async-first design, etc.

### 🔌 API Reference
Complete API endpoint documentation.

- [api.md](api/api.md) — All endpoints, request/response schemas, authentication

### 📖 Reference
Issue codes, scoring formulas, configuration.

- [issue-codes.md](reference/issue-codes.md) — All 50+ issue codes with descriptions, severity, category
- [scoring.md](reference/scoring.md) — Health score calculation, impact/effort weighting

### 🛠️ Guides
How-to guides, setup instructions, troubleshooting.

- [local-dev-setup.md](guides/local-dev-setup.md) — Running TalkingToad locally
- [wordpress-config.md](guides/wordpress-config.md) — WordPress credential setup, app passwords

## Quick Navigation

| I want to... | Go to... |
|---|---|
| Understand the project overview | [CLAUDE.md](../CLAUDE.md) at project root |
| See all feature specs | [specs/README.md](specs/README.md) |
| Understand system architecture | [architecture/architecture.md](architecture/architecture.md) |
| Find an API endpoint | [api/api.md](api/api.md) |
| Look up an issue code | [reference/issue-codes.md](reference/issue-codes.md) |
| Set up WordPress integration | [guides/wordpress-config.md](guides/wordpress-config.md) |
| Run locally | [guides/local-dev-setup.md](guides/local-dev-setup.md) |

## Specification Versions

| Feature | Version | Status |
|---------|---------|--------|
| Core Crawler | v1.5 | ✅ Implemented |
| Image Analysis | v1.9.1 | ✅ Implemented |
| AI-Readiness | v1.7 + v2.0 draft | ✅ v1.7 / ⏳ v2.0 |
| WordPress Integration | v1.0 | ✅ Implemented |

See [specs/README.md](specs/README.md) for detailed version history and implementation status per feature.

## Key Documents by Topic

### For Developers
- [architecture/architecture.md](architecture/architecture.md) — Data flow, design patterns, constraints
- [api/api.md](api/api.md) — Endpoint contracts
- [CLAUDE.md](../CLAUDE.md) — Coding standards, testing requirements, tech stack

### For Product/Planning
- [specs/core-crawler/README.md](specs/core-crawler/README.md) — Core features
- [specs/image-analysis/README.md](specs/image-analysis/README.md) — Image Intelligence roadmap
- [specs/ai-readiness/README.md](specs/ai-readiness/README.md) — AI-readiness module (v2 draft)

### For Nonprofits Using TalkingToad
- [guides/local-dev-setup.md](guides/local-dev-setup.md) — Getting started
- [reference/issue-codes.md](reference/issue-codes.md) — Understanding audit results
- [guides/wordpress-config.md](guides/wordpress-config.md) — One-click fix setup

---

**Project Version:** 1.9.1  
**Last Updated:** May 3, 2026  
**GitHub:** https://github.com/dbgnvan2/talkingtoad

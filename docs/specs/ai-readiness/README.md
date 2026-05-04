# AI-Readiness Module Specifications

Audit site readiness for AI crawler access, citation, and content extraction.

## Specifications

| Version | Status | File | Description |
|---------|--------|------|-------------|
| v1.7 | Implemented | (in `../../architecture/architecture.md`) | Baseline module. `llms.txt` presence, semantic density, JSON-LD schema, conversational headings |
| v2.0 | Draft | [v2-extended-module.md](v2-extended-module.md) | Major extension. AI bot access checks (robots.txt), schema typing, content extractability heuristics, citation hooks |

## Key Features

### v1.7 (Implemented)

- `llms.txt` presence check
- Semantic density (text-to-HTML ratio)
- JSON-LD schema detection
- Conversational H2 headings

### v2.0 (Draft for Implementation)

- **AI Bot Access Checks** — Validates robots.txt for 20+ AI bots (training, search, user-fetch categories)
- **Schema Typing** — Infers page type and validates appropriate JSON-LD schema
- **Content Extractability** — Checks for `<main>` landmark, heading hierarchy, paragraph length
- **Passage Heuristics** — Detects long paragraphs, missing definitions (opt-in, behind feature flag)
- **Citation Hooks** — Data model for ingesting AI citation data from sibling SERP tool

## Confidence Labeling

Every check carries one of three labels (required in UI):

- **Established** — Vendor-confirmed effect on AI crawling/indexing
- **Reasonable proxy** — Industry consensus but partial vendor confirmation
- **Heuristic** — Believed influential but no vendor confirmation

## Implementation Status

✅ v1.7 baseline (implemented)  
⏳ v2.0 extended (draft, pending review and implementation planning)

## Related Documentation

- Architecture: `../../architecture/architecture.md`
- Issue Codes: `../../reference/issue-codes.md#ai-readiness-codes`
- API: `../../api/api.md`

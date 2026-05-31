# TalkingToad Repository Summary
*Generated on Friday, May 29, 2026*

This document provides a comprehensive technical description of the TalkingToad codebase, focusing on feature-level functionality for Python modules and core frontend components.

## 1. API Core & Lifecycle (`api/`)

- **main.py**: The FastAPI application entry point. Wires together CORS middleware, slowapi rate limiting, bearer token authentication, and all service routers. It manages the lifecycle of the `JobStore` and provides structured JSON logging for production monitoring.
- **crawler/**:
    - **engine.py**: The central orchestration engine for crawling. Manages concurrency (default 5 workers), coordinates between the `fetcher`, `parser`, and `issue_checker`, and handles progress tracking across distinct phases: `crawling_pages`, `checking_external_links`, and `analyzing_images`.
    - **fetcher.py**: A robust HTTP client wrapper for crawling. Implements exponential backoff retry logic, user-agent rotation, timeout management, and SSRF safety checks. Supports `HEAD` requests for fast metadata gathering of images and external resources.
    - **parser.py**: Extracts semantic data from HTML using `BeautifulSoup`. Specifically extracts metadata (titles, descriptions, OpenGraph), headings (H1-H6), links, and image attributes (including `srcset` and WordPress-specific captions).
    - **issue_checker.py**: Coordinates a suite of specialized "Checkers" to identify SEO and quality issues. It maps raw crawl data to the unified `Issue` model, including impact and effort scoring for priority ranking.
    - **normaliser.py**: Utility for URL normalization and identifying "noise" paths (e.g., WordPress admin, login pages, or feed URLs) to optimize crawl efficiency and avoid redundant processing.
    - **robots.py**: Fetches and parses `robots.txt` files to ensure crawl compliance and extract sitemap URLs. Detects bot-specific blocks that might affect AI readiness.
    - **sitemap.py**: Recursively fetches and parses XML sitemaps to build a prioritized list of URLs for the crawler, ensuring deep discovery of site content.
    - **checkers/**: Modular plugins for `issue_checker.py`:
        - **ai_readiness.py**: Validates robots.txt for AI bot access and checks for `llms.txt` presence.
        - **crawlability.py**: Detects indexing blocks (`noindex`), canonical mismatches, and status code errors.
        - **headings.py**: Validates H1 presence, uniqueness, and heading hierarchy.
        - **images.py**: Flags missing alt text, oversized files, and scaling issues.
        - **links.py**: Identifies broken internal/external links and redirect chains.
        - **metadata.py**: Checks for missing or suboptimal SEO titles and meta descriptions.
        - **security.py**: Validates HTTPS usage and cross-origin security headers.

## 2. API Routers (`api/routers/`)

- **crawl.py**: Full lifecycle management for crawl jobs. Provides endpoints for starting, monitoring status, canceling, and exporting results as CSV or structured JSON.
- **geo.py**: Manages GEO (Generative Engine Optimization) settings. Allows users to define domain-specific identity and location pools for AI-assisted image metadata generation.
- **fixes.py**: The master router for WordPress remediations. Aggregates category-specific routers for links, titles, headings, and images into a single mount point.
- **advisor.py**: Interfaces with the AI Advisor service (Tool A). Provides endpoints for evaluating page quality for AI retrieval and generating rewrite prompts based on identified gaps.
- **ai.py**: General-purpose AI analysis router. Handles multi-modal image analysis, semantic issue detection, and executive summary generation.
- **usage.py**: Provides detailed reporting on AI provider usage (tokens, costs, success rates) for auditing and billing.
- **fix_manager_router.py**: Core CRUD operations for the v2.0 Fix Manager. Generates fix proposals by matching crawl issues with WordPress post data.
- **link_router / title_router / heading_router / image_router**: Specialized routers for targeted remediations, such as bulk-trimming SEO titles or fixing broken links in WordPress content.
- **batch_optimizer_router.py**: Orchestrates long-running batch processes for image optimization, allowing for pause/resume/cancel controls and real-time status updates.

## 3. Services Layer (`api/services/`)

- **ai_router.py**: The central LLM provider orchestrator (v2.6). Selects the appropriate provider (OpenAI/Gemini), manages credentials, handles retries, and records usage metadata via a unified internal protocol.
- **providers/ (openai.py, gemini.py, base.py)**: Concrete driver implementations that use raw `httpx` to interface with AI APIs. This ensures no provider-specific SDKs are imported into the core application, maintaining a clean abstraction boundary.
- **advisor.py**: Implements "Tool A" (Content Evaluation). Analyzes content across six properties: source fidelity, factual grounding, self-containment, structural fitness, authority signals, and honest placeholders.
- **rewriter.py**: Implements "Tool B" (Content Rewriting). Applies targeted prompts to original content to produce optimized versions while maintaining factual integrity and tone.
- **ai_analyzer.py**: Orchestrates multi-modal analysis. Uses vision models for accessibility audits (alt text generation) and GEO optimization of images.
- **ai_readiness.py / ai_bots.py**: Maintains a reference table of AI crawlers and validates site-level configuration for AI-friendly access.
- **wp_client.py**: A specialized, authenticated client for the WordPress REST API. Handles cookie-based login and nonce management, supporting custom login URLs and SEO plugin integration.
- **wp_fixer.py**: The primary engine for applying changes to WordPress. Resolves URLs to post IDs and executes updates across SEO plugins (Yoast/RankMath) and native fields.
- **job_store.py / sqlite_store.py / redis_store.py**: Persistence layer. Manages jobs, pages, and issues with support for local SQLite or production-grade Upstash Redis via a common `JobStore` protocol.
- **image_processor.py**: Technical image optimization. Handles WebP conversion, resizing, and LANCZOS resampling to reduce file size while preserving visual quality.
- **exif_injector.py**: Injects GPS and copyright metadata into optimized images for local SEO and GEO ranking.
- **report_generator.py / excel_generator.py**: Generates professional PDF and Excel reports for clients, including executive summaries, prioritized remediation lists, and health scores.
- **usage_logger.py / ai_pricing.py**: Tracks every LLM call for cost calculation and reconciliation, ensuring cent-precise financial reporting across providers.

## 4. Models & Schemas (`api/models/` & `api/schemas/`)

- **job.py**: Defines `CrawlJob` and `CrawlSettings`, tracking progress across crawling, external link checking, and image analysis.
- **page.py**: Represents a `CrawledPage`, storing extracted HTML data, status codes, and metadata.
- **issue.py**: Defines the unified `Issue` model with severity, category, and priority ranking (impact vs. effort).
- **link.py**: Tracks discovered hyperlinks and their verified status (broken vs. working).
- **image.py**: The `ImageInfo` model, storing technical performance metrics alongside AI-generated semantic metadata.
- **geo_config.py**: Stores per-domain identity settings for GEO optimization.
- **fix.py**: Tracks the state of a WordPress remediation (e.g., `proposed_value` vs. `current_value`).
- **usage.py**: Pydantic schemas for the usage aggregation API (DTOs).

## 5. Frontend (`frontend/src/`)

- **App.jsx**: The main application layout. Manages global routing, sidebar navigation, and integrates the `ThemeContext` for light/dark mode.
- **api.js**: The frontend API client. Provides a structured interface to all backend endpoints, including error handling, polling logic, and authentication header management.
- **pages/**:
    - **Home.jsx**: The landing page for starting new crawls and managing historical jobs.
    - **Progress.jsx**: Real-time dashboard for monitoring an active crawl job with phase-specific progress bars and a live URL feed.
    - **Results.jsx**: The primary data view. Displays the health score, issue breakdowns, and provides access to remediations and exports.
- **components/**:
    - **FixManager.jsx**: The central UI for reviewing, editing, and applying WordPress fixes.
    - **GEOReportPanel.jsx**: Displays the results of the GEO analysis and image optimization, including "Before vs. After" comparisons.
    - **AIReadinessPanel.jsx**: Summarizes the site's accessibility to AI crawlers and generates `llms.txt` recommendations.
    - **IssueTable.jsx**: A sortable, filterable table for exploring all discovered SEO issues with detailed help text.
    - **BatchOptimizePanel.jsx**: UI for managing and monitoring bulk image optimization jobs.
- **hooks/**:
    - **useCrawl.js**: Custom hook for managing crawl job state, triggering starts/cancels, and handling result data.
    - **usePolling.js**: Utility hook for periodic status updates (e.g., during a crawl or long-running batch process).
- **data/**:
    - **issueHelp.js / categoryHelp.js**: Local repository of educational content that explains the "What", "Impact", and "Fix" for every issue code identified by the crawler.

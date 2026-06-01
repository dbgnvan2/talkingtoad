---
title: Security Model
status: draft
last_updated: 2026-06-01
---

# Security Model

## OAuth Token Storage (GSC)

### Threat Model

- **Assets**: GSC OAuth tokens (access + refresh tokens), AI provider API keys.
- **Adversary**: Attacker with filesystem access to the server, or SQL injection access to the database.
- **Goal**: Extract tokens to impersonate the user's GSC account or consume AI API credits.

### Encryption

- Tokens are encrypted using **Fernet** (symmetric AES-128-CBC + HMAC-SHA256) via `cryptography.fernet`.
- The encryption key is `AI_CREDS_ENCRYPTION_KEY` from environment variables.
- In production, this key must be a 32-byte URL-safe base64-encoded value.

### Storage

- **Production (Upstash Redis)**: Encrypted tokens stored as JSON blobs with key prefix `gsc_tokens:{site_url}`.
- **Local dev (SQLite)**: Encrypted tokens stored in `gsc_credentials` table.
- **Fallback**: If `AI_CREDS_ENCRYPTION_KEY` is not set, tokens are stored as raw JSON **only** when the request comes from `localhost` (checked via `request.client.host`). This is an insecure-transport gate for development convenience.

### Token Refresh

- Expired access tokens are automatically refreshed using the stored refresh token.
- Refresh failures revoke the stored token set and return `401 GSC_TOKEN_EXPIRED`.

## SSRF Protection

### Coverage

- **All outbound HTTP fetches** go through `api/crawler/fetcher.py:is_ssrf_safe()`.
- This includes: crawl targets, robots.txt, sitemaps, image downloads.
- **GSC API calls** are exempt from `is_ssrf_safe` because they only hit Google hosts (`www.googleapis.com`, `oauth2.googleapis.com`). The GSC client hardcodes these hosts.
- **Citation/entity URLs** embedded in user input are **never fetched**. They are stored and cross-referenced against already-crawled pages only.

### Implementation

- `is_ssrf_safe(url)` resolves the hostname and checks against private IP ranges (RFC 1918, loopback, link-local, etc.).
- Check is performed **before** the first request **and** on every redirect hop.
- Blocked IPs return `403 SSRF_BLOCKED`.

## WordPress Domain Validation

- Every WordPress-touching endpoint validates that the target domain matches the job's registered WordPress domain.
- Validation functions: `_validate_wp_domain_for_job(store, job_id)` and `_validate_wp_domain_for_url(url)`.
- Mismatches return `403 DOMAIN_MISMATCH`.
- This prevents cross-tenant WP operations (critical for future multi-tenant support).

## Authentication Model

- **Auth-required routers**: `/api/ai/*`, `/api/geo/*`, `/api/gsc/*`, `/api/*` utility endpoints.
- **Mechanism**: Bearer token via `Authorization` header, validated by `require_auth` dependency.
- **Fail-closed**: In production, if `AUTH_TOKEN` environment variable is empty or unset, all auth-required endpoints return `401 UNAUTHORIZED`.
- **Public endpoints**: Only `/api/health`.

## XSS Prevention

- Any helper that injects user-supplied text into HTML (e.g., `change_heading_text`) must HTML-escape before insertion.
- The frontend renders all API responses as text, not HTML, unless explicitly sanitized.

## Related

- API reference: [`api.md`](api.md)
- AI routing: [`ai-routing.md`](ai-routing.md)

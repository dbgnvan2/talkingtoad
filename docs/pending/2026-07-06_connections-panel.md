# Connections Panel — micro-spec (2026-07-06)

**Status:** implemented (owner-approved: explicit request + design decisions).

## Feature summary

A dedicated **Connections** modal (opened from the Results header, alongside the
existing Display Settings / GEO triggers) that lets the operator test the two
external service integrations without leaving the results view:

1. **LLM / AI provider** — runs a real round-trip against the configured provider.
2. **Google Search Console (GSC)** — checks OAuth connection status.

The existing `SettingsPanel` is display-only (font sizes); connection testing is a
distinct concern, so it lives in its own component rather than being bolted on.

## Endpoints + frontend contract

Both endpoints already exist and require bearer auth (`require_auth`). No new
endpoints were added.

| Endpoint | Method | Frontend-contract fields | Notes |
|---|---|---|---|
| `/api/ai/test` | GET | `success` (bool), `message` (str), `sample` (str, success only) | **`api_key_read` removed** from all return branches per owner decision. |
| `/api/gsc/status` | GET | `connected` (bool), `properties` (list); `configured` (bool) synthesised client-side on 503 | 503 `"GSC not configured"` when OAuth env vars unset — surfaced distinctly in the UI. |

The frontend `gscStatus()` helper already maps a 503 to
`{ connected: false, properties: [], configured: false }`; the panel treats the
three cases (connected / configured-but-not-connected / not-configured) distinctly.

## Placement decision

- New component `frontend/src/components/ConnectionsPanel.jsx` (modal, mirrors
  `SettingsPanel.jsx` shell + adds `role="dialog"`, `aria-modal`, Escape + backdrop close).
- Opened from `frontend/src/pages/Results.jsx` header via a new `showConnections`
  state + a "Connections" button placed next to the existing ⚙ / GEO buttons.
- No other navigation changed.

## Acceptance criteria → tests

### Backend (contract tests written first)

| Criterion | Test |
|---|---|
| `/api/ai/test` response has `success` + `message` and does **not** contain `api_key_read` | `tests/test_ai_test_endpoint.py::test_ai_test_response_omits_api_key_read` |
| `/api/ai/test` success path shape (`success:true`, `message`, `sample`), no `api_key_read` | `tests/test_ai_test_endpoint.py::test_ai_test_success_shape_no_api_key_read` |
| `/api/ai/test` failure path (`success:false` + message) when provider returns error sentinel, no `api_key_read` | `tests/test_ai_test_endpoint.py::test_ai_test_failure_shape_no_api_key_read` |
| `/api/gsc/status` returns `{connected, properties}` frontend contract fields | `tests/test_gsc_integration.py::TestGscStatus::test_status_response_contract_fields` |
| `/api/gsc/status` → `{connected:false, properties:[]}` when no creds | `tests/test_gsc_integration.py::TestGscStatus::test_not_connected_when_no_creds` (pre-existing) |
| `/api/gsc/status` → connected + properties when creds present | `tests/test_gsc_integration.py::TestGscStatus::test_connected_with_creds` (pre-existing) |
| `/api/gsc/status` → 503 when GSC env not configured | `tests/test_gsc_integration.py::TestOptInGuarantee::test_status_503_when_env_unset` (pre-existing) |

### Frontend

| Criterion | Test |
|---|---|
| Test LLM button calls helper and renders success state | `ConnectionsPanel.test.jsx › LLM test renders success state` |
| Test LLM button renders failure state | `ConnectionsPanel.test.jsx › LLM test renders failure state` |
| Test GSC renders connected state (properties count) | `ConnectionsPanel.test.jsx › GSC test renders connected state` |
| Test GSC renders configured-but-not-connected state | `ConnectionsPanel.test.jsx › GSC test renders not-connected state` |
| Test GSC renders not-configured (503) state | `ConnectionsPanel.test.jsx › GSC test renders not-configured state` |

## Adjacent issues noted, not fixed

- **P14 (error-as-content):** `/api/ai/test` and `analyze_with_ai` still signal
  failure via sentinel strings (`"AI analysis skipped …"`, `"Error calling …"`)
  matched by `str.startswith`. The endpoint correctly routes these to
  `success:false`, but the underlying mixed-mode `str` return is a latent P14
  pattern shared with `/api/ai/analyze`. Left as-is (out of scope for this change).

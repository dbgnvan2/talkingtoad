---
status: pending
proposed: 2026-05-29
author: System Architect
source: PLAN-V3.0.md
---

# Milestone 2 Prep: AI Router Auth Audit

## Goal
Ensure 100% authentication coverage across all AI-related endpoints before they are migrated to the `AIRouter` multi-provider orchestrator. This prevents authorization bypasses on paid LLM API calls.

## Scope
Audit the following routing modules:
* `api/routers/rewriter.py`
* `api/routers/ai.py`
* `api/routers/geo.py`
* (Verify `api/routers/advisor.py` remains secure per Cycle V).

## Execution Requirements

### 1. Structural Verification
- Check the `APIRouter` instantiation in each target file.
- Confirm whether `dependencies=[Depends(require_auth)]` is applied at the router level.
- If not applied globally, verify that *every* individual `@router.post` and `@router.get` endpoint interacting with an AI provider has the dependency explicitly declared.

### 2. Remediation
- If any AI-triggering endpoint lacks the `require_auth` dependency, apply it immediately. Prefer router-level dependencies unless a specific public webhook requires exclusion.

### 3. Contract Test Enforcement
- For every endpoint audited, verify a corresponding `test_<endpoint_name>_requires_auth` exists in the test suite.
- The test must assert a `401 Unauthorized` HTTP status when called without a valid Bearer token.
- Generate and commit any missing contract tests.

## Acceptance Criteria
1. Zero AI-related endpoints are accessible without authentication.
2. The test suite passes with all 401 assertion tests explicitly verified.

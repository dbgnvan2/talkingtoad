---
status: pending
proposed: 2026-05-28
author: System Architect
---

# Documentation Compilation: Modular Architecture Sync

## Goal
Synchronize `docs/functional-specification.md` and the automated `docs/issue-codes.md` generation with the new `api/crawler/checkers/` package structure.

## Requirements

### 1. Architectural Diagram Sync
* Update the `functional-specification.md` architecture section.
* Replace the monolithic `issue_checker.py` reference with the new Facade pattern.
* Include a list of the 11 domain modules and their primary responsibilities.

### 2. Registry Integrity & Auto-Docs
* Execute the documentation generator to ensure `docs/issue-codes.md` is rebuilt using the latest `registry.py`.
* Verify that no codes in `_ISSUE_SCORING` are missing descriptions or recommendation fields in the catalogue.

### 3. Namespace Cleanup
* Ensure any legacy references to `api/crawler/issue_checker.py` as the *source* of truth for business logic are replaced with references to the specific domain modules in `api/crawler/checkers/`.

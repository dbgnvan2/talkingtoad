# Cycle GG — Tree-Walking Validator (Answerability Audit)

## Implementation Prompt for Claude Code

### Overview

Add a "content-node depth auditor" to the extractability service that checks whether the core answer/content under `<h2>` headings is buried too deep in the HTML tree. This is a new issue code in the existing detection framework.

### Files to Create

1. **`/Users/davemini/projectsmini1/talkingtoad/api/services/extractability.py`** (NEW)
   - Contains the `ContentNodeAuditor` class with a `walk_h2_content_nodes()` method
   - Also contains an `audit_answerability(parsed_page)` entry point

### Files to Modify

2. **`/Users/davemini/projectsmini1/talkingtoad/api/crawler/issue_checker.py`**
   - Add issue code `GEO_SUMMARY_BURIED` to the `_CATALOGUE` dict
   - Add scoring entry in `_ISSUE_SCORING`
   - Add AI-readiness confidence in `_AI_READINESS_CONFIDENCE`
   - Wire the new auditor into the existing `diagnose_extractability()` function

3. **`/Users/davemini/projectsmini1/talkingtoad/frontend/src/data/issueHelp.js`**
   - Add help text for the new `GEO_SUMMARY_BURIED` code

4. **NEW test file**: **`/Users/davemini/projectsmini1/talkingtoad/tests/test_extractability.py`**

### Detailed Implementation

#### 1. ContentNodeAuditor class (`api/services/extractability.py`)

```python
"""Structural content-node depth auditor for answerability checks."""

from typing import List, Dict, Any
from bs4 import Tag, NavigableString

DECORATIVE_TAGS = {"svg", "script", "style", "noscript"}
CONTENT_TAGS = {"p", "ul", "li"}


class ContentNodeAuditor:
    """Walks the DOM under <h2> headings, counting content-node depth."""

    @staticmethod
    def walk_h2_content_nodes(soup) -> List[Dict[str, Any]]:
        """
        For each <h2> in the parsed HTML, find the first content node
        (<p>, <ul>, <li>) that follows it and report its depth (1-indexed
        content-node position).
        """
        results = []
        h2_tags = soup.find_all("h2")
        for h2 in h2_tags:
            # Gather all following siblings until the next heading
            content_count = 0
            first_content_node = None
            for sibling in h2.find_next_siblings():
                if sibling.name and sibling.name.startswith("h"):
                    # Hit next heading — stop
                    break
                if sibling.name in DECORATIVE_TAGS:
                    continue
                if sibling.name in CONTENT_TAGS:
                    content_count += 1
                    if first_content_node is None:
                        first_content_node = sibling.name
            results.append({
                "h2_text": h2.get_text(strip=True)[:80],
                "first_content_tag": first_content_node,
                "first_content_depth": content_count,
            })
        return results

    @staticmethod
    def is_answer_buried(results: List[Dict[str, Any]], threshold: int = 4) -> bool:
        """
        Returns True if any h2 section has its first content node at a depth
        >= threshold (i.e. the core answer is buried under too many intervening
        content nodes).
        """
        for r in results:
            if r["first_content_depth"] >= threshold:
                return True
        return False
```

#### 2. Wire into extractability service

In `api/services/extractability.py`, also add the existing `diagnose_extractability()` function structure that mirrors how it's called from the crawler. If `diagnose_extractability` already exists elsewhere, add a call to the auditor inside it.

**Important**: Check if `diagnose_extractability` already exists in another file (search for it first). If it does, import the auditor there instead.

#### 3. Issue code registration

In `api/crawler/issue_checker.py`, add to `_CATALOGUE`:

```python
    "GEO_SUMMARY_BURIED": {
        "id": "GEO_SUMMARY_BURIED",
        "category": "Content Structure",
        "title": "Core summary buried under content nodes",
        "description": "The page's main point is not immediately reachable — too many content nodes (p, ul, li) appear before the key information under an H2 heading.",
        "remediation": "Reorder or reduce content nodes preceding the core answer under each H2 heading.",
    },
```

Add to `_ISSUE_SCORING`:

```python
    "GEO_SUMMARY_BURIED": {"impact": "high", "weight": 8},
```

Add to `_AI_READINESS_CONFIDENCE`:

```python
    "GEO_SUMMARY_BURIED": {"confidence": "low", "reason": "Deeply buried answers reduce AI extraction reliability."},
```

#### 4. The wire-up

In the existing `diagnose_extractability()` function (wherever it lives), add:

```python
    from api.services.extractability import ContentNodeAuditor
    auditor = ContentNodeAuditor()
    h2_results = auditor.walk_h2_content_nodes(soup)
    if auditor.is_answer_buried(h2_results):
        issues.append(Issue(code="GEO_SUMMARY_BURIED", ...))
```

Match the exact Issue object pattern used by the rest of the file.

#### 5. Test file (`tests/test_extractability.py`)

Create tests that follow the project's existing test patterns. Check how existing tests are structured (look at `tests/` for conventions like asyncio markers, fixture patterns, etc.).

Test 1 (Answer Buried): Create mock HTML where the core answer is in the 5th `<p>` under an `<h2>`. Assert auditor issues `GEO_SUMMARY_BURIED`.

Test 2 (Node Filtering): Mock HTML with 3 `<svg>` icons and 1 `<p>` under an `<h2>`. Assert auditor correctly ignores SVGs and reports depth=1.

Test 3 (Clean page): Mock HTML with a well-structured page (single `<p>` per `<h2>`). Assert no false positive.

Test 4 (Registry integration): Verify `GEO_SUMMARY_BURIED` exists in `_CATALOGUE` keys.

#### 6. Frontend help text

In `frontend/src/data/issueHelp.js`, add a help entry for `GEO_SUMMARY_BURIED` matching the existing format.

### Check Before Running

1. Find where `diagnose_extractability` currently lives — search the codebase
2. Match the existing Issue object constructor pattern used in `issue_checker.py`
3. Match existing test conventions (fixtures, async markers, import patterns)

### Definition of Done

- All 4 tests pass
- Existing test suite still passes (run `pytest` from repo root)
- `GEO_SUMMARY_BURIED` appears in the issue catalogue
- The auditor correctly ignores decorative tags (svg, script, style, noscript)
- No LLM calls are made by the auditor (CPU-bound only)

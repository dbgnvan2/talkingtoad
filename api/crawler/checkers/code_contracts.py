"""Per-code contracts — the machine-checkable claim that a check actually works.

Purpose: give every issue code a contract that CI can verify, so the classes of
         defect found by the 2026-08-30 audit cannot recur silently.
Spec:    docs/pending/2026-08-30_audit-fixes.md#AF11
Tests:   tests/test_code_contracts.py

The audit found 20 defects across 170 codes. Every one belonged to a class that a
per-code contract makes impossible to reintroduce unnoticed:

  * DEAD          — the code cannot fire at all       -> POSITIVE fixture
  * STARVED       — its input is never populated      -> GUARD FIELDS + coverage
  * FALSE-POSITIVE— it fires on correct input         -> NEGATIVE fixture
  * NO EVIDENCE   — the finding names nothing         -> EVIDENCE keys

The negative fixture is the highest-value element and the one no existing test
required: `alt=""` is CORRECT markup, and nothing in 2,700 tests asserted that a
correct-looking input must stay clean.

This module derives what it can automatically (guard fields, by AST) so the
contract cannot drift from the code it describes.
"""

from __future__ import annotations

import ast
import pathlib
from functools import lru_cache

# repo root: api/crawler/checkers/code_contracts.py -> up 3
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

# Parameter names that hold a ParsedPage / ImageInfo in checker code.
# NOTE: "p" is deliberately excluded — checker code also binds `p` to a
# urlparse() result, and including it made this tool report `query` as a
# ParsedPage field. A validation tool needs the same precision it demands.
_MODEL_OWNERS = frozenset({"page", "parsed_page", "img", "image"})

# Attribute names that belong to urlparse() results, not to our models.
# `metadata.py` binds `parsed_page` to a urlparse result while using `page`
# for the actual ParsedPage, so a name-based scan cannot tell them apart.
# Excluding these keeps the tool precise instead of reporting `query` as a
# missing model field — a validation tool owes the same precision it demands.
_URLPARSE_ATTRS = frozenset({
    "scheme", "netloc", "path", "params", "query", "fragment",
    "hostname", "port", "username", "password",
})


def _model_attrs(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id in _MODEL_OWNERS):
            if n.attr not in _URLPARSE_ATTRS:
                out.add(n.attr)
    return out


@lru_cache(maxsize=1)
def guard_fields() -> dict[str, frozenset[str]]:
    """Map issue code -> model fields read by the IF-conditions that gate it.

    Scoped to the guard, not the enclosing function: a 400-line ``check_page``
    would otherwise attribute every field it touches to every code it emits, and
    the result would be noise. Verified: ``HIGH_CRAWL_DEPTH -> {crawl_depth}``,
    ``IMG_NO_SRCSET -> {width, rendered_width, has_srcset}``.
    """
    from api.crawler.checkers.registry import _CATALOGUE

    deps: dict[str, set[str]] = {}
    for path in (_REPO_ROOT / "api").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text())
        except (OSError, SyntaxError):
            continue
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child._parent = parent  # type: ignore[attr-defined]
        for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
            fn = call.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name != "make_issue" or not call.args:
                continue
            first = call.args[0]
            if not (isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                    and first.value in _CATALOGUE):
                continue
            node: ast.AST = call
            found: set[str] = set()
            while hasattr(node, "_parent"):
                parent = node._parent  # type: ignore[attr-defined]
                if isinstance(parent, (ast.If, ast.While)):
                    body = list(getattr(parent, "body", [])) + list(getattr(parent, "orelse", []))
                    if node in body:
                        found |= _model_attrs(parent.test)
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    break
                node = parent
            deps.setdefault(first.value, set()).update(found)
    return {k: frozenset(v) for k, v in deps.items()}


def codes_reading(field: str) -> list[str]:
    """Every code whose guard reads *field* — the starvation query.

    ``codes_reading("width")`` returns the four image checks that were dead
    because the crawl never collected intrinsic dimensions.
    """
    return sorted(c for c, f in guard_fields().items() if field in f)

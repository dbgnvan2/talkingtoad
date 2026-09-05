"""The code must need only what `requirements.txt` declares.

`tests/test_declared_environment.py` checks one direction — that the installed
set satisfies the file. Nothing checked the other, and on 2026-09-04 that cost a
session: `tests/test_performance_fold.py` patched `google.oauth2.credentials`,
`google-auth` is not declared, my venv happened to carry it, and CI failed on
every push for a day while I reported "the suite is green" from here. The gap is
invisible from inside a developer machine, which is exactly why it needs a test
rather than a habit.

The rule is "would this import resolve in an environment built from
requirements.txt alone" — CI installs that file and nothing else. So a
transitive of a declared package is fine (it is genuinely there), and extras are
honoured (`uvicorn[standard]` really does pull its extra's dependencies).

Tests get one exception the app does not: a test may use an undeclared package
**if the same file skips when that package is absent**. `test_gsc_integration.py`
established the pattern, per-class rather than per-file, so the tests that need
no Google library still run in the environment that ships.
"""

from __future__ import annotations

import ast
import sys
from importlib.metadata import PackageNotFoundError, packages_distributions, requires
from pathlib import Path

import pytest
from packaging.markers import UndefinedEnvironmentName
from packaging.requirements import Requirement

_ROOT = Path(__file__).resolve().parent.parent
_FIRST_PARTY = {"api", "tests", "scripts", "conftest"}


def _canon(name: str) -> str:
    return name.lower().replace("_", "-")


def _declared() -> list[Requirement]:
    out = []
    for line in (_ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line and not line.startswith("-"):
            out.append(Requirement(line))
    return out


def _installable_closure() -> set[str]:
    """Distributions a `pip install -r requirements.txt` would end up with.

    Extras matter: `uvicorn[standard]` really does install its extra's
    dependencies, and treating every marker-gated requirement as absent would
    make the guard cry wolf. Markers that depend on anything other than `extra`
    (python_version, sys_platform) are treated as satisfiable — this test cannot
    know CI's platform, and guessing would be worse than being generous.
    """
    seen: set[str] = set()
    stack: list[tuple[str, frozenset[str]]] = [
        (_canon(r.name), frozenset(r.extras)) for r in _declared()
    ]
    while stack:
        name, extras = stack.pop()
        key = name
        if key in seen and not extras:
            continue
        seen.add(key)
        try:
            reqs = requires(name) or []
        except PackageNotFoundError:
            continue
        for raw in reqs:
            try:
                req = Requirement(raw)
            except Exception:  # noqa: BLE001 — a malformed pin must not break the guard
                continue
            if req.marker is not None:
                try:
                    keep = any(req.marker.evaluate({"extra": e}) for e in extras or {""})
                except UndefinedEnvironmentName:
                    keep = True
                except Exception:  # noqa: BLE001
                    keep = True
                if not keep:
                    continue
            stack.append((_canon(req.name), frozenset(req.extras)))
    return seen


def _is_type_checking_block(node: ast.AST) -> bool:
    test = getattr(node, "test", None)
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _catches_import_error(node: ast.Try) -> bool:
    for handler in node.handlers:
        exc = handler.type
        names = []
        if isinstance(exc, ast.Name):
            names = [exc.id]
        elif isinstance(exc, ast.Tuple):
            names = [e.id for e in exc.elts if isinstance(e, ast.Name)]
        if any(n in {"ImportError", "ModuleNotFoundError", "Exception"} for n in names):
            return True
    return False


def _external_modules(path: Path, *, module_level_only: bool = False) -> set[str]:
    """Top-level third-party modules a file imports OR patches by string.

    `patch("google.oauth2.credentials.Credentials")` needs the package just as
    much as an import does, and that is the form that caused the outage — an
    import-only scan would have missed it entirely.

    ``module_level_only`` is the distinction that makes this usable on `api/`.
    A module-level import of a missing package is an ImportError at startup; an
    import inside a function is a feature that can degrade — `gsc.py` imports
    Google libraries only inside handlers and answers 503 when they are absent,
    and `js_renderer.py` does the same behind a `playwright_available` flag.
    Flagging those would demand declaring every optional dependency, which is
    the opposite of what the Dockerfile does, and the guard would be turned off.
    `if TYPE_CHECKING:` blocks never execute and are skipped.
    """
    mods: set[str] = set()

    def _add_import(node):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])

    def _walk(nodes, *, executing: bool):
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if executing:
                    _add_import(node)
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                _walk(node.body, executing=executing and not module_level_only)
                continue
            if isinstance(node, ast.If) and _is_type_checking_block(node):
                _walk(node.orelse, executing=executing)
                continue
            if isinstance(node, ast.Try) and _catches_import_error(node):
                # `try: import x / except ImportError: HAS_X = False` is a
                # module-level import that is EXPLICITLY optional — the module
                # still loads without the package. js_renderer.py does exactly
                # this for playwright, which the Dockerfile installs separately
                # from requirements.txt. The body is skipped; the handlers and
                # else-branch are still walked, because an import there is not
                # guarded by anything.
                _walk(node.handlers, executing=executing)
                _walk(node.orelse, executing=executing)
                _walk(node.finalbody, executing=executing)
                continue
            for child in ast.iter_child_nodes(node):
                _walk([child], executing=executing)

    tree = ast.parse(path.read_text())
    _walk(tree.body, executing=True)

    if not module_level_only:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                fname = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if fname in {"patch", "patch_object"} and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        if "." in first.value:
                            mods.add(first.value.split(".")[0])

    return {
        m for m in mods
        if m not in _FIRST_PARTY
        and m not in sys.stdlib_module_names
        and not m.startswith("_")
    }


def _undeclared(path: Path, closure: set[str], *,
                module_level_only: bool = False) -> dict[str, list[str]]:
    dist_map = packages_distributions()
    out: dict[str, list[str]] = {}
    for mod in sorted(_external_modules(path, module_level_only=module_level_only)):
        dists = {_canon(d) for d in dist_map.get(mod, [])}
        if not dists:
            # Not importable here at all — the local venv cannot answer, so this
            # is reported rather than silently passed.
            out[mod] = []
        elif not (dists & closure):
            out[mod] = sorted(dists)
    return out


def _guards(path: Path, module: str) -> bool:
    """Does the file skip when *module* is absent?

    Deliberately per-module: guarding on `googleapiclient` while patching
    `google.*` is the shape that let the outage through, and it reads as covered.
    """
    text = path.read_text()
    return any(
        f'{fn}("{module}"' in text or f"{fn}('{module}'" in text
        for fn in ("find_spec", "importorskip")
    )


_CLOSURE = _installable_closure()
_API_FILES = sorted((_ROOT / "api").rglob("*.py"))
_TEST_FILES = sorted((_ROOT / "tests").glob("*.py"))


@pytest.mark.parametrize("path", _API_FILES, ids=lambda p: p.name)
def test_the_app_imports_only_what_requirements_declares(path):
    """Runtime code gets no skip-guard exception: an import that is not there is
    an ImportError in production, not a skipped test."""
    bad = _undeclared(path, _CLOSURE, module_level_only=True)
    assert not bad, (
        f"{path.relative_to(_ROOT)} imports {list(bad)} AT MODULE LEVEL, which "
        f"`pip install -r requirements.txt` would not provide "
        f"(distributions: {bad}). Declare it, or stop importing it."
    )


@pytest.mark.parametrize("path", _TEST_FILES, ids=lambda p: p.name)
def test_the_tests_import_only_what_is_declared_or_guarded(path):
    """A test may use an undeclared package only if it skips without it."""
    unguarded = {
        mod: dists for mod, dists in _undeclared(path, _CLOSURE).items()
        if not _guards(path, mod)
    }
    assert not unguarded, (
        f"{path.relative_to(_ROOT)} uses {list(unguarded)} (distributions: "
        f"{unguarded}), which CI does not install, and does not skip without "
        f"them. Either declare the package, or guard THIS module name with "
        f"`importlib.util.find_spec(\"<module>\")` / `pytest.importorskip`."
    )


# ── The guard on the guard ──────────────────────────────────────────────────


def test_the_check_rejects_an_undeclared_import(tmp_path):
    """Without this, the two tests above could be `assert True` and read as rigour.

    Feeds the checker a file importing a package that is real, installed, and
    NOT reachable from requirements.txt — the exact shape of the outage.
    """
    f = tmp_path / "test_pretend.py"
    f.write_text("import googleapiclient\n")
    assert "googleapiclient" in _undeclared(f, _CLOSURE), (
        "the checker accepted an import CI cannot satisfy"
    )


def test_the_check_sees_a_patch_target_not_only_an_import(tmp_path):
    """The outage arrived as a `patch("google.oauth2…")` string, not an import.
    A scan that only walked import statements would have missed it."""
    f = tmp_path / "test_pretend.py"
    f.write_text('from unittest.mock import patch\n'
                 'patch("google.oauth2.credentials.Credentials")\n')
    assert "google" in _undeclared(f, _CLOSURE)


def test_a_guarded_module_is_accepted(tmp_path):
    """The other direction: the exception must actually work, or every properly
    guarded optional-dependency test becomes a failure."""
    f = tmp_path / "test_pretend.py"
    f.write_text('import importlib.util\n'
                 'x = importlib.util.find_spec("googleapiclient")\n'
                 'import googleapiclient\n')
    assert _guards(f, "googleapiclient")


def test_a_guard_on_a_different_module_does_not_count(tmp_path):
    """The precise shape that let the outage through: guarding `googleapiclient`
    while using `google.*` reads as covered and is not."""
    f = tmp_path / "test_pretend.py"
    f.write_text('import importlib.util\n'
                 'x = importlib.util.find_spec("googleapiclient")\n'
                 'from unittest.mock import patch\n'
                 'patch("google.oauth2.credentials.Credentials")\n')
    assert not _guards(f, "google"), "a guard on a sibling module was accepted"


def test_the_closure_honours_declared_extras():
    """`uvicorn[standard]` really does install its extra's dependencies.

    Treating every marker-gated requirement as absent would make the guard cry
    wolf on a dozen packages and get it switched off — which is how a guard
    dies. Pinned so a future simplification of the closure fails loudly.
    """
    assert any(r.extras for r in _declared()), "no extras declared — update this test"
    assert "click" in _CLOSURE, "uvicorn[standard]'s dependencies are missing from the closure"

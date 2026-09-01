"""The app must import on the Python and the dependency set it ships on.

Class this guards (Cycle 4, bug-class elimination):
    3,426 tests passed on the dev interpreter (3.14) while `api.main` could not
    import at all on the pinned one (Dockerfile: python:3.11-slim), for two
    independent reasons:

      1. api/routers/advisor.py annotated `store: SQLiteJobStore` without
         importing the name. Annotations are evaluated at def-time before
         Python 3.14; PEP 649 made them lazy in 3.14, so the dev box sees
         nothing and 3.11 raises NameError at import. This is the same class as
         the 2026-08-13 production bug, whose fix added
         test_checker_modules_import_before_any_def -- scoped to CHECKER
         modules. Routers were never covered (P5/P12: the guard was written for
         one member of the class).

      2. api/services/gsc_client.py imported google-* at module level while
         those packages are in neither requirements.txt nor the Dockerfile, so
         an OPTIONAL feature's missing library took down the whole app --
         contradicting gsc.py's own promise that without GSC configured
         "TalkingToad behaves exactly as before".

Why these checks are static, not `import every module`:
    A runtime import sweep passes on 3.14 and is blind to the entire
    annotation class -- it would have certified this app as healthy on the
    morning it could not boot. Static analysis fails on the developer's own
    machine, which is where a guard has to be red to be useful. It also means
    the check works without installing the shipping dependency set.

Spec: docs/pending/2026-08-31_shipping-runtime-parity.md
"""

from __future__ import annotations

import ast
import builtins
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
API = REPO / "api"
BUILTIN_NAMES = set(dir(builtins))
STDLIB = set(sys.stdlib_module_names)

# Third-party packages imported at module level but deliberately NOT in
# requirements.txt. Each needs a reason: an unexplained entry here is how this
# check gets hollowed out.
_UNDECLARED_BY_DESIGN = {
    # Installed separately by Dockerfile:43 so the image can stay small without
    # it. js_renderer degrades gracefully when it is absent, and three
    # rendering checks simply do not fire.
    "playwright",
}


def _api_module_name(p: Path) -> str:
    rel = p.relative_to(REPO)
    return ".".join((rel.parent if p.name == "__init__.py" else rel.with_suffix("")).parts)


def _modules() -> dict[str, Path]:
    return {_api_module_name(p): p for p in sorted(API.rglob("*.py"))}


def _has_future_annotations(tree: ast.Module) -> bool:
    return any(
        isinstance(n, ast.ImportFrom)
        and n.module == "__future__"
        and any(a.name == "annotations" for a in n.names)
        for n in tree.body
    )


def _bound_names(tree: ast.Module) -> set[str]:
    """Names bound at MODULE SCOPE and available when annotations evaluate.

    Deliberately not `ast.walk`. An earlier version walked the whole tree, so
    any binding anywhere counted, and two live routes back to the bug slipped
    through — both proven to leave the check green while the module raised
    NameError on 3.11:

      - `if TYPE_CHECKING: from x import Y` — exactly what a type checker
        tells you to do with an annotation-only import, and False at runtime.
      - a function-local import — which is the very remedy applied to
        gsc_client.py in the same commit as this file.

    Function bodies are skipped for the same reason: a name bound inside a
    function is not available when a module-level def evaluates its
    annotations. `try/except ImportError` at module level DOES bind, so it is
    walked.
    """
    names: set[str] = set()

    def visit(body):
        for node in body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)          # the name, NOT the body
            elif isinstance(node, ast.Assign):
                names.update(x.id for x in node.targets if isinstance(x, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node, ast.If):
                if _is_type_checking_guard(node.test):
                    visit(node.orelse)        # the body never runs
                else:
                    visit(node.body)
                    visit(node.orelse)
            elif isinstance(node, ast.Try):
                visit(node.body)
                visit(node.orelse)
                visit(node.finalbody)
                for h in node.handlers:
                    visit(h.body)

    visit(tree.body)
    return names


def _import_time_annotations(tree: ast.Module) -> list[ast.expr]:
    """Annotations evaluated when the module is imported.

    Module-level defs and defs inside module-level classes. A def nested in a
    function does not evaluate its annotations until that function runs, so it
    cannot break startup.
    """
    out: list[ast.expr] = []

    def visit(body):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = n.args
                for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                    if a.annotation is not None:
                        out.append(a.annotation)
                if n.returns is not None:
                    out.append(n.returns)
            elif isinstance(n, ast.ClassDef):
                visit(n.body)
            elif isinstance(n, ast.AnnAssign) and n.annotation is not None:
                out.append(n.annotation)

    visit(tree.body)
    return out


def _unresolved_annotation_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    if _has_future_annotations(tree):
        # PEP 563: annotations are strings and never evaluated. Nothing here
        # can raise at import, whatever it names.
        return set()
    bound = _bound_names(tree) | BUILTIN_NAMES
    bad: set[str] = set()
    for ann in _import_time_annotations(tree):
        # A string annotation is a forward reference -- also never evaluated.
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            continue
        bad |= {n.id for n in ast.walk(ann) if isinstance(n, ast.Name)} - bound
    return bad


class TestAnnotationsResolveAtImportTime:
    def test_every_annotation_name_is_resolvable(self):
        offenders = {}
        for mod, path in _modules().items():
            bad = _unresolved_annotation_names(path)
            if bad:
                offenders[str(path.relative_to(REPO))] = sorted(bad)
        assert not offenders, (
            "Annotation names that are never imported. These evaluate at "
            "def-time on Python < 3.14 (the Dockerfile pins 3.11), so the "
            "module raises NameError at import and the app does not start. "
            "Python 3.14 makes annotations lazy, which is why this is "
            f"invisible on the dev interpreter:\n{offenders}"
        )

    def test_adversarial_the_check_catches_a_lazy_annotation_on_this_interpreter(self, tmp_path):
        """The whole point: flagged on 3.14, where the interpreter will not
        complain. Without this, the check could silently depend on the runtime
        and be worthless exactly where it is run."""
        p = tmp_path / "m.py"
        p.write_text("def f(x: NeverImported) -> None: ...\n")
        assert _unresolved_annotation_names(p) == {"NeverImported"}

    def test_adversarial_deferred_annotations_are_not_flagged(self, tmp_path):
        """Guards the guard. `from __future__ import annotations` and string
        forward references never evaluate, so flagging them would be a false
        positive -- and a check that cries wolf gets switched off."""
        future = tmp_path / "a.py"
        future.write_text("from __future__ import annotations\ndef f(x: NeverImported) -> None: ...\n")
        assert _unresolved_annotation_names(future) == set()

        stringy = tmp_path / "b.py"
        stringy.write_text('def f(x: "NeverImported") -> None: ...\n')
        assert _unresolved_annotation_names(stringy) == set()

    def test_adversarial_a_nested_def_does_not_break_startup(self, tmp_path):
        """A def inside a function evaluates its annotations only when that
        function runs, so it cannot prevent import. Flagging it would push
        people to silence the check."""
        p = tmp_path / "c.py"
        p.write_text("def outer():\n    def inner(x: NeverImported) -> None: ...\n    return inner\n")
        assert _unresolved_annotation_names(p) == set()


def _walk_import_closure() -> tuple[dict[str, set[str]], set[str]]:
    """Walk api.main's import closure ONCE and return (third_party, modules_seen).

    Both tests below consume this. An earlier version had the coverage guard
    re-implement the walk in its own body, so the guard passed over a broken
    walk -- it was checking its own copy, not the one under test. Returning
    both values from a single traversal makes that impossible.
    """
    if True:
        files = _modules()
        seen: set[str] = set()
        queue = ["api.main"]
        third: dict[str, set[str]] = {}
        while queue:
            mod = queue.pop()
            if mod in seen or mod not in files:
                continue
            seen.add(mod)
            tree = ast.parse(files[mod].read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("api"):
                    queue.append(n.module)
                    # `from api.routers import gsc` -> api.routers.gsc
                    queue.extend(f"{n.module}.{a.name}" for a in n.names)
                elif isinstance(n, ast.Import):
                    queue.extend(a.name for a in n.names if a.name.startswith("api"))
            for top in _module_level_import_roots(tree):
                if top not in STDLIB and not top.startswith("api"):
                    third.setdefault(top, set()).add(mod)
    return third, seen


class TestTheAppOnlyNeedsDeclaredDependencies:
    def _closure_third_party(self) -> dict[str, set[str]]:
        return _walk_import_closure()[0]

    def test_importing_the_app_needs_only_declared_dependencies(self):
        declared = _declared_importable_names()
        offenders = {
            pkg: sorted(users)
            for pkg, users in sorted(self._closure_third_party().items())
            if pkg not in declared and pkg not in _UNDECLARED_BY_DESIGN
        }
        assert not offenders, (
            "Modules api.main imports pull in packages that requirements.txt "
            "does not declare. The Docker image installs requirements.txt (plus "
            "playwright) and nothing else, so these raise ModuleNotFoundError "
            "at startup:\n"
            + "\n".join(f"  {p} <- {u}" for p, u in offenders.items())
            + "\n\nEither declare the package, or import it lazily so the "
            "feature degrades instead of the application failing to boot."
        )

    def test_the_closure_actually_reaches_the_routers(self):
        """Guards the guard, by consuming the SAME walk the test above uses.

        The first version of this walk queued `api.routers` for
        `from api.routers import gsc` and never reached the module with the
        undeclared import, reporting a clean result over the live bug. An
        earlier version of THIS test re-implemented the walk correctly in its
        own body, so it stayed green while the real one was broken -- it was
        asserting about its own copy.
        """
        _, seen = _walk_import_closure()
        assert "api.services.gsc_client" in seen, (
            "the import closure no longer reaches gsc_client -- the dependency "
            "check above is blind to whatever else it now misses"
        )
        assert len(seen) > 100, f"closure suspiciously small: {len(seen)} modules"

def _module_level_import_roots(tree: ast.Module) -> list[str]:
    """Top-level package names imported in the module body.

    Includes try/except and if bodies -- those still execute at import. Excludes
    imports inside functions, which is exactly the lazy-import escape hatch a
    module uses to make a dependency optional.
    """
    out: list[str] = []

    def walk(body):
        for n in body:
            if isinstance(n, ast.Import):
                out.extend(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                out.append(n.module.split(".")[0])
            elif isinstance(n, ast.If) and _is_type_checking_guard(n.test):
                # `if TYPE_CHECKING:` is False at runtime, so these imports
                # never execute. Skipping the body is not a loophole: the else
                # branch still counts, and anything the module actually uses at
                # runtime has to be imported somewhere that does execute.
                walk(n.orelse)
            elif isinstance(n, (ast.Try, ast.If)):
                walk(n.body)
                walk(n.orelse)
                walk(getattr(n, "finalbody", []))
                for h in getattr(n, "handlers", []):
                    walk(h.body)

    walk(tree.body)
    return out


def _is_type_checking_guard(test: ast.expr) -> bool:
    """`TYPE_CHECKING` or `typing.TYPE_CHECKING` — and nothing looser."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _declared_importable_names() -> set[str]:
    """Import names for everything requirements.txt declares.

    Distribution name != import name for several of these, so the mapping is
    explicit rather than guessed.
    """
    alias = {
        "beautifulsoup4": "bs4",
        "python_json_logger": "pythonjsonlogger",
        "python_dotenv": "dotenv",
        "pillow": "PIL",
        "fpdf2": "fpdf",
        "python_multipart": "multipart",
    }
    declared: set[str] = set()
    for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        dist = re.split(r"[~=<>\[]", line)[0].lower().replace("-", "_")
        declared.add(dist)
        declared.add(alias.get(dist, dist))
    return declared


class TestTheDependencyCheckDiscriminates:
    """`if TYPE_CHECKING:` is skipped because it does not execute. That
    exemption must stay narrow, or it becomes the way undeclared runtime
    dependencies get smuggled past this check.
    """

    def test_adversarial_a_type_checking_import_is_exempt(self):
        tree = ast.parse(
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    import nonexistent_pkg\n"
        )
        assert "nonexistent_pkg" not in _module_level_import_roots(tree)

    def test_adversarial_a_real_module_level_import_is_still_caught(self):
        """The same package, imported for real, must be flagged. Without this
        the exemption above could be widened until nothing is checked."""
        tree = ast.parse("import nonexistent_pkg\n")
        assert "nonexistent_pkg" in _module_level_import_roots(tree)

    def test_adversarial_a_try_guarded_import_is_still_caught(self):
        """try/except ImportError DOES execute at import time. A package
        imported that way is still required for the module to load cleanly, so
        it must stay declared — this is not the lazy-import escape hatch."""
        tree = ast.parse(
            "try:\n    import nonexistent_pkg\nexcept ImportError:\n    nonexistent_pkg = None\n"
        )
        assert "nonexistent_pkg" in _module_level_import_roots(tree)

    def test_adversarial_an_import_inside_a_function_is_exempt(self):
        """The actual fix applied to gsc_client: a function-local import makes
        the dependency genuinely optional."""
        tree = ast.parse("def f():\n    import nonexistent_pkg\n    return nonexistent_pkg\n")
        assert "nonexistent_pkg" not in _module_level_import_roots(tree)


class TestTheAnnotationCheckHasNoEscapeHatches:
    """Both of these left the check green while the module raised NameError on
    the pinned 3.11. They are the two routes a well-meaning change takes.
    """

    def test_adversarial_a_type_checking_only_import_does_not_satisfy_an_annotation(self, tmp_path):
        """What a type checker tells you to do with an annotation-only import.
        TYPE_CHECKING is False at runtime, so the name is absent when a
        module-level def evaluates its annotations."""
        p = tmp_path / "a.py"
        p.write_text(
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    from decimal import Decimal\n"
            "def f(x: Decimal) -> None: ...\n"
        )
        assert _unresolved_annotation_names(p) == {"Decimal"}

    def test_adversarial_a_function_local_import_does_not_satisfy_an_annotation(self, tmp_path):
        """The exact remedy applied to gsc_client.py in the same commit as this
        file — correct there, and not a substitute for a module-level import
        when a module-level annotation needs the name."""
        p = tmp_path / "b.py"
        p.write_text(
            "def _lazy():\n    from decimal import Decimal\n    return Decimal\n"
            "def f(x: Decimal) -> None: ...\n"
        )
        assert _unresolved_annotation_names(p) == {"Decimal"}

    def test_adversarial_a_module_level_try_import_does_satisfy_it(self, tmp_path):
        """The inverse: `try: import x / except ImportError:` DOES run at
        import, so it must NOT be flagged, or the check pushes people to
        silence it."""
        p = tmp_path / "c.py"
        p.write_text(
            "try:\n    from decimal import Decimal\nexcept ImportError:\n    Decimal = None\n"
            "def f(x: Decimal) -> None: ...\n"
        )
        assert _unresolved_annotation_names(p) == set()

"""The code declares what it imports, and pyproject.toml declares nothing it does not use (ADR-0052).

Every top-level import of `src/agency` and `tests` is mapped to the distributions that provide it, with
`importlib.metadata.packages_distributions()`. An engine import needs a runtime dependency, since the API
image installs only those. A test import may use a dev dependency too. A top-level name that several
distributions share, such as `langgraph` or `opentelemetry`, counts as declared when one of them is. The
vendored QA scripts run in the toolchain's own Python and are left out.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

from agency.config import REPO_ROOT

PROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
SRC = REPO_ROOT / "src"
TESTS = REPO_ROOT / "tests"
VENDORED = SRC / "agency" / "qa" / "scripts"
# Run as commands or read by pyright, never imported.
TOOLS = {"ruff", "pyright", "import-linter", "django-stubs"}


def canonical(name: str) -> str:
    """A distribution name in the form PEP 503 compares."""
    return re.sub(r"[-_.]+", "-", name).lower()


def declared(requirements: list[str]) -> set[str]:
    names = (re.match(r"[A-Za-z0-9._-]+", requirement) for requirement in requirements)
    return {canonical(name[0]) for name in names if name}


RUNTIME = declared(PROJECT["project"]["dependencies"])
DEV = declared(PROJECT["dependency-groups"]["dev"])


def top_level(folder: Path) -> set[str]:
    """The names of the modules and packages directly under `folder`."""
    return {
        path.stem for path in folder.iterdir() if path.suffix == ".py" or (path / "__init__.py").is_file()
    }


def imports(folder: Path, own: set[str], skip: Path | None = None) -> dict[str, str]:
    """Each third-party top-level name imported under `folder`, with the first file that imports it.

    The standard library, relative imports and the project's `own` modules are left out.
    """
    found: dict[str, str] = {}
    for path in sorted(folder.rglob("*.py")):
        if skip is not None and path.is_relative_to(skip):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                name = module.partition(".")[0]
                if name not in sys.stdlib_module_names and name not in own:
                    found.setdefault(name, path.relative_to(folder).as_posix())
    return found


PROVIDERS = {
    name: {canonical(dist) for dist in dists} for name, dists in metadata.packages_distributions().items()
}
OWN = top_level(SRC) | top_level(TESTS)
ENGINE = imports(SRC, OWN, skip=VENDORED)
TESTED = imports(TESTS, OWN)


def test_the_engine_imports_only_runtime_dependencies() -> None:
    missing = {name: where for name, where in ENGINE.items() if not PROVIDERS.get(name, set()) & RUNTIME}
    assert missing == {}, f"declare them with uv add: {missing}"


def test_the_tests_import_only_declared_dependencies() -> None:
    missing = {
        name: where for name, where in TESTED.items() if not PROVIDERS.get(name, set()) & (RUNTIME | DEV)
    }
    assert missing == {}, f"declare them with uv add --dev, or uv add if the engine needs them: {missing}"


def test_every_declared_dependency_is_imported() -> None:
    """A runtime dependency is imported by the engine; a dev dependency by the tests, unless it is a tool."""
    engine = {dist for name in ENGINE for dist in PROVIDERS.get(name, set())}
    tests = {dist for name in TESTED for dist in PROVIDERS.get(name, set())}
    assert RUNTIME - engine == set(), "nothing in src/ imports them: remove them with uv remove"
    assert DEV - tests - TOOLS == set(), "nothing in tests/ imports them: remove them with uv remove --dev"
    assert TOOLS <= DEV


def test_the_check_reads_imports_but_not_the_stdlib_relative_or_own_modules(tmp_path: Path) -> None:
    (tmp_path / "own").mkdir()
    (tmp_path / "own" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "helper.py").write_text("", encoding="utf-8")
    (tmp_path / "sample.py").write_text(
        "import json\n"
        "import yaml.loader\n"
        "from requests import get\n"
        "from . import sibling\n"
        "from own import thing\n"
        "import helper\n",
        encoding="utf-8",
    )
    assert imports(tmp_path, top_level(tmp_path)) == {"yaml": "sample.py", "requests": "sample.py"}

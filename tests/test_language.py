"""Comments and docstrings are in English (CLAUDE.md; Phase 3 of docs/audit/PLAN.md).

The words the check looks for are Italian and never English, so a comment or a docstring that holds one
is Italian. Comments are read with `tokenize` and docstrings with `ast`: a string the code prints, stores or
sends to the model never matches, and those strings stay Italian on purpose. The vendored QA scripts and the
frozen migrations are left out.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

from agency.config import REPO_ROOT

# The English prefix "non-" (as in "non-root") is no match: the Italian word never takes a hyphen.
ITALIAN = re.compile(
    r"\b(che|non(?!-)|della|delle|nella|perché|sono|questo|questa|degli|alla|senza|quando|viene)\b",
    re.IGNORECASE,
)
FROZEN = ("src/agency/qa/scripts/", "src/agency/ledger/migrations/versions/")
DOCUMENTED = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def italian(path: Path, root: Path) -> list[str]:
    """Each comment and docstring of the file that holds an Italian word, as `<path>:<line> <kind>`."""
    text = path.read_text(encoding="utf-8")
    where = path.relative_to(root).as_posix()
    found = [
        f"{where}:{token.start[0]} comment"
        for token in tokenize.generate_tokens(io.StringIO(text).readline)
        if token.type == tokenize.COMMENT and ITALIAN.search(token.string)
    ]
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, DOCUMENTED) and (doc := ast.get_docstring(node)) and ITALIAN.search(doc):
            found.append(f"{where}:{node.body[0].lineno} docstring")
    return found


def sources() -> list[Path]:
    """The Python files of the engine and of the tests, without the vendored and the frozen ones."""
    files = [
        *sorted((REPO_ROOT / "src" / "agency").rglob("*.py")),
        *sorted((REPO_ROOT / "tests").rglob("*.py")),
    ]
    return [path for path in files if not path.relative_to(REPO_ROOT).as_posix().startswith(FROZEN)]


def test_comments_and_docstrings_are_in_english() -> None:
    found = [line for path in sources() for line in italian(path, REPO_ROOT)]
    assert found == [], "Italian in comments or docstrings; translate them:\n" + "\n".join(found)


def test_the_check_reads_comments_and_docstrings_but_not_strings(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        '"""Questa docstring è italiana."""\n'
        'TEXT = "un testo che resta in italiano"\n'
        "# un commento che non va\n",
        encoding="utf-8",
    )
    assert italian(sample, tmp_path) == ["sample.py:3 comment", "sample.py:1 docstring"]


def test_the_frozen_and_vendored_files_are_the_only_ones_left_out() -> None:
    left_out = {path for path in (REPO_ROOT / "src" / "agency").rglob("*.py")} - set(sources())
    assert left_out
    assert all(path.relative_to(REPO_ROOT).as_posix().startswith(FROZEN) for path in left_out)

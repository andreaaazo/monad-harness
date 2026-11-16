"""Tests of the checks `coverage` and `diff-coverage` (SPEC §7.4, §8.6)."""

from pathlib import Path

from quality_gate.checks import covered, diff_coverage, suite
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status
from quality_gate.tests.conftest import commit_all
from quality_gate.tests.fakes import with_fakes, write_file, write_tool

CONFIG = (
    '[tool.coverage.run]\n'
    'branch = true\n'
    'source = ["."]\n'
    'relative_files = true\n'
    '\n'
    '[tool.coverage.report]\n'
    'fail_under = 100\n'
)
MODULE = (
    'def sign(number):\n'
    '    if number > 0:\n'
    "        return 'plus'\n"
    "    return 'other'\n"
)
HALF = (
    'from pkg.m import sign\n'
    '\n'
    '\n'
    'def test_plus():\n'
    "    assert sign(1) == 'plus'\n"
)
BOTH = f"{HALF}\n\ndef test_other():\n    assert sign(0) == 'other'\n"
FILES = ('pkg/__init__.py', 'pkg/m.py', 'tests/test_m.py')
SCRIPT = '#!/usr/bin/env python3\nVALUE = 1\n'


def _project(root: Path, tests: str, module: str = MODULE) -> None:
    write_file(root, 'pyproject.toml', CONFIG)
    write_file(root, 'pkg/__init__.py', '')
    write_file(root, 'pkg/m.py', module)
    write_file(root, 'tests/test_m.py', tests)


def _given(runner: Runner, files: tuple[str, ...] = FILES) -> CheckInput:
    return CheckInput(runner=runner, files=files)


def _suite(repository: Runner) -> Path:
    workspace = repository.root.parent
    assert suite.run(repository, workspace).status is Status.PASS
    return workspace


def _found(
    repository: Runner,
    *,
    whole: bool,
    files: tuple[str, ...] = FILES,
) -> tuple[Status, list[str]]:
    outcome = covered.run(
        _given(repository, files),
        _suite(repository),
        required=files,
        whole=whole,
    )
    return outcome.status, [found.render() for found in outcome.violations]


def test_coherent_sets_pass_in_changed(repository: Runner) -> None:
    """In `changed`, partial coverage passes when the file sets agree.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, HALF)
    assert _found(repository, whole=False) == (Status.PASS, [])


def test_partial_coverage_fails_in_full(repository: Runner) -> None:
    """In `full`, a missed line and a missed branch fail, by name.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, HALF)
    assert _found(repository, whole=True) == (
        Status.FAIL,
        ['pkg/m.py:1:1 not-covered lines [4], branches [[2, 4]]'],
    )


def test_full_coverage_passes_in_full(repository: Runner) -> None:
    """Every line and branch run: the whole check passes.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, BOTH)
    assert _found(repository, whole=True) == (Status.PASS, [])


def test_an_ignored_module_fails_coherence(repository: Runner) -> None:
    """A module git ignores, yet the tests import, is a hidden path.

    Args:
        repository: A fresh repository.
    """
    root = repository.root
    write_file(root, '.gitignore', 'hidden/\n')
    write_file(root, 'hidden/helper.py', 'VALUE = 1\n')
    _project(root, f'from hidden.helper import VALUE\n{BOTH}')
    reason = 'measured, but not a file the gate sees'
    assert _found(repository, whole=False) == (
        Status.FAIL,
        [f'hidden/helper.py:1:1 not-discovered {reason}'],
    )


def test_a_never_imported_file_fails_in_full(repository: Runner) -> None:
    """In `full`, a discovered file no test imports counts as 0%; a stub not.

    A script without a suffix is discovered by its shebang, and counts too.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'scripts/tool.py', 'VALUE = 1\n')
    write_file(repository.root, 'scripts/run', SCRIPT)
    _project(repository.root, BOTH)
    files = (*FILES, 'scripts/run', 'scripts/tool.py', 'pkg/types.pyi')
    assert _found(repository, whole=True, files=files) == (
        Status.FAIL,
        [
            'scripts/run:1:1 never-imported no test ever imports it',
            'scripts/tool.py:1:1 never-imported no test ever imports it',
        ],
    )


def test_a_changed_module_nothing_imports_fails(
    repository: Runner,
) -> None:
    """In `changed`, a changed file no test imports fails; an unchanged not.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'scripts/tool.py', 'VALUE = 1\n')
    _project(repository.root, HALF)
    files = (*FILES, 'scripts/tool.py')
    workspace = _suite(repository)
    statuses = [
        covered.run(
            _given(repository, files),
            workspace,
            required=required,
            whole=False,
        ).status
        for required in (('pkg/m.py', 'NOTES.md'), ('scripts/tool.py',))
    ]
    assert statuses == [Status.PASS, Status.FAIL]


def test_no_coverage_data_is_an_error(repository: Runner) -> None:
    """Without the suite's data there is nothing to judge.

    Args:
        repository: A fresh repository.
    """
    write_file(repository.root, 'pyproject.toml', CONFIG)
    outcome = covered.run(
        _given(repository),
        repository.root.parent,
        required=FILES,
        whole=True,
    )
    assert outcome.status is Status.ERROR


def test_a_report_without_files_is_an_error(
    repository: Runner,
    scripts: Path,
) -> None:
    """A coverage report that lists no files cannot be judged.

    Args:
        repository: A fresh repository.
        scripts: A scripts folder with a coverage that writes `{}`.
    """
    body = (
        'import pathlib, sys\n'
        "if '-o' in sys.argv:\n"
        "    pathlib.Path(sys.argv[-1]).write_text('{}')\n"
    )
    write_tool(scripts, 'coverage', body)
    runner = with_fakes(repository, scripts)
    outcome = covered.run(
        _given(runner),
        repository.root.parent,
        required=FILES,
        whole=False,
    )
    assert (outcome.status, outcome.raw) == (
        Status.ERROR,
        'coverage wrote a report with no files',
    )


def test_an_untested_branch_fails_diff_coverage(repository: Runner) -> None:
    """A branch added since the base, and never run, fails.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, BOTH)
    commit_all(repository)
    added = MODULE.replace(
        "    return 'other'\n",
        "    if number < 0:\n        return 'minus'\n    return 'other'\n",
    )
    write_file(repository.root, 'pkg/m.py', added)
    workspace = _suite(repository)
    coverage = covered.run(
        _given(repository), workspace, required=FILES, whole=False
    )
    assert coverage.status is Status.PASS
    outcome = diff_coverage.run(repository, workspace, 'HEAD')
    assert outcome.status is Status.FAIL
    assert {found.path for found in outcome.violations} == {'pkg/m.py'}


def test_tested_changes_pass_diff_coverage(repository: Runner) -> None:
    """Changed lines that the tests run pass.

    Args:
        repository: A fresh repository.
    """
    _project(repository.root, BOTH)
    commit_all(repository)
    renamed = MODULE.replace("'plus'", "'positive'")
    _project(repository.root, BOTH.replace("'plus'", "'positive'"), renamed)
    workspace = _suite(repository)
    coverage = covered.run(
        _given(repository), workspace, required=FILES, whole=False
    )
    assert coverage.status is Status.PASS
    outcome = diff_coverage.run(repository, workspace, 'HEAD')
    assert (outcome.name, outcome.status) == ('diff-coverage', Status.PASS)


def test_missing_diff_report_is_an_error(
    repository: Runner,
    scripts: Path,
) -> None:
    """A diff-cover that wrote no report, or one without lines, is an error.

    Args:
        repository: A fresh repository.
        scripts: A scripts folder with a fake diff-cover.
    """
    write_tool(scripts, 'diff-cover', 'import sys\nsys.exit(0)\n')
    runner = with_fakes(repository, scripts)
    workspace = repository.root.parent
    assert diff_coverage.run(runner, workspace, 'HEAD').status is Status.ERROR
    body = (
        'import pathlib, sys\n'
        "report = sys.argv[-1].removeprefix('json:')\n"
        """pathlib.Path(report).write_text('{"src_stats": {"a.py": {}}}')\n"""
    )
    write_tool(scripts, 'diff-cover', body)
    assert diff_coverage.run(runner, workspace, 'HEAD').status is Status.ERROR
    write_tool(
        scripts, 'diff-cover', body.replace('{"src_stats": {"a.py": {}}}', '{}')
    )
    assert diff_coverage.run(runner, workspace, 'HEAD').status is Status.ERROR

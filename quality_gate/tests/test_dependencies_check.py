"""Tests of the check `dependencies`, through deptry (SPEC §6.6, §7.4)."""

import json
from pathlib import Path

import pytest

from quality_gate.checks import dependencies
from quality_gate.checks.verdict import CheckInput
from quality_gate.execution import Runner
from quality_gate.model import Status, Violation
from quality_gate.tests.fakes import write_file, write_tool

ROOT = Path('/repository')
DISCOVERED = frozenset(('src/a.py', 'quality_gate/tests/test_x.py'))


def _finding(code: str, path: str, line: int | None) -> dict[str, object]:
    return {
        'error': {'code': code, 'message': f'{code} found'},
        'module': 'yaml',
        'location': {'file': path, 'line': line, 'column': line},
    }


def _parsed(report: Path, findings: list[object]) -> tuple[Violation, ...]:
    write_file(report.parent, report.name, json.dumps(findings))
    return dependencies.parse_deptry(
        '',
        ROOT,
        report=report,
        discovered=DISCOVERED,
    )


def test_deptry_findings_become_violations(tmp_path: Path) -> None:
    """Each finding is a violation at its place; DEP002 sits on line 1.

    Args:
        tmp_path: Holds deptry's report.
    """
    findings: list[object] = [
        _finding('DEP001', 'src/a.py', 3),
        _finding('DEP002', 'pyproject.toml', None),
    ]
    assert _parsed(tmp_path / 'deptry.json', findings) == (
        Violation('src/a.py', 3, 3, 'DEP001', 'DEP001 found'),
        Violation('pyproject.toml', 1, 1, 'DEP002', 'DEP002 found'),
    )


def test_findings_outside_discovery_are_dropped(tmp_path: Path) -> None:
    """A finding in a file the gate does not see is not the gate's.

    Args:
        tmp_path: Holds deptry's report.
    """
    findings: list[object] = [_finding('DEP001', 'legacy/old.py', 1)]
    assert _parsed(tmp_path / 'deptry.json', findings) == ()


def test_dep004_in_test_files_is_dropped(tmp_path: Path) -> None:
    """Tests may import dev dependencies; the engine may not.

    Args:
        tmp_path: Holds deptry's report.
    """
    findings: list[object] = [
        _finding('DEP004', 'quality_gate/tests/test_x.py', 1),
        _finding('DEP004', 'src/a.py', 2),
    ]
    found = _parsed(tmp_path / 'deptry.json', findings)
    assert [(kept.path, kept.code) for kept in found] == [
        ('src/a.py', 'DEP004'),
    ]


def test_missing_deptry_report_is_an_error(
    repository: Runner,
    scripts: Path,
) -> None:
    """A deptry that wrote no report gives no verdict.

    Args:
        repository: A fresh repository.
        scripts: A scripts folder with a deptry that writes nothing.
    """
    write_tool(scripts, 'deptry', 'import sys\nsys.exit(0)\n')
    runner = Runner(
        root=repository.root,
        scripts=scripts,
        environment=repository.environment,
        timeout=30,
    )
    given = CheckInput(runner=runner, files=('src/a.py',))
    outcome = dependencies.run(given, repository.root.parent)
    assert outcome.status is Status.ERROR


def test_an_undeclared_import_fails(repository: Runner) -> None:
    """The pinned deptry finds an import no dependency provides.

    Args:
        repository: A fresh repository.
    """
    project = '[project]\nname = "x"\nversion = "0"\ndependencies = []\n'
    write_file(repository.root, 'pyproject.toml', project)
    write_file(repository.root, 'src/a.py', 'import no_such_package\n')
    given = CheckInput(runner=repository, files=('src/a.py',))
    outcome = dependencies.run(given, repository.root.parent)
    assert outcome.status is Status.FAIL
    assert [found.code for found in outcome.violations] == ['DEP001']


def test_a_clean_project_passes(repository: Runner) -> None:
    """A project whose imports are all its own passes.

    Args:
        repository: A fresh repository.
    """
    project = '[project]\nname = "x"\nversion = "0"\ndependencies = []\n'
    write_file(repository.root, 'pyproject.toml', project)
    write_file(repository.root, 'src/a.py', 'import json\n')
    given = CheckInput(runner=repository, files=('src/a.py',))
    outcome = dependencies.run(given, repository.root.parent)
    assert (outcome.name, outcome.status) == ('dependencies', Status.PASS)


@pytest.mark.parametrize(
    ('report', 'pattern'),
    [
        ([1], 'deptry wrote a finding'),
        ({'findings': []}, 'deptry wrote a report'),
    ],
)
def test_an_unreadable_report_is_refused(
    tmp_path: Path,
    report: object,
    pattern: str,
) -> None:
    """A report or finding without deptry's shape cannot be read.

    Args:
        tmp_path: Holds deptry's report.
        report: What a broken or changed deptry might write.
        pattern: What the refusal says.
    """
    path = tmp_path / 'deptry.json'
    write_file(tmp_path, 'deptry.json', json.dumps(report))
    with pytest.raises(ValueError, match=pattern):
        pytest.fail(
            repr(
                dependencies.parse_deptry(
                    '',
                    ROOT,
                    report=path,
                    discovered=DISCOVERED,
                ),
            ),
        )


def test_filtered_findings_pass(repository: Runner, scripts: Path) -> None:
    """When the gate drops every finding, the check passes despite exit 1.

    Args:
        repository: A fresh repository.
        scripts: A scripts folder with a deptry that reports only legacy.
    """
    finding = json.dumps([_finding('DEP001', 'legacy/old.py', 1)])
    body = (
        'import pathlib, sys\n'
        f'pathlib.Path(sys.argv[-1]).write_text({finding!r})\n'
        'sys.exit(1)\n'
    )
    write_tool(scripts, 'deptry', body)
    runner = Runner(
        root=repository.root,
        scripts=scripts,
        environment=repository.environment,
        timeout=30,
    )
    given = CheckInput(runner=runner, files=('src/a.py',))
    outcome = dependencies.run(given, repository.root.parent)
    assert outcome.status is Status.PASS

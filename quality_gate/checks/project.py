"""The project checks of §7.4, which read the whole repository at once.

They run in `full` and `changed`. The four analyses come first; then the
suite runs under coverage, and coverage judges what the suite ran. In
`changed` the analyses still read everything, but only their findings that
touch a changed file count, and diff-coverage judges the changed lines.
"""

from collections.abc import Collection
from pathlib import Path

from quality_gate.checks import (
    contracts,
    covered,
    dead_code,
    dependencies,
    diff_coverage,
    duplication,
    suite,
)
from quality_gate.checks.scope import keep_in
from quality_gate.checks.verdict import CheckInput
from quality_gate.model import CheckResult


def analyse(given: CheckInput, workspace: Path) -> tuple[CheckResult, ...]:
    """Run the four analyses of the whole repository, in the order of §7.4.

    Args:
        given: The runner and every discovered file.
        workspace: The run's temporary folder.

    Returns:
        import-contracts, dead-code, dependencies and duplication.
    """
    return (
        contracts.run(given.runner),
        dead_code.run(given),
        dependencies.run(given, workspace),
        duplication.run(given),
    )


def measure(
    given: CheckInput,
    workspace: Path,
    *,
    whole: bool,
) -> tuple[CheckResult, ...]:
    """Run the suite under coverage, then judge the coverage.

    Args:
        given: The runner and every discovered file.
        workspace: The run's temporary folder, where the suite's data goes.
        whole: True in `full`, where every line and branch must run.

    Returns:
        tests, then coverage.
    """
    tests = suite.run(given.runner, workspace)
    coverage = covered.run(given.runner, workspace, given.files, whole=whole)
    return tests, coverage


def analyse_changes(
    given: CheckInput,
    workspace: Path,
    changed: Collection[str],
) -> tuple[CheckResult, ...]:
    """Run the four analyses, and keep what touches a changed file.

    import-contracts is kept whole: a broken contract has no file of its
    own. A duplicated block counts when any of its files changed.

    Args:
        given: The runner and every discovered file.
        workspace: The run's temporary folder.
        changed: Every changed path, root-relative.

    Returns:
        import-contracts, dead-code, dependencies and duplication.
    """
    imports, dead, needed, repeated = analyse(given, workspace)
    return (
        imports,
        keep_in(dead, changed),
        keep_in(needed, changed),
        keep_in(repeated, changed, places=duplication.block_paths),
    )


def measure_changes(
    given: CheckInput,
    workspace: Path,
    base: str,
) -> tuple[CheckResult, ...]:
    """Run the suite, check the file sets, then the lines changed since base.

    Args:
        given: The runner and every discovered file.
        workspace: The run's temporary folder.
        base: The reference the changes are measured from.

    Returns:
        tests, coverage and diff-coverage.
    """
    measured = measure(given, workspace, whole=False)
    return (*measured, diff_coverage.run(given.runner, workspace, base))

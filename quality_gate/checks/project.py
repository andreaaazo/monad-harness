"""The project checks of §7.4, which read the whole repository at once.

They run in `full` and `changed`. The four analyses come first; then the
suite runs under coverage, and coverage judges what the suite ran.
"""

from pathlib import Path

from quality_gate.checks import (
    contracts,
    covered,
    dead_code,
    dependencies,
    duplication,
    suite,
)
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

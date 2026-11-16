"""The checks that judge one file at a time, in the order of SPEC §7.4."""

from typing import Final

from quality_gate.checks import (
    basedpyright,
    pydoclint,
    ruff_format,
    ruff_lint,
    suppressions,
    wps,
)
from quality_gate.checks.verdict import Check

PER_FILE_CHECKS: Final[tuple[Check, ...]] = (
    ruff_lint.run,
    ruff_format.run,
    wps.run,
    pydoclint.run,
    basedpyright.run,
    suppressions.run,
)

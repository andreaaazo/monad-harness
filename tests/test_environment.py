"""The shell that runs pytest cannot change what the tests check."""

from __future__ import annotations

import os
import subprocess
import sys

from agency.config import REPO_ROOT, Settings
from support.environment import operator_variables


def test_the_engine_settings_and_the_key_are_operator_variables() -> None:
    names = [
        "AGENCY_EXPLORERS",
        "agency_data_dir",  # the settings read their variables in any case
        "ANTHROPIC_API_KEY",
        "AGENCY_ANTHROPIC_API_KEY",
        "anthropic_api_key",  # the key's names are read in any case too
        "PATH",
        "HOME",
        "MY_AGENCY_EXPLORERS",
    ]
    assert operator_variables(names) == [
        "AGENCY_ANTHROPIC_API_KEY",
        "AGENCY_EXPLORERS",
        "ANTHROPIC_API_KEY",
        "agency_data_dir",
        "anthropic_api_key",
    ]


def test_no_test_inherits_them() -> None:
    # The autouse fixture of conftest.py ran before this test: whatever the shell exported, none is left, and
    # the settings are the code's defaults. Run the suite with AGENCY_EXPLORERS=2 to see it matter.
    assert operator_variables(os.environ) == []
    assert Settings().explorers == Settings.model_fields["explorers"].default
    assert Settings().anthropic_api_key is None


def test_a_shell_with_the_operator_variables_changes_nothing() -> None:
    """The check above, in a pytest run whose shell exports what an operator's might: in a clean shell it
    would pass even without the fixture."""
    exported = {
        "AGENCY_EXPLORERS": "2",
        "AGENCY_PROPOSAL_EFFORT": "low",
        "ANTHROPIC_API_KEY": "sk-ant-finta-della-shell",
        "anthropic_api_key": "sk-ant-finta-minuscola",
    }
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-o", "addopts=", "-q",
         "tests/test_environment.py::test_no_test_inherits_them"],
        cwd=REPO_ROOT,
        env=os.environ | exported,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout[-2000:]

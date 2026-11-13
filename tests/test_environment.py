"""The shell that runs pytest cannot change what the tests check."""

from __future__ import annotations

import os

from agency.config import Settings
from support.environment import operator_variables


def test_the_engine_settings_and_the_key_are_operator_variables() -> None:
    names = [
        "AGENCY_EXPLORERS",
        "agency_data_dir",  # the settings read their variables in any case
        "ANTHROPIC_API_KEY",
        "AGENCY_ANTHROPIC_API_KEY",
        "PATH",
        "HOME",
        "MY_AGENCY_EXPLORERS",
    ]
    assert operator_variables(names) == [
        "AGENCY_ANTHROPIC_API_KEY",
        "AGENCY_EXPLORERS",
        "ANTHROPIC_API_KEY",
        "agency_data_dir",
    ]


def test_no_test_inherits_them() -> None:
    # The autouse fixture of conftest.py ran before this test: whatever the shell exported, none is left, and
    # the settings are the code's defaults. Run the suite with AGENCY_EXPLORERS=2 to see it matter.
    assert operator_variables(os.environ) == []
    assert Settings().explorers == Settings.model_fields["explorers"].default
    assert Settings().anthropic_api_key is None

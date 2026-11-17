"""What the gate's tests share: fake tools, files, the gate's table, the order.

A fake tool is an executable Python script written into a test's own folder.
"""

import dataclasses
import stat
import sys
from pathlib import Path
from typing import Final

from quality_gate.execution import Runner

# The gate's own table, as a test repository's pyproject.toml holds it.
GATE_TABLE: Final = (
    '[tool.quality_gate]\n'
    'exclude = []\n'
    'env_passthrough = []\n'
    'check_timeout_seconds = 120\n'
    'mutation_min_score = 0.9\n'
)
# The per-file checks, in the order of SPEC §7.4, which every mode keeps.
PER_FILE_ORDER: Final = (
    'ruff-lint',
    'ruff-format',
    'wps',
    'pydoclint',
    'basedpyright',
    'suppressions',
)


def with_fakes(repository: Runner, scripts: Path) -> Runner:
    """Give a copy of a repository's runner whose tools are the fakes.

    Args:
        repository: A runner rooted in a test's repository.
        scripts: The folder that holds the fake tools.

    Returns:
        The same runner, taking its tools from `scripts`.
    """
    return dataclasses.replace(repository, scripts=scripts)


def write_tool(scripts: Path, name: str, body: str) -> None:
    """Write an executable Python script that stands in for a tool.

    Args:
        scripts: The folder that plays the interpreter's scripts folder.
        name: The tool's executable name, which is the script's file name.
        body: The script's Python code, which follows the shebang.
    """
    tool = scripts / name
    with tool.open('w', encoding='utf-8') as script:
        script.writelines((f'#!{sys.executable}\n', body))
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)


def write_file(root: Path, name: str, text: str) -> None:
    """Write a text file under a root, with the folders it needs.

    Args:
        root: The folder the name is relative to.
        name: The file's path below the root, in POSIX form.
        text: The file's content.
    """
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as written:
        written.writelines((text,))

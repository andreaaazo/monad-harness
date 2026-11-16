"""Fake tools: executable Python scripts written into a test's own folder."""

import stat
import sys
from pathlib import Path


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

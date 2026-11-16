"""JSON read into plain values, without `Any` (SPEC §8.7).

`json.loads` returns `Any`. Bound to a callable that returns `object`, it gives
values that the guards below narrow, so no `Any` reaches the gate's code.
"""

import json
from collections.abc import Callable
from typing import TypeIs

# Not Final: basedpyright would read a Final through to json.loads's Any.
_LOADS: Callable[[str], object] = json.loads


def load_json(text: str) -> object:
    """Parse JSON text into plain values.

    Args:
        text: The JSON text.

    Returns:
        A dict, list, str, int, float, bool or None.

    Raises:
        ValueError: The text is not JSON.
    """
    try:
        return _LOADS(text)
    except json.JSONDecodeError as error:
        raise ValueError(str(error)) from error


def is_array(candidate: object) -> TypeIs[list[object]]:
    """Tell whether a parsed value is a JSON array.

    Args:
        candidate: A value from `load_json` or `tomllib`.

    Returns:
        True for a list.
    """
    return isinstance(candidate, list)


def is_table(candidate: object) -> TypeIs[dict[str, object]]:
    """Tell whether a parsed value is a JSON object or a TOML table.

    Args:
        candidate: A value from `load_json` or `tomllib`, whose keys are text.

    Returns:
        True for a dict.
    """
    return isinstance(candidate, dict)

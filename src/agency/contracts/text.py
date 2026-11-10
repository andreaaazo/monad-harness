"""Text sanitising shared by the layers above contracts."""

import re

CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # every control character except \n and \t


def plain(text: str) -> str:
    """Drop C0, C1 and DEL (not strictly C0, but terminals act on it), keeping newline and tab."""
    return CONTROL.sub("", text)

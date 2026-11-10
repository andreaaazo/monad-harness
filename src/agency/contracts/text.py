"""Text sanitising shared by the layers above contracts."""

import re

CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # every control character except \n and \t


def plain(text: str) -> str:
    """Drop C0, C1 and DEL (not strictly C0, but terminals act on it), keeping newline and tab."""
    return CONTROL.sub("", text)


LINE_BREAKS = re.compile(r"[\n\r\t]+")


def one_line(text: str) -> str:
    """`plain`, then one line: every run of newlines, carriage returns and tabs becomes one space.

    For a message that is one line by design and carries outside text (an API or proxy body, systemd's
    output): a newline inside it would start a line that can look like the CLI's own.
    """
    return plain(LINE_BREAKS.sub(" ", text)).strip()

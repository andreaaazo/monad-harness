"""The studio rules the tests pass to what needs them, loaded once from the repository's registry."""

from __future__ import annotations

from agency.registry import load_rules

RULES = load_rules()

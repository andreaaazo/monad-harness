"""Tests of JSON read into plain values, and of the guards that narrow them."""

import pytest

from quality_gate.jsonvalue import is_array, is_table, load_json


def test_load_json_returns_plain_values() -> None:
    """Objects, arrays, strings and numbers come back as plain values."""
    assert load_json('{"a": [1, "x"]}') == {'a': [1, 'x']}


def test_load_json_refuses_text_that_is_not_json() -> None:
    """Text that is not JSON raises a ValueError naming the problem."""
    with pytest.raises(ValueError, match='Expecting value'):
        pytest.fail(repr(load_json('not json')))


def test_the_guards_tell_arrays_and_tables_apart() -> None:
    """A list is an array and not a table; a dict is the other way round."""
    arrays = (is_array([]), is_array({}))
    tables = (is_table({}), is_table([]))
    assert (arrays, tables) == ((True, False), (True, False))

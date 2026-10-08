# -*- coding: utf-8 -*-

import sys

import pytest

from s3pathlib.marker import deprecated
from s3pathlib.tests import run_cov_test

MSG = "Deprecated since 3.1.0, will be removed in 4.0.0. Use new_func instead."


@deprecated(MSG)
def old_func(a: int, b: int = 2) -> int:
    """Add two numbers."""
    return a + b


class MyClass:
    @deprecated(MSG)
    def old_method(self, a: int) -> int:
        return a * 10


@deprecated(MSG)
class OldClass:
    def __init__(self, value: int):
        self.value = value


def test_deprecated_is_standard_pep702():
    """
    ``deprecated`` must be the standard PEP 702 object, otherwise type checkers
    and IDEs do not flag call sites.
    """
    if sys.version_info >= (3, 13):  # pragma: no cover
        import warnings

        assert deprecated is warnings.deprecated
    else:  # pragma: no cover
        import typing_extensions

        assert deprecated is typing_extensions.deprecated


def test_deprecated_function_warns():
    """
    Calling a deprecated function emits a ``DeprecationWarning`` (not a
    ``UserWarning``) with the given message, so warning filters treat it as a
    deprecation.
    """
    with pytest.warns(DeprecationWarning) as record:
        old_func(1)
    assert len(record) == 1
    assert record[0].category is DeprecationWarning
    assert str(record[0].message) == MSG


def test_deprecated_warning_points_to_caller():
    """
    The warning is attributed to the caller's file, not to s3pathlib, so users
    can find the line they need to change.
    """
    with pytest.warns(DeprecationWarning) as record:
        old_func(1)
    assert record[0].filename == __file__


def test_deprecated_function_passes_args_and_return():
    """
    The wrapped function still receives positional and keyword arguments and
    returns its result unchanged.
    """
    with pytest.warns(DeprecationWarning):
        assert old_func(1) == 3
    with pytest.warns(DeprecationWarning):
        assert old_func(1, b=5) == 6


def test_deprecated_function_keeps_metadata():
    """
    The decorated function keeps its name and docstring (for Sphinx and
    ``help()``) and exposes the message as ``__deprecated__``.
    """
    assert old_func.__name__ == "old_func"
    assert old_func.__doc__ == "Add two numbers."
    assert old_func.__deprecated__ == MSG


def test_deprecated_method_warns():
    """
    Works on instance methods: the call warns and ``self`` is still bound.
    """
    with pytest.warns(DeprecationWarning, match="Deprecated since 3.1.0"):
        assert MyClass().old_method(2) == 20


def test_deprecated_class_warns_on_instantiation():
    """
    Works on classes: instantiation warns and the constructor still runs.
    """
    with pytest.warns(DeprecationWarning, match="Deprecated since 3.1.0"):
        obj = OldClass(7)
    assert obj.value == 7


if __name__ == "__main__":
    run_cov_test(
        __file__,
        "s3pathlib.marker",
        preview=False,
    )

# -*- coding: utf-8 -*-

import inspect
import warnings
from types import SimpleNamespace

import pytest

from s3pathlib.metadata import _stacklevel_outside_package
from s3pathlib.metadata import warn_upper_case_in_metadata_key
from s3pathlib.tests import run_cov_test


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"author": "Alice", "x-1": "Value With Upper Case"},
    ],
)
def test_warn_upper_case_no_warning_for_lowercase(metadata):
    """
    Lowercase keys (and an empty dict) are valid, so no warning is emitted.
    Uppercase letters in values do not matter.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        warn_upper_case_in_metadata_key(metadata)


def test_warn_upper_case_warns_with_key_name():
    """
    An uppercase key emits a ``UserWarning`` that names the key and the
    lowercase key S3 will store instead.
    """
    with pytest.warns(UserWarning) as record:
        warn_upper_case_in_metadata_key({"Author": "Alice"})
    assert len(record) == 1
    message = str(record[0].message)
    assert "'Author'" in message
    assert "read back as 'author'" in message


def test_warn_upper_case_points_at_the_caller():
    """
    The warning points at the line of the caller outside ``s3pathlib``, so the
    user sees which line wrote the key.
    """
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        warn_upper_case_in_metadata_key({"Author": "Alice"})
    assert record[0].filename == __file__


def test_stacklevel_when_no_frame_is_outside_the_package(monkeypatch):
    """
    If every frame of the stack is inside ``s3pathlib`` (no user frame), the
    level is the depth of the stack instead of an error.
    """
    inner = SimpleNamespace(f_globals={"__name__": "s3pathlib.a"}, f_back=None)
    outer = SimpleNamespace(f_globals={"__name__": "s3pathlib.b"}, f_back=inner)
    monkeypatch.setattr(inspect, "currentframe", lambda: outer)
    assert _stacklevel_outside_package() == 2


def test_warn_upper_case_one_warning_per_bad_key():
    """
    Each uppercase key gets its own warning; lowercase keys get none.
    """
    with pytest.warns(UserWarning) as record:
        warn_upper_case_in_metadata_key({"a": "1", "B": "2", "Cc": "3"})
    messages = [str(r.message) for r in record]
    assert len(messages) == 2
    assert "'B'" in messages[0]
    assert "'Cc'" in messages[1]


if __name__ == "__main__":
    run_cov_test(
        __file__,
        "s3pathlib.metadata",
        preview=False,
    )

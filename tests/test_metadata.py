# -*- coding: utf-8 -*-

import warnings

import pytest

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
    An uppercase key emits a ``UserWarning`` that names the key, so the user
    knows which key S3 will rename.
    """
    with pytest.warns(UserWarning) as record:
        warn_upper_case_in_metadata_key({"Author": "Alice"})
    assert len(record) == 1
    assert "'Author'" in str(record[0].message)


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

# -*- coding: utf-8 -*-

"""
Test ``s3pathlib._arg``: the ``OPT`` sentinel and ``remove_optional``.

Test order:

1. the sentinels: their repr, and they stay the same object when copied or
   pickled;
2. ``remove_optional``.
"""

import copy
import pickle

import pytest

from s3pathlib._arg import NOT_GIVEN
from s3pathlib._arg import OPT
from s3pathlib._arg import remove_optional
from s3pathlib.tests import run_cov_test


# ------------------------------------------------------------------------------
# 1. The sentinels
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sentinel, name",
    [
        pytest.param(OPT, "OPT", id="OPT"),
        pytest.param(NOT_GIVEN, "NOT_GIVEN", id="NOT_GIVEN"),
    ],
)
def test_sentinel_repr(sentinel, name):
    """
    The repr is the name, so a signature reads ``version_id: str = OPT``.
    """
    assert repr(sentinel) == name


@pytest.mark.parametrize("sentinel", [OPT, NOT_GIVEN], ids=["OPT", "NOT_GIVEN"])
@pytest.mark.parametrize(
    "clone",
    [
        pytest.param(copy.copy, id="copy"),
        pytest.param(copy.deepcopy, id="deepcopy"),
        pytest.param(lambda x: pickle.loads(pickle.dumps(x)), id="pickle"),
    ],
)
def test_sentinel_identity(sentinel, clone):
    """
    A copied or pickled sentinel is the same object, so ``is OPT`` still
    works on copied keyword arguments.
    """
    assert clone(sentinel) is sentinel


def test_sentinels_are_different():
    assert OPT is not NOT_GIVEN


# ------------------------------------------------------------------------------
# 2. remove_optional
# ------------------------------------------------------------------------------
def test_remove_optional():
    """
    Only ``OPT`` is removed; ``None`` and other falsy values are kept, so that
    botocore rejects ``None`` instead of silently not sending it.
    """
    kwargs = remove_optional(
        Bucket="bucket",
        VersionId=OPT,
        IfMatch=None,
        MaxKeys=0,
        Prefix="",
        FetchOwner=False,
    )
    assert kwargs == {
        "Bucket": "bucket",
        "IfMatch": None,
        "MaxKeys": 0,
        "Prefix": "",
        "FetchOwner": False,
    }


def test_remove_optional_empty():
    assert remove_optional() == {}
    assert remove_optional(VersionId=OPT) == {}


if __name__ == "__main__":
    run_cov_test(
        __file__,
        "s3pathlib._arg",
        preview=False,
    )

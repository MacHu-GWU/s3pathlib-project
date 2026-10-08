# -*- coding: utf-8 -*-

import sys

import pytest

import s3pathlib
import s3pathlib.api
import s3pathlib.better_client.api
from s3pathlib.tests import run_cov_test

# Names users could import from the top level package in 2.x. ``context`` was
# renamed to ``s3_context`` in 3.0 (the old name is removed, see
# ``tests/test_aws.py``).
TOP_LEVEL_NAMES = [
    "S3Path",
    "s3_context",
    "utils",
    "ContentTypeEnum",
    "validate_s3_bucket",
    "validate_s3_key",
    "validate_s3_uri",
    "validate_s3_arn",
    "and_",
    "or_",
    "not_",
]

# Names users could access as ``s3pathlib.api.*`` in 2.x,
# now under ``s3pathlib.api.better_client.*``.
BETTER_CLIENT_NAMES = [
    name
    for name in dir(s3pathlib.better_client.api)
    if not name.startswith("_")
]


@pytest.mark.parametrize("name", TOP_LEVEL_NAMES)
def test_api_exports(name):
    """
    Every top level public name of 2.x is importable from ``s3pathlib.api``,
    which is the only migration step most users need for 3.0.
    """
    assert hasattr(s3pathlib.api, name)


@pytest.mark.parametrize("name", BETTER_CLIENT_NAMES)
def test_api_better_client_exports(name):
    """
    The low level helpers are grouped under ``s3pathlib.api.better_client``
    instead of being mixed into ``s3pathlib.api``.
    """
    assert getattr(s3pathlib.api.better_client, name) is getattr(
        s3pathlib.better_client.api, name
    )
    assert not hasattr(s3pathlib.api, name)


def test_top_level_api_is_the_api_module():
    """
    ``s3pathlib.api`` means the same thing whether it is reached as an
    attribute of the package or imported as a submodule.
    """
    assert s3pathlib.api is sys.modules["s3pathlib.api"]


@pytest.mark.parametrize("name", TOP_LEVEL_NAMES)
def test_top_level_names_still_work(name):
    """
    ``from s3pathlib import ...`` still works until it is removed in 3.0.
    """
    assert getattr(s3pathlib, name) is getattr(s3pathlib.api, name)


if __name__ == "__main__":
    run_cov_test(
        __file__,
        "s3pathlib.api",
        preview=False,
    )

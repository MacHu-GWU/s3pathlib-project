# -*- coding: utf-8 -*-

"""
Test the public entry point ``s3pathlib.api``.

Test order:

1. the exact set of public names (any change of the public API breaks this
   test on purpose);
2. each name is the object of the module that defines it;
3. the 2.x top level names, and the low level helpers under
   ``better_client``;
4. ``from s3pathlib import ...``, kept until Phase 4.
"""

import inspect
import sys

import iterproxy
import pytest

import s3pathlib
import s3pathlib.api
import s3pathlib.better_client.api
import s3pathlib.constants
import s3pathlib.content_type
import s3pathlib.core
import s3pathlib.core.iter_objects
import s3pathlib.core.serde
import s3pathlib.exc
import s3pathlib.utils
import s3pathlib.validate
from s3pathlib.aws import s3_context
from s3pathlib.tests import run_cov_test

# public name -> the object it must be
API = {
    # 2.x top level names
    "S3Path": s3pathlib.core.S3Path,
    "s3_context": s3_context,
    "utils": s3pathlib.utils,
    "ContentTypeEnum": s3pathlib.content_type.ContentTypeEnum,
    "validate_s3_bucket": s3pathlib.validate.validate_s3_bucket,
    "validate_s3_key": s3pathlib.validate.validate_s3_key,
    "validate_s3_uri": s3pathlib.validate.validate_s3_uri,
    "validate_s3_arn": s3pathlib.validate.validate_s3_arn,
    "and_": iterproxy.and_,
    "or_": iterproxy.or_,
    "not_": iterproxy.not_,
    # added in 3.0
    "better_client": s3pathlib.better_client.api,
    "exc": s3pathlib.exc,
    "S3PathDict": s3pathlib.core.serde.S3PathDict,
    "S3PathIterProxy": s3pathlib.core.iter_objects.S3PathIterProxy,
    "AwsPartitionEnum": s3pathlib.constants.AwsPartitionEnum,
}

# names of 2.x that ``from s3pathlib import ...`` still gives
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

# names users could access as ``s3pathlib.api.*`` in 2.x, now under
# ``s3pathlib.api.better_client.*``
BETTER_CLIENT_NAMES = [
    name for name in dir(s3pathlib.better_client.api) if not name.startswith("_")
]

EXCEPTIONS = [
    name
    for name, obj in inspect.getmembers(s3pathlib.exc, inspect.isclass)
    if issubclass(obj, s3pathlib.exc.S3PathlibError)
]


# ------------------------------------------------------------------------------
# 1. The public names
# ------------------------------------------------------------------------------
def test_public_names():
    """
    ``s3pathlib.api`` has exactly the documented public names: an added or
    removed name (e.g. a stray import) is an API change, update ``API`` and
    the changelog on purpose.
    """
    public = {name for name in dir(s3pathlib.api) if not name.startswith("_")}
    assert public == set(API)


# ------------------------------------------------------------------------------
# 2. Each name is the original object
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(API))
def test_api_names_are_the_originals(name):
    assert getattr(s3pathlib.api, name) is API[name]


@pytest.mark.parametrize("name", EXCEPTIONS)
def test_exceptions(name):
    """
    Every exception is reachable as ``s3pathlib.api.exc.<name>``.
    """
    assert getattr(s3pathlib.api.exc, name) is getattr(s3pathlib.exc, name)


def test_exceptions_listed():
    """
    The exception list is not empty and has the base class (guard for the
    parametrized test above).
    """
    assert "S3PathlibError" in EXCEPTIONS
    assert "S3SyncError" in EXCEPTIONS


# ------------------------------------------------------------------------------
# 3. 2.x names and better_client
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("name", BETTER_CLIENT_NAMES)
def test_api_better_client_exports(name):
    """
    The low level helpers are grouped under ``s3pathlib.api.better_client``
    instead of being mixed into ``s3pathlib.api`` (2.x).
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


# ------------------------------------------------------------------------------
# 4. from s3pathlib import ...
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("name", TOP_LEVEL_NAMES)
def test_top_level_names_still_work(name):
    """
    ``from s3pathlib import ...`` still works; it will be removed in Phase 4
    of 3.0, use ``from s3pathlib.api import ...``.
    """
    assert getattr(s3pathlib, name) is getattr(s3pathlib.api, name)


if __name__ == "__main__":
    run_cov_test(
        __file__,
        "s3pathlib.api",
        preview=False,
    )

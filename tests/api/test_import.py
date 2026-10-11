# -*- coding: utf-8 -*-

"""
Test the public entry point ``s3pathlib.api``.

Test order:

1. the exact set of public names (any change of the public API breaks this
   test on purpose);
2. each name is the object of the module that defines it;
3. the 2.x top level names, and the low level helpers under
   ``better_client``;
4. ``from s3pathlib import ...``, removed in 3.0.0: an error that says where
   the name moved, and ``import s3pathlib`` only gives the version info.
"""

import inspect
import subprocess
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

# names of 2.x that ``from s3pathlib import ...`` gave, moved to
# ``s3pathlib.api`` in 3.0.0 (``utils`` is a submodule, so it still imports)
TOP_LEVEL_NAMES = [
    "S3Path",
    "s3_context",
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
def test_top_level_names_removed(name):
    """
    ``from s3pathlib import ...`` was removed in 3.0.0; the error says to
    use ``from s3pathlib.api import ...`` instead of a bare "cannot import
    name", so users and AI know how to upgrade.
    """
    message = f"use 'from s3pathlib.api import {name}'"
    with pytest.raises(ImportError, match=message):
        exec(f"from s3pathlib import {name}", {})
    with pytest.raises(ImportError, match=message):
        getattr(s3pathlib, name)


def test_top_level_unknown_name():
    """
    Any other missing name is a normal ``AttributeError``, so ``hasattr`` and
    ``getattr(..., default)`` work.
    """
    assert hasattr(s3pathlib, "no_such_name") is False
    with pytest.raises(AttributeError, match="has no attribute 'no_such_name'"):
        s3pathlib.no_such_name


def test_top_level_submodules():
    """
    Submodules still import from the package, e.g. ``from s3pathlib import
    utils``.
    """
    namespace = dict()
    exec("from s3pathlib import utils, api", namespace)
    assert namespace["utils"] is s3pathlib.utils
    assert namespace["api"] is s3pathlib.api


def test_import_package_only_gives_version_info():
    """
    In a new process, ``import s3pathlib`` gives only the version info, and
    does not import the library (2.x imported everything, and silently left
    names out when a dependency was missing).
    """
    code = (
        "import sys, s3pathlib; "
        "print(sorted(n for n in dir(s3pathlib) if not n.startswith('__'))); "
        "print('s3pathlib.core' in sys.modules)"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    names, core_imported = res.stdout.splitlines()
    assert names == "['_MOVED_TO_API', '_version']"
    assert core_imported == "False"
    assert s3pathlib.__version__ == s3pathlib._version.__version__


if __name__ == "__main__":
    run_cov_test(
        __file__,
        "s3pathlib.api",
        preview=False,
    )

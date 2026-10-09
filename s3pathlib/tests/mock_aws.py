# -*- coding: utf-8 -*-

"""
Base class for tests that call the AWS API, against moto or real AWS.

Write the tests once in a mixin, and run them in two one-line subclasses::

    from s3pathlib.tests.mock_aws import BaseTest
    from s3pathlib.tests.mock_aws import mock_only

    class HeadBucketMixin(BaseTest):
        module = "better_client.head_bucket"  # sub folder in the test buckets

        def test_exists(self):
            assert is_bucket_exists(self.s3_client, self.bucket) is True

        @mock_only("creates a bucket with a fixed global name")
        def test_create(self): ...

    class TestMock(HeadBucketMixin):
        use_mock = True

    class TestRealAws(HeadBucketMixin):
        use_mock = False

**When a test runs**

- ``TestMock`` (``use_mock = True``) always runs, against moto.
- ``TestRealAws`` (``use_mock = False``) runs against real AWS only when BOTH:

    1. the test can run on AWS: the subclass exists, and the test is not
       decorated with ``@mock_only``; and
    2. this run allows AWS: the environment variable
       ``S3PATHLIB_TEST_REAL_AWS`` is ``true`` (``mise run cov-aws``).

  Neither overrides the other. When the variable is unset or ``false``, the
  whole class is skipped with the reason. Any other value is an error, and so
  are missing credentials when it is ``true``: a run that asked for AWS must
  not silently skip.
- ``@real_aws_only(reason)`` skips a test in ``TestMock``.

**Credentials on real AWS**: on CI (``CI`` is set), the access key in
``AWS_ACCESS_KEY_ID_FOR_GITHUB_CI`` / ``AWS_SECRET_ACCESS_KEY_FOR_GITHUB_CI``;
locally, the profile named by ``S3PATHLIB_TEST_AWS_PROFILE`` (``mise.toml``).
``mise run setup-aws-ci`` creates the buckets and the IAM user.

**Isolation**: each test class works under ``s3dir_root``, a folder named
after ``module`` in the test buckets, and each test under its own
``s3dir_test`` (``s3dir_root / "<test name>/"``). On real AWS, everything under
``s3dir_root`` (all object versions) is deleted when the class starts, so a run
never sees objects left by a previous run. With moto, each class starts from
empty buckets. The folders of concurrent runs never overlap, see
``get_root_prefix``.
"""

from __future__ import annotations

import typing as T
import os
import re
import sys

import boto3
import moto
import pytest

from ..api import S3Path
from ..api import s3_context

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client

ENV_REAL_AWS = "S3PATHLIB_TEST_REAL_AWS"
ENV_TEST_AWS_PROFILE = "S3PATHLIB_TEST_AWS_PROFILE"
ENV_CI_ACCESS_KEY_ID = "AWS_ACCESS_KEY_ID_FOR_GITHUB_CI"
ENV_CI_SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY_FOR_GITHUB_CI"
ENV_GITHUB_RUN_ID = "GITHUB_RUN_ID"

AWS_REGION = "us-east-1"

_MOCK_ONLY = "_s3pathlib_mock_only_reason"
_REAL_AWS_ONLY = "_s3pathlib_real_aws_only_reason"


def is_ci() -> bool:
    return "CI" in os.environ


def get_root_prefix() -> str:
    """
    The S3 folder of this test run. Different OS / Python versions (e.g. the
    CI matrix) use different folders, so they can run at the same time. On
    GitHub Actions, each workflow run also has its own folder
    (``GITHUB_RUN_ID``), so two runs at the same time (e.g. pushes to ``main``
    and ``dev``) never empty each other's folders; the lifecycle rule of the
    test buckets deletes them after one day.
    """
    if is_ci():
        run_id = os.environ.get(ENV_GITHUB_RUN_ID, "")
        if run_id == "":
            runtime = "ci"
        else:
            runtime = f"ci/{run_id}"
    else:
        runtime = "local"
    return (
        f"projects/s3pathlib/unittest/{runtime}/{sys.platform}"
        f"/py{sys.version_info.major}{sys.version_info.minor}"
    )


def get_bucket_name(aws_account_id: str, aws_region: str, name: str) -> str:
    """
    Keep in sync with ``get_bucket_name`` in ``.mise/tasks/aws_ci.py``, which
    creates the buckets on real AWS.
    """
    return f"{aws_account_id}-{aws_region}-{name}"


def is_real_aws_enabled() -> bool:
    """
    Whether this run allows tests against real AWS: ``S3PATHLIB_TEST_REAL_AWS``
    is ``true``. Unset or ``false`` means no.

    :raises ValueError: for any other value, e.g. a typo such as ``ture``.
    """
    if ENV_REAL_AWS not in os.environ:
        return False
    value = os.environ[ENV_REAL_AWS]
    if value == "true":
        return True
    elif value == "false":
        return False
    else:
        raise ValueError(
            f"{ENV_REAL_AWS} must be 'true' or 'false', got {value!r}"
        )


def new_mock_boto_session() -> boto3.session.Session:
    """
    A session with fake credentials, so that a moto test can never pick up a
    real profile from the environment.
    """
    return boto3.session.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name=AWS_REGION,
    )


def new_real_boto_session() -> boto3.session.Session:
    """
    The session of the test IAM user.

    :raises RuntimeError: if the credentials are not available.
    """
    if is_ci():
        for name in [ENV_CI_ACCESS_KEY_ID, ENV_CI_SECRET_ACCESS_KEY]:
            if os.environ.get(name, "") == "":
                raise RuntimeError(
                    f"{ENV_REAL_AWS} is 'true' but {name} is not set; "
                    "only enable real AWS tests when the secrets are available"
                )
        return boto3.session.Session(
            aws_access_key_id=os.environ[ENV_CI_ACCESS_KEY_ID],
            aws_secret_access_key=os.environ[ENV_CI_SECRET_ACCESS_KEY],
            region_name=AWS_REGION,
        )
    else:
        if ENV_TEST_AWS_PROFILE not in os.environ:
            raise RuntimeError(
                f"{ENV_REAL_AWS} is 'true' but {ENV_TEST_AWS_PROFILE} is not "
                "set; run the tests with mise, which sets it from mise.toml"
            )
        profile = os.environ[ENV_TEST_AWS_PROFILE]
        try:
            boto_ses = boto3.session.Session(
                profile_name=profile,
                region_name=AWS_REGION,
            )
        except Exception as e:
            raise RuntimeError(
                f"{ENV_REAL_AWS} is 'true' but the AWS profile {profile!r} "
                f"cannot be loaded ({e}); run 'mise run setup-aws-ci' and add "
                "the profile it prints to ~/.aws"
            ) from e
        if boto_ses.get_credentials() is None:
            raise RuntimeError(
                f"{ENV_REAL_AWS} is 'true' but the AWS profile {profile!r} has "
                "no credentials; run 'mise run setup-aws-ci' and add the "
                "profile it prints to ~/.aws"
            )
        return boto_ses


def delete_s3_prefix(s3_client: S3Client, bucket: str, prefix: str) -> int:
    """
    Delete every object version and delete marker under ``prefix``, with plain
    boto3 calls (not with the s3pathlib code under test).

    :return: the number of deleted versions and delete markers.
    """
    paginator = s3_client.get_paginator("list_object_versions")
    n_deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = list()
        for key in ["Versions", "DeleteMarkers"]:
            for version in page.get(key, []):
                objects.append(
                    {"Key": version["Key"], "VersionId": version["VersionId"]}
                )
        if len(objects) == 0:
            continue
        # a page has at most 1000 entries, the delete_objects limit
        res = s3_client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": objects, "Quiet": True},
        )
        if len(res.get("Errors", [])) > 0:
            raise RuntimeError(f"failed to delete test objects: {res['Errors']}")
        n_deleted += len(objects)
    return n_deleted


def _check_reason(reason: str):
    if not isinstance(reason, str):
        raise TypeError(f"reason must be a str, got {reason!r}")
    if reason.strip() == "":
        raise ValueError("reason must not be empty")


def mock_only(reason: str):
    """
    Decorate a test that only runs with moto; it is skipped in ``TestRealAws``.
    ``reason`` says why, e.g. ``"moto only: creates a bucket with a fixed
    global name"``.
    """
    _check_reason(reason)

    def decorator(func):
        setattr(func, _MOCK_ONLY, reason)
        return func

    return decorator


def real_aws_only(reason: str):
    """
    Decorate a test that only runs on real AWS; it is skipped in ``TestMock``.
    ``reason`` says why, e.g. ``"moto does not implement ..."``.
    """
    _check_reason(reason)

    def decorator(func):
        setattr(func, _REAL_AWS_ONLY, reason)
        return func

    return decorator


def get_test_dir_name(test_name: str) -> str:
    """
    The folder name of a test: its pytest name (with the parametrize id), with
    every character other than letters, digits, ``.``, ``_``, ``=`` and ``-``
    replaced by ``-``. E.g. ``test_put[a/b c]`` -> ``test_put-a-b-c-``.
    """
    return re.sub(r"[^A-Za-z0-9._=-]+", "-", test_name)


class BaseTest:
    """
    See the module docstring.

    Set in the subclass:

    - ``use_mock``: ``True`` for moto, ``False`` for real AWS.
    - ``module``: the module under test, e.g. ``"core.copy"``; it becomes the
      folder of the class in the test buckets.

    Available as ``cls.x`` (in ``custom_setup_class``) and ``self.x``:

    - ``boto_ses``, ``s3_client``: the session and S3 client of the class.
      ``s3_client`` is also attached to ``s3_context``, so ``S3Path`` methods
      use it. Verify S3 state with native ``self.s3_client`` calls.
    - ``aws_account_id``, ``aws_region``
    - ``bucket``, ``bucket_with_versioning``: the regular test bucket and the
      one with versioning enabled.
    - ``s3dir_root``, ``s3dir_root_with_versioning``: the folder of the class
      in each bucket.

    Available as ``self.x`` in a test:

    - ``s3dir_test``, ``s3dir_test_with_versioning``: a folder only this test
      uses, ``s3dir_root / "<test name>/"``.
    """

    use_mock: bool
    module: str

    boto_ses: boto3.session.Session
    s3_client: S3Client
    aws_account_id: str
    aws_region: str
    bucket: str
    bucket_with_versioning: str
    s3dir_root: S3Path
    s3dir_root_with_versioning: S3Path

    s3dir_test: S3Path
    s3dir_test_with_versioning: S3Path

    mock_aws: T.Any = None

    @classmethod
    def custom_setup_class(cls):
        """
        Override to prepare data for all tests of the class. Runs after the
        buckets are ready.
        """

    @classmethod
    def custom_teardown_class(cls):
        """
        Override to clean up after all tests of the class. Runs before moto
        stops, so it still talks to the same backend as the tests.
        """

    @classmethod
    def setup_class(cls):
        if cls.use_mock is True:
            pass
        elif cls.use_mock is False:
            if is_real_aws_enabled() is False:
                pytest.skip(
                    f"real AWS test; set {ENV_REAL_AWS}=true to run it "
                    "(mise run cov-aws)"
                )
        else:
            raise TypeError(
                f"{cls.__name__}.use_mock must be True or False, "
                f"got {cls.use_mock!r}"
            )

        if cls.use_mock:
            cls.mock_aws = moto.mock_aws()
            cls.mock_aws.start()
        try:
            cls._setup_aws()
            cls.custom_setup_class()
        except BaseException:
            # pytest does not call teardown_class when setup_class fails, and a
            # moto mock left running would leak into the next test classes
            cls._stop_mock()
            raise

    @classmethod
    def _setup_aws(cls):
        if cls.use_mock:
            cls.boto_ses = new_mock_boto_session()
        else:
            cls.boto_ses = new_real_boto_session()
        res = cls.boto_ses.client("sts").get_caller_identity()
        cls.aws_account_id = res["Account"]
        cls.aws_region = cls.boto_ses.region_name
        cls.s3_client = cls.boto_ses.client("s3")
        s3_context.attach_s3_client(cls.s3_client)

        cls.bucket = get_bucket_name(
            cls.aws_account_id, cls.aws_region, "s3pathlib-test"
        )
        cls.bucket_with_versioning = get_bucket_name(
            cls.aws_account_id, cls.aws_region, "s3pathlib-test-versioning-on"
        )
        prefix = get_root_prefix() + "/" + cls.module.replace(".", "/") + "/"
        cls.s3dir_root = S3Path(cls.bucket, prefix)
        cls.s3dir_root_with_versioning = S3Path(cls.bucket_with_versioning, prefix)

        if cls.use_mock:
            cls.s3_client.create_bucket(Bucket=cls.bucket)
            cls.s3_client.create_bucket(Bucket=cls.bucket_with_versioning)
            cls.s3_client.put_bucket_versioning(
                Bucket=cls.bucket_with_versioning,
                VersioningConfiguration={"Status": "Enabled"},
            )
        else:
            delete_s3_prefix(cls.s3_client, cls.bucket, prefix)
            delete_s3_prefix(cls.s3_client, cls.bucket_with_versioning, prefix)

    @classmethod
    def _stop_mock(cls):
        if cls.mock_aws is not None:
            cls.mock_aws.stop()
            cls.mock_aws = None

    @classmethod
    def teardown_class(cls):
        try:
            cls.custom_teardown_class()
        finally:
            cls._stop_mock()

    @pytest.fixture(autouse=True)
    def _setup_test(self, request):
        """
        Skip a test that cannot run in this mode, and give it its own folder.
        """
        func = request.function
        if self.use_mock is False and hasattr(func, _MOCK_ONLY):
            pytest.skip(f"mock only: {getattr(func, _MOCK_ONLY)}")
        if self.use_mock is True and hasattr(func, _REAL_AWS_ONLY):
            pytest.skip(f"real AWS only: {getattr(func, _REAL_AWS_ONLY)}")
        dir_name = get_test_dir_name(request.node.name) + "/"
        self.s3dir_test = self.s3dir_root.joinpath(dir_name)
        self.s3dir_test_with_versioning = self.s3dir_root_with_versioning.joinpath(
            dir_name
        )

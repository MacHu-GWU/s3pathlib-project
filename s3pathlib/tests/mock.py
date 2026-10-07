# -*- coding: utf-8 -*-

from __future__ import annotations

import typing as T
import contextlib
import datetime
import os
import sys
from functools import cached_property

import boto3
import botocore.session
import moto
from botocore.credentials import DeferredRefreshableCredentials
from rich import print as rprint

from ..api import S3Path
from ..api import s3_context

if T.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

if "CI" in os.environ:
    runtime = "ci"
else:
    runtime = "local"

prefix = "projects/s3pathlib/unittest/{runtime}/{os}/py{major}{minor}".format(
    runtime=runtime,
    os=sys.platform,
    major=sys.version_info.major,
    minor=sys.version_info.minor,
)


def get_bucket_name(aws_account_id: str, aws_region: str, name: str) -> str:
    """
    Keep in sync with ``get_bucket_name`` in ``.mise/tasks/aws_ci.py``, which
    creates the buckets on real AWS.
    """
    return f"{aws_account_id}-{aws_region}-{name}"


def make_refreshable_s3_client() -> tuple[S3Client, list[str]]:
    """
    Create an S3 client whose credentials expire one second after each fetch,
    so that botocore fetches new ones before every request (it refreshes
    credentials that expire within the next minutes). This is how a client
    built from an assumed role session (e.g. ``BotoSesManager.assume_role``)
    keeps working after the role session expires.

    :return: the client, and the list of access keys fetched so far
        (``"AK1"``, ``"AK2"``, ...), which grows on every fetch.
    """
    fetched_keys = list()

    def fetch() -> dict:
        access_key = f"AK{len(fetched_keys) + 1}"
        fetched_keys.append(access_key)
        now = datetime.datetime.now(datetime.timezone.utc)
        expiry_time = now + datetime.timedelta(seconds=1)
        return {
            "access_key": access_key,
            "secret_key": "secret",
            "token": "token",
            "expiry_time": expiry_time.isoformat(),
        }

    botocore_session = botocore.session.Session()
    botocore_session._credentials = DeferredRefreshableCredentials(
        refresh_using=fetch,
        method="custom-refreshable",
    )
    boto_ses = boto3.session.Session(
        botocore_session=botocore_session,
        region_name="us-east-1",
    )
    return boto_ses.client("s3"), fetched_keys


@contextlib.contextmanager
def record_signing_access_keys(s3_client: S3Client):
    """
    Record the access key that signs each request sent by ``s3_client``.
    """
    access_keys = list()

    def record(request, **kwargs):
        # "AWS4-HMAC-SHA256 Credential=AK1/20261007/us-east-1/s3/aws4_request, ..."
        authorization = request.headers["Authorization"]
        if isinstance(authorization, bytes):
            authorization = authorization.decode("utf-8")
        credential = authorization.split("Credential=")[1]
        access_keys.append(credential.split("/")[0])

    events = s3_client.meta.events
    events.register("before-send.s3", record)
    try:
        yield access_keys
    finally:
        events.unregister("before-send.s3", record)


class BaseTest:
    """
    Class attributes:

    - use_mock: if True, use moto.mock_s3, otherwise use real S3
    - module: the Python module you are testing with, the module name will become
        a sub-folder in the test S3 bucket.
    """
    use_mock: bool
    module: str

    boto_ses: boto3.session.Session
    aws_account_id: str
    aws_region: str
    force_use_mock: bool = False

    @classmethod
    def custom_setup_class(cls):
        """
        You can override this method to do custom setup.
        """
        pass

    @classmethod
    def custom_teardown_class(cls):
        """
        You can override this method to do custom teardown.
        """
        pass

    @classmethod
    def get_bucket(cls) -> str:
        """
        Get the bucket name for testing.
        """
        return get_bucket_name(cls.aws_account_id, cls.aws_region, "s3pathlib-test")

    @classmethod
    def get_bucket_with_versioning(cls) -> str:
        """
        Get the bucket name for testing versioning feature.
        """
        return get_bucket_name(
            cls.aws_account_id,
            cls.aws_region,
            "s3pathlib-test-versioning-on",
        )

    @classmethod
    def setup_moto(cls):
        if cls.force_use_mock is True:
            cls.use_mock = True

        if cls.use_mock is True:
            cls.mock_aws = moto.mock_aws()
            cls.mock_aws.start()
        elif cls.use_mock is False:
            pass
        else:
            raise NotImplementedError("use_mock must be True or False!")

    @classmethod
    def teardown_moto(cls):
        if cls.force_use_mock is True:
            cls.use_mock = True

        if cls.use_mock is True:
            cls.mock_aws.stop()
        elif cls.use_mock is False:
            pass
        else:
            raise NotImplementedError("use_mock must be True or False!")

    @classmethod
    def setup_boto_session(cls):
        kwargs = dict(region_name="us-east-1")
        if cls.use_mock is True:
            pass
        elif cls.use_mock is False:
            if runtime == "ci":
                kwargs["aws_access_key_id"] = os.environ[
                    "AWS_ACCESS_KEY_ID_FOR_GITHUB_CI"
                ]
                kwargs["aws_secret_access_key"] = os.environ[
                    "AWS_SECRET_ACCESS_KEY_FOR_GITHUB_CI"
                ]
            else:
                # the profile name is defined in mise.toml
                env_name = "S3PATHLIB_TEST_AWS_PROFILE"
                if env_name not in os.environ:
                    raise RuntimeError(
                        f"Environment variable {env_name} is not set; "
                        "run the tests with mise, which sets it from mise.toml"
                    )
                kwargs["profile_name"] = os.environ[env_name]
        else:
            raise NotImplementedError("use_mock must be True or False!")

        cls.boto_ses = boto3.session.Session(**kwargs)
        cls.aws_account_id = cls.boto_ses.client("sts").get_caller_identity()["Account"]
        cls.aws_region = cls.boto_ses.region_name
        s3_context.attach_s3_client(cls.boto_ses.client("s3"))

    @classmethod
    def setup_bucket(cls):
        """
        We need two buckets for testing. One is a regular bucket, another is a
        bucket with versioning enabled.

        On real AWS, ``mise run setup-aws-ci`` creates them (see
        ``.github/workflows/README.rst``).
        """
        if cls.use_mock:
            s3_client = s3_context.s3_client
            s3_client.create_bucket(Bucket=cls.get_bucket())
            s3_client.create_bucket(Bucket=cls.get_bucket_with_versioning())
            s3_client.put_bucket_versioning(
                Bucket=cls.get_bucket_with_versioning(),
                VersioningConfiguration={"Status": "Enabled"},
            )

    @classmethod
    def setup_class(cls):
        cls.setup_moto()
        cls.setup_boto_session()
        cls.setup_bucket()
        cls.custom_setup_class()

    @classmethod
    def teardown_class(cls):
        cls.teardown_moto()
        cls.custom_teardown_class()

    @classmethod
    def get_module_folders(cls) -> str:
        """
        The module name will become a sub-folder in the test S3 bucket,
        providing module level test cases isolation.
        """
        return "/".join(cls.module.split("."))

    @cached_property
    def bucket(self) -> str:
        return self.get_bucket()

    @cached_property
    def bucket_with_versioning(self) -> str:
        return self.get_bucket_with_versioning()

    @classmethod
    def get_prefix(cls) -> str:
        return f"{prefix}/{cls.get_module_folders()}"

    @cached_property
    def prefix(self) -> str:
        return self.get_prefix()

    @classmethod
    def get_s3dir_root(cls) -> S3Path:
        return S3Path(
            cls.get_bucket(),
            cls.get_prefix(),
        ).to_dir()

    @classmethod
    def get_s3dir_root_with_versioning(cls) -> S3Path:
        return S3Path(
            cls.get_bucket_with_versioning(),
            cls.get_prefix(),
        ).to_dir()

    @cached_property
    def s3dir_root(self) -> S3Path:
        """
        The root S3 directory for testing in the regular S3 bucket.
        """
        return self.get_s3dir_root()

    @cached_property
    def s3dir_root_with_versioning(self) -> S3Path:
        """
        The root S3 directory for testing in the versioning S3 bucket.
        """
        return self.get_s3dir_root_with_versioning()

    def rprint_response(self, res: dict):
        """
        Pretty print the boto3 response.
        """
        if "ResponseMetadata" in res:
            res.pop("ResponseMetadata")
        rprint(res)

    def rprint(self, data):
        rprint(data)

    @property
    def s3_client(self) -> S3Client:
        """
        The boto3 S3 client the tests run against (moto or real AWS). Use it
        to verify S3 state with native calls.
        """
        return s3_context.s3_client

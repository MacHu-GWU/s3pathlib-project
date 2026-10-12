# -*- coding: utf-8 -*-

"""
Test the bucket methods of ``S3Path`` (``s3pathlib.core.bucket``).

Test order:

1. ``from_bucket``;
2. every instance method only accepts a bucket, and checks it before calling
   AWS;
3. ``create_bucket``: the region, a bucket that already exists, the arguments;
4. ``delete_bucket``;
5. the versioning methods;
6. ``list_buckets``: the data of each bucket, legacy names, pagination;
7. AWS errors raised as is.

Every test that creates or deletes a bucket uses its own temporary bucket
``s3pathlib-test-tmp-{uuid}``, never the shared test buckets. Arguments that
cannot be checked against AWS (ACL grants, MFA delete) are checked with
``botocore.stub.Stubber``.
"""

import contextlib
import uuid

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.exc import S3PathIsNotBucketError
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import delete_s3_prefix
from s3pathlib.tests.mock_aws import mock_only
from s3pathlib.tests.mock_aws import real_aws_only


def random_bucket_name() -> str:
    return f"s3pathlib-test-tmp-{uuid.uuid4().hex}"


def error_code(exc_info) -> str:
    return exc_info.value.response["Error"]["Code"]


# (method name, arguments) of every instance method that needs a bucket
INSTANCE_METHODS = [
    pytest.param("create_bucket", {}, id="create_bucket"),
    pytest.param("delete_bucket", {}, id="delete_bucket"),
    pytest.param("get_bucket_versioning", {}, id="get_bucket_versioning"),
    pytest.param("is_versioning_enabled", {}, id="is_versioning_enabled"),
    pytest.param("is_versioning_suspended", {}, id="is_versioning_suspended"),
    pytest.param(
        "put_bucket_versioning",
        {"enable_versioning": True},
        id="put_bucket_versioning",
    ),
]


class BucketMixin(BaseTest):
    module = "core.bucket"

    @pytest.fixture
    def new_bucket_name(self):
        """
        A function that returns a new temporary bucket name. Every bucket
        created with these names is emptied and deleted after the test.
        """
        names = list()

        def make() -> str:
            name = random_bucket_name()
            names.append(name)
            return name

        yield make
        for name in names:
            try:
                delete_s3_prefix(self.s3_client, name, "")
                self.s3_client.delete_bucket(Bucket=name)
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchBucket":
                    raise

    @pytest.fixture
    def tmp_bucket(self, new_bucket_name) -> str:
        """
        A new empty bucket, deleted after the test.
        """
        name = new_bucket_name()
        self.s3_client.create_bucket(Bucket=name)
        return name

    @contextlib.contextmanager
    def use_client(self, s3_client):
        """
        Make ``S3Path`` methods call AWS through ``s3_client``, e.g. a stubbed
        client or a client in another region.
        """
        s3_context.attach_s3_client(s3_client)
        try:
            yield
        finally:
            s3_context.attach_s3_client(self.s3_client)

    @contextlib.contextmanager
    def stub(self):
        """
        A ``Stubber`` on a new client, used by ``S3Path`` methods inside the
        block. Every expected response must be consumed.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        with stubber, self.use_client(s3_client):
            yield stubber
        stubber.assert_no_pending_responses()

    def get_location(self, bucket: str) -> str | None:
        res = self.s3_client.get_bucket_location(Bucket=bucket)
        return res.get("LocationConstraint")

    # --------------------------------------------------------------------------
    # 1. from_bucket
    # --------------------------------------------------------------------------
    def test_from_bucket_skips_naming_rules(self):
        """
        ``from_bucket`` accepts a legacy bucket name (uppercase, underscore),
        because S3, not s3pathlib, is the authority on bucket names.
        """
        p = S3Path.from_bucket("My_Legacy_Bucket")
        assert p.is_bucket()
        assert p.uri == "s3://My_Legacy_Bucket/"

    @pytest.mark.parametrize(
        "bucket",
        [
            pytest.param("", id="empty"),
            pytest.param("bucket/key", id="path"),
            pytest.param("s3://bucket", id="uri"),
            pytest.param("arn:aws:s3:::bucket", id="arn"),
        ],
    )
    def test_from_bucket_invalid_format(self, bucket):
        """
        Only a single bucket name is accepted, not a path, a URI or an ARN.
        """
        with pytest.raises(S3ValidationError, match="is not a bucket name"):
            S3Path.from_bucket(bucket)

    # --------------------------------------------------------------------------
    # 2. Only a bucket
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("key", ["folder/", "file.txt"])
    @pytest.mark.parametrize("method, kwargs", INSTANCE_METHODS)
    def test_not_a_bucket(self, method, kwargs, key):
        """
        A folder or a file is rejected before any AWS call, so that e.g.
        ``delete_bucket`` on a folder never touches the bucket.
        """
        p = S3Path(self.bucket, key)
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(S3PathIsNotBucketError, match="is not a bucket"):
                getattr(p, method)(**kwargs)
        assert calls == []

    # --------------------------------------------------------------------------
    # 3. create_bucket
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "client_region, location",
        [
            pytest.param("us-east-1", None, id="us-east-1"),
            pytest.param("us-west-2", "us-west-2", id="us-west-2"),
        ],
    )
    def test_create_bucket_in_client_region(
        self,
        new_bucket_name,
        client_region,
        location,
    ):
        """
        Without ``region``, the bucket is created in the region of the client.
        Always asking for ``us-east-1`` is rejected by S3 from a client in any
        other region (``IllegalLocationConstraintException``).
        """
        p = S3Path.from_bucket(new_bucket_name())
        s3_client = self.boto_ses.client("s3", region_name=client_region)
        with self.use_client(s3_client):
            p.create_bucket()
        assert self.get_location(p.bucket) == location

    def test_create_bucket_in_given_region(self, new_bucket_name):
        """
        ``region`` is sent as the ``LocationConstraint``; a client in
        ``us-east-1`` can create a bucket in any region.
        """
        p = S3Path.from_bucket(new_bucket_name())
        p.create_bucket(region="us-west-1")
        assert self.get_location(p.bucket) == "us-west-1"

    def test_create_bucket_us_east_1_already_owned(self, tmp_bucket):
        """
        In ``us-east-1``, creating a bucket you already own succeeds (a legacy
        behavior of S3, documented in the docstring).
        """
        p = S3Path.from_bucket(tmp_bucket)
        res = p.create_bucket()
        assert res["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_create_bucket_other_region_already_owned(self, new_bucket_name):
        """
        In any other region, creating a bucket you already own raises
        ``BucketAlreadyOwnedByYou`` as is.
        """
        p = S3Path.from_bucket(new_bucket_name())
        p.create_bucket(region="us-west-1")
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.create_bucket(region="us-west-1")
        assert error_code(exc_info) == "BucketAlreadyOwnedByYou"

    @real_aws_only("moto has no global bucket namespace, any name can be created")
    def test_create_bucket_of_other_account(self):
        """
        A name owned by another AWS account raises ``BucketAlreadyExists`` as
        is.
        """
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            S3Path.from_bucket("aws").create_bucket()
        assert error_code(exc_info) == "BucketAlreadyExists"

    def test_create_bucket_arguments_passed_to_boto3(self):
        """
        Every argument is sent under its boto3 name.
        """
        with self.stub() as stubber:
            stubber.add_response(
                "create_bucket",
                {"Location": "/my-bucket"},
                expected_params={
                    "Bucket": "my-bucket",
                    "ACL": "private",
                    "CreateBucketConfiguration": {"LocationConstraint": "us-west-1"},
                    "GrantFullControl": "id=full",
                    "GrantRead": "id=read",
                    "GrantReadACP": "id=read-acp",
                    "GrantWrite": "id=write",
                    "GrantWriteACP": "id=write-acp",
                    "ObjectLockEnabledForBucket": True,
                    "ObjectOwnership": "BucketOwnerEnforced",
                },
            )
            res = S3Path.from_bucket("my-bucket").create_bucket(
                region="us-west-1",
                acl="private",
                grant_full_control="id=full",
                grant_read="id=read",
                grant_read_acp="id=read-acp",
                grant_write="id=write",
                grant_write_acp="id=write-acp",
                object_lock_enabled_for_bucket=True,
                object_ownership="BucketOwnerEnforced",
            )
        assert res["Location"] == "/my-bucket"

    # --------------------------------------------------------------------------
    # 4. delete_bucket
    # --------------------------------------------------------------------------
    def test_delete_bucket(self, tmp_bucket):
        """
        The bucket is deleted, and the path is not changed: a bucket from
        ``list_buckets`` keeps its snapshot.
        """
        p = [b for b in S3Path.list_buckets() if b.bucket == tmp_bucket][0]
        snapshot = p.response
        assert "LastModified" in snapshot
        res = p.delete_bucket()
        assert res["ResponseMetadata"]["HTTPStatusCode"] == 204
        assert p.response == snapshot
        # real AWS takes a while to propagate a bucket deletion
        if self.use_mock:
            with pytest.raises(botocore.exceptions.ClientError) as exc_info:
                self.s3_client.head_bucket(Bucket=tmp_bucket)
            assert error_code(exc_info) == "404"

    def test_delete_bucket_not_empty(self, tmp_bucket):
        """
        A bucket with objects raises ``BucketNotEmpty`` as is.
        """
        self.s3_client.put_object(Bucket=tmp_bucket, Key="file.txt", Body=b"")
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            S3Path.from_bucket(tmp_bucket).delete_bucket()
        assert error_code(exc_info) == "BucketNotEmpty"

    @real_aws_only("moto has no global bucket namespace, any bucket can be deleted")
    def test_delete_bucket_of_other_account(self):
        """
        A bucket of another AWS account raises ``AccessDenied`` as is.
        """
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            S3Path.from_bucket("aws").delete_bucket()
        assert error_code(exc_info) == "AccessDenied"

    # --------------------------------------------------------------------------
    # 5. Versioning
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "status, is_enabled, is_suspended",
        [
            pytest.param(None, False, False, id="never"),
            pytest.param("Enabled", True, False, id="enabled"),
            pytest.param("Suspended", False, True, id="suspended"),
        ],
    )
    def test_versioning_state(self, tmp_bucket, status, is_enabled, is_suspended):
        """
        The three versioning states of a bucket; a bucket that never had
        versioning has no ``Status`` and is neither enabled nor suspended.
        """
        if status is not None:
            self.s3_client.put_bucket_versioning(
                Bucket=tmp_bucket,
                VersioningConfiguration={"Status": status},
            )
        p = S3Path.from_bucket(tmp_bucket)
        assert p.get_bucket_versioning().get("Status") == status
        assert p.is_versioning_enabled() is is_enabled
        assert p.is_versioning_suspended() is is_suspended

    @pytest.mark.parametrize(
        "enable_versioning, status",
        [
            pytest.param(True, "Enabled", id="enable"),
            pytest.param(False, "Suspended", id="suspend"),
        ],
    )
    def test_put_bucket_versioning(self, tmp_bucket, enable_versioning, status):
        """
        ``enable_versioning`` maps to ``Enabled`` / ``Suspended``; suspending a
        bucket that never had versioning makes it suspended.
        """
        S3Path.from_bucket(tmp_bucket).put_bucket_versioning(enable_versioning)
        res = self.s3_client.get_bucket_versioning(Bucket=tmp_bucket)
        assert res["Status"] == status

    def test_put_bucket_versioning_mfa_delete_disabled(self, tmp_bucket):
        """
        ``enable_mfa_delete=False`` works without MFA on a bucket whose MFA
        delete is off (``MFADelete`` is sent as a string, not a bool).
        """
        p = S3Path.from_bucket(tmp_bucket)
        p.put_bucket_versioning(True, enable_mfa_delete=False)
        res = self.s3_client.get_bucket_versioning(Bucket=tmp_bucket)
        assert res["Status"] == "Enabled"
        if self.use_mock:
            # moto does not return MFADelete
            assert "MFADelete" not in res
        else:
            assert res["MFADelete"] == "Disabled"

    @pytest.mark.parametrize(
        "enable_versioning, enable_mfa_delete, versioning_configuration",
        [
            pytest.param(
                False,
                True,
                {"Status": "Suspended", "MFADelete": "Enabled"},
                id="suspend-mfa-on",
            ),
            pytest.param(
                True,
                False,
                {"Status": "Enabled", "MFADelete": "Disabled"},
                id="enable-mfa-off",
            ),
            pytest.param(
                True,
                None,
                {"Status": "Enabled"},
                id="mfa-none-not-sent",
            ),
        ],
    )
    def test_put_bucket_versioning_arguments_passed_to_boto3(
        self,
        enable_versioning,
        enable_mfa_delete,
        versioning_configuration,
    ):
        """
        ``enable_mfa_delete`` only sets ``MFADelete`` and leaves ``Status`` as
        given by ``enable_versioning``;
        ``None`` (the default) does not send ``MFADelete``; the
        other arguments are sent under their boto3 names. Enabling MFA delete
        needs the root user and an MFA device, so it is only stubbed.
        """
        with self.stub() as stubber:
            stubber.add_response(
                "put_bucket_versioning",
                {},
                expected_params={
                    "Bucket": "my-bucket",
                    "ChecksumAlgorithm": "SHA256",
                    "VersioningConfiguration": versioning_configuration,
                    "MFA": "arn:aws:iam::111122223333:mfa/root 123456",
                    "ExpectedBucketOwner": "111122223333",
                },
            )
            S3Path.from_bucket("my-bucket").put_bucket_versioning(
                enable_versioning,
                enable_mfa_delete=enable_mfa_delete,
                checksum_algorithm="SHA256",
                mfa="arn:aws:iam::111122223333:mfa/root 123456",
                expected_bucket_owner="111122223333",
            )

    @pytest.mark.parametrize(
        "method, operation",
        [
            pytest.param("delete_bucket", "delete_bucket", id="delete_bucket"),
            pytest.param(
                "get_bucket_versioning",
                "get_bucket_versioning",
                id="get_bucket_versioning",
            ),
        ],
    )
    def test_expected_bucket_owner_passed_to_boto3(self, method, operation):
        """
        ``expected_bucket_owner`` is sent as ``ExpectedBucketOwner``.
        """
        with self.stub() as stubber:
            stubber.add_response(
                operation,
                {},
                expected_params={
                    "Bucket": "my-bucket",
                    "ExpectedBucketOwner": "111122223333",
                },
            )
            p = S3Path.from_bucket("my-bucket")
            getattr(p, method)(expected_bucket_owner="111122223333")

    # --------------------------------------------------------------------------
    # 6. list_buckets
    # --------------------------------------------------------------------------
    def test_list_buckets(self, tmp_bucket):
        """
        Each bucket is a bucket ``S3Path``; ``last_modified_at`` is its
        creation date and ``response["BucketRegion"]`` its region (real AWS
        returns it for a paginated request, moto does not).
        """
        s3bucket_list = S3Path.list_buckets()
        assert all(p.is_bucket() for p in s3bucket_list)
        s3bucket = {p.bucket: p for p in s3bucket_list}[tmp_bucket]

        res = self.s3_client.list_buckets()
        creation_date = {dct["Name"]: dct["CreationDate"] for dct in res["Buckets"]}[
            tmp_bucket
        ]
        assert s3bucket.last_modified_at == creation_date
        if self.use_mock:
            assert "BucketRegion" not in s3bucket.response
        else:
            assert s3bucket.response["BucketRegion"] == "us-east-1"

    @mock_only("a legacy bucket name cannot be created on real AWS any more")
    def test_list_buckets_with_legacy_bucket(self):
        """
        A legacy bucket returned by ListBuckets does not break
        ``list_buckets()``.
        """
        self.s3_client.create_bucket(Bucket="My_Legacy_Bucket")
        try:
            uris = [s3bucket.uri for s3bucket in S3Path.list_buckets()]
            assert "s3://My_Legacy_Bucket/" in uris
        finally:
            self.s3_client.delete_bucket(Bucket="My_Legacy_Bucket")

    def test_list_buckets_all_pages(self):
        """
        Every page is fetched, 10,000 buckets at a time: a request without
        ``MaxBuckets`` is rejected by S3 for an account allowed to have more
        than 10,000 buckets.
        """
        with self.stub() as stubber:
            stubber.add_response(
                "list_buckets",
                {
                    "Buckets": [
                        {"Name": "bucket-1", "CreationDate": "2024-01-01"},
                        {"Name": "bucket-2", "CreationDate": "2024-01-02"},
                    ],
                    "ContinuationToken": "token-1",
                },
                expected_params={"MaxBuckets": 10000},
            )
            stubber.add_response(
                "list_buckets",
                {
                    "Buckets": [
                        {
                            "Name": "bucket-3",
                            "CreationDate": "2024-01-03",
                            "BucketRegion": "eu-west-1",
                        },
                    ],
                },
                expected_params={"MaxBuckets": 10000, "ContinuationToken": "token-1"},
            )
            s3bucket_list = S3Path.list_buckets()
        assert [p.bucket for p in s3bucket_list] == ["bucket-1", "bucket-2", "bucket-3"]
        assert s3bucket_list[2].response["BucketRegion"] == "eu-west-1"

    def test_list_buckets_no_bucket(self):
        """
        An account without bucket (S3 omits ``Buckets``) gives an empty list.
        """
        with self.stub() as stubber:
            stubber.add_response(
                "list_buckets",
                {},
                expected_params={"MaxBuckets": 10000},
            )
            assert S3Path.list_buckets() == []

    # --------------------------------------------------------------------------
    # 7. AWS errors
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "method, kwargs",
        [param for param in INSTANCE_METHODS if param.id != "create_bucket"],
    )
    def test_missing_bucket(self, method, kwargs):
        """
        A missing bucket raises ``NoSuchBucket`` as is.
        """
        p = S3Path.from_bucket(random_bucket_name())
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            getattr(p, method)(**kwargs)
        assert error_code(exc_info) == "NoSuchBucket"


class TestMock(BucketMixin):
    use_mock = True


class TestRealAws(BucketMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.bucket",
        preview=False,
    )

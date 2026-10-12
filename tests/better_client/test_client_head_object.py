# -*- coding: utf-8 -*-

"""
Test ``head_object`` and ``is_object_exists``.

Test order:

1. ``head_object``: an existing object, dir markers, every argument is passed
   to boto3;
2. "not found": a missing key or bucket, delete markers (latest version, or
   ``version_id`` pointing at one), old versions;
3. errors: 404 is recognized by its code, 403 becomes ``S3PermissionDenied``,
   other errors (412, 304) are raised as is;
4. ``is_object_exists``, which follows the same rules.
"""

import datetime
import uuid

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.better_client.head_object import head_object
from s3pathlib.better_client.head_object import is_object_exists
from s3pathlib.exc import S3FileNotExist
from s3pathlib.exc import S3PermissionDenied
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only


class HeadObjectMixin(BaseTest):
    module = "better_client.head_object"

    def put(self, key: str, body: bytes = b"hello", versioning: bool = False) -> dict:
        """
        Put an object under the folder of the test, with a plain boto3 call.
        """
        if versioning:
            s3dir = self.s3dir_test_with_versioning
        else:
            s3dir = self.s3dir_test
        return self.s3_client.put_object(
            Bucket=s3dir.bucket,
            Key=s3dir.key + key,
            Body=body,
        )

    def stub(self) -> tuple:
        """
        A new client and its stubber, to fake a response.
        """
        s3_client = self.boto_ses.client("s3")
        return s3_client, Stubber(s3_client)

    # --------------------------------------------------------------------------
    # 1. head_object
    # --------------------------------------------------------------------------
    def test_existing_object(self):
        """
        Returns the head_object response.
        """
        res_put = self.put("file.txt", b"hello")
        res = head_object(self.s3_client, self.bucket, self.s3dir_test.key + "file.txt")
        assert res["ContentLength"] == 5
        assert res["ETag"] == res_put["ETag"]

    def test_dir_marker(self):
        """
        A key ending with ``/`` is an object like any other; without the ``/``
        it is another key, which does not exist.
        """
        self.put("folder/", b"")
        key = self.s3dir_test.key + "folder"
        res = head_object(self.s3_client, self.bucket, key + "/")
        assert res["ContentLength"] == 0
        assert (
            head_object(self.s3_client, self.bucket, key, ignore_not_found=True) is None
        )

    def test_arguments_passed_to_boto3(self):
        """
        Every argument is passed to boto3 under its API name, and arguments
        left out are not sent at all.
        """
        s3_client, stubber = self.stub()
        dt = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        stubber.add_response(
            "head_object",
            {"ContentLength": 5},
            expected_params={
                "Bucket": "my-bucket",
                "Key": "file.txt",
                "IfMatch": "etag-1",
                "IfModifiedSince": dt,
                "IfNoneMatch": "etag-2",
                "IfUnmodifiedSince": dt,
                "Range": "bytes=0-1",
                "VersionId": "v1",
                "SSECustomerAlgorithm": "AES256",
                "SSECustomerKey": "k" * 32,
                "RequestPayer": "requester",
                "PartNumber": 1,
                "ExpectedBucketOwner": "111122223333",
                "ChecksumMode": "ENABLED",
            },
        )
        stubber.add_response(
            "head_object",
            {"ContentLength": 5},
            expected_params={"Bucket": "my-bucket", "Key": "file.txt"},
        )
        with stubber:
            res = head_object(
                s3_client,
                "my-bucket",
                "file.txt",
                if_match="etag-1",
                if_modified_since=dt,
                if_none_match="etag-2",
                if_unmodified_since=dt,
                range="bytes=0-1",
                version_id="v1",
                sse_customer_algorithm="AES256",
                sse_customer_key="k" * 32,
                request_payer="requester",
                part_number=1,
                expected_bucket_owner="111122223333",
                checksum_mode="ENABLED",
            )
            assert res["ContentLength"] == 5
            head_object(s3_client, "my-bucket", "file.txt")
        stubber.assert_no_pending_responses()

    # --------------------------------------------------------------------------
    # 2. Not found
    # --------------------------------------------------------------------------
    def test_missing_key(self):
        """
        A missing key raises ``S3FileNotExist`` with the URI, or gives ``None``
        with ``ignore_not_found=True``.
        """
        key = self.s3dir_test.key + "missing.txt"
        with pytest.raises(S3FileNotExist) as exc_info:
            head_object(self.s3_client, self.bucket, key)
        assert str(exc_info.value) == (
            f"S3 object 's3://{self.bucket}/{key}' does not exist!"
        )
        assert isinstance(exc_info.value.__cause__, botocore.exceptions.ClientError)
        assert (
            head_object(self.s3_client, self.bucket, key, ignore_not_found=True) is None
        )

    def test_missing_bucket(self):
        """
        A missing bucket is "not found" too: S3 answers 404 to a HEAD request
        either way. moto raises ``NoSuchBucket`` instead; it is handled the
        same, so code tested with moto behaves as on AWS.
        """
        bucket = f"s3pathlib-test-tmp-{uuid.uuid4().hex}"
        with pytest.raises(S3FileNotExist, match=f"s3://{bucket}/file.txt"):
            head_object(self.s3_client, bucket, "file.txt")
        assert (
            head_object(self.s3_client, bucket, "file.txt", ignore_not_found=True)
            is None
        )

    def test_versions_and_delete_markers(self):
        """
        When the latest version is a delete marker, the object does not exist,
        but an old version can still be read with ``version_id``. A
        ``version_id`` pointing at a delete marker (S3 answers 405) does not
        exist either, and the error names the version.
        """
        s3dir = self.s3dir_test_with_versioning
        key = s3dir.key + "file.txt"
        v1 = self.put("file.txt", b"v1", versioning=True)["VersionId"]
        res = self.s3_client.delete_object(Bucket=s3dir.bucket, Key=key)
        v_marker = res["VersionId"]

        assert (
            head_object(self.s3_client, s3dir.bucket, key, ignore_not_found=True)
            is None
        )
        res = head_object(self.s3_client, s3dir.bucket, key, version_id=v1)
        assert res["VersionId"] == v1
        assert res["ContentLength"] == 2

        with pytest.raises(S3FileNotExist) as exc_info:
            head_object(self.s3_client, s3dir.bucket, key, version_id=v_marker)
        assert str(exc_info.value) == (
            f"S3 object 's3://{s3dir.bucket}/{key}' version {v_marker!r} "
            "does not exist!"
        )
        res = head_object(
            self.s3_client,
            s3dir.bucket,
            key,
            version_id=v_marker,
            ignore_not_found=True,
        )
        assert res is None

    def test_version_of_another_key(self):
        """
        A version id that belongs to another key does not exist for this key.
        """
        s3dir = self.s3dir_test_with_versioning
        v_other = self.put("other.txt", versioning=True)["VersionId"]
        self.put("file.txt", versioning=True)
        res = head_object(
            self.s3_client,
            s3dir.bucket,
            s3dir.key + "file.txt",
            version_id=v_other,
            ignore_not_found=True,
        )
        assert res is None

    # --------------------------------------------------------------------------
    # 3. Errors
    # --------------------------------------------------------------------------
    def test_not_found_by_code(self):
        """
        404 is recognized by its code, not by the message (a HEAD response has
        no body).
        """
        s3_client, stubber = self.stub()
        stubber.add_client_error("head_object", "404", http_status_code=404)
        with stubber:
            assert head_object(s3_client, "b", "k", ignore_not_found=True) is None

    @pytest.mark.parametrize("ignore_not_found", [False, True])
    def test_forbidden(self, ignore_not_found):
        """
        403 raises ``S3PermissionDenied`` with the reason, even with
        ``ignore_not_found=True``: no permission is not "not found". Before
        3.0 the ``ClientError`` was raised as is.
        """
        s3_client, stubber = self.stub()
        stubber.add_client_error("head_object", "403", http_status_code=403)
        with stubber:
            with pytest.raises(S3PermissionDenied) as exc_info:
                head_object(s3_client, "b", "k", ignore_not_found=ignore_not_found)
        assert str(exc_info.value).startswith(
            "no permission to read S3 object 's3://b/k': "
        )
        assert isinstance(exc_info.value.__cause__, botocore.exceptions.ClientError)

    @real_aws_only("moto does not model buckets of other accounts (NoSuchBucket)")
    def test_forbidden_bucket_of_other_account(self):
        """
        The bucket ``aws`` belongs to another account.
        """
        with pytest.raises(S3PermissionDenied, match="s3://aws/file.txt"):
            head_object(self.s3_client, "aws", "file.txt", ignore_not_found=True)

    def test_precondition_errors_raised(self):
        """
        A failed condition is not "not found": 412 (``if_match`` does not
        match) and 304 (``if_none_match`` matches) are raised as is.
        """
        etag = self.put("file.txt")["ETag"]
        key = self.s3dir_test.key + "file.txt"
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            head_object(self.s3_client, self.bucket, key, if_match='"0000"')
        assert exc_info.value.response["Error"]["Code"] == "412"
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            head_object(self.s3_client, self.bucket, key, if_none_match=etag)
        assert exc_info.value.response["Error"]["Code"] == "304"

    # --------------------------------------------------------------------------
    # 4. is_object_exists
    # --------------------------------------------------------------------------
    def test_is_object_exists(self):
        """
        ``True`` for an existing object, ``False`` for a missing key or bucket.
        """
        self.put("file.txt")
        key = self.s3dir_test.key + "file.txt"
        assert is_object_exists(self.s3_client, self.bucket, key) is True
        assert is_object_exists(self.s3_client, self.bucket, key + ".missing") is False
        bucket = f"s3pathlib-test-tmp-{uuid.uuid4().hex}"
        assert is_object_exists(self.s3_client, bucket, "file.txt") is False

    def test_is_object_exists_arguments_passed_to_boto3(self):
        """
        ``request_payer`` and ``expected_bucket_owner`` reach head_object.
        """
        s3_client, stubber = self.stub()
        stubber.add_response(
            "head_object",
            {"ContentLength": 5},
            expected_params={
                "Bucket": "my-bucket",
                "Key": "file.txt",
                "VersionId": "v1",
                "RequestPayer": "requester",
                "ExpectedBucketOwner": "111122223333",
            },
        )
        with stubber:
            assert (
                is_object_exists(
                    s3_client,
                    "my-bucket",
                    "file.txt",
                    version_id="v1",
                    request_payer="requester",
                    expected_bucket_owner="111122223333",
                )
                is True
            )
        stubber.assert_no_pending_responses()

    def test_is_object_exists_version(self):
        """
        ``version_id`` checks one version: an old version exists after the
        object is deleted, the delete marker does not.
        """
        s3dir = self.s3dir_test_with_versioning
        key = s3dir.key + "file.txt"
        v1 = self.put("file.txt", versioning=True)["VersionId"]
        v_marker = self.s3_client.delete_object(Bucket=s3dir.bucket, Key=key)[
            "VersionId"
        ]
        assert is_object_exists(self.s3_client, s3dir.bucket, key) is False
        assert (
            is_object_exists(self.s3_client, s3dir.bucket, key, version_id=v1) is True
        )
        assert (
            is_object_exists(self.s3_client, s3dir.bucket, key, version_id=v_marker)
            is False
        )

    def test_is_object_exists_forbidden(self):
        """
        No permission raises ``S3PermissionDenied``; it is not ``False``.
        """
        s3_client, stubber = self.stub()
        stubber.add_client_error("head_object", "403", http_status_code=403)
        with stubber:
            with pytest.raises(S3PermissionDenied):
                is_object_exists(s3_client, "b", "k")


class TestMock(HeadObjectMixin):
    use_mock = True


class TestRealAws(HeadObjectMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.better_client.head_object",
        preview=False,
    )

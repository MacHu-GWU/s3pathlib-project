# -*- coding: utf-8 -*-

"""
Test ``update_bucket_tagging`` and ``update_object_tagging``.

Test order:

1. bucket tagging: merge like ``dict.update``, special characters, arguments
   passed to boto3, errors;
2. object tagging: merge, special characters, versions and delete markers,
   arguments passed to boto3, errors.

Errors of the AWS calls are raised as is (see "Errors" in ``CLAUDE.md``), so
the error tests check the boto3 error code.

Bucket tagging changes the bucket itself, so each test uses its own temporary
bucket instead of the shared test buckets (tests run in parallel on CI).
S3 does not keep the order of the tags, so tags are compared as dicts.
"""

import uuid

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.better_client.tagging import update_bucket_tagging
from s3pathlib.better_client.tagging import update_object_tagging
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only

# values that need URL encoding in the Tagging header of put_object; the
# space is sent as %20 (see s3pathlib.tag)
SPECIAL_TAGS = {
    "space": "a b",
    "plus": "a+b",
    "unicode": "中文",
    "symbols": "=:/@._-",
}


def random_bucket_name() -> str:
    return f"s3pathlib-test-tmp-{uuid.uuid4().hex}"


def to_dict(tag_set: list) -> dict:
    return {tag["Key"]: tag["Value"] for tag in tag_set}


def error_code(exc_info) -> str:
    return exc_info.value.response["Error"]["Code"]


class TaggingMixin(BaseTest):
    module = "better_client.tagging"

    @pytest.fixture
    def tmp_bucket(self):
        """
        A new empty bucket, deleted after the test.
        """
        bucket = random_bucket_name()
        self.s3_client.create_bucket(Bucket=bucket)
        yield bucket
        self.s3_client.delete_bucket(Bucket=bucket)

    def get_bucket_tags(self, bucket: str) -> dict:
        res = self.s3_client.get_bucket_tagging(Bucket=bucket)
        return to_dict(res["TagSet"])

    def put(self, name: str, versioning: bool = False) -> tuple[str, str, dict]:
        """
        Put an object under the folder of the test.

        :return: bucket, key, put_object response
        """
        if versioning:
            s3dir = self.s3dir_test_with_versioning
        else:
            s3dir = self.s3dir_test
        key = s3dir.key + name
        res = self.s3_client.put_object(Bucket=s3dir.bucket, Key=key, Body=b"x")
        return s3dir.bucket, key, res

    def get_object_tags(self, bucket: str, key: str, version_id: str = None) -> dict:
        kwargs = dict(Bucket=bucket, Key=key)
        if version_id is not None:
            kwargs["VersionId"] = version_id
        res = self.s3_client.get_object_tagging(**kwargs)
        return to_dict(res["TagSet"])

    def stub(self) -> tuple:
        s3_client = self.boto_ses.client("s3")
        return s3_client, Stubber(s3_client)

    # --------------------------------------------------------------------------
    # 1. Bucket tagging
    # --------------------------------------------------------------------------
    def test_bucket_merge(self, tmp_bucket):
        """
        The first update adds tags to a bucket without tags; the next one adds
        and overwrites keys and keeps the others. The return value is all the
        tags, as stored by S3.
        """
        tags = update_bucket_tagging(
            self.s3_client, tmp_bucket, {"k1": "v1", "k2": "v2"}
        )
        assert tags == {"k1": "v1", "k2": "v2"}
        assert self.get_bucket_tags(tmp_bucket) == tags

        tags = update_bucket_tagging(
            self.s3_client, tmp_bucket, {"k2": "v22", "k3": "v3"}
        )
        assert tags == {"k1": "v1", "k2": "v22", "k3": "v3"}
        assert self.get_bucket_tags(tmp_bucket) == tags

    def test_bucket_special_values(self, tmp_bucket):
        """
        Spaces, ``+``, non-ASCII and symbols are stored as given.
        """
        update_bucket_tagging(self.s3_client, tmp_bucket, SPECIAL_TAGS)
        assert self.get_bucket_tags(tmp_bucket) == SPECIAL_TAGS

    def test_bucket_arguments_passed_to_boto3(self):
        """
        The arguments reach both API calls under their API names.
        """
        s3_client, stubber = self.stub()
        stubber.add_response(
            "get_bucket_tagging",
            {"TagSet": [{"Key": "old", "Value": "1"}]},
            expected_params={
                "Bucket": "my-bucket",
                "ExpectedBucketOwner": "111122223333",
            },
        )
        stubber.add_response(
            "put_bucket_tagging",
            {},
            expected_params={
                "Bucket": "my-bucket",
                "Tagging": {
                    "TagSet": [
                        {"Key": "old", "Value": "1"},
                        {"Key": "new", "Value": "2"},
                    ]
                },
                "ChecksumAlgorithm": "SHA256",
                "ExpectedBucketOwner": "111122223333",
            },
        )
        with stubber:
            tags = update_bucket_tagging(
                s3_client,
                "my-bucket",
                {"new": "2"},
                checksum_algorithm="SHA256",
                expected_bucket_owner="111122223333",
            )
        assert tags == {"old": "1", "new": "2"}
        stubber.assert_no_pending_responses()

    def test_bucket_without_tags_by_code(self):
        """
        A bucket without tags is recognized by the code ``NoSuchTagSet``, not by
        the message.
        """
        s3_client, stubber = self.stub()
        stubber.add_client_error(
            "get_bucket_tagging", "NoSuchTagSet", http_status_code=404
        )
        stubber.add_response("put_bucket_tagging", {})
        with stubber:
            assert update_bucket_tagging(s3_client, "my-bucket", {"k": "v"}) == {
                "k": "v"
            }

    def test_bucket_missing(self):
        """
        A missing bucket raises boto3's ``NoSuchBucket`` as is.
        """
        with pytest.raises(self.s3_client.exceptions.NoSuchBucket):
            update_bucket_tagging(self.s3_client, random_bucket_name(), {"k": "v"})

    @pytest.mark.parametrize("failing_call", ["get", "put"])
    def test_bucket_error_raised_as_is(self, failing_call):
        """
        An error of either call is raised as is.
        """
        s3_client, stubber = self.stub()
        if failing_call == "get":
            stubber.add_client_error(
                "get_bucket_tagging", "AccessDenied", http_status_code=403
            )
        else:
            stubber.add_response("get_bucket_tagging", {"TagSet": []})
            stubber.add_client_error(
                "put_bucket_tagging", "AccessDenied", http_status_code=403
            )
        with stubber:
            with pytest.raises(botocore.exceptions.ClientError) as exc_info:
                update_bucket_tagging(s3_client, "my-bucket", {"k": "v"})
        assert error_code(exc_info) == "AccessDenied"

    @real_aws_only("moto does not model buckets of other accounts (NoSuchBucket)")
    def test_bucket_of_other_account(self):
        """
        The bucket ``aws`` belongs to another account: ``AccessDenied``.
        """
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            update_bucket_tagging(self.s3_client, "aws", {"k": "v"})
        assert error_code(exc_info) == "AccessDenied"

    # --------------------------------------------------------------------------
    # 2. Object tagging
    # --------------------------------------------------------------------------
    def test_object_merge(self):
        """
        Same merge as for a bucket. In a bucket without versioning, the
        returned version is ``None``.
        """
        bucket, key, _ = self.put("file.txt")
        version_id, tags = update_object_tagging(
            self.s3_client, bucket, key, {"k1": "v1", "k2": "v2"}
        )
        assert version_id is None
        assert tags == {"k1": "v1", "k2": "v2"}
        assert self.get_object_tags(bucket, key) == tags

        _, tags = update_object_tagging(
            self.s3_client, bucket, key, {"k2": "v22", "k3": "v3"}
        )
        assert tags == {"k1": "v1", "k2": "v22", "k3": "v3"}
        assert self.get_object_tags(bucket, key) == tags

    def test_object_special_values(self):
        """
        Spaces, ``+``, non-ASCII and symbols are stored as given.
        """
        bucket, key, _ = self.put("file.txt")
        update_object_tagging(self.s3_client, bucket, key, SPECIAL_TAGS)
        assert self.get_object_tags(bucket, key) == SPECIAL_TAGS

    def test_object_versions(self):
        """
        Without ``version_id`` the latest version is updated and returned; with
        ``version_id`` only that version is. The other version is untouched.
        """
        bucket, key, res = self.put("file.txt", versioning=True)
        v1 = res["VersionId"]
        _, _, res = self.put("file.txt", versioning=True)
        v2 = res["VersionId"]

        version_id, tags = update_object_tagging(
            self.s3_client, bucket, key, {"latest": "1"}
        )
        assert version_id == v2
        assert tags == {"latest": "1"}
        assert self.get_object_tags(bucket, key, v1) == {}

        version_id, tags = update_object_tagging(
            self.s3_client, bucket, key, {"old": "1"}, version_id=v1
        )
        assert version_id == v1
        assert tags == {"old": "1"}
        assert self.get_object_tags(bucket, key, v2) == {"latest": "1"}

    def test_object_arguments_passed_to_boto3(self):
        """
        The arguments reach both API calls under their API names, and the put
        targets the version returned by the get.
        """
        s3_client, stubber = self.stub()
        stubber.add_response(
            "get_object_tagging",
            {"TagSet": [{"Key": "old", "Value": "1"}], "VersionId": "v1"},
            expected_params={
                "Bucket": "my-bucket",
                "Key": "file.txt",
                "VersionId": "v1",
                "ExpectedBucketOwner": "111122223333",
                "RequestPayer": "requester",
            },
        )
        stubber.add_response(
            "put_object_tagging",
            {"VersionId": "v1"},
            expected_params={
                "Bucket": "my-bucket",
                "Key": "file.txt",
                "Tagging": {
                    "TagSet": [
                        {"Key": "old", "Value": "1"},
                        {"Key": "new", "Value": "2"},
                    ]
                },
                "VersionId": "v1",
                "ContentMD5": "md5",
                "ChecksumAlgorithm": "SHA256",
                "ExpectedBucketOwner": "111122223333",
                "RequestPayer": "requester",
            },
        )
        with stubber:
            res = update_object_tagging(
                s3_client,
                "my-bucket",
                "file.txt",
                {"new": "2"},
                version_id="v1",
                content_md5="md5",
                checksum_algorithm="SHA256",
                expected_bucket_owner="111122223333",
                request_payer="requester",
            )
        assert res == ("v1", {"old": "1", "new": "2"})
        stubber.assert_no_pending_responses()

    def test_object_missing(self):
        """
        A missing key raises ``NoSuchKey``, a missing bucket ``NoSuchBucket``,
        as is.
        """
        key = self.s3dir_test.key + "missing.txt"
        with pytest.raises(self.s3_client.exceptions.NoSuchKey):
            update_object_tagging(self.s3_client, self.bucket, key, {"k": "v"})
        with pytest.raises(self.s3_client.exceptions.NoSuchBucket):
            update_object_tagging(
                self.s3_client, random_bucket_name(), "file.txt", {"k": "v"}
            )

    def test_object_delete_marker(self):
        """
        A delete marker has no tags. Real S3 answers ``MethodNotAllowed`` when
        it is the latest version or ``version_id`` points at it; moto answers
        ``NoSuchKey`` / ``NoSuchVersion``. The error is raised as is.
        """
        bucket, key, _ = self.put("file.txt", versioning=True)
        res = self.s3_client.delete_object(Bucket=bucket, Key=key)
        v_marker = res["VersionId"]
        if self.use_mock:
            expected_latest = "NoSuchKey"
            expected_version = "NoSuchVersion"
        else:
            expected_latest = "MethodNotAllowed"
            expected_version = "MethodNotAllowed"

        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            update_object_tagging(self.s3_client, bucket, key, {"k": "v"})
        assert error_code(exc_info) == expected_latest
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            update_object_tagging(
                self.s3_client, bucket, key, {"k": "v"}, version_id=v_marker
            )
        assert error_code(exc_info) == expected_version

    @pytest.mark.parametrize("failing_call", ["get", "put"])
    def test_object_error_raised_as_is(self, failing_call):
        """
        An error of either call is raised as is.
        """
        s3_client, stubber = self.stub()
        if failing_call == "get":
            stubber.add_client_error(
                "get_object_tagging", "AccessDenied", http_status_code=403
            )
        else:
            stubber.add_response("get_object_tagging", {"TagSet": []})
            stubber.add_client_error(
                "put_object_tagging", "AccessDenied", http_status_code=403
            )
        with stubber:
            with pytest.raises(botocore.exceptions.ClientError) as exc_info:
                update_object_tagging(s3_client, "my-bucket", "file.txt", {"k": "v"})
        assert error_code(exc_info) == "AccessDenied"

    @real_aws_only("moto does not model buckets of other accounts (NoSuchBucket)")
    def test_object_of_other_account(self):
        """
        The bucket ``aws`` belongs to another account: ``AccessDenied``.
        """
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            update_object_tagging(self.s3_client, "aws", "file.txt", {"k": "v"})
        assert error_code(exc_info) == "AccessDenied"

    def test_object_too_many_tags(self):
        """
        S3 checks the limits: an object has at most 10 tags. The error is
        raised as is.
        """
        bucket, key, _ = self.put("file.txt")
        tags = {f"k{i}": "v" for i in range(11)}
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            update_object_tagging(self.s3_client, bucket, key, tags)
        assert exc_info.value.response["Error"]["Code"] == "BadRequest"


class TestMock(TaggingMixin):
    use_mock = True


class TestRealAws(TaggingMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.better_client.tagging",
        preview=False,
    )

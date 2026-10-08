# -*- coding: utf-8 -*-

"""
Test ``delete_object``, ``delete_dir``, ``delete_object_versions`` and
``delete_object_all_versions``.

Test order:

1. ``delete_object``: existing / missing keys, versions, arguments, the
   deprecated ``ignore_not_found``, errors;
2. ``delete_dir``: a folder, the prefix rule, ``limit``, versioning;
3. ``delete_object_versions``: a folder, the prefix rule, ``limit``;
4. ``delete_object_all_versions``: only the exact key (the hard delete bug);
5. deleting a whole bucket (``prefix=""``), on a temporary bucket only;
6. partial failures of ``delete_objects`` raise ``S3DeleteObjectsError``.

Errors of the AWS calls are raised as is (see "Errors" in ``CLAUDE.md``).
Any ``DeprecationWarning`` that a test does not expect with ``pytest.warns``
fails the test.
"""

import uuid

import botocore.exceptions
import pytest
from botocore.stub import ANY
from botocore.stub import Stubber

from s3pathlib.api import S3Path
from s3pathlib.better_client.delete_object import delete_dir
from s3pathlib.better_client.delete_object import delete_object
from s3pathlib.better_client.delete_object import delete_object_all_versions
from s3pathlib.better_client.delete_object import delete_object_versions
from s3pathlib.exc import S3DeleteObjectsError
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only

pytestmark = pytest.mark.filterwarnings("error::DeprecationWarning")


def random_bucket_name() -> str:
    return f"s3pathlib-test-tmp-{uuid.uuid4().hex}"


class DeleteObjectMixin(BaseTest):
    module = "better_client.delete_object"

    # --- helpers ---------------------------------------------------------------
    def put(self, keys: list[str], versioning: bool = False) -> tuple[str, str]:
        """
        Put objects under the folder of the test.

        :return: bucket, folder prefix
        """
        if versioning:
            s3dir = self.s3dir_test_with_versioning
        else:
            s3dir = self.s3dir_test
        for key in keys:
            if key.endswith("/"):
                body = b""
            else:
                body = b"x"
            self.s3_client.put_object(Bucket=s3dir.bucket, Key=s3dir.key + key, Body=body)
        return s3dir.bucket, s3dir.key

    def keys(self, bucket: str, prefix: str) -> list[str]:
        """
        The keys under the prefix (latest versions), relative to it.
        """
        res = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return sorted(dct["Key"][len(prefix):] for dct in res.get("Contents", []))

    def versions(self, bucket: str, prefix: str) -> list[str]:
        """
        One relative key per version and delete marker under the prefix.
        """
        res = self.s3_client.list_object_versions(Bucket=bucket, Prefix=prefix)
        keys = list()
        for kind in ["Versions", "DeleteMarkers"]:
            for dct in res.get(kind, []):
                keys.append(dct["Key"][len(prefix):])
        return sorted(keys)

    @pytest.fixture
    def tmp_bucket(self):
        """
        A new bucket, emptied and deleted after the test.
        """
        bucket = random_bucket_name()
        self.s3_client.create_bucket(Bucket=bucket)
        yield bucket
        res = self.s3_client.list_objects_v2(Bucket=bucket)
        for dct in res.get("Contents", []):
            self.s3_client.delete_object(Bucket=bucket, Key=dct["Key"])
        self.s3_client.delete_bucket(Bucket=bucket)

    # --------------------------------------------------------------------------
    # 1. delete_object
    # --------------------------------------------------------------------------
    def test_delete_object(self):
        """
        The object is deleted, the others are kept.
        """
        bucket, prefix = self.put(["a.txt", "b.txt"])
        delete_object(self.s3_client, bucket, prefix + "a.txt")
        assert self.keys(bucket, prefix) == ["b.txt"]

    def test_delete_object_missing_key(self):
        """
        Deleting a missing key succeeds. In a bucket with versioning, real S3
        adds a delete marker for it anyway; moto does not.
        """
        delete_object(self.s3_client, self.bucket, self.s3dir_test.key + "missing")

        s3dir = self.s3dir_test_with_versioning
        res = delete_object(self.s3_client, s3dir.bucket, s3dir.key + "missing")
        if self.use_mock:
            assert self.versions(s3dir.bucket, s3dir.key) == []
        else:
            assert res["DeleteMarker"] is True
            assert self.versions(s3dir.bucket, s3dir.key) == ["missing"]

    def test_delete_object_versions(self):
        """
        In a bucket with versioning, deleting adds a delete marker and returns
        it; deleting a ``version_id`` removes only that version.
        """
        bucket, prefix = self.put(["a.txt"], versioning=True)
        res = self.s3_client.put_object(Bucket=bucket, Key=prefix + "a.txt", Body=b"2")
        v2 = res["VersionId"]

        res = delete_object(self.s3_client, bucket, prefix + "a.txt", version_id=v2)
        assert res["VersionId"] == v2
        assert self.versions(bucket, prefix) == ["a.txt"]

        res = delete_object(self.s3_client, bucket, prefix + "a.txt")
        assert res["DeleteMarker"] is True
        assert self.keys(bucket, prefix) == []
        assert self.versions(bucket, prefix) == ["a.txt", "a.txt"]

    def test_delete_object_arguments_passed_to_boto3(self):
        """
        Every argument reaches delete_object under its API name.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        stubber.add_response(
            "delete_object",
            {},
            expected_params={
                "Bucket": "my-bucket",
                "Key": "file.txt",
                "VersionId": "v1",
                "MFA": "serial 123456",
                "RequestPayer": "requester",
                "BypassGovernanceRetention": True,
                "ExpectedBucketOwner": "111122223333",
            },
        )
        with stubber:
            delete_object(
                s3_client,
                "my-bucket",
                "file.txt",
                version_id="v1",
                mfa="serial 123456",
                request_payer="requester",
                bypass_governance_retention=True,
                expected_bucket_owner="111122223333",
            )
        stubber.assert_no_pending_responses()

    @pytest.mark.parametrize("value", [True, False])
    def test_delete_object_ignore_not_found_deprecated(self, value):
        """
        ``ignore_not_found`` has no effect (S3 never reports a missing key);
        passing it warns at the caller's line.
        """
        key = self.s3dir_test.key + "missing"
        with pytest.warns(DeprecationWarning, match="ignore_not_found is deprecated") as record:
            delete_object(self.s3_client, self.bucket, key, ignore_not_found=value)
        assert record[0].filename == __file__

    def test_delete_object_missing_bucket(self):
        """
        A missing bucket raises boto3's ``NoSuchBucket`` as is.
        """
        with pytest.raises(self.s3_client.exceptions.NoSuchBucket):
            delete_object(self.s3_client, random_bucket_name(), "file.txt")

    @real_aws_only("moto does not model buckets of other accounts (NoSuchBucket)")
    def test_delete_object_bucket_of_other_account(self):
        """
        The bucket ``aws`` belongs to another account: ``AccessDenied``.
        """
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            delete_object(self.s3_client, "aws", "file.txt")
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    # --------------------------------------------------------------------------
    # 2. delete_dir
    # --------------------------------------------------------------------------
    def test_delete_dir(self):
        """
        Every object under the folder is deleted, the folder marker too; a
        folder whose name starts the same (``folder-2/``) is kept.
        """
        bucket, prefix = self.put(
            ["folder/", "folder/a.txt", "folder/sub/b.txt", "folder-2/c.txt"]
        )
        count = delete_dir(self.s3_client, bucket, prefix + "folder/")
        assert count == 3
        assert self.keys(bucket, prefix) == ["folder-2/c.txt"]

    def test_delete_dir_prefix_must_be_a_folder(self):
        """
        A prefix that does not end with ``/`` is rejected before any call.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(S3ValidationError, match="doesn't represent s3 dir"):
                delete_dir(self.s3_client, self.bucket, self.s3dir_test.key + "folder")
        assert calls == []

    def test_delete_dir_limit(self):
        """
        ``limit`` caps the number of deleted objects, in key order.
        """
        bucket, prefix = self.put(["a.txt", "b.txt", "c.txt"])
        count = delete_dir(self.s3_client, bucket, prefix, limit=2, batch_size=1)
        assert count == 2
        assert self.keys(bucket, prefix) == ["c.txt"]

    def test_delete_dir_versioning(self):
        """
        In a bucket with versioning, the objects disappear but their versions
        are kept, behind delete markers.
        """
        bucket, prefix = self.put(["a.txt", "b.txt"], versioning=True)
        assert delete_dir(self.s3_client, bucket, prefix) == 2
        assert self.keys(bucket, prefix) == []
        assert self.versions(bucket, prefix) == ["a.txt", "a.txt", "b.txt", "b.txt"]

    # --------------------------------------------------------------------------
    # 3. delete_object_versions
    # --------------------------------------------------------------------------
    def test_delete_object_versions_folder(self):
        """
        Every version and delete marker under the folder is deleted; a folder
        whose name starts the same is kept.
        """
        bucket, prefix = self.put(
            ["folder/a.txt", "folder/a.txt", "folder/b.txt", "folder-2/c.txt"],
            versioning=True,
        )
        self.s3_client.delete_object(Bucket=bucket, Key=prefix + "folder/b.txt")
        count = delete_object_versions(self.s3_client, bucket, prefix + "folder/")
        assert count == 4
        assert self.versions(bucket, prefix) == ["folder-2/c.txt"]

    def test_delete_object_versions_prefix_must_be_a_folder(self):
        """
        A prefix that does not end with ``/`` is rejected: ``data/file.txt``
        would also match ``data/file.txt.bak``. Before 3.0 it deleted those.
        """
        bucket, prefix = self.put(["file.txt", "file.txt.bak"], versioning=True)
        with pytest.raises(S3ValidationError, match="doesn't represent s3 dir"):
            delete_object_versions(self.s3_client, bucket, prefix + "file.txt")
        assert self.versions(bucket, prefix) == ["file.txt", "file.txt.bak"]

    def test_delete_object_versions_limit(self):
        """
        ``limit`` caps the number of deleted versions and delete markers.
        """
        bucket, prefix = self.put(["a.txt", "b.txt", "c.txt"], versioning=True)
        count = delete_object_versions(self.s3_client, bucket, prefix, limit=2)
        assert count == 2
        assert len(self.versions(bucket, prefix)) == 1

    # --------------------------------------------------------------------------
    # 4. delete_object_all_versions
    # --------------------------------------------------------------------------
    def test_delete_object_all_versions(self):
        """
        All versions and delete markers of the key are deleted, and only those:
        keys that start with it are kept.
        """
        bucket, prefix = self.put(
            ["file.txt", "file.txt", "file.txt.bak", "file.txt2/x.csv"],
            versioning=True,
        )
        self.s3_client.delete_object(Bucket=bucket, Key=prefix + "file.txt")
        count = delete_object_all_versions(self.s3_client, bucket, prefix + "file.txt")
        assert count == 3
        assert self.versions(bucket, prefix) == ["file.txt.bak", "file.txt2/x.csv"]

    def test_delete_object_all_versions_missing_key(self):
        """
        A key without versions deletes nothing.
        """
        bucket, prefix = self.put(["file.txt.bak"], versioning=True)
        assert delete_object_all_versions(self.s3_client, bucket, prefix + "file.txt") == 0
        assert self.versions(bucket, prefix) == ["file.txt.bak"]

    def test_delete_object_all_versions_empty_key(self):
        """
        An empty key would mean every key of the bucket.
        """
        with pytest.raises(ValueError, match="key must not be empty"):
            delete_object_all_versions(self.s3_client, self.bucket, "")

    def test_s3path_hard_delete_keeps_similar_keys(self):
        """
        Regression test of ``S3Path.delete(is_hard_delete=True)`` on a file,
        which deleted every key starting with it. Move it to
        ``tests/core/test_core_delete.py`` when that file is migrated (#37).
        """
        bucket, prefix = self.put(
            ["file.txt", "file.txt.bak", "file.txt2/x.csv"],
            versioning=True,
        )
        S3Path(bucket, prefix + "file.txt").delete(is_hard_delete=True)
        assert self.versions(bucket, prefix) == ["file.txt.bak", "file.txt2/x.csv"]

    # --------------------------------------------------------------------------
    # 5. Deleting a whole bucket (temporary bucket only)
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("func", [delete_dir, delete_object_versions])
    def test_delete_bucket_aborted(self, func, tmp_bucket, monkeypatch):
        """
        ``prefix=""`` asks to type ``YES``; any other answer deletes nothing.
        """
        self.s3_client.put_object(Bucket=tmp_bucket, Key="a.txt", Body=b"x")
        prompts = list()

        def answer(prompt):
            prompts.append(prompt)
            return "no"

        monkeypatch.setattr("builtins.input", answer)
        assert func(self.s3_client, tmp_bucket, "") == 0
        assert len(prompts) == 1
        assert prompts[0].startswith("You are deleting everything in an S3 Bucket")
        assert self.keys(tmp_bucket, "") == ["a.txt"]

    @pytest.mark.parametrize("func", [delete_dir, delete_object_versions])
    def test_delete_bucket_confirmed(self, func, tmp_bucket, monkeypatch):
        """
        Typing ``YES`` deletes everything in the bucket.
        """
        self.s3_client.put_object(Bucket=tmp_bucket, Key="a.txt", Body=b"x")
        self.s3_client.put_object(Bucket=tmp_bucket, Key="b/c.txt", Body=b"x")
        monkeypatch.setattr("builtins.input", lambda prompt: " YES ")
        assert func(self.s3_client, tmp_bucket, "") == 2
        assert self.keys(tmp_bucket, "") == []

    @pytest.mark.parametrize("func", [delete_dir, delete_object_versions])
    def test_delete_bucket_skip_prompt(self, func, tmp_bucket, monkeypatch):
        """
        ``skip_prompt=True`` deletes everything without asking.
        """
        self.s3_client.put_object(Bucket=tmp_bucket, Key="a.txt", Body=b"x")

        def fail(prompt):
            raise AssertionError("must not ask")

        monkeypatch.setattr("builtins.input", fail)
        assert func(self.s3_client, tmp_bucket, "", skip_prompt=True) == 1
        assert self.keys(tmp_bucket, "") == []

    # --------------------------------------------------------------------------
    # 6. Partial failures of delete_objects
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("func", [delete_dir, delete_object_versions])
    def test_partial_failure(self, func):
        """
        S3 answers HTTP 200 with the failed keys in ``Errors``; that raises
        ``S3DeleteObjectsError`` with the errors and the number deleted so far
        (the first batch of 1000 succeeded here). Before 3.0 the failures were
        ignored and counted as deleted.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        keys = [f"folder/{i:04d}.txt" for i in range(1001)]
        if func is delete_dir:
            stubber.add_response(
                "list_objects_v2",
                {"Contents": [{"Key": key} for key in keys], "IsTruncated": False},
            )
        else:
            stubber.add_response(
                "list_object_versions",
                {
                    "Versions": [{"Key": key, "VersionId": "v1"} for key in keys],
                    "IsTruncated": False,
                },
            )
        stubber.add_response("delete_objects", {}, expected_params={"Bucket": "my-bucket", "Delete": ANY})
        error = {"Key": keys[-1], "Code": "AccessDenied", "Message": "Access Denied"}
        stubber.add_response("delete_objects", {"Errors": [error]})
        with stubber:
            with pytest.raises(S3DeleteObjectsError) as exc_info:
                func(s3_client, "my-bucket", "folder/")
        assert exc_info.value.errors == [error]
        assert exc_info.value.n_deleted == 1000
        assert str(exc_info.value) == (
            "failed to delete 1 object(s) in bucket 'my-bucket', e.g. "
            "'folder/1000.txt': AccessDenied (Access Denied); 1000 object(s) "
            "were deleted before stopping"
        )
        stubber.assert_no_pending_responses()

    def test_delete_objects_arguments_passed_to_boto3(self):
        """
        The arguments of ``delete_object_all_versions`` reach delete_objects
        under their API names.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        stubber.add_response(
            "list_object_versions",
            {"Versions": [{"Key": "file.txt", "VersionId": "v1"}], "IsTruncated": False},
        )
        stubber.add_response(
            "delete_objects",
            {},
            expected_params={
                "Bucket": "my-bucket",
                "Delete": {"Objects": [{"Key": "file.txt", "VersionId": "v1"}]},
                "MFA": "serial 123456",
                "RequestPayer": "requester",
                "BypassGovernanceRetention": True,
                "ExpectedBucketOwner": "111122223333",
                "ChecksumAlgorithm": "SHA256",
            },
        )
        with stubber:
            count = delete_object_all_versions(
                s3_client,
                "my-bucket",
                "file.txt",
                mfa="serial 123456",
                request_payer="requester",
                bypass_governance_retention=True,
                expected_bucket_owner="111122223333",
                check_sum_algorithm="SHA256",
            )
        assert count == 1
        stubber.assert_no_pending_responses()


class TestMock(DeleteObjectMixin):
    use_mock = True


class TestRealAws(DeleteObjectMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.better_client.delete_object",
        preview=False,
    )

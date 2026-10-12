# -*- coding: utf-8 -*-

"""
Test ``S3Path.delete``.

Test order:

1. a file: without versioning, with versioning (delete marker),
   ``version_id``, ``is_hard_delete``; the returned path;
2. a folder: without versioning, with versioning, ``is_hard_delete``;
3. a bucket (temporary bucket only): the prompt;
4. the arguments, invalid input, AWS errors.

The details of the batch deletes are tested in
``tests/better_client/test_client_delete_object.py``.
"""

import contextlib
import uuid

import botocore.exceptions
import pytest

from s3pathlib.api import S3Path
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import delete_s3_prefix


class Captured(Exception):
    """
    Raised to stop an API call once its parameters are recorded.
    """


@contextlib.contextmanager
def capture_params(s3_client, operation: str):
    """
    Record the parameters of the first ``operation`` call made through
    ``s3_client`` and stop it with ``Captured``: no request is sent.
    """
    captured = dict()

    def record(params: dict, **kwargs):
        captured.update(params)
        raise Captured

    events = s3_client.meta.events
    events.register(f"provide-client-params.s3.{operation}", record)
    try:
        yield captured
    finally:
        events.unregister(f"provide-client-params.s3.{operation}", record)


class DeleteMixin(BaseTest):
    module = "core.delete"

    def put(self, p: S3Path, body: bytes = b"hello") -> str | None:
        res = self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=body)
        return res.get("VersionId")

    def keys(self, s3dir: S3Path) -> list[str]:
        res = self.s3_client.list_objects_v2(Bucket=s3dir.bucket, Prefix=s3dir.key)
        return sorted(dct["Key"][len(s3dir.key) :] for dct in res.get("Contents", []))

    def versions(self, s3dir: S3Path) -> tuple[list[str], list[str]]:
        """
        :return: the keys (relative to ``s3dir``) of the versions, and of the
            delete markers.
        """
        res = self.s3_client.list_object_versions(Bucket=s3dir.bucket, Prefix=s3dir.key)
        versions = sorted(
            dct["Key"][len(s3dir.key) :] for dct in res.get("Versions", [])
        )
        markers = sorted(
            dct["Key"][len(s3dir.key) :] for dct in res.get("DeleteMarkers", [])
        )
        return versions, markers

    @pytest.fixture
    def tmp_bucket(self):
        """
        A new empty bucket, emptied and deleted after the test.
        """
        bucket = f"s3pathlib-test-tmp-{uuid.uuid4().hex}"
        self.s3_client.create_bucket(Bucket=bucket)
        yield bucket
        delete_s3_prefix(self.s3_client, bucket, "")
        self.s3_client.delete_bucket(Bucket=bucket)

    # --------------------------------------------------------------------------
    # 1. A file
    # --------------------------------------------------------------------------
    def test_file(self):
        """
        The object is deleted; it returns a new path without snapshot, and
        this path is not changed.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p)
        p.head_object()
        new = p.delete()
        assert self.keys(self.s3dir_test) == []
        assert new == p
        assert new is not p
        assert new.response is None
        assert p.response["ContentLength"] == 5

    def test_file_missing(self):
        """
        Deleting a missing object is not an error.
        """
        p = self.s3dir_test / "missing.txt"
        assert p.delete() == p

    def test_file_with_versioning(self):
        """
        With versioning, a delete marker is added and returned: its
        properties never call AWS: ``is_delete_marker()`` is ``True``, ``size``
        does not raise ``S3FileNotExist``.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        self.put(p)
        marker = p.delete()
        res = self.s3_client.list_object_versions(Bucket=p.bucket, Prefix=p.key)
        assert len(res["Versions"]) == 1
        assert len(res["DeleteMarkers"]) == 1
        with record_api_calls(self.s3_client) as calls:
            assert marker.is_delete_marker() is True
            assert marker.version_id == res["DeleteMarkers"][0]["VersionId"]
            assert marker.size == 0
        assert calls == []

    def test_file_version(self):
        """
        ``version_id`` deletes that version permanently; the returned path
        has its version id.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p, b"v1")
        v2 = self.put(p, b"v2")
        deleted = p.delete(version_id=v1)
        res = self.s3_client.list_object_versions(Bucket=p.bucket, Prefix=p.key)
        assert [dct["VersionId"] for dct in res["Versions"]] == [v2]
        with record_api_calls(self.s3_client) as calls:
            assert deleted.version_id == v1
            assert deleted.is_delete_marker() is False
        assert calls == []

    def test_file_delete_marker_version(self):
        """
        Deleting the delete marker brings the object back. The returned path
        is the delete marker on AWS (moto does not say it was one).
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        self.put(p, b"v1")
        marker_id = p.delete().version_id
        deleted = p.delete(version_id=marker_id)
        assert (
            self.s3_client.get_object(Bucket=p.bucket, Key=p.key)["Body"].read()
            == b"v1"
        )
        assert deleted.version_id == marker_id
        if self.use_mock:
            assert deleted.is_delete_marker() is False
        else:
            assert deleted.is_delete_marker() is True

    def test_file_hard_delete(self):
        """
        ``is_hard_delete=True`` deletes every version and delete marker of
        this exact key, not of other keys starting with it (``file.txt.bak``,
        ``file.txt2/...``).
        """
        s3dir = self.s3dir_test_with_versioning
        for key in ["file.txt", "file.txt", "file.txt.bak", "file.txt2/x.csv"]:
            self.put(s3dir / key)
        self.s3_client.delete_object(Bucket=s3dir.bucket, Key=(s3dir / "file.txt").key)
        new = (s3dir / "file.txt").delete(is_hard_delete=True)
        assert self.versions(s3dir) == (["file.txt.bak", "file.txt2/x.csv"], [])
        assert new.response is None

    # --------------------------------------------------------------------------
    # 2. A folder
    # --------------------------------------------------------------------------
    def test_folder(self):
        """
        Every object under the folder is deleted, its marker included, and
        not a sibling folder starting with the same name.
        """
        s3dir = self.s3dir_test / "folder/"
        for key in ["folder/", "folder/a.txt", "folder/sub/b.txt", "folder2/c.txt"]:
            self.put(self.s3dir_test / key)
        new = s3dir.delete()
        assert self.keys(self.s3dir_test) == ["folder2/c.txt"]
        assert new == s3dir
        assert new is not s3dir

    def test_folder_with_versioning(self):
        """
        With versioning, delete markers are added, the versions are kept.
        """
        s3dir = self.s3dir_test_with_versioning / "folder/"
        for key in ["a.txt", "sub/b.txt"]:
            self.put(s3dir / key)
        s3dir.delete()
        assert self.keys(s3dir) == []
        assert self.versions(s3dir) == (["a.txt", "sub/b.txt"], ["a.txt", "sub/b.txt"])

    def test_folder_hard_delete(self):
        s3dir = self.s3dir_test_with_versioning / "folder/"
        for key in ["a.txt", "a.txt", "sub/b.txt"]:
            self.put(s3dir / key)
        self.s3_client.delete_object(Bucket=s3dir.bucket, Key=(s3dir / "a.txt").key)
        s3dir.delete(is_hard_delete=True)
        assert self.versions(s3dir) == ([], [])

    # --------------------------------------------------------------------------
    # 3. A bucket
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("is_hard_delete", [False, True])
    def test_bucket(self, tmp_bucket, is_hard_delete):
        """
        A bucket is emptied without asking with ``skip_prompt=True``.
        """
        self.s3_client.put_object(Bucket=tmp_bucket, Key="a/b.txt", Body=b"x")
        S3Path(tmp_bucket).delete(is_hard_delete=is_hard_delete, skip_prompt=True)
        assert self.keys(S3Path(tmp_bucket)) == []

    def test_bucket_prompt(self, tmp_bucket, monkeypatch):
        """
        Without ``skip_prompt``, emptying a bucket asks to type ``YES``; any
        other answer deletes nothing.
        """
        self.s3_client.put_object(Bucket=tmp_bucket, Key="a.txt", Body=b"x")
        prompts = list()

        def answer(prompt):
            prompts.append(prompt)
            return "no"

        monkeypatch.setattr("builtins.input", answer)
        S3Path(tmp_bucket).delete()
        assert len(prompts) == 1
        assert self.keys(S3Path(tmp_bucket)) == ["a.txt"]

    # --------------------------------------------------------------------------
    # 4. Arguments, invalid input, errors
    # --------------------------------------------------------------------------
    def test_file_arguments_passed_to_boto3(self):
        p = self.s3dir_test / "file.txt"
        with capture_params(self.s3_client, "DeleteObject") as params:
            with pytest.raises(Captured):
                p.delete(
                    version_id="v1",
                    mfa="serial 123456",
                    request_payer="requester",
                    bypass_governance_retention=True,
                    expected_bucket_owner="111122223333",
                )
        assert params == {
            "Bucket": p.bucket,
            "Key": p.key,
            "VersionId": "v1",
            "MFA": "serial 123456",
            "RequestPayer": "requester",
            "BypassGovernanceRetention": True,
            "ExpectedBucketOwner": "111122223333",
        }

    @pytest.mark.parametrize("is_hard_delete", [False, True])
    def test_folder_arguments_passed_to_boto3(self, is_hard_delete):
        """
        The batch delete also gets ``checksum_algorithm``.
        """
        s3dir = self.s3dir_test_with_versioning / "folder/"
        self.put(s3dir / "a.txt")
        with capture_params(self.s3_client, "DeleteObjects") as params:
            with pytest.raises(Captured):
                s3dir.delete(
                    is_hard_delete=is_hard_delete,
                    mfa="serial 123456",
                    request_payer="requester",
                    bypass_governance_retention=True,
                    checksum_algorithm="SHA256",
                )
        assert params["MFA"] == "serial 123456"
        assert params["RequestPayer"] == "requester"
        assert params["BypassGovernanceRetention"] is True
        assert params["ChecksumAlgorithm"] == "SHA256"

    @pytest.mark.parametrize(
        "key, kwargs, match",
        [
            pytest.param(
                "file.txt", {"is_hard_delete": True}, "give only one", id="hard-delete"
            ),
            pytest.param("folder/", {}, "only applies to deleting a file", id="folder"),
        ],
    )
    def test_version_id_conflict(self, key, kwargs, match):
        """
        ``version_id`` is not ignored here: with ``is_hard_delete=True`` it
        would delete every version instead of one, so the two conflict.
        """
        p = self.s3dir_test_with_versioning / key
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match=match):
                p.delete(version_id="v1", **kwargs)
        assert calls == []

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(S3Path(), id="void"),
            pytest.param(S3Path.make_relpath("a.txt"), id="relpath-file"),
            pytest.param(S3Path.make_relpath("a/"), id="relpath-dir"),
        ],
    )
    def test_relative_path(self, p):
        """
        A relative path and the void path raise ``S3PathTypeError``, not a
        botocore ``TypeError``.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(S3PathTypeError, match="is a relative path"):
                p.delete()
        assert calls == []

    def test_missing_bucket(self):
        p = S3Path(f"s3pathlib-test-tmp-{uuid.uuid4().hex}", "file.txt")
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.delete()
        assert exc_info.value.response["Error"]["Code"] == "NoSuchBucket"


class TestMock(DeleteMixin):
    use_mock = True


class TestRealAws(DeleteMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.delete",
        preview=False,
    )

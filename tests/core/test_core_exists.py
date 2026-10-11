# -*- coding: utf-8 -*-

"""
Test ``S3Path.exists`` and ``S3Path.ensure_not_exists``.

Test order:

1. a bucket;
2. a file: plain objects, the cached metadata, versions and delete markers;
3. a folder: soft / hard / empty folders, the folder name boundary;
4. a path without bucket, and ``version_id`` on a bucket or a folder;
5. AWS errors;
6. ``ensure_not_exists``.
"""

import uuid

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.exc import S3AlreadyExist
from s3pathlib.exc import S3BucketAlreadyExist
from s3pathlib.exc import S3FileAlreadyExist
from s3pathlib.exc import S3FolderAlreadyExist
from s3pathlib.exc import S3PathTypeError
from s3pathlib.exc import S3PermissionDenied
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only


def missing_bucket() -> str:
    """
    A bucket name that does not exist (never created).
    """
    return f"s3pathlib-test-tmp-{uuid.uuid4().hex}"


def error_code(exc_info) -> str:
    return exc_info.value.response["Error"]["Code"]


class ExistsMixin(BaseTest):
    module = "core.exists"

    def put(self, s3path: S3Path, body: bytes = b"a") -> str | None:
        """
        Write an object with the native client.

        :return: the version id (``None`` without versioning)
        """
        res = self.s3_client.put_object(Bucket=s3path.bucket, Key=s3path.key, Body=body)
        return res.get("VersionId")

    def delete(self, s3path: S3Path) -> str | None:
        """
        Delete an object with the native client.

        :return: the version id of the delete marker (``None`` without
            versioning)
        """
        res = self.s3_client.delete_object(Bucket=s3path.bucket, Key=s3path.key)
        return res.get("VersionId")

    # --------------------------------------------------------------------------
    # 1. Bucket
    # --------------------------------------------------------------------------
    def test_bucket_exists(self):
        assert S3Path(self.bucket).exists() is True

    def test_bucket_not_exists(self):
        assert S3Path(missing_bucket()).exists() is False

    # --------------------------------------------------------------------------
    # 2. File
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "body",
        [
            pytest.param(b"a", id="with-content"),
            pytest.param(b"", id="empty"),
        ],
    )
    def test_file_exists(self, body):
        """
        An object exists whatever its size.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, body)
        assert p.exists() is True

    def test_file_not_exists(self):
        assert (self.s3dir_test / "file.txt").exists() is False

    def test_file_in_missing_bucket(self):
        """
        A missing bucket means the file does not exist; no error.
        """
        assert S3Path(missing_bucket(), "file.txt").exists() is False

    def test_file_caches_metadata(self):
        """
        ``exists()`` keeps the ``head_object`` response, without
        ``ResponseMetadata``, so that reading the metadata needs no more call.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        assert p.exists() is True
        assert "ResponseMetadata" not in p.response
        with record_api_calls(self.s3_client) as calls:
            assert p.size == 3
        assert calls == []

    def test_file_keeps_existing_snapshot(self):
        """
        ``exists()`` only fills an empty metadata snapshot: a path that already
        describes an object keeps describing it after the object is
        overwritten or deleted (see ``s3pathlib.core.metadata``).
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        assert p.exists() is True
        self.put(p, b"hello")
        assert p.exists() is True
        assert p.size == 3
        self.delete(p)
        assert p.exists() is False
        assert p.size == 3

    def test_file_latest_version_is_delete_marker(self):
        """
        An object whose latest version is a delete marker does not exist, but
        its older version does, and the metadata of that version is cached.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p)
        marker = self.delete(p)
        assert p.exists() is False
        assert p.exists(version_id=v1) is True
        assert p.response["VersionId"] == v1
        assert p.exists(version_id=marker) is False

    def test_file_invalid_version_id(self):
        """
        A malformed version id raises the ``head_object`` error (400) as is.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        self.put(p)
        if self.use_mock:
            # moto answers 404 instead
            assert p.exists(version_id="not-a-version-id") is False
        else:
            with pytest.raises(botocore.exceptions.ClientError) as exc_info:
                p.exists(version_id="not-a-version-id")
            assert error_code(exc_info) == "400"

    # --------------------------------------------------------------------------
    # 3. Folder
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "keys",
        [
            pytest.param(["folder/file.txt"], id="soft-folder"),
            pytest.param(["folder/", "folder/file.txt"], id="hard-folder"),
            pytest.param(["folder/"], id="empty-folder-marker"),
            pytest.param(["folder/sub/file.txt"], id="nested-only"),
        ],
    )
    def test_folder_exists(self, keys):
        """
        A folder exists when any key starts with it, the folder marker
        included.
        """
        for key in keys:
            self.put(self.s3dir_test / key, b"")
        assert (self.s3dir_test / "folder/").exists() is True

    def test_folder_not_exists(self):
        assert (self.s3dir_test / "folder/").exists() is False

    def test_folder_name_boundary(self):
        """
        ``ab/`` does not exist because of ``abc/x.txt``, and the file
        ``folder`` does not exist because of the marker ``folder/``.
        """
        self.put(self.s3dir_test / "abc/x.txt")
        self.put(self.s3dir_test / "folder/", b"")
        assert (self.s3dir_test / "ab/").exists() is False
        assert (self.s3dir_test / "folder").exists() is False

    def test_folder_with_only_delete_markers(self):
        """
        A folder whose objects are all deleted (only delete markers and old
        versions remain) does not exist.
        """
        p = self.s3dir_test_with_versioning / "folder/file.txt"
        self.put(p)
        self.delete(p)
        assert (self.s3dir_test_with_versioning / "folder/").exists() is False

    def test_folder_one_api_call(self):
        """
        Testing a folder with many objects needs a single call.
        """
        for i in range(3):
            self.put(self.s3dir_test / f"folder/{i}.txt")
        with record_api_calls(self.s3_client) as calls:
            assert (self.s3dir_test / "folder/").exists() is True
        assert calls == ["ListObjectsV2"]

    def test_folder_in_missing_bucket(self):
        """
        A missing bucket means the folder does not exist, the same as a file, and
        ``NoSuchBucket`` is not raised.
        """
        assert S3Path(missing_bucket(), "folder/").exists() is False

    # --------------------------------------------------------------------------
    # 4. Invalid input
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(S3Path(), id="void"),
            pytest.param(S3Path.make_relpath("folder", "file.txt"), id="relpath-file"),
            pytest.param(S3Path.make_relpath("folder/"), id="relpath-dir"),
        ],
    )
    def test_path_without_bucket(self, p):
        """
        A path without bucket cannot exist in S3: ``S3PathTypeError`` before
        any AWS call, the same error for every kind of path.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(S3PathTypeError, match="is a relative path"):
                p.exists()
        assert calls == []

    @pytest.mark.parametrize("key", [None, "folder/"])
    def test_version_id_not_on_file(self, key):
        """
        ``version_id`` on a bucket or a folder raises ``ValueError`` before any
        AWS call, it is not ignored.
        """
        if key is None:
            p = S3Path(self.bucket)
        else:
            p = S3Path(self.bucket, key)
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match="version_id only applies to a file"):
                p.exists(version_id="v1")
        assert calls == []

    # --------------------------------------------------------------------------
    # 5. AWS errors
    # --------------------------------------------------------------------------
    @real_aws_only("moto answers 404 / NoSuchBucket for another account's bucket")
    @pytest.mark.parametrize("key", [None, "file.txt"])
    def test_no_permission_head(self, key):
        """
        A bucket or a file of another account raises ``S3PermissionDenied``
        (from the HEAD call).
        """
        if key is None:
            p = S3Path("aws")
        else:
            p = S3Path("aws", key)
        with pytest.raises(S3PermissionDenied):
            p.exists()

    def test_folder_other_error_raised_as_is(self):
        """
        Only ``NoSuchBucket`` means "the folder does not exist"; any other
        ``list_objects_v2`` error is raised as is.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        stubber.add_client_error("list_objects_v2", service_error_code="SlowDown")
        s3_context.attach_s3_client(s3_client)
        try:
            with stubber:
                with pytest.raises(botocore.exceptions.ClientError) as exc_info:
                    S3Path(self.bucket, "folder/").exists()
        finally:
            s3_context.attach_s3_client(self.s3_client)
        assert error_code(exc_info) == "SlowDown"
        stubber.assert_no_pending_responses()

    @real_aws_only("moto answers NoSuchBucket for another account's bucket")
    def test_no_permission_folder(self):
        """
        A folder of another account raises the ``list_objects_v2`` error
        ``AccessDenied`` as is.
        """
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            S3Path("aws", "folder/").exists()
        assert error_code(exc_info) == "AccessDenied"

    # --------------------------------------------------------------------------
    # 6. ensure_not_exists
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("key", ["file.txt", "folder/"])
    def test_ensure_not_exists_ok(self, key):
        assert (self.s3dir_test / key).ensure_not_exists() is None

    def test_ensure_not_exists_file(self):
        p = self.s3dir_test / "file.txt"
        self.put(p)
        with pytest.raises(S3FileAlreadyExist, match=f"S3 object '{p.uri}'"):
            p.ensure_not_exists()

    def test_ensure_not_exists_folder(self):
        p = self.s3dir_test / "folder/"
        self.put(p / "file.txt")
        with pytest.raises(S3FolderAlreadyExist, match=f"S3 folder '{p.uri}'"):
            p.ensure_not_exists()

    def test_ensure_not_exists_bucket(self):
        p = S3Path(self.bucket)
        with pytest.raises(S3BucketAlreadyExist, match=f"S3 bucket '{p.uri}'"):
            p.ensure_not_exists()

    def test_ensure_not_exists_version_id(self):
        """
        ``version_id`` is passed on: an old version exists even when the
        latest version is a delete marker.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p)
        self.delete(p)
        assert p.ensure_not_exists() is None
        with pytest.raises(S3AlreadyExist):
            p.ensure_not_exists(version_id=v1)


class TestMock(ExistsMixin):
    use_mock = True


class TestRealAws(ExistsMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.exists",
        preview=False,
    )

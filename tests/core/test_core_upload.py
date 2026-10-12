# -*- coding: utf-8 -*-

"""
Test ``S3Path.upload_file`` and ``S3Path.upload_dir``.

Test order:

1. ``upload_file``: the uploaded object and the returned path, ``overwrite``,
   the local path, the arguments, errors;
2. ``upload_dir`` (the details are tested in
   ``tests/better_client/test_client_upload.py``);
3. paths that cannot be uploaded to.

Local files are created in pytest's ``tmp_path``.
"""

import pathlib
import uuid

import boto3.exceptions
import pytest
from boto3.s3.transfer import TransferConfig

from s3pathlib.api import S3Path
from s3pathlib.exc import S3FileAlreadyExist
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.exc import S3PathIsNotFolderError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest


class UploadMixin(BaseTest):
    module = "core.upload"

    def get(self, p: S3Path) -> bytes:
        return self.s3_client.get_object(Bucket=p.bucket, Key=p.key)["Body"].read()

    def keys(self, s3dir: S3Path) -> list[str]:
        res = self.s3_client.list_objects_v2(Bucket=s3dir.bucket, Prefix=s3dir.key)
        return sorted(dct["Key"][len(s3dir.key):] for dct in res.get("Contents", []))

    @pytest.fixture
    def local_file(self, tmp_path) -> pathlib.Path:
        path = tmp_path / "file.txt"
        path.write_bytes(b"hello")
        return path

    # --------------------------------------------------------------------------
    # 1. upload_file
    # --------------------------------------------------------------------------
    def test_upload_file(self, local_file):
        """
        The file is uploaded; it returns a new path without snapshot, and
        this path is not changed.
        """
        p = self.s3dir_test / "file.txt"
        new = p.upload_file(local_file)
        assert self.get(p) == b"hello"
        assert new == p
        assert new is not p
        assert new.response is None
        assert p.response is None
        assert new.size == 5

    def test_upload_file_existing(self, local_file):
        """
        With ``overwrite=False`` (default), an existing object raises
        ``S3FileAlreadyExist`` and is not changed.
        """
        p = self.s3dir_test / "file.txt"
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"old")
        with pytest.raises(S3FileAlreadyExist, match="already exist"):
            p.upload_file(local_file)
        assert self.get(p) == b"old"

    def test_upload_file_overwrite(self, local_file):
        """
        With ``overwrite=True``, the object is replaced without checking it
        first.
        """
        p = self.s3dir_test / "file.txt"
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"old")
        with record_api_calls(self.s3_client) as calls:
            p.upload_file(local_file, overwrite=True)
        assert calls == ["PutObject"]
        assert self.get(p) == b"hello"

    def test_upload_file_after_delete_marker(self, local_file):
        """
        An object whose latest version is a delete marker does not exist.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"old")
        self.s3_client.delete_object(Bucket=p.bucket, Key=p.key)
        p.upload_file(local_file)
        assert self.get(p) == b"hello"

    @pytest.mark.parametrize("kind", ["str", "pathlib", "relative"])
    def test_upload_file_local_path(self, kind, local_file, monkeypatch):
        """
        The local path can be a ``str``, a ``pathlib.Path`` or a path relative
        to the current directory.
        """
        if kind == "str":
            path = str(local_file)
        elif kind == "pathlib":
            path = local_file
        else:
            monkeypatch.chdir(local_file.parent)
            path = local_file.name
        p = self.s3dir_test / "file.txt"
        p.upload_file(path)
        assert self.get(p) == b"hello"

    @pytest.mark.parametrize(
        "name, error",
        [
            pytest.param("missing.txt", FileNotFoundError, id="missing"),
            pytest.param("folder", IsADirectoryError, id="directory"),
        ],
    )
    def test_upload_file_bad_local_path(self, name, error, tmp_path):
        """
        The local path is checked before any AWS call: real AWS would
        raise ``UnseekableStreamError`` for a directory.
        """
        (tmp_path / "folder").mkdir()
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error):
                (self.s3dir_test / "file.txt").upload_file(tmp_path / name)
        assert calls == []

    def test_upload_file_arguments(self, local_file):
        """
        ``extra_args``, ``callback`` and ``config`` are passed to boto3.
        """
        p = self.s3dir_test / "file.txt"
        sent = list()
        p.upload_file(
            local_file,
            extra_args={"ContentType": "text/plain", "Metadata": {"k": "v"}},
            callback=sent.append,
            config=TransferConfig(use_threads=False),
        )
        res = self.s3_client.head_object(Bucket=p.bucket, Key=p.key)
        assert res["ContentType"] == "text/plain"
        assert res["Metadata"] == {"k": "v"}
        assert sum(sent) == 5

    def test_upload_file_invalid_extra_args(self, local_file):
        """
        boto3 rejects a key that upload_file does not allow, e.g.
        ``IfNoneMatch``.
        """
        with pytest.raises(ValueError, match="Invalid extra_args key"):
            (self.s3dir_test / "file.txt").upload_file(
                local_file,
                overwrite=True,
                extra_args={"IfNoneMatch": "*"},
            )

    def test_upload_file_missing_bucket(self, local_file):
        """
        boto3 raises ``S3UploadFailedError``, with the ``ClientError`` as its
        context.
        """
        p = S3Path(f"s3pathlib-test-tmp-{uuid.uuid4().hex}", "file.txt")
        with pytest.raises(boto3.exceptions.S3UploadFailedError) as exc_info:
            p.upload_file(local_file, overwrite=True)
        assert exc_info.value.__context__.response["Error"]["Code"] == "NoSuchBucket"

    # --------------------------------------------------------------------------
    # 2. upload_dir
    # --------------------------------------------------------------------------
    def test_upload_dir(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("b")
        (tmp_path / "sub" / "c.csv").write_text("c")
        s3dir = self.s3dir_test / "folder/"
        assert s3dir.upload_dir(tmp_path, pattern="**/*.txt") == 2
        assert self.keys(s3dir) == ["a.txt", "sub/b.txt"]

    def test_upload_dir_existing(self, tmp_path):
        """
        With ``overwrite=False``, nothing is uploaded if any key exists.
        """
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        s3dir = self.s3dir_test / "folder/"
        self.s3_client.put_object(Bucket=s3dir.bucket, Key=s3dir.key + "b.txt", Body=b"old")
        with pytest.raises(S3FileAlreadyExist):
            s3dir.upload_dir(tmp_path)
        assert self.keys(s3dir) == ["b.txt"]
        assert s3dir.upload_dir(tmp_path, overwrite=True) == 2

    # --------------------------------------------------------------------------
    # 3. Invalid paths
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, error, match",
        [
            pytest.param(S3Path(), S3PathTypeError, "is a relative path", id="void"),
            pytest.param(
                S3Path.make_relpath("a.txt"),
                S3PathTypeError,
                "is a relative path",
                id="relpath",
            ),
            pytest.param(S3Path("bucket", "a/"), S3PathIsNotFileError, "is not a file", id="dir"),
            pytest.param(S3Path("bucket"), S3PathIsNotFileError, "is not a file", id="bucket"),
        ],
    )
    def test_upload_file_not_a_file(self, p, error, match, local_file):
        """
        A relative path is rejected before botocore sees it, also with
        ``overwrite=True``.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error, match=match):
                p.upload_file(local_file, overwrite=True)
        assert calls == []

    @pytest.mark.parametrize(
        "p, error, match",
        [
            pytest.param(S3Path(), S3PathTypeError, "is a relative path", id="void"),
            pytest.param(
                S3Path.make_relpath("a/"),
                S3PathTypeError,
                "is a relative path",
                id="relpath",
            ),
            pytest.param(S3Path("bucket", "a.txt"), S3PathIsNotFolderError, "is not a dir", id="file"),
        ],
    )
    def test_upload_dir_not_a_folder(self, p, error, match, tmp_path):
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error, match=match):
                p.upload_dir(tmp_path)
        assert calls == []


class TestMock(UploadMixin):
    use_mock = True


class TestRealAws(UploadMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.upload",
        preview=False,
    )

# -*- coding: utf-8 -*-

"""
Test ``upload_dir``.

Test order:

1. uploading: keys and content, ``prefix`` rules, ``pattern``, empty
   directories, special file names, the accepted ``local_dir`` types;
2. ``overwrite``;
3. errors.

Local directories are built under pytest's ``tmp_path``. Uploading to the
root of a bucket (``prefix=""``) only happens in a temporary bucket.
"""

import os
import uuid
from pathlib import Path

import botocore.exceptions
import pytest
from boto3.exceptions import S3UploadFailedError

from s3pathlib.better_client.upload import upload_dir
from s3pathlib.exc import S3FileAlreadyExist
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock_aws import BaseTest


class CustomPathLike:
    """
    A local path that is only an ``os.PathLike``: neither a ``str`` nor a
    ``pathlib.Path``, e.g. a ``pathlib_mate.Path``.
    """

    def __init__(self, path: str):
        self._path = path

    def __fspath__(self) -> str:
        return self._path


# relative path -> content
FILES = {
    "1.txt": "one",
    "data.json": "{}",
    "sub/2.txt": "two",
    "sub/deep/3.txt": "three",
}


def make_local_dir(root: Path, files: dict[str, str]) -> Path:
    local_dir = root.joinpath("local")
    for relpath, content in files.items():
        path = local_dir.joinpath(relpath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    local_dir.mkdir(exist_ok=True)
    return local_dir


class UploadMixin(BaseTest):
    module = "better_client.upload"

    def read_all(self, bucket: str, prefix: str) -> dict[str, str]:
        """
        Relative key -> content of every object under the prefix.
        """
        res = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        result = dict()
        for dct in res.get("Contents", []):
            body = self.s3_client.get_object(Bucket=bucket, Key=dct["Key"])["Body"]
            result[dct["Key"][len(prefix):]] = body.read().decode("utf-8")
        return result

    @pytest.fixture
    def tmp_bucket(self):
        """
        A new bucket, emptied and deleted after the test.
        """
        bucket = f"s3pathlib-test-tmp-{uuid.uuid4().hex}"
        self.s3_client.create_bucket(Bucket=bucket)
        yield bucket
        res = self.s3_client.list_objects_v2(Bucket=bucket)
        for dct in res.get("Contents", []):
            self.s3_client.delete_object(Bucket=bucket, Key=dct["Key"])
        self.s3_client.delete_bucket(Bucket=bucket)

    # --------------------------------------------------------------------------
    # 1. Uploading
    # --------------------------------------------------------------------------
    def test_upload_dir(self, tmp_path):
        """
        Every file becomes an object, keyed by its path relative to the local
        directory with ``/`` as separator; the count is returned.
        """
        local_dir = make_local_dir(tmp_path, FILES)
        prefix = self.s3dir_test.key
        count = upload_dir(self.s3_client, self.bucket, prefix, local_dir)
        assert count == 4
        assert self.read_all(self.bucket, prefix) == FILES

    def test_prefix_without_slash(self, tmp_path):
        """
        ``"data"`` is the same folder as ``"data/"``.
        """
        local_dir = make_local_dir(tmp_path, {"1.txt": "one"})
        prefix = self.s3dir_test.key + "data"
        upload_dir(self.s3_client, self.bucket, prefix, local_dir)
        assert self.read_all(self.bucket, prefix + "/") == {"1.txt": "one"}

    def test_prefix_empty_is_bucket_root(self, tmp_path, tmp_bucket):
        """
        ``prefix=""`` uploads to the root of the bucket.
        """
        local_dir = make_local_dir(tmp_path, {"1.txt": "one", "sub/2.txt": "two"})
        assert upload_dir(self.s3_client, tmp_bucket, "", local_dir) == 2
        assert self.read_all(tmp_bucket, "") == {"1.txt": "one", "sub/2.txt": "two"}

    @pytest.mark.parametrize(
        "pattern, expected",
        [
            pytest.param("**/*.txt", ["1.txt", "sub/2.txt", "sub/deep/3.txt"], id="recursive-txt"),
            pytest.param("*.txt", ["1.txt"], id="top-level-txt"),
            pytest.param("sub/**/*", ["sub/2.txt", "sub/deep/3.txt"], id="sub-folder"),
            pytest.param("*.csv", [], id="no-match"),
        ],
    )
    def test_pattern(self, tmp_path, pattern, expected):
        """
        ``pattern`` is a glob relative to the local directory.
        """
        local_dir = make_local_dir(tmp_path, FILES)
        prefix = self.s3dir_test.key
        count = upload_dir(self.s3_client, self.bucket, prefix, local_dir, pattern=pattern)
        assert count == len(expected)
        assert sorted(self.read_all(self.bucket, prefix)) == expected

    def test_empty_directories_not_uploaded(self, tmp_path):
        """
        Only files are uploaded: no folder marker for an empty directory.
        """
        local_dir = make_local_dir(tmp_path, {"1.txt": "one"})
        local_dir.joinpath("empty", "nested").mkdir(parents=True)
        prefix = self.s3dir_test.key
        assert upload_dir(self.s3_client, self.bucket, prefix, local_dir) == 1
        assert self.read_all(self.bucket, prefix) == {"1.txt": "one"}

    def test_special_file_names(self, tmp_path):
        """
        Spaces and non-ASCII characters in file names are kept in the keys.
        """
        files = {"a b.txt": "space", "中文/文件.txt": "unicode"}
        local_dir = make_local_dir(tmp_path, files)
        prefix = self.s3dir_test.key
        upload_dir(self.s3_client, self.bucket, prefix, local_dir)
        assert self.read_all(self.bucket, prefix) == files

    @pytest.mark.parametrize("kind", ["str", "pathlib", "os.PathLike", "relative"])
    def test_local_dir_types(self, tmp_path, monkeypatch, kind):
        """
        ``local_dir`` can be a ``str``, a ``pathlib.Path``, any other
        ``os.PathLike``, or a path relative to the current directory.
        """
        local_dir = make_local_dir(tmp_path, {"1.txt": "one"})
        if kind == "str":
            arg = str(local_dir)
        elif kind == "pathlib":
            arg = local_dir
        elif kind == "os.PathLike":
            arg = CustomPathLike(str(local_dir))
        else:
            monkeypatch.chdir(tmp_path)
            arg = os.path.join(".", "local")
        prefix = self.s3dir_test.key
        assert upload_dir(self.s3_client, self.bucket, prefix, arg) == 1
        assert self.read_all(self.bucket, prefix) == {"1.txt": "one"}

    # --------------------------------------------------------------------------
    # 2. overwrite
    # --------------------------------------------------------------------------
    def test_overwrite_false(self, tmp_path):
        """
        If any target key exists, ``S3FileAlreadyExist`` is raised and nothing
        is uploaded, not even the files whose key is free.
        """
        local_dir = make_local_dir(tmp_path, {"1.txt": "new", "2.txt": "new"})
        prefix = self.s3dir_test.key
        self.s3_client.put_object(Bucket=self.bucket, Key=prefix + "2.txt", Body=b"old")
        with pytest.raises(S3FileAlreadyExist, match=f"s3://{self.bucket}/{prefix}2.txt"):
            upload_dir(self.s3_client, self.bucket, prefix, local_dir)
        assert self.read_all(self.bucket, prefix) == {"2.txt": "old"}

    def test_overwrite_true(self, tmp_path):
        """
        With ``overwrite=True``, existing keys are replaced.
        """
        local_dir = make_local_dir(tmp_path, {"1.txt": "new"})
        prefix = self.s3dir_test.key
        self.s3_client.put_object(Bucket=self.bucket, Key=prefix + "1.txt", Body=b"old")
        upload_dir(self.s3_client, self.bucket, prefix, local_dir, overwrite=True)
        assert self.read_all(self.bucket, prefix) == {"1.txt": "new"}

    # --------------------------------------------------------------------------
    # 3. Errors
    # --------------------------------------------------------------------------
    def test_local_dir_is_a_file(self, tmp_path):
        local_dir = make_local_dir(tmp_path, {"1.txt": "one"})
        path = local_dir.joinpath("1.txt")
        with pytest.raises(TypeError, match="is a file, not a directory"):
            upload_dir(self.s3_client, self.bucket, self.s3dir_test.key, path)

    def test_local_dir_missing(self, tmp_path):
        path = tmp_path.joinpath("missing")
        with pytest.raises(FileNotFoundError, match="not found"):
            upload_dir(self.s3_client, self.bucket, self.s3dir_test.key, path)

    def test_missing_bucket(self, tmp_path):
        """
        Errors of the upload are raised as boto3 raises them:
        ``upload_file`` wraps the ``ClientError`` in ``S3UploadFailedError``
        (the ``ClientError`` is its ``__context__``).
        """
        local_dir = make_local_dir(tmp_path, {"1.txt": "one"})
        bucket = f"s3pathlib-test-tmp-{uuid.uuid4().hex}"
        with pytest.raises(S3UploadFailedError, match="NoSuchBucket") as exc_info:
            upload_dir(self.s3_client, bucket, "", local_dir, overwrite=True)
        cause = exc_info.value.__context__
        assert isinstance(cause, botocore.exceptions.ClientError)
        assert cause.response["Error"]["Code"] == "NoSuchBucket"


class TestMock(UploadMixin):
    use_mock = True


class TestRealAws(UploadMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.better_client.upload",
        preview=False,
    )

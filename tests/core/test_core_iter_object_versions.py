# -*- coding: utf-8 -*-

"""
Test ``S3Path.list_object_versions``.

Test order:

1. a file: its versions and delete markers, newest first, with metadata; only
   this exact key;
2. a folder: every key, in S3 order, each entry once, not again after each
   page;
3. ``limit``, laziness, ``delimiter``, a bucket without versioning, errors.

The versions of a key are written one second apart, so that their order is
known (S3 timestamps have a one second resolution).
"""

import time
import uuid

import pytest

from s3pathlib.api import S3Path
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest


class ListObjectVersionsMixin(BaseTest):
    module = "core.iter_object_versions"

    def put(self, key: str, body: str) -> str:
        """
        Put an object version under the versioning folder of the test.

        :return: the version id
        """
        s3dir = self.s3dir_test_with_versioning
        res = self.s3_client.put_object(Bucket=s3dir.bucket, Key=s3dir.key + key, Body=body)
        return res["VersionId"]

    def delete(self, key: str) -> str:
        """
        Add a delete marker.

        :return: its version id
        """
        s3dir = self.s3dir_test_with_versioning
        res = self.s3_client.delete_object(Bucket=s3dir.bucket, Key=s3dir.key + key)
        return res["VersionId"]

    def relative(self, p: S3Path) -> str:
        return p.key[len(self.s3dir_test_with_versioning.key):]

    # --------------------------------------------------------------------------
    # 1. A file
    # --------------------------------------------------------------------------
    def test_file_versions_newest_first(self):
        """
        The versions and delete markers of a file, newest first, each with its
        metadata; a delete marker has no ETag and no size.
        """
        v1 = self.put("file.txt", "v1")
        time.sleep(1)
        marker = self.delete("file.txt")
        time.sleep(1)
        v2 = self.put("file.txt", "v22")
        time.sleep(1)
        v3 = self.put("file.txt", "v333")

        p = self.s3dir_test_with_versioning.joinpath("file.txt")
        result = p.list_object_versions().all()
        assert [x.version_id for x in result] == [v3, v2, marker, v1]
        assert [x.is_delete_marker() for x in result] == [False, False, True, False]
        assert [x.size for x in result] == [4, 3, 0, 2]
        assert result[2].etag is None
        assert result[0].etag is not None
        assert all(x.key == p.key for x in result)

    def test_file_only_this_key(self):
        """
        Only the versions of this exact key, not of keys that start with it.
        """
        self.put("file.txt", "a")
        self.put("file.txt", "b")
        self.put("file.txt.bak", "c")
        self.put("file.txt2/x.csv", "d")
        p = self.s3dir_test_with_versioning.joinpath("file.txt")
        result = p.list_object_versions(batch_size=1).all()
        assert [self.relative(x) for x in result] == ["file.txt", "file.txt"]

    # --------------------------------------------------------------------------
    # 2. A folder
    # --------------------------------------------------------------------------
    def test_folder_s3_order_without_duplicates(self):
        """
        Every version of every key under the folder, by key, then newest
        first; each entry exactly once, also when it takes many pages.
        """
        a1 = self.put("a.txt", "1")
        b1 = self.put("b/c.txt", "1")
        time.sleep(1)
        a2 = self.put("a.txt", "2")
        b_marker = self.delete("b/c.txt")

        for batch_size in [1, 2, 1000]:
            result = self.s3dir_test_with_versioning.list_object_versions(
                batch_size=batch_size
            ).all()
            entries = [(self.relative(x), x.version_id) for x in result]
            assert entries == [
                ("a.txt", a2),
                ("a.txt", a1),
                ("b/c.txt", b_marker),
                ("b/c.txt", b1),
            ], batch_size

    # --------------------------------------------------------------------------
    # 3. limit, laziness, delimiter, errors
    # --------------------------------------------------------------------------
    def test_limit(self):
        """
        ``limit`` caps the number of returned entries, and no page is fetched
        after it is reached.
        """
        for key in ["a.txt", "b.txt", "c.txt", "d.txt"]:
            self.put(key, "x")
        s3dir = self.s3dir_test_with_versioning
        with record_api_calls(self.s3_client) as calls:
            result = s3dir.list_object_versions(batch_size=1, limit=2).all()
        assert [self.relative(x) for x in result] == ["a.txt", "b.txt"]
        assert calls == ["ListObjectVersions"] * 2

    def test_limit_counts_only_this_file(self):
        """
        For a file, ``limit`` counts its own versions only.
        """
        self.put("file.txt", "1")
        self.put("file.txt", "2")
        self.put("file.txt.bak", "3")
        p = self.s3dir_test_with_versioning.joinpath("file.txt")
        assert len(p.list_object_versions(limit=5).all()) == 2
        assert len(p.list_object_versions(limit=1).all()) == 1

    def test_limit_none(self):
        """
        ``limit=None`` is no limit, the same as leaving it out.
        """
        for key in ["a.txt", "b.txt", "c.txt"]:
            self.put(key, "x")
        s3dir = self.s3dir_test_with_versioning
        assert len(s3dir.list_object_versions(batch_size=1, limit=None).all()) == 3

    def test_limit_zero(self):
        """
        ``limit=0`` returns nothing without calling AWS.
        """
        self.put("file.txt", "1")
        with record_api_calls(self.s3_client) as calls:
            assert self.s3dir_test_with_versioning.list_object_versions(limit=0).all() == []
        assert calls == []

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            pytest.param({"limit": -1}, "must not be negative", id="limit-negative"),
            pytest.param({"batch_size": 0}, "batch_size", id="batch-size-0"),
        ],
    )
    def test_invalid_arguments(self, kwargs, match):
        """
        Invalid arguments are rejected when the method is called.
        """
        with pytest.raises(ValueError, match=match):
            self.s3dir_test_with_versioning.list_object_versions(**kwargs)

    def test_lazy(self):
        """
        Calling the method does not call AWS; iterating does.
        """
        self.put("file.txt", "1")
        with record_api_calls(self.s3_client) as calls:
            result = self.s3dir_test_with_versioning.list_object_versions()
            assert calls == []
            assert len(result.all()) == 1
        assert calls == ["ListObjectVersions"]

    def test_delimiter(self):
        """
        With ``delimiter="/"``, only the direct objects of the folder.
        """
        self.put("a.txt", "1")
        self.put("sub/b.txt", "1")
        result = self.s3dir_test_with_versioning.list_object_versions(delimiter="/").all()
        assert [self.relative(x) for x in result] == ["a.txt"]

    def test_bucket_without_versioning(self):
        """
        In a bucket that never had versioning, a file has one version,
        ``"null"``.
        """
        p = self.s3dir_test.joinpath("file.txt")
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"1")
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"2")
        result = p.list_object_versions().all()
        assert [x.version_id for x in result] == ["null"]
        assert result[0].size == 1

    def test_missing_bucket(self):
        """
        Errors are raised as is, when the iteration starts.
        """
        p = S3Path(f"s3pathlib-test-tmp-{uuid.uuid4().hex}", "file.txt")
        result = p.list_object_versions()
        with pytest.raises(self.s3_client.exceptions.NoSuchBucket):
            result.all()


class TestMock(ListObjectVersionsMixin):
    use_mock = True


class TestRealAws(ListObjectVersionsMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.iter_object_versions",
        preview=False,
    )

# -*- coding: utf-8 -*-

"""
Test ``S3Path.list_object_versions``.

Test order:

1. a file: its versions and delete markers, newest first, with metadata; only
   this exact key;
2. a folder: every key, in S3 order, each entry once, not again after each
   page;
3. ``limit``, laziness, ``delimiter``, a bucket without versioning, errors;
4. entries written in the same second: the latest entry of each key first.

Sections 1 to 3 write the versions of a key one second apart, so that the
order of all of them is known (S3 timestamps have a one second resolution).
Section 4 writes them in the same second on purpose.
"""

import time
import uuid
from datetime import datetime
from datetime import timezone

import pytest
from botocore.stub import Stubber

from s3pathlib.api import S3Path
from s3pathlib.exc import S3PathTypeError
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import mock_only

SAME_SECOND = datetime(2026, 1, 1, tzinfo=timezone.utc)


def version_entry(version_id: str, is_latest: bool) -> dict:
    return {
        "Key": "file.txt",
        "VersionId": version_id,
        "IsLatest": is_latest,
        "LastModified": SAME_SECOND,
        "ETag": '"etag"',
        "Size": 1,
        "StorageClass": "STANDARD",
    }


def marker_entry(version_id: str, is_latest: bool) -> dict:
    return {
        "Key": "file.txt",
        "VersionId": version_id,
        "IsLatest": is_latest,
        "LastModified": SAME_SECOND,
    }


class ListObjectVersionsMixin(BaseTest):
    module = "core.iter_object_versions"

    def put(self, key: str, body: str) -> str:
        """
        Put an object version under the versioning folder of the test.

        :return: the version id
        """
        s3dir = self.s3dir_test_with_versioning
        res = self.s3_client.put_object(
            Bucket=s3dir.bucket, Key=s3dir.key + key, Body=body
        )
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
        return p.key[len(self.s3dir_test_with_versioning.key) :]

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
            assert (
                self.s3dir_test_with_versioning.list_object_versions(limit=0).all()
                == []
            )
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

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(S3Path(), id="void"),
            pytest.param(S3Path.make_relpath("a/"), id="relpath"),
        ],
    )
    def test_not_an_absolute_path(self, p):
        """
        A relative path or the void path is rejected when the method is
        called, as ``iter_objects`` does, not by botocore while iterating.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(S3PathTypeError, match="is a relative path"):
                p.list_object_versions()
        assert calls == []

    @pytest.mark.parametrize("kind", ["version", "delete-marker"])
    def test_key_that_s3path_cannot_represent(self, kind):
        """
        ``S3Path`` joins consecutive ``/``, so the path of ``a//b.txt`` would
        be ``a/b.txt``, another object that ``delete()`` would delete. A
        version or a delete marker of such a key raises instead of returning
        a wrong path.
        """
        self.put("ok.txt", "1")
        self.put("a//b.txt", "1")
        if kind == "delete-marker":
            self.delete("a//b.txt")
        with pytest.raises(S3ValidationError, match="cannot be represented") as e:
            self.s3dir_test_with_versioning.list_object_versions().all()
        assert "a//b.txt" in str(e.value)

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
        result = self.s3dir_test_with_versioning.list_object_versions(
            delimiter="/"
        ).all()
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

    # --------------------------------------------------------------------------
    # 4. Entries written in the same second
    # --------------------------------------------------------------------------
    @mock_only("a stubbed response with entries of the same timestamp")
    @pytest.mark.parametrize(
        "versions, delete_markers, expected_first",
        [
            pytest.param(
                [version_entry("v1", False)],
                [marker_entry("m1", True)],
                "m1",
                id="latest-is-delete-marker",
            ),
            pytest.param(
                [version_entry("v2", True), version_entry("v1", False)],
                [marker_entry("m1", False)],
                "v2",
                id="latest-is-version",
            ),
        ],
    )
    def test_same_second_latest_first(self, versions, delete_markers, expected_first):
        """
        S3 sends versions and delete markers in two lists, and their
        timestamps have a one second resolution: the entry S3 marks as
        ``IsLatest`` comes first, whatever list it is in.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        stubber.add_response(
            "list_object_versions",
            {
                "Versions": versions,
                "DeleteMarkers": delete_markers,
                "IsTruncated": False,
            },
        )
        with stubber:
            result = S3Path("bucket", "file.txt").list_object_versions(
                s3_client=s3_client
            )
            version_ids = [x.version_id for x in result]
        stubber.assert_no_pending_responses()
        assert version_ids[0] == expected_first
        assert len(version_ids) == len(versions) + len(delete_markers)

    def test_file_deleted_right_after_write(self):
        """
        A file deleted right after it was written (in the same second on AWS):
        the delete marker comes first, so ``one()`` is the latest entry.
        """
        v1 = self.put("file.txt", "1")
        marker = self.delete("file.txt")
        p = self.s3dir_test_with_versioning.joinpath("file.txt")
        assert [x.version_id for x in p.list_object_versions()] == [marker, v1]
        assert p.list_object_versions().one().is_delete_marker() is True

    def test_folder_deleted_right_after_write(self):
        """
        ``delete()`` on a folder right after writing it: in each key, the
        delete marker comes before the version it hides.
        """
        self.put("a.txt", "1")
        self.put("b.txt", "1")
        s3dir = self.s3dir_test_with_versioning
        s3dir.delete()
        result = s3dir.list_object_versions().all()
        entries = [(self.relative(x), x.is_delete_marker()) for x in result]
        assert entries == [
            ("a.txt", True),
            ("a.txt", False),
            ("b.txt", True),
            ("b.txt", False),
        ]


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

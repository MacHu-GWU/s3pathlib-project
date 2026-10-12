# -*- coding: utf-8 -*-

"""
Test ``paginate_list_object_versions``.

Test order:

1. listing: versions, delete markers, ``IsLatest``, a bucket without
   versioning;
2. pagination and ``limit`` (versions, delete markers and folders counted
   together), ``delimiter``, single use, ``iterate_key_and_version``;
3. arguments passed to boto3 (and the page markers), invalid arguments,
   errors.

The tests share one set of object versions, written when the class starts
under ``s3dir_root_with_versioning / "data/"`` (see ``custom_setup_class``),
and only read it. Versions written in the same second may be listed in any
order, so the tests compare counts and sets, not the exact order.
"""

import uuid

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.better_client.list_object_versions import paginate_list_object_versions
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only

# entries of the data set, see custom_setup_class
N_VERSIONS = 6
N_DELETE_MARKERS = 2
N_ENTRIES = N_VERSIONS + N_DELETE_MARKERS


class ListObjectVersionsMixin(BaseTest):
    module = "better_client.list_object_versions"

    prefix: str

    @classmethod
    def custom_setup_class(cls):
        """
        - ``a.txt``: 3 versions, 1 delete marker; the latest is a version
        - ``b.txt``: 1 version, then a delete marker (the latest)
        - ``d1/x.txt``, ``d2/y.txt``: 1 version each
        """
        cls.prefix = cls.s3dir_root_with_versioning.key + "data/"
        bucket = cls.bucket_with_versioning

        def put(key: str):
            cls.s3_client.put_object(Bucket=bucket, Key=cls.prefix + key, Body=b"x")

        def delete(key: str):
            cls.s3_client.delete_object(Bucket=bucket, Key=cls.prefix + key)

        put("a.txt")
        put("a.txt")
        delete("a.txt")
        put("a.txt")
        put("b.txt")
        delete("b.txt")
        put("d1/x.txt")
        put("d2/y.txt")

    def paginate(self, **kwargs):
        return paginate_list_object_versions(
            s3_client=self.s3_client,
            bucket=self.bucket_with_versioning,
            prefix=self.prefix,
            **kwargs,
        )

    def relative(self, key: str) -> str:
        return key[len(self.prefix) :]

    def entries(self, **kwargs) -> list[tuple[str, str]]:
        """
        ``(relative key or prefix, version id)`` of every entry; folders have
        no version id.
        """
        versions, delete_markers, common_prefixes = self.paginate(
            **kwargs
        ).versions_and_delete_markers_and_common_prefixes()
        entries = list()
        for dct in versions + delete_markers:
            entries.append((self.relative(dct["Key"]), dct["VersionId"]))
        for dct in common_prefixes:
            entries.append((self.relative(dct["Prefix"]), None))
        return entries

    # --------------------------------------------------------------------------
    # 1. Listing
    # --------------------------------------------------------------------------
    def test_list_all(self):
        """
        Every version and delete marker under the prefix, with ``IsLatest``
        set on the current one of each key.
        """
        versions, delete_markers, common_prefixes = (
            self.paginate().versions_and_delete_markers_and_common_prefixes()
        )
        assert sorted(self.relative(v["Key"]) for v in versions) == [
            "a.txt",
            "a.txt",
            "a.txt",
            "b.txt",
            "d1/x.txt",
            "d2/y.txt",
        ]
        assert sorted(self.relative(d["Key"]) for d in delete_markers) == [
            "a.txt",
            "b.txt",
        ]
        assert common_prefixes == []
        latest = sorted(
            (self.relative(dct["Key"]), kind)
            for kind, dcts in [("version", versions), ("marker", delete_markers)]
            for dct in dcts
            if dct["IsLatest"]
        )
        assert latest == [
            ("a.txt", "version"),
            ("b.txt", "marker"),
            ("d1/x.txt", "version"),
            ("d2/y.txt", "version"),
        ]

    def test_bucket_without_versioning(self):
        """
        In a bucket that never had versioning, each object has one version,
        whose id is ``"null"``.
        """
        key = self.s3dir_test.key + "file.txt"
        self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=b"1")
        self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=b"2")
        result = paginate_list_object_versions(
            s3_client=self.s3_client,
            bucket=self.bucket,
            prefix=self.s3dir_test.key,
        )
        assert list(result.iterate_key_and_version()) == [(key, "null")]

    # --------------------------------------------------------------------------
    # 2. Pagination, limit, delimiter
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "batch_size, n_calls",
        [pytest.param(3, 3, id="3-per-page"), pytest.param(1000, 1, id="default")],
    )
    def test_pagination(self, batch_size, n_calls):
        """
        All pages together give every entry once.
        """
        with record_api_calls(self.s3_client) as calls:
            entries = self.entries(batch_size=batch_size)
        assert len(entries) == N_ENTRIES
        assert len(set(entries)) == N_ENTRIES
        assert calls == ["ListObjectVersions"] * n_calls

    @pytest.mark.parametrize(
        "batch_size, limit, n_calls",
        [
            pytest.param(3, 5, 2, id="limit-over-two-pages"),
            pytest.param(10, 3, 1, id="limit-under-batch-size"),
            pytest.param(3, 6, 2, id="limit-on-page-boundary"),
            pytest.param(3, 100, 3, id="limit-over-total"),
        ],
    )
    def test_limit(self, batch_size, limit, n_calls):
        """
        ``limit`` counts versions and delete markers together, and no page is
        fetched after it is reached: ``limit=3`` returns 3 entries, not 4.
        """
        with record_api_calls(self.s3_client) as calls:
            entries = self.entries(batch_size=batch_size, limit=limit)
        assert len(entries) == min(limit, N_ENTRIES)
        assert len(set(entries)) == len(entries)
        assert calls == ["ListObjectVersions"] * n_calls

    def test_limit_zero(self):
        """
        ``limit=0`` returns nothing without calling AWS.
        """
        with record_api_calls(self.s3_client) as calls:
            assert self.entries(limit=0) == []
        assert calls == []

    def test_limit_none(self):
        """
        ``limit=None`` is no limit, the same as leaving it out.
        """
        assert len(self.entries(batch_size=3, limit=None)) == N_ENTRIES

    def test_delimiter(self):
        """
        With ``delimiter="/"``, the entries of the direct objects are listed
        and the sub folders are common prefixes.
        """
        versions, delete_markers, common_prefixes = self.paginate(
            delimiter="/"
        ).versions_and_delete_markers_and_common_prefixes()
        assert sorted({self.relative(v["Key"]) for v in versions}) == ["a.txt", "b.txt"]
        assert len(versions) == 4
        assert len(delete_markers) == 2
        assert [self.relative(cp["Prefix"]) for cp in common_prefixes] == ["d1/", "d2/"]

    @pytest.mark.parametrize("batch_size", [2, 1000])
    def test_delimiter_limit(self, batch_size):
        """
        ``limit`` counts the folders too: the 6 entries of ``a.txt`` and
        ``b.txt``, then the first folder.
        """
        entries = self.entries(delimiter="/", limit=7, batch_size=batch_size)
        assert len(entries) == 7
        assert ("d1/", None) in entries
        assert ("d2/", None) not in entries

    def test_parts(self):
        """
        ``versions()``, ``delete_markers()`` and ``common_prefixes()`` each
        give one part of the responses.
        """
        assert len(self.paginate().versions().all()) == N_VERSIONS
        delete_markers = self.paginate().delete_markers().all()
        assert sorted(self.relative(d["Key"]) for d in delete_markers) == [
            "a.txt",
            "b.txt",
        ]
        common_prefixes = self.paginate(delimiter="/").common_prefixes().all()
        assert [self.relative(cp["Prefix"]) for cp in common_prefixes] == ["d1/", "d2/"]

    def test_single_use(self):
        """
        The result can be iterated only once.
        """
        result = self.paginate()
        assert len(result.versions().all()) == N_VERSIONS
        assert result.delete_markers().all() == []

    def test_iterate_key_and_version(self):
        """
        Every ``(key, version_id)`` pair, versions and delete markers.
        """
        res = self.s3_client.list_object_versions(
            Bucket=self.bucket_with_versioning,
            Prefix=self.prefix,
        )
        expected = {
            (dct["Key"], dct["VersionId"])
            for dct in res["Versions"] + res["DeleteMarkers"]
        }
        pairs = list(self.paginate(batch_size=3).iterate_key_and_version())
        assert len(pairs) == N_ENTRIES
        assert set(pairs) == expected

    # --------------------------------------------------------------------------
    # 3. Arguments and errors
    # --------------------------------------------------------------------------
    def test_arguments_passed_to_boto3(self):
        """
        Every argument reaches list_object_versions under its API name. The
        next page starts at the markers of the previous one, and asks for the
        remaining entries; a page that ends with a folder has no version id
        marker.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        common = {
            "Bucket": "my-bucket",
            "Prefix": "folder/",
            "Delimiter": "/",
            "EncodingType": "url",
            "RequestPayer": "requester",
            "ExpectedBucketOwner": "111122223333",
        }
        stubber.add_response(
            "list_object_versions",
            {
                "Versions": [{"Key": "folder/a", "VersionId": "v2"}],
                "DeleteMarkers": [{"Key": "folder/a", "VersionId": "v1"}],
                "IsTruncated": True,
                "NextKeyMarker": "folder/a",
                "NextVersionIdMarker": "v1",
            },
            expected_params={**common, "MaxKeys": 2},
        )
        stubber.add_response(
            "list_object_versions",
            {
                "CommonPrefixes": [{"Prefix": "folder/b/"}, {"Prefix": "folder/c/"}],
                "IsTruncated": True,
                "NextKeyMarker": "folder/c/",
            },
            expected_params={
                **common,
                "MaxKeys": 2,
                "KeyMarker": "folder/a",
                "VersionIdMarker": "v1",
            },
        )
        stubber.add_response(
            "list_object_versions",
            {
                "Versions": [{"Key": "folder/d", "VersionId": "v3"}],
                "IsTruncated": False,
            },
            expected_params={**common, "MaxKeys": 1, "KeyMarker": "folder/c/"},
        )
        with stubber:
            result = paginate_list_object_versions(
                s3_client=s3_client,
                bucket="my-bucket",
                prefix="folder/",
                batch_size=2,
                limit=5,
                delimiter="/",
                encoding_type="url",
                request_payer="requester",
                expected_bucket_owner="111122223333",
            )
            versions, delete_markers, common_prefixes = (
                result.versions_and_delete_markers_and_common_prefixes()
            )
        assert [v["VersionId"] for v in versions] == ["v2", "v3"]
        assert [d["VersionId"] for d in delete_markers] == ["v1"]
        assert [cp["Prefix"] for cp in common_prefixes] == ["folder/b/", "folder/c/"]
        stubber.assert_no_pending_responses()

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            pytest.param({"batch_size": 0}, "batch_size", id="batch-size-0"),
            pytest.param({"batch_size": 1001}, "batch_size", id="batch-size-1001"),
            pytest.param({"limit": -1}, "must not be negative", id="limit-negative"),
        ],
    )
    def test_invalid_arguments(self, kwargs, match):
        """
        Invalid arguments are rejected when the function is called, before any
        API call (S3 rejects a negative MaxKeys, moto silently accepts it).
        """
        with pytest.raises(ValueError, match=match):
            paginate_list_object_versions(
                s3_client=None, bucket="b", prefix="p", **kwargs
            )

    def test_missing_bucket(self):
        """
        Errors are raised as is, when the iteration starts.
        """
        result = paginate_list_object_versions(
            s3_client=self.s3_client,
            bucket=f"s3pathlib-test-tmp-{uuid.uuid4().hex}",
            prefix="",
        )
        with pytest.raises(self.s3_client.exceptions.NoSuchBucket):
            result.all()

    @real_aws_only("moto does not model buckets of other accounts (NoSuchBucket)")
    def test_bucket_of_other_account(self):
        """
        The bucket ``aws`` belongs to another account: ``AccessDenied``.
        """
        result = paginate_list_object_versions(
            s3_client=self.s3_client, bucket="aws", prefix=""
        )
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            result.all()
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"


class TestMock(ListObjectVersionsMixin):
    use_mock = True


class TestRealAws(ListObjectVersionsMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.better_client.list_object_versions",
        preview=False,
    )

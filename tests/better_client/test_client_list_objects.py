# -*- coding: utf-8 -*-

"""
Test ``paginate_list_objects_v2``, ``is_content_an_object``,
``calculate_total_size`` and ``count_objects``.

Test order:

1. ``paginate_list_objects_v2``: listing, pagination, ``limit`` (objects and
   folders counted together), ``delimiter``, single use, arguments passed to
   boto3, invalid arguments, errors;
2. ``is_content_an_object``: the truth table;
3. ``calculate_total_size`` and ``count_objects``.

The tests share one set of objects, written when the class starts under
``s3dir_root / "data/"`` (see ``DATA``), and only read it.
"""

import uuid

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.better_client.list_objects import calculate_total_size
from s3pathlib.better_client.list_objects import count_objects
from s3pathlib.better_client.list_objects import is_content_an_object
from s3pathlib.better_client.list_objects import paginate_list_objects_v2
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only

# key (relative to the data folder) -> body
DATA = {
    "a.txt": b"aaaaa",
    "b.txt": b"",  # an empty file is an object
    "d1/1.txt": b"11111",
    "d1/2.txt": b"22222",
    "d2/": b"",  # folder marker
    "d2/3.txt": b"33333",
    "d3/": b"",  # empty folder, only the marker
    "data-folder/": b"",  # starts with "d" too
    "non-empty/": b"abc",  # ends with "/" but has data: an object
    "x/y/z.txt": b"zzzzz",
}
KEYS = sorted(DATA)


class ListObjectsMixin(BaseTest):
    module = "better_client.list_objects"

    prefix: str

    @classmethod
    def custom_setup_class(cls):
        cls.prefix = cls.s3dir_root.key + "data/"
        for key, body in DATA.items():
            cls.s3_client.put_object(Bucket=cls.bucket, Key=cls.prefix + key, Body=body)

    def list_keys(self, **kwargs) -> list[str]:
        """
        The keys (relative to the data folder) returned by the paginator.
        """
        result = paginate_list_objects_v2(
            s3_client=self.s3_client,
            bucket=self.bucket,
            prefix=self.prefix,
            **kwargs,
        )
        return [content["Key"][len(self.prefix) :] for content in result.contents()]

    def list_both(self, **kwargs) -> tuple[list[str], list[str]]:
        """
        The keys and the common prefixes (relative to the data folder).
        """
        contents, common_prefixes = paginate_list_objects_v2(
            s3_client=self.s3_client,
            bucket=self.bucket,
            prefix=self.prefix,
            **kwargs,
        ).contents_and_common_prefixes()
        keys = [content["Key"][len(self.prefix) :] for content in contents]
        prefixes = [cp["Prefix"][len(self.prefix) :] for cp in common_prefixes]
        return keys, prefixes

    # --------------------------------------------------------------------------
    # 1. paginate_list_objects_v2
    # --------------------------------------------------------------------------
    def test_list_all(self):
        """
        Every key under the prefix, in key order, folder markers included.
        """
        assert self.list_keys() == KEYS

    @pytest.mark.parametrize(
        "batch_size, n_calls",
        [
            pytest.param(3, 4, id="3-per-page"),
            pytest.param(10, 1, id="exact"),
            pytest.param(1000, 1, id="default"),
        ],
    )
    def test_pagination(self, batch_size, n_calls):
        """
        ``batch_size`` is the page size; all pages together give every key.
        """
        with record_api_calls(self.s3_client) as calls:
            keys = self.list_keys(batch_size=batch_size)
        assert keys == KEYS
        assert calls == ["ListObjectsV2"] * n_calls

    @pytest.mark.parametrize(
        "batch_size, limit, n_calls",
        [
            pytest.param(3, 5, 2, id="limit-over-two-pages"),
            pytest.param(10, 3, 1, id="limit-under-batch-size"),
            pytest.param(3, 6, 2, id="limit-on-page-boundary"),
            pytest.param(3, 100, 4, id="limit-over-total"),
            pytest.param(3, None, 4, id="none-is-no-limit"),
        ],
    )
    def test_limit(self, batch_size, limit, n_calls):
        """
        ``limit`` caps the total, and no page is fetched after it is reached;
        ``None`` is no limit.
        """
        with record_api_calls(self.s3_client) as calls:
            keys = self.list_keys(batch_size=batch_size, limit=limit)
        assert keys == KEYS[:limit]
        assert calls == ["ListObjectsV2"] * n_calls

    def test_limit_zero(self):
        """
        ``limit=0`` returns nothing without calling AWS.
        """
        with record_api_calls(self.s3_client) as calls:
            assert self.list_keys(limit=0) == []
        assert calls == []

    def test_delimiter(self):
        """
        With ``delimiter="/"``, the direct objects are contents and the sub
        folders are common prefixes.
        """
        keys, prefixes = self.list_both(delimiter="/")
        assert keys == ["a.txt", "b.txt"]
        assert prefixes == ["d1/", "d2/", "d3/", "data-folder/", "non-empty/", "x/"]

        result = paginate_list_objects_v2(
            s3_client=self.s3_client,
            bucket=self.bucket,
            prefix=self.prefix,
            delimiter="/",
        )
        assert [
            cp["Prefix"][len(self.prefix) :] for cp in result.common_prefixes()
        ] == prefixes

    @pytest.mark.parametrize("batch_size", [2, 1000])
    def test_delimiter_limit(self, batch_size):
        """
        ``limit`` counts objects and folders together, in key order. Before
        3.0 it only counted objects, and ``limit=3`` returned 8 entries.
        """
        keys, prefixes = self.list_both(delimiter="/", limit=3, batch_size=batch_size)
        assert keys == ["a.txt", "b.txt"]
        assert prefixes == ["d1/"]

    def test_single_use(self):
        """
        The result can be iterated only once: the second iteration is empty.
        Use ``contents_and_common_prefixes`` to get both.
        """
        result = paginate_list_objects_v2(
            s3_client=self.s3_client,
            bucket=self.bucket,
            prefix=self.prefix,
        )
        assert len(result.contents().all()) == len(KEYS)
        assert result.common_prefixes().all() == []
        assert result.contents().all() == []

    def test_prefix_is_a_string_prefix(self):
        """
        ``prefix`` is not a folder: ``d`` matches ``d1/`` and ``data-folder/``;
        a prefix that matches nothing gives nothing.
        """
        keys = [
            content["Key"][len(self.prefix) :]
            for content in paginate_list_objects_v2(
                s3_client=self.s3_client,
                bucket=self.bucket,
                prefix=self.prefix + "d",
            ).contents()
        ]
        assert keys == [key for key in KEYS if key.startswith("d")]

        result = paginate_list_objects_v2(
            s3_client=self.s3_client,
            bucket=self.bucket,
            prefix=self.prefix + "nothing/",
        )
        assert result.contents().all() == []

    def test_arguments_passed_to_boto3(self):
        """
        Every argument reaches list_objects_v2 under its API name; the next
        page uses the continuation token and asks for the remaining entries.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        common = {
            "Bucket": "my-bucket",
            "Prefix": "folder/",
            "Delimiter": "/",
            "EncodingType": "url",
            "FetchOwner": True,
            "StartAfter": "folder/a",
            "RequestPayer": "requester",
            "ExpectedBucketOwner": "111122223333",
        }
        stubber.add_response(
            "list_objects_v2",
            {
                "Contents": [{"Key": "folder/b"}, {"Key": "folder/c"}],
                "IsTruncated": True,
                "NextContinuationToken": "token-1",
            },
            expected_params={**common, "MaxKeys": 2},
        )
        stubber.add_response(
            "list_objects_v2",
            {"CommonPrefixes": [{"Prefix": "folder/d/"}], "IsTruncated": False},
            expected_params={**common, "MaxKeys": 1, "ContinuationToken": "token-1"},
        )
        with stubber:
            result = paginate_list_objects_v2(
                s3_client=s3_client,
                bucket="my-bucket",
                prefix="folder/",
                batch_size=2,
                limit=3,
                delimiter="/",
                encoding_type="url",
                fetch_owner=True,
                start_after="folder/a",
                request_payer="requester",
                expected_bucket_owner="111122223333",
            )
            contents, common_prefixes = result.contents_and_common_prefixes()
        assert [c["Key"] for c in contents] == ["folder/b", "folder/c"]
        assert [cp["Prefix"] for cp in common_prefixes] == ["folder/d/"]
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
            paginate_list_objects_v2(s3_client=None, bucket="b", prefix="p", **kwargs)

    def test_missing_bucket(self):
        """
        Errors are raised as is, when the iteration starts: the function itself
        does not call AWS.
        """
        result = paginate_list_objects_v2(
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
        result = paginate_list_objects_v2(
            s3_client=self.s3_client, bucket="aws", prefix=""
        )
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            result.all()
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    # --------------------------------------------------------------------------
    # 2. is_content_an_object
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "key, size, expected",
        [
            pytest.param("folder/", 0, False, id="folder-marker"),
            pytest.param("folder/", 3, True, id="slash-with-data"),
            pytest.param("file.txt", 0, True, id="empty-file"),
            pytest.param("file.txt", 3, True, id="file"),
        ],
    )
    def test_is_content_an_object(self, key, size, expected):
        """
        Only an empty object whose key ends with ``/`` is a folder marker.
        """
        assert is_content_an_object({"Key": key, "Size": size}) is expected

    # --------------------------------------------------------------------------
    # 3. calculate_total_size and count_objects
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "sub_prefix, include_folder, expected",
        [
            pytest.param("", False, (7, 28), id="all-without-markers"),
            pytest.param("", True, (10, 28), id="all-with-markers"),
            pytest.param("d2/", False, (1, 5), id="folder-without-marker"),
            pytest.param("d2/", True, (2, 5), id="folder-with-marker"),
            pytest.param("d3/", False, (0, 0), id="empty-folder"),
            pytest.param("d3/", True, (1, 0), id="empty-folder-marker"),
            pytest.param("d", False, (3, 15), id="string-prefix"),
            pytest.param("nothing/", True, (0, 0), id="missing-prefix"),
        ],
    )
    def test_calculate_total_size_and_count_objects(
        self, sub_prefix, include_folder, expected
    ):
        """
        The number of objects and their total size under a prefix; folder
        markers are counted only with ``include_folder=True``.
        ``count_objects`` gives the same count.
        """
        prefix = self.prefix + sub_prefix
        result = calculate_total_size(
            s3_client=self.s3_client,
            bucket=self.bucket,
            prefix=prefix,
            include_folder=include_folder,
        )
        assert result == expected
        count = count_objects(
            s3_client=self.s3_client,
            bucket=self.bucket,
            prefix=prefix,
            include_folder=include_folder,
        )
        assert count == expected[0]


class TestMock(ListObjectsMixin):
    use_mock = True


class TestRealAws(ListObjectsMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.better_client.list_objects",
        preview=False,
    )

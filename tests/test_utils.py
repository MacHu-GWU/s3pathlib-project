# -*- coding: utf-8 -*-

"""
Each function is tested in the same order:

1. normal usage and boundaries;
2. invalid inputs, one case per ``raise``;
3. properties that tie functions together (round trips).
"""

from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest

from s3pathlib.api import utils
from s3pathlib.constants import AwsPartitionEnum
from s3pathlib.constants import AWS_CONSOLE_DOMAIN
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test


# ------------------------------------------------------------------------------
# split_s3_uri / join_s3_uri
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "uri, expected",
    [
        pytest.param(
            "s3://my-bucket/my-prefix/my-file.zip",
            ("my-bucket", "my-prefix/my-file.zip"),
            id="file",
        ),
        pytest.param(
            "s3://my-bucket/my-prefix/", ("my-bucket", "my-prefix/"), id="folder"
        ),
        pytest.param("s3://my-bucket/", ("my-bucket", ""), id="bucket"),
        pytest.param("s3://my-bucket", ("my-bucket", ""), id="bucket-no-slash"),
        pytest.param("s3://my-bucket/a//b", ("my-bucket", "a//b"), id="key-kept-as-is"),
        pytest.param(
            "s3://My_Legacy_Bucket/a:b.txt",
            ("My_Legacy_Bucket", "a:b.txt"),
            id="legacy-bucket-colon-in-key",
        ),
    ],
)
def test_split_s3_uri(uri, expected):
    """
    An S3 URI splits into bucket and key; the key is returned exactly as
    written. Only the format is checked, so a legacy bucket name and a ``:``
    in the key are fine.
    """
    assert utils.split_s3_uri(uri) == expected


@pytest.mark.parametrize(
    "uri, message",
    [
        pytest.param("my-bucket/key", "must start with 's3://'", id="no-scheme"),
        pytest.param("s3:/my-bucket/key", "must start with 's3://'", id="bad-scheme"),
        pytest.param(
            "https://my-bucket/key", "must start with 's3://'", id="other-scheme"
        ),
        pytest.param("s3://", "bucket is empty", id="empty"),
        pytest.param("s3:///key", "bucket is empty", id="empty-bucket"),
        pytest.param("s3://a:b/key", "contains ':'", id="colon-in-bucket"),
    ],
)
def test_split_s3_uri_invalid(uri, message):
    """
    A string that is not a well formed S3 URI is rejected instead of being
    split into a wrong bucket and key.
    """
    with pytest.raises(S3ValidationError, match=message):
        utils.split_s3_uri(uri)


@pytest.mark.parametrize(
    "bucket, key, expected",
    [
        ("my-bucket", "my-prefix/my-file.zip", "s3://my-bucket/my-prefix/my-file.zip"),
        ("my-bucket", "my-prefix/", "s3://my-bucket/my-prefix/"),
        ("my-bucket", "", "s3://my-bucket/"),
    ],
)
def test_join_s3_uri(bucket, key, expected):
    """
    Bucket and key join into an S3 URI; an empty key is the bucket root.
    """
    assert utils.join_s3_uri(bucket, key) == expected


@pytest.mark.parametrize(
    "key", ["file.txt", "a/b/c.txt", "folder/", "", "数据/a b.csv"]
)
def test_split_and_join_s3_uri_round_trip(key):
    """
    ``split_s3_uri`` is the inverse of ``join_s3_uri``.
    """
    assert utils.split_s3_uri(utils.join_s3_uri("my-bucket", key)) == ("my-bucket", key)


# ------------------------------------------------------------------------------
# split_s3_arn
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "arn, expected",
    [
        pytest.param("arn:aws:s3:::bucket", ("aws", "bucket", ""), id="bucket"),
        pytest.param(
            "arn:aws:s3:::bucket/", ("aws", "bucket", ""), id="bucket-with-slash"
        ),
        pytest.param(
            "arn:aws:s3:::bucket/folder/", ("aws", "bucket", "folder/"), id="folder"
        ),
        pytest.param(
            "arn:aws-cn:s3:::bucket/folder/file.txt",
            ("aws-cn", "bucket", "folder/file.txt"),
            id="aws-cn",
        ),
        pytest.param(
            "arn:aws-us-gov:s3:::bucket/file.txt",
            ("aws-us-gov", "bucket", "file.txt"),
            id="aws-us-gov",
        ),
        pytest.param(
            "arn:aws-eusc:s3:::bucket/file.txt",
            ("aws-eusc", "bucket", "file.txt"),
            id="aws-eusc",
        ),
        pytest.param(
            "arn:aws:s3:::My_Legacy_Bucket/a:b.txt",
            ("aws", "My_Legacy_Bucket", "a:b.txt"),
            id="legacy-bucket-colon-in-key",
        ),
    ],
)
def test_split_s3_arn(arn, expected):
    """
    An S3 ARN in any supported partition splits into partition, bucket and
    key; the partition is an ``AwsPartitionEnum`` member.
    """
    partition, bucket, key = utils.split_s3_arn(arn)
    assert (partition, bucket, key) == expected
    assert isinstance(partition, AwsPartitionEnum)


@pytest.mark.parametrize(
    "arn",
    [
        pytest.param("s3://bucket/key", id="uri"),
        pytest.param("arn:aws-iso:s3:::bucket/key", id="unsupported-partition"),
        pytest.param("arn:aws:iam::bucket/key", id="not-s3"),
    ],
)
def test_split_s3_arn_invalid(arn):
    """
    Anything that is not an S3 ARN of a supported partition is rejected, and
    the message lists the supported partitions.
    """
    with pytest.raises(S3ValidationError, match="aws, aws-cn, aws-us-gov, aws-eusc"):
        utils.split_s3_arn(arn)


@pytest.mark.parametrize(
    "arn, message",
    [
        pytest.param("arn:aws:s3:::", "bucket is empty", id="empty"),
        pytest.param("arn:aws:s3:::/key", "bucket is empty", id="empty-bucket"),
        pytest.param("arn:aws:s3:::a:b/key", "contains ':'", id="colon-in-bucket"),
    ],
)
def test_split_s3_arn_bad_bucket_part(arn, message):
    """
    A well formed ARN prefix with an empty or impossible bucket part is
    rejected.
    """
    with pytest.raises(S3ValidationError, match=message):
        utils.split_s3_arn(arn)


# ------------------------------------------------------------------------------
# split_parts / smart_join_s3_key
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "key, expected",
    [
        ("a/b/c", ["a", "b", "c"]),
        ("//a//b//c//", ["a", "b", "c"]),
        ("a", ["a"]),
        ("", []),
        ("////", []),
        ("a b/c.d/中文", ["a b", "c.d", "中文"]),
    ],
)
def test_split_parts(key, expected):
    """
    A key splits on ``/``; empty segments from repeated, leading or trailing
    slashes are dropped.
    """
    assert utils.split_parts(key) == expected


@pytest.mark.parametrize(
    "parts, is_dir, expected",
    [
        (["/a/", "b/", "/c"], True, "a/b/c/"),
        (["/a/", "b/", "/c"], False, "a/b/c"),
        (["//a//b//c//"], True, "a/b/c/"),
        (["//a//b//c//"], False, "a/b/c"),
        (["a", "", "/", "b"], False, "a/b"),
        (["a"], True, "a/"),
    ],
)
def test_smart_join_s3_key(parts, is_dir, expected):
    """
    Parts join with a single ``/``; ``is_dir`` controls the trailing slash.
    """
    assert utils.smart_join_s3_key(parts=parts, is_dir=is_dir) == expected


@pytest.mark.parametrize("parts", [[], [""], ["/", "//"]])
@pytest.mark.parametrize("is_dir", [True, False])
def test_smart_join_s3_key_no_parts_is_root(parts, is_dir):
    """
    With no non-empty part the key is ``""`` (the bucket root), not ``"/"``,
    which would be a folder literally named empty string.
    """
    assert utils.smart_join_s3_key(parts=parts, is_dir=is_dir) == ""


@pytest.mark.parametrize("key", ["a/b/c", "a/b/c/", "a", "a/"])
def test_split_parts_and_smart_join_round_trip(key):
    """
    Splitting a normalized key and joining it back gives the same key.
    """
    is_dir = key.endswith("/")
    assert utils.smart_join_s3_key(utils.split_parts(key), is_dir=is_dir) == key


# ------------------------------------------------------------------------------
# make_s3_console_url
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kwargs, expected",
    [
        pytest.param(
            dict(bucket="my-bucket", prefix="my-folder/data.json"),
            "https://console.aws.amazon.com/s3/object/my-bucket?prefix=my-folder/data.json",
            id="object",
        ),
        pytest.param(
            dict(bucket="my-bucket", prefix="my-folder/"),
            "https://console.aws.amazon.com/s3/buckets/my-bucket?prefix=my-folder/",
            id="folder",
        ),
        pytest.param(
            dict(bucket="my-bucket", prefix=""),
            "https://console.aws.amazon.com/s3/buckets/my-bucket?tab=objects",
            id="bucket-root",
        ),
        pytest.param(
            dict(s3_uri="s3://my-bucket/my-folder/data.json"),
            "https://console.aws.amazon.com/s3/object/my-bucket?prefix=my-folder/data.json",
            id="from-uri",
        ),
        pytest.param(
            dict(s3_uri="s3://my-bucket/my-file.zip", version_id="v123"),
            "https://console.aws.amazon.com/s3/object/my-bucket?prefix=my-file.zip&versionId=v123",
            id="version-id",
        ),
        pytest.param(
            dict(s3_uri="s3://my-bucket/my-file.zip", aws_region="us-east-1"),
            "https://us-east-1.console.aws.amazon.com/s3/object/my-bucket?region=us-east-1&prefix=my-file.zip",
            id="regional",
        ),
        pytest.param(
            dict(s3_uri="s3://my-bucket/", aws_region="us-east-1"),
            "https://us-east-1.console.aws.amazon.com/s3/buckets/my-bucket?region=us-east-1&tab=objects",
            id="regional-bucket-root",
        ),
        pytest.param(
            dict(s3_uri="s3://my-bucket/my-file.zip", partition="aws-us-gov"),
            "https://console.amazonaws-us-gov.com/s3/object/my-bucket?prefix=my-file.zip",
            id="us-gov",
        ),
        pytest.param(
            dict(
                s3_uri="s3://my-bucket/my-file.zip",
                partition="aws-us-gov",
                aws_region="us-gov-east-1",
            ),
            "https://us-gov-east-1.console.amazonaws-us-gov.com/s3/object/my-bucket?region=us-gov-east-1&prefix=my-file.zip",
            id="us-gov-partition-regional",
        ),
        pytest.param(
            dict(
                s3_uri="s3://my-bucket/my-file.zip",
                partition="aws-cn",
                aws_region="cn-north-1",
            ),
            "https://cn-north-1.console.amazonaws.cn/s3/object/my-bucket?region=cn-north-1&prefix=my-file.zip",
            id="china-regional",
        ),
        pytest.param(
            dict(s3_uri="s3://my-bucket/my-folder/", partition="aws-cn"),
            "https://console.amazonaws.cn/s3/buckets/my-bucket?prefix=my-folder/",
            id="china-folder",
        ),
        pytest.param(
            dict(
                s3_uri="s3://my-bucket/my-file.zip",
                partition="aws-eusc",
                aws_region="eusc-de-east-1",
            ),
            "https://eusc-de-east-1.console.amazonaws-eusc.eu/s3/object/my-bucket?region=eusc-de-east-1&prefix=my-file.zip",
            id="eusc-regional",
        ),
        pytest.param(
            dict(s3_uri="s3://my-bucket/my-file.zip", partition=AwsPartitionEnum.aws),
            "https://console.aws.amazon.com/s3/object/my-bucket?prefix=my-file.zip",
            id="partition-enum",
        ),
    ],
)
def test_make_s3_console_url(kwargs, expected):
    """
    The URL points at the bucket root, a folder or an object, in the chosen
    partition and region, optionally at a specific version.
    """
    assert utils.make_s3_console_url(**kwargs) == expected


@pytest.mark.parametrize(
    "key",
    [
        "a&b.txt",
        "a#b.txt",
        "a b.txt",
        "a+b.txt",
        "a?b=c.txt",
        "a%20b.txt",
        "数据/报表.csv",
        "folder/a&b/",
    ],
)
def test_make_s3_console_url_encodes_key(key):
    """
    The key is URL encoded, so ``&``, ``#``, ``?``, ``+``, spaces, ``%`` and
    non-ASCII characters cannot break the query string; decoding the
    ``prefix`` parameter gives back exactly the key.
    """
    url = utils.make_s3_console_url(bucket="my-bucket", prefix=key)
    query = urlsplit(url).query
    assert "#" not in url
    assert parse_qs(query) == {"prefix": [key]}


def test_every_partition_has_console_domain():
    """
    Adding a partition to ``AwsPartitionEnum`` without its console domain
    would make console URLs fail for it.
    """
    assert set(AWS_CONSOLE_DOMAIN) == set(AwsPartitionEnum)


def test_make_s3_console_url_keeps_slash_readable():
    """
    ``/`` is not encoded, so the URL stays readable.
    """
    url = utils.make_s3_console_url(bucket="my-bucket", prefix="a/b/c.txt")
    assert url.endswith("prefix=a/b/c.txt")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        pytest.param(
            dict(bucket="my-bucket"), "pass both bucket and prefix", id="bucket-only"
        ),
        pytest.param(
            dict(prefix="key"), "pass both bucket and prefix", id="prefix-only"
        ),
        pytest.param(dict(), "pass both bucket and prefix", id="nothing"),
        pytest.param(
            dict(bucket="b", prefix="k", s3_uri="s3://b/k"), "not both", id="both-forms"
        ),
    ],
)
def test_make_s3_console_url_invalid_args(kwargs, message):
    """
    Each invalid combination of arguments is rejected with a message that
    says what is wrong.
    """
    with pytest.raises(ValueError, match=message):
        utils.make_s3_console_url(**kwargs)


def test_make_s3_console_url_invalid_uri():
    """
    A malformed ``s3_uri`` is rejected by the URI parser.
    """
    with pytest.raises(S3ValidationError):
        utils.make_s3_console_url(s3_uri="https://my-bucket/key")


def test_make_s3_console_url_unsupported_partition():
    """
    An unsupported partition is rejected, and the message lists the
    supported ones.
    """
    with pytest.raises(
        S3ValidationError,
        match="partition must be one of aws, aws-cn, aws-us-gov, aws-eusc, got 'aws-iso'",
    ):
        utils.make_s3_console_url(s3_uri="s3://b/k", partition="aws-iso")


def test_make_s3_console_url_empty_region():
    """
    An empty region would build a host starting with ``.``; ``None`` is the
    way to ask for the global console.
    """
    with pytest.raises(S3ValidationError, match="aws_region must not be empty"):
        utils.make_s3_console_url(s3_uri="s3://b/k", aws_region="")


# ------------------------------------------------------------------------------
# ensure_s3_object / ensure_s3_dir
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["path/to/key", "s3://bucket/key", "key"])
def test_ensure_s3_object(value):
    """
    A key or URI without a trailing ``/`` is an object.
    """
    utils.ensure_s3_object(value)


@pytest.mark.parametrize("value", ["path/to/dir/", "s3://bucket/"])
def test_ensure_s3_object_invalid(value):
    """
    A folder is rejected with ``S3ValidationError``, still a ``ValueError``.
    """
    with pytest.raises(S3ValidationError, match="doesn't represent s3 object"):
        utils.ensure_s3_object(value)


@pytest.mark.parametrize("value", ["path/to/dir/", "s3://bucket/"])
def test_ensure_s3_dir(value):
    """
    A key or URI with a trailing ``/`` is a folder.
    """
    utils.ensure_s3_dir(value)


@pytest.mark.parametrize("value", ["path/to/key", "s3://bucket", ""])
def test_ensure_s3_dir_invalid(value):
    """
    Anything without a trailing ``/`` is rejected.
    """
    with pytest.raises(S3ValidationError, match="doesn't represent s3 dir"):
        utils.ensure_s3_dir(value)


# ------------------------------------------------------------------------------
# repr_data_size / parse_data_size
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "size, expected",
    [
        pytest.param(0, "0 B", id="zero"),
        pytest.param(100, "100 B", id="bytes"),
        pytest.param(1023, "1023 B", id="max-bytes"),
        pytest.param(1024, "1.00 KB", id="1-KB"),
        pytest.param(100_000, "97.66 KB", id="KB"),
        pytest.param(3_600_000, "3.43 MB", id="MB"),
        pytest.param(1024**2 - 1, "1.00 MB", id="rounding-carries-to-MB"),
        pytest.param(1024**3, "1.00 GB", id="GB"),
        pytest.param(1024**4, "1.00 TB", id="TB"),
        pytest.param(1024**5, "1.00 PB", id="PB"),
        pytest.param(1024**6, "1.00 EB", id="EB"),
        pytest.param(1024**7, "1.00 ZB", id="ZB"),
        pytest.param(1024**8, "1.00 YB", id="YB"),
        pytest.param(1024**9, "1024.00 YB", id="beyond-YB-stays-in-YB"),
        pytest.param(1024**9 - 1, "1024.00 YB", id="rounding-at-last-unit"),
    ],
)
def test_repr_data_size(size, expected):
    """
    Sizes are shown with 1024 based units; a value that rounds up to 1024 of
    a unit is shown as 1 of the next unit, and ``YB`` is the largest unit.
    """
    assert utils.repr_data_size(size) == expected


def test_repr_data_size_precision():
    """
    ``precision`` sets the number of digits after the decimal point.
    """
    assert utils.repr_data_size(100_000, precision=0) == "98 KB"
    assert utils.repr_data_size(100_000, precision=4) == "97.6562 KB"


def test_repr_data_size_negative():
    """
    A negative size is a bug in the caller, so it is rejected.
    """
    with pytest.raises(ValueError, match="cannot be negative"):
        utils.repr_data_size(-1)


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param("3.43 MB", 3596615, id="MB"),
        pytest.param("2_512.4 MB", 2634442342, id="underscore-separator"),
        pytest.param("2,512.4 MB", 2634442342, id="comma-separator"),
        pytest.param("1.5kb", 1536, id="lowercase-no-space"),
        pytest.param("  1 GB  ", 1024**3, id="surrounding-spaces"),
        pytest.param("100", 100, id="no-unit-is-bytes"),
        pytest.param("100 B", 100, id="bytes"),
        pytest.param(".5 KB", 512, id="leading-dot"),
        pytest.param("1 YB", 1024**8, id="YB"),
    ],
)
def test_parse_data_size(text, expected):
    """
    A human readable size parses into bytes; units are case insensitive and
    1024 based, a bare number is bytes.
    """
    assert utils.parse_data_size(text) == expected


@pytest.mark.parametrize(
    "text, message",
    [
        pytest.param("", "cannot parse", id="empty"),
        pytest.param("MB", "cannot parse", id="no-number"),
        pytest.param("-1 KB", "cannot parse", id="negative"),
        pytest.param("1 2 KB", "cannot parse", id="two-numbers"),
        pytest.param("1 KiB", "unknown unit 'KiB'", id="unknown-unit"),
        pytest.param("1 XB", "unknown unit 'XB'", id="bad-unit"),
    ],
)
def test_parse_data_size_invalid(text, message):
    """
    Text that is not a data size is rejected with a message, instead of a
    bare ``ValueError``.
    """
    with pytest.raises(ValueError, match=message):
        utils.parse_data_size(text)


@pytest.mark.parametrize(
    "size", [0, 1, 1023, 1024, 3_600_000, 1024**3 + 12345, 7 * 1024**5]
)
def test_parse_and_repr_data_size_round_trip(size):
    """
    Parsing the displayed size gives back the size within the rounding error
    of the display (half a unit of the last shown digit).
    """
    text = utils.repr_data_size(size)
    unit = text.split(" ")[1]
    max_error = 0.005 * 1024 ** list(utils.MAGNITUDE_OF_DATA.values()).index(unit)
    assert abs(utils.parse_data_size(text) - size) <= max_error + 1


# ------------------------------------------------------------------------------
# grouper_list
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "items, n, expected",
    [
        pytest.param(
            range(10), 3, [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]], id="remainder"
        ),
        pytest.param(range(9), 3, [[0, 1, 2], [3, 4, 5], [6, 7, 8]], id="exact"),
        pytest.param(range(2), 3, [[0, 1]], id="fewer-than-n"),
        pytest.param(range(3), 1, [[0], [1], [2]], id="n-1"),
        pytest.param([], 3, [], id="empty"),
    ],
)
def test_grouper_list(items, n, expected):
    """
    Items are grouped into lists of ``n``; the last list holds the rest and
    no empty list is produced.
    """
    assert list(utils.grouper_list(items, n)) == expected


def test_grouper_list_consumes_iterator_once():
    """
    A one-shot iterator (e.g. a paginator) is consumed exactly once, in order.
    """
    iterator = iter(range(5))
    assert list(utils.grouper_list(iterator, 2)) == [[0, 1], [2, 3], [4]]
    assert list(iterator) == []


@pytest.mark.parametrize("n", [0, -1])
def test_grouper_list_invalid_n(n):
    """
    ``n`` below 1 is rejected immediately, at call time, instead of silently
    returning everything as one list.
    """
    with pytest.raises(ValueError, match="at least 1"):
        utils.grouper_list(range(5), n)


if __name__ == "__main__":
    run_cov_test(
        __file__,
        "s3pathlib.utils",
        preview=False,
    )

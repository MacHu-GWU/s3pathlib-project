# -*- coding: utf-8 -*-

"""
Each validator is tested in the same order:

1. valid inputs, including the boundaries;
2. invalid inputs, one case per rule (every ``raise`` is triggered);
3. the error contract (exception type and message).
"""

import subprocess
import sys

import pytest

from s3pathlib.api import validate_s3_bucket
from s3pathlib.api import validate_s3_key
from s3pathlib.api import validate_s3_uri
from s3pathlib.api import validate_s3_arn
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test

KEY_1024_BYTES = "中" * 341 + "a"  # 341 * 3 + 1 = 1024 bytes
KEY_1025_BYTES = "中" * 341 + "ab"


# ------------------------------------------------------------------------------
# validate_s3_bucket
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bucket",
    [
        pytest.param("abc", id="min-length-3"),
        pytest.param("a" * 63, id="max-length-63"),
        pytest.param("my-bucket.data-2024", id="dots-and-hyphens"),
        pytest.param("1.2.3", id="ip-like-3-parts"),
        pytest.param("999.1.1.1", id="ip-like-out-of-range"),
        pytest.param("1.2.3.4.5", id="ip-like-5-parts"),
        pytest.param("www.example.com.data", id="four-labels-not-numeric"),
        pytest.param("my-ap-hrzrlukc5m36ft7okagglf3gmwlu-s3alias", id="access-point-alias"),
        pytest.param("mybucket--usw2-az1--x-s3", id="directory-bucket"),
    ],
)
def test_validate_s3_bucket_valid(bucket):
    """
    Names that S3 APIs accept as a bucket pass, including names that only
    look like an IP address, access point aliases and directory buckets.
    """
    validate_s3_bucket(bucket)


@pytest.mark.parametrize(
    "bucket, message",
    [
        pytest.param("ab", "between 3 and 63", id="too-short"),
        pytest.param("a" * 64, "between 3 and 63", id="too-long"),
        pytest.param("My-Bucket", "invalid char found", id="uppercase"),
        pytest.param("my_bucket", "invalid char found", id="underscore"),
        pytest.param("bucket@example.com", "invalid char found", id="at-sign"),
        pytest.param("-my-bucket", "begin and end", id="starts-with-hyphen"),
        pytest.param(".my-bucket", "begin and end", id="starts-with-dot"),
        pytest.param("my-bucket-", "begin and end", id="ends-with-hyphen"),
        pytest.param("192.168.5.4", "IP address", id="ip-address"),
        pytest.param("xn--my-bucket", "xn--", id="xn-prefix"),
    ],
)
def test_validate_s3_bucket_invalid(bucket, message):
    """
    Each bucket naming rule rejects its violation with a message that names
    the rule.
    """
    with pytest.raises(S3ValidationError, match=message):
        validate_s3_bucket(bucket)


def test_validate_s3_bucket_error_names_bad_chars():
    """
    The charset error lists the offending characters, so the user knows what
    to fix.
    """
    with pytest.raises(S3ValidationError) as e:
        validate_s3_bucket("my_bucket")
    assert "'_'" in str(e.value)


def test_validate_s3_bucket_ip_check_without_assert():
    """
    The IP address check gives the same result under ``python -O``, which
    strips ``assert`` statements (2.x relied on them and rejected valid names
    such as ``1.2.3``).
    """
    code = (
        "from s3pathlib.validate import validate_s3_bucket\n"
        "for b in ['1.2.3', '999.1.1.1', '1.2.3.4.5']:\n"
        "    validate_s3_bucket(b)\n"
        "try:\n"
        "    validate_s3_bucket('192.168.5.4')\n"
        "except ValueError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('IP address was accepted')\n"
    )
    result = subprocess.run(
        [sys.executable, "-O", "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


# ------------------------------------------------------------------------------
# validate_s3_key
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "key",
    [
        pytest.param("", id="empty-is-bucket-root"),
        pytest.param("folder/file.txt", id="file"),
        pytest.param("folder/", id="folder"),
        pytest.param("数据/报表.csv", id="non-ascii"),
        pytest.param("a~b%c#d{e}f^g[h]i`j|k\\l<m>n\"o", id="avoid-but-legal-chars"),
        pytest.param("a" * 1024, id="max-1024-ascii-bytes"),
        pytest.param(KEY_1024_BYTES, id="max-1024-utf8-bytes"),
    ],
)
def test_validate_s3_key_valid(key):
    """
    Any UTF-8 key up to 1024 bytes passes; characters that S3 only advises to
    avoid are still legal.
    """
    validate_s3_key(key)


@pytest.mark.parametrize(
    "key, message",
    [
        pytest.param("a" * 1025, "at most 1024 bytes", id="1025-ascii-bytes"),
        pytest.param(KEY_1025_BYTES, "at most 1024 bytes", id="1025-utf8-bytes"),
        pytest.param("a\ud800b", "not valid UTF-8", id="lone-surrogate"),
    ],
)
def test_validate_s3_key_invalid(key, message):
    """
    A key over 1024 UTF-8 bytes, or one that cannot be encoded as UTF-8, is
    rejected. The limit counts bytes, not characters.
    """
    with pytest.raises(S3ValidationError, match=message):
        validate_s3_key(key)


def test_validate_s3_key_error_reports_byte_count():
    """
    The length error reports the actual byte count, which differs from the
    character count for non-ASCII keys.
    """
    with pytest.raises(S3ValidationError) as e:
        validate_s3_key(KEY_1025_BYTES)
    assert "got 1025 bytes" in str(e.value)


# ------------------------------------------------------------------------------
# validate_s3_uri
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "uri",
    [
        pytest.param("s3://my-bucket", id="bucket-no-slash"),
        pytest.param("s3://my-bucket/", id="bucket"),
        pytest.param("s3://my-bucket/folder/", id="folder"),
        pytest.param("s3://my-bucket/folder/file.txt", id="file"),
        pytest.param("s3://my-bucket/数据.csv", id="non-ascii-key"),
    ],
)
def test_validate_s3_uri_valid(uri):
    """
    Bucket, folder and file URIs pass, with or without the trailing slash
    after the bucket.
    """
    validate_s3_uri(uri)


@pytest.mark.parametrize(
    "uri, message",
    [
        pytest.param("my-bucket/key", "must starts with 's3://'", id="no-scheme"),
        pytest.param("s3:/my-bucket/key", "must starts with 's3://'", id="bad-scheme"),
        pytest.param("s3://", "between 3 and 63", id="empty-bucket"),
        pytest.param("s3://My_Bucket/key", "invalid char found", id="bad-bucket"),
        pytest.param("s3://my-bucket/" + "a" * 1025, "at most 1024 bytes", id="bad-key"),
    ],
)
def test_validate_s3_uri_invalid(uri, message):
    """
    The scheme is checked here; the bucket and key are delegated to
    ``validate_s3_bucket`` and ``validate_s3_key``, so their messages surface.
    """
    with pytest.raises(S3ValidationError, match=message):
        validate_s3_uri(uri)


# ------------------------------------------------------------------------------
# validate_s3_arn
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "arn",
    [
        pytest.param("arn:aws:s3:::my-bucket", id="bucket"),
        pytest.param("arn:aws:s3:::my-bucket/", id="bucket-with-slash"),
        pytest.param("arn:aws:s3:::my-bucket/folder/", id="folder"),
        pytest.param("arn:aws:s3:::my-bucket/folder/file.txt", id="file"),
        pytest.param("arn:aws:s3:::my-bucket/数据.csv", id="non-ascii-key"),
        pytest.param("arn:aws-cn:s3:::my-bucket/folder/file.txt", id="china-partition"),
        pytest.param("arn:aws-us-gov:s3:::my-bucket/folder/file.txt", id="us-gov-partition"),
    ],
)
def test_validate_s3_arn_valid(arn):
    """
    Bucket, folder and file ARNs pass in every supported partition
    (``aws``, ``aws-cn``, ``aws-us-gov``).
    """
    validate_s3_arn(arn)


@pytest.mark.parametrize(
    "arn, message",
    [
        pytest.param("my-bucket/key", "partition is one of", id="no-prefix"),
        pytest.param("s3://my-bucket", "partition is one of", id="uri-not-arn"),
        pytest.param("arn:aws-iso:s3:::my-bucket", "partition is one of", id="unsupported-partition"),
        pytest.param("arn:aws:iam::my-bucket", "partition is one of", id="not-s3-service"),
        pytest.param("arn:aws:s3:::b", "between 3 and 63", id="bad-bucket"),
        pytest.param("arn:aws:s3:::my-bucket/" + "a" * 1025, "at most 1024 bytes", id="bad-key"),
    ],
)
def test_validate_s3_arn_invalid(arn, message):
    """
    The ARN prefix (partition and service) is checked first; the bucket and
    key are delegated to ``validate_s3_bucket`` and ``validate_s3_key``.
    """
    with pytest.raises(S3ValidationError, match=message):
        validate_s3_arn(arn)


# ------------------------------------------------------------------------------
# Error contract shared by all validators
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "validator, value",
    [
        (validate_s3_bucket, "ab"),
        (validate_s3_key, "a" * 1025),
        (validate_s3_uri, "my-bucket/key"),
        (validate_s3_arn, "my-bucket/key"),
    ],
)
def test_validator_error_is_value_error(validator, value):
    """
    Validation errors are ``S3ValidationError`` and still ``ValueError``, so
    2.x ``except ValueError`` code keeps working.
    """
    with pytest.raises(ValueError) as e:
        validator(value)
    assert type(e.value) is S3ValidationError


if __name__ == "__main__":
    run_cov_test(__file__, "s3pathlib.validate", preview=False)

# -*- coding: utf-8 -*-

import pytest
import os
from s3pathlib import utils
from s3pathlib.constants import AwsPartitionEnum
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test

dir_here = os.path.dirname(os.path.abspath(__file__))
dir_project_root = os.path.dirname(dir_here)


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("s3://my-bucket/my-prefix/my-file.zip", ("my-bucket", "my-prefix/my-file.zip")),
        ("s3://my-bucket/my-prefix/", ("my-bucket", "my-prefix/")),
        ("s3://my-bucket/", ("my-bucket", "")),
        ("s3://my-bucket", ("my-bucket", "")),
        ("s3://My_Legacy_Bucket/a:b.txt", ("My_Legacy_Bucket", "a:b.txt")),
    ],
)
def test_split_s3_uri(uri, expected):
    """
    An S3 URI splits into bucket and key. Only the format is checked, so a
    legacy bucket name and a ``:`` in the key are fine.
    """
    assert utils.split_s3_uri(uri) == expected


@pytest.mark.parametrize(
    "uri, message",
    [
        ("my-bucket/key", "must start with 's3://'"),
        ("s3:/my-bucket/key", "must start with 's3://'"),
        ("https://my-bucket/key", "must start with 's3://'"),
        ("s3://", "bucket is empty"),
        ("s3:///key", "bucket is empty"),
        ("s3://a:b/key", "contains ':'"),
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
    "arn, expected",
    [
        ("arn:aws:s3:::bucket", ("aws", "bucket", "")),
        ("arn:aws:s3:::bucket/", ("aws", "bucket", "")),
        ("arn:aws:s3:::bucket/folder/", ("aws", "bucket", "folder/")),
        ("arn:aws-cn:s3:::bucket/folder/file.txt", ("aws-cn", "bucket", "folder/file.txt")),
        ("arn:aws-us-gov:s3:::bucket/file.txt", ("aws-us-gov", "bucket", "file.txt")),
        ("arn:aws-eusc:s3:::bucket/file.txt", ("aws-eusc", "bucket", "file.txt")),
        ("arn:aws:s3:::My_Legacy_Bucket/a:b.txt", ("aws", "My_Legacy_Bucket", "a:b.txt")),
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
        "s3://bucket/key",
        "arn:aws-iso:s3:::bucket/key",
        "arn:aws:iam::bucket/key",
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
        ("arn:aws:s3:::", "bucket is empty"),
        ("arn:aws:s3:::/key", "bucket is empty"),
        ("arn:aws:s3:::a:b/key", "contains ':'"),
    ],
)
def test_split_s3_arn_bad_bucket_part(arn, message):
    """
    A well formed ARN prefix with an empty or impossible bucket part is
    rejected.
    """
    with pytest.raises(S3ValidationError, match=message):
        utils.split_s3_arn(arn)


def test_join_s3_uri():
    bucket = "my-bucket"
    key = "my-prefix/my-file.zip"
    s3_uri = utils.join_s3_uri(bucket, key)
    assert s3_uri == "s3://my-bucket/my-prefix/my-file.zip"


def test_split_parts():
    assert utils.split_parts("a/b/c") == ["a", "b", "c"]
    assert utils.split_parts("//a//b//c//") == ["a", "b", "c"]
    assert utils.split_parts("") == []
    assert utils.split_parts("////") == []


def test_s3_key_smart_join():
    assert utils.smart_join_s3_key(
        parts=["/a/", "b/", "/c"],
        is_dir=True,
    ) == "a/b/c/"

    assert utils.smart_join_s3_key(
        parts=["/a/", "b/", "/c"],
        is_dir=False,
    ) == "a/b/c"

    assert utils.smart_join_s3_key(
        parts=["//a//b//c//"],
        is_dir=True,
    ) == "a/b/c/"

    assert utils.smart_join_s3_key(
        parts=["//a//b//c//"],
        is_dir=False,
    ) == "a/b/c"


def test_make_s3_console_url():
    # object
    url = utils.make_s3_console_url("my-bucket", "my-file.zip")
    assert "object" in url

    # folder
    url = utils.make_s3_console_url("my-bucket", "my-folder/")
    assert "bucket" in url

    # uri
    url = utils.make_s3_console_url(s3_uri="s3://my-bucket/my-folder/data.json")
    assert url == "https://console.aws.amazon.com/s3/object/my-bucket?prefix=my-folder/data.json"

    # s3 bucket root
    url = utils.make_s3_console_url(s3_uri="s3://my-bucket/")
    assert url == "https://console.aws.amazon.com/s3/buckets/my-bucket?tab=objects"

    # version id
    url = utils.make_s3_console_url(s3_uri="s3://my-bucket/my-folder/my-file.zip", version_id="v123")
    assert url == "https://console.aws.amazon.com/s3/object/my-bucket?prefix=my-folder/my-file.zip&versionId=v123"

    # us gov cloud
    url = utils.make_s3_console_url(
        s3_uri="s3://my-bucket/my-folder/data.json", is_us_gov_cloud=True
    )
    assert url == "https://console.amazonaws-us-gov.com/s3/object/my-bucket?prefix=my-folder/data.json"

    with pytest.raises(ValueError):
        utils.make_s3_console_url(bucket="")

    with pytest.raises(ValueError):
        utils.make_s3_console_url(prefix="", s3_uri="")


def test_ensure_s3_object():
    utils.ensure_s3_object("path/to/key")
    with pytest.raises(Exception):
        utils.ensure_s3_object("path/to/dir/")


def test_ensure_s3_dir():
    utils.ensure_s3_dir("path/to/dir/")
    with pytest.raises(Exception):
        utils.ensure_s3_dir("path/to/key")


def test_repr_data_size():
    assert utils.repr_data_size(3600000) == "3.43 MB"


def test_parse_data_size():
    assert utils.parse_data_size("3.43 MB") == 3596615
    assert utils.parse_data_size("2_512.4 MB") == 2634442342
    assert utils.parse_data_size("2,512.4 MB") == 2634442342


if __name__ == "__main__":
    run_cov_test(__file__, "s3pathlib.utils", preview=False)

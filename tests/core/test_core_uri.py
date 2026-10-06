# -*- coding: utf-8 -*-

import pytest
from s3pathlib.core import S3Path
from s3pathlib.constants import AwsPartitionEnum
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test


class TestUriAPIMixin:
    def test_uri_properties(self):
        # s3 object
        p = S3Path("bucket", "folder", "file.txt")
        assert p.bucket == "bucket"
        assert p.key == "folder/file.txt"
        assert p.uri == "s3://bucket/folder/file.txt"
        assert p.arn == "arn:aws:s3:::bucket/folder/file.txt"
        assert (
            p.console_url
            == "https://console.aws.amazon.com/s3/object/bucket?prefix=folder/file.txt"
        )
        assert (
            p.get_regional_console_url("us-east-1")
            == "https://us-east-1.console.aws.amazon.com/s3/object/bucket?region=us-east-1&prefix=folder/file.txt"
        )
        assert (
            p.us_gov_cloud_console_url
            == "https://console.amazonaws-us-gov.com/s3/object/bucket?prefix=folder/file.txt"
        )
        assert (
            p.get_regional_us_gov_cloud_console_url("us-gov-east-1")
            == "https://us-gov-east-1.console.amazonaws-us-gov.com/s3/object/bucket?region=us-gov-east-1&prefix=folder/file.txt"
        )
        assert (
            p.s3_select_console_url
            == "https://console.aws.amazon.com/s3/buckets/bucket/object/select?prefix=folder/file.txt"
        )
        assert (
            p.get_regional_s3_select_console_url("us-east-1")
            == "https://us-east-1.console.aws.amazon.com/s3/buckets/bucket/object/select?region=us-east-1&prefix=folder/file.txt"
        )
        assert (
            p.s3_select_us_gov_cloud_console_url
            == "https://console.amazonaws-us-gov.com/s3/buckets/bucket/object/select?prefix=folder/file.txt"
        )
        assert (
            p.get_regional_s3_select_us_gov_cloud_console_url("us-gov-east-1")
            == "https://us-gov-east-1.console.amazonaws-us-gov.com/s3/buckets/bucket/object/select?region=us-gov-east-1&prefix=folder/file.txt"
        )

        # s3 directory
        p = S3Path("bucket", "folder/")
        assert p.bucket == "bucket"
        assert p.key == "folder/"
        assert p.uri == "s3://bucket/folder/"
        assert p.arn == "arn:aws:s3:::bucket/folder/"
        assert (
            p.console_url
            == "https://console.aws.amazon.com/s3/buckets/bucket?prefix=folder/"
        )

        with pytest.raises(TypeError):
            assert p.s3_select_console_url
        with pytest.raises(TypeError):
            assert p.s3_select_us_gov_cloud_console_url

        # s3 bucket
        p = S3Path("bucket")
        assert p.bucket == "bucket"
        assert p.key == ""
        assert p.uri == "s3://bucket/"
        assert p.arn == "arn:aws:s3:::bucket"
        assert (
            p.console_url
            == "https://console.aws.amazon.com/s3/buckets/bucket?tab=objects"
        )

        with pytest.raises(TypeError):
            assert p.s3_select_console_url
        with pytest.raises(TypeError):
            assert p.s3_select_us_gov_cloud_console_url

        # void path
        p = S3Path()
        assert p.bucket is None
        assert p.key == ""
        assert p.uri is None
        assert p.arn is None
        assert p.console_url is None
        assert p.us_gov_cloud_console_url is None

        with pytest.raises(TypeError):
            assert p.s3_select_console_url
        with pytest.raises(TypeError):
            assert p.s3_select_us_gov_cloud_console_url

    def test_from_s3_uri(self):
        p = S3Path.from_s3_uri("s3://bucket/")
        assert p._bucket == "bucket"
        assert p.parts == []
        assert p._is_dir is True

        p = S3Path.from_s3_uri("s3://bucket/folder/")
        assert p._bucket == "bucket"
        assert p.parts == [
            "folder",
        ]
        assert p._is_dir is True

        p = S3Path.from_s3_uri("s3://bucket/folder/file.txt")
        assert p._bucket == "bucket"
        assert p.parts == ["folder", "file.txt"]
        assert p._is_dir is False

    def test_from_s3_arn(self):
        p = S3Path.from_s3_arn("arn:aws:s3:::bucket")
        assert p._bucket == "bucket"
        assert p.parts == []
        assert p._is_dir is True

        p = S3Path.from_s3_arn("arn:aws:s3:::bucket/")
        assert p._bucket == "bucket"
        assert p.parts == []
        assert p._is_dir is True

        p = S3Path.from_s3_arn("arn:aws:s3:::bucket/folder/")
        assert p._bucket == "bucket"
        assert p.parts == [
            "folder",
        ]
        assert p._is_dir is True

        p = S3Path.from_s3_arn("arn:aws:s3:::bucket/folder/file.txt")
        assert p._bucket == "bucket"
        assert p.parts == ["folder", "file.txt"]
        assert p._is_dir is False

    @pytest.mark.parametrize(
        "partition, arn",
        [
            ("aws", "arn:aws:s3:::bucket/folder/file.txt"),
            ("aws-cn", "arn:aws-cn:s3:::bucket/folder/file.txt"),
            ("aws-us-gov", "arn:aws-us-gov:s3:::bucket/folder/file.txt"),
            (AwsPartitionEnum.aws_cn, "arn:aws-cn:s3:::bucket/folder/file.txt"),
        ],
    )
    def test_get_arn_partitions(self, partition, arn):
        """
        ``get_arn`` builds the ARN in the given partition, accepting either a
        plain string or an ``AwsPartitionEnum`` member.
        """
        assert S3Path("bucket", "folder", "file.txt").get_arn(partition) == arn

    def test_get_arn_bucket_and_void(self):
        """
        A bucket has no key part; a void path (no bucket) has no ARN.
        """
        assert S3Path("bucket").get_arn("aws-cn") == "arn:aws-cn:s3:::bucket"
        assert S3Path().get_arn("aws-cn") is None

    def test_get_arn_default_matches_arn_property(self):
        """
        ``arn`` stays the ``aws`` partition ARN, same as ``get_arn()``.
        """
        p = S3Path("bucket", "folder/")
        assert p.arn == p.get_arn() == "arn:aws:s3:::bucket/folder/"

    def test_get_arn_invalid_partition(self):
        """
        An unsupported partition is rejected instead of building a bad ARN.
        """
        with pytest.raises(ValueError):
            S3Path("bucket", "file.txt").get_arn("aws-iso")

    @pytest.mark.parametrize("partition", ["aws-cn", "aws-us-gov"])
    def test_from_s3_arn_partitions(self, partition):
        """
        ARNs from other partitions parse to the same bucket and key; the
        partition is not stored on the path.
        """
        p = S3Path.from_s3_arn(f"arn:{partition}:s3:::bucket/folder/file.txt")
        assert p == S3Path("s3://bucket/folder/file.txt")
        assert p.get_arn(partition) == f"arn:{partition}:s3:::bucket/folder/file.txt"

    def test_from_s3_uri_and_arn_skip_naming_rules(self):
        """
        Only the format is checked, not bucket naming rules, so a legacy
        bucket (uppercase, underscore), which S3 still serves, can be used.
        """
        expected = S3Path("My_Legacy_Bucket", "folder", "file.txt")
        assert S3Path.from_s3_uri("s3://My_Legacy_Bucket/folder/file.txt") == expected
        assert S3Path.from_s3_arn("arn:aws:s3:::My_Legacy_Bucket/folder/file.txt") == expected

    @pytest.mark.parametrize(
        "uri",
        ["my-bucket/key", "https://my-bucket/key", "s3://", "arn:aws:s3:::bucket/key"],
    )
    def test_from_s3_uri_invalid_format(self, uri):
        """
        A string that is not an S3 URI is rejected, even if another
        constructor would accept it (e.g. an ARN).
        """
        with pytest.raises(S3ValidationError):
            S3Path.from_s3_uri(uri)

    @pytest.mark.parametrize(
        "arn",
        ["s3://bucket/key", "arn:aws-iso:s3:::bucket/key", "arn:aws:s3:::"],
    )
    def test_from_s3_arn_invalid_format(self, arn):
        """
        A string that is not an S3 ARN of a supported partition is rejected.
        """
        with pytest.raises(S3ValidationError):
            S3Path.from_s3_arn(arn)


if __name__ == "__main__":
    run_cov_test(__file__, module="s3pathlib.core.uri", preview=False)

# -*- coding: utf-8 -*-

"""
Test the URI, ARN and console URL API of ``S3Path``.

Test order:

1. ``bucket`` / ``key`` / ``uri`` / ``arn``, for every kind of path
   (object, directory, bucket root, relative path, void path);
2. ``get_arn`` partitions and its error;
3. ``console_url`` / ``get_console_url``, including the version id loaded
   from S3 (the only part that needs moto);
4. ``from_s3_uri`` / ``from_s3_arn`` and their errors;
5. the attributes can be used as filters.
"""

import pytest

from s3pathlib.api import S3Path
from s3pathlib.constants import AwsPartitionEnum
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock import BaseTest

OBJECT = S3Path("bucket", "folder", "file.txt")
DIRECTORY = S3Path("bucket", "folder/")
BUCKET = S3Path("bucket")
RELPATH_FILE = OBJECT.relative_to(BUCKET)
RELPATH_DIR = DIRECTORY.relative_to(BUCKET)
VOID = S3Path()

ALL_KINDS = [
    pytest.param(OBJECT, id="object"),
    pytest.param(DIRECTORY, id="directory"),
    pytest.param(BUCKET, id="bucket"),
    pytest.param(RELPATH_FILE, id="relpath-file"),
    pytest.param(RELPATH_DIR, id="relpath-dir"),
    pytest.param(VOID, id="void"),
]


class UriAPIMixin(BaseTest):
    module = "core.uri"

    # --------------------------------------------------------------------------
    # 1. bucket / key / uri / arn
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, bucket, key, uri, arn",
        [
            pytest.param(
                OBJECT,
                "bucket",
                "folder/file.txt",
                "s3://bucket/folder/file.txt",
                "arn:aws:s3:::bucket/folder/file.txt",
                id="object",
            ),
            pytest.param(
                DIRECTORY,
                "bucket",
                "folder/",
                "s3://bucket/folder/",
                "arn:aws:s3:::bucket/folder/",
                id="directory",
            ),
            pytest.param(
                BUCKET,
                "bucket",
                "",
                "s3://bucket/",
                "arn:aws:s3:::bucket",
                id="bucket",
            ),
            pytest.param(
                RELPATH_FILE, None, "folder/file.txt", None, None, id="relpath-file"
            ),
            pytest.param(RELPATH_DIR, None, "folder/", None, None, id="relpath-dir"),
            pytest.param(VOID, None, "", None, None, id="void"),
        ],
    )
    def test_uri_attributes(self, p, bucket, key, uri, arn):
        """
        A directory key ends with ``/``; a path without bucket has a key but
        no URI or ARN.
        """
        assert p.bucket == bucket
        assert p.key == key
        assert p.uri == uri
        assert p.arn == arn

    def test_uri_attributes_keep_special_chars(self):
        """
        URI and ARN keep the key as it is: no URL encoding, and ``?`` is not
        a query string, because these are all valid characters in an S3 key.
        """
        p = S3Path("bucket", "a b/c?versionId=1&x#y.txt")
        assert p.key == "a b/c?versionId=1&x#y.txt"
        assert p.uri == "s3://bucket/a b/c?versionId=1&x#y.txt"
        assert p.arn == "arn:aws:s3:::bucket/a b/c?versionId=1&x#y.txt"

    # --------------------------------------------------------------------------
    # 2. get_arn
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "partition, arn",
        [
            pytest.param("aws", "arn:aws:s3:::bucket/folder/file.txt", id="aws"),
            pytest.param("aws-cn", "arn:aws-cn:s3:::bucket/folder/file.txt", id="aws-cn"),
            pytest.param(
                "aws-us-gov", "arn:aws-us-gov:s3:::bucket/folder/file.txt", id="aws-us-gov"
            ),
            pytest.param(
                "aws-eusc", "arn:aws-eusc:s3:::bucket/folder/file.txt", id="aws-eusc"
            ),
            pytest.param(
                AwsPartitionEnum.aws_cn,
                "arn:aws-cn:s3:::bucket/folder/file.txt",
                id="enum-member",
            ),
        ],
    )
    def test_get_arn_partitions(self, partition, arn):
        """
        ``get_arn`` builds the ARN in the given partition, accepting either a
        plain string or an ``AwsPartitionEnum`` member.
        """
        assert OBJECT.get_arn(partition) == arn

    @pytest.mark.parametrize(
        "p, arn",
        [
            pytest.param(BUCKET, "arn:aws-cn:s3:::bucket", id="bucket"),
            pytest.param(RELPATH_FILE, None, id="relpath"),
            pytest.param(VOID, None, id="void"),
        ],
    )
    def test_get_arn_without_key_or_bucket(self, p, arn):
        """
        A bucket has no key part; a path without bucket has no ARN.
        """
        assert p.get_arn("aws-cn") == arn

    @pytest.mark.parametrize("p", ALL_KINDS)
    def test_get_arn_default_matches_arn_property(self, p):
        """
        ``arn`` stays the ``aws`` partition ARN, same as ``get_arn()``.
        """
        assert p.arn == p.get_arn()

    def test_get_arn_invalid_partition(self):
        """
        An unsupported partition is rejected instead of building a bad ARN.
        """
        with pytest.raises(
            S3ValidationError, match="partition must be one of .*, got 'aws-iso'"
        ):
            OBJECT.get_arn("aws-iso")

    # --------------------------------------------------------------------------
    # 3. console_url / get_console_url
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, url",
        [
            pytest.param(
                OBJECT,
                "https://console.aws.amazon.com/s3/object/bucket?prefix=folder/file.txt",
                id="object",
            ),
            pytest.param(
                DIRECTORY,
                "https://console.aws.amazon.com/s3/buckets/bucket?prefix=folder/",
                id="directory",
            ),
            pytest.param(
                BUCKET,
                "https://console.aws.amazon.com/s3/buckets/bucket?tab=objects",
                id="bucket",
            ),
            pytest.param(RELPATH_FILE, None, id="relpath"),
            pytest.param(VOID, None, id="void"),
        ],
    )
    def test_console_url(self, p, url):
        """
        Object, directory and bucket open different console pages; a path
        without bucket has no console url.
        """
        assert p.console_url == url

    @pytest.mark.parametrize("p", ALL_KINDS)
    def test_console_url_matches_get_console_url(self, p):
        """
        ``console_url`` is the global console of the ``aws`` partition.
        """
        assert p.console_url == p.get_console_url()

    @pytest.mark.parametrize(
        "kwargs, url",
        [
            pytest.param(
                dict(region="us-east-1"),
                "https://us-east-1.console.aws.amazon.com/s3/object/bucket?region=us-east-1&prefix=folder/file.txt",
                id="regional",
            ),
            pytest.param(
                dict(partition="aws-us-gov"),
                "https://console.amazonaws-us-gov.com/s3/object/bucket?prefix=folder/file.txt",
                id="us-gov",
            ),
            pytest.param(
                dict(region="us-gov-east-1", partition="aws-us-gov"),
                "https://us-gov-east-1.console.amazonaws-us-gov.com/s3/object/bucket?region=us-gov-east-1&prefix=folder/file.txt",
                id="us-gov-regional",
            ),
            pytest.param(
                dict(region="cn-north-1", partition="aws-cn"),
                "https://cn-north-1.console.amazonaws.cn/s3/object/bucket?region=cn-north-1&prefix=folder/file.txt",
                id="china-regional",
            ),
            pytest.param(
                dict(partition=AwsPartitionEnum.aws_eusc),
                "https://console.amazonaws-eusc.eu/s3/object/bucket?prefix=folder/file.txt",
                id="eusc-enum-member",
            ),
        ],
    )
    def test_get_console_url_region_and_partition(self, kwargs, url):
        """
        ``region`` and ``partition`` pick the console host; this replaces the
        removed ``get_regional_*`` and ``*us_gov_cloud*`` methods.
        """
        assert OBJECT.get_console_url(**kwargs) == url

    @pytest.mark.parametrize("p", [RELPATH_FILE, VOID])
    def test_get_console_url_without_bucket(self, p):
        """
        A path without bucket has no console url in any region or partition.
        """
        assert p.get_console_url(region="cn-north-1", partition="aws-cn") is None

    def test_get_console_url_encodes_key(self):
        """
        Unlike ``uri``, the console url encodes the key, so the special
        characters can not break the query string.
        """
        p = S3Path("bucket", "a b/c?versionId=1&x#y.txt")
        assert p.console_url == (
            "https://console.aws.amazon.com/s3/object/bucket"
            "?prefix=a%20b/c%3FversionId%3D1%26x%23y.txt"
        )

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            pytest.param(
                dict(partition="aws-iso"),
                "partition must be one of .*, got 'aws-iso'",
                id="unsupported-partition",
            ),
            pytest.param(
                dict(region=""), "aws_region must not be empty", id="empty-region"
            ),
        ],
    )
    def test_get_console_url_invalid_args(self, kwargs, message):
        with pytest.raises(S3ValidationError, match=message):
            OBJECT.get_console_url(**kwargs)

    def test_console_url_with_loaded_version_id(self):
        """
        Once the metadata is loaded from a versioned bucket, the console url
        opens that exact version.
        """
        p = self.s3dir_root_with_versioning.joinpath("console-url", "file.txt")
        res = self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"hello")
        version_id = res["VersionId"]

        p.head_object()
        assert p.console_url == (
            f"https://console.aws.amazon.com/s3/object/{p.bucket}"
            f"?prefix={p.key}&versionId={version_id}"
        )
        assert p.get_console_url(region="us-east-1").endswith(
            f"&versionId={version_id}"
        )

    def test_console_url_does_not_call_aws(self):
        """
        Without loaded metadata there is no version id: the console url is
        built locally, it never calls ``head_object``.
        """
        p = self.s3dir_root_with_versioning.joinpath("console-url-no-meta", "file.txt")
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"hello")
        assert "versionId" not in p.console_url
        assert p.response is None

    def test_console_url_without_versioning(self):
        """
        An object in a bucket without versioning has no version id to open.
        """
        p = self.s3dir_root.joinpath("console-url", "file.txt")
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"hello")
        p.head_object()
        assert "versionId" not in p.console_url

    # --------------------------------------------------------------------------
    # 4. from_s3_uri / from_s3_arn
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "uri, expected",
        [
            pytest.param("s3://bucket", BUCKET, id="bucket-no-slash"),
            pytest.param("s3://bucket/", BUCKET, id="bucket"),
            pytest.param("s3://bucket/folder/", DIRECTORY, id="directory"),
            pytest.param("s3://bucket/folder/file.txt", OBJECT, id="object"),
        ],
    )
    def test_from_s3_uri(self, uri, expected):
        p = S3Path.from_s3_uri(uri)
        assert p == expected
        assert p.uri == expected.uri

    @pytest.mark.parametrize(
        "arn, expected",
        [
            pytest.param("arn:aws:s3:::bucket", BUCKET, id="bucket"),
            pytest.param("arn:aws:s3:::bucket/", BUCKET, id="bucket-slash"),
            pytest.param("arn:aws:s3:::bucket/folder/", DIRECTORY, id="directory"),
            pytest.param("arn:aws:s3:::bucket/folder/file.txt", OBJECT, id="object"),
        ],
    )
    def test_from_s3_arn(self, arn, expected):
        p = S3Path.from_s3_arn(arn)
        assert p == expected
        assert p.is_dir() is expected.is_dir()

    @pytest.mark.parametrize("partition", ["aws-cn", "aws-us-gov", "aws-eusc"])
    def test_from_s3_arn_partitions(self, partition):
        """
        ARNs from other partitions parse to the same bucket and key; the
        partition is not stored on the path.
        """
        arn = f"arn:{partition}:s3:::bucket/folder/file.txt"
        p = S3Path.from_s3_arn(arn)
        assert p == OBJECT
        assert p.arn == "arn:aws:s3:::bucket/folder/file.txt"
        assert p.get_arn(partition) == arn

    @pytest.mark.parametrize("p", [OBJECT, DIRECTORY, BUCKET])
    def test_uri_and_arn_round_trip(self, p):
        """
        ``from_s3_uri(p.uri)`` and ``from_s3_arn(p.get_arn(...))`` give back
        the same path.
        """
        assert S3Path.from_s3_uri(p.uri) == p
        for partition in AwsPartitionEnum:
            assert S3Path.from_s3_arn(p.get_arn(partition)) == p

    def test_from_s3_uri_and_arn_skip_naming_rules(self):
        """
        Only the format is checked, not bucket naming rules, so a legacy
        bucket (uppercase, underscore), which S3 still serves, can be used.
        """
        expected = S3Path("My_Legacy_Bucket", "folder", "file.txt")
        assert S3Path.from_s3_uri("s3://My_Legacy_Bucket/folder/file.txt") == expected
        assert (
            S3Path.from_s3_arn("arn:aws:s3:::My_Legacy_Bucket/folder/file.txt")
            == expected
        )

    @pytest.mark.parametrize(
        "uri, message",
        [
            pytest.param("my-bucket/key", "must start with 's3://'", id="no-scheme"),
            pytest.param("https://my-bucket/key", "must start with 's3://'", id="https"),
            pytest.param("s3://", "bucket is empty", id="no-bucket"),
            pytest.param(
                "arn:aws:s3:::bucket/key", "must start with 's3://'", id="an-arn"
            ),
        ],
    )
    def test_from_s3_uri_invalid_format(self, uri, message):
        """
        A string that is not an S3 URI is rejected, even if the constructor
        would accept it (e.g. an ARN or a bucket name).
        """
        with pytest.raises(S3ValidationError, match=message):
            S3Path.from_s3_uri(uri)

    @pytest.mark.parametrize(
        "arn, message",
        [
            pytest.param(
                "s3://bucket/key", "must start with 'arn:{partition}:s3:::'", id="a-uri"
            ),
            pytest.param(
                "bucket/key",
                "must start with 'arn:{partition}:s3:::'",
                id="bucket-name",
            ),
            pytest.param(
                "arn:aws-iso:s3:::bucket/key",
                "must start with 'arn:{partition}:s3:::'",
                id="unsupported-partition",
            ),
            pytest.param("arn:aws:s3:::", "bucket is empty", id="no-bucket"),
        ],
    )
    def test_from_s3_arn_invalid_format(self, arn, message):
        """
        A string that is not an S3 ARN of a supported partition is rejected.
        """
        with pytest.raises(S3ValidationError, match=message):
            S3Path.from_s3_arn(arn)

    # --------------------------------------------------------------------------
    # 5. filters
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "attr, value",
        [
            pytest.param("bucket", "bucket", id="bucket"),
            pytest.param("key", "folder/file.txt", id="key"),
            pytest.param("uri", "s3://bucket/folder/file.txt", id="uri"),
            pytest.param("arn", "arn:aws:s3:::bucket/folder/file.txt", id="arn"),
        ],
    )
    def test_attributes_are_filterable(self, attr, value):
        """
        ``S3Path.<attr> == value`` builds a filter function for ``IterProxy``.
        """
        filter_ = getattr(S3Path, attr) == value
        assert filter_(OBJECT) is True
        assert filter_(S3Path("other-bucket", "other.txt")) is False


# class Test(UriAPIMixin):
#     use_mock = False


class TestUseMock(UriAPIMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.uri",
        preview=False,
    )

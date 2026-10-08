# -*- coding: utf-8 -*-

import uuid

import pytest

from s3pathlib.core import S3Path
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock import BaseTest


class BucketAPIMixin(BaseTest):
    module = "core.bucket"

    def test(self):
        bucket = uuid.uuid4().hex
        s3bucket = S3Path.from_bucket(bucket)
        assert s3bucket.exists() is False

        s3bucket.create_bucket()
        assert s3bucket.exists() is True

        assert s3bucket.is_versioning_enabled() is False
        s3bucket.put_bucket_versioning(enable_versioning=True)
        assert s3bucket.is_versioning_enabled() is True
        s3bucket.put_bucket_versioning(enable_versioning=False)
        assert s3bucket.is_versioning_enabled() is False
        assert s3bucket.is_versioning_suspended() is True

        s3bucket.delete_bucket()
        assert s3bucket.exists() is False

        s3bucket.create_bucket(region="us-west-1")
        s3bucket.delete_bucket()

        s3bucket_list = S3Path.list_buckets()
        for s3bucket in s3bucket_list:
            _ = s3bucket.last_modified_at

    def test_from_bucket_skips_naming_rules(self):
        """
        ``from_bucket`` accepts a legacy bucket name (uppercase, underscore),
        because S3, not s3pathlib, is the authority on bucket names.
        """
        assert S3Path.from_bucket("My_Legacy_Bucket").uri == "s3://My_Legacy_Bucket/"

    @pytest.mark.parametrize("bucket", ["", "bucket/key", "s3://bucket"])
    def test_from_bucket_invalid_format(self, bucket):
        """
        Only a single bucket name is accepted, not a path or a URI.
        """
        with pytest.raises(S3ValidationError):
            S3Path.from_bucket(bucket)

    def test_list_buckets_with_legacy_bucket(self):
        """
        A legacy bucket returned by ListBuckets does not break
        ``list_buckets()`` (2.x raised on such a name).
        """
        self.s3_client.create_bucket(Bucket="My_Legacy_Bucket")
        try:
            uris = [s3bucket.uri for s3bucket in S3Path.list_buckets()]
            assert "s3://My_Legacy_Bucket/" in uris
        finally:
            self.s3_client.delete_bucket(Bucket="My_Legacy_Bucket")


class TestUseMock(BucketAPIMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.bucket",
        preview=False,
    )

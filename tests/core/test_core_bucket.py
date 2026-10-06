# -*- coding: utf-8 -*-

import uuid

import pytest

from s3pathlib.core import S3Path
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


class TestUseMock(BucketAPIMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(__file__, module="s3pathlib.core.bucket", preview=False)

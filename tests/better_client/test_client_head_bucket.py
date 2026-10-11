# -*- coding: utf-8 -*-

"""
Test ``is_bucket_exists``.

Test order:

1. a bucket that exists (also in another region), a bucket that does not;
2. names: S3, not s3pathlib, decides whether they exist; botocore rejects
   some before sending the request;
3. errors: 404 is recognized by its code, 403 becomes ``S3PermissionDenied``,
   any other error is raised as is (stubbed responses, so both modes test the
   same thing), and a real 403 from a bucket of another account.
"""

import uuid

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.better_client.head_bucket import is_bucket_exists
from s3pathlib.exc import S3PermissionDenied
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only


def random_bucket_name() -> str:
    """
    A valid bucket name that nobody owns.
    """
    return f"s3pathlib-test-tmp-{uuid.uuid4().hex}"


class HeadBucketMixin(BaseTest):
    module = "better_client.head_bucket"

    # --------------------------------------------------------------------------
    # 1. Exists or not
    # --------------------------------------------------------------------------
    def test_existing_bucket(self):
        """
        A bucket you own exists.
        """
        assert is_bucket_exists(self.s3_client, self.bucket) is True

    def test_missing_bucket(self):
        """
        A name nobody owns does not exist (404), without error.
        """
        assert is_bucket_exists(self.s3_client, random_bucket_name()) is False

    def test_bucket_in_other_region(self):
        """
        A bucket in another region is found with a client of this region.
        """
        bucket = random_bucket_name()
        region = "us-west-1"
        s3_client = self.boto_ses.client("s3", region_name=region)
        s3_client.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": region},
        )
        try:
            assert is_bucket_exists(self.s3_client, bucket) is True
        finally:
            # S3 takes a while to forget a deleted bucket, so do not check that
            # it is gone right away
            s3_client.delete_bucket(Bucket=bucket)

    # --------------------------------------------------------------------------
    # 2. Names
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "bucket",
        [
            pytest.param(f"S3PATHLIB_{uuid.uuid4().hex}", id="uppercase-underscore"),
            pytest.param("a" * 64, id="too-long"),
        ],
    )
    def test_name_s3_does_not_find(self, bucket):
        """
        A name that breaks the naming rules is sent to S3, which answers that
        it does not exist; s3pathlib does not check the rules itself.
        """
        assert is_bucket_exists(self.s3_client, bucket) is False

    @pytest.mark.parametrize(
        "bucket",
        [pytest.param("", id="empty"), pytest.param("a b", id="space")],
    )
    def test_name_rejected_by_botocore(self, bucket):
        """
        botocore rejects some names before sending the request.
        """
        with pytest.raises(botocore.exceptions.ParamValidationError):
            is_bucket_exists(self.s3_client, bucket)

    # --------------------------------------------------------------------------
    # 3. Errors
    # --------------------------------------------------------------------------
    def stub_error(self, code: str, status: int) -> tuple:
        """
        A new client whose next head_bucket fails with ``code``.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        stubber.add_client_error(
            "head_bucket",
            service_error_code=code,
            http_status_code=status,
            expected_params={"Bucket": "my-bucket"},
        )
        return s3_client, stubber

    def test_not_found_by_code(self):
        """
        404 is recognized by its code, not by the message: head_bucket has no
        response body, so the message is not reliable.
        """
        s3_client, stubber = self.stub_error("404", 404)
        with stubber:
            assert is_bucket_exists(s3_client, "my-bucket") is False

    def test_forbidden(self):
        """
        403 means the bucket exists but you cannot access it; it raises
        ``S3PermissionDenied`` (a ``PermissionError``) with the reason, and
        keeps the ``ClientError`` as the cause.
        """
        s3_client, stubber = self.stub_error("403", 403)
        with stubber:
            with pytest.raises(S3PermissionDenied) as exc_info:
                is_bucket_exists(s3_client, "my-bucket")
        assert str(exc_info.value) == (
            "no permission to access bucket 's3://my-bucket/': it exists, but "
            "it belongs to another AWS account, or you lack the s3:ListBucket "
            "permission"
        )
        assert isinstance(exc_info.value, PermissionError)
        assert isinstance(exc_info.value.__cause__, botocore.exceptions.ClientError)

    def test_other_error_reraised(self):
        """
        Any other error is raised as is.
        """
        s3_client, stubber = self.stub_error("InternalError", 500)
        with stubber:
            with pytest.raises(botocore.exceptions.ClientError) as exc_info:
                is_bucket_exists(s3_client, "my-bucket")
        assert exc_info.value.response["Error"]["Code"] == "InternalError"

    @real_aws_only("moto does not model buckets of other accounts (it returns 404)")
    def test_forbidden_bucket_of_other_account(self):
        """
        The bucket ``aws`` exists and belongs to another account.
        """
        with pytest.raises(S3PermissionDenied, match="s3://aws/"):
            is_bucket_exists(self.s3_client, "aws")


class TestMock(HeadBucketMixin):
    use_mock = True


class TestRealAws(HeadBucketMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.better_client.head_bucket",
        preview=False,
    )

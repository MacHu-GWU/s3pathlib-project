# -*- coding: utf-8 -*-

"""
Bucket related API.

.. _bsm: https://github.com/aws-samples/boto-session-manager-project
.. _create_bucket: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/create_bucket.html

"""

from __future__ import annotations

import typing as T

from func_args import NOTHING, resolve_kwargs

from ..aws import s3_context
from ..exc import S3ValidationError
from .resolve_s3_client import resolve_s3_client


if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from boto_session_manager.api import BotoSesManager
    from mypy_boto3_s3 import S3Client


class BucketAPIMixin:
    """
    A mixin class that implements the bucket related methods.
    """

    @classmethod
    def from_bucket(
        cls: type[S3Path],
        bucket: str,
    ) -> S3Path:
        """
        Create an S3Path object from a bucket name.

        Only the format is checked (a non-empty name without ``/`` or ``:``),
        not the bucket naming rules, so a legacy bucket name such as
        ``My_Bucket`` works.

        :raises S3ValidationError: if it is not a single bucket name.
        """
        if (not bucket) or ("/" in bucket) or (":" in bucket):
            raise S3ValidationError(f"{bucket!r} is not a bucket name")
        return cls(f"s3://{bucket}/")

    def create_bucket(
        self: S3Path,
        region: str = "us-east-1",
        acl: str = NOTHING,
        grant_full_control: str = NOTHING,
        grant_read: str = NOTHING,
        grant_read_acp: str = NOTHING,
        grant_write: str = NOTHING,
        grant_write_acp: str = NOTHING,
        object_lock_enabled_for_bucket: bool = NOTHING,
        object_ownership: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> dict:
        """
        Create an S3 bucket.
        """
        self.ensure_bucket()
        if region == "us-east-1":
            create_bucket_configuration = NOTHING
        else:
            create_bucket_configuration = dict(LocationConstraint=region)
        s3_client = resolve_s3_client(s3_context, bsm)
        response = s3_client.create_bucket(
            **resolve_kwargs(
                Bucket=self.bucket,
                ACL=acl,
                CreateBucketConfiguration=create_bucket_configuration,
                GrantFullControl=grant_full_control,
                GrantRead=grant_read,
                GrantReadACP=grant_read_acp,
                GrantWrite=grant_write,
                GrantWriteACP=grant_write_acp,
                ObjectLockEnabledForBucket=object_lock_enabled_for_bucket,
                ObjectOwnership=object_ownership,
            ),
        )
        return response

    def delete_bucket(
        self: S3Path,
        expected_bucket_owner: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ):
        """
        Delete an S3 bucket.
        """
        self.ensure_bucket()
        s3_client = resolve_s3_client(s3_context, bsm)
        response = s3_client.delete_bucket(
            **resolve_kwargs(
                Bucket=self.bucket,
                ExpectedBucketOwner=expected_bucket_owner,
            ),
        )
        self.clear_cache()
        return response

    def get_bucket_versioning(
        self: S3Path,
        expected_bucket_owner: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> dict:
        """
        Get the versioning state of an S3 bucket.
        """
        self.ensure_bucket()
        s3_client = resolve_s3_client(s3_context, bsm)
        response = s3_client.get_bucket_versioning(
            **resolve_kwargs(
                Bucket=self.bucket,
                ExpectedBucketOwner=expected_bucket_owner,
            ),
        )
        return response

    def is_versioning_enabled(
        self: S3Path,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> bool:
        """
        Check if the versioning of an S3 bucket is enabled.
        """
        res = self.get_bucket_versioning(bsm=bsm)
        return res.get("Status", "UNKNOWN") == "Enabled"

    def is_versioning_suspended(
        self: S3Path,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> bool:
        """
        Check if the versioning of an S3 bucket is suspended.
        """
        res = self.get_bucket_versioning(bsm=bsm)
        return res.get("Status", "UNKNOWN") == "Suspended"

    def put_bucket_versioning(
        self: S3Path,
        enable_versioning: bool,
        enable_mfa_delete: bool = NOTHING,
        check_sum_algorithm: str = NOTHING,
        mfa: str = NOTHING,
        expected_bucket_owner: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> dict:
        """
        Enable or suspend S3 bucket versioning.
        """
        self.ensure_bucket()
        s3_client = resolve_s3_client(s3_context, bsm)
        if enable_versioning:
            enable_versioning = "Enabled"
        else:
            enable_versioning = "Suspended"
        if enable_mfa_delete is not NOTHING:  # pragma: no cover
            if enable_mfa_delete:
                enable_versioning = "Enabled"
            else:
                enable_versioning = "Disabled"
        versioning_configuration = resolve_kwargs(
            MFADelete=enable_mfa_delete,
            Status=enable_versioning,
        )
        response = s3_client.put_bucket_versioning(
            **resolve_kwargs(
                Bucket=self.bucket,
                ChecksumAlgorithm=check_sum_algorithm,
                VersioningConfiguration=versioning_configuration,
                MFA=mfa,
                ExpectedBucketOwner=expected_bucket_owner,
            ),
        )
        return response

    @classmethod
    def list_buckets(
        cls: type[S3Path],
        bsm: BotoSesManager | S3Client | None = None,
    ) -> list[S3Path]:
        """
        List all S3 buckets.
        """
        s3_client = resolve_s3_client(s3_context, bsm)
        response = s3_client.list_buckets()
        s3bucket_list = list()
        for dct in response.get("Buckets", []):
            s3bucket = cls.from_bucket(dct["Name"])
            s3bucket._meta = {"LastModified": dct["CreationDate"]}
            s3bucket_list.append(s3bucket)
        return s3bucket_list

# -*- coding: utf-8 -*-

"""
Bucket related API.

Every method except ``from_bucket`` and ``list_buckets`` must be called on a
bucket (e.g. ``S3Path("my-bucket")``), and raises ``S3PathIsNotBucketError``
on any other path, before calling AWS.

Errors from AWS are raised as is (``botocore.exceptions.ClientError``), e.g.
``NoSuchBucket`` for a missing bucket.

.. _create_bucket: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/create_bucket.html
.. _delete_bucket: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/delete_bucket.html
.. _get_bucket_versioning: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_bucket_versioning.html
.. _put_bucket_versioning: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_bucket_versioning.html
.. _list_buckets: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/list_buckets.html
"""

from __future__ import annotations

import typing as T

from .._arg import OPT
from .._arg import remove_optional
from ..aws import s3_context
from ..constants import S3_LIST_BUCKETS_MAX_BUCKETS
from ..exc import S3ValidationError
from .resolve_s3_client import resolve_s3_client


if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client


class BucketAPIMixin:
    """
    A mixin class that implements the bucket related methods.
    """

    __slots__ = ()

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
        region: str | None = None,
        acl: str = OPT,
        grant_full_control: str = OPT,
        grant_read: str = OPT,
        grant_read_acp: str = OPT,
        grant_write: str = OPT,
        grant_write_acp: str = OPT,
        object_lock_enabled_for_bucket: bool = OPT,
        object_ownership: str = OPT,
        s3_client: S3Client | None = None,
    ) -> dict:
        """
        Create this bucket, see `create_bucket`_.

        :param region: the region of the new bucket. ``None`` (the default)
            means the region of the S3 client. S3 rejects a region other than
            the one of the client with ``IllegalLocationConstraintException``,
            except when the client is in ``us-east-1``.
        :param acl: ``ACL``, e.g. ``"private"``.
        :param grant_full_control: ``GrantFullControl``.
        :param grant_read: ``GrantRead``.
        :param grant_read_acp: ``GrantReadACP``.
        :param grant_write: ``GrantWrite``.
        :param grant_write_acp: ``GrantWriteACP``.
        :param object_lock_enabled_for_bucket: ``ObjectLockEnabledForBucket``.
        :param object_ownership: ``ObjectOwnership``, e.g.
            ``"BucketOwnerEnforced"``.

        :return: the response of `create_bucket`_.

        :raises S3PathIsNotBucketError: if this path is not a bucket.
        :raises botocore.exceptions.ClientError: as is, e.g.
            ``BucketAlreadyExists`` when another AWS account owns the name, and
            ``BucketAlreadyOwnedByYou`` when you already own it.

        .. note::

            In ``us-east-1``, creating a bucket you already own succeeds and
            resets its ACL, instead of raising ``BucketAlreadyOwnedByYou``
            (a legacy behavior of S3).
        """
        self.ensure_bucket()
        client = resolve_s3_client(s3_context, s3_client)
        if region is None:
            region = client.meta.region_name
        # us-east-1 is the default location, S3 rejects it as a LocationConstraint
        if region == "us-east-1":
            create_bucket_configuration = OPT
        else:
            create_bucket_configuration = dict(LocationConstraint=region)
        response = client.create_bucket(
            **remove_optional(
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
        expected_bucket_owner: str = OPT,
        s3_client: S3Client | None = None,
    ) -> dict:
        """
        Delete this bucket, see `delete_bucket`_. The bucket must be empty
        (no object, no object version, no delete marker). This ``S3Path`` is
        not changed: a bucket listed by ``list_buckets`` keeps its snapshot,
        like every other method that changes S3 (see ``core.metadata``).

        :param expected_bucket_owner: ``ExpectedBucketOwner``, the AWS account
            id that must own the bucket.

        :return: the response of `delete_bucket`_.

        :raises S3PathIsNotBucketError: if this path is not a bucket.
        :raises botocore.exceptions.ClientError: as is, e.g. ``NoSuchBucket``,
            and ``BucketNotEmpty`` when the bucket is not empty.
        """
        self.ensure_bucket()
        client = resolve_s3_client(s3_context, s3_client)
        response = client.delete_bucket(
            **remove_optional(
                Bucket=self.bucket,
                ExpectedBucketOwner=expected_bucket_owner,
            ),
        )
        return response

    def get_bucket_versioning(
        self: S3Path,
        expected_bucket_owner: str = OPT,
        s3_client: S3Client | None = None,
    ) -> dict:
        """
        Get the versioning state of this bucket, see `get_bucket_versioning`_.

        :param expected_bucket_owner: ``ExpectedBucketOwner``, the AWS account
            id that must own the bucket.

        :return: the response of `get_bucket_versioning`_. ``"Status"`` is
            ``"Enabled"`` or ``"Suspended"``, and missing if versioning was
            never enabled.

        :raises S3PathIsNotBucketError: if this path is not a bucket.
        :raises botocore.exceptions.ClientError: as is, e.g. ``NoSuchBucket``.
        """
        self.ensure_bucket()
        client = resolve_s3_client(s3_context, s3_client)
        response = client.get_bucket_versioning(
            **remove_optional(
                Bucket=self.bucket,
                ExpectedBucketOwner=expected_bucket_owner,
            ),
        )
        return response

    def is_versioning_enabled(
        self: S3Path,
        s3_client: S3Client | None = None,
    ) -> bool:
        """
        Check if the versioning of this bucket is enabled. ``False`` if it is
        suspended or was never enabled.

        :raises S3PathIsNotBucketError: if this path is not a bucket.
        :raises botocore.exceptions.ClientError: as is, e.g. ``NoSuchBucket``.
        """
        res = self.get_bucket_versioning(s3_client=s3_client)
        return res.get("Status", "UNKNOWN") == "Enabled"

    def is_versioning_suspended(
        self: S3Path,
        s3_client: S3Client | None = None,
    ) -> bool:
        """
        Check if the versioning of this bucket is suspended. ``False`` if it
        is enabled or was never enabled.

        :raises S3PathIsNotBucketError: if this path is not a bucket.
        :raises botocore.exceptions.ClientError: as is, e.g. ``NoSuchBucket``.
        """
        res = self.get_bucket_versioning(s3_client=s3_client)
        return res.get("Status", "UNKNOWN") == "Suspended"

    def put_bucket_versioning(
        self: S3Path,
        enable_versioning: bool,
        enable_mfa_delete: bool | None = None,
        check_sum_algorithm: str = OPT,
        mfa: str = OPT,
        expected_bucket_owner: str = OPT,
        s3_client: S3Client | None = None,
    ) -> dict:
        """
        Enable or suspend the versioning of this bucket, see
        `put_bucket_versioning`_. Versioning cannot be turned off once
        enabled, only suspended.

        :param enable_versioning: ``True`` sets ``Status`` to ``"Enabled"``,
            ``False`` to ``"Suspended"``.
        :param enable_mfa_delete: ``True`` sets ``MFADelete`` to
            ``"Enabled"``, ``False`` to ``"Disabled"``; ``None`` (default), it
            is not sent. Only the root user of the bucket owner account can change
            it, and it requires ``mfa``.
        :param check_sum_algorithm: ``ChecksumAlgorithm``.
        :param mfa: ``MFA``, the serial number of the MFA device, a space, and
            the code it shows.
        :param expected_bucket_owner: ``ExpectedBucketOwner``, the AWS account
            id that must own the bucket.

        :return: the response of `put_bucket_versioning`_.

        :raises S3PathIsNotBucketError: if this path is not a bucket.
        :raises botocore.exceptions.ClientError: as is, e.g. ``NoSuchBucket``.
        """
        self.ensure_bucket()
        client = resolve_s3_client(s3_context, s3_client)
        if enable_versioning:
            status = "Enabled"
        else:
            status = "Suspended"
        versioning_configuration = dict(Status=status)
        if enable_mfa_delete is not None:
            if enable_mfa_delete:
                versioning_configuration["MFADelete"] = "Enabled"
            else:
                versioning_configuration["MFADelete"] = "Disabled"
        response = client.put_bucket_versioning(
            **remove_optional(
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
        s3_client: S3Client | None = None,
    ) -> list[S3Path]:
        """
        List all buckets of the AWS account, see `list_buckets`_. It fetches
        every page (up to 10,000 buckets per call), so it also works for an
        account allowed to have more than 10,000 buckets, where S3 rejects a
        ListBuckets request without ``MaxBuckets``.

        Each bucket carries the data S3 returned: ``last_modified_at`` is the
        creation date of the bucket, and ``response["BucketRegion"]`` its
        region (when S3 returns it).

        :raises botocore.exceptions.ClientError: as is, e.g. ``AccessDenied``.
        """
        client = resolve_s3_client(s3_context, s3_client)
        kwargs = dict(MaxBuckets=S3_LIST_BUCKETS_MAX_BUCKETS)
        s3bucket_list = list()
        while True:
            response = client.list_buckets(**kwargs)
            for dct in response.get("Buckets", []):
                s3bucket = cls.from_bucket(dct["Name"])
                meta = {"LastModified": dct["CreationDate"]}
                if "BucketRegion" in dct:
                    meta["BucketRegion"] = dct["BucketRegion"]
                s3bucket._set_meta(
                    meta,
                    complete=False,
                    s3_client=s3_client,
                )
                s3bucket_list.append(s3bucket)
            continuation_token = response.get("ContinuationToken")
            if continuation_token is None:
                break
            kwargs["ContinuationToken"] = continuation_token
        return s3bucket_list

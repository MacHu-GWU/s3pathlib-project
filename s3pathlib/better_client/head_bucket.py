# -*- coding: utf-8 -*-

"""
Improve the head_bucket_ API.

.. _head_bucket: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/head_bucket.html
"""

from __future__ import annotations

import typing as T

import botocore.exceptions

from .. import exc

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


def is_bucket_exists(
    s3_client: S3Client,
    bucket: str,
) -> bool:
    """
    Check if a bucket exists, with head_bucket_.

    Example::

        is_bucket_exists(s3_client, "my-bucket")  # True

    S3 decides whether a name exists: a name that breaks the bucket naming
    rules (e.g. uppercase letters) simply does not exist. A bucket in another
    region is found too (botocore follows the region redirect).

    :return: ``True`` if the bucket exists and you can access it, ``False`` if
        it does not exist (S3 returns 404).

    :raises S3PermissionDenied: if S3 returns 403: the bucket exists but you
        cannot access it, because it belongs to another AWS account or you lack
        the ``s3:ListBucket`` permission. The ``ClientError`` is its
        ``__cause__``.
    :raises botocore.exceptions.ParamValidationError: if botocore rejects the
        name before sending the request, e.g. an empty name or one with a space.
    :raises botocore.exceptions.ClientError: for any other error.
    """
    try:
        s3_client.head_bucket(Bucket=bucket)
        return True
    except botocore.exceptions.ClientError as e:
        # head_bucket has no response body, so the code is the HTTP status
        code = e.response["Error"]["Code"]
        if code == "404":
            return False
        elif code == "403":
            raise exc.S3PermissionDenied(
                f"no permission to access bucket 's3://{bucket}/': it exists, "
                "but it belongs to another AWS account, or you lack the "
                "s3:ListBucket permission"
            ) from e
        else:
            raise

# -*- coding: utf-8 -*-

"""
Improve the head_object_ API.

.. _head_object: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/head_object.html
"""

from __future__ import annotations

import typing as T
from datetime import datetime

import botocore.exceptions

from .._arg import OPT
from .._arg import remove_optional
from .. import exc

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import HeadObjectOutputTypeDef


def head_object(
    s3_client: S3Client,
    bucket: str,
    key: str,
    if_match: str = OPT,
    if_modified_since: datetime = OPT,
    if_none_match: str = OPT,
    if_unmodified_since: datetime = OPT,
    range: str = OPT,
    version_id: str = OPT,
    sse_customer_algorithm: str = OPT,
    sse_customer_key: str = OPT,
    request_payer: str = OPT,
    part_number: int = OPT,
    expected_bucket_owner: str = OPT,
    checksum_mode: str = OPT,
    ignore_not_found: bool = False,
) -> dict | HeadObjectOutputTypeDef | None:
    """
    Wrapper of head_object_ that turns "not found" into ``S3FileNotExist`` (or
    ``None``) and "no permission" into ``S3PermissionDenied``.

    Example::

        response = head_object(s3_client, "my-bucket", "file.txt", ignore_not_found=True)
        if response is None:
            print("Object not found")
        else:
            print(response["ContentLength"])

    The object does not exist when S3 answers 404 (the key, or the bucket, does
    not exist; or the latest version is a delete marker) or 405 (``version_id``
    is a delete marker). A ``HEAD`` response has no body, so S3 cannot tell a
    missing key from a missing bucket.

    :param ignore_not_found: if ``True``, return ``None`` when the object is
        not found instead of raising an error.

    :return: the head_object_ response, or ``None`` if the object does not
        exist and ``ignore_not_found`` is ``True``.

    :raises S3FileNotExist: if the object does not exist and
        ``ignore_not_found`` is ``False``. The ``ClientError`` is its
        ``__cause__``.
    :raises S3PermissionDenied: if S3 answers 403: you cannot read the object,
        or the bucket belongs to another AWS account. Without the
        ``s3:ListBucket`` permission, S3 also answers 403 for a missing key.
        Raised even if ``ignore_not_found`` is ``True``.
    :raises botocore.exceptions.ClientError: for any other error, e.g. 400 for
        a malformed ``version_id``, 412 when ``if_match`` does not match, 304
        when ``if_none_match`` matches.
    """
    try:
        dct = s3_client.head_object(
            **remove_optional(
                Bucket=bucket,
                Key=key,
                IfMatch=if_match,
                IfModifiedSince=if_modified_since,
                IfNoneMatch=if_none_match,
                IfUnmodifiedSince=if_unmodified_since,
                Range=range,
                VersionId=version_id,
                SSECustomerAlgorithm=sse_customer_algorithm,
                SSECustomerKey=sse_customer_key,
                RequestPayer=request_payer,
                PartNumber=part_number,
                ExpectedBucketOwner=expected_bucket_owner,
                ChecksumMode=checksum_mode,
            )
        )
        return dct
    except botocore.exceptions.ClientError as e:
        # a HEAD response has no body, so the code is the HTTP status
        code = e.response["Error"]["Code"]
        # - "404": the key or the bucket does not exist, or the latest version
        #   is a delete marker
        # - "405": version_id is a delete marker
        # - "NoSuchBucket": what moto raises for a missing bucket (real S3
        #   answers "404"); handled the same, so code tested with moto behaves
        #   as on AWS
        if code in ["404", "405", "NoSuchBucket"]:
            if ignore_not_found:
                return None
            else:
                uri = f"s3://{bucket}/{key}"
                if version_id is OPT:
                    raise exc.S3FileNotExist.make(uri) from e
                else:
                    raise exc.S3FileNotExist(
                        f"S3 object {uri!r} version {version_id!r} does not exist!"
                    ) from e
        elif code == "403":
            raise exc.S3PermissionDenied(
                f"no permission to read S3 object 's3://{bucket}/{key}': the "
                "bucket belongs to another AWS account, or you lack the "
                "s3:GetObject permission (without s3:ListBucket, S3 also "
                "answers 403 for a missing key)"
            ) from e
        else:
            raise


def is_object_exists(
    s3_client: S3Client,
    bucket: str,
    key: str,
    version_id: str = OPT,
) -> bool:
    """
    Check if an object exists. To use the head_object_ response when it
    exists, use :func:`head_object` instead. It follows the same rules as
    :func:`head_object`: a missing bucket and a delete marker mean ``False``,
    and no permission raises ``S3PermissionDenied``.
    """
    response = head_object(
        s3_client=s3_client,
        bucket=bucket,
        key=key,
        version_id=version_id,
        ignore_not_found=True,
    )
    if response is None:
        return False
    else:
        return True

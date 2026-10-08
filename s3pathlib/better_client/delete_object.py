# -*- coding: utf-8 -*-

"""
Improve the delete_object_ API.

.. _delete_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/delete_object.html
.. _delete_objects: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/delete_objects.html
"""

from __future__ import annotations

import typing as T
import warnings

from func_args import NOTHING
from func_args import resolve_kwargs

from .. import exc
from ..utils import grouper_list
from ..utils import ensure_s3_dir
from .list_objects import paginate_list_objects_v2
from .list_object_versions import paginate_list_object_versions

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import DeleteObjectOutputTypeDef


def delete_object(
    s3_client: S3Client,
    bucket: str,
    key: str,
    version_id: str = NOTHING,
    mfa: str = NOTHING,
    request_payer: str = NOTHING,
    bypass_governance_retention: bool = NOTHING,
    expected_bucket_owner: str = NOTHING,
    ignore_not_found: bool = NOTHING,
) -> DeleteObjectOutputTypeDef:
    """
    Wrapper of delete_object_.

    S3 never reports a missing key: deleting it succeeds. In a bucket with
    versioning, it adds a delete marker, even if the key never existed (moto
    does not). Errors of the AWS call (e.g. ``NoSuchBucket``,
    ``AccessDenied``) are raised as is.

    :param s3_client: ``boto3.session.Session().client("s3")`` object.
    :param bucket: See delete_object_.
    :param key: See delete_object_.
    :param version_id: See delete_object_.
    :param mfa: See delete_object_.
    :param request_payer: See delete_object_.
    :param bypass_governance_retention: See delete_object_.
    :param expected_bucket_owner: See delete_object_.
    :param ignore_not_found: Deprecated since 3.0.0, will be removed in 4.0.0.
        It has no effect, because S3 never reports a missing key.

    :return: See delete_object_.
    """
    if ignore_not_found is not NOTHING:
        warnings.warn(
            "ignore_not_found is deprecated since 3.0.0, will be removed in "
            "4.0.0. It has no effect: S3 never reports a missing key when "
            "deleting. Remove the argument.",
            DeprecationWarning,
            stacklevel=2,
        )
    return s3_client.delete_object(
        **resolve_kwargs(
            Bucket=bucket,
            Key=key,
            MFA=mfa,
            VersionId=version_id,
            RequestPayer=request_payer,
            BypassGovernanceRetention=bypass_governance_retention,
            ExpectedBucketOwner=expected_bucket_owner,
        )
    )


def _delete_objects(
    s3_client: S3Client,
    bucket: str,
    objects: list[dict],
    n_deleted: int,
    mfa: str,
    request_payer: str,
    bypass_governance_retention: bool,
    expected_bucket_owner: str,
    check_sum_algorithm: str,
) -> int:
    """
    Call delete_objects_ for at most 1000 objects.

    :param objects: ``[{"Key": ...}]`` or ``[{"Key": ..., "VersionId": ...}]``.
    :param n_deleted: The number of objects deleted by the previous calls,
        for the error message.

    :return: the number of objects deleted by this call.

    :raises S3DeleteObjectsError: if S3 failed to delete some of the objects.
    """
    response = s3_client.delete_objects(
        **resolve_kwargs(
            Bucket=bucket,
            Delete={"Objects": objects},
            MFA=mfa,
            RequestPayer=request_payer,
            BypassGovernanceRetention=bypass_governance_retention,
            ExpectedBucketOwner=expected_bucket_owner,
            ChecksumAlgorithm=check_sum_algorithm,
        )
    )
    errors = response.get("Errors", [])
    n_deleted_now = len(objects) - len(errors)
    if len(errors) > 0:
        first = errors[0]
        raise exc.S3DeleteObjectsError(
            f"failed to delete {len(errors)} object(s) in bucket {bucket!r}, "
            f"e.g. {first.get('Key')!r}: {first.get('Code')} "
            f"({first.get('Message')}); {n_deleted + n_deleted_now} object(s) "
            "were deleted before stopping",
            errors=errors,
            n_deleted=n_deleted + n_deleted_now,
        )
    return n_deleted_now


def _confirm_delete_bucket(message: str, skip_prompt: bool) -> bool:
    """
    Ask the user to type ``YES`` before deleting everything in a bucket.
    """
    if skip_prompt:
        return True
    answer = input(f"{message}, are you sure you want to do this? (YES/NO): ")
    if answer.strip() == "YES":
        return True
    else:
        print("Aborting")
        return False


def delete_dir(
    s3_client,
    bucket: str,
    prefix: str,
    batch_size: int = 1000,
    limit: int = NOTHING,
    mfa: str = NOTHING,
    request_payer: str = NOTHING,
    bypass_governance_retention: bool = NOTHING,
    expected_bucket_owner: str = NOTHING,
    check_sum_algorithm: str = NOTHING,
    skip_prompt: bool = False,
) -> int:
    """
    Recursively delete all objects under a s3 prefix, including the folder
    marker itself, with delete_objects_. In a bucket with versioning, it adds
    a delete marker to each object; use :func:`delete_object_versions` to
    delete them permanently.

    :param s3_client: ``boto3.session.Session().client("s3")`` object.
    :param bucket: S3 bucket name.
    :param prefix: The folder to delete; it has to end with ``/``. ``""``
        deletes everything in the bucket, after asking you to confirm.
    :param batch_size: Number of objects listed per API call, 1 to 1000.
    :param limit: Total Number of s3 object to delete.
    :param mfa: See delete_object_.
    :param request_payer: See delete_object_.
    :param bypass_governance_retention: See delete_object_.
    :param expected_bucket_owner: See delete_object_.
    :param check_sum_algorithm: See delete_objects_.
    :param skip_prompt: Default False: with ``prefix=""``, ask you to type
        ``YES`` before deleting everything in the bucket.

    :return: number of deleted objects.

    :raises S3ValidationError: if ``prefix`` is not empty and does not end
        with ``/``.
    :raises S3DeleteObjectsError: if S3 failed to delete some objects; the
        objects of the following batches are not deleted.
    """
    if prefix == "":
        message = "You are deleting everything in an S3 Bucket"
        if _confirm_delete_bucket(message, skip_prompt) is False:
            return 0
    else:
        ensure_s3_dir(prefix)

    contents_iterproxy = paginate_list_objects_v2(
        s3_client=s3_client,
        bucket=bucket,
        prefix=prefix,
        batch_size=batch_size,
        limit=limit,
        request_payer=request_payer,
        expected_bucket_owner=expected_bucket_owner,
    ).contents()

    count = 0
    for contents in grouper_list(contents_iterproxy, 1000):
        count += _delete_objects(
            s3_client=s3_client,
            bucket=bucket,
            objects=[dict(Key=dct["Key"]) for dct in contents],
            n_deleted=count,
            mfa=mfa,
            request_payer=request_payer,
            bypass_governance_retention=bypass_governance_retention,
            expected_bucket_owner=expected_bucket_owner,
            check_sum_algorithm=check_sum_algorithm,
        )
    return count


def delete_object_versions(
    s3_client: S3Client,
    bucket: str,
    prefix: str,
    batch_size: int = 1000,
    limit: int = NOTHING,
    mfa: str = NOTHING,
    request_payer: str = NOTHING,
    bypass_governance_retention: bool = NOTHING,
    expected_bucket_owner: str = NOTHING,
    check_sum_algorithm: str = NOTHING,
    skip_prompt: bool = False,
) -> int:
    """
    Recursively delete all objects and all their versions and delete markers
    under a folder, permanently, with delete_objects_. To delete all versions
    of one object, use :func:`delete_object_all_versions`.

    :param s3_client: ``boto3.session.Session().client("s3")`` object.
    :param bucket: S3 bucket name.
    :param prefix: The folder to delete; it has to end with ``/``. ``""``
        deletes everything in the bucket, after asking you to confirm.
    :param batch_size: Number of versions listed per API call, 1 to 1000.
    :param limit: Total number of versions and delete markers to delete.
    :param mfa: See delete_object_.
    :param request_payer: See delete_object_.
    :param bypass_governance_retention: See delete_object_.
    :param expected_bucket_owner: See delete_object_.
    :param check_sum_algorithm: See delete_objects_.
    :param skip_prompt: Default False: with ``prefix=""``, ask you to type
        ``YES`` before deleting everything in the bucket.

    :return: number of deleted versions and delete markers.

    :raises S3ValidationError: if ``prefix`` is not empty and does not end
        with ``/``. A prefix such as ``"data/file.txt"`` would also match
        ``data/file.txt.bak``; before 3.0 it deleted those too.
    :raises S3DeleteObjectsError: if S3 failed to delete some versions; the
        versions of the following batches are not deleted.
    """
    if prefix == "":
        message = (
            "You are deleting everything in an S3 Bucket, "
            "including all historical versions"
        )
        if _confirm_delete_bucket(message, skip_prompt) is False:
            return 0
    else:
        ensure_s3_dir(prefix)

    proxy = paginate_list_object_versions(
        s3_client=s3_client,
        bucket=bucket,
        prefix=prefix,
        batch_size=batch_size,
        limit=limit,
        expected_bucket_owner=expected_bucket_owner,
    )
    count = 0
    for pairs in grouper_list(proxy.iterate_key_and_version(), 1000):
        count += _delete_objects(
            s3_client=s3_client,
            bucket=bucket,
            objects=[dict(Key=key, VersionId=version_id) for key, version_id in pairs],
            n_deleted=count,
            mfa=mfa,
            request_payer=request_payer,
            bypass_governance_retention=bypass_governance_retention,
            expected_bucket_owner=expected_bucket_owner,
            check_sum_algorithm=check_sum_algorithm,
        )
    return count


def delete_object_all_versions(
    s3_client: S3Client,
    bucket: str,
    key: str,
    mfa: str = NOTHING,
    request_payer: str = NOTHING,
    bypass_governance_retention: bool = NOTHING,
    expected_bucket_owner: str = NOTHING,
    check_sum_algorithm: str = NOTHING,
) -> int:
    """
    Delete all versions and delete markers of one object, permanently, with
    delete_objects_. Only the versions whose key is exactly ``key``: other
    keys that start with it (e.g. ``file.txt.bak`` for ``file.txt``) are kept.

    :param s3_client: ``boto3.session.Session().client("s3")`` object.
    :param bucket: S3 bucket name.
    :param key: The key of the object.
    :param mfa: See delete_object_.
    :param request_payer: See delete_object_.
    :param bypass_governance_retention: See delete_object_.
    :param expected_bucket_owner: See delete_object_.
    :param check_sum_algorithm: See delete_objects_.

    :return: number of deleted versions and delete markers; ``0`` if the
        object has none.

    :raises ValueError: if ``key`` is empty.
    :raises S3DeleteObjectsError: if S3 failed to delete some versions.
    """
    if key == "":
        raise ValueError("key must not be empty")
    proxy = paginate_list_object_versions(
        s3_client=s3_client,
        bucket=bucket,
        prefix=key,
        expected_bucket_owner=expected_bucket_owner,
    )
    # the prefix also matches longer keys, keep only this key
    pairs_of_key = (
        (k, version_id) for k, version_id in proxy.iterate_key_and_version() if k == key
    )
    count = 0
    for pairs in grouper_list(pairs_of_key, 1000):
        count += _delete_objects(
            s3_client=s3_client,
            bucket=bucket,
            objects=[dict(Key=k, VersionId=version_id) for k, version_id in pairs],
            n_deleted=count,
            mfa=mfa,
            request_payer=request_payer,
            bypass_governance_retention=bypass_governance_retention,
            expected_bucket_owner=expected_bucket_owner,
            check_sum_algorithm=check_sum_algorithm,
        )
    return count

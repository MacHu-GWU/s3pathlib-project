# -*- coding: utf-8 -*-

"""
Improve the delete_object_ and delete_objects_ APIs.

**Design notes**

*Permanent deletion needs a folder prefix.* ``delete_dir`` and
``delete_object_versions`` take a prefix that ends with ``/`` (or ``""`` for
the whole bucket, after a confirmation). A prefix such as ``"data/file.txt"``
is a string prefix: it also matches ``data/file.txt.bak``, and deleting all
the versions of the match would lose data that is not the object. Use
``delete_object_all_versions`` for the versions of exactly one key.

*delete_objects can fail with HTTP 200.* The failed keys are in the ``Errors``
of the response, and boto3 raises nothing, so ``delete_in_batches`` checks
them and raises :class:`~s3pathlib.exc.S3DeleteObjectsError`.

.. _delete_object: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/delete_object.html
.. _delete_objects: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/delete_objects.html
"""

from __future__ import annotations

import typing as T
import warnings

from .._arg import NOT_GIVEN
from .._arg import OPT
from .._arg import remove_optional
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
    version_id: str = OPT,
    mfa: str = OPT,
    request_payer: str = OPT,
    bypass_governance_retention: bool = OPT,
    expected_bucket_owner: str = OPT,
    ignore_not_found: bool = NOT_GIVEN,
) -> DeleteObjectOutputTypeDef:
    """
    Wrapper of delete_object_.

    S3 never reports a missing key: deleting it succeeds. In a bucket with
    versioning, it adds a delete marker, even if the key never existed (moto
    does not). Errors of the AWS call (e.g. ``NoSuchBucket``,
    ``AccessDenied``) are raised as is.

    :param ignore_not_found: Deprecated since 3.0.0, will be removed in 4.0.0.
        It has no effect, because S3 never reports a missing key.
    """
    if ignore_not_found is not NOT_GIVEN:
        warnings.warn(
            "ignore_not_found is deprecated since 3.0.0, will be removed in "
            "4.0.0. It has no effect: S3 never reports a missing key when "
            "deleting. Remove the argument.",
            DeprecationWarning,
            stacklevel=2,  # user -> delete_object
        )
    return s3_client.delete_object(
        **remove_optional(
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
    checksum_algorithm: str,
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
        **remove_optional(
            Bucket=bucket,
            Delete={"Objects": objects},
            MFA=mfa,
            RequestPayer=request_payer,
            BypassGovernanceRetention=bypass_governance_retention,
            ExpectedBucketOwner=expected_bucket_owner,
            ChecksumAlgorithm=checksum_algorithm,
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


def delete_in_batches(
    s3_client: S3Client,
    bucket: str,
    objects: T.Iterable[dict],
    mfa: str = OPT,
    request_payer: str = OPT,
    bypass_governance_retention: bool = OPT,
    expected_bucket_owner: str = OPT,
    checksum_algorithm: str = OPT,
) -> int:
    """
    Delete ``objects`` with delete_objects_, 1000 at a time (its limit), and
    stop at the first batch that S3 fails to delete.

    :param objects: ``{"Key": ...}`` or ``{"Key": ..., "VersionId": ...}``,
        consumed lazily.

    :return: the number of objects deleted.

    :raises S3DeleteObjectsError: if S3 failed to delete some of a batch; the
        following batches are not deleted.
    """
    count = 0
    for batch in grouper_list(objects, 1000):
        count += _delete_objects(
            s3_client=s3_client,
            bucket=bucket,
            objects=batch,
            n_deleted=count,
            mfa=mfa,
            request_payer=request_payer,
            bypass_governance_retention=bypass_governance_retention,
            expected_bucket_owner=expected_bucket_owner,
            checksum_algorithm=checksum_algorithm,
        )
    return count


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
    s3_client: S3Client,
    bucket: str,
    prefix: str,
    batch_size: int = 1000,
    limit: int | None = None,
    mfa: str = OPT,
    request_payer: str = OPT,
    bypass_governance_retention: bool = OPT,
    expected_bucket_owner: str = OPT,
    checksum_algorithm: str = OPT,
    skip_prompt: bool = False,
) -> int:
    """
    Recursively delete all objects under a folder, the folder marker itself
    included, with delete_objects_. In a bucket with versioning, it adds a
    delete marker to each object; use :func:`delete_object_versions` to delete
    them permanently.

    :param prefix: The folder to delete; it has to end with ``/``. ``""``
        deletes everything in the bucket, after asking you to confirm.
    :param batch_size: Number of objects listed per API call, 1 to 1000.
    :param limit: Total number of objects to delete. ``None`` (default):
        no limit.
    :param skip_prompt: Default False: with ``prefix=""``, ask you to type
        ``YES`` before deleting everything in the bucket.

    :return: number of deleted objects.

    :raises S3ValidationError: if ``prefix`` is not empty and does not end
        with ``/``.
    :raises S3DeleteObjectsError: if S3 failed to delete some objects.
    """
    if prefix == "":
        message = "You are deleting everything in an S3 Bucket"
        if _confirm_delete_bucket(message, skip_prompt) is False:
            return 0
    else:
        ensure_s3_dir(prefix)

    contents = paginate_list_objects_v2(
        s3_client=s3_client,
        bucket=bucket,
        prefix=prefix,
        batch_size=batch_size,
        limit=limit,
        request_payer=request_payer,
        expected_bucket_owner=expected_bucket_owner,
    ).contents()
    return delete_in_batches(
        s3_client=s3_client,
        bucket=bucket,
        objects=(dict(Key=content["Key"]) for content in contents),
        mfa=mfa,
        request_payer=request_payer,
        bypass_governance_retention=bypass_governance_retention,
        expected_bucket_owner=expected_bucket_owner,
        checksum_algorithm=checksum_algorithm,
    )


def delete_object_versions(
    s3_client: S3Client,
    bucket: str,
    prefix: str,
    batch_size: int = 1000,
    limit: int | None = None,
    mfa: str = OPT,
    request_payer: str = OPT,
    bypass_governance_retention: bool = OPT,
    expected_bucket_owner: str = OPT,
    checksum_algorithm: str = OPT,
    skip_prompt: bool = False,
) -> int:
    """
    Recursively delete all objects and all their versions and delete markers
    under a folder, permanently, with delete_objects_. To delete all versions
    of one object, use :func:`delete_object_all_versions`.

    :param prefix: The folder to delete; it has to end with ``/``. ``""``
        deletes everything in the bucket, after asking you to confirm.
    :param batch_size: Number of versions listed per API call, 1 to 1000.
    :param limit: Total number of versions and delete markers to delete.
        ``None`` (default): no limit.
    :param skip_prompt: Default False: with ``prefix=""``, ask you to type
        ``YES`` before deleting everything in the bucket.

    :return: number of deleted versions and delete markers.

    :raises S3ValidationError: if ``prefix`` is not empty and does not end
        with ``/``.
    :raises S3DeleteObjectsError: if S3 failed to delete some versions.
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
        request_payer=request_payer,
        expected_bucket_owner=expected_bucket_owner,
    )
    return delete_in_batches(
        s3_client=s3_client,
        bucket=bucket,
        objects=(
            dict(Key=key, VersionId=version_id)
            for key, version_id in proxy.iterate_key_and_version()
        ),
        mfa=mfa,
        request_payer=request_payer,
        bypass_governance_retention=bypass_governance_retention,
        expected_bucket_owner=expected_bucket_owner,
        checksum_algorithm=checksum_algorithm,
    )


def delete_object_all_versions(
    s3_client: S3Client,
    bucket: str,
    key: str,
    mfa: str = OPT,
    request_payer: str = OPT,
    bypass_governance_retention: bool = OPT,
    expected_bucket_owner: str = OPT,
    checksum_algorithm: str = OPT,
) -> int:
    """
    Delete all versions and delete markers of one object, permanently, with
    delete_objects_. Only the versions whose key is exactly ``key``: other
    keys that start with it (e.g. ``file.txt.bak`` for ``file.txt``) are kept.

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
        request_payer=request_payer,
        expected_bucket_owner=expected_bucket_owner,
    )
    # the prefix also matches longer keys, keep only this key
    return delete_in_batches(
        s3_client=s3_client,
        bucket=bucket,
        objects=(
            dict(Key=k, VersionId=version_id)
            for k, version_id in proxy.iterate_key_and_version()
            if k == key
        ),
        mfa=mfa,
        request_payer=request_payer,
        bypass_governance_retention=bypass_governance_retention,
        expected_bucket_owner=expected_bucket_owner,
        checksum_algorithm=checksum_algorithm,
    )

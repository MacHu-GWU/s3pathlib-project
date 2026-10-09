# -*- coding: utf-8 -*-

"""
Update S3 bucket, object tagging.

.. _get_bucket_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_bucket_tagging.html
.. _put_bucket_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_bucket_tagging.html

.. _get_object_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_object_tagging.html
.. _put_object_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object_tagging.html
"""

from __future__ import annotations

import typing as T

import botocore.exceptions

from .._arg import OPT
from .._arg import remove_optional
from .. import tag

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


def update_bucket_tagging(
    s3_client: S3Client,
    bucket: str,
    tags: tag.TagType,
    checksum_algorithm: str = OPT,
    expected_bucket_owner: str = OPT,
) -> tag.TagType:
    """
    Update the bucket tags like ``dict.update``: add the new keys, overwrite
    the existing ones, keep the others. It calls get_bucket_tagging_, merges,
    then calls put_bucket_tagging_, so it is not atomic: a change made by
    someone else in between is lost.

    Example::

        >>> update_bucket_tagging(s3_client, "my-bucket", {"team": "data"})
        {'team': 'data'}

    S3 checks the limits (at most 50 tags per bucket, key and value length) and
    raises ``ClientError`` when they are broken.

    :param s3_client: See put_bucket_tagging_
    :param bucket: See put_bucket_tagging_
    :param tags: The tags to add or overwrite.
    :param checksum_algorithm: See put_bucket_tagging_
    :param expected_bucket_owner: See put_bucket_tagging_

    :return: All the tags of the bucket after the update.

    Errors of the AWS calls are raised as is (``botocore.exceptions.ClientError``,
    check ``e.response["Error"]["Code"]``), e.g.:

    - ``NoSuchBucket``: the bucket does not exist.
    - ``AccessDenied``: the bucket belongs to another AWS account, or you lack
      the ``s3:GetBucketTagging`` / ``s3:PutBucketTagging`` permission.
    """
    try:
        res = s3_client.get_bucket_tagging(
            **remove_optional(
                Bucket=bucket,
                ExpectedBucketOwner=expected_bucket_owner,
            )
        )
        existing_tags = tag.parse_tags(res.get("TagSet", []))
    except botocore.exceptions.ClientError as e:
        # a bucket without tags; not a modeled exception, check the code
        if e.response["Error"]["Code"] == "NoSuchTagSet":
            existing_tags = {}
        else:
            raise e

    existing_tags.update(tags)
    s3_client.put_bucket_tagging(
        **remove_optional(
            Bucket=bucket,
            Tagging=dict(TagSet=tag.encode_for_put_bucket_tagging(existing_tags)),
            ChecksumAlgorithm=checksum_algorithm,
            ExpectedBucketOwner=expected_bucket_owner,
        )
    )
    return existing_tags


def update_object_tagging(
    s3_client: S3Client,
    bucket: str,
    key: str,
    tags: tag.TagType,
    version_id: str = OPT,
    content_md5: str = OPT,
    checksum_algorithm: str = OPT,
    expected_bucket_owner: str = OPT,
    request_payer: str = OPT,
) -> tuple[str | None, tag.TagType]:
    """
    Update the object tags like ``dict.update``: add the new keys, overwrite
    the existing ones, keep the others. It calls get_object_tagging_, merges,
    then calls put_object_tagging_, so it is not atomic: a change made by
    someone else in between is lost.

    Without ``version_id``, it updates the latest version: the version read by
    get_object_tagging_, even if a new version is written before the put.

    Example::

        >>> update_object_tagging(s3_client, "my-bucket", "file.txt", {"team": "data"})
        (None, {'team': 'data'})

    S3 checks the limits (at most 10 tags per object, key and value length)
    and raises ``ClientError`` when they are broken.

    :param s3_client: See put_object_tagging_
    :param bucket: See put_object_tagging_
    :param key: See put_object_tagging_
    :param tags: The tags to add or overwrite.
    :param version_id: See put_object_tagging_
    :param content_md5: See put_object_tagging_
    :param checksum_algorithm: See put_object_tagging_
    :param expected_bucket_owner: See put_object_tagging_
    :param request_payer: See put_object_tagging_

    :return: ``(version_id, tags)``: the version that was updated (``None``
        if the bucket never had versioning), and all its tags after the update.

    Errors of the AWS calls are raised as is (``botocore.exceptions.ClientError``,
    check ``e.response["Error"]["Code"]``), e.g.:

    - ``NoSuchKey``: the key does not exist.
    - ``NoSuchBucket``: the bucket does not exist.
    - ``MethodNotAllowed``: the latest version, or ``version_id``, is a delete
      marker (moto raises ``NoSuchKey`` / ``NoSuchVersion`` instead).
    - ``AccessDenied``: the bucket belongs to another AWS account, or you lack
      the ``s3:GetObjectTagging`` / ``s3:PutObjectTagging`` permission.
    """
    res = s3_client.get_object_tagging(
        **remove_optional(
            Bucket=bucket,
            Key=key,
            VersionId=version_id,
            ExpectedBucketOwner=expected_bucket_owner,
            RequestPayer=request_payer,
        )
    )
    existing_version_id = res.get("VersionId", None)
    existing_tags = tag.parse_tags(res.get("TagSet", []))
    existing_tags.update(tags)
    s3_client.put_object_tagging(
        **remove_optional(
            Bucket=bucket,
            Key=key,
            Tagging=dict(TagSet=tag.encode_for_put_object_tagging(existing_tags)),
            # pin the version that was read
            VersionId=res.get("VersionId", OPT),
            ContentMD5=content_md5,
            ChecksumAlgorithm=checksum_algorithm,
            ExpectedBucketOwner=expected_bucket_owner,
            RequestPayer=request_payer,
        )
    )
    return existing_version_id, existing_tags

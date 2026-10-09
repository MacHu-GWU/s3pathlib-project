# -*- coding: utf-8 -*-

"""
Object tagging related API.

The methods work on a file (an S3 object). Without ``version_id``, they work
on the latest version of the object, even if this ``S3Path`` has the metadata
snapshot of an older version (see :mod:`s3pathlib.core.metadata`); pass
``version_id=p.version_id`` to work on that version. Changing the tags does
not create a new version and does not change ``last_modified_at``.

Errors of the AWS calls are raised as is (``botocore.exceptions.ClientError``,
check ``e.response["Error"]["Code"]``), e.g.:

- ``NoSuchKey``: the object does not exist.
- ``NoSuchBucket``: the bucket does not exist.
- ``MethodNotAllowed``: the latest version, or ``version_id``, is a delete
  marker (moto raises ``NoSuchKey`` / ``NoSuchVersion`` instead).
- ``BadRequest``: more than 10 tags, or a key / value that is too long.
- ``AccessDenied``: the bucket belongs to another AWS account, or you lack the
  ``s3:GetObjectTagging`` / ``s3:PutObjectTagging`` permission.

.. _get_object_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_object_tagging.html
.. _put_object_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object_tagging.html
"""

from __future__ import annotations

import typing as T

from .._arg import OPT
from .._arg import remove_optional
from .resolve_s3_client import resolve_s3_client
from ..better_client.tagging import update_object_tagging
from ..aws import s3_context
from ..type import TagType
from ..tag import parse_tags, encode_tag_set


if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from boto_session_manager.api import BotoSesManager
    from mypy_boto3_s3 import S3Client


class TaggingAPIMixin:
    """
    A mixin class that implements the tagging related methods, see the module
    docstring.
    """

    def _ensure_taggable(self: S3Path) -> None:
        """
        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFileError: for a folder or a bucket.
        """
        self.ensure_not_relpath()
        self.ensure_object()

    def get_tags(
        self: S3Path,
        version_id: str = OPT,
        expected_bucket_owner: str = OPT,
        request_payer: str = OPT,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> tuple[str | None, TagType]:
        """
        Get the tags of the object, see get_object_tagging_.

        Example::

            >>> S3Path("bucket", "file.txt").get_tags()
            (None, {'team': 'data'})

        :param version_id: the version to read, default the latest one.

        :return: ``(version_id, tags)``: the version that was read (``None``
            if the bucket never had versioning), and its tags as a dict
            (``{}`` if it has none).

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFileError: for a folder or a bucket.
        """
        self._ensure_taggable()
        s3_client = resolve_s3_client(s3_context, bsm)
        res = s3_client.get_object_tagging(
            **remove_optional(
                Bucket=self.bucket,
                Key=self.key,
                VersionId=version_id,
                ExpectedBucketOwner=expected_bucket_owner,
                RequestPayer=request_payer,
            )
        )
        returned_version_id = res.get("VersionId", None)
        tags = parse_tags(res.get("TagSet", []))
        return returned_version_id, tags

    def put_tags(
        self: S3Path,
        tags: TagType,
        version_id: str = OPT,
        content_md5: str = OPT,
        checksum_algorithm: str = OPT,
        expected_bucket_owner: str = OPT,
        request_payer: str = OPT,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> tuple[str | None, TagType]:
        """
        Replace all the tags of the object with ``tags``, see
        put_object_tagging_. ``{}`` removes all tags.

        Example::

            >>> S3Path("bucket", "file.txt").put_tags({"team": "data"})
            (None, {'team': 'data'})

        :param tags: the new tags; keys and values must be ``str``.
        :param version_id: the version to change, default the latest one.

        :return: ``(version_id, tags)``: the version that was changed
            (``None`` if the bucket never had versioning), and a copy of
            ``tags``.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFileError: for a folder or a bucket.
        """
        self._ensure_taggable()
        s3_client = resolve_s3_client(s3_context, bsm)
        res = s3_client.put_object_tagging(
            **remove_optional(
                Bucket=self.bucket,
                Key=self.key,
                Tagging=dict(TagSet=encode_tag_set(tags)),
                VersionId=version_id,
                ContentMD5=content_md5,
                ChecksumAlgorithm=checksum_algorithm,
                ExpectedBucketOwner=expected_bucket_owner,
                RequestPayer=request_payer,
            )
        )
        returned_version_id = res.get("VersionId", None)
        return returned_version_id, dict(tags)

    def update_tags(
        self: S3Path,
        tags: TagType,
        version_id: str = OPT,
        content_md5: str = OPT,
        checksum_algorithm: str = OPT,
        expected_bucket_owner: str = OPT,
        request_payer: str = OPT,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> tuple[str | None, TagType]:
        """
        Update the tags of the object like ``dict.update``: add the new keys,
        overwrite the existing ones, keep the others. It reads the tags, merges
        and writes them back, so it is not atomic: a change made by someone
        else in between is lost. See
        :func:`s3pathlib.better_client.tagging.update_object_tagging`.

        Example::

            >>> S3Path("bucket", "file.txt").update_tags({"owner": "alice"})
            (None, {'team': 'data', 'owner': 'alice'})

        :param tags: the tags to add or overwrite; keys and values must be
            ``str``.
        :param version_id: the version to change, default the latest one.

        :return: ``(version_id, tags)``: the version that was changed
            (``None`` if the bucket never had versioning), and all its tags
            after the update.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFileError: for a folder or a bucket.
        """
        self._ensure_taggable()
        s3_client = resolve_s3_client(s3_context, bsm)
        return update_object_tagging(
            s3_client=s3_client,
            bucket=self.bucket,
            key=self.key,
            tags=tags,
            version_id=version_id,
            content_md5=content_md5,
            checksum_algorithm=checksum_algorithm,
            expected_bucket_owner=expected_bucket_owner,
            request_payer=request_payer,
        )

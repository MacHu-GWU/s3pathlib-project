# -*- coding: utf-8 -*-

"""
Delete S3 file or folder.

.. _delete_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/delete_object.html
.. _delete_objects: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/delete_objects.html
"""

from __future__ import annotations

import typing as T

from .._arg import OPT
from ..constants import IS_DELETE_MARKER
from .resolve_s3_client import resolve_s3_client
from ..aws import s3_context
from ..better_client.delete_object import delete_object
from ..better_client.delete_object import delete_dir
from ..better_client.delete_object import delete_object_versions
from ..better_client.delete_object import delete_object_all_versions


if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client


class DeleteAPIMixin:
    """
    A mixin class that implements delete method.
    """

    __slots__ = ()

    def delete(
        self: S3Path,
        version_id: str = OPT,
        mfa: str = OPT,
        request_payer: str = OPT,
        bypass_governance_retention: bool = OPT,
        expected_bucket_owner: str = OPT,
        check_sum_algorithm: str = OPT,
        is_hard_delete: bool = False,
        skip_prompt: bool = False,
        s3_client: S3Client | None = None,
    ) -> S3Path:
        """
        Delete this file, or every object under this folder (or bucket).

        - A file, without versioning: the object is deleted.
        - A file, with versioning: a delete marker is added, the versions are
          kept. In a bucket with versioning, deleting a missing key also adds
          a delete marker (moto does not).
        - A file with ``version_id``: that version (or delete marker) is
          deleted permanently.
        - A file with ``is_hard_delete=True``: every version and delete
          marker of this exact key is deleted permanently (not of other keys
          starting with it, e.g. ``file.txt.bak``).
        - A folder: every object under it (folder markers included) is
          deleted, with delete markers when the bucket has versioning; with
          ``is_hard_delete=True``, every version and delete marker under it is
          deleted permanently.
        - A bucket: everything in it, after asking you to type ``YES`` (unless
          ``skip_prompt=True``).

        Deleting what does not exist is not an error (S3 never reports it).

        Example::

            s3path = S3Path("s3://my-bucket/my-file.txt")
            s3dir = S3Path("s3://my-bucket/my-folder/")
            # delete an object; with versioning, add a delete marker
            s3path_deleted = s3path.delete()
            # delete one version (or delete marker) of an object
            s3path.delete(version_id="v123456")
            # delete all versions and delete markers of an object
            s3path.delete(is_hard_delete=True)
            # delete every object in a folder; with versioning, add delete markers
            s3dir.delete()
            # delete every version and delete marker in a folder
            s3dir.delete(is_hard_delete=True)

        :param version_id: the version (or delete marker) of a file to delete
            permanently, see delete_object_.
        :param mfa: see delete_object_.
        :param request_payer: see delete_object_.
        :param bypass_governance_retention: see delete_object_.
        :param expected_bucket_owner: see delete_object_.
        :param check_sum_algorithm: ``ChecksumAlgorithm`` of delete_objects_,
            used when deleting a folder or with ``is_hard_delete=True``.
        :param is_hard_delete: if ``True``, delete every version and delete
            marker permanently, see above.
        :param skip_prompt: if ``True``, do not ask to confirm before
            deleting everything in a bucket.
        :param s3_client: the boto3 S3 client to use, default the client of
            ``s3_context``.

        :return: a new ``S3Path`` equal to this one; this ``S3Path`` is not
            changed (see :mod:`s3pathlib.core.metadata`). When S3 answers with
            a version, it has a metadata snapshot that never calls AWS:

            - a file with versioning, without ``version_id``: the new delete
              marker (``is_delete_marker()`` is ``True``, ``version_id`` is
              its version id);
            - a file with ``version_id``: the deleted version (``version_id``;
              ``is_delete_marker()`` is ``True`` if it was a delete marker, on
              AWS; moto does not say so).

            Otherwise it has no snapshot.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises ValueError: if ``version_id`` is given for a folder or with
            ``is_hard_delete=True`` (it used to be ignored, and every version
            was deleted).
        :raises S3DeleteObjectsError: if S3 failed to delete some objects of a
            folder.
        :raises botocore.exceptions.ClientError: as is, e.g. ``NoSuchBucket``.
        """
        self.ensure_not_relpath()
        if version_id is not OPT:
            if self.is_dir():
                raise ValueError("version_id only applies to deleting a file")
            if is_hard_delete:
                raise ValueError(
                    "version_id deletes one version, is_hard_delete=True deletes "
                    "all versions: give only one of them"
                )
        client = resolve_s3_client(s3_context, s3_client)
        explicit_client = s3_client
        bucket = self.bucket
        s3path = self.copy()
        s3path._s3_client = explicit_client
        if self.is_file():
            if is_hard_delete:
                # only this key: a prefix would also match "file.txt.bak"
                delete_object_all_versions(
                    s3_client=client,
                    bucket=bucket,
                    key=self.key,
                    mfa=mfa,
                    request_payer=request_payer,
                    bypass_governance_retention=bypass_governance_retention,
                    expected_bucket_owner=expected_bucket_owner,
                    check_sum_algorithm=check_sum_algorithm,
                )
            else:
                response = delete_object(
                    s3_client=client,
                    bucket=bucket,
                    key=self.key,
                    version_id=version_id,
                    mfa=mfa,
                    request_payer=request_payer,
                    bypass_governance_retention=bypass_governance_retention,
                    expected_bucket_owner=expected_bucket_owner,
                )
                # a new delete marker, or the deleted version; a complete
                # snapshot, so that it never loads a version that is gone
                if "VersionId" in response:
                    meta = {"VersionId": response["VersionId"]}
                    if response.get("DeleteMarker") is True:
                        meta[IS_DELETE_MARKER] = True
                    s3path._set_meta(meta, complete=True, s3_client=explicit_client)
        else:
            if is_hard_delete:
                delete_object_versions(
                    s3_client=client,
                    bucket=bucket,
                    prefix=self.key,
                    mfa=mfa,
                    request_payer=request_payer,
                    bypass_governance_retention=bypass_governance_retention,
                    expected_bucket_owner=expected_bucket_owner,
                    check_sum_algorithm=check_sum_algorithm,
                    skip_prompt=skip_prompt,
                )
            else:
                delete_dir(
                    s3_client=client,
                    bucket=bucket,
                    prefix=self.key,
                    mfa=mfa,
                    request_payer=request_payer,
                    bypass_governance_retention=bypass_governance_retention,
                    expected_bucket_owner=expected_bucket_owner,
                    check_sum_algorithm=check_sum_algorithm,
                    skip_prompt=skip_prompt,
                )
        return s3path

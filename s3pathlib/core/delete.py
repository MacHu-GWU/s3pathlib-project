# -*- coding: utf-8 -*-

"""
Delete S3 file or folder.

.. _bsm: https://github.com/aws-samples/boto-session-manager-project
.. _delete_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/delete_object.html
"""

from __future__ import annotations

import typing as T
from func_args import NOTHING

from .resolve_s3_client import resolve_s3_client
from ..aws import s3_context
from ..better_client.delete_object import (
    delete_object,
    delete_dir,
    delete_object_versions,
)


if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from boto_session_manager.api import BotoSesManager
    from mypy_boto3_s3 import S3Client


class DeleteAPIMixin:
    """
    A mixin class that implements delete method.
    """
    def delete(
        self: S3Path,
        version_id: str = NOTHING,
        mfa: str = NOTHING,
        request_payer: str = NOTHING,
        bypass_governance_retention: bool = NOTHING,
        expected_bucket_owner: str = NOTHING,
        check_sum_algorithm: str = NOTHING,
        is_hard_delete: bool = False,
        skip_prompt: bool = False,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> S3Path:
        """
        Can delete:

        - an object.
        - all objects in a directory.
        - specific version or delete marker of an object.
        - all historical versions and delete markers of an object.
        - all objects, all versions in a directory.

        It won't raise any error if the object or the directory doesn't exist.

        Example:

            >>> s3path = S3Path.from_s3_uri("s3://my-bucket/my-file.txt")
            >>> s3dir = S3Path.from_s3_uri("s3://my-bucket/my-folder/")
            # Delete an object
            # for versioning enabled bucket, it just creates a delete maker
            >>> s3path.delete()
            # Delete all objects in a directory
            # for versioning enabled bucket, it just creates delete makers for all objects
            >>> s3path.delete()
            # Delete specific version or delete marker of an object
            >>> s3path.delete(version_id="v123456")
            # Delete all historical versions and delete markers of an object
            >>> s3path.delete(is_hard_delete=True)
            # Delete all objects, all versions in a directory
            >>> s3dir.delete(is_hard_delete=True)

        :param version_id: see delete_object_.
        :param mfa: see delete_object_.
        :param request_payer: see delete_object_.
        :param bypass_governance_retention: see delete_object_.
        :param expected_bucket_owner: see delete_object_.
        :param check_sum_algorithm: See delete_object_.
        :param is_hard_delete: if ``True``, then it will delete all versions
            of the object, then the data is permanently deleted.
        :param skip_prompt: Default False, it will prompt you to confirm when deleting
            everything in an S3 bucket.
        :param bsm: See bsm_.

        :return: a new ``S3Path`` object representing the deleted object

            - if it's a file and the versioning is NOT enabled, then it will
                return the deleted file itself.
            - if it's a file and the versioning is ENABLED,
                - if ``version_id`` is not given, then it will return the
                    ``S3Path`` representing the delete-marker.
                - if ``version_id`` is given, then it will return the ``S3Path``
                    representing the deleted version.
            - if it's a directory, then it will return the deleted folder itself.
        """
        s3_client = resolve_s3_client(s3_context, bsm)
        bucket = self.bucket
        if self.is_file():
            if is_hard_delete:
                delete_object_versions(
                    s3_client=s3_client,
                    bucket=bucket,
                    prefix=self.key,
                    mfa=mfa,
                    request_payer=request_payer,
                    bypass_governance_retention=bypass_governance_retention,
                    expected_bucket_owner=expected_bucket_owner,
                    check_sum_algorithm=check_sum_algorithm,
                )
                self.clear_cache()
                return self

            response = delete_object(
                s3_client=s3_client,
                bucket=bucket,
                key=self.key,
                version_id=version_id,
                mfa=mfa,
                request_payer=request_payer,
                bypass_governance_retention=bypass_governance_retention,
                expected_bucket_owner=expected_bucket_owner,
                ignore_not_found=True,
            )
            # delete_object API succeeded
            if bool(response):
                del response["ResponseMetadata"]
                # print(response)
                # it could be a delete marker or a deleted version
                if "VersionId" in response:
                    s3path = self.copy()
                    s3path._meta = response
                    return s3path
                # not a versioned bucket
                else:
                    self.clear_cache()
                    return self
            # object not exists, nothing happen
            else:  # pragma: no cover
                return self
        elif self.is_dir():
            if is_hard_delete:
                delete_object_versions(
                    s3_client=s3_client,
                    bucket=bucket,
                    prefix=self.key,
                    mfa=mfa,
                    request_payer=request_payer,
                    bypass_governance_retention=bypass_governance_retention,
                    expected_bucket_owner=expected_bucket_owner,
                    check_sum_algorithm=check_sum_algorithm,
                    skip_prompt=skip_prompt,
                )
                return self

            delete_dir(
                s3_client=s3_client,
                bucket=bucket,
                prefix=self.key,
                mfa=mfa,
                request_payer=request_payer,
                bypass_governance_retention=bypass_governance_retention,
                expected_bucket_owner=expected_bucket_owner,
                skip_prompt=skip_prompt,
            )
            return self
        else:  # pragma: no cover
            raise ValueError

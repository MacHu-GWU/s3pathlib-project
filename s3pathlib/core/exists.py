# -*- coding: utf-8 -*-

"""
Existence test related API.
"""

from __future__ import annotations

import typing as T

import botocore.exceptions

from .._arg import OPT
from .. import exc
from ..better_client.head_bucket import is_bucket_exists
from ..better_client.head_object import head_object
from ..better_client.list_objects import paginate_list_objects_v2
from ..aws import s3_context

from .resolve_s3_client import resolve_s3_client

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client


class ExistsAPIMixin:
    """
    A mixin class that implements the exists test related methods.
    """

    __slots__ = ()

    def _ensure_version_id_on_file(self: S3Path, version_id: str):
        if (version_id is not OPT) and (self.is_file() is False):
            raise ValueError(
                f"version_id only applies to a file, "
                f"{self._error_label()} is not a file"
            )

    def exists(
        self: S3Path,
        version_id: str = OPT,
        s3_client: S3Client | None = None,
    ) -> bool:
        """
        Test if this path exists in S3.

        - Bucket: the bucket exists (``head_bucket``).
        - File: the object exists (``head_object``). A missing bucket, or an
          object whose latest version is a delete marker, does not exist. With
          ``version_id``, test that version instead of the latest one; a
          delete marker does not exist. When the object exists and this
          ``S3Path`` has no metadata snapshot yet, the ``head_object``
          response becomes its snapshot (see :mod:`s3pathlib.core.metadata`);
          an existing snapshot is never replaced.
        - Folder: at least one object key starts with the folder key,
          including the folder marker object itself (e.g. ``folder/``), found
          with one ``list_objects_v2`` call. A folder in a missing bucket does
          not exist.

        Example::

            S3Path("bucket").exists()
            S3Path("bucket/file.txt").exists()
            S3Path("bucket/folder/").exists()
            S3Path("bucket/file.txt").exists(version_id="v123456")

        :param version_id: the version of a file to test.

        :raises S3PathTypeError: if this path has no bucket (a relative path
            or the void path).
        :raises ValueError: if ``version_id`` is given for a bucket or a
            folder.
        :raises S3PermissionDenied: if S3 answers 403 for a bucket or a file.
        :raises botocore.exceptions.ClientError: any other error, as is; e.g.
            ``AccessDenied`` for a folder you cannot list.
        """
        self.ensure_not_relpath()
        self._ensure_version_id_on_file(version_id)
        if self.is_bucket():
            client = resolve_s3_client(s3_context, s3_client)
            return is_bucket_exists(client, self.bucket)
        elif self.is_file():
            client = resolve_s3_client(s3_context, s3_client)
            dct = head_object(
                s3_client=client,
                bucket=self.bucket,
                key=self.key,
                version_id=version_id,
                ignore_not_found=True,
            )
            if dct is None:
                return False
            else:
                # only fill an empty snapshot, see core.metadata
                if self._meta is None:
                    dct.pop("ResponseMetadata", None)
                    self._set_meta(
                        dct,
                        complete=True,
                        s3_client=s3_client,
                    )
                return True
        else:  # a folder
            client = resolve_s3_client(s3_context, s3_client)
            # any key under the folder, its folder marker included
            proxy = paginate_list_objects_v2(
                s3_client=client,
                bucket=self.bucket,
                prefix=self.key,
                batch_size=1,
                limit=1,
            )
            try:
                l = list(proxy.contents())
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchBucket":
                    return False
                else:
                    raise e
            if len(l):
                return True
            else:
                return False

    def ensure_not_exists(
        self: S3Path,
        version_id: str = OPT,
        s3_client: S3Client | None = None,
    ) -> None:
        """
        A validator method that ensures this path does not exist, see
        :meth:`exists`.

        :param version_id: the version of a file to test.

        :raises S3FileAlreadyExist: if this path is a file and it exists.
        :raises S3FolderAlreadyExist: if this path is a folder and it exists.
        :raises S3BucketAlreadyExist: if this path is a bucket and it exists.

        It also raises the errors of :meth:`exists`.
        """
        if self.exists(version_id=version_id, s3_client=s3_client):
            if self.is_bucket():
                raise exc.S3BucketAlreadyExist.make(self.uri)
            elif self.is_file():
                raise exc.S3FileAlreadyExist.make(self.uri)
            else:
                raise exc.S3FolderAlreadyExist.make(self.uri)

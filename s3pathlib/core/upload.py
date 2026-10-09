# -*- coding: utf-8 -*-

"""
Upload local files to S3.

.. _bsm: https://github.com/aws-samples/boto-session-manager-project
.. _upload_file: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/upload_file.html
"""

from __future__ import annotations

import typing as T
from pathlib import Path

from .._arg import OPT
from .._arg import remove_optional
from .metadata import explicit_s3_client
from .resolve_s3_client import resolve_s3_client
from ..better_client.upload import upload_dir
from ..type import PathType
from ..aws import s3_context

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from boto3.s3.transfer import TransferConfig
    from boto_session_manager.api import BotoSesManager
    from mypy_boto3_s3 import S3Client


class UploadAPIMixin:
    """
    A mixin class that implements upload method.
    """

    def upload_file(
        self: S3Path,
        path: PathType,
        overwrite: bool = False,
        extra_args: dict = OPT,
        callback: T.Callable[[int], T.Any] = OPT,
        config: TransferConfig = OPT,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> S3Path:
        """
        Upload a local file to this S3 object, with boto3's upload_file_
        (multipart upload for large files).

        Example::

            s3path = S3Path("bucket", "artifacts", "deployment.zip")
            s3path_new = s3path.upload_file(path="/tmp/build/deployment.zip", overwrite=True)
            print(s3path_new.size)

        :param path: the local file, a ``str`` or any ``os.PathLike`` (e.g.
            ``pathlib.Path``); a relative path is relative to the current
            directory.
        :param overwrite: if ``False`` (default), raise
            ``S3FileAlreadyExist`` and upload nothing when the object exists
            (a delete marker as the latest version counts as not existing).
            The check and the upload are not atomic: an object written by
            someone else in between is overwritten (upload_file_ does not
            support conditional writes).
        :param extra_args: ``ExtraArgs`` of upload_file_, e.g.
            ``{"ContentType": "text/plain", "Metadata": {"k": "v"}}``; boto3
            raises ``ValueError`` for a key it does not allow.
        :param callback: ``Callback`` of upload_file_, called with the number
            of bytes sent.
        :param config: ``Config`` of upload_file_, a
            ``boto3.s3.transfer.TransferConfig``.
        :param bsm: See bsm_.

        :return: a new :class:`~s3pathlib.core.s3path.S3Path` of the uploaded
            object, without metadata snapshot (the first property read loads
            it); this ``S3Path`` is not changed.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFileError: for a folder or a bucket.
        :raises FileNotFoundError: if the local file does not exist.
        :raises IsADirectoryError: if the local path is a directory.
        :raises S3FileAlreadyExist: if ``overwrite`` is ``False`` and the
            object exists.
        :raises boto3.exceptions.S3UploadFailedError: if the upload fails,
            e.g. the bucket does not exist; boto3 raises it with the
            ``ClientError`` as its ``__context__``.
        """
        self.ensure_not_relpath()
        self.ensure_object()
        # check the local file before calling AWS
        p = Path(path)
        if p.exists() is False:
            raise FileNotFoundError(f"local file '{p}' does not exist")
        if p.is_dir():
            raise IsADirectoryError(f"local path '{p}' is a directory, not a file")
        if overwrite is False:
            self.ensure_not_exists(bsm=bsm)
        s3_client = resolve_s3_client(s3_context, bsm)
        s3_client.upload_file(
            Filename=str(p.absolute()),
            Bucket=self.bucket,
            Key=self.key,
            **remove_optional(
                ExtraArgs=extra_args,
                Callback=callback,
                Config=config,
            ),
        )
        s3path = self.copy()
        # no snapshot (upload_file returns nothing), but remember the client
        # that loads it, see core.metadata
        s3path._s3_client = explicit_s3_client(s3_client, bsm)
        return s3path

    def upload_dir(
        self: S3Path,
        local_dir: PathType,
        pattern: str = "**/*",
        overwrite: bool = False,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> int:
        """
        Upload the files of a local directory and its subdirectories to this
        S3 folder (or bucket). The path of each file relative to ``local_dir``
        becomes its key under this folder. See
        :func:`s3pathlib.better_client.upload.upload_dir`.

        Example::

            s3dir = S3Path("bucket", "datalake", "orders/")
            n_files = s3dir.upload_dir(local_dir="/data/orders", pattern="**/*.csv", overwrite=True)

        :param local_dir: the local directory, a ``str`` or any
            ``os.PathLike``.
        :param pattern: which files to upload, a glob pattern relative to
            ``local_dir``, see https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob.
            Default ``"**/*"``: every file, in every subdirectory.
        :param overwrite: if ``False`` (default), check every target key
            first, and upload nothing if any of them exists (not atomic).
        :param bsm: See bsm_.

        :return: the number of files uploaded.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFolderError: for a file.

        It also raises the errors of
        :func:`s3pathlib.better_client.upload.upload_dir`.
        """
        self.ensure_not_relpath()
        self.ensure_dir()
        s3_client = resolve_s3_client(s3_context, bsm)
        return upload_dir(
            s3_client=s3_client,
            bucket=self.bucket,
            prefix=self.key,
            local_dir=local_dir,
            pattern=pattern,
            overwrite=overwrite,
        )

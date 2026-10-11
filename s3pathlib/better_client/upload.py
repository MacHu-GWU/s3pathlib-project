# -*- coding: utf-8 -*-

"""
Upload a local directory to S3.

.. _upload_file: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/upload_file.html
"""

from __future__ import annotations

import typing as T
from pathlib import Path

from .. import exc
from ..type import PathType
from ..utils import join_s3_uri
from .head_object import is_object_exists

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


def upload_dir(
    s3_client: S3Client,
    bucket: str,
    prefix: str,
    local_dir: PathType,
    pattern: str = "**/*",
    overwrite: bool = False,
) -> int:
    """
    Recursively upload the files of a local directory and its subdirectories
    to S3, with upload_file_ (multipart upload for large files). The path of
    each file relative to ``local_dir`` becomes its key under ``prefix``, with
    ``/`` as separator on every OS.

    Example::

        upload_dir(s3_client, "my-bucket", "data/", "/tmp/data")  # 3

    Only files are uploaded: an empty local directory does not create
    anything in S3.

    :param prefix: The S3 folder to upload to, e.g. ``"data/"``. A missing
        trailing ``/`` is added (``"data"`` is the same as ``"data/"``), and
        ``""`` is the root of the bucket.
    :param local_dir: The local directory, a ``str`` or any ``os.PathLike``
        (e.g. ``pathlib.Path``); a relative path is relative to the current
        directory.
    :param pattern: Which files to upload, a glob pattern relative to
        ``local_dir``, see https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob.
        Default ``"**/*"``: every file, in every subdirectory.
    :param overwrite: If False (default), check every target key first, and
        upload nothing if any of them exists. The check and the upload are not
        atomic: a key written by someone else in between is overwritten.

    :return: number of files uploaded

    :raises TypeError: if ``local_dir`` is a file.
    :raises FileNotFoundError: if ``local_dir`` does not exist.
    :raises S3FileAlreadyExist: if ``overwrite`` is False and a target key
        exists; nothing is uploaded.
    :raises boto3.exceptions.S3UploadFailedError: if an upload fails, e.g. the
        bucket does not exist; boto3 raises it with the ``ClientError`` as its
        ``__context__``. The files uploaded before it are kept.
    """
    # preprocess input arguments
    if prefix.endswith("/"):
        prefix = prefix[:-1]

    p_local_dir = Path(local_dir)

    if p_local_dir.is_file():
        raise TypeError(f"'{p_local_dir}' is a file, not a directory!")

    if p_local_dir.exists() is False:
        raise FileNotFoundError(f"'{p_local_dir}' not found!")

    if len(prefix):
        final_prefix = f"{prefix}/"
    else:
        final_prefix = ""

    # list of (local file path, target s3 key)
    todo: list[tuple[str, str]] = list()
    for p in p_local_dir.glob(pattern):
        if p.is_file():
            relative_path = p.relative_to(p_local_dir)
            key = final_prefix + "/".join(relative_path.parts)
            todo.append((str(p.absolute()), key))

    # make sure all target s3 location not exists
    if overwrite is False:
        for abspath, key in todo:
            if is_object_exists(s3_client, bucket, key) is True:
                s3_uri = join_s3_uri(bucket, key)
                raise exc.S3FileAlreadyExist.make(s3_uri)

    # execute upload
    for abspath, key in todo:
        s3_client.upload_file(abspath, bucket, key)

    return len(todo)

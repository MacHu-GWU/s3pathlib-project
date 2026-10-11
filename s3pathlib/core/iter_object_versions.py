# -*- coding: utf-8 -*-

"""
List object versions related API.

.. _ListObjectVersions: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjectVersions.html
"""

from __future__ import annotations

import typing as T

from .._arg import OPT
from ..aws import s3_context
from ..better_client.list_object_versions import paginate_list_object_versions
from .iter_objects import S3PathIterProxy
from .resolve_s3_client import resolve_s3_client

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client


class IterObjectVersionsAPIMixin:
    """
    A mixin class that implements the iter object versions methods.
    """

    __slots__ = ()

    def list_object_versions(
        self: S3Path,
        batch_size: int = 1000,
        limit: int | None = None,
        delimiter: str = OPT,
        encoding_type: str = OPT,
        expected_bucket_owner: str = OPT,
        s3_client: S3Client | None = None,
    ) -> S3PathIterProxy:
        """
        Iterate the versions and delete markers, yield :class:`S3Path` objects
        that carry their metadata (``version_id``, ``is_delete_marker()``,
        ``last_modified_at``, ...).

        - For a file: the versions of this exact key, not of other keys that
          start with it (e.g. ``file.txt.bak`` for ``file.txt``).
        - For a folder (or a bucket): the versions of every key under it,
          recursively (unless ``delimiter`` is given).

        The order is the one of S3: by key, then from the newest to the oldest
        version of each key (versions and delete markers merged by
        ``LastModified``; a version and a delete marker written in the same
        second are in no particular order). The pages are fetched while
        iterating, so a big folder is not loaded in memory.

        Example::

            for p in S3Path("bucket", "file.txt").list_object_versions():
                print(p.version_id, p.is_delete_marker(), p.last_modified_at)

        :param batch_size: Number of entries per API call, 1 to 1000.
        :param limit: Total number of versions and delete markers to return.
            ``0`` returns nothing without calling AWS. ``None`` (default): no
            limit.
        :param delimiter: See ListObjectVersions_. Folders (common prefixes)
            are not returned.
        :param encoding_type: See ListObjectVersions_.
        :param expected_bucket_owner: See ListObjectVersions_.
        :param s3_client: the boto3 S3 client to use, default the client of
            ``s3_context``.

        :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
            negative.
        """
        if limit is not None:
            if limit < 0:
                raise ValueError(f"``limit`` must not be negative, got {limit}.")
        client = resolve_s3_client(s3_context, s3_client)
        bucket = self.bucket
        if self.is_file():
            exact_key = self.key
        else:
            exact_key = None
        # ``limit`` is applied here, to the yielded paths: for a file, the
        # versions of other keys that start with it must not count
        proxy = paginate_list_object_versions(
            s3_client=client,
            bucket=bucket,
            prefix=self.key,
            batch_size=batch_size,
            delimiter=delimiter,
            encoding_type=encoding_type,
            expected_bucket_owner=expected_bucket_owner,
        )

        def _iter_s3path() -> T.Iterable[S3Path]:
            if limit is None:
                remaining = None
            else:
                remaining = limit
            if remaining == 0:
                return
            for response in proxy:
                (
                    versions,
                    delete_markers,
                    _,
                ) = proxy.extract_versions_and_delete_markers_and_common_prefixes(
                    response
                )
                s3path_list = list()
                explicit_client = s3_client
                for dct in versions:
                    s3path_list.append(
                        self._from_version_dict(bucket, dct=dct, s3_client=explicit_client)
                    )
                for dct in delete_markers:
                    s3path_list.append(
                        self._from_delete_marker(bucket, dct=dct, s3_client=explicit_client)
                    )
                # S3 order: by key, then newest first. S3 sends the versions
                # and the delete markers of a page in two lists, merge them;
                # the pages themselves come in this order.
                s3path_list.sort(key=lambda x: x.last_modified_at, reverse=True)
                s3path_list.sort(key=lambda x: x.key)
                for s3path in s3path_list:
                    if exact_key is not None:
                        if s3path.key != exact_key:
                            continue
                    yield s3path
                    if remaining is not None:
                        remaining -= 1
                        if remaining == 0:
                            return

        return S3PathIterProxy(_iter_s3path())

# -*- coding: utf-8 -*-

"""
List object versions related API.

**Design notes**

*The order is the one of S3.* S3 lists the versions and delete markers by key,
then from the newest to the oldest, and splits the pages in that order, but
each page sends them in two lists (``Versions`` and ``DeleteMarkers``). Merging
the two lists by ``LastModified`` alone is not enough: it has a one second
resolution, so an object deleted in the same second it was written has a
version and a delete marker with the same timestamp. S3 marks the newest entry
of each key with ``IsLatest``, so that entry goes first; the other ones go
newest first. The newest entry of a key is always in the first page where the
key appears, so this works page by page.

*Rejected:* listing one entry per call (``MaxKeys=1``) gives the exact order,
at the cost of one API call per version; a public ``is_latest()`` would read a
snapshot that can be stale, while the order of the iteration itself is what
callers rely on (``one()``, ``skip(1)``); sleeping between writes only hides
the problem.

.. _list_object_versions: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/list_object_versions.html
"""

from __future__ import annotations

import typing as T
import itertools

from .._arg import OPT
from ..aws import s3_context
from ..better_client._paginate import validate_limit
from ..better_client.list_object_versions import paginate_list_object_versions
from .iter_objects import S3PathIterProxy
from .resolve_s3_client import resolve_s3_client

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client


def _last_modified(p: S3Path):
    return p.last_modified_at


def _s3_order(p: S3Path) -> tuple[str, bool]:
    """
    The sort key that restores the order of S3 within a page: by key, then
    the entry S3 marks as the latest first (``False`` sorts before ``True``).
    It reads the snapshot of the listed path and never calls AWS.
    """
    is_latest = p._meta.get("IsLatest", False)
    return (p.key, is_latest is False)


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
        Iterate the versions and delete markers with list_object_versions_,
        yield :class:`S3Path` objects that carry their metadata
        (``version_id``, ``is_delete_marker()``, ``last_modified_at``, ...).

        - For a file: the versions of this exact key, not of other keys that
          start with it (e.g. ``file.txt.bak`` for ``file.txt``).
        - For a folder (or a bucket): the versions of every key under it,
          recursively (unless ``delimiter`` is given).

        The order is the one of S3: by key, then from the newest to the oldest
        version of each key. The entry S3 marks as the latest of each key
        (``IsLatest``) always comes first, e.g. the delete marker of an object
        deleted in the same second it was written. The older entries are
        merged by ``LastModified``, which has a one second resolution, so the
        older versions and delete markers written in the same second are in no
        particular order. The pages are fetched while iterating, so a big
        folder is not loaded in memory.

        Example::

            for p in S3Path("bucket", "file.txt").list_object_versions():
                print(p.version_id, p.is_delete_marker(), p.last_modified_at)

        :param batch_size: Number of entries per API call, 1 to 1000.
        :param limit: Total number of versions and delete markers to return.
            ``0`` returns nothing without calling AWS. ``None`` (default): no
            limit.
        :param delimiter: Folders (common prefixes) are not returned.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
            negative.
        :raises S3ValidationError: while iterating, if a key (or a folder) cannot be
            represented by ``S3Path``, see :mod:`s3pathlib.core.metadata`.
        """
        self.ensure_not_relpath()
        validate_limit(limit)
        client = resolve_s3_client(s3_context, s3_client)
        bucket = self.bucket
        if self.is_file():
            exact_key = self.key
        else:
            exact_key = None
        proxy = paginate_list_object_versions(
            s3_client=client,
            bucket=bucket,
            prefix=self.key,
            batch_size=batch_size,
            delimiter=delimiter,
            encoding_type=encoding_type,
            expected_bucket_owner=expected_bucket_owner,
        )

        def _iter_s3path() -> T.Iterator[S3Path]:
            for response in proxy:
                (
                    versions,
                    delete_markers,
                    _,
                ) = proxy.extract_versions_and_delete_markers_and_common_prefixes(
                    response
                )
                s3path_list = list()
                for dct in versions:
                    s3path_list.append(
                        self._from_version_dict(bucket, dct=dct, s3_client=s3_client)
                    )
                for dct in delete_markers:
                    s3path_list.append(
                        self._from_delete_marker(bucket, dct=dct, s3_client=s3_client)
                    )
                # S3 sends the versions and the delete markers of a page in
                # two lists; restore its order, see the design notes. Both
                # sorts are stable: equal timestamps keep the list order.
                s3path_list.sort(key=_last_modified, reverse=True)
                s3path_list.sort(key=_s3_order)
                for s3path in s3path_list:
                    if exact_key is not None:
                        if s3path.key != exact_key:
                            continue
                    yield s3path

        # ``limit`` is applied to the yielded paths, not passed on to S3: for a
        # file, the versions of other keys that start with it must not count
        return S3PathIterProxy(itertools.islice(_iter_s3path(), limit))

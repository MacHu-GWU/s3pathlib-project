# -*- coding: utf-8 -*-

"""
List objects related API.

The examples use this folder structure::

    s3://my-bucket/
    s3://my-bucket/README.txt (1000 bytes)
    s3://my-bucket/hard-folder/ (a folder marker)
    s3://my-bucket/hard-folder/1.txt (2000 bytes)
    s3://my-bucket/soft-folder/2.txt (3000 bytes, no folder marker)

A folder marker is the empty object ``folder/`` that "Create folder" makes in
the S3 console.

.. _list_objects_v2: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/list_objects_v2.html
"""

from __future__ import annotations

import typing as T
import itertools

from iterproxy import IterProxy

from .._arg import OPT
from .. import utils
from ..aws import s3_context
from ..better_client._paginate import validate_limit
from ..better_client.list_objects import (
    paginate_list_objects_v2,
    is_content_an_object,
    calculate_total_size,
    count_objects,
)
from .resolve_s3_client import resolve_s3_client

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client


class S3PathIterProxy(IterProxy["S3Path"]):
    """
    An iterator of :class:`S3Path`, with client side in-memory filters, see
    :class:`iterproxy.IterProxy` and :mod:`s3pathlib.core.filterable_property`.
    It can be iterated only once.
    """

    # the methods below only narrow the return types, for IDE completion

    def __next__(self) -> S3Path:
        return super(S3PathIterProxy, self).__next__()

    def one(self) -> S3Path:
        return super(S3PathIterProxy, self).one()

    def one_or_none(self) -> S3Path | None:
        return super(S3PathIterProxy, self).one_or_none()

    def many(self, k: int) -> list[S3Path]:
        return super(S3PathIterProxy, self).many(k)

    def all(self) -> list[S3Path]:
        return super(S3PathIterProxy, self).all()

    def skip(self, k: int) -> S3PathIterProxy:
        return super(S3PathIterProxy, self).skip(k=k)

    def filter_by_ext(self, *exts: str) -> S3PathIterProxy:
        """
        Keep the files whose extension is one of ``exts``, case insensitive.
        ``""`` matches the files without extension. A folder (e.g. an object
        ``data/`` that has content) never matches.

        Example::

            for p in S3Path("bucket", "folder/").iter_objects().filter_by_ext(".csv", ".json"):
                print(p)

        :raises ValueError: if no extension is given, or an extension is not
            ``""`` and does not start with ``.`` (e.g. ``"csv"``).
        """
        if len(exts) == 0:
            raise ValueError("give at least one extension, e.g. '.csv'")
        for ext in exts:
            if (ext != "") and (ext.startswith(".") is False):
                raise ValueError(
                    f"an extension starts with '.' (or is '' for no extension), "
                    f"got {ext!r}"
                )
        valid_exts = set([ext.lower() for ext in exts])

        def f(p: S3Path) -> bool:
            if p.is_file() is False:
                return False
            return p.ext.lower() in valid_exts

        return self.filter(f)


def _get_page_size(batch_size: int, limit: int | None) -> int:
    """
    The number of entries per API call: no more than ``limit`` when it is
    given (more pages are fetched if some entries are skipped).
    """
    if (limit is None) or (limit == 0):
        return batch_size
    else:
        return min(batch_size, limit)


class IterObjectsAPIMixin:
    """
    A mixin class that implements the iter objects methods.
    """

    __slots__ = ()

    def _ensure_s3_dir(self: S3Path) -> None:
        """
        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFolderError: for a file.
        """
        self.ensure_not_relpath()
        self.ensure_dir()

    def iter_objects(
        self: S3Path,
        batch_size: int = 1000,
        limit: int | None = None,
        encoding_type: str = OPT,
        fetch_owner: bool = OPT,
        start_after: str = OPT,
        request_payer: str = OPT,
        expected_bucket_owner: str = OPT,
        recursive: bool = True,
        s3_client: S3Client | None = None,
    ) -> S3PathIterProxy:
        """
        Iterate the objects under this folder (or bucket) with list_objects_v2_,
        yield :class:`S3Path` objects in the S3 order (by key). Folder markers
        are skipped; an object whose key ends with ``/`` but has content is
        yielded, as a folder ``S3Path``.

        Each path has the metadata returned by the list API (``size``,
        ``etag``, ``last_modified_at``), see :mod:`s3pathlib.core.metadata`.
        The pages are fetched while iterating, and the result can be iterated
        only once. Errors of the AWS calls (e.g. ``NoSuchBucket``) are raised
        as is when the iteration starts.

        Example::

            S3Path("s3://my-bucket/").iter_objects().all()
            # [README.txt, hard-folder/1.txt, soft-folder/2.txt]
            S3Path("s3://my-bucket/").iter_objects(recursive=False).all()
            # [README.txt]

        :param batch_size: Number of entries per API call, 1 to 1000.
        :param limit: Total number of objects to return. ``0`` returns nothing
            without calling AWS. ``None`` (default): no limit.
        :param recursive: ``True`` (default) for all the objects under this
            folder, ``False`` for the objects directly in it only (not in sub
            folders).

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFolderError: for a file.
        :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
            negative.
        """
        self._ensure_s3_dir()
        validate_limit(limit)
        client = resolve_s3_client(s3_context, s3_client)
        bucket = self.bucket
        kwargs = dict(
            s3_client=client,
            bucket=bucket,
            prefix=self.key,
            batch_size=_get_page_size(batch_size, limit),
            encoding_type=encoding_type,
            fetch_owner=fetch_owner,
            start_after=start_after,
            request_payer=request_payer,
            expected_bucket_owner=expected_bucket_owner,
        )
        if recursive is False:
            kwargs["delimiter"] = "/"
        proxy = paginate_list_objects_v2(**kwargs)

        def _iter_s3path() -> T.Iterator[S3Path]:
            for content in proxy.contents():
                if is_content_an_object(content) is False:
                    continue
                yield self._from_content_dict(
                    bucket,
                    dct=content,
                    s3_client=s3_client,
                )

        # ``limit`` is applied to the yielded paths, not passed on to S3: the
        # folder markers and the folders (common prefixes) are skipped, they
        # must not count
        return S3PathIterProxy(itertools.islice(_iter_s3path(), limit))

    def iterdir(
        self: S3Path,
        batch_size: int = 1000,
        limit: int | None = None,
        encoding_type: str = OPT,
        fetch_owner: bool = OPT,
        start_after: str = OPT,
        request_payer: str = OPT,
        expected_bucket_owner: str = OPT,
        s3_client: S3Client | None = None,
    ) -> S3PathIterProxy:
        """
        Iterate the files and the folders directly in this folder (or bucket)
        with list_objects_v2_, not recursively. Yield :class:`S3Path` objects
        in the S3 order (by key, so files and folders are mixed). The folder
        marker of this folder itself is skipped.

        A file has the metadata returned by the list API (``size``, ``etag``,
        ``last_modified_at``), see :mod:`s3pathlib.core.metadata`; a folder
        has none. The pages are fetched while iterating, and the result can be
        iterated only once. Errors of the AWS calls (e.g. ``NoSuchBucket``)
        are raised as is when the iteration starts.

        Example::

            S3Path("s3://my-bucket/").iterdir().all()
            # [README.txt, hard-folder/, soft-folder/]

        :param batch_size: Number of entries per API call, 1 to 1000.
        :param limit: Total number of files and folders to return. ``0``
            returns nothing without calling AWS. ``None`` (default): no
            limit.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFolderError: for a file.
        :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
            negative.
        """
        self._ensure_s3_dir()
        validate_limit(limit)
        client = resolve_s3_client(s3_context, s3_client)
        bucket = self.bucket
        root = self.root
        proxy = paginate_list_objects_v2(
            s3_client=client,
            bucket=bucket,
            prefix=self.key,
            batch_size=_get_page_size(batch_size, limit),
            delimiter="/",
            encoding_type=encoding_type,
            fetch_owner=fetch_owner,
            start_after=start_after,
            request_payer=request_payer,
            expected_bucket_owner=expected_bucket_owner,
        )

        def _iter_s3path() -> T.Iterator[S3Path]:
            for res in proxy:
                # S3 sends the folders and the files of a page in two lists,
                # merge them by key; the pages themselves come in key order
                entries = list()
                for dct in res.get("CommonPrefixes", list()):
                    entries.append((dct["Prefix"], root.joinpath(dct["Prefix"])))
                for dct in res.get("Contents", list()):
                    if dct["Key"] == self.key:
                        continue
                    entries.append(
                        (
                            dct["Key"],
                            self._from_content_dict(
                                bucket,
                                dct,
                                s3_client=s3_client,
                            ),
                        )
                    )
                entries.sort(key=lambda x: x[0])
                for _, s3path in entries:
                    yield s3path

        # ``limit`` is applied to the yielded paths, not passed on to S3: the
        # folder marker of this folder is skipped, it must not count
        return S3PathIterProxy(itertools.islice(_iter_s3path(), limit))

    def calculate_total_size(
        self: S3Path,
        for_human: bool = False,
        include_folder: bool = False,
        s3_client: S3Client | None = None,
    ) -> tuple[int, int | str]:
        """
        Count the objects under this folder (or bucket), recursively, and sum
        their sizes, like the "Calculate total size" action of the S3 console.

        Example::

            S3Path("s3://my-bucket/").calculate_total_size()  # (3, 6000)
            S3Path("s3://my-bucket/").calculate_total_size(for_human=True)  # (3, '5.86 KB')
            S3Path("s3://my-bucket/").calculate_total_size(include_folder=True)  # (4, 6000)

        :param for_human: if ``True``, the size is a human readable string.
        :param include_folder: if ``True``, also count the folder markers.

        :return: ``(count, total_size)``, the size in bytes (or a string with
            ``for_human=True``).

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFolderError: for a file.
        """
        self._ensure_s3_dir()
        client = resolve_s3_client(s3_context, s3_client)
        count, size = calculate_total_size(
            s3_client=client,
            bucket=self.bucket,
            prefix=self.key,
            include_folder=include_folder,
        )
        if for_human:
            size = utils.repr_data_size(size)
        return count, size

    def count_objects(
        self: S3Path,
        include_folder: bool = False,
        s3_client: S3Client | None = None,
    ) -> int:
        """
        Count the objects under this folder (or bucket), recursively.

        Example::

            S3Path("s3://my-bucket/").count_objects()  # 3
            S3Path("s3://my-bucket/").count_objects(include_folder=True)  # 4

        :param include_folder: if ``True``, also count the folder markers.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFolderError: for a file.
        """
        self._ensure_s3_dir()
        client = resolve_s3_client(s3_context, s3_client)
        return count_objects(
            s3_client=client,
            bucket=self.bucket,
            prefix=self.key,
            include_folder=include_folder,
        )

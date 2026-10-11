# -*- coding: utf-8 -*-

"""
Comparison operator implementation.

Two paths are equal if they have the same bucket, the same parts and the same
type (file or dir): ``S3Path("b", "a")`` (a file) is not ``S3Path("b", "a/")``
(a dir). Equality only looks at the path, not at the metadata loaded from S3,
so two versions of the same object are equal, and a ``set`` keeps one of them.
Use ``(p, p.version_id)`` as the key to tell versions apart.

Paths are ordered part by part, the same as ``pathlib``: a dir comes right
before its content, and the content stays together::

    >>> sorted([S3Path("b", "a-b"), S3Path("b", "a/b"), S3Path("b", "a/")])
    [S3Path('s3://b/a/'), S3Path('s3://b/a/b'), S3Path('s3://b/a-b')]

This is not the order of S3 list APIs, which sort keys as strings (``"a-b"``
comes before ``"a/b"``, because ``"-"`` is before ``"/"``). Use
``sorted(paths, key=lambda p: p.key)`` for that order. Paths without bucket
come first: void, then relative paths, then absolute paths.

Comparing with something that is not an ``S3Path`` returns ``NotImplemented``,
the same as ``pathlib``: ``==`` is ``False`` and ``<`` raises ``TypeError``.

**Design notes**

*A path is a location, the version is metadata.* Equality and hash ignore the
metadata because the metadata changes when it is loaded, which would change
the hash of a path that is already in a ``set`` or a ``dict``.

*Order is by parts, not by key string.* The key string order puts a dir
anywhere among its siblings (``"a-b"`` before ``"a/b"``); the part by part
order keeps a dir with its content, which is what a tree view needs.

*The comparison tuple.* A path is compared by a tuple: the bucket (``""``
without bucket), the parts, and ``""`` at the end for a dir. A bucket and a
part are never empty (see :mod:`s3pathlib.core.base`), so different paths
never have the same tuple. The ``""`` sorts before every part, so a dir sorts
right after the file of the same name and before its content, whatever the
names in the dir are (a marker such as ``"/"`` would sort after a name like
``"-x"``).
"""

from __future__ import annotations

import typing as T

from .base import BaseS3Path

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class ComparisonAPIMixin:
    """
    A mixin class that implements the comparison operator magic methods.
    """

    __slots__ = ()

    @property
    def _cparts(self: S3Path) -> tuple[str, ...]:
        """
        Cached comparison parts, for hashing and comparison. A tuple, like
        ``_parts``, so the cache can not be changed and is hashable as it is.
        """
        try:
            return self._cached_cparts
        except AttributeError:
            if self._bucket is None:
                bucket = ""
            else:
                bucket = self._bucket

            if self._is_dir:
                cparts = (bucket,) + self._parts + ("",)
            else:
                cparts = (bucket,) + self._parts

            self._cached_cparts = cparts
            return self._cached_cparts

    def __eq__(self: S3Path, other: object) -> bool:
        if not isinstance(other, BaseS3Path):
            return NotImplemented
        return self._cparts == other._cparts

    def __lt__(self: S3Path, other: object) -> bool:
        if not isinstance(other, BaseS3Path):
            return NotImplemented
        return self._cparts < other._cparts

    def __gt__(self: S3Path, other: object) -> bool:
        if not isinstance(other, BaseS3Path):
            return NotImplemented
        return self._cparts > other._cparts

    def __le__(self: S3Path, other: object) -> bool:
        if not isinstance(other, BaseS3Path):
            return NotImplemented
        return self._cparts <= other._cparts

    def __ge__(self: S3Path, other: object) -> bool:
        if not isinstance(other, BaseS3Path):
            return NotImplemented
        return self._cparts >= other._cparts

    def __hash__(self: S3Path) -> int:
        try:
            return self._hash
        except AttributeError:
            self._hash = hash(self._cparts)
            return self._hash

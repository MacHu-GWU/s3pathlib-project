# -*- coding: utf-8 -*-

"""
Comparison operator implementation.

**Equality and hash**

Two paths are equal if they have the same bucket, the same parts and the same
type (file or dir): ``S3Path("b", "a")`` (a file) is not ``S3Path("b", "a/")``
(a dir). Equality only looks at the path, not at the metadata loaded from S3,
so two versions of the same object are equal, and a ``set`` keeps one of them.
A path is a location, the version is metadata; it also keeps the hash stable,
because the metadata changes when it is loaded. Use ``(p, p.version_id)`` as
the key to tell versions apart.

**Order**

Paths are ordered part by part, the same as ``pathlib``, so the content of a
dir stays together right after the dir::

    >>> sorted([S3Path("b", "a-b"), S3Path("b", "a/b"), S3Path("b", "a/")])
    [S3Path('s3://b/a/'), S3Path('s3://b/a/b'), S3Path('s3://b/a-b')]

This is not the order of S3 list APIs, which sort keys as strings (``"a-b"``
comes before ``"a/"``, because ``"-"`` is before ``"/"``). Use
``sorted(paths, key=lambda p: p.key)`` for that order.

Paths without bucket come first: void, then relative paths, then absolute
paths.

**Other types**

Comparing with something that is not an ``S3Path`` returns
``NotImplemented``, the same as ``pathlib``: ``==`` is ``False`` and ``<``
raises ``TypeError``.

**How it works**

Each path is compared by a tuple: its bucket (``""`` without bucket), its
parts, and ``"/"`` at the end for a dir. Two different paths always have
different tuples, because a bucket is never empty and a part never contains
``/`` (see :mod:`s3pathlib.core.base`).
"""

from __future__ import annotations

import typing as T

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class ComparisonAPIMixin:
    """
    A mixin class that implements the comparison operator magic methods.
    """

    @property
    def _cparts(self: S3Path) -> tuple[str, ...]:
        """
        Cached comparison parts, for hashing and comparison.

        A tuple of the bucket (``""`` for a path without bucket), the parts,
        and a trailing ``"/"`` for a dir. It is a tuple, like ``_parts``, so
        the cache can not be changed and is hashable as it is.
        """
        try:
            return self._cached_cparts
        except AttributeError:
            if self._bucket is None:
                bucket = ""
            else:
                bucket = self._bucket

            if self._is_dir:
                cparts = (bucket,) + self._parts + ("/",)
            else:
                cparts = (bucket,) + self._parts

            self._cached_cparts = cparts
            return self._cached_cparts

    def __eq__(self: S3Path, other: object) -> bool:
        """
        Return ``self == other``.
        """
        if not isinstance(other, ComparisonAPIMixin):
            return NotImplemented
        return self._cparts == other._cparts

    def __lt__(self: S3Path, other: object) -> bool:
        """
        Return ``self < other``.
        """
        if not isinstance(other, ComparisonAPIMixin):
            return NotImplemented
        return self._cparts < other._cparts

    def __gt__(self: S3Path, other: object) -> bool:
        """
        Return ``self > other``.
        """
        if not isinstance(other, ComparisonAPIMixin):
            return NotImplemented
        return self._cparts > other._cparts

    def __le__(self: S3Path, other: object) -> bool:
        """
        Return ``self <= other``.
        """
        if not isinstance(other, ComparisonAPIMixin):
            return NotImplemented
        return self._cparts <= other._cparts

    def __ge__(self: S3Path, other: object) -> bool:
        """
        Return ``self >= other``.
        """
        if not isinstance(other, ComparisonAPIMixin):
            return NotImplemented
        return self._cparts >= other._cparts

    def __hash__(self: S3Path) -> int:
        """
        Return ``hash(self)``
        """
        try:
            return self._hash
        except AttributeError:
            self._hash = hash(self._cparts)
            return self._hash

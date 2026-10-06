# -*- coding: utf-8 -*-

"""
Comparison operator implementation.
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

    def __eq__(self: S3Path, other: S3Path) -> bool:
        """
        Return ``self == other``.
        """
        return self._cparts == other._cparts

    def __lt__(self: S3Path, other: S3Path) -> bool:
        """
        Return ``self < other``.
        """
        return self._cparts < other._cparts

    def __gt__(self: S3Path, other: S3Path) -> bool:
        """
        Return ``self > other``.
        """
        return self._cparts > other._cparts

    def __le__(self: S3Path, other: S3Path) -> bool:
        """
        Return ``self <= other``.
        """
        return self._cparts <= other._cparts

    def __ge__(self: S3Path, other: S3Path) -> bool:
        """
        Return ``self >= other``.
        """
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

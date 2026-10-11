# -*- coding: utf-8 -*-

"""
Relative Path implementation.

A relative path is a path without bucket. ``relative_to`` (and ``-``) is the
inverse of ``/``, see the design notes in :mod:`s3pathlib.core.joinpath`.
"""

from __future__ import annotations

import typing as T
import warnings

from .base import BaseS3Path
from ..exc import S3PathIsNotRelpathError
from ..exc import S3PathTypeError

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class RelativePathAPIMixin:
    """
    A mixin class that implements the relative path concept.
    """

    __slots__ = ()

    @classmethod
    def make_relpath(
        cls: type[S3Path],
        *parts: str | S3Path,
    ) -> S3Path:
        """
        Create a relative path from string parts or other relative paths. It
        follows the same rules as the
        :class:`~s3pathlib.core.s3path.S3Path` constructor: ``/`` is
        collapsed, empty arguments are ignored, and the last non-empty
        argument decides whether it is a file or a dir. With no parts it is
        the void path, which is neither a file nor a dir.

        Example::

            >>> S3Path.make_relpath("folder", "file.txt")
            S3RelPath('folder/file.txt')

        :raises TypeError: if a part is not a str or a relative path.
        """
        void = cls._from_parsed_parts(bucket=None, parts=(), is_dir=None)
        return cls._from_parts([void, *parts])

    def relative_to(self: S3Path, other: S3Path) -> S3Path:
        """
        Return the relative path from ``other`` to this path, the inverse of
        ``/``: ``other / self.relative_to(other) == self``. ``-`` is a syntax
        sugar for it. The same path gives the void path.

        Example::

            >>> S3Path("bucket", "a/b/c").relative_to(S3Path("bucket", "a/"))
            S3RelPath('b/c')

        Both paths are absolute paths in the same bucket, or both are relative
        paths (a relative path relative to another one).

        ``other`` should be a dir. Using a file as ``other`` (e.g.
        ``S3Path("bucket", "folder")`` without the trailing ``/``) is
        deprecated since 3.0.0: it still works, emits a ``DeprecationWarning``,
        and will raise :class:`~s3pathlib.exc.S3PathIsNotFolderError` in
        4.0.0. See :meth:`~s3pathlib.core.joinpath.JoinPathAPIMixin.joinpath`.

        :raises TypeError: if ``other`` is not an S3Path.
        :raises ValueError: if this path is not under ``other``, e.g. a
            different bucket, a sibling path, or the same parts but one is a
            file and the other a dir, so that no relative path can lead from
            ``other`` to this path.
        """
        return self._relative_to(other)

    def _relative_to(self: S3Path, other: S3Path) -> S3Path:
        """
        Implementation of :meth:`relative_to` and ``-``.
        """
        if not isinstance(other, BaseS3Path):
            raise TypeError(
                f"other has to be an S3Path, got {type(other).__name__}: {other!r}"
            )
        if self._bucket != other._bucket:
            if (self._bucket is None) or (other._bucket is None):
                raise ValueError(
                    f"{self!r} and {other!r}: both have to be absolute paths, "
                    "or both relative paths"
                )
            raise ValueError(
                f"{self!r} is not under {other!r}: they are in different buckets"
            )

        n = len(other._parts)
        if self._parts[:n] != other._parts:
            raise ValueError(f"{self!r} is not under {other!r}")

        rel_parts = self._parts[n:]
        if len(rel_parts) == 0:
            # same parts: only the same path gives the void relative path,
            # because ``other / void`` is ``other`` itself
            if self._is_dir != other._is_dir:
                raise ValueError(
                    f"{self!r} is not under {other!r}: they have the same parts, "
                    "but one is a file and the other is a dir, no relative path "
                    "leads from one to the other"
                )
            is_dir = None
        else:
            is_dir = self._is_dir

        if other.is_file():
            warnings.warn(
                f"{other!r} is a file. Using a file as the base of relative_to "
                "is deprecated since 3.0.0, and will raise "
                "S3PathIsNotFolderError in 4.0.0. Use a dir instead, "
                "e.g. end it with '/' or call .to_dir().",
                DeprecationWarning,
                stacklevel=3,  # user -> relative_to or - -> _relative_to
            )

        return self._from_parsed_parts(
            bucket=None,
            parts=rel_parts,
            is_dir=is_dir,
        )

    def is_relpath(self: S3Path) -> bool:
        """
        Test if it is a relative path, i.e. any path without bucket. The
        :meth:`void <is_void>` path is a relative path too. See
        :mod:`s3pathlib.core.base`.
        """
        return self._bucket is None

    def __sub__(self: S3Path, other: S3Path) -> S3Path:
        """
        A syntax sugar. ``s3path1 - s3path2`` is ``s3path1.relative_to(s3path2)``.
        """
        return self._relative_to(other)

    def ensure_relpath(self: S3Path) -> None:
        """
        A validator method that ensure it represents a S3 relative path.

        :raises S3PathIsNotRelpathError: if it is not a relative path.
        """
        if self.is_relpath() is not True:
            raise S3PathIsNotRelpathError.make(self.uri)

    def ensure_not_relpath(self: S3Path) -> None:
        """
        A validator method that ensure it is not a relative path, i.e. it is
        an absolute path with a bucket.

        :raises S3PathTypeError: if it is a relative path.
        """
        if self.is_relpath() is True:
            raise S3PathTypeError(
                f"{self!r} is a relative path, an absolute path is required!"
            )

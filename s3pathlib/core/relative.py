# -*- coding: utf-8 -*-

"""
Relative Path implementation.
"""

from __future__ import annotations

import typing as T
import warnings

from ..exc import S3PathIsNotRelpathError
from ..exc import S3PathTypeError

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class RelativePathAPIMixin:
    """
    A mixin class that implements the relative path concept.

    :meth:`relative_to` is the inverse of ``/``
    (:meth:`~s3pathlib.core.joinpath.JoinPathAPIMixin.joinpath`): for a dir
    ``base`` and any ``target`` under it,
    ``base / target.relative_to(base) == target``.
    """

    __slots__ = ()

    @classmethod
    def make_relpath(
        cls: type[S3Path],
        *parts: str | S3Path,
    ) -> S3Path:
        """
        A construct method that create a relative S3 Path, from string parts
        or other relative paths. It follows the same rules as the
        :class:`~s3pathlib.core.s3path.S3Path` constructor: ``/`` is
        collapsed, empty arguments are ignored, and the last non-empty
        argument decides whether it is a file or a dir.

        Example::

            >>> S3Path.make_relpath("folder", "file.txt")
            S3RelPath('folder/file.txt')
            >>> S3Path.make_relpath("folder/")
            S3RelPath('folder/')
            >>> S3Path.make_relpath()
            S3VoidPath()

        A relative path has no bucket. With no parts it is the void path, which
        is neither a file nor a dir. See :mod:`s3pathlib.core.base`.

        **中文文档**

        相对路径的概念是 p1 + p2 = p3, 其中 p1 和 p3 都是实际存在的路径, 而 p2 则是
        相对路径.

        相对路径的功能是如果 p3 - p1 = p2, 那么 p1 + p2 必须还能等于 p3. 有一个特殊情况是
        如果 p1 - p1 = p0, 两个相同的绝对路径之间的相对路径是 p0, 我们还是需要满足
        p1 + p0 = p1 以保证逻辑上的一致.

        :raises TypeError: if a part is not a str or a relative path.
        """
        void = cls._from_parsed_parts(bucket=None, parts=(), is_dir=None)
        return cls._from_parts([void, *parts])

    def relative_to(self: S3Path, other: S3Path) -> S3Path:
        """
        Return the relative path from ``other`` to this path, the inverse of
        ``/``: ``other / self.relative_to(other) == self``.

        ``-`` is a syntax sugar for ``relative_to``. See more information at
        :meth:`~RelativePathAPIMixin.__sub__`.

        Examples::

            >>> S3Path("bucket", "a/b/c").relative_to(S3Path("bucket", "a/"))
            S3RelPath('b/c')

            >>> S3Path("bucket", "a/b/").relative_to(S3Path("bucket"))
            S3RelPath('a/b/')

            >>> S3Path("bucket", "a/").relative_to(S3Path("bucket", "a/"))
            S3VoidPath()

            >>> S3Path("bucket") / S3Path("new_bucket/file.txt").relative_to(S3Path("new_bucket"))
            S3Path('s3://bucket/file.txt')

        Both paths are absolute paths in the same bucket, or both are relative
        paths (a relative path relative to another one).

        ``other`` should be a dir. Using a file as ``other`` (e.g.
        ``S3Path("bucket", "folder")`` without the trailing ``/``) is
        deprecated since 3.0.0: it still works, emits a ``DeprecationWarning``,
        and will raise :class:`~s3pathlib.exc.S3PathIsNotFolderError` in
        4.0.0. See :meth:`~s3pathlib.core.joinpath.JoinPathAPIMixin.joinpath`.

        :param other: other :class:`S3Path` instance.

        :return: a relative path object, which is a special version of S3Path

        :raises TypeError: if ``other`` is not an S3Path.
        :raises ValueError: if this path is not under ``other``, e.g. a
            different bucket, a sibling path, or the same parts but one is a
            file and the other a dir, so that no relative path can lead from
            ``other`` to this path.
        """
        return self._relative_to(other)

    def _relative_to(self: S3Path, other: S3Path) -> S3Path:
        """
        Implementation of :meth:`relative_to` and ``-``. Both call it directly,
        so the deprecation warning (``stacklevel=3``) points at the user's line.
        """
        if not isinstance(other, RelativePathAPIMixin):
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
                stacklevel=3,
            )

        return self._from_parsed_parts(
            bucket=None,
            parts=rel_parts,
            is_dir=is_dir,
        )

    def is_relpath(self: S3Path) -> bool:
        """
        Relative path is a special path supposed to join with other concrete
        path.

        **Definition**

        A long full path relating to its parent directory is a relative path.
        A :meth:`void <is_void>` path also a special relative path. In other
        words, any path without bucket, see :mod:`s3pathlib.core.base`.
        """
        return self._bucket is None

    def __sub__(self: S3Path, other: S3Path) -> S3Path:
        """
        A syntax sugar. Basically ``s3path1 - s3path2`` is equal to
        ``s3path1.relative_to(s3path2)``.

        Example::

            >>> S3Path("bucket", "a/b/c") - S3Path("bucket", "a/")
            S3RelPath('b/c')
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

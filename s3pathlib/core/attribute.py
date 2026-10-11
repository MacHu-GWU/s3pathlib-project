# -*- coding: utf-8 -*-

"""
S3Path property methods.
"""

from __future__ import annotations

import typing as T

from .base import BaseS3Path
from .filterable_property import FilterableProperty
from ..exc import S3PathIsNotFileError
from ..exc import S3PathIsNotFolderError
from ..exc import S3PathTypeError

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


def _split_basename(basename: str) -> tuple[str, str]:
    """
    Split a file name into the name and the last extension, the same as
    ``pathlib``: a leading dot (``.env``) and a trailing dot (``a.``) do not
    start an extension.
    """
    i = basename.rfind(".")
    if 0 < i < len(basename) - 1:
        return basename[:i], basename[i:]
    else:
        return basename, ""


class AttributeAPIMixin:
    """
    A mixin class that implements the property methods.
    """

    __slots__ = ()

    @property
    def parent(self: S3Path) -> S3Path:
        """
        Return the parent dir. It is always a dir, except for the parent of a
        single part relative path, which is the void path (the same as
        ``PurePosixPath("a").parent`` is ``"."``). A bucket root and void have
        no parent, they return themselves.

        Example::

            >>> S3Path("my-bucket", "my-folder", "my-file.json").parent
            S3Path('s3://my-bucket/my-folder/')
        """
        if len(self._parts) == 0:
            return self
        parts = self._parts[:-1]
        if (self._bucket is None) and len(parts) == 0:
            is_dir = None  # void
        else:
            is_dir = True
        return self._from_parsed_parts(
            bucket=self._bucket,
            parts=parts,
            is_dir=is_dir,
        )

    @property
    def parents(self: S3Path) -> list[S3Path]:
        """
        The logical ancestors of the path, from the nearest to the farthest,
        the same as ``pathlib.PurePath.parents``: an absolute path ends with
        its bucket root, a relative path ends with the void path, and a bucket
        root and the void path have no parents.

        Example::

            >>> S3Path.make_relpath("a/b/c").parents
            [S3RelPath('a/b/'), S3RelPath('a/'), S3VoidPath()]
        """
        parents = list()
        path = self
        while len(path._parts):
            path = path.parent
            parents.append(path)
        return parents

    def is_parent_of(self: S3Path, other: S3Path) -> bool:
        """
        Test if it is the parent dir, or a grand-grand-... parent dir, of
        another path, i.e. it is in ``other.parents``. A dir is not its own
        parent, except a bucket root and the void path, which are their own
        parent. A path in another bucket, or an absolute path and a relative
        path, is never a parent.

        Example::

            >>> S3Path("bucket").is_parent_of(S3Path("bucket/folder/file.txt"))
            True

        :raises S3PathIsNotFolderError: if this path is a file, a file can not
            be a parent.
        :raises TypeError: if ``other`` is not an S3Path.
        """
        if not isinstance(other, BaseS3Path):
            raise TypeError(
                f"other has to be an S3Path, got {type(other).__name__}: {other!r}"
            )
        if self.is_file():
            raise S3PathIsNotFolderError(
                f"{self._error_label()} is a file, it can not be a parent dir!"
            )
        if self._bucket != other._bucket:
            return False
        if len(other._parts) == 0:
            return self == other
        n = len(self._parts)
        return (n < len(other._parts)) and (other._parts[:n] == self._parts)

    def is_prefix_of(self: S3Path, other: S3Path) -> bool:
        """
        Test if its key is a prefix of the key of another path in the same
        bucket. It is a string prefix, the same as the ``Prefix`` of the S3
        list APIs, so ``a`` is a prefix of ``ab``, and a path is a prefix of
        itself. Use :meth:`is_parent_of` to test the dir hierarchy. A path in
        another bucket, or an absolute path and a relative path, is never a
        prefix.

        Example::

            >>> S3Path("bucket/data").is_prefix_of(S3Path("bucket/data-2024.csv"))
            True

        :raises TypeError: if ``other`` is not an S3Path.
        """
        if not isinstance(other, BaseS3Path):
            raise TypeError(
                f"other has to be an S3Path, got {type(other).__name__}: {other!r}"
            )
        if self._bucket != other._bucket:
            return False
        return other.key.startswith(self.key)

    @FilterableProperty
    def basename(self: S3Path) -> str:
        """
        The file name with extension, or the last folder name for a dir. A
        bucket root and void have no name, they return ``""``.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").basename
            'file.txt'
        """
        if len(self._parts):
            return self._parts[-1]
        else:
            return ""

    @FilterableProperty
    def dirname(self: S3Path) -> str:
        """
        The basename of the parent dir; ``""`` for the bucket root.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").dirname
            'folder'
        """
        return self.parent.basename

    @FilterableProperty
    def fname(self: S3Path) -> str:
        """
        The file name minus its last extension. Only for a file. A leading dot
        is part of the name, the same as ``pathlib.PurePath.stem``.

        Example::

            >>> S3Path("bucket", "archive.tar.gz").fname
            'archive.tar'

        :raises S3PathIsNotFileError: if it is not a file.
        """
        self._ensure_file_for("fname")
        return _split_basename(self.basename)[0]

    @FilterableProperty
    def ext(self: S3Path) -> str:
        """
        The last extension of the file name, or ``""``. Only for a file. The
        same as ``pathlib.PurePath.suffix``.

        Example::

            >>> S3Path("bucket", "archive.tar.gz").ext
            '.gz'

        :raises S3PathIsNotFileError: if it is not a file.
        """
        self._ensure_file_for("ext")
        return _split_basename(self.basename)[1]

    def _ensure_file_for(self: S3Path, attribute: str) -> None:
        """
        ``fname`` and ``ext`` only exist for a file.
        """
        if self.is_file() is False:
            raise S3PathIsNotFileError(
                f"{self._error_label()} is not a file, it has no {attribute}!"
            )

    @FilterableProperty
    def abspath(self: S3Path) -> str:
        """
        The Unix styled absolute path from the bucket, which works like a root
        drive. It is ``"/" + key``.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").abspath
            '/folder/file.txt'

        :raises S3PathTypeError: if it has no bucket (a relative path or void).
        """
        self._ensure_bucket_for("abspath")
        return "/" + self.key

    @FilterableProperty
    def dirpath(self: S3Path) -> str:
        """
        The :attr:`abspath` of the parent dir.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").dirpath
            '/folder/'

        :raises S3PathTypeError: if it has no bucket (a relative path or void).
        """
        self._ensure_bucket_for("dirpath")
        return self.parent.abspath

    @property
    def root(self: S3Path) -> S3Path:
        """
        Return the bucket root of this path.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").root
            S3Path('s3://bucket/')

        :raises S3PathTypeError: if it has no bucket (a relative path or void).
        """
        self._ensure_bucket_for("root")
        return self._from_parsed_parts(
            bucket=self._bucket,
            parts=(),
            is_dir=True,
        )

    def _ensure_bucket_for(self: S3Path, attribute: str) -> None:
        """
        ``abspath``, ``dirpath`` and ``root`` only exist for a path with a
        bucket.
        """
        if self._bucket is None:
            raise S3PathTypeError(
                f"{self._error_label()} has no bucket, it has no {attribute}!"
            )

    def __repr__(self: S3Path):
        """
        Not meant to be evaluated back; ``str(p)`` is the same as ``repr(p)``.
        Use :attr:`uri` for the S3 URI.

        Example::

            >>> S3Path.make_relpath("folder/")
            S3RelPath('folder/')
        """
        if self.is_void():
            return "S3VoidPath()"
        elif self.is_relpath():
            return f"S3RelPath({self.key!r})"
        else:  # bucket, folder or object
            return f"{self.__class__.__name__}({self.uri!r})"

    def __str__(self: S3Path):
        return self.__repr__()

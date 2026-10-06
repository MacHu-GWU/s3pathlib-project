# -*- coding: utf-8 -*-

"""
S3Path property methods.
"""

from __future__ import annotations

import typing as T

from .filterable_property import FilterableProperty
from ..exc import S3PathIsNotFileError
from ..exc import S3PathIsNotFolderError
from ..exc import S3PathTypeError

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class AttributeAPIMixin:
    """
    A mixin class that implements the property methods.
    """

    @property
    def parent(self: S3Path) -> S3Path:
        """
        Return the parent s3 directory.

        - if current object is on s3 bucket root directory, it returns bucket
            root directory
        - it is always a directory (``s3path.is_dir() is True``), except for
            the parent of a single part relative path, which is the void path
            (the same as ``PurePosixPath("a").parent`` is ``"."``)
        - if it is already s3 bucket root directory or void, it returns itself

        Examples::

            >>> S3Path("my-bucket", "my-folder", "my-file.json").parent.uri
            's3://my-bucket/my-folder/'

            >>> S3Path("my-bucket", "my-folder", "my-subfolder/").parent.uri
            's3://my-bucket/my-folder/'

            >>> S3Path("my-bucket", "my-folder").parent.uri
            's3://my-bucket/'

            >>> S3Path("my-bucket", "my-file.json").parent.uri
            's3://my-bucket/'

            >>> S3Path.make_relpath("a/b").parent
            S3RelPath('a/')

            >>> S3Path.make_relpath("a").parent
            S3VoidPath()
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
        the same as ``pathlib.PurePath.parents``.

        - an absolute path ends with its bucket root
        - a relative path ends with the void path, the same as
            ``PurePosixPath("a/b").parents`` ends with ``"."``
        - a bucket root and the void path have no parents

        Examples::

            >>> S3Path("my-bucket", "my-folder", "my-file.json").parents
            [S3Path('s3://my-bucket/my-folder/'), S3Path('s3://my-bucket/')]

            >>> S3Path.make_relpath("a/b/c").parents
            [S3RelPath('a/b/'), S3RelPath('a/'), S3VoidPath()]

            >>> S3Path("my-bucket").parents
            []
        """
        parents = list()
        path = self
        while len(path._parts):
            path = path.parent
            parents.append(path)
        return parents

    def is_parent_of(self: S3Path, other: S3Path) -> bool:
        """
        Test if it is the parent directory or grand-grand-... parent directory
        of another one, i.e. it is in ``other.parents``.

        Examples::

            # is parent
            >>> S3Path("bucket").is_parent_of(S3Path("bucket/folder/"))
            True

            # is grand parent
            >>> S3Path("bucket").is_parent_of(S3Path("bucket/folder/file.txt"))
            True

            # a dir is not its own parent
            >>> S3Path("bucket/folder/").is_parent_of(S3Path("bucket/folder/"))
            False

            # but the bucket root's parent is itself, see :attr:`parent`
            >>> S3Path("bucket").is_parent_of(S3Path("bucket"))
            True

            # relative paths, void is the parent of every relative path
            >>> S3Path.make_relpath("a/").is_parent_of(S3Path.make_relpath("a/b/c"))
            True

        A path in another bucket, or an absolute path and a relative path, is
        never a parent.

        :raises S3PathIsNotFolderError: if this path is a file, a file can not
            be a parent.
        :raises TypeError: if ``other`` is not an S3Path.
        """
        if not isinstance(other, AttributeAPIMixin):
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
            # a bucket root (or void) is its own parent
            return self == other
        return self in other.parents

    def is_prefix_of(self: S3Path, other: S3Path) -> bool:
        """
        Test if its key is a prefix of the key of another one, in the same
        bucket. It is a string prefix, the same as the ``Prefix`` of the S3
        list APIs, so ``a`` is a prefix of ``ab``, and a path is a prefix of
        itself. Use :meth:`is_parent_of` to test the dir hierarchy.

        Example::

            >>> S3Path("bucket/folder/").is_prefix_of(S3Path("bucket/folder/file.txt"))
            True

            >>> S3Path("bucket/folder/").is_prefix_of(S3Path("bucket/folder/"))
            True

            >>> S3Path("bucket/data").is_prefix_of(S3Path("bucket/data-2024.csv"))
            True

            >>> S3Path("bucket/b").is_prefix_of(S3Path("bucket/c"))
            False

        A path in another bucket, or an absolute path and a relative path, is
        never a prefix.

        :raises TypeError: if ``other`` is not an S3Path.
        """
        if not isinstance(other, AttributeAPIMixin):
            raise TypeError(
                f"other has to be an S3Path, got {type(other).__name__}: {other!r}"
            )
        if self._bucket != other._bucket:
            return False
        return other.key.startswith(self.key)

    @FilterableProperty
    def basename(self: S3Path) -> str:
        """
        The file name with extension, or the last folder name if it is a
        directory. A bucket root and void have no name, it returns ``""``.

        Logically: dirname + basename = abspath

        Example::

            # s3 object
            >>> S3Path("bucket", "folder", "file.txt").basename
            'file.txt'

            # s3 directory
            >>> S3Path("bucket", "folder/").basename
            'folder'

            # s3 bucket
            >>> S3Path("bucket").basename
            ''

            # void path
            >>> S3Path().basename
            ''

            # relative path
            >>> S3Path.make_relpath("folder", "file.txt").basename
            'file.txt'
        """
        if len(self._parts):
            return self._parts[-1]
        else:
            return ""

    @FilterableProperty
    def dirname(self: S3Path) -> str:
        """
        The basename of it's parent directory.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").dirname
            'folder'

            # root dir name is ''
            >>> S3Path("bucket", "folder").dirname
            ''
        """
        return self.parent.basename

    @FilterableProperty
    def fname(self: S3Path) -> str:
        """
        The final path component, minus its last suffix (file extension).
        Only for a file. A leading dot is part of the name, the same as
        ``pathlib.PurePath.stem``.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").fname
            'file'
            >>> S3Path("bucket", "archive.tar.gz").fname
            'archive.tar'
            >>> S3Path("bucket", ".env").fname
            '.env'

        :raises S3PathIsNotFileError: if it is not a file.
        """
        self._ensure_file_for("fname")
        basename = self.basename
        i = basename.rfind(".")
        if 0 < i < len(basename) - 1:
            return basename[:i]
        else:
            return basename

    @FilterableProperty
    def ext(self: S3Path) -> str:
        """
        The final component's last suffix, if any. Usually it is the file
        extension. Only for a file. The same as ``pathlib.PurePath.suffix``.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").ext
            '.txt'
            >>> S3Path("bucket", "archive.tar.gz").ext
            '.gz'
            >>> S3Path("bucket", "README").ext
            ''

        :raises S3PathIsNotFileError: if it is not a file.
        """
        self._ensure_file_for("ext")
        basename = self.basename
        i = basename.rfind(".")
        if 0 < i < len(basename) - 1:
            return basename[i:]
        else:
            return ""

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
        The Unix styled absolute path from the bucket. You can think of the
        bucket as a root drive. It is ``"/" + key``.

        Example::

            # s3 object
            >>> S3Path("bucket", "folder", "file.txt").abspath
            '/folder/file.txt'

            # s3 directory
            >>> S3Path("bucket", "folder/").abspath
            '/folder/'

            # s3 bucket
            >>> S3Path("bucket").abspath
            '/'

        :raises S3PathTypeError: if it has no bucket (a relative path or void).
        """
        self._ensure_bucket_for("abspath")
        return "/" + self.key

    @FilterableProperty
    def dirpath(self: S3Path) -> str:
        """
        The Unix styled absolute path from the bucket of the **parent directory**.

        Example::

            # s3 object
            >>> S3Path("bucket", "folder", "file.txt").dirpath
            '/folder/'

            # s3 directory
            >>> S3Path("bucket", "folder/").dirpath
            '/'

            # s3 bucket
            >>> S3Path("bucket").dirpath
            '/'

        :raises S3PathTypeError: if it has no bucket (a relative path or void).
        """
        self._ensure_bucket_for("dirpath")
        return self.parent.abspath

    @property
    def root(self: S3Path) -> S3Path:
        """
        Return the S3 Bucket root folder S3Path object.

        Example::

            # s3 object
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
        You cannot use the returned string of __repr__ to recover the original
        S3Path method. ``str(p)`` is the same as ``repr(p)``; use :attr:`uri`
        for the S3 URI.

        Example::

            >>> S3Path("bucket", "folder/")
            S3Path('s3://bucket/folder/')
            >>> S3Path.make_relpath("folder/")
            S3RelPath('folder/')
            >>> S3Path()
            S3VoidPath()
        """
        if self.is_void():
            return "S3VoidPath()"
        elif self.is_relpath():
            return f"S3RelPath({self.key!r})"
        else:  # bucket, folder or object
            return f"{self.__class__.__name__}('{self.uri}')"

    def __str__(self: S3Path):
        return self.__repr__()

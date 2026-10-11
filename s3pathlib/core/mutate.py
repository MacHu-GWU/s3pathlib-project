# -*- coding: utf-8 -*-

"""
S3Path object mutation implementation.
"""

from __future__ import annotations

import typing as T

from .. import exc

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class MutateAPIMixin:
    """
    A mixin class that implements the S3Path object mutation.
    """

    __slots__ = ()

    def copy(self: S3Path) -> S3Path:
        """
        Create a copy of S3Path object that logically equals to this one,
        but is actually different identity in memory. Also, the cache data
        (the metadata loaded from S3) are cleared.

        Example::

            >>> p1 = S3Path("bucket", "folder", "file.txt")
            >>> p2 = p1.copy()
            >>> p1 == p2
            True
            >>> p1 is p2
            False
        """
        return self._from_parsed_parts(
            bucket=self._bucket,
            parts=self._parts,
            is_dir=self._is_dir,
        )

    def change(
        self: S3Path,
        new_bucket: str | None = None,
        new_abspath: str | None = None,
        new_dirpath: str | None = None,
        new_dirname: str | None = None,
        new_basename: str | None = None,
        new_fname: str | None = None,
        new_ext: str | None = None,
    ) -> S3Path:
        """
        Create a new S3Path by replacing part of the attributes. If no argument
        is given, it behaves like :meth:`copy`.

        Take ``s3://bucket/folder/subfolder/file.txt`` as an example:

        - bucket: ``bucket``
        - abspath (the whole key): ``folder/subfolder/file.txt``
        - dirpath (the key of the parent dir): ``folder/subfolder/``
        - dirname (the name of the parent dir): ``subfolder``
        - basename (the last part): ``file.txt``
        - fname (basename without extension): ``file``
        - ext (the last extension): ``.txt``

        Example::

            >>> s3path = S3Path("bucket", "folder", "file.txt")
            >>> s3path.change(new_bucket="new-bucket")
            S3Path('s3://new-bucket/folder/file.txt')
            >>> s3path.change(new_basename="data.json")
            S3Path('s3://bucket/folder/data.json')
            >>> s3path.change(new_fname="log")
            S3Path('s3://bucket/folder/log.txt')
            >>> s3path.change(new_dirname="archive", new_ext=".json")
            S3Path('s3://bucket/archive/file.json')

            # a dir keeps being a dir
            >>> S3Path("bucket", "folder/").change(new_bucket="new-bucket")
            S3Path('s3://new-bucket/folder/')

        The arguments are applied in this order:

        1. ``new_bucket`` replaces the bucket. On a relative path, it gives an
           absolute path.
        2. ``new_abspath`` replaces the whole key. It can only be used with
           ``new_bucket``.
        3. Otherwise the parent dir and the last part are replaced separately:

           - the parent dir: ``new_dirpath`` replaces all of it,
             ``new_dirname`` only its name; pass at most one of them.
           - the last part: ``new_basename`` replaces it, and its trailing
             ``/`` decides whether the result is a file or a dir. Or
             ``new_fname`` and / or ``new_ext`` replace the name and the
             extension of a file. If none is given, the last part and the
             type are kept.

        :param new_bucket: the new bucket name.
        :param new_abspath: the new key, e.g. ``"folder/file.txt"``; a trailing
            ``/`` makes it a dir.
        :param new_dirpath: the new key of the parent dir, e.g.
            ``"folder/subfolder/"``; ``""`` moves it to the bucket root.
        :param new_dirname: the new name of the parent dir.
        :param new_basename: the new last part, e.g. ``"data.json"``, or
            ``"data/"`` for a dir. It can not be empty.
        :param new_fname: the new file name without extension. Only for a
            file, and it can not contain ``/``.
        :param new_ext: the new extension, empty or starting with ``.``, e.g.
            ``".json"``. Only for a file, and it can not contain ``/``.

        :raises ValueError: if the arguments conflict, or one of them is not
            valid for this path (see above).
        """
        # 1. the bucket; a path without bucket starts from void
        if new_bucket is None:
            bucket = self._bucket
        else:
            bucket = new_bucket
        if bucket is None:
            first = self._from_parsed_parts(bucket=None, parts=(), is_dir=None)
        else:
            first = bucket

        # 2. the whole key
        if new_abspath is not None:
            conflicts = list()
            for name, value in [
                ("new_dirpath", new_dirpath),
                ("new_dirname", new_dirname),
                ("new_basename", new_basename),
                ("new_fname", new_fname),
                ("new_ext", new_ext),
            ]:
                if value is not None:
                    conflicts.append(name)
            if conflicts:
                raise ValueError(
                    "new_abspath replaces the whole key, "
                    f"it can not be used with {', '.join(conflicts)}"
                )
            return self._from_parts([first, new_abspath])

        # 3.1 the parent dir
        if (new_dirpath is not None) and (new_dirname is not None):
            raise ValueError("pass new_dirpath or new_dirname, not both")
        if new_dirpath is not None:
            dir_parts = [new_dirpath]
        elif new_dirname is not None:
            if len(self._parts) < 2:
                raise ValueError(
                    f"{self!r} has no parent dir to rename, "
                    "use new_dirpath to put it in a dir"
                )
            dir_parts = list(self._parts[:-2]) + [new_dirname]
        else:
            dir_parts = list(self._parts[:-1])

        # 3.2 the last part
        if new_basename is not None:
            if (new_fname is not None) or (new_ext is not None):
                raise ValueError(
                    "pass new_basename, or new_fname / new_ext, not both"
                )
            if new_basename == "":
                raise ValueError("new_basename can not be empty")
            last = new_basename
        elif (new_fname is not None) or (new_ext is not None):
            if self.is_file() is False:
                raise ValueError(
                    f"new_fname and new_ext only work on a file, {self!r} is not a file"
                )
            if new_fname is None:
                new_fname = self.fname
            elif "/" in new_fname:
                raise ValueError(f"new_fname can not contain '/', got {new_fname!r}")
            if new_ext is None:
                new_ext = self.ext
            elif "/" in new_ext:
                raise ValueError(f"new_ext can not contain '/', got {new_ext!r}")
            elif new_ext and ((not new_ext.startswith(".")) or (new_ext == ".")):
                raise ValueError(
                    f"new_ext has to be empty, or '.' followed by the extension, got {new_ext!r}"
                )
            last = new_fname + new_ext
            if last == "":
                raise ValueError("new_fname and new_ext make an empty file name")
        elif len(self._parts):
            if self._is_dir:
                last = self._parts[-1] + "/"
            else:
                last = self._parts[-1]
        else:
            # a bucket root or void has no last part
            last = ""

        return self._from_parts([first] + dir_parts + [last])

    def to_dir(self: S3Path) -> S3Path:
        """
        Convert the S3Path to a directory. If the S3Path is a file, then append
        a "/" at the end. If the S3Path is already a directory, then do nothing.

        Example::

            >>> S3Path.from_s3_uri("s3://bucket/folder").to_dir()
            S3Path('s3://bucket/folder/')

        :raises ValueError: if it is the void path, which is neither a file
            nor a dir.
        """
        if self.is_dir():
            return self.copy()
        elif self.is_file():
            return self._from_parsed_parts(
                bucket=self._bucket,
                parts=self._parts,
                is_dir=True,
            )
        else:
            raise ValueError(f"{self!r} is neither a file nor a dir, it can not be converted to a dir")

    def to_file(self: S3Path) -> S3Path:
        """
        Convert the S3Path to a file. If the S3Path is a directory, then strip
        out the last "/". If the S3Path is already a file, then do nothing.

        A bucket root can not be a file, it raises
        :class:`~s3pathlib.exc.S3PathIsNotFileError`.

        Example::

            >>> S3Path.from_s3_uri("s3://bucket/file/").to_file()
            S3Path('s3://bucket/file')

        :raises S3PathIsNotFileError: if it is a bucket root.
        :raises ValueError: if it is the void path, which is neither a file
            nor a dir.
        """
        if self.is_file():
            return self.copy()
        elif self.is_bucket():
            raise exc.S3PathIsNotFileError(
                f"{self.uri!r} is a bucket root, it can not be converted to a file!"
            )
        elif self.is_dir():
            return self._from_parsed_parts(
                bucket=self._bucket,
                parts=self._parts,
                is_dir=False,
            )
        else:
            raise ValueError(f"{self!r} is neither a file nor a dir, it can not be converted to a file")

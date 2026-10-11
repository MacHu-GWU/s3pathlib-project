# -*- coding: utf-8 -*-

"""
Join path operator implementation.
"""

from __future__ import annotations

import typing as T
import warnings

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class JoinPathAPIMixin:
    """
    A mixin class that implements the join path operator.

    ``/`` and :meth:`~JoinPathAPIMixin.joinpath` put key parts *under* a dir.
    Joining onto a file is deprecated, see :meth:`~JoinPathAPIMixin.joinpath`.
    """

    __slots__ = ()

    def joinpath(self: S3Path, *other: str | S3Path) -> S3Path:
        """
        Join this dir with string parts or relative paths. The same as
        ``S3Path(self, *other)``: ``/`` is collapsed, empty arguments are
        ignored, and the last non-empty argument decides whether the result is
        a file or a dir.

        Example::

            # join with string parts
            >>> p = S3Path("bucket")
            >>> p.joinpath("folder", "file.txt")
            S3Path('s3://bucket/folder/file.txt')

            # join with relative path or string parts
            >>> relpath = S3Path("my-bucket", "data", "folder/").relative_to(S3Path("my-bucket", "data/"))
            >>> p.joinpath("data", relpath, "file.txt")
            S3Path('s3://bucket/data/folder/file.txt')

        This path should be a dir (a bucket, a folder ending with ``/``, a
        relative dir, or void). Joining onto a file, e.g.
        ``S3Path("bucket", "folder").joinpath("file.txt")``, is deprecated since
        3.0.0: it still works, emits a ``DeprecationWarning``, and will raise
        :class:`~s3pathlib.exc.S3PathIsNotFolderError` in 4.0.0. Use
        ``S3Path("bucket", "folder/")``, call :meth:`to_dir` first, or join all
        parts at once: ``S3Path("bucket").joinpath("folder", "file.txt")``.

        :param other: many string or relative path

        :raises TypeError: if a part is not a str or a relative path.
        """
        return self._joinpath(other)

    def _joinpath(self: S3Path, other: T.Iterable[str | S3Path]) -> S3Path:
        """
        Implementation of :meth:`joinpath` and ``/``. Both call it directly, so
        the deprecation warning (``stacklevel=3``) points at the user's line.
        """
        result = self._from_parts([self, *other])
        # joining nothing (e.g. "" or void) onto a file is fine, it is the file
        if self.is_file() and (result != self):
            warnings.warn(
                f"{self!r} is a file. Joining onto a file is deprecated since "
                "3.0.0, and will raise S3PathIsNotFolderError in 4.0.0. Join "
                "onto a dir instead: end the folder with '/' "
                '(e.g. ... / "folder/" / "file.txt"), call .to_dir() first, '
                'or join all parts at once (e.g. .joinpath("folder", "file.txt")).',
                DeprecationWarning,
                stacklevel=3,
            )
        return result

    def __truediv__(
        self: S3Path, other: str | S3Path | list[str | S3Path]
    ) -> S3Path:
        """
        A syntax sugar. ``s3path / part`` is ``s3path.joinpath(part)``, and
        ``s3path / [part1, part2]`` is ``s3path.joinpath(part1, part2)``.

        Example::

            >>> S3Path("bucket") / "folder/" / "file.txt"
            S3Path('s3://bucket/folder/file.txt')

            >>> S3Path("bucket") / ["folder", "file.txt"]
            S3Path('s3://bucket/folder/file.txt')

            # relative path also work
            >>> S3Path("new-bucket") / (S3Path("bucket/file.txt").relative_to(S3Path("bucket")))
            S3Path('s3://new-bucket/file.txt')

        Each ``/`` joins onto the result of the previous one, so in a chain
        every part but the last has to be a dir: write
        ``S3Path("bucket") / "folder/" / "file.txt"``, not
        ``S3Path("bucket") / "folder" / "file.txt"`` (deprecated, see
        :meth:`joinpath`).
        """
        if isinstance(other, list):
            return self._joinpath(other)
        else:
            return self._joinpath([other])

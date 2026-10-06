# -*- coding: utf-8 -*-

"""
The base constructor of S3Path object.
"""

from __future__ import annotations

import typing as T

from .filterable_property import FilterableProperty
from .. import utils

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class BaseS3Path:
    """
    Similar to ``pathlib.Path``. An object-oriented programming interface
    for AWS S3 object or logical directory.

    You can use this class in different way.

    1. pure s3 object / directory path manipulation without actually
        talking to AWS API.
    2. get metadata of an object, count objects, get statistics information
        of a directory
    3. enhanced s3 API that do: :meth:`upload_file <upload_file>`,
        :meth:`upload_dir <upload_dir>`,
        :meth:`copy <copy_to>` a file or directory,
        :meth:`move <move_to>` a file or directory,
        :meth:`delete <delete>`  a file or directory,
        :meth:`iter_objects <iter_objects>` from a prefix.

    **Constructor**

    The :class:`S3Path` itself is a constructor. It takes ``str`` and other
    relative :class:`S3Path` as arguments.

    1. The first argument defines the S3 bucket
    2. The rest of arguments defines the path parts of the S3 key
    3. The final argument defines the type whether is a file (object) or
        a directory. Empty arguments (``""`` or a void path) are ignored, so
        the last non-empty argument decides the type.

    The first argument can also be an S3 URI (``s3://...``) or an S3 ARN
    (``arn:{partition}:s3:::...``). The constructor only checks the format
    (well formed URI / ARN, non-empty bucket); it does not check bucket naming
    rules, S3 does that when you call the API. Use :mod:`s3pathlib.validate`
    if you want to check a name yourself.

    First let's create a S3 object path from string::

        # first argument becomes the bucket
        >>> s3path = S3Path("bucket", "folder", "file.txt")
        # print S3Path object gives you info in S3 URI format
        >>> s3path
        S3Path('s3://bucket/folder/file.txt')

        # If the last argument has a trailing slash ("/"), it indicates that
        # it refers to a directory. Otherwise, it is assumed to be a file.
        >>> s3path.is_file()
        True
        >>> s3path.is_dir()
        False

        # "/" separator will be automatically handled
        >>> S3Path("bucket", "folder/file.txt")
        S3Path('s3://bucket/folder/file.txt')

        >>> S3Path("bucket/folder/file.txt")
        S3Path('s3://bucket/folder/file.txt')

    Then let's create a S3 directory path::

        >>> s3path= S3Path("bucket/folder/")
        >>> s3path
        S3Path('s3://bucket/folder/')

        # last argument defines that it is a directory
        >>> s3path.is_dir()
        True
        >>> s3path.is_file()
        False

    You can also create it from S3 URI or ARN::

        >>> S3Path("s3://bucket/folder/file.txt")
        S3Path('s3://bucket/folder/file.txt')
        >>> S3Path("arn:aws:s3:::bucket/folder/file.txt")
        S3Path('s3://bucket/folder/file.txt')
    """

    __slots__ = (
        "_bucket",
        "_parts",
        "_is_dir",
        "_cached_cparts",  # cached comparison parts
        "_hash",  # cached hash value
        "_meta",  # s3 object metadata cache object
    )

    def __new__(
        cls: type[S3Path],
        *args: str | S3Path,
    ) -> S3Path:
        """
        The constructor of :class:`S3Path`.
        """
        return cls._from_parts(args)

    @classmethod
    def _from_parts(
        cls: type[S3Path],
        args: list[str | S3Path],
    ) -> S3Path:
        """
        Low level implementation of the constructor.
        """
        _bucket = None
        _parts = list()
        _is_dir = None

        if len(args) == 0:
            return cls._from_parsed_parts(
                bucket=_bucket,
                parts=_parts,
                is_dir=_is_dir,
            )

        # resolve self._bucket
        arg = args[0]

        if isinstance(arg, str):
            # Only check the format here, not the bucket naming rules:
            # S3 is the authority on names (e.g. legacy buckets with uppercase
            # letters are still valid). See ``s3pathlib.validate``.
            value = arg
            if arg.startswith("s3://"):
                utils.split_s3_uri(arg)
                arg = arg[len("s3://") :]
            elif arg.startswith("arn:"):
                utils.split_s3_arn(arg)
                arg = arg.split(":::", 1)[1]

            parts = utils.split_parts(arg)
            # catches "", "/", and malformed URIs such as "https://..." or
            # "s3:/...", whose first part contains ":"
            utils._ensure_bucket_part(parts[0] if parts else "", value)
            _bucket = parts[0]
            _parts.extend(parts[1:])
            _is_dir = arg.endswith("/")
        elif isinstance(arg, BaseS3Path):
            _bucket = arg._bucket
            _parts.extend(arg._parts)
            _is_dir = arg._is_dir
        else:
            raise TypeError(
                "the first argument has to be a str or an S3Path, "
                f"got {type(arg).__name__}: {arg!r}"
            )

        # resolve self._parts and self._is_dir:
        # the last non-empty argument decides whether it is a directory,
        # empty arguments ("" or a void path) are ignored
        for arg in args[1:]:
            if isinstance(arg, str):
                if arg:
                    _parts.extend(utils.split_parts(arg))
                    _is_dir = arg.endswith("/")
            elif isinstance(arg, BaseS3Path):
                if arg._bucket is not None:
                    raise TypeError(
                        "from the second arguments, it has to be raw string "
                        "(as a part) or a relative S3Path (without bucket)! "
                        f"this is invalid: {arg}."
                    )
                if arg._parts:
                    _parts.extend(arg._parts)
                    _is_dir = arg._is_dir
            else:
                raise TypeError(
                    "from the second arguments, it has to be a str or a "
                    f"relative S3Path, got {type(arg).__name__}: {arg!r}"
                )

        if (_bucket is not None) and len(_parts) == 0:  # bucket root
            _is_dir = True

        return cls._from_parsed_parts(
            bucket=_bucket,
            parts=_parts,
            is_dir=_is_dir,
        )

    @classmethod
    def _from_parsed_parts(
        cls: type[S3Path],
        bucket: str | None,
        parts: T.Iterable[str],
        is_dir: bool | None,
    ) -> S3Path:
        """
        Build the object from already parsed parts, without any parsing.

        ``parts`` is copied into a tuple, so the path never shares a mutable
        list with the caller and can not be changed after it is built.
        """
        self = object.__new__(cls)
        self._bucket = bucket
        self._parts = tuple(parts)
        self._is_dir = is_dir
        self._meta = None
        return self

    @FilterableProperty
    def parts(self: S3Path) -> list[str]:
        """
        Provides sequence-like access to the components in the filesystem path.
        It doesn't include the bucket, because bucket is considered as "drive".

        It returns a new list each time, changing it does not change the path.
        """
        return list(self._parts)

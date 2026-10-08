# -*- coding: utf-8 -*-

"""
The base constructor of S3Path object, and the states an S3Path can be in.

**The six states**

An S3Path is fully defined by three internal fields: ``_bucket``
(``str`` or ``None``), ``_parts`` (a tuple of key parts, empty or not) and
``_is_dir`` (``True``, ``False`` or ``None``). Of the 2 x 2 x 3 = 12
combinations, only these six are valid:

===========  ==========  ===========  ==============================
``_bucket``  ``_parts``  ``_is_dir``  kind
===========  ==========  ===========  ==============================
str          non-empty   False        file (an S3 object)
str          non-empty   True         dir (a logical S3 folder)
str          empty       True         bucket (the root dir)
None         non-empty   False        relative path to a file
None         non-empty   True         relative path to a dir
None         empty       None         void (the empty relative path)
===========  ==========  ===========  ==============================

In words: with parts, ``_is_dir`` says file or dir; without parts, a path
with a bucket is the bucket root, which is a dir, and a path without bucket
is void, which has no type.

The kinds nest in two levels. A path *with* a bucket is absolute (file, dir
or bucket; a bucket is a special dir). A path *without* bucket is relative
(a relative file, a relative dir or void; void is a special relative path).
Void is the identity of joining paths: ``p / S3Path() == p``, and
``p.relative_to(p)`` is void, so it has to be a relative path.

Every S3Path is built by :meth:`BaseS3Path._from_parsed_parts`, which rejects
the other six combinations, an empty bucket or a bucket with ``:``, and empty
parts or parts with ``/``, with :class:`~s3pathlib.exc.S3ValidationError`. So
no API can return a path in an undefined state.
"""

from __future__ import annotations

import typing as T

from .filterable_property import FilterableProperty
from .. import utils
from ..exc import S3ValidationError

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


def _ensure_valid_state(
    bucket: T.Any,
    parts: tuple,
    is_dir: T.Any,
) -> None:
    """
    Check that the three internal fields are one of the six valid states
    listed in the module docstring.

    :raises S3ValidationError: if they are not.
    """

    def error(reason: str) -> S3ValidationError:
        return S3ValidationError(
            f"invalid S3Path state (bucket={bucket!r}, parts={list(parts)!r}, "
            f"is_dir={is_dir!r}): {reason}"
        )

    if bucket is not None:
        if not isinstance(bucket, str):
            raise error("bucket must be a str or None")
        if not bucket:
            raise error("bucket must not be empty")
        if ":" in bucket:
            raise error("bucket must not contain ':'")
    for part in parts:
        if not (isinstance(part, str) and part and "/" not in part):
            raise error("every part must be a non-empty str without '/'")
    if not (is_dir is None or isinstance(is_dir, bool)):
        raise error("is_dir must be True, False or None")
    if parts:
        if is_dir is None:
            raise error("a path with parts must be a file or a dir")
    elif bucket is not None:
        if is_dir is not True:
            raise error("a bucket root must be a dir")
    elif is_dir is not None:
        raise error("a void path (no bucket, no parts) has no type")


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
        "_meta",  # metadata snapshot of one object version, see core.metadata
        "_meta_complete",  # True if _meta is a full head_object / get_object response
        "_s3_client",  # the explicit client that loaded _meta, see core.metadata
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
                        "a key part has to be a str or a relative S3Path, "
                        f"got an absolute path {arg!r}; only the first "
                        "argument can have a bucket"
                    )
                if arg._parts:
                    _parts.extend(arg._parts)
                    _is_dir = arg._is_dir
            else:
                raise TypeError(
                    "a key part has to be a str or a relative S3Path, "
                    f"got {type(arg).__name__}: {arg!r}"
                )

        if len(_parts) == 0:
            # bucket root is a dir, no bucket and no parts is void
            _is_dir = True if (_bucket is not None) else None

        return cls._from_parsed_parts(
            bucket=_bucket,
            parts=_parts,
            is_dir=_is_dir,
        )

    @classmethod
    def _from_parsed_parts(
        cls: type[S3Path],
        bucket: str | None,
        parts: list[str] | tuple[str, ...],
        is_dir: bool | None,
    ) -> S3Path:
        """
        Build the object from already parsed parts, without any parsing.

        ``parts`` is copied into a tuple, so the path never shares a mutable
        list with the caller and can not be changed after it is built.

        :raises S3ValidationError: if ``parts`` is not a list or a tuple, or
            the fields are not one of the six valid states, see the module
            docstring.
        """
        # a str is iterable too: tuple("abc") would silently give 3 parts
        if not isinstance(parts, (list, tuple)):
            raise S3ValidationError(
                "invalid S3Path state: parts must be a list or a tuple of str, "
                f"got {type(parts).__name__}: {parts!r}"
            )
        parts = tuple(parts)
        _ensure_valid_state(bucket, parts, is_dir)
        self = object.__new__(cls)
        self._bucket = bucket
        self._parts = parts
        self._is_dir = is_dir
        self._meta = None
        self._meta_complete = False
        self._s3_client = None
        return self

    @FilterableProperty
    def parts(self: S3Path) -> list[str]:
        """
        Provides sequence-like access to the components in the filesystem path.
        It doesn't include the bucket, because bucket is considered as "drive".

        It returns a new list each time, changing it does not change the path.
        """
        return list(self._parts)

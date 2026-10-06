# -*- coding: utf-8 -*-

"""
Exceptions and argument validators.

Every exception raised by ``s3pathlib`` inherits from :class:`S3PathlibError`.
Each one also inherits from the matching builtin exception, so
``except FileNotFoundError`` and similar still work::

    S3PathlibError(Exception)
    ├── S3NotExist(FileNotFoundError)
    │   ├── S3BucketNotExist
    │   ├── S3FolderNotExist
    │   └── S3FileNotExist
    ├── S3AlreadyExist(FileExistsError)
    │   ├── S3BucketAlreadyExist
    │   ├── S3FolderAlreadyExist
    │   └── S3FileAlreadyExist
    ├── S3PermissionDenied(PermissionError)
    ├── S3ValidationError(ValueError)
    └── S3PathTypeError(TypeError)
        ├── S3PathIsNotBucketError
        ├── S3PathIsNotFolderError
        ├── S3PathIsNotFileError
        └── S3PathIsNotRelpathError
"""

from __future__ import annotations


def ensure_all_none(**kwargs) -> None:
    """
    Ensure all the keyword arguments are None.
    """
    if len(kwargs) == 0:
        raise ValueError
    if sum([v is not None for _, v in kwargs.items()]) != 0:
        raise ValueError(f"arguments from {list(kwargs)} has to be all None!")


class S3PathlibError(Exception):
    """
    Base class of all exceptions raised by ``s3pathlib``.
    """


class _UriRelatedError:
    _tpl: str

    @classmethod
    def make(
        cls: type[Exception | _UriRelatedError],
        uri: str,
    ):
        return cls(cls._tpl.format(uri=uri))


class S3NotExist(S3PathlibError, FileNotFoundError, _UriRelatedError):
    _tpl = "{uri!r} does not exist!"


class S3BucketNotExist(S3NotExist):
    _tpl = "S3 bucket {uri!r} does not exist!"


class S3FolderNotExist(S3NotExist):
    _tpl = "S3 folder {uri!r} does not exist!"


class S3FileNotExist(S3NotExist):
    _tpl = "S3 object {uri!r} does not exist!"


class S3AlreadyExist(S3PathlibError, FileExistsError, _UriRelatedError):
    _tpl = "{uri!r} already exist!"


class S3BucketAlreadyExist(S3AlreadyExist):
    _tpl = "S3 bucket {uri!r} already exist!"


class S3FolderAlreadyExist(S3AlreadyExist):
    _tpl = "S3 folder {uri!r} already exist!"


class S3FileAlreadyExist(S3AlreadyExist):
    _tpl = "S3 object {uri!r} already exist!"


class S3PermissionDenied(S3PathlibError, PermissionError):
    pass


class S3ValidationError(S3PathlibError, ValueError):
    """
    A bucket name, key, URI or ARN is not valid.
    """


class S3PathTypeError(S3PathlibError, TypeError):
    """
    The S3 path is not the expected type (bucket, folder, file or relpath).
    """

    _expected_type: str

    @classmethod
    def make(
        cls: type[Exception | S3PathTypeError],
        uri: str,
    ):
        return cls(f"{uri!r} is not a {cls._expected_type}!")


class S3PathIsNotBucketError(S3PathTypeError):
    _expected_type = "bucket"


class S3PathIsNotFolderError(S3PathTypeError):
    _expected_type = "dir"


class S3PathIsNotFileError(S3PathTypeError):
    _expected_type = "file"


class S3PathIsNotRelpathError(S3PathTypeError):
    _expected_type = "relpath"

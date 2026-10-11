# -*- coding: utf-8 -*-

"""
Exceptions.

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
    ├── S3DeleteObjectsError
    ├── S3ObjectChangedError
    ├── S3SyncError
    ├── S3ValidationError(ValueError)
    └── S3PathTypeError(TypeError)
        ├── S3PathIsNotBucketError
        ├── S3PathIsNotFolderError
        ├── S3PathIsNotFileError
        └── S3PathIsNotRelpathError

**Design notes**

*Builtin base classes.* Each exception also inherits the builtin exception
that matches its meaning, so generic handlers such as
``except FileNotFoundError`` catch it without knowing ``s3pathlib``.

*AWS errors are not wrapped.* An error of an AWS call that has a response body
(get, list, tagging, copy, delete, ...) is raised as boto3 raises it:
``NoSuchKey``, ``NoSuchBucket`` and ``AccessDenied`` are named and documented,
and ``except ClientError`` keeps working. The exceptions here are for
``s3pathlib``'s own rules (path type, ``overwrite=False``, validation) and for
the HEAD calls (``head_bucket``, ``head_object``), whose errors carry only a
bare ``"404"`` or ``"403"`` code that ``s3_client.exceptions`` cannot catch.
``S3PermissionDenied`` comes from the 403 of a HEAD call. The original error
is always the ``__cause__``.
"""

from __future__ import annotations


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
    ) -> Exception:
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


class S3ObjectChangedError(S3PathlibError):
    """
    The S3 object changed since its metadata was loaded, so the missing
    metadata fields cannot be loaded from the same object. Raised when an
    ``S3Path`` returned by a list API (without version id) loads the rest of
    its metadata, and the object was overwritten in between. Get a new
    ``S3Path`` (e.g. list again) to read the new object.
    """


class S3SyncError(S3PathlibError):
    """
    The ``aws s3 sync`` command run by ``S3Path.sync`` failed.

    :param returncode: the exit code of the command.
    :param stderr: what the command wrote to stderr.
    :param command: the command line (it has no credentials, they are passed
        as environment variables).
    """

    def __init__(self, message: str, returncode: int, stderr: str, command: list[str]):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr
        self.command = command


class S3DeleteObjectsError(S3PathlibError):
    """
    S3 failed to delete some of the objects of a ``delete_objects`` call. The
    call itself succeeds (HTTP 200): the failures are in the ``Errors`` part
    of the response, so boto3 raises nothing.

    :param errors: The ``Errors`` of the response, e.g.
        ``[{"Key": "a.txt", "VersionId": "v1", "Code": "AccessDenied", "Message": "..."}]``.
    :param n_deleted: The number of objects deleted before (and in) the
        failed call.
    """

    def __init__(self, message: str, errors: list[dict], n_deleted: int):
        super().__init__(message)
        self.errors = errors
        self.n_deleted = n_deleted


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
    ) -> Exception:
        return cls(f"{uri!r} is not a {cls._expected_type}!")


class S3PathIsNotBucketError(S3PathTypeError):
    _expected_type = "bucket"


class S3PathIsNotFolderError(S3PathTypeError):
    _expected_type = "dir"


class S3PathIsNotFileError(S3PathTypeError):
    _expected_type = "file"


class S3PathIsNotRelpathError(S3PathTypeError):
    _expected_type = "relpath"

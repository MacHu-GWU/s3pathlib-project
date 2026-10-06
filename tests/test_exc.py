# -*- coding: utf-8 -*-

import pytest

from s3pathlib.core import S3Path
from s3pathlib.exc import ensure_all_none
from s3pathlib.exc import S3PathlibError
from s3pathlib.exc import S3NotExist
from s3pathlib.exc import S3BucketNotExist
from s3pathlib.exc import S3FolderNotExist
from s3pathlib.exc import S3FileNotExist
from s3pathlib.exc import S3AlreadyExist
from s3pathlib.exc import S3BucketAlreadyExist
from s3pathlib.exc import S3FolderAlreadyExist
from s3pathlib.exc import S3FileAlreadyExist
from s3pathlib.exc import S3PermissionDenied
from s3pathlib.exc import S3PathTypeError
from s3pathlib.exc import S3PathIsNotBucketError
from s3pathlib.exc import S3PathIsNotFolderError
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.exc import S3PathIsNotRelpathError
from s3pathlib.tests import run_cov_test


# ------------------------------------------------------------------------------
# ensure_all_none
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kwargs",
    [
        dict(a=None),
        dict(a=None, b=None, c=None),
    ],
)
def test_ensure_all_none_all_none(kwargs):
    """
    Passes silently when every argument is None.
    """
    assert ensure_all_none(**kwargs) is None


def test_ensure_all_none_no_kwargs():
    """
    Calling with no arguments is a programming error, not a vacuous pass.
    """
    with pytest.raises(ValueError):
        ensure_all_none()


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(a=1, b=None),
        dict(a=None, b="x"),
        dict(a=1, b=2),
    ],
)
def test_ensure_all_none_not_none(kwargs):
    """
    Raises when any argument, in any position, is not None.
    """
    with pytest.raises(ValueError):
        ensure_all_none(**kwargs)


@pytest.mark.parametrize("value", [0, "", False, [], {}])
def test_ensure_all_none_falsy_counts_as_not_none(value):
    """
    Falsy values are still "provided"; the check must use ``is not None``,
    not truthiness.
    """
    with pytest.raises(ValueError):
        ensure_all_none(a=None, b=value)


def test_ensure_all_none_message_lists_arg_names():
    """
    The error message names the arguments so the caller knows what to fix.
    """
    with pytest.raises(ValueError) as e:
        ensure_all_none(new_dirname="d", new_ext=None)
    assert (
        str(e.value) == "arguments from ['new_dirname', 'new_ext'] has to be all None!"
    )


# ------------------------------------------------------------------------------
# Exception hierarchy
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "exc_class, parents",
    [
        (S3PathlibError, [Exception]),
        (S3NotExist, [S3PathlibError, FileNotFoundError]),
        (S3BucketNotExist, [S3NotExist, S3PathlibError, FileNotFoundError]),
        (S3FolderNotExist, [S3NotExist, S3PathlibError, FileNotFoundError]),
        (S3FileNotExist, [S3NotExist, S3PathlibError, FileNotFoundError]),
        (S3AlreadyExist, [S3PathlibError, FileExistsError]),
        (S3BucketAlreadyExist, [S3AlreadyExist, S3PathlibError, FileExistsError]),
        (S3FolderAlreadyExist, [S3AlreadyExist, S3PathlibError, FileExistsError]),
        (S3FileAlreadyExist, [S3AlreadyExist, S3PathlibError, FileExistsError]),
        (S3PermissionDenied, [S3PathlibError, PermissionError]),
        (S3PathTypeError, [S3PathlibError, TypeError]),
        (S3PathIsNotBucketError, [S3PathTypeError, S3PathlibError, TypeError]),
        (S3PathIsNotFolderError, [S3PathTypeError, S3PathlibError, TypeError]),
        (S3PathIsNotFileError, [S3PathTypeError, S3PathlibError, TypeError]),
        (S3PathIsNotRelpathError, [S3PathTypeError, S3PathlibError, TypeError]),
    ],
)
def test_exception_hierarchy(exc_class, parents):
    """
    Each exception can be caught by s3pathlib's base class, its group class,
    and the builtin exception it has always inherited from (so 2.x
    ``except FileNotFoundError`` style code keeps working).
    """
    for parent in parents:
        assert issubclass(exc_class, parent)


# ------------------------------------------------------------------------------
# .make()
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "exc_class, message",
    [
        (S3NotExist, "'s3://b/k' does not exist!"),
        (S3BucketNotExist, "S3 bucket 's3://b/k' does not exist!"),
        (S3FolderNotExist, "S3 folder 's3://b/k' does not exist!"),
        (S3FileNotExist, "S3 object 's3://b/k' does not exist!"),
        (S3AlreadyExist, "'s3://b/k' already exist!"),
        (S3BucketAlreadyExist, "S3 bucket 's3://b/k' already exist!"),
        (S3FolderAlreadyExist, "S3 folder 's3://b/k' already exist!"),
        (S3FileAlreadyExist, "S3 object 's3://b/k' already exist!"),
    ],
)
def test_uri_error_make(exc_class, message):
    """
    ``make(uri)`` builds an instance of that exact class with a message that
    names the URI.
    """
    e = exc_class.make("s3://b/k")
    assert type(e) is exc_class
    assert str(e) == message


@pytest.mark.parametrize(
    "exc_class, message",
    [
        (S3PathIsNotBucketError, "'s3://b/k' is not a bucket!"),
        (S3PathIsNotFolderError, "'s3://b/k' is not a dir!"),
        (S3PathIsNotFileError, "'s3://b/k' is not a file!"),
        (S3PathIsNotRelpathError, "'s3://b/k' is not a relpath!"),
    ],
)
def test_path_type_error_make(exc_class, message):
    """
    ``make(uri)`` builds an instance of that exact class with a message that
    names the URI and the expected path type.
    """
    e = exc_class.make("s3://b/k")
    assert type(e) is exc_class
    assert str(e) == message


# ------------------------------------------------------------------------------
# Raised by the library
# ------------------------------------------------------------------------------
def test_catch_by_base_class():
    """
    An exception raised from a real library call path is catchable with
    ``except S3PathlibError``, proving the library raises this hierarchy.
    """
    with pytest.raises(S3PathlibError) as e:
        S3Path("s3://bucket/folder/").ensure_file()
    assert type(e.value) is S3PathIsNotFileError
    assert str(e.value) == "'s3://bucket/folder/' is not a file!"


if __name__ == "__main__":
    run_cov_test(
        __file__,
        "s3pathlib.exc",
        preview=False,
    )

# -*- coding: utf-8 -*-

"""
Is the S3Path a XYZ testing.

- :meth:`~IsTestAPIMixin.is_void`
- :meth:`~IsTestAPIMixin.is_dir`
- :meth:`~IsTestAPIMixin.is_file`
- :meth:`~IsTestAPIMixin.is_bucket`

Each test is one condition on the internal fields, because an S3Path is
always in one of the six valid states (see :mod:`s3pathlib.core.base`):

==============  ========  ===========  ==========  =======  ========
kind            is_void   is_relpath   is_bucket   is_dir   is_file
==============  ========  ===========  ==========  =======  ========
file            False     False        False       False    True
dir             False     False        False       True     False
bucket          False     False        True        True     False
relative file   False     True         False       False    True
relative dir    False     True         False       True     False
void            True      True         False       False    False
==============  ========  ===========  ==========  =======  ========
"""

from __future__ import annotations

import typing as T

from ..exc import S3PathIsNotBucketError
from ..exc import S3PathIsNotFileError
from ..exc import S3PathIsNotFolderError
from ..exc import S3PathTypeError
from ..constants import IS_DELETE_MARKER

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class IsTestAPIMixin:
    """
    A mixin class that implements the condition test methods.
    """

    __slots__ = ()

    def is_void(self: S3Path) -> bool:
        """
        Test if it is a void S3 path.

        **Definition**

        no bucket, no key, no parts, no type, no nothing.
        A void path is also a special :meth:`relative path <is_relpath>`,
        because any path join with void path results to itself.
        """
        return (self._bucket is None) and (len(self._parts) == 0)

    def is_dir(self: S3Path) -> bool:
        """
        Test if it is a S3 directory

        **Definition**

        A logical S3 directory that never physically exists. An S3
        :meth:`bucket <is_bucket>` is also a special dir, which is the root dir.
        A relative path ending with ``/`` is a dir too.
        """
        return self._is_dir is True

    def is_file(self: S3Path) -> bool:
        """
        Test if it is a S3 object

        **Definition**

        A S3 object, or a relative path that does not end with ``/``.
        """
        return self._is_dir is False

    def is_bucket(self: S3Path) -> bool:
        """
        Test if it is a S3 bucket.

        **Definition**

        A S3 bucket, the root folder S3 path is equivalent to a S3 bucket.
        A S3 bucket are always :meth:`is_dir() is True <is_dir>`
        """
        return (self._bucket is not None) and (len(self._parts) == 0)

    def is_delete_marker(self: S3Path) -> bool:
        """
        Test if it is a delete-marker. A delete-marker is just a version of
        an object without content.

        Only a path returned by
        :meth:`~s3pathlib.core.iter_object_versions.IterObjectVersionsAPIMixin.list_object_versions`
        can be a delete marker, because S3 only reports delete markers there
        (``head_object`` on a delete marker fails). So it only looks at the
        metadata already loaded, and never calls the AWS API: any other path
        returns ``False``.
        """
        if self._meta is None:
            return False
        return self._meta.get(IS_DELETE_MARKER, False) is True

    def _error_label(self: S3Path) -> str:
        """
        How the path is shown in an error message: the URI when it has a
        bucket, otherwise the repr (a relative path or void has no URI).
        """
        if self._bucket is None:
            return repr(self)
        else:
            return repr(self.uri)

    def ensure_object(self: S3Path) -> None:
        """
        A validator method that ensure it represents a S3 object (or a
        relative path to a file).

        :raises S3PathIsNotFileError: if it is not a file.
        """
        if self.is_file() is not True:
            raise S3PathIsNotFileError(f"{self._error_label()} is not a file!")

    def ensure_file(self: S3Path) -> None:
        """
        The same as :meth:`ensure_object`.
        """
        return self.ensure_object()

    def ensure_not_object(self: S3Path) -> None:
        """
        A validator method that ensure it IS NOT a S3 object (or a relative
        path to a file).

        :raises S3PathTypeError: if it is a file.
        """
        if self.is_file() is True:
            raise S3PathTypeError(f"{self._error_label()} is a file!")

    def ensure_not_file(self: S3Path) -> None:
        """
        The same as :meth:`ensure_not_object`.
        """
        return self.ensure_not_object()

    def ensure_dir(self: S3Path) -> None:
        """
        A validator method that ensure it represents a S3 dir (a bucket
        included, or a relative path to a dir).

        :raises S3PathIsNotFolderError: if it is not a dir.
        """
        if self.is_dir() is not True:
            raise S3PathIsNotFolderError(f"{self._error_label()} is not a dir!")

    def ensure_not_dir(self: S3Path) -> None:
        """
        A validator method that ensure it IS NOT a S3 dir.

        :raises S3PathTypeError: if it is a dir.
        """
        if self.is_dir() is True:
            raise S3PathTypeError(f"{self._error_label()} is a dir!")

    def ensure_bucket(self: S3Path) -> None:
        """
        A validator method that ensure it represents a S3 bucket.

        :raises S3PathIsNotBucketError: if it is not a bucket.
        """
        if self.is_bucket() is not True:
            raise S3PathIsNotBucketError(f"{self._error_label()} is not a bucket!")

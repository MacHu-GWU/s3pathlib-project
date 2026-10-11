# -*- coding: utf-8 -*-

"""
S3 URI (Uniform Resource Identifier), ARN (Amazon Resource Name),
console URL related API.

**What each attribute returns**

An S3Path is one of six kinds (see :mod:`s3pathlib.core.base`); the relative
file and the relative dir behave the same here:

=============  ==========  =============  ====================  =========================
kind           ``bucket``  ``key``        ``uri``               ``arn`` / ``console_url``
=============  ==========  =============  ====================  =========================
file           ``"b"``     ``"a/f.txt"``  ``"s3://b/a/f.txt"``  str
dir            ``"b"``     ``"a/"``       ``"s3://b/a/"``       str
bucket         ``"b"``     ``""``         ``"s3://b/"``         str
relative path  ``None``    ``"a/f.txt"``  ``None``              ``None``
void           ``None``    ``""``         ``None``              ``None``
=============  ==========  =============  ====================  =========================

**Design notes**

The attributes are in three layers, and each layer treats "missing" in its
own way:

1. The anchor, ``bucket``: only an absolute path has one. A relative path or
   void is not anchored to any bucket, so it returns ``None``, which means
   "there is none", not "it is empty".
2. The path inside the bucket, ``key`` (and ``parts``): every path has one, so
   it is always a ``str``.

   - A relative path has nothing but its key, so its key can not be ``None``.
   - Void is the identity of joining paths (``p / S3Path() == p``), and the
     matching identity of string concatenation is ``""``.
   - It is the same as the S3 API, where ``Prefix=""`` is the bucket root. So
     the key of a bucket is ``""``, not ``"/"``. A dir key ends with ``/``.

3. The full address, ``uri``, ``arn`` and the console URLs: they need both a
   bucket and a key, so a path without bucket returns ``None``. It returns
   ``None`` instead of raising, because these attributes are used as filters
   (``S3Path.uri == ...``) or for display, on collections that may mix
   absolute and relative paths.

The key is kept as it is in ``uri`` and ``arn`` (an S3 URI is not URL
encoded), and URL encoded in the console URLs.
"""

from __future__ import annotations

import typing as T

from .filterable_property import FilterableProperty
from .. import utils
from ..constants import AwsPartitionEnum

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class UriAPIMixin:
    """
    A mixin class that implements the S3 URI, ARN, console url etc ...
    """

    __slots__ = ()

    @FilterableProperty
    def bucket(self: S3Path) -> str | None:
        """
        Return bucket name as string, if available.

        Example::

            >>> S3Path("bucket/folder/file.txt").bucket
            'bucket'
        """
        return self._bucket

    @FilterableProperty
    def key(self: S3Path) -> str:
        """
        Return the key as a string. A dir key ends with ``/``; a bucket and
        the void path have an empty key. See the table above.

        Example::

            >>> S3Path("bucket/folder/").key
            'folder/'
        """
        if len(self._parts):
            return "/".join(self._parts) + ("/" if self._is_dir else "")
        else:
            return ""

    @FilterableProperty
    def uri(self: S3Path) -> str | None:
        """
        Return the S3 URI, ``"s3://{bucket}/{key}"``; ``None`` if it has no
        bucket (a relative path or the void path). The key is not URL encoded.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").uri
            's3://bucket/folder/file.txt'
        """
        if self._bucket is None:
            return None
        return f"s3://{self._bucket}/{self.key}"

    @property
    def console_url(self: S3Path) -> str | None:
        """
        The URL of the path in the global AWS console of the ``aws``
        partition, the same as :meth:`get_console_url` with the defaults.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").console_url
            'https://console.aws.amazon.com/s3/object/bucket?prefix=folder/file.txt'
        """
        return self.get_console_url()

    def get_console_url(
        self: S3Path,
        region: str | None = None,
        partition: str = AwsPartitionEnum.aws,
    ) -> str | None:
        """
        Return the URL of the path in the AWS console. If the metadata is
        already loaded and has a version id, the URL opens that version. It
        never calls the AWS API.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").get_console_url(partition="aws-us-gov")
            'https://console.amazonaws-us-gov.com/s3/object/bucket?prefix=folder/file.txt'

        :param region: use the regional console, e.g. ``"us-east-1"``.
            ``None`` (the default) uses the global console.
        :param partition: one of :class:`~s3pathlib.constants.AwsPartitionEnum`,
            e.g. ``aws``, ``aws-cn``, ``aws-us-gov`` or ``aws-eusc``.

        :return: ``None`` if it has no bucket (a relative path or a void path).

        :raises S3ValidationError: if the partition is not supported or
            ``region`` is empty.
        """
        uri = self.uri
        if uri is None:
            return None
        return utils.make_s3_console_url(
            s3_uri=uri,
            version_id=self._static_version_id,
            aws_region=region,
            partition=partition,
        )

    @FilterableProperty
    def arn(self: S3Path) -> str | None:
        """
        Return the `ARN <https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html>`_
        in the ``aws`` partition; use :meth:`get_arn` for the other partitions.

        Example::

            >>> S3Path("bucket", "folder", "file.txt").arn
            'arn:aws:s3:::bucket/folder/file.txt'
        """
        return self.get_arn()

    def get_arn(
        self: S3Path,
        partition: str = AwsPartitionEnum.aws,
    ) -> str | None:
        """
        Return the ARN in the given partition.

        Example::

            >>> S3Path("s3://bucket/folder/file.txt").get_arn("aws-cn")
            'arn:aws-cn:s3:::bucket/folder/file.txt'

        :param partition: one of :class:`~s3pathlib.constants.AwsPartitionEnum`,
            e.g. ``aws``, ``aws-cn``, ``aws-us-gov`` or ``aws-eusc``.

        :return: ``None`` if it has no bucket (a relative path or a void path).

        :raises S3ValidationError: if the partition is not supported.
        """
        partition = utils._ensure_partition(partition)
        if self._bucket is None:
            return None
        if len(self._parts):
            return f"arn:{partition}:s3:::{self._bucket}/{self.key}"
        else:
            return f"arn:{partition}:s3:::{self._bucket}"

    @classmethod
    def from_s3_uri(cls: type[S3Path], uri: str) -> S3Path:
        """
        Construct an :class:`S3Path` from an S3 URI. Only the URI format is
        checked, not the bucket naming rules, so a legacy bucket name such as
        ``My_Bucket`` works.

        Example::

            >>> S3Path.from_s3_uri("s3://bucket/folder/file.txt")
            S3Path('s3://bucket/folder/file.txt')

        :raises S3ValidationError: if it is not an S3 URI.
        """
        # the constructor also accepts an ARN or a bucket name, so check that
        # it is a URI first
        utils.split_s3_uri(uri)
        return cls._from_parts([uri])

    @classmethod
    def from_s3_arn(cls: type[S3Path], arn: str) -> S3Path:
        """
        Construct an :class:`S3Path` from an S3 ARN of any partition in
        :class:`~s3pathlib.constants.AwsPartitionEnum`. The partition is not
        stored, an S3 path is identified by bucket and key. Only the ARN format
        is checked, not the bucket naming rules.

        Example::

            >>> S3Path.from_s3_arn("arn:aws:s3:::bucket/folder/file.txt")
            S3Path('s3://bucket/folder/file.txt')

        :raises S3ValidationError: if it is not an S3 ARN of a supported partition.
        """
        # the constructor also accepts a URI or a bucket name, so check that
        # it is an ARN first
        utils.split_s3_arn(arn)
        return cls._from_parts([arn])

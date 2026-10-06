# -*- coding: utf-8 -*-

"""
S3 URI (Uniform Resource Identifier), ARN (Amazon Resource Name),
console URL related API.
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
        Return object or directory key as string. A directory key ends with
        ``/``; a bucket or void path has an empty key.

        Examples::

            # a s3 object
            >>> S3Path("bucket/folder/file.txt").key
            'folder/file.txt'

            # a s3 directory
            >>> S3Path("bucket/folder/").key
            'folder/'

            # a relative path
            >>> S3Path("bucket/folder/file.txt").relative_to(S3Path("bucket")).key
            'folder/file.txt'

            >>> S3Path("bucket/folder/").relative_to(S3Path("bucket")).key
            'folder/'

            # a bucket and a void path
            >>> S3Path("bucket").key
            ''
            >>> S3Path().key
            ''
        """
        if len(self._parts):
            return "/".join(self._parts) + ("/" if self._is_dir else "")
        else:
            return ""

    @FilterableProperty
    def uri(self: S3Path) -> str | None:
        """
        Return AWS S3 URI.

        - for regular s3 object, it returns ``"s3://{bucket}/{key}"``
        - if it is a directory, the s3 uri always ends with ``"/"``.
        - if it is bucket only (no key), it returns ``"s3://{bucket}/"``
        - if it has no bucket (a relative path or a void path), it returns
            ``None``

        The key is not URL encoded, an S3 URI keeps the key as it is.

        Examples::

            >>> S3Path("bucket", "folder", "file.txt").uri
            's3://bucket/folder/file.txt'

            >>> S3Path("bucket", "folder/").uri
            's3://bucket/folder/'

            >>> S3Path("bucket").uri
            's3://bucket/'

            # void path doesn't have uri
            >>> S3Path().uri is None
            True

            # relative path doesn't have uri
            >>> S3Path("bucket/folder/file.txt").relative_to(S3Path("bucket")).uri is None
            True
        """
        if self._bucket is None:
            return None
        return f"s3://{self._bucket}/{self.key}"

    @property
    def console_url(self: S3Path) -> str | None:
        """
        Return an url that can inspect the object, directory details in the
        global AWS Console of the ``aws`` partition. Same as
        :meth:`get_console_url` with the default arguments.

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
        Return an url that can inspect the object, directory details in AWS
        Console.

        Example::

            >>> p = S3Path("bucket", "folder", "file.txt")
            >>> p.get_console_url(region="us-east-1")
            'https://us-east-1.console.aws.amazon.com/s3/object/bucket?region=us-east-1&prefix=folder/file.txt'
            >>> p.get_console_url(partition="aws-us-gov")
            'https://console.amazonaws-us-gov.com/s3/object/bucket?prefix=folder/file.txt'

        If the object metadata is already loaded and has a version id, the url
        opens that version. It does not call the AWS API.

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
        Return the AWS S3 resource ARN in the ``aws`` partition.
        Use :meth:`get_arn` for the other partitions.
        See `ARN definition here <https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html>`_

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
        Return the AWS S3 resource ARN in the given partition.

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
        Construct an :class:`S3Path` from S3 URI.

        >>> p = S3Path.from_s3_uri("s3://bucket/folder/file.txt")

        >>> p
        S3Path('s3://bucket/folder/file.txt')

        >>> p.uri
        's3://bucket/folder/file.txt'

        Only the URI format is checked, not the bucket naming rules, so a
        legacy bucket name such as ``My_Bucket`` works.

        :raises S3ValidationError: if it is not an S3 URI.
        """
        # the constructor also accepts an ARN or a bucket name, so check that
        # it is a URI first
        utils.split_s3_uri(uri)
        return cls._from_parts([uri])

    @classmethod
    def from_s3_arn(cls: type[S3Path], arn: str) -> S3Path:
        """
        Construct an :class:`S3Path` from S3 ARN.

        >>> p = S3Path.from_s3_arn("arn:aws:s3:::bucket/folder/file.txt")

        >>> p
        S3Path('s3://bucket/folder/file.txt')

        >>> p.arn
        'arn:aws:s3:::bucket/folder/file.txt'

        Every partition in :class:`~s3pathlib.constants.AwsPartitionEnum` is
        supported. The partition is not stored, an S3 path is identified by
        bucket and key. Only the ARN format is checked, not the bucket naming
        rules.

        :raises S3ValidationError: if it is not an S3 ARN of a supported partition.
        """
        # the constructor also accepts a URI or a bucket name, so check that
        # it is an ARN first
        utils.split_s3_arn(arn)
        return cls._from_parts([arn])

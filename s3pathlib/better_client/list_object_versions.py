# -*- coding: utf-8 -*-

"""
Improve the list_object_versions_ and ListObjectVersions_ API.

.. _list_object_versions: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/list_object_versions.html
.. _ListObjectVersions: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjectVersions.html
"""

from __future__ import annotations

import typing as T

from func_args import NOTHING
from func_args import resolve_kwargs
from iterproxy import IterProxy

from .list_objects import CommonPrefixTypeDefIterproxy

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import ListObjectVersionsOutputTypeDef
    from mypy_boto3_s3.type_defs import ObjectVersionTypeDef
    from mypy_boto3_s3.type_defs import DeleteMarkerEntryTypeDef
    from mypy_boto3_s3.type_defs import CommonPrefixTypeDef

    _ = ListObjectVersionsOutputTypeDef


class ObjectVersionTypeDefIterproxy(IterProxy["ObjectVersionTypeDef"]):
    """
    An iterproxy that yields the "Versions" part of the ListObjectVersions_ response.
    """


class DeleteMarkerEntryTypeDefIterproxy(IterProxy["DeleteMarkerEntryTypeDef"]):
    """
    An iterproxy that yields the "DeleteMarkers" part of the ListObjectVersions_ response.
    """


class ListObjectVersionsOutputTypeDefIterproxy(
    IterProxy["ListObjectVersionsOutputTypeDef"]
):
    """
    An iterproxy that yields the original list_object_versions_ responses, one
    per page. :meth:`versions`, :meth:`delete_markers`,
    :meth:`common_prefixes`, :meth:`versions_and_delete_markers_and_common_prefixes`
    and :meth:`iterate_key_and_version` give the parts of the responses.

    It can be iterated only once: the pages are fetched while iterating, and
    using one of the methods consumes it. To get several parts, use
    :meth:`versions_and_delete_markers_and_common_prefixes`.
    """

    def _yield_versions(self) -> T.Iterator[ObjectVersionTypeDef]:
        for response in self:
            for version in response.get("Versions", []):
                yield version

    def versions(self) -> ObjectVersionTypeDefIterproxy:
        """
        Iterate object versions.
        """
        return ObjectVersionTypeDefIterproxy(self._yield_versions())

    def _yield_delete_markers(self) -> T.Iterator[DeleteMarkerEntryTypeDef]:
        for response in self:
            for delete_marker in response.get("DeleteMarkers", []):
                yield delete_marker

    def delete_markers(self) -> DeleteMarkerEntryTypeDefIterproxy:
        """
        Iterate delete markers.
        """
        return DeleteMarkerEntryTypeDefIterproxy(self._yield_delete_markers())

    def _yield_common_prefixes(self) -> T.Iterator[CommonPrefixTypeDef]:
        for response in self:
            for common_prefix in response.get("CommonPrefixes", []):
                yield common_prefix

    def common_prefixes(self) -> CommonPrefixTypeDefIterproxy:
        """
        Iterate folders.
        """
        return CommonPrefixTypeDefIterproxy(self._yield_common_prefixes())

    def extract_versions_and_delete_markers_and_common_prefixes(
        self, response: dict
    ) -> tuple[
        list[ObjectVersionTypeDef],
        list[DeleteMarkerEntryTypeDef],
        list[CommonPrefixTypeDef],
    ]:
        return (
            response.get("Versions", []),
            response.get("DeleteMarkers", []),
            response.get("CommonPrefixes", []),
        )

    def versions_and_delete_markers_and_common_prefixes(
        self,
    ) -> tuple[
        list[ObjectVersionTypeDef],
        list[DeleteMarkerEntryTypeDef],
        list[CommonPrefixTypeDef],
    ]:
        """
        Return the full list of object versions, delete markers and folders.
        """
        versions = list()
        delete_markers = list()
        common_prefixes = list()
        for response in self:
            (
                versions_,
                delete_markers_,
                common_prefixes_,
            ) = self.extract_versions_and_delete_markers_and_common_prefixes(response)
            versions.extend(versions_)
            delete_markers.extend(delete_markers_)
            common_prefixes.extend(common_prefixes_)
        return versions, delete_markers, common_prefixes

    def iterate_key_and_version(self) -> T.Iterator[tuple[str, str]]:
        """
        Iterate the ``(key, version_id)`` pairs of the versions and the delete
        markers (page by page: the versions of a page, then its delete
        markers). In a bucket that never had versioning, the version id is
        ``"null"``.
        """
        for response in self:
            for version in response.get("Versions", []):
                yield (version["Key"], version["VersionId"])
            for delete_marker in response.get("DeleteMarkers", []):
                yield (delete_marker["Key"], delete_marker["VersionId"])


def paginate_list_object_versions(
    s3_client: S3Client,
    bucket: str,
    prefix: str,
    batch_size: int = 1000,
    limit: int = NOTHING,
    delimiter: str = NOTHING,
    encoding_type: str = NOTHING,
    expected_bucket_owner: str = NOTHING,
) -> ListObjectVersionsOutputTypeDefIterproxy:
    """
    Call list_object_versions_ page by page, and return a user-friendly
    :class:`ListObjectVersionsOutputTypeDefIterproxy` of the responses.

    Example::

        >>> proxy = paginate_list_object_versions(
        ...     s3_client=s3_client,
        ...     bucket="my-bucket",
        ...     prefix="my-folder/",
        ... )
        >>> versions, delete_markers, common_prefixes = proxy.versions_and_delete_markers_and_common_prefixes()
        >>> [(version["Key"], version["IsLatest"]) for version in versions]
        [('my-folder/file.txt', True)]

    ``prefix`` is a string prefix, not a folder: ``"my-folder"`` also matches
    ``my-folder-2/...``. End it with ``/`` to list a folder.

    The pages are fetched lazily, while iterating the result: errors of the
    AWS call (e.g. ``NoSuchBucket``, ``AccessDenied``) are raised as is, when
    the iteration starts, not when this function is called.

    :param s3_client: ``boto3.session.Session().client("s3")`` object.
    :param bucket: See list_object_versions_.
    :param prefix: See list_object_versions_.
    :param batch_size: The number of entries per API call (``MaxKeys``),
        1 to 1000.
    :param limit: The maximum number of entries in total: versions, delete
        markers and folders (common prefixes, when ``delimiter`` is given)
        counted together, the same as ``MaxKeys``. ``0`` returns nothing
        without calling AWS. Not given: no limit.
    :param delimiter: See list_object_versions_.
    :param encoding_type: See list_object_versions_.
    :param expected_bucket_owner: See list_object_versions_.

    :return: a :class:`ListObjectVersionsOutputTypeDefIterproxy` object.

    :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
        negative.
    """
    # validate arguments
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("``batch_size`` has to be 1 ~ 1000.")
    if limit is not NOTHING:
        if limit < 0:
            raise ValueError(f"``limit`` must not be negative, got {limit}.")

    def _paginate_list_object_versions():
        # Not the botocore paginator: its MaxItems only counts "Versions", so
        # it returned more entries than ``limit`` when there were delete
        # markers or common prefixes. S3's MaxKeys counts all of them, so
        # asking for the remaining number on each call gives exactly ``limit``.
        if limit is NOTHING:
            remaining = None
        else:
            remaining = limit
        key_marker = NOTHING
        version_id_marker = NOTHING
        while True:
            if remaining is None:
                max_keys = batch_size
            else:
                if remaining <= 0:
                    break
                max_keys = min(batch_size, remaining)
            response = s3_client.list_object_versions(
                **resolve_kwargs(
                    Bucket=bucket,
                    Prefix=prefix,
                    Delimiter=delimiter,
                    EncodingType=encoding_type,
                    ExpectedBucketOwner=expected_bucket_owner,
                    MaxKeys=max_keys,
                    KeyMarker=key_marker,
                    VersionIdMarker=version_id_marker,
                )
            )
            yield response
            if remaining is not None:
                n_entries = len(response.get("Versions", []))
                n_entries += len(response.get("DeleteMarkers", []))
                n_entries += len(response.get("CommonPrefixes", []))
                remaining -= n_entries
            if response.get("IsTruncated", False) is False:
                break
            key_marker = response["NextKeyMarker"]
            # absent when the page ends with a common prefix
            version_id_marker = response.get("NextVersionIdMarker", NOTHING)

    return ListObjectVersionsOutputTypeDefIterproxy(_paginate_list_object_versions())

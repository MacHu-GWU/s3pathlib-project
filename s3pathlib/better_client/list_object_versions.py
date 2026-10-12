# -*- coding: utf-8 -*-

"""
Improve the list_object_versions_ API.

.. _list_object_versions: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/list_object_versions.html
"""

from __future__ import annotations

import typing as T

from iterproxy import IterProxy

from .._arg import OPT
from ._paginate import iter_pages
from ._paginate import yield_items
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
    An iterproxy that yields the "Versions" part of the list_object_versions_
    responses.
    """


class DeleteMarkerEntryTypeDefIterproxy(IterProxy["DeleteMarkerEntryTypeDef"]):
    """
    An iterproxy that yields the "DeleteMarkers" part of the
    list_object_versions_ responses.
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

    def versions(self) -> ObjectVersionTypeDefIterproxy:
        """
        Iterate object versions.
        """
        return ObjectVersionTypeDefIterproxy(yield_items(self, "Versions"))

    def delete_markers(self) -> DeleteMarkerEntryTypeDefIterproxy:
        """
        Iterate delete markers.
        """
        return DeleteMarkerEntryTypeDefIterproxy(yield_items(self, "DeleteMarkers"))

    def common_prefixes(self) -> CommonPrefixTypeDefIterproxy:
        """
        Iterate folders.
        """
        return CommonPrefixTypeDefIterproxy(yield_items(self, "CommonPrefixes"))

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
    limit: int | None = None,
    delimiter: str = OPT,
    encoding_type: str = OPT,
    request_payer: str = OPT,
    expected_bucket_owner: str = OPT,
) -> ListObjectVersionsOutputTypeDefIterproxy:
    """
    Call list_object_versions_ page by page, and return the responses as a
    :class:`ListObjectVersionsOutputTypeDefIterproxy`.

    ``prefix`` is a string prefix, not a folder: ``"my-folder"`` also matches
    ``my-folder-2/...``. End it with ``/`` to list a folder.

    The pages are fetched lazily, while iterating the result: errors of the
    AWS call (e.g. ``NoSuchBucket``, ``AccessDenied``) are raised as is, when
    the iteration starts, not when this function is called.

    Example::

        proxy = paginate_list_object_versions(s3_client, "my-bucket", "my-folder/")
        versions, delete_markers, common_prefixes = (
            proxy.versions_and_delete_markers_and_common_prefixes()
        )

    :param batch_size: The number of entries per API call (``MaxKeys``),
        1 to 1000.
    :param limit: The maximum number of entries in total: versions, delete
        markers and folders (common prefixes, when ``delimiter`` is given)
        counted together, the same as ``MaxKeys``. ``0`` returns nothing
        without calling AWS. ``None`` (default): no limit.

    :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
        negative.
    """
    pages = iter_pages(
        s3_client=s3_client,
        method="list_object_versions",
        params=dict(
            Bucket=bucket,
            Prefix=prefix,
            Delimiter=delimiter,
            EncodingType=encoding_type,
            RequestPayer=request_payer,
            ExpectedBucketOwner=expected_bucket_owner,
        ),
        batch_size=batch_size,
        limit=limit,
        entry_keys=("Versions", "DeleteMarkers", "CommonPrefixes"),
        next_params=lambda response: dict(
            KeyMarker=response["NextKeyMarker"],
            # absent when the page ends with a common prefix
            VersionIdMarker=response.get("NextVersionIdMarker", OPT),
        ),
    )
    return ListObjectVersionsOutputTypeDefIterproxy(pages)

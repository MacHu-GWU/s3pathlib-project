# -*- coding: utf-8 -*-

"""
Improve the list_objects_v2_ API.

.. _list_objects_v2: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/list_objects_v2.html
"""

from __future__ import annotations

import typing as T

from iterproxy import IterProxy

from .._arg import OPT
from ._paginate import iter_pages
from ._paginate import yield_items

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import (
        ListObjectsV2OutputTypeDef,
        ObjectTypeDef,
        CommonPrefixTypeDef,
    )

    _ = ListObjectsV2OutputTypeDef


class ObjectTypeDefIterproxy(IterProxy["ObjectTypeDef"]):
    """
    An iterproxy that yields the "Contents" part of the list_objects_v2_
    responses.
    """


class CommonPrefixTypeDefIterproxy(IterProxy["CommonPrefixTypeDef"]):
    """
    An iterproxy that yields the "CommonPrefixes" part of the list_objects_v2_
    or list_object_versions responses.
    """


class ListObjectsV2OutputTypeDefIterproxy(IterProxy["ListObjectsV2OutputTypeDef"]):
    """
    An iterproxy that yields the original list_objects_v2_ responses, one per
    page. :meth:`contents`, :meth:`common_prefixes` and
    :meth:`contents_and_common_prefixes` give the objects and the folders.

    It can be iterated only once: the pages are fetched while iterating, and
    using one of the methods consumes it. To get both the objects and the
    folders, use :meth:`contents_and_common_prefixes`.
    """

    def contents(self) -> ObjectTypeDefIterproxy:
        """
        Iterate object contents.
        """
        return ObjectTypeDefIterproxy(yield_items(self, "Contents"))

    def common_prefixes(self) -> CommonPrefixTypeDefIterproxy:
        """
        Iterate folders.
        """
        return CommonPrefixTypeDefIterproxy(yield_items(self, "CommonPrefixes"))

    def extract_contents_and_common_prefixes(
        self, response: dict
    ) -> tuple[
        list[ObjectTypeDef],
        list[CommonPrefixTypeDef],
    ]:
        return (
            response.get("Contents", []),
            response.get("CommonPrefixes", []),
        )

    def contents_and_common_prefixes(
        self,
    ) -> tuple[list[ObjectTypeDef], list[CommonPrefixTypeDef]]:
        """
        Return the full list of object contents and folders.
        """
        contents = list()
        common_prefixes = list()
        for response in self:
            (
                _contents,
                _common_prefixes,
            ) = self.extract_contents_and_common_prefixes(response)
            contents.extend(_contents)
            common_prefixes.extend(_common_prefixes)
        return contents, common_prefixes


def paginate_list_objects_v2(
    s3_client: S3Client,
    bucket: str,
    prefix: str,
    batch_size: int = 1000,
    limit: int | None = None,
    delimiter: str = OPT,
    encoding_type: str = OPT,
    fetch_owner: bool = OPT,
    start_after: str = OPT,
    request_payer: str = OPT,
    expected_bucket_owner: str = OPT,
) -> ListObjectsV2OutputTypeDefIterproxy:
    """
    Call list_objects_v2_ page by page, and return the responses as a
    :class:`ListObjectsV2OutputTypeDefIterproxy`.

    ``prefix`` is a string prefix, not a folder: ``"my-folder"`` also matches
    ``my-folder-2/...``. End it with ``/`` to list a folder.

    The pages are fetched lazily, while iterating the result: errors of the
    AWS call (e.g. ``NoSuchBucket``, ``AccessDenied``) are raised as is, when
    the iteration starts, not when this function is called.

    Example::

        result = paginate_list_objects_v2(s3_client, "my-bucket", "my-folder/")
        for content in result.contents():
            print(content["Key"])

    :param batch_size: The number of entries per API call (``MaxKeys``),
        1 to 1000.
    :param limit: The maximum number of entries in total, objects and folders
        (common prefixes, when ``delimiter`` is given) counted together, the
        same as ``MaxKeys``. ``0`` returns nothing without calling AWS.
        ``None`` (default): no limit.

    :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
        negative.
    """
    pages = iter_pages(
        s3_client=s3_client,
        method="list_objects_v2",
        params=dict(
            Bucket=bucket,
            Prefix=prefix,
            Delimiter=delimiter,
            EncodingType=encoding_type,
            FetchOwner=fetch_owner,
            StartAfter=start_after,
            RequestPayer=request_payer,
            ExpectedBucketOwner=expected_bucket_owner,
        ),
        batch_size=batch_size,
        limit=limit,
        entry_keys=("Contents", "CommonPrefixes"),
        next_params=lambda response: dict(
            ContinuationToken=response["NextContinuationToken"]
        ),
    )
    return ListObjectsV2OutputTypeDefIterproxy(pages)


def is_content_an_object(content: ObjectTypeDef) -> bool:
    """
    Return True if the content is an object, False if it is a folder marker
    (an empty object whose key ends with ``/``, made by "Create folder" in
    the S3 console).

    Truth table:

    - key ends with ``/``, size is 0: False (folder marker)
    - key ends with ``/``, size > 0: True (an object that has data)
    - key ends without ``/``, size is 0: True (an empty file)
    - key ends without ``/``, size > 0: True
    """
    return (not content["Key"].endswith("/")) or (content["Size"] != 0)


def calculate_total_size(
    s3_client: S3Client,
    bucket: str,
    prefix: str,
    include_folder: bool = False,
) -> tuple[int, int]:
    """
    Perform the "Calculate Total Size" action of the AWS S3 console.
    ``prefix`` is a string prefix, e.g. ``"my-folder/"``; ``"my-folder"`` also
    matches ``my-folder-2/...``.

    :param include_folder: whether to count the folder markers (see
        :func:`is_content_an_object`).

    :return: ``(count, total_size)``: the number of objects and their total
        size in bytes.
    """
    count = 0
    total_size = 0
    contents_iterproxy = paginate_list_objects_v2(
        s3_client=s3_client,
        bucket=bucket,
        prefix=prefix,
    ).contents()
    if include_folder is False:
        contents_iterproxy = contents_iterproxy.filter(is_content_an_object)
    for content in contents_iterproxy:
        count += 1
        total_size += content["Size"]
    return count, total_size


def count_objects(
    s3_client: S3Client,
    bucket: str,
    prefix: str,
    include_folder: bool = False,
) -> int:
    """
    Count the objects under ``prefix``, a string prefix like
    ``"my-folder/"``; ``"my-folder"`` also matches ``my-folder-2/...``.

    :param include_folder: whether to count the folder markers (see
        :func:`is_content_an_object`).
    """
    contents_iterproxy = paginate_list_objects_v2(
        s3_client=s3_client,
        bucket=bucket,
        prefix=prefix,
    ).contents()
    if include_folder is False:
        contents_iterproxy = contents_iterproxy.filter(is_content_an_object)
    count = 0
    for count, _ in enumerate(contents_iterproxy, start=1):
        pass
    return count

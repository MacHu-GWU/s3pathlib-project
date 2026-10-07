# -*- coding: utf-8 -*-

"""
Improve the list_objects_v2_ and ListObjectsV2_ API.

.. _list_objects_v2: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.list_objects_v2
.. _ListObjectsV2: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/paginator/ListObjectsV2.html
"""

from __future__ import annotations

import typing as T

from func_args import NOTHING
from func_args import resolve_kwargs
from iterproxy import IterProxy


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
    An iterproxy that yields the "Contents" part of the ListObjectsV2_ response.
    """


class CommonPrefixTypeDefIterproxy(IterProxy["CommonPrefixTypeDef"]):
    """
    An iterproxy that yields the "CommonPrefixes" part of the ListObjectsV2_ response.
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

    def _yield_content(self) -> T.Iterator[ObjectTypeDef]:
        for response in self:
            for content in response.get("Contents", []):
                yield content

    def contents(self) -> ObjectTypeDefIterproxy:
        """
        Iterate object contents.
        """
        return ObjectTypeDefIterproxy(self._yield_content())

    def _yield_common_prefixes(self) -> T.Iterator[CommonPrefixTypeDef]:
        for response in self:
            for common_prefix in response.get("CommonPrefixes", []):
                yield common_prefix

    def common_prefixes(self) -> CommonPrefixTypeDefIterproxy:
        """
        Iterate folders.
        """
        return CommonPrefixTypeDefIterproxy(self._yield_common_prefixes())

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
    limit: int = NOTHING,
    delimiter: str = NOTHING,
    encoding_type: str = NOTHING,
    fetch_owner: bool = NOTHING,
    start_after: str = NOTHING,
    request_payer: str = NOTHING,
    expected_bucket_owner: str = NOTHING,
) -> ListObjectsV2OutputTypeDefIterproxy:
    """
    Call list_objects_v2_ page by page, and return a user-friendly
    :class:`ListObjectsV2OutputTypeDefIterproxy` of the responses.

    Example::

        >>> result = paginate_list_objects_v2(
        ...     s3_client=s3_client,
        ...     bucket="my-bucket",
        ...     prefix="my-folder/",
        ... )
        >>> for content in result.contents():
        ...     print(content["Key"])
        my-folder/1.json
        my-folder/2.json

    ``prefix`` is a string prefix, not a folder: ``"my-folder"`` also matches
    ``my-folder-2/...``. End it with ``/`` to list a folder.

    The pages are fetched lazily, while iterating the result: errors of the
    AWS call (e.g. ``NoSuchBucket``, ``AccessDenied``) are raised as is, when
    the iteration starts, not when this function is called.

    :param s3_client: ``boto3.session.Session().client("s3")`` object.
    :param bucket: See list_objects_v2_.
    :param prefix: See list_objects_v2_.
    :param batch_size: The number of entries per API call (``MaxKeys``),
        1 to 1000.
    :param limit: The maximum number of entries in total, objects and folders
        (common prefixes, when ``delimiter`` is given) counted together, the
        same as ``MaxKeys``. ``0`` returns nothing without calling AWS. Not
        given: no limit.
    :param delimiter: See list_objects_v2_.
    :param encoding_type: See list_objects_v2_.
    :param fetch_owner: See list_objects_v2_.
    :param start_after: See list_objects_v2_.
    :param request_payer: See list_objects_v2_.
    :param expected_bucket_owner: See list_objects_v2_.

    :return: a :class:`ListObjectsV2OutputTypeDefIterproxy` object.

    :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
        negative.
    """
    # validate arguments
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("``batch_size`` has to be 1 ~ 1000.")
    if limit is not NOTHING:
        if limit < 0:
            raise ValueError(f"``limit`` must not be negative, got {limit}.")

    def _paginate_list_objects_v2():
        # Not the botocore paginator: its MaxItems only counts "Contents", so
        # with a delimiter it returned more entries than ``limit``. S3's
        # MaxKeys counts objects and common prefixes together, so asking for
        # the remaining number on each call gives exactly ``limit`` entries.
        if limit is NOTHING:
            remaining = None
        else:
            remaining = limit
        continuation_token = NOTHING
        while True:
            if remaining is None:
                max_keys = batch_size
            else:
                if remaining <= 0:
                    break
                max_keys = min(batch_size, remaining)
            response = s3_client.list_objects_v2(
                **resolve_kwargs(
                    Bucket=bucket,
                    Prefix=prefix,
                    Delimiter=delimiter,
                    EncodingType=encoding_type,
                    FetchOwner=fetch_owner,
                    StartAfter=start_after,
                    RequestPayer=request_payer,
                    ExpectedBucketOwner=expected_bucket_owner,
                    MaxKeys=max_keys,
                    ContinuationToken=continuation_token,
                )
            )
            yield response
            if remaining is not None:
                n_entries = len(response.get("Contents", []))
                n_entries += len(response.get("CommonPrefixes", []))
                remaining -= n_entries
            if response.get("IsTruncated", False) is False:
                break
            continuation_token = response["NextContinuationToken"]

    return ListObjectsV2OutputTypeDefIterproxy(_paginate_list_objects_v2())


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
    Perform the "Calculate Total Size" action in AWS S3 console.

    :param s3_client: ``boto3.session.Session().client("s3")`` object
    :param bucket: S3 bucket name
    :param prefix: The S3 prefix to calculate, e.g. ``"my-folder/"``. It is a
        string prefix: ``"my-folder"`` also matches ``my-folder-2/...``.
    :param include_folder: Default False, whether counting the folder markers
        (see :func:`is_content_an_object`).

    :return: Tuple of ``(count, total_size)``. First value is number of objects,
        Second value is total size in bytes.
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
    Count number of objects under prefix.

    :param s3_client: ``boto3.session.Session().client("s3")`` object
    :param bucket: S3 bucket name
    :param prefix: The S3 prefix to count, e.g. ``"my-folder/"``. It is a
        string prefix: ``"my-folder"`` also matches ``my-folder-2/...``.
    :param include_folder: Default False, whether counting the folder markers
        (see :func:`is_content_an_object`).

    :return: Number of objects under prefix.
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

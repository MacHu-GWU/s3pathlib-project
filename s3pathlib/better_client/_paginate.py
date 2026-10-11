# -*- coding: utf-8 -*-

"""
The page by page loop shared by ``paginate_list_objects_v2`` and
``paginate_list_object_versions``.

**Design notes**

*Not the botocore paginator.* Its ``MaxItems`` only counts one kind of entry
(``Contents`` or ``Versions``), so with a delimiter, folders or delete markers
it returned more entries than ``limit``. S3's ``MaxKeys`` counts all of them
together, so asking for the remaining number on each call gives exactly
``limit`` entries.
"""

from __future__ import annotations

import typing as T

from .._arg import remove_optional

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


def yield_items(pages: T.Iterable[dict], name: str) -> T.Iterator[dict]:
    """
    Yield the entries under the key ``name`` of each page.
    """
    for response in pages:
        for item in response.get(name, []):
            yield item


def validate_paging_arguments(batch_size: int, limit: int | None) -> None:
    """
    :raises ValueError: if ``batch_size`` is not 1 to 1000, or ``limit`` is
        negative.
    """
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("``batch_size`` has to be 1 ~ 1000.")
    if limit is not None:
        if limit < 0:
            raise ValueError(f"``limit`` must not be negative, got {limit}.")


def iter_pages(
    s3_client: S3Client,
    method: str,
    params: dict[str, T.Any],
    batch_size: int,
    limit: int | None,
    entry_keys: tuple[str, ...],
    next_params: T.Callable[[dict], dict[str, T.Any]],
) -> T.Iterator[dict]:
    """
    Call ``s3_client.<method>(**params, MaxKeys=...)`` until the last page or
    ``limit`` entries, and yield each response. The arguments are validated
    when this function is called, the client is only used while iterating.

    :param params: the boto3 parameters, the ones whose value is ``OPT`` are
        dropped.
    :param entry_keys: the keys of a response that hold the entries counted by
        ``limit``, e.g. ``("Contents", "CommonPrefixes")``.
    :param next_params: the parameters that ask for the page after
        ``response``, e.g. ``{"ContinuationToken": ...}``.
    """
    validate_paging_arguments(batch_size, limit)

    def pages():
        remaining = limit
        page_params = dict()
        while True:
            if remaining is None:
                max_keys = batch_size
            else:
                if remaining <= 0:
                    break
                max_keys = min(batch_size, remaining)
            response = getattr(s3_client, method)(
                **remove_optional(**params, MaxKeys=max_keys, **page_params)
            )
            yield response
            if remaining is not None:
                for key in entry_keys:
                    remaining -= len(response.get(key, []))
            if response.get("IsTruncated", False) is False:
                break
            page_params = next_params(response)

    return pages()

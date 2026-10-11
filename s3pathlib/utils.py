# -*- coding: utf-8 -*-

"""
In-memory helpers: S3 URI / ARN parsing, S3 key joining, AWS console URLs,
human readable data sizes. Nothing here talks to AWS.
"""

from __future__ import annotations

import re
import typing as T
from urllib.parse import quote

from .constants import AwsPartitionEnum
from .constants import AWS_CONSOLE_DOMAIN
from .exc import S3ValidationError


def _ensure_bucket_part(bucket: str, value: str) -> None:
    """
    Format check on the bucket part parsed from an S3 URI or ARN: it must not
    be empty, and it must not contain ``:``, which no bucket name (not even a
    legacy one) can have. This is not a bucket naming rules check.
    """
    if not bucket:
        raise S3ValidationError(f"bucket is empty in {value!r}")
    if ":" in bucket:
        raise S3ValidationError(
            f"bucket {bucket!r} in {value!r} contains ':', "
            f"which is not allowed in any bucket name"
        )


def split_s3_uri(
    s3_uri: str,
) -> tuple[str, str]:
    """
    Split an AWS S3 URI, returns bucket and key.

    Example::

        >>> split_s3_uri("s3://my-bucket/my-folder/data.json")
        ('my-bucket', 'my-folder/data.json')
        >>> split_s3_uri("s3://my-bucket")
        ('my-bucket', '')

    This only checks the format (``s3://`` scheme, non-empty bucket). It does
    not check bucket naming rules; use
    :func:`~s3pathlib.validate.validate_s3_uri` for that.

    :param s3_uri: ``s3://{bucket}``, ``s3://{bucket}/`` or ``s3://{bucket}/{key}``.

    :raises S3ValidationError: if it is not an S3 URI.
    """
    if not s3_uri.startswith("s3://"):
        raise S3ValidationError(f"S3 URI must start with 's3://', got {s3_uri!r}")
    bucket, _, key = s3_uri[len("s3://") :].partition("/")
    _ensure_bucket_part(bucket, s3_uri)
    return bucket, key


def split_s3_arn(
    s3_arn: str,
) -> tuple[AwsPartitionEnum, str, str]:
    """
    Split an AWS S3 ARN, returns partition, bucket and key.

    Example::

        >>> split_s3_arn("arn:aws-cn:s3:::my-bucket/my-folder/data.json")
        (<AwsPartitionEnum.aws_cn: 'aws-cn'>, 'my-bucket', 'my-folder/data.json')

    This only checks the format (partition, ``s3`` service, non-empty bucket).
    It does not check bucket naming rules; use
    :func:`~s3pathlib.validate.validate_s3_arn` for that.

    :param s3_arn: ``arn:{partition}:s3:::{bucket}`` or
        ``arn:{partition}:s3:::{bucket}/{key}``, where partition is one of
        :class:`~s3pathlib.constants.AwsPartitionEnum`.

    :raises S3ValidationError: if it is not an S3 ARN of a supported partition.
    """
    for partition in AwsPartitionEnum:
        prefix = f"arn:{partition}:s3:::"
        if s3_arn.startswith(prefix):
            bucket, _, key = s3_arn[len(prefix) :].partition("/")
            _ensure_bucket_part(bucket, s3_arn)
            return partition, bucket, key
    partitions = ", ".join(partition.value for partition in AwsPartitionEnum)
    raise S3ValidationError(
        f"S3 ARN must start with 'arn:{{partition}}:s3:::', "
        f"partition is one of {partitions}, got {s3_arn!r}"
    )


def join_s3_uri(
    bucket: str,
    key: str,
) -> str:
    """
    Join an AWS S3 URI from bucket and key. The inverse of :func:`split_s3_uri`.

    Example::

        >>> join_s3_uri("my-bucket", "my-folder/data.json")
        's3://my-bucket/my-folder/data.json'
        >>> join_s3_uri("my-bucket", "")
        's3://my-bucket/'
    """
    return f"s3://{bucket}/{key}"


def split_parts(key: str) -> list[str]:
    """
    Split an S3 key into parts by ``/``, dropping empty parts.

    Example::

        >>> split_parts("a/b/c")
        ['a', 'b', 'c']
        >>> split_parts("//a//b//c//")
        ['a', 'b', 'c']
    """
    return [part for part in key.split("/") if part]


def smart_join_s3_key(
    parts: list[str],
    is_dir: bool,
) -> str:
    """
    Join parts into an S3 key. Each part may contain ``/``; repeated, leading
    and trailing ``/`` are collapsed so the key has no empty segment.

    Example::

        >>> smart_join_s3_key(parts=["/a/", "b/", "/c"], is_dir=True)
        'a/b/c/'
        >>> smart_join_s3_key(parts=["/a/", "b/", "/c"], is_dir=False)
        'a/b/c'

    :param parts: parts of the S3 key, each may contain ``/``.
    :param is_dir: if True, the key ends with ``/``, otherwise it does not.
        With no parts the key is ``""`` (the bucket root) either way.
    """
    new_parts = list()
    for part in parts:
        new_parts.extend(split_parts(part))
    key = "/".join(new_parts)
    if is_dir and key:
        return key + "/"
    else:
        return key


def _ensure_partition(partition: str) -> AwsPartitionEnum:
    """
    Convert a partition name to :class:`~s3pathlib.constants.AwsPartitionEnum`.

    :raises S3ValidationError: if the partition is not supported.
    """
    try:
        return AwsPartitionEnum(partition)
    except ValueError:
        partitions = ", ".join(partition.value for partition in AwsPartitionEnum)
        raise S3ValidationError(
            f"partition must be one of {partitions}, got {partition!r}"
        ) from None


def _console_endpoint(
    partition: AwsPartitionEnum,
    aws_region: str | None,
) -> tuple[str, str]:
    """
    Return the console host and the ``region=...&`` query string part.

    :raises S3ValidationError: if ``aws_region`` is an empty string.
    """
    domain = AWS_CONSOLE_DOMAIN[partition]
    if aws_region is None:
        return domain, ""
    if not aws_region:
        raise S3ValidationError(
            "aws_region must not be empty, use None for the global console"
        )
    return f"{aws_region}.{domain}", f"region={aws_region}&"


def make_s3_console_url(
    bucket: str | None = None,
    prefix: str | None = None,
    s3_uri: str | None = None,
    version_id: str | None = None,
    aws_region: str | None = None,
    partition: str = AwsPartitionEnum.aws,
) -> str:
    """
    Return the AWS S3 console URL of a bucket, folder or object, to open it in
    a browser.

    Example::

        >>> make_s3_console_url(s3_uri="s3://my-bucket/my-folder/data.json")
        'https://console.aws.amazon.com/s3/object/my-bucket?prefix=my-folder/data.json'
        >>> make_s3_console_url("my-bucket", "my-folder/")
        'https://console.aws.amazon.com/s3/buckets/my-bucket?prefix=my-folder/'
        >>> make_s3_console_url("my-bucket", "")
        'https://console.aws.amazon.com/s3/buckets/my-bucket?tab=objects'
        >>> make_s3_console_url("my-bucket", "data.json", aws_region="us-gov-west-1", partition="aws-us-gov")
        'https://us-gov-west-1.console.amazonaws-us-gov.com/s3/object/my-bucket?region=us-gov-west-1&prefix=data.json'

    Pass either ``bucket`` and ``prefix``, or ``s3_uri``. A prefix ending with
    ``/`` is a folder, an empty prefix is the bucket root, otherwise it is an
    object. The prefix is URL encoded, so keys with ``&``, ``#``, spaces etc.
    still open the right object.

    :param bucket: e.g. ``"my-bucket"``.
    :param prefix: the key, e.g. ``"my-folder/data.json"`` or ``"my-folder/"``.
    :param s3_uri: e.g. ``"s3://my-bucket/my-folder/data.json"``.
    :param version_id: open a specific version of the object.
    :param aws_region: use the regional console, e.g. ``"us-east-1"``.
        ``None`` (the default) uses the global console.
    :param partition: the AWS partition of the console, one of
        :class:`~s3pathlib.constants.AwsPartitionEnum`. Default ``"aws"``.

    :raises ValueError: if the arguments are not one of the two forms above.
    :raises S3ValidationError: if the partition is not supported or
        ``aws_region`` is empty.
    """
    if s3_uri is None:
        if (bucket is None) or (prefix is None):
            raise ValueError("pass both bucket and prefix, or s3_uri")
    else:
        if (bucket is not None) or (prefix is not None):
            raise ValueError("pass either bucket and prefix, or s3_uri, not both")
        bucket, prefix = split_s3_uri(s3_uri)

    partition = _ensure_partition(partition)
    endpoint, region_param = _console_endpoint(partition, aws_region)

    if len(prefix) == 0:
        return f"https://{endpoint}/s3/buckets/{bucket}?{region_param}tab=objects"
    elif prefix.endswith("/"):
        s3_type = "buckets"
    else:
        s3_type = "object"
    prefix_part = f"prefix={quote(prefix, safe='/')}"

    if version_id is None:
        version_part = ""
    else:
        version_part = f"&versionId={quote(version_id, safe='')}"

    return f"https://{endpoint}/s3/{s3_type}/{bucket}?{region_param}{prefix_part}{version_part}"


def ensure_s3_object(
    s3_key_or_uri: str,
) -> None:
    """
    Check that an S3 key or URI is an object, i.e. it does not end with ``/``.

    :raises S3ValidationError: if it is a folder.
    """
    if s3_key_or_uri.endswith("/"):
        raise S3ValidationError(f"{s3_key_or_uri!r} doesn't represent s3 object!")


def ensure_s3_dir(s3_key_or_uri: str) -> None:
    """
    Check that an S3 key or URI is a folder, i.e. it ends with ``/``.

    :raises S3ValidationError: if it is not a folder.
    """
    if not s3_key_or_uri.endswith("/"):
        raise S3ValidationError(f"{s3_key_or_uri!r} doesn't represent s3 dir!")


MAGNITUDE_OF_DATA = {
    i: v for i, v in enumerate(["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"])
}

_DATA_SIZE_UNITS = list(MAGNITUDE_OF_DATA.values())


def repr_data_size(
    size_in_bytes: int,
    precision: int = 2,
) -> str:
    """
    Return a human readable data size. Units are powers of 1024
    (``1 KB = 1024 B``), up to ``YB``; larger sizes are shown in ``YB``.

    Example::

        >>> repr_data_size(100)
        '100 B'
        >>> repr_data_size(100_000)
        '97.66 KB'
        >>> repr_data_size(100_000_000)
        '95.37 MB'

    :param size_in_bytes: the size, must not be negative.
    :param precision: number of digits after the decimal point.

    :raises ValueError: if the size is negative.
    """
    if size_in_bytes < 0:
        raise ValueError(f"data size cannot be negative, got {size_in_bytes}")
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"

    last = len(_DATA_SIZE_UNITS) - 1
    size = float(size_in_bytes)
    index = 0
    while size >= 1024 and index < last:
        size /= 1024
        index += 1
    # rounding can carry over to the next unit, e.g. 1023.999 KB -> 1.00 MB
    if round(size, precision) >= 1024 and index < last:
        size /= 1024
        index += 1
    return f"{size:.{precision}f} {_DATA_SIZE_UNITS[index]}"


_DATA_SIZE_PATTERN = re.compile(r"(\d[\d_,]*(?:\.\d*)?|\.\d+)\s*([A-Za-z]*)")


def parse_data_size(s: str) -> int:
    """
    Parse a human readable data size into bytes. The inverse of
    :func:`repr_data_size`, units are powers of 1024 and case insensitive.
    A number without unit is in bytes. ``_`` and ``,`` thousand separators
    are allowed.

    Example::

        >>> parse_data_size("3.43 MB")
        3596615
        >>> parse_data_size("2,512.4 MB")
        2634442342
        >>> parse_data_size("100")
        100

    :raises ValueError: if the string is not a data size.
    """
    match = _DATA_SIZE_PATTERN.fullmatch(s.strip())
    if match is None:
        raise ValueError(f"cannot parse data size {s!r}, expected e.g. '3.43 MB'")
    number, unit = match.groups()
    unit = unit.upper() or "B"
    if unit not in _DATA_SIZE_UNITS:
        raise ValueError(
            f"unknown unit {match.group(2)!r} in {s!r}, "
            f"expected one of {', '.join(_DATA_SIZE_UNITS)}"
        )
    value = float(number.replace("_", "").replace(",", ""))
    return int(value * 1024 ** _DATA_SIZE_UNITS.index(unit))


def grouper_list(
    l: T.Iterable,
    n: int,
) -> T.Iterable[list]:
    """
    Split an iterable into lists of ``n`` items; the last list holds the rest.

    Example::

        >>> list(grouper_list(range(10), n=3))
        [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]

    :param l: an iterable, consumed once.
    :param n: number of items per list, at least 1.

    :raises ValueError: if ``n`` is less than 1.
    """
    # this is a plain function that returns a generator, so that a bad ``n`` is
    # reported when it is called, not when the iteration starts
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")
    return _grouper_list(l, n)


def _grouper_list(l: T.Iterable, n: int) -> T.Iterable[list]:
    chunk = list()
    for item in l:
        chunk.append(item)
        if len(chunk) == n:
            yield chunk
            chunk = list()
    if chunk:
        yield chunk

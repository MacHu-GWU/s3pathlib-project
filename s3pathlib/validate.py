# -*- coding: utf-8 -*-

"""
Validate S3 bucket names, keys, URIs and ARNs.

The validators check whether a value can be used to address S3 in an API call,
not whether it can be used to create a new bucket. For example, an access
point alias (ends with ``-s3alias``) and a directory bucket name (ends with
``--x-s3``) are both accepted, because S3 APIs accept them as bucket names.

Every validator raises :class:`~s3pathlib.exc.S3ValidationError`, which is
also a ``ValueError``.
"""

import string

from .constants import S3_KEY_MAX_BYTES
from .exc import S3ValidationError

valid_bucket_charset: set = set(string.ascii_lowercase + string.digits + ".-")
letter_and_number: set = set(string.ascii_lowercase + string.digits)


def _is_ip_address_like(bucket: str) -> bool:
    """
    Check whether the bucket name is formatted as an IPv4 address,
    e.g. ``192.168.5.4``.
    """
    parts = bucket.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        if not (0 <= int(part) <= 255):
            return False
    return True


def validate_s3_bucket(bucket: str) -> None:
    """
    Validate an S3 bucket name.

    Rules checked:

    - 3 to 63 characters long.
    - Only lowercase letters, numbers, dots (``.``) and hyphens (``-``).
    - Begins and ends with a letter or number.
    - Not formatted as an IPv4 address (e.g. ``192.168.5.4``).
    - Does not start with ``xn--``.

    Ref: `Bucket naming rules <https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html>`_

    :raises S3ValidationError: if the bucket name is not valid.

    .. versionchanged:: 3.0.0

        Raise :class:`~s3pathlib.exc.S3ValidationError` (still a ``ValueError``).
        Accept access point aliases that end with ``-s3alias``.
    """
    if not (3 <= len(bucket) <= 63):
        raise S3ValidationError(
            "Bucket names must be between 3 and 63 characters long."
        )

    invalid_chars = set(bucket).difference(valid_bucket_charset)
    if len(invalid_chars) != 0:
        raise S3ValidationError(
            (
                "Bucket names can consist only of lowercase letters, numbers, "
                "dots (.), and hyphens (-). invalid char found {}"
            ).format(invalid_chars)
        )

    if (bucket[0] not in letter_and_number) or (bucket[-1] not in letter_and_number):
        raise S3ValidationError(
            "Bucket names must begin and end with a letter or number."
        )

    if _is_ip_address_like(bucket):
        raise S3ValidationError(
            "Bucket names must not be formatted as an IP address "
            "(for example, 192.168.5.4)."
        )

    if bucket.startswith("xn--"):
        raise S3ValidationError("Bucket names must not start with the prefix xn--.")


def validate_s3_key(key: str) -> None:
    """
    Validate an S3 object key (or a prefix).

    S3 accepts any UTF-8 character in a key, so only these rules are checked:

    - The key can be encoded as UTF-8.
    - The key is at most 1024 bytes long in UTF-8.

    An empty key is valid; it means the bucket root.

    Ref: `Object key naming <https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html>`_

    :raises S3ValidationError: if the key is not valid.

    .. versionchanged:: 3.0.0

        Accept every UTF-8 character (e.g. non-ASCII text, ``~``, ``%``), and
        measure the length limit in UTF-8 bytes instead of characters.
        Raise :class:`~s3pathlib.exc.S3ValidationError` (still a ``ValueError``).
    """
    try:
        n_bytes = len(key.encode("utf-8"))
    except UnicodeEncodeError as e:
        raise S3ValidationError(f"S3 key {key!r} is not valid UTF-8: {e}") from e

    if n_bytes > S3_KEY_MAX_BYTES:
        raise S3ValidationError(
            f"S3 key must be at most {S3_KEY_MAX_BYTES} bytes in UTF-8, "
            f"got {n_bytes} bytes."
        )


def validate_s3_uri(uri: str) -> None:
    """
    Validate an S3 URI: ``s3://{bucket}``, ``s3://{bucket}/`` or
    ``s3://{bucket}/{key}``.

    The bucket and key parts are checked by :func:`validate_s3_bucket` and
    :func:`validate_s3_key`.

    :raises S3ValidationError: if the URI is not valid.

    .. versionchanged:: 3.0.0

        Accept a bucket URI without the trailing slash, e.g. ``s3://bucket``.
    """
    if not uri.startswith("s3://"):
        raise S3ValidationError("S3 URI must starts with 's3://'")

    bucket, _, key = uri[len("s3://") :].partition("/")
    validate_s3_bucket(bucket)
    validate_s3_key(key)


def validate_s3_arn(arn: str) -> None:
    """
    Validate an S3 ARN:

    - bucket: ``arn:aws:s3:::{bucket}``
    - object: ``arn:aws:s3:::{bucket}/{key}``
    - directory: ``arn:aws:s3:::{bucket}/{prefix}/``

    The bucket and key parts are checked by :func:`validate_s3_bucket` and
    :func:`validate_s3_key`. Only the ``aws`` partition is supported.

    :raises S3ValidationError: if the ARN is not valid.
    """
    if not arn.startswith("arn:aws:s3:::"):
        raise S3ValidationError("S3 ARN must starts with 'arn:aws:s3:::'")

    bucket, _, key = arn[len("arn:aws:s3:::") :].partition("/")
    validate_s3_bucket(bucket)
    validate_s3_key(key)

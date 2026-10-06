# -*- coding: utf-8 -*-

"""
Optional tools to check S3 bucket names, keys, URIs and ARNs.

``s3pathlib`` itself never calls these validators. Checking is split in two:

- **Format**: whether a string is a well formed S3 URI or ARN that can be
  split into bucket and key. Only the client can check this, because S3 APIs
  receive the bucket and key separately. ``s3pathlib`` always checks the format
  when it parses a string (``S3Path(...)``, ``S3Path.from_s3_uri``,
  :func:`~s3pathlib.utils.split_s3_uri`, ...).
- **Naming rules**: bucket naming rules and the key length limit. S3 is the
  authority on these and enforces them when you call the API. A copy of the
  rules on the client gets out of date and would reject valid names, such as
  legacy buckets created before March 2018 (uppercase letters, underscores),
  access point aliases and directory buckets. So ``s3pathlib`` does not check
  them when it reads from or sends to S3.

Call these validators yourself when you want an early, clear error, for
example to check a bucket name typed by a user before creating the bucket.

Every validator raises :class:`~s3pathlib.exc.S3ValidationError`, which is
also a ``ValueError``.
"""

import string

from .constants import S3_KEY_MAX_BYTES
from .constants import S3_BUCKET_MIN_LENGTH
from .constants import S3_BUCKET_MAX_LENGTH
from .constants import S3_BUCKET_RESERVED_PREFIXES
from .constants import S3_BUCKET_RESERVED_SUFFIXES
from .exc import S3ValidationError
from .utils import split_s3_uri
from .utils import split_s3_arn

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
    Check a name against the naming rules for a **new general purpose bucket**.

    Rules checked:

    - 3 to 63 characters long.
    - Only lowercase letters, numbers, periods (``.``) and hyphens (``-``).
    - Begins and ends with a letter or number.
    - No two adjacent periods.
    - Not formatted as an IPv4 address (e.g. ``192.168.5.4``).
    - Does not start with a reserved prefix: ``xn--``, ``sthree-``,
      ``amzn-s3-demo-``.
    - Does not end with a reserved suffix: ``-s3alias``, ``--ol-s3``,
      ``.mrap``, ``--x-s3``, ``--table-s3``.

    Names that S3 accepts for an *existing* bucket can still fail this check:
    legacy buckets created in us-east-1 before March 1, 2018, access point
    aliases, directory buckets and S3 Tables buckets. That is expected.

    The ``-an`` suffix is not checked: it is valid for buckets created in an
    account regional namespace.

    Ref: `General purpose bucket naming rules <https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html>`_

    :raises S3ValidationError: if the name breaks a rule.
    """
    if not (S3_BUCKET_MIN_LENGTH <= len(bucket) <= S3_BUCKET_MAX_LENGTH):
        raise S3ValidationError(
            f"Bucket names must be between {S3_BUCKET_MIN_LENGTH} and "
            f"{S3_BUCKET_MAX_LENGTH} characters long."
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

    if ".." in bucket:
        raise S3ValidationError("Bucket names must not contain two adjacent periods.")

    if _is_ip_address_like(bucket):
        raise S3ValidationError(
            "Bucket names must not be formatted as an IP address "
            "(for example, 192.168.5.4)."
        )

    for prefix in S3_BUCKET_RESERVED_PREFIXES:
        if bucket.startswith(prefix):
            raise S3ValidationError(
                f"Bucket names must not start with the reserved prefix {prefix!r}."
            )

    for suffix in S3_BUCKET_RESERVED_SUFFIXES:
        if bucket.endswith(suffix):
            raise S3ValidationError(
                f"Bucket names must not end with the reserved suffix {suffix!r}."
            )


def validate_s3_key(key: str) -> None:
    """
    Check an S3 object key (or a prefix).

    S3 accepts any UTF-8 character in a key, so only these rules are checked:

    - The key can be encoded as UTF-8.
    - The key is at most 1024 bytes long in UTF-8.

    An empty key is valid; it means the bucket root.

    Ref: `Object key naming <https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html>`_

    :raises S3ValidationError: if the key is not valid.
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
    Check an S3 URI: ``s3://{bucket}``, ``s3://{bucket}/`` or
    ``s3://{bucket}/{key}``.

    The format is checked by :func:`~s3pathlib.utils.split_s3_uri`, then the
    bucket and key by :func:`validate_s3_bucket` and :func:`validate_s3_key`.

    :raises S3ValidationError: if the URI is not valid.
    """
    bucket, key = split_s3_uri(uri)
    validate_s3_bucket(bucket)
    validate_s3_key(key)


def validate_s3_arn(arn: str) -> None:
    """
    Check an S3 ARN:

    - bucket: ``arn:{partition}:s3:::{bucket}``
    - object: ``arn:{partition}:s3:::{bucket}/{key}``
    - directory: ``arn:{partition}:s3:::{bucket}/{prefix}/``

    ``partition`` is one of :class:`~s3pathlib.constants.AwsPartitionEnum`.
    The format is checked by :func:`~s3pathlib.utils.split_s3_arn`, then the
    bucket and key by :func:`validate_s3_bucket` and :func:`validate_s3_key`.

    :raises S3ValidationError: if the ARN is not valid.
    """
    _, bucket, key = split_s3_arn(arn)
    validate_s3_bucket(bucket)
    validate_s3_key(key)

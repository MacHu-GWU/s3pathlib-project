# -*- coding: utf-8 -*-

"""
Helpers for S3 object user-defined metadata.
"""

from __future__ import annotations

import warnings

from .type import MetadataType


def warn_upper_case_in_metadata_key(metadata: MetadataType):
    """
    Emit a ``UserWarning`` for each user-defined metadata key that has
    uppercase letters.

    S3 stores user-defined metadata keys in lowercase, so a key such as
    ``"Author"`` is read back as ``"author"``.

    Ref: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html#UserMetadata
    """
    for k, v in metadata.items():
        if k.lower() != k:
            msg = (
                f"metadata key {k!r} has uppercase letters; S3 stores "
                f"user-defined metadata keys in lowercase, so it is read back "
                f"as {k.lower()!r}. See "
                f"https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html#UserMetadata"
            )
            warnings.warn(msg, UserWarning)

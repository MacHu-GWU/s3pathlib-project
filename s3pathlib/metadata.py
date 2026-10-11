# -*- coding: utf-8 -*-

"""
Helpers for S3 object user-defined metadata.
"""

from __future__ import annotations

import warnings

from .type import MetadataType

_USER_METADATA_DOC = "https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html#UserMetadata"


def warn_upper_case_in_metadata_key(metadata: MetadataType):
    """
    Emit a ``UserWarning`` for each user-defined metadata key that has
    uppercase letters.

    S3 stores user-defined metadata keys in lowercase, so a key such as
    ``"Author"`` is read back as ``"author"``.

    Ref: `User-defined object metadata <https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html#UserMetadata>`_
    """
    # .keys() on purpose: metadata=None keeps failing with AttributeError
    for key in metadata.keys():
        if key.lower() != key:
            msg = (
                f"metadata key {key!r} has uppercase letters; S3 stores "
                f"user-defined metadata keys in lowercase, so it is read back "
                f"as {key.lower()!r}. See {_USER_METADATA_DOC}"
            )
            warnings.warn(msg, UserWarning)

# -*- coding: utf-8 -*-

"""
Resolve what s3 client to use for API call.
"""

from __future__ import annotations

import typing as T

from ..aws import S3Context

if T.TYPE_CHECKING:  # pragma: no cover
    from boto_session_manager.api import BotoSesManager
    from mypy_boto3_s3 import S3Client


def resolve_s3_client(
    s3_context: S3Context,
    bsm: BotoSesManager | S3Client | None = None,
) -> S3Client:
    """
    Figure out the S3 client to use for an API call.

    - ``bsm`` is ``None``: use the default client, ``s3_context.s3_client``.
    - ``bsm`` has an ``s3_client`` attribute (e.g. a ``BotoSesManager``): use
      that client.
    - otherwise ``bsm`` is an S3 client: use it as is.
    """
    if bsm is None:
        return s3_context.s3_client
    else:
        try:
            return bsm.s3_client
        except AttributeError:
            return bsm

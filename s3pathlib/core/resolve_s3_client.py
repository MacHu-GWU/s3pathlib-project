# -*- coding: utf-8 -*-

"""
Resolve what s3 client to use for API call.
"""

from __future__ import annotations

import typing as T

from ..aws import Context

if T.TYPE_CHECKING:  # pragma: no cover
    from boto_session_manager.api import BotoSesManager
    from mypy_boto3_s3 import S3Client


def resolve_s3_client(
    context: Context,
    bsm: BotoSesManager | S3Client | None = None,
) -> S3Client:
    """
    Figure out the final boto session to use for API call.
    If ``BotoSesManager`` is defined, then prioritize to use it.
    If bsm is an pre-defined s3 client, then use it.
    """
    if bsm is None:
        return context.s3_client
    else:
        try:
            return bsm.s3_client
        except AttributeError:
            return bsm

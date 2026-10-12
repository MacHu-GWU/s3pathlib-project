# -*- coding: utf-8 -*-

"""
Resolve what S3 client to use for an API call.

**Design notes**

*Only a boto3 S3 client is accepted,* not a ``BotoSesManager`` or any object
with an ``s3_client`` attribute. The library only ever needs the client, and a
client built from an assumed role keeps refreshing its own credentials, so
nothing is lost by passing ``bsm.s3_client``. A wrong object fails at the call
with a message that says so, instead of deep inside botocore.

*The remembered client is not resolved here.* The client an ``S3Path``
remembers is only used to load its metadata snapshot, see
:mod:`s3pathlib.core.metadata`.
"""

from __future__ import annotations

import typing as T

from botocore.client import BaseClient

from ..aws import S3Context

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


def resolve_s3_client(
    s3_context: S3Context,
    s3_client: S3Client | None = None,
) -> S3Client:
    """
    Figure out the S3 client to use for an API call: ``s3_client`` if it is
    given, otherwise the default client, ``s3_context.s3_client``.

    :raises TypeError: if ``s3_client`` is not a boto3 S3 client, e.g. a
        ``BotoSesManager`` (pass its ``s3_client`` instead).
    """
    if s3_client is None:
        return s3_context.s3_client
    if isinstance(s3_client, BaseClient):
        if s3_client.meta.service_model.service_name == "s3":
            return s3_client
    raise TypeError(
        f"s3_client must be a boto3 S3 client, got {s3_client!r}; for a "
        "BotoSesManager, pass bsm.s3_client"
    )

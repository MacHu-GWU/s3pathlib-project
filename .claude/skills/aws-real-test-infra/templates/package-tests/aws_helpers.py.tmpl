# -*- coding: utf-8 -*-

"""
Helpers for tests that call the AWS API (moto or real AWS): record what a
client sends, and build a client with refreshable credentials.
"""

from __future__ import annotations

import typing as T
import contextlib
import datetime

import boto3
import botocore.session
from botocore.credentials import DeferredRefreshableCredentials

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


@contextlib.contextmanager
def record_api_calls(s3_client: S3Client):
    """
    Record the name of every S3 API call made through ``s3_client``, e.g.
    ``["HeadObject", "PutObject"]``. Use it to assert which calls a method
    makes, or that it makes none.
    """
    calls = list()

    def record(model, **kwargs):
        calls.append(model.name)

    events = s3_client.meta.events
    events.register("before-call.s3.*", record)
    try:
        yield calls
    finally:
        events.unregister("before-call.s3.*", record)


@contextlib.contextmanager
def record_api_params(s3_client: S3Client):
    """
    Record the name and the parameters of every S3 API call made through
    ``s3_client``, e.g. ``[("HeadObject", {"Bucket": "b", "Key": "k"})]``.
    The parameters are the ones the caller passes to boto3, before botocore
    converts them. Use it to assert that an argument reaches every call that
    can take it.
    """
    calls = list()

    def record(params, model, **kwargs):
        calls.append((model.name, dict(params)))

    events = s3_client.meta.events
    events.register("provide-client-params.s3.*", record)
    try:
        yield calls
    finally:
        events.unregister("provide-client-params.s3.*", record)


def make_refreshable_s3_client() -> tuple[S3Client, list[str]]:
    """
    Create an S3 client whose credentials expire one second after each fetch,
    so that botocore fetches new ones before every request (it refreshes
    credentials that expire within the next minutes). This is how a client
    built from an assumed role session keeps working after the role session
    expires. The credentials are fake, so use it with moto only.

    :return: the client, and the list of access keys fetched so far
        (``"AK1"``, ``"AK2"``, ...), which grows on every fetch.
    """
    fetched_keys = list()

    def fetch() -> dict:
        access_key = f"AK{len(fetched_keys) + 1}"
        fetched_keys.append(access_key)
        now = datetime.datetime.now(datetime.timezone.utc)
        expiry_time = now + datetime.timedelta(seconds=1)
        return {
            "access_key": access_key,
            "secret_key": "secret",
            "token": "token",
            "expiry_time": expiry_time.isoformat(),
        }

    botocore_session = botocore.session.Session()
    botocore_session._credentials = DeferredRefreshableCredentials(
        refresh_using=fetch,
        method="custom-refreshable",
    )
    boto_ses = boto3.session.Session(
        botocore_session=botocore_session,
        region_name="us-east-1",
    )
    return boto_ses.client("s3"), fetched_keys


@contextlib.contextmanager
def record_signing_access_keys(s3_client: S3Client):
    """
    Record the access key that signs each request sent by ``s3_client``.
    """
    access_keys = list()

    def record(request, **kwargs):
        # "AWS4-HMAC-SHA256 Credential=AK1/20261007/us-east-1/s3/aws4_request, ..."
        authorization = request.headers["Authorization"]
        if isinstance(authorization, bytes):
            authorization = authorization.decode("utf-8")
        credential = authorization.split("Credential=")[1]
        access_keys.append(credential.split("/")[0])

    events = s3_client.meta.events
    events.register("before-send.s3", record)
    try:
        yield access_keys
    finally:
        events.unregister("before-send.s3", record)

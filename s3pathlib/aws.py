# -*- coding: utf-8 -*-

"""
Manage the AWS environment that ``s3pathlib`` dealing with.
"""

from __future__ import annotations

import typing as T

try:
    import boto3
except ImportError:  # pragma: no cover
    pass
except:  # pragma: no cover
    raise

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_sts import STSClient
import botocore


class Context:
    """
    A globally available context object managing AWS SDK credentials.

    TODO: use singleton pattern to create context object
    """

    def __init__(self):
        self.boto_ses: boto3.session.Session | None = None
        self._aws_region: str | None = None
        self._aws_account_id: str | None = None
        self._s3_client: S3Client | None = None
        self._sts_client: STSClient | None = None

        # try to create default session
        try:
            self.boto_ses = boto3.session.Session()
        except:  # pragma: no cover
            pass

    def attach_boto_session(self, boto_ses: boto3.session.Session):
        """
        Attach a custom boto session, also remove caches.
        """
        self.boto_ses = boto_ses
        self._s3_client = None
        self._sts_client = None
        self._aws_account_id = None
        self._aws_region = None

    def attach_s3_client(self, s3_client: S3Client):
        """
        Attach a custom s3 client.
        """
        self._s3_client = s3_client

    def attach_sts_client(self, sts_client: STSClient):
        """
        Attach a custom sts client.
        """
        self._sts_client = sts_client

    @property
    def s3_client(self) -> S3Client:
        """
        Access the s3 client.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#client
        """
        if self._s3_client is None:
            self._s3_client = self.boto_ses.client("s3")
        return self._s3_client

    @property
    def sts_client(self) -> STSClient:
        """
        Access the s3 client.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#client
        """
        if self._sts_client is None:
            self._sts_client = self.boto_ses.client("sts")
        return self._sts_client

    @property
    def aws_account_id(self) -> str:
        """
        The AWS Account ID of the current boto session.
        """
        if self._aws_account_id is None:
            self._aws_account_id = self.sts_client.get_caller_identity()["Account"]
        return self._aws_account_id

    @property
    def aws_region(self) -> str:
        """
        The AWS Region of the current boto session.
        """
        if self._aws_region is None:
            self._aws_region = self.boto_ses.region_name
        return self._aws_region


context = Context()

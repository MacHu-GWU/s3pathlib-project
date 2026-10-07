# -*- coding: utf-8 -*-

"""
The default S3 client that ``s3pathlib`` uses to call the AWS API.

Every ``S3Path`` method that calls AWS takes an optional ``bsm`` argument. When
it is not given, the method uses ``s3_context.s3_client``::

    import boto3
    from s3pathlib.api import S3Path
    from s3pathlib.api import s3_context

    # use your own client for every call that does not pass one explicitly
    s3_context.attach_s3_client(
        boto3.session.Session(profile_name="my_aws_profile").client("s3")
    )
    S3Path("bucket", "file.txt").read_text()

If no client is attached, the first call creates one from the default
credentials and region (environment variables, ``~/.aws``, instance role, ...),
as ``boto3.client("s3")`` does. It is created when first used, not when
``s3pathlib`` is imported, so environment variables set after the import are
honored, and an error (e.g. an unknown ``AWS_PROFILE``) is raised to the caller
instead of being hidden.

Thread safety: the client is created at most once, under a lock, from a new
``boto3.session.Session`` (a session object is not thread safe, a client is).
``attach_s3_client`` replaces the client in one step, so a thread reading
``s3_client`` at the same time gets either the old or the new client.

``s3_context`` was called ``context`` before 3.0.0. The old name was removed: it
collides with the ``context`` argument of AWS Lambda handlers
(``def lambda_handler(event, context)``).
"""

from __future__ import annotations

import typing as T
import threading

import boto3

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


class S3Context:
    """
    Holds the default S3 client of ``s3pathlib``. Use the global instance
    ``s3_context`` instead of creating your own.
    """

    def __init__(self):
        self._s3_client: S3Client | None = None
        self._lock = threading.Lock()

    def attach_s3_client(self, s3_client: S3Client):
        """
        Use ``s3_client`` for every API call that does not pass a client
        explicitly. Replaces the client attached or created before.

        Any object with the boto3 S3 client methods is accepted (e.g. a stub
        in tests).

        :raises TypeError: if ``s3_client`` is ``None``.
        """
        if s3_client is None:
            raise TypeError("s3_client must be a boto3 S3 client, not None")
        with self._lock:
            self._s3_client = s3_client

    @property
    def s3_client(self) -> S3Client:
        """
        The attached S3 client. If none is attached, create one from the
        default credentials and region on first access, and keep it.
        """
        s3_client = self._s3_client
        if s3_client is None:
            with self._lock:
                # another thread may have created or attached it meanwhile
                if self._s3_client is None:
                    self._s3_client = boto3.session.Session().client("s3")
                s3_client = self._s3_client
        return s3_client


s3_context = S3Context()

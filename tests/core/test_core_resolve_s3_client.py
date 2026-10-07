# -*- coding: utf-8 -*-

"""
Test ``resolve_s3_client``: which S3 client an API call uses, and the explicit
``bsm`` argument of ``S3Path`` methods.

This is the only test file that passes a client explicitly (``bsm=``); the
other tests rely on ``s3_context``. When ``bsm`` is renamed, only this file
changes.

Test order:

1. ``resolve_s3_client`` with nothing, a client, and an object holding a client;
2. an ``S3Path`` method with ``bsm=`` calls AWS through that client only;
3. an explicit client with refreshable credentials keeps working.
"""

import contextlib
import types

from s3pathlib.api import s3_context
from s3pathlib.core.resolve_s3_client import resolve_s3_client
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock import BaseTest
from s3pathlib.tests.mock import make_refreshable_s3_client
from s3pathlib.tests.mock import record_signing_access_keys


@contextlib.contextmanager
def record_api_calls(s3_client):
    """
    Record the name of every API call made through ``s3_client``.
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


class ResolveS3ClientMixin(BaseTest):
    module = "core.resolve_s3_client"

    # --------------------------------------------------------------------------
    # 1. resolve_s3_client
    # --------------------------------------------------------------------------
    def test_resolve_none(self):
        """
        Without an explicit client, use the default client of ``s3_context``.
        """
        assert resolve_s3_client(s3_context, None) is s3_context.s3_client

    def test_resolve_s3_client(self):
        """
        An S3 client is used as is.
        """
        s3_client = self.boto_ses.client("s3")
        assert resolve_s3_client(s3_context, s3_client) is s3_client

    def test_resolve_object_with_s3_client(self):
        """
        An object with an ``s3_client`` attribute (e.g. a ``BotoSesManager``)
        gives that client.
        """
        s3_client = self.boto_ses.client("s3")
        bsm = types.SimpleNamespace(s3_client=s3_client)
        assert resolve_s3_client(s3_context, bsm) is s3_client

    # --------------------------------------------------------------------------
    # 2. S3Path methods with bsm=
    # --------------------------------------------------------------------------
    def test_s3path_explicit_client(self):
        """
        ``bsm=`` sends the call through the given client, not through
        ``s3_context``.
        """
        p = self.s3dir_root.joinpath("explicit-client", "file.txt")
        s3_client = self.boto_ses.client("s3")
        with record_api_calls(s3_context.s3_client) as default_calls:
            with record_api_calls(s3_client) as explicit_calls:
                p.write_text("hello", bsm=s3_client)
        assert explicit_calls == ["PutObject"]
        assert default_calls == []

    # --------------------------------------------------------------------------
    # 3. Refreshable credentials
    # --------------------------------------------------------------------------
    def test_explicit_client_refreshable_credentials(self):
        """
        An explicit client with refreshable credentials (e.g. from an assumed
        role) gets new credentials when they expire and signs with them.
        """
        p = self.s3dir_root.joinpath("refreshable-credentials", "file.txt")
        s3_client, fetched_keys = make_refreshable_s3_client()
        with record_signing_access_keys(s3_client) as access_keys:
            for _ in range(3):
                p.write_text("hello", bsm=s3_client)
        assert fetched_keys == ["AK1", "AK2", "AK3"]
        assert access_keys == ["AK1", "AK2", "AK3"]


# class Test(ResolveS3ClientMixin):
#     use_mock = False


class TestUseMock(ResolveS3ClientMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(__file__, module="s3pathlib.core.resolve_s3_client", preview=False)

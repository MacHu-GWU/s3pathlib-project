# -*- coding: utf-8 -*-

"""
Test ``s3pathlib.aws``: the default S3 client ``s3_context``.

Test order:

1. the default client: created on first access, from the environment at that
   time, and errors are raised to the caller;
2. ``attach_s3_client``;
3. thread safety;
4. the names removed in 3.0.0 (including ``context`` and ``Context``);
5. the global ``s3_context`` is the client ``S3Path`` uses;
6. refreshable credentials (e.g. an assumed role) keep working.

Except in 5 and 6, every test uses its own ``S3Context()``, so it does not
change the global client the other tests use.
"""

import importlib
import subprocess
import sys
import threading
import time

import boto3
import botocore.exceptions
import pytest

from s3pathlib.api import s3_context
from s3pathlib.aws import S3Context
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import make_refreshable_s3_client
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.aws_helpers import record_signing_access_keys
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import mock_only


class FakeS3Client:
    """
    Stands for an S3 client; ``attach_s3_client`` accepts any object.
    """


def count_new_sessions(monkeypatch, delay: float = 0) -> list:
    """
    Replace ``boto3.session.Session`` with a fake whose ``client("s3")``
    returns a new ``FakeS3Client``, and wait ``delay`` seconds in the
    constructor to widen race windows.

    :return: the list of sessions created, which grows on every creation.
    """
    sessions = list()

    class FakeSession:
        def __init__(self):
            time.sleep(delay)
            sessions.append(self)

        def client(self, service_name: str):
            assert service_name == "s3"
            return FakeS3Client()

    monkeypatch.setattr(boto3.session, "Session", FakeSession)
    return sessions



class AwsMixin(BaseTest):
    module = "aws"

    # --------------------------------------------------------------------------
    # 1. The default client
    # --------------------------------------------------------------------------
    def test_s3_client_created_once_on_first_access(self, monkeypatch):
        """
        Creating the context creates no client; the first access creates one
        and later accesses return the same client.
        """
        sessions = count_new_sessions(monkeypatch)
        ctx = S3Context()
        assert sessions == []
        s3_client = ctx.s3_client
        assert isinstance(s3_client, FakeS3Client)
        assert ctx.s3_client is s3_client
        assert len(sessions) == 1

    def test_s3_client_uses_environment_at_first_access(self, monkeypatch):
        """
        The default client reads the region when it is first used, so a
        setting made after the context exists is honored.
        """
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        ctx = S3Context()
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
        assert ctx.s3_client.meta.region_name == "eu-west-1"

    def test_s3_client_raises_and_recovers(self, monkeypatch):
        """
        An unknown profile raises ``ProfileNotFound`` on access, not at
        import time (it would be swallowed and every later call would fail
        with ``AttributeError: 'NoneType' object has no attribute 'client'``),
        and the next access works once the environment is fixed.
        """
        monkeypatch.setenv("AWS_PROFILE", "s3pathlib-no-such-profile")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        ctx = S3Context()
        with pytest.raises(botocore.exceptions.ProfileNotFound):
            _ = ctx.s3_client
        monkeypatch.delenv("AWS_PROFILE")
        assert ctx.s3_client.meta.region_name == "us-east-1"

    def test_import_creates_no_client(self):
        """
        Importing ``s3pathlib`` creates no boto session, so it has no side
        effect and cannot fail because of the AWS configuration.
        """
        code = (
            "import boto3.session\n"
            "def fail(*args, **kwargs):\n"
            "    raise AssertionError('a boto session was created')\n"
            "boto3.session.Session = fail\n"
            "import s3pathlib.api\n"
            "print('imported')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert result.stderr == ""
        assert result.stdout == "imported\n"

    # --------------------------------------------------------------------------
    # 2. attach_s3_client
    # --------------------------------------------------------------------------
    def test_attach_s3_client(self, monkeypatch):
        """
        The attached object is returned as is (any object is accepted), and
        no default client is created.
        """
        sessions = count_new_sessions(monkeypatch)
        ctx = S3Context()
        s3_client = FakeS3Client()
        ctx.attach_s3_client(s3_client)
        assert ctx.s3_client is s3_client
        assert sessions == []

    def test_attach_s3_client_replaces_previous(self):
        """
        Attaching again replaces the client attached or created before.
        """
        ctx = S3Context()
        _ = ctx.s3_client
        s3_client_1 = FakeS3Client()
        s3_client_2 = FakeS3Client()
        ctx.attach_s3_client(s3_client_1)
        assert ctx.s3_client is s3_client_1
        ctx.attach_s3_client(s3_client_2)
        assert ctx.s3_client is s3_client_2

    def test_attach_s3_client_none(self):
        """
        ``None`` is rejected; it is not a way to reset to the default client.
        """
        ctx = S3Context()
        with pytest.raises(TypeError, match="s3_client must be a boto3 S3 client"):
            ctx.attach_s3_client(None)

    # --------------------------------------------------------------------------
    # 3. Thread safety
    # --------------------------------------------------------------------------
    def test_s3_client_first_access_from_many_threads(self, monkeypatch):
        """
        Threads that access the default client at the same time create it only
        once and all get the same client. A slow session constructor makes
        every thread enter the creation at the same time.
        """
        sessions = count_new_sessions(monkeypatch, delay=0.05)
        ctx = S3Context()
        n_thread = 32
        barrier = threading.Barrier(n_thread)
        results = [None] * n_thread

        def access(i: int):
            barrier.wait()
            results[i] = ctx.s3_client

        threads = [threading.Thread(target=access, args=(i,)) for i in range(n_thread)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(sessions) == 1
        assert len({id(s3_client) for s3_client in results}) == 1
        assert results[0] is ctx.s3_client

    def test_s3_client_read_while_attaching(self):
        """
        A thread that reads the client while another thread attaches clients
        always gets one of the attached clients, never ``None`` or a default
        client.
        """
        ctx = S3Context()
        s3_client_1 = FakeS3Client()
        s3_client_2 = FakeS3Client()
        ctx.attach_s3_client(s3_client_1)
        stop = threading.Event()
        seen = set()

        def read():
            while not stop.is_set():
                seen.add(id(ctx.s3_client))

        reader = threading.Thread(target=read)
        reader.start()
        for i in range(2000):
            if i % 2 == 0:
                ctx.attach_s3_client(s3_client_2)
            else:
                ctx.attach_s3_client(s3_client_1)
        stop.set()
        reader.join()

        assert seen <= {id(s3_client_1), id(s3_client_2)}

    # --------------------------------------------------------------------------
    # 4. Names removed in 3.0.0
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "name",
        [
            "attach_boto_session",
            "attach_sts_client",
            "boto_ses",
            "sts_client",
            "aws_account_id",
            "aws_region",
        ],
    )
    def test_removed_members(self, name):
        """
        The context only holds the S3 client. Attach a client with
        ``attach_s3_client(boto_ses.client("s3"))``.
        """
        assert hasattr(S3Context(), name) is False

    @pytest.mark.parametrize("module_name", ["s3pathlib.api", "s3pathlib", "s3pathlib.aws"])
    def test_removed_context_name(self, module_name):
        """
        The name ``context`` is not defined in any module, it would collide
        with the ``context`` argument of Lambda handlers; use ``s3_context``.
        """
        module = importlib.import_module(module_name)
        assert hasattr(module, "context") is False

    def test_removed_context_class_name(self):
        """
        The class is ``S3Context``, not ``Context``.
        """
        module = importlib.import_module("s3pathlib.aws")
        assert hasattr(module, "Context") is False
        assert isinstance(s3_context, S3Context)

    # --------------------------------------------------------------------------
    # 5. The global ``s3_context``
    # --------------------------------------------------------------------------
    def test_s3path_uses_s3_context(self):
        """
        An ``S3Path`` method without an explicit client calls AWS through
        ``s3_context.s3_client``.
        """
        p = self.s3dir_test.joinpath("file.txt")
        with record_api_calls(s3_context.s3_client) as calls:
            p.write_text("hello")
        assert calls == ["PutObject"]

    # --------------------------------------------------------------------------
    # 6. Refreshable credentials
    # --------------------------------------------------------------------------
    @mock_only("the refreshable credentials are fake")
    def test_refreshable_credentials(self):
        """
        A client with refreshable credentials (e.g. from an assumed role) gets
        new credentials when they expire and signs with them, also when it is
        attached to ``s3_context``. This is why attaching a client is enough,
        without keeping a boto session.
        """
        p = self.s3dir_test.joinpath("file.txt")
        original = s3_context.s3_client
        s3_client, fetched_keys = make_refreshable_s3_client()
        s3_context.attach_s3_client(s3_client)
        try:
            with record_signing_access_keys(s3_client) as access_keys:
                for _ in range(3):
                    p.write_text("hello")
        finally:
            s3_context.attach_s3_client(original)
        assert fetched_keys == ["AK1", "AK2", "AK3"]
        assert access_keys == ["AK1", "AK2", "AK3"]


class TestMock(AwsMixin):
    use_mock = True


class TestRealAws(AwsMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.aws",
        preview=False,
    )

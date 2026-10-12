# -*- coding: utf-8 -*-

"""
Test ``resolve_s3_client``: which S3 client an API call uses, and the explicit
``s3_client`` argument of ``S3Path`` methods.

This is the only test file that passes a client explicitly (``s3_client=``);
the other tests rely on ``s3_context``.

Test order:

1. ``resolve_s3_client`` with nothing, an S3 client, and anything else;
2. an ``S3Path`` method with ``s3_client=`` calls AWS through that client
   only; there is no ``bsm`` argument;
3. an ``S3Path`` produced with ``s3_client=`` loads its missing metadata with
   that client, but its other methods do not use it (see
   ``s3pathlib.core.metadata``);
4. an explicit client with refreshable credentials keeps working.
"""

import inspect
import subprocess
import types

import boto3
import pytest

from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.core.resolve_s3_client import resolve_s3_client
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import make_refreshable_s3_client
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.aws_helpers import record_signing_access_keys
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import mock_only


class ResolveS3ClientMixin(BaseTest):
    module = "core.resolve_s3_client"

    def put(self, p: S3Path, body: bytes = b"hello"):
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=body)

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

    @pytest.mark.parametrize(
        "kind",
        [
            pytest.param("bsm", id="object-with-s3_client"),
            pytest.param("sts", id="other-boto3-client"),
            pytest.param("str", id="str"),
        ],
    )
    def test_resolve_not_an_s3_client(self, kind):
        """
        Anything but a boto3 S3 client raises ``TypeError``, before any call.
        A ``BotoSesManager`` is not accepted: pass its ``s3_client``.
        """
        if kind == "bsm":
            value = types.SimpleNamespace(s3_client=self.boto_ses.client("s3"))
        elif kind == "sts":
            value = self.boto_ses.client("sts")
        else:
            value = "s3"
        with pytest.raises(
            TypeError, match="s3_client must be a boto3 S3 client.*bsm.s3_client"
        ):
            resolve_s3_client(s3_context, value)

    # --------------------------------------------------------------------------
    # 2. S3Path methods with s3_client=
    # --------------------------------------------------------------------------
    def test_s3path_explicit_client(self):
        """
        ``s3_client=`` sends the call through the given client, not through
        ``s3_context``.
        """
        p = self.s3dir_test / "file.txt"
        s3_client = self.boto_ses.client("s3")
        with record_api_calls(s3_context.s3_client) as default_calls:
            with record_api_calls(s3_client) as explicit_calls:
                p.write_text("hello", s3_client=s3_client)
        assert explicit_calls == ["PutObject"]
        assert default_calls == []

    def test_s3path_not_an_s3_client(self):
        """
        A ``BotoSesManager`` passed as ``s3_client`` raises ``TypeError``
        before any call, not an ``AttributeError`` at the first call.
        """
        p = self.s3dir_test / "file.txt"
        bsm = types.SimpleNamespace(s3_client=self.boto_ses.client("s3"))
        with record_api_calls(s3_context.s3_client) as calls:
            with pytest.raises(TypeError, match="bsm.s3_client"):
                p.write_text("hello", s3_client=bsm)
        assert calls == []

    def test_bsm_removed(self):
        """
        No ``S3Path`` method has a ``bsm`` argument; every method that
        calls AWS takes ``s3_client`` instead.
        """
        with_bsm = list()
        with_s3_client = list()
        for name in dir(S3Path):
            if name.startswith("_"):
                continue
            func = getattr(S3Path, name)
            if not inspect.isfunction(func) and not inspect.ismethod(func):
                continue
            parameters = inspect.signature(func).parameters
            if "bsm" in parameters:
                with_bsm.append(name)
            if "s3_client" in parameters:
                with_s3_client.append(name)
        assert with_bsm == []
        assert len(with_s3_client) == 35

    # --------------------------------------------------------------------------
    # 3. Metadata loaded with the client that produced the path
    # --------------------------------------------------------------------------
    def test_listed_path_loads_metadata_with_its_client(self):
        """
        A path listed with ``s3_client=`` loads its missing metadata with that
        client, not with ``s3_context`` (which may be another account when
        listing with the client of one).
        """
        self.put(self.s3dir_test / "file.txt")
        s3_client = self.boto_ses.client("s3")
        p = self.s3dir_test.iter_objects(s3_client=s3_client).one()
        with record_api_calls(s3_context.s3_client) as default_calls:
            with record_api_calls(s3_client) as explicit_calls:
                assert p.metadata == {}
        assert explicit_calls == ["HeadObject"]
        assert default_calls == []

    def test_head_object_remembers_its_client(self):
        """
        ``head_object(s3_client=...)`` remembers the client: after ``clear_cache()``,
        the next property read loads the metadata with it.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p)
        s3_client = self.boto_ses.client("s3")
        p.head_object(s3_client=s3_client)
        p.clear_cache()
        with record_api_calls(s3_context.s3_client) as default_calls:
            with record_api_calls(s3_client) as explicit_calls:
                assert p.size == 5
        assert explicit_calls == ["HeadObject"]
        assert default_calls == []

    def test_uploaded_path_loads_metadata_with_its_client(self, tmp_path):
        """
        The path returned by ``upload_file(s3_client=...)`` has no snapshot, and
        loads it with that client.
        """
        local_file = tmp_path / "file.txt"
        local_file.write_bytes(b"hello")
        s3_client = self.boto_ses.client("s3")
        new = (self.s3dir_test / "file.txt").upload_file(
            local_file, s3_client=s3_client
        )
        with record_api_calls(s3_context.s3_client) as default_calls:
            with record_api_calls(s3_client) as explicit_calls:
                assert new.size == 5
        assert explicit_calls == ["HeadObject"]
        assert default_calls == []

    def test_sync_uses_explicit_client(self, monkeypatch):
        """
        ``S3Path.sync(s3_client=...)`` runs the AWS CLI with the credentials and the
        region of that client, not of ``s3_context``.
        """
        calls = list()

        def run(args, env, stderr, text):
            calls.append(env)
            return subprocess.CompletedProcess(args, 0, stderr="")

        monkeypatch.setattr("s3pathlib.core.sync.shutil.which", lambda name: "/bin/aws")
        monkeypatch.setattr("s3pathlib.core.sync.subprocess.run", run)
        s3_client = boto3.session.Session(
            aws_access_key_id="EXPLICIT",
            aws_secret_access_key="secret",
            region_name="eu-west-1",
        ).client("s3")
        S3Path.sync(self.s3dir_test, "/tmp/data", s3_client=s3_client, verbose=False)
        assert calls[0]["AWS_ACCESS_KEY_ID"] == "EXPLICIT"
        assert calls[0]["AWS_DEFAULT_REGION"] == "eu-west-1"

    def test_path_without_client_uses_s3_context(self):
        """
        A path built by the user, or derived from a path with a client
        (``parent``, ``joinpath``, ...), uses ``s3_context`` at the time of
        the call.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p)
        s3_client = self.boto_ses.client("s3")
        listed = self.s3dir_test.iter_objects(s3_client=s3_client).one()
        derived = listed.parent / "file.txt"
        with record_api_calls(s3_context.s3_client) as default_calls:
            with record_api_calls(s3_client) as explicit_calls:
                assert derived.size == 5
                assert S3Path(p.uri).size == 5
        assert default_calls == ["HeadObject", "HeadObject"]
        assert explicit_calls == []

    def test_operations_do_not_use_remembered_client(self):
        """
        The remembered client is only for the snapshot: the other methods of a
        listed path use ``s3_context`` unless given ``s3_client``, the same as
        a derived path, so the client never depends on where the path came
        from.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p)
        s3_client = self.boto_ses.client("s3")
        listed = self.s3dir_test.iter_objects(s3_client=s3_client).one()
        with record_api_calls(s3_context.s3_client) as default_calls:
            with record_api_calls(s3_client) as explicit_calls:
                assert listed.read_bytes() == b"hello"
                listed.get_tags()
        assert default_calls == ["GetObject", "GetObjectTagging"]
        assert explicit_calls == []

    # --------------------------------------------------------------------------
    # 4. Refreshable credentials
    # --------------------------------------------------------------------------
    @mock_only("the refreshable credentials are fake")
    def test_explicit_client_refreshable_credentials(self):
        """
        An explicit client with refreshable credentials (e.g. from an assumed
        role) gets new credentials when they expire and signs with them.
        """
        p = self.s3dir_test / "file.txt"
        s3_client, fetched_keys = make_refreshable_s3_client()
        with record_signing_access_keys(s3_client) as access_keys:
            for _ in range(3):
                p.write_text("hello", s3_client=s3_client)
        assert fetched_keys == ["AK1", "AK2", "AK3"]
        assert access_keys == ["AK1", "AK2", "AK3"]


class TestMock(ResolveS3ClientMixin):
    use_mock = True


class TestRealAws(ResolveS3ClientMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.resolve_s3_client",
        preview=False,
    )

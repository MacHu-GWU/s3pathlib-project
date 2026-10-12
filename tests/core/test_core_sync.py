# -*- coding: utf-8 -*-

"""
Test ``S3Path.sync``, ``sync_from`` and ``sync_to``.

Test order:

1. the command line: the paths, the flags, ``quiet`` / ``quite``;
2. the environment of the command: the identity of the S3 client;
3. errors and invalid input;
4. end to end, with the real ``aws`` command: against a moto server (moto
   mode) or AWS. These tests are skipped when the AWS CLI is not installed.

Sections 1 to 3 replace ``subprocess.run`` with a recorder, so they need no
AWS CLI. Clients with special settings are attached to ``s3_context`` for the
duration of a test.
"""

import contextlib
import pathlib
import shutil
import socket
import subprocess
import uuid

import boto3
import botocore
import botocore.config
import botocore.exceptions
import pytest

from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.exc import S3PathIsNotFolderError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.exc import S3SyncError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock_aws import BaseTest

AWS_CLI = shutil.which("aws")

IDENTITY_ENV_VARS = [
    "AWS_PROFILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_ENDPOINT_URL",
    "AWS_ENDPOINT_URL_S3",
    "AWS_ROLE_ARN",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class SyncMixin(BaseTest):
    module = "core.sync"

    @pytest.fixture
    def runner(self, monkeypatch):
        """
        Replace ``subprocess.run`` with a recorder (and pretend that the AWS
        CLI is installed). ``runner.returncode`` / ``runner.stderr`` set what
        it returns.
        """

        class Runner:
            calls = list()
            returncode = 0
            stderr = ""

            def __call__(self, args, env, stderr, text):
                self.calls.append({"args": args, "env": env})
                return subprocess.CompletedProcess(
                    args, self.returncode, stderr=self.stderr
                )

            @property
            def args(self) -> list[str]:
                return self.calls[-1]["args"]

            @property
            def env(self) -> dict[str, str]:
                return self.calls[-1]["env"]

        runner = Runner()
        runner.calls = list()
        monkeypatch.setattr("s3pathlib.core.sync.shutil.which", lambda name: "/bin/aws")
        monkeypatch.setattr("s3pathlib.core.sync.subprocess.run", runner)
        return runner

    @contextlib.contextmanager
    def use_client(self, s3_client):
        s3_context.attach_s3_client(s3_client)
        try:
            yield
        finally:
            s3_context.attach_s3_client(self.s3_client)

    def make_client(self, **kwargs):
        """
        A client with fake credentials, for the tests that only build the
        command.
        """
        session_kwargs = dict(
            aws_access_key_id="AKID",
            aws_secret_access_key="SECRET",
            region_name="eu-west-1",
        )
        if "aws_session_token" in kwargs:
            session_kwargs["aws_session_token"] = kwargs.pop("aws_session_token")
        return boto3.session.Session(**session_kwargs).client("s3", **kwargs)

    # --------------------------------------------------------------------------
    # 1. Command line
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "src, dst, expected",
        [
            pytest.param(
                "s3dir:a/", "s3dir:b/", ["s3dir:a/", "s3dir:b/"], id="s3-to-s3"
            ),
            pytest.param(
                "/tmp/data", "s3dir:b/", ["/tmp/data", "s3dir:b/"], id="local-to-s3"
            ),
            pytest.param(
                "s3dir:a/",
                pathlib.Path("/tmp/data"),
                ["s3dir:a/", "/tmp/data"],
                id="s3-to-pathlib",
            ),
            pytest.param(
                "s3://bucket/a/",
                "/tmp/data",
                ["s3://bucket/a/", "/tmp/data"],
                id="s3-uri",
            ),
            pytest.param(
                "C:\\data",
                "s3://bucket/a/",
                ["C:/data", "s3://bucket/a/"],
                id="windows-path",
            ),
        ],
    )
    def test_paths(self, runner, src, dst, expected):
        """
        An ``S3Path`` folder becomes its URI; ``s3://`` URIs and local paths
        (``str`` or ``os.PathLike``) are passed as they are.
        """

        def resolve(x):
            if isinstance(x, str) and x.startswith("s3dir:"):
                return self.s3dir_test / x[len("s3dir:") :]
            return x

        S3Path.sync(resolve(src), resolve(dst), verbose=False)
        expected = [
            resolve(x).uri if isinstance(resolve(x), S3Path) else x for x in expected
        ]
        assert runner.args[:5] == ["/bin/aws", "s3", "sync", *expected]

    @pytest.mark.parametrize("method", ["sync", "sync_from", "sync_to"])
    def test_flags(self, runner, method):
        """
        Every flag reaches the command, whichever of the three methods is
        called.
        """
        flags = dict(
            include="*.csv",
            exclude="*.tmp",
            acl="private",
            only_show_errors=True,
            no_progress=True,
            page_size=100,
            delete=True,
            verbose=False,
        )
        s3dir = self.s3dir_test / "a/"
        if method == "sync":
            S3Path.sync(s3dir, "/tmp/data", **flags)
        elif method == "sync_from":
            s3dir.sync_from("/tmp/data", **flags)
        else:
            s3dir.sync_to("/tmp/data", **flags)
        assert runner.args[5:] == [
            "--only-show-errors",
            "--include",
            "*.csv",
            "--exclude",
            "*.tmp",
            "--acl",
            "private",
            "--no-progress",
            "--page-size",
            "100",
            "--delete",
        ]

    def test_quiet(self, runner):
        """
        By default only the errors are shown (``--only-show-errors``, not
        ``--quiet``, which hides the errors too); ``quiet=False`` shows the
        progress, and ``only_show_errors`` still works with it.
        """
        S3Path.sync(self.s3dir_test / "a/", "/tmp/data", verbose=False)
        assert runner.args[5:] == ["--only-show-errors"]
        S3Path.sync(self.s3dir_test / "a/", "/tmp/data", quiet=False, verbose=False)
        assert runner.args[5:] == []
        S3Path.sync(
            self.s3dir_test / "a/",
            "/tmp/data",
            quiet=False,
            only_show_errors=True,
            verbose=False,
        )
        assert runner.args[5:] == ["--only-show-errors"]

    @pytest.mark.parametrize("method", ["sync", "sync_from", "sync_to"])
    def test_quite_deprecated(self, runner, method):
        """
        The misspelled ``quite`` still works, with a ``DeprecationWarning``
        that points at the caller.
        """
        s3dir = self.s3dir_test / "a/"
        with pytest.warns(DeprecationWarning, match="Use 'quiet' instead") as record:
            if method == "sync":
                S3Path.sync(s3dir, "/tmp/data", quite=False, verbose=False)
            else:
                getattr(s3dir, method)("/tmp/data", quite=False, verbose=False)
        assert record[0].filename == __file__
        assert "--only-show-errors" not in runner.args

    def test_quiet_and_quite(self, runner):
        """
        When both are given, the deprecated ``quite`` wins: ``quiet`` has a
        plain default, so passing it cannot be told from leaving it out.
        """
        with pytest.warns(DeprecationWarning, match="Use 'quiet' instead"):
            S3Path.sync(
                self.s3dir_test / "a/",
                "/tmp/data",
                quiet=True,
                quite=False,
                verbose=False,
            )
        assert "--only-show-errors" not in runner.args

    def test_sync_from_and_to(self, runner):
        s3dir = self.s3dir_test / "a/"
        s3dir.sync_from("/tmp/data", verbose=False)
        assert runner.args[3:5] == ["/tmp/data", s3dir.uri]
        s3dir.sync_to("/tmp/data", verbose=False)
        assert runner.args[3:5] == [s3dir.uri, "/tmp/data"]

    def test_verbose(self, runner, capsys):
        """
        ``verbose`` prints the command line, which has no credentials.
        """
        with self.use_client(self.make_client()):
            S3Path.sync(self.s3dir_test / "a/", "/tmp/data")
        printed = capsys.readouterr().out
        assert "aws s3 sync" in printed
        assert "SECRET" not in printed

    # --------------------------------------------------------------------------
    # 2. Identity of the S3 client
    # --------------------------------------------------------------------------
    def test_env_credentials_of_client(self, runner, monkeypatch):
        """
        The command gets the credentials and the region of the client of
        ``s3_context``, and none of the variables that would give it another
        identity: the default credentials of the environment are not used.
        """
        for name in IDENTITY_ENV_VARS:
            monkeypatch.setenv(name, "other")
        monkeypatch.setenv("SOME_OTHER_VAR", "kept")
        S3Path.sync(self.s3dir_test / "a/", "/tmp/data", verbose=False)
        frozen = self.s3_client._get_credentials().get_frozen_credentials()
        env = runner.env
        assert env["AWS_ACCESS_KEY_ID"] == frozen.access_key
        assert env["AWS_SECRET_ACCESS_KEY"] == frozen.secret_key
        assert env["AWS_DEFAULT_REGION"] == self.s3_client.meta.region_name
        assert env["AWS_REGION"] == self.s3_client.meta.region_name
        assert env["SOME_OTHER_VAR"] == "kept"
        for name in [
            "AWS_PROFILE",
            "AWS_DEFAULT_PROFILE",
            "AWS_ENDPOINT_URL",
            "AWS_ROLE_ARN",
        ]:
            assert name not in env
        assert "--endpoint-url" not in runner.args

    @pytest.mark.parametrize("token", [None, "TOKEN"])
    def test_env_session_token(self, runner, token, monkeypatch):
        monkeypatch.setenv("AWS_SESSION_TOKEN", "other")
        if token is None:
            s3_client = self.make_client()
        else:
            s3_client = self.make_client(aws_session_token=token)
        with self.use_client(s3_client):
            S3Path.sync(self.s3dir_test / "a/", "/tmp/data", verbose=False)
        assert runner.env.get("AWS_SESSION_TOKEN") == token

    @pytest.mark.parametrize(
        "endpoint_url, expected",
        [
            pytest.param(None, None, id="aws"),
            pytest.param("https://s3.cn-north-1.amazonaws.com.cn", None, id="aws-cn"),
            pytest.param("http://127.0.0.1:5000", "http://127.0.0.1:5000", id="custom"),
        ],
    )
    def test_endpoint(self, runner, endpoint_url, expected):
        """
        A custom endpoint (e.g. a local S3 compatible server) is passed with
        ``--endpoint-url``; an AWS endpoint is not.
        """
        kwargs = dict()
        if endpoint_url is not None:
            kwargs["endpoint_url"] = endpoint_url
        with self.use_client(self.make_client(**kwargs)):
            S3Path.sync(self.s3dir_test / "a/", "/tmp/data", verbose=False)
        if expected is None:
            assert "--endpoint-url" not in runner.args
        else:
            index = runner.args.index("--endpoint-url")
            assert runner.args[index + 1] == expected

    def test_unsigned_client(self, runner):
        """
        An unsigned client gives ``--no-sign-request`` and no credentials.
        """
        s3_client = self.make_client(
            config=botocore.config.Config(signature_version=botocore.UNSIGNED)
        )
        with self.use_client(s3_client):
            S3Path.sync(self.s3dir_test / "a/", "/tmp/data", verbose=False)
        assert "--no-sign-request" in runner.args
        assert "AWS_ACCESS_KEY_ID" not in runner.env

    def test_no_credentials(self, runner, monkeypatch):
        s3_client = self.make_client()
        monkeypatch.setattr(s3_client, "_get_credentials", lambda: None)
        with self.use_client(s3_client):
            with pytest.raises(botocore.exceptions.NoCredentialsError):
                S3Path.sync(self.s3dir_test / "a/", "/tmp/data", verbose=False)
        assert runner.calls == []

    # --------------------------------------------------------------------------
    # 3. Errors and invalid input
    # --------------------------------------------------------------------------
    def test_command_failed(self, runner):
        """
        A failed command raises ``S3SyncError`` with the exit code, stderr
        and the command line (without credentials).
        """
        runner.returncode = 1
        runner.stderr = "fatal error: NoSuchBucket\n"
        with self.use_client(self.make_client()):
            with pytest.raises(
                S3SyncError, match="exit code 1: fatal error: NoSuchBucket"
            ) as exc_info:
                S3Path.sync(self.s3dir_test / "a/", "/tmp/data", verbose=False)
        error = exc_info.value
        assert error.returncode == 1
        assert error.stderr == "fatal error: NoSuchBucket\n"
        assert error.command[:3] == ["aws", "s3", "sync"]
        assert "SECRET" not in " ".join(error.command)

    def test_aws_cli_missing(self, runner, monkeypatch):
        monkeypatch.setattr("s3pathlib.core.sync.shutil.which", lambda name: None)
        with pytest.raises(FileNotFoundError, match="install the AWS CLI"):
            S3Path.sync(self.s3dir_test / "a/", "/tmp/data", verbose=False)
        assert runner.calls == []

    def test_both_local(self, runner):
        with pytest.raises(
            ValueError, match="at least one of src and dst must be an S3 path"
        ):
            S3Path.sync("/tmp/a", pathlib.Path("/tmp/b"), verbose=False)
        assert runner.calls == []

    @pytest.mark.parametrize(
        "p, error, match",
        [
            pytest.param(S3Path(), S3PathTypeError, "is a relative path", id="void"),
            pytest.param(
                S3Path.make_relpath("a/"),
                S3PathTypeError,
                "is a relative path",
                id="relpath",
            ),
            pytest.param(
                S3Path("bucket", "file.txt"),
                S3PathIsNotFolderError,
                "is not a dir",
                id="file",
            ),
        ],
    )
    def test_not_a_folder(self, runner, p, error, match):
        with pytest.raises(error, match=match):
            S3Path.sync(p, "/tmp/data", verbose=False)
        assert runner.calls == []

    # --------------------------------------------------------------------------
    # 4. End to end with the AWS CLI
    # --------------------------------------------------------------------------
    @pytest.fixture
    def cli_client(self):
        """
        The client the CLI syncs with: in moto mode, a client of a moto
        server (a real HTTP endpoint the CLI can call, with the same data as
        the in-process mock); on AWS, the client of the test.
        """
        if AWS_CLI is None:
            pytest.skip("the AWS CLI ('aws') is not installed")
        if self.use_mock:
            from moto.server import ThreadedMotoServer

            port = free_port()
            server = ThreadedMotoServer(port=port, verbose=False)
            server.start()
            s3_client = self.boto_ses.client(
                "s3", endpoint_url=f"http://127.0.0.1:{port}"
            )
            try:
                with self.use_client(s3_client):
                    yield s3_client
            finally:
                server.stop()
        else:
            yield self.s3_client

    def keys(self, s3dir: S3Path) -> list[str]:
        res = self.s3_client.list_objects_v2(Bucket=s3dir.bucket, Prefix=s3dir.key)
        return sorted(dct["Key"][len(s3dir.key) :] for dct in res.get("Contents", []))

    def test_e2e(self, cli_client, tmp_path):
        """
        Local to S3, S3 to S3 (with ``delete``), S3 to local, with the
        identity of the S3 client.
        """
        local = tmp_path / "src"
        (local / "sub").mkdir(parents=True)
        (local / "a.txt").write_text("a")
        (local / "sub" / "b.csv").write_text("b")
        s3dir1 = self.s3dir_test / "dir1/"
        s3dir2 = self.s3dir_test / "dir2/"

        s3dir1.sync_from(local, verbose=False)
        assert self.keys(s3dir1) == ["a.txt", "sub/b.csv"]

        self.s3_client.put_object(
            Bucket=s3dir2.bucket, Key=s3dir2.key + "extra.txt", Body=b"x"
        )
        s3dir1.sync_to(s3dir2, delete=True, verbose=False)
        assert self.keys(s3dir2) == ["a.txt", "sub/b.csv"]

        out = tmp_path / "out"
        s3dir2.sync_to(out, exclude="*.csv", verbose=False)
        files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
        assert files == ["a.txt"]

    def test_e2e_failure(self, cli_client, tmp_path):
        """
        The error of the CLI is in the exception, also when quiet (the
        default).
        """
        p = S3Path(f"s3pathlib-test-tmp-{uuid.uuid4().hex}", "folder/")
        with pytest.raises(S3SyncError, match="NoSuchBucket") as exc_info:
            p.sync_from(tmp_path, verbose=False)
        assert exc_info.value.returncode != 0


class TestMock(SyncMixin):
    use_mock = True


class TestRealAws(SyncMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.sync",
        preview=False,
    )

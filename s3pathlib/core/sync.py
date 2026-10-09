# -*- coding: utf-8 -*-

"""
Sync folders between S3 and S3, S3 and local, local and S3, with the
`aws s3 sync <https://docs.aws.amazon.com/cli/latest/reference/s3/sync.html>`_
command of the AWS CLI, which must be installed.

**The CLI uses the identity of the S3 client.** The command runs with the
credentials and the region of the S3 client of the call (``s3_client=...``, or
the client of ``s3_context``), passed as environment variables, and with its
endpoint (``--endpoint-url``) when it is not an AWS endpoint. The environment
variables that would make the CLI use another identity (``AWS_PROFILE``,
``AWS_ACCESS_KEY_ID``, ...) are removed from the environment of the command,
so it never syncs with other credentials than the rest of s3pathlib. Limits:

- The CLI gets the credentials of the moment: temporary credentials (an
  assumed role, SSO) are not refreshed during the sync, so a sync longer than
  their remaining lifetime fails.
- Only the credentials, the region and the endpoint are passed; other
  settings of the client (proxies, retries, addressing style, ...) are not.
- The credentials are read with ``s3_client._get_credentials()``, a private
  botocore API (there is no public one).
"""

from __future__ import annotations

import typing as T
import os
import shutil
import subprocess
import warnings
from urllib.parse import urlparse

import botocore
import botocore.exceptions

from .._arg import NOT_GIVEN
from .. import exc
from ..aws import s3_context
from ..type import PathType
from .resolve_s3_client import resolve_s3_client

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client

# environment variables that would give the CLI another identity, region or
# endpoint than the S3 client
_IDENTITY_ENV_VARS = (
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
)

# the hosts of AWS endpoints; any other endpoint is passed with --endpoint-url
_AWS_ENDPOINT_SUFFIXES = (".amazonaws.com", ".amazonaws.com.cn")


def _to_cli_path(path: S3Path | PathType) -> tuple[str, bool]:
    """
    :return: the path for the command line, and whether it is an S3 path.

    :raises S3PathTypeError: for a relative ``S3Path`` or the void path.
    :raises S3PathIsNotFolderError: for an ``S3Path`` of a file.
    """
    if hasattr(path, "console_url"):  # an S3Path
        path.ensure_not_relpath()
        path.ensure_dir()
        return path.uri, True
    else:
        path = os.fspath(path)
        if path.startswith("s3://"):
            return path, True
        else:
            return path.replace("\\", "/"), False


def _make_env(s3_client: S3Client) -> tuple[dict[str, str], list[str]]:
    """
    The environment and the extra arguments that make the CLI use the
    identity of ``s3_client``, see the module docstring.

    :raises botocore.exceptions.NoCredentialsError: if the client has no
        credentials and is not unsigned.
    """
    env = dict()
    for key, value in os.environ.items():
        if key not in _IDENTITY_ENV_VARS:
            env[key] = value
    extra_args = list()
    if s3_client.meta.config.signature_version is botocore.UNSIGNED:
        extra_args.append("--no-sign-request")
    else:
        credentials = s3_client._get_credentials()
        if credentials is None:
            raise botocore.exceptions.NoCredentialsError()
        frozen = credentials.get_frozen_credentials()
        env["AWS_ACCESS_KEY_ID"] = frozen.access_key
        env["AWS_SECRET_ACCESS_KEY"] = frozen.secret_key
        if frozen.token is not None:
            env["AWS_SESSION_TOKEN"] = frozen.token
    # an S3 client always has a region (us-east-1 when none is configured)
    env["AWS_DEFAULT_REGION"] = s3_client.meta.region_name
    env["AWS_REGION"] = s3_client.meta.region_name
    host = urlparse(s3_client.meta.endpoint_url).hostname
    if not host.endswith(_AWS_ENDPOINT_SUFFIXES):
        extra_args.extend(["--endpoint-url", s3_client.meta.endpoint_url])
    return env, extra_args


def _sync(
    src: S3Path | PathType,
    dst: S3Path | PathType,
    s3_client: S3Client | None,
    quite: bool,
    include: str | None,
    exclude: str | None,
    acl: str | None,
    only_show_errors: bool,
    no_progress: bool,
    page_size: str | None,
    delete: bool,
    verbose: bool,
    quiet: bool,
) -> None:
    """
    The implementation of ``S3Path.sync``, ``sync_from`` and ``sync_to``;
    they call it directly, so that the deprecation warning points at the
    caller of any of them.
    """
    if quite is not NOT_GIVEN:
        warnings.warn(
            "The 'quite' argument is deprecated since 3.0.0, will be removed in "
            "4.0.0. Use 'quiet' instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        quiet = quite

    src_arg, src_is_s3 = _to_cli_path(src)
    dst_arg, dst_is_s3 = _to_cli_path(dst)
    if (src_is_s3 is False) and (dst_is_s3 is False):
        raise ValueError(
            f"at least one of src and dst must be an S3 path, got {src_arg!r} "
            f"and {dst_arg!r}"
        )
    aws = shutil.which("aws")
    if aws is None:
        raise FileNotFoundError(
            "the 'aws' command is not found: S3Path.sync runs 'aws s3 sync', "
            "install the AWS CLI, see "
            "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        )

    client = resolve_s3_client(s3_context, s3_client)
    env, extra_args = _make_env(client)
    args = ["aws", "s3", "sync", src_arg, dst_arg]
    args.extend(extra_args)
    # not --quiet, which also hides the errors: they go into S3SyncError
    if quiet or only_show_errors:
        args.append("--only-show-errors")
    if include:
        args.extend(["--include", include])
    if exclude:
        args.extend(["--exclude", exclude])
    if acl:
        args.extend(["--acl", acl])
    if no_progress:
        args.append("--no-progress")
    if page_size:
        args.extend(["--page-size", str(page_size)])
    if delete:
        args.append("--delete")

    if verbose:
        print(" ".join(args))
    # stdout (the progress) goes to the terminal, stderr into the error
    response = subprocess.run(
        [aws] + args[1:],
        env=env,
        stderr=subprocess.PIPE,
        text=True,
    )
    if response.returncode != 0:
        raise exc.S3SyncError(
            f"'aws s3 sync' failed with exit code {response.returncode}: "
            f"{response.stderr.strip()}",
            returncode=response.returncode,
            stderr=response.stderr,
            command=args,
        )


class SyncAPIMixin:
    """
    A mixin class that implements aws s3 sync feature, see the module
    docstring.
    """

    @classmethod
    def sync(
        cls: type[S3Path],
        src: S3Path | PathType,
        dst: S3Path | PathType,
        s3_client: S3Client | None = None,
        quite: bool = NOT_GIVEN,
        include: str | None = None,
        exclude: str | None = None,
        acl: str | None = None,
        only_show_errors: bool = False,
        no_progress: bool = False,
        page_size: str | None = None,
        delete: bool = False,
        verbose: bool = True,
        quiet: bool = True,
    ) -> None:
        """
        Run ``aws s3 sync src dst`` with the identity of the S3 client, see
        the module docstring.

        Example::

            S3Path.sync("/data/orders", S3Path("bucket", "orders/"), delete=True)

        :param src: the source folder: an ``S3Path`` folder (or bucket), an
            ``s3://`` URI, or a local path (``str`` or ``os.PathLike``).
        :param dst: the target folder, the same kinds as ``src``. At least
            one of them is in S3.
        :param s3_client: the boto3 S3 client whose identity the CLI uses,
            default the client of ``s3_context``.
        :param quite: deprecated, use ``quiet``. When given, it is used
            instead of ``quiet``.
        :param include: ``--include`` pattern.
        :param exclude: ``--exclude`` pattern.
        :param acl: ``--acl``.
        :param only_show_errors: ``--only-show-errors``, see ``quiet``.
        :param no_progress: ``--no-progress``.
        :param page_size: ``--page-size``.
        :param delete: ``--delete``: delete the files of ``dst`` that are not
            in ``src``.
        :param verbose: print the command line (it has no credentials).
        :param quiet: ``True`` (default): print nothing but the errors. It
            runs the command with ``--only-show-errors``, not ``--quiet``,
            which hides the errors too: on failure, the error is in the
            ``S3SyncError``. ``False`` shows the progress.

        :raises S3PathTypeError: for a relative ``S3Path`` or the void path.
        :raises S3PathIsNotFolderError: for an ``S3Path`` of a file.
        :raises ValueError: if neither ``src`` nor ``dst`` is in S3.
        :raises FileNotFoundError: if the ``aws`` command is not installed.
        :raises botocore.exceptions.NoCredentialsError: if the S3 client has
            no credentials.
        :raises S3SyncError: if the command fails; it has the exit code and
            stderr.
        """
        _sync(
            src=src,
            dst=dst,
            s3_client=s3_client,
            quite=quite,
            include=include,
            exclude=exclude,
            acl=acl,
            only_show_errors=only_show_errors,
            no_progress=no_progress,
            page_size=page_size,
            delete=delete,
            verbose=verbose,
            quiet=quiet,
        )

    def sync_from(
        self: S3Path,
        src: S3Path | PathType,
        s3_client: S3Client | None = None,
        quite: bool = NOT_GIVEN,
        include: str | None = None,
        exclude: str | None = None,
        acl: str | None = None,
        only_show_errors: bool = False,
        no_progress: bool = False,
        page_size: str | None = None,
        delete: bool = False,
        verbose: bool = True,
        quiet: bool = True,
    ) -> None:
        """
        Sync ``src`` to this S3 folder, see :meth:`sync`.
        """
        _sync(
            src=src,
            dst=self,
            s3_client=s3_client,
            quite=quite,
            include=include,
            exclude=exclude,
            acl=acl,
            only_show_errors=only_show_errors,
            no_progress=no_progress,
            page_size=page_size,
            delete=delete,
            verbose=verbose,
            quiet=quiet,
        )

    def sync_to(
        self: S3Path,
        dst: S3Path | PathType,
        s3_client: S3Client | None = None,
        quite: bool = NOT_GIVEN,
        include: str | None = None,
        exclude: str | None = None,
        acl: str | None = None,
        only_show_errors: bool = False,
        no_progress: bool = False,
        page_size: str | None = None,
        delete: bool = False,
        verbose: bool = True,
        quiet: bool = True,
    ) -> None:
        """
        Sync this S3 folder to ``dst``, see :meth:`sync`.
        """
        _sync(
            src=self,
            dst=dst,
            s3_client=s3_client,
            quite=quite,
            include=include,
            exclude=exclude,
            acl=acl,
            only_show_errors=only_show_errors,
            no_progress=no_progress,
            page_size=page_size,
            delete=delete,
            verbose=verbose,
            quiet=quiet,
        )

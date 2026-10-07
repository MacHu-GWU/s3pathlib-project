# -*- coding: utf-8 -*-

"""
Sync file, folder between s3-to-s3, s3-to-local, local-to-s3.
"""

from __future__ import annotations

import typing as T

import subprocess

import boto3
from boto_session_manager.api import BotoSesManager

from ..type import PathType

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


def _preprocess(path: S3Path | PathType) -> S3Path | str:
    if hasattr(path, "console_url"):
        return path
    else:
        return str(path)


class SyncAPIMixin:
    """
    A mixin class that implements aws s3 sync feature.
    """

    @classmethod
    def sync(
        cls: type[S3Path],
        src: S3Path | PathType,
        dst: S3Path | PathType,
        bsm: BotoSesManager | None = None,
        quite: bool = True,
        include: str | None = None,
        exclude: str | None = None,
        acl: str | None = None,
        only_show_errors: bool = False,
        no_progress: bool = False,
        page_size: str | None = None,
        delete: bool = False,
        verbose: bool = True,
    ):
        """
        Implement the `aws s3 sync <https://docs.aws.amazon.com/cli/latest/reference/s3/sync.html>`_
        CLI behavior.

        :param src:
        :param dst:
        :param bsm:
        :param quite:
        :param include:
        :param exclude:
        :param acl:
        :param only_show_errors:
        :param no_progress:
        :param page_size:
        :param delete:
        :param verbose:

        TODO: add support for all aws s3 sync supported arguments
        """
        args = [
            "aws",
            "s3",
            "sync",
        ]

        # handle source and target
        src = _preprocess(src)
        dst = _preprocess(dst)

        if isinstance(src, str):
            if src.startswith("s3://"):
                src_is_s3 = True
            else:
                src_is_s3 = False
            src_arg = src.replace("\\", "/")
        else:
            src_is_s3 = True
            src_arg = src.uri

        if isinstance(dst, str):
            if dst.startswith("s3://"):
                dst_is_s3 = True
            else:
                dst_is_s3 = False
            dst_arg = dst.replace("\\", "/")
        else:
            dst_is_s3 = True
            dst_arg = dst.uri

        if src_is_s3 is False and dst_is_s3 is False:
            raise ValueError

        args.extend([src_arg, dst_arg])

        # handle additional CLI argument
        if quite:  # pragma: no cover
            args.append("--quiet")
        if include:  # pragma: no cover
            args.extend(["--include", include])
        if exclude:  # pragma: no cover
            args.extend(["--exclude", exclude])
        if acl:  # pragma: no cover
            args.extend(["--acl", acl])
        if only_show_errors:  # pragma: no cover
            args.append("--only-show-errors")
        if no_progress:  # pragma: no cover
            args.append("--no-progress")
        if page_size:  # pragma: no cover
            args.extend(["--page-size", str(page_size)])
        if delete:  # pragma: no cover
            args.append("--delete")

        if bsm is None:  # pragma: no cover
            # TODO (#38): use the credentials of s3_context.s3_client; for now
            # the CLI uses the default credentials, not the attached client
            boto_ses = boto3.session.Session()
            with BotoSesManager(botocore_session=boto_ses._session).awscli():
                if verbose:
                    print(" ".join(args))
                response = subprocess.run(args)
        else:  # pragma: no cover
            with bsm.awscli():
                response = subprocess.run(args)
        if response.returncode != 0:  # pragma: no cover
            raise SystemError("'aws s3 sync' command failed!")

    def sync_from(
        self: S3Path,
        src: S3Path | PathType,
        bsm: BotoSesManager | None = None,
        quite: bool = True,
        include: str | None = None,
        exclude: str | None = None,
        acl: str | None = None,
        only_show_errors: bool = False,
        no_progress: bool = False,
        page_size: str | None = None,
        delete: bool = False,
        verbose: bool = True,
    ):
        """
        Sync data from external place to this S3 location.
        """
        return self.sync(
            src=src,
            dst=self,
            bsm=bsm,
            quite=quite,
            include=include,
            exclude=exclude,
            acl=acl,
            only_show_errors=only_show_errors,
            no_progress=no_progress,
            page_size=page_size,
            delete=delete,
            verbose=verbose,
        )

    def sync_to(
        self: S3Path,
        dst: S3Path | PathType,
        bsm: BotoSesManager | None = None,
        quite: bool = True,
        include: str | None = None,
        exclude: str | None = None,
        acl: str | None = None,
        only_show_errors: bool = False,
        no_progress: bool = False,
        page_size: str | None = None,
        delete: bool = False,
        verbose: bool = True,
    ):
        """
        Sync the data at this S3 location to external place.
        """
        return self.sync(
            src=self,
            dst=dst,
            bsm=bsm,
            quite=quite,
            include=include,
            exclude=exclude,
            acl=acl,
            only_show_errors=only_show_errors,
            no_progress=no_progress,
            page_size=page_size,
            delete=delete,
            verbose=verbose,
        )

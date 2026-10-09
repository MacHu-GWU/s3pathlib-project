# -*- coding: utf-8 -*-

"""
Smart open library integration.

.. _bsm: https://github.com/aws-samples/boto-session-manager-project
.. _smart_open: https://github.com/RaRe-Technologies/smart_open
.. _get_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.get_object
.. _put_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object
.. _create_multipart_upload: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/create_multipart_upload.html
"""

from __future__ import annotations

import typing as T
import copy
import re
from datetime import datetime

import smart_open
from func_args import NOTHING, resolve_kwargs

from ..metadata import warn_upper_case_in_metadata_key
from ..aws import s3_context
from ..type import MetadataType, TagType
from ..tag import encode_url_query

from .resolve_s3_client import resolve_s3_client

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from boto_session_manager.api import BotoSesManager
    from mypy_boto3_s3 import S3Client


_VALID_MODES = ("r", "rb", "rt", "w", "wb", "wt")

# The part of an S3 URI that smart_open 8 (``smart_open.s3.parse_uri``, checked
# on 8.0.2) takes as a version id and removes from the key: ``?versionId=...``
# or ``&versionId=...``, case sensitive. See ``OpenerAPIMixin.open``.
_VERSION_ID_IN_KEY = re.compile(r"[?&]versionId=")


class OpenerAPIMixin:
    """
    A mixin class that implements the file-object protocol.
    """

    def open(
        self: S3Path,
        mode: str = "r",
        version_id: str = NOTHING,
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
        closefd=True,
        opener=None,
        compression: str | None = None,
        multipart_upload: bool = True,
        metadata: MetadataType = NOTHING,
        tags: TagType = NOTHING,
        # write related parameters
        acl: str = NOTHING,
        cache_control: str = NOTHING,
        content_disposition: str = NOTHING,
        content_encoding: str = NOTHING,
        content_language: str = NOTHING,
        content_length: int = NOTHING,
        content_md5: str = NOTHING,
        content_type: str = NOTHING,
        checksum_algorithm: str = NOTHING,
        # put_object exclusive parameters
        checksum_crc32: str = NOTHING,
        checksum_crc32c: str = NOTHING,
        checksum_sha1: str = NOTHING,
        checksum_sha256: str = NOTHING,
        # write related parameters
        expires_datetime: datetime = NOTHING,
        grant_full_control: str = NOTHING,
        grant_read: str = NOTHING,
        grant_read_acp: str = NOTHING,
        grant_write_acp: str = NOTHING,
        server_side_encryption: str = NOTHING,
        storage_class: str = NOTHING,
        website_redirect_location: str = NOTHING,
        # common read / write related parameters
        sse_customer_algorithm: str = NOTHING,
        sse_customer_key: str = NOTHING,
        # write related parameters
        sse_kms_key_id: str = NOTHING,
        sse_kms_encryption_context: str = NOTHING,
        bucket_key_enabled: bool = NOTHING,
        # common read / write related parameters
        request_payer: str = NOTHING,
        # write related parameters
        object_lock_mode: str = NOTHING,
        object_lock_retain_until_datetime: datetime = NOTHING,
        object_lock_legal_hold_status: str = NOTHING,
        # common read / write related parameters
        expected_bucket_owner: str = NOTHING,
        # read related parameters
        if_match: str = NOTHING,
        if_modified_since: datetime = NOTHING,
        if_none_match: str = NOTHING,
        if_unmodified_since: datetime = NOTHING,
        response_cache_control: str = NOTHING,
        response_content_disposition: str = NOTHING,
        response_content_encoding: str = NOTHING,
        response_content_language: str = NOTHING,
        response_content_type: str = NOTHING,
        response_expires: str = NOTHING,
        checksum_mode: str = NOTHING,
        # other parameters
        transport_params: dict | None = None,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> T.IO:
        """
        Open the object as a file object, with smart_open_: the content is
        streamed, so a big object is never loaded in memory at once.

        Example::

            >>> import json
            >>> with S3Path("s3://my-bucket/open.json").open("w") as f:
            ...     json.dump({"a": 1}, f)
            >>> with S3Path("s3://my-bucket/open.json").open("r") as f:
            ...     json.load(f)
            {'a': 1}

        **Whole object only.** ``open`` reads or writes the whole object as a
        stream. It has no ``range`` / ``part_number`` (removed in 3.0, they
        never worked: smart_open sets its own ``Range`` to stream and seek).
        To read part of an object, use ``read_bytes(range=...)`` or
        ``read_bytes(part_number=...)``; to skip ahead in the stream, use
        ``f.seek(offset)`` then ``f.read(n)``.

        **Compression.** By default (``compression=None``), smart_open infers
        it from the extension of the key: writing ``data.json.gz`` writes gzip
        data, reading it gives the uncompressed content. Use
        ``compression="disable"`` to read / write the bytes as they are, or
        e.g. ``compression=".gz"`` to compress whatever the extension.

        **Errors.** If an exception is raised inside the ``with`` block of a
        write, nothing is written (the upload is aborted), so no partial
        object is left. Reading a missing object raises ``OSError`` from
        smart_open, with the boto3 error (e.g. ``NoSuchKey``) as its
        ``__cause__``.

        **Keys containing "?versionId=".** A key containing ``?versionId=`` or
        ``&versionId=`` (e.g. ``page?versionId=1``, a valid S3 key) raises
        ``ValueError``; use ``read_bytes`` / ``write_bytes`` for it. Why:
        ``open`` gives smart_open an ``s3://bucket/key`` URI, and smart_open 8
        takes that part of the URI as a version id and removes it from the
        key, even when ``version_id`` is given: writing fails, and reading
        silently reads another object (key ``page``) or another version.
        smart_open has no way to escape it (``%3F`` is kept as is in the key)
        or to turn it off. It is rejected with every smart_open version, so
        that code tested with smart_open 7 (which keeps such keys as they
        are) does not break when smart_open is upgraded. Other ``?`` in a key
        (e.g. ``page?id=1``) are fine.

        :param mode: ``"r"`` / ``"rt"`` (text), ``"rb"`` (bytes), ``"w"`` /
            ``"wt"``, ``"wb"``.
        :param version_id: the version to read; not allowed when writing.
        :param buffering: not used for S3 (smart_open only uses it for local
            files).
        :param encoding: See smart_open_.
        :param errors: See smart_open_.
        :param newline: See smart_open_.
        :param closefd: not used for S3 (smart_open only uses it for local
            files).
        :param opener: not used for S3 (smart_open only uses it for local
            files).
        :param compression: ``None`` (infer from the extension),
            ``"disable"``, or an extension such as ``".gz"``, see above.
        :param multipart_upload: ``True`` (default) uploads with
            create_multipart_upload_ (the data is sent in parts while writing);
            ``False`` keeps all data in memory and uploads it with
            put_object_ when the file is closed.
        :param metadata: the user metadata of the written object.
        :param tags: the tags of the written object.
        :param acl: See put_object_.
        :param cache_control: See put_object_.
        :param content_disposition: See put_object_.
        :param content_encoding: See put_object_.
        :param content_language: See put_object_.
        :param content_length: See put_object_; only with
            ``multipart_upload=False``.
        :param content_md5: See put_object_; only with
            ``multipart_upload=False``.
        :param content_type: See put_object_.
        :param checksum_algorithm: See put_object_.
        :param checksum_crc32: See put_object_; only with
            ``multipart_upload=False``.
        :param checksum_crc32c: See put_object_; only with
            ``multipart_upload=False``.
        :param checksum_sha1: See put_object_; only with
            ``multipart_upload=False``.
        :param checksum_sha256: See put_object_; only with
            ``multipart_upload=False``.
        :param expires_datetime: See put_object_.
        :param grant_full_control: See put_object_.
        :param grant_read: See put_object_.
        :param grant_read_acp: See put_object_.
        :param grant_write_acp: See put_object_.
        :param server_side_encryption: See put_object_.
        :param storage_class: See put_object_.
        :param website_redirect_location: See put_object_.
        :param sse_customer_algorithm: See put_object_ or get_object_.
        :param sse_customer_key: See put_object_ or get_object_.
        :param sse_kms_key_id: See put_object_.
        :param sse_kms_encryption_context: See put_object_.
        :param bucket_key_enabled: See put_object_.
        :param request_payer: See put_object_ or get_object_.
        :param object_lock_mode: See put_object_.
        :param object_lock_retain_until_datetime: See put_object_.
        :param object_lock_legal_hold_status: See put_object_.
        :param expected_bucket_owner: See put_object_ or get_object_.
        :param if_match: See get_object_.
        :param if_modified_since: See get_object_.
        :param if_none_match: See get_object_.
        :param if_unmodified_since: See get_object_.
        :param response_cache_control: See get_object_.
        :param response_content_disposition: See get_object_.
        :param response_content_encoding: See get_object_.
        :param response_content_language: See get_object_.
        :param response_content_type: See get_object_.
        :param response_expires: See get_object_.
        :param checksum_mode: See get_object_.
        :param transport_params: See smart_open_. Its ``client`` is replaced
            by the S3 client of this call; its ``client_kwargs`` are merged
            with the arguments above (which win).
        :param bsm: See bsm_.

        :return: a file object; use it in a ``with`` block, a write is only
            finished when it is closed.

        :raises S3PathTypeError: for a bucket, a relative path or the void
            path.
        :raises ValueError: for an invalid ``mode``, ``version_id`` when
            writing, a ``multipart_upload=False`` only argument with
            ``multipart_upload=True``, or a key containing ``?versionId=`` /
            ``&versionId=``.
        """
        self._ensure_has_object()
        if mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}, got {mode!r}")
        if _VERSION_ID_IN_KEY.search(self.key):
            raise ValueError(
                f"S3Path.open() cannot open the key {self.key!r}: smart_open 8 "
                f"takes '?versionId=' / '&versionId=' in a key as a version id; "
                f"use read_bytes() / write_bytes() instead"
            )
        is_write_mode = mode.startswith("w")
        if is_write_mode and (version_id is not NOTHING):
            raise ValueError("version_id is only for reading, not for writing")

        s3_client = resolve_s3_client(s3_context, bsm)
        if transport_params is None:
            transport_params = dict()
        else:
            transport_params = transport_params.copy()
            if "client_kwargs" in transport_params:
                transport_params["client_kwargs"] = copy.deepcopy(
                    transport_params["client_kwargs"]
                )
        transport_params["client"] = s3_client
        transport_params["multipart_upload"] = multipart_upload
        if version_id is not NOTHING:
            transport_params["version_id"] = version_id

        if is_write_mode:
            if metadata is not NOTHING:
                warn_upper_case_in_metadata_key(metadata)
            if tags is NOTHING:
                tagging = NOTHING
            else:
                tagging = encode_url_query(tags)
            s3_client_kwargs = resolve_kwargs(
                Metadata=metadata,
                Tagging=tagging,
                ACL=acl,
                CacheControl=cache_control,
                ContentDisposition=content_disposition,
                ContentEncoding=content_encoding,
                ContentLanguage=content_language,
                ContentType=content_type,
                ChecksumAlgorithm=checksum_algorithm,
                Expires=expires_datetime,
                GrantFullControl=grant_full_control,
                GrantRead=grant_read,
                GrantReadACP=grant_read_acp,
                GrantWriteACP=grant_write_acp,
                ServerSideEncryption=server_side_encryption,
                StorageClass=storage_class,
                WebsiteRedirectLocation=website_redirect_location,
                SSECustomerAlgorithm=sse_customer_algorithm,
                SSECustomerKey=sse_customer_key,
                SSEKMSKeyId=sse_kms_key_id,
                SSEKMSEncryptionContext=sse_kms_encryption_context,
                BucketKeyEnabled=bucket_key_enabled,
                RequestPayer=request_payer,
                ObjectLockMode=object_lock_mode,
                ObjectLockRetainUntilDate=object_lock_retain_until_datetime,
                ObjectLockLegalHoldStatus=object_lock_legal_hold_status,
                ExpectedBucketOwner=expected_bucket_owner,
            )
            # put_object has them, create_multipart_upload does not
            put_object_only = {
                "content_length": ("ContentLength", content_length),
                "content_md5": ("ContentMD5", content_md5),
                "checksum_crc32": ("ChecksumCRC32", checksum_crc32),
                "checksum_crc32c": ("ChecksumCRC32C", checksum_crc32c),
                "checksum_sha1": ("ChecksumSHA1", checksum_sha1),
                "checksum_sha256": ("ChecksumSHA256", checksum_sha256),
            }
            given = list()
            for name, (param, value) in put_object_only.items():
                if value is not NOTHING:
                    given.append(name)
                    s3_client_kwargs[param] = value
            if multipart_upload:
                if len(given):
                    raise ValueError(
                        f"{given} only apply with multipart_upload=False"
                    )
                key_name = "S3.Client.create_multipart_upload"
            else:
                key_name = "S3.Client.put_object"
        else:
            s3_client_kwargs = resolve_kwargs(
                IfMatch=if_match,
                IfModifiedSince=if_modified_since,
                IfNoneMatch=if_none_match,
                IfUnmodifiedSince=if_unmodified_since,
                ResponseCacheControl=response_cache_control,
                ResponseContentDisposition=response_content_disposition,
                ResponseContentEncoding=response_content_encoding,
                ResponseContentLanguage=response_content_language,
                ResponseContentType=response_content_type,
                ResponseExpires=response_expires,
                SSECustomerAlgorithm=sse_customer_algorithm,
                SSECustomerKey=sse_customer_key,
                RequestPayer=request_payer,
                ExpectedBucketOwner=expected_bucket_owner,
                ChecksumMode=checksum_mode,
            )
            key_name = "S3.Client.get_object"

        if len(s3_client_kwargs):
            client_kwargs = transport_params.get("client_kwargs", dict())
            if key_name in client_kwargs:
                client_kwargs[key_name].update(s3_client_kwargs)
            else:
                client_kwargs[key_name] = s3_client_kwargs
            transport_params["client_kwargs"] = client_kwargs

        open_kwargs = dict(
            uri=self.uri,
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
            closefd=closefd,
            opener=opener,
            transport_params=transport_params,
        )
        if compression is not None:
            open_kwargs["compression"] = compression
        return smart_open.open(**open_kwargs)

# -*- coding: utf-8 -*-

"""
Read and write related API.

The methods read or write one S3 object: a file, or a folder marker object
(e.g. ``folder/``, which ``mkdir`` writes). A bucket, a relative path or the
void path raise ``S3PathTypeError`` before calling AWS.

Writing returns a new ``S3Path`` with the metadata snapshot of the written
object, and leaves this one as it was (see :mod:`s3pathlib.core.metadata`).
Without ``version_id``, reading reads the latest version.

Errors of the AWS calls are raised as is (``botocore.exceptions.ClientError``,
check ``e.response["Error"]["Code"]``), e.g. ``NoSuchKey``, ``NoSuchBucket``,
``PreconditionFailed`` (``if_match`` / ``if_none_match`` not met when writing,
``if_match`` not met when reading), ``304`` (``if_none_match`` met when
reading).

.. _bsm: https://github.com/aws-samples/boto-session-manager-project
.. _get_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.get_object
.. _put_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object
.. _decode: https://docs.python.org/3/library/stdtypes.html#bytes.decode
.. _encode: https://docs.python.org/3/library/stdtypes.html#str.encode
"""

from __future__ import annotations

import typing as T
from datetime import datetime

import botocore.exceptions
from func_args import NOTHING, resolve_kwargs

from .. import exc
from ..metadata import warn_upper_case_in_metadata_key
from ..type import TagType, MetadataType
from ..tag import encode_url_query
from ..aws import s3_context

from .metadata import explicit_s3_client
from .resolve_s3_client import resolve_s3_client

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from boto_session_manager.api import BotoSesManager
    from mypy_boto3_s3 import S3Client


class ReadAndWriteAPIMixin:
    """
    A mixin class that implements the Text / Bytes, Read / Write methods.
    """
    def read_bytes(
        self: S3Path,
        version_id: str = NOTHING,
        if_match: str = NOTHING,
        if_modified_since: datetime = NOTHING,
        if_none_match: str = NOTHING,
        if_unmodified_since: datetime = NOTHING,
        range: str = NOTHING,
        response_cache_control: str = NOTHING,
        response_content_disposition: str = NOTHING,
        response_content_encoding: str = NOTHING,
        response_content_language: str = NOTHING,
        response_content_type: str = NOTHING,
        response_expires: str = NOTHING,
        sse_customer_algorithm: str = NOTHING,
        sse_customer_key: str = NOTHING,
        request_payer: str = NOTHING,
        part_number: int = NOTHING,
        expected_bucket_owner: str = NOTHING,
        checksum_mode: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> bytes:
        """
        Read the content of the object, a wrapper of get_object_.

        If this ``S3Path`` has no metadata snapshot yet, the get_object_
        response becomes its snapshot (``etag``, ``size``, ``version_id``,
        ...), unless ``range`` or ``part_number`` is given (the response then
        describes a part only). An existing snapshot is never replaced, see
        :mod:`s3pathlib.core.metadata`.

        Example::

            >>> s3path = S3Path("s3://my-bucket/read-bytes.txt")
            >>> _ = s3path.write_bytes(b"hello", metadata={"creator": "me"})
            >>> s3path.read_bytes()
            b'hello'
            >>> s3path.size
            5
            >>> s3path.metadata
            {'creator': 'me'}

        :param version_id: See get_object_.
        :param if_match: See get_object_.
        :param if_modified_since: See get_object_.
        :param if_none_match: See get_object_.
        :param if_unmodified_since: See get_object_.
        :param range: See get_object_.
        :param response_cache_control: See get_object_.
        :param response_content_disposition: See get_object_.
        :param response_content_encoding: See get_object_.
        :param response_content_language: See get_object_.
        :param response_content_type: See get_object_.
        :param response_expires: See get_object_.
        :param sse_customer_algorithm: See get_object_.
        :param sse_customer_key: See get_object_.
        :param request_payer: See get_object_.
        :param part_number: See get_object_.
        :param expected_bucket_owner: See get_object_.
        :param checksum_mode: See get_object_.
        :param bsm: See bsm_.

        :return: the binary data.

        :raises S3PathTypeError: for a bucket, a relative path or the void
            path.
        """
        self._ensure_has_object()
        s3_client = resolve_s3_client(s3_context, bsm)
        response = s3_client.get_object(
            **resolve_kwargs(
                Bucket=self.bucket,
                Key=self.key,
                VersionId=version_id,
                IfMatch=if_match,
                IfModifiedSince=if_modified_since,
                IfNoneMatch=if_none_match,
                IfUnmodifiedSince=if_unmodified_since,
                Range=range,
                ResponseCacheControl=response_cache_control,
                ResponseContentDisposition=response_content_disposition,
                ResponseContentEncoding=response_content_encoding,
                ResponseContentLanguage=response_content_language,
                ResponseContentType=response_content_type,
                ResponseExpires=response_expires,
                SSECustomerAlgorithm=sse_customer_algorithm,
                SSECustomerKey=sse_customer_key,
                RequestPayer=request_payer,
                PartNumber=part_number,
                ExpectedBucketOwner=expected_bucket_owner,
                ChecksumMode=checksum_mode,
            ),
        )
        data = response["Body"].read()
        # only fill an empty snapshot with a full response, see core.metadata
        if (
            (self._meta is None)
            and (range is NOTHING)
            and (part_number is NOTHING)
        ):
            del response["Body"]
            response.pop("ResponseMetadata", None)
            self._set_meta(
                response,
                complete=True,
                s3_client=explicit_s3_client(s3_client, bsm),
            )
        return data

    def read_text(
        self: S3Path,
        encoding="utf-8",
        errors="strict",
        version_id: str = NOTHING,
        if_match: str = NOTHING,
        if_modified_since: datetime = NOTHING,
        if_none_match: str = NOTHING,
        if_unmodified_since: datetime = NOTHING,
        range: str = NOTHING,
        response_cache_control: str = NOTHING,
        response_content_disposition: str = NOTHING,
        response_content_encoding: str = NOTHING,
        response_content_language: str = NOTHING,
        response_content_type: str = NOTHING,
        response_expires: str = NOTHING,
        sse_customer_algorithm: str = NOTHING,
        sse_customer_key: str = NOTHING,
        request_payer: str = NOTHING,
        part_number: int = NOTHING,
        expected_bucket_owner: str = NOTHING,
        checksum_mode: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> str:
        """
        Read the content of the object as text, see :meth:`read_bytes`.

        If this ``S3Path`` has no metadata snapshot yet, the get_object_
        response becomes its snapshot (``etag``, ``size``, ``version_id``,
        ...), unless ``range`` or ``part_number`` is given (the response then
        describes a part only). An existing snapshot is never replaced, see
        :mod:`s3pathlib.core.metadata`.

        Example::

            >>> s3path = S3Path("s3://my-bucket/read-text.txt")
            >>> _ = s3path.write_text("hello")
            >>> s3path.read_text()
            'hello'

        :param encoding: See decode_.
        :param errors: See decode_.
        :param version_id: See get_object_.
        :param if_match: See get_object_.
        :param if_modified_since: See get_object_.
        :param if_none_match: See get_object_.
        :param if_unmodified_since: See get_object_.
        :param range: See get_object_.
        :param response_cache_control: See get_object_.
        :param response_content_disposition: See get_object_.
        :param response_content_encoding: See get_object_.
        :param response_content_language: See get_object_.
        :param response_content_type: See get_object_.
        :param response_expires: See get_object_.
        :param sse_customer_algorithm: See get_object_.
        :param sse_customer_key: See get_object_.
        :param request_payer: See get_object_.
        :param part_number: See get_object_.
        :param expected_bucket_owner: See get_object_.
        :param checksum_mode: See get_object_.
        :param bsm: See bsm_.

        :return: the string data.

        :raises S3PathTypeError: for a bucket, a relative path or the void
            path.
        """
        data = self.read_bytes(
            version_id=version_id,
            if_match=if_match,
            if_modified_since=if_modified_since,
            if_none_match=if_none_match,
            if_unmodified_since=if_unmodified_since,
            range=range,
            response_cache_control=response_cache_control,
            response_content_disposition=response_content_disposition,
            response_content_encoding=response_content_encoding,
            response_content_language=response_content_language,
            response_content_type=response_content_type,
            response_expires=response_expires,
            sse_customer_algorithm=sse_customer_algorithm,
            sse_customer_key=sse_customer_key,
            request_payer=request_payer,
            part_number=part_number,
            expected_bucket_owner=expected_bucket_owner,
            checksum_mode=checksum_mode,
            bsm=bsm,
        )
        return data.decode(encoding, errors=errors)

    def write_bytes(
        self: S3Path,
        data: bytes,
        metadata: MetadataType = NOTHING,
        tags: TagType = NOTHING,
        acl: str = NOTHING,
        cache_control: str = NOTHING,
        content_disposition: str = NOTHING,
        content_encoding: str = NOTHING,
        content_language: str = NOTHING,
        content_length: int = NOTHING,
        content_md5: str = NOTHING,
        content_type: str = NOTHING,
        checksum_algorithm: str = NOTHING,
        checksum_crc32: str = NOTHING,
        checksum_crc32c: str = NOTHING,
        checksum_sha1: str = NOTHING,
        checksum_sha256: str = NOTHING,
        expires_datetime: datetime = NOTHING,
        grant_full_control: str = NOTHING,
        grant_read: str = NOTHING,
        grant_read_acp: str = NOTHING,
        grant_write_acp: str = NOTHING,
        server_side_encryption: str = NOTHING,
        storage_class: str = NOTHING,
        website_redirect_location: str = NOTHING,
        sse_customer_algorithm: str = NOTHING,
        sse_customer_key: str = NOTHING,
        sse_kms_key_id: str = NOTHING,
        sse_kms_encryption_context: str = NOTHING,
        bucket_key_enabled: bool = NOTHING,
        request_payer: str = NOTHING,
        object_lock_mode: str = NOTHING,
        object_lock_retain_until_datetime: datetime = NOTHING,
        object_lock_legal_hold_status: str = NOTHING,
        expected_bucket_owner: str = NOTHING,
        if_match: str = NOTHING,
        if_none_match: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> S3Path:
        """
        Write ``data`` to the object (replacing it if it exists), a wrapper of
        put_object_.

        Example::

            >>> s3path = S3Path("s3://my-bucket/write-bytes.txt")
            >>> s3path_new = s3path.write_bytes(b"hello", metadata={"creator": "me"})
            >>> s3path_new.size
            5
            >>> s3path_new.metadata
            {'creator': 'me'}

        :param data: the content to write.
        :param metadata: the user metadata, a dict of str. S3 stores the keys
            in lower case.
        :param tags: the object tags, a dict of str.
        :param acl: See put_object_.
        :param cache_control: See put_object_.
        :param content_disposition: See put_object_.
        :param content_encoding: See put_object_.
        :param content_language: See put_object_.
        :param content_length: See put_object_.
        :param content_md5: See put_object_.
        :param content_type: See put_object_.
        :param checksum_algorithm: See put_object_.
        :param checksum_crc32: See put_object_.
        :param checksum_crc32c: See put_object_.
        :param checksum_sha1: See put_object_.
        :param checksum_sha256: See put_object_.
        :param expires_datetime: See put_object_.
        :param grant_full_control: See put_object_.
        :param grant_read: See put_object_.
        :param grant_read_acp: See put_object_.
        :param grant_write_acp: See put_object_.
        :param server_side_encryption: See put_object_.
        :param storage_class: See put_object_.
        :param website_redirect_location: See put_object_.
        :param sse_customer_algorithm: See put_object_.
        :param sse_customer_key: See put_object_.
        :param sse_kms_key_id: See put_object_.
        :param sse_kms_encryption_context: See put_object_.
        :param bucket_key_enabled: See put_object_.
        :param request_payer: See put_object_.
        :param object_lock_mode: See put_object_.
        :param object_lock_retain_until_datetime: See put_object_.
        :param object_lock_legal_hold_status: See put_object_.
        :param expected_bucket_owner: See put_object_.
        :param if_match: only write if the ETag of the object is this one
            (nobody changed it since you read it), See put_object_.
        :param if_none_match: ``"*"`` only writes if the object does not exist
            (a delete marker as the latest version counts as not existing),
            See put_object_.
        :param bsm: See bsm_.

        :return: a new :class:`~s3pathlib.core.s3path.S3Path` with the metadata
            snapshot of the written object (``size``, ``etag``, ``metadata``,
            ``version_id``, ...); this ``S3Path`` is not changed.

        :raises S3PathTypeError: for a bucket, a relative path or the void
            path.
        """
        self._ensure_has_object()
        s3_client = resolve_s3_client(s3_context, bsm)
        if metadata is not NOTHING:
            warn_upper_case_in_metadata_key(metadata)
        response = s3_client.put_object(
            **resolve_kwargs(
                Bucket=self.bucket,
                Key=self.key,
                Body=data,
                Metadata=metadata,
                Tagging=tags if tags is NOTHING else encode_url_query(tags),
                ACL=acl,
                CacheControl=cache_control,
                ContentDisposition=content_disposition,
                ContentEncoding=content_encoding,
                ContentLanguage=content_language,
                ContentLength=content_length,
                ContentMD5=content_md5,
                ContentType=content_type,
                ChecksumAlgorithm=checksum_algorithm,
                ChecksumCRC32=checksum_crc32,
                ChecksumCRC32C=checksum_crc32c,
                ChecksumSHA1=checksum_sha1,
                ChecksumSHA256=checksum_sha256,
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
                IfMatch=if_match,
                IfNoneMatch=if_none_match,
            )
        )
        response.pop("ResponseMetadata", None)
        response["ContentLength"] = len(data)
        # the user metadata the object has, as S3 stores it
        stored_metadata = dict()
        if metadata is not NOTHING:
            for key, value in metadata.items():
                stored_metadata[key.lower()] = value
        response["Metadata"] = stored_metadata
        s3path = self.copy()
        s3path._set_meta(
            response,
            complete=False,
            s3_client=explicit_s3_client(s3_client, bsm),
        )
        return s3path

    def write_text(
        self: S3Path,
        data: str,
        encoding: str = "utf-8",
        errors: str = "strict",
        metadata: MetadataType = NOTHING,
        tags: TagType = NOTHING,
        acl: str = NOTHING,
        cache_control: str = NOTHING,
        content_disposition: str = NOTHING,
        content_encoding: str = NOTHING,
        content_language: str = NOTHING,
        content_length: int = NOTHING,
        content_md5: str = NOTHING,
        content_type: str = NOTHING,
        checksum_algorithm: str = NOTHING,
        checksum_crc32: str = NOTHING,
        checksum_crc32c: str = NOTHING,
        checksum_sha1: str = NOTHING,
        checksum_sha256: str = NOTHING,
        expires_datetime: datetime = NOTHING,
        grant_full_control: str = NOTHING,
        grant_read: str = NOTHING,
        grant_read_acp: str = NOTHING,
        grant_write_acp: str = NOTHING,
        server_side_encryption: str = NOTHING,
        storage_class: str = NOTHING,
        website_redirect_location: str = NOTHING,
        sse_customer_algorithm: str = NOTHING,
        sse_customer_key: str = NOTHING,
        sse_kms_key_id: str = NOTHING,
        sse_kms_encryption_context: str = NOTHING,
        bucket_key_enabled: bool = NOTHING,
        request_payer: str = NOTHING,
        object_lock_mode: str = NOTHING,
        object_lock_retain_until_datetime: datetime = NOTHING,
        object_lock_legal_hold_status: str = NOTHING,
        expected_bucket_owner: str = NOTHING,
        if_match: str = NOTHING,
        if_none_match: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> S3Path:
        """
        Write the text ``data`` to the object, see :meth:`write_bytes`.

        Example::

            >>> s3path_new = S3Path("s3://my-bucket/write-text.txt").write_text("hello")
            >>> s3path_new.size
            5

        :param data: the text to write.
        :param encoding: See encode_.
        :param errors: See encode_.
        :param metadata: the user metadata, a dict of str. S3 stores the keys
            in lower case.
        :param tags: the object tags, a dict of str.
        :param acl: See put_object_.
        :param cache_control: See put_object_.
        :param content_disposition: See put_object_.
        :param content_encoding: See put_object_.
        :param content_language: See put_object_.
        :param content_length: See put_object_.
        :param content_md5: See put_object_.
        :param content_type: See put_object_.
        :param checksum_algorithm: See put_object_.
        :param checksum_crc32: See put_object_.
        :param checksum_crc32c: See put_object_.
        :param checksum_sha1: See put_object_.
        :param checksum_sha256: See put_object_.
        :param expires_datetime: See put_object_.
        :param grant_full_control: See put_object_.
        :param grant_read: See put_object_.
        :param grant_read_acp: See put_object_.
        :param grant_write_acp: See put_object_.
        :param server_side_encryption: See put_object_.
        :param storage_class: See put_object_.
        :param website_redirect_location: See put_object_.
        :param sse_customer_algorithm: See put_object_.
        :param sse_customer_key: See put_object_.
        :param sse_kms_key_id: See put_object_.
        :param sse_kms_encryption_context: See put_object_.
        :param bucket_key_enabled: See put_object_.
        :param request_payer: See put_object_.
        :param object_lock_mode: See put_object_.
        :param object_lock_retain_until_datetime: See put_object_.
        :param object_lock_legal_hold_status: See put_object_.
        :param expected_bucket_owner: See put_object_.
        :param if_match: only write if the ETag of the object is this one
            (nobody changed it since you read it), See put_object_.
        :param if_none_match: ``"*"`` only writes if the object does not exist
            (a delete marker as the latest version counts as not existing),
            See put_object_.
        :param bsm: See bsm_.

        :return: a new :class:`~s3pathlib.core.s3path.S3Path` with the metadata
            snapshot of the written object (``size``, ``etag``, ``metadata``,
            ``version_id``, ...); this ``S3Path`` is not changed.

        :raises S3PathTypeError: for a bucket, a relative path or the void
            path.
        """
        body = data.encode(encoding, errors=errors)
        return self.write_bytes(
            data=body,
            metadata=metadata,
            tags=tags,
            bsm=bsm,
            acl=acl,
            cache_control=cache_control,
            content_disposition=content_disposition,
            content_encoding=content_encoding,
            content_language=content_language,
            content_length=content_length,
            content_md5=content_md5,
            content_type=content_type,
            checksum_algorithm=checksum_algorithm,
            checksum_crc32=checksum_crc32,
            checksum_crc32c=checksum_crc32c,
            checksum_sha1=checksum_sha1,
            checksum_sha256=checksum_sha256,
            expires_datetime=expires_datetime,
            grant_full_control=grant_full_control,
            grant_read=grant_read,
            grant_read_acp=grant_read_acp,
            grant_write_acp=grant_write_acp,
            server_side_encryption=server_side_encryption,
            storage_class=storage_class,
            website_redirect_location=website_redirect_location,
            sse_customer_algorithm=sse_customer_algorithm,
            sse_customer_key=sse_customer_key,
            sse_kms_key_id=sse_kms_key_id,
            sse_kms_encryption_context=sse_kms_encryption_context,
            bucket_key_enabled=bucket_key_enabled,
            request_payer=request_payer,
            object_lock_mode=object_lock_mode,
            object_lock_retain_until_datetime=object_lock_retain_until_datetime,
            object_lock_legal_hold_status=object_lock_legal_hold_status,
            expected_bucket_owner=expected_bucket_owner,
            if_match=if_match,
            if_none_match=if_none_match,
        )

    def touch(
        self: S3Path,
        exist_ok: bool = False,
        metadata: MetadataType = NOTHING,
        tags: TagType = NOTHING,
        acl: str = NOTHING,
        cache_control: str = NOTHING,
        content_disposition: str = NOTHING,
        content_encoding: str = NOTHING,
        content_language: str = NOTHING,
        content_length: int = NOTHING,
        content_md5: str = NOTHING,
        content_type: str = NOTHING,
        checksum_algorithm: str = NOTHING,
        checksum_crc32: str = NOTHING,
        checksum_crc32c: str = NOTHING,
        checksum_sha1: str = NOTHING,
        checksum_sha256: str = NOTHING,
        expires_datetime: datetime = NOTHING,
        grant_full_control: str = NOTHING,
        grant_read: str = NOTHING,
        grant_read_acp: str = NOTHING,
        grant_write_acp: str = NOTHING,
        server_side_encryption: str = NOTHING,
        storage_class: str = NOTHING,
        website_redirect_location: str = NOTHING,
        sse_customer_algorithm: str = NOTHING,
        sse_customer_key: str = NOTHING,
        sse_kms_key_id: str = NOTHING,
        sse_kms_encryption_context: str = NOTHING,
        bucket_key_enabled: bool = NOTHING,
        request_payer: str = NOTHING,
        object_lock_mode: str = NOTHING,
        object_lock_retain_until_datetime: datetime = NOTHING,
        object_lock_legal_hold_status: str = NOTHING,
        expected_bucket_owner: str = NOTHING,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> None:
        """
        Create an empty object if it does not exist, with one conditional
        put_object_ (``IfNoneMatch="*"``), so it is atomic: an object written
        by someone else in between is never replaced. An existing object is
        never changed.

        Example::

            >>> s3path = S3Path("s3://my-bucket/touch.txt")
            >>> s3path.touch()
            >>> s3path.read_text()
            ''
            >>> s3path.touch(exist_ok=True)

        :param exist_ok: if ``False`` (default), raise ``S3FileAlreadyExist``
            when the object exists; if ``True``, do nothing then.
        :param metadata: the user metadata of the new object.
        :param tags: the tags of the new object.

        The other arguments are the ones of :meth:`write_bytes`.

        :raises S3PathTypeError: for a relative path or the void path.
        :raises S3PathIsNotFileError: for a folder or a bucket.
        :raises S3FileAlreadyExist: if the object exists and ``exist_ok`` is
            ``False``.
        """
        self.ensure_not_relpath()
        self.ensure_object()
        try:
            self.write_bytes(
                data=b"",
                metadata=metadata,
                tags=tags,
                acl=acl,
                cache_control=cache_control,
                content_disposition=content_disposition,
                content_encoding=content_encoding,
                content_language=content_language,
                content_length=content_length,
                content_md5=content_md5,
                content_type=content_type,
                checksum_algorithm=checksum_algorithm,
                checksum_crc32=checksum_crc32,
                checksum_crc32c=checksum_crc32c,
                checksum_sha1=checksum_sha1,
                checksum_sha256=checksum_sha256,
                expires_datetime=expires_datetime,
                grant_full_control=grant_full_control,
                grant_read=grant_read,
                grant_read_acp=grant_read_acp,
                grant_write_acp=grant_write_acp,
                server_side_encryption=server_side_encryption,
                storage_class=storage_class,
                website_redirect_location=website_redirect_location,
                sse_customer_algorithm=sse_customer_algorithm,
                sse_customer_key=sse_customer_key,
                sse_kms_key_id=sse_kms_key_id,
                sse_kms_encryption_context=sse_kms_encryption_context,
                bucket_key_enabled=bucket_key_enabled,
                request_payer=request_payer,
                object_lock_mode=object_lock_mode,
                object_lock_retain_until_datetime=object_lock_retain_until_datetime,
                object_lock_legal_hold_status=object_lock_legal_hold_status,
                expected_bucket_owner=expected_bucket_owner,
                if_none_match="*",
                bsm=bsm,
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "PreconditionFailed":
                if exist_ok:
                    return
                else:
                    raise exc.S3FileAlreadyExist.make(self.uri) from e
            else:
                raise e

    def _write_folder_marker(
        self: S3Path,
        bsm: BotoSesManager | S3Client | None,
    ) -> bool:
        """
        Write the folder marker object of this folder, unless it exists.

        :return: ``True`` if it was written.
        """
        try:
            self.write_bytes(data=b"", if_none_match="*", bsm=bsm)
            return True
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "PreconditionFailed":
                return False
            else:
                raise e

    def mkdir(
        self: S3Path,
        exist_ok: bool = False,
        parents: bool = False,
        bsm: BotoSesManager | S3Client | None = None,
    ) -> None:
        """
        Create the folder marker object of this folder (an empty object whose
        key ends with ``/``, what "Create folder" does in the S3 console), and
        of each parent folder with ``parents=True``. A marker that exists is
        never replaced (conditional put_object_ with ``IfNoneMatch="*"``).

        A folder exists in S3 as soon as an object key starts with it, even
        without marker ("soft folder"), see ``exists()``.

        Example::

            >>> s3dir = S3Path("s3://my-bucket/mkdir/sub/")
            >>> s3dir.mkdir(parents=True)
            >>> S3Path("s3://my-bucket/mkdir/").read_text()
            ''
            >>> s3dir.mkdir(exist_ok=True)

        :param exist_ok: if ``False`` (default), raise
            ``S3FolderAlreadyExist`` when the folder exists (with or without
            marker); if ``True``, only write the markers that do not exist.
        :param parents: if ``True``, also write the markers of the parent
            folders (up to the bucket).
        :param bsm: See bsm_.

        :raises S3PathTypeError: for a relative path, the void path, or a
            bucket (use ``create_bucket()``).
        :raises S3PathIsNotFolderError: for a file.
        :raises S3FolderAlreadyExist: if the folder exists and ``exist_ok`` is
            ``False``.
        """
        self.ensure_not_relpath()
        self.ensure_dir()
        if self.is_bucket():
            raise exc.S3PathTypeError(
                f"{self._error_label()} is a bucket, use create_bucket() to "
                f"create it"
            )
        if exist_ok is False:
            if self.exists(bsm=bsm):
                raise exc.S3FolderAlreadyExist.make(self.uri)
        written = self._write_folder_marker(bsm=bsm)
        # a marker written by someone else after the exists() check
        if (written is False) and (exist_ok is False):
            raise exc.S3FolderAlreadyExist.make(self.uri)
        if parents:
            for p in self.parents:
                if p.is_bucket() is False:
                    p._write_folder_marker(bsm=bsm)

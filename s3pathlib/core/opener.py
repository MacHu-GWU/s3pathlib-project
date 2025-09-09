# -*- coding: utf-8 -*-

"""
Smart open library integration.

.. _bsm: https://github.com/aws-samples/boto-session-manager-project
.. _smart_open: https://github.com/RaRe-Technologies/smart_open
.. _get_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.get_object
.. _put_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object
"""

import typing as T
import copy
from datetime import datetime

from func_args import NOTHING, resolve_kwargs

from ..metadata import warn_upper_case_in_metadata_key
from ..aws import context
from ..type import MetadataType, TagType
from ..tag import encode_url_query

from .resolve_s3_client import resolve_s3_client

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from boto_session_manager import BotoSesManager
    from mypy_boto3_s3 import S3Client


class OpenerAPIMixin:
    """
    A mixin class that implements the file-object protocol.
    """

    def open(
        self: "S3Path",
        mode: T.Optional[str] = "r",
        version_id: T.Optional[str] = NOTHING,
        buffering: T.Optional[int] = -1,
        encoding: T.Optional[str] = None,
        errors: T.Optional[str] = None,
        newline: T.Optional[str] = None,
        closefd=True,
        opener=None,
        ignore_ext: bool = False,
        compression: T.Optional[str] = None,
        multipart_upload: bool = True,
        metadata: T.Optional[MetadataType] = NOTHING,
        tags: T.Optional[TagType] = NOTHING,
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
        range: str = NOTHING,
        response_cache_control: str = NOTHING,
        response_content_disposition: str = NOTHING,
        response_content_encoding: str = NOTHING,
        response_content_language: str = NOTHING,
        response_content_type: str = NOTHING,
        response_expires: str = NOTHING,
        part_number: int = NOTHING,
        checksum_mode: str = NOTHING,
        # other parameters
        transport_params: T.Optional[dict] = None,
        bsm: T.Optional[T.Union["BotoSesManager", "S3Client"]] = None,
    ):
        """
        Open S3Path as a file-liked object.

        Example::

            >>> import json
            >>> with S3Path("s3://bucket/data.json").open("w") as f:
            ...     json.dump({"a": 1}, f)

            >>> with S3Path("s3://bucket/data.json").open("r") as f:
            ...     data = json.load(f)

        :param mode: "r", "w", "rb", "wb".
        :param version_id: optional version id you want to read from.
        :param buffering: See smart_open_.
        :param encoding: See smart_open_.
        :param errors: See smart_open_.
        :param newline: See smart_open_.
        :param closefd: See smart_open_.
        :param opener: See smart_open_.
        :param ignore_ext: See smart_open_.
        :param compression: whether do you want to compress the content.
        :param multipart_upload: do you want to use multi-parts upload,
            by default it is True.
        :param metadata: also put the user defined metadata dictionary.
        :param tags: also put the tag dictionary.
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
        :param range: See get_object_.
        :param response_cache_control: See get_object_.
        :param response_content_disposition: See get_object_.
        :param response_content_encoding: See get_object_.
        :param response_content_language: See get_object_.
        :param response_content_type: See get_object_.
        :param response_expires: See get_object_.
        :param part_number: See get_object_.
        :param checksum_mode: See get_object_.
        :param bsm: See bsm_.

        :return: a file-like object that has ``read()`` and ``write()`` method.

        See smart_open_ for more info.
        Also see https://github.com/RaRe-Technologies/smart_open/blob/develop/howto.md#how-to-access-s3-anonymously
        for S3 related info.

        .. versionadded:: 1.0.1

        .. versionchanged:: 1.2.1

            add ``metadata`` and ``tags`` parameters

        .. versionchanged:: 2.0.1

            add ``version_id`` parameter

        .. versionchanged:: 2.1.1

            add full list of get_object, put_object, create_multipart_upload arguments
        """
        import smart_open

        s3_client = resolve_s3_client(context, bsm)
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
        # write API doesn't take version_id parameter
        # set it to NOTHING in case human made a mistake
        if mode.startswith("w") is True:  # pragma: no cover
            version_id = NOTHING
            if metadata is not NOTHING:
                warn_upper_case_in_metadata_key(metadata)
            is_write_mode = True
        elif mode.startswith("r") is True:  # pragma: no cover
            is_write_mode = False
        else:  # pragma: no cover
            raise ValueError("mode must be one of 'r', 'w', 'rb', 'wb'")

        if version_id is not NOTHING:
            transport_params["version_id"] = version_id

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

        existing_client_kwargs: T.Dict[str, T.Dict[str, T.Any]]
        existing_client_kwargs = transport_params.get("client_kwargs", {})
        if is_write_mode:
            # if any of additional parameters exists, we need additional handling
            if sum([metadata is not NOTHING, tags is not NOTHING]) > 0:
                s3_client_kwargs = resolve_kwargs(
                    Metadata=metadata,
                    Tagging=tags if tags is NOTHING else encode_url_query(tags),
                )
                if multipart_upload:
                    key_name = "S3.Client.create_multipart_upload"
                    s3_client_kwargs.update(
                        resolve_kwargs(
                            ACL=acl,
                            CacheControl=cache_control,
                            ContentDisposition=content_disposition,
                            ContentEncoding=content_encoding,
                            ContentLanguage=content_language,
                            ContentType=content_type,
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
                            ChecksumAlgorithm=checksum_algorithm,
                        )
                    )
                else:
                    s3_client_kwargs.update(
                        resolve_kwargs(
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
                        )
                    )
                    key_name = "S3.Client.put_object"
                if key_name in existing_client_kwargs:
                    existing_client_kwargs[key_name].update(s3_client_kwargs)
                else:
                    existing_client_kwargs[key_name] = s3_client_kwargs
                if len(existing_client_kwargs):
                    transport_params["client_kwargs"] = existing_client_kwargs
        else:  # read mode only
            s3_client_kwargs = resolve_kwargs(
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
            )
            key_name = "S3.Client.get_object"
            if key_name in existing_client_kwargs:  # pragma: no cover
                existing_client_kwargs[key_name].update(s3_client_kwargs)
            else:
                existing_client_kwargs[key_name] = s3_client_kwargs
            if len(existing_client_kwargs):
                transport_params["client_kwargs"] = existing_client_kwargs

        return smart_open.open(**open_kwargs)

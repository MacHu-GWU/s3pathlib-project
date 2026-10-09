# -*- coding: utf-8 -*-

"""
Copy and move S3 objects and folders, with copy_object_.

**Metadata and content headers.** S3 ignores ``content_type``,
``cache_control``, ``content_disposition``, ``content_encoding``,
``content_language``, ``expires_datetime`` and ``website_redirect_location``
unless the user metadata is replaced too (``MetadataDirective=REPLACE``), and
then resets the ones that are not given (e.g. ``ContentType`` becomes
``binary/octet-stream``). So when any of them, or ``metadata``, is given,
s3pathlib first reads the source object (``head_object``), keeps its values
for the ones not given, and replaces the rest: only what you pass changes.
Otherwise the copy keeps all of them, without the extra call.

**Size limit.** copy_object_ copies objects up to 5 GB. A bigger object raises
``InvalidRequest``; copy it with boto3's managed ``s3_client.copy()``.

**Errors.** Errors of the AWS calls are raised as is
(``botocore.exceptions.ClientError``), e.g. ``NoSuchKey`` for a missing
source, ``NoSuchBucket``.

.. _copy_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/copy_object.html
"""

from __future__ import annotations

import typing as T
from datetime import datetime

import botocore.exceptions

from .._arg import OPT
from .._arg import remove_optional
from .. import exc
from .. import utils
from ..type import TagType, MetadataType
from ..tag import encode_url_query
from ..better_client.head_object import head_object
from ..better_client.head_object import is_object_exists
from ..better_client.list_objects import paginate_list_objects_v2
from ..better_client.delete_object import _delete_objects
from ..better_client.delete_object import delete_object

from .resolve_s3_client import resolve_s3_client
from ..aws import s3_context

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client

# copy_object parameters that S3 only applies with MetadataDirective=REPLACE,
# and resets when they are not given; also fields of head_object
_REPLACE_PARAMS = (
    "ContentType",
    "CacheControl",
    "ContentDisposition",
    "ContentEncoding",
    "ContentLanguage",
    "Expires",
    "WebsiteRedirectLocation",
)


def _ensure_no_overlap(src: S3Path, dst: S3Path):
    """
    :raises ValueError: if the two folders are in the same bucket and one is
        inside the other (or they are equal).
    """
    if src.bucket == dst.bucket:
        if dst.key.startswith(src.key) or src.key.startswith(dst.key):
            raise ValueError(
                f"{src.uri!r} and {dst.uri!r} overlap: copying would overwrite "
                f"source objects before they are copied (and moving would "
                f"delete the copies); copy to another folder first"
            )


def _copy_object(
    s3_client: S3Client,
    src_bucket: str,
    src_key: str,
    dst_bucket: str,
    dst_key: str,
    version_id: str,
    overwrite: bool,
    metadata: MetadataType,
    tags: TagType,
    replace_kwargs: dict,
    other_kwargs: dict,
    head_kwargs: dict,
) -> dict:
    """
    Copy one object, see the module docstring.

    :param replace_kwargs: the given ``_REPLACE_PARAMS``.
    :param other_kwargs: the other given copy_object parameters.
    :param head_kwargs: the given parameters to read the source with
        ``head_object``.

    :return: the copy_object response.

    :raises S3FileAlreadyExist: if ``overwrite`` is ``False`` and the target
        exists.
    """
    kwargs = dict(
        Bucket=dst_bucket,
        Key=dst_key,
        CopySource=remove_optional(
            Bucket=src_bucket,
            Key=src_key,
            VersionId=version_id,
        ),
    )
    kwargs.update(other_kwargs)
    if (metadata is not OPT) or len(replace_kwargs):
        src = head_object(
            s3_client,
            src_bucket,
            src_key,
            version_id=version_id,
            **head_kwargs,
        )
        kwargs["MetadataDirective"] = "REPLACE"
        if metadata is OPT:
            kwargs["Metadata"] = src["Metadata"]
        else:
            kwargs["Metadata"] = metadata
        for param in _REPLACE_PARAMS:
            if param in replace_kwargs:
                kwargs[param] = replace_kwargs[param]
            elif param in src:
                kwargs[param] = src[param]
    if tags is not OPT:
        kwargs["Tagging"] = encode_url_query(tags)
        kwargs["TaggingDirective"] = "REPLACE"
    if overwrite is False:
        # atomic on AWS (moto ignores it, the caller checks first)
        kwargs["IfNoneMatch"] = "*"
    try:
        return s3_client.copy_object(**kwargs)
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "PreconditionFailed":
            raise exc.S3FileAlreadyExist.make(f"s3://{dst_bucket}/{dst_key}") from e
        else:
            raise e


class CopyAPIMixin:
    """
    A mixin class that implements copy related methods.
    """

    def copy_file(
        self: S3Path,
        dst: S3Path,
        version_id: str = OPT,
        metadata: MetadataType = OPT,
        tags: TagType = OPT,
        overwrite: bool = False,
        s3_client: S3Client | None = None,
        acl: str = OPT,
        cache_control: str = OPT,
        content_disposition: str = OPT,
        content_encoding: str = OPT,
        content_language: str = OPT,
        content_type: str = OPT,
        copy_source_if_match: str = OPT,
        copy_source_if_modified_since: datetime = OPT,
        copy_source_if_none_match: str = OPT,
        copy_source_if_unmodified_since: datetime = OPT,
        expires_datetime: datetime = OPT,
        grant_full_control: str = OPT,
        grant_read: str = OPT,
        grant_read_acp: str = OPT,
        grant_write_acp: str = OPT,
        server_side_encryption: str = OPT,
        storage_class: str = OPT,
        website_redirect_location: str = OPT,
        sse_customer_algorithm: str = OPT,
        sse_customer_key: str = OPT,
        sse_kms_key_id: str = OPT,
        sse_kms_encryption_context: str = OPT,
        bucket_key_enabled: bool = OPT,
        copy_source_sse_customer_algorithm: str = OPT,
        copy_source_sse_customer_key: str = OPT,
        request_payer: str = OPT,
        object_lock_mode: str = OPT,
        object_lock_retain_until_datetime: datetime = OPT,
        object_lock_legal_hold_status: str = OPT,
        expected_bucket_owner: str = OPT,
        expected_source_bucket_owner: str = OPT,
    ) -> S3Path:
        """
        Copy this object to the object ``dst``, see copy_object_ and the
        module docstring. Copying an object to itself with new metadata
        changes its metadata in place.

        :param dst: the target object.
        :param version_id: the version of this object to copy, default the
            latest one.
        :param metadata: the user metadata of the copy; default: the one of
            the source.
        :param tags: the tags of the copy; default: the ones of the source.
        :param overwrite: if ``False`` (default), raise ``S3FileAlreadyExist``
            when ``dst`` exists (a delete marker as the latest version counts
            as not existing). On AWS the copy is conditional
            (``IfNoneMatch="*"``), so an object written by someone else in
            between is not replaced either.

        The other arguments are the parameters of copy_object_ with the same
        names (``expires_datetime`` is ``Expires``).

        :return: a new :class:`~s3pathlib.core.s3path.S3Path` of the copy,
            with the metadata snapshot of the response (``etag``,
            ``last_modified_at``, ``version_id``); this ``S3Path`` and ``dst``
            are not changed.

        :raises S3PathTypeError: if this path or ``dst`` is a relative path or
            the void path.
        :raises S3PathIsNotFileError: if this path or ``dst`` is not a file.
        :raises S3FileAlreadyExist: if ``overwrite`` is ``False`` and ``dst``
            exists.
        """
        self.ensure_not_relpath()
        self.ensure_object()
        dst.ensure_not_relpath()
        dst.ensure_object()
        if overwrite is False:
            dst.ensure_not_exists(s3_client=s3_client)
        client = resolve_s3_client(s3_context, s3_client)
        replace_kwargs, other_kwargs, head_kwargs = _make_copy_kwargs(
            cache_control=cache_control,
            content_disposition=content_disposition,
            content_encoding=content_encoding,
            content_language=content_language,
            content_type=content_type,
            expires_datetime=expires_datetime,
            website_redirect_location=website_redirect_location,
            acl=acl,
            copy_source_if_match=copy_source_if_match,
            copy_source_if_modified_since=copy_source_if_modified_since,
            copy_source_if_none_match=copy_source_if_none_match,
            copy_source_if_unmodified_since=copy_source_if_unmodified_since,
            grant_full_control=grant_full_control,
            grant_read=grant_read,
            grant_read_acp=grant_read_acp,
            grant_write_acp=grant_write_acp,
            server_side_encryption=server_side_encryption,
            storage_class=storage_class,
            sse_customer_algorithm=sse_customer_algorithm,
            sse_customer_key=sse_customer_key,
            sse_kms_key_id=sse_kms_key_id,
            sse_kms_encryption_context=sse_kms_encryption_context,
            bucket_key_enabled=bucket_key_enabled,
            copy_source_sse_customer_algorithm=copy_source_sse_customer_algorithm,
            copy_source_sse_customer_key=copy_source_sse_customer_key,
            request_payer=request_payer,
            object_lock_mode=object_lock_mode,
            object_lock_retain_until_datetime=object_lock_retain_until_datetime,
            object_lock_legal_hold_status=object_lock_legal_hold_status,
            expected_bucket_owner=expected_bucket_owner,
            expected_source_bucket_owner=expected_source_bucket_owner,
        )
        response = _copy_object(
            s3_client=client,
            src_bucket=self.bucket,
            src_key=self.key,
            dst_bucket=dst.bucket,
            dst_key=dst.key,
            version_id=version_id,
            overwrite=overwrite,
            metadata=metadata,
            tags=tags,
            replace_kwargs=replace_kwargs,
            other_kwargs=other_kwargs,
            head_kwargs=head_kwargs,
        )
        result = response["CopyObjectResult"]
        meta = {"ETag": result["ETag"], "LastModified": result["LastModified"]}
        if "VersionId" in response:
            meta["VersionId"] = response["VersionId"]
        if metadata is not OPT:
            # the user metadata the copy has, as S3 stores it
            stored_metadata = dict()
            for key, value in metadata.items():
                stored_metadata[key.lower()] = value
            meta["Metadata"] = stored_metadata
        s3path = dst.copy()
        s3path._set_meta(
            meta,
            complete=False,
            s3_client=s3_client,
        )
        return s3path

    def _copy_dir(
        self: S3Path,
        dst: S3Path,
        metadata: MetadataType,
        tags: TagType,
        overwrite: bool,
        s3_client: S3Client | None,
        kwargs: dict,
    ) -> list[str]:
        """
        The implementation of :meth:`copy_dir`.

        :param kwargs: the other arguments of :meth:`copy_dir`.

        :return: the copied source keys.
        """
        self.ensure_not_relpath()
        self.ensure_dir()
        dst.ensure_not_relpath()
        dst.ensure_dir()
        for name in [
            "copy_source_if_match",
            "copy_source_if_modified_since",
            "copy_source_if_none_match",
            "copy_source_if_unmodified_since",
        ]:
            if kwargs[name] is not OPT:
                raise ValueError(
                    f"{name} only applies to copying a file, not a folder"
                )
        _ensure_no_overlap(self, dst)
        client = resolve_s3_client(s3_context, s3_client)
        replace_kwargs, other_kwargs, head_kwargs = _make_copy_kwargs(**kwargs)

        # every key under the folder, folder markers included
        src_keys = list()
        for content in paginate_list_objects_v2(
            s3_client=client,
            bucket=self.bucket,
            prefix=self.key,
        ).contents():
            src_keys.append(content["Key"])
        todo: list[tuple[str, str]] = list()
        for src_key in src_keys:
            dst_key = dst.key + src_key[len(self.key):]
            todo.append((src_key, dst_key))

        if overwrite is False:
            for _, dst_key in todo:
                if is_object_exists(client, dst.bucket, dst_key):
                    raise exc.S3FileAlreadyExist.make(f"s3://{dst.bucket}/{dst_key}")

        for src_key, dst_key in todo:
            _copy_object(
                s3_client=client,
                src_bucket=self.bucket,
                src_key=src_key,
                dst_bucket=dst.bucket,
                dst_key=dst_key,
                version_id=OPT,
                overwrite=overwrite,
                metadata=metadata,
                tags=tags,
                replace_kwargs=replace_kwargs,
                other_kwargs=other_kwargs,
                head_kwargs=head_kwargs,
            )
        return src_keys

    def copy_dir(
        self: S3Path,
        dst: S3Path,
        metadata: MetadataType = OPT,
        tags: TagType = OPT,
        overwrite: bool = False,
        s3_client: S3Client | None = None,
        acl: str = OPT,
        cache_control: str = OPT,
        content_disposition: str = OPT,
        content_encoding: str = OPT,
        content_language: str = OPT,
        content_type: str = OPT,
        copy_source_if_match: str = OPT,
        copy_source_if_modified_since: datetime = OPT,
        copy_source_if_none_match: str = OPT,
        copy_source_if_unmodified_since: datetime = OPT,
        expires_datetime: datetime = OPT,
        grant_full_control: str = OPT,
        grant_read: str = OPT,
        grant_read_acp: str = OPT,
        grant_write_acp: str = OPT,
        server_side_encryption: str = OPT,
        storage_class: str = OPT,
        website_redirect_location: str = OPT,
        sse_customer_algorithm: str = OPT,
        sse_customer_key: str = OPT,
        sse_kms_key_id: str = OPT,
        sse_kms_encryption_context: str = OPT,
        bucket_key_enabled: bool = OPT,
        copy_source_sse_customer_algorithm: str = OPT,
        copy_source_sse_customer_key: str = OPT,
        request_payer: str = OPT,
        object_lock_mode: str = OPT,
        object_lock_retain_until_datetime: datetime = OPT,
        object_lock_legal_hold_status: str = OPT,
        expected_bucket_owner: str = OPT,
        expected_source_bucket_owner: str = OPT,
    ) -> int:
        """
        Copy every object under this folder (or bucket) to the folder ``dst``,
        keeping the paths relative to the folder. Every key is copied, folder
        markers included (``folder/`` itself becomes ``dst``'s marker), so the
        copy has the same folders, even empty ones. The latest version of each
        object is copied. The arguments apply to every object, see
        :meth:`copy_file` and the module docstring.

        :param dst: the target folder; it must not overlap this folder (be
            equal, inside it, or contain it, in the same bucket).
        :param overwrite: if ``False`` (default), check every target key
            first, and copy nothing if any of them exists.

        :return: the number of keys copied.

        :raises S3PathTypeError: if this path or ``dst`` is a relative path or
            the void path.
        :raises S3PathIsNotFolderError: if this path or ``dst`` is a file.
        :raises ValueError: if the folders overlap, or a ``copy_source_if_*``
            argument is given (it would apply to every object).
        :raises S3FileAlreadyExist: if ``overwrite`` is ``False`` and a target
            key exists.
        """
        src_keys = self._copy_dir(
            dst=dst,
            metadata=metadata,
            tags=tags,
            overwrite=overwrite,
            s3_client=s3_client,
            kwargs=dict(
                acl=acl,
                cache_control=cache_control,
                content_disposition=content_disposition,
                content_encoding=content_encoding,
                content_language=content_language,
                content_type=content_type,
                copy_source_if_match=copy_source_if_match,
                copy_source_if_modified_since=copy_source_if_modified_since,
                copy_source_if_none_match=copy_source_if_none_match,
                copy_source_if_unmodified_since=copy_source_if_unmodified_since,
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
                copy_source_sse_customer_algorithm=copy_source_sse_customer_algorithm,
                copy_source_sse_customer_key=copy_source_sse_customer_key,
                request_payer=request_payer,
                object_lock_mode=object_lock_mode,
                object_lock_retain_until_datetime=object_lock_retain_until_datetime,
                object_lock_legal_hold_status=object_lock_legal_hold_status,
                expected_bucket_owner=expected_bucket_owner,
                expected_source_bucket_owner=expected_source_bucket_owner,
            ),
        )
        return len(src_keys)

    def copy_to(
        self: S3Path,
        dst: S3Path,
        version_id: str = OPT,
        metadata: MetadataType = OPT,
        tags: TagType = OPT,
        overwrite: bool = False,
        s3_client: S3Client | None = None,
        acl: str = OPT,
        cache_control: str = OPT,
        content_disposition: str = OPT,
        content_encoding: str = OPT,
        content_language: str = OPT,
        content_type: str = OPT,
        copy_source_if_match: str = OPT,
        copy_source_if_modified_since: datetime = OPT,
        copy_source_if_none_match: str = OPT,
        copy_source_if_unmodified_since: datetime = OPT,
        expires_datetime: datetime = OPT,
        grant_full_control: str = OPT,
        grant_read: str = OPT,
        grant_read_acp: str = OPT,
        grant_write_acp: str = OPT,
        server_side_encryption: str = OPT,
        storage_class: str = OPT,
        website_redirect_location: str = OPT,
        sse_customer_algorithm: str = OPT,
        sse_customer_key: str = OPT,
        sse_kms_key_id: str = OPT,
        sse_kms_encryption_context: str = OPT,
        bucket_key_enabled: bool = OPT,
        copy_source_sse_customer_algorithm: str = OPT,
        copy_source_sse_customer_key: str = OPT,
        request_payer: str = OPT,
        object_lock_mode: str = OPT,
        object_lock_retain_until_datetime: datetime = OPT,
        object_lock_legal_hold_status: str = OPT,
        expected_bucket_owner: str = OPT,
        expected_source_bucket_owner: str = OPT,
    ) -> int:
        """
        Copy this file with :meth:`copy_file`, or this folder with
        :meth:`copy_dir`.

        :return: the number of objects copied (``1`` for a file).

        :raises ValueError: if ``version_id`` is given for a folder.

        It also raises the errors of :meth:`copy_file` / :meth:`copy_dir`.
        """
        self.ensure_not_relpath()
        kwargs = dict(
            metadata=metadata,
            tags=tags,
            overwrite=overwrite,
            s3_client=s3_client,
            acl=acl,
            cache_control=cache_control,
            content_disposition=content_disposition,
            content_encoding=content_encoding,
            content_language=content_language,
            content_type=content_type,
            copy_source_if_match=copy_source_if_match,
            copy_source_if_modified_since=copy_source_if_modified_since,
            copy_source_if_none_match=copy_source_if_none_match,
            copy_source_if_unmodified_since=copy_source_if_unmodified_since,
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
            copy_source_sse_customer_algorithm=copy_source_sse_customer_algorithm,
            copy_source_sse_customer_key=copy_source_sse_customer_key,
            request_payer=request_payer,
            object_lock_mode=object_lock_mode,
            object_lock_retain_until_datetime=object_lock_retain_until_datetime,
            object_lock_legal_hold_status=object_lock_legal_hold_status,
            expected_bucket_owner=expected_bucket_owner,
            expected_source_bucket_owner=expected_source_bucket_owner,
        )
        if self.is_dir():
            if version_id is not OPT:
                raise ValueError("version_id only applies to copying a file")
            return self.copy_dir(dst=dst, **kwargs)
        else:
            self.copy_file(dst=dst, version_id=version_id, **kwargs)
            return 1

    def move_to(
        self: S3Path,
        dst: S3Path,
        metadata: MetadataType = OPT,
        tags: TagType = OPT,
        overwrite: bool = False,
        s3_client: S3Client | None = None,
        acl: str = OPT,
        cache_control: str = OPT,
        content_disposition: str = OPT,
        content_encoding: str = OPT,
        content_language: str = OPT,
        content_type: str = OPT,
        copy_source_if_match: str = OPT,
        copy_source_if_modified_since: datetime = OPT,
        copy_source_if_none_match: str = OPT,
        copy_source_if_unmodified_since: datetime = OPT,
        expires_datetime: datetime = OPT,
        grant_full_control: str = OPT,
        grant_read: str = OPT,
        grant_read_acp: str = OPT,
        grant_write_acp: str = OPT,
        server_side_encryption: str = OPT,
        storage_class: str = OPT,
        website_redirect_location: str = OPT,
        sse_customer_algorithm: str = OPT,
        sse_customer_key: str = OPT,
        sse_kms_key_id: str = OPT,
        sse_kms_encryption_context: str = OPT,
        bucket_key_enabled: bool = OPT,
        copy_source_sse_customer_algorithm: str = OPT,
        copy_source_sse_customer_key: str = OPT,
        request_payer: str = OPT,
        object_lock_mode: str = OPT,
        object_lock_retain_until_datetime: datetime = OPT,
        object_lock_legal_hold_status: str = OPT,
        expected_bucket_owner: str = OPT,
        expected_source_bucket_owner: str = OPT,
    ) -> int:
        """
        Move this file or folder: copy it with :meth:`copy_to`, then delete
        exactly the copied source keys (an object written to the source folder
        during the move is neither copied nor deleted). With versioning,
        deleting adds delete markers, the old versions are kept.

        :param dst: the target; a file can not be moved to itself, and a
            folder can not be moved to a folder that overlaps it.

        :return: the number of objects moved.

        :raises ValueError: if a file is moved to itself, or a folder to an
            overlapping folder.

        It also raises the errors of :meth:`copy_file` / :meth:`copy_dir`.
        """
        self.ensure_not_relpath()
        dst.ensure_not_relpath()
        kwargs = dict(
            acl=acl,
            cache_control=cache_control,
            content_disposition=content_disposition,
            content_encoding=content_encoding,
            content_language=content_language,
            content_type=content_type,
            copy_source_if_match=copy_source_if_match,
            copy_source_if_modified_since=copy_source_if_modified_since,
            copy_source_if_none_match=copy_source_if_none_match,
            copy_source_if_unmodified_since=copy_source_if_unmodified_since,
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
            copy_source_sse_customer_algorithm=copy_source_sse_customer_algorithm,
            copy_source_sse_customer_key=copy_source_sse_customer_key,
            request_payer=request_payer,
            object_lock_mode=object_lock_mode,
            object_lock_retain_until_datetime=object_lock_retain_until_datetime,
            object_lock_legal_hold_status=object_lock_legal_hold_status,
            expected_bucket_owner=expected_bucket_owner,
            expected_source_bucket_owner=expected_source_bucket_owner,
        )
        client = resolve_s3_client(s3_context, s3_client)
        if self.is_dir():
            src_keys = self._copy_dir(
                dst=dst,
                metadata=metadata,
                tags=tags,
                overwrite=overwrite,
                s3_client=s3_client,
                kwargs=kwargs,
            )
            n_deleted = 0
            for keys in utils.grouper_list(src_keys, 1000):
                objects = [{"Key": key} for key in keys]
                n_deleted += _delete_objects(
                    s3_client=client,
                    bucket=self.bucket,
                    objects=objects,
                    n_deleted=n_deleted,
                    mfa=OPT,
                    request_payer=request_payer,
                    bypass_governance_retention=OPT,
                    expected_bucket_owner=OPT,
                    check_sum_algorithm=OPT,
                )
            return len(src_keys)
        else:
            if dst == self:
                raise ValueError(f"cannot move {self.uri!r} to itself")
            self.copy_file(
                dst=dst,
                metadata=metadata,
                tags=tags,
                overwrite=overwrite,
                s3_client=s3_client,
                **kwargs,
            )
            delete_object(client, self.bucket, self.key)
            return 1


def _make_copy_kwargs(
    cache_control: str,
    content_disposition: str,
    content_encoding: str,
    content_language: str,
    content_type: str,
    expires_datetime: datetime,
    website_redirect_location: str,
    acl: str,
    copy_source_if_match: str,
    copy_source_if_modified_since: datetime,
    copy_source_if_none_match: str,
    copy_source_if_unmodified_since: datetime,
    grant_full_control: str,
    grant_read: str,
    grant_read_acp: str,
    grant_write_acp: str,
    server_side_encryption: str,
    storage_class: str,
    sse_customer_algorithm: str,
    sse_customer_key: str,
    sse_kms_key_id: str,
    sse_kms_encryption_context: str,
    bucket_key_enabled: bool,
    copy_source_sse_customer_algorithm: str,
    copy_source_sse_customer_key: str,
    request_payer: str,
    object_lock_mode: str,
    object_lock_retain_until_datetime: datetime,
    object_lock_legal_hold_status: str,
    expected_bucket_owner: str,
    expected_source_bucket_owner: str,
) -> tuple[dict, dict, dict]:
    """
    Map the arguments of the copy methods to boto3 parameters.

    :return: ``(replace_kwargs, other_kwargs, head_kwargs)``, see
        :func:`_copy_object`.
    """
    replace_kwargs = remove_optional(
        CacheControl=cache_control,
        ContentDisposition=content_disposition,
        ContentEncoding=content_encoding,
        ContentLanguage=content_language,
        ContentType=content_type,
        Expires=expires_datetime,
        WebsiteRedirectLocation=website_redirect_location,
    )
    other_kwargs = remove_optional(
        ACL=acl,
        CopySourceIfMatch=copy_source_if_match,
        CopySourceIfModifiedSince=copy_source_if_modified_since,
        CopySourceIfNoneMatch=copy_source_if_none_match,
        CopySourceIfUnmodifiedSince=copy_source_if_unmodified_since,
        GrantFullControl=grant_full_control,
        GrantRead=grant_read,
        GrantReadACP=grant_read_acp,
        GrantWriteACP=grant_write_acp,
        ServerSideEncryption=server_side_encryption,
        StorageClass=storage_class,
        SSECustomerAlgorithm=sse_customer_algorithm,
        SSECustomerKey=sse_customer_key,
        SSEKMSKeyId=sse_kms_key_id,
        SSEKMSEncryptionContext=sse_kms_encryption_context,
        BucketKeyEnabled=bucket_key_enabled,
        CopySourceSSECustomerAlgorithm=copy_source_sse_customer_algorithm,
        CopySourceSSECustomerKey=copy_source_sse_customer_key,
        RequestPayer=request_payer,
        ObjectLockMode=object_lock_mode,
        ObjectLockRetainUntilDate=object_lock_retain_until_datetime,
        ObjectLockLegalHoldStatus=object_lock_legal_hold_status,
        ExpectedBucketOwner=expected_bucket_owner,
        ExpectedSourceBucketOwner=expected_source_bucket_owner,
    )
    # to read the source object (it may be encrypted with SSE-C)
    head_kwargs = remove_optional(
        sse_customer_algorithm=copy_source_sse_customer_algorithm,
        sse_customer_key=copy_source_sse_customer_key,
        request_payer=request_payer,
        expected_bucket_owner=expected_source_bucket_owner,
    )
    return replace_kwargs, other_kwargs, head_kwargs

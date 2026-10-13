# -*- coding: utf-8 -*-

"""
Metadata related API.

**The metadata snapshot**

An ``S3Path`` can carry a snapshot of the metadata of the S3 object at its
path: the size, ETag, last modified time, version id, user metadata, ... of
**one object version, at one moment**. It comes from the API call that
produced the ``S3Path``, and the properties (``size``, ``etag``,
``last_modified_at``, ``version_id``, ``expire_at``, ``metadata``) read it:

- a full snapshot comes from ``head_object`` / ``get_object``
  (:meth:`~MetadataAPIMixin.head_object`, ``exists()``, ``read_bytes()``,
  or the first property read of a path without snapshot);
- a partial snapshot comes from a list or write API: ``iter_objects()``,
  ``iterdir()``, ``list_object_versions()``, ``list_buckets()``,
  ``write_bytes()``, ``delete()``, ... It only has the fields that API returns,
  e.g. a listed object has no user metadata and no version id.

Reading a property:

1. the field is in the snapshot: return it, no AWS call;
2. the snapshot is full, or is a delete marker: the object has no such field,
   return ``None`` (``version_id`` returns ``"null"``, the version id S3 gives
   an object written without versioning; ``size`` of a delete marker is
   ``0``), no AWS call;
3. the snapshot is partial: load the missing fields with ``head_object`` **of
   the same object version**, with the snapshot's ``VersionId`` if it has one,
   otherwise with ``IfMatch`` set to its ``ETag``. If the object changed since
   the snapshot (``IfMatch`` fails), raise ``S3ObjectChangedError``. The
   loaded fields are added, the existing ones are kept;
4. no snapshot: load the latest version with ``head_object``.

Loading a snapshot in steps 3 and 4 fills the cache of this ``S3Path``; it is
the only way the snapshot changes on its own. Methods that change S3
(``write_bytes``, ``copy_file``, ``delete``, ...) return a new ``S3Path`` with
the new snapshot and leave this one as it was. ``exists()`` and
``read_bytes()`` only fill an empty snapshot. Only
:meth:`~MetadataAPIMixin.head_object` (load the latest data) and
:meth:`~MetadataAPIMixin.clear_cache` replace the snapshot in place. A new
path built from this one (``joinpath``, ``parent``, ``change``, ``copy()``,
...) has no snapshot.

An ``S3Path`` produced by a call with an explicit client (``s3_client=...``)
remembers that client, and loads the missing fields (and ``head_object()``
without a client) with it. Otherwise, the client of ``s3_context`` at the time
of the call is used. Pickle does not keep the client (``copy.copy`` /
``copy.deepcopy`` do). ``response`` and ``metadata`` return a new ``dict`` on
every call.

**Design notes**

*One version at one moment.* Loading the missing fields of a listed object
from the latest version would mix the data of two objects. So they come from
the same version, and ``S3ObjectChangedError`` says when that is not possible.
An ``S3Path`` returned by ``list_object_versions()`` keeps describing its
version: its ``metadata`` is the metadata of that version.

*The snapshot never decides which version an operation works on.* Without
``version_id``, ``read_bytes()``, ``get_tags()``, ``delete()``, ... work on the
latest version, even for a path that describes an older one; pass
``version_id=p.version_id`` to work on that version. An implicit version would
make e.g. ``delete()`` permanently delete a listed version instead of adding a
delete marker.

*The remembered client is only for the snapshot.* So that a path listed with
the client of another AWS account is not loaded with the default client. Every
other method uses its ``s3_client`` argument, or else ``s3_context``, however
the path was made: a derived path (``parent``, ``/``, ``change``) has no
snapshot and no remembered client, so using it for operations would make the
same code call different accounts depending on where the path came from.

*Properties return copies,* so that changing the returned ``dict`` does not
change the snapshot.

*A listed key that* ``S3Path`` *cannot represent raises.* S3 allows keys with
consecutive ``/`` (``a//b``) or a leading ``/``, but ``S3Path`` joins and drops
them, so the path of ``a//b`` would be ``a/b``: another object, with the
snapshot of the first one, and ``delete()`` would delete the wrong object.
Listing such a key (or a folder prefix, with ``iterdir``) raises
``S3ValidationError``, which also stops the listing of the other keys. They
can be listed with ``better_client`` or boto3. Methods that copy or delete a
whole folder (``copy_dir``, ``move_to``, ``delete``) work on the keys S3
returns, not on paths, so they are not affected.
"""

from __future__ import annotations

import typing as T
import copy
from datetime import datetime

import botocore.exceptions

from .._arg import OPT
from .. import exc
from .. import utils
from ..constants import IS_DELETE_MARKER
from ..better_client.head_object import head_object
from ..aws import s3_context

from .resolve_s3_client import resolve_s3_client
from .filterable_property import FilterableProperty

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import HeadObjectOutputTypeDef, PutObjectOutputTypeDef


def _object_meta(dct: dict) -> dict:
    """
    The snapshot fields of a ``Contents`` item of ``list_objects_v2`` or a
    ``Versions`` item of ``list_object_versions``, under the names of a
    ``head_object`` response.
    """
    return {
        "Key": dct["Key"],
        "LastModified": dct["LastModified"],
        "ETag": dct["ETag"],
        "ContentLength": dct["Size"],
        "StorageClass": dct["StorageClass"],
        "ChecksumAlgorithm": dct.get("ChecksumAlgorithm", []),
        "Owner": dct.get("Owner", {}),
    }


class MetadataAPIMixin:
    """
    A mixin class that implements the metadata related methods, see the
    module docstring.
    """

    __slots__ = ()

    def _set_meta(
        self: S3Path,
        meta: dict,
        complete: bool,
        s3_client: S3Client | None,
    ) -> None:
        """
        Set the metadata snapshot, used by every API that produces an
        ``S3Path`` with metadata.

        :param meta: the response of the API, without ``ResponseMetadata``.
        :param complete: ``True`` for a ``head_object`` / ``get_object``
            response, ``False`` for a partial one.
        :param s3_client: the explicit client that made the call, ``None`` if
            it used ``s3_context``.
        """
        self._meta = meta
        self._meta_complete = complete
        self._s3_client = s3_client

    def _ensure_has_object(self: S3Path) -> None:
        """
        Make sure this path can be an S3 object (a file, or a folder marker
        object such as ``folder/``) before calling ``head_object``.

        :raises S3PathTypeError: for a relative path, the void path, or a
            bucket.
        """
        self.ensure_not_relpath()
        if self.is_bucket():
            raise exc.S3PathTypeError(
                f"{self._error_label()} is a bucket, not an object!"
            )

    def head_object(
        self: S3Path,
        version_id: str = OPT,
        s3_client: S3Client | None = None,
    ) -> dict:
        """
        Load the latest metadata of the object (or of ``version_id``) with
        ``head_object``, and replace the metadata snapshot of this ``S3Path``
        with it. See the module docstring.

        :param version_id: the version to load, default the latest one.
        :param s3_client: the boto3 S3 client to use. Default: the client that
            loaded the current snapshot, if any, otherwise ``s3_context``.

        :return: the ``head_object`` response.

        :raises S3PathTypeError: for a relative path, the void path, or a
            bucket.
        :raises S3FileNotExist: if the object (or the version) does not exist;
            the snapshot is cleared.
        :raises S3PermissionDenied: if S3 answers 403.
        """
        self._ensure_has_object()
        if s3_client is None:
            explicit_client = self._s3_client
        else:
            explicit_client = resolve_s3_client(s3_context, s3_client)
        if explicit_client is None:
            client = resolve_s3_client(s3_context, None)
        else:
            client = explicit_client
        try:
            response = head_object(
                client,
                self.bucket,
                self.key,
                version_id=version_id,
            )
        except exc.S3FileNotExist:
            self.clear_cache()
            raise
        # the snapshot gets its own copy: the nested Metadata dict is shared
        meta = copy.deepcopy(response)
        meta.pop("ResponseMetadata", None)
        self._set_meta(meta, complete=True, s3_client=explicit_client)
        return response

    def _load_meta(self: S3Path) -> None:
        """
        Load the metadata that the snapshot does not have yet (steps 3 and 4
        of the module docstring).
        """
        self._ensure_has_object()
        if self._s3_client is None:
            s3_client = resolve_s3_client(s3_context, None)
        else:
            s3_client = self._s3_client

        if self._meta is None:
            response = head_object(s3_client, self.bucket, self.key)
            meta = dict(response)
        else:
            if "VersionId" in self._meta:
                version_id = self._meta["VersionId"]
                if_match = OPT
            elif "ETag" in self._meta:
                version_id = OPT
                if_match = self._meta["ETag"]
            else:
                version_id = OPT
                if_match = OPT
            try:
                response = head_object(
                    s3_client,
                    self.bucket,
                    self.key,
                    version_id=version_id,
                    if_match=if_match,
                )
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "412":
                    # the ETag without quotes, as the etag property shows it
                    etag = self._meta["ETag"][1:-1]
                    raise exc.S3ObjectChangedError(
                        f"S3 object {self.uri!r} changed since its metadata "
                        f"was loaded (ETag {etag}), get a new S3Path to read "
                        f"the new object"
                    ) from e
                else:
                    raise
            # keep the fields of the snapshot, only add the missing ones
            meta = dict(response)
            meta.update(self._meta)
        meta.pop("ResponseMetadata", None)
        self._set_meta(meta, complete=True, s3_client=self._s3_client)

    def _get_meta_field(self: S3Path, key: str) -> T.Any:
        """
        Read a field of the metadata snapshot, loading it when needed. See the
        module docstring.

        :return: the value, or ``None`` if the object has no such field.
        """
        if self._meta is not None:
            if key in self._meta:
                return self._meta[key]
            if self._meta_complete or self.is_delete_marker():
                return None
        self._load_meta()
        return self._meta.get(key)

    @property
    def response(
        self: S3Path,
    ) -> HeadObjectOutputTypeDef | PutObjectOutputTypeDef | dict | None:
        """
        A copy of the metadata snapshot (see the module docstring): the
        response of the API that loaded it, without ``ResponseMetadata``, e.g.
        the response of ``head_object`` or ``put_object``. ``None`` if no
        metadata is loaded. It never calls AWS.
        """
        if self._meta is None:
            return None
        else:
            return copy.deepcopy(self._meta)

    @FilterableProperty
    def etag(self: S3Path) -> str | None:
        """
        The ETag of the object, without the surrounding quotes. For an object
        uploaded in one part (and not encrypted with SSE-KMS / SSE-C), it is
        the MD5 of the content; for a multipart upload, it is the MD5 of the
        MD5s of the parts, followed by ``-`` and the number of parts. ``None``
        for a delete marker.

        Ref: https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html
        """
        v = self._get_meta_field("ETag")
        if v is None:
            return v
        else:
            return v[1:-1]

    @FilterableProperty
    def last_modified_at(self: S3Path) -> datetime:
        """
        When the object (or this version of it) was written. For a bucket
        returned by ``list_buckets()``, the creation date of the bucket.

        Ref: https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html
        """
        return self._get_meta_field("LastModified")

    @FilterableProperty
    def size(self: S3Path) -> int:
        """
        The size of the object in bytes. ``0`` for a delete marker.

        Ref: https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html
        """
        if self.is_delete_marker():
            return 0
        return self._get_meta_field("ContentLength")

    @property
    def size_for_human(self: S3Path) -> str:
        """
        A human-readable string version of the size, e.g. ``"1.50 KB"``.
        """
        return utils.repr_data_size(self.size)

    @property
    def _static_version_id(self: S3Path) -> str | None:
        """
        The version id in the metadata snapshot, ``None`` if there is none.
        Unlike :attr:`version_id`, it never calls AWS.
        """
        if self._meta is None:
            return None
        else:
            return self._meta.get("VersionId", None)

    @FilterableProperty
    def version_id(self: S3Path) -> str:
        """
        The version id of the object (or of this version of it). ``"null"``
        for an object written while versioning was not enabled, the version
        id S3 gives it.

        Ref: https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html
        """
        v = self._get_meta_field("VersionId")
        if v is None:
            return "null"
        else:
            return v

    @FilterableProperty
    def expire_at(self: S3Path) -> datetime | None:
        """
        The ``Expires`` HTTP header of the object: the date after which a
        cached copy of the object is stale, set when the object is written
        (e.g. ``write_bytes(..., expires_datetime=...)``). ``None`` if not
        set. It is not the expiration date of an S3 lifecycle rule, which is
        in ``response["Expiration"]`` after a ``head_object``.

        Ref: https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html
        """
        return self._get_meta_field("Expires")

    @property
    def metadata(self: S3Path) -> dict[str, str] | None:
        """
        A copy of the user metadata of the object (``x-amz-meta-*``). S3
        stores the keys in lower case. ``None`` for a delete marker.

        Ref: https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html
        """
        if self.is_delete_marker():
            return None
        v = self._get_meta_field("Metadata")
        if v is None:
            return None
        else:
            return dict(v)

    def clear_cache(self: S3Path) -> None:
        """
        Remove the metadata snapshot. The next property read loads the latest
        metadata. The client that loaded the snapshot is kept.
        """
        self._meta = None
        self._meta_complete = False

    @classmethod
    def _from_listed_key(
        cls: type[S3Path],
        bucket: str,
        key: str,
    ) -> S3Path:
        """
        Construct the S3Path of a key (or a folder prefix) that S3 listed.

        :raises S3ValidationError: if the path would have another key.
        """
        p = cls(bucket, key)
        if p.key != key:
            raise exc.S3ValidationError(
                f"the S3 key {key!r} in bucket {bucket!r} cannot be "
                f"represented by S3Path, which joins consecutive '/' and drops "
                f"a leading '/' (its path would be {p.uri!r}, another object). "
                f"List this folder with s3pathlib.api.better_client or boto3 "
                f"instead"
            )
        return p

    @classmethod
    def _from_content_dict(
        cls: type[S3Path],
        bucket: str,
        dct: dict,
        s3_client: S3Client | None = None,
    ) -> S3Path:
        """
        Construct S3Path object from a ``Contents`` item of
        ``list_objects_v2``, with a partial metadata snapshot.

        :param s3_client: the explicit client of the list call, if any.
        """
        p = cls._from_listed_key(bucket, dct["Key"])
        p._set_meta(_object_meta(dct), complete=False, s3_client=s3_client)
        return p

    @classmethod
    def _from_version_dict(
        cls: type[S3Path],
        bucket: str,
        dct: dict,
        s3_client: S3Client | None = None,
    ) -> S3Path:
        """
        Construct S3Path object from a ``Versions`` item of
        ``list_object_versions``, with a partial metadata snapshot.

        :param s3_client: the explicit client of the list call, if any.
        """
        p = cls._from_listed_key(bucket, dct["Key"])
        meta = _object_meta(dct)
        meta["VersionId"] = dct["VersionId"]
        meta["IsLatest"] = dct["IsLatest"]
        p._set_meta(meta, complete=False, s3_client=s3_client)
        return p

    @classmethod
    def _from_delete_marker(
        cls: type[S3Path],
        bucket: str,
        dct: dict,
        s3_client: S3Client | None = None,
    ) -> S3Path:
        """
        Construct S3Path object from a ``DeleteMarkers`` item of
        ``list_object_versions``. A delete marker has no content, its
        properties never call AWS.

        :param s3_client: the explicit client of the list call, if any.
        """
        p = cls._from_listed_key(bucket, dct["Key"])
        p._set_meta(
            {
                "Key": dct["Key"],
                "VersionId": dct["VersionId"],
                "LastModified": dct["LastModified"],
                "IsLatest": dct["IsLatest"],
                "Owner": dct.get("Owner", {}),
                IS_DELETE_MARKER: True,
            },
            complete=False,
            s3_client=s3_client,
        )
        return p

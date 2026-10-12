# -*- coding: utf-8 -*-

"""
Test ``S3Path.copy_file``, ``copy_dir``, ``copy_to`` and ``move_to``.

Test order:

1. ``copy_file``: the copy and the returned path, versions, ``overwrite``,
   metadata / content headers / tags, the arguments, errors;
2. ``copy_dir``: every key (folder markers included), ``overwrite``,
   overlapping folders, invalid arguments;
3. ``copy_to``;
4. ``move_to``: files and folders, only the copied keys are deleted, unsafe
   targets;
5. paths that cannot be copied.
"""

import contextlib

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.exc import S3FileAlreadyExist
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.exc import S3PathIsNotFolderError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only

# copy_file argument -> (copy_object parameter, value), not needing the source
OTHER_ARGUMENTS = {
    "acl": ("ACL", "private"),
    "copy_source_if_match": ("CopySourceIfMatch", '"etag"'),
    "copy_source_if_none_match": ("CopySourceIfNoneMatch", '"other"'),
    "grant_full_control": ("GrantFullControl", "id=full"),
    "grant_read": ("GrantRead", "id=read"),
    "grant_read_acp": ("GrantReadACP", "id=read-acp"),
    "grant_write_acp": ("GrantWriteACP", "id=write-acp"),
    "server_side_encryption": ("ServerSideEncryption", "aws:kms"),
    "storage_class": ("StorageClass", "STANDARD_IA"),
    "sse_customer_algorithm": ("SSECustomerAlgorithm", "AES256"),
    "sse_customer_key": ("SSECustomerKey", "key"),
    "sse_kms_key_id": ("SSEKMSKeyId", "key-id"),
    "sse_kms_encryption_context": ("SSEKMSEncryptionContext", "context"),
    "bucket_key_enabled": ("BucketKeyEnabled", True),
    "request_payer": ("RequestPayer", "requester"),
    "object_lock_mode": ("ObjectLockMode", "GOVERNANCE"),
    "object_lock_legal_hold_status": ("ObjectLockLegalHoldStatus", "OFF"),
    "expected_bucket_owner": ("ExpectedBucketOwner", "111122223333"),
}

# copy_file argument -> copy_object parameter, applied with REPLACE
REPLACE_ARGUMENTS = {
    "cache_control": ("CacheControl", "no-cache"),
    "content_disposition": ("ContentDisposition", "inline"),
    "content_encoding": ("ContentEncoding", "identity"),
    "content_language": ("ContentLanguage", "en"),
    "content_type": ("ContentType", "text/plain"),
    "website_redirect_location": ("WebsiteRedirectLocation", "/other"),
}


class Captured(Exception):
    """
    Raised to stop an API call once its parameters are recorded.
    """


@contextlib.contextmanager
def capture_params(s3_client, operation: str):
    """
    Record the parameters of the first ``operation`` call made through
    ``s3_client`` and stop it with ``Captured``: no request is sent.
    """
    captured = dict()

    def record(params: dict, **kwargs):
        captured.update(params)
        raise Captured

    events = s3_client.meta.events
    events.register(f"provide-client-params.s3.{operation}", record)
    try:
        yield captured
    finally:
        events.unregister(f"provide-client-params.s3.{operation}", record)


class CopyMixin(BaseTest):
    module = "core.copy"

    def put(self, p: S3Path, body: bytes = b"hello", **kwargs) -> str | None:
        res = self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=body, **kwargs)
        return res.get("VersionId")

    def get(self, p: S3Path) -> bytes:
        return self.s3_client.get_object(Bucket=p.bucket, Key=p.key)["Body"].read()

    def head(self, p: S3Path) -> dict:
        return self.s3_client.head_object(Bucket=p.bucket, Key=p.key)

    def keys(self, s3dir: S3Path) -> list[str]:
        res = self.s3_client.list_objects_v2(Bucket=s3dir.bucket, Prefix=s3dir.key)
        return sorted(dct["Key"][len(s3dir.key):] for dct in res.get("Contents", []))

    def tags(self, p: S3Path) -> dict:
        res = self.s3_client.get_object_tagging(Bucket=p.bucket, Key=p.key)
        return {tag["Key"]: tag["Value"] for tag in res["TagSet"]}

    def make_dir(self, s3dir: S3Path):
        """
        A folder with its marker, an empty sub folder (marker only), a file,
        a nested file and an object ``data/`` with content.
        """
        self.put(s3dir, b"")
        self.put(s3dir / "empty/", b"")
        self.put(s3dir / "a.txt", b"a")
        self.put(s3dir / "sub/b.txt", b"b")
        self.put(s3dir / "data/", b"content")

    # --------------------------------------------------------------------------
    # 1. copy_file
    # --------------------------------------------------------------------------
    def test_copy_file(self):
        """
        The content is copied; it returns a new path of the copy with the
        snapshot of the response, and changes neither path.
        """
        src = self.s3dir_test / "src.txt"
        dst = self.s3dir_test / "dst.txt"
        self.put(src)
        new = src.copy_file(dst)
        assert self.get(dst) == b"hello"
        assert new == dst
        assert new is not dst
        assert src.response is None
        assert dst.response is None
        with record_api_calls(self.s3_client) as calls:
            assert new.etag == self.head(dst)["ETag"][1:-1]
        assert calls == ["HeadObject"]

    def test_copy_file_versions(self):
        """
        ``version_id`` copies that version; the copy's version id is in the
        snapshot.
        """
        src = self.s3dir_test_with_versioning / "src.txt"
        dst = self.s3dir_test_with_versioning / "dst.txt"
        v1 = self.put(src, b"v1")
        self.put(src, b"v2")
        new = src.copy_file(dst, version_id=v1)
        assert self.get(dst) == b"v1"
        assert new._static_version_id == self.head(dst)["VersionId"]

    def test_copy_file_existing(self):
        p = self.s3dir_test / "dst.txt"
        self.put(self.s3dir_test / "src.txt", b"new")
        self.put(p, b"old")
        with pytest.raises(S3FileAlreadyExist, match="already exist"):
            (self.s3dir_test / "src.txt").copy_file(p)
        assert self.get(p) == b"old"
        (self.s3dir_test / "src.txt").copy_file(p, overwrite=True)
        assert self.get(p) == b"new"

    def test_copy_file_conditional(self):
        """
        With ``overwrite=False``, the copy is conditional: if the target is
        written after the check, S3 answers ``PreconditionFailed``, raised as
        ``S3FileAlreadyExist``.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        stubber.add_client_error("head_object", service_error_code="404", http_status_code=404)
        stubber.add_client_error(
            "copy_object",
            service_error_code="PreconditionFailed",
            http_status_code=412,
            expected_params={
                "Bucket": "bucket",
                "Key": "dst.txt",
                "CopySource": {"Bucket": "bucket", "Key": "src.txt"},
                "IfNoneMatch": "*",
            },
        )
        s3_context.attach_s3_client(s3_client)
        try:
            with stubber:
                with pytest.raises(S3FileAlreadyExist, match="dst.txt") as exc_info:
                    S3Path("bucket", "src.txt").copy_file(S3Path("bucket", "dst.txt"))
        finally:
            s3_context.attach_s3_client(self.s3_client)
        assert isinstance(exc_info.value.__cause__, botocore.exceptions.ClientError)
        stubber.assert_no_pending_responses()

    @real_aws_only("moto ignores IfNoneMatch on copy_object and replaces the object")
    def test_copy_file_conditional_on_aws(self, monkeypatch):
        """
        A target written after the existence check is not replaced.
        """
        src = self.s3dir_test / "src.txt"
        dst = self.s3dir_test / "dst.txt"
        self.put(src, b"new")
        self.put(dst, b"old")
        monkeypatch.setattr(S3Path, "exists", lambda self, **kwargs: False)
        with pytest.raises(S3FileAlreadyExist):
            src.copy_file(dst)
        assert self.get(dst) == b"old"

    def test_copy_file_keeps_headers_and_metadata(self):
        """
        By default the copy keeps the content headers, the user metadata and
        the tags of the source, with one call.
        """
        src = self.s3dir_test / "src.txt"
        dst = self.s3dir_test / "dst.txt"
        self.put(src, ContentType="text/csv", CacheControl="max-age=1", Metadata={"m": "1"}, Tagging="t=1")
        with record_api_calls(self.s3_client) as calls:
            src.copy_file(dst, overwrite=True)
        assert calls == ["CopyObject"]
        res = self.head(dst)
        assert res["ContentType"] == "text/csv"
        assert res["CacheControl"] == "max-age=1"
        assert res["Metadata"] == {"m": "1"}
        assert self.tags(dst) == {"t": "1"}

    def test_copy_file_content_type_only(self):
        """
        Only the given content header changes, the rest is kept; it works
        without ``metadata``.
        """
        src = self.s3dir_test / "src.txt"
        dst = self.s3dir_test / "dst.txt"
        self.put(src, ContentType="text/csv", CacheControl="max-age=1", Metadata={"m": "1"})
        with record_api_calls(self.s3_client) as calls:
            src.copy_file(dst, content_type="text/plain", overwrite=True)
        assert calls == ["HeadObject", "CopyObject"]
        res = self.head(dst)
        assert res["ContentType"] == "text/plain"
        assert res["CacheControl"] == "max-age=1"
        assert res["Metadata"] == {"m": "1"}

    def test_copy_file_metadata_only(self):
        """
        Only the user metadata changes, ``ContentType`` is not reset to
        ``binary/octet-stream``. The snapshot has the metadata as S3 stores
        it.
        """
        src = self.s3dir_test / "src.txt"
        dst = self.s3dir_test / "dst.txt"
        self.put(src, ContentType="text/csv", Metadata={"m": "1"})
        new = src.copy_file(dst, metadata={"N": "2"})
        res = self.head(dst)
        assert res["ContentType"] == "text/csv"
        assert res["Metadata"] == {"n": "2"}
        with record_api_calls(self.s3_client) as calls:
            assert new.metadata == {"n": "2"}
        assert calls == []

    def test_copy_file_tags(self):
        src = self.s3dir_test / "src.txt"
        dst = self.s3dir_test / "dst.txt"
        self.put(src, Tagging="t=1")
        src.copy_file(dst, tags={"new": "a b"})
        assert self.tags(dst) == {"new": "a b"}

    def test_copy_file_to_itself(self):
        """
        Copying an object to itself with new metadata changes its metadata in
        place.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, Metadata={"m": "1"})
        p.copy_file(p, metadata={"m": "2"}, overwrite=True)
        assert self.head(p)["Metadata"] == {"m": "2"}
        assert self.get(p) == b"hello"

    def test_copy_file_arguments_passed_to_boto3(self):
        """
        Every argument is sent to copy_object under its boto3 name.
        """
        src = self.s3dir_test / "src.txt"
        self.put(src)
        kwargs = dict()
        for name, (_, value) in {**OTHER_ARGUMENTS, **REPLACE_ARGUMENTS}.items():
            kwargs[name] = value
        with capture_params(self.s3_client, "CopyObject") as params:
            with pytest.raises(Captured):
                src.copy_file(self.s3dir_test / "dst.txt", overwrite=True, **kwargs)
        for param, value in {**OTHER_ARGUMENTS, **REPLACE_ARGUMENTS}.values():
            assert params[param] == value, param
        assert params["MetadataDirective"] == "REPLACE"
        assert params["Metadata"] == {}
        assert "IfNoneMatch" not in params

    @pytest.mark.parametrize(
        "method, kind",
        [
            pytest.param("copy_dir", "dir", id="copy_dir"),
            pytest.param("copy_to", "dir", id="copy_to-dir"),
            pytest.param("copy_to", "file", id="copy_to-file"),
            pytest.param("move_to", "dir", id="move_to-dir"),
            pytest.param("move_to", "file", id="move_to-file"),
        ],
    )
    def test_arguments_reach_copy_object(self, method, kind):
        """
        Every argument of ``copy_dir``, ``copy_to`` and ``move_to`` is passed
        on to copy_object like the ones of ``copy_file``: a forwarding line
        that is forgotten would silently drop the argument.
        """
        arguments = {**OTHER_ARGUMENTS, **REPLACE_ARGUMENTS}
        if kind == "dir":
            # a folder rejects the copy_source_if_* conditions, see below
            arguments = {
                name: item
                for name, item in arguments.items()
                if not name.startswith("copy_source_if_")
            }
            src = self.s3dir_test / "src/"
            self.put(src / "a.txt")
            dst = self.s3dir_test / "dst/"
        else:
            src = self.s3dir_test / "src.txt"
            self.put(src)
            dst = self.s3dir_test / "dst.txt"
        kwargs = {name: value for name, (_, value) in arguments.items()}
        with capture_params(self.s3_client, "CopyObject") as params:
            with pytest.raises(Captured):
                getattr(src, method)(dst, overwrite=True, **kwargs)
        for param, value in arguments.values():
            assert params[param] == value, param

    @pytest.mark.parametrize("kind", ["file", "dir"])
    def test_move_to_delete_gets_request_payer(self, kind):
        """
        The delete of the source gets ``request_payer`` too, for a file
        (``DeleteObject``) as for a folder (``DeleteObjects``).
        """
        if kind == "file":
            src = self.s3dir_test / "src.txt"
            self.put(src)
            dst = self.s3dir_test / "dst.txt"
            operation = "DeleteObject"
        else:
            src = self.s3dir_test / "src/"
            self.put(src / "a.txt")
            dst = self.s3dir_test / "dst/"
            operation = "DeleteObjects"
        with capture_params(self.s3_client, operation) as params:
            with pytest.raises(Captured):
                src.move_to(dst, request_payer="requester")
        assert params["RequestPayer"] == "requester"

    def test_copy_file_source_arguments(self):
        """
        The arguments to read the source are also used by the ``head_object``
        that reads its headers.
        """
        src = self.s3dir_test / "src.txt"
        with capture_params(self.s3_client, "HeadObject") as params:
            with pytest.raises(Captured):
                src.copy_file(
                    self.s3dir_test / "dst.txt",
                    version_id="v1",
                    overwrite=True,
                    content_type="text/plain",
                    copy_source_sse_customer_algorithm="AES256",
                    copy_source_sse_customer_key="key",
                    request_payer="requester",
                    expected_source_bucket_owner="111122223333",
                )
        assert params["Key"] == src.key
        assert params["VersionId"] == "v1"
        assert params["SSECustomerAlgorithm"] == "AES256"
        assert params["SSECustomerKey"] == "key"
        assert params["RequestPayer"] == "requester"
        assert params["ExpectedBucketOwner"] == "111122223333"

    def test_copy_file_missing_source(self):
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            (self.s3dir_test / "missing.txt").copy_file(self.s3dir_test / "dst.txt")
        assert exc_info.value.response["Error"]["Code"] == "NoSuchKey"

    # --------------------------------------------------------------------------
    # 2. copy_dir
    # --------------------------------------------------------------------------
    def test_copy_dir(self):
        """
        Every key is copied, folder markers included, so empty folders and an
        object ``data/`` with content are kept.
        """
        src = self.s3dir_test / "src/"
        dst = self.s3dir_test / "dst/"
        self.make_dir(src)
        assert src.copy_dir(dst) == 5
        assert self.keys(dst) == ["", "a.txt", "data/", "empty/", "sub/b.txt"]
        assert self.get(dst / "data/") == b"content"
        assert self.keys(src) == ["", "a.txt", "data/", "empty/", "sub/b.txt"]

    def test_copy_dir_existing(self):
        """
        With ``overwrite=False``, nothing is copied if any target key exists.
        """
        src = self.s3dir_test / "src/"
        dst = self.s3dir_test / "dst/"
        self.make_dir(src)
        self.put(dst / "sub/b.txt", b"old")
        with pytest.raises(S3FileAlreadyExist, match="sub/b.txt"):
            src.copy_dir(dst)
        assert self.keys(dst) == ["sub/b.txt"]
        assert src.copy_dir(dst, overwrite=True) == 5
        assert self.get(dst / "sub/b.txt") == b"b"

    def test_copy_dir_metadata(self):
        """
        The arguments apply to every object.
        """
        src = self.s3dir_test / "src/"
        dst = self.s3dir_test / "dst/"
        self.put(src / "a.txt", ContentType="text/csv")
        self.put(src / "b.txt", ContentType="text/csv")
        src.copy_dir(dst, metadata={"k": "v"})
        for name in ["a.txt", "b.txt"]:
            res = self.head(dst / name)
            assert res["Metadata"] == {"k": "v"}
            assert res["ContentType"] == "text/csv"

    def test_copy_dir_other_bucket(self):
        """
        The same folder in another bucket does not overlap.
        """
        src = self.s3dir_test / "src/"
        dst = S3Path(self.bucket_with_versioning, src.key)
        self.put(src / "a.txt")
        assert src.copy_dir(dst) == 1
        assert self.get(dst / "a.txt") == b"hello"

    @pytest.mark.parametrize(
        "src_name, dst_name",
        [
            pytest.param("a/", "a/", id="same"),
            pytest.param("a/", "a/b/", id="dst-inside"),
            pytest.param("a/b/", "a/", id="src-inside"),
        ],
    )
    @pytest.mark.parametrize("method", ["copy_dir", "move_to"])
    def test_overlap(self, method, src_name, dst_name):
        """
        Overlapping folders raise before any AWS call: a source object could
        be overwritten before it is copied, and a move would delete the copies
        (all the data of ``move_to("a/" -> "a/b/")``).
        """
        src = self.s3dir_test / src_name
        dst = self.s3dir_test / dst_name
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match="overlap"):
                getattr(src, method)(dst, overwrite=True)
        assert calls == []

    @pytest.mark.parametrize(
        "name",
        [
            "copy_source_if_match",
            "copy_source_if_modified_since",
            "copy_source_if_none_match",
            "copy_source_if_unmodified_since",
        ],
    )
    def test_copy_dir_source_conditions(self, name):
        """
        A condition on the source would apply to every object.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match="only applies to copying a file"):
                (self.s3dir_test / "src/").copy_dir(self.s3dir_test / "dst/", **{name: "x"})
        assert calls == []

    # --------------------------------------------------------------------------
    # 3. copy_to
    # --------------------------------------------------------------------------
    def test_copy_to(self):
        self.put(self.s3dir_test / "a.txt")
        self.make_dir(self.s3dir_test / "src/")
        assert (self.s3dir_test / "a.txt").copy_to(self.s3dir_test / "b.txt") == 1
        assert self.get(self.s3dir_test / "b.txt") == b"hello"
        assert (self.s3dir_test / "src/").copy_to(self.s3dir_test / "dst/") == 5

    def test_copy_to_folder_version_id(self):
        """
        ``version_id`` is not ignored for a folder.
        """
        with pytest.raises(ValueError, match="version_id only applies to copying a file"):
            (self.s3dir_test / "src/").copy_to(self.s3dir_test / "dst/", version_id="v1")

    # --------------------------------------------------------------------------
    # 4. move_to
    # --------------------------------------------------------------------------
    def test_move_file(self):
        src = self.s3dir_test / "src.txt"
        dst = self.s3dir_test / "dst.txt"
        self.put(src)
        assert src.move_to(dst) == 1
        assert self.keys(self.s3dir_test) == ["dst.txt"]
        assert self.get(dst) == b"hello"

    def test_move_file_to_itself(self):
        """
        Copying the object onto itself and then deleting it would lose the
        data, so it raises before any AWS call.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p)
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match="to itself"):
                p.move_to(p, metadata={"a": "b"}, overwrite=True)
        assert calls == []
        assert self.get(p) == b"hello"

    def test_move_file_existing(self):
        """
        If the copy fails, nothing is deleted.
        """
        src = self.s3dir_test / "src.txt"
        dst = self.s3dir_test / "dst.txt"
        self.put(src, b"new")
        self.put(dst, b"old")
        with pytest.raises(S3FileAlreadyExist):
            src.move_to(dst)
        assert self.get(src) == b"new"
        assert self.get(dst) == b"old"

    def test_move_dir(self):
        src = self.s3dir_test / "src/"
        dst = self.s3dir_test / "dst/"
        self.make_dir(src)
        assert src.move_to(dst) == 5
        assert self.keys(src) == []
        assert self.keys(dst) == ["", "a.txt", "data/", "empty/", "sub/b.txt"]

    def test_move_dir_only_copied_keys(self):
        """
        An object written to the source while the move copies is neither
        copied nor deleted: the source is not listed again to delete it.
        """
        src = self.s3dir_test / "src/"
        dst = self.s3dir_test / "dst/"
        self.put(src / "a.txt")
        late = src / "late.txt"

        def write_late(**kwargs):
            if late.key not in [dct["Key"] for dct in self.s3_client.list_objects_v2(
                Bucket=src.bucket, Prefix=late.key
            ).get("Contents", [])]:
                self.put(late, b"late")

        events = self.s3_client.meta.events
        events.register("after-call.s3.CopyObject", write_late)
        try:
            assert src.move_to(dst) == 1
        finally:
            events.unregister("after-call.s3.CopyObject", write_late)
        assert self.keys(src) == ["late.txt"]
        assert self.keys(dst) == ["a.txt"]

    def test_move_dir_with_versioning(self):
        """
        Moving adds delete markers, the old versions are kept.
        """
        src = self.s3dir_test_with_versioning / "src/"
        dst = self.s3dir_test_with_versioning / "dst/"
        self.put(src / "a.txt")
        src.move_to(dst)
        assert self.keys(src) == []
        res = self.s3_client.list_object_versions(Bucket=src.bucket, Prefix=src.key)
        assert len(res["Versions"]) == 1
        assert len(res["DeleteMarkers"]) == 1

    # --------------------------------------------------------------------------
    # 5. Invalid paths
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "src, dst, error, match",
        [
            pytest.param(S3Path(), "dst.txt", S3PathTypeError, "is a relative path", id="src-void"),
            pytest.param(S3Path.make_relpath("a.txt"), "dst.txt", S3PathTypeError, "is a relative path", id="src-relpath"),
            pytest.param("src/", "dst.txt", S3PathIsNotFileError, "is not a file", id="src-dir"),
            pytest.param("src.txt", S3Path.make_relpath("a.txt"), S3PathTypeError, "is a relative path", id="dst-relpath"),
            pytest.param("src.txt", "dst/", S3PathIsNotFileError, "is not a file", id="dst-dir"),
        ],
    )
    def test_copy_file_wrong_path(self, src, dst, error, match):
        if isinstance(src, str):
            src = self.s3dir_test / src
        if isinstance(dst, str):
            dst = self.s3dir_test / dst
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error, match=match):
                src.copy_file(dst)
        assert calls == []

    @pytest.mark.parametrize(
        "src, dst, error, match",
        [
            pytest.param(S3Path.make_relpath("a/"), "dst/", S3PathTypeError, "is a relative path", id="src-relpath"),
            pytest.param("src.txt", "dst/", S3PathIsNotFolderError, "is not a dir", id="src-file"),
            pytest.param("src/", S3Path(), S3PathTypeError, "is a relative path", id="dst-void"),
            pytest.param("src/", "dst.txt", S3PathIsNotFolderError, "is not a dir", id="dst-file"),
        ],
    )
    def test_copy_dir_wrong_path(self, src, dst, error, match):
        if isinstance(src, str):
            src = self.s3dir_test / src
        if isinstance(dst, str):
            dst = self.s3dir_test / dst
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error, match=match):
                src.copy_dir(dst)
        assert calls == []

    @pytest.mark.parametrize("method", ["copy_to", "move_to"])
    def test_copy_to_move_to_void(self, method):
        """
        The void path raises ``S3PathTypeError``, not a bare ``TypeError``.
        """
        with pytest.raises(S3PathTypeError, match="is a relative path"):
            getattr(S3Path(), method)(self.s3dir_test / "dst.txt")
        with pytest.raises(S3PathTypeError, match="is a relative path"):
            getattr(self.s3dir_test / "src.txt", method)(S3Path())


class TestMock(CopyMixin):
    use_mock = True


class TestRealAws(CopyMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.copy",
        preview=False,
    )

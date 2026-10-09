# -*- coding: utf-8 -*-

"""
Test the read and write methods of ``S3Path`` (``s3pathlib.core.rw``).

Test order:

1. ``read_bytes`` / ``read_text``: content, versions, folder markers, errors,
   the arguments;
2. ``write_bytes`` / ``write_text``: content, the returned path and its
   metadata snapshot, conditional writes, the arguments;
3. ``touch``;
4. ``mkdir``;
5. paths that cannot be read or written.

How ``read_bytes`` fills the metadata snapshot is tested in
``tests/core/test_core_metadata.py``.
"""

import contextlib
import hashlib
import io
import uuid

import botocore.exceptions
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.exc import S3FileAlreadyExist
from s3pathlib.exc import S3FolderAlreadyExist
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.exc import S3PathIsNotFolderError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import delete_s3_prefix

# every argument of write_bytes / write_text that maps to put_object, with a
# value, and the put_object parameter it becomes
PUT_ARGUMENTS = {
    "metadata": ("Metadata", {"k": "v"}),
    "tags": ("Tagging", {"t": "a b"}),
    "acl": ("ACL", "private"),
    "cache_control": ("CacheControl", "no-cache"),
    "content_disposition": ("ContentDisposition", "inline"),
    "content_encoding": ("ContentEncoding", "gzip"),
    "content_language": ("ContentLanguage", "en"),
    "content_length": ("ContentLength", 5),
    "content_md5": ("ContentMD5", "md5"),
    "content_type": ("ContentType", "text/plain"),
    "checksum_algorithm": ("ChecksumAlgorithm", "SHA256"),
    "checksum_crc32": ("ChecksumCRC32", "crc32"),
    "checksum_crc32c": ("ChecksumCRC32C", "crc32c"),
    "checksum_sha1": ("ChecksumSHA1", "sha1"),
    "checksum_sha256": ("ChecksumSHA256", "sha256"),
    "grant_full_control": ("GrantFullControl", "id=full"),
    "grant_read": ("GrantRead", "id=read"),
    "grant_read_acp": ("GrantReadACP", "id=read-acp"),
    "grant_write_acp": ("GrantWriteACP", "id=write-acp"),
    "server_side_encryption": ("ServerSideEncryption", "aws:kms"),
    "storage_class": ("StorageClass", "STANDARD_IA"),
    "website_redirect_location": ("WebsiteRedirectLocation", "/other"),
    "sse_kms_key_id": ("SSEKMSKeyId", "key-id"),
    "sse_kms_encryption_context": ("SSEKMSEncryptionContext", "context"),
    "bucket_key_enabled": ("BucketKeyEnabled", True),
    "request_payer": ("RequestPayer", "requester"),
    "object_lock_mode": ("ObjectLockMode", "GOVERNANCE"),
    "object_lock_legal_hold_status": ("ObjectLockLegalHoldStatus", "OFF"),
    "expected_bucket_owner": ("ExpectedBucketOwner", "111122223333"),
    "if_match": ("IfMatch", '"etag"'),
    "if_none_match": ("IfNoneMatch", "*"),
}

# every argument of read_bytes / read_text that maps to get_object
GET_ARGUMENTS = {
    "version_id": ("VersionId", "v1"),
    "if_match": ("IfMatch", '"etag"'),
    "if_none_match": ("IfNoneMatch", '"other"'),
    "range": ("Range", "bytes=0-1"),
    "response_cache_control": ("ResponseCacheControl", "no-cache"),
    "response_content_disposition": ("ResponseContentDisposition", "inline"),
    "response_content_encoding": ("ResponseContentEncoding", "gzip"),
    "response_content_language": ("ResponseContentLanguage", "en"),
    "response_content_type": ("ResponseContentType", "text/plain"),
    "request_payer": ("RequestPayer", "requester"),
    "part_number": ("PartNumber", 1),
    "expected_bucket_owner": ("ExpectedBucketOwner", "111122223333"),
    "checksum_mode": ("ChecksumMode", "ENABLED"),
}


def error_code(exc_info) -> str:
    return exc_info.value.response["Error"]["Code"]


class ReadAndWriteMixin(BaseTest):
    module = "core.rw"

    def put(self, p: S3Path, body: bytes = b"hello") -> str | None:
        """
        Write an object with the native client.

        :return: the version id (``None`` without versioning)
        """
        res = self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=body)
        return res.get("VersionId")

    def get(self, p: S3Path) -> bytes:
        return self.s3_client.get_object(Bucket=p.bucket, Key=p.key)["Body"].read()

    @contextlib.contextmanager
    def stub(self):
        """
        A ``Stubber`` on a new client, used by ``S3Path`` methods inside the
        block. Every expected response must be consumed.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        s3_context.attach_s3_client(s3_client)
        try:
            with stubber:
                yield stubber
        finally:
            s3_context.attach_s3_client(self.s3_client)
        stubber.assert_no_pending_responses()

    @pytest.fixture
    def tmp_bucket(self):
        """
        A new empty bucket, emptied and deleted after the test.
        """
        bucket = f"s3pathlib-test-tmp-{uuid.uuid4().hex}"
        self.s3_client.create_bucket(Bucket=bucket)
        yield bucket
        delete_s3_prefix(self.s3_client, bucket, "")
        self.s3_client.delete_bucket(Bucket=bucket)

    # --------------------------------------------------------------------------
    # 1. read_bytes / read_text
    # --------------------------------------------------------------------------
    def test_read_bytes(self):
        p = self.s3dir_test / "file.txt"
        self.put(p, b"\x00\xffhello")
        assert p.read_bytes() == b"\x00\xffhello"

    def test_read_text_encoding(self):
        p = self.s3dir_test / "file.txt"
        self.put(p, "你好".encode("utf-16"))
        assert p.read_text(encoding="utf-16") == "你好"
        assert p.read_text(errors="replace") != "你好"

    def test_read_version(self):
        """
        Without ``version_id``, the latest version is read.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p, b"v1")
        self.put(p, b"v2")
        assert p.read_text() == "v2"
        assert p.read_text(version_id=v1) == "v1"

    def test_read_folder_marker(self):
        """
        A folder marker object is an object; it can be read.
        """
        p = self.s3dir_test / "folder/"
        self.put(p, b"")
        assert p.read_bytes() == b""

    @pytest.mark.parametrize(
        "kwargs, code",
        [
            pytest.param({}, "NoSuchKey", id="missing"),
            pytest.param({"if_match": '"other"'}, "PreconditionFailed", id="if-match"),
        ],
    )
    def test_read_error_raised_as_is(self, kwargs, code):
        p = self.s3dir_test / "file.txt"
        if code != "NoSuchKey":
            self.put(p)
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.read_bytes(**kwargs)
        assert error_code(exc_info) == code

    def test_read_not_modified(self):
        """
        ``if_none_match`` with the current ETag: S3 answers 304, raised as is.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"hello")
        etag = f'"{hashlib.md5(b"hello").hexdigest()}"'
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.read_bytes(if_none_match=etag)
        assert error_code(exc_info) == "304"

    @pytest.mark.parametrize("method", ["read_bytes", "read_text"])
    def test_read_arguments_passed_to_boto3(self, method):
        """
        Every argument is sent to get_object under its boto3 name.
        """
        kwargs = {name: value for name, (_, value) in GET_ARGUMENTS.items()}
        expected = {"Bucket": "bucket", "Key": "file.txt"}
        for param, value in GET_ARGUMENTS.values():
            expected[param] = value
        with self.stub() as stubber:
            stubber.add_response(
                "get_object",
                {"Body": StreamingBody(io.BytesIO(b"he"), 2)},
                expected_params=expected,
            )
            data = getattr(S3Path("bucket", "file.txt"), method)(**kwargs)
        assert data in (b"he", "he")

    def test_read_none_is_not_omitted(self):
        """
        ``None`` is not "not given": botocore rejects it before sending the
        request, instead of reading the latest version.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p)
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(botocore.exceptions.ParamValidationError, match="VersionId"):
                p.read_bytes(version_id=None)
        assert calls == []

    # --------------------------------------------------------------------------
    # 2. write_bytes / write_text
    # --------------------------------------------------------------------------
    def test_write_returns_new_path(self):
        """
        Writing returns a new path with the snapshot of the written object;
        this path is not changed.
        """
        p = self.s3dir_test / "file.txt"
        new = p.write_bytes(b"hello")
        assert self.get(p) == b"hello"
        assert new == p
        assert new is not p
        assert p.response is None
        with record_api_calls(self.s3_client) as calls:
            assert new.size == 5
            assert new.etag == hashlib.md5(b"hello").hexdigest()
        assert calls == []

    def test_write_metadata_snapshot(self):
        """
        The snapshot has the user metadata as S3 stores it (keys in lower
        case, 2.x kept the given case), and ``{}`` when none is given, without
        any more call.
        """
        p = self.s3dir_test / "file.txt"
        with pytest.warns(UserWarning):
            new = p.write_text("x", metadata={"Creator": "Me"})
        head = self.s3_client.head_object(Bucket=p.bucket, Key=p.key)
        with record_api_calls(self.s3_client) as calls:
            assert new.metadata == head["Metadata"] == {"creator": "Me"}
            assert p.write_text("y").metadata == {}
        assert calls == ["PutObject"]

    def test_write_version(self):
        p = self.s3dir_test_with_versioning / "file.txt"
        new = p.write_text("hello")
        res = self.s3_client.head_object(Bucket=p.bucket, Key=p.key)
        assert new.version_id == res["VersionId"]

    def test_write_tags(self):
        """
        Tags with spaces are read back as they are.
        """
        p = self.s3dir_test / "file.txt"
        p.write_text("x", tags={"team": "data eng", "k": "a+b"})
        res = self.s3_client.get_object_tagging(Bucket=p.bucket, Key=p.key)
        tags = {tag["Key"]: tag["Value"] for tag in res["TagSet"]}
        assert tags == {"team": "data eng", "k": "a+b"}

    def test_write_text_encoding(self):
        p = self.s3dir_test / "file.txt"
        new = p.write_text("你好", encoding="utf-16")
        assert self.get(p) == "你好".encode("utf-16")
        assert new.size == len("你好".encode("utf-16"))

    def test_write_if_none_match(self):
        """
        ``if_none_match="*"`` writes a new object, but does not replace an
        existing one (``PreconditionFailed``, raised as is).
        """
        p = self.s3dir_test / "file.txt"
        p.write_text("first", if_none_match="*")
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.write_text("second", if_none_match="*")
        assert error_code(exc_info) == "PreconditionFailed"
        assert self.get(p) == b"first"

    def test_write_if_match(self):
        """
        ``if_match`` only replaces the object if it still has that ETag.
        """
        p = self.s3dir_test / "file.txt"
        etag = f'"{p.write_text("v1").etag}"'
        p.write_text("v2", if_match=etag)
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.write_text("v3", if_match=etag)
        assert error_code(exc_info) == "PreconditionFailed"
        assert self.get(p) == b"v2"

    @pytest.mark.parametrize("method", ["write_bytes", "write_text"])
    def test_write_arguments_passed_to_boto3(self, method):
        """
        Every argument is sent to put_object under its boto3 name; tags are
        URL encoded with ``%20`` for spaces.
        """
        kwargs = {name: value for name, (_, value) in PUT_ARGUMENTS.items()}
        expected = {"Bucket": "bucket", "Key": "file.txt", "Body": b"hello"}
        for param, value in PUT_ARGUMENTS.values():
            expected[param] = value
        expected["Tagging"] = "t=a%20b"
        if method == "write_bytes":
            data = b"hello"
        else:
            data = "hello"
        with self.stub() as stubber:
            stubber.add_response("put_object", {"ETag": '"e"'}, expected_params=expected)
            getattr(S3Path("bucket", "file.txt"), method)(data, **kwargs)

    @pytest.mark.parametrize(
        "kwargs, error, match",
        [
            pytest.param(
                {"if_match": None},
                botocore.exceptions.ParamValidationError,
                "IfMatch",
                id="if_match",
            ),
            # tags and metadata are encoded before the boto3 call, which fails
            pytest.param({"tags": None}, TypeError, None, id="tags"),
            pytest.param({"metadata": None}, AttributeError, None, id="metadata"),
        ],
    )
    def test_write_none_is_not_omitted(self, kwargs, error, match):
        """
        ``None`` is not "not given": the write fails before calling AWS. If it
        were "not given", ``if_match=p.etag`` with no ETag would silently
        drop the condition and overwrite the object.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"v1")
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error, match=match):
                p.write_bytes(b"v2", **kwargs)
        assert calls == []
        assert self.get(p) == b"v1"

    # --------------------------------------------------------------------------
    # 3. touch
    # --------------------------------------------------------------------------
    def test_touch_creates_empty_object(self):
        """
        One conditional call creates the object, with the given metadata.
        """
        p = self.s3dir_test / "file.txt"
        with record_api_calls(self.s3_client) as calls:
            assert p.touch(metadata={"k": "v"}) is None
        assert calls == ["PutObject"]
        assert self.get(p) == b""
        assert self.s3_client.head_object(Bucket=p.bucket, Key=p.key)["Metadata"] == {"k": "v"}

    def test_touch_existing(self):
        """
        An existing object raises ``S3FileAlreadyExist`` and is not changed.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"important")
        with pytest.raises(S3FileAlreadyExist, match="already exist"):
            p.touch()
        assert self.get(p) == b"important"

    def test_touch_existing_ok(self):
        """
        With ``exist_ok=True``, an existing object is not changed. 2.x
        replaced it with an empty object.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"important")
        assert p.touch(exist_ok=True) is None
        assert self.get(p) == b"important"

    def test_touch_after_delete_marker(self):
        """
        An object whose latest version is a delete marker does not exist, the
        same as for ``exists()``.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        self.put(p, b"old")
        self.s3_client.delete_object(Bucket=p.bucket, Key=p.key)
        p.touch()
        assert self.get(p) == b""

    def test_touch_error_raised_as_is(self):
        p = S3Path(f"s3pathlib-test-tmp-{uuid.uuid4().hex}", "file.txt")
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.touch()
        assert error_code(exc_info) == "NoSuchBucket"

    # --------------------------------------------------------------------------
    # 4. mkdir
    # --------------------------------------------------------------------------
    def test_mkdir(self):
        p = self.s3dir_test / "folder/"
        assert p.mkdir() is None
        assert self.get(p) == b""

    @pytest.mark.parametrize(
        "key",
        [
            pytest.param("folder/", id="hard-folder"),
            pytest.param("folder/file.txt", id="soft-folder"),
        ],
    )
    def test_mkdir_existing(self, key):
        """
        A folder that exists, with or without marker, raises
        ``S3FolderAlreadyExist``.
        """
        self.put(self.s3dir_test / key, b"")
        with pytest.raises(S3FolderAlreadyExist, match="already exist"):
            (self.s3dir_test / "folder/").mkdir()

    def test_mkdir_existing_ok_keeps_marker(self):
        """
        With ``exist_ok=True``, an existing marker is not replaced, even if it
        has content. 2.x replaced it with an empty object.
        """
        p = self.s3dir_test / "folder/"
        self.put(p, b"data")
        p.mkdir(exist_ok=True)
        assert self.get(p) == b"data"

    def test_mkdir_existing_ok_soft_folder(self):
        """
        With ``exist_ok=True``, a folder without marker gets one.
        """
        p = self.s3dir_test / "folder/"
        self.put(p / "file.txt")
        p.mkdir(exist_ok=True)
        assert self.get(p) == b""

    def test_mkdir_marker_written_meanwhile(self, monkeypatch):
        """
        If the marker appears after the existence check (written by someone
        else), ``exist_ok=False`` still raises and the marker is kept.
        """
        p = self.s3dir_test / "folder/"
        self.put(p, b"data")
        monkeypatch.setattr(S3Path, "exists", lambda self, **kwargs: False)
        with pytest.raises(S3FolderAlreadyExist):
            p.mkdir()
        assert self.get(p) == b"data"

    def test_mkdir_parents(self, tmp_bucket):
        """
        ``parents=True`` writes the marker of every parent folder up to the
        bucket, keeping the existing ones. Run in a temporary bucket, because
        it writes markers up to the bucket root.
        """
        self.s3_client.put_object(Bucket=tmp_bucket, Key="a/", Body=b"data")
        S3Path(tmp_bucket, "a/b/c/").mkdir(parents=True)
        res = self.s3_client.list_objects_v2(Bucket=tmp_bucket)
        sizes = {dct["Key"]: dct["Size"] for dct in res["Contents"]}
        assert sizes == {"a/": 4, "a/b/": 0, "a/b/c/": 0}

    def test_mkdir_error_raised_as_is(self):
        p = S3Path(f"s3pathlib-test-tmp-{uuid.uuid4().hex}", "folder/")
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.mkdir()
        assert error_code(exc_info) == "NoSuchBucket"

    # --------------------------------------------------------------------------
    # 5. Invalid paths
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "method, args",
        [
            pytest.param("read_bytes", [], id="read_bytes"),
            pytest.param("read_text", [], id="read_text"),
            pytest.param("write_bytes", [b"x"], id="write_bytes"),
            pytest.param("write_text", ["x"], id="write_text"),
        ],
    )
    @pytest.mark.parametrize(
        "p, match",
        [
            pytest.param(S3Path(), "is a relative path", id="void"),
            pytest.param(S3Path.make_relpath("a.txt"), "is a relative path", id="relpath"),
            pytest.param(S3Path("bucket"), "is a bucket", id="bucket"),
        ],
    )
    def test_read_write_not_an_object(self, method, args, p, match):
        """
        Only an object can be read or written; 2.x raised botocore errors.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(S3PathTypeError, match=match):
                getattr(p, method)(*args)
        assert calls == []

    @pytest.mark.parametrize(
        "method, p, error, match",
        [
            pytest.param("touch", S3Path(), S3PathTypeError, "is a relative path", id="touch-void"),
            pytest.param(
                "touch",
                S3Path.make_relpath("a.txt"),
                S3PathTypeError,
                "is a relative path",
                id="touch-relpath",
            ),
            pytest.param("touch", S3Path("b", "a/"), S3PathIsNotFileError, "is not a file", id="touch-dir"),
            pytest.param("touch", S3Path("b"), S3PathIsNotFileError, "is not a file", id="touch-bucket"),
            pytest.param("mkdir", S3Path(), S3PathTypeError, "is a relative path", id="mkdir-void"),
            pytest.param(
                "mkdir",
                S3Path.make_relpath("a/"),
                S3PathTypeError,
                "is a relative path",
                id="mkdir-relpath",
            ),
            pytest.param("mkdir", S3Path("b", "a.txt"), S3PathIsNotFolderError, "is not a dir", id="mkdir-file"),
            pytest.param("mkdir", S3Path("b"), S3PathTypeError, "use create_bucket", id="mkdir-bucket"),
        ],
    )
    def test_touch_mkdir_wrong_path(self, method, p, error, match):
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error, match=match):
                getattr(p, method)(exist_ok=True)
        assert calls == []


class TestMock(ReadAndWriteMixin):
    use_mock = True


class TestRealAws(ReadAndWriteMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.rw",
        preview=False,
    )

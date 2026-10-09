# -*- coding: utf-8 -*-

"""
Test ``S3Path.open`` (``s3pathlib.core.opener``).

Test order:

1. reading and writing text and bytes, versions;
2. the write arguments (they take effect, and their boto3 names), the read
   arguments, ``transport_params``;
3. compression;
4. errors: an exception in the ``with`` block, a missing object;
5. invalid input: mode, ``version_id`` when writing, keys containing
   ``?versionId=``, paths that are not objects, removed arguments.
"""

import contextlib
import datetime
import json
import pickle

import pytest

from s3pathlib.api import S3Path
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest

EXPIRES = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)

# open() argument -> (boto3 parameter, value), sent to both
# create_multipart_upload and put_object
WRITE_ARGUMENTS = {
    "metadata": ("Metadata", {"k": "v"}),
    "acl": ("ACL", "private"),
    "cache_control": ("CacheControl", "no-cache"),
    "content_disposition": ("ContentDisposition", "inline"),
    "content_encoding": ("ContentEncoding", "identity"),
    "content_language": ("ContentLanguage", "en"),
    "content_type": ("ContentType", "text/plain"),
    "checksum_algorithm": ("ChecksumAlgorithm", "SHA256"),
    "expires_datetime": ("Expires", EXPIRES),
    "grant_full_control": ("GrantFullControl", "id=full"),
    "grant_read": ("GrantRead", "id=read"),
    "grant_read_acp": ("GrantReadACP", "id=read-acp"),
    "grant_write_acp": ("GrantWriteACP", "id=write-acp"),
    "server_side_encryption": ("ServerSideEncryption", "aws:kms"),
    "storage_class": ("StorageClass", "STANDARD_IA"),
    "website_redirect_location": ("WebsiteRedirectLocation", "/other"),
    "sse_customer_algorithm": ("SSECustomerAlgorithm", "AES256"),
    "sse_customer_key": ("SSECustomerKey", "key"),
    "sse_kms_key_id": ("SSEKMSKeyId", "key-id"),
    "sse_kms_encryption_context": ("SSEKMSEncryptionContext", "context"),
    "bucket_key_enabled": ("BucketKeyEnabled", True),
    "request_payer": ("RequestPayer", "requester"),
    "object_lock_mode": ("ObjectLockMode", "GOVERNANCE"),
    "object_lock_retain_until_datetime": ("ObjectLockRetainUntilDate", EXPIRES),
    "object_lock_legal_hold_status": ("ObjectLockLegalHoldStatus", "OFF"),
    "expected_bucket_owner": ("ExpectedBucketOwner", "111122223333"),
}

# only put_object has them (multipart_upload=False)
PUT_OBJECT_ONLY_ARGUMENTS = {
    "content_length": ("ContentLength", 1),
    "content_md5": ("ContentMD5", "md5"),
    "checksum_crc32": ("ChecksumCRC32", "crc32"),
    "checksum_crc32c": ("ChecksumCRC32C", "crc32c"),
    "checksum_sha1": ("ChecksumSHA1", "sha1"),
    "checksum_sha256": ("ChecksumSHA256", "sha256"),
}

READ_ARGUMENTS = {
    "if_match": ("IfMatch", '"etag"'),
    "if_modified_since": ("IfModifiedSince", EXPIRES),
    "if_none_match": ("IfNoneMatch", '"other"'),
    "if_unmodified_since": ("IfUnmodifiedSince", EXPIRES),
    "response_cache_control": ("ResponseCacheControl", "no-cache"),
    "response_content_disposition": ("ResponseContentDisposition", "inline"),
    "response_content_encoding": ("ResponseContentEncoding", "identity"),
    "response_content_language": ("ResponseContentLanguage", "en"),
    "response_content_type": ("ResponseContentType", "text/plain"),
    "response_expires": ("ResponseExpires", EXPIRES),
    "sse_customer_algorithm": ("SSECustomerAlgorithm", "AES256"),
    "sse_customer_key": ("SSECustomerKey", "key"),
    "request_payer": ("RequestPayer", "requester"),
    "expected_bucket_owner": ("ExpectedBucketOwner", "111122223333"),
    "checksum_mode": ("ChecksumMode", "ENABLED"),
}


class Captured(Exception):
    """
    Raised to stop an API call once its parameters are recorded.
    """


@contextlib.contextmanager
def capture_params(s3_client, operation: str):
    """
    Record the parameters of the first ``operation`` call (e.g.
    ``"PutObject"``) made through ``s3_client``, and stop it by raising
    ``Captured``, so that no request is sent.
    """
    params = dict()

    def record(params: dict, **kwargs):
        captured.update(params)
        raise Captured

    captured = params
    events = s3_client.meta.events
    events.register(f"provide-client-params.s3.{operation}", record)
    try:
        yield params
    finally:
        events.unregister(f"provide-client-params.s3.{operation}", record)


def expected_params(arguments: dict) -> dict:
    return {param: value for param, value in arguments.values()}


def call_kwargs(arguments: dict) -> dict:
    return {name: value for name, (_, value) in arguments.items()}


class OpenerMixin(BaseTest):
    module = "core.opener"

    def put(self, p: S3Path, body: bytes = b"hello") -> str | None:
        res = self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=body)
        return res.get("VersionId")

    def get(self, p: S3Path) -> bytes:
        return self.s3_client.get_object(Bucket=p.bucket, Key=p.key)["Body"].read()

    def exists(self, p: S3Path) -> bool:
        res = self.s3_client.list_objects_v2(Bucket=p.bucket, Prefix=p.key)
        return res.get("KeyCount", 0) > 0

    # --------------------------------------------------------------------------
    # 1. Read and write
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("write_mode, read_mode", [("w", "r"), ("wt", "rt")])
    def test_text(self, write_mode, read_mode):
        p = self.s3dir_test / "data.json"
        with p.open(write_mode) as f:
            json.dump({"a": 1}, f)
        with p.open(read_mode) as f:
            assert json.load(f) == {"a": 1}

    def test_bytes(self):
        p = self.s3dir_test / "data.pickle"
        with p.open("wb") as f:
            pickle.dump({"a": 1}, f)
        with p.open("rb") as f:
            assert pickle.load(f) == {"a": 1}

    def test_encoding(self):
        p = self.s3dir_test / "file.txt"
        with p.open("w", encoding="utf-16") as f:
            f.write("你好")
        assert self.get(p) == "你好".encode("utf-16")
        with p.open("r", encoding="utf-16") as f:
            assert f.read() == "你好"

    def test_read_version(self):
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p, b"v1")
        self.put(p, b"v2")
        with p.open() as f:
            assert f.read() == "v2"
        with p.open(version_id=v1) as f:
            assert f.read() == "v1"

    def test_snapshot_unchanged(self):
        """
        ``open`` never changes the metadata snapshot of the path.
        """
        p = self.s3dir_test / "file.txt"
        with p.open("w") as f:
            f.write("hello")
        with p.open() as f:
            f.read()
        assert p.response is None

    def test_question_mark_in_key(self):
        """
        A ``?`` that is not ``?versionId=`` works (case sensitive).
        """
        for key in ["page?id=1", "page?versionid=1"]:
            p = self.s3dir_test / key
            with p.open("w") as f:
                f.write(key)
            assert self.get(p) == key.encode()
            with p.open() as f:
                assert f.read() == key

    def test_folder_marker(self):
        """
        A folder marker object can be written and read.
        """
        p = self.s3dir_test / "folder/"
        with p.open("wb"):
            pass
        assert self.get(p) == b""

    # --------------------------------------------------------------------------
    # 2. Arguments
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("multipart_upload", [True, False])
    def test_write_arguments_take_effect(self, multipart_upload):
        """
        The write arguments take effect without ``metadata`` / ``tags``; 2.x
        ignored them unless one of these was given.
        """
        p = self.s3dir_test / "file.txt"
        with p.open(
            "w",
            content_type="text/plain",
            cache_control="no-cache",
            storage_class="STANDARD_IA",
            multipart_upload=multipart_upload,
        ) as f:
            f.write("hello")
        res = self.s3_client.head_object(Bucket=p.bucket, Key=p.key)
        assert res["ContentType"] == "text/plain"
        assert res["CacheControl"] == "no-cache"
        assert res["StorageClass"] == "STANDARD_IA"

    @pytest.mark.parametrize("multipart_upload", [True, False])
    def test_write_metadata_and_tags(self, multipart_upload):
        p = self.s3dir_test / "file.txt"
        with p.open(
            "w",
            metadata={"creator": "s3pathlib"},
            tags={"team": "data eng"},
            multipart_upload=multipart_upload,
        ) as f:
            f.write("hello")
        res = self.s3_client.head_object(Bucket=p.bucket, Key=p.key)
        assert res["Metadata"] == {"creator": "s3pathlib"}
        res = self.s3_client.get_object_tagging(Bucket=p.bucket, Key=p.key)
        assert res["TagSet"] == [{"Key": "team", "Value": "data eng"}]

    @pytest.mark.parametrize(
        "multipart_upload, operation, arguments",
        [
            pytest.param(True, "CreateMultipartUpload", WRITE_ARGUMENTS, id="multipart"),
            pytest.param(
                False,
                "PutObject",
                {**WRITE_ARGUMENTS, **PUT_OBJECT_ONLY_ARGUMENTS},
                id="put_object",
            ),
        ],
    )
    def test_write_arguments_passed_to_boto3(self, multipart_upload, operation, arguments):
        """
        Every write argument is sent under its boto3 name, the tags URL
        encoded.
        """
        p = S3Path("bucket", "file.txt")
        with capture_params(self.s3_client, operation) as params:
            with pytest.raises(Captured):
                with p.open(
                    "w",
                    multipart_upload=multipart_upload,
                    tags={"t": "a b"},
                    **call_kwargs(arguments),
                ) as f:
                    f.write("x")
        expected = expected_params(arguments)
        expected["Tagging"] = "t=a%20b"
        for key, value in expected.items():
            assert params[key] == value, key

    @pytest.mark.parametrize("name", list(PUT_OBJECT_ONLY_ARGUMENTS))
    def test_put_object_only_argument_with_multipart(self, name):
        """
        ``create_multipart_upload`` has no such parameter; 2.x ignored it.
        """
        p = self.s3dir_test / "file.txt"
        _, value = PUT_OBJECT_ONLY_ARGUMENTS[name]
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match="only apply with multipart_upload=False"):
                p.open("w", **{name: value})
        assert calls == []

    def test_read_arguments_passed_to_boto3(self):
        p = S3Path("bucket", "file.txt")
        with capture_params(self.s3_client, "GetObject") as params:
            with pytest.raises(Captured):
                with p.open("r", version_id="v1", **call_kwargs(READ_ARGUMENTS)) as f:
                    f.read()
        expected = expected_params(READ_ARGUMENTS)
        expected["VersionId"] = "v1"
        for key, value in expected.items():
            assert params[key] == value, key

    def test_transport_params_merged(self):
        """
        ``client_kwargs`` of ``transport_params`` are merged with the
        arguments (which win), and the given dict is not changed.
        """
        p = self.s3dir_test / "file.txt"
        transport_params = {
            "client_kwargs": {
                "S3.Client.create_multipart_upload": {
                    "ContentType": "text/csv",
                    "CacheControl": "max-age=1",
                },
            },
        }
        with p.open("w", cache_control="no-cache", transport_params=transport_params) as f:
            f.write("a,b")
        res = self.s3_client.head_object(Bucket=p.bucket, Key=p.key)
        assert res["ContentType"] == "text/csv"
        assert res["CacheControl"] == "no-cache"
        assert transport_params == {
            "client_kwargs": {
                "S3.Client.create_multipart_upload": {
                    "ContentType": "text/csv",
                    "CacheControl": "max-age=1",
                },
            },
        }

    def test_transport_params_for_smart_open(self):
        """
        Other ``transport_params`` go to smart_open as they are, and the given
        dict is not changed (its ``client`` is set on a copy).
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"0123456789")
        transport_params = {"buffer_size": 4}
        with p.open("rb", transport_params=transport_params) as f:
            assert f.read() == b"0123456789"
        assert transport_params == {"buffer_size": 4}

    # --------------------------------------------------------------------------
    # 3. Compression
    # --------------------------------------------------------------------------
    def test_compression_from_extension(self):
        """
        By default, ``.gz`` keys are compressed and decompressed.
        """
        p = self.s3dir_test / "data.txt.gz"
        with p.open("w") as f:
            f.write("hello")
        assert self.get(p)[:2] == b"\x1f\x8b"
        with p.open() as f:
            assert f.read() == "hello"

    def test_compression_disable(self):
        p = self.s3dir_test / "data.txt.gz"
        with p.open("w", compression="disable") as f:
            f.write("plain")
        assert self.get(p) == b"plain"

    def test_compression_explicit(self):
        p = self.s3dir_test / "data.txt"
        with p.open("w", compression=".gz") as f:
            f.write("hello")
        assert self.get(p)[:2] == b"\x1f\x8b"
        with p.open(compression=".gz") as f:
            assert f.read() == "hello"

    # --------------------------------------------------------------------------
    # 4. Errors
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("multipart_upload", [True, False])
    @pytest.mark.parametrize("mode", ["w", "wb"])
    def test_exception_writes_nothing(self, mode, multipart_upload):
        """
        An exception inside the ``with`` block aborts the write: no partial
        object.
        """
        p = self.s3dir_test / "file.txt"
        with pytest.raises(RuntimeError):
            with p.open(mode, multipart_upload=multipart_upload) as f:
                if mode == "w":
                    f.write("partial")
                else:
                    f.write(b"partial")
                raise RuntimeError("boom")
        assert self.exists(p) is False

    def test_missing_object(self):
        """
        smart_open raises ``OSError``, with the boto3 error as its cause.
        """
        p = self.s3dir_test / "missing.txt"
        with pytest.raises(OSError) as exc_info:
            with p.open() as f:
                f.read()
        assert exc_info.value.__cause__.response["Error"]["Code"] == "NoSuchKey"

    # --------------------------------------------------------------------------
    # 5. Invalid input
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("mode", ["a", "x", "w+", "r+", "", None])
    def test_invalid_mode(self, mode):
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match="mode must be one of"):
                (self.s3dir_test / "file.txt").open(mode)
        assert calls == []

    def test_version_id_when_writing(self):
        """
        2.x ignored ``version_id`` when writing.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match="only for reading"):
                (self.s3dir_test / "file.txt").open("w", version_id="v1")
        assert calls == []

    @pytest.mark.parametrize(
        "key",
        ["page?versionId=1", "page&versionId=1", "page?a=1&versionId=1", "page?versionId="],
    )
    @pytest.mark.parametrize("mode", ["r", "w"])
    def test_key_with_version_id(self, key, mode):
        """
        smart_open 8 takes ``?versionId=`` / ``&versionId=`` in a key as a
        version id; such keys are rejected with every smart_open version (see
        the docstring of ``open``).
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match="use read_bytes"):
                (self.s3dir_test / key).open(mode)
        assert calls == []

    @pytest.mark.parametrize(
        "p, match",
        [
            pytest.param(S3Path(), "is a relative path", id="void"),
            pytest.param(S3Path.make_relpath("a.txt"), "is a relative path", id="relpath"),
            pytest.param(S3Path("bucket"), "is a bucket", id="bucket"),
        ],
    )
    def test_not_an_object(self, p, match):
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(S3PathTypeError, match=match):
                p.open()
        assert calls == []

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"ignore_ext": True}, id="ignore_ext"),
            pytest.param({"range": "bytes=0-1"}, id="range"),
            pytest.param({"part_number": 1}, id="part_number"),
        ],
    )
    def test_removed_arguments(self, kwargs):
        """
        Removed in 3.0: they never had an effect (or failed).
        """
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            (self.s3dir_test / "file.txt").open(**kwargs)


class TestMock(OpenerMixin):
    use_mock = True


class TestRealAws(OpenerMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.opener",
        preview=False,
    )

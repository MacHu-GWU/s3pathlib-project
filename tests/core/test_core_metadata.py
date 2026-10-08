# -*- coding: utf-8 -*-

"""
Test the metadata snapshot of ``S3Path`` (``s3pathlib.core.metadata``).

Test order:

1. no snapshot: the first property read loads the latest version, once;
2. a partial snapshot (from a list or write API): its fields need no call,
   the missing ones are loaded from the same object version;
3. a delete marker never calls AWS;
4. ``head_object`` and ``clear_cache``, the only ways to replace a snapshot;
   ``read_bytes`` only fills an empty one;
5. returned dicts are copies; a new path built from a path has no snapshot;
6. paths that cannot have object metadata.

Which client loads the metadata is tested in
``tests/core/test_core_resolve_s3_client.py``.
"""

import contextlib
import datetime
import hashlib
import time

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.api import S3Path
from s3pathlib.exc import S3FileNotExist
from s3pathlib.exc import S3ObjectChangedError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest


@contextlib.contextmanager
def record_head_params(s3_client):
    """
    Record the parameters of every ``head_object`` call made through
    ``s3_client``.
    """
    params_list = list()

    def record(params, **kwargs):
        params_list.append(dict(params))

    events = s3_client.meta.events
    events.register("provide-client-params.s3.HeadObject", record)
    try:
        yield params_list
    finally:
        events.unregister("provide-client-params.s3.HeadObject", record)


class MetadataMixin(BaseTest):
    module = "core.metadata"

    def put(self, p: S3Path, body: bytes, **kwargs) -> str | None:
        """
        Write an object with the native client.

        :return: the version id (``None`` without versioning)
        """
        res = self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=body, **kwargs)
        return res.get("VersionId")

    # --------------------------------------------------------------------------
    # 1. No snapshot
    # --------------------------------------------------------------------------
    def test_properties_match_head_object(self):
        """
        Each property gives the matching ``head_object`` field; the ETag has
        no quotes; an object written without versioning has the version id
        ``"null"``.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"Hello World!", Metadata={"creator": "alice"})
        res = self.s3_client.head_object(Bucket=p.bucket, Key=p.key)
        assert p.etag == hashlib.md5(b"Hello World!").hexdigest()
        assert p.size == 12
        assert p.size_for_human == "12 B"
        assert p.last_modified_at == res["LastModified"]
        assert p.metadata == {"creator": "alice"}
        assert p.version_id == "null"
        assert p.expire_at is None

    def test_first_read_loads_once(self):
        """
        The first property read loads the whole snapshot with one
        ``head_object``; the others, including a field the object does not
        have (``expire_at``), need no call.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        with record_api_calls(self.s3_client) as calls:
            _ = p.size
            _ = p.etag
            _ = p.metadata
            _ = p.version_id
            _ = p.expire_at
        assert calls == ["HeadObject"]

    def test_version_id_with_versioning(self):
        p = self.s3dir_test_with_versioning / "file.txt"
        version_id = self.put(p, b"abc")
        assert p.version_id == version_id

    def test_expire_at(self):
        """
        ``expire_at`` is the ``Expires`` header set when writing the object.
        """
        p = self.s3dir_test / "file.txt"
        expires = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
        self.put(p, b"abc", Expires=expires)
        assert p.expire_at == expires

    def test_folder_marker_object(self):
        """
        A folder marker object (``folder/``) is a real object with metadata.
        """
        p = self.s3dir_test / "folder/"
        self.put(p, b"")
        assert p.size == 0

    # --------------------------------------------------------------------------
    # 2. Partial snapshot
    # --------------------------------------------------------------------------
    def test_listed_fields_need_no_call(self):
        """
        The fields returned by the list API are read from the snapshot.
        """
        self.put(self.s3dir_test / "file.txt", b"abc")
        p = self.s3dir_test.iter_objects().one()
        with record_api_calls(self.s3_client) as calls:
            assert p.size == 3
            assert p.etag == hashlib.md5(b"abc").hexdigest()
            assert p.last_modified_at is not None
        assert calls == []

    def test_listed_missing_field_loads_same_object(self):
        """
        A field the list API does not return is loaded with ``head_object``
        and ``IfMatch`` set to the listed ETag. 2.x returned ``"null"`` as the
        version id of a listed object, even with versioning.
        """
        version_id = self.put(self.s3dir_test_with_versioning / "file.txt", b"abc")
        p = self.s3dir_test_with_versioning.iter_objects().one()
        with record_head_params(self.s3_client) as params_list:
            assert p.version_id == version_id
            assert p.metadata == {}
        assert len(params_list) == 1
        assert params_list[0]["IfMatch"] == f'"{hashlib.md5(b"abc").hexdigest()}"'
        assert "VersionId" not in params_list[0]

    def test_listed_object_changed(self):
        """
        If the object was overwritten after it was listed, its missing fields
        are not loaded from the new object: ``S3ObjectChangedError``, and the
        snapshot is unchanged.
        """
        self.put(self.s3dir_test / "file.txt", b"abc")
        p = self.s3dir_test.iter_objects().one()
        self.put(p, b"hello")
        with pytest.raises(S3ObjectChangedError, match="changed since its metadata"):
            _ = p.metadata
        assert p.size == 3

    def test_version_snapshot_stays_on_its_version(self):
        """
        An old version from ``list_object_versions`` loads its missing fields
        from that version. 2.x loaded the latest version, so the old version
        silently got the size, metadata and version id of the latest one.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p, b"one", Metadata={"n": "1"})
        time.sleep(1)
        self.put(p, b"two!!", Metadata={"n": "2"})
        old = [x for x in p.list_object_versions() if x.version_id == v1][0]
        with record_head_params(self.s3_client) as params_list:
            assert old.metadata == {"n": "1"}
        assert params_list[0]["VersionId"] == v1
        assert old.size == 3
        assert old.version_id == v1

    def test_write_snapshot_stays_on_its_version(self):
        """
        The path returned by ``write_text`` describes the written version,
        even after the object is overwritten.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        written = p.write_text("a")
        version_id = written.version_id
        self.put(p, b"bb")
        assert written.last_modified_at is not None
        assert written.size == 1
        assert written.version_id == version_id

    def test_partial_snapshot_without_version_or_etag(self):
        """
        A partial snapshot without ``VersionId`` and ``ETag`` (e.g. unpickled
        from an older version) loads the latest version, keeping its fields.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        p._set_meta({"StorageClass": "STANDARD"}, complete=False, s3_client=None)
        with record_head_params(self.s3_client) as params_list:
            assert p.size == 3
        assert "IfMatch" not in params_list[0]
        assert "VersionId" not in params_list[0]
        assert p.response["StorageClass"] == "STANDARD"

    def test_load_error_raised_as_is(self):
        """
        Only a failed ``IfMatch`` means "the object changed"; any other
        ``head_object`` error is raised as is.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        stubber.add_client_error(
            "head_object",
            service_error_code="500",
            http_status_code=500,
        )
        p = self.s3dir_test / "file.txt"
        p._set_meta({"ETag": '"abc"'}, complete=False, s3_client=s3_client)
        with stubber:
            with pytest.raises(botocore.exceptions.ClientError) as exc_info:
                _ = p.metadata
        assert exc_info.value.response["Error"]["Code"] == "500"
        stubber.assert_no_pending_responses()

    def test_full_snapshot_missing_field(self):
        """
        A field missing from a full snapshot does not exist on the object:
        ``None``, no call.
        """
        p = self.s3dir_test / "file.txt"
        p._set_meta({"ContentLength": 3}, complete=True, s3_client=None)
        with record_api_calls(self.s3_client) as calls:
            assert p.metadata is None
            assert p.etag is None
            assert p.version_id == "null"
        assert calls == []

    # --------------------------------------------------------------------------
    # 3. Delete marker
    # --------------------------------------------------------------------------
    def test_delete_marker_never_calls_aws(self):
        """
        A delete marker has no content: ``size`` is ``0``, the content fields
        are ``None``. 2.x loaded the latest version and raised
        ``S3FileNotExist`` for ``metadata``.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        self.put(p, b"abc")
        res = self.s3_client.delete_object(Bucket=p.bucket, Key=p.key)
        marker = [x for x in p.list_object_versions() if x.is_delete_marker()][0]
        with record_api_calls(self.s3_client) as calls:
            assert marker.size == 0
            assert marker.etag is None
            assert marker.metadata is None
            assert marker.expire_at is None
            assert marker.version_id == res["VersionId"]
            assert marker.last_modified_at is not None
        assert calls == []

    # --------------------------------------------------------------------------
    # 4. head_object and clear_cache
    # --------------------------------------------------------------------------
    def test_snapshot_not_refreshed_on_its_own(self):
        """
        A loaded snapshot describes the object when it was loaded; reading it
        again does not call AWS.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        assert p.size == 3
        self.put(p, b"hello")
        assert p.size == 3

    def test_head_object_refreshes(self):
        """
        ``head_object()`` loads the latest metadata and replaces the snapshot;
        it returns the response, the snapshot has no ``ResponseMetadata``.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        assert p.size == 3
        self.put(p, b"hello")
        res = p.head_object()
        assert res["ContentLength"] == 5
        assert "ResponseMetadata" in res
        assert "ResponseMetadata" not in p.response
        assert p.size == 5

    def test_head_object_version_id(self):
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p, b"abc")
        self.put(p, b"hello")
        p.head_object(version_id=v1)
        assert p.size == 3
        assert p.version_id == v1

    def test_head_object_missing_clears_snapshot(self):
        """
        When the object no longer exists, ``head_object()`` raises
        ``S3FileNotExist`` and clears the snapshot, so it is not read as the
        metadata of an existing object.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        assert p.size == 3
        self.s3_client.delete_object(Bucket=p.bucket, Key=p.key)
        with pytest.raises(S3FileNotExist):
            p.head_object()
        assert p.response is None

    def test_clear_cache(self):
        """
        After ``clear_cache()``, the next read loads the latest metadata.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        assert p.size == 3
        self.put(p, b"hello")
        p.clear_cache()
        assert p.response is None
        assert p.size == 5

    def test_read_bytes_fills_empty_snapshot(self):
        """
        ``read_bytes`` gives an empty snapshot the ``get_object`` response, so
        reading the size afterwards needs no call.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"0123456789")
        p.read_bytes()
        with record_api_calls(self.s3_client) as calls:
            assert p.size == 10
        assert calls == []

    def test_read_bytes_range_does_not_fill(self):
        """
        A ranged read describes a part only, it does not become the snapshot.
        2.x stored it, so ``size`` became the length of the range.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"0123456789")
        assert p.read_bytes(range="bytes=0-1") == b"01"
        assert p.response is None
        assert p.size == 10

    def test_read_bytes_keeps_existing_snapshot(self):
        """
        ``read_bytes`` does not replace an existing snapshot: the path keeps
        describing the object as it was loaded.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        assert p.size == 3
        self.put(p, b"hello")
        assert p.read_bytes() == b"hello"
        assert p.size == 3

    # --------------------------------------------------------------------------
    # 5. Copies and new paths
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("attr", ["response", "metadata"])
    def test_returned_dict_is_a_copy(self, attr):
        """
        Changing the returned dict does not change the snapshot (2.x returned
        the cached dict itself).
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc", Metadata={"creator": "alice"})
        p.head_object()
        getattr(p, attr)["x"] = "y"
        if attr == "response":
            p.response["Metadata"]["x"] = "y"
        assert "x" not in p.response
        assert p.metadata == {"creator": "alice"}

    @pytest.mark.parametrize(
        "derive",
        [
            pytest.param(lambda p: p.copy(), id="copy"),
            pytest.param(lambda p: p.change(new_basename="file.txt"), id="change"),
            pytest.param(lambda p: p.parent.joinpath("file.txt"), id="joinpath"),
        ],
    )
    def test_new_path_has_no_snapshot(self, derive):
        """
        A new path built from a path is a new location, it does not share the
        snapshot.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, b"abc")
        p.head_object()
        new = derive(p)
        assert new == p
        assert new.response is None

    # --------------------------------------------------------------------------
    # 6. No object metadata
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, match",
        [
            pytest.param(S3Path(), "is a relative path", id="void"),
            pytest.param(S3Path.make_relpath("a.txt"), "is a relative path", id="relpath"),
            pytest.param(S3Path("bucket"), "is a bucket", id="bucket"),
        ],
    )
    def test_path_without_object(self, p, match):
        """
        A path that cannot be an object raises ``S3PathTypeError`` before any
        AWS call (2.x raised botocore errors).
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(S3PathTypeError, match=match):
                _ = p.size
            with pytest.raises(S3PathTypeError, match=match):
                p.head_object()
        assert calls == []

    def test_bucket_from_list_buckets(self):
        """
        A bucket from ``list_buckets()`` has its creation date without any
        call, but no object metadata.
        """
        s3bucket = {p.bucket: p for p in S3Path.list_buckets()}[self.bucket]
        with record_api_calls(self.s3_client) as calls:
            assert s3bucket.last_modified_at is not None
            with pytest.raises(S3PathTypeError, match="is a bucket"):
                _ = s3bucket.size
        assert calls == []


class TestMock(MetadataMixin):
    use_mock = True


class TestRealAws(MetadataMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.metadata",
        preview=False,
    )

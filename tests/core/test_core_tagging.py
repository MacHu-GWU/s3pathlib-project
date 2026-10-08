# -*- coding: utf-8 -*-

"""
Test the object tagging methods of ``S3Path`` (``s3pathlib.core.tagging``).

Test order:

1. ``get_tags``;
2. ``put_tags``: full replacement, versions, the arguments;
3. ``update_tags``: merge, versions (the merge itself is tested in
   ``tests/better_client/test_client_tagging.py``);
4. paths that cannot have tags;
5. AWS errors raised as is.

Tag sets are compared as dicts: real S3 does not return them in the written
order.
"""

import time

import botocore.exceptions
import pytest
from botocore.stub import Stubber

from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tag import encode_url_query
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest
from s3pathlib.tests.mock_aws import real_aws_only

# characters S3 accepts in tags, verified on real AWS
SPECIAL_TAGS = {
    "space": "a b",
    "plus": "a+b",
    "unicode": "中文",
    "symbols": "=:/@._-",
}

METHODS = [
    pytest.param("get_tags", {}, id="get_tags"),
    pytest.param("put_tags", {"tags": {"k": "v"}}, id="put_tags"),
    pytest.param("update_tags", {"tags": {"k": "v"}}, id="update_tags"),
]


def error_code(exc_info) -> str:
    return exc_info.value.response["Error"]["Code"]


class TaggingMixin(BaseTest):
    module = "core.tagging"

    def put(self, p: S3Path, tags: dict | None = None) -> str | None:
        """
        Write an object with the native client, with ``tags``.

        :return: the version id (``None`` without versioning)
        """
        kwargs = dict(Bucket=p.bucket, Key=p.key, Body=b"hello")
        if tags is not None:
            kwargs["Tagging"] = encode_url_query(tags)
        res = self.s3_client.put_object(**kwargs)
        return res.get("VersionId")

    def native_tags(self, p: S3Path, version_id: str | None = None) -> dict:
        kwargs = dict(Bucket=p.bucket, Key=p.key)
        if version_id is not None:
            kwargs["VersionId"] = version_id
        res = self.s3_client.get_object_tagging(**kwargs)
        return {tag["Key"]: tag["Value"] for tag in res["TagSet"]}

    # --------------------------------------------------------------------------
    # 1. get_tags
    # --------------------------------------------------------------------------
    def test_get_tags_none(self):
        """
        An object without tags gives ``{}``; without versioning, the version
        is ``None``.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p)
        assert p.get_tags() == (None, {})

    def test_get_tags_special_values(self):
        """
        Tags written with ``put_object`` are read back as they are, including
        spaces, ``+`` and non-ASCII characters.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, SPECIAL_TAGS)
        assert p.get_tags()[1] == SPECIAL_TAGS

    def test_get_tags_versions(self):
        """
        Without ``version_id``, the latest version is read, even for a path
        that describes an older version; ``version_id`` reads that version.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p, {"n": "1"})
        time.sleep(1)
        v2 = self.put(p, {"n": "2"})
        old = [x for x in p.list_object_versions() if x.version_id == v1][0]
        assert old.get_tags() == (v2, {"n": "2"})
        assert old.get_tags(version_id=old.version_id) == (v1, {"n": "1"})

    # --------------------------------------------------------------------------
    # 2. put_tags
    # --------------------------------------------------------------------------
    def test_put_tags_replaces_all(self):
        """
        ``put_tags`` is a full replacement: the old keys are gone. It returns
        a copy of the tags.
        """
        p = self.s3dir_test / "file.txt"
        self.put(p, {"k1": "v1", "k2": "v2"})
        tags = {"k2": "v22", "k3": "v3"}
        version_id, returned = p.put_tags(tags)
        assert version_id is None
        assert returned == tags
        assert returned is not tags
        assert self.native_tags(p) == {"k2": "v22", "k3": "v3"}

    @real_aws_only("moto crashes on an empty TagSet")
    def test_put_tags_empty_removes_all(self):
        p = self.s3dir_test / "file.txt"
        self.put(p, {"k1": "v1"})
        assert p.put_tags({}) == (None, {})
        assert self.native_tags(p) == {}

    def test_put_tags_version(self):
        """
        ``version_id`` changes that version only; without it, the latest
        version is changed and returned.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p, {"n": "1"})
        v2 = self.put(p, {"n": "2"})
        p.put_tags({"old": "yes"}, version_id=v1)
        assert self.native_tags(p, v1) == {"old": "yes"}
        assert self.native_tags(p, v2) == {"n": "2"}
        version_id, _ = p.put_tags({"new": "yes"})
        if self.use_mock:
            # moto does not return the version id of the latest version
            assert version_id != v1
        else:
            assert version_id == v2
        assert self.native_tags(p, v2) == {"new": "yes"}

    def test_put_tags_arguments_passed_to_boto3(self):
        """
        Every argument is sent under its boto3 name, the tags as a tag set.
        """
        s3_client = self.boto_ses.client("s3")
        stubber = Stubber(s3_client)
        stubber.add_response(
            "put_object_tagging",
            {"VersionId": "v1"},
            expected_params={
                "Bucket": "bucket",
                "Key": "file.txt",
                "Tagging": {"TagSet": [{"Key": "k", "Value": "v"}]},
                "VersionId": "v1",
                "ContentMD5": "md5",
                "ChecksumAlgorithm": "SHA256",
                "ExpectedBucketOwner": "111122223333",
                "RequestPayer": "requester",
            },
        )
        s3_context.attach_s3_client(s3_client)
        try:
            with stubber:
                res = S3Path("bucket", "file.txt").put_tags(
                    {"k": "v"},
                    version_id="v1",
                    content_md5="md5",
                    checksum_algorithm="SHA256",
                    expected_bucket_owner="111122223333",
                    request_payer="requester",
                )
        finally:
            s3_context.attach_s3_client(self.s3_client)
        assert res == ("v1", {"k": "v"})
        stubber.assert_no_pending_responses()

    # --------------------------------------------------------------------------
    # 3. update_tags
    # --------------------------------------------------------------------------
    def test_update_tags_merges(self):
        p = self.s3dir_test / "file.txt"
        self.put(p, {"k1": "v1", "k2": "v2"})
        assert p.update_tags({"k2": "v22", "k3": "v3"}) == (
            None,
            {"k1": "v1", "k2": "v22", "k3": "v3"},
        )
        assert self.native_tags(p) == {"k1": "v1", "k2": "v22", "k3": "v3"}

    def test_update_tags_version(self):
        p = self.s3dir_test_with_versioning / "file.txt"
        v1 = self.put(p, {"n": "1"})
        v2 = self.put(p, {"n": "2"})
        assert p.update_tags({"old": "yes"}, version_id=v1) == (
            v1,
            {"n": "1", "old": "yes"},
        )
        assert self.native_tags(p, v2) == {"n": "2"}

    # --------------------------------------------------------------------------
    # 4. No tags
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("method, kwargs", METHODS)
    @pytest.mark.parametrize(
        "p, error, match",
        [
            pytest.param(S3Path(), S3PathTypeError, "is a relative path", id="void"),
            pytest.param(
                S3Path.make_relpath("a.txt"),
                S3PathTypeError,
                "is a relative path",
                id="relpath-file",
            ),
            pytest.param(
                S3Path.make_relpath("a/"),
                S3PathTypeError,
                "is a relative path",
                id="relpath-dir",
            ),
            pytest.param(
                S3Path("bucket", "folder/"),
                S3PathIsNotFileError,
                "is not a file",
                id="dir",
            ),
            pytest.param(
                S3Path("bucket"),
                S3PathIsNotFileError,
                "is not a file",
                id="bucket",
            ),
        ],
    )
    def test_not_a_file(self, method, kwargs, p, error, match):
        """
        Only a file has tags; anything else is rejected before any AWS call
        (2.x let a relative file through, and botocore raised ``TypeError``).
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error, match=match):
                getattr(p, method)(**kwargs)
        assert calls == []

    # --------------------------------------------------------------------------
    # 5. AWS errors
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("method, kwargs", METHODS)
    def test_missing_object(self, method, kwargs):
        p = self.s3dir_test / "missing.txt"
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            getattr(p, method)(**kwargs)
        assert error_code(exc_info) == "NoSuchKey"

    def test_missing_bucket(self):
        p = S3Path("s3pathlib-test-tmp-missing-bucket-for-tagging", "file.txt")
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.get_tags()
        assert error_code(exc_info) == "NoSuchBucket"

    def test_too_many_tags(self):
        p = self.s3dir_test / "file.txt"
        self.put(p)
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.put_tags({f"k{i}": "v" for i in range(11)})
        assert error_code(exc_info) == "BadRequest"

    def test_delete_marker(self):
        """
        The latest version is a delete marker: real S3 answers
        ``MethodNotAllowed``, moto ``NoSuchKey``.
        """
        p = self.s3dir_test_with_versioning / "file.txt"
        self.put(p)
        self.s3_client.delete_object(Bucket=p.bucket, Key=p.key)
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            p.get_tags()
        if self.use_mock:
            assert error_code(exc_info) == "NoSuchKey"
        else:
            assert error_code(exc_info) == "MethodNotAllowed"


class TestMock(TaggingMixin):
    use_mock = True


class TestRealAws(TaggingMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.tagging",
        preview=False,
    )

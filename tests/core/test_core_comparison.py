# -*- coding: utf-8 -*-

"""
Test the comparison operators and the hash of ``S3Path``.

Test order:

1. equality: each kind of path is only equal to itself, however it is built;
2. hash: equal paths hash the same, so sets and dicts work;
3. order: part by part like ``pathlib``, with a fixed order between kinds;
4. comparing with other types;
5. versions: equality ignores the version (the only part that needs moto).
"""

import operator

import pytest

from s3pathlib.api import S3Path
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock import BaseTest

R = S3Path.make_relpath

FILE = S3Path("bucket", "file.txt")
DIRECTORY = S3Path("bucket", "folder/")
BUCKET = S3Path("bucket")
RELPATH_FILE = R("file.txt")
RELPATH_DIR = R("folder/")
VOID = S3Path()

ALL_KINDS = [FILE, DIRECTORY, BUCKET, RELPATH_FILE, RELPATH_DIR, VOID]
ALL_KINDS_IDS = ["file", "dir", "bucket", "relpath-file", "relpath-dir", "void"]


class ComparisonAPIMixin(BaseTest):
    module = "core.comparison"

    # --------------------------------------------------------------------------
    # 1. equality
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("p1", ALL_KINDS, ids=ALL_KINDS_IDS)
    @pytest.mark.parametrize("p2", ALL_KINDS, ids=ALL_KINDS_IDS)
    def test_eq_between_kinds(self, p1, p2):
        """
        Each of the six kinds is equal to itself and different from the
        others; ``!=`` is always the opposite of ``==``.
        """
        assert (p1 == p2) is (p1 is p2)
        assert (p1 != p2) is (p1 is not p2)

    @pytest.mark.parametrize(
        "p1, p2",
        [
            pytest.param(FILE, S3Path("bucket/file.txt"), id="file-string"),
            pytest.param(FILE, S3Path.from_s3_uri("s3://bucket/file.txt"), id="uri"),
            pytest.param(FILE, S3Path.from_s3_arn("arn:aws:s3:::bucket/file.txt"), id="arn"),
            pytest.param(DIRECTORY, S3Path("s3://bucket/folder/"), id="dir-uri"),
            pytest.param(BUCKET, S3Path("bucket", ""), id="bucket"),
            pytest.param(RELPATH_FILE, FILE.relative_to(BUCKET), id="relpath-file"),
            pytest.param(RELPATH_DIR, DIRECTORY.relative_to(BUCKET), id="relpath-dir"),
            pytest.param(VOID, BUCKET.relative_to(BUCKET), id="void"),
        ],
    )
    def test_eq_however_built(self, p1, p2):
        """
        The same path built in different ways is equal.
        """
        assert p1 == p2
        assert p1 is not p2

    @pytest.mark.parametrize(
        "p1, p2",
        [
            pytest.param(S3Path("b", "a"), S3Path("b", "a/"), id="absolute"),
            pytest.param(R("a"), R("a/"), id="relative"),
        ],
    )
    def test_eq_file_is_not_dir(self, p1, p2):
        """
        Same parts, but a file is not a dir.
        """
        assert p1 != p2

    @pytest.mark.parametrize(
        "p1, p2",
        [
            pytest.param(S3Path("b", "a"), R("a"), id="absolute-vs-relative"),
            pytest.param(S3Path("b1", "a"), S3Path("b2", "a"), id="other-bucket"),
            pytest.param(S3Path("a"), R("a/"), id="bucket-vs-relpath-dir"),
        ],
    )
    def test_eq_other_location(self, p1, p2):
        """
        The bucket is part of the path: a relative path never equals an
        absolute one, even when the bucket name looks like a part.
        """
        assert p1 != p2

    # --------------------------------------------------------------------------
    # 2. hash
    # --------------------------------------------------------------------------
    def test_hash_set_and_dict(self):
        """
        Equal paths hash the same, so a set keeps one of them and a dict
        finds a key by an equal path.
        """
        p_list = [
            FILE,
            DIRECTORY,
            BUCKET,
            VOID,
            FILE.relative_to(BUCKET),
            DIRECTORY.relative_to(BUCKET),
            BUCKET.relative_to(BUCKET),
            RELPATH_FILE,
            RELPATH_DIR,
        ]
        p_set = set(p_list + p_list)
        assert len(p_set) == 6
        for p in p_list:
            assert p in p_set

        mapping = {S3Path("bucket", "a.txt"): 1}
        assert mapping[S3Path("s3://bucket/a.txt")] == 1

    def test_cparts_is_tuple(self):
        """
        The comparison cache is a tuple like ``_parts``: it can not be changed,
        and the hash is the hash of the cache, so equal paths hash the same.
        """
        p1 = S3Path("bucket", "folder/")
        p2 = S3Path("bucket/folder/")
        assert p1._cparts == ("bucket", "folder", "/")
        assert isinstance(p1._cparts, tuple)
        assert hash(p1) == hash(p2) == hash(("bucket", "folder", "/"))

    # --------------------------------------------------------------------------
    # 3. order
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "small, big",
        [
            pytest.param(BUCKET, FILE, id="bucket-file"),
            pytest.param(BUCKET, DIRECTORY, id="bucket-dir"),
            pytest.param(S3Path("b", "a/"), S3Path("b", "a/b"), id="dir-content"),
            pytest.param(S3Path("b", "a"), S3Path("b", "a/"), id="file-dir"),
            pytest.param(S3Path("a"), S3Path("b"), id="bucket-name"),
        ],
    )
    def test_order_operators(self, small, big):
        """
        ``<``, ``<=``, ``>``, ``>=`` agree with each other.
        """
        assert small < big
        assert small <= big
        assert big > small
        assert big >= small
        assert not (big < small)
        assert not (small > big)
        assert small <= S3Path(small)
        assert small >= S3Path(small)

    def test_order_by_parts(self):
        """
        Paths are ordered part by part, like ``pathlib``, so a dir and its
        content stay together; S3 list APIs use the key string order instead.
        """
        paths = [
            S3Path("b", "a-b"),
            S3Path("b", "a/b"),
            S3Path("b", "a/"),
            S3Path("b", "a"),
            S3Path("b", "a!"),
        ]
        assert [p.key for p in sorted(paths)] == ["a", "a/", "a/b", "a!", "a-b"]
        assert [p.key for p in sorted(paths, key=lambda p: p.key)] == [
            "a",
            "a!",
            "a-b",
            "a/",
            "a/b",
        ]

    def test_order_between_kinds(self):
        """
        Void comes first, then relative paths, then absolute paths.
        """
        kinds = [FILE, DIRECTORY, BUCKET, RELPATH_FILE, RELPATH_DIR, VOID]
        assert sorted(kinds) == [
            VOID,
            RELPATH_FILE,
            RELPATH_DIR,
            BUCKET,
            FILE,
            DIRECTORY,
        ]

    # --------------------------------------------------------------------------
    # 4. other types
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "other",
        [
            pytest.param("s3://bucket/file.txt", id="uri-string"),
            pytest.param(None, id="none"),
            pytest.param(1, id="int"),
        ],
    )
    def test_eq_other_type(self, other):
        """
        A path is never equal to another type, even its URI string; before
        3.0 it raised ``AttributeError``.
        """
        assert (FILE == other) is False
        assert (FILE != other) is True
        assert (other == FILE) is False

    def test_in_mixed_list(self):
        """
        ``in`` compares with every item, so a list with other types must not
        raise.
        """
        assert FILE in ["s3://bucket/file.txt", None, FILE]
        assert FILE not in ["s3://bucket/file.txt", None]

    @pytest.mark.parametrize(
        "op, symbol",
        [
            pytest.param(operator.lt, "<", id="lt"),
            pytest.param(operator.le, "<=", id="le"),
            pytest.param(operator.gt, ">", id="gt"),
            pytest.param(operator.ge, ">=", id="ge"),
        ],
    )
    def test_order_other_type(self, op, symbol):
        """
        Ordering with another type raises ``TypeError``, like ``pathlib``.
        """
        with pytest.raises(
            TypeError,
            match=f"'{symbol}' not supported between instances of 'S3Path' and 'str'",
        ):
            op(FILE, "s3://bucket/file.txt")

    # --------------------------------------------------------------------------
    # 5. versions
    # --------------------------------------------------------------------------
    def test_eq_ignores_version(self):
        """
        Two versions of the same object are the same path: equal, same hash,
        and a set keeps one. Use ``(p, p.version_id)`` to tell them apart.
        """
        s3path = self.s3dir_root_with_versioning.joinpath("eq-ignores-version.txt")
        self.s3_client.put_object(Bucket=s3path.bucket, Key=s3path.key, Body=b"v1")
        self.s3_client.put_object(Bucket=s3path.bucket, Key=s3path.key, Body=b"v2")
        v1, v2 = list(s3path.list_object_versions())

        assert v1.version_id != v2.version_id
        assert v1 == v2 == s3path
        assert hash(v1) == hash(v2)
        assert len({v1, v2}) == 1
        assert len({(v1, v1.version_id), (v2, v2.version_id)}) == 2


# class Test(ComparisonAPIMixin):
#     use_mock = False


class TestUseMock(ComparisonAPIMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.comparison",
        preview=False,
    )

# -*- coding: utf-8 -*-

"""
Test the ``S3Path(...)`` constructor.

Test order:

1. the four kinds of path (object, directory, bucket root, void), each built
   in many equivalent ways;
2. the S3 URI / ARN input and the boundaries of the later arguments;
3. immutability;
4. invalid inputs, one case per ``raise``.

The constructor is pure logic, but it follows the moto mixin pattern like the
other ``core`` tests.
"""

import pytest

from s3pathlib.api import S3Path
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock import BaseTest


def state(p: S3Path) -> tuple:
    """
    The internal state that fully defines a path: bucket, parts, is_dir.
    """
    return p._bucket, p.parts, p._is_dir


def relpath(key: str) -> S3Path:
    """
    Build a relative path through the public API.
    """
    return S3Path("bucket", key).relative_to(S3Path("bucket"))


class BaseS3PathMixin(BaseTest):
    # --------------------------------------------------------------------------
    # 1. the four kinds of path
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(("bucket", "a", "b", "c"), id="one-part-per-arg"),
            pytest.param(("bucket/a/b/c",), id="single-string"),
            pytest.param(("bucket", "a/b/c"), id="key-in-one-arg"),
            pytest.param(("bucket", "/a/b/c"), id="leading-slash"),
            pytest.param((S3Path("//bucket//"), "/a/b/c"), id="bucket-s3path"),
            pytest.param(("s3://bucket/a/b/c",), id="s3-uri"),
            pytest.param(("arn:aws:s3:::bucket/a/b/c",), id="s3-arn"),
        ],
    )
    def test_constructor_object(self, args):
        """
        Equivalent ways to build an object path; ``/`` is collapsed.
        """
        p = S3Path(*args)
        assert state(p) == ("bucket", ["a", "b", "c"], False)
        assert p.is_file() is True
        assert p.uri == "s3://bucket/a/b/c"

    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(("bucket", "a", "b", "c/"), id="one-part-per-arg"),
            pytest.param(("bucket", "/a", "b", "c/"), id="leading-slash"),
            pytest.param(("//bucket", "a//b//c//"), id="repeated-slash"),
            pytest.param(("//bucket", "//a//b//c//"), id="repeated-slash-both"),
            pytest.param(("bucket//a//b//c//",), id="single-string"),
            pytest.param(("//bucket//a//b//c//",), id="single-string-slash"),
            pytest.param((S3Path("//bucket//"), "//a//b//c//"), id="bucket-s3path"),
            pytest.param(("bucket", "a/b/c", "/"), id="last-arg-is-slash"),
            pytest.param(("s3://bucket/a/b/c/",), id="s3-uri"),
            pytest.param(("arn:aws:s3:::bucket/a/b/c/",), id="s3-arn"),
        ],
    )
    def test_constructor_directory(self, args):
        """
        A trailing ``/`` on the last argument makes it a directory.
        """
        p = S3Path(*args)
        assert state(p) == ("bucket", ["a", "b", "c"], True)
        assert p.is_dir() is True
        assert p.uri == "s3://bucket/a/b/c/"

    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(("bucket",), id="name"),
            pytest.param(("/bucket",), id="leading-slash"),
            pytest.param(("//bucket//",), id="surrounding-slash"),
            pytest.param((S3Path("//bucket//"),), id="s3path"),
            pytest.param(("bucket", ""), id="empty-part"),
            pytest.param(("s3://bucket",), id="s3-uri"),
            pytest.param(("s3://bucket/",), id="s3-uri-slash"),
            pytest.param(("arn:aws:s3:::bucket",), id="s3-arn"),
        ],
    )
    def test_constructor_bucket_root(self, args):
        """
        A bucket without key is always a directory, even without trailing ``/``.
        """
        p = S3Path(*args)
        assert state(p) == ("bucket", [], True)
        assert p.is_bucket() is True
        assert p.uri == "s3://bucket/"

    @pytest.mark.parametrize(
        "args",
        [
            pytest.param((), id="no-args"),
            pytest.param((S3Path(),), id="void"),
            pytest.param((S3Path(), S3Path(), S3Path()), id="void-joined"),
            pytest.param((S3Path(), ""), id="void-and-empty-string"),
        ],
    )
    def test_constructor_void(self, args):
        """
        No bucket, no parts and no type: the void path.
        """
        p = S3Path(*args)
        assert state(p) == (None, [], None)
        assert p.is_void() is True

    # --------------------------------------------------------------------------
    # 2. S3 URI / ARN and the later arguments
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "partition",
        ["aws", "aws-cn", "aws-us-gov", "aws-eusc"],
    )
    def test_constructor_arn_partition(self, partition):
        """
        An ARN from any supported partition gives the same path.
        """
        p = S3Path(f"arn:{partition}:s3:::bucket/folder/file.txt")
        assert state(p) == ("bucket", ["folder", "file.txt"], False)
        p = S3Path(f"arn:{partition}:s3:::bucket/folder/subfolder/")
        assert state(p) == ("bucket", ["folder", "subfolder"], True)

    def test_constructor_skips_naming_rules(self):
        """
        Only the format is checked: a legacy bucket name (uppercase,
        underscore) and ``:`` in the key are kept, S3 is the judge of names.
        """
        p = S3Path("My_Legacy_Bucket", "2024-01-01T00:00:00.json")
        assert p.uri == "s3://My_Legacy_Bucket/2024-01-01T00:00:00.json"
        p = S3Path("s3://My_Legacy_Bucket/a:b.txt")
        assert p.uri == "s3://My_Legacy_Bucket/a:b.txt"

    @pytest.mark.parametrize(
        "args, parts",
        [
            pytest.param(("bucket", "a b", "中文"), ["a b", "中文"], id="space-unicode"),
            pytest.param(("bucket", ".", ".."), [".", ".."], id="dot-parts"),
            pytest.param(
                ("s3://bucket/a?versionId=1",), ["a?versionId=1"], id="query-like"
            ),
        ],
    )
    def test_constructor_special_chars_kept(self, args, parts):
        """
        Parts are taken literally: no normalization of ``.`` / ``..`` and
        no URL parsing, because they are all valid characters in an S3 key.
        """
        assert S3Path(*args).parts == parts

    @pytest.mark.parametrize(
        "part, parts",
        [
            pytest.param("s3://x/y", ["s3:", "x", "y"], id="s3-uri"),
            pytest.param("arn:aws:s3:::x/y", ["arn:aws:s3:::x", "y"], id="s3-arn"),
        ],
    )
    def test_constructor_later_uri_is_a_part(self, part, parts):
        """
        Only the first argument is parsed as URI / ARN; later ones are key parts.
        """
        assert S3Path("bucket", part).parts == parts

    @pytest.mark.parametrize(
        "args, expected",
        [
            pytest.param(
                ("bucket", relpath("x/y")),
                ("bucket", ["x", "y"], False),
                id="relpath-file-last",
            ),
            pytest.param(
                ("bucket", relpath("x/y/")),
                ("bucket", ["x", "y"], True),
                id="relpath-dir-last",
            ),
            pytest.param(
                ("bucket", relpath("x/"), "y"),
                ("bucket", ["x", "y"], False),
                id="relpath-then-file",
            ),
            pytest.param(
                (S3Path(), "a/"),
                (None, ["a"], True),
                id="void-then-dir",
            ),
            pytest.param(
                (S3Path("bucket", "a/"), "b"),
                ("bucket", ["a", "b"], False),
                id="dir-then-file",
            ),
            pytest.param(
                (S3Path("bucket", "a"),),
                ("bucket", ["a"], False),
                id="copy-file",
            ),
            pytest.param(
                (S3Path("bucket", "a/"),),
                ("bucket", ["a"], True),
                id="copy-dir",
            ),
        ],
    )
    def test_constructor_last_arg_decides_type(self, args, expected):
        """
        Later arguments append parts, and the last one decides file or directory.
        """
        assert state(S3Path(*args)) == expected

    @pytest.mark.parametrize(
        "args, expected",
        [
            pytest.param(
                ("bucket", "a/", ""),
                ("bucket", ["a"], True),
                id="dir-then-empty-string",
            ),
            pytest.param(
                ("bucket", "a", ""),
                ("bucket", ["a"], False),
                id="file-then-empty-string",
            ),
            pytest.param(
                ("bucket", "a", S3Path()),
                ("bucket", ["a"], False),
                id="file-then-void",
            ),
            pytest.param(
                ("bucket", "a/", S3Path(), ""),
                ("bucket", ["a"], True),
                id="dir-then-void-and-empty",
            ),
            pytest.param(
                (relpath("x/"), S3Path()),
                (None, ["x"], True),
                id="relpath-then-void",
            ),
        ],
    )
    def test_constructor_empty_args_ignored(self, args, expected):
        """
        ``""`` and a void path add nothing, so they must not change the type
        either; before 3.0 a trailing void path left the type as ``None``.
        """
        assert state(S3Path(*args)) == expected

    # --------------------------------------------------------------------------
    # 3. immutability
    # --------------------------------------------------------------------------
    def test_constructor_copy(self):
        """
        ``S3Path(p)`` builds a new, equal path.
        """
        p1 = S3Path("bucket", "a")
        p2 = S3Path(p1)
        assert p2 == p1
        assert p2 is not p1

    def test_from_parsed_parts_stores_tuple(self):
        """
        The parts are stored as a tuple copy, so the list passed in can not
        change the path afterwards, the same as ``pathlib``.
        """
        parts = ["a", "b"]
        p = S3Path._from_parsed_parts(bucket="bucket", parts=parts, is_dir=False)
        parts.append("c")
        assert p._parts == ("a", "b")
        assert p.uri == "s3://bucket/a/b"

    def test_parts_returns_copy(self):
        """
        Changing the returned list must not change the path, otherwise the
        cached hash goes stale and ``==`` / ``hash`` become wrong.
        """
        p = S3Path("bucket", "a")
        h = hash(p)
        p.parts.append("b")
        assert p.parts == ["a"]
        assert p.uri == "s3://bucket/a"
        assert hash(p) == h == hash(S3Path("bucket", "a"))

    def test_parts_is_read_only(self):
        """
        ``parts`` can not be assigned.
        """
        p = S3Path("bucket", "a")
        with pytest.raises(AttributeError, match="can't set attribute S3Path.parts"):
            p.parts = ["b"]

    # --------------------------------------------------------------------------
    # 4. invalid inputs
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "value, message",
        [
            pytest.param("https://bucket/key", "contains ':'", id="https"),
            pytest.param("s3:/bucket/key", "contains ':'", id="s3-one-slash"),
            pytest.param("b:c", "contains ':'", id="colon-in-bucket"),
            pytest.param("s3://", "bucket is empty", id="uri-no-bucket"),
            pytest.param("arn:aws:s3:::", "bucket is empty", id="arn-no-bucket"),
            pytest.param("", "bucket is empty", id="empty-string"),
            pytest.param("/", "bucket is empty", id="slash"),
            pytest.param(
                "arn:aws-iso:s3:::bucket/key",
                "must start with 'arn:{partition}:s3:::'",
                id="arn-unsupported-partition",
            ),
        ],
    )
    def test_constructor_invalid_format(self, value, message):
        """
        A malformed URI / ARN or an empty bucket is rejected instead of
        silently becoming a wrong path.
        """
        with pytest.raises(S3ValidationError, match=message):
            S3Path(value)

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param(1, id="int"),
            pytest.param(None, id="none"),
        ],
    )
    def test_constructor_first_arg_type_error(self, value):
        with pytest.raises(
            TypeError, match="the first argument has to be a str or an S3Path"
        ):
            S3Path(value, "a", "b", "c")

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param(1, id="int"),
            pytest.param(None, id="none"),
        ],
    )
    def test_constructor_later_arg_type_error(self, value):
        with pytest.raises(
            TypeError, match="it has to be a str or a relative S3Path, got"
        ):
            S3Path("bucket", "a", value)

    def test_constructor_later_arg_with_bucket(self):
        """
        Only the first argument can carry a bucket.
        """
        with pytest.raises(TypeError, match="relative S3Path \\(without bucket\\)"):
            S3Path(S3Path("bucket"), S3Path("a", "b", "c"))


# class Test(BaseS3PathMixin):
#     use_mock = False


class TestUseMock(BaseS3PathMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(__file__, module="s3pathlib.core.base", preview=False)

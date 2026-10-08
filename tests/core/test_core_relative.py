# -*- coding: utf-8 -*-

"""
Test the relative path API: ``make_relpath``, ``relative_to`` / ``-``,
``ensure_relpath`` / ``ensure_not_relpath``.

Test order:

1. ``make_relpath``: equivalent forms, the type rule, invalid parts;
2. ``relative_to``: normal use, the inverse of ``/`` (round trip), relative
   paths, the deprecated file base, then one case per ``raise``;
3. ``-`` is the same as ``relative_to``;
4. ``ensure_relpath`` / ``ensure_not_relpath`` on every kind of path.

``is_relpath`` for every kind of path is in the truth table of
``test_core_is_test.py``.

Any ``DeprecationWarning`` that a test does not expect with ``pytest.warns``
fails the test.
"""

import pytest

from s3pathlib.api import S3Path
from s3pathlib.exc import S3PathIsNotRelpathError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock import BaseTest

pytestmark = pytest.mark.filterwarnings("error::DeprecationWarning")

R = S3Path.make_relpath

FILE_BASE_WARNING = "is a file. Using a file as the base of relative_to is deprecated"


class RelativePathAPIMixin(BaseTest):
    module = "core.relative"

    # --------------------------------------------------------------------------
    # 1. make_relpath
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(("a", "b", "c"), id="one-part-per-arg"),
            pytest.param(("", "a", "b", "c", ""), id="empty-args"),
            pytest.param(("a/b/c",), id="single-string"),
            pytest.param(("", "a/b/c", ""), id="single-string-empty-args"),
            pytest.param(("/a//b/", "c"), id="extra-slashes"),
            pytest.param((R("a/"), "b", "c"), id="relpath-arg"),
        ],
    )
    def test_make_relpath_file(self, args):
        """
        Equivalent ways to build a relative file path; ``/`` is collapsed.
        """
        p = R(*args)
        assert (p.bucket, p.parts, p.is_file()) == (None, ["a", "b", "c"], True)

    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(("a", "b", "c/"), id="trailing-slash"),
            pytest.param(("a/b/c/", ""), id="then-empty"),
            pytest.param(("a/b/c", "/"), id="last-arg-is-slash"),
            pytest.param((R("a/b/c/"),), id="relpath-dir"),
        ],
    )
    def test_make_relpath_dir(self, args):
        """
        The last non-empty argument decides the type, the same rule as the
        ``S3Path`` constructor; before 3.0 a trailing ``"/"`` argument was
        ignored by ``make_relpath`` but not by the constructor.
        """
        p = R(*args)
        assert (p.bucket, p.parts, p.is_dir()) == (None, ["a", "b", "c"], True)
        assert p == S3Path(S3Path(), *args)

    @pytest.mark.parametrize(
        "args",
        [
            pytest.param((), id="no-args"),
            pytest.param(("",), id="empty-string"),
            pytest.param(("/",), id="slash"),
            pytest.param(("//", ""), id="slashes"),
            pytest.param((S3Path(),), id="void"),
        ],
    )
    def test_make_relpath_void(self, args):
        """
        No parts gives the void path, which has no type.
        """
        assert R(*args) == S3Path()
        assert R(*args).is_void() is True

    def test_make_relpath_does_not_parse_uri(self):
        """
        A relative path has no bucket, so ``s3://`` is just key parts.
        """
        assert R("s3://bucket/key").parts == ["s3:", "bucket", "key"]

    @pytest.mark.parametrize(
        "arg, message",
        [
            pytest.param(1, "got int: 1", id="int"),
            pytest.param(None, "got NoneType: None", id="none"),
            pytest.param(S3Path("b", "a"), "got an absolute path", id="absolute-path"),
        ],
    )
    def test_make_relpath_invalid_part(self, arg, message):
        with pytest.raises(TypeError, match=message):
            R("a", arg)

    # --------------------------------------------------------------------------
    # 2. relative_to
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "target, base, expected",
        [
            pytest.param(
                S3Path("bucket", "a/b/c"), S3Path("bucket", "a/"), R("b/c"), id="file"
            ),
            pytest.param(
                S3Path("bucket", "a/b/c/"), S3Path("bucket", "a/"), R("b/c/"), id="dir"
            ),
            pytest.param(
                S3Path("bucket", "a/b"), S3Path("bucket"), R("a/b"), id="bucket-file"
            ),
            pytest.param(
                S3Path("bucket", "a/b/"), S3Path("bucket"), R("a/b/"), id="bucket-dir"
            ),
            pytest.param(
                S3Path("bucket", "folder/a/b/c"),
                S3Path("bucket", "folder/"),
                R("a/b/c"),
                id="nested",
            ),
            pytest.param(
                S3Path("bucket", "a/"), S3Path("bucket", "a/"), S3Path(), id="same-dir"
            ),
            pytest.param(S3Path("bucket"), S3Path("bucket"), S3Path(), id="same-bucket"),
        ],
    )
    def test_relative_to(self, target, base, expected):
        """
        The relative path keeps the type of the target; a dir relative to
        itself is void.
        """
        assert target.relative_to(base) == expected

    @pytest.mark.parametrize(
        "target, base, expected",
        [
            pytest.param(R("a/b.txt"), R("a/"), R("b.txt"), id="relpath"),
            pytest.param(R("a/b/"), S3Path(), R("a/b/"), id="relpath-to-void"),
            pytest.param(R("a/"), R("a/"), S3Path(), id="same-relpath"),
            pytest.param(S3Path(), S3Path(), S3Path(), id="void-to-void"),
        ],
    )
    def test_relative_to_between_relpaths(self, target, base, expected):
        """
        A relative path can be relative to another relative path, as in
        ``pathlib``; before 3.0 it raised ``ValueError``.
        """
        assert target.relative_to(base) == expected

    @pytest.mark.parametrize(
        "target, base",
        [
            pytest.param(S3Path("b", "a/b/c.txt"), S3Path("b"), id="bucket-file"),
            pytest.param(S3Path("b", "a/b/"), S3Path("b"), id="bucket-dir"),
            pytest.param(S3Path("b", "a/b/c.txt"), S3Path("b", "a/"), id="dir-file"),
            pytest.param(S3Path("b", "a/b/"), S3Path("b", "a/"), id="dir-dir"),
            pytest.param(S3Path("b", "a/"), S3Path("b", "a/"), id="dir-same"),
            pytest.param(S3Path("b"), S3Path("b"), id="bucket-same"),
            pytest.param(R("a/b.txt"), R("a/"), id="relpath"),
            pytest.param(R("a/b.txt"), S3Path(), id="relpath-void"),
            pytest.param(S3Path(), S3Path(), id="void-same"),
        ],
    )
    def test_relative_to_is_inverse_of_join(self, target, base):
        """
        ``base / (target - base) == target`` for a dir base and any target
        under it: ``relative_to`` is the inverse of ``/``.
        """
        assert base / target.relative_to(base) == target

    @pytest.mark.parametrize(
        "target, base, expected",
        [
            pytest.param(
                S3Path("bucket", "a", "b", "c"),
                S3Path("bucket", "a"),
                R("b/c"),
                id="under-file",
            ),
            pytest.param(
                S3Path("bucket", "a", "b", "c/"),
                S3Path("bucket", "a"),
                R("b/c/"),
                id="dir-under-file",
            ),
            pytest.param(
                S3Path("bucket", "a"), S3Path("bucket", "a"), S3Path(), id="same-file"
            ),
            pytest.param(R("a/b"), R("a"), R("b"), id="relpath-file"),
        ],
    )
    def test_relative_to_file_base_is_deprecated(self, target, base, expected):
        """
        A file as the base still works in 3.x (the key is used as a prefix),
        but warns at the caller's line, because a file has no sub path; it
        will raise in 4.0.
        """
        with pytest.warns(DeprecationWarning, match=FILE_BASE_WARNING) as record:
            assert target.relative_to(base) == expected
        assert record[0].filename == __file__

    @pytest.mark.parametrize(
        "target, base, error, message",
        [
            pytest.param(
                S3Path("bucket1", "a"),
                S3Path("bucket2/"),
                ValueError,
                "they are in different buckets",
                id="different-bucket",
            ),
            pytest.param(
                S3Path("bucket", "a"),
                R("a/"),
                ValueError,
                "both have to be absolute paths, or both relative paths",
                id="absolute-to-relative",
            ),
            pytest.param(
                S3Path(),
                S3Path("bucket"),
                ValueError,
                "both have to be absolute paths, or both relative paths",
                id="void-to-absolute",
            ),
            pytest.param(
                S3Path("bucket", "a"),
                S3Path("bucket", "b/"),
                ValueError,
                "is not under",
                id="sibling",
            ),
            pytest.param(
                S3Path("bucket", "ab"),
                S3Path("bucket", "a/"),
                ValueError,
                "is not under",
                id="string-prefix-is-not-parent",
            ),
            pytest.param(
                S3Path("bucket", "a"),
                S3Path("bucket", "a/b/c/"),
                ValueError,
                "is not under",
                id="target-is-shorter",
            ),
            pytest.param(
                S3Path("bucket", "a"),
                S3Path("bucket", "a/"),
                ValueError,
                "one is a file and the other is a dir",
                id="file-to-same-dir",
            ),
            pytest.param(
                S3Path("bucket", "a/"),
                S3Path("bucket", "a"),
                ValueError,
                "one is a file and the other is a dir",
                id="dir-to-same-file",
            ),
            pytest.param(
                S3Path("bucket", "a"),
                "s3://bucket/",
                TypeError,
                "other has to be an S3Path, got str",
                id="not-s3path",
            ),
        ],
    )
    def test_relative_to_error(self, target, base, error, message):
        """
        Every case where no relative path leads from ``base`` to ``target``
        is rejected. "Same parts, one file and one dir" returned void before
        3.0, which broke ``base / (target - base) == target``.
        """
        with pytest.raises(error, match=message):
            target.relative_to(base)

    # --------------------------------------------------------------------------
    # 3. -
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "target, base",
        [
            pytest.param(S3Path("bucket", "folder/"), S3Path("bucket"), id="dir"),
            pytest.param(
                S3Path("bucket", "folder", "file.txt"),
                S3Path("bucket", "folder/"),
                id="file",
            ),
            pytest.param(R("a/b"), R("a/"), id="relpath"),
        ],
    )
    def test_sub_operator(self, target, base):
        """
        ``target - base`` is ``target.relative_to(base)``.
        """
        assert (target - base) == target.relative_to(base)

    def test_sub_operator_file_base_warns_at_caller(self):
        """
        The deprecation warning of ``-`` also points at the caller's line.
        """
        with pytest.warns(DeprecationWarning, match=FILE_BASE_WARNING) as record:
            _ = S3Path("bucket", "a/b") - S3Path("bucket", "a")
        assert record[0].filename == __file__

    def test_sub_operator_error(self):
        with pytest.raises(ValueError, match="is not under"):
            _ = S3Path("bucket", "a") - S3Path("bucket", "b/")

    # --------------------------------------------------------------------------
    # 4. ensure_relpath / ensure_not_relpath
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(S3Path("bucket", "file.txt"), id="file"),
            pytest.param(S3Path("bucket", "folder/"), id="dir"),
            pytest.param(S3Path("bucket"), id="bucket"),
        ],
    )
    def test_ensure_relpath_on_absolute_path(self, p):
        """
        An absolute path fails ``ensure_relpath`` and passes
        ``ensure_not_relpath``; the message says what it is.
        """
        with pytest.raises(S3PathIsNotRelpathError, match="is not a relpath"):
            p.ensure_relpath()
        p.ensure_not_relpath()

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(R("file.txt"), id="relpath-file"),
            pytest.param(R("folder/"), id="relpath-dir"),
            pytest.param(S3Path(), id="void"),
        ],
    )
    def test_ensure_relpath_on_relative_path(self, p):
        """
        A relative path, void included, passes ``ensure_relpath`` and fails
        ``ensure_not_relpath``; before 3.0 both messages were swapped.
        """
        p.ensure_relpath()
        with pytest.raises(
            S3PathTypeError, match="is a relative path, an absolute path is required"
        ):
            p.ensure_not_relpath()

    def test_ensure_errors_are_type_errors(self):
        """
        Both errors are still ``TypeError``, as before 3.0.
        """
        with pytest.raises(TypeError):
            S3Path("bucket").ensure_relpath()
        with pytest.raises(TypeError):
            S3Path().ensure_not_relpath()


# class Test(RelativePathAPIMixin):
#     use_mock = False


class TestUseMock(RelativePathAPIMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.relative",
        preview=False,
    )

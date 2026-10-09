# -*- coding: utf-8 -*-

"""
Test the attributes of ``S3Path``: ``parent``, ``parents``, ``is_parent_of``,
``is_prefix_of``, ``basename``, ``dirname``, ``fname``, ``ext``,
``abspath``, ``dirpath``, ``root``, and ``repr`` / ``str``.

Test order:

1. ``parent`` / ``parents``;
2. the name and path attributes on every kind of path, as a table;
3. ``fname`` / ``ext`` on tricky names;
4. ``is_parent_of`` and ``is_prefix_of``, then their errors;
5. ``repr`` / ``str``, and the attributes are read-only.
"""

import pytest

from s3pathlib.api import S3Path
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.exc import S3PathIsNotFolderError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock_aws import BaseTest

R = S3Path.make_relpath

FILE = S3Path("bucket", "folder", "file.txt")
DIRECTORY = S3Path("bucket", "folder/")
BUCKET = S3Path("bucket")
RELPATH = FILE.relative_to(BUCKET)  # folder/file.txt
VOID = S3Path()

NOT_A_FILE = (S3PathIsNotFileError, "is not a file, it has no {attr}!")
NO_BUCKET = (S3PathTypeError, "has no bucket, it has no {attr}!")


class AttributeAPIMixin(BaseTest):
    module = "core.attribute"

    # --------------------------------------------------------------------------
    # 1. parent / parents
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, expected",
        [
            pytest.param(FILE, ("bucket", ["folder"], True), id="file"),
            pytest.param(
                S3Path("bucket", "folder", "subfolder/"),
                ("bucket", ["folder"], True),
                id="dir",
            ),
            pytest.param(S3Path("bucket", "folder"), ("bucket", [], True), id="top-file"),
            pytest.param(S3Path("bucket", "file.txt"), ("bucket", [], True), id="top-file-2"),
            pytest.param(BUCKET, ("bucket", [], True), id="bucket-is-own-parent"),
            pytest.param(VOID, (None, [], None), id="void-is-own-parent"),
            pytest.param(R("a/b"), (None, ["a"], True), id="relpath"),
            pytest.param(R("a"), (None, [], None), id="relpath-one-part-file"),
            pytest.param(R("a/"), (None, [], None), id="relpath-one-part-dir"),
        ],
    )
    def test_parent(self, p, expected):
        """
        The parent is a dir; the parent of a single part relative path is
        void (like ``PurePosixPath("a").parent`` is ``"."``), not a "void with
        a type", which is not a valid state.
        """
        parent = p.parent
        assert (parent._bucket, parent.parts, parent._is_dir) == expected

    @pytest.mark.parametrize(
        "p, expected",
        [
            pytest.param(FILE, ["s3://bucket/folder/", "s3://bucket/"], id="file"),
            pytest.param(
                S3Path("bucket", "folder", "subfolder/"),
                ["s3://bucket/folder/", "s3://bucket/"],
                id="dir",
            ),
            pytest.param(S3Path("bucket", "folder"), ["s3://bucket/"], id="top-file"),
            pytest.param(S3Path("bucket", "file.txt"), ["s3://bucket/"], id="top-file-2"),
            pytest.param(BUCKET, [], id="bucket"),
        ],
    )
    def test_parents_absolute(self, p, expected):
        """
        The parents of an absolute path end with its bucket root.
        """
        assert [x.uri for x in p.parents] == expected

    @pytest.mark.parametrize(
        "p, expected",
        [
            pytest.param(
                S3Path("bucket", "folder", "subfolder", "file.txt").relative_to(BUCKET),
                [R("folder/subfolder/"), R("folder/"), VOID],
                id="relpath",
            ),
            pytest.param(R("a/"), [VOID], id="relpath-one-part"),
            pytest.param(VOID, [], id="void"),
        ],
    )
    def test_parents_relative(self, p, expected):
        """
        The parents of a relative path end with void, like
        ``PurePosixPath("a/b/c").parents`` ends with ``"."``.
        """
        assert p.parents == expected

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(S3Path("bucket", "a", "b", "c.txt"), id="absolute"),
            pytest.param(R("a/b/c.txt"), id="relative"),
        ],
    )
    def test_parents_are_chained_parents(self, p):
        """
        Every parent is the parent of the one before it.
        """
        parents = p.parents
        assert parents == [p.parent, p.parent.parent, p.parent.parent.parent]

    # --------------------------------------------------------------------------
    # 2. name and path attributes
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, attr, expected",
        [
            # basename: the last part, "" without parts
            pytest.param(FILE, "basename", "file.txt", id="file-basename"),
            pytest.param(DIRECTORY, "basename", "folder", id="dir-basename"),
            pytest.param(BUCKET, "basename", "", id="bucket-basename"),
            pytest.param(RELPATH, "basename", "file.txt", id="relpath-basename"),
            pytest.param(VOID, "basename", "", id="void-basename"),
            # dirname: the basename of the parent
            pytest.param(FILE, "dirname", "folder", id="file-dirname"),
            pytest.param(DIRECTORY, "dirname", "", id="dir-dirname"),
            pytest.param(BUCKET, "dirname", "", id="bucket-dirname"),
            pytest.param(RELPATH, "dirname", "folder", id="relpath-dirname"),
            pytest.param(VOID, "dirname", "", id="void-dirname"),
            # fname / ext: only for a file
            pytest.param(FILE, "fname", "file", id="file-fname"),
            pytest.param(DIRECTORY, "fname", NOT_A_FILE, id="dir-fname"),
            pytest.param(BUCKET, "fname", NOT_A_FILE, id="bucket-fname"),
            pytest.param(RELPATH, "fname", "file", id="relpath-fname"),
            pytest.param(VOID, "fname", NOT_A_FILE, id="void-fname"),
            pytest.param(FILE, "ext", ".txt", id="file-ext"),
            pytest.param(DIRECTORY, "ext", NOT_A_FILE, id="dir-ext"),
            pytest.param(BUCKET, "ext", NOT_A_FILE, id="bucket-ext"),
            pytest.param(RELPATH, "ext", ".txt", id="relpath-ext"),
            pytest.param(VOID, "ext", NOT_A_FILE, id="void-ext"),
            # abspath / dirpath / root: only with a bucket
            pytest.param(FILE, "abspath", "/folder/file.txt", id="file-abspath"),
            pytest.param(DIRECTORY, "abspath", "/folder/", id="dir-abspath"),
            pytest.param(BUCKET, "abspath", "/", id="bucket-abspath"),
            pytest.param(RELPATH, "abspath", NO_BUCKET, id="relpath-abspath"),
            pytest.param(VOID, "abspath", NO_BUCKET, id="void-abspath"),
            pytest.param(FILE, "dirpath", "/folder/", id="file-dirpath"),
            pytest.param(DIRECTORY, "dirpath", "/", id="dir-dirpath"),
            pytest.param(BUCKET, "dirpath", "/", id="bucket-dirpath"),
            pytest.param(RELPATH, "dirpath", NO_BUCKET, id="relpath-dirpath"),
            pytest.param(VOID, "dirpath", NO_BUCKET, id="void-dirpath"),
            pytest.param(FILE, "root", BUCKET, id="file-root"),
            pytest.param(DIRECTORY, "root", BUCKET, id="dir-root"),
            pytest.param(BUCKET, "root", BUCKET, id="bucket-root"),
            pytest.param(RELPATH, "root", NO_BUCKET, id="relpath-root"),
            pytest.param(VOID, "root", NO_BUCKET, id="void-root"),
        ],
    )
    def test_attribute(self, p, attr, expected):
        """
        The value of each attribute on each kind of path, or the error when
        it does not exist (before 3.0 ``fname`` / ``ext`` raised a bare
        ``TypeError`` or ``ValueError``).
        """
        if isinstance(expected, tuple):
            error, template = expected
            with pytest.raises(error, match=template.format(attr=attr)):
                getattr(p, attr)
        else:
            assert getattr(p, attr) == expected

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(FILE, id="file"),
            pytest.param(DIRECTORY, id="dir"),
            pytest.param(BUCKET, id="bucket"),
        ],
    )
    def test_abspath_is_slash_key(self, p):
        """
        ``abspath`` is the key with a leading ``/``, and ``dirpath`` is the
        ``abspath`` of the parent.
        """
        assert p.abspath == "/" + p.key
        assert p.dirpath == p.parent.abspath

    def test_attribute_errors_are_type_errors(self):
        """
        The errors are still ``TypeError``, as before 3.0 for a dir; for void
        ``fname`` / ``ext`` used to raise ``ValueError``.
        """
        with pytest.raises(TypeError):
            _ = DIRECTORY.ext
        with pytest.raises(TypeError):
            _ = VOID.fname
        with pytest.raises(TypeError):
            _ = RELPATH.abspath

    # --------------------------------------------------------------------------
    # 3. fname / ext on tricky names
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "basename, fname, ext",
        [
            pytest.param("file", "file", "", id="no-ext"),
            pytest.param("a.tar.gz", "a.tar", ".gz", id="double-ext"),
            pytest.param(".env", ".env", "", id="dotfile"),
            pytest.param(".env.bak", ".env", ".bak", id="dotfile-ext"),
            pytest.param("file.", "file.", "", id="trailing-dot"),
            pytest.param("a..b", "a.", ".b", id="double-dot"),
            pytest.param(".", ".", "", id="dot-only"),
        ],
    )
    def test_fname_ext(self, basename, fname, ext):
        """
        Only the last suffix is the extension and a leading dot is part of the
        name, the same as ``PurePath.stem`` / ``PurePath.suffix``;
        ``fname + ext`` is always the basename.
        """
        p = S3Path("bucket", basename)
        assert (p.fname, p.ext) == (fname, ext)
        assert p.fname + p.ext == basename

    # --------------------------------------------------------------------------
    # 4. is_parent_of / is_prefix_of
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "parent, child, expected",
        [
            pytest.param("bkt", "bkt/a", True, id="bucket-file"),
            pytest.param("bkt", "bkt/a/", True, id="bucket-dir"),
            pytest.param("bkt/a/", "bkt/a/b", True, id="dir-file"),
            pytest.param("bkt/a/", "bkt/a/b/", True, id="dir-dir"),
            pytest.param("bkt/a/", "bkt/a/b/c", True, id="grand-parent"),
            pytest.param("bkt", "bkt/a/b/c", True, id="bucket-grand-parent"),
            pytest.param("bkt", "bkt", True, id="bucket-is-own-parent"),
            pytest.param("bkt/a/", "bkt/a/", False, id="dir-is-not-own-parent"),
            pytest.param("bkt/a/b/", "bkt/a", False, id="child-is-shorter"),
            pytest.param("bkt/x/", "bkt/a/b", False, id="sibling"),
            pytest.param("bkt/a/b/", "bkt/a/x/y", False, id="cousin"),
            pytest.param("bkt/a/", "bkt/ab/c", False, id="string-prefix-is-not-parent"),
            pytest.param("bkt1/a/", "bkt2/a/b/", False, id="other-bucket"),
        ],
    )
    def test_is_parent_of(self, parent, child, expected):
        """
        ``a.is_parent_of(b)`` is ``a in b.parents``; before 3.0 only the
        direct parent was detected, not a grand parent.
        """
        assert S3Path(parent).is_parent_of(S3Path(child)) is expected

    @pytest.mark.parametrize(
        "parent, child, expected",
        [
            pytest.param(R("a/"), R("a/b/c"), True, id="relpath"),
            pytest.param(VOID, R("a/b"), True, id="void-is-parent-of-relpath"),
            pytest.param(VOID, VOID, True, id="void-is-own-parent"),
            pytest.param(R("a/"), R("x/b"), False, id="relpath-sibling"),
            pytest.param(VOID, S3Path("bkt/a"), False, id="void-absolute"),
            pytest.param(BUCKET, R("a"), False, id="absolute-relpath"),
        ],
    )
    def test_is_parent_of_relpath(self, parent, child, expected):
        """
        Relative paths work like absolute ones, and an absolute path and a
        relative path are never parents of each other; before 3.0 they
        raised ``TypeError``.
        """
        assert parent.is_parent_of(child) is expected

    @pytest.mark.parametrize(
        "prefix, other, expected",
        [
            pytest.param("bkt", "bkt/a", True, id="bucket-file"),
            pytest.param("bkt", "bkt/a/", True, id="bucket-dir"),
            pytest.param("bkt/a/", "bkt/a/b", True, id="dir-file"),
            pytest.param("bkt/a/", "bkt/a/b/", True, id="dir-dir"),
            pytest.param("bkt", "bkt", True, id="bucket-itself"),
            pytest.param("bkt/a", "bkt/a", True, id="file-itself"),
            pytest.param("bkt/a/", "bkt/a/", True, id="dir-itself"),
            pytest.param("bkt/a", "bkt/ab", True, id="string-prefix"),
            pytest.param("bkt/a", "bkt/a/b", True, id="file-key-prefix"),
            pytest.param("bkt/a/b/", "bkt/a", False, id="longer"),
            pytest.param("bkt/b", "bkt/c", False, id="sorted-before"),
            pytest.param("bkt/a/", "bkt/b", False, id="sorted-before-dir"),
            pytest.param("bkt/a/", "bkt/ab", False, id="dir-is-not-prefix-of-sibling"),
            pytest.param("bkt1/a/", "bkt2/a/b/", False, id="other-bucket"),
        ],
    )
    def test_is_prefix_of(self, prefix, other, expected):
        """
        A string prefix of the key, like the S3 ``Prefix``; before 3.0 it
        compared the URIs with ``<=``, so ``bkt/b`` was a "prefix" of
        ``bkt/c``.
        """
        assert S3Path(prefix).is_prefix_of(S3Path(other)) is expected

    @pytest.mark.parametrize(
        "prefix, other, expected",
        [
            pytest.param(R("a/"), R("a/b"), True, id="relpath"),
            pytest.param(VOID, R("a/b"), True, id="void"),
            pytest.param(R("a/"), R("b"), False, id="relpath-not"),
            pytest.param(VOID, S3Path("bkt/a"), False, id="void-absolute"),
            pytest.param(BUCKET, R("a"), False, id="absolute-relpath"),
        ],
    )
    def test_is_prefix_of_relpath(self, prefix, other, expected):
        assert prefix.is_prefix_of(other) is expected

    def test_is_parent_of_file(self):
        """
        A file can not be a parent.
        """
        with pytest.raises(
            S3PathIsNotFolderError, match="is a file, it can not be a parent dir!"
        ):
            S3Path("bkt/a").is_parent_of(S3Path("bkt/a/b/"))
        with pytest.raises(TypeError):  # still a TypeError, as before 3.0
            R("a").is_parent_of(R("a/b"))

    @pytest.mark.parametrize("method", ["is_parent_of", "is_prefix_of"])
    def test_other_is_not_s3path(self, method):
        with pytest.raises(TypeError, match="other has to be an S3Path, got str"):
            getattr(BUCKET, method)("s3://bucket/a")

    # --------------------------------------------------------------------------
    # 5. repr / str, read-only
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, expected",
        [
            pytest.param(FILE, "S3Path('s3://bucket/folder/file.txt')", id="file"),
            pytest.param(DIRECTORY, "S3Path('s3://bucket/folder/')", id="dir"),
            pytest.param(BUCKET, "S3Path('s3://bucket/')", id="bucket"),
            pytest.param(RELPATH, "S3RelPath('folder/file.txt')", id="relpath"),
            pytest.param(R("folder/"), "S3RelPath('folder/')", id="relpath-dir"),
            pytest.param(VOID, "S3VoidPath()", id="void"),
        ],
    )
    def test_repr_str(self, p, expected):
        """
        ``str`` is the same as ``repr``.
        """
        assert repr(p) == expected
        assert str(p) == expected

    @pytest.mark.parametrize(
        "attr",
        ["bucket", "basename", "dirname", "fname", "ext", "abspath", "dirpath"],
    )
    def test_attribute_is_read_only(self, attr):
        with pytest.raises(AttributeError, match=f"can't set attribute S3Path.{attr}"):
            setattr(FILE, attr, "x")


class TestMock(AttributeAPIMixin):
    use_mock = True


class TestRealAws(AttributeAPIMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.attribute",
        preview=False,
    )

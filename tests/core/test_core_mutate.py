# -*- coding: utf-8 -*-

"""
Test ``copy``, ``change``, ``to_dir`` and ``to_file``.

Test order:

1. ``copy`` on every kind of path;
2. ``change``: each argument on a file, then on the other kinds of path,
   combinations, boundaries, one case per ``raise``, and properties;
3. ``to_dir`` / ``to_file`` on every kind of path, and the round trip.
"""

import pytest

from s3pathlib.api import S3Path
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock_aws import BaseTest

R = S3Path.make_relpath

FILE = S3Path("bkt", "a", "b", "c.jpg")
DIRECTORY = S3Path("bkt", "a", "b/")
BUCKET = S3Path("bkt")
RELPATH_FILE = R("a/b/c.jpg")
RELPATH_DIR = R("a/b/")
VOID = S3Path()

ALL_KINDS = [
    pytest.param(FILE, id="file"),
    pytest.param(DIRECTORY, id="dir"),
    pytest.param(BUCKET, id="bucket"),
    pytest.param(RELPATH_FILE, id="relpath-file"),
    pytest.param(RELPATH_DIR, id="relpath-dir"),
    pytest.param(VOID, id="void"),
]


class MutateAPIMixin(BaseTest):
    module = "core.mutate"

    # --------------------------------------------------------------------------
    # 1. copy
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("p", ALL_KINDS)
    def test_copy(self, p):
        """
        A copy is equal but a new object, for every kind of path.
        """
        p1 = p.copy()
        assert p1 == p
        assert p1 is not p

    def test_copy_clears_metadata(self):
        """
        The metadata loaded from S3 is not copied.
        """
        p = self.s3dir_test.joinpath("file.txt")
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"hello")
        p.head_object()
        assert p.response is not None
        assert p.copy().response is None

    # --------------------------------------------------------------------------
    # 2. change
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "kwargs, uri",
        [
            pytest.param(dict(), "s3://bkt/a/b/c.jpg", id="nothing"),
            pytest.param(dict(new_bucket="bkt1"), "s3://bkt1/a/b/c.jpg", id="bucket"),
            pytest.param(
                dict(new_abspath="x/y/z.png"), "s3://bkt/x/y/z.png", id="abspath"
            ),
            pytest.param(dict(new_abspath="x/y/"), "s3://bkt/x/y/", id="abspath-dir"),
            pytest.param(dict(new_abspath=""), "s3://bkt/", id="abspath-empty"),
            pytest.param(dict(new_dirpath="x/y/"), "s3://bkt/x/y/c.jpg", id="dirpath"),
            pytest.param(
                dict(new_dirpath="x/y"), "s3://bkt/x/y/c.jpg", id="dirpath-no-slash"
            ),
            pytest.param(dict(new_dirpath=""), "s3://bkt/c.jpg", id="dirpath-root"),
            pytest.param(
                dict(new_dirpath="/"), "s3://bkt/c.jpg", id="dirpath-root-slash"
            ),
            pytest.param(
                dict(new_dirpath="/x/y/"),
                "s3://bkt/x/y/c.jpg",
                id="dirpath-leading-slash",
            ),
            pytest.param(dict(new_dirname="d"), "s3://bkt/a/d/c.jpg", id="dirname"),
            pytest.param(
                dict(new_dirname="d/"), "s3://bkt/a/d/c.jpg", id="dirname-slash"
            ),
            pytest.param(
                dict(new_basename="d.png"), "s3://bkt/a/b/d.png", id="basename"
            ),
            pytest.param(dict(new_basename="d/"), "s3://bkt/a/b/d/", id="basename-dir"),
            pytest.param(dict(new_fname="d"), "s3://bkt/a/b/d.jpg", id="fname"),
            pytest.param(dict(new_fname=""), "s3://bkt/a/b/.jpg", id="fname-empty"),
            pytest.param(dict(new_ext=".png"), "s3://bkt/a/b/c.png", id="ext"),
            pytest.param(dict(new_ext=""), "s3://bkt/a/b/c", id="ext-empty"),
            pytest.param(
                dict(new_fname="d", new_ext=".png"),
                "s3://bkt/a/b/d.png",
                id="fname-ext",
            ),
            pytest.param(
                dict(new_bucket="x", new_abspath="y.txt"),
                "s3://x/y.txt",
                id="bucket-abspath",
            ),
            pytest.param(
                dict(new_bucket="x", new_abspath="/y.txt"),
                "s3://x/y.txt",
                id="bucket-abspath-leading-slash",
            ),
            pytest.param(
                dict(new_dirname="d", new_ext=".png"),
                "s3://bkt/a/d/c.png",
                id="dirname-ext",
            ),
            pytest.param(
                dict(new_bucket="x", new_dirpath="p/", new_basename="q.txt"),
                "s3://x/p/q.txt",
                id="bucket-dirpath-basename",
            ),
        ],
    )
    def test_change_file(self, kwargs, uri):
        """
        Each argument replaces its part of a file path, and they combine.
        """
        assert FILE.change(**kwargs).uri == uri

    @pytest.mark.parametrize(
        "p, kwargs, expected",
        [
            pytest.param(DIRECTORY, dict(), DIRECTORY, id="dir-nothing"),
            pytest.param(
                DIRECTORY, dict(new_bucket="x"), S3Path("x", "a/b/"), id="dir-bucket"
            ),
            pytest.param(
                DIRECTORY,
                dict(new_dirname="z"),
                S3Path("bkt", "z/b/"),
                id="dir-dirname",
            ),
            pytest.param(
                DIRECTORY,
                dict(new_dirpath="p/q"),
                S3Path("bkt", "p/q/b/"),
                id="dir-dirpath",
            ),
            pytest.param(
                DIRECTORY,
                dict(new_basename="e/"),
                S3Path("bkt", "a/e/"),
                id="dir-basename",
            ),
            pytest.param(
                DIRECTORY,
                dict(new_basename="e"),
                S3Path("bkt", "a/e"),
                id="dir-to-file",
            ),
            pytest.param(BUCKET, dict(), BUCKET, id="bucket-nothing"),
            pytest.param(BUCKET, dict(new_bucket="x"), S3Path("x"), id="bucket-bucket"),
            pytest.param(
                BUCKET, dict(new_dirpath="p/"), S3Path("bkt", "p/"), id="bucket-dirpath"
            ),
            pytest.param(
                RELPATH_FILE,
                dict(new_basename="d.png"),
                R("a/b/d.png"),
                id="relpath-basename",
            ),
            pytest.param(
                RELPATH_FILE,
                dict(new_basename="d/"),
                R("a/b/d/"),
                id="relpath-basename-dir",
            ),
            pytest.param(
                RELPATH_FILE, dict(new_ext=".png"), R("a/b/c.png"), id="relpath-ext"
            ),
            pytest.param(
                RELPATH_FILE,
                dict(new_abspath="y.txt"),
                R("y.txt"),
                id="relpath-abspath",
            ),
            pytest.param(
                R("b.txt"),
                dict(new_basename="c.json"),
                R("c.json"),
                id="relpath-one-part",
            ),
            pytest.param(
                RELPATH_FILE,
                dict(new_bucket="x"),
                S3Path("x", "a/b/c.jpg"),
                id="relpath-to-absolute",
            ),
            pytest.param(
                RELPATH_DIR, dict(new_dirname="z"), R("z/b/"), id="relpath-dir-dirname"
            ),
            pytest.param(VOID, dict(), VOID, id="void-nothing"),
            pytest.param(VOID, dict(new_bucket="x"), S3Path("x"), id="void-bucket"),
            pytest.param(
                VOID, dict(new_basename="a.txt"), R("a.txt"), id="void-basename"
            ),
        ],
    )
    def test_change_other_kinds(self, p, kwargs, expected):
        """
        A dir stays a dir unless ``new_basename`` says otherwise, a bucket
        root and void keep having no last part, and a relative path stays
        relative unless ``new_bucket`` is given. ``change`` works on a dir and a
        bucket, not only on a file.
        """
        assert p.change(**kwargs) == expected

    @pytest.mark.parametrize(
        "p, kwargs, expected",
        [
            pytest.param(
                S3Path("b", "a.tar.gz"),
                dict(new_ext=".zip"),
                "a.tar.zip",
                id="double-ext",
            ),
            pytest.param(
                S3Path("b", "a.tar.gz"),
                dict(new_fname="x"),
                "x.gz",
                id="double-ext-fname",
            ),
            pytest.param(
                S3Path("b", "README"), dict(new_ext=".md"), "README.md", id="no-ext"
            ),
            pytest.param(S3Path("b", ".env"), dict(new_fname="x"), "x", id="dotfile"),
            pytest.param(
                S3Path("b", ".env"), dict(new_ext=".bak"), ".env.bak", id="dotfile-ext"
            ),
        ],
    )
    def test_change_name_boundaries(self, p, kwargs, expected):
        """
        Only the last extension is replaced, and a leading dot is part of the
        name, the same as ``fname`` and ``ext``.
        """
        assert p.change(**kwargs).basename == expected

    @pytest.mark.parametrize(
        "p, kwargs, message",
        [
            pytest.param(
                FILE,
                dict(new_abspath="x/y/z.png", new_basename="file.txt"),
                "new_abspath replaces the whole key, it can not be used with new_basename",
                id="abspath-basename",
            ),
            pytest.param(
                FILE,
                dict(new_abspath="x", new_dirname="d", new_ext=".y"),
                "it can not be used with new_dirname, new_ext",
                id="abspath-many",
            ),
            pytest.param(
                FILE,
                dict(new_dirpath="x", new_dirname="y"),
                "pass new_dirpath or new_dirname, not both",
                id="dirpath-dirname",
            ),
            pytest.param(
                VOID,
                dict(new_dirpath="x", new_dirname="y"),
                "pass new_dirpath or new_dirname, not both",
                id="dirpath-dirname-void",
            ),
            pytest.param(
                S3Path("bkt", "top.jpg"),
                dict(new_dirname="z"),
                "has no parent dir to rename, use new_dirpath",
                id="dirname-top-level",
            ),
            pytest.param(
                BUCKET,
                dict(new_dirname="z"),
                "has no parent dir to rename",
                id="dirname-bucket",
            ),
            pytest.param(
                FILE,
                dict(new_basename="x", new_fname="y", new_ext=".zip"),
                "pass new_basename, or new_fname / new_ext, not both",
                id="basename-fname",
            ),
            pytest.param(
                FILE,
                dict(new_basename=""),
                "new_basename can not be empty",
                id="basename-empty",
            ),
            pytest.param(
                DIRECTORY,
                dict(new_ext=".x"),
                "new_fname and new_ext only work on a file",
                id="ext-on-dir",
            ),
            pytest.param(
                BUCKET,
                dict(new_fname="x"),
                "new_fname and new_ext only work on a file",
                id="fname-on-bucket",
            ),
            pytest.param(
                VOID,
                dict(new_fname="x"),
                "new_fname and new_ext only work on a file",
                id="fname-on-void",
            ),
            pytest.param(
                FILE,
                dict(new_fname="x/y"),
                "new_fname can not contain '/'",
                id="fname-slash",
            ),
            pytest.param(
                FILE,
                dict(new_ext=".a/b"),
                "new_ext can not contain '/'",
                id="ext-slash",
            ),
            pytest.param(
                FILE,
                dict(new_ext="png"),
                "has to be empty, or '.' followed by",
                id="ext-no-dot",
            ),
            pytest.param(
                FILE,
                dict(new_ext="."),
                "has to be empty, or '.' followed by",
                id="ext-dot-only",
            ),
            pytest.param(
                FILE,
                dict(new_fname="", new_ext=""),
                "new_fname and new_ext make an empty file name",
                id="empty-name",
            ),
        ],
    )
    def test_change_error(self, p, kwargs, message):
        """
        Conflicting or invalid arguments are rejected instead of silently
        giving another path (e.g. ``new_ext="png"`` would give ``cpng``, and
        ``new_dirname`` on a top level file would add a dir).
        """
        with pytest.raises(ValueError, match=message):
            p.change(**kwargs)

    @pytest.mark.parametrize("p", ALL_KINDS)
    def test_change_nothing_is_copy(self, p):
        """
        ``change()`` with no argument is ``copy()``, for every kind of path.
        """
        p1 = p.change()
        assert p1 == p.copy()
        assert p1 is not p

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param(dict(new_basename="c.jpg"), id="basename"),
            pytest.param(dict(new_fname="c", new_ext=".jpg"), id="fname-ext"),
            pytest.param(dict(new_dirname="b"), id="dirname"),
            pytest.param(dict(new_dirpath="a/b/"), id="dirpath"),
            pytest.param(dict(new_abspath="a/b/c.jpg"), id="abspath"),
            pytest.param(dict(new_bucket="bkt"), id="bucket"),
        ],
    )
    def test_change_to_same_value(self, kwargs):
        """
        Replacing a part with its current value gives the same path, so
        each argument replaces exactly its own part.
        """
        assert FILE.change(**kwargs) == FILE

    # --------------------------------------------------------------------------
    # 3. to_dir / to_file
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, expected",
        [
            pytest.param(FILE, S3Path("bkt", "a/b/c.jpg/"), id="file"),
            pytest.param(DIRECTORY, DIRECTORY, id="dir"),
            pytest.param(BUCKET, BUCKET, id="bucket"),
            pytest.param(RELPATH_FILE, R("a/b/c.jpg/"), id="relpath-file"),
            pytest.param(RELPATH_DIR, RELPATH_DIR, id="relpath-dir"),
        ],
    )
    def test_to_dir(self, p, expected):
        """
        A file becomes the dir with the same parts; a dir is copied.
        """
        p1 = p.to_dir()
        assert p1 == expected
        assert p1.is_dir() is True
        assert p1 is not p

    @pytest.mark.parametrize(
        "p, expected",
        [
            pytest.param(FILE, FILE, id="file"),
            pytest.param(DIRECTORY, S3Path("bkt", "a/b"), id="dir"),
            pytest.param(RELPATH_FILE, RELPATH_FILE, id="relpath-file"),
            pytest.param(RELPATH_DIR, R("a/b"), id="relpath-dir"),
        ],
    )
    def test_to_file(self, p, expected):
        """
        A dir becomes the file with the same parts; a file is copied.
        """
        p1 = p.to_file()
        assert p1 == expected
        assert p1.is_file() is True
        assert p1 is not p

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(FILE, id="file"),
            pytest.param(RELPATH_FILE, id="relpath-file"),
        ],
    )
    def test_to_dir_to_file_round_trip(self, p):
        assert p.to_dir().to_file() == p
        assert p.to_dir().to_file().to_dir() == p.to_dir()

    @pytest.mark.parametrize(
        "method, message",
        [
            pytest.param("to_dir", "can not be converted to a dir", id="to_dir"),
            pytest.param("to_file", "can not be converted to a file", id="to_file"),
        ],
    )
    def test_to_dir_to_file_void(self, method, message):
        """
        Void is neither a file nor a dir.
        """
        with pytest.raises(ValueError, match=f"neither a file nor a dir, it {message}"):
            getattr(VOID, method)()

    def test_to_file_bucket(self):
        """
        A bucket root is always a dir: "a bucket that is a file" is not a valid
        state.
        """
        with pytest.raises(
            S3PathIsNotFileError, match="is a bucket root, it can not be converted"
        ):
            BUCKET.to_file()
        with pytest.raises(TypeError):  # S3PathIsNotFileError is a TypeError
            BUCKET.to_file()

    def test_change_takes_abspath_and_dirpath_of_another_path(self):
        """
        ``abspath`` / ``dirpath`` start with ``/``; ``change`` takes them as
        they are, as its docstring says.
        """
        other = S3Path("x", "p", "q", "r.txt")
        assert FILE.change(new_dirpath=other.dirpath) == S3Path(
            "bkt", "p", "q", "c.jpg"
        )
        assert FILE.change(new_bucket="x", new_abspath=other.abspath) == other

    @pytest.mark.parametrize(
        "call, message",
        [
            pytest.param(
                lambda: DIRECTORY.change(new_fname="x"),
                "only work on a file, 's3://bkt/a/b/' is not a file",
                id="absolute",
            ),
            pytest.param(
                lambda: RELPATH_DIR.change(new_fname="x"),
                r"only work on a file, S3RelPath\('a/b/'\) is not a file",
                id="relpath",
            ),
            pytest.param(
                lambda: BUCKET.to_file(),
                "^'s3://bkt/' is a bucket root",
                id="bucket",
            ),
            pytest.param(
                lambda: VOID.to_dir(),
                r"^S3VoidPath\(\) is neither a file nor a dir",
                id="void",
            ),
        ],
    )
    def test_error_shows_path_label(self, call, message):
        """
        Errors show an absolute path as its URI and a relative path as its
        repr, like every other error of s3pathlib.
        """
        with pytest.raises((ValueError, TypeError), match=message):
            call()


class TestMock(MutateAPIMixin):
    use_mock = True


class TestRealAws(MutateAPIMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.mutate",
        preview=False,
    )

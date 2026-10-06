# -*- coding: utf-8 -*-

"""
Test ``joinpath`` and the ``/`` operator.

Test order:

1. ``joinpath`` onto a dir (bucket, folder, relative dir, void): string parts,
   relative paths, the type rule;
2. ``/``, including a list on the right and chains;
3. joining onto a file: deprecated, still works, warns at the caller's line;
4. invalid parts, one case per ``raise``.

Any ``DeprecationWarning`` that a test does not expect with ``pytest.warns``
fails the test.
"""

import pytest

from s3pathlib.api import S3Path
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock import BaseTest

pytestmark = pytest.mark.filterwarnings("error::DeprecationWarning")

R = S3Path.make_relpath

BUCKET = S3Path("bucket")
DIRECTORY = S3Path("bucket", "folder/")
FILE = S3Path("bucket", "folder", "file.txt")
RELPATH_FILE = FILE.relative_to(BUCKET)  # folder/file.txt
RELPATH_DIR = DIRECTORY.relative_to(BUCKET)  # folder/

FILE_WARNING = "is a file. Joining onto a file is deprecated"


class JoinPathAPIMixin(BaseTest):
    module = "core.joinpath"

    # --------------------------------------------------------------------------
    # 1. joinpath onto a dir
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "args, uri",
        [
            pytest.param(("file.txt",), "s3://bucket/file.txt", id="file"),
            pytest.param(("/file.txt",), "s3://bucket/file.txt", id="leading-slash"),
            pytest.param(("folder/",), "s3://bucket/folder/", id="dir"),
            pytest.param(("/folder/",), "s3://bucket/folder/", id="dir-leading-slash"),
            pytest.param(
                ("folder", "file.txt"), "s3://bucket/folder/file.txt", id="many-parts"
            ),
            pytest.param(
                ("/folder/", "/file.txt"),
                "s3://bucket/folder/file.txt",
                id="many-parts-extra-slashes",
            ),
            pytest.param(("folder", "/"), "s3://bucket/folder/", id="last-is-slash"),
            pytest.param(("folder/", ""), "s3://bucket/folder/", id="last-is-empty"),
            pytest.param((RELPATH_DIR,), "s3://bucket/folder/", id="relpath-dir"),
            pytest.param(
                ("data", RELPATH_DIR, "file.txt"),
                "s3://bucket/data/folder/file.txt",
                id="mixed",
            ),
            pytest.param((), "s3://bucket/", id="nothing"),
        ],
    )
    def test_joinpath_onto_bucket(self, args, uri):
        """
        Leading and repeated ``/`` are collapsed, and the last non-empty
        argument decides whether the result is a file or a dir.
        """
        assert BUCKET.joinpath(*args).uri == uri

    @pytest.mark.parametrize(
        "base, args, expected",
        [
            pytest.param(DIRECTORY, ("file.txt",), FILE, id="folder"),
            pytest.param(R("a/"), ("b.txt",), R("a/b.txt"), id="relpath-dir"),
            pytest.param(S3Path(), ("a", "b/"), R("a/b/"), id="void"),
            pytest.param(S3Path(), (RELPATH_FILE,), RELPATH_FILE, id="void-relpath"),
            pytest.param(DIRECTORY, (S3Path(),), DIRECTORY, id="void-on-the-right"),
        ],
    )
    def test_joinpath_onto_other_dirs(self, base, args, expected):
        """
        Any dir can be joined onto: a folder, a relative dir, and void, which
        is the identity of joining.
        """
        assert base.joinpath(*args) == expected

    def test_joinpath_is_constructor(self):
        """
        ``p.joinpath(*parts)`` is ``S3Path(p, *parts)``.
        """
        args = ("data", RELPATH_DIR, "file.txt")
        assert BUCKET.joinpath(*args) == S3Path(BUCKET, *args)

    # --------------------------------------------------------------------------
    # 2. /
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "make, expected",
        [
            pytest.param(lambda: BUCKET / "folder/", DIRECTORY, id="dir"),
            pytest.param(lambda: BUCKET / ["folder/"], DIRECTORY, id="list-dir"),
            pytest.param(lambda: BUCKET / ["folder", "/"], DIRECTORY, id="list-slash"),
            pytest.param(lambda: BUCKET / "folder/" / "file.txt", FILE, id="chain"),
            pytest.param(
                lambda: BUCKET / "folder/" / "/file.txt", FILE, id="chain-slash"
            ),
            pytest.param(lambda: BUCKET / ["folder", "file.txt"], FILE, id="list"),
            pytest.param(lambda: BUCKET / ["folder/", "file.txt"], FILE, id="list-2"),
            pytest.param(lambda: BUCKET / ["folder/", "/file.txt"], FILE, id="list-3"),
            pytest.param(lambda: BUCKET / RELPATH_FILE, FILE, id="relpath"),
            pytest.param(
                lambda: BUCKET / [RELPATH_DIR, R("file.txt")], FILE, id="list-relpaths"
            ),
            pytest.param(
                lambda: BUCKET / (RELPATH_DIR / R("file.txt")),
                FILE,
                id="relpath-joined-first",
            ),
            pytest.param(
                lambda: S3Path("new-bucket") / RELPATH_FILE,
                S3Path("new-bucket", "folder", "file.txt"),
                id="relpath-to-other-bucket",
            ),
            pytest.param(lambda: S3Path() / "folder/", R("folder/"), id="void"),
        ],
    )
    def test_divide_operator(self, make, expected):
        """
        ``p / x`` is ``p.joinpath(x)``, and ``p / [x, y]`` is
        ``p.joinpath(x, y)``: a list is joined at once, so its middle parts do
        not have to be dirs.
        """
        assert make() == expected

    @pytest.mark.parametrize(
        "make",
        [
            pytest.param(lambda: BUCKET / "folder", id="no-slash"),
            pytest.param(lambda: BUCKET / ["folder"], id="list-no-slash"),
        ],
    )
    def test_divide_operator_file_result(self, make):
        """
        Without the trailing ``/`` the result is a file, not the dir.
        """
        assert make() != DIRECTORY
        assert make().is_file() is True

    # --------------------------------------------------------------------------
    # 3. joining onto a file (deprecated)
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "make, uri",
        [
            pytest.param(
                lambda: BUCKET / "folder" / "file.txt",
                "s3://bucket/folder/file.txt",
                id="chain-without-slash",
            ),
            pytest.param(
                lambda: FILE.joinpath("/"), "s3://bucket/folder/file.txt/", id="slash"
            ),
            pytest.param(lambda: FILE / "/", "s3://bucket/folder/file.txt/", id="div-slash"),
            pytest.param(
                lambda: FILE.joinpath("subfolder", "/"),
                "s3://bucket/folder/file.txt/subfolder/",
                id="parts",
            ),
            pytest.param(
                lambda: FILE / ["subfolder", "/"],
                "s3://bucket/folder/file.txt/subfolder/",
                id="div-list",
            ),
        ],
    )
    def test_join_onto_file_is_deprecated(self, make, uri):
        """
        Joining onto a file still uses its key as a prefix in 3.x, but warns:
        a file has no sub path. It will raise in 4.0.
        """
        with pytest.warns(DeprecationWarning, match=FILE_WARNING):
            assert make().uri == uri

    @pytest.mark.parametrize(
        "make",
        [
            pytest.param(lambda: FILE.joinpath("x"), id="joinpath"),
            pytest.param(lambda: FILE / "x", id="div"),
        ],
    )
    def test_join_onto_file_warns_at_caller(self, make):
        """
        The warning points at the caller's line, for both ``joinpath`` and
        ``/``, and tells how to fix it.
        """
        with pytest.warns(DeprecationWarning) as record:
            make()
        assert record[0].filename == __file__
        message = str(record[0].message)
        assert "end the folder with '/'" in message
        assert 'join all parts at once (e.g. .joinpath("folder", "file.txt"))' in message

    @pytest.mark.parametrize(
        "args",
        [
            pytest.param((), id="nothing"),
            pytest.param(("",), id="empty-string"),
            pytest.param((S3Path(),), id="void"),
        ],
    )
    def test_join_nothing_onto_file(self, args):
        """
        Joining nothing onto a file gives the same file, so it does not warn.
        """
        assert FILE.joinpath(*args) == FILE

    # --------------------------------------------------------------------------
    # 4. invalid parts
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "make, message",
        [
            pytest.param(
                lambda: S3Path("bucket1").joinpath(S3Path("bucket2")),
                "got an absolute path",
                id="absolute-path",
            ),
            pytest.param(
                lambda: DIRECTORY.joinpath(FILE, FILE.parent),
                "got an absolute path",
                id="absolute-paths",
            ),
            pytest.param(lambda: DIRECTORY.joinpath(1), "got int: 1", id="int"),
            pytest.param(lambda: R("a/") / BUCKET, "got an absolute path", id="relpath-div-absolute"),
            pytest.param(lambda: S3Path() / BUCKET, "got an absolute path", id="void-div-absolute"),
            pytest.param(lambda: BUCKET / [1], "got int: 1", id="list-int"),
        ],
    )
    def test_join_invalid_part(self, make, message):
        """
        Only str parts and relative paths can be joined: an absolute path on
        the right would replace the bucket.
        """
        with pytest.raises(TypeError, match=message):
            make()

    def test_join_invalid_part_onto_file_does_not_warn(self):
        """
        An invalid part raises before any deprecation warning.
        """
        with pytest.raises(TypeError, match="got an absolute path"):
            FILE.joinpath(BUCKET)


# class Test(JoinPathAPIMixin):
#     use_mock = False


class TestUseMock(JoinPathAPIMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(__file__, module="s3pathlib.core.joinpath", preview=False)

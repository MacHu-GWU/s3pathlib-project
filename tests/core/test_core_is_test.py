# -*- coding: utf-8 -*-

import pytest

from s3pathlib.core import S3Path
from s3pathlib.tests import run_cov_test


class TestIsTestAPIMixin:
    def _test_type_test(self):
        """
        Test if the instance is a ...

        - is_dir()
        - is_file()
        - is_bucket()
        - is_void()
        """
        # s3 object
        p = S3Path("bucket", "file.txt")
        assert p.is_void() is False
        assert p.is_dir() is False
        assert p.is_file() is True
        assert p.is_bucket() is False

        p.ensure_file()
        with pytest.raises(Exception):
            p.ensure_not_file()
        with pytest.raises(Exception):
            p.ensure_dir()
        p.ensure_not_dir()

        # s3 directory
        p = S3Path("bucket", "folder/")
        assert p.is_void() is False
        assert p.is_dir() is True
        assert p.is_file() is False
        assert p.is_bucket() is False
        assert p.is_delete_marker() is False

        with pytest.raises(Exception):
            p.ensure_file()
        p.ensure_not_file()
        p.ensure_dir()
        with pytest.raises(Exception):
            p.ensure_not_dir()

        # s3 bucket
        p = S3Path("bucket")
        assert p.is_void() is False
        assert p.is_dir() is True
        assert p.is_file() is False
        assert p.is_bucket() is True
        assert p.is_delete_marker() is False

        # void path
        p = S3Path()
        assert p.is_void() is True
        assert p.is_dir() is False
        assert p.is_file() is False
        assert p.is_bucket() is False

    def test(self):
        self._test_type_test()

    @pytest.mark.parametrize(
        "p, expected",
        [
            # is_void, is_relpath, is_bucket, is_dir, is_file
            pytest.param(
                S3Path("bucket", "file.txt"),
                (False, False, False, False, True),
                id="file",
            ),
            pytest.param(
                S3Path("bucket", "folder/"),
                (False, False, False, True, False),
                id="dir",
            ),
            pytest.param(
                S3Path("bucket"),
                (False, False, True, True, False),
                id="bucket",
            ),
            pytest.param(
                S3Path.make_relpath("folder/file.txt"),
                (False, True, False, False, True),
                id="relpath-file",
            ),
            pytest.param(
                S3Path.make_relpath("folder/"),
                (False, True, False, True, False),
                id="relpath-dir",
            ),
            pytest.param(
                S3Path(),
                (True, True, False, False, False),
                id="void",
            ),
        ],
    )
    def test_is_truth_table(self, p, expected):
        """
        The full truth table of the six valid states (see
        ``s3pathlib.core.base``): a bucket is also a dir, void is also a
        relpath, and void is neither a file nor a dir.
        """
        actual = (p.is_void(), p.is_relpath(), p.is_bucket(), p.is_dir(), p.is_file())
        assert actual == expected

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(S3Path.make_relpath("a").parent, id="relpath-parent"),
            pytest.param(S3Path(S3Path(), "/"), id="void-and-slash"),
            pytest.param(S3Path("b", "a/").relative_to(S3Path("b", "a/")), id="p-minus-p"),
            pytest.param(S3Path.make_relpath("/"), id="make-relpath-slash"),
        ],
    )
    def test_is_void_from_operations(self, p):
        """
        Every operation that ends with no bucket and no parts gives the same
        void path, which is also a relpath; before 3.0 some of them gave a
        "void with a type" for which ``is_relpath()`` was False.
        """
        assert p == S3Path()
        assert p.is_void() is True
        assert p.is_relpath() is True
        assert p.is_dir() is False


if __name__ == "__main__":
    run_cov_test(__file__, module="s3pathlib.core.is_test", preview=False)

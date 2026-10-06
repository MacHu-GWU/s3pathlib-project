# -*- coding: utf-8 -*-

import pytest
from s3pathlib.core import S3Path
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.tests import run_cov_test


class TestMutateAPIMixin:
    def test_copy(self):
        p1 = S3Path()
        p2 = p1.copy()
        assert p1 is not p2

    def test_change(self):
        p = S3Path("bkt", "a", "b", "c.jpg")

        p1 = p.change()
        assert p1 == p
        assert p1 is not p

        p1 = p.change(new_bucket="bkt1")
        assert p1.uri == "s3://bkt1/a/b/c.jpg"

        p1 = p.change(new_abspath="x/y/z.png")
        assert p1.uri == "s3://bkt/x/y/z.png"

        p1 = p.change(new_ext=".png")
        assert p1.uri == "s3://bkt/a/b/c.png"

        p1 = p.change(new_fname="d")
        assert p1.uri == "s3://bkt/a/b/d.jpg"

        p1 = p.change(new_basename="d.png")
        assert p1.uri == "s3://bkt/a/b/d.png"

        p1 = p.change(new_basename="d/")
        assert p1.uri == "s3://bkt/a/b/d/"
        assert p1.is_dir()

        p1 = p.change(new_dirname="d/")
        assert p1.uri == "s3://bkt/a/d/c.jpg"

        p1 = p.change(new_dirpath="x/y/")
        assert p1.uri == "s3://bkt/x/y/c.jpg"

        p1 = S3Path.make_relpath("a/b/c.jpg")
        p2 = p1.change(new_basename="d.png")
        assert p2._bucket is None
        assert p2.parts == ["a", "b", "d.png"]
        assert p2._is_dir is False

        p2 = p1.change(new_basename="d/")
        assert p2._bucket is None
        assert p2.parts == ["a", "b", "d"]
        assert p2._is_dir is True

        with pytest.raises(ValueError):
            p1 = S3Path()
            p1.change(new_dirpath="x", new_dirname="y")

        with pytest.raises(ValueError):
            p.change(new_abspath="x/y/z.png", new_basename="file.txt")

        with pytest.raises(ValueError):
            p.change(new_dirpath="x", new_dirname="y")

        with pytest.raises(ValueError):
            p.change(new_basename="x", new_fname="y", new_ext=".zip")

    def test_to_dir(self):
        p1 = S3Path("bkt", "a/")
        p2 = p1.to_dir()
        assert p2.is_dir()
        assert p2 == p1
        assert p2 is not p1

        p3 = S3Path("bkt", "a")
        p4 = p3.to_dir()
        assert p4.is_dir()
        assert p4 == p1

        with pytest.raises(ValueError):
            _ = S3Path().to_dir()

    def test_to_file(self):
        p1 = S3Path("bkt", "a")
        p2 = p1.to_file()
        assert p2.is_file()
        assert p2 == p1
        assert p2 is not p1

        p3 = S3Path("bkt", "a/")
        p4 = p3.to_file()
        assert p4.is_file()
        assert p4 == p1

        with pytest.raises(ValueError):
            _ = S3Path().to_file()

    def test_to_file_relpath(self):
        """
        A relative dir becomes a relative file.
        """
        p = S3Path.make_relpath("a/").to_file()
        assert p == S3Path.make_relpath("a")
        assert p.is_file() is True

    def test_to_file_bucket(self):
        """
        A bucket root is always a dir; before 3.0 ``to_file()`` returned a
        "bucket that is a file", which is not a valid state.
        """
        with pytest.raises(
            S3PathIsNotFileError, match="is a bucket root, it can not be converted"
        ):
            S3Path("bkt").to_file()
        with pytest.raises(TypeError):  # S3PathIsNotFileError is a TypeError
            S3Path("bkt").to_file()

    @pytest.mark.parametrize(
        "p, expected",
        [
            pytest.param(
                S3Path.make_relpath("a/b.txt"),
                S3Path.make_relpath("a/c.json"),
                id="relpath",
            ),
            pytest.param(
                S3Path.make_relpath("b.txt"), S3Path.make_relpath("c.json"), id="one-part"
            ),
        ],
    )
    def test_change_relpath(self, p, expected):
        """
        Changing a relative path keeps it relative: it has no bucket.
        """
        p1 = p.change(new_basename="c.json")
        assert p1 == expected
        assert p1.is_relpath() is True
        assert p1.bucket is None


if __name__ == "__main__":
    run_cov_test(__file__, module="s3pathlib.core.mutate", preview=False)

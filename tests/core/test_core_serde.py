# -*- coding: utf-8 -*-

import pytest

from s3pathlib.core import S3Path
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test


class TestSerdeAPIMixin:
    def test_serialization(self):
        p1 = S3Path("bucket", "folder", "file.txt")
        assert p1.to_dict() == {
            "bucket": "bucket",
            "parts": ["folder", "file.txt"],
            "is_dir": False,
        }
        p2 = S3Path.from_dict(p1.to_dict())
        assert p1 == p2
        assert p1 is not p2

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(S3Path("bucket", "folder/"), id="dir"),
            pytest.param(S3Path("bucket"), id="bucket"),
            pytest.param(S3Path.make_relpath("a/b.txt"), id="relpath"),
            pytest.param(S3Path(), id="void"),
        ],
    )
    def test_round_trip(self, p):
        """
        Every valid state survives ``to_dict`` -> ``from_dict``.
        """
        assert S3Path.from_dict(p.to_dict()) == p

    @pytest.mark.parametrize(
        "dct, message",
        [
            pytest.param(
                dict(bucket="b", parts=[], is_dir=False),
                "a bucket root must be a dir",
                id="bucket-is-file",
            ),
            pytest.param(
                dict(bucket="b", parts=["a"], is_dir=None),
                "must be a file or a dir",
                id="no-type",
            ),
            pytest.param(
                dict(bucket="", parts=["a"], is_dir=False),
                "bucket must not be empty",
                id="empty-bucket",
            ),
            pytest.param(
                dict(bucket="b", parts=["a/b"], is_dir=False),
                "non-empty str without '/'",
                id="slash-in-part",
            ),
        ],
    )
    def test_from_dict_invalid_state(self, dct, message):
        """
        ``from_dict`` rejects data that is not a valid S3Path state, instead
        of building a path such as ``s3:///a`` or a "bucket that is a file".
        """
        with pytest.raises(S3ValidationError, match=message):
            S3Path.from_dict(dct)


if __name__ == "__main__":
    run_cov_test(__file__, module="s3pathlib.core.serde", preview=False)

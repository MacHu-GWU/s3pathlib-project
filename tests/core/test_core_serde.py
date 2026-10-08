# -*- coding: utf-8 -*-

"""
Test ``to_dict`` / ``from_dict``, ``S3PathDict``, and pickle / copy.

Test order:

1. ``to_dict``: the format of every kind of path;
2. ``from_dict``: round trips, then one case per kind of bad input;
3. pickle and ``copy``: every protocol, the hash across processes, the
   metadata snapshot and its S3 client, pickles from 2.x, and tampered state.
"""

import copy
import json
import pickle
import subprocess
import sys
import typing as T

import pytest

from s3pathlib.api import S3Path
from s3pathlib.api import S3PathDict
from s3pathlib.exc import S3ValidationError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest

R = S3Path.make_relpath

ALL_KINDS = [
    pytest.param(
        S3Path("bucket", "folder", "file.txt"),
        {"bucket": "bucket", "parts": ["folder", "file.txt"], "is_dir": False},
        id="file",
    ),
    pytest.param(
        S3Path("bucket", "folder/"),
        {"bucket": "bucket", "parts": ["folder"], "is_dir": True},
        id="dir",
    ),
    pytest.param(
        S3Path("bucket"),
        {"bucket": "bucket", "parts": [], "is_dir": True},
        id="bucket",
    ),
    pytest.param(
        R("a/b.txt"),
        {"bucket": None, "parts": ["a", "b.txt"], "is_dir": False},
        id="relpath-file",
    ),
    pytest.param(
        R("a/"),
        {"bucket": None, "parts": ["a"], "is_dir": True},
        id="relpath-dir",
    ),
    pytest.param(
        S3Path(),
        {"bucket": None, "parts": [], "is_dir": None},
        id="void",
    ),
]


class SerdeAPIMixin(BaseTest):
    module = "core.serde"

    # --------------------------------------------------------------------------
    # 1. to_dict
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("p, dct", ALL_KINDS)
    def test_to_dict(self, p, dct):
        """
        The dict holds the three fields that define the path, with ``parts``
        as a list.
        """
        assert p.to_dict() == dct
        assert type(p.to_dict()["parts"]) is list

    def test_to_dict_is_a_copy(self):
        """
        Changing the returned dict does not change the path.
        """
        p = S3Path("bucket", "a.txt")
        dct = p.to_dict()
        dct["parts"].append("b")
        dct["bucket"] = "other"
        assert p.uri == "s3://bucket/a.txt"

    def test_s3_path_dict(self):
        """
        ``S3PathDict`` is a public TypedDict with exactly the keys of
        ``to_dict``.
        """
        assert T.get_type_hints(S3PathDict) == {
            "bucket": T.Optional[str],
            "parts": list[str],
            "is_dir": T.Optional[bool],
        }
        assert S3PathDict.__required_keys__ == {"bucket", "parts", "is_dir"}

    # --------------------------------------------------------------------------
    # 2. from_dict
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("p, dct", ALL_KINDS)
    def test_from_dict(self, p, dct):
        """
        ``from_dict`` is the inverse of ``to_dict`` for every kind of path.
        """
        assert S3Path.from_dict(dct) == p
        assert S3Path.from_dict(p.to_dict()) == p

    @pytest.mark.parametrize("p, dct", ALL_KINDS)
    def test_from_dict_json_round_trip(self, p, dct):
        """
        The dict survives JSON unchanged, because ``parts`` is a list.
        """
        loaded = json.loads(json.dumps(p.to_dict()))
        assert loaded == p.to_dict()
        assert S3Path.from_dict(loaded) == p

    def test_from_dict_tuple_parts(self):
        assert S3Path.from_dict(
            {"bucket": "b", "parts": ("a", "c.txt"), "is_dir": False}
        ) == S3Path("b", "a", "c.txt")

    def test_from_dict_ignores_other_keys(self):
        """
        Other keys are ignored, so a newer format with more keys still loads.
        """
        dct = {"bucket": "b", "parts": ["a"], "is_dir": False, "version": 2}
        assert S3Path.from_dict(dct) == S3Path("b", "a")

    @pytest.mark.parametrize(
        "dct, message",
        [
            pytest.param(["b"], "dct has to be a dict, got list", id="not-dict"),
            pytest.param(
                {"bucket": "b", "parts": ["a"]},
                r"dct misses the key\(s\) \['is_dir'\]",
                id="missing-key",
            ),
            pytest.param(
                {},
                r"misses the key\(s\) \['bucket', 'parts', 'is_dir'\]",
                id="empty",
            ),
            pytest.param(
                {"bucket": "b", "parts": "abc", "is_dir": False},
                "parts must be a list or a tuple of str, got str",
                id="parts-str",
            ),
            pytest.param(
                {"bucket": "b", "parts": None, "is_dir": False},
                "parts must be a list or a tuple of str, got NoneType",
                id="parts-none",
            ),
            pytest.param(
                {"bucket": "b", "parts": [], "is_dir": False},
                "a bucket root must be a dir",
                id="bucket-is-file",
            ),
            pytest.param(
                {"bucket": "b", "parts": ["a"], "is_dir": None},
                "must be a file or a dir",
                id="no-type",
            ),
            pytest.param(
                {"bucket": "", "parts": ["a"], "is_dir": False},
                "bucket must not be empty",
                id="empty-bucket",
            ),
            pytest.param(
                {"bucket": "b", "parts": ["a/b"], "is_dir": False},
                "non-empty str without '/'",
                id="slash-in-part",
            ),
        ],
    )
    def test_from_dict_invalid(self, dct, message):
        """
        Bad data is rejected with ``S3ValidationError``, instead of a
        ``KeyError`` or a wrong path: before 3.0, ``"parts": "abc"`` gave
        ``s3://b/a/b/c``, and an empty bucket gave ``s3:///a``.
        """
        with pytest.raises(S3ValidationError, match=message):
            S3Path.from_dict(dct)

    # --------------------------------------------------------------------------
    # 3. pickle and copy
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    @pytest.mark.parametrize("p, dct", ALL_KINDS)
    def test_pickle(self, p, dct, protocol):
        """
        Every kind of path survives every pickle protocol; before 3.0
        protocols 0 and 1 failed.
        """
        loaded = pickle.loads(pickle.dumps(p, protocol=protocol))
        assert loaded == p
        assert repr(loaded) == repr(p)
        assert type(loaded._parts) is tuple

    def test_pickle_does_not_save_caches(self):
        """
        The cached hash and comparison parts are not saved.
        """
        p = S3Path("bucket", "a.txt")
        _ = hash(p)
        state = p.__getstate__()
        assert set(state) == {"_bucket", "_parts", "_is_dir", "_meta", "_meta_complete"}
        loaded = pickle.loads(pickle.dumps(p))
        assert hasattr(loaded, "_hash") is False
        assert hasattr(loaded, "_cached_cparts") is False

    def test_pickle_hash_across_processes(self, tmp_path):
        """
        A path pickled in one process works as a dict key in another one.
        The hash of a str differs between processes, so before 3.0 the
        pickled cached hash made ``d[S3Path(...)]`` miss.
        """
        path = tmp_path / "d.pkl"
        dump = (
            "import pickle, sys; from s3pathlib.api import S3Path; "
            "p = S3Path('bucket', 'a.txt'); hash(p); "
            "open(sys.argv[1], 'wb').write(pickle.dumps({p: 'value'}))"
        )
        load = (
            "import pickle, sys; from s3pathlib.api import S3Path; "
            "d = pickle.loads(open(sys.argv[1], 'rb').read()); "
            "print(d.get(S3Path('bucket', 'a.txt'), 'NOT FOUND'))"
        )
        for code, seed in [(dump, "1"), (load, "2")]:
            res = subprocess.run(
                [sys.executable, "-c", code, str(path)],
                env={"PYTHONHASHSEED": seed},
                capture_output=True,
                text=True,
                check=True,
            )
        assert res.stdout.strip() == "value"

    def test_pickle_keeps_metadata(self):
        """
        Metadata loaded from S3 is kept, so a path with its size can be sent
        to another process without calling ``head_object`` again.
        """
        p = self.s3dir_test / "pickle.txt"
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"hello")
        p.head_object()
        loaded = pickle.loads(pickle.dumps(p))
        assert loaded.response == p.response
        with record_api_calls(self.s3_client) as calls:
            assert loaded.size == 5
            # a full snapshot stays full: a missing field needs no call
            assert loaded.expire_at is None
        assert calls == []

    def test_pickle_drops_s3_client(self):
        """
        The S3 client that loaded the metadata cannot be pickled; a loaded
        path falls back to ``s3_context``.
        """
        p = S3Path("bucket", "a.txt")
        p._set_meta({"ETag": '"abc"'}, complete=False, s3_client=self.s3_client)
        loaded = pickle.loads(pickle.dumps(p))
        assert loaded._s3_client is None
        assert loaded._meta_complete is False
        assert loaded.response == {"ETag": '"abc"'}

    @pytest.mark.parametrize(
        "copier",
        [
            pytest.param(copy.copy, id="copy"),
            pytest.param(copy.deepcopy, id="deepcopy"),
        ],
    )
    def test_copy_module(self, copier):
        """
        ``copy.copy`` / ``copy.deepcopy`` give an equal new path, with the
        metadata snapshot and the S3 client that loaded it (shared), and
        without the caches.
        """
        p = S3Path("bucket", "a.txt")
        p._set_meta({"VersionId": "v1"}, complete=True, s3_client=self.s3_client)
        _ = hash(p)
        p1 = copier(p)
        assert p1 == p
        assert p1 is not p
        assert p1.response == {"VersionId": "v1"}
        assert p1._meta_complete is True
        assert p1._s3_client is self.s3_client
        assert hasattr(p1, "_hash") is False

    @pytest.mark.parametrize(
        "dict_state",
        [
            pytest.param(None, id="no-dict"),
            pytest.param({"unknown": 1}, id="with-dict"),
        ],
    )
    def test_unpickle_2x_state(self, dict_state):
        """
        A pickle made by s3pathlib 2.x has the default ``(dict, slots)``
        state, with ``_parts`` as a list and a cached hash; it still loads,
        and the hash is computed again.
        """
        p = S3Path.__new__(S3Path)
        p.__setstate__(
            (
                dict_state,
                {
                    "_bucket": "bucket",
                    "_parts": ["a.txt"],
                    "_is_dir": False,
                    "_meta": None,
                    "_hash": 12345,
                    "_cached_cparts": ["bucket", "a.txt"],
                },
            )
        )
        assert p == S3Path("bucket", "a.txt")
        assert type(p._parts) is tuple
        assert hash(p) == hash(S3Path("bucket", "a.txt"))
        assert p._meta_complete is False
        assert p._s3_client is None

    def test_unpickle_invalid_state(self):
        """
        A tampered state can not build a path in an invalid state.
        """
        p = S3Path.__new__(S3Path)
        with pytest.raises(S3ValidationError, match="a bucket root must be a dir"):
            p.__setstate__(
                {"_bucket": "bucket", "_parts": [], "_is_dir": False, "_meta": None}
            )


class TestMock(SerdeAPIMixin):
    use_mock = True


class TestRealAws(SerdeAPIMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.serde",
        preview=False,
    )

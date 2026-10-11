# -*- coding: utf-8 -*-

"""
Test ``S3Path.iter_objects``, ``iterdir``, ``calculate_total_size``,
``count_objects`` and ``S3PathIterProxy.filter_by_ext``.

Test order:

1. ``iter_objects``: the objects, the order, ``recursive``, ``limit``,
   ``batch_size``;
2. ``iterdir``: files and folders, its own folder marker, ``limit``;
3. ``filter_by_ext`` and the metadata filters;
4. ``count_objects`` and ``calculate_total_size``;
5. invalid paths and arguments, AWS errors.

All tests read the same data, written once by ``custom_setup_class`` under
``s3dir_root / "data/"`` (see ``KEYS``), and never write.
"""

import contextlib
import uuid

import botocore.exceptions
import pytest

from s3pathlib.api import S3Path
from s3pathlib.exc import S3PathIsNotFolderError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.aws_helpers import record_api_calls
from s3pathlib.tests.mock_aws import BaseTest

# key under the data folder -> content; "" is the folder marker of the data
# folder itself, "hard/" a folder marker, "dirobj/" an object with content
KEYS = {
    "": b"",
    "README.txt": b"readme",
    "c.csv": b"a,b",
    "d.JSON": b"{}",
    "dirobj/": b"x",
    "f.txt": b"f",
    "f.txt.bak": b"bak",
    "f.txt/inner.txt": b"inner",
    "hard/": b"",
    "hard/1.txt": b"1",
    "hard/sub/2.txt": b"22",
    "noext": b"no",
    "soft/3.txt": b"333",
}

# iter_objects(): every object, in key order, without the folder markers
ALL_OBJECTS = [
    "README.txt",
    "c.csv",
    "d.JSON",
    "dirobj/",
    "f.txt",
    "f.txt.bak",
    "f.txt/inner.txt",
    "hard/1.txt",
    "hard/sub/2.txt",
    "noext",
    "soft/3.txt",
]

# iter_objects(recursive=False): the objects directly in the folder
TOP_OBJECTS = ["README.txt", "c.csv", "d.JSON", "f.txt", "f.txt.bak", "noext"]

# iterdir(): files and folders, in key order, without the folder itself
TOP_ENTRIES = [
    "README.txt",
    "c.csv",
    "d.JSON",
    "dirobj/",
    "f.txt",
    "f.txt.bak",
    "f.txt/",
    "hard/",
    "noext",
    "soft/",
]

N_OBJECTS = len(ALL_OBJECTS)
TOTAL_SIZE = sum(len(body) for body in KEYS.values())

METHODS = [
    pytest.param("iter_objects", id="iter_objects"),
    pytest.param("iterdir", id="iterdir"),
    pytest.param("count_objects", id="count_objects"),
    pytest.param("calculate_total_size", id="calculate_total_size"),
]


def error_code(exc_info) -> str:
    return exc_info.value.response["Error"]["Code"]


@contextlib.contextmanager
def record_max_keys(s3_client):
    """
    Record the ``MaxKeys`` of every ``list_objects_v2`` call.
    """
    max_keys = list()

    def record(params, **kwargs):
        max_keys.append(params.get("MaxKeys"))

    events = s3_client.meta.events
    events.register("provide-client-params.s3.ListObjectsV2", record)
    try:
        yield max_keys
    finally:
        events.unregister("provide-client-params.s3.ListObjectsV2", record)


class IterObjectsMixin(BaseTest):
    module = "core.iter_objects"

    s3dir_data: S3Path

    @classmethod
    def custom_setup_class(cls):
        cls.s3dir_data = cls.s3dir_root / "data/"
        for key, body in KEYS.items():
            cls.s3_client.put_object(
                Bucket=cls.s3dir_data.bucket,
                Key=cls.s3dir_data.key + key,
                Body=body,
            )

    def rel(self, s3path_list: list[S3Path], base: S3Path | None = None) -> list[str]:
        """
        The keys relative to ``base`` (default the data folder).
        """
        if base is None:
            base = self.s3dir_data
        return [p.key[len(base.key):] for p in s3path_list]

    # --------------------------------------------------------------------------
    # 1. iter_objects
    # --------------------------------------------------------------------------
    def test_iter_objects(self):
        """
        Every object under the folder, recursively, in key order; the folder
        markers are skipped, an object ``dirobj/`` with content is a folder
        path.
        """
        result = self.s3dir_data.iter_objects().all()
        assert self.rel(result) == ALL_OBJECTS
        dirobj = result[ALL_OBJECTS.index("dirobj/")]
        assert dirobj.is_dir()
        assert dirobj.size == 1

    def test_iter_objects_not_recursive(self):
        result = self.s3dir_data.iter_objects(recursive=False).all()
        assert self.rel(result) == TOP_OBJECTS

    def test_iter_objects_metadata_from_list(self):
        """
        Each path has the size and ETag from the list API, no more call.
        """
        result = self.s3dir_data.iter_objects().all()
        with record_api_calls(self.s3_client) as calls:
            sizes = [p.size for p in result]
            _ = [p.etag for p in result]
        assert calls == []
        assert sizes == [len(KEYS[key]) for key in ALL_OBJECTS]

    @pytest.mark.parametrize("recursive", [True, False])
    @pytest.mark.parametrize("limit", [1, 3, 100, None])
    def test_iter_objects_limit(self, recursive, limit):
        """
        ``limit`` counts the returned objects; ``None`` is no limit. The folder
        markers and folders that are skipped do not count, so ``limit=3``
        returns 3 objects.
        """
        if recursive:
            expected = ALL_OBJECTS
        else:
            expected = TOP_OBJECTS
        result = self.s3dir_data.iter_objects(recursive=recursive, limit=limit).all()
        assert self.rel(result) == expected[:limit]

    def test_iter_objects_limit_zero(self):
        with record_api_calls(self.s3_client) as calls:
            assert self.s3dir_data.iter_objects(limit=0).all() == []
        assert calls == []

    def test_iter_objects_limit_page_size(self):
        """
        A small ``limit`` asks for no more than ``limit`` entries per call.
        """
        with record_max_keys(self.s3_client) as max_keys:
            self.s3dir_data.iter_objects(limit=2).all()
        assert set(max_keys) == {2}

    def test_iter_objects_batch_size(self):
        """
        Small pages give the same result, one call per page.
        """
        with record_api_calls(self.s3_client) as calls:
            result = self.s3dir_data.iter_objects(batch_size=4).all()
        assert self.rel(result) == ALL_OBJECTS
        # 13 keys, 4 per page
        assert len(calls) == 4

    def test_iter_objects_empty_folder(self):
        assert (self.s3dir_root / "empty/").iter_objects().all() == []

    # --------------------------------------------------------------------------
    # 2. iterdir
    # --------------------------------------------------------------------------
    def test_iterdir(self):
        """
        The files and folders directly in the folder, in key order (files and
        folders mixed), without the folder itself. A file has the metadata
        from the list API, a folder has none.
        """
        result = self.s3dir_data.iterdir().all()
        assert self.rel(result) == TOP_ENTRIES
        by_name = dict(zip(TOP_ENTRIES, result))
        assert by_name["hard/"].is_dir()
        assert by_name["hard/"].response is None
        assert by_name["c.csv"].is_file()
        assert by_name["c.csv"].response["ContentLength"] == 3

    def test_iterdir_skips_its_folder_marker(self):
        """
        The folder marker ``hard/`` is the folder itself, not an entry in it.
        """
        s3dir = self.s3dir_data / "hard/"
        assert self.rel(s3dir.iterdir().all(), base=s3dir) == ["1.txt", "sub/"]

    def test_iterdir_batch_size(self):
        """
        Small pages give the same order: the key order, files and folders
        mixed, not the folders then the files of each page.
        """
        result = self.s3dir_data.iterdir(batch_size=2).all()
        assert self.rel(result) == TOP_ENTRIES

    @pytest.mark.parametrize("limit", [1, 4, 100, None])
    def test_iterdir_limit(self, limit):
        """
        ``limit`` counts the returned files and folders; ``None`` is no limit.
        """
        result = self.s3dir_data.iterdir(limit=limit).all()
        assert self.rel(result) == TOP_ENTRIES[:limit]

    def test_iterdir_limit_zero(self):
        with record_api_calls(self.s3_client) as calls:
            assert self.s3dir_data.iterdir(limit=0).all() == []
        assert calls == []

    # --------------------------------------------------------------------------
    # 3. Filters
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "exts, expected",
        [
            pytest.param([".csv"], ["c.csv"], id="one"),
            pytest.param([".json"], ["d.JSON"], id="case-insensitive"),
            pytest.param([".CSV", ".Json"], ["c.csv", "d.JSON"], id="many"),
            pytest.param([""], ["noext"], id="no-ext"),
            pytest.param([".bak"], ["f.txt.bak"], id="last-ext"),
        ],
    )
    def test_filter_by_ext(self, exts, expected):
        """
        Files with one of the extensions; the folder object ``dirobj/`` is
        skipped, it does not raise ``S3PathIsNotFileError``.
        """
        result = self.s3dir_data.iter_objects().filter_by_ext(*exts).all()
        assert self.rel(result) == expected

    @pytest.mark.parametrize(
        "exts, match",
        [
            pytest.param([], "at least one extension", id="none"),
            pytest.param(["csv"], "starts with '.'", id="no-dot"),
        ],
    )
    def test_filter_by_ext_invalid(self, exts, match):
        with pytest.raises(ValueError, match=match):
            self.s3dir_data.iter_objects().filter_by_ext(*exts)

    def test_iterproxy_methods(self):
        """
        ``one`` / ``one_or_none`` / ``many`` / ``skip`` / ``all`` consume the
        same iterator, which can be iterated only once.
        """
        proxy = self.s3dir_data.iter_objects()
        assert self.rel([proxy.one()]) == ALL_OBJECTS[:1]
        assert self.rel([proxy.one_or_none()]) == ALL_OBJECTS[1:2]
        assert self.rel(proxy.many(2)) == ALL_OBJECTS[2:4]
        proxy.skip(2)
        assert self.rel(proxy.all()) == ALL_OBJECTS[6:]
        assert proxy.one_or_none() is None
        assert proxy.all() == []

    def test_metadata_filter_needs_no_call(self):
        """
        Filters on the metadata from the list API need no ``head_object``.
        """
        with record_api_calls(self.s3_client) as calls:
            result = self.s3dir_data.iter_objects().filter(S3Path.size >= 3).all()
        assert calls == ["ListObjectsV2"]
        assert self.rel(result) == ["README.txt", "c.csv", "f.txt.bak", "f.txt/inner.txt", "soft/3.txt"]

    # --------------------------------------------------------------------------
    # 4. count_objects and calculate_total_size
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "include_folder, count",
        [
            pytest.param(False, N_OBJECTS, id="objects"),
            # plus the folder markers "data/" and "hard/"
            pytest.param(True, N_OBJECTS + 2, id="with-folders"),
        ],
    )
    def test_count_objects(self, include_folder, count):
        assert self.s3dir_data.count_objects(include_folder=include_folder) == count

    def test_calculate_total_size(self):
        assert self.s3dir_data.calculate_total_size() == (N_OBJECTS, TOTAL_SIZE)
        assert self.s3dir_data.calculate_total_size(
            for_human=True,
            include_folder=True,
        ) == (N_OBJECTS + 2, f"{TOTAL_SIZE} B")

    # --------------------------------------------------------------------------
    # 5. Invalid input and AWS errors
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("method", METHODS)
    @pytest.mark.parametrize(
        "p, error, match",
        [
            pytest.param(S3Path(), S3PathTypeError, "is a relative path", id="void"),
            pytest.param(
                S3Path.make_relpath("a/"),
                S3PathTypeError,
                "is a relative path",
                id="relpath",
            ),
            pytest.param(
                S3Path("bucket", "f.txt"),
                S3PathIsNotFolderError,
                "is not a dir",
                id="file",
            ),
        ],
    )
    def test_not_a_folder(self, method, p, error, match):
        """
        Only a folder or a bucket can be listed; anything else is rejected
        before any AWS call: a file does not list the keys that start with its
        key (``f.txt.bak``, ``f.txt/inner.txt``), and a relative path does not
        reach botocore.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(error, match=match):
                getattr(p, method)()
        assert calls == []

    @pytest.mark.parametrize("method", ["iter_objects", "iterdir"])
    @pytest.mark.parametrize(
        "kwargs, match",
        [
            pytest.param({"limit": -1}, "must not be negative", id="limit"),
            pytest.param({"batch_size": 0}, "1 ~ 1000", id="batch_size"),
        ],
    )
    def test_invalid_arguments(self, method, kwargs, match):
        """
        Invalid arguments raise when the method is called, not when the
        iteration starts.
        """
        with record_api_calls(self.s3_client) as calls:
            with pytest.raises(ValueError, match=match):
                getattr(self.s3dir_data, method)(**kwargs)
        assert calls == []

    @pytest.mark.parametrize("method", ["iter_objects", "iterdir"])
    def test_missing_bucket(self, method):
        """
        ``NoSuchBucket`` is raised as is, when the iteration starts.
        """
        p = S3Path(f"s3pathlib-test-tmp-{uuid.uuid4().hex}", "folder/")
        proxy = getattr(p, method)()
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            proxy.all()
        assert error_code(exc_info) == "NoSuchBucket"


class TestMock(IterObjectsMixin):
    use_mock = True


class TestRealAws(IterObjectsMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.iter_objects",
        preview=False,
    )

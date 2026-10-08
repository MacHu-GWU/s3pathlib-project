# -*- coding: utf-8 -*-

"""
Test the ``is_*`` tests and the ``ensure_*`` validators.

Test order:

1. the truth table of ``is_void`` / ``is_relpath`` / ``is_bucket`` /
   ``is_dir`` / ``is_file`` for the six valid states;
2. every ``ensure_*`` on the six states: pass, or the exception and message;
3. ``is_delete_marker``, against moto (it must never call the AWS API).
"""

import contextlib

import pytest

from s3pathlib.api import S3Path
from s3pathlib.api import s3_context
from s3pathlib.exc import S3PathIsNotBucketError
from s3pathlib.exc import S3PathIsNotFileError
from s3pathlib.exc import S3PathIsNotFolderError
from s3pathlib.exc import S3PathTypeError
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock import BaseTest

R = S3Path.make_relpath

FILE = S3Path("bucket", "file.txt")
DIRECTORY = S3Path("bucket", "folder/")
BUCKET = S3Path("bucket")
RELPATH_FILE = R("folder/file.txt")
RELPATH_DIR = R("folder/")
VOID = S3Path()

KINDS = {
    "file": FILE,
    "dir": DIRECTORY,
    "bucket": BUCKET,
    "relpath-file": RELPATH_FILE,
    "relpath-dir": RELPATH_DIR,
    "void": VOID,
}

LABELS = {
    "file": "'s3://bucket/file.txt'",
    "dir": "'s3://bucket/folder/'",
    "bucket": "'s3://bucket/'",
    "relpath-file": "S3RelPath('folder/file.txt')",
    "relpath-dir": "S3RelPath('folder/')",
    "void": "S3VoidPath()",
}

# ensure method -> (kinds that pass, exception class, message template)
ENSURE = {
    "ensure_object": (
        {"file", "relpath-file"},
        S3PathIsNotFileError,
        "{label} is not a file!",
    ),
    "ensure_file": (
        {"file", "relpath-file"},
        S3PathIsNotFileError,
        "{label} is not a file!",
    ),
    "ensure_not_object": (
        {"dir", "bucket", "relpath-dir", "void"},
        S3PathTypeError,
        "{label} is a file!",
    ),
    "ensure_not_file": (
        {"dir", "bucket", "relpath-dir", "void"},
        S3PathTypeError,
        "{label} is a file!",
    ),
    "ensure_dir": (
        {"dir", "bucket", "relpath-dir"},
        S3PathIsNotFolderError,
        "{label} is not a dir!",
    ),
    "ensure_not_dir": (
        {"file", "relpath-file", "void"},
        S3PathTypeError,
        "{label} is a dir!",
    ),
    "ensure_bucket": (
        {"bucket"},
        S3PathIsNotBucketError,
        "{label} is not a bucket!",
    ),
}

@contextlib.contextmanager
def record_api_calls():
    """
    Record the name of every S3 API call made by ``S3Path`` (through the
    client of ``s3_context``).
    """
    calls = list()

    def record(model, **kwargs):
        calls.append(model.name)

    events = s3_context.s3_client.meta.events
    events.register("before-call.s3.*", record)
    try:
        yield calls
    finally:
        events.unregister("before-call.s3.*", record)


ENSURE_CASES = [
    pytest.param(method, kind, id=f"{method}-{kind}")
    for method in ENSURE
    for kind in KINDS
]


class IsTestAPIMixin(BaseTest):
    module = "core.is_test"

    # --------------------------------------------------------------------------
    # 1. is_*
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "p, expected",
        [
            # is_void, is_relpath, is_bucket, is_dir, is_file
            pytest.param(FILE, (False, False, False, False, True), id="file"),
            pytest.param(DIRECTORY, (False, False, False, True, False), id="dir"),
            pytest.param(BUCKET, (False, False, True, True, False), id="bucket"),
            pytest.param(RELPATH_FILE, (False, True, False, False, True), id="relpath-file"),
            pytest.param(RELPATH_DIR, (False, True, False, True, False), id="relpath-dir"),
            pytest.param(VOID, (True, True, False, False, False), id="void"),
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
            pytest.param(R("a").parent, id="relpath-parent"),
            pytest.param(S3Path(S3Path(), "/"), id="void-and-slash"),
            pytest.param(S3Path("b", "a/").relative_to(S3Path("b", "a/")), id="p-minus-p"),
            pytest.param(R("/"), id="make-relpath-slash"),
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

    # --------------------------------------------------------------------------
    # 2. ensure_*
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("method, kind", ENSURE_CASES)
    def test_ensure(self, method, kind):
        """
        Each validator passes for the kinds it accepts, and otherwise raises
        its exception with the path in the message: the URI for an absolute
        path, the repr for a relative path or void (before 3.0 they showed
        ``None``). ``ensure_file`` / ``ensure_not_file`` are aliases.
        """
        accepted, error, template = ENSURE[method]
        p = KINDS[kind]
        if kind in accepted:
            assert getattr(p, method)() is None
        else:
            with pytest.raises(error) as e:
                getattr(p, method)()
            assert type(e.value) is error
            assert str(e.value) == template.format(label=LABELS[kind])

    @pytest.mark.parametrize(
        "method",
        [
            pytest.param("ensure_not_object", id="ensure_not_object"),
            pytest.param("ensure_not_dir", id="ensure_not_dir"),
        ],
    )
    def test_ensure_not_is_type_error(self, method):
        """
        ``ensure_not_*`` raise ``S3PathTypeError``, which is still a
        ``TypeError`` as before 3.0, and now also an ``S3PathlibError``.
        """
        p = FILE if method == "ensure_not_object" else DIRECTORY
        with pytest.raises(TypeError):
            getattr(p, method)()

    # --------------------------------------------------------------------------
    # 3. is_delete_marker
    # --------------------------------------------------------------------------
    def test_is_delete_marker_from_versions(self):
        """
        In the versions of a deleted object, the delete marker is the latest
        version and is the only one that is a delete marker.
        """
        p = self.s3dir_root_with_versioning.joinpath("delete-marker", "file.txt")
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"v1")
        self.s3_client.delete_object(Bucket=p.bucket, Key=p.key)

        versions = list(p.list_object_versions())
        markers = [v for v in versions if v.is_delete_marker()]
        assert len(versions) == 2
        assert len(markers) == 1
        assert markers[0].response["IsLatest"] is True

    @pytest.mark.parametrize(
        "key, setup",
        [
            pytest.param("missing.txt", "nothing", id="missing"),
            pytest.param("existing.txt", "put", id="existing"),
            pytest.param("deleted.txt", "put-and-delete", id="latest-is-delete-marker"),
        ],
    )
    def test_is_delete_marker_does_not_call_aws(self, key, setup):
        """
        Without metadata from ``list_object_versions`` it is ``False``, and it
        never calls the API; before 3.0 it called ``head_object``, which
        raised ``S3FileNotExist`` for a missing object and, worse, for an
        object whose latest version is a delete marker.
        """
        p = self.s3dir_root_with_versioning.joinpath("no-api-call", key)
        if setup in ("put", "put-and-delete"):
            self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"v1")
        if setup == "put-and-delete":
            self.s3_client.delete_object(Bucket=p.bucket, Key=p.key)

        with record_api_calls() as calls:
            assert p.is_delete_marker() is False
        assert calls == []

    @pytest.mark.parametrize(
        "p",
        [
            pytest.param(DIRECTORY, id="dir"),
            pytest.param(BUCKET, id="bucket"),
            pytest.param(RELPATH_FILE, id="relpath-file"),
            pytest.param(VOID, id="void"),
        ],
    )
    def test_is_delete_marker_other_kinds(self, p):
        """
        Only an object version can be a delete marker; before 3.0 a relative
        file raised ``TypeError``.
        """
        assert p.is_delete_marker() is False

    def test_is_delete_marker_regular_object_metadata(self):
        """
        Metadata from ``head_object`` never marks a delete marker.
        """
        p = self.s3dir_root.joinpath("is-delete-marker", "file.txt")
        self.s3_client.put_object(Bucket=p.bucket, Key=p.key, Body=b"hello")
        with record_api_calls() as calls:
            p.head_object()
        assert calls == ["HeadObject"]  # the recorder works
        assert p.is_delete_marker() is False


# class Test(IsTestAPIMixin):
#     use_mock = False


class TestUseMock(IsTestAPIMixin):
    use_mock = True


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.is_test",
        preview=False,
    )

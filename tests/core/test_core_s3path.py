# -*- coding: utf-8 -*-

"""
Test how ``S3Path`` is assembled from its mixins (``s3pathlib.core.s3path``).
"""

from s3pathlib.api import S3Path
from s3pathlib.core.base import BaseS3Path
from s3pathlib.tests import run_cov_test

# attributes that every class body gets from Python, not defined by the mixin
IMPLICIT = {
    "__module__",
    "__qualname__",
    "__doc__",
    "__slots__",
    "__annotations__",
    "__firstlineno__",
    "__static_attributes__",
    "__dict__",
    "__weakref__",
}


def test_base_comes_first():
    """
    ``BaseS3Path`` holds the state and the constructor, so it is the first
    base.
    """
    assert S3Path.__bases__[0] is BaseS3Path


def test_mixins_do_not_define_the_same_name():
    """
    No two classes of ``S3Path`` define the same name, so the order of the
    bases (the MRO) does not change any behavior, and a new mixin that
    overrides a method by accident is caught.
    """
    owner = dict()
    for cls in S3Path.__mro__[1:]:
        if cls is object:
            continue
        for name in vars(cls):
            if name in IMPLICIT:
                continue
            assert name not in owner, (
                f"{name!r} is defined by {owner[name]} and {cls.__name__}"
            )
            owner[name] = cls.__name__


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.s3path",
        preview=False,
    )

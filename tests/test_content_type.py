# -*- coding: utf-8 -*-

import re

from s3pathlib.api import ContentTypeEnum
from s3pathlib.tests import run_cov_test

VALUES = {
    name: value
    for name, value in vars(ContentTypeEnum).items()
    if not name.startswith("_")
}


def test_content_type_values_are_mime():
    """
    Every value is a ``type/subtype`` MIME string, so a typo or a non MIME
    value cannot slip in.
    """
    assert len(VALUES) > 0
    for name, value in VALUES.items():
        assert isinstance(value, str), name
        assert re.fullmatch(r"[a-z]+/[a-z0-9.+-]+", value), name


def test_content_type_values_unique():
    """
    No two names map to the same value (a common copy-paste mistake).
    """
    assert len(set(VALUES.values())) == len(VALUES)


def test_content_type_usable_as_str():
    """
    Members are plain strings, so they can be passed straight to boto3.
    """
    assert ContentTypeEnum.app_json == "application/json"
    assert type(ContentTypeEnum.app_json) is str


if __name__ == "__main__":
    run_cov_test(__file__, "s3pathlib.content_type", preview=False)

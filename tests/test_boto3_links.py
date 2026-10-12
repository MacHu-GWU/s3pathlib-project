# -*- coding: utf-8 -*-

"""
Check the boto3 documentation links of the library, without network access.

A module links a boto3 method once, in its docstring, as a target
``.. _head_object: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/head_object.html``,
and the text uses ``head_object_``. The URL is built from the method name, so
that when AWS moves the documentation, one search and replace fixes every link.
This test checks that every target follows that format, and that the name is a
real method of the S3 client, including the ones boto3 adds such as
``upload_file``. Whether the pages exist is checked with
``sphinx-build -b linkcheck`` before a release.
"""

import re

import boto3
import pytest

from s3pathlib.paths import path_enum
from s3pathlib.tests import run_unit_test

URL_FORMAT = (
    "https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/{name}.html"
)
TARGET = re.compile(r"^\s*\.\. _(?P<name>\w+): (?P<url>https://\S*/boto3/\S+)$", re.M)
OLD_DOMAIN = "boto3.amazonaws.com"

# creating a client makes no request
S3_CLIENT = boto3.session.Session(
    aws_access_key_id="testing",
    aws_secret_access_key="testing",
    region_name="us-east-1",
).client("s3")


def iter_source_files():
    for path in sorted(path_enum.dir_package.rglob("*.py")):
        if "vendor" not in path.parts:
            yield path


LINKS = []
for _path in iter_source_files():
    for _match in TARGET.finditer(_path.read_text(encoding="utf-8")):
        LINKS.append(
            pytest.param(
                _match.group("name"),
                _match.group("url"),
                id=f"{_path.relative_to(path_enum.dir_package)}:{_match.group('name')}",
            )
        )


def test_links_are_found():
    """
    The scan finds the links, so that the checks below do not pass on nothing.
    """
    assert len(LINKS) > 20


@pytest.mark.parametrize("name, url", LINKS)
def test_link_format(name, url):
    """
    The URL is built from the method name, and the name is a method of the S3
    client.
    """
    assert url == URL_FORMAT.format(name=name)
    assert callable(getattr(S3_CLIENT, name, None)), name


def test_no_link_with_the_old_domain():
    """
    No link uses the old documentation domain, whose anchors do not work.
    """
    for path in iter_source_files():
        assert OLD_DOMAIN not in path.read_text(encoding="utf-8"), path


if __name__ == "__main__":
    run_unit_test(__file__)

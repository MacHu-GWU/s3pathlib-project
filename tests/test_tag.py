# -*- coding: utf-8 -*-

from urllib.parse import parse_qs

import pytest

from s3pathlib.tag import parse_tags
from s3pathlib.tag import encode_tag_set
from s3pathlib.tag import encode_url_query
from s3pathlib.tag import encode_for_put_object
from s3pathlib.tag import encode_for_put_bucket_tagging
from s3pathlib.tag import encode_for_put_object_tagging
from s3pathlib.tests import run_cov_test


# ------------------------------------------------------------------------------
# parse_tags
# ------------------------------------------------------------------------------
def test_parse_tags():
    """
    A boto3 ``TagSet`` becomes a dict of key to value.
    """
    tag_set = [
        {"Key": "name", "Value": "Alice"},
        {"Key": "team", "Value": "data"},
    ]
    assert parse_tags(tag_set) == {"name": "Alice", "team": "data"}


def test_parse_tags_empty():
    """
    boto3 returns an empty ``TagSet`` when there are no tags; that is ``{}``.
    """
    assert parse_tags([]) == {}


def test_parse_tags_not_a_list():
    """
    Only the ``TagSet`` list is accepted; passing the whole response dict by
    mistake fails loudly instead of returning garbage.
    """
    with pytest.raises(NotImplementedError):
        parse_tags({"TagSet": []})


# ------------------------------------------------------------------------------
# encode_tag_set
# ------------------------------------------------------------------------------
def test_encode_tag_set():
    """
    A dict becomes a ``TagSet`` list, in the dict's order.
    """
    assert encode_tag_set({"k2": "v2", "k1": "v1"}) == [
        {"Key": "k2", "Value": "v2"},
        {"Key": "k1", "Value": "v1"},
    ]


def test_encode_tag_set_empty():
    """
    No tags encode to an empty ``TagSet``.
    """
    assert encode_tag_set({}) == []


def test_encode_tag_set_round_trip():
    """
    Encoding then parsing gives back the original tags.
    """
    tags = {"name": "Alice", "team": "data eng"}
    assert parse_tags(encode_tag_set(tags)) == tags


# ------------------------------------------------------------------------------
# encode_url_query
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value, encoded",
    [
        ("v", "k=v"),
        ("a b", "k=a%20b"),
        ("a=b", "k=a%3Db"),
        ("a&b", "k=a%26b"),
        ("a/b", "k=a%2Fb"),
        ("a+b", "k=a%2Bb"),
        ("中文", "k=%E4%B8%AD%E6%96%87"),
    ],
)
def test_encode_url_query_special_chars(value, encoded):
    """
    Characters that have meaning in a query string are escaped, so a value
    cannot be split into extra tags or change its content. A space is sent as
    ``%20`` (like the official AWS SDKs), not ``+``, which S3 could read as a
    literal plus sign.
    """
    assert encode_url_query({"k": value}) == encoded


def test_encode_url_query_multiple_tags():
    """
    Multiple tags are joined with ``&`` in the dict's order.
    """
    assert encode_url_query({"k1": "v1", "k2": "v2"}) == "k1=v1&k2=v2"


def test_encode_url_query_round_trip():
    """
    Decoding the query string gives back exactly the original tags, including
    keys and values with special characters.
    """
    tags = {"name": "Alice Bob", "a=b": "c&d", "plus": "1+1", "path": "x/y"}
    decoded = {k: v[0] for k, v in parse_qs(encode_url_query(tags)).items()}
    assert decoded == tags


# ------------------------------------------------------------------------------
# encode_for_* aliases
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "alias, base",
    [
        (encode_for_put_object, encode_url_query),
        (encode_for_put_bucket_tagging, encode_tag_set),
        (encode_for_put_object_tagging, encode_tag_set),
    ],
)
def test_encode_for_api_aliases(alias, base):
    """
    Each API specific encoder uses the format that API expects.
    """
    tags = {"name": "Alice", "team": "data eng"}
    assert alias(tags) == base(tags)


if __name__ == "__main__":
    run_cov_test(__file__, "s3pathlib.tag", preview=False)

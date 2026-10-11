# -*- coding: utf-8 -*-

"""
Helpers that convert S3 tags between a Python dict and the formats boto3 uses.

**Design notes**

*Encoders named by API.* S3 takes tags in two formats: a ``TagSet`` list
(``put_bucket_tagging``, ``put_object_tagging``) and a URL query string (the
``Tagging`` parameter of ``put_object``). ``encode_for_put_object`` and the two
other ``encode_for_*`` functions only call :func:`encode_tag_set` or
:func:`encode_url_query`. They exist so that a call site says which API it
feeds, which reads better than a format name.

*Spaces are sent as* ``%20``. The AWS docs do not say how S3 decodes ``+`` in
the query string. The official AWS SDKs send ``%20``, so that is what
:func:`encode_url_query` does, and a space can never be read as a literal
plus sign.

.. _get_bucket_tagging: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_bucket_tagging.html
.. _get_object_tagging: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object_tagging.html
.. _put_object: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html
.. _put_bucket_tagging: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_bucket_tagging.html
.. _put_object_tagging: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object_tagging.html
"""

from __future__ import annotations

from urllib.parse import quote
from urllib.parse import urlencode

from .type import TagType
from .type import TagSetType


def parse_tags(data: TagSetType) -> TagType:
    """
    Convert the tag set that get_bucket_tagging_ and get_object_tagging_
    return into a dict.

    Example::

        >>> parse_tags([{"Key": "name", "Value": "Alice"}])
        {'name': 'Alice'}

    :param data: the ``TagSet`` list of the response, not the whole response.
    """
    return {dct["Key"]: dct["Value"] for dct in data}


def encode_tag_set(tags: TagType) -> TagSetType:
    """
    Encode a dict of tags as a tag set, the format some APIs use for the
    tagging parameter.

    Example::

        >>> encode_tag_set({"name": "Alice"})
        [{'Key': 'name', 'Value': 'Alice'}]
    """
    return [{"Key": k, "Value": v} for k, v in tags.items()]


def encode_url_query(tags: TagType) -> str:
    """
    Encode a dict of tags as a URL query string (``Key1=Value1&Key2=Value2``),
    the format some APIs use for the tagging parameter. Special characters
    are percent-encoded, and spaces become ``%20``.

    Example::

        >>> encode_url_query({"name": "Alice", "team": "data eng"})
        'name=Alice&team=data%20eng'
    """
    return urlencode(tags, quote_via=quote)


def encode_for_put_object(tags: TagType) -> str:
    """
    Encode tags for put_object_.
    """
    return encode_url_query(tags)


def encode_for_put_bucket_tagging(tags: TagType) -> TagSetType:
    """
    Encode tags for put_bucket_tagging_.
    """
    return encode_tag_set(tags)


def encode_for_put_object_tagging(tags: TagType) -> TagSetType:
    """
    Encode tags for put_object_tagging_.
    """
    return encode_tag_set(tags)

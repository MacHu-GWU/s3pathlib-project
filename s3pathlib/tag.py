# -*- coding: utf-8 -*-

"""
Helpers that convert S3 tags between a Python dict and the formats boto3 uses.

.. _get_bucket_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_bucket_tagging.html
.. _get_object_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_object_tagging.html
.. _put_object: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object.html
.. _put_bucket_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_bucket_tagging.html
.. _put_object_tagging: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object_tagging.html
"""

from urllib.parse import urlencode

from .type import TagType, TagSetType


def parse_tags(data: TagSetType) -> TagType:
    """
    Convert a tag set from a boto3 response into a dict.

    get_bucket_tagging_ and get_object_tagging_ return tags as a tag set.

    Example::

        >>> parse_tags([{"Key": "name", "Value": "Alice"}])
        {'name': 'Alice'}

    :param data: the ``TagSet`` list in the boto3 response.
    :return: a dict of tag key and value.
    """
    if isinstance(data, list):
        return {dct["Key"]: dct["Value"] for dct in data}
    else:  # pragma: no cover
        raise NotImplementedError


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
    are percent-encoded, and spaces become ``+``.

    Example::

        >>> encode_url_query({"name": "Alice", "team": "data eng"})
        'name=Alice&team=data+eng'
    """
    return urlencode(tags)


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

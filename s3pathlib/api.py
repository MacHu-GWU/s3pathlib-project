# -*- coding: utf-8 -*-

"""
The public API of ``s3pathlib``.

Usage::

    from s3pathlib.api import S3Path
    from s3pathlib.api import context

.. versionadded:: 3.0.0

    Import public names from ``s3pathlib.api`` instead of ``s3pathlib``.
    ``from s3pathlib import ...`` will be removed.
"""

from iterproxy import and_
from iterproxy import or_
from iterproxy import not_

from . import utils
from .aws import context
from .core import S3Path
from .content_type import ContentTypeEnum
from .validate import validate_s3_bucket
from .validate import validate_s3_key
from .validate import validate_s3_uri
from .validate import validate_s3_arn

# Low level helpers on top of the boto3 S3 client.
# They were available as ``s3pathlib.api.*`` in 2.x.
from .better_client.api import is_bucket_exists
from .better_client.api import head_object
from .better_client.api import is_object_exists
from .better_client.api import update_bucket_tagging
from .better_client.api import update_object_tagging
from .better_client.api import upload_dir
from .better_client.api import ObjectTypeDefIterproxy
from .better_client.api import CommonPrefixTypeDefIterproxy
from .better_client.api import ListObjectsV2OutputTypeDefIterproxy
from .better_client.api import paginate_list_objects_v2
from .better_client.api import is_content_an_object
from .better_client.api import calculate_total_size
from .better_client.api import count_objects
from .better_client.api import ObjectVersionTypeDefIterproxy
from .better_client.api import DeleteMarkerEntryTypeDefIterproxy
from .better_client.api import ListObjectVersionsOutputTypeDefIterproxy
from .better_client.api import paginate_list_object_versions
from .better_client.api import delete_object
from .better_client.api import delete_dir
from .better_client.api import delete_object_versions

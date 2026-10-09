# -*- coding: utf-8 -*-

"""
The public API of ``s3pathlib``.

Usage::

    from s3pathlib.api import S3Path
    from s3pathlib.api import s3_context
    from s3pathlib.api import exc

    try:
        S3Path("bucket", "file.txt").head_object()
    except exc.S3FileNotExist:
        ...
"""
from iterproxy import and_
from iterproxy import or_
from iterproxy import not_

from . import exc
from . import utils
from .aws import s3_context
from .constants import AwsPartitionEnum
from .core import S3Path
from .core.iter_objects import S3PathIterProxy
from .core.serde import S3PathDict
from .content_type import ContentTypeEnum
from .validate import validate_s3_bucket
from .validate import validate_s3_key
from .validate import validate_s3_uri
from .validate import validate_s3_arn

from .better_client import api as better_client

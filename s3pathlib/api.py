# -*- coding: utf-8 -*-

"""
The public API of ``s3pathlib``.

Usage::

    from s3pathlib.api import S3Path
    from s3pathlib.api import context
"""
from iterproxy import and_
from iterproxy import or_
from iterproxy import not_

from . import utils
from .aws import context
from .core import S3Path
from .core.serde import S3PathDict
from .content_type import ContentTypeEnum
from .validate import validate_s3_bucket
from .validate import validate_s3_key
from .validate import validate_s3_uri
from .validate import validate_s3_arn

from .better_client import api as better_client

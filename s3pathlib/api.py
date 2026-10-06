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

from .better_client import api as better_client

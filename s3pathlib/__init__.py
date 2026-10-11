# -*- coding: utf-8 -*-

"""
Import the public API from ``s3pathlib.api``::

    from s3pathlib.api import S3Path
"""

from ._version import __version__
from ._version import __short_description__
from ._version import __license__
from ._version import __author__
from ._version import __author_email__
from ._version import __maintainer__
from ._version import __maintainer_email__

# The names that ``from s3pathlib import ...`` gave in 2.x. They moved to
# ``s3pathlib.api`` in 3.0.0; asking for one raises an ImportError that says
# where it is. Remove this in 4.0.0.
_MOVED_TO_API = (
    "S3Path",
    "s3_context",
    "ContentTypeEnum",
    "validate_s3_bucket",
    "validate_s3_key",
    "validate_s3_uri",
    "validate_s3_arn",
    "and_",
    "or_",
    "not_",
)


def __getattr__(name):
    if name in _MOVED_TO_API:
        # an ImportError, not an AttributeError: ``from s3pathlib import X``
        # replaces an AttributeError with a generic "cannot import name"
        raise ImportError(
            f"'from s3pathlib import {name}' was removed in 3.0.0; "
            f"use 'from s3pathlib.api import {name}'",
            name="s3pathlib",
        )
    raise AttributeError(f"module 's3pathlib' has no attribute {name!r}")

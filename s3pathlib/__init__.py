# -*- coding: utf-8 -*-

from ._version import __version__
from ._version import __short_description__
from ._version import __license__
from ._version import __author__
from ._version import __author_email__
from ._version import __maintainer__
from ._version import __maintainer_email__

try:
    from . import utils
    from . import api
    from .aws import context
    from .core import S3Path
    from .content_type import ContentTypeEnum
    from .validate import validate_s3_bucket
    from .validate import validate_s3_key
    from .validate import validate_s3_uri
    from .validate import validate_s3_arn

    from iterproxy import and_, or_, not_
except ImportError:  # pragma: no cover
    pass
except:  # pragma: no cover
    raise

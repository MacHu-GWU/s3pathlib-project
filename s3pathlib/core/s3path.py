# -*- coding: utf-8 -*-

"""
The ``S3Path`` public API class.
"""

from __future__ import annotations

from .base import BaseS3Path
from .is_test import IsTestAPIMixin
from .uri import UriAPIMixin
from .relative import RelativePathAPIMixin
from .comparison import ComparisonAPIMixin
from .attribute import AttributeAPIMixin
from .joinpath import JoinPathAPIMixin
from .mutate import MutateAPIMixin
from .metadata import MetadataAPIMixin
from .bucket import BucketAPIMixin
from .tagging import TaggingAPIMixin
from .iter_objects import IterObjectsAPIMixin
from .iter_object_versions import IterObjectVersionsAPIMixin
from .exists import ExistsAPIMixin
from .rw import ReadAndWriteAPIMixin
from .delete import DeleteAPIMixin
from .upload import UploadAPIMixin
from .copy import CopyAPIMixin
from .sync import SyncAPIMixin
from .serde import SerdeAPIMixin
from .opener import OpenerAPIMixin


# The order of the bases is the MRO. The mixins do not define the same name,
# so the order does not change any behavior (tests/core/test_core_s3path.py
# checks it); BaseS3Path has to come first, it holds the state.
class S3Path(
    BaseS3Path,
    IsTestAPIMixin,
    UriAPIMixin,
    RelativePathAPIMixin,
    ComparisonAPIMixin,
    AttributeAPIMixin,
    JoinPathAPIMixin,
    MutateAPIMixin,
    MetadataAPIMixin,
    BucketAPIMixin,
    TaggingAPIMixin,
    IterObjectsAPIMixin,
    IterObjectVersionsAPIMixin,
    ExistsAPIMixin,
    ReadAndWriteAPIMixin,
    DeleteAPIMixin,
    UploadAPIMixin,
    CopyAPIMixin,
    SyncAPIMixin,
    SerdeAPIMixin,
    OpenerAPIMixin,
):
    """
    The ``S3Path`` public API class.
    """

    __slots__ = ()

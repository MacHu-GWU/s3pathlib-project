# -*- coding: utf-8 -*-

"""
serialization and deserialization.
"""

from __future__ import annotations

import typing as T

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class SerdeAPIMixin:
    """
    A mixin class that implements the serialization and deserialization.
    """

    def to_dict(self: S3Path) -> dict:
        """
        Serialize to Python dict
        """
        return {
            "bucket": self._bucket,
            "parts": self._parts,
            "is_dir": self._is_dir,
        }

    @classmethod
    def from_dict(cls: S3Path, dct: dict) -> S3Path:
        """
        Deserialize from Python dict
        """
        return cls._from_parsed_parts(
            bucket=dct["bucket"],
            parts=dct["parts"],
            is_dir=dct["is_dir"],
        )

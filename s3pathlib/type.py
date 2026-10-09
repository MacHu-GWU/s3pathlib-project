# -*- coding: utf-8 -*-

"""
Type hint variables.
"""

from __future__ import annotations

import os

TagType = dict[str, str]  # {"Key": "Value"}
TagSetType = list[dict[str, str]]  # [{"Key": "Value"}, ...]

MetadataType = dict[str, str]  # {"Key": "Value"}
# a local path: str, pathlib.Path, or any os.PathLike (e.g. pathlib_mate.Path)
PathType = str | os.PathLike

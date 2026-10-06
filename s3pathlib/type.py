# -*- coding: utf-8 -*-

"""
Type hint variables.
"""

from __future__ import annotations

from pathlib import Path as Path1
from pathlib_mate import Path as Path2

TagType = dict[str, str]  # {"Key": "Value"}
TagSetType = list[dict[str, str]]  # [{"Key": "Value"}, ...]

MetadataType = dict[str, str]  # {"Key": "Value"}
PathType = str | Path1 | Path2  # str, pathlib.Path, pathlib_mate.Path

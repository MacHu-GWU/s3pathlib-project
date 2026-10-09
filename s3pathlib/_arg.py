# -*- coding: utf-8 -*-

"""
The "not given" value of the arguments that are passed on to boto3.

The rule for argument defaults:

- An argument passed on to a boto3 call (``version_id``, ``if_match``,
  ``metadata``, ...) defaults to :data:`OPT`, which means "do not send this
  parameter". :func:`remove_optional` drops it before the call.
- ``None`` is not "not given": S3 has no ``None`` value, so botocore rejects it
  with ``ParamValidationError`` before sending the request. Treating ``None`` as
  "not given" would silently drop a condition such as ``if_match=p.etag`` when
  ``p.etag`` is ``None``.
- An argument of s3pathlib itself (``s3_client``, ``limit``, ``region``, ...)
  defaults to ``None`` or a plain value, so users who wrap s3pathlib never need
  to import :data:`OPT`.

This module is private: users leave an argument out instead of passing
:data:`OPT`.
"""

from __future__ import annotations

import typing as T


class _Sentinel:
    """
    A unique value that stays the same object when copied or pickled.
    """

    def __init__(self, name: str):
        self._name = name

    def __repr__(self) -> str:
        return self._name

    def __copy__(self) -> _Sentinel:
        return self

    def __deepcopy__(self, memo: dict) -> _Sentinel:
        return self

    def __reduce__(self) -> str:
        # pickle stores the name of the module global, and loads that object
        return self._name


OPT: T.Any = _Sentinel("OPT")
"""
The default of an argument that is passed on to boto3: "do not send it".
Typed ``Any`` so that a signature can say ``version_id: str = OPT``.
"""

NOT_GIVEN: T.Any = _Sentinel("NOT_GIVEN")
"""
The default of a deprecated argument, to tell whether the caller passed it
(``S3Path.sync(quite=...)``, ``better_client.delete_object(ignore_not_found=...)``).
Remove it in 4.0.0 together with those arguments.
"""


def remove_optional(**kwargs) -> dict[str, T.Any]:
    """
    Return the keyword arguments without the ones whose value is :data:`OPT`.
    ``None`` is kept, so that botocore rejects it.
    """
    return {key: value for key, value in kwargs.items() if value is not OPT}

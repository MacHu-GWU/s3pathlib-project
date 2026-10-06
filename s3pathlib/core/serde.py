# -*- coding: utf-8 -*-

"""
Serialization and deserialization: to / from a dict, and pickle.

**Dict**

:meth:`~SerdeAPIMixin.to_dict` gives an :class:`S3PathDict`, the three fields
that define a path (see :mod:`s3pathlib.core.base`)::

    >>> S3Path("bucket", "folder", "file.txt").to_dict()
    {'bucket': 'bucket', 'parts': ['folder', 'file.txt'], 'is_dir': False}

It only holds the path, not the metadata loaded from S3, and it can be stored
as JSON as it is. ``parts`` is a ``list``, not a ``tuple`` like the internal
``_parts``: the dict is a new copy on every call, so changing it can not
change the path, and a ``list`` is what JSON (and YAML, msgpack, ...) gives
back, so ``json.loads(json.dumps(d)) == d``. It is also the type of
``S3Path.parts``.

**Pickle**

Pickling (and ``copy.copy`` / ``copy.deepcopy``) keeps the path and the
metadata loaded from S3, but not the cached hash: the hash of a ``str`` is
different in every Python process, so a cached hash would be wrong after
loading it in another process (e.g. with ``multiprocessing``).
"""

from __future__ import annotations

import typing as T

from ..exc import S3ValidationError
from .base import _ensure_valid_state

if T.TYPE_CHECKING:  # pragma: no cover
    from .s3path import S3Path


class S3PathDict(T.TypedDict):
    """
    The dict form of an :class:`~s3pathlib.core.s3path.S3Path`, returned by
    ``S3Path.to_dict`` and accepted by ``S3Path.from_dict``.

    - ``bucket``: the bucket, ``None`` for a relative path or void.
    - ``parts``: the parts of the key, e.g. ``["folder", "file.txt"]``.
    - ``is_dir``: ``True`` for a dir, ``False`` for a file, ``None`` for void.
    """

    bucket: str | None
    parts: list[str]
    is_dir: bool | None


_DICT_KEYS = ("bucket", "parts", "is_dir")

# the fields saved by pickle; the caches (``_hash``, ``_cached_cparts``) are not
_PICKLE_FIELDS = ("_bucket", "_parts", "_is_dir", "_meta")


class SerdeAPIMixin:
    """
    A mixin class that implements the serialization and deserialization.
    """

    def to_dict(self: S3Path) -> S3PathDict:
        """
        Serialize to Python dict. See the module docstring for the format.

        Example::

            >>> S3Path("bucket", "folder/").to_dict()
            {'bucket': 'bucket', 'parts': ['folder'], 'is_dir': True}
        """
        return {
            "bucket": self._bucket,
            "parts": list(self._parts),
            "is_dir": self._is_dir,
        }

    @classmethod
    def from_dict(cls: type[S3Path], dct: S3PathDict) -> S3Path:
        """
        Deserialize from Python dict, the inverse of :meth:`to_dict`.
        ``parts`` can be a list or a tuple. Other keys are ignored.

        Example::

            >>> S3Path.from_dict({"bucket": "bucket", "parts": ["folder"], "is_dir": True})
            S3Path('s3://bucket/folder/')

        :raises S3ValidationError: if ``dct`` is not a dict, misses a key, or
            is not a valid path (see :mod:`s3pathlib.core.base`).
        """
        if not isinstance(dct, dict):
            raise S3ValidationError(
                f"dct has to be a dict, got {type(dct).__name__}: {dct!r}"
            )
        missing = list()
        for key in _DICT_KEYS:
            if key not in dct:
                missing.append(key)
        if missing:
            raise S3ValidationError(
                f"dct misses the key(s) {missing}, it has to have {list(_DICT_KEYS)}"
            )
        return cls._from_parsed_parts(
            bucket=dct["bucket"],
            parts=dct["parts"],
            is_dir=dct["is_dir"],
        )

    def __getstate__(self: S3Path) -> dict:
        """
        The state saved by pickle: the path and the metadata, without caches.
        """
        state = dict()
        for field in _PICKLE_FIELDS:
            state[field] = getattr(self, field)
        return state

    def __setstate__(self: S3Path, state: dict | tuple) -> None:
        """
        Restore the state saved by :meth:`__getstate__`, and check that it is
        a valid path.

        A pickle made by s3pathlib 2.x has the default state of a class with
        ``__slots__``: a ``(dict, slots_dict)`` tuple, which also works. Its
        cached hash is ignored.
        """
        if isinstance(state, tuple):
            dict_state, slots_state = state
            merged = dict()
            if dict_state:
                merged.update(dict_state)
            merged.update(slots_state)
            state = merged
        parts = tuple(state["_parts"])
        _ensure_valid_state(state["_bucket"], parts, state["_is_dir"])
        self._bucket = state["_bucket"]
        self._parts = parts
        self._is_dir = state["_is_dir"]
        self._meta = state.get("_meta")

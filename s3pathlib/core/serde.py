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

Pickling keeps the path and the metadata snapshot loaded from S3 (see
:mod:`s3pathlib.core.metadata`), but not the cached hash: the hash of a ``str``
is different in every Python process, so a cached hash would be wrong after
loading it in another process (e.g. with ``multiprocessing``). It does not keep
the S3 client that loaded the metadata either (a client cannot be pickled), so
a loaded path uses ``s3_context`` to load the missing metadata fields.

``copy.copy`` and ``copy.deepcopy`` keep the same things, plus the S3 client
(shared, not copied).
"""

from __future__ import annotations

import typing as T
import copy

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

# the fields saved by pickle; the caches (``_hash``, ``_cached_cparts``) and
# the S3 client (``_s3_client``, which cannot be pickled) are not
_PICKLE_FIELDS = ("_bucket", "_parts", "_is_dir", "_meta", "_meta_complete")


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
        The state saved by pickle: the path and the metadata snapshot, without
        caches and without the S3 client that loaded the metadata (a loaded
        copy uses ``s3_context`` to load the missing metadata fields).
        """
        state = dict()
        for field in _PICKLE_FIELDS:
            state[field] = getattr(self, field)
        return state

    def __copy__(self: S3Path) -> S3Path:
        new = object.__new__(type(self))
        new.__setstate__(self.__getstate__())
        new._s3_client = self._s3_client
        return new

    def __deepcopy__(self: S3Path, memo: dict) -> S3Path:
        new = object.__new__(type(self))
        new.__setstate__(copy.deepcopy(self.__getstate__(), memo))
        new._s3_client = self._s3_client
        return new

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
        # pickles made before 3.0 have no _meta_complete; treating their
        # metadata as partial only costs a head_object call when needed
        self._meta_complete = state.get("_meta_complete", False)
        self._s3_client = None

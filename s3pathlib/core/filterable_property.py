# -*- coding: utf-8 -*-

"""
Many popular ORM framework offers a popular feature that can use the following
syntax to filter an iterable of object by its attributes. For example, in
`sqlalchemy <https://docs.sqlalchemy.org/en/14/orm/quickstart.html#simple-select>`_
you can use:

.. code-block:: python

    class User(Base):
        name: str

    select(User).where(User.name == "alice")

This module implements the same feature. On an instance, a
:class:`FilterableProperty` is a read-only property; on the class, comparing
it gives a filter function, for ``S3PathIterProxy.filter``:

.. code-block:: python

    s3dir.iter_objects().filter(S3Path.ext == ".csv")
    s3dir.iter_objects().filter(S3Path.size >= 1000, S3Path.ext == ".csv")
    s3dir.iter_objects().filter(or_(S3Path.ext == ".csv", S3Path.ext == ".tsv"))

The filter functions are:

- ``==``, ``!=``, ``>``, ``<``, ``>=``, ``<=``, and the same as methods:
  ``equal_to``, ``not_equal_to``, ``greater``, ``less``, ``greater_equal``,
  ``less_equal``.
- ``between(lower, upper)``: ``lower <= value <= upper``.
- ``startswith(prefix)``, ``endswith(suffix)``: for a ``str`` attribute.
- ``contains(item)``: ``item in value``, for a ``str`` or a ``list``.

``filter(a, b)`` keeps the items that pass both ``a`` and ``b``, and so does
``filter(a).filter(b)``. Use ``and_``, ``or_`` and ``not_`` from
``s3pathlib.api`` for other combinations.

Notes:

- A filter function calls the property, so if the property raises for an
  item, the filter raises too, e.g. ``S3Path.bucket.startswith("b")`` on a
  relative path, whose ``bucket`` is ``None``. The error is not hidden.
- Comparing on the class always gives a function, never a ``bool``: even
  ``S3Path.key == S3Path.key`` is a (truthy) function. That is the price of
  this syntax, the same as in sqlalchemy.
"""

from __future__ import annotations

import typing as T
import functools

FilterableType = T.TypeVar("FilterableType")


class FilterableProperty(T.Generic[FilterableType]):
    """
    A descriptor decorator that convert a method to a property method.
    ALSO, convert the class attribute to be a comparable object that returns
    filter function for ``iterproxy.IterProxy.filter`` (e.g.
    ``S3PathIterProxy.filter``) to use.

    .. code-block:: python

        class User:
            def __init__(self, name: str):
                self.name = name

            @FilterableProperty
            def username(self) -> str:
                return self.name

        filter_function = User.username == "alice"
        assert filter_function(User(name="alice")) == True
        assert filter_function(User(name="bob")) == False
    """

    def __init__(self, func: T.Callable[[FilterableType], T.Any]):
        functools.wraps(func)(self)
        self._func = func

    def __get__(self, obj: FilterableType | None, obj_type):
        if obj is None:
            return self
        return self._func(obj)

    def __set__(self, obj: FilterableType, value: T.Any):
        raise AttributeError(
            f"can't set attribute {type(obj).__name__}.{self.__name__}"
        )

    def __delete__(self, obj: FilterableType):
        raise AttributeError(
            f"can't delete attribute {type(obj).__name__}.{self.__name__}"
        )

    def __eq__(self, other):
        def filter_(obj):
            return self._func(obj) == other

        return filter_

    def __ne__(self, other):
        def filter_(obj):
            return self._func(obj) != other

        return filter_

    def __gt__(self, other):
        def filter_(obj):
            return self._func(obj) > other

        return filter_

    def __lt__(self, other):
        def filter_(obj):
            return self._func(obj) < other

        return filter_

    def __ge__(self, other):
        def filter_(obj):
            return self._func(obj) >= other

        return filter_

    def __le__(self, other):
        def filter_(obj):
            return self._func(obj) <= other

        return filter_

    def equal_to(self, other):
        """
        Return a filter function that returns True
        only if ``FilterableType.attribute_name == other``
        """
        return self.__eq__(other)

    def not_equal_to(self, other):
        """
        Return a filter function that returns True
        only if ``FilterableType.attribute_name != other``
        """
        return self.__ne__(other)

    def greater(self, other):
        """
        Return a filter function that returns True
        only if ``FilterableType.attribute_name > other``
        """
        return self.__gt__(other)

    def less(self, other):
        """
        Return a filter function that returns True
        only if ``FilterableType.attribute_name < other``
        """
        return self.__lt__(other)

    def greater_equal(self, other):
        """
        Return a filter function that returns True
        only if ``FilterableType.attribute_name >= other``
        """
        return self.__ge__(other)

    def less_equal(self, other):
        """
        Return a filter function that returns True
        only if ``FilterableType.attribute_name <= other``
        """
        return self.__le__(other)

    def between(self, lower, upper):
        """
        Return a filter function that returns True
        only if ``lower <= FilterableType.attribute_name <= upper``
        """

        def filter_(obj):
            return lower <= self._func(obj) <= upper

        return filter_

    def startswith(self, other: str):
        """
        Return a filter function that returns True
        only if ``FilterableType.attribute_name.startswith(other)``.
        The attribute has to be a string attribute.
        """

        def filter_(obj):
            return self._func(obj).startswith(other)

        return filter_

    def endswith(self, other: str):
        """
        Return a filter function that returns True
        only if ``FilterableType.attribute_name.endswith(other)``.
        The attribute has to be a string attribute.
        """

        def filter_(obj):
            return self._func(obj).endswith(other)

        return filter_

    def contains(self, other):
        """
        Return a filter function that returns True
        only if ``other in FilterableType.attribute_name``
        """

        def filter_(obj):
            return other in self._func(obj)

        return filter_

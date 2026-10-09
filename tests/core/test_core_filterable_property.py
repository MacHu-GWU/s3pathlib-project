# -*- coding: utf-8 -*-

"""
Test ``FilterableProperty``.

Test order:

1. the descriptor: a read-only property on an instance, a filter factory on
   the class;
2. every filter function, on a pass and a fail case, and the named methods
   agree with the operators;
3. filtering ``S3Path`` objects with ``S3PathIterProxy``, as in the docs;
4. errors of the property are not hidden.

Pure logic, but it follows the moto mixin pattern like the other ``core``
tests.
"""

import operator

import pytest

from s3pathlib.api import S3Path
from s3pathlib.api import and_
from s3pathlib.api import or_
from s3pathlib.api import not_
from s3pathlib.core.filterable_property import FilterableProperty
from s3pathlib.core.iter_objects import S3PathIterProxy
from s3pathlib.tests import run_cov_test
from s3pathlib.tests.mock_aws import BaseTest


class User:
    def __init__(self, name: str, age: int = 0, tags: list[str] | None = None):
        self.name = name
        self.age = age
        self.tags = tags or []

    @FilterableProperty
    def username(self) -> str:
        """
        The user name.
        """
        return self.name

    @FilterableProperty
    def user_age(self) -> int:
        return self.age

    @FilterableProperty
    def user_tags(self) -> list[str]:
        return self.tags


ALICE = User("alice", age=30, tags=["admin", "dev"])
BOB = User("bob", age=20, tags=["dev"])

PATHS = [
    S3Path("bucket", "a.txt"),
    S3Path("bucket", "data", "b.csv"),
    S3Path("bucket", "data", "subfolder", "c.csv"),
    S3Path("other-bucket", "d.json"),
]


def keys(proxy) -> list[str]:
    return [p.key for p in proxy]


class FilterablePropertyMixin(BaseTest):
    module = "core.filterable_property"

    # --------------------------------------------------------------------------
    # 1. the descriptor
    # --------------------------------------------------------------------------
    def test_get(self):
        """
        On an instance it is the value; on the class it is the descriptor.
        """
        assert ALICE.username == "alice"
        assert isinstance(User.username, FilterableProperty)

    def test_keeps_name_and_doc(self):
        """
        ``functools.wraps`` keeps the name and docstring, for Sphinx and
        ``help()``.
        """
        assert User.username.__name__ == "username"
        assert User.username.__doc__.strip() == "The user name."

    def test_set_and_delete_raise(self):
        """
        It is read-only; the message names the actual class (before 3.0 it
        always said ``S3Path``, and ``del`` only said ``__delete__``).
        """
        user = User("alice")
        with pytest.raises(AttributeError, match="can't set attribute User.username"):
            user.username = "bob"
        with pytest.raises(AttributeError, match="can't delete attribute User.username"):
            del user.username
        p = S3Path("bucket", "a.txt")
        with pytest.raises(AttributeError, match="can't set attribute S3Path.key"):
            p.key = "b.txt"
        with pytest.raises(AttributeError, match="can't delete attribute S3Path.key"):
            del p.key

    def test_compare_on_class_gives_function(self):
        """
        Comparing on the class always gives a function, never a ``bool``.
        """
        assert callable(User.username == "alice")
        assert callable(User.username == User.username)

    # --------------------------------------------------------------------------
    # 2. filter functions
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "make, passes, fails",
        [
            pytest.param(lambda: User.username == "alice", ALICE, BOB, id="eq"),
            pytest.param(lambda: User.username != "alice", BOB, ALICE, id="ne"),
            pytest.param(lambda: User.user_age > 25, ALICE, BOB, id="gt"),
            pytest.param(lambda: User.user_age < 25, BOB, ALICE, id="lt"),
            pytest.param(lambda: User.user_age >= 30, ALICE, BOB, id="ge"),
            pytest.param(lambda: User.user_age <= 20, BOB, ALICE, id="le"),
            pytest.param(lambda: User.user_age.between(25, 35), ALICE, BOB, id="between"),
            pytest.param(lambda: User.username.startswith("al"), ALICE, BOB, id="startswith"),
            pytest.param(lambda: User.username.endswith("ob"), BOB, ALICE, id="endswith"),
            pytest.param(lambda: User.username.contains("lic"), ALICE, BOB, id="contains-str"),
            pytest.param(lambda: User.user_tags.contains("admin"), ALICE, BOB, id="contains-list"),
        ],
    )
    def test_filter_function(self, make, passes, fails):
        """
        Each filter function keeps the item that matches and drops the other.
        """
        filter_ = make()
        assert filter_(passes) is True
        assert filter_(fails) is False

    @pytest.mark.parametrize("value", [19, 20, 21, 29, 30, 31])
    @pytest.mark.parametrize(
        "method, op",
        [
            pytest.param("equal_to", operator.eq, id="equal_to"),
            pytest.param("not_equal_to", operator.ne, id="not_equal_to"),
            pytest.param("greater", operator.gt, id="greater"),
            pytest.param("less", operator.lt, id="less"),
            pytest.param("greater_equal", operator.ge, id="greater_equal"),
            pytest.param("less_equal", operator.le, id="less_equal"),
        ],
    )
    def test_named_method_is_operator(self, method, op, value):
        """
        Each named method gives the same result as its operator, around the
        boundaries; before 3.0 ``greater_equal`` and ``less_equal`` did
        ``==``.
        """
        by_method = getattr(User.user_age, method)(value)
        by_operator = op(User.user_age, value)
        for user in [ALICE, BOB]:
            assert by_method(user) is by_operator(user)
            assert by_method(user) is op(user.age, value)

    @pytest.mark.parametrize(
        "lower, upper, expected",
        [
            pytest.param(20, 30, True, id="both-ends-included"),
            pytest.param(30, 30, True, id="single-value"),
            pytest.param(31, 40, False, id="below"),
            pytest.param(10, 29, False, id="above"),
        ],
    )
    def test_between_boundaries(self, lower, upper, expected):
        """
        Both ends are included.
        """
        assert User.user_age.between(lower, upper)(ALICE) is expected

    # --------------------------------------------------------------------------
    # 3. with S3PathIterProxy
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "filters, expected",
        [
            pytest.param((S3Path.ext == ".csv",), ["data/b.csv", "data/subfolder/c.csv"], id="ext"),
            pytest.param((S3Path.bucket != "bucket",), ["d.json"], id="bucket"),
            pytest.param(
                (S3Path.basename.startswith("b"),), ["data/b.csv"], id="basename-startswith"
            ),
            pytest.param(
                (S3Path.abspath.contains("subfolder"),),
                ["data/subfolder/c.csv"],
                id="abspath-contains",
            ),
            pytest.param(
                (S3Path.parts.contains("data"),),
                ["data/b.csv", "data/subfolder/c.csv"],
                id="parts-contains",
            ),
            pytest.param(
                (S3Path.ext == ".csv", S3Path.dirname == "data"),
                ["data/b.csv"],
                id="many-args-are-and",
            ),
            pytest.param(
                (and_(S3Path.ext == ".csv", S3Path.dirname == "subfolder"),),
                ["data/subfolder/c.csv"],
                id="and",
            ),
            pytest.param(
                (or_(S3Path.ext == ".txt", S3Path.ext == ".json"),),
                ["a.txt", "d.json"],
                id="or",
            ),
            pytest.param((not_(S3Path.ext == ".csv"),), ["a.txt", "d.json"], id="not"),
        ],
    )
    def test_filter_s3path(self, filters, expected):
        """
        The filters work with ``S3PathIterProxy.filter``, as in the docs.
        """
        assert keys(S3PathIterProxy(iter(PATHS)).filter(*filters)) == expected

    def test_filter_chained(self):
        """
        Chained ``filter`` calls are joined with AND, the same as many
        arguments.
        """
        proxy = (
            S3PathIterProxy(iter(PATHS))
            .filter(S3Path.ext == ".csv")
            .filter(S3Path.basename.endswith("c.csv"))
        )
        assert keys(proxy) == ["data/subfolder/c.csv"]

    # --------------------------------------------------------------------------
    # 4. errors are not hidden
    # --------------------------------------------------------------------------
    def test_property_error_is_raised(self):
        """
        If the property raises (here ``bucket`` is ``None`` for a relative
        path), the filter raises too, instead of silently dropping the item.
        """
        filter_ = S3Path.bucket.startswith("b")
        assert filter_(S3Path("bucket", "a.txt")) is True
        with pytest.raises(AttributeError):
            filter_(S3Path.make_relpath("a.txt"))


class TestMock(FilterablePropertyMixin):
    use_mock = True


class TestRealAws(FilterablePropertyMixin):
    use_mock = False


if __name__ == "__main__":
    run_cov_test(
        __file__,
        module="s3pathlib.core.filterable_property",
        preview=False,
    )

from typing import Any, ClassVar, Generic, TypeVar

from nameparser import HumanName
from nameparser.config import Constants

T = TypeVar('T')


class HumanNameTestBase(Generic[T]):
    """Shared assert helpers for the parsing tests.

    Formerly subclassed unittest.TestCase. It is now a plain class so pytest can
    apply the parametrized dual-run fixture in conftest.py — parametrized
    fixtures do not apply to unittest.TestCase subclasses. The assert* methods
    are thin shims so existing test bodies move over unchanged.
    """

    def m(self, actual: T, expected: T, hn: HumanName) -> None:
        """assertEqual with a better message and awareness of hn.C.empty_attribute_default"""
        expected_ = expected or hn.C.empty_attribute_default
        try:
            assert actual == expected_, f"{actual!r} != {expected!r} for {hn.original!r}\n{hn!r}"
        except UnicodeDecodeError:
            assert actual == expected_, f"actual={actual!r} != expected={expected_!r}"

    def assertEqual(self, first: object, second: object, msg: object = None) -> None:
        assert first == second, msg

    def assertTrue(self, expr: object, msg: object = None) -> None:
        assert expr, msg

    def assertFalse(self, expr: object, msg: object = None) -> None:
        assert not expr, msg

    def assertIn(self, member: object, container: object, msg: object = None) -> None:
        assert member in container, msg  # type: ignore[operator]

    def assertNotEqual(self, first: object, second: object, msg: object = None) -> None:
        assert first != second, msg

    def assertNotIn(self, member: object, container: object, msg: object = None) -> None:
        assert member not in container, msg  # type: ignore[operator]

    def assertIs(self, first: object, second: object, msg: object = None) -> None:
        assert first is second, msg or f"{first!r} is not {second!r}"

    def assertIsNot(self, first: object, second: object, msg: object = None) -> None:
        assert first is not second, msg or f"{first!r} is {second!r}"

    def assertIsNone(self, expr: object, msg: object = None) -> None:
        assert expr is None, msg or f"{expr!r} is not None"

    def assertIsNotNone(self, expr: object, msg: object = None) -> None:
        assert expr is not None, msg or "unexpectedly None"


class FlaggedConstantsTestBase(HumanNameTestBase[T]):
    """Base for test classes that parse with a dedicated, flagged Constants.

    Subclasses set ``constants_kwargs``; each test method gets a fresh
    ``Constants(**constants_kwargs)`` via ``setup_method``, and ``hn()``
    parses with it.
    """

    constants_kwargs: ClassVar[dict[str, Any]] = {}

    def setup_method(self) -> None:
        self.C = Constants(**self.constants_kwargs)

    def hn(self, name: str) -> HumanName:
        return HumanName(name, constants=self.C)

from typing import Generic, TypeVar

from nameparser import HumanName

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
            assert actual == expected_, "'%s' != '%s' for '%s'\n%r" % (
                actual,
                expected,
                hn.original,
                hn,
            )
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

    def assertNotIn(self, member: object, container: object, msg: object = None) -> None:
        assert member not in container, msg  # type: ignore[operator]

    def assertIs(self, first: object, second: object, msg: object = None) -> None:
        assert first is second, msg

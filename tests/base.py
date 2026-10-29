from typing import Any, ClassVar

from nameparser import ParsedName, Parser, Policy


class ParsedNameTestBase:
    """Shared assert helpers for the parsing tests ported from the 1.x suite.

    These tests asserted through ``HumanName`` until 3.0 removed it; they
    now assert the same readings through :func:`nameparser.parse`, with
    ``first``/``last`` read as ``given``/``family``. The assert* methods
    are thin shims, kept from the suite's unittest days so the test
    bodies stayed unchanged.
    """

    def m(self, actual: object, expected: object, name: ParsedName) -> None:
        """assertEqual with a message naming the input; an empty field is ''."""
        expected_ = expected or ''
        assert actual == expected_, f"{actual!r} != {expected!r} for {name.original!r}\n{name!r}"

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


class FlaggedPolicyTestBase(ParsedNameTestBase):
    """Base for test classes that parse with a dedicated, flagged Policy.

    Subclasses set ``policy_kwargs``; each test method gets a fresh
    ``Parser(policy=Policy(**policy_kwargs))`` via ``setup_method``, and
    ``hn()`` parses with it.
    """

    policy_kwargs: ClassVar[dict[str, Any]] = {}

    def setup_method(self) -> None:
        self.parser = Parser(policy=Policy(**self.policy_kwargs))

    def hn(self, name: str) -> ParsedName:
        return self.parser.parse(name)

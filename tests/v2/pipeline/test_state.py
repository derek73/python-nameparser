import dataclasses

from nameparser._lexicon import Lexicon
from nameparser._pipeline._state import ParseState, Structure, WorkToken
from nameparser._policy import Policy
from nameparser._types import Role, Span


def _state(text: str) -> ParseState:
    return ParseState(original=text, lexicon=Lexicon.empty(), policy=Policy())


def test_state_defaults_are_empty() -> None:
    s = _state("John Smith")
    assert s.tokens == () and s.segments == () and s.pieces == ()
    assert s.structure is Structure.NO_COMMA
    assert s.ambiguities == () and s.extracted == () and s.masked == ()
    assert s.comma_offsets == () and s.dropped == () and s.piece_tags == ()


def test_state_is_frozen_and_replace_works() -> None:
    s = _state("x")
    tok = WorkToken("x", Span(0, 1))
    s2 = dataclasses.replace(s, tokens=(tok,))
    assert s.tokens == () and s2.tokens == (tok,)
    assert s2.tokens[0].role is None and s2.tokens[0].tags == frozenset()


def test_worktoken_carries_optional_role() -> None:
    t = WorkToken("Jack", Span(6, 10), role=Role.NICKNAME)
    assert t.role is Role.NICKNAME

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


def test_stage_field_ownership() -> None:
    # The ParseState docstring's ownership map, pinned mechanically: run
    # the whole case corpus through the fold stage by stage and assert
    # each stage only changes the fields it owns. Converts the prose
    # contract into a test (a future stage clobbering another stage's
    # field fails here, not in a distant assertion).
    import dataclasses as _dc

    from nameparser import Lexicon as _Lexicon
    from nameparser._pipeline import STAGES

    from ..cases import CASES

    ownership = {
        "extract_delimited": {"extracted", "masked", "ambiguities"},
        "tokenize": {"tokens", "comma_offsets"},
        "segment": {"segments", "structure", "ambiguities"},
        "classify": {"tokens"},
        "group": {"tokens", "pieces", "piece_tags", "dropped"},
        "assign": {"tokens", "ambiguities"},
        "post_rules": {"tokens"},
    }
    assert {s.__name__ for s in STAGES} == set(ownership)
    # Within the tokens themselves the contract is finer: texts and
    # spans are fixed at tokenize (the anti-#100 invariant -- tokens
    # are never re-created), classify touches only tags, and the
    # role-assigning stages touch only roles (group also tags, for the
    # ph-d "joined" marker).
    token_ownership = {
        "classify": {"tags"},
        "group": {"tags", "role"},
        "assign": {"role"},
        "post_rules": {"role"},
    }
    for case in CASES:
        state = ParseState(original=case.text, lexicon=_Lexicon.default(),
                           policy=case.policy or Policy())
        for stage in STAGES:
            before = {f.name: getattr(state, f.name)
                      for f in _dc.fields(state)}
            state = stage(state)
            changed = {name for name, value in before.items()
                       if getattr(state, name) != value}
            assert changed <= ownership[stage.__name__], (
                f"{case.id}: {stage.__name__} changed {changed - ownership[stage.__name__]}")
            if stage.__name__ not in token_ownership:
                continue
            allowed = token_ownership[stage.__name__]
            assert len(state.tokens) == len(before["tokens"]), (
                f"{case.id}: {stage.__name__} changed the token count")
            for old, new in zip(before["tokens"], state.tokens):
                token_changed = {
                    f.name for f in _dc.fields(old)
                    if getattr(old, f.name) != getattr(new, f.name)}
                assert token_changed <= allowed, (
                    f"{case.id}: {stage.__name__} changed token fields "
                    f"{token_changed - allowed} on {old.text!r}")

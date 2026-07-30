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
    assert s.segmenter is None


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
        # tokenize also rewrites ambiguities: extract_delimited runs
        # before tokens exist, so its UNBALANCED_DELIMITER entries carry
        # a character offset that tokenize resolves to a token index
        "tokenize": {"tokens", "comma_offsets", "ambiguities"},
        "segment": {"segments", "structure", "ambiguities"},
        # script_segment splits one unspaced CJK token into n+1 pieces
        # (n = 1 from the vocabulary, any n from a segmenter), so it
        # rewrites tokens and shifts every later index the earlier
        # stages recorded -- the segment runs included. It is
        # deliberately absent from token_ownership below, whose
        # token-count assert is the one contract this stage is exempt
        # from. structure and segmenter it only READS (the
        # FAMILY_COMMA opt-out, and the hook it consults on a
        # vocabulary decline).
        "script_segment": {"tokens", "segments", "ambiguities"},
        # classify also emits SUFFIX_OR_NICKNAME: the delimiter escape
        # that decides it lives in extract_delimited, which has no token
        # index to point at, so the report is raised here instead
        "classify": {"tokens", "ambiguities"},
        # group also emits PARTICLE_OR_GIVEN: the prefix chain takes
        # the particle branch of a fork whose given branch _assign
        # takes, so each stage reports the side it decides
        "group": {"tokens", "pieces", "piece_tags", "dropped",
                  "ambiguities"},
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
        # post_rules also tags: the middle_as_family fold marks folded
        # tokens vocab:folded-middle for the family view's prepend order
        "post_rules": {"role", "tags"},
    }
    for case in CASES:
        if case.locale is not None:
            # locale rows dissolve into a Policy only through parser_for
            # (nameparser._parser); this test exercises the raw stage
            # pipeline directly, and the same inputs already run here
            # under the equivalent synthetic Policy row (_ES/_TK) --
            # covering them again through a resolved locale policy would
            # be redundant, not additive.
            continue
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

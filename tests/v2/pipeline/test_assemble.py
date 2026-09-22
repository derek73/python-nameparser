from nameparser._lexicon import Lexicon
from nameparser._pipeline import run
from nameparser._pipeline._assemble import assemble
from nameparser._pipeline._state import ParseState, WorkToken
from nameparser._policy import Policy
from nameparser._types import AmbiguityKind, ParsedName, Role, Span

_LEX = Lexicon(
    titles=frozenset({"dr"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
    suffix_words=frozenset({"iii"}),
    maiden_markers=frozenset({"née"}),
)


def _parse(text: str) -> ParsedName:
    return assemble(run(ParseState(original=text, lexicon=_LEX,
                                   policy=Policy())))


def test_assemble_produces_validated_parsedname() -> None:
    pn = _parse("Dr. Juan de la Vega III")
    assert pn.title == "Dr."
    assert pn.given == "Juan"
    assert pn.family == "de la Vega"
    assert pn.family_base == "Vega"          # particle tags carried over
    assert pn.family_particles == "de la"
    assert pn.suffix == "III"
    assert pn.original == "Dr. Juan de la Vega III"
    for t in pn.tokens:
        assert t.span is not None
        assert t.text == pn.original[t.span.start:t.span.end]


def test_assemble_materializes_ambiguities_on_final_tokens() -> None:
    pn = _parse("Van Johnson")
    assert len(pn.ambiguities) == 1
    amb = pn.ambiguities[0]
    assert amb.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert amb.tokens[0] is pn.tokens[0]


def test_assemble_drops_structural_marker_tokens() -> None:
    pn = _parse("Jane Smith née Jones")
    assert [t.text for t in pn.tokens] == ["Jane", "Smith", "Jones"]
    assert pn.maiden == "Jones"


def test_empty_parse_is_falsy() -> None:
    assert not _parse("")
    assert not _parse("   ")


def test_content_free_input_parses_to_empty() -> None:
    # An input with no alphanumeric character is not a name. v1 kept
    # it (parse('.') -> first='.'); 2.0 empties it so bool() stays an
    # honest "did I get a name?" check. isalnum is Unicode-aware, so
    # this only fires on pure punctuation/symbols. The test is over the
    # SURVIVING tokens, which since #329 is not the same as over the
    # input -- see cases.py's maiden_marker_delimited_content_free,
    # where dropping a marker is what leaves nothing behind.
    for junk in [".", ".,", "- -", ". .", "'", "∫≜⩕", "()", "-"]:
        pn = _parse(junk)
        assert not pn, f"{junk!r} should be falsy"
        assert pn.tokens == (), f"{junk!r} should have no tokens"
        assert pn.original == junk       # the raw input is still remembered


def test_a_single_letter_of_content_survives() -> None:
    # the guard keys on content, not length: one alnum char is a name
    for real in ["a.", ".a", "a", "李", "О"]:
        assert _parse(real), f"{real!r} should be truthy"


def test_a_content_free_parse_keeps_its_diagnostics() -> None:
    # Emptying the name must not take the reports with it. "Was this
    # input malformed?" is the one question still worth answering when
    # there is no parse left to infer it from, and every junk row in
    # the test above is balanced or delimiter-free, so none of them
    # would notice if the ambiguities were dropped again.
    pn = _parse("(")
    assert not pn and pn.tokens == ()
    assert [a.kind for a in pn.ambiguities] == [
        AmbiguityKind.UNBALANCED_DELIMITER]
    # points at no token, because none survived -- the load-bearing
    # assertion: a fix that materialized a phantom token would
    # otherwise pass, and ParsedName would reject it anyway
    assert pn.ambiguities[0].tokens == ()
    assert len(_parse("((").ambiguities) == 2      # one report each
    # a delimiter that IS balanced still reports nothing
    assert _parse("()").ambiguities == ()


def test_assemble_falls_back_to_given_for_unassigned_role() -> None:
    # This should never happen through the real pipeline -- assign/group
    # always set a role on every main-stream token before assemble runs.
    # This test constructs the invariant violation directly to pin the
    # documented last-resort behavior: assemble() must stay total over
    # its input and never raise just because upstream left a role unset.
    state = ParseState(
        original="Jane",
        lexicon=Lexicon.default(),
        policy=Policy(),
        tokens=(WorkToken("Jane", Span(0, 4), role=None),),
    )
    pn = assemble(state)
    assert pn.tokens[0].role is Role.GIVEN
    assert pn.given == "Jane"


def test_ambiguity_with_all_indices_dropped_is_omitted() -> None:
    # an ambiguity whose referent tokens were ALL dropped describes
    # nothing; emitting it hollow would mislead consumers. Born-empty
    # ambiguities (unbalanced delimiters) are kept -- they are
    # token-independent by design.
    from nameparser._pipeline._state import PendingAmbiguity
    from nameparser._types import AmbiguityKind as AK
    import dataclasses
    state = run(ParseState(original="Jane Smith née Jones", lexicon=_LEX,
                           policy=Policy()))
    née_idx = next(i for i, t in enumerate(state.tokens)
                   if t.text == "née")
    poisoned = dataclasses.replace(
        state, ambiguities=state.ambiguities + (
            PendingAmbiguity(AK.ORDER, "refers only to the marker",
                             (née_idx,)),
            PendingAmbiguity(AK.UNBALANCED_DELIMITER, "born empty", ()),
        ))
    pn = assemble(poisoned)
    kinds = [a.kind for a in pn.ambiguities]
    assert AK.ORDER not in kinds          # fully dangled: omitted
    assert AK.UNBALANCED_DELIMITER in kinds  # born empty: kept


def test_a_connective_or_initial_report_is_withdrawn_where_the_role_is_a_suffix(
) -> None:
    """rules.md#A1, the withdrawal (#397 second review).

    classify's connective-or-initial fork offers a connective and an
    initial and its detail says which it took. A generation is
    neither, so where the parse goes on to role the letter SUFFIX the
    report describes a branch nobody took -- and 'JOHN QUINCY SMITH
    I' carried it beside a `suffix-or-name` saying the same token
    reads as a generational suffix. 'i' is the first word that is
    both a marked connective and suffix vocabulary, so no parse
    before this cycle could reach the shape.

    The shipped vocabulary is what these names need, so `parse` is
    used rather than the trimmed `_LEX` above.
    """
    from nameparser import parse
    withdrawn = {
        "JOHN QUINCY SMITH I": ["suffix-or-name"],
        "john smith i": ["suffix-or-name"],
        "SMITH, JOHN I": [],
        "HENRY I": ["suffix-or-name", "given-or-family"],
    }
    for text, kinds in withdrawn.items():
        name = parse(text)
        assert name.suffix.lower() == "i", text
        assert sorted(a.kind.value for a in name.ambiguities) \
            == sorted(kinds), text
    # the contrast that keeps the withdrawal honest: where the parse
    # roles the same letter a NAME word the fork DID resolve to one
    # of its branches, and the report stands
    for text in ("JOSEP CAROD I ROVIRA", "josep carod i rovira",
                 "JOHN I SMITH", "JOSEP CAROD I ROVIRA III"):
        name = parse(text)
        assert "conjunction-or-initial" in [
            a.kind.value for a in name.ambiguities], text
    # ... and an unmarked-position letter of the same class reports
    # nothing at all, which is the third state
    assert [a.kind.value for a in parse("Josep Carod i Rovira").ambiguities] \
        == []


def test_the_withdrawal_reads_the_role_and_not_the_word() -> None:
    """The same withdrawal asked of a TITLE, the other role a fork
    between a connective and an initial cannot have resolved to.

    Nothing shipped builds this state -- a marked letter roled TITLE
    -- which is exactly why it is built here: an implementation
    keyed on the suffix role alone would pass every row above and
    fail this one (AGENTS.md: "Pin the decision, not the vocabulary").
    """
    import dataclasses
    from nameparser._pipeline._state import PendingAmbiguity
    from nameparser._types import AmbiguityKind as AK
    state = run(ParseState(original="Dr. Jane", lexicon=_LEX,
                           policy=Policy()))
    dr = next(i for i, t in enumerate(state.tokens) if t.text == "Dr.")
    assert state.tokens[dr].role is Role.TITLE
    poisoned = dataclasses.replace(
        state, ambiguities=state.ambiguities + (
            PendingAmbiguity(AK.CONJUNCTION_OR_INITIAL,
                             "read as an initial", (dr,)),))
    assert AK.CONJUNCTION_OR_INITIAL not in [
        a.kind for a in assemble(poisoned).ambiguities]

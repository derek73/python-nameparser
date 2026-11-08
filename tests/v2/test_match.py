"""Name matching: the settings object and the result types."""
from __future__ import annotations

import pickle

import pytest

from nameparser import Parser, Role
from nameparser._match import (
    DEFAULT_ACCEPT,
    Matching,
    MatchResult,
    Outcome,
    RoleMatch,
    Side,
)


def _result() -> MatchResult:
    return MatchResult(
        consistent=True,
        roles=tuple(
            RoleMatch(role, Outcome.INITIAL, "J.", "John", Side.RIGHT)
            for role in Role
        ),
    )


def test_accept_rejects_a_bare_string() -> None:
    with pytest.raises(TypeError, match="iterable of outcome names"):
        Matching(Parser(), accept="initial")  # type: ignore[arg-type]


def test_accept_rejects_a_mapping() -> None:
    with pytest.raises(TypeError, match="iterable of outcome names"):
        Matching(Parser(), accept={"initial": 1})  # type: ignore[arg-type]


def test_accept_rejects_a_non_iterable() -> None:
    with pytest.raises(TypeError, match="iterable of outcome names"):
        Matching(Parser(), accept=3)  # type: ignore[arg-type]


def test_accept_rejects_a_non_outcome_member() -> None:
    with pytest.raises(TypeError, match="iterable of outcome names"):
        Matching(Parser(), accept={3})  # type: ignore[arg-type]


def test_parser_must_be_a_parser() -> None:
    with pytest.raises(TypeError, match="Parser"):
        Matching("nope")  # type: ignore[arg-type]


def test_accept_rejects_an_unknown_outcome_naming_the_valid_ones() -> None:
    with pytest.raises(ValueError, match="'nickname-table'.*family-initial"):
        Matching(Parser(), accept={"nickname-table"})  # type: ignore[arg-type]


def test_conflict_cannot_be_accepted() -> None:
    for spelling in ("conflict", Outcome.CONFLICT):
        with pytest.raises(ValueError, match="conflict"):
            Matching(Parser(), accept={spelling})  # type: ignore[arg-type]


def test_accept_takes_strings_or_outcomes() -> None:
    expected = {Outcome.FAMILY_INITIAL, Outcome.SAME}
    assert Matching(Parser(), accept={"family-initial"}).accept == expected  # type: ignore[arg-type]
    assert Matching(Parser(), accept=[Outcome.FAMILY_INITIAL]).accept == expected  # type: ignore[arg-type]


def test_passing_accept_replaces_the_default() -> None:
    assert Matching(Parser(), accept=set()).accept == {Outcome.SAME}  # type: ignore[arg-type]


def test_the_default_accepts_what_the_spec_lists() -> None:
    assert DEFAULT_ACCEPT == {
        Outcome.SAME, Outcome.FOLDED, Outcome.LISTED_SPELLING,
        Outcome.PARTICLES_ASIDE, Outcome.PART_OF_OTHER, Outcome.INITIAL,
        Outcome.INITIALS_AGREE, Outcome.ONE_SIDE,
        Outcome.GENERATION_ONE_SIDE, Outcome.NOTED,
    }
    assert Matching(Parser()).accept == DEFAULT_ACCEPT


def test_outcomes_are_declared_strongest_first() -> None:
    names = [o.value for o in Outcome]
    assert names[0] == "same" and names[-1] == "conflict"
    assert len(names) == 16


def test_match_types_round_trip_through_pickle() -> None:
    matching = Matching(Parser(), accept={"initial"})  # type: ignore[arg-type]
    for obj in (matching, _result(), _result().roles[0]):
        assert pickle.loads(pickle.dumps(obj)) == obj


def test_mirrored_swaps_text_and_sides() -> None:
    mirrored = _result().mirrored()
    assert mirrored.consistent
    first = mirrored.roles[0]
    assert (first.left, first.right, first.more) == ("John", "J.", Side.LEFT)
    assert [m.role for m in mirrored.roles] == list(Role)
    assert mirrored.mirrored() == _result()


def test_mirrored_keeps_neither() -> None:
    both = RoleMatch(Role.GIVEN, Outcome.SAME, "a", "a", Side.NEITHER)
    assert both.__class__ is RoleMatch
    result = MatchResult(True, (both,))
    assert result.mirrored().roles[0].more is Side.NEITHER


def test_matching_repr_shows_only_the_deviation() -> None:
    assert repr(Matching(Parser())) == "Matching(default)"
    assert repr(Matching(
        Parser(), DEFAULT_ACCEPT | {Outcome.FAMILY_INITIAL},
    )) == "Matching(default + family-initial)"
    assert repr(Matching(
        Parser(), DEFAULT_ACCEPT - {Outcome.NOTED, Outcome.INITIAL},
    )) == "Matching(default - initial, noted)"
    assert repr(Matching(
        Parser(), (DEFAULT_ACCEPT - {Outcome.NOTED}) | {Outcome.ACROSS_ROLES},
    )) == "Matching(default + across-roles - noted)"

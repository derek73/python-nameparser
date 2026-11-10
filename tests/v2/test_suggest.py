"""The per-name signals of the group suggester (nameparser/_suggest.py)."""
from __future__ import annotations

import pytest

from nameparser import Lexicon
from nameparser._policy import PatronymicRule
from nameparser._suggest import Signal, name_votes
from nameparser._types import FAMILY_FIRST, GIVEN_FIRST

L = Lexicon.default()

_VOTES = [
    ("Mehmet DEMİR", Signal.CAPITALS, GIVEN_FIRST),
    ("DUPONT Jean", Signal.CAPITALS, FAMILY_FIRST),
    ("Armitage J.", Signal.TRAILING_INITIAL, FAMILY_FIRST),
    ("van Berg Jan", Signal.PARTICLE, FAMILY_FIRST),
    ("Jan van Berg", Signal.PARTICLE, GIVEN_FIRST),
    ("Kim Minjun", Signal.SURNAME, FAMILY_FIRST),
    ("Minjun Kim", Signal.SURNAME, GIVEN_FIRST),
    ("Priem Jason", Signal.GIVEN_NAME, FAMILY_FIRST),
    ("Jason Priem", Signal.GIVEN_NAME, GIVEN_FIRST),
    ("Иванов Иван Петрович", Signal.PATRONYMIC, PatronymicRule.EAST_SLAVIC),
    ("Ivan Petrovich Sidorov", Signal.PATRONYMIC, PatronymicRule.EAST_SLAVIC),
    ("Ziyo Azamat Hamid o‘g‘li", Signal.PATRONYMIC, PatronymicRule.TURKIC),
]


@pytest.mark.parametrize(("text", "signal", "value"), _VOTES)
def test_a_name_casts_its_vote(
    text: str, signal: Signal, value: object,
) -> None:
    assert name_votes(text, L)[signal] == value


@pytest.mark.parametrize(("text", "signal"), [
    ("Jeffrey LAM Kin-fung", Signal.CAPITALS),
    ("JOHN SMITH", Signal.CAPITALS),
    ("john smith", Signal.CAPITALS),
    ("S. Ramesh", Signal.TRAILING_INITIAL),
    ("Smith A.", Signal.SURNAME),
    ("A. Smith", Signal.SURNAME),
    ("김민준", Signal.CAPITALS),
    ("김민준", Signal.SURNAME),
    ("김민준", Signal.GIVEN_NAME),
    ("鄭和", Signal.CAPITALS),
    ("鄭和", Signal.SURNAME),
    ("鄭和", Signal.GIVEN_NAME),
])
def test_a_name_casts_no_such_vote(text: str, signal: Signal) -> None:
    assert signal not in name_votes(text, L)


def test_a_patronymic_casts_no_order_vote_of_its_own() -> None:
    votes = name_votes("Ivan Petrovich Sidorov", L)
    assert votes[Signal.PATRONYMIC] == PatronymicRule.EAST_SLAVIC
    assert set(votes) - {Signal.PATRONYMIC, Signal.GIVEN_NAME} == set()


def test_a_name_with_both_patronymic_shapes_reports_turkic() -> None:
    votes = name_votes("Ali Petrovich Hamid oglu", L)
    assert votes[Signal.PATRONYMIC] == PatronymicRule.TURKIC


@pytest.mark.parametrize("text", ["Priem, Jason", "", "   ", "Madonna"])
def test_a_name_with_nothing_to_read_casts_nothing(text: str) -> None:
    assert name_votes(text, L) == {}


@pytest.mark.parametrize("text", ["\u0000", "A.", "a b c d", "İ İ İ", "-", ". ."])
def test_no_signal_raises(text: str) -> None:
    assert isinstance(name_votes(text, L), dict)

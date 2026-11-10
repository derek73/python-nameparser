"""The per-name signals of the group suggester (nameparser/_suggest.py)."""
from __future__ import annotations

import unicodedata

import pytest

from collections.abc import Iterator

from nameparser import (
    FAMILY_FIRST_GIVEN_LAST, UNSET, Lexicon, NameEvidence, Parser, Policy,
    PolicyPatch, SettingEvidence, Suggestion,
)
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
    ("O'BRIEN Sean", Signal.CAPITALS, FAMILY_FIRST),
    ("GOMINA-MUSA Abɖu", Signal.CAPITALS, FAMILY_FIRST),
    ("Mary de Jean", Signal.PARTICLE, GIVEN_FIRST),
    (unicodedata.normalize("NFD", "Nguyễn Minh"), Signal.SURNAME, FAMILY_FIRST),
    (unicodedata.normalize("NFC", "Nguyễn Minh"), Signal.SURNAME, FAMILY_FIRST),
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
    ("Smith J.-P.", Signal.CAPITALS),
    ("Smith J-P", Signal.CAPITALS),
    ("Smith J.P.", Signal.CAPITALS),
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


# -- the group: Parser.suggest ------------------------------------------


def _order_evidence(s: Suggestion) -> SettingEvidence:
    return next(e for e in s.evidence if e.setting == "name_order")


def _patronymic_evidence(s: Suggestion) -> SettingEvidence:
    return next(e for e in s.evidence if e.setting == "patronymic_rules")


def test_an_empty_group_suggests_nothing() -> None:
    s = Parser().suggest([])
    assert s.patch == PolicyPatch()
    assert s.parser.policy == Parser().policy
    assert s.names == ()
    assert s.disagreeing() == ()


def test_a_group_without_evidence_keeps_the_base() -> None:
    s = Parser().suggest(["Xyzzy Plugh"])
    assert s.patch == PolicyPatch()
    assert not _order_evidence(s).decided
    assert _order_evidence(s).no_evidence == 1


def test_a_group_of_one_decides_by_its_votes() -> None:
    # provisional thresholds (_MIN_VOTES = 1): one vote is enough
    assert Parser().suggest(["Priem Jason"]).patch == PolicyPatch(
        name_order=FAMILY_FIRST)


def test_a_family_first_group_suggests_family_first() -> None:
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Wang Xiaoming"])
    assert s.patch.name_order == FAMILY_FIRST
    assert s.parser.policy.name_order == FAMILY_FIRST
    order = _order_evidence(s)
    assert order.decided
    assert (order.votes_for, order.votes_against, order.no_evidence) == (
        3, 0, 0)
    assert (Signal.SURNAME, FAMILY_FIRST, 2) in order.by_signal
    assert (Signal.GIVEN_NAME, FAMILY_FIRST, 1) in order.by_signal


def test_a_family_first_base_can_be_moved_back() -> None:
    base = Parser(policy=Policy(name_order=FAMILY_FIRST))
    s = base.suggest(["Jason Priem", "Minjun Kim"])
    assert s.patch.name_order == GIVEN_FIRST
    assert s.parser.policy.name_order == GIVEN_FIRST


def test_a_vi_base_keeps_its_family_first_spelling() -> None:
    # `Nguyen Van An` casts no vote: `an` is a pinyin surname too, so
    # both ends are listed
    base = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    s = base.suggest(["Nguyen Van Thanh", "Tran Thi Huong"])
    assert s.patch.name_order is UNSET
    assert _order_evidence(s).decided
    assert _order_evidence(s).value == FAMILY_FIRST_GIVEN_LAST
    assert s.parser.policy.name_order == FAMILY_FIRST_GIVEN_LAST


def test_a_decided_order_equal_to_the_base_leaves_the_patch_empty() -> None:
    s = Parser().suggest(["Jason Priem", "Minjun Kim"])
    assert s.patch == PolicyPatch()
    assert _order_evidence(s).decided


def test_a_tie_decides_nothing() -> None:
    s = Parser().suggest(["Priem Jason", "Jason Smith"])
    assert s.patch == PolicyPatch()
    assert not _order_evidence(s).decided
    assert s.disagreeing() == ()


def test_an_east_slavic_group_gets_the_rule_not_an_order() -> None:
    s = Parser().suggest(["Сидоров Иван Петрович", "Иванов Пётр Сергеевич"])
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.EAST_SLAVIC})
    assert s.patch.name_order is UNSET
    assert _patronymic_evidence(s).decided
    assert not _order_evidence(s).decided
    assert s.parser.parse("Ivan Petrovich Sidorov").family == "Sidorov"


def test_an_east_slavic_rule_suppresses_an_order_the_names_vote_for() -> None:
    # `Ivan` at the front votes given-first, but the decided rule
    # reorders each name itself, so the order is not decided
    s = Parser(policy=Policy(name_order=FAMILY_FIRST)).suggest(
        ["Ivan Petrovich Sidorov"])
    assert s.patch.name_order is UNSET
    order = _order_evidence(s)
    assert not order.decided
    assert order.votes_against == 1


def test_a_turkic_group_is_reported_but_not_yet_decided() -> None:
    s = Parser().suggest(["Mamedov Ali Huseyn oglu", "Aliyev Rauf Ilham oglu"])
    assert s.patch.patronymic_rules is UNSET
    patronymic = _patronymic_evidence(s)
    assert not patronymic.decided
    assert (Signal.PATRONYMIC, PatronymicRule.TURKIC, 2) in patronymic.by_signal
    assert patronymic.note


def test_a_base_holding_the_rule_already_leaves_the_patch_empty() -> None:
    base = Parser(policy=Policy(
        patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC})))
    s = base.suggest(["Сидоров Иван Петрович"])
    assert s.patch == PolicyPatch()
    assert _patronymic_evidence(s).decided


def test_comma_names_cast_no_vote() -> None:
    s = Parser().suggest(["Priem, Jason", "Smith, John"])
    assert s.patch == PolicyPatch()
    assert _order_evidence(s).no_evidence == 2


def test_disagreeing_lists_the_names_against_the_answer() -> None:
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Jason Smith"])
    assert [n.text for n in s.disagreeing()] == ["Jason Smith"]


def test_a_name_with_no_votes_never_disagrees() -> None:
    s = Parser().suggest(["Priem Jason", "Xyzzy Plugh", "Smith, Jason"])
    assert s.disagreeing() == ()


def test_names_keeps_every_input_in_order_including_blanks_and_duplicates(
        ) -> None:
    texts = ["Priem Jason", "", "Priem Jason", "   ", "Kim Minjun"]
    s = Parser().suggest(texts)
    assert [n.text for n in s.names] == texts
    assert s.names[1].votes == {}
    assert s.names[0].votes == {Signal.GIVEN_NAME: FAMILY_FIRST}
    assert _order_evidence(s).no_evidence == 2


def test_a_generator_is_consumed_once() -> None:
    pulled: list[str] = []

    def names() -> Iterator[str]:
        for text in ["Priem Jason", "Kim Minjun"]:
            pulled.append(text)
            yield text

    s = Parser().suggest(names())
    assert pulled == ["Priem Jason", "Kim Minjun"]
    assert [n.text for n in s.names] == pulled
    assert s.patch.name_order == FAMILY_FIRST


@pytest.mark.parametrize("bad, fragment", [
    ("Priem Jason", "bare string: 'Priem Jason'"),
    ({"Priem Jason": 1}, "mapping: {'Priem Jason': 1}"),
    (b"Priem Jason", "decode"),
    (5, "got 5"),
    ([1], "item 0 is 1"),
    (["Priem Jason", None], "item 1 is None"),
])
def test_a_wrong_shape_raises_type_error_with_the_fix(
        bad: object, fragment: str) -> None:
    with pytest.raises(TypeError) as info:
        Parser().suggest(bad)  # type: ignore[arg-type]
    message = str(info.value)
    assert fragment in message
    if not isinstance(bad, bytes):
        assert "parser.suggest([" in message


def test_the_offered_fix_runs() -> None:
    with pytest.raises(TypeError) as info:
        Parser().suggest("Priem Jason")  # type: ignore[arg-type]
    offered = str(info.value).rsplit(": ", 1)[1]
    assert offered.startswith("parser.suggest(")
    result = eval(offered, {"parser": Parser()})
    assert isinstance(result, Suggestion)


def test_suggest_never_mutates_the_base() -> None:
    base = Parser(policy=Policy(name_order=FAMILY_FIRST))
    before = (base.policy, base.lexicon)
    s = base.suggest(["Jason Priem", "Minjun Kim", "Сидоров Иван Петрович"])
    assert (base.policy, base.lexicon) == before
    assert s.base is base
    assert s.parser.lexicon is base.lexicon


def test_the_parser_keeps_the_base_segmenter() -> None:
    base = Parser(segmenter=_decline)
    s = base.suggest(["Priem Jason"])
    assert s.parser.segmenter is _decline
    assert s.parser.policy.name_order == FAMILY_FIRST


def test_name_evidence_votes_are_read_only() -> None:
    evidence = NameEvidence("Priem Jason", {Signal.GIVEN_NAME: FAMILY_FIRST})
    with pytest.raises(TypeError):
        evidence.votes[Signal.SURNAME] = FAMILY_FIRST  # type: ignore[index]
    assert evidence == NameEvidence(
        "Priem Jason", {Signal.GIVEN_NAME: FAMILY_FIRST})


def test_the_report_names_the_setting_and_the_disagreeing_names() -> None:
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Jason Smith"])
    report = str(s)
    assert "Suggested for 3 names" in report
    assert "name_order" in report and "FAMILY_FIRST" in report
    assert "Jason Smith" in report


def test_the_new_types_are_exported() -> None:
    import nameparser
    for name in ("Suggestion", "NameEvidence", "SettingEvidence", "Signal"):
        assert name in nameparser.__all__
        assert getattr(nameparser, name) is not None


def _decline(token: str) -> None:
    return None

"""The per-name signals of the group suggester (nameparser/_suggest.py)."""
from __future__ import annotations

import unicodedata
import warnings

import pytest

from collections.abc import Iterator

from nameparser import (
    FAMILY_FIRST_GIVEN_LAST, UNSET, Lexicon, NameEvidence, Parser, Policy,
    PolicyPatch, SettingEvidence, Suggestion,
)
from nameparser._policy import PatronymicRule
from nameparser._suggest import Signal, name_votes
from nameparser._types import FAMILY_FIRST, GIVEN_FIRST, Role

L = Lexicon.default()

_VOTES = [
    ("Mehmet DEMİR", Signal.CAPITALS, GIVEN_FIRST),
    ("DUPONT Jean", Signal.CAPITALS, FAMILY_FIRST),
    ("Armitage J.", Signal.TRAILING_INITIAL, FAMILY_FIRST),
    ("Smith J.P.", Signal.TRAILING_INITIAL, FAMILY_FIRST),
    ("Smith J.-P.", Signal.TRAILING_INITIAL, FAMILY_FIRST),
    ("Smith J-P", Signal.TRAILING_INITIAL, FAMILY_FIRST),
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
    ("J.-P. Smith", Signal.TRAILING_INITIAL),
    ("Smith Jean-Pierre", Signal.TRAILING_INITIAL),
    ("Smith J-", Signal.TRAILING_INITIAL),
    ("Smith -", Signal.TRAILING_INITIAL),
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


# a final all-capitals word of two or three letters in a mixed-case name
# is joined initials (`Armitage JO`) or a short surname (`Jason NG`):
# it casts no capitals vote and is not looked up as a surname; a
# leading one still votes
@pytest.mark.parametrize("text", [
    "Armitage JO", "Smith JP", "Jones AB", "Jason NG", "Lee SH",
    "DUPONT Jean AB"])
def test_a_final_short_capitals_word_casts_no_capitals_vote(text: str) -> None:
    assert Signal.CAPITALS not in name_votes(text, L)


@pytest.mark.parametrize("text", ["Armitage JO", "Smith JP", "Jason NG"])
def test_a_final_short_capitals_word_is_not_looked_up_as_a_surname(
        text: str) -> None:
    assert Signal.SURNAME not in name_votes(text, L)


@pytest.mark.parametrize(("text", "signal"), [
    ("NG Jason", Signal.CAPITALS), ("KIM Jason", Signal.CAPITALS),
    ("NG Jason", Signal.SURNAME), ("Lee SH", Signal.SURNAME),
    ("Mehmet DEMİR", Signal.CAPITALS)])
def test_a_leading_or_longer_capitals_word_still_votes(
        text: str, signal: Signal) -> None:
    votes = name_votes(text, L)
    expected = GIVEN_FIRST if text == "Mehmet DEMİR" else FAMILY_FIRST
    assert votes[signal] == expected


def test_joined_initials_keep_a_family_first_base() -> None:
    base = Parser(policy=Policy(name_order=FAMILY_FIRST))
    s = base.suggest(["Armitage JO", "Smith JP", "Jones AB", "Brown KL",
                      "Garcia M", "Lee SH"])
    assert s.patch.name_order is UNSET
    assert s.parser.policy.name_order == FAMILY_FIRST


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


_EAST_SLAVIC = ["Сидоров Иван Петрович", "Иванов Пётр Сергеевич",
                "Петров Олег Иванович", "Смирнов Павел Андреевич",
                "Попов Илья Ильич"]
_TURKIC = ["Mamedov Ali Huseyn oglu", "Aliyev Rauf Ilham oglu",
           "Quliyev Elman Rasim oglu", "Hasanova Afet Abil qizi",
           "Mikayilova Sevil Alirza qizi"]


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


def test_one_name_voting_decides_nothing() -> None:
    # _MIN_VOTES = 2: one name is thin evidence, so the base stands
    s = Parser().suggest(["Priem Jason", "Xyzzy Plugh"])
    assert s.patch == PolicyPatch()
    assert not _order_evidence(s).decided
    assert _order_evidence(s).votes_against == 1


def test_two_names_voting_one_way_decide() -> None:
    assert Parser().suggest(["Priem Jason", "Kim Minjun"]).patch == (
        PolicyPatch(name_order=FAMILY_FIRST))


def test_an_order_needs_more_than_two_thirds_of_the_voting_names() -> None:
    # two for, one against: two thirds, not more
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Jason Smith"])
    assert not _order_evidence(s).decided
    # three for, one against: more than two thirds
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Wang Xiaoming",
                          "Jason Smith"])
    assert s.patch == PolicyPatch(name_order=FAMILY_FIRST)


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


def test_an_east_slavic_group_gets_the_rule_and_a_given_first_order(
        ) -> None:
    s = Parser().suggest(_EAST_SLAVIC)
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.EAST_SLAVIC})
    # the base is given-first already, so the patch leaves the order out
    assert s.patch.name_order is UNSET
    assert _patronymic_evidence(s).decided
    order = _order_evidence(s)
    assert order.decided
    assert order.value == GIVEN_FIRST
    assert "East Slavic" in order.note
    assert s.parser.parse("Ivan Petrovich Sidorov").family == "Sidorov"


@pytest.mark.parametrize("base_order", [FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST])
def test_an_east_slavic_group_moves_a_family_first_base_to_given_first(
        base_order: tuple[Role, Role, Role]) -> None:
    # the rule stands down under a family-first order, so it brings a
    # given-first one with it, whatever the names' order votes say
    s = Parser(policy=Policy(name_order=base_order)).suggest(
        ["Сидоров Иван Петрович", "Иванов Пётр Сергеевич",
         "Петров Олег Иванович", "Смирнов Павел Андреевич",
         "Попов Илья Ильич", "Kim Minjun"])
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.EAST_SLAVIC})
    assert s.patch.name_order == GIVEN_FIRST
    order = _order_evidence(s)
    assert order.decided
    assert (order.votes_for, order.votes_against) == (0, 1)
    assert s.parser.parse("Ivan Petrovich Sidorov").family == "Sidorov"
    assert s.parser.parse("Sidorov Ivan Petrovich").family == "Sidorov"


@pytest.mark.parametrize("names, rule", [
    (_EAST_SLAVIC, PatronymicRule.EAST_SLAVIC),
    (_TURKIC, PatronymicRule.TURKIC)])
def test_a_patronymic_rule_needs_five_names_carrying_it(
        names: list[str], rule: PatronymicRule) -> None:
    # _MIN_PATRONYMIC_VOTES = 5: two to four Russian names written
    # family-first moved a family-first base to given-first in 8-20% of
    # groups, so a rule needs five names however large their share
    base = Parser(policy=Policy(name_order=FAMILY_FIRST))
    for size in (2, 3, 4):
        s = base.suggest(names[:size])
        assert s.patch.patronymic_rules is UNSET, size
        assert not _patronymic_evidence(s).decided, size
        assert s.patch.name_order is UNSET, size
    s = base.suggest(names)
    assert s.patch.patronymic_rules == frozenset({rule})


def test_one_patronymic_among_given_first_names_decides_nothing() -> None:
    s = Parser().suggest(["Jason Priem", "Mary Smith", "Anna Jones",
                          "Jason Smith", "Mary Priem",
                          "Сидоров Иван Петрович"])
    assert s.patch.patronymic_rules is UNSET
    assert not _patronymic_evidence(s).decided
    assert _order_evidence(s).decided
    assert _order_evidence(s).value == GIVEN_FIRST


def test_patronymics_need_more_than_four_in_five_of_the_voting_names(
        ) -> None:
    # _MIN_PATRONYMIC_SHARE = 0.8: the rule forces a given-first order,
    # so a family-first group whose names half carry a patronymic
    # (PatentsView's Russian inventors) must not be reordered.
    # Four of five voting names: four in five, not more
    s = Parser().suggest(["Jason Priem", *_EAST_SLAVIC[:4]])
    assert s.patch.patronymic_rules is UNSET
    assert not _patronymic_evidence(s).decided
    # five of six: more than four in five
    s = Parser().suggest(["Jason Priem", *_EAST_SLAVIC])
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.EAST_SLAVIC})


def test_a_turkic_rule_needs_more_than_four_in_five_of_the_voting_names(
        ) -> None:
    # the same share as the East Slavic rule's: four of five voting
    # names is four in five, not more
    s = Parser().suggest(["Jason Priem", *_TURKIC[:4]])
    assert s.patch.patronymic_rules is UNSET
    assert not _patronymic_evidence(s).decided
    # five of six: more than four in five
    s = Parser().suggest(["Jason Priem", *_TURKIC])
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.TURKIC})


def test_a_turkic_group_gets_the_rule_alone() -> None:
    s = Parser().suggest(_TURKIC)
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.TURKIC})
    # the rule reads either order, so it forces no order of its own
    assert s.patch.name_order is UNSET
    patronymic = _patronymic_evidence(s)
    assert patronymic.decided
    assert (Signal.PATRONYMIC, PatronymicRule.TURKIC, 5) in patronymic.by_signal


@pytest.mark.parametrize("text", [
    "Mamedov Ali Huseyn oglu", "Ali Huseyn oglu Mamedov"])
def test_a_turkic_group_reads_the_family_whichever_end_it_is_at(
        text: str) -> None:
    s = Parser().suggest([text, "Aliyev Rauf Ilham oglu",
                          "Rauf Ilham oglu Aliyev", *_TURKIC[2:]])
    name = s.parser.parse(text)
    assert name.family == "Mamedov"
    assert name.given == "Ali"
    assert name.patronymic == "Huseyn oglu"


def test_a_turkic_group_keeps_the_order_its_own_votes_decide() -> None:
    names = ["NƏBİYEV Rizvan Novruz oğlu", "HƏSƏNOVA Afət Əbil qızı",
             "AĞAZADƏ Əminə Həmid qızı", "MİKAYILOVA Sevil Əlirazı qızı",
             "QULİYEV Elman Rasim oğlu", "BÜLBÜLOĞLU Polad"]
    s = Parser().suggest(names)
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.TURKIC})
    assert s.patch.name_order == FAMILY_FIRST
    assert s.parser.parse("BÜLBÜLOĞLU Polad").family == "BÜLBÜLOĞLU"


def test_a_turkic_group_on_a_family_first_base_follows_its_names() -> None:
    base = Parser(policy=Policy(name_order=FAMILY_FIRST))
    s = base.suggest(["Ali Huseyn oglu Mamedov", "Leyla Rasim qizi Aliyeva",
                      "Tural Ilham oglu Aliyev", "Aysel Rauf qizi Quliyeva",
                      "Elman Rasim oglu Quliyev"])
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.TURKIC})
    # the rule forces no order, and the names' own votes decide it
    assert s.patch.name_order == GIVEN_FIRST
    assert s.parser.parse("Ali Huseyn oglu Mamedov").family == "Mamedov"


def test_a_base_holding_the_turkic_rule_leaves_the_patch_empty() -> None:
    base = Parser(policy=Policy(
        patronymic_rules=frozenset({PatronymicRule.TURKIC})))
    s = base.suggest(_TURKIC)
    assert s.patch.patronymic_rules is UNSET
    assert _patronymic_evidence(s).decided


def test_a_base_holding_the_rule_already_leaves_the_patch_empty() -> None:
    base = Parser(policy=Policy(
        patronymic_rules=frozenset({PatronymicRule.EAST_SLAVIC})))
    s = base.suggest(_EAST_SLAVIC)
    assert s.patch == PolicyPatch()
    assert _patronymic_evidence(s).decided


def test_comma_names_cast_no_vote() -> None:
    s = Parser().suggest(["Priem, Jason", "Smith, John"])
    assert s.patch == PolicyPatch()
    assert _order_evidence(s).no_evidence == 2


def test_disagreeing_lists_the_names_against_the_answer() -> None:
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Wang Xiaoming",
                          "Jason Smith"])
    assert [n.text for n in s.disagreeing()] == ["Jason Smith"]


def test_a_name_with_no_votes_never_disagrees() -> None:
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Wang Xiaoming",
                          "Jason Smith", "Xyzzy Plugh", "Smith, Jason"])
    assert s.patch == PolicyPatch(name_order=FAMILY_FIRST)
    assert [n.text for n in s.disagreeing()] == ["Jason Smith"]


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
    ({"Priem Jason": 1}, "not a mapping (dict)"),
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


def test_a_mapping_error_does_not_embed_the_mapping() -> None:
    names = {f"Name{i} Surname{i}": i for i in range(10_000)}
    with pytest.raises(TypeError) as info:
        Parser().suggest(names)  # type: ignore[arg-type]
    assert "Name9999" not in str(info.value)
    assert len(str(info.value)) < 300


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
    s = base.suggest(["Priem Jason", "Kim Minjun"])
    assert s.parser.segmenter is _decline
    assert s.parser.policy.name_order == FAMILY_FIRST


def test_the_parser_does_not_warn_again_for_its_base() -> None:
    # a JA base without a segmenter warns its caller once, when it is
    # built; the suggested parser is built from it and must not warn
    # again, on every access
    from nameparser import locales, parser_for
    with pytest.warns(UserWarning):
        base = parser_for(locales.JA)
    s = base.suggest(["Priem Jason", "Kim Minjun"])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        parser = s.parser
        assert s.parser.policy.name_order == FAMILY_FIRST
    assert parser.lexicon is base.lexicon


def test_a_patch_that_moves_segment_scripts_still_warns_its_caller() -> None:
    # suggest() never patches segment_scripts, but a hand-built
    # Suggestion may, and a warning that patch itself causes (Han
    # segmentation with no Chinese surnames listed) is new to the
    # caller, so .parser must pass it on, attributed to the caller
    from nameparser import PolicyPatch, Script, Suggestion
    s = Suggestion(Parser(), PolicyPatch(
        segment_scripts=frozenset({Script.HAN})), (), ())
    with pytest.warns(UserWarning) as caught:
        s.parser
    assert caught[0].filename == __file__


def test_name_evidence_votes_are_read_only() -> None:
    evidence = NameEvidence("Priem Jason", {Signal.GIVEN_NAME: FAMILY_FIRST})
    with pytest.raises(TypeError):
        evidence.votes[Signal.SURNAME] = FAMILY_FIRST  # type: ignore[index]
    assert evidence == NameEvidence(
        "Priem Jason", {Signal.GIVEN_NAME: FAMILY_FIRST})


def test_the_report_names_the_setting_and_the_disagreeing_names() -> None:
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Wang Xiaoming",
                          "Jason Smith"])
    report = str(s)
    assert "Suggested for 4 names" in report
    assert "name_order" in report and "FAMILY_FIRST" in report
    assert "Jason Smith" in report


def test_the_new_types_are_exported() -> None:
    import nameparser
    for name in ("Suggestion", "NameEvidence", "SettingEvidence", "Signal"):
        assert name in nameparser.__all__
        assert getattr(nameparser, name) is not None


# -- one order vote per name (fix round 1) --------------------------------


def test_one_heavily_marked_name_does_not_outvote_two() -> None:
    # `KIM Jason J.` carries three family-first signals, but is one name
    s = Parser().suggest(["Jason Smith", "Mary Jones", "Anna Brown",
                          "KIM Jason J."])
    assert s.patch.name_order is UNSET
    order = _order_evidence(s)
    assert order.decided
    assert (order.votes_for, order.votes_against) == (3, 1)
    assert (Signal.CAPITALS, FAMILY_FIRST, 1) in order.by_signal
    assert (Signal.TRAILING_INITIAL, FAMILY_FIRST, 1) in order.by_signal


def test_two_signal_names_count_once_each() -> None:
    # per name 2 of 3 for family-first, which is not more than two
    # thirds; counted per signal it would be 4 of 5, and decide
    s = Parser().suggest(["Jason Smith", "van Berg Mary", "van Berg Anna"])
    assert s.patch == PolicyPatch()
    order = _order_evidence(s)
    assert not order.decided
    assert (order.votes_for, order.votes_against) == (1, 2)
    assert s.disagreeing() == ()


def test_a_name_whose_signals_conflict_is_contested() -> None:
    # `Jason Kim J.`: the trailing initial says family-first, the given
    # name at the front says given-first
    s = Parser().suggest(["Priem Jason", "Kim Minjun", "Jason Kim J."])
    assert s.patch.name_order == FAMILY_FIRST
    order = _order_evidence(s)
    assert (order.votes_for, order.votes_against, order.contested,
            order.no_evidence) == (2, 0, 1, 0)
    assert s.disagreeing() == ()
    # the signal breakdown still holds both of its votes
    assert (Signal.GIVEN_NAME, GIVEN_FIRST, 1) in order.by_signal
    assert (Signal.TRAILING_INITIAL, FAMILY_FIRST, 1) in order.by_signal


@pytest.mark.parametrize("names", [
    [],
    ["Xyzzy Plugh"],
    ["Priem Jason", "Jason Kim J.", "Smith, John", "", "Jason Smith"],
    ["Jason Smith", "Mary Jones", "KIM Jason J."],
    ["Сидоров Иван Петрович", "SIDOROV Ivan Petrovich", "Kim Minjun"],
    ["Mamedov Ali Huseyn oglu", "Jason Kim J.", "Priem Jason"],
])
def test_the_counts_add_up_to_the_group(names: list[str]) -> None:
    s = Parser().suggest(names)
    for e in s.evidence:
        assert (e.votes_for + e.votes_against + e.contested
                + e.no_evidence) == len(names), e


def test_an_east_slavic_name_never_disagrees_on_order() -> None:
    # `SIDOROV Ivan Petrovich` votes family-first by its capitals, but
    # the decided East Slavic rule reorders it
    s = Parser().suggest([*_EAST_SLAVIC, "SIDOROV Ivan Petrovich"])
    assert s.patch.patronymic_rules == frozenset({PatronymicRule.EAST_SLAVIC})
    assert _order_evidence(s).votes_against == 1
    assert s.disagreeing() == ()


def test_a_non_east_slavic_name_still_disagrees_in_an_east_slavic_group(
        ) -> None:
    s = Parser().suggest([*_EAST_SLAVIC, "Kim Minjun"])
    assert [n.text for n in s.disagreeing()] == ["Kim Minjun"]


# -- eager validation of the result types -----------------------------------


@pytest.mark.parametrize("votes, error, fragment", [
    ({Signal.SURNAME: "family-first"}, TypeError, "must be an order"),
    ({Signal.SURNAME: FAMILY_FIRST_GIVEN_LAST}, ValueError, "GIVEN_FIRST or FAMILY_FIRST"),
    ({Signal.SURNAME: PatronymicRule.TURKIC}, TypeError, "must be an order"),
    ({Signal.PATRONYMIC: FAMILY_FIRST}, TypeError, "PatronymicRule"),
    ({Signal.PATRONYMIC: "turkic"}, TypeError, "PatronymicRule"),
    ({"no-such-signal": FAMILY_FIRST}, ValueError, "no-such-signal"),
])
def test_name_evidence_refuses_a_vote_of_the_wrong_kind(
        votes: dict[object, object], error: type[Exception],
        fragment: str) -> None:
    with pytest.raises(error, match=fragment):
        NameEvidence("Priem Jason", votes)  # type: ignore[arg-type]


def test_name_evidence_accepts_an_order_written_as_a_list() -> None:
    evidence = NameEvidence("Priem Jason", {Signal.SURNAME: list(FAMILY_FIRST)})  # type: ignore[dict-item]
    assert evidence.votes[Signal.SURNAME] == FAMILY_FIRST


def _setting_evidence(**changes: object) -> SettingEvidence:
    fields: dict[str, object] = dict(
        setting="name_order", value=FAMILY_FIRST, decided=True, votes_for=1,
        votes_against=0, contested=0, no_evidence=0, by_signal=())
    fields.update(changes)
    return SettingEvidence(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize("changes, error, fragment", [
    ({"decided": 1}, TypeError, "decided must be a bool, got 1"),
    ({"decided": "yes"}, TypeError, "decided must be a bool"),
    ({"votes_for": -1}, ValueError, "votes_for must not be negative, got -1"),
    ({"votes_against": -2}, ValueError, "votes_against must not be negative"),
    ({"contested": -1}, ValueError, "contested must not be negative"),
    ({"no_evidence": -1}, ValueError, "no_evidence must not be negative"),
    ({"votes_for": 1.5}, TypeError, "votes_for must be an int"),
    ({"no_evidence": True}, TypeError, "no_evidence must be an int"),
    ({"setting": 5}, TypeError, "setting must be a Policy field name"),
    ({"note": None}, TypeError, "note must be a str"),
])
def test_setting_evidence_refuses_bad_counts_and_flags(
        changes: dict[str, object], error: type[Exception],
        fragment: str) -> None:
    with pytest.raises(error, match=fragment):
        _setting_evidence(**changes)


def test_setting_evidence_accepts_a_well_formed_value() -> None:
    assert _setting_evidence().votes_for == 1


@pytest.mark.parametrize("changes, error, fragment", [
    ({"setting": "no_such_field"}, ValueError,
     "setting must name a Policy field, got 'no_such_field'"),
    ({"setting": ""}, ValueError, "must name a Policy field"),
    ({"by_signal": "capitals"}, TypeError, "by_signal must be an iterable"),
    ({"by_signal": 5}, TypeError, "by_signal must be an iterable"),
    ({"by_signal": [(Signal.SURNAME, FAMILY_FIRST)]}, TypeError,
     r"\(signal, vote, count\)"),
    ({"by_signal": ["abc"]}, TypeError, r"\(signal, vote, count\)"),
    ({"by_signal": [("no-such", FAMILY_FIRST, 1)]}, ValueError, "no-such"),
    ({"by_signal": [(Signal.SURNAME, "family-first", 1)]}, TypeError,
     "must be an order"),
    ({"by_signal": [(Signal.PATRONYMIC, FAMILY_FIRST, 1)]}, TypeError,
     "PatronymicRule"),
    ({"by_signal": [(Signal.SURNAME, FAMILY_FIRST, -1)]}, ValueError,
     "count must not be negative, got -1"),
    ({"by_signal": [(Signal.SURNAME, FAMILY_FIRST, True)]}, TypeError,
     "count must be an int"),
])
def test_setting_evidence_refuses_a_bad_setting_or_row(
        changes: dict[str, object], error: type[Exception],
        fragment: str) -> None:
    with pytest.raises(error, match=fragment):
        _setting_evidence(**changes)


def test_setting_evidence_keeps_well_formed_rows() -> None:
    evidence = _setting_evidence(
        by_signal=[["surname", list(FAMILY_FIRST), 2]])
    assert evidence.by_signal == ((Signal.SURNAME, FAMILY_FIRST, 2),)


def test_a_valid_setting_evidence_renders_in_a_report() -> None:
    s = Suggestion(Parser(), PolicyPatch(), (_setting_evidence(
        setting="patronymic_rules", value=frozenset(), decided=False),), ())
    assert "patronymic_rules" in str(s)


@pytest.mark.parametrize("changes, error, fragment", [
    ({"base": Policy()}, TypeError, "base must be a Parser"),
    ({"base": None}, TypeError, "base must be a Parser"),
    ({"patch": {}}, TypeError, "patch must be a PolicyPatch"),
    ({"evidence": "name_order"}, TypeError,
     "evidence must be a tuple of SettingEvidence"),
    ({"evidence": [object()]}, TypeError, "evidence must hold SettingEvidence"),
    ({"names": "Priem Jason"}, TypeError,
     "names must be a tuple of NameEvidence"),
    ({"names": None}, TypeError, "names must be a tuple of NameEvidence"),
    ({"names": ["Priem Jason"]}, TypeError, "names must hold NameEvidence"),
])
def test_suggestion_refuses_fields_of_the_wrong_type(
        changes: dict[str, object], error: type[Exception],
        fragment: str) -> None:
    fields: dict[str, object] = dict(
        base=Parser(), patch=PolicyPatch(), evidence=(), names=())
    fields.update(changes)
    with pytest.raises(error, match=fragment):
        Suggestion(**fields)  # type: ignore[arg-type]


def _decline(token: str) -> None:
    return None


# -- the review's fix wave: where a signal reads (A1-A4, A8) ----------------

_OVICH_SURNAMES = ["Abramovich Roman", "Rabinovich Pavel",
                   "Shostakovich Dmitri", "Lukashevich Anton",
                   "Karpovich Igor", "Yurkevich Oleg"]


@pytest.mark.parametrize("text", [
    *_OVICH_SURNAMES, "Roman Abramovich",
    # rules/O1 reads three name words, the ending never on the first
    "Petrovich Ivan Sidorov", "Ivan Sidorov Petrovich Ivanovich",
    # rules/O2 reads four name words, the marker never first or second
    "Ali Huseyn oglu", "oglu Ali Huseyn Mamedov", "Ali oglu Huseyn Mamedov",
])
def test_a_patronymic_ending_the_pipeline_cannot_read_casts_no_vote(
        text: str) -> None:
    assert Signal.PATRONYMIC not in name_votes(text, L)


@pytest.mark.parametrize("text, rule", [
    ("Sidorov Ivan Petrovich", PatronymicRule.EAST_SLAVIC),
    ("Ivan Petrovich Sidorov", PatronymicRule.EAST_SLAVIC),
    ("Иванов Иван Петрович", PatronymicRule.EAST_SLAVIC),
    ("Dr. Ivan Petrovich Sidorov", PatronymicRule.EAST_SLAVIC),
    ("Sidorov Ivan Petrovich Jr.", PatronymicRule.EAST_SLAVIC),
    ("Mamedov Ali Huseyn oglu", PatronymicRule.TURKIC),
    ("Ali Huseyn oglu Mamedov", PatronymicRule.TURKIC),
])
def test_a_patronymic_the_pipeline_reads_still_votes(
        text: str, rule: PatronymicRule) -> None:
    assert name_votes(text, L)[Signal.PATRONYMIC] is rule


def test_ovich_surnames_keep_a_family_first_base() -> None:
    base = Parser(policy=Policy(name_order=FAMILY_FIRST))
    s = base.suggest(_OVICH_SURNAMES)
    assert s.patch.patronymic_rules is UNSET
    assert s.parser.policy.name_order == FAMILY_FIRST
    assert s.parser.parse("Abramovich Roman").family == "Abramovich"


_CAPITALS_EAST_SLAVIC = [
    "SIDOROV Ivan Petrovich", "IVANOV Petr Sergeevich",
    "PETROV Oleg Ivanovich", "SMIRNOV Pavel Andreevich", "POPOV Ilya Ilyich"]


@pytest.mark.parametrize("base_order", [GIVEN_FIRST, FAMILY_FIRST])
def test_a_decided_rule_never_overrides_an_order_decided_against_it(
        base_order: tuple[Role, Role, Role]) -> None:
    # five East Slavic names whose capitals all write the family first:
    # the rule is decided, and so is the family-first order, which the
    # rule's given-first order does not override
    s = Parser(policy=Policy(name_order=base_order)).suggest(
        _CAPITALS_EAST_SLAVIC)
    assert _patronymic_evidence(s).decided
    assert s.parser.policy.patronymic_rules == frozenset(
        {PatronymicRule.EAST_SLAVIC})
    order = _order_evidence(s)
    assert order.decided and order.value == FAMILY_FIRST
    assert (order.votes_for, order.votes_against) == (5, 0)
    assert "East Slavic" in order.note and "stands down" in order.note
    assert s.parser.policy.name_order == FAMILY_FIRST
    assert s.parser.parse("SIDOROV Ivan Petrovich").family == "SIDOROV"
    assert s.disagreeing() == ()


@pytest.mark.parametrize("text, signal, value", [
    ("Dr. Zhang Xiaoming", Signal.SURNAME, FAMILY_FIRST),
    ("Prof. Pham Minh Duc", Signal.SURNAME, FAMILY_FIRST),
    ("Mr Kim Minjun", Signal.SURNAME, FAMILY_FIRST),
    ("Zhang Xiaoming PhD", Signal.SURNAME, FAMILY_FIRST),
    ("Kim Minjun Jr.", Signal.SURNAME, FAMILY_FIRST),
    ("Kim Minjun III", Signal.SURNAME, FAMILY_FIRST),
])
def test_titles_and_post_nominals_are_read_past(
        text: str, signal: Signal, value: object) -> None:
    assert name_votes(text, L)[signal] == value


@pytest.mark.parametrize("text, signal", [
    ("Tanaka Hiroshi FACS", Signal.CAPITALS),
    ("Tanaka Hiroshi MBBS", Signal.CAPITALS),
    ("John Smith V", Signal.TRAILING_INITIAL),
    ("John Smith II", Signal.TRAILING_INITIAL),
])
def test_a_post_nominal_casts_no_vote(text: str, signal: Signal) -> None:
    assert signal not in name_votes(text, L)


@pytest.mark.parametrize("text", ["Armitage V", "Smith J. V"])
def test_a_one_letter_numeral_without_words_to_spare_is_an_initial(
        text: str) -> None:
    # the trailing fork reads a one-letter numeral as the generation
    # only bare, with a word to spare and no initial in front
    assert name_votes(text, L)[Signal.TRAILING_INITIAL] == FAMILY_FIRST


def test_titled_chinese_names_keep_a_family_first_base() -> None:
    base = Parser(policy=Policy(name_order=FAMILY_FIRST))
    s = base.suggest(["Dr. Zhang Wei", "Dr. Wang Fang", "Prof. Li Jing",
                      "Dr. Liu Lei", "Prof. Chen Yang", "Dr. Huang Hong"])
    assert s.patch.name_order is UNSET
    assert s.parser.policy.name_order == FAMILY_FIRST


@pytest.mark.parametrize("text, signal, value", [
    ("Zhang Xiaoming, PhD", Signal.SURNAME, FAMILY_FIRST),
    ("Kim Minjun, Jr., MD", Signal.SURNAME, FAMILY_FIRST),
    ("Sidorov Ivan Petrovich, PhD", Signal.PATRONYMIC,
     PatronymicRule.EAST_SLAVIC),
])
def test_a_comma_before_post_nominals_alone_reads_the_name_before_it(
        text: str, signal: Signal, value: object) -> None:
    assert name_votes(text, L)[signal] == value


@pytest.mark.parametrize("text", ["Priem, Jason", "Kim, Minjun Jr.",
                                  "Zhang Xiaoming, Beijing"])
def test_any_other_comma_name_casts_nothing(text: str) -> None:
    assert name_votes(text, L) == {}


def test_the_order_note_counts_the_comma_names_left_out() -> None:
    s = Parser().suggest(["Priem, Jason", "Smith, John", "Kim Minjun",
                          "Zhang Xiaoming, PhD", "Wang Xiaoming"])
    order = _order_evidence(s)
    assert "2 names with a comma" in order.note
    # Kim Minjun, Wang Xiaoming and the name before `, PhD`
    assert order.votes_for == 3
    s = Parser().suggest(["Kim Minjun", "Wang Xiaoming"])
    assert "comma" not in _order_evidence(s).note


@pytest.mark.parametrize("text, signal, value", [
    ("Petrov Ivan Ivanovich.", Signal.PATRONYMIC, PatronymicRule.EAST_SLAVIC),
    ('"Kim" Minjun', Signal.SURNAME, FAMILY_FIRST),
    ("(Kim) Minjun", Signal.SURNAME, FAMILY_FIRST),
    ("Minjun 'Kim'", Signal.SURNAME, GIVEN_FIRST),
    ("Mamedov Ali Huseyn (oglu)", Signal.PATRONYMIC, PatronymicRule.TURKIC),
])
def test_edge_punctuation_is_read_past(
        text: str, signal: Signal, value: object) -> None:
    assert name_votes(text, L)[signal] == value

import pickle

import pytest

from nameparser import Lexicon, Locale, Parser, Policy, PolicyPatch, parse, parser_for
from nameparser._policy import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, PatronymicRule,
)
from nameparser._types import AmbiguityKind


def test_parser_defaults_and_properties() -> None:
    p = Parser()
    assert p.lexicon == Lexicon.default()
    assert p.policy == Policy()


def test_parser_rejects_wrong_types_eagerly() -> None:
    with pytest.raises(TypeError, match="lexicon"):
        Parser(lexicon={"titles": set()})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="policy"):
        Parser(policy="strict")  # type: ignore[arg-type]


def test_parse_end_to_end_with_default_vocabulary() -> None:
    pn = parse("Dr. Juan de la Vega III")
    assert pn.title == "Dr."
    assert pn.given == "Juan"
    assert pn.family == "de la Vega"
    assert pn.suffix == "III"
    assert str(pn) == "Dr. Juan de la Vega III"


def test_parse_rejects_non_str_with_decode_hint() -> None:
    with pytest.raises(TypeError, match="decode"):
        parse(b"John Smith")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="str"):
        parse(None)  # type: ignore[arg-type]


def test_degenerate_inputs_are_total() -> None:
    # spec §5a table
    assert not parse("")
    assert not parse("   ")
    assert parse("").original == ""
    single = parse("John")
    assert single.given == "John"
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    assert family_first.parse("Yamada").family == "Yamada"
    title_only = parse("Dr.")
    assert title_only.title == "Dr." and not title_only.given
    unbalanced = parse('Jon "Nick Smith')
    kinds = {a.kind for a in unbalanced.ambiguities}
    assert AmbiguityKind.UNBALANCED_DELIMITER in kinds
    assert '"Nick' in [t.text for t in unbalanced.tokens]  # literal


def test_parser_is_picklable_and_frozen() -> None:
    p = Parser(policy=Policy(name_order=FAMILY_FIRST))
    loaded = pickle.loads(pickle.dumps(p))
    assert loaded == p
    assert loaded.parse("Yamada Taro").family == "Yamada"
    with pytest.raises(AttributeError):
        p.policy = Policy()  # type: ignore[misc]


def test_parser_repr_composes_component_reprs() -> None:
    assert repr(Parser()) == "Parser(Lexicon(default), Policy())"
    p = Parser(policy=Policy(name_order=FAMILY_FIRST))
    assert repr(p) == "Parser(Lexicon(default), Policy(name_order=FAMILY_FIRST))"


def test_parsedname_repr_includes_ambiguities_line() -> None:
    pn = parse("Van Johnson")
    r = repr(pn)
    assert "given: 'Van'" in r
    assert "ambiguities:" in r and "particle-or-given" in r


def test_module_parse_reuses_the_default_parser() -> None:
    import nameparser._parser as parser_mod
    assert parser_mod._default_parser() is parser_mod._default_parser()


def test_parser_for_stacks_locales() -> None:
    ru = Locale(code="ru",
                lexicon=Lexicon.empty().add(titles={"г-н"}),
                policy=PolicyPatch(patronymic_rules=frozenset(
                    {PatronymicRule.EAST_SLAVIC})))
    p = parser_for(ru)
    assert PatronymicRule.EAST_SLAVIC in p.policy.patronymic_rules
    pn = p.parse("г-н Сидоров Иван Петрович")
    assert pn.title == "г-н"
    assert pn.given == "Иван"
    assert pn.family == "Сидоров"


def test_parser_for_rejects_non_locales() -> None:
    with pytest.raises(TypeError, match="Locale"):
        parser_for("ru")  # type: ignore[arg-type]


def test_parser_for_wraps_pack_errors_with_identity() -> None:
    # PolicyPatch validates lazily (by design), so an invalid value sits
    # latent in a perfectly constructible Locale until apply time
    bad = Locale(code="xx", lexicon=Lexicon.empty(),
                 policy=PolicyPatch(name_order=(1, 2, 3)))  # type: ignore[arg-type]
    # the rewrap preserves the taxonomy's exception type (here the
    # non-Role element TypeError) while adding the pack identity
    with pytest.raises(TypeError, match="while applying locale 'xx'"):
        parser_for(bad)


def test_parser_for_warns_on_scalar_conflict() -> None:
    a = Locale(code="aa", lexicon=Lexicon.empty(),
               policy=PolicyPatch(strip_emoji=False))
    b = Locale(code="bb", lexicon=Lexicon.empty(),
               policy=PolicyPatch(strip_emoji=True))
    with pytest.warns(UserWarning, match="strip_emoji"):
        p = parser_for(a, b)
    assert p.policy.strip_emoji is True  # later wins


def test_matches_component_wise_case_insensitive() -> None:
    pn = parse("John Smith")
    assert pn.matches("JOHN SMITH")
    assert pn.matches(parse("john smith"))
    assert not pn.matches("John Smythe")
    with pytest.raises(TypeError, match="str or ParsedName"):
        pn.matches(42)  # type: ignore[arg-type]


def test_family_first_given_last_places_middle_between() -> None:
    # T1: the three-piece FAMILY_FIRST_GIVEN_LAST assignment -- family
    # from the front, given from the END, middle between (not a rotation
    # of FAMILY_FIRST)
    p = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    pn = p.parse("Zeng Xiao Long")
    assert (pn.family, pn.middle, pn.given) == ("Zeng", "Xiao", "Long")


def test_multiple_unbalanced_delimiters_each_reported() -> None:
    # T4: the extract scan continues past the first unmatched opener;
    # each one is reported and treated as literal text
    pn = parse('John "Jack (Smith')
    unbalanced = [a for a in pn.ambiguities
                  if a.kind is AmbiguityKind.UNBALANCED_DELIMITER]
    assert len(unbalanced) == 2
    assert pn.given == "John" and pn.family == "(Smith"
    assert not pn.nickname


def test_matches_accepts_explicit_parser() -> None:
    family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    pn = family_first.parse("Yamada Taro")
    assert pn.matches("Yamada Taro", parser=family_first)
    assert not pn.matches("Yamada Taro")  # default parser reads given-first


def test_phd_split_heals_in_the_suffix_view() -> None:
    # v1 parity via fix_phd: the split credential renders as one suffix
    assert parse("John Ph. D.").suffix == "Ph. D."
    assert parse("John Smith PhD MD").suffix == "PhD, MD"  # unchanged


def test_phd_split_mid_name_is_a_suffix() -> None:
    # v1 parity: fix_phd extracted the credential BEFORE parsing, so
    # position never mattered; the merged piece is a suffix anywhere
    pn = parse("Dr. John Ph. D. Smith")
    assert pn.suffix == "Ph. D."
    assert pn.family == "Smith"
    assert pn.middle == ""

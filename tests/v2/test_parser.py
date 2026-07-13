import pickle

import pytest

from nameparser import Lexicon, Parser, Policy, parse
from nameparser._policy import FAMILY_FIRST
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

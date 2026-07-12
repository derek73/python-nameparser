
from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._policy import FAMILY_FIRST, PatronymicRule, Policy, PolicyPatch
from nameparser._types import Ambiguity, AmbiguityKind, ParsedName, Role, Span, Token


def test_token_repr_is_compact() -> None:
    t = Token("de", Span(9, 11), Role.FAMILY, frozenset({"particle"}))
    assert repr(t) == "Token('de' @9:11 FAMILY {particle})"
    assert repr(Token("Jane", None, Role.GIVEN)) == "Token('Jane' @synthetic GIVEN)"


def test_ambiguity_repr_shows_kind_and_token_texts() -> None:
    van = Token("Van", Span(0, 3), Role.GIVEN)
    a = Ambiguity(AmbiguityKind.PARTICLE_OR_GIVEN, "detail", (van,))
    assert repr(a) == "Ambiguity('particle-or-given': 'Van')"


def test_parsedname_repr_lists_nonempty_fields_in_canonical_order() -> None:
    pn = ParsedName("John Smith", (
        Token("John", Span(0, 4), Role.GIVEN),
        Token("Smith", Span(5, 10), Role.FAMILY),
    ))
    assert repr(pn) == (
        "<ParsedName: [\n\tgiven: 'John'\n\tfamily: 'Smith'\n]>"
    )


def test_parsedname_repr_includes_ambiguities_line_when_present() -> None:
    van = Token("Van", Span(0, 3), Role.GIVEN)
    pn = ParsedName("Van Johnson",
                    (van, Token("Johnson", Span(4, 11), Role.FAMILY)),
                    (Ambiguity(AmbiguityKind.PARTICLE_OR_GIVEN, "d", (van,)),))
    assert "ambiguities: ['particle-or-given']" in repr(pn)


def test_empty_parsedname_repr() -> None:
    assert repr(ParsedName("", ())) == "<ParsedName: []>"


def test_policy_repr_shows_only_nondefault_fields() -> None:
    assert repr(Policy()) == "Policy()"
    p = Policy(name_order=FAMILY_FIRST, strip_bidi=False)
    assert repr(p) == "Policy(name_order=FAMILY_FIRST, strip_bidi=False)"


def test_lexicon_repr_is_bounded() -> None:
    assert repr(Lexicon.default()) == "Lexicon(default)"
    lex = Lexicon.default().add(titles={"zqx", "zqy"})
    assert repr(lex) == "Lexicon(default + titles: +2)"
    assert "zqx" not in repr(lex)  # never dump contents


def test_locale_repr_shows_code_and_patched_fields() -> None:
    ru = Locale("ru", Lexicon.empty(),
                PolicyPatch(patronymic_rules=frozenset(
                    {PatronymicRule.EAST_SLAVIC})))
    assert repr(ru) == "Locale('ru': patronymic_rules)"
    assert repr(Locale("xx", Lexicon.empty())) == "Locale('xx')"

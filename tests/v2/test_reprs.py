import pytest

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._parser import Parser
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
        "<ParsedName: [\n    given: 'John'\n    family: 'Smith'\n]>"
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


def test_lexicon_repr_diffs_against_nearer_baseline() -> None:
    # An empty()-built Lexicon must not render as default() minus ~700
    # entries -- diff against whichever named constructor is nearer.
    assert repr(Lexicon.empty()) == "Lexicon(empty)"
    lex = Lexicon.empty().add(titles={"zqx"})
    assert repr(lex) == "Lexicon(empty + titles: +1)"


def test_policy_patch_repr_shows_only_set_fields() -> None:
    assert repr(PolicyPatch()) == "PolicyPatch()"
    assert repr(PolicyPatch(middle_as_family=True)) == \
        "PolicyPatch(middle_as_family=True)"
    assert repr(PolicyPatch(name_order=FAMILY_FIRST)) == \
        "PolicyPatch(name_order=FAMILY_FIRST)"


@pytest.mark.parametrize("obj", [
    Policy(),
    Policy(middle_as_family=True),
    PolicyPatch(),
    PolicyPatch(strip_emoji=False),
    Locale("xx", Lexicon.empty()),
    Locale("xx", Lexicon.empty(), PolicyPatch(middle_as_family=True)),
    Parser(),
])
def test_config_reprs_never_leak_the_unset_sentinel(obj: object) -> None:
    # Guard the whole family: every config type's repr is bounded and
    # deviation-only; the UNSET sentinel must never appear.
    assert "UNSET" not in repr(obj)
    assert "_Unset" not in repr(obj)


def test_policy_patch_repr_survives_unvalidated_name_order() -> None:
    # PolicyPatch defers name_order validation to apply time, so a
    # patch can hold a non-canonical or even garbage tuple -- its repr
    # must describe it, never raise.
    patch = PolicyPatch(name_order=(Role.GIVEN, Role.FAMILY, Role.MIDDLE))
    assert repr(patch) == "PolicyPatch(name_order=(GIVEN, FAMILY, MIDDLE))"
    garbage = PolicyPatch(name_order=("given", "family", "middle"))  # type: ignore[arg-type]
    assert "given" in repr(garbage)          # described, not crashed
    unhashable = PolicyPatch(name_order=([1], "y", "z"))  # type: ignore[arg-type]
    repr(unhashable)                          # must not raise

# tests/v2/pipeline/test_assign.py
from nameparser._lexicon import Lexicon
from nameparser._pipeline._assign import assign
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._group import group
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, Policy
from nameparser._types import AmbiguityKind, Role

_LEX = Lexicon(
    titles=frozenset({"dr", "mr", "mrs", "sir"}),
    given_name_titles=frozenset({"sir"}),
    suffix_acronyms=frozenset({"phd", "md"}),
    suffix_words=frozenset({"jr", "iii", "v"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
    conjunctions=frozenset({"and"}),
    maiden_markers=frozenset({"née"}),
)


def _assigned(text: str, policy: Policy | None = None) -> ParseState:
    state = ParseState(original=text, lexicon=_LEX,
                       policy=policy or Policy())
    return assign(group(classify(segment(tokenize(
        extract_delimited(state))))))


def _by_role(state: ParseState, role: Role) -> str:
    return " ".join(t.text for t in state.tokens if t.role is role)


def test_given_first_positional() -> None:
    out = _assigned("Dr. Juan de la Vega III")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.GIVEN) == "Juan"
    assert _by_role(out, Role.FAMILY) == "de la Vega"
    assert _by_role(out, Role.SUFFIX) == "III"


def test_middles() -> None:
    out = _assigned("John Quincy Adams Smith")
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.MIDDLE) == "Quincy Adams"
    assert _by_role(out, Role.FAMILY) == "Smith"


def test_single_token_takes_name_order_head() -> None:
    assert _by_role(_assigned("John"), Role.GIVEN) == "John"
    out = _assigned("John", Policy(name_order=FAMILY_FIRST))
    assert _by_role(out, Role.FAMILY) == "John"


def test_title_only() -> None:
    out = _assigned("Dr.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert not _by_role(out, Role.GIVEN)


def test_leading_ambiguous_particle_reads_as_given_with_ambiguity() -> None:
    out = _assigned("Van Johnson")
    assert _by_role(out, Role.GIVEN) == "Van"
    assert _by_role(out, Role.FAMILY) == "Johnson"
    assert any(a.kind is AmbiguityKind.PARTICLE_OR_GIVEN
               for a in out.ambiguities)
    # unambiguous input: no ambiguity recorded
    assert not _assigned("John Smith").ambiguities


def test_family_comma() -> None:
    out = _assigned("de la Vega, Juan")
    assert _by_role(out, Role.FAMILY) == "de la Vega"
    assert _by_role(out, Role.GIVEN) == "Juan"


def test_family_comma_with_title_and_middle() -> None:
    out = _assigned("Smith, Dr. John A.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.MIDDLE) == "A."
    assert _by_role(out, Role.FAMILY) == "Smith"


def test_family_comma_lone_post_comma_title() -> None:
    # v1 parity: a lone post-comma title is a TITLE ('Smith, Dr.'),
    # not a given name or suffix; post_rules later applies the
    # title+lone-family handling
    out = _assigned("Smith, Dr.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert not _by_role(out, Role.GIVEN)


def test_suffix_comma_and_extra_segments() -> None:
    out = _assigned("Smith, John, Jr.")
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert _by_role(out, Role.SUFFIX) == "Jr."


def test_trailing_suffix_run_no_comma() -> None:
    out = _assigned("John Jack Kennedy PhD MD")
    assert _by_role(out, Role.MIDDLE) == "Jack"
    assert _by_role(out, Role.FAMILY) == "Kennedy"
    assert _by_role(out, Role.SUFFIX) == "PhD MD"


def test_initial_veto_keeps_v_in_middle() -> None:
    out = _assigned("John V. Smith")
    assert _by_role(out, Role.MIDDLE) == "V."
    assert _by_role(out, Role.FAMILY) == "Smith"


def test_nickname_only_leaves_name_fields_empty() -> None:
    out = _assigned("(Jack)")
    assert _by_role(out, Role.NICKNAME) == "Jack"
    assert not _by_role(out, Role.GIVEN) and not _by_role(out, Role.FAMILY)


def test_single_name_with_nickname_goes_to_family() -> None:
    out = _assigned("John (Jack)")
    assert _by_role(out, Role.FAMILY) == "John"
    assert not _by_role(out, Role.GIVEN)


def test_family_first_order() -> None:
    out = _assigned("Yamada Taro", Policy(name_order=FAMILY_FIRST))
    assert _by_role(out, Role.FAMILY) == "Yamada"
    assert _by_role(out, Role.GIVEN) == "Taro"
    out2 = _assigned("Yamada Hanako Taro",
                     Policy(name_order=FAMILY_FIRST))
    assert _by_role(out2, Role.FAMILY) == "Yamada"
    assert _by_role(out2, Role.GIVEN) == "Hanako"
    assert _by_role(out2, Role.MIDDLE) == "Taro"


def test_family_first_given_last_order() -> None:
    # Pinned against the actual built pipeline (2026-07-12), not guessed:
    # 'Van' is particles_ambiguous and non-leading, so group's prefix
    # chain (which is name_order-agnostic -- it lands upstream of assign
    # and doesn't consult Policy) absorbs 'Van Anh Thu' into ONE piece
    # before assign ever sees it. With only two name pieces left,
    # FAMILY_FIRST_GIVEN_LAST's positional rule (family, then given for
    # count==2) correctly assigns Nguyen -> FAMILY and the whole merged
    # piece -> GIVEN; there is no MIDDLE piece to assign. This is a
    # sensible consequence of the current, order-agnostic group stage --
    # not a contract violation of assign -- and is the exact kind of gap
    # the Vietnamese-aware locale pack (#270/#272 follow-ups) is meant to
    # close by teaching group to suppress the particle chain under this
    # name_order. Do not "fix" this by changing assign.
    out = _assigned("Nguyen Van Anh Thu",
                    Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    assert _by_role(out, Role.FAMILY) == "Nguyen"
    assert _by_role(out, Role.GIVEN) == "Van Anh Thu"
    assert _by_role(out, Role.MIDDLE) == ""

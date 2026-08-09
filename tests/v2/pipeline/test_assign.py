# tests/v2/pipeline/test_assign.py
import pytest

from nameparser._lexicon import Lexicon
from nameparser._pipeline._assign import assign
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._group import group
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, Policy, Script,
)
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


def _assigned(text: str, policy: Policy | None = None,
              lexicon: Lexicon | None = None) -> ParseState:
    state = ParseState(original=text, lexicon=lexicon or _LEX,
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


@pytest.mark.parametrize("policy,role", [
    (None, "given"),
    (Policy(name_order=FAMILY_FIRST), "family"),
    (Policy(name_order=FAMILY_FIRST_GIVEN_LAST), "family"),
])
def test_leading_particle_detail_names_the_role_it_took(
        policy: Policy | None, role: str) -> None:
    # The fork is the same under every order -- particle or name --
    # but which role the head piece actually took is the assignment's
    # answer, so the user-facing detail has to read it off the token
    # rather than hardcode "given", exactly as SUFFIX_OR_NAME does.
    # kind is public API and stays PARTICLE_OR_GIVEN throughout: the
    # fork really is "particle or given" even where the piece landed
    # in FAMILY.
    (amb,) = _assigned("Van Johnson", policy).ambiguities
    assert amb.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert amb.detail == (
        f"leading 'Van' may be a family-name particle; "
        f"read as a {role} name")


def test_leading_particle_detail_follows_the_effective_order() -> None:
    # Reading policy.name_order[0] instead of the token's own role
    # would pass every case above, because there the two agree. They
    # come apart on the script_orders path (#271): a wholly-Han name
    # resolves family-first through _effective_order while name_order
    # is untouched and still reads given-first. The head piece is the
    # FAMILY name here, and the detail has to say so.
    han = _LEX.add(particles={"毛"}, particles_ambiguous={"毛"})
    out = _assigned("毛 泽东", lexicon=han)
    assert out.policy.name_order[0] is Role.GIVEN
    assert out.policy.script_orders[0][0] is Script.HAN
    assert _by_role(out, Role.FAMILY) == "毛"
    assert _by_role(out, Role.GIVEN) == "泽东"
    (amb,) = out.ambiguities
    assert amb.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert amb.detail == (
        "leading '毛' may be a family-name particle; "
        "read as a family name")


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


def test_suffix_comma_structure() -> None:
    # Structure.SUFFIX_COMMA (segment.py): >1 word before the first
    # comma AND every post-first segment is entirely lenient-suffix.
    # ('Smith, John, Jr.' above only has ONE word before its first
    # comma, so it is FAMILY_COMMA with a trailing suffix segment, not
    # this branch.) Previously this assign() branch (tail=1) was only
    # reached via the full-corpus test, not its own isolated case.
    out = _assigned("John Smith, PhD")
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert _by_role(out, Role.SUFFIX) == "PhD"


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


def test_script_order_applies_when_every_piece_is_one_script() -> None:
    out = _assigned("毛 泽东")
    assert _by_role(out, Role.FAMILY) == "毛"
    assert _by_role(out, Role.GIVEN) == "泽东"


def test_script_order_declines_on_a_mixed_piece_set() -> None:
    # {None, HAN}: one Latin piece is enough to put the name back on
    # the positional default, even though the other piece is Han.
    out = _assigned("毛 Smith")
    assert _by_role(out, Role.GIVEN) == "毛"
    assert _by_role(out, Role.FAMILY) == "Smith"


def test_script_order_declines_when_no_piece_has_a_script() -> None:
    # all-None: the ordinary Latin path, unreachable by the table.
    out = _assigned("John Smith")
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"


def test_kana_licensed_piece_resolves_via_hiragana_entry() -> None:
    # a kanji+hiragana mixed piece set takes the license (#272) and
    # resolves through the HIRAGANA table entry, family-first
    out = _assigned("高橋 みなみ")
    assert _by_role(out, Role.FAMILY) == "高橋"
    assert _by_role(out, Role.GIVEN) == "みなみ"


def test_pure_katakana_piece_falls_back_to_name_order() -> None:
    # katakana alone is not in the table (transcription ambiguity), so
    # a pure-katakana piece set falls back to the positional default
    out = _assigned("マイケル ジャクソン")
    assert _by_role(out, Role.GIVEN) == "マイケル"
    assert _by_role(out, Role.FAMILY) == "ジャクソン"


def test_interpunct_divided_name_reads_positionally() -> None:
    # 威廉·莎士比亚 is William Shakespeare: a 间隔号-divided name is a
    # transcription and keeps source order (spec 2026-07-30) -- the
    # B7 is the marker, playing the role pure katakana plays in the
    # kana license
    out = _assigned("威廉·莎士比亚")
    assert _by_role(out, Role.GIVEN) == "威廉"
    assert _by_role(out, Role.FAMILY) == "莎士比亚"


def test_interpunct_suppression_yields_to_explicit_name_order() -> None:
    # the suppression falls back to name_order, it does not force
    # given-first: an explicit FAMILY_FIRST governs the transcription
    out = _assigned("威廉·莎士比亚", Policy(name_order=FAMILY_FIRST))
    assert _by_role(out, Role.FAMILY) == "威廉"
    assert _by_role(out, Role.GIVEN) == "莎士比亚"


def test_script_with_no_table_entry_falls_back() -> None:
    # A single, well-defined script the table simply does not list:
    # resolution must fall through to name_order rather than pick an
    # arbitrary entry.
    hangul_only = Policy(script_orders={Script.HANGUL: FAMILY_FIRST})  # type: ignore[arg-type]
    out = _assigned("毛 泽东", hangul_only)
    assert _by_role(out, Role.GIVEN) == "毛"
    assert _by_role(out, Role.FAMILY) == "泽东"

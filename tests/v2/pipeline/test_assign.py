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

#: The three read orders and the role a lone name word takes under
#: each, shared by every parametrized case below that asks the same
#: question of all three: the default (None, given-first), and the two
#: declared family-first orders.
_ORDERS = [
    (None, "given"),
    (Policy(name_order=FAMILY_FIRST), "family"),
    (Policy(name_order=FAMILY_FIRST_GIVEN_LAST), "family"),
]

_LEX = Lexicon(
    titles=frozenset({"dr", "mr", "mrs", "sir", "sr"}),
    given_name_titles=frozenset({"sir"}),
    suffix_acronyms=frozenset({"phd", "md"}),
    suffix_words=frozenset({"jr", "iii", "v", "sr"}),
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


def test_a_title_needs_a_following_piece() -> None:
    # v1 parity, in the count group shares since #424: the last of two
    # title words is the name, not a second title
    out = _assigned("Dr. Mr.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.GIVEN) == "Mr."


def test_leading_ambiguous_particle_reads_as_given_with_ambiguity() -> None:
    out = _assigned("Van Johnson")
    assert _by_role(out, Role.GIVEN) == "Van"
    assert _by_role(out, Role.FAMILY) == "Johnson"
    assert any(a.kind is AmbiguityKind.PARTICLE_OR_GIVEN
               for a in out.ambiguities)
    # unambiguous input: no ambiguity recorded
    assert not _assigned("John Smith").ambiguities


@pytest.mark.parametrize("policy,role", _ORDERS)
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


@pytest.mark.parametrize("policy,role", _ORDERS)
@pytest.mark.parametrize("text,kind,detail", [
    ("Andrew", AmbiguityKind.GIVEN_OR_FAMILY,
     "'Andrew' is the only name word and nothing else decides it; "
     "read as a {role} name by convention, which follows the read order"),
    ("Rinpoche", AmbiguityKind.SUFFIX_OR_NAME,
     "'Rinpoche' is post-nominal vocabulary with no name word beside "
     "it; read as a {role} name rather than a post-nominal, nothing "
     "else being left to be the name"),
    ("John of Prince", AmbiguityKind.TITLE_OR_NAME,
     "'John of Prince' is the only name unit and joins title "
     "vocabulary to a name word; read as a {role} name by convention"),
])
def test_convention_details_name_the_role_the_assignment_took(
        text: str, kind: AmbiguityKind, detail: str,
        policy: Policy | None, role: str) -> None:
    # The three conventions this site reports all place a lone name
    # word, and all three details have to READ the field back off the
    # token rather than hardcode "given": the field follows the read
    # order, which is why none of the three kinds names it. The
    # PARTICLE_OR_GIVEN test above is the precedent, and these are the
    # only other details at this site that name a field -- H4's PEEL
    # shape ("Lord Chancellor") deliberately names none, because H1
    # retags that word after assign under the default order.
    lex = _LEX.add(suffix_words={"rinpoche"}, conjunctions={"of"},
                   titles={"prince"})
    (amb,) = _assigned(text, policy, lexicon=lex).ambiguities
    assert amb.kind is kind
    assert amb.detail == detail.format(role=role)


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


def test_trailing_title_run_is_set_before_the_positional_read() -> None:
    """The walk shortens the name-piece list, and does it early.

    Two TITLE tokens from opposite ends of the input, and the piece
    between them read as the family name -- which is only true if the
    walk ran before _name_positions did. `order` is the default
    because the positional read still happened: the walk removes
    pieces from it, it does not replace it.
    """
    out = _assigned("Dr. John Smith Mr.")
    assert _by_role(out, Role.TITLE) == "Dr. Mr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert out.order == Policy().name_order


def test_the_suffix_peel_runs_over_the_pieces_the_walk_left() -> None:
    """The trailing title can stand BEHIND a suffix word.

    'Mr.' stopped the first peel, so a single pass would have left
    'Jr.' as the last name piece and made a generational suffix the
    family name. The first peel is provisional: the walk's piece is
    spliced out and the peel runs over what stands, reading 'Jr.' as
    the suffix it is.
    """
    out = _assigned("John Smith Jr. Mr.")
    assert _by_role(out, Role.TITLE) == "Mr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert _by_role(out, Role.SUFFIX) == "Jr."


def test_the_trailing_title_is_transparent_to_the_suffix_peel() -> None:
    """The principle the provisional peel serves.

    'X Mr. Y' reads exactly as 'X Y' reads, plus the title -- so the
    peel decides over the pieces with the title spliced OUT, in
    original order, rather than over the two halves separately. Both
    readings below are what the same input without 'Mr.' gives: the
    reserve keeps a bare ambiguous acronym the family of a two-word
    name, and takes it as a credential when a full name remains.
    """
    lex = _LEX.add(suffix_acronyms={"ma"},
                   suffix_acronyms_ambiguous={"ma"})
    out = _assigned("John Mr. MA", lexicon=lex)
    assert _by_role(out, Role.TITLE) == "Mr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "MA"
    assert not _by_role(out, Role.SUFFIX)
    out = _assigned("John Smith Mr. MA", lexicon=lex)
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert _by_role(out, Role.SUFFIX) == "MA"


def test_the_walk_reports_only_the_peel_that_decided() -> None:
    """One peel decides, so one peel reports.

    The numeral fork reads the piece before the numeral. Over the
    input as written that piece is 'Mr.' and 'VI' is taken; over the
    spliced pieces it is 'V', an initial shape, and the fork declines
    -- which is the answer 'John Smith V VI' gets, with no report.
    Reporting from the provisional peel as well said suffix 'V VI'
    and reported the fork twice.
    """
    out = _assigned("John Smith V Mr. VI")
    assert _by_role(out, Role.TITLE) == "Mr."
    assert _by_role(out, Role.MIDDLE) == "Smith V"
    assert _by_role(out, Role.FAMILY) == "VI"
    assert not _by_role(out, Role.SUFFIX)
    assert not out.ambiguities


def test_the_family_comma_walk_reads_past_its_own_suffix_tail() -> None:
    """Segment 1's candidates are what its walk does not read as a
    suffix -- the strict test AND the lenient one (#144).

    'V' after the comma is this segment's suffix, so the title behind
    it is still the trailing piece; and with the two words swapped
    'V' is where the name ends once the walk has taken the title, so
    the lenient test still reaches it. Both are 'Smith, John V' plus
    a title.
    """
    for text in ("Smith, John Mr. V", "Smith, John V Mr."):
        out = _assigned(text)
        assert _by_role(out, Role.TITLE) == "Mr.", text
        assert _by_role(out, Role.GIVEN) == "John", text
        assert _by_role(out, Role.FAMILY) == "Smith", text
        assert _by_role(out, Role.SUFFIX) == "V", text
        assert not _by_role(out, Role.MIDDLE), text


def test_trailing_title_run_after_a_family_comma() -> None:
    """The same rule on segment 1's own walk.

    A name word after the comma keeps the no-name gate from reading
    the segment as a credential run, so this shape had no route to
    TITLE at all and read the word as a middle name.
    """
    out = _assigned("Smith, John Mr.")
    assert _by_role(out, Role.TITLE) == "Mr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert not _by_role(out, Role.MIDDLE)


def test_the_trailing_title_is_taken_before_the_script_order_resolves(
) -> None:
    """The other half of "set BEFORE _name_positions".

    The sibling above pins that the walk shortens the piece list in
    time for the POSITIONAL read. This pins it for the SCRIPT read,
    which is the reason the placement was chosen: a Latin title at
    the back of a wholly-Han name is the one piece that would make
    the piece set look mixed-script, and a mixed set declines the
    script order. Taken first, the pieces the script test sees are
    all Han and the Han order stands -- family '毛', given '泽东',
    which is not what the default order would have given.
    """
    out = _assigned("毛 泽东 Dr.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.FAMILY) == "毛"
    assert _by_role(out, Role.GIVEN) == "泽东"
    assert out.order != Policy().name_order


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
    # transcription and keeps source order (rule W4's Accepted) -- the
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


def test_all_title_post_comma_segment_leaves_segment_zero_positional() -> None:
    # 'John Smith, Dr.' -- the comma is followed by nothing but a title,
    # so it never said where the family name ends. Reading segment 0
    # wholly as family throws away a split the writer gave us.
    out = _assigned("John Smith, Dr.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"


def test_all_title_post_comma_segment_needs_two_pre_comma_pieces() -> None:
    # 'Smith, Dr.' has nothing to split: one pre-comma piece stays FAMILY
    # rather than becoming a lone GIVEN under the positional read.
    out = _assigned("Smith, Dr.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert _by_role(out, Role.GIVEN) == ""


def test_post_comma_title_run_is_all_titles() -> None:
    out = _assigned("John Smith, Mr. Dr.")
    assert _by_role(out, Role.TITLE) == "Mr. Dr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"


def test_a_title_and_a_suffix_after_the_comma_fix_no_family_either() -> None:
    # the condition is "no name word", not "all titles": a title and a
    # postnominal with nothing between them said nothing about where
    # the family ends (the design-docs review found C1 silent on it)
    out = _assigned("John Smith, Mr. Jr.")
    assert _by_role(out, Role.TITLE) == "Mr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert _by_role(out, Role.SUFFIX) == "Jr."


def test_the_positional_segment_zero_records_its_order() -> None:
    # post_rules' family-first fold and its leading-piece scan key on
    # "assign records no order after a family comma"; the positional
    # read is the path that gives one (the test review found the fold
    # missing 'de Mesnil Jean, Dr.' under a family-first order)
    out = _assigned("John Smith, Dr.")
    assert out.order is not None
    out = _assigned("Smith, Dr. John")
    assert out.order is None


def test_partly_title_post_comma_segment_keeps_family_comma() -> None:
    # 'Smith, Dr. John' still has a name after the title, so the comma
    # DID fix the family: segment 0 stays wholly family.
    out = _assigned("Smith, Dr. John")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.FAMILY) == "Smith"


def test_non_title_post_comma_segment_is_untouched() -> None:
    out = _assigned("John Smith, Jones")
    assert _by_role(out, Role.FAMILY) == "John Smith"
    assert _by_role(out, Role.GIVEN) == "Jones"


def test_positional_segment_zero_reports_the_particle_fork() -> None:
    # The comma no longer fixed the family, so the leading ambiguous
    # particle IS a live fork again -- emitted at the site that decides
    # it, per the ambiguity doctrine.
    out = _assigned("Van Johnson, Dr.")
    assert _by_role(out, Role.GIVEN) == "Van"
    assert _by_role(out, Role.FAMILY) == "Johnson"
    assert [a.kind for a in out.ambiguities] == \
        [AmbiguityKind.PARTICLE_OR_GIVEN]


def test_a_credential_run_after_a_family_comma_reads_as_suffixes() -> None:
    # 'Smith, Jr.' -- the peel's whole-segment exception claimed this
    # even with 'jr' out of TITLES, because is_leading_title also
    # infers a title from the period-abbreviation shape. The slot after
    # a family comma IS postnominal position, so a run that is nothing
    # but suffix pieces is read as one before the peel gets a chance
    # (#296) -- and the whole run, not the lone piece: 'Smith, Ph. D.
    # Jr.' put the split credential in the given name (#325).
    out = _assigned("Smith, Jr.")
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert _by_role(out, Role.SUFFIX) == "Jr."
    assert _by_role(out, Role.TITLE) == ""
    out = _assigned("Smith, Ph. D. Jr.")
    assert _by_role(out, Role.FAMILY) == "Smith"
    assert _by_role(out, Role.SUFFIX) == "Ph. D. Jr."
    assert _by_role(out, Role.GIVEN) == ""
    out = _assigned("Smith, Jr. PhD")
    assert _by_role(out, Role.SUFFIX) == "Jr. PhD"
    assert _by_role(out, Role.TITLE) == ""


def test_lone_post_comma_dual_word_reads_as_the_postnominal() -> None:
    # 'sr' kept BOTH memberships; position is what decides, and this is
    # the position that decides postnominal.
    out = _assigned("Smith, Sr.")
    assert _by_role(out, Role.SUFFIX) == "Sr."
    assert _by_role(out, Role.TITLE) == ""


def test_leading_dual_word_still_reads_as_the_title() -> None:
    # The other half of the same fork, untouched: the peel's normal path.
    out = _assigned("Sr. Garcia")
    assert _by_role(out, Role.TITLE) == "Sr."
    # assign leaves the one name word as the given; H1 (post_rules)
    # makes it the family
    assert _by_role(out, Role.GIVEN) == "Garcia"


def test_lone_post_comma_title_is_not_a_suffix() -> None:
    # 'Smith, Dr.' decides WITHOUT consulting the ordering: after the
    # audit 'dr' is not suffix-tagged, so the suffix test simply declines
    # and the title peel takes it as before.
    out = _assigned("Smith, Dr.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.SUFFIX) == ""


def test_a_mixed_post_comma_run_keeps_the_walk_order() -> None:
    # a title then a suffix word is read where each stands (v1's walk:
    # leading titles peel, the rest is given / middle / suffix), and a
    # name word anywhere in the run makes it a name, not a credential run
    out = _assigned("Smith, Dr. Jr.")
    assert _by_role(out, Role.TITLE) == "Dr."
    assert _by_role(out, Role.SUFFIX) == "Jr."
    out = _assigned("Smith, John Jr.")
    assert _by_role(out, Role.GIVEN) == "John"
    assert _by_role(out, Role.SUFFIX) == "Jr."

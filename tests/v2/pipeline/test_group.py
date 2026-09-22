import bisect
import dataclasses
from collections.abc import Sequence
from typing import cast

import pytest

from nameparser import Parser
from nameparser._lexicon import Lexicon
from nameparser._pipeline import _group as _group_module
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited, _maiden_marked
from nameparser._pipeline._group import (
    TailReader, _group_segment, group, marker_run_length,
)
from nameparser._pipeline._script_segment import script_segment
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import (
    ParseState, PendingAmbiguity, Structure, WorkToken,
)
from nameparser._pipeline._tokenize import tokenize
from nameparser._pipeline._vocab import maiden_marker_run
from nameparser._policy import Policy, Script
from nameparser._types import AmbiguityKind, Role

_LEX = Lexicon(
    titles=frozenset({"mr", "mrs", "secretary", "the", "state"}),
    suffix_acronyms=frozenset({"phd"}),
    suffix_words=frozenset({"jr"}),
    particles=frozenset({"de", "la", "van", "von", "und", "zu"}),
    particles_ambiguous=frozenset({"van"}),
    conjunctions=frozenset({"and", "of", "the", "y"}),
    bound_given_names=frozenset({"abdul"}),
    maiden_markers=frozenset({"née", "geb"}),
)
# NOTE: "the" sits in both titles and conjunctions here, mirroring v1's
# real vocabulary overlap; the subset rule only constrains particles.


def _grouped(text: str, policy: Policy | None = None,
             lexicon: Lexicon | None = None) -> ParseState:
    state = ParseState(original=text, lexicon=lexicon or _LEX,
                       policy=policy or Policy())
    return group(classify(segment(tokenize(extract_delimited(state)))))


def _piece_texts(state: ParseState) -> list[list[str]]:
    return [[" ".join(state.tokens[i].text for i in piece)
             for piece in seg] for seg in state.pieces]


def _piece_has_tag(state: ParseState, piece: tuple[int, ...],
                   tag: str) -> bool:
    return any(tag in state.tokens[i].tags for i in piece)


def test_no_joins_pass_through() -> None:
    out = _grouped("John Smith")
    assert _piece_texts(out) == [["John", "Smith"]]


def test_conjunction_joins_neighbors() -> None:
    out = _grouped("Mr. and Mrs. John Smith")
    assert _piece_texts(out) == [["Mr. and Mrs.", "John", "Smith"]]
    # joined-to-a-title piece is flagged a derived title
    assert "title" in out.piece_tags[0][0]


def test_contiguous_conjunctions_join_first() -> None:
    out = _grouped("The Secretary of State Hillary Clinton")
    assert _piece_texts(out) == [["The Secretary of State", "Hillary", "Clinton"]]
    assert "title" in out.piece_tags[0][0]


def test_single_letter_conjunction_prefers_initial_when_short() -> None:
    # v1 Google Code issue 11 ("john e smith"): 3 rootname parts,
    # single-letter conjunction "y"
    out = _grouped("John y Smith")
    assert _piece_texts(out) == [["John", "y", "Smith"]]


def test_prefix_chain_joins_to_following() -> None:
    out = _grouped("Juan de la Vega")
    assert _piece_texts(out) == [["Juan", "de la Vega"]]


def test_prefix_chain_absorbs_through_to_next_suffix() -> None:
    out = _grouped("Juan de la Vega Martinez PhD")
    assert _piece_texts(out) == [["Juan", "de la Vega Martinez", "PhD"]]


def test_leading_prefix_is_never_chained() -> None:
    # "Van Johnson": the leading piece is a first name, not a particle
    out = _grouped("Van Johnson")
    assert _piece_texts(out) == [["Van", "Johnson"]]


def test_a_title_does_not_make_the_particle_behind_it_non_leading() -> None:
    # #367: "leading" is the first piece of the NAME. A title is not
    # part of the name, so it is stepped over and the grouping is the
    # untitled one with the title in front of it.
    assert _piece_texts(_grouped("Mr. Van Johnson")) == \
        [["Mr.", "Van", "Johnson"]]
    assert _piece_texts(_grouped("Mr. Van Johnson Smith")) == \
        [["Mr.", "Van", "Johnson", "Smith"]]


def test_a_title_that_is_also_a_particle_stops_the_scan() -> None:
    # the other half of the same rule, and the reason it is not spelled
    # "the first piece that is not a title": the default vocabulary
    # puts `freiherr`, `st` and `do` in BOTH sets, so any of them could
    # be the name's own first piece. Stepping over one would make the
    # particle behind it chain, and would break a name with no title in
    # front of it at all ("St John Smith" -> title St, given John,
    # family Smith). Spelled here as the overlap a CONFIG can create,
    # which is the same shape: tests/test_constants.py::test_add_title
    # adds `te` to the titles while `te` ships as a particle.
    overlap = dataclasses.replace(_LEX, titles=_LEX.titles | {"van"})
    assert _piece_texts(_grouped("Van von Richthofen", lexicon=overlap)) == \
        [["Van", "von Richthofen"]]
    assert _piece_texts(_grouped("Van Johnson Smith", lexicon=overlap)) == \
        [["Van", "Johnson", "Smith"]]


def test_a_suffix_shaped_leading_piece_is_not_stepped_over() -> None:
    # #367 steps over TITLE pieces only. Adding suffix pieces to that
    # scan survives the whole suite while changing what these names
    # parse to, so pin them here: with the skip, `leading` moves to
    # "Van", the chain loop passes over it, and the two pieces below
    # become three -- which puts Van in the middle name rather than the
    # family once roles exist. See _group.py for why that reading is
    # worse rather than merely different.
    #
    # "Ph. D. Van Johnson" left this test with #371: the pair is no
    # longer merged at the head, so there is no suffix-shaped leading
    # piece there to step over or not.
    #
    # `PhD` is the replacement witness and `II` is NOT one, which is
    # the trap this file's reduced lexicon sets: `_LEX` ships
    # suffix_acronyms={"phd"} and no roman numerals, so `II` is not a
    # suffix piece HERE however the shipped vocabulary reads it, and
    # the assertion below survives the very mutation this test is
    # named for. Measured: with suffix pieces added to the scan,
    # "PhD Van Johnson" moves and "II Van Johnson" does not.
    assert _piece_texts(_grouped("PhD Van Johnson")) == [["PhD", "Van Johnson"]]
    assert _piece_texts(_grouped("II Van Johnson")) == [["II", "Van Johnson"]]


def test_the_phd_merge_declines_at_the_head_of_a_name() -> None:
    # A suffix never begins a name (S2, and #371). The merge is what
    # made a leading "Ph." "D." a credential at all, and it emptied the
    # family doing it. Segment 0 only: after a family comma the run
    # legitimately opens its segment, which C1 reads as a listing.
    assert _piece_texts(_grouped("Ph. D. Van Johnson")) == \
        [["Ph.", "D.", "Van Johnson"]]
    assert _piece_texts(_grouped("Smith, Ph. D. Jr.")) == \
        [["Smith"], ["Ph. D.", "Jr."]]
    # segment 0 BEFORE a family comma is the family the comma named,
    # and v1 merges there too ("Ph. D., John" reads last 'Ph. D.'), so
    # the `not family_comma` half of the flag has its own witness --
    # without it this name declines and the family splits.
    assert _piece_texts(_grouped("Ph. D., John")) == \
        [["Ph. D."], ["John"]]
    # the first PIECE is not the first word: a quoted clause leaves the
    # token stream before grouping, so the pair reaches k == 0 with a
    # word ahead of it in the input. v1 merges (its regex needed a
    # preceding space); declining here broke parity on 112 names.
    assert _piece_texts(_grouped('"Bob" Ph. D. John Smith')) == \
        [["Ph. D.", "John", "Smith"]]


def test_von_und_zu_bridges() -> None:
    # conjunction "und" joins two prefixes; the joined piece is a derived
    # prefix and still chains onto the following name (v1 PR #191)
    out = _grouped("Otto von und zu Habsburg")
    assert _piece_texts(out) == [["Otto", "von und zu Habsburg"]]


def test_bound_given_joins_with_three_rootnames() -> None:
    assert _piece_texts(_grouped("abdul rahman al-said")) == \
        [["abdul rahman", "al-said"]]
    # only two rootname pieces: no join (v1 reserve_last)
    assert _piece_texts(_grouped("abdul rahman")) == [["abdul", "rahman"]]


def test_phd_split_across_tokens_merges_as_suffix() -> None:
    out = _grouped("John Smith Ph. D.")
    assert _piece_texts(out) == [["John", "Smith", "Ph. D."]]
    assert "suffix" in out.piece_tags[0][2]
    # continuation tokens of the merged piece carry the stable "joined"
    # tag so the suffix string view can heal the split (", " join would
    # otherwise render 'Ph., D.')
    d_tok = next(t for t in out.tokens if t.text == "D.")
    assert "joined" in d_tok.tags


def test_maiden_marker_consumes_tail() -> None:
    out = _grouped("Jane Smith née Jones")
    assert _piece_texts(out) == [["Jane", "Smith"]]
    maiden = [t.text for t in out.tokens if t.role is Role.MAIDEN]
    assert maiden == ["Jones"]
    # the marker token itself is structural: dropped from assembly
    née_idx = next(i for i, t in enumerate(out.tokens) if t.text == "née")
    assert née_idx in out.dropped


def test_maiden_marker_stops_at_suffix() -> None:
    out = _grouped("Jane Smith née Jones PhD")
    maiden = [t.text for t in out.tokens if t.role is Role.MAIDEN]
    assert maiden == ["Jones"]
    assert _piece_texts(out)[0][-1] == "PhD"


def test_leading_marker_is_not_consumed() -> None:
    # "née Jones" alone: marker at piece 0 has no name before it
    out = _grouped("née Jones")
    assert _piece_texts(out) == [["née", "Jones"]]


_MAIDEN_PARENS = Policy(maiden_delimiters=frozenset({("(", ")")}))
#: `nee` a marker AND `Nee` a surname in one vocabulary -- the collision
#: the clause-size guard exists for. _LEX alone leaves `Nee` untagged,
#: which would let the guard tests pass under every mutant.
_NEE_LEX = _LEX.add(maiden_markers=frozenset({"nee"}))


def test_delimited_marker_is_dropped() -> None:
    """#329: the marker IS tagged -- classify reaches it like any other
    token. What it never enters is `pieces`: extract claims the clause
    and its tokens carry Role.MAIDEN from tokenize, so segment keeps
    them out of the main stream. The #274 rule above walks pieces, so
    the tag alone does it no good."""
    out = _grouped("Jane Smith (née Jones)", policy=_MAIDEN_PARENS)
    maiden = [t.text for i, t in enumerate(out.tokens)
              if t.role is Role.MAIDEN and i not in out.dropped]
    assert maiden == ["Jones"]
    née_idx = next(i for i, t in enumerate(out.tokens) if t.text == "née")
    assert née_idx in out.dropped


def test_lone_delimited_marker_is_kept_when_a_clause_follows() -> None:
    """The clause-size guard, and it is load-bearing rather than
    defensive: `Nee` is a real surname (Irish Ni/Nee, and a Chinese
    romanization), so a one-token clause is a maiden NAME, not a marker.

    The trailing "(Jones)" is what makes this pin the guard. With
    "(Nee)" alone the marker is also the last token in the string, so a
    rule that merely checked for a following token would keep it too
    and the mutant would live. Here a token does follow -- only the
    CLAUSE bound distinguishes them."""
    out = _grouped("Jane Smith (Nee) (Jones)", policy=_MAIDEN_PARENS,
                   lexicon=_NEE_LEX)
    kept = [t.text for i, t in enumerate(out.tokens)
            if t.role is Role.MAIDEN and i not in out.dropped]
    assert kept == ["Nee", "Jones"]


def test_marker_in_the_bare_form_is_left_to_the_piece_rule() -> None:
    """#274 sets Role.MAIDEN on consumed tokens itself, so a maiden role
    is NOT proof that extract produced it. Keying this pass on
    state.extracted spans is what keeps it off the bare path -- a
    neighbour test would eat the `Nee` here, the very surname the guard
    above exists to protect.

    Reads inert and is not: deleting the #329 pass outright leaves this
    green, because the value comes from #274's piece rule and the pass
    never touches the bare path. What it kills is a SPELLING of the
    pass -- drop a maiden marker whose next token is also maiden, the
    form this fix originally took -- and nothing else here covers the
    bare path against it. Checked both ways 2026-08-03."""
    out = _grouped("Jane Smith nee Nee Jones", lexicon=_NEE_LEX)
    kept = [t.text for i, t in enumerate(out.tokens)
            if t.role is Role.MAIDEN and i not in out.dropped]
    assert kept == ["Nee", "Jones"]


def test_every_delimited_marker_is_dropped_not_only_the_first() -> None:
    """Two maiden clauses land as ONE contiguous run of maiden-role
    tokens, so a rule keyed on the run would strip the first marker and
    keep the second. Each clause is scoped separately, so each loses its
    own leading marker."""
    out = _grouped("Jane Smith (née Jones) (geb Braun)",
                   policy=_MAIDEN_PARENS)
    kept = [t.text for i, t in enumerate(out.tokens)
            if t.role is Role.MAIDEN and i not in out.dropped]
    assert kept == ["Jones", "Braun"]


def test_clause_containment_survives_script_segmentation() -> None:
    """The #329 pass finds the clause's first token by SPAN, and the
    comment on it rests that on script_segment only ever cutting a
    token into sub-slices. _grouped omits that stage, so this is the
    one place the two meet: 王小明 becomes 王 + 小明 before group runs,
    which shifts every token index after it while the spans stay
    exact, and the marker is still the token the clause drops."""
    lex = Lexicon(surnames=frozenset({"王"}),
                  maiden_markers=frozenset({"旧姓"}))
    policy = Policy(segment_scripts=frozenset({Script.HAN}),
                    maiden_delimiters=frozenset({("（", "）")}))
    state = ParseState(original="王小明（旧姓 李四）", lexicon=lex,
                       policy=policy)
    out = group(classify(script_segment(segment(
        tokenize(extract_delimited(state))))))
    assert [t.text for t in out.tokens] == ["王", "小明", "旧姓", "李四"]
    kept = [t.text for i, t in enumerate(out.tokens)
            if t.role is Role.MAIDEN and i not in out.dropped]
    assert kept == ["李四"]


def test_initials_do_not_count_as_rootnames_for_conjunction_carveout() -> None:
    # v1 parity: 'J.' is an initial, so total rootnames stay under 4 and
    # the single-letter conjunction 'y' is treated as an initial, not joined
    out = _grouped("J. Ruiz y Gomez")
    assert _piece_texts(out) == [["J.", "Ruiz", "y", "Gomez"]]


def test_extra_suffix_delimiter_splits_tail_entries() -> None:
    # v1 expand_suffix_delimiter parity (#206): a configured delimiter
    # is transparent in a FAMILY_COMMA tail segment -- it separates
    # suffix ENTRIES (each rendered independently) and is itself
    # dropped, rather than becoming a suffix token or fusing the
    # entries on either side into one "joined" run.
    lex = Lexicon(suffix_acronyms=frozenset({"phd"}),
                  suffix_words=frozenset({"jr", "v", "md"}))
    out = _grouped("Smith, John, V MD / PhD",
                   Policy(extra_suffix_delimiters=frozenset({"/"})),
                   lexicon=lex)
    # one tail SEGMENT, split into three suffix pieces: "/" is dropped
    # rather than surviving as its own piece
    assert _piece_texts(out) == [["Smith"], ["John"], ["V", "MD", "PhD"]]
    slash_idx = next(i for i, t in enumerate(out.tokens) if t.text == "/")
    assert slash_idx in out.dropped
    # The tagging half moved to post_rules with #436: the core is
    # dropped HERE, and the entry it separates is decided there, over
    # the spans. test_a_dropped_core_parts_two_entries in
    # tests/v2/pipeline/test_post_rules.py is the assertion that used
    # to sit on the two lines below this one.
    # group writes no between-piece tag at all since #436, and a
    # re-add here would glue the run across the dropped core.
    assert not any("joined" in t.tags for t in out.tokens)


def test_suffix_comma_name_segment_gets_no_additional_count() -> None:
    # v1 parity: additional_parts_count applies to FAMILY_COMMA parts only;
    # ', PhD' must not tip the single-letter-conjunction carve-out
    out = _grouped("John y Smith, PhD")
    assert _piece_texts(out) == [["John", "y", "Smith"], ["PhD"]]


_DUAL_LEX = dataclasses.replace(
    _LEX, bound_given_names=frozenset({"abdul", "dual"}),
    suffix_acronyms=frozenset({"phd", "dual"}))


def test_a_bound_word_in_two_vocabularies_still_joins() -> None:
    # The reserve counts the pieces left to spare, and the bound word's
    # own piece is not one of them to spare -- it is the piece the rule
    # has already claimed. Counting it as a suffix, because the same
    # word is ALSO suffix vocabulary, left the rule silently unable to
    # fire: three name words, but only two counted, one short of the
    # threshold. This is what kept 'abd' out of BOUND_GIVEN_NAMES; the
    # shipped word is exercised in tests/test_bound_given_names.py.
    # Synthetic word, so this pins the MECHANISM -- 'abd' is the only
    # shipped member of the intersection, and removing it from the
    # vocabulary leaves this test green.
    out = _grouped("dual Allah Smith", lexicon=_DUAL_LEX)
    assert _piece_texts(out) == [["dual Allah", "Smith"]]


def test_the_reserve_still_declines_when_only_a_suffix_is_left() -> None:
    # The counted piece is the bound word's own, and NOTHING else that
    # a suffix check excludes: with 'jr' behind it there is no family
    # name to spare, so the join must still decline. The tempting
    # simpler repair -- count every non-title piece -- passes the test
    # above and fails this one, joining 'dual Allah' and leaving the
    # name with no family at all.
    out = _grouped("dual Allah jr", lexicon=_DUAL_LEX)
    assert _piece_texts(out) == [["dual", "Allah", "jr"]]


def test_a_chain_never_leaves_a_marker_standing_alone() -> None:
    """A marker standing as its own piece never follows a piece carrying
    a particle -- the invariant the ORDER buys, pinned at the piece
    level because the fields cannot see it break: a stranded marker is
    a lone trailing piece, which takes the family field and demotes
    the real surname to the middle, and every field still holds
    something plausible.

    The consumer runs before the chain, so a marker still standing when
    the chain arrives is one the consumer declined, and the chain takes
    it as the word M2 says it is. Either the consumer took the marker
    (gone from pieces altogether) or the chain did. What breaks this is
    the pass moving back behind the chain, or a stop on the chain
    reintroduced: #399's stop restated the consumer's condition and
    disagreed with it one suffix later (#417 -- the 'née Jr Jones' row
    below, which the old list did not carry).

    A marker DOES stand alone where no chain reached it, which is M2's
    own "Jones nee" -> family "nee" boundary, so the assertion is
    keyed on the preceding piece rather than on markers as such.
    """
    for text in ("Jane van der Berg née Jones",     # consumer takes
                 "Jane van der Berg née",           # nothing follows
                 "Jane van der Berg née Jr",        # only a suffix
                 "Jane van der Berg née Jr Jones",  # suffix, then a word (#417)
                 "Jane van der née",                # particles only
                 "Jane Smith née Jones",            # no particle: takes
                 "Jane Smith née",                  # no particle: stands
                 "Jane née",
                 # The bound-given join also produces multi-word
                 # pieces, and it may leave a marker standing after
                 # one -- 'abdul Berg' + 'née'. That is M2's allowed
                 # boundary, not a stranding, which is why this
                 # invariant is keyed on the PARTICLE chain rather
                 # than on any joined neighbour. Listed so the
                 # distinction is exercised rather than assumed.
                 "abdul Berg née", "abdul Berg née Jones",
                 "abdul née Jones", "abdul née"):
        out = _grouped(text)
        for seg, texts in zip(out.pieces, _piece_texts(out)):
            for k, (piece, shown) in enumerate(zip(seg, texts)):
                if shown.lower() not in _LEX.maiden_markers or k == 0:
                    continue
                assert not _piece_has_tag(out, seg[k - 1], "particle"), (
                    f"{text!r}: marker {shown!r} left standing after "
                    f"the particle piece {texts[k - 1]!r}")


def test_where_the_marker_lands_when_the_consumer_declines() -> None:
    """The concrete shapes behind the invariant above, so a change that
    preserves it by restructuring the pieces still has to say so here.
    """
    # consumer takes: marker and maiden name leave `pieces` entirely
    assert _piece_texts(_grouped("Jane van der Berg née Jones")) == [
        ["Jane", "van der Berg"]]
    assert _piece_texts(_grouped("Jane Smith née Jones")) == [
        ["Jane", "Smith"]]
    # consumer declines, chain present: the marker rides inside it
    assert _piece_texts(_grouped("Jane van der Berg née")) == [
        ["Jane", "van der Berg née"]]
    assert _piece_texts(_grouped("Jane van der Berg née Jr")) == [
        ["Jane", "van der Berg née", "Jr"]]
    # #417: a name word BEHIND the inner suffix does not change the
    # consumer's answer (its walk stops at the suffix), so the marker
    # still rides inside the chain rather than standing between the
    # chain and the suffix. The parsed fields read the same either
    # way -- middle 'van der Berg née Jr', family 'Jones' -- which is
    # why this is pinned at the piece level.
    assert _piece_texts(_grouped("Jane van der Berg née Jr Jones")) == [
        ["Jane", "van der Berg née", "Jr", "Jones"]]
    # ...and a chain carrying a declined marker is a name piece like
    # any other to the bound-given join (P5 declines a marker "standing
    # as a word of its own", and this one is not)
    assert _piece_texts(_grouped("abdul van der Berg née Jr Jones")) == [
        ["abdul van der Berg née", "Jr", "Jones"]]
    # consumer declines, no chain: the marker stands as its own piece
    assert _piece_texts(_grouped("Jane Smith née")) == [
        ["Jane", "Smith", "née"]]


def test_the_connective_carveout_counts_the_surviving_name() -> None:
    # P3's carve-out asks how many name words the name has,
    # and the marker and the maiden name are not among them: they
    # leave. Counted, 'juan y garcia née jones' was five words, 'y'
    # joined, and once the clause left there was no family name (#418).
    assert _piece_texts(_grouped("juan y garcia née jones")) == [
        ["juan", "y", "garcia"]]
    # the control: the clause changes nothing about the rest
    assert _piece_texts(_grouped("juan y garcia")) == [
        ["juan", "y", "garcia"]]
    # a marker the consumer DECLINES is a word (M2) and counts: four
    # words, so the connective joins
    assert _piece_texts(_grouped("juan y garcia née")) == [
        ["juan y garcia", "née"]]
    # the three-piece gate ahead of the count has the same exposure:
    # taken on the list as written, 'Jane and née Jones' is four
    # pieces, the joins run, and 'and' takes 'Jane' -- the #418
    # empty family one gate earlier. Two pieces remain, so no join.
    assert _piece_texts(_grouped("Jane and née Jones")) == [
        ["Jane", "and"]]


_DASH = Policy(extra_suffix_delimiters=frozenset({" - "}))


def test_a_delimiter_core_in_a_suffix_tail_is_not_maiden_text() -> None:
    """A tail segment drops its delimiter cores (#206) and the marker
    takes what is left, in that order -- the order group() had before
    the marker pass moved ahead of the joins. A core is not a word the
    marker can take: it is structure, like the marker itself."""
    out = _grouped("Smith, John, PhD née - Jones", policy=_DASH)
    core = next(i for i, t in enumerate(out.tokens) if t.text == "-")
    assert core in out.dropped
    assert out.tokens[core].role is not Role.MAIDEN
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == [
        "Jones"]


def test_the_walk_peels_past_a_trailing_core() -> None:
    # The walk's peel skips the cores a tail segment drops, so a core
    # standing last does not make the numeral "not last": the V is the
    # suffix and the marker takes 'Jones' alone (#424; the test
    # review's surviving mutant).
    out = _grouped("Smith, John, PhD née Jones V -", policy=_DASH)
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == [
        "Jones"]


def test_a_core_is_screened_before_the_marker_looks_for_a_word_ahead() -> None:
    """M2 needs a name word BEFORE the marker. A core is not one, so a
    marker standing behind nothing but a core is a leading marker and
    is not taken -- and the core, no longer the segment's only piece
    once the tail is read as written, is dropped as usual."""
    out = _grouped("Smith, John, - née Jones", policy=_DASH)
    assert not any(t.role is Role.MAIDEN for t in out.tokens)
    core = next(i for i, t in enumerate(out.tokens) if t.text == "-")
    assert core in out.dropped
    assert _piece_texts(out)[2] == ["née", "Jones"]


def test_no_join_reaches_a_taken_marker() -> None:
    """A marker the consumer takes is gone before any join looks, so
    there is no piece list on which a join could absorb it (#412).
    Pinned per shape the connective join reached the marker through;
    the particle chain on its own is pinned in
    test_where_the_marker_lands_when_the_consumer_declines."""
    # connective after the marker, behind a chain (#412's headline)
    assert _piece_texts(_grouped("Jane van der Berg née y Jones")) == [
        ["Jane", "van der Berg"]]
    # connective before the marker: 'Smith and' is what 'Jane Smith
    # and' alone reads too, so the odd-looking family is consistency,
    # not an artifact
    assert _piece_texts(_grouped("Jane Smith and née Jones")) == [
        ["Jane", "Smith and"]]
    # marker-headed: the connective is the first word the marker takes
    assert _piece_texts(_grouped("Jane née and Jones Smith")) == [
        ["Jane"]]


def test_the_bound_given_join_never_absorbs_a_marker() -> None:
    """P5 joins the bound word to "the word after it", and a maiden
    marker is not a name word -- it announces that another name
    follows.

    Joining one merged the marker into the given name and left M2
    nothing to find, which was the P5 half of the join-swallow #412
    records. With the marker pass ahead of the joins, a marker the
    consumer takes is gone before P5 looks, so the taken-marker rows
    below hold by construction. The guard's live shape is a DECLINED
    marker standing directly after the bound word with the reserve
    satisfied -- 'Berg, abdul née Jr', 'Berg, abdul née PhD', 'Berg,
    abdul née' -- where only the guard keeps the join from reading
    given 'abdul née'.

    Asserted at the piece level because the field reading can look
    perfectly ordinary while this is wrong: the shipped-vocabulary
    twin of the first case below read given 'abdul nee' with a
    plausible family name beside it.
    """
    for text in ("abdul née Jones",
                 "abdul née Jones Jr Berg Smith",
                 "abdul née",
                 "abdul née Jr",
                 "Berg, abdul née Jones",
                 "Berg, abdul née Jr"):
        out = _grouped(text)
        for seg, texts in zip(out.pieces, _piece_texts(out)):
            for piece, shown in zip(seg, texts):
                # Keyed on the piece carrying the BOUND word, not on
                # width. "no wide piece holds a marker" would be a
                # different and false claim -- the particle chain
                # builds exactly that, and the test above pins it
                # ("Jane van der Berg née" -> ['Jane',
                # 'van der Berg née']).
                if not _piece_has_tag(out, piece, "vocab:bound-given"):
                    continue
                assert not _piece_has_tag(
                    out, piece, "vocab:maiden-marker"), (
                        f"{text!r}: the join absorbed a marker into "
                        f"the piece {shown!r}")


_GIVEN_NAME_TITLE_LEX = dataclasses.replace(
    _LEX, titles=_LEX.titles | {"sir"},
    given_name_titles=frozenset({"sir"}))


def test_a_given_name_title_licenses_the_bound_join_with_one_word_to_spare() -> None:
    # rules.md#P5 (#369): a given-name title asserts that a given name
    # follows -- the same assertion H1 reads when it keeps "Sir John" a
    # given name -- so behind one the reserve is the post-comma one,
    # and two name words join where STRICT keeps the second back as
    # the family name.
    out = _grouped("sir abdul rahman", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["sir", "abdul rahman"]]


def test_a_plain_title_keeps_the_strict_reserve() -> None:
    # The licence is the given-name title's, not any title's: "mr"
    # addresses by family, so the second word is still the family
    # name the reserve exists to keep.
    out = _grouped("mr abdul rahman", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["mr", "abdul", "rahman"]]


def test_the_licence_still_needs_two_name_words() -> None:
    # A suffix is still no word to spare: LENIENT needs two name
    # words and "jr" is not one, exactly as after a family comma.
    # (The count is what this witnesses; the decline below, which
    # #421 will make general, fires on a different shape.)
    out = _grouped("sir abdul jr", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["sir", "abdul", "jr"]]


def test_the_title_run_is_read_as_h1_reads_it() -> None:
    # P5 and post_rules ask ONE predicate of the run
    # (_run_addresses_by_given), so they cannot disagree about what the
    # same run asserts: if P5 joined where H1 then read the joined
    # piece as the family name, one run would have two readings. The
    # run "mr sir" is #369's own example and it moved with #489 -- the
    # whole run is no entry, its LAST word is, so the run addresses by
    # given name and the licence fires.
    out = _grouped("mr sir abdul rahman", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["mr", "sir", "abdul rahman"]]


def test_the_licence_joins_a_word_not_a_particle_chain() -> None:
    # P5 joins "the word after it", and the licence lifts the reserve
    # for two WORDS. A particle chain is one piece but not one word --
    # it is the family name P2 built -- so behind a given-name title
    # the bound word must not absorb it: untitled, "abdul van der
    # Berg" keeps the chain as its family, and the title cannot make
    # the surname vanish. Found in review; the rules.md example carries
    # the shape into the rules corpus, so the gate witnesses it too.
    out = _grouped("sir abdul van der Berg", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["sir", "abdul", "van der Berg"]]


def test_the_licence_takes_a_name_word_not_a_suffix() -> None:
    # P5 joins "the word after it", and a suffix is not a name word.
    # The lowered reserve must not open to titled names the
    # absorb-a-suffix shape #421 records for the post-comma LENIENT
    # path: "abdul Jr rahman" keeps 'Jr' out of the given name behind
    # a plain title, and a given-name title cannot change that. (#421
    # will make the decline general; until then it is the licence's.)
    out = _grouped("sir abdul jr rahman", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["sir", "abdul", "jr", "rahman"]]


def test_a_conjunction_joined_title_run_is_keyed_over_every_token_of_the_piece(
) -> None:
    # A conjunction-merged title is one multi-token PIECE. The key is
    # built from every token of every title piece, as post_rules
    # builds it from every title token; keyed on first tokens alone,
    # "sir and mrs" would read as "sir", the join would fire, and H1
    # would then read the joined pair as the family.
    out = _grouped("sir and mrs abdul rahman", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["sir and mrs", "abdul", "rahman"]]


def test_the_licence_still_declines_a_lone_marker() -> None:
    # The lowered reserve changes the count, not what the join may
    # take: a marker the consumer declined (nothing after it) is no
    # name word behind a given-name title either, as after a comma.
    out = _grouped("sir abdul née", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["sir", "abdul", "née"]]


# -- #401 / #421: the reserve and the join agree about what a name word is


def test_the_reserve_counts_a_trailing_numeral_as_the_suffix_assign_reads() -> None:
    # rules.md#P5 says the reserve "needs a name word to spare". A bare
    # 'V' carries both vocab:suffix and the initial tag, so the
    # suffix-piece test vetoes it -- right for assign's middle-initial
    # question, wrong here: assign reads a FINAL roman numeral after a
    # non-initial piece as the suffix (S2's fork), so the family the
    # reserve believed it was sparing was never there. 'abdul Smith V'
    # read given 'abdul Smith', family '' (#401).
    out = _grouped("abdul Smith V")
    assert _piece_texts(out) == [["abdul", "Smith", "V"]]


def test_a_numeral_that_is_not_last_is_a_name_word() -> None:
    # The mirror is exact: assign's fork takes only the LAST piece, so
    # a numeral with a suffix behind it is a middle initial to assign
    # and a name word to the reserve -- 'abdul Smith V jr' joins, and
    # the family assign then reads is 'V', not nothing.
    out = _grouped("abdul Smith V jr")
    assert _piece_texts(out) == [["abdul Smith", "V", "jr"]]


def test_the_numeral_is_read_after_a_suffix_word_that_is_also_a_title() -> None:
    # assign's fork asks only that the numeral not be the first NAME
    # piece; 'jr' is title vocabulary as well as a suffix, so a guard
    # phrased as "the piece before it is not a title" loses the
    # family again: 'abdul Smith jr V' read given 'abdul Smith',
    # suffix 'jr, V'. Found by the design-docs review. The shipped
    # vocabulary has jr in TITLES; the test lexicon gets the same.
    out = _grouped("abdul Smith jr V", lexicon=_LEX.add(titles={"jr"}))
    assert _piece_texts(out) == [["abdul", "Smith", "jr", "V"]]


def test_the_reserve_reads_the_numeral_as_the_join_would_leave_it() -> None:
    # assign tests the piece before the numeral AFTER the join, whose
    # first token is the bound word; the reserve must look at the
    # same layout, or an initial-shaped second word suppresses the
    # fork for the reserve alone: 'abdul J. V' read given 'abdul J.',
    # family ''. The reserve now declines, and assign, seeing the
    # unjoined pieces, reads the V as the family -- exactly as it
    # reads 'John J. V' (pinned at the field level in test_parser).
    out = _grouped("abdul J. V")
    assert _piece_texts(out) == [["abdul", "J.", "V"]]


def test_the_numeral_is_last_among_the_pieces_assign_keeps() -> None:
    # assign drops a group-flagged credential piece (the Ph. D. merge)
    # from its walk at ANY position before the trailing peel, so a
    # numeral can be last in that walk without being the last piece:
    # 'abdul Smith V Ph. D.' read given 'abdul Smith', family '',
    # suffix 'V, Ph. D.' where 'John Smith V Ph. D.' keeps family
    # 'Smith'. Found by the code review.
    out = _grouped("abdul Smith V Ph. D.")
    assert _piece_texts(out) == [["abdul", "Smith", "V", "Ph. D."]]


def test_the_numeral_fork_is_not_mirrored_after_a_family_comma() -> None:
    # The post-comma walk has no roman-numeral fork -- assign reads a
    # trailing 'V' there by a lenient last-of-two rule, and as a middle
    # initial with a third part -- so the LENIENT reserve counts suffix
    # pieces only, as it always did: 'Berg, abdul V' keeps given
    # 'abdul V' at every baseline, and so does 'Berg, abdul V, jr'.
    # Found by the code review; a mirror of the main walk's fork here
    # declined both with nothing classifying the change.
    out = _grouped("Berg, abdul V")
    assert _piece_texts(out) == [["Berg"], ["abdul V"]]
    out = _grouped("Berg, abdul V, jr")
    assert _piece_texts(out) == [["Berg"], ["abdul V"], ["jr"]]


def test_the_join_never_absorbs_a_suffix_piece() -> None:
    # rules.md#P5 says the join takes "the word after it"; a suffix is
    # not a name word -- the same decline the join already makes for a
    # marker. The reserve counted only non-suffix pieces, so 'abdul jr
    # Jones' declined, but with a word to spare the join took the
    # suffix as the word: 'abdul jr Smith Berg' read given 'abdul jr'
    # (#421; 1.4.0 parity, not a regression).
    out = _grouped("abdul jr Smith Berg")
    assert _piece_texts(out) == [["abdul", "jr", "Smith", "Berg"]]


def test_the_join_never_absorbs_a_split_credential() -> None:
    # The worse half of #421, a 2.0 regression: merge() unions piece
    # tags, so joining onto the 'Ph. D.' piece made the joined piece a
    # SUFFIX piece and assign routed the bound word to the suffix
    # field -- 'abdul Ph. D. Smith Berg' read suffix 'abdul Ph. D.'.
    # The credential piece carries the suffix ptag, which is the first
    # thing the suffix-piece test asks.
    out = _grouped("abdul Ph. D. Smith Berg")
    assert _piece_texts(out) == [["abdul", "Ph. D.", "Smith", "Berg"]]
    assert "suffix" not in out.piece_tags[0][0]


def test_the_join_declines_a_suffix_after_a_family_comma_too() -> None:
    # The post-comma LENIENT reserve is the path decisions.md#P5 first
    # recorded the absorb-a-suffix shape on ('Berg, abdul jr Smith'
    # read given 'abdul jr'); the decline is the join's, so it holds
    # under every reserve.
    out = _grouped("Berg, abdul jr Smith")
    assert _piece_texts(out) == [["Berg"], ["abdul", "jr", "Smith"]]


# -- #425: the reserve runs assign's peel over the post-join view

_AMBIGUOUS_LEX = _LEX.add(suffix_acronyms={"ma"},
                          suffix_acronyms_ambiguous={"ma"})


def test_the_reserve_mirrors_the_bare_acronym_fork() -> None:
    # S2's other positional fork: a bare ambiguous acronym is peeled
    # only with a given AND a family left. Read over the joined view
    # 'abdul Smith Jr Ma' is three pieces, so assign peels the acronym,
    # then the suffix, and one piece remains -- no family. The reserve
    # now runs that same peel over the view and declines (#425); it
    # used to count 'Ma' as a name word and join.
    #
    # MOVED by #289, not deleted: 'Ma' is Title-case in a mixed-case
    # name, so it leans SURNAME and the peel declines it even with
    # words to spare -- the walk stops at the declined pick, 'jr'
    # never reached behind it, so the reserve now sees the SAME
    # suffixes on both sides of the join (none) and the join stands
    # (the accepted cost decisions.md#S2 records for
    # 'abdul Smith Jr Ma').
    out = _grouped("abdul Smith jr Ma", lexicon=_AMBIGUOUS_LEX)
    assert _piece_texts(out) == [["abdul Smith", "jr", "Ma"]]


def test_the_join_never_turns_a_suffix_into_a_name() -> None:
    # Unjoined, 'abdul Smith Ma' has words to spare and the peel reads
    # the acronym as a credential; joined, the view is two pieces and
    # the fork would keep it as the family. The join joins two name
    # words and changes nothing else, so it declines -- 1.4.0's
    # reading, and 'John Smith Ma's. With a family behind it the
    # acronym peels either way, and the join stands.
    #
    # MOVED by #289, not deleted: 'Ma' now leans SURNAME (Title case,
    # mixed-case name) on BOTH sides of the join, so the two views'
    # suffix readings still agree and the join stands -- 'abdul Smith'
    # given, 'Ma' family (decisions.md#S2's corpus row).
    out = _grouped("abdul Smith Ma", lexicon=_AMBIGUOUS_LEX)
    assert _piece_texts(out) == [["abdul Smith", "Ma"]]
    out = _grouped("abdul Smith Berg Ma", lexicon=_AMBIGUOUS_LEX)
    assert _piece_texts(out) == [["abdul Smith", "Berg", "Ma"]]


def test_the_join_never_turns_a_name_into_a_suffix_either() -> None:
    # The same rule from the other side: 'abdul V' is two pieces
    # whose V the peel reads as the suffix; joined it would be one
    # piece the fork cannot fire on, so the V would become a name
    # word. The peel takes the V unjoined and nothing joined -- the
    # join declines. (Of the numeral pins above, 'abdul J. V'
    # declines by this comparison; 'abdul Smith V' by the threshold,
    # one name word being no family to spare.)
    out = _grouped("abdul V")
    assert _piece_texts(out) == [["abdul", "V"]]


def test_the_joined_pair_is_a_given_name_whatever_tag_the_word_carried() -> None:
    # A title word standing in the name is a name word (H3) and the
    # join takes it as v1 did -- but the conjunction merge derives a
    # `title` piece tag for "mr and mrs", and merge()'s tag union
    # would hand that tag to the joined pair, which assign then peels
    # as a leading title: 'abdul Sheikh and Ahmad Bakar Smith' read
    # title 'abdul Sheikh and Ahmad' on 2.0 and 2.1, and the shorter
    # 'abdul Sheikh and Ahmad Bakar' would have too once the count's
    # title exclusion went. The bound join drops the tag: the pair is
    # a given name. Found by the code review.
    out = _grouped("abdul mr and mrs Smith Berg")
    assert _piece_texts(out) == [["abdul mr and mrs", "Smith", "Berg"]]
    assert "title" not in out.piece_tags[0][0]


def test_a_title_word_in_the_name_is_a_name_word_to_the_join() -> None:
    # The 2.x reserve had excluded title pieces from its count, an
    # unrecorded deviation from v1, which joined them; assign reads a
    # mid-name title word as a name word, and the shared peel follows
    # assign. 1.4.0 parity on every shape here.
    out = _grouped("abdul mr Smith Berg")
    assert _piece_texts(out) == [["abdul mr", "Smith", "Berg"]]
    out = _grouped("abdul Smith mr")
    assert _piece_texts(out) == [["abdul Smith", "mr"]]
    out = _grouped("Berg, abdul mr")
    assert _piece_texts(out) == [["Berg"], ["abdul mr"]]


def test_the_licence_does_not_lift_the_equality() -> None:
    # The one shape where the join would move the numeral fork AND
    # the licence's threshold of one would let it through: 'sir abdul
    # J. V' -- unjoined the V is a name word (the fork is suppressed
    # by the initial-shaped 'J.'), joined it is the suffix: the peel
    # takes nothing unjoined and the V joined. Declines, as 'Sir John
    # J. V' reads. A looser comparison passed every other test; found
    # by the test review.
    out = _grouped("sir abdul J. V", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["sir", "abdul", "J.", "V"]]


# -- #424: the chain and the maiden walk stop where assign's peel begins


def test_the_chain_stops_before_the_numeral_assign_reads_as_the_suffix() -> None:
    # P2's chain ran "until a trailing suffix begins" and asked with
    # the suffix-piece test, which vetoes a bare 'V' as an initial --
    # the #401 question at a third site: 'John van der Berg V' read
    # family 'van der Berg V'. The chain now stops where the S2 peel,
    # read over the pieces as they stand, begins the trailing run.
    out = _grouped("John van der Berg V")
    assert _piece_texts(out) == [["John", "van der Berg", "V"]]
    # the stop is kept as a length from the end, so a second chain
    # ahead of it stops there too (the test review's surviving mutant)
    out = _grouped("John van der Berg de la Vega V")
    assert _piece_texts(out) == [
        ["John", "van der Berg", "de la Vega", "V"]]
    out = _grouped("John van der Berg jr")
    assert _piece_texts(out) == [["John", "van der Berg", "jr"]]


def test_the_chain_keeps_an_acronym_assign_will_not_peel() -> None:
    # Behind a word in both the title and particle vocabularies the
    # leading-particle scan stops (P4, #367) before assign's title
    # peel does, so the chain takes the name's first word: read over
    # the pieces as they stand the acronym has three pieces to spare,
    # read over the pieces the chain leaves it has two, and assign
    # would make it the family ('Freiherr von Berg Ma' read given 'von
    # Berg', family 'Ma' -- 1.4.0's reading, and the reviews' find).
    # The chain asks the peel again over what it leaves, and takes the
    # acronym assign will not peel.
    lex = _AMBIGUOUS_LEX.add(titles={"st"}, particles={"st"})
    out = _grouped("St van Berg Ma", lexicon=lex)
    assert _piece_texts(out) == [["St", "van Berg Ma"]]
    # MOVED by #289, not deleted: with a given word of its own the
    # three pieces used to survive the chain (words to spare read 'Ma'
    # as a credential); now 'Ma' leans SURNAME (Title case, mixed-case
    # name) and the peel declines it regardless of the count, so the
    # second re-ask absorbs it into the particle run too
    # (decisions.md#S2).
    out = _grouped("St John van Berg Ma", lexicon=lex)
    assert _piece_texts(out) == [["St", "John", "van Berg Ma"]]


def test_the_chain_keeps_a_numeral_the_peel_does_not_take() -> None:
    # The fork is assign's: a numeral after an initial-shaped piece is
    # a name word, so the chain takes it as before -- as 'John J. V'
    # reads the V as a name. And a numeral with a suffix behind it is
    # not last in the walk.
    out = _grouped("John van der J. V")
    assert _piece_texts(out) == [["John", "van der J. V"]]
    out = _grouped("John van der Berg V jr")
    assert _piece_texts(out) == [["John", "van der Berg V", "jr"]]


def test_the_chain_stops_before_a_bare_acronym_with_words_to_spare() -> None:
    # S2's other fork, the same way: 'John Smith Ma' peels the acronym
    # as a credential, so 'John van der Berg Ma' does too -- 1.4.0 read
    # suffix 'Ma' there, and 2.0 had let the chain take it.
    #
    # MOVED by #289, not deleted: 'Ma' is Title-case in a mixed-case
    # name, so it now leans SURNAME and the chain's re-ask no longer
    # stops before it -- 'Ma' joins the particle run instead
    # (decisions.md#S2's corpus row).
    out = _grouped("John van der Berg Ma", lexicon=_AMBIGUOUS_LEX)
    assert _piece_texts(out) == [["John", "van der Berg Ma"]]


def test_the_maiden_walk_stops_before_the_numeral_too() -> None:
    # M2's walk takes the words after the marker "up to any trailing
    # suffix", asked with the same test: 'John née Jones Smith V' took
    # the V into the maiden name. Read by the peel from the marker on,
    # the V is the suffix, and the walk stops before it.
    out = _grouped("John née Jones Smith V")
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Smith"]
    assert _piece_texts(out) == [["John", "V"]]


def test_the_maiden_walk_keeps_the_acronym_its_writing_declines(
) -> None:
    # The walk asks the acronym fork the way it asks the numeral one
    # (#533): the peel over the pieces as they stand, then again over
    # the name the take would leave. 'Ma' is Title case in a
    # mixed-case name, so the peel declines it either way and the
    # clause keeps it -- the same answer this test pinned when the
    # fork was left to assign, for a different reason. The WRITING
    # keeps the word, not the count.
    out = _grouped("John née Jones Smith Ma", lexicon=_AMBIGUOUS_LEX)
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Smith", "Ma"]
    # and the capitals go the other way, which is what makes the row
    # above a reading rather than a floor
    out = _grouped("John née Jones Smith MA", lexicon=_AMBIGUOUS_LEX)
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Smith"]
    # The numeral half is untouched: the acronym BETWEEN the maiden
    # name and the numeral still declines, and the walk still stops at
    # the numeral fork (the test review's surviving mutant).
    out = _grouped("Jane Smith née Jones Ma V", lexicon=_AMBIGUOUS_LEX)
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Ma"]


# -- #533: the acronym fork, the reader, the clamp and the emitter

def _maiden_texts(state: ParseState) -> list[str]:
    return [t.text for t in state.tokens if t.role is Role.MAIDEN]


def _suffix_forks(state: ParseState) -> list[str]:
    return [a.detail for a in state.ambiguities
            if a.kind is AmbiguityKind.SUFFIX_OR_NAME]


def test_the_clause_stops_before_a_credential_the_reader_takes(
) -> None:
    out = _grouped("Jane Doe née Smith MA", lexicon=_AMBIGUOUS_LEX)
    assert _maiden_texts(out) == ["Smith"]


def test_the_clause_never_gives_up_the_first_word_after_the_marker(
) -> None:
    """Option 1's floor, as a CLAMP. A member standing alone after the
    marker stays the maiden name; where the peel consumed that word
    AND words behind it, only the first stays -- a veto that cancelled
    the stop outright handed the words behind it back to the clause
    too."""
    out = _grouped("Jane Doe née MA", lexicon=_AMBIGUOUS_LEX)
    assert _maiden_texts(out) == ["MA"]
    out = _grouped("Doe, J. née MA ba",
                   lexicon=_AMBIGUOUS_LEX.add(
                       suffix_acronyms={"ba"},
                       suffix_acronyms_ambiguous={"ba"}))
    assert _maiden_texts(out) == ["MA"]


def test_the_clamped_stop_may_land_on_no_member_and_declines() -> None:
    """The clamp can move the stop onto a piece that is no class
    member at all, and then the test declines and nothing changes --
    the walk stopping at that suffix word of its own accord."""
    out = _grouped("Jane Doe née MA Jr", lexicon=_AMBIGUOUS_LEX)
    assert _maiden_texts(out) == ["MA"]


def test_the_view_check_asks_about_the_member_and_not_about_the_run(
) -> None:
    """The take would leave 'JOHN MA PHD', whose peel takes 'PHD' and
    then declines 'MA' for want of words to spare. A check asking
    whether the reader takes SOMETHING answers yes there, and the
    member becomes the FAMILY name."""
    # NOTE the accented marker: this module's `_LEX` ships
    # maiden_markers={"née", "geb"} and NOT the unaccented "nee", so
    # the plain spelling takes nothing at all here and the test would
    # pass vacuously. cases.py's row of the same shape uses the
    # DEFAULT vocabulary, where both spellings are markers.
    lex = _AMBIGUOUS_LEX.add(suffix_acronyms={"phd"})
    out = _grouped("JOHN NÉE JONES SMITH MA PHD", lexicon=lex)
    assert _maiden_texts(out) == ["JONES", "SMITH", "MA"]
    assert len(_suffix_forks(out)) == 1


def test_the_reader_is_none_in_the_family_segment() -> None:
    """Segment 0 of a family comma: the comma has already named the
    family, so no trailing rule reads those words and the clause keeps
    them -- and nothing reports, nothing having been decided."""
    out = _grouped("Smith née Jones MA, Jane", lexicon=_AMBIGUOUS_LEX)
    assert _maiden_texts(out) == ["Jones", "MA"]
    assert _suffix_forks(out) == []


def test_the_reader_is_none_in_a_third_comma_part() -> None:
    """A segment past the second comma is read as credentials whole,
    so no trailing rule is consulted there either."""
    out = _grouped("Smith, John, Jr née Jones MA",
                   lexicon=_AMBIGUOUS_LEX.add(suffix_words={"jr"}))
    assert _maiden_texts(out) == ["Jones", "MA"]
    assert _suffix_forks(out) == []


def test_the_emitter_fires_on_the_last_maiden_piece_and_only_there(
) -> None:
    """The word the trailing rule was asked about is the LAST piece of
    the maiden name: everything behind it read as a suffix, which is
    what let the peel reach it. A member with a name word behind it
    was never asked."""
    out = _grouped("Jane Doe née Smith Ma", lexicon=_AMBIGUOUS_LEX)
    assert _suffix_forks(out) == [
        "'Ma' ending the maiden name is also a post-nominal; the "
        "maiden marker's clause keeps it rather than reading it as one"]
    out = _grouped("Jane Doe née MA Smith", lexicon=_AMBIGUOUS_LEX)
    assert _suffix_forks(out) == []


def test_the_emitter_reports_a_by_shape_member_too() -> None:
    """The emitter's gate reads EITHER tag, as the chain emitter's
    does, so a member admitted by SHAPE reports even where the class
    does not admit it and the peel declined to consume it -- it
    records the word in `picks` and breaks, so the walk's own reading
    gate is never asked about it (measured 2026-09-19)."""
    out = _grouped("John Smith née Jones R.A.I.",
                   policy=Policy(unlisted_dotted_suffixes=False))
    assert _maiden_texts(out) == ["Jones", "R.A.I."]
    assert len(_suffix_forks(out)) == 1


def test_the_maiden_report_survives_the_family_comma_suppression(
) -> None:
    """group() passes `None` for the chain emitter, deliberately --
    the comma fixed the family. The maiden fork is not that fork, so
    it travels on its own channel and reports after a comma too."""
    out = _grouped("Doe, Jane née Smith Ma", lexicon=_AMBIGUOUS_LEX)
    assert _maiden_texts(out) == ["Smith", "Ma"]
    assert len(_suffix_forks(out)) == 1


def test_the_two_ambiguity_channels_route_independently() -> None:
    """Both channels are REQUIRED arguments, and they are two so that
    silencing one never silences the other.

    `reader` and `maiden_ambiguities` have no defaults: the one
    production caller answers both off the segment's structure, and a
    default would be this module guessing what that caller knows. The
    routing is what the split buys -- the same list in both slots is
    one channel, two lists are two, and #533's review found the
    earlier spelling defaulting the maiden channel to whatever the
    first was, so `ambiguities=None` silenced both.
    """
    state = classify(segment(tokenize(extract_delimited(ParseState(
        original="Jane Doe née Smith Ma", lexicon=_AMBIGUOUS_LEX,
        policy=Policy())))))
    general: list[PendingAmbiguity] = []
    maiden: list[PendingAmbiguity] = []
    _group_segment(state.segments[0], 0, state.tokens,
                   ambiguities=general, one_case=state.one_case,
                   reader=TailReader.TRAILING,
                   maiden_ambiguities=maiden)
    assert [a.kind for a in maiden] == [AmbiguityKind.SUFFIX_OR_NAME]
    assert general == []
    # the general channel suppressed, the maiden one still speaks --
    # which is exactly what group() does after a family comma
    only_maiden: list[PendingAmbiguity] = []
    _group_segment(state.segments[0], 0, state.tokens,
                   ambiguities=None, one_case=state.one_case,
                   reader=TailReader.TRAILING,
                   maiden_ambiguities=only_maiden)
    assert [a.kind for a in only_maiden] == [AmbiguityKind.SUFFIX_OR_NAME]
    # and NONE is the reader that silences the maiden channel itself,
    # because nothing was decided there
    silent: list[PendingAmbiguity] = []
    _group_segment(state.segments[0], 0, state.tokens,
                   ambiguities=None, one_case=state.one_case,
                   reader=TailReader.NONE, maiden_ambiguities=silent)
    assert silent == []


def test_an_unmapped_reader_is_a_loud_failure_rather_than_a_default(
) -> None:
    """The exhaustive dispatch, exercised.

    `_maiden_take` ends its reader branch with `assert_never`, which
    makes a fourth `TailReader` member a mypy error at this site
    rather than a silent fall-through to one of the three readings.
    At RUNTIME that line is unreachable by construction, so it is
    reached here the only way it can be -- with a value outside the
    enum -- both to pin the loudness and to keep the line from being
    the one uncovered statement in the module.
    """
    state = classify(segment(tokenize(extract_delimited(ParseState(
        original="Jane Doe née Smith MA", lexicon=Lexicon.default(),
        policy=Policy())))))
    with pytest.raises(AssertionError):
        _group_segment(state.segments[0], 0, state.tokens,
                       ambiguities=[], one_case=state.one_case,
                       reader=cast(TailReader, 99),
                       maiden_ambiguities=[])


def test_the_reader_is_pinned_to_the_structure_it_is_read_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`TailReader` is a closed set, and group() maps (structure,
    segment index) onto it in one place. Pinned here by WATCHING that
    mapping rather than restating it -- a restatement passes when the
    code changes under it, which is the shape of vacuous guard
    AGENTS.md warns about. `_maiden_take` dispatches on the enum
    exhaustively (`assert_never`), so a fourth member with no row
    here is a type error rather than a silent default.
    """
    assert len(TailReader) == 3
    want = {
        # no comma: the whole name, read by the S2 peel
        (Structure.NO_COMMA, 0): TailReader.TRAILING,
        # suffix comma: segment 0 is the name, the rest is the
        # credential run and is read whole
        (Structure.SUFFIX_COMMA, 0): TailReader.TRAILING,
        (Structure.SUFFIX_COMMA, 1): TailReader.NONE,
        (Structure.SUFFIX_COMMA, 2): TailReader.NONE,
        # family comma: segment 0 is the family the comma named,
        # segment 1 is the given part with its own trailing slot
        # (#531), and a third part is a credential run again
        (Structure.FAMILY_COMMA, 0): TailReader.NONE,
        (Structure.FAMILY_COMMA, 1): TailReader.GIVEN_SLOT,
        (Structure.FAMILY_COMMA, 2): TailReader.NONE,
    }
    texts = ("Jane Doe née Smith MA",
             "Jane Doe née Smith, MD, PhD",
             "Doe, Jane née Smith MA, MD")
    seen: dict[tuple[Structure, int], TailReader] = {}
    real = _group_module._group_segment

    def spy(seg: tuple[int, ...], additional: int,
            tokens: Sequence[WorkToken], *args: object,
            **kwargs: object) -> object:
        seen[(state.structure, len(seen_order))] = cast(
            TailReader, kwargs["reader"])
        seen_order.append(seg)
        return real(seg, additional, tokens, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(_group_module, "_group_segment", spy)
    for text in texts:
        seen_order: list[tuple[int, ...]] = []
        state = classify(segment(tokenize(extract_delimited(ParseState(
            original=text, lexicon=Lexicon.default(),
            policy=Policy())))))
        group(state)
    assert seen == want, (
        f"group() maps the structures to {seen}, pinned as {want}")


def test_a_marker_followed_only_by_the_numeral_is_just_a_word() -> None:
    # The peel is read from the marker, so 'née V' is two pieces and
    # the fork fires on the V: nothing follows the marker but a
    # suffix, the pass declines, and the marker stays a word -- as
    # for 'Jane Smith née PhD', and as 1.4.0 read it (suffix 'V').
    out = _grouped("Jane Smith née V")
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == []
    assert _piece_texts(out) == [["Jane", "Smith", "née", "V"]]


def test_the_walk_stops_only_where_the_numeral_survives_the_take() -> None:
    # The fork reads the piece before the numeral, and the walk
    # REMOVES that piece: after the take, what assign sees before the
    # V is the piece before the marker. Where that is initial-shaped
    # the fork will not fire, and a walk that stopped anyway handed
    # the V to the family ('J. née Jones Smith V' read family 'V').
    # So the walk stops only where the numeral reads as the suffix
    # both as written and as the take would leave it. Found by both
    # reviews.
    out = _grouped("J. née Jones Smith V")
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Smith", "V"]
    # and it is the whole peel that is re-asked, not one condition of
    # it: a title before the marker is peeled by assign first, leaving
    # the numeral as the whole rest, where no fork fires (the code
    # review found the first re-ask handing the V to the given name)
    out = _grouped("Dr. née Jones Smith V")
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Smith", "V"]


def test_an_unlisted_abbreviation_is_as_transparent_as_a_title() -> None:
    # #367 keyed the leading-particle exception on the first piece of
    # the NAME, stepping over titles; assign also peels an unlisted
    # abbreviation as a title (H2), and the scan here did not, so
    # 'Xyz. van Johnson' chained where 'Dr. van Johnson' did not --
    # and 'Xyz. van Berg Ma' chained the given word into the family,
    # leaving assign two pieces where the acronym fork had counted
    # three. The scan asks assign's leading-title test now.
    out = _grouped("Xyz. van Johnson")
    assert _piece_texts(out) == [["Xyz.", "van", "Johnson"]]
    out = _grouped("Xyz. van Berg Ma", lexicon=_AMBIGUOUS_LEX)
    assert _piece_texts(out) == [["Xyz.", "van", "Berg", "Ma"]]
    # and the bound join's "first non-title piece" is the same count,
    # so a bound word behind an unlisted abbreviation joins as it does
    # behind a listed title (the design-docs review's find)
    out = _grouped("Xyz. abdul John Smith")
    assert _piece_texts(out) == [["Xyz.", "abdul John", "Smith"]]
    out = _grouped("Berg, Xyz. abdul van")
    assert _piece_texts(out)[1] == ["Xyz.", "abdul van"]


# -- the marker sites' cross-site contract --------------------------

# A maiden marker is asked about at FOUR sites, and _title_key's
# docstring names what a divergence between two of them costs: "a
# divergence between them fails silently: the entry simply stops
# matching". This lexicon carries a word entry, a phrase entry, and a
# phrase whose FIRST WORD is itself an entry -- the longest-first case,
# where a site that stopped at the first word would still find a
# marker and simply find a shorter one.
_MARKER_LEX = Lexicon(
    maiden_markers=frozenset({"née", "z domu", "geb", "geb von"}))


def _marker_sites(spelling: str) -> dict[str, int]:
    """Every site's answer to "how many words is the marker here", for
    a name whose marker is written `spelling`."""
    clause = spelling.split() + ["Jones"]
    answers = {"predicate": maiden_marker_run(clause,
                                              _MARKER_LEX.maiden_markers)}

    def staged(text: str) -> ParseState:
        return classify(segment(tokenize(extract_delimited(ParseState(
            original=text, lexicon=_MARKER_LEX, policy=Policy())))))

    # classify: the run it tagged, head plus continuations
    bare = staged(f"Jane Smith {spelling} Jones")
    head = next(i for i, t in enumerate(bare.tokens)
                if "vocab:maiden-marker" in t.tags)
    answers["classify"] = marker_run_length(
        t.tags for t in bare.tokens[head + 1:])
    # group's piece test and the M2 take built on it: the pass drops
    # the marker and nothing else, so the count of dropped tokens is
    # where that walk decided the marker ends
    answers["group piece walk"] = len(group(bare).dropped)
    # group's OTHER drop, the one inside an extracted clause (#329) --
    # a separate site reached only through a delimited name
    answers["group clause drop"] = len(
        group(staged(f"Jane Smith ({spelling} Jones)")).dropped)
    # extract's clause test, which is a boolean: a clause is marker-led
    # exactly while a word remains past the run, so the LONGEST prefix
    # it still declines is the run itself. Read this way rather than as
    # "the first prefix it accepts", which would answer 1 for every
    # phrase whose first word is also an entry.
    answers["extract"] = max(
        k for k in range(len(clause) + 1)
        if not _maiden_marked(" ".join(clause[:k]), _MARKER_LEX))
    return answers


@pytest.mark.parametrize("spelling", [
    "née", "Née", "née.",                    # a word entry
    "z domu", "Z Domu", "z. domu", "z domu.",  # a phrase entry
    "geb", "geb von",                        # both, longest first
])
def test_every_marker_site_ends_the_run_in_the_same_place(
        spelling: str) -> None:
    # The contract is AGREEMENT, not four expected numbers: a site that
    # drifted would keep passing its own tests while disagreeing with
    # the others about an input neither covers, which is exactly how
    # the title-run key's two builders could have gone wrong (#369) and
    # why P5 and H1 have a contract test of their own.
    #
    # This test varies the marker's SPELLING and holds its PLACEMENT
    # fixed, so every run it builds is structurally contiguous by
    # construction. That was a hole: the sites can also disagree
    # because they walk different token populations, which no spelling
    # reaches. test_a_tagged_marker_run_is_contiguous_and_drops_whole
    # below is the placement axis, added after a real disagreement got
    # through here.
    answers = _marker_sites(spelling)
    assert len(set(answers.values())) == 1, answers
    # never vacuous: the parametrization's own precondition is that
    # each spelling is WHOLLY a marker, so the agreed answer is its
    # word count -- an all-zero agreement would otherwise pass
    assert answers["predicate"] == len(spelling.split())


# Placements, not spellings: the axis the test above does not vary. A
# marker run is tagged over the whole span-sorted token stream and
# consumed over one SEGMENT, and the two populations differ -- extract
# gives a delimited clause's tokens a role and _segment.py:31 keeps
# only role-None tokens, then buckets those by the commas before them.
# So a run written across a clause edge or a structure comma is one the
# piece walk cannot see whole. Every row here writes 'z domu' at a
# different place relative to those boundaries.
_MARKER_PLACEMENTS = [
    "Jane Smith z domu Jones",          # contiguous, bare
    "Jane Smith (z domu Jones)",        # contiguous, wholly inside a clause
    'Jane Smith "z domu Jones"',        # the same, in the other default pair
    "Jane z (domu) Jones",              # straddles a clause OPEN
    "Jane Smith (z) domu Jones",        # straddles a clause CLOSE
    "Jane z, domu Jones",               # straddles a structure comma
    "Jane Smith née Jones",             # the one-word control
    "Jane Smith (née Jones)",           # the one-word control, delimited
]


def _tagged_runs(state: ParseState) -> list[list[int]]:
    """Every maiden marker run classify tagged, as token indices."""
    runs = []
    for i, token in enumerate(state.tokens):
        if "vocab:maiden-marker" not in token.tags:
            continue
        length = marker_run_length(t.tags for t in state.tokens[i + 1:])
        runs.append(list(range(i, i + length)))
    return runs


@pytest.mark.parametrize("text", _MARKER_PLACEMENTS)
def test_a_tagged_marker_run_is_contiguous_and_drops_whole(text: str) -> None:
    state = ParseState(original=text, lexicon=_MARKER_LEX, policy=Policy())
    classified = classify(segment(tokenize(extract_delimited(state))))
    runs = _tagged_runs(classified)
    commas = classified.comma_offsets

    def bucket(i: int) -> int:
        return bisect.bisect_left(commas, classified.tokens[i].span.start)

    # 1. What classify tags is what a segment can hold: one role and one
    # comma bucket throughout. _group._marker_run_pieces asserts this in
    # prose and depends on it in fact -- with a run allowed to straddle,
    # its walk stops at the boundary and hands M2 a proper PREFIX of the
    # phrase as if it were the whole marker, which is how
    # 'Anna z (domu) Nowak' came to read family 'Anna', maiden 'Nowak'.
    for run in runs:
        roles = {classified.tokens[i].role for i in run}
        assert len(roles) == 1, (text, run, roles)
        assert len({bucket(i) for i in run}) == 1, (text, run)

    # 2. And the consumer takes the whole run or declines it. A count
    # that disagrees with the tagged length is the cross-site
    # disagreement itself, whatever produced it.
    dropped = set(group(classified).dropped)
    for run in runs:
        taken = dropped & set(run)
        assert taken in (set(), set(run)), (text, run, sorted(taken))


def test_the_marker_placements_reach_both_answers() -> None:
    # Neither half of the pin above is vacuous: some placements must
    # tag a run (or the contiguity assertion quantifies over nothing)
    # and some must tag none (or the straddling rows have stopped
    # straddling and the regression they pin is unwatched).
    tagged = {}
    for text in _MARKER_PLACEMENTS:
        state = ParseState(original=text, lexicon=_MARKER_LEX, policy=Policy())
        runs = _tagged_runs(classify(segment(tokenize(
            extract_delimited(state)))))
        tagged[text] = bool(runs)
    assert sum(tagged.values()) >= 4
    assert sum(not v for v in tagged.values()) >= 3


# --- #397: the carve-out's count, and the both-sides condition ------
# _LEX ships no single letter that is BOTH connective and generational
# vocabulary, so each test below builds the overlap it is about. That
# is the point of the rule -- it is keyed on the CLASS, never on the
# letter -- and a test using the shipped sets would walk the right
# branch while proving nothing about it (AGENTS.md: "Pin the decision,
# not the vocabulary").
_LINK_LEX = _LEX.add(conjunctions={"i"}, suffix_words={"i"})
#: the same letter as a connective that is NOT generational vocabulary
_PLAIN_LEX = _LEX.add(conjunctions={"i"})


def test_a_connective_piece_counts_toward_the_carve_outs_total() -> None:
    # rules.md#P3's count (#397). Four words, one of them the link,
    # and the link is suffix vocabulary -- so the total reaches four
    # only because a connective counts ITSELF. Without the count arm
    # the total is three, the carve-out declines, and the link stays
    # a name word in the middle.
    out = _grouped("Josep Carod i Rovira", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Josep", "Carod i Rovira"]]


def test_the_count_arm_is_what_moves_it_not_the_vocabulary() -> None:
    # the control that separates the two halves of commit 1: with the
    # letter a connective but NOT generational vocabulary, nothing
    # refused it before and the join already fired. Same output, and
    # the pair is what says the count arm is about the overlap.
    out = _grouped("Josep Carod i Rovira", lexicon=_PLAIN_LEX)
    assert _piece_texts(out) == [["Josep", "Carod i Rovira"]]


def test_a_connective_with_nothing_to_its_right_does_not_join() -> None:
    # the both-sides condition (#397). Four name words, so the count
    # no longer declines -- what keeps the generation here is the
    # condition, and dropping it reads 'Smith i' as one piece. The
    # simplest shape of it: there is no piece to the right at all.
    out = _grouped("John Quincy Smith i", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["John", "Quincy", "Smith", "i"]]


# The condition asks about the NEIGHBOUR's class, and every arm of
# that question has a LINK/PLAIN pair below: with the letter outside
# the generational vocabulary nothing is asked and the link joins, so
# each pair says which arm is doing the work rather than that some
# arm is (#397 review -- the first cut asked about the link's
# POSITION, which every one of these shapes satisfies).
def test_a_suffix_word_on_the_right_is_no_name_word() -> None:
    out = _grouped("Josep Lluis Carod i Jr.", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Josep", "Lluis", "Carod", "i", "Jr."]]
    plain = _grouped("Josep Lluis Carod i Jr.", lexicon=_PLAIN_LEX)
    assert _piece_texts(plain) == [["Josep", "Lluis", "Carod i Jr."]]


def test_the_right_hand_test_reads_the_peel_not_the_suffix_piece(
) -> None:
    # the arm that forces trailing_start rather than is_suffix_piece:
    # a ONE-CHARACTER suffix word is initial-shaped, so the
    # suffix-piece test refuses it (rules.md#S2's initial veto) while
    # assign's trailing peel takes it. Spelled with the piece test
    # alone, the link would swallow the generation here.
    lex = _LINK_LEX.add(suffix_words={"v"})
    out = _grouped("Josep Lluis Carod i V", lexicon=lex)
    assert _piece_texts(out) == [["Josep", "Lluis", "Carod", "i", "V"]]
    plain = _grouped("Josep Lluis Carod i V",
                     lexicon=_PLAIN_LEX.add(suffix_words={"v"}))
    assert _piece_texts(plain) == [["Josep", "Lluis", "Carod i V"]]


def test_a_title_on_the_right_is_no_name_word() -> None:
    out = _grouped("Josep Lluis Carod i Mr.", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Josep", "Lluis", "Carod", "i", "Mr."]]
    plain = _grouped("Josep Lluis Carod i Mr.", lexicon=_PLAIN_LEX)
    assert _piece_texts(plain) == [["Josep", "Lluis", "Carod i Mr."]]


def test_a_leading_title_on_the_left_is_no_name_word() -> None:
    # the link opens the NAME even though a piece stands before it:
    # assign peels the title run off the front.
    out = _grouped("Mr. i Rovira Puig Vila", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Mr.", "i", "Rovira", "Puig", "Vila"]]
    plain = _grouped("Mr. i Rovira Puig Vila", lexicon=_PLAIN_LEX)
    assert _piece_texts(plain) == [["Mr. i Rovira", "Puig", "Vila"]]


def test_an_unlisted_leading_abbreviation_is_no_name_word_either(
) -> None:
    # and THIS is the `lo` bound's own row, the listed spelling above
    # being caught by the title-piece test as well. rules.md#H2 reads
    # an unlisted abbreviation opening a name as a title by SHAPE, so
    # the vocabulary says nothing about 'Xyz.' and only the bound
    # assign's own title run draws keeps the link from joining it.
    # Measured 2026-09-20: replace `lo` with 0 and this is the one
    # test in the suite that dies.
    out = _grouped("Xyz. i Rovira Puig Vila", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Xyz.", "i", "Rovira", "Puig", "Vila"]]
    plain = _grouped("Xyz. i Rovira Puig Vila", lexicon=_PLAIN_LEX)
    assert _piece_texts(plain) == [["Xyz. i Rovira", "Puig", "Vila"]]


def test_a_credential_or_honorific_mid_name_is_no_name_word_either(
) -> None:
    # what the two bounds do NOT reach, and why the piece tests stay
    # inside them: neither the title run nor the trailing peel walks
    # into the middle of a name.
    suffix = _grouped("Josep Lluis Jr. i Rovira", lexicon=_LINK_LEX)
    assert _piece_texts(suffix) == [
        ["Josep", "Lluis", "Jr.", "i", "Rovira"]]
    title = _grouped("Josep Lluis Mr. i Rovira", lexicon=_LINK_LEX)
    assert _piece_texts(title) == [
        ["Josep", "Lluis", "Mr.", "i", "Rovira"]]
    assert _piece_texts(_grouped("Josep Lluis Jr. i Rovira",
                                  lexicon=_PLAIN_LEX)) == [
        ["Josep", "Lluis", "Jr. i Rovira"]]
    assert _piece_texts(_grouped("Josep Lluis Mr. i Rovira",
                                  lexicon=_PLAIN_LEX)) == [
        ["Josep", "Lluis", "Mr. i Rovira"]]


def test_a_credential_or_honorific_mid_name_on_the_right_too() -> None:
    # the MIRROR of the pair above, and the two rows that make the
    # right-hand piece tests mean something: the credential and the
    # honorific rows further up stand at the END of the name, where
    # `hi` refuses them before either piece test is asked, so with
    # those rows alone the right-hand tests could be deleted and no
    # test would fail (measured 2026-09-21 by mutation, which is what
    # asking both sides in ONE call made visible -- a per-side call
    # mutated both sides at once and the left-hand rows covered it).
    # Mid-name on the RIGHT is inside both bounds, so only the piece
    # tests keep the link from joining a credential or a title.
    suffix = _grouped("Josep Lluis i Jr. Rovira", lexicon=_LINK_LEX)
    assert _piece_texts(suffix) == [
        ["Josep", "Lluis", "i", "Jr.", "Rovira"]]
    title = _grouped("Josep Lluis i Mr. Rovira", lexicon=_LINK_LEX)
    assert _piece_texts(title) == [
        ["Josep", "Lluis", "i", "Mr.", "Rovira"]]
    assert _piece_texts(_grouped("Josep Lluis i Jr. Rovira",
                                  lexicon=_PLAIN_LEX)) == [
        ["Josep", "Lluis i Jr.", "Rovira"]]
    assert _piece_texts(_grouped("Josep Lluis i Mr. Rovira",
                                  lexicon=_PLAIN_LEX)) == [
        ["Josep", "Lluis i Mr.", "Rovira"]]


def test_the_walk_looks_past_a_run_of_connectives() -> None:
    # a RUN joins as one, so the word the condition is about is the
    # first one past the run, not the connective beside the link.
    out = _grouped("Carod i y Rovira", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Carod i y Rovira"]]


def test_where_the_run_runs_out_there_is_no_name_word() -> None:
    # the same walk reaching the end of the pieces: a link behind
    # nothing but connectives is joining nothing, and the run may not
    # absorb it either.
    out = _grouped("Juan i y", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Juan", "i", "y"]]
    assert _piece_texts(_grouped("Juan i y", lexicon=_PLAIN_LEX)) == [
        ["Juan i y"]]
    doubled = _grouped("Josep Lluis Carod i i", lexicon=_LINK_LEX)
    assert _piece_texts(doubled) == [
        ["Josep", "Lluis", "Carod", "i", "i"]]
    assert _piece_texts(_grouped("Josep Lluis Carod i i",
                                  lexicon=_PLAIN_LEX)) == [
        ["Josep", "Lluis", "Carod i i"]]


def test_a_link_that_joins_nothing_does_not_count_for_another_join(
) -> None:
    # the COUNT half agreeing with the join (#397 review). The
    # trailing link joins nothing, so it is the generation -- and a
    # generation is no rootname, so the total stays at three and the
    # unrelated 'y' two pieces away keeps the carve-out. Counting it
    # gave the total four and joined the 'y'.
    out = _grouped("Carod y Rovira i", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Carod", "y", "Rovira", "i"]]
    plain = _grouped("Carod y Rovira i", lexicon=_PLAIN_LEX)
    assert _piece_texts(plain) == [["Carod y Rovira i"]]


def test_a_connective_with_nothing_to_its_left_does_not_join() -> None:
    # the other side of the same condition, and it needs four pieces
    # to get past the count: a link OPENING the name has no name word
    # behind it either.
    out = _grouped("i Carod Rovira Puig", lexicon=_LINK_LEX)
    assert _piece_texts(out)[0][0] == "i"


def test_the_both_sides_condition_reads_the_class_not_the_letter(
) -> None:
    # the recorded negative control for the class test the freeze
    # walk opens with, and the one the property invariants CANNOT
    # give: with the same letter outside the generational vocabulary
    # the condition declines to ask and the trailing connective
    # joins, exactly as a trailing 'y' does today. Measured -- remove
    # the "vocab:suffix" arm and this test is the one that dies.
    out = _grouped("John Quincy Smith i", lexicon=_PLAIN_LEX)
    assert _piece_texts(out) == [["John", "Quincy", "Smith i"]]


def test_a_trailing_shipped_connective_is_untouched_by_the_condition(
) -> None:
    # the shipped-vocabulary half of the same control: 'y' is a
    # connective and not a suffix word, so the condition never reaches
    # it and 'Lopez y' stays one piece.
    out = _grouped("Juan Garcia Lopez y")
    assert _piece_texts(out) == [["Juan", "Garcia", "Lopez y"]]


def test_the_three_word_carve_out_still_declines_before_both_sides(
) -> None:
    # the two gates are separate and this is what separates them:
    # three name words, so the count refuses and the both-sides test
    # is never reached. Delete the both-sides condition and this test
    # still passes while its four-word sibling does not.
    out = _grouped("Josep Carod i", lexicon=_LINK_LEX)
    assert _piece_texts(out) == [["Josep", "Carod", "i"]]


def test_a_one_case_letter_is_an_initial_and_never_counts() -> None:
    # what keeps the one-case fork's count where it was: classify
    # writes `initial` or `conjunction` on a single letter and never
    # both, so a letter the fork read as an initial reaches
    # _is_rootname with no conjunction tag at all, the count is
    # unmoved, and the name reads as it always did. The EXCLUSIVITY is
    # the load-bearing part, not the order of the two tests -- measured
    # (swapping them moves nothing).
    lex = _LINK_LEX.add(conjunctions_ambiguous={"i"})
    out = _grouped("josep carod i rovira", lexicon=lex)
    assert _piece_texts(out) == [["josep", "carod", "i", "rovira"]]


def test_the_class_reaches_a_callers_own_connective() -> None:
    # rules.md#P3 is keyed on the class throughout: a caller who adds
    # 'v' to their connectives gets the Catalan link's behavior for
    # it, because 'v' is generational vocabulary the way 'i' is.
    p = Parser(lexicon=Lexicon.default().add(conjunctions={"v"}))
    joined = p.parse("Josep Carod v Rovira")
    assert (joined.given, joined.family) == ("Josep", "Carod v Rovira")
    trailing = p.parse("John Quincy Smith v")
    assert (trailing.family, trailing.suffix) == ("Smith", "v")


def test_a_callers_non_generational_letter_is_outside_the_condition(
) -> None:
    # the recorded negative control, at the reading level: 'x' is a
    # roman numeral letter that is NOT suffix vocabulary, so the
    # both-sides condition declines to ask and BOTH positions join,
    # which is what they did before this change too.
    p = Parser(lexicon=Lexicon.default().add(conjunctions={"x"}))
    assert p.parse("John Quincy Smith x").family == "Smith x"
    assert p.parse("Josep Carod x Rovira").family == "Carod x Rovira"


def test_the_count_reaches_a_connective_that_is_particle_vocabulary(
) -> None:
    # the ACCEPTED CONSEQUENCE of counting a connective whatever else
    # it is: _is_rootname refuses a PARTICLE piece the same way it
    # refuses a generational one, so a caller who makes 'y' a particle
    # too used to get a different reading from the default lexicon.
    # Now it agrees with it -- the direction the rule wants. Measured
    # before this change: given 'Juan', middle 'Velasquez', family
    # 'y Garcia', family_base 'Garcia'.
    p = Parser(lexicon=Lexicon.default().add(particles={"y"}))
    out = p.parse("Juan Velasquez y Garcia")
    assert (out.given, out.middle, out.family) == (
        "Juan", "", "Velasquez y Garcia")
    # the cost that comes with it, pinned rather than hidden:
    # family_base drops a particle wherever it stands and not only
    # leading, so the joined run loses the letter here. A standing
    # rules.md#R2 limit this row surfaces, not one it creates.
    assert out.family_base == "Velasquez Garcia"


# --- #397 review: the link inside a MAIDEN CLAUSE -------------------
# rules.md#M2's link clause. The walk ends the birth name at the first
# suffix WORD after the marker, and the link is one -- so it ended the
# clause there, and what #397 added was to JOIN the words it left
# standing into the current surname. Each branch below has the same
# LINK/PLAIN pair the both-sides tests above use: with the letter
# outside the generational vocabulary the walk never stopped at it in
# the first place, so the pair says which arm does the work.
#
# `ma` is added to BOTH acronym sets where the right-hand neighbour
# has to be an AMBIGUOUS credential: such a word carries no
# `vocab:suffix` tag, so the piece test cannot refuse it and only the
# peel bound keeps it out of the clause.
_LINK_MA_LEX = _LINK_LEX.add(suffix_acronyms={"ma"},
                             suffix_acronyms_ambiguous={"ma"})
_PLAIN_MA_LEX = _PLAIN_LEX.add(suffix_acronyms={"ma"},
                               suffix_acronyms_ambiguous={"ma"})


def test_a_link_inside_a_maiden_clause_does_not_end_it() -> None:
    # the statement of the rule. A birth-name word on each side of the
    # link, so the walk steps over it and the clause takes all three
    # words; without the exception the clause is 'Puig' and 'i Soler'
    # is left for the joins to build a surname out of.
    out = _grouped("Jane Doe née Puig i Soler", lexicon=_LINK_LEX)
    assert _maiden_texts(out) == ["Puig", "i", "Soler"]
    assert _piece_texts(out) == [["Jane", "Doe"]]


def test_the_clause_link_arm_is_what_moves_it_not_the_vocabulary(
) -> None:
    # the PLAIN twin: with the letter a connective but NOT generational
    # vocabulary the walk never stopped at it, so the reading is the
    # one it always had. The pair is what says the exception is about
    # the overlap.
    out = _grouped("Jane Doe née Puig i Soler", lexicon=_PLAIN_LEX)
    assert _maiden_texts(out) == ["Puig", "i", "Soler"]


def test_the_clause_link_survives_a_family_comma() -> None:
    # the same walk under the GIVEN_SLOT reader, which is a different
    # branch of the take rather than a second member of one shape:
    # before the exception the leak landed in the given part.
    out = _grouped("Doe, Jane née Puig i Soler", lexicon=_LINK_LEX)
    assert _maiden_texts(out) == ["Puig", "i", "Soler"]
    assert _piece_texts(out) == [["Doe"], ["Jane"]]


def test_a_clause_link_runs_twice_over() -> None:
    # every link of the clause is asked, not just the first: the walk
    # steps over each one it finds between two birth-name words.
    out = _grouped("Jane Doe née Puig i Soler i Vila", lexicon=_LINK_LEX)
    assert _maiden_texts(out) == ["Puig", "i", "Soler", "i", "Vila"]


def test_a_clause_link_with_nothing_on_its_right_still_ends_it(
) -> None:
    # the first control. Nothing stands after the link at all, so it
    # is joining nothing and is the generation it also spells -- the
    # clause ends at it exactly as it did before, and `_name_word_
    # beside` walks off the end. The PLAIN twin keeps the letter,
    # which is what says this row is the condition's doing.
    out = _grouped("Jane Doe née Puig i", lexicon=_LINK_LEX)
    assert _maiden_texts(out) == ["Puig"]
    plain = _grouped("Jane Doe née Puig i", lexicon=_PLAIN_LEX)
    assert _maiden_texts(plain) == ["Puig"]


def test_a_generation_on_the_links_right_is_no_name_word() -> None:
    # the second control, refused by CLASS: 'jr' is suffix vocabulary,
    # so `_between_name_words` declines it wherever it stands.
    out = _grouped("Jane Doe née Puig i jr", lexicon=_LINK_LEX)
    assert _maiden_texts(out) == ["Puig"]
    plain = _grouped("Jane Doe née Puig i jr", lexicon=_PLAIN_LEX)
    assert _maiden_texts(plain) == ["Puig", "i"]


def test_an_ambiguous_credential_on_the_right_is_refused_by_bound(
) -> None:
    # the third control, and the one that pins WHICH right-hand bound
    # the exception reads. 'MA' carries no `vocab:suffix` tag -- the
    # piece test says nothing about it -- so what keeps it out of the
    # clause is `peel_start`, where assign's trailing run begins over
    # the pieces as written. Read the walk's own stop instead and this
    # row takes 'i MA' into the birth name.
    out = _grouped("Jane Doe née Puig i MA", lexicon=_LINK_MA_LEX)
    assert _maiden_texts(out) == ["Puig"]
    plain = _grouped("Jane Doe née Puig i MA", lexicon=_PLAIN_MA_LEX)
    assert _maiden_texts(plain) == ["Puig", "i"]


def test_a_suffix_word_that_is_no_connective_still_ends_the_clause(
) -> None:
    # the recorded negative control for the CLASS half of the
    # exception, the shape 'Juan Garcia Lopez y' is for the join: 'jr'
    # stands between two birth-name words and is not a connective at
    # all, so the exception is never asked and the clause ends at it
    # as it always did. Drop the connective conjunct and this row
    # reads maiden 'Puig jr Soler' -- measured. Identical under both
    # lexicons, the letter deciding nothing here.
    out = _grouped("Jane Doe née Puig jr Soler", lexicon=_LINK_LEX)
    assert _maiden_texts(out) == ["Puig"]
    assert _piece_texts(out) == [["Jane", "Doe", "jr", "Soler"]]


def test_the_marker_is_not_the_name_word_on_the_links_left() -> None:
    # the fourth control, and the one the clause's own `lo` bound
    # carries: the marker announces the name and is no word of it, so
    # a link standing first inside the clause joins nothing there. The
    # walk then stops at its very first piece and the pass declines
    # altogether, leaving the marker an ordinary word (rules.md#M2).
    out = _grouped("Jane Doe née i Soler", lexicon=_LINK_LEX)
    assert _maiden_texts(out) == []
    assert _piece_texts(out) == [["Jane", "Doe", "née i Soler"]]
    plain = _grouped("Jane Doe née i Soler", lexicon=_PLAIN_LEX)
    assert _maiden_texts(plain) == ["i", "Soler"]


def test_a_core_between_the_marker_and_the_first_word_is_below_lo(
) -> None:
    # A delimiter core is TAIL-segment structure that group() drops
    # after this pass, so it is never a word of the clause -- and
    # between the marker and the first word it is below `lo`, which
    # the bound refuses without the piece tests ever being asked.
    # Reachable, not theoretical: measured 2026-09-21 over corpus u
    # cases.py u the property grids u a 50,925-name generated set with
    # cores, under thirteen core-bearing policies, 25,536 of 596,392
    # maiden takes had a core standing there.
    out = _grouped("Smith, John, PhD née - i Jones", policy=_DASH,
                   lexicon=_LINK_LEX)
    assert _maiden_texts(out) == []
    # and the control that says the CORE is doing it: with no
    # delimiter configured the dash is an ordinary word, so the link
    # has a name word on its left and the clause keeps the run.
    plain = _grouped("Smith, John, PhD née - i Jones", lexicon=_LINK_LEX)
    assert _maiden_texts(plain) == ["-", "i", "Jones"]


def test_a_core_beside_a_link_inside_the_clause_passes_for_a_word(
) -> None:
    # WHAT IS NOT TRUE OF A CORE PAST `lo`, pinned as it reads rather
    # than as it ought to: inside the clause a core is an ordinary
    # index to `_run_neighbours`, which steps over CONNECTIVES and
    # nothing else, so it stands as the name word on the link's left
    # and the clause runs on past a title it would otherwise stop at.
    # `_between_name_words` is asked about a core on one side or the
    # other in 51,072 of 900,023 calls over the population above, and
    # the answer differs from a core-skipping reading in 8,094 parses
    # (1,278 texts); 1,824 of those move the `maiden` field, on 288
    # texts. None is a corpus or cases.py name and none is reachable
    # at the default policy, `extra_suffix_delimiters` being empty
    # there. Reported, not fixed: the repair is `cores` threaded
    # through three call sites into `_run_neighbours`, not a one-liner
    # (#397 follow-up, 2026-09-21).
    out = _grouped("Smith, John, PhD née Puig Mr. - i Soler",
                   policy=_DASH, lexicon=_LINK_LEX)
    assert _maiden_texts(out) == ["Puig", "Mr.", "i", "Soler"]
    # the same clause with the core taken out of it: the title IS the
    # word on the link's left and refuses, so the clause ends there.
    without = _grouped("Smith, John, PhD née Puig Mr. i Soler",
                       policy=_DASH, lexicon=_LINK_LEX)
    assert _maiden_texts(without) == ["Puig", "Mr."]


def test_a_marker_with_nothing_after_it_declines_before_the_bound(
) -> None:
    # the clause's `lo` is the first piece after the marker run, and
    # with nothing behind the marker there is no such piece: the pass
    # declines here rather than indexing for a bound it would never
    # read. Unchanged behavior, and the row exists because the early
    # return is what makes it unchanged.
    out = _grouped("Jane Doe née", lexicon=_LINK_LEX)
    assert _maiden_texts(out) == []
    assert _piece_texts(out) == [["Jane", "Doe", "née"]]


# --- #397 second review: the bound, the class and the frozen piece --

def test_a_trailing_title_does_not_hide_the_suffix_run_from_the_join(
) -> None:
    # rules.md#H5 read where the JOIN asks its question (#397 second
    # review). `trailing_start` reads the peel over the pieces as
    # WRITTEN, so a title standing behind the suffix run makes the
    # peel take nothing and the answer is `len(pieces)` -- and a
    # caller using it as the right bound of the NAME is then told a
    # credential is a name word. 'MA' carries no `vocab:suffix` tag,
    # so the piece test cannot refuse it either and the join swallowed
    # it: family 'Adams i MA', no report, and `initials()` gaining an
    # 'M.'.
    #
    # The pair is the finding, and it is H5's own sentence: the name
    # one title shorter has always read the other way.
    # the SHIPPED vocabulary reaches this row -- 'i' is a default
    # connective and a default suffix word, 'MA' a default ambiguous
    # acronym and 'Prof.' a default title -- so this is one of the
    # few #397 rows that needs no built lexicon at all.
    shipped = Lexicon.default()
    titled = _grouped("John Quincy Adams i MA Prof.", lexicon=shipped)
    bare = _grouped("John Quincy Adams i MA", lexicon=shipped)
    assert _piece_texts(titled) == [
        ["John", "Quincy", "Adams", "i", "MA", "Prof."]]
    assert _piece_texts(bare) == [["John", "Quincy", "Adams", "i", "MA"]]
    # and end to end, where the fields say what the bound bought.
    # The SHIPPED vocabulary reaches this: 'i' is a default
    # connective and a default suffix word, and 'MA' a default
    # ambiguous acronym, so no built lexicon is needed here and the
    # row is a real parse rather than a configured one.
    parser = Parser()
    name = parser.parse("John Quincy Adams i MA Prof.")
    assert name.as_dict() == {
        "title": "Prof.", "given": "John", "middle": "Quincy",
        "family": "Adams", "suffix": "i MA", "nickname": "", "maiden": ""}
    assert name.initials() == "J. Q. A."
    assert [a.kind.value for a in name.ambiguities] == ["suffix-or-name"]
    # a LOWER-CASE title is the same shape and reaches the same
    # bound: the vocabulary lookup is folded, so 'prof.' peels like
    # 'Prof.'
    lower_title = parser.parse("John Quincy Adams i MA prof.")
    assert lower_title.title == "prof."
    assert lower_title.suffix == "i MA"
    # the ONE-CASE spellings never reached the defect and are pinned
    # as the control: written wholly in one case the letter reads as
    # an initial (rules.md#P3's marked subset), no join is attempted
    # at all, and both spellings already agreed with each other and
    # with the untitled name at dc3bdf9c -- which is what says the
    # bound and not the marking is what this row is about.
    for text, title in (("john quincy adams i ma prof.", "prof."),
                        ("JOHN QUINCY ADAMS I MA PROF.", "PROF.")):
        one_case = parser.parse(text)
        assert one_case.title == title
        assert one_case.suffix == text.split()[-2]


def test_a_multi_letter_link_of_the_suffix_vocabulary_joins_by_the_same_rule(
) -> None:
    # rules.md#P3's both-sides clause names a CLASS -- "a connective
    # that is also generational vocabulary" -- and says nothing about
    # how the word is spelled (#397 second review). A `len(text) != 1`
    # filter stood in the stage and narrowed the clause to one-letter
    # connectives, untested and undocumented; this is the row that was
    # caller-reachable past it. Nothing SHIPPED reaches it -- 'i' is
    # the only member of the class in the default vocabulary and in
    # every locale pack -- which is why the lexicon is built here.
    lex = Lexicon.default().add(conjunctions={"og"},
                                suffix_words={"og"})
    parser = Parser(lexicon=lex)
    # nothing on its right: it is the generation it also spells
    lone = parser.parse("John Quincy Smith og")
    assert lone.family == "Smith"
    assert lone.suffix == "og"
    # a name word on each side: it joins, exactly as a one-letter
    # member does
    joined = parser.parse("Josep Carod og Rovira")
    assert joined.family == "Carod og Rovira"
    # the three-word carve-out stays SINGLE-LETTER, which is what its
    # own sentence says ("a single-letter connective in a three-word
    # name"): 'og' is two letters, so it joins in a THREE-word name
    # where the one-letter 'i' of the shipped vocabulary stays a name
    # word in the middle.
    assert parser.parse("Josep og Carod").given == "Josep og Carod"
    assert Parser().parse("Josep i Carod").middle == "i"
    # and with nothing on its right the class test decides before the
    # carve-out is ever asked, for either spelling
    assert parser.parse("Josep Carod og").suffix == "og"
    assert Parser().parse("Josep Carod i").suffix == "i"


def test_a_frozen_link_is_still_absorbed_by_a_neighbours_join() -> None:
    # What freezing a piece claims and what it does not (#397 second
    # review). `frozen` keeps a connective from being the SUBJECT of a
    # join; it does not keep the word out of the span another
    # connective's join takes. The trailing 'i' here has nothing on
    # its right and is frozen, and the 'y' beside it joins across it
    # all the same.
    #
    # Not a defect and not a silence: this is the reading the parent
    # commit 46651750 gives the same name, the letter being no
    # connective there at all, so the row is a CONTROL for the
    # comment beside `frozen` rather than a behavior claim of its own.
    out = Parser().parse("Josep Carod Rovira Puig y i")
    assert out.family == "Puig y i"
    assert out.middle == "Carod Rovira"
    assert out.suffix == ""

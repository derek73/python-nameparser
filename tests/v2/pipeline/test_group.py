import dataclasses

import pytest

from nameparser._lexicon import Lexicon
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited, _maiden_marked
from nameparser._pipeline._group import group
from nameparser._pipeline._script_segment import script_segment
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._pipeline._vocab import maiden_marker_run
from nameparser._policy import Policy, Script
from nameparser._types import Role

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
    assert _piece_texts(_grouped("Ph. D. Van Johnson")) == \
        [["Ph. D.", "Van Johnson"]]
    assert _piece_texts(_grouped("II Van Johnson")) == [["II", "Van Johnson"]]


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
    # "MD" continues the "V MD" entry (joined); "PhD" starts a fresh
    # entry across the dropped delimiter, so it does NOT get "joined"
    md_tok = next(t for t in out.tokens if t.text == "MD")
    phd_tok = next(t for t in out.tokens if t.text == "PhD")
    assert "joined" in md_tok.tags
    assert "joined" not in phd_tok.tags


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


def test_the_title_run_is_one_key_as_h1_reads_it() -> None:
    # post_rules looks the WHOLE title run up as one key, so "mr sir"
    # is not "sir". P5 has to read the run the same way: if it joined
    # here, H1 would then read the joined piece as the family name --
    # the two rules would disagree about what the same run asserts.
    out = _grouped("mr sir abdul rahman", lexicon=_GIVEN_NAME_TITLE_LEX)
    assert _piece_texts(out) == [["mr", "sir", "abdul", "rahman"]]


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


def test_a_conjunction_joined_title_run_is_keyed_whole() -> None:
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
    out = _grouped("abdul Smith jr Ma", lexicon=_AMBIGUOUS_LEX)
    assert _piece_texts(out) == [["abdul", "Smith", "jr", "Ma"]]


def test_the_join_never_turns_a_suffix_into_a_name() -> None:
    # Unjoined, 'abdul Smith Ma' has words to spare and the peel reads
    # the acronym as a credential; joined, the view is two pieces and
    # the fork would keep it as the family. The join joins two name
    # words and changes nothing else, so it declines -- 1.4.0's
    # reading, and 'John Smith Ma's. With a family behind it the
    # acronym peels either way, and the join stands.
    out = _grouped("abdul Smith Ma", lexicon=_AMBIGUOUS_LEX)
    assert _piece_texts(out) == [["abdul", "Smith", "Ma"]]
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
    # with a given word of its own the three pieces survive the chain
    out = _grouped("St John van Berg Ma", lexicon=lex)
    assert _piece_texts(out) == [["St", "John", "van Berg", "Ma"]]


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
    out = _grouped("John van der Berg Ma", lexicon=_AMBIGUOUS_LEX)
    assert _piece_texts(out) == [["John", "van der Berg", "Ma"]]


def test_the_maiden_walk_stops_before_the_numeral_too() -> None:
    # M2's walk takes the words after the marker "up to any trailing
    # suffix", asked with the same test: 'John née Jones Smith V' took
    # the V into the maiden name. Read by the peel from the marker on,
    # the V is the suffix, and the walk stops before it.
    out = _grouped("John née Jones Smith V")
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Smith"]
    assert _piece_texts(out) == [["John", "V"]]


def test_the_maiden_walk_leaves_the_acronym_fork_to_assign() -> None:
    # The bare-acronym fork counts pieces, and the walk removes the
    # pieces it counted: peeled over the pieces as they stand, 'Ma'
    # would be a credential with words to spare, but once 'Jones
    # Smith' has left the name it is the family of a two-piece name.
    # So the walk takes it as maiden text, as it always did, and
    # stops only at the numeral fork.
    out = _grouped("John née Jones Smith Ma", lexicon=_AMBIGUOUS_LEX)
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Smith", "Ma"]
    # The numeral-only reading is what the acronym BETWEEN the maiden
    # name and the numeral shows: the general peel would stop at the
    # acronym, the re-ask would veto it, and the walk would take the
    # numeral too (the test review's surviving mutant).
    out = _grouped("Jane Smith née Jones Ma V", lexicon=_AMBIGUOUS_LEX)
    assert [t.text for t in out.tokens if t.role is Role.MAIDEN] == \
        ["Jones", "Ma"]


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
    run = 1
    while (head + run < len(bare.tokens)
           and "vocab:maiden-marker-cont" in bare.tokens[head + run].tags):
        run += 1
    answers["classify"] = run
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
    answers = _marker_sites(spelling)
    assert len(set(answers.values())) == 1, answers
    # never vacuous: the parametrization's own precondition is that
    # each spelling is WHOLLY a marker, so the agreed answer is its
    # word count -- an all-zero agreement would otherwise pass
    assert answers["predicate"] == len(spelling.split())

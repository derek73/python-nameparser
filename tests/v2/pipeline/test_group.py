from nameparser._lexicon import Lexicon
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._group import group
from nameparser._pipeline._script_segment import script_segment
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
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
    above exists to protect."""
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
    # v1 expand_suffix_delimiter parity (#191): a configured delimiter
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

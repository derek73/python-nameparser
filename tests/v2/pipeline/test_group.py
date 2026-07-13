from nameparser._lexicon import Lexicon
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._group import group
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import Policy
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


def _grouped(text: str) -> ParseState:
    state = ParseState(original=text, lexicon=_LEX, policy=Policy())
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
    # v1 issue #11: 3 rootname parts, single-letter conjunction "y"
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


def test_initials_do_not_count_as_rootnames_for_conjunction_carveout() -> None:
    # v1 parity: 'J.' is an initial, so total rootnames stay under 4 and
    # the single-letter conjunction 'y' is treated as an initial, not joined
    out = _grouped("J. Ruiz y Gomez")
    assert _piece_texts(out) == [["J.", "Ruiz", "y", "Gomez"]]


def test_suffix_comma_name_segment_gets_no_additional_count() -> None:
    # v1 parity: additional_parts_count applies to FAMILY_COMMA parts only;
    # ', PhD' must not tip the single-letter-conjunction carve-out
    out = _grouped("John y Smith, PhD")
    assert _piece_texts(out) == [["John", "y", "Smith"], ["PhD"]]

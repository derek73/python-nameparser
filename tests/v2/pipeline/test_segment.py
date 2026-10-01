from nameparser._lexicon import Lexicon
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState, Structure
from nameparser._pipeline._tokenize import tokenize
import dataclasses

from nameparser._policy import Policy
from nameparser._types import AmbiguityKind

# synthetic vocabulary: behavior given a lexicon, never default() contents
_LEX = Lexicon(
    suffix_acronyms=frozenset({"phd", "md", "do", "dds", "ma", "ed"}),
    suffix_acronyms_ambiguous=frozenset({"ma", "ed", "do"}),
    suffix_words=frozenset({"jr", "v"}),
)


def _segmented(text: str) -> ParseState:
    state = ParseState(original=text, lexicon=_LEX, policy=Policy())
    return segment(tokenize(extract_delimited(state)))


def _texts(state: ParseState, seg: tuple[int, ...]) -> list[str]:
    return [state.tokens[i].text for i in seg]


def test_no_comma() -> None:
    out = _segmented("John Smith")
    assert out.structure is Structure.NO_COMMA
    assert [_texts(out, s) for s in out.segments] == [["John", "Smith"]]


def test_family_comma() -> None:
    out = _segmented("Smith, John")
    assert out.structure is Structure.FAMILY_COMMA
    assert [_texts(out, s) for s in out.segments] == [["Smith"], ["John"]]


def test_suffix_comma_when_all_rest_groups_are_suffixes() -> None:
    out = _segmented("John Smith, PhD")
    assert out.structure is Structure.SUFFIX_COMMA
    assert [_texts(out, s) for s in out.segments] == [["John", "Smith"], ["PhD"]]


def test_suffix_comma_lenient_accepts_initial_shaped_suffix_word() -> None:
    # "V" is initial-shaped; the strict test vetoes it, the post-comma
    # lenient test accepts suffix_words unconditionally (v1 parity)
    out = _segmented("John Ingram, V")
    assert out.structure is Structure.SUFFIX_COMMA


def test_the_credential_pair_merges_anywhere_in_the_run() -> None:
    # v1's fix_phd healed a split 'Ph. D.' wherever it fell, and the
    # suffix-comma test inherits that: the pair counts as ONE unit at
    # any position, not just at the head of the run. Nothing else
    # reaches past position 0 -- 'John Smith, Ph. D.' above puts the
    # pair first -- and the flip is silent, because 'D.' alone is
    # suffix vocabulary in no lexicon, so the run stops being wholly
    # suffix and this reads as a FAMILY comma instead.
    out = _segmented("John Smith, Jr. Ph. D.")
    assert out.structure is Structure.SUFFIX_COMMA
    assert [_texts(out, s) for s in out.segments] == [
        ["John", "Smith"], ["Jr.", "Ph.", "D."]]


def test_family_comma_with_trailing_suffix_segment() -> None:
    out = _segmented("Smith, John, Jr.")
    assert out.structure is Structure.FAMILY_COMMA
    assert [_texts(out, s) for s in out.segments] == [["Smith"], ["John"], ["Jr."]]


def test_single_pre_comma_word_never_suffix_comma() -> None:
    # v1: suffix-comma requires >1 word before the comma
    out = _segmented("Johnson, Jr.")
    assert out.structure is Structure.FAMILY_COMMA


def test_excess_non_suffix_segment_flags_comma_structure() -> None:
    out = _segmented("Smith, John, Extra, Jr.")
    assert out.structure is Structure.FAMILY_COMMA
    kinds = [a.kind for a in out.ambiguities]
    assert AmbiguityKind.COMMA_STRUCTURE in kinds


def test_empty_input_yields_no_segments() -> None:
    assert _segmented("").segments == ()


def test_comma_only_input_is_no_comma_structure() -> None:
    out = _segmented(",,,")
    assert out.structure is Structure.NO_COMMA
    assert out.segments == ()


def test_single_trailing_comma_is_cosmetic_and_dropped() -> None:
    # v1 parity: exactly ONE trailing comma is cosmetic and stripped
    # (segment.py's "pop the trailing empty bucket" step), so
    # 'Smith, John,' segments identically to 'Smith, John' -- unlike a
    # genuinely empty INTERIOR bucket ('Doe,, Jr.'), which stays
    # structural and keeps its position.
    out = _segmented("Smith, John,")
    assert out.structure is Structure.FAMILY_COMMA
    assert [_texts(out, s) for s in out.segments] == [["Smith"], ["John"]]


def test_leading_comma_yields_empty_first_segment() -> None:
    # A leading comma produces a non-trailing empty bucket, which is
    # structural (not cosmetic) and keeps its position as segment 0.
    out = _segmented(",John Smith")
    assert out.structure is Structure.FAMILY_COMMA
    assert [_texts(out, s) for s in out.segments] == [[], ["John", "Smith"]]


def test_strict_comma_suffixes_veto_lenient_only_members() -> None:
    # lenient_comma_suffixes=False: the post-comma test drops back to
    # the strict predicate, so initial-shaped suffix words no longer
    # qualify and the structure reads FAMILY_COMMA
    state = ParseState(
        original="John Ingram, V", lexicon=_LEX,
        policy=dataclasses.replace(Policy(), lenient_comma_suffixes=False))
    out = segment(tokenize(extract_delimited(state)))
    assert out.structure is Structure.FAMILY_COMMA


def test_structure_flips_for_the_ambiguous_class_on_a_name_word_count() -> None:
    # rules.md#C1 for the ambiguous class: two or more NAME words
    # before the comma read the part after it as the credential run.
    # 'John Smith, MA' flips; 'Smith Jr., MA' does not, having two
    # TOKENS and one name word -- which is what keeps Smith in the
    # family (#289, decisions.md#S2).
    assert _segmented("John Smith, MA").structure is Structure.SUFFIX_COMMA
    assert _segmented("Smith Jr., MA").structure is Structure.FAMILY_COMMA
    assert _segmented("Smith, MA").structure is Structure.FAMILY_COMMA
    # the extension reaches the LISTED set whatever the case says, so
    # a one-case name flips too -- 1.4.0 read all three as suffixes
    assert _segmented("JOHN SMITH, MA").structure is Structure.SUFFIX_COMMA
    assert _segmented("john smith, ma").structure is Structure.SUFFIX_COMMA
    assert _segmented("John Smith, Ed").structure is Structure.SUFFIX_COMMA
    assert _segmented("Davis Royce, Ed").structure is Structure.SUFFIX_COMMA
    assert _segmented("Royce, Ed").structure is Structure.FAMILY_COMMA


def test_structure_flips_for_a_by_shape_member_too() -> None:
    # #516: an unlisted dotted token joins the class the same way, via
    # `_vocab.ambiguous_class_candidate` -- 'X.Y.Z.' is three unclaimed
    # single-letter chunks, not vocabulary at all, so this is the
    # by-shape twin of the test above. 'Smith Jr., X.Y.Z.' does not
    # flip for the SAME reason 'Smith Jr., MA' does not (#516 review
    # round: is_wholly_suffix must never admit the shape class here, or
    # C1's legacy TOKEN-count disjunct flips it wrongly on 'Jr.').
    assert _segmented("John Smith, X.Y.Z.").structure \
        is Structure.SUFFIX_COMMA
    assert _segmented("Smith, X.Y.Z.").structure is Structure.FAMILY_COMMA
    assert _segmented("Smith Jr., X.Y.Z.").structure \
        is Structure.FAMILY_COMMA


def test_paired_initials_need_a_word_to_speak_for_them() -> None:
    # rules.md#C1 (#563): two dotted single letters are how a person's
    # own initials are written, and two words before the comma may be
    # one surname, so alone they keep the family comma. Each contrast
    # pair differs in the one thing that speaks: a third letter, a
    # credential IN FRONT (not behind), a second by-shape word. A
    # generational word in front speaks like any suffix word; the
    # title-vocabulary exception needs titles this lexicon lacks, so
    # its contrast is the case-table pair
    # a_title_in_front_of_paired_initials_does_not_speak.
    for alone, spoken in (("García Márquez, G.J.", "García Márquez, G.J.R."),
                          ("De La Cruz, M.J. PhD", "De La Cruz, PhD M.J."),
                          ("John Smith, X.Y. MA", "John Smith, X.Y. P.Q."),
                          ("García Márquez, G.J.", "García Márquez, Jr G.J.")):
        assert _segmented(alone).structure is Structure.FAMILY_COMMA, alone
        assert _segmented(spoken).structure is Structure.SUFFIX_COMMA, spoken


def test_a_flip_on_dotted_shape_alone_is_silent() -> None:
    # rules.md#C1 (#563): with paired initials set aside, a word the
    # class admits by its dotted shape has no name reading to report,
    # while a LISTED member in the same position still reports the
    # flip -- the control that keeps the silence from being a lost
    # emitter.
    for text in ("John Smith, X.Y.Z.", "John Smith, B.Tech.",
                 "John Smith, X.Y.Z. P.D.Q.", "John Smith, PhD P.D.Q."):
        out = _segmented(text)
        assert out.structure is Structure.SUFFIX_COMMA, text
        assert _flip_reports(out) == [], text
    for text in ("John Smith, Ma", "John Smith, PhD Ma",
                 "John Smith, X.Y.Z. MA"):
        out = _segmented(text)
        assert out.structure is Structure.SUFFIX_COMMA, text
        assert _flip_reports(out) == [_texts(out, out.segments[1])], text


def test_segment_records_the_case_fact_only_where_it_asked() -> None:
    # (a-lazy): the fact costs nothing on a name whose comma form
    # could not turn on it, and nothing at all on a comma-less name.
    assert _segmented("John Smith MA").one_case is None
    assert _segmented("Smith, John Q. Public").one_case is None
    assert _segmented("John Smith, MA").one_case is False
    assert _segmented("JOHN SMITH, MA").one_case is True
    # the regression test for the eager-gate fix: a single-token
    # post-comma part that is NOT a member of the ambiguous class
    # must not force the fact either -- membership is tested
    # case-free first, and only a genuine candidate pays for it.
    assert _segmented("Smith, John").one_case is None
    assert _segmented("John Smith, Jr.").one_case is None


def test_a_tail_segment_of_leaning_credentials_is_not_flagged() -> None:
    # The third reading site, and the one place this design QUIETS a
    # report: 'DO' leans credential in a mixed-case name, so the third
    # segment is a credential run and rules.md#C2's flag stops firing.
    state = _segmented("Steven Hardman, MD, DO, DDS")
    assert not [a for a in state.ambiguities
                if a.kind is AmbiguityKind.COMMA_STRUCTURE]
    # the one-case spelling keeps today's reading, flag and all
    state = _segmented("STEVEN HARDMAN, MD, DO, DDS")
    assert [a for a in state.ambiguities
            if a.kind is AmbiguityKind.COMMA_STRUCTURE]


def test_the_structure_flip_reports_a_verbatim_detail() -> None:
    # The first report of the comma's OWN decision in the library
    # (#289): C2's structural flag already reports on the comma path,
    # but it reports what the parse could not recognize, not a fork
    # it called. P6's attachment fork has separately reported on a
    # family-comma path since 2.3 ("Berg, Jan vd"). Pinned verbatim so
    # a wording edit is a deliberate one,
    # not a silent drift the case table's looser `ambiguities=` tuple
    # check would never catch.
    state = _segmented("John Smith, MA")
    (amb,) = [a for a in state.ambiguities
             if a.kind is AmbiguityKind.SUFFIX_OR_NAME]
    assert amb.detail == (
        "'MA' after the comma is also an ordinary name word; the part "
        "before the comma holds 2 name words, so it is read as a "
        "credential run")


def test_the_structure_flip_report_counts_the_real_pre_comma_words() -> None:
    # The count is INTERPOLATED, not a hardcoded "two": a three-word
    # pre-comma part reports its own count.
    state = _segmented("John Q. Public, MA")
    (amb,) = [a for a in state.ambiguities
             if a.kind is AmbiguityKind.SUFFIX_OR_NAME]
    assert "holds 3 name words" in amb.detail


def _flip_reports(state: ParseState) -> list[list[str]]:
    return [_texts(state, a.indices) for a in state.ambiguities
            if a.kind is AmbiguityKind.SUFFIX_OR_NAME]


def test_the_name_word_count_reads_a_run_as_it_reads_one_word() -> None:
    # rules.md#C1 (#544): a part of two or more words, every one of
    # them suffix vocabulary or a class member and at least one a
    # member, reads by the same NAME-word count as the single token,
    # and the flip reports once, over the whole part.
    for text in ("John Smith, PhD Ma", "John Smith, Ed Ma",
                 "John Smith, Ma PhD", "john smith, phd ma",
                 "JOHN SMITH, PHD MA", "John Smith, MD Ma",
                 "John Smith, X.Y.Z. MA", "John Smith, Ph. D. Ma"):
        out = _segmented(text)
        assert out.structure is Structure.SUFFIX_COMMA, text
        assert _flip_reports(out) == [_texts(out, out.segments[1])], text
    # one name word before the comma: the count leaves the listing form
    # and the run test is not even asked, so the case fact stays unasked
    out = _segmented("Smith, PhD Ma")
    assert out.structure is Structure.FAMILY_COMMA
    assert out.one_case is None
    assert _segmented("Smith Jr., PhD Ma").structure \
        is Structure.FAMILY_COMMA


def test_the_run_test_declines_a_name_word_and_a_numeral() -> None:
    # a name word anywhere in the part, or a word that is neither
    # vocabulary nor a member, keeps the listing form -- and so does a
    # single-letter roman numeral, in any case, for its one-letter
    # shape (a multi-letter one runs: 'John Smith, III Ma')
    for text in ("John Smith, Jones Ma", "John Smith, PhD Jones Ma",
                 "John Smith, V Ma", "John Smith, PhD v Ma",
                 "John Smith, PhD Ma.", "John Smith, J. Ma"):
        out = _segmented(text)
        assert out.structure is Structure.FAMILY_COMMA, text
        assert not _flip_reports(out), text


def test_a_run_the_writing_settles_is_left_to_the_listing_form() -> None:
    # every member written in capitals in a mixed-case name leans
    # credential (S2), so the part is already the credential run on
    # that evidence: no flip here and no report from this stage
    out = _segmented("John Smith, PhD MA")
    assert out.structure is Structure.FAMILY_COMMA
    assert not _flip_reports(out)
    assert out.one_case is False
    # the lean is the LISTED set's alone: a member admitted by SHAPE
    # is read by the count, capitals or not
    out = _segmented("John Smith, X.Y.Z. MA")
    assert out.structure is Structure.SUFFIX_COMMA
    # and one Title-case member is enough to make it the count's call
    assert _segmented("John Smith, MA Ed").structure \
        is Structure.SUFFIX_COMMA


def test_the_run_test_reads_a_delimiter_core_transparently() -> None:
    # a configured delimiter core is _vocab.run_word_fold's "defer"
    # (#544): without a delimiter policy
    # the bare token is a definite "reject" (no suffix set, no core)
    # and the run test breaks on it before it ever reaches
    # `is_wholly_suffix`; with the core configured the SAME token is
    # left for `is_wholly_suffix`'s own `text in cores` disjunct,
    # which admits it, so the two members either side of it still
    # complete the run.
    text = "John Smith, Ma - Ed"
    assert _segmented(text).structure is Structure.FAMILY_COMMA
    state = ParseState(
        original=text, lexicon=_LEX,
        policy=dataclasses.replace(
            Policy(), extra_suffix_delimiters=frozenset({" - "})))
    out = segment(tokenize(extract_delimited(state)))
    assert out.structure is Structure.SUFFIX_COMMA


def test_the_run_test_reads_lenient_comma_suffixes() -> None:
    # rules.md#C1's leftovers ask `is_wholly_suffix`'s own POLICY-
    # selected predicate (#544): an
    # initial-shaped suffix WORD ('B.') that is not a single-letter
    # roman numeral is a member of neither the ambiguous class nor
    # `is_single_letter_numeral`'s carve-out, so it reaches `rest` and
    # is read by `is_wholly_suffix` alone -- lenient by default (v1's
    # is_suffix_lenient bypasses the initial veto), strict under
    # Policy(lenient_comma_suffixes=False) (v1's is_suffix, which the
    # veto reads as a middle initial instead).
    lex = _LEX.add(suffix_words={"b"})
    text = "John Smith, Ma B."
    state = ParseState(original=text, lexicon=lex, policy=Policy())
    out = segment(tokenize(extract_delimited(state)))
    assert out.structure is Structure.SUFFIX_COMMA
    state = ParseState(
        original=text, lexicon=lex,
        policy=dataclasses.replace(Policy(), lenient_comma_suffixes=False))
    out = segment(tokenize(extract_delimited(state)))
    assert out.structure is Structure.FAMILY_COMMA

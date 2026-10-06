"""rules.md#C1's decision, made at the head of group once classify has
tagged the words (#613): `_comma.decide`. These tests were segment's
until the decision moved; they run the stages up to classify and then
the decision, as group does."""
from nameparser._lexicon import Lexicon
from nameparser._pipeline import _comma
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState, Structure
from nameparser._pipeline._tokenize import tokenize
import dataclasses

from nameparser._policy import Policy
from nameparser._types import AmbiguityKind, Role

# synthetic vocabulary: behavior given a lexicon, never default() contents
_LEX = Lexicon(
    suffix_acronyms=frozenset({"phd", "md", "do", "dds", "ma", "ed"}),
    suffix_acronyms_ambiguous=frozenset({"ma", "ed", "do"}),
    suffix_words=frozenset({"jr", "v"}),
)


def _decided(text: str, lexicon: Lexicon = _LEX,
             policy: Policy = Policy()) -> ParseState:
    state = ParseState(original=text, lexicon=lexicon, policy=policy)
    return _comma.decide(classify(segment(tokenize(extract_delimited(state)))))


def _texts(state: ParseState, seg: tuple[int, ...]) -> list[str]:
    return [state.tokens[i].text for i in seg]


def _flip_reports(state: ParseState) -> list[list[str]]:
    return [_texts(state, a.indices) for a in state.ambiguities
            if a.kind is AmbiguityKind.SUFFIX_OR_NAME]


def test_suffix_comma_when_all_rest_groups_are_suffixes() -> None:
    out = _decided("John Smith, PhD")
    assert out.structure is Structure.SUFFIX_COMMA
    assert [_texts(out, s) for s in out.segments] == [["John", "Smith"], ["PhD"]]


def test_suffix_comma_lenient_accepts_initial_shaped_suffix_word() -> None:
    # "V" is initial-shaped; the strict test vetoes it, the post-comma
    # lenient test accepts suffix_words unconditionally (v1 parity)
    out = _decided("John Ingram, V")
    assert out.structure is Structure.SUFFIX_COMMA


def test_the_credential_pair_merges_anywhere_in_the_run() -> None:
    # v1's fix_phd healed a split 'Ph. D.' wherever it fell, and the
    # suffix-comma test inherits that: the pair counts as ONE unit at
    # any position, not just at the head of the run. Behind a class
    # member, which opens nothing (#603's opener being an unambiguous
    # credential), the pair is what makes the part a run: without the
    # merge 'Ph.' and 'D.' are suffix vocabulary in no lexicon and this
    # reads as the FAMILY comma (measured with `_pieces` patched to
    # merge nothing, #613's PR review). Behind 'Jr.' the opener alone
    # would decide it, so that input pinned nothing.
    out = _decided("John Smith, MA Ph. D.")
    assert out.structure is Structure.SUFFIX_COMMA
    assert [_texts(out, s) for s in out.segments] == [
        ["John", "Smith"], ["MA", "Ph.", "D."]]


def test_structure_flips_for_the_ambiguous_class_on_a_name_word_count() -> None:
    # rules.md#C1 for the ambiguous class: two or more NAME words
    # before the comma read the part after it as the credential run.
    # 'John Smith, MA' flips; 'Smith Jr., MA' does not, having two
    # TOKENS and one name word -- which is what keeps Smith in the
    # family (#289, decisions.md#S2).
    assert _decided("John Smith, MA").structure is Structure.SUFFIX_COMMA
    assert _decided("Smith Jr., MA").structure is Structure.FAMILY_COMMA
    assert _decided("Smith, MA").structure is Structure.FAMILY_COMMA
    # the extension reaches the LISTED set whatever the case says, so
    # a one-case name flips too -- 1.4.0 read all three as suffixes
    assert _decided("JOHN SMITH, MA").structure is Structure.SUFFIX_COMMA
    assert _decided("john smith, ma").structure is Structure.SUFFIX_COMMA
    assert _decided("John Smith, Ed").structure is Structure.SUFFIX_COMMA
    assert _decided("Davis Royce, Ed").structure is Structure.SUFFIX_COMMA
    assert _decided("Royce, Ed").structure is Structure.FAMILY_COMMA


def test_structure_flips_for_a_by_shape_member_too() -> None:
    # #516: an unlisted dotted token joins the class the same way,
    # through the shape tags classify writes -- 'X.Y.Z.' is three
    # unclaimed single-letter chunks, not vocabulary at all, so this is
    # the by-shape twin of the test above. 'Smith Jr., X.Y.Z.' does not
    # flip for the SAME reason 'Smith Jr., MA' does not (#516 review
    # round: is_wholly_suffix must never admit the shape class, or
    # decide's whole-name suffix fallback would read it without the
    # NAME-word count, as segment's token-count disjunct once did on
    # 'Jr.').
    assert _decided("John Smith, X.Y.Z.").structure \
        is Structure.SUFFIX_COMMA
    assert _decided("Smith, X.Y.Z.").structure is Structure.FAMILY_COMMA
    assert _decided("Smith Jr., X.Y.Z.").structure \
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
                          ("García Márquez, G.J.", "García Márquez, Jr G.J."),
                          # a class member in front speaks for nothing,
                          # as S2's company has it; an unambiguous one does
                          ("García Márquez, Ma G.J.", "García Márquez, PhD G.J.")):
        assert _decided(alone).structure is Structure.FAMILY_COMMA, alone
        assert _decided(spoken).structure is Structure.SUFFIX_COMMA, spoken


def test_a_flip_no_listed_member_takes_part_in_is_silent() -> None:
    # rules.md#C1 (#563): a flip in which no listed member takes part
    # is silent, while a LISTED member in the same position still
    # reports the flip -- the control that keeps the silence from
    # being a lost emitter -- and so do paired initials spoken for
    # only by each other, each of them a word a reader takes for a
    # name. A pair beside a three-letter word, or behind PhD, is
    # spoken for by something else and stays silent.
    for text in ("John Smith, X.Y.Z.", "John Smith, B.Tech.",
                 "John Smith, X.Y.Z. P.D.Q.", "John Smith, PhD P.D.Q.",
                 "John Smith, X.Y.Z. G.J.", "John Smith, PhD G.J. K.L."):
        out = _decided(text)
        assert out.structure is Structure.SUFFIX_COMMA, text
        assert _flip_reports(out) == [], text
    for text in ("John Smith, Ma", "John Smith, PhD Ma",
                 "John Smith, X.Y.Z. MA", "De La Cruz, M.J. K.L.",
                 "John Smith, X.Y. P.Q."):
        out = _decided(text)
        assert out.structure is Structure.SUFFIX_COMMA, text
        assert _flip_reports(out) == [_texts(out, out.segments[1])], text


def test_the_structure_flip_reports_a_verbatim_detail() -> None:
    # The first report of the comma's OWN decision in the library
    # (#289): C2's structural flag already reports on the comma path,
    # but it reports what the parse could not recognize, not a fork
    # it called. P6's attachment fork has separately reported on a
    # family-comma path since 2.3 ("Berg, Jan vd"). Pinned verbatim so
    # a wording edit is a deliberate one,
    # not a silent drift the case table's looser `ambiguities=` tuple
    # check would never catch.
    state = _decided("John Smith, MA")
    (amb,) = [a for a in state.ambiguities
             if a.kind is AmbiguityKind.SUFFIX_OR_NAME]
    assert amb.detail == (
        "'MA' after the comma is also an ordinary name word; the part "
        "before the comma holds 2 name words, so it is read as a "
        "credential run")


def test_the_structure_flip_report_counts_the_real_pre_comma_words() -> None:
    # The count is INTERPOLATED, not a hardcoded "two": a three-word
    # pre-comma part reports its own count.
    state = _decided("John Q. Public, MA")
    (amb,) = [a for a in state.ambiguities
             if a.kind is AmbiguityKind.SUFFIX_OR_NAME]
    assert "holds 3 name words" in amb.detail


def test_the_name_word_count_reads_a_run_as_it_reads_one_word() -> None:
    # rules.md#C1 (#544): a part of two or more words, every one of
    # them suffix vocabulary or a class member and at least one a
    # member, reads by the same NAME-word count as the single token,
    # and the flip reports once, over the whole part.
    for text in ("John Smith, PhD Ma", "John Smith, Ed Ma",
                 "John Smith, Ma PhD", "john smith, phd ma",
                 "JOHN SMITH, PHD MA", "John Smith, MD Ma",
                 "John Smith, X.Y.Z. MA", "John Smith, Ph. D. Ma"):
        out = _decided(text)
        assert out.structure is Structure.SUFFIX_COMMA, text
        assert _flip_reports(out) == [_texts(out, out.segments[1])], text
    # one name word before the comma: the count leaves the family comma
    out = _decided("Smith, PhD Ma")
    assert out.structure is Structure.FAMILY_COMMA
    assert _decided("Smith Jr., PhD Ma").structure \
        is Structure.FAMILY_COMMA


def test_a_run_the_writing_settles_raises_no_flip_report() -> None:
    # every member written in capitals in a mixed-case name leans
    # credential (S2), so the part is the credential run on that
    # evidence rather than the count's: a suffix comma, and no flip
    # report. (Before #613 segment left this part to the listing form,
    # whose reading of a no-name part reached the same fields.)
    out = _decided("John Smith, PhD MA")
    assert out.structure is Structure.SUFFIX_COMMA
    assert not _flip_reports(out)
    assert out.one_case is False
    # the lean is the LISTED set's alone: a member admitted by SHAPE
    # is read by the count, capitals or not
    out = _decided("John Smith, X.Y.Z. MA")
    assert out.structure is Structure.SUFFIX_COMMA
    # and one Title-case member is enough to make it the count's call
    assert _decided("John Smith, MA Ed").structure \
        is Structure.SUFFIX_COMMA


def test_the_run_test_reads_a_delimiter_core_transparently() -> None:
    # without a delimiter policy the bare '-' is a word, which ends the
    # run; with the core configured behind a whole name it is no word
    # of the reading (#549, #613), so the two members either side of
    # it complete the run.
    text = "John Smith, Ma - Ed"
    assert _decided(text).structure is Structure.FAMILY_COMMA
    state = ParseState(
        original=text, lexicon=_LEX,
        policy=dataclasses.replace(
            Policy(), extra_suffix_delimiters=frozenset({" - "})))
    out = _comma.decide(classify(segment(tokenize(extract_delimited(state)))))
    assert out.structure is Structure.SUFFIX_COMMA


def test_the_run_test_reads_lenient_comma_suffixes() -> None:
    # rules.md#C1's leftovers ask `is_wholly_suffix`'s own POLICY-
    # selected predicate (#544): an
    # initial-shaped suffix WORD ('B.') that is not a single-letter
    # roman numeral is a member of neither the ambiguous class nor
    # `is_single_letter_numeral`'s carve-out, so it reaches `others` and
    # is read by `is_wholly_suffix` alone -- lenient by default (v1's
    # is_suffix_lenient bypasses the initial veto), strict under
    # Policy(lenient_comma_suffixes=False) (v1's is_suffix, which the
    # veto reads as a middle initial instead).
    lex = _LEX.add(suffix_words={"b"})
    text = "John Smith, Ma B."
    state = ParseState(original=text, lexicon=lex, policy=Policy())
    out = _comma.decide(classify(segment(tokenize(extract_delimited(state)))))
    assert out.structure is Structure.SUFFIX_COMMA
    state = ParseState(
        original=text, lexicon=lex,
        policy=dataclasses.replace(Policy(), lenient_comma_suffixes=False))
    out = _comma.decide(classify(segment(tokenize(extract_delimited(state)))))
    assert out.structure is Structure.FAMILY_COMMA


def test_one_word_before_the_comma_never_makes_a_suffix_comma() -> None:
    # v1: suffix-comma requires >1 word before the comma. The part
    # after it is still bound as the postnominal part, but the comma
    # stays the family comma naming the one word; a second word makes
    # it the suffix comma.
    out = _decided("Johnson, Jr.")
    assert out.structure is Structure.FAMILY_COMMA
    assert out.tokens[1].role is Role.SUFFIX
    assert _decided("John Johnson, Jr.").structure is Structure.SUFFIX_COMMA


def test_strict_comma_suffixes_veto_lenient_only_members() -> None:
    # lenient_comma_suffixes=False: the post-comma test drops back to
    # the strict predicate, so an initial-shaped suffix word no longer
    # qualifies, the part is not bound, and the comma stays the family
    # comma -- where the default reads 'John Ingram, V' as a suffix
    # comma (test_suffix_comma_lenient_accepts_initial_shaped_suffix_word)
    out = _decided("John Ingram, V", policy=dataclasses.replace(
        Policy(), lenient_comma_suffixes=False))
    assert out.structure is Structure.FAMILY_COMMA
    assert out.tokens[2].role is None


def test_the_run_test_declines_a_name_word_and_a_numeral() -> None:
    # a name word anywhere in the part, or a word that is neither
    # vocabulary nor a member, keeps the listing form -- and so does a
    # single-letter roman numeral, in any case, for its one-letter
    # shape (a multi-letter one runs: 'John Smith, III Ma')
    for text in ("John Smith, Jones Ma", "John Smith, V Ma",
                 "John Smith, J. Ma"):
        out = _decided(text)
        assert out.structure is Structure.FAMILY_COMMA, text
        assert not _flip_reports(out), text
    # a credential opening the part makes it the postnominal part
    # however it goes on (#603), but the run test still declines it:
    # no report spans the whole part as the count's flip does
    for text in ("John Smith, PhD Jones Ma", "John Smith, PhD v Ma"):
        out = _decided(text)
        assert out.structure is Structure.SUFFIX_COMMA, text
        assert _texts(out, out.segments[1]) not in _flip_reports(out), text
    out = _decided("John Smith, III Ma")
    assert _flip_reports(out) == [_texts(out, out.segments[1])]


def test_a_listed_surname_still_carries_the_name_contrast() -> None:
    # #564: a word a caller lists as a SURNAME is name text, so it
    # carries the contrast the comma caps reading needs
    # (`_vocab.claimed_as_non_name` leaves the surname and bound-given
    # lists out); `in_any_wordlist`, the caps shape's own "unlisted",
    # is a different question. A draft shared one predicate for both
    # and this read given 'XYZ'. The all-caps spelling is the control:
    # no word before the comma is written as a name, so no contrast.
    lex = Lexicon.default().add(surnames={"smith", "jones"})
    out = _decided("Smith Jones, XYZ", lexicon=lex)
    assert out.structure is Structure.SUFFIX_COMMA
    assert out.tokens[2].role is Role.SUFFIX
    assert _decided("SMITH JONES, XYZ", lexicon=lex).structure \
        is Structure.FAMILY_COMMA


def test_decide_hands_back_a_state_with_no_family_comma_unchanged() -> None:
    # group calls decide only on a family comma, but decide's contract
    # covers any state: a comma-less name, and a comma with nothing
    # after it, are returned as they came. Nothing BEFORE the comma is
    # not this exit -- ', Jr.' is read and bound, as the row below pins
    for text in ("John Smith", "Smith,, Jr."):
        state = classify(segment(tokenize(extract_delimited(ParseState(
            original=text, lexicon=_LEX, policy=Policy())))))
        assert _comma.decide(state) is state, text


def test_a_part_of_delimiter_cores_alone_decides_nothing() -> None:
    # behind a whole name a declared core is no word of the reading, so
    # a part holding nothing else has no reading to bind and keeps the
    # listing form (garbage in; pinned so the empty-part exit is held)
    policy = Policy(extra_suffix_delimiters=frozenset({" - "}))
    state = classify(segment(tokenize(extract_delimited(ParseState(
        original="John Smith, - -", lexicon=_LEX, policy=policy)))))
    decided = _comma.decide(state)
    assert decided is state
    assert decided.structure is Structure.FAMILY_COMMA


def test_an_empty_part_before_the_comma_still_reads_the_part_after_it() -> None:
    # #613 PR review: decide had returned early on an empty part before
    # the comma, leaving the credentials to the listing walk (', PhD'
    # read given 'PhD', ', Jr.' title 'Jr.', where 2.3.0 read suffix)
    for text, bound in ((", PhD", ["PhD"]), (", Jr.", ["Jr."]),
                        (", MD PhD", ["MD", "PhD"])):
        decided = _decided(text)
        assert decided.structure is Structure.FAMILY_COMMA, text
        assert [decided.tokens[i].text for i in decided.segments[1]
                if decided.tokens[i].role is Role.SUFFIX] == bound, text

"""rules/C1's decision, made at the head of group once classify has
tagged the words (#613): `_comma.decide`. These tests were segment's
until the decision moved; they run the stages up to classify and then
the decision, as group does."""
from nameparser import (
    FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, GIVEN_FIRST, Parser, parse,
)
from nameparser._lexicon import Lexicon
from nameparser._pipeline import _comma
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState, Structure
from nameparser._pipeline._tokenize import tokenize
import dataclasses

import pytest

from nameparser._policy import CapsSuffixes, Policy
from nameparser._types import AmbiguityKind, Role

# synthetic vocabulary: behavior given a lexicon, never default() contents
_LEX = (Lexicon()
        .add("phd", "md", "do", "dds", "ma", "ed", kind="credential")
        # a family reading makes the credential ambiguous
        .add("ma", "ed", "do", kind="family")
        .add("jr", "v", kind="suffix"))


def _decided(text: str, lexicon: Lexicon = _LEX,
             policy: Policy = Policy()) -> ParseState:
    state = ParseState(original=text, lexicon=lexicon, policy=policy)
    return _comma.decide(classify(segment(tokenize(extract_delimited(state)))))


def _texts(state: ParseState, seg: tuple[int, ...]) -> list[str]:
    return [state.tokens[i].text for i in seg]


def _part(state: ParseState) -> list[str]:
    """The part after the comma: decide empties its segment when it
    binds the part (#613's /simplify), so a bound part is read off the
    roles decide wrote, and a declined one off its segment."""
    if state.segments[1]:
        return _texts(state, state.segments[1])
    return [t.text for t in state.tokens
            if t.role in (Role.SUFFIX, Role.TITLE)]


def _flip_reports(state: ParseState) -> list[list[str]]:
    return [_texts(state, a.indices) for a in state.ambiguities
            if a.kind is AmbiguityKind.SUFFIX_OR_NAME]


def test_suffix_comma_when_all_rest_groups_are_suffixes() -> None:
    out = _decided("John Smith, PhD")
    assert out.structure is Structure.SUFFIX_COMMA
    assert (_texts(out, out.segments[0]), _part(out)) == (
        ["John", "Smith"], ["PhD"])


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
    assert (_texts(out, out.segments[0]), _part(out)) == (
        ["John", "Smith"], ["MA", "Ph.", "D."])


def test_structure_flips_for_the_ambiguous_class_on_a_name_word_count() -> None:
    # rules/C4 for the ambiguous class: two or more NAME words
    # before the comma read the part after it as the credential run.
    # 'John Smith, MA' flips; 'Smith Jr., MA' does not, having two
    # TOKENS and one name word -- which is what keeps Smith in the
    # family (#289, decisions/S6).
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
    # rules/C5 (#563): two dotted single letters are how a person's
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
                          # as S7's company has it; an unambiguous one does
                          ("García Márquez, Ma G.J.", "García Márquez, PhD G.J.")):
        assert _decided(alone).structure is Structure.FAMILY_COMMA, alone
        assert _decided(spoken).structure is Structure.SUFFIX_COMMA, spoken


def test_a_flip_no_listed_member_takes_part_in_is_silent() -> None:
    # rules/C11 (#563): a flip in which no listed member takes part
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
        assert _flip_reports(out) == [_part(out)], text


def test_the_structure_flip_reports_a_verbatim_detail() -> None:
    # The first report of the comma's OWN decision in the library
    # (#289): C2's structural flag already reports on the comma path,
    # but it reports what the parse could not recognize, not a fork
    # it called. P6's attachment fork has separately reported on a
    # family-comma path since 2.3 ("Berg, Jan vd"). Pinned verbatim so
    # a wording edit is a deliberate one,
    # not a silent drift the case table's looser `ambiguities=` tuple
    # check would never catch. In one case: capitals in a name of mixed
    # case settle the word and the flip reports nothing (rules/S6, #785).
    state = _decided("JOHN SMITH, MA")
    (amb,) = [a for a in state.ambiguities
             if a.kind is AmbiguityKind.SUFFIX_OR_NAME]
    assert amb.detail == (
        "'MA' after the comma is also an ordinary name word; the part "
        "before the comma holds 2 name words, so it is read as a "
        "credential run")


def test_the_structure_flip_report_counts_the_real_pre_comma_words() -> None:
    # The count is INTERPOLATED, not a hardcoded "two": a three-word
    # pre-comma part reports its own count.
    state = _decided("JOHN Q. PUBLIC, MA")
    (amb,) = [a for a in state.ambiguities
             if a.kind is AmbiguityKind.SUFFIX_OR_NAME]
    assert "holds 3 name words" in amb.detail


def test_the_name_word_count_reads_a_run_as_it_reads_one_word() -> None:
    # rules/C4 (#544): a part of two or more words, every one of
    # them suffix vocabulary or a class member and at least one a
    # member, reads by the same NAME-word count as the single token,
    # and the flip reports once, over the whole part.
    for text in ("John Smith, PhD Ma", "John Smith, Ed Ma",
                 "John Smith, Ma PhD", "john smith, phd ma",
                 "JOHN SMITH, PHD MA", "John Smith, MD Ma",
                 "John Smith, X.Y.Z. MA", "John Smith, Ph. D. Ma"):
        out = _decided(text)
        assert out.structure is Structure.SUFFIX_COMMA, text
        assert _flip_reports(out) == [_part(out)], text
    # one name word before the comma: the count leaves the family comma
    out = _decided("Smith, PhD Ma")
    assert out.structure is Structure.FAMILY_COMMA
    assert _decided("Smith Jr., PhD Ma").structure \
        is Structure.FAMILY_COMMA


def test_a_run_the_writing_settles_raises_no_flip_report() -> None:
    # every member written in capitals in a mixed-case name leans
    # credential (S6), so the part is the credential run on that
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
    # without a delimiter policy the bare '|' is a word, which ends the
    # run; with the core configured behind a whole name it is no word
    # of the reading (#549, #613), so the two members either side of
    # it complete the run. Not '-': a hyphen standing alone is a
    # built-in core (#889), as the next line shows.
    assert _decided("John Smith, Ma - Ed").structure \
        is Structure.SUFFIX_COMMA
    text = "John Smith, Ma | Ed"
    assert _decided(text).structure is Structure.FAMILY_COMMA
    state = ParseState(
        original=text, lexicon=_LEX,
        policy=dataclasses.replace(
            Policy(), extra_suffix_delimiters=frozenset({" | "})))
    out = _comma.decide(classify(segment(tokenize(extract_delimited(state)))))
    assert out.structure is Structure.SUFFIX_COMMA


def test_the_run_test_reads_lenient_comma_suffixes() -> None:
    # rules/C4's leftovers ask `is_wholly_suffix`'s own POLICY-
    # selected predicate (#544): an
    # initial-shaped suffix WORD ('B.') that is not a single-letter
    # roman numeral is a member of neither the ambiguous class nor
    # `is_single_letter_numeral`'s carve-out, so it reaches `others` and
    # is read by `is_wholly_suffix` alone -- lenient by default (v1's
    # is_suffix_lenient bypasses the initial veto), strict under
    # Policy(lenient_comma_suffixes=False) (v1's is_suffix, which the
    # veto reads as a middle initial instead).
    lex = _LEX.add("b", kind="suffix")
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
        assert _part(out) not in _flip_reports(out), text
    out = _decided("John Smith, III Ma")
    assert _flip_reports(out) == [_part(out)]


def test_a_listed_surname_still_carries_the_name_contrast() -> None:
    # #564: a word a caller lists as a SURNAME is name text, so it
    # carries the contrast the comma caps reading needs
    # (`_vocab.claimed_as_non_name` leaves the surname and bound-given
    # lists out); `in_any_wordlist`, the caps shape's own "unlisted",
    # is a different question. A draft shared one predicate for both
    # and this read given 'XYZ'. The all-caps spelling is the control:
    # no word before the comma is written as a name, so no contrast.
    lex = Lexicon.default() | Lexicon(surnames={"smith", "jones"})
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
    policy = Policy(extra_suffix_delimiters=frozenset({" | "}))
    state = classify(segment(tokenize(extract_delimited(ParseState(
        original="John Smith, | |", lexicon=_LEX, policy=policy)))))
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
        assert _part(decided) == bound, text


def test_a_bound_caps_word_keeps_its_capitals_in_case_repair() -> None:
    # decide writes the caps shape's marks on a word it binds (#564,
    # rules/R4), so case repair keeps the capitals -- also where the
    # run test declined and #603's opener bound the part anyway; the
    # marks had been cleared there, and 'XYZ' repaired to 'Xyz'
    # (#613's PR review). A name in one case carries no contrast.
    def repaired(text: str) -> str:
        return str(parse(text).capitalized(force=True))
    assert repaired("John Smith, XYZ") == "John Smith, XYZ"
    assert repaired("John Smith, PhD Jones XYZ") == \
        "John Smith, PhD Jones XYZ"
    assert repaired("JOHN SMITH, PhD JONES XYZ") == \
        "John Smith, PhD Jones Xyz"


def test_a_lone_core_after_the_comma_is_a_word_of_the_part() -> None:
    # the cores guard needs two tokens: a core alone is no delimiter
    # between suffixes, so it stays in the part (garbage in, pinned
    # because the guard reads so)
    policy = Policy(extra_suffix_delimiters=frozenset({" | "}))
    name = Parser(policy=policy).parse("John Smith, |")
    assert (name.given, name.family, name.suffix) == ("John", "Smith", "|")


def test_a_generational_connective_joins_no_title_after_the_comma() -> None:
    # P3's generational clause: a connective that is also
    # generational vocabulary joins only between two name words, and a
    # part read for credentials holds none, so the comma decision
    # freezes it as group freezes one with no name word beside it
    # (#617). The default class, 'i', is one letter, so the freeze
    # reaches it only in a run ('Rovira, Dr. i i', pinned by the
    # property grid's off-switch walk); a word of more letters shows
    # it in a plain join, which only caller vocabulary can spell. The
    # control is the same word as a plain connective, which joins the
    # titles.
    generational = (Lexicon.default().add("og", kind="conjunction")
                    .add("og", kind="suffix"))
    plain = Lexicon.default().add("og", kind="conjunction")
    name = Parser(lexicon=generational).parse("Smith, Mr. og Mrs.")
    assert (name.title, name.suffix) == ("Mr. Mrs.", "og")
    name = Parser(lexicon=plain).parse("Smith, Mr. og Mrs.")
    assert (name.title, name.suffix) == ("Mr. og Mrs.", "")


def test_a_split_member_opening_the_part_is_no_name_word_to_either_count() -> None:
    """rules/C3's opening suffix word excepts a split credential's
    member (rules/S12): `_members` finds it among classify's tags, and
    `name_word_count` leaves it out of the names behind the titles, as
    `_whole_name` leaves it out of the units -- the one-letter
    numeral's count (rules/C12) and the ambiguous class's (C4) alike."""
    from nameparser._pipeline._vocab import name_word_count
    lexicon, policy = Lexicon.default(), Policy()
    state = classify(segment(tokenize(extract_delimited(ParseState(
        original="Dr. MB ChB V, AD", lexicon=lexicon, policy=policy)))))
    front = state.segments[0][:-1]
    assert _texts(state, front) == ["Dr.", "MB", "ChB"]
    assert _comma._members(front, state.tokens) == {1}
    texts = _texts(state, front)
    assert name_word_count(texts, lexicon, policy, members={1}) == 1
    assert name_word_count(texts, lexicon, policy) == 2
    # the ambiguous class's count, which decide scans for inline
    # ("MB ChB, Ing" read suffix 'Ing' with the member counted)
    assert parse("MB ChB, Ing").given == "Ing"


# C3's numeral clause: a shape-only numeral ending the part before the
# comma counts as the listed 'III' does, and P3's three-word count asks
# the same of a name ending in one, or in one before its suffix words
# (#893). Each grid row is compared
# with its 'III' twin under all three orders.
_GENERATION_HEADS = ("Dumas {n}", "de la Vega {n}", "Ortega y Gasset {n}",
                     "John Dumas {n}", "(Bob) Dumas {n}", "Dr. Dumas {n}",
                     "Dumas {n} MD", "Dumas {n} Jr.", "Dumas {n} Sr.",
                     "Dumas {n} Ms")
_GENERATION_TAILS = (", Jr.", ", MA", ", PhD", ", Ed", ", Filho", ", John",
                     ", Dr.", ", AD", ", Jr., PhD", "", " MD", " Jr.",
                     " PhD")


@pytest.mark.parametrize("order", [GIVEN_FIRST, FAMILY_FIRST,
                                   FAMILY_FIRST_GIVEN_LAST])
@pytest.mark.parametrize("numeral", ["VI", "VI.", "IX", "vi"])
def test_a_shape_only_generation_reads_as_a_listed_one(
        numeral: str, order: tuple[Role, Role, Role]) -> None:
    parser = Parser(policy=Policy(name_order=order))
    moved: list[str] = []
    for head in _GENERATION_HEADS:
        for tail in _GENERATION_TAILS:
            text = head.format(n=numeral) + tail
            listed = parser.parse(head.format(n="III") + tail).as_dict()
            got = {k: v.replace(numeral, "III")
                   for k, v in parser.parse(text).as_dict().items()}
            if got != listed:
                moved.append(text)
    assert not moved


# C16's run of initials behind one word, read as the given name
# whatever it spells (#1238). Synthetic vocabulary: 'jp' and 'md'
# unambiguous credentials, 'ma' a credential with a family reading, 'bin'
# a particle that may be a given name.
_RUN_LEX = (Lexicon()
            .add("phd", "md", "jp", "ma", kind="credential", acronym=True)
            .add("ma", kind="family")
            .add("jr", kind="suffix")
            .add("de", "bin", kind="particle")
            .add("bin", kind="given")
            .add("dr", "knight", kind="title"))
_RUN_PARSER = Parser(lexicon=_RUN_LEX,
                     policy=Policy(segment_scripts=frozenset()))


@pytest.mark.parametrize(("text", "fields"), [
    # a listed run reads as an unlisted one does, whatever it spells
    ("Jansen, J.P.", {"given": "J.", "middle": "P.", "family": "Jansen"}),
    ("Jansen, M.A.", {"given": "M.", "middle": "A.", "family": "Jansen"}),
    # the suffix after a further comma stays the suffix
    ("Jansen, J.P., Jr.", {"given": "J.", "middle": "P.", "suffix": "Jr."}),
    # a title in front leaves it a name: the run is tagged an initial so
    # the given part's walk does not peel it as a trailing suffix
    ("Jansen, Dr. J.P.", {"title": "Dr.", "given": "J.", "middle": "P."}),
    # a particle written in lower case before a capitalized word is no
    # second name word
    ("de Waart, J.P.", {"given": "J.", "family": "de Waart"}),
    # a name written in one case parts its run as its capitals would
    ("jansen, j.p.", {"given": "j.", "middle": "p.", "family": "jansen"}),
    # a suffix word ending the head is no second word
    ("Jansen Jr., J.P.", {"given": "J.", "family": "Jansen",
                          "suffix": "Jr."}),
])
def test_a_listed_run_behind_one_name_word_is_the_given_name(
        text: str, fields: dict[str, str]) -> None:
    n = _RUN_PARSER.parse(text)
    assert {k: getattr(n, k) for k in fields} == fields
    # the decision is reported where it was taken, the credential its
    # other branch
    [report] = n.ambiguities
    assert report.kind is AmbiguityKind.SUFFIX_OR_NAME
    assert report.alternative is not None
    assert report.alternative.role is Role.SUFFIX
    # naming the run's own letters, which T7 parts
    assert [t.text for t in report.tokens] == [
        t.text for t in n.tokens if t.role in (Role.GIVEN, Role.MIDDLE)][:2]


@pytest.mark.parametrize(("text", "suffix"), [
    # two name words before the comma: C4's count reads the credential
    ("Jan Jansen, J.P.", "J.P."),
    # a capitalized particle that may be the given name counts as a word
    ("Bin Zhang, M.D.", "M.D."),
    # a head written all in lower case in a name of mixed case
    ("de jansen, M.D.", "M.D."),

    # every other word of the part a credential: C8's run
    ("Jansen, M.D. PhD", "M.D. PhD"),
    # a second listed run is company like any credential
    ("Jansen, J.P. M.A.", "J.P. M.A."),
    # a credential in front makes the run (the paired-initials Except)
    ("Jansen, PhD J.P.", "PhD J.P."),
    # lower case among capitals is no initials' writing, as rules/T7 has
    # it
    ("Jansen, j.p.", "j.p."),
    # undotted, the credential's own spelling
    ("Jansen, JP", "JP"),
])
def test_a_listed_run_stays_the_credential_outside_the_lone_word(
        text: str, suffix: str) -> None:
    n = _RUN_PARSER.parse(text)
    assert n.suffix == suffix
    # no letter of the run read as a name
    assert not any(t.role in (Role.GIVEN, Role.MIDDLE)
                   and "initial" in t.tags for t in n.tokens)


def test_a_word_the_count_leaves_out_is_a_word_as_written() -> None:
    # the default vocabulary's 'knight', a title C4's count does not
    # read as a name word: one word as written, the head is two, and the
    # part stays the credential run (ClinicalTrials.gov's officials)
    n = parse("Ashley Knight, M.S. BME")
    assert (n.given, n.family, n.suffix) == ("Ashley", "Knight", "M.S. BME")


def test_a_listed_run_behind_a_name_word_is_the_given_parts_to_read() -> None:
    # 'John' made the part the given part, so the run is not the one the
    # reading stopped at: it ends the given part as a credential, unreported
    n = _RUN_PARSER.parse("Jansen, John J.P.")
    assert (n.given, n.suffix, n.ambiguities) == ("John", "J.P.", ())


def test_a_run_holding_an_uncased_letter_is_no_initials() -> None:
    # 'J.씨' is a glued honorific, its second letter in a script with no
    # capitals: not every letter is one, so it is no run of initials
    n = parse("김민준씨, J.씨")
    assert (n.family, n.suffix) == ("김민준", "씨, J.씨")


def test_a_decomposed_run_reads_as_its_composed_twin() -> None:
    import unicodedata
    lex = _RUN_LEX.add("ép", kind="credential", acronym=True)
    p = Parser(lexicon=lex, policy=Policy(segment_scripts=frozenset()))
    composed = p.parse("Jansen, É.P.")
    decomposed = p.parse(unicodedata.normalize("NFD", "Jansen, É.P."))
    assert composed.given == "É."
    assert unicodedata.normalize("NFC", decomposed.given) == "É."


@pytest.mark.parametrize(("text", "given", "suffix"), [
    # a capitalized particle that is the whole head is one word
    ("Le, J.P.", "J.", ""),
    # a numeral of two or more letters ending the head is none, as C3
    # counts it
    ("Jansen VI, J.P.", "J.", "VI"),
    # only the suffix words ENDING the head are none: one in front of a
    # name word is a word, so the head is two (ClinicalTrials.gov)
    ("Dr.B. Akila., M.D", "Dr.B.", "M.D"),
    # a numeral is passed over only in capitals ('Vi' a surname), a
    # single letter never ('Smith V' a whole name, C1), and a title
    # alone is no surname
    ("Le Vi, M.D.", "", "M.D."),
    ("Smith V, M.D.", "Smith", "M.D."),
    ("Dr. VI, M.D.", "", "M.D."),
    # a generation behind the run is no company, nor a dual written as
    # a title rather than a credential
    ("Rinehart, J.D. Jr.", "J.", "Jr."),
    ("Smith, J.P. Ms.", "J.", "Ms."),
    # a capitals word is company only where C6 finds the name's contrast
    ("McDONALD, J.P. ANNE", "J.", ""),
    # a split credential and one of several words are company too
    ("Smith, J.P. Pharm D", "", "J.P. Pharm D"),
    ("Smith, J.P. Ph. D.", "", "J.P. Ph. D."),
    # a run of words that is no suffix piece is none
    ("Smith, J.P. Mr. and Mrs.", "J.", ""),
    # an empty or nickname-only head reads as C15 has it, as 'Smith, X'
    # less the surname, the company arm included
    (", J.P.", "J.", ""),
    ("(Jo), M.D.", "M.", ""),
    (", M.D. PhD", "", "M.D. PhD"),
    # a suffix word in front makes the run; a dual in front is a title,
    # as C5's paired initials read behind one
    ("Smith, Jr. J.P.", "", "Jr. J.P."),
    ("Smith, MS J.P.", "J.", ""),
    # a member of the ambiguous class behind the run is company; a
    # numeral by shape is none
    ("Jansen, J.P. MA", "", "J.P. MA"),
    ("Smith, M.D. VI", "M.", "VI"),
    # one case: a dual is company whatever its case, and the caps shape
    # has no contrast to ask
    ("smith, m.d. ms", "", "m.d. ms"),
    ("SMITH, M.D. FRCS", "M.", ""),
    # a title word that is the whole head is a surname ('Knight'); the
    # run needs no closing stop
    ("Knight, J.P.", "J.", ""),
    ("Smith, M.D", "M.", ""),
    # C10: a glued delimiter reads as a space in its place, as the
    # unlisted twin 'Smith, X.Q.;' reads
    ("Smith, J.P.;", "J.P.;", ""),
    # behind the run a title/suffix dual, a spaced delimiter and an
    # unlisted capitals credential C6 admits are company: C8's run
    ("Smith, M.D. MS", "", "M.D. MS"),
    ("Smith, M.D. / PhD", "", "M.D. / PhD"),
    ("Smith, M.D. FRCS", "", "M.D. FRCS"),
])
def test_a_listed_run_behind_one_word_in_the_default_vocabulary(
        text: str, given: str, suffix: str) -> None:
    n = parse(text)
    assert (n.given, n.suffix) == (given, suffix)


@pytest.mark.parametrize(("text", "caps", "suffix"), [
    # the caps shape decides whether an unlisted capitals word is company
    ("Smith, M.D. FRCS", CapsSuffixes.OFF, ""),
    ("McDONALD, J.P. ANNE", CapsSuffixes.EVERYWHERE, "J.P. ANNE"),
])
def test_the_caps_switch_reaches_the_runs_company(
        text: str, caps: CapsSuffixes, suffix: str) -> None:
    p = Parser(policy=Policy(unlisted_caps_suffixes=caps))
    assert p.parse(text).suffix == suffix


@pytest.mark.parametrize("policy", [
    Policy(lenient_comma_suffixes=False),
    Policy(unlisted_dotted_suffixes=False),
])
def test_the_comma_switches_leave_a_listed_run_the_given_name(
        policy: Policy) -> None:
    n = Parser(policy=policy).parse("Jansen, J.P.")
    assert (n.given, n.middle, n.suffix) == ("J.", "P.", "")


def test_a_listed_run_read_as_initials_matches_the_name_written_out() -> None:
    # the C16 parse reaches the name match as initials, as 'J. P.' does
    check = Parser().matching().check
    assert check("Jansen, J.P.", "Jan Pieter Jansen").consistent
    assert check("Jansen, J.P.", "J. P. Jansen").consistent

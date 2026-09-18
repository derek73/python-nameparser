import unicodedata

import pytest

from nameparser._lexicon import Lexicon, _normalize, _title_key
from nameparser._pipeline._vocab import (
    ambiguous_class_candidate, ambiguous_class_member, ambiguous_lean,
    effective_script, is_initial, is_initial_shaped, is_one_case,
    is_suffix_lenient, is_suffix_strict, is_title_shaped, is_wholly_suffix,
    maiden_marker_run, name_word_count, period_joined_vocab,
    resolve_script_set, single_script,
)
from nameparser._policy import (Policy, Script, _NO_INITIALS,
                                _SCRIPT_RANGES)

_LEX = Lexicon(
    suffix_acronyms=frozenset({"phd", "ma"}),
    suffix_words=frozenset({"jr", "v"}),
    suffix_acronyms_ambiguous=frozenset({"ma"}),
)


def test_is_initial() -> None:
    assert is_initial("A.")
    assert is_initial("j.")
    assert is_initial("B")
    assert not is_initial("Jo")
    assert not is_initial("b")  # bare lowercase letter is not an initial


def test_is_initial_script_repertoire() -> None:
    # An initial is a single LETTER standing in for a name. Alphabets
    # have letters, so these are real initials ("А. С. Пушкин").
    assert is_initial("А.")    # Cyrillic
    assert is_initial("Α.")    # Greek
    assert is_initial("م.")    # Arabic
    assert is_initial("ה.")    # Hebrew
    assert is_initial("र.")    # Devanagari
    assert is_initial("Ա.")    # Armenian
    # Han ideographs, hangul syllables and kana are morphemes or
    # syllables -- a single one never stands in for a name (#320).
    assert not is_initial("씨.")
    assert not is_initial("様.")
    assert not is_initial("김.")
    assert not is_initial("さ.")
    assert not is_initial("ラ.")
    # unchanged: a digit is ONE edge of \w's reach and '_' is another,
    # and the shape half still owns both -- only the repertoire narrowed
    assert is_initial("2.")
    assert is_initial("_.")
    # unchanged: the SHAPE half still requires a single character
    assert not is_initial("राम.")


@pytest.mark.parametrize("word", ["씨.", "씨．", "씨。", "씨｡",
                                  unicodedata.normalize("NFD", "씨.")])
def test_suffix_lookup_reads_every_full_stop(word: str) -> None:
    # #322: the four stops and NFD all reach the one stored entry.
    # is_initial stays False on every spelling: the initial veto is a
    # repertoire test on the raw text (#320) and the stop set does not
    # touch it.
    lex = Lexicon(suffix_words=frozenset({"씨"}))
    assert is_suffix_strict(word, lex)
    assert not is_initial(word)


def test_is_initial_shaped_keeps_the_shape_half_reachable() -> None:
    """The two halves are separately askable (#320): assign's
    roman-numeral fork asks the SHAPE question about the piece before a
    trailing 'V', and answering it with the narrowed predicate dropped
    the family name out of 'John 씨. V' entirely."""
    for text in ("A.", "j.", "B", "2."):
        assert is_initial_shaped(text) is is_initial(text) is True
    for text in ("Jo", "b", "raam."):
        assert is_initial_shaped(text) is is_initial(text) is False
    # the whole difference between them, in both directions
    for text in ("씨.", "様.", "김.", "さ.", "ラ."):
        assert is_initial_shaped(text) and not is_initial(text)


def test_strict_suffix_veto_skips_cjk() -> None:
    """#320: the initial veto is what stopped a period-written CJK
    honorific being recognized. _normalize strips the trailing period,
    so '씨.' reaches the vocabulary as '씨' -- the veto was the only
    thing rejecting it."""
    lex = Lexicon(suffix_words=frozenset({"씨", "様"}))
    assert is_suffix_strict("씨.", lex)
    assert is_suffix_strict("様.", lex)


def _representative(script: Script) -> str:
    """The first codepoint of `script`'s _SCRIPT_RANGES spans that the
    SHAPE half admits as an initial. Shape-admitted, not simply the
    first codepoint: a range's first codepoint is often unassigned or
    punctuation (KATAKANA's 0x30A0 is a hyphen, HIRAGANA's 0x3040 is
    unassigned), which \\w does not match -- and testing is_initial on
    such a character answers False for the SHAPE's reason, making the
    repertoire assertion below vacuously green. Raising when no span
    holds one is the point rather than a corner: a script whose
    declared ranges contain no initial-shaped character at all has
    ranges that do not describe it."""
    for lo, hi in _SCRIPT_RANGES[script]:
        for cp in range(lo, hi + 1):
            if is_initial_shaped(chr(cp) + "."):
                return chr(cp)
    raise AssertionError(
        f"no character in _SCRIPT_RANGES[{script}] is initial-SHAPED, "
        f"so this script's declaration cannot be tested against "
        f"is_initial -- check that the ranges are that script's")


def test_every_script_is_classified_for_initials() -> None:
    """A member joining Script must be classified here on purpose;
    _policy._NO_INITIALS carries the reasoning.

    The classification lives in this table rather than the assertion
    being `set(Script) == set(_NO_INITIALS)`: that passes trivially
    today, since all four current members are CJK, and the only way to
    green it again after adding a script would be to declare that
    script initial-less. That prejudges the answer. The point is to
    force a decision, not a particular one.

    Three bindings, not two: the table covers Script, the table's
    False rows are _NO_INITIALS, and -- the one that makes this a
    behavioral test rather than a comparison of two constants -- each
    row is checked against is_initial on a character DERIVED from that
    script's own _SCRIPT_RANGES entry. Without the third, a script
    declared initial-less under ranges that are not its own passes all
    the way through while is_initial still says yes to its characters.
    """
    has_initials = {
        Script.HAN: False,       # ideographs are morphemes
        Script.HANGUL: False,    # syllable blocks
        Script.HIRAGANA: False,  # syllables
        Script.KATAKANA: False,  # syllables
    }
    assert set(has_initials) == set(Script), (
        "a Script member is unclassified for initials: decide whether "
        "a single character of it can stand in for a name, add the row, "
        "and put it in _policy._NO_INITIALS if it cannot")
    assert {s for s, yes in has_initials.items() if not yes} \
        == set(_NO_INITIALS), (
        "this table and _policy._NO_INITIALS disagree about which "
        "scripts have initials: a row here saying False is what puts a "
        "script in the constant, so add the missing member to "
        "_NO_INITIALS -- or, if the constant is the one that's right, "
        "flip the row")
    for script, yes in has_initials.items():
        char = _representative(script)
        assert is_initial(char + ".") is yes, (
            f"the declaration for {script} does not reach is_initial: "
            f"the row says has_initials={yes}, but is_initial("
            f"{char + '.'!r}) -- on a character taken from "
            f"_SCRIPT_RANGES[{script}] -- says {not yes}. Either the "
            f"ranges are not this script's, or _NO_INITIALS and the "
            f"repertoire predicate have come apart")


def test_strict_suffix_initial_veto() -> None:
    assert is_suffix_strict("PhD", _LEX)
    assert not is_suffix_strict("V.", _LEX)   # initial veto
    assert not is_suffix_strict("V", _LEX)    # initial veto
    assert is_suffix_strict("Jr", _LEX)


def test_a_wide_stop_on_a_latin_word_reaches_the_vocabulary() -> None:
    # #322's unasked-for Latin reach, pinned rather than argued: the
    # fold strips all four FULL_STOPS off any word, while the initial
    # veto reads an ASCII-period pattern alone. So the WIDE spelling of
    # a Latin word gets past a veto its ASCII twin does not -- 'V。'
    # folds to 'v', is not initial-shaped, and reads as roman five,
    # where 'V.' stays a middle initial. 'Jr。' needs no veto argument
    # and simply reaches its entry.
    d = Lexicon.default()
    assert is_suffix_strict("Jr。", d)
    assert is_suffix_strict("V。", d)
    assert not is_suffix_strict("V.", d)


def test_ambiguous_acronym_needs_periods_and_beats_the_veto() -> None:
    assert is_suffix_strict("M.A.", _LEX)
    assert not is_suffix_strict("Ma", _LEX)


def test_lenient_accepts_suffix_words_unconditionally() -> None:
    assert is_suffix_lenient("V", _LEX)
    assert is_suffix_lenient("V.", _LEX)
    assert not is_suffix_lenient("Ma", _LEX)


def test_strict_excludes_bare_ambiguous_even_when_in_acronyms() -> None:
    # mirrors the real data shape: ambiguous is a SUBSET of acronyms
    assert not is_suffix_strict("Ma", _LEX)
    assert is_suffix_strict("M.A.", _LEX)


_SUFFIX_LEX = Lexicon(
    suffix_acronyms=frozenset({"phd", "md"}),
    suffix_words=frozenset({"jr", "v"}),
)


def test_is_wholly_suffix() -> None:
    lex, pol = _SUFFIX_LEX, Policy()
    assert is_wholly_suffix(["Jr."], lex, pol)
    assert is_wholly_suffix(["PhD", "Jr."], lex, pol)
    assert not is_wholly_suffix(["Smith"], lex, pol)
    assert not is_wholly_suffix(["PhD", "Smith"], lex, pol)
    # an adjacent Ph./D. pair is ONE unit. 'D.' is what makes the merge
    # load-bearing: it is not suffix vocabulary in ANY lexicon, so the
    # pair fails without the merge. ('Ph.' happens to fail alone here
    # too, but only because _SUFFIX_LEX is synthetic -- under
    # Lexicon.default(), 'ph' IS in suffix_acronyms.)
    assert is_wholly_suffix(["Ph.", "D."], lex, pol)
    assert not is_wholly_suffix(["Ph."], lex, pol)
    assert is_wholly_suffix(["Ph.", "D.", "Jr."], lex, pol)
    # and the pair is found wherever it sits, not only at the head of
    # the run: the merge walks the whole list. 'John Smith, Jr. Ph. D.'
    # is the reachable input -- restricted to position 0 the pair never
    # merges, 'D.' fails alone, and segment reads a FAMILY comma where
    # it should read a suffix comma.
    assert is_wholly_suffix(["Jr.", "Ph.", "D."], lex, pol)
    # the two routes that are neither the policy-selected predicate nor
    # the merge, each with the input that reaches ONLY it. Both die in
    # the v1 banks and the case table today, so a break here is
    # diagnosed a long way from its cause.
    assert is_wholly_suffix(["Lt.Jr."], lex, pol)        # period-joined
    assert not is_wholly_suffix(["Lt.Smith"], lex, pol)  # no suffix chunk
    delim = Policy(extra_suffix_delimiters=frozenset({"/"}))
    assert is_wholly_suffix(["PhD/MD"], lex, delim)      # delimiter split
    assert not is_wholly_suffix(["PhD/MD"], lex, pol)


def test_is_wholly_suffix_empty_run_is_false() -> None:
    """NOT vacuous truth, unlike Python's all() and unlike v1's
    are_suffixes. v1's suffix-comma detection fails on an empty
    parts[1] -- 'John Smith,, MD' is a family-comma parse -- and the
    'wholly' idiom agrees (_script_matcher(whole=True) requires
    non-empty too)."""
    assert not is_wholly_suffix([], _SUFFIX_LEX, Policy())


def test_is_wholly_suffix_is_not_the_plural_of_is_post_nominal() -> None:
    """The #319 bug in one assertion. _script_segment._is_post_nominal
    asks is_suffix_strict per token; this asks the POLICY-selected
    predicate over a run. 'V.' is the input that tells them apart: a
    suffix run, but not a post-nominal."""
    lex, pol = _SUFFIX_LEX, Policy()
    assert is_wholly_suffix(["V."], lex, pol)
    assert not is_suffix_strict("V.", lex)
    # and the knob moves it: under strict, 'V.' is name text
    assert not is_wholly_suffix(
        ["V."], lex, Policy(lenient_comma_suffixes=False))


def test_is_wholly_suffix_never_reads_the_by_shape_class() -> None:
    # #516 review round: an EARLIER version of this predicate admitted
    # a by-shape member unconditionally, bypassing both the lean and
    # the NAME-word count -- combined with C1's own legacy TOKEN-count
    # disjunct in _segment.py, that flipped 'Smith Jr., A.B.' to a
    # one-word given with a self-contradicting report. Proved by
    # mutation to be otherwise unreached, and dropped: the by-shape
    # class reaches the comma form only through
    # `ambiguous_class_candidate`, never through this predicate, on
    # or off.
    lex, pol = Lexicon.default(), Policy()
    assert not is_wholly_suffix(["A.B."], lex, pol)
    assert not is_wholly_suffix(
        ["A.B."], lex, Policy(unlisted_dotted_suffixes=False))
    # whole-token vocabulary is untouched either way -- it never went
    # through the shape branch this predicate lost
    assert is_wholly_suffix(["A.B.C."], lex, pol)
    assert is_wholly_suffix(["A.B.C."], lex,
                            Policy(unlisted_dotted_suffixes=False))


def test_is_wholly_suffix_reads_the_credential_lean() -> None:
    # The third reading site (#289): segment's structure decision and
    # its tail segments ask this, and 'Steven Hardman, MD, DO, DDS'
    # loses its comma-structure flag because 'DO' leans credential
    # here. A caller with nothing to say passes nothing and gets the
    # answer every release before this one gave.
    lex, pol = Lexicon.default(), Policy()
    assert not is_wholly_suffix(["DO"], lex, pol)
    assert is_wholly_suffix(["DO"], lex, pol, one_case=False)
    assert not is_wholly_suffix(["Do"], lex, pol, one_case=False)
    assert not is_wholly_suffix(["DO"], lex, pol, one_case=True)
    assert not is_wholly_suffix(["DO", "Smith"], lex, pol, one_case=False)


def test_ambiguous_class_member_is_the_comma_form_s_candidate() -> None:
    # The comma structure asks a different question from the lean: is
    # this token a member of the ambiguous class AT ALL, in any case?
    # -- because the count of NAME words before the comma is what
    # decides there, and it decides for the listed set too
    # ('JOHN SMITH, MA', 1.4.0 parity restored). Case-free: this
    # predicate takes no `one_case` at all, unlike the lean.
    lex = Lexicon.default()
    assert ambiguous_class_member("MA", lex)
    assert ambiguous_class_member("Ma", lex)
    assert ambiguous_class_member("ed", lex)
    assert not ambiguous_class_member("PhD", lex)
    assert not ambiguous_class_member("Smith", lex)
    # whole-token vocabulary wins over any shape reading
    assert not ambiguous_class_member("M.A.", lex)
    # a period ANYWHERE excludes membership here, deliberately
    # stricter than S2's own dotted-form test: the trailing-period
    # spelling still leans (ambiguous_lean('MA.', ...) reads as 'MA'
    # does) but reaches the comma slot through the TAG path, not this
    # predicate, which only the comma-form's own candidate check and
    # the credential-lean disjunct in is_wholly_suffix consult.
    assert not ambiguous_class_member("MA.", lex)
    assert not ambiguous_class_member("Ed.", lex)


def test_period_joined_vocab_retires_the_single_character_chunk() -> None:
    # #516, NARROWLY: the chunk rule survives except where every chunk
    # the vocabulary matches is a single ASCII character, which is the
    # roman numeral reaching a word that is not about generations at
    # all. CHARACTER because '2' is a digit and in the set, ASCII
    # because '씨' is the one that must KEEP its claim. The roster
    # itself is asserted below, not just described, so a future
    # vocabulary change cannot silently drift this test's premise.
    lex = Lexicon.default()
    assert {c for c in lex.suffix_acronyms | lex.suffix_words
            if len(c) == 1 and c.isascii()} == {"2", "i", "v"}
    assert period_joined_vocab("R.A.I.", lex) == "shape"
    assert period_joined_vocab("X.Y.I.", lex) == "shape"
    assert period_joined_vocab("J.u.n.i.o.r.", lex) == "shape"
    assert period_joined_vocab("Msc.Ed.", lex) == "suffix"   # 'ed', two chars
    assert period_joined_vocab("JD.CPA", lex) == "suffix"
    assert period_joined_vocab("J.씨", lex) == "suffix"       # not ASCII
    assert period_joined_vocab("Lt.Gov.", lex) == "title"     # title wins
    # the shape itself: two or more chunks nothing claims
    assert period_joined_vocab("X.Y.Z.", lex) == "shape"
    assert period_joined_vocab("B.Tech.", lex) == "shape"
    assert period_joined_vocab("Q.W.E.R.T.", lex) == "shape"
    assert period_joined_vocab("E.S.Q.", lex) == "shape"
    # one trailing period is not the shape, and never was
    assert period_joined_vocab("Xyz.", lex) is None
    # a bare digit chunk is never an acronym by shape either
    assert period_joined_vocab("1.4", lex) is None
    # nor is a CJK word glued into period-separated single characters:
    # a script with no period abbreviations at all has nothing for
    # interior periods to abbreviate (#323's reasoning, shared with
    # is_title_shaped)
    assert period_joined_vocab("田.中.", lex) is None
    assert period_joined_vocab("이.박.", lex) is None
    assert period_joined_vocab("たな.か.", lex) is None


def test_ambiguous_class_candidate_admits_a_by_shape_member() -> None:
    # #516: the comma form's own candidate test reaches a by-shape
    # member too, once Policy admits it -- case-free either way, the
    # periods being the whole signal.
    lex, pol = Lexicon.default(), Policy()
    assert ambiguous_class_candidate("A.B.", lex, pol)
    assert ambiguous_class_candidate("MA", lex, pol)      # listed, unaffected
    assert not ambiguous_class_candidate(
        "A.B.", lex, Policy(unlisted_dotted_suffixes=False))
    # whole-token vocabulary wins over the shape reading here too
    assert not ambiguous_class_candidate("A.B.C.", lex, pol)
    assert not ambiguous_class_candidate("M.A.", lex, pol)
    assert not ambiguous_class_candidate("Smith", lex, pol)


def test_is_title_shaped_is_h2_s_shape_alone() -> None:
    # Shared with _pieces.is_leading_title's own inline copy
    # (#289/#516, quality-review finding): both must answer alike for
    # name_word_count's comma-form count not to disagree with the
    # leading peel about what a title is.
    assert is_title_shaped("Xyz.")       # unlisted, H2-shaped
    # LISTED or not is a vocabulary question this predicate never
    # asks -- 'Dr.' wears the same shape 'Xyz.' does, and answers the
    # same way; the caller's own listed lookup is what tells them
    # apart (is_title_piece/lexicon.titles, at each call site)
    assert is_title_shaped("Dr.")
    assert not is_title_shaped("Xyz")    # no trailing period
    assert not is_title_shaped("X.")     # one letter: an initial,
                                        # not an abbreviation
    assert not is_title_shaped("田中.")   # initialless script (#323)


def test_name_word_count_counts_names_not_tokens() -> None:
    # rules.md#C1's count for the ambiguous class: 'Smith Jr.' is two
    # tokens and ONE name word, which is what keeps its family where a
    # token count would hand it to `given`.
    lex, pol = Lexicon.default(), Policy()
    assert name_word_count(["John", "Smith"], lex, pol) == 2
    assert name_word_count(["Smith", "Jr."], lex, pol) == 1
    assert name_word_count(["Dr.", "Smith"], lex, pol) == 1
    assert name_word_count(["Davis", "Royce"], lex, pol) == 2
    assert name_word_count(["Royce"], lex, pol) == 1
    # #289/#516, quality-review finding: the title half asks H2's
    # shape test too, not just the listed lookup -- an UNLISTED
    # period-marked opener now counts the way a LISTED one does
    # ('Xyz.' beside 'Dr.', both 1), where before this it counted as
    # a plain name word and could flip a comma structure a listed
    # title of the same shape would not.
    assert name_word_count(["Xyz.", "Smith"], lex, pol) == 1


# Stored form: space-joined, per-word normalized -- what _normset
# writes for this field. Built as bare frozensets rather than through a
# Lexicon so these exercise the predicate and nothing else.
_WORD_ONLY = frozenset({"née"})
_PHRASE = frozenset({"z domu"})
_BOTH = frozenset({"geb", "geb von"})


def test_maiden_marker_run_has_nothing_to_claim() -> None:
    assert maiden_marker_run([], _WORD_ONLY) == 0
    assert maiden_marker_run(["née", "Jones"], frozenset()) == 0
    assert maiden_marker_run(["Smith", "Jones"], _WORD_ONLY) == 0


def test_maiden_marker_run_claims_one_word() -> None:
    assert maiden_marker_run(["née", "Jones"], _WORD_ONLY) == 1
    # the marker alone is still a run of one; the caller decides
    # whether a word has to follow it
    assert maiden_marker_run(["née"], _WORD_ONLY) == 1


def test_maiden_marker_run_claims_a_phrase() -> None:
    assert maiden_marker_run(["z", "domu", "Nowak"], _PHRASE) == 2


def test_maiden_marker_run_takes_the_longest_match_first() -> None:
    # A caller configuring both a word and a phrase starting with it
    # gets the phrase where it matches and the bare word everywhere
    # else. Shortest-first would claim 'geb' and leave 'von' a name
    # word.
    assert maiden_marker_run(["geb", "von", "Braun"], _BOTH) == 2
    assert maiden_marker_run(["geb", "Braun"], _BOTH) == 1


def test_maiden_marker_run_declines_a_partial_phrase() -> None:
    # 'z' alone is not a marker -- the whole point of shipping the
    # phrase rather than its words. This is the reading the library's
    # own split-it-into-separate-entries advice produced.
    assert maiden_marker_run(["z", "Nowak"], _PHRASE) == 0
    # and a phrase with nothing after its first word cannot match either
    assert maiden_marker_run(["z"], _PHRASE) == 0


def test_maiden_marker_run_folds_per_word() -> None:
    # _title_key's storage rule, rebuilt at match time: case folds, and
    # each word loses its own edge periods. Normalizing the JOINED
    # phrase would leave 'z.' with its period and never match.
    assert maiden_marker_run(["Z", "Domu", "Nowak"], _PHRASE) == 2
    assert maiden_marker_run(["z", "domu.", "Nowak"], _PHRASE) == 2
    assert maiden_marker_run(["z.", "domu", "Nowak"], _PHRASE) == 2


@pytest.mark.parametrize("words", [
    ("z", "domu"), ("Z.", "Domu"), ("née",), ("née", "."), (".", "z"),
    ("z", "", "domu"), ("GEB", "VON"), (),
])
def test_the_marker_key_is_title_keys_own_fold(words: tuple[str, ...]) -> None:
    """maiden_marker_run builds its lookup key inline so each word is
    folded once rather than once per candidate length. That makes it a
    COPY of a fold whose definition lives in _lexicon, and this is the
    pin that keeps the copy honest: change _title_key and this fails
    rather than the entry quietly ceasing to match."""
    assert " ".join(filter(None, (_normalize(w) for w in words))) \
        == _title_key(words)


def test_maiden_marker_run_does_not_claim_a_word_that_folds_away() -> None:
    # _title_key drops a word that normalizes to nothing, so ['née',
    # '.'] keys as 'née' -- a one-word entry would match a two-word
    # run and the drop would take the period with it.
    assert maiden_marker_run(["née", "."], _WORD_ONLY) == 1
    # and a word that folds away cannot OPEN a run either -- the
    # question the head fast path has to answer the same way the loop
    # would
    assert maiden_marker_run([".", "née"], _WORD_ONLY) == 0
    assert maiden_marker_run([".", "z", "domu"], _PHRASE) == 0


def test_single_script_requires_every_char_in_one_script() -> None:
    assert single_script("毛泽东") is Script.HAN
    assert single_script("諸葛") is Script.HAN          # traditional
    assert single_script("김민준") is Script.HANGUL
    assert single_script("Smith") is None
    assert single_script("毛zedong") is None            # mixed
    assert single_script("毛김") is None                 # mixed CJK
    # kana classifies as its own script (#272), not HAN -- was None
    # before kana had a table entry; single_script's job is telling
    # kana apart from Han, not lumping the two together
    assert single_script("イチロー") is Script.KATAKANA


def test_single_script_range_edges() -> None:
    # one char at each declared bound, and a neighbour outside
    assert single_script("㐀") is Script.HAN    # Ext A first
    assert single_script("䶿") is Script.HAN    # Ext A last
    assert single_script("䷀") is None          # hexagram, not Han
    # U+F900 is a COMPATIBILITY ideograph; it renders identically to
    # the URO 豈 (U+8C48) it decomposes to, so spell it as an escape
    # or this assertion silently tests the URO range instead
    assert single_script("\uf900") is Script.HAN
    assert single_script("\U00020bb7") is Script.HAN  # Ext B (𠮷)
    assert single_script("가") is Script.HANGUL
    assert single_script("힣") is Script.HANGUL  # last ASSIGNED syllable
    assert single_script("ힰ") is None          # jungseong, not a syllable
    assert single_script("ㄱ") is None          # bare jamo


def test_single_script_empty_string_is_no_script() -> None:
    assert single_script("") is None


def test_no_script_range_reaches_ascii() -> None:
    # single_script short-circuits on an ASCII token instead of
    # sweeping the ranges (the hot path: every Latin name). The
    # classifications above stay pinned either way; what the shortcut
    # rests on is this floor, so a future script entry that dips below
    # it fails here rather than silently going unclassified.
    assert all(lo >= 0x80
               for ranges in _SCRIPT_RANGES.values() for lo, _ in ranges)


def test_kana_singles_classify() -> None:
    assert single_script("みなみ") is Script.HIRAGANA
    assert single_script("エミ") is Script.KATAKANA
    assert single_script("ー") is Script.KATAKANA   # prolonged mark, in-block


def test_effective_script_kana_license() -> None:
    # pure single-script tokens pass through unchanged
    assert effective_script("山田") is Script.HAN
    assert effective_script("みなみ") is Script.HIRAGANA
    assert effective_script("マイケル") is Script.KATAKANA
    # the license: a MIXED token wholly in Han∪kana is Japanese and
    # resolves to the HIRAGANA carrier entry
    assert effective_script("高橋みなみ") is Script.HIRAGANA  # kanji+hira
    assert effective_script("山田エミ") is Script.HIRAGANA    # kanji+kata
    assert effective_script("さくらエミ") is Script.HIRAGANA  # hira+kata
    # outside the license: anything beyond the JA repertoire
    assert effective_script("毛김") is None
    assert effective_script("山田x") is None
    # NOT None: U+30FB sits INSIDE the katakana block (verified by
    # codepoint), so this stays a PURE-katakana token, same as
    # "マイケル" above -- the license only ever fires on a MIXED
    # token, and this one isn't mixed. It has no order-default entry
    # (DEFAULT_SCRIPT_ORDERS carries no KATAKANA key), which is where
    # "declines the license" actually shows up. tokenize (#272 Task 2b)
    # now turns U+30FB into a token separator, so this exact string
    # arrives at effective_script as two tokens during a real parse --
    # this unit test calls effective_script directly on the whole
    # string, bypassing tokenize, so it still sees the dot and must
    # keep passing unchanged.
    assert effective_script("マイケル・ジャクソン") is Script.KATAKANA
    assert effective_script("") is None


def test_script_classification_ignores_edge_full_stops() -> None:
    # #323: a period glued to a script-written token is not part of
    # its script and must not remove the token from classification --
    # the surname site, the order rule and the segmenter's neighbour
    # precondition all read this answer. Each of the four stops
    # trailing; the remainder still has to be classifiable on its own.
    assert effective_script("양.") is Script.HANGUL
    assert effective_script("양．") is Script.HANGUL
    assert effective_script("양。") is Script.HANGUL
    assert effective_script("양｡") is Script.HANGUL
    # TRAILING ONLY, and each of the four leading pins it. This fold
    # feeds the two division sites, which index a word from its start,
    # so a leading stop is the one edge classification must not hide:
    # classified, '.김민준' becomes a surname site whose head match
    # (rstrip, so it never matches through a leading stop) declines,
    # and a configured segmenter is then handed the raw token and can
    # answer offset 1 -- '.' as the given name, the name as the family.
    # No script means no site, which is the pre-#323 reading and the
    # no-split rules.md#W1 already accepts.
    assert effective_script(".양") is None
    assert effective_script("．양") is None
    assert effective_script("。양") is None
    assert effective_script("｡양") is None
    assert single_script("太郎.") is Script.HAN
    assert effective_script("高橋みなみ。") is Script.HIRAGANA  # license survives
    # nothing left, or ASCII left: no script, as before
    assert effective_script(".") is None
    assert effective_script("。") is None
    assert effective_script("abc。") is None
    assert single_script("Smith.") is None


def test_resolve_script_set_generalizes_the_license_across_pieces() -> None:
    # a single script passes through as-is, including a script with no
    # order-default entry (KATAKANA): the caller decides what to do
    # with that, this function only reports what was found
    assert resolve_script_set([Script.HAN]) is Script.HAN
    assert resolve_script_set([Script.HAN, Script.HAN]) is Script.HAN
    assert resolve_script_set([Script.KATAKANA]) is Script.KATAKANA
    # the license, generalized: Han + Hiragana across two SEPARATE,
    # individually single-script pieces (never mixed within one
    # token) is exactly the repertoire effective_script licenses
    # inside a single token, so it collapses to the carrier key
    assert resolve_script_set([Script.HAN, Script.HIRAGANA]) \
        is Script.HIRAGANA
    assert resolve_script_set([Script.HAN, Script.KATAKANA]) \
        is Script.HIRAGANA
    assert resolve_script_set([Script.HIRAGANA, Script.KATAKANA]) \
        is Script.HIRAGANA
    # outside the license: Han+Hangul is two real scripts, neither
    # kana -- no single tradition, so this declines like the caller's
    # own None (Latin, mixed, empty)
    assert resolve_script_set([Script.HAN, Script.HANGUL]) is None
    assert resolve_script_set([]) is None


def test_nfd_katakana_still_classifies_and_declines_the_license() -> None:
    # Built via normalize(), never pasted as decomposed literals --
    # NFD "ガガ" is base katakana カ + COMBINING VOICED SOUND MARK
    # (U+3099) twice; U+3099 sits in the HIRAGANA block, not
    # katakana's, so classifying raw NFD text would see one char from
    # each block and either call it mixed (single_script: None) or
    # wrongly grant the kana license (effective_script: HIRAGANA) for
    # what is really one pure-katakana token. NFC-normalizing first
    # (the #272 amendment's NFC decision) recomposes it back to ガガ,
    # which reads as ordinary katakana either way -- the license
    # still correctly declines, because this token isn't mixed.
    nfd = unicodedata.normalize("NFD", "ガガ")
    assert nfd != "ガガ"  # sanity: confirms the decomposition actually ran
    assert single_script(nfd) is Script.KATAKANA
    assert effective_script(nfd) is Script.KATAKANA


def test_nfd_hangul_still_classifies() -> None:
    # NFD decomposes each precomposed syllable onto 2-3 jamo
    # (U+1100-U+11FF), entirely outside the HANGUL range -- raw NFD
    # input would silently miss the shipped family-first order rule
    # rather than merely misclassify. Built via normalize(), not
    # pasted decomposed literals, same reason as above.
    nfd = unicodedata.normalize("NFD", "김민준")
    assert nfd != "김민준"  # sanity: confirms the decomposition actually ran
    assert single_script(nfd) is Script.HANGUL


def test_script_ranges_are_pairwise_disjoint() -> None:
    # The table's own comment states this invariant and nothing
    # checked it: single_script returns the FIRST covering entry (dict
    # iteration order), so any overlap would make the answer depend on
    # declaration order instead of being well-defined. Compared over
    # every entry of every script rather than script by script,
    # because the adjacent blocks are exactly where a future edit
    # would go wrong -- HIRAGANA ends at U+309F and KATAKANA opens at
    # U+30A0 with no gap at all, and HAN's U+3005-U+3006 span sits just
    # below both.
    spans = [(lo, hi, script)
             for script, ranges in _SCRIPT_RANGES.items()
             for lo, hi in ranges]
    assert len(spans) > 1        # never passes vacuously
    for i, (lo, hi, script) in enumerate(spans):
        assert lo <= hi, f"{script} range ({lo:#x}, {hi:#x}) is inverted"
        for other_lo, other_hi, other in spans[i + 1:]:
            assert hi < other_lo or other_hi < lo, (
                f"{script} range ({lo:#x}, {hi:#x}) overlaps {other} "
                f"range ({other_lo:#x}, {other_hi:#x})")


def test_is_one_case() -> None:
    assert is_one_case(["jose", "e", "maria", "santos"])
    assert is_one_case(["JOSE", "E", "MARIA", "SANTOS"])
    assert not is_one_case(["Jose", "e", "Maria", "Santos"])
    assert not is_one_case(["john", "e", "jones", "III"])
    # a caseless script is "one case" harmlessly: the fork that reads
    # this ALSO requires a cased token, so a caseless letter never
    # enters it (rules.md#P3, decisions.md#P3)
    assert is_one_case(["محمد", "و", "علي"])
    assert is_one_case(["山田", "太郎"])
    # the empty and single-token edges
    assert is_one_case([])
    assert is_one_case(["e"])
    # the comparison is over the SPACE-JOINED text, R5's own gate, so a
    # token that is caseless does not break a Latin name's verdict
    assert is_one_case(["john", "e", "山田"])
    assert not is_one_case(["John", "e", "山田"])


def test_ambiguous_lean_reads_the_written_case() -> None:
    # #289: in a name written in more than one case, an all-caps
    # member of the ambiguous set leans CREDENTIAL and a member in any
    # other cased form that is not wholly lower leans SURNAME. A
    # lowercase member carries no lean, and neither does anything at
    # all in a one-case name -- both fall through to today's count.
    assert ambiguous_lean("MA", one_case=False) == "credential"
    assert ambiguous_lean("Ma", one_case=False) == "name"
    assert ambiguous_lean("ma", one_case=False) is None
    assert ambiguous_lean("MA", one_case=True) is None
    assert ambiguous_lean("Ma", one_case=True) is None
    # a trailing period is not the signal and does not disturb one:
    # 'MA.' is still written in capitals ('.' has no case)
    assert ambiguous_lean("MA.", one_case=False) == "credential"
    assert ambiguous_lean("Ma.", one_case=False) == "name"
    # a caseless token can be written against nothing, so it leans
    # neither way even where the name around it is mixed
    assert ambiguous_lean("씨", one_case=False) is None
    assert ambiguous_lean("毛", one_case=False) is None

from nameparser._lexicon import Lexicon
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import Policy

_LEX = Lexicon(
    titles=frozenset({"dr", "sir"}),
    given_name_titles=frozenset({"sir"}),
    suffix_acronyms=frozenset({"phd", "ma"}),
    suffix_words=frozenset({"jr", "v"}),
    suffix_acronyms_ambiguous=frozenset({"ma"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
    # й is COPIED from the shipped conjunctions (Ukrainian, #267) so the
    # collision test_cyrillic_initial_outranks_the_conjunction pins is
    # one that really ships and the reader can check against the
    # defaults. The copy is local: this file never reads the shipped set
    conjunctions=frozenset({"and", "y", "й"}),
    bound_given_names=frozenset({"abdul"}),
    maiden_markers=frozenset({"née"}),
)


def _classified(text: str) -> ParseState:
    state = ParseState(original=text, lexicon=_LEX, policy=Policy())
    return classify(segment(tokenize(extract_delimited(state))))


def _tags(state: ParseState, text: str) -> frozenset[str]:
    return next(t.tags for t in state.tokens if t.text == text)


def test_vocabulary_tags() -> None:
    out = _classified("Dr. van de la Smith and abdul née PhD Jr")
    assert "vocab:title" in _tags(out, "Dr.")
    assert {"particle", "vocab:particle-ambiguous"} <= _tags(out, "van")
    assert "particle" in _tags(out, "de")
    assert "vocab:particle-ambiguous" not in _tags(out, "de")
    assert "conjunction" in _tags(out, "and")
    assert "vocab:bound-given" in _tags(out, "abdul")
    assert "vocab:maiden-marker" in _tags(out, "née")
    assert "vocab:suffix" in _tags(out, "PhD")
    assert {"vocab:suffix", "vocab:suffix-word"} <= _tags(out, "Jr")
    assert _tags(out, "Smith") == frozenset()


def test_given_title_tag() -> None:
    out = _classified("Sir John")
    assert {"vocab:title", "vocab:given-title"} <= _tags(out, "Sir")


def test_initial_tag() -> None:
    out = _classified("John A. B Smith")
    assert "initial" in _tags(out, "A.")
    assert "initial" in _tags(out, "B")
    assert "initial" not in _tags(out, "John")


def test_cyrillic_initial_outranks_the_conjunction() -> None:
    """#320 regression. 'й' is the Ukrainian conjunction (#267); 'Й.'
    is an initial and must not be read as it. Narrowing is_initial to
    [A-Za-z] -- the fix #320 originally proposed -- flips this token to
    'conjunction' and strips 'initial' off every Cyrillic, Greek,
    Arabic, Hebrew, Devanagari and Armenian initial (the six
    test_vocab.test_is_initial_script_repertoire asserts). Neither
    moves field output on a short name, so this asserts the TAG. _LEX
    copies й from the SHIPPED conjunctions so the collision is a real
    one -- but the copy is local, so this test would keep passing if й
    were dropped from the defaults."""
    out = _classified("Й. Сліпий")
    assert "initial" in _tags(out, "Й.")
    assert "conjunction" not in _tags(out, "Й.")


def test_ambiguous_suffix_acronym_needs_periods() -> None:
    out = _classified("M.A. Ma")
    assert "vocab:suffix" in _tags(out, "M.A.")
    assert "vocab:suffix" not in _tags(out, "Ma")
    assert "vocab:suffix-ambiguous" in _tags(out, "Ma")


def test_v_is_suffix_word_and_initial() -> None:
    # both tags present; assign applies the veto, not classify
    out = _classified("John V Smith")
    assert {"vocab:suffix", "vocab:suffix-word", "initial"} <= _tags(out, "V")


def test_bare_ambiguous_acronym_in_acronyms_is_not_suffix() -> None:
    # the default lexicon has suffix_acronyms_ambiguous SUBSET OF
    # suffix_acronyms (v1 data shape); the plain membership test must
    # exclude the ambiguous members or the period gate is dead code
    # and bare 'Ed'/'Jd' silently become suffixes (PR review C1)
    out = _classified("Ma M.A.")
    assert "vocab:suffix" not in _tags(out, "Ma")
    assert "vocab:suffix" in _tags(out, "M.A.")

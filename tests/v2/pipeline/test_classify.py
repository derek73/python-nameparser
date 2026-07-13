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
    suffix_acronyms=frozenset({"phd"}),
    suffix_words=frozenset({"jr", "v"}),
    suffix_acronyms_ambiguous=frozenset({"ma"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
    conjunctions=frozenset({"and", "y"}),
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


def test_ambiguous_suffix_acronym_needs_periods() -> None:
    out = _classified("M.A. Ma")
    assert "vocab:suffix" in _tags(out, "M.A.")
    assert "vocab:suffix" not in _tags(out, "Ma")
    assert "vocab:suffix-ambiguous" in _tags(out, "Ma")


def test_v_is_suffix_word_and_initial() -> None:
    # both tags present; assign applies the veto, not classify
    out = _classified("John V Smith")
    assert {"vocab:suffix", "vocab:suffix-word", "initial"} <= _tags(out, "V")

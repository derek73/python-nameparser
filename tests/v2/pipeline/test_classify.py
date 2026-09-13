import dataclasses

from nameparser._lexicon import Lexicon
from nameparser._pipeline._classify import classify
from nameparser._pipeline._extract import extract_delimited
from nameparser._pipeline._segment import segment
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._tokenize import tokenize
from nameparser._policy import Policy
from nameparser._types import AmbiguityKind, Role

_LEX = Lexicon(
    titles=frozenset({"dr", "sir"}),
    given_name_titles=frozenset({"sir"}),
    suffix_acronyms=frozenset({"phd", "ma"}),
    suffix_words=frozenset({"jr", "v"}),
    suffix_acronyms_ambiguous=frozenset({"ma"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
    # 'e' and 'y' are both shipped single-letter conjunctions and the
    # fork treats them differently, which is the whole point of the
    # subset; й is COPIED from the shipped conjunctions (Ukrainian,
    # #267) so the collision
    # test_cyrillic_initial_outranks_the_conjunction pins is one that
    # really ships and the reader can check against the defaults. The
    # copies are local: this file never reads the shipped sets.
    conjunctions=frozenset({"and", "e", "y", "й"}),
    conjunctions_ambiguous=frozenset({"e"}),
    bound_given_names=frozenset({"abdul"}),
    maiden_markers=frozenset({"née"}),
)


def _classified_with(text: str, lexicon: Lexicon) -> ParseState:
    state = ParseState(original=text, lexicon=lexicon, policy=Policy())
    return classify(segment(tokenize(extract_delimited(state))))


def _classified(text: str) -> ParseState:
    return _classified_with(text, _LEX)


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


def test_one_case_subset_member_is_an_initial_and_reports() -> None:
    # rules.md#P3 says a one-case name carries no case evidence, so
    # the vocabulary decides, and 'e' is marked as reading both ways.
    # (No colon after the rule id on purpose: tests/ is swept by
    # test_doc_citations.py, and the colon form must quote the rule
    # verbatim and puts this file on P3's implemented: list.)
    for text in ("jose e maria santos", "JOSE E MARIA SANTOS"):
        out = _classified(text)
        letter = "e" if text.islower() else "E"
        assert "initial" in _tags(out, letter), text
        assert "conjunction" not in _tags(out, letter), text
        kinds = [a.kind for a in out.ambiguities]
        assert kinds == [AmbiguityKind.CONJUNCTION_OR_INITIAL], text
        assert out.ambiguities[0].indices == (1,), text
        assert repr(letter) in out.ambiguities[0].detail, text


def test_one_case_non_member_joins_even_as_a_bare_capital() -> None:
    # the half that changes for 'y': a bare capital used to be vetoed
    # into an initial by its Latin shape, and now joins, because the
    # rule is about EVIDENCE and an all-upper name has none.
    out = _classified("JUAN GARCIA Y LOPEZ")
    assert "conjunction" in _tags(out, "Y")
    assert "initial" not in _tags(out, "Y")
    assert out.ambiguities == ()


def test_mixed_case_keeps_todays_rule_verbatim() -> None:
    # both halves, unchanged and unreported: a bare capital is an
    # initial, a lowercase letter is the connective.
    upper = _classified("Jose E Maria Santos")
    assert "initial" in _tags(upper, "E")
    assert "conjunction" not in _tags(upper, "E")
    lower = _classified("John e Smith")
    assert "conjunction" in _tags(lower, "e")
    assert "initial" not in _tags(lower, "e")
    assert upper.ambiguities == () and lower.ambiguities == ()


def test_a_trailing_uppercase_suffix_makes_the_name_mixed_case() -> None:
    # the gate reads the whole name's text, so 'john e jones, III' is
    # mixed case and keeps today's reading -- the boundary that keeps
    # a v1 corpus name still.
    out = _classified("john e jones, III")
    assert "conjunction" in _tags(out, "e")
    assert out.ambiguities == ()


def test_emptying_the_subset_restores_joining_for_e() -> None:
    # the knob, and the reason there is no switch: remove 'e' and a
    # one-case name joins it again, silently.
    lex = dataclasses.replace(_LEX, conjunctions_ambiguous=frozenset())
    out = _classified_with("jose e maria santos", lex)
    assert "conjunction" in _tags(out, "e")
    assert "initial" not in _tags(out, "e")
    assert out.ambiguities == ()


def test_an_orphan_marker_is_inert_even_in_the_emitter() -> None:
    # 'e' left in conjunctions_ambiguous but removed from conjunctions
    # -- legal since the pair is not in _SUBSET_FIELDS (decisions.md#P3)
    # -- never takes the fork, so 'E' in an all-upper name falls to the
    # else branch and is tagged "initial" by is_initial() alone, same as
    # any bare capital. Without the emitter's base-vocabulary gate this
    # would still report a connective that the lexicon no longer has.
    orphan = dataclasses.replace(
        _LEX, conjunctions=_LEX.conjunctions - {"e"})
    out = _classified_with("JOSE E MARIA SANTOS", orphan)
    assert "initial" in _tags(out, "E")
    assert "conjunction" not in _tags(out, "E")
    assert out.ambiguities == ()


def test_a_caseless_connective_never_enters_the_fork() -> None:
    # Arabic و has no case, so token.upper() == token.lower() and
    # today's rule stands whatever the name's case class is.
    lex = dataclasses.replace(
        _LEX, conjunctions=_LEX.conjunctions | frozenset({"و"}))
    out = _classified_with("محمد و علي", lex)
    assert "conjunction" in _tags(out, "و")
    assert out.ambiguities == ()


def test_a_multi_letter_connective_is_untouched() -> None:
    out = _classified("john and jane smith")
    assert "conjunction" in _tags(out, "and")
    assert out.ambiguities == ()


def test_a_dotted_letter_is_an_initial_by_shape_in_any_case_class() -> None:
    # 'e.' is initial-SHAPED, so the fork's len(text) == 1 gate declines
    # and today's rule takes it -- initial, unreported, as it always was.
    out = _classified("john e. smith")
    assert "initial" in _tags(out, "e.")
    assert "conjunction" not in _tags(out, "e.")
    assert out.ambiguities == ()


def test_a_maiden_clause_does_not_count_toward_the_case_class() -> None:
    # rules.md#P3 says a maiden marker, taken as one, and the words it
    # takes, are not among the name's own words -- so appending
    # ' née Jones' must not flip 'Y' back to an initial: the name's own
    # words ("JUAN GARCIA Y LOPEZ") are still all-upper on their own,
    # and 'née Jones' being Title-case is not evidence about THEM.
    out = _classified("JUAN GARCIA Y LOPEZ née Jones")
    assert "conjunction" in _tags(out, "Y")
    assert "initial" not in _tags(out, "Y")
    assert out.ambiguities == ()


def test_a_maiden_clause_leaves_the_own_words_report_intact() -> None:
    # the other half: a one-case name's own words still report, clause
    # appended or not.
    out = _classified("jose e maria santos née jones")
    assert "initial" in _tags(out, "e")
    assert "conjunction" not in _tags(out, "e")
    kinds = [a.kind for a in out.ambiguities]
    assert kinds == [AmbiguityKind.CONJUNCTION_OR_INITIAL]


def test_a_delimited_clause_does_not_count_toward_the_case_class() -> None:
    # delimited (nickname) content arrives with its role already set by
    # extract, before classify ever runs, so it is excluded from the
    # name's own words the same way a maiden clause is -- confirmed by
    # inspecting the token here (role is Role.NICKNAME, not None).
    out = _classified('JOSE E MARIA SANTOS "Pepe"')
    pepe = next(t for t in out.tokens if t.text == "Pepe")
    assert pepe.role is Role.NICKNAME
    assert "initial" in _tags(out, "E")
    kinds = [a.kind for a in out.ambiguities]
    assert kinds == [AmbiguityKind.CONJUNCTION_OR_INITIAL]


def test_the_fork_itself_never_reads_a_delimited_clauses_tokens() -> None:
    # the other half of the bug the above test alone did not catch: not
    # just the CASE CLASS but the fork itself must skip a clause's own
    # tokens, or a nickname's bare capital gets read as though it were
    # one of the name's own words. 'Y' is initial-SHAPED, so pre-fork
    # (2.3.0) it read "initial" and nothing else -- that must hold
    # whatever the surrounding name's case class is.
    y = _classified('JOSE MARIA SANTOS "Y"')
    assert "initial" in _tags(y, "Y")
    assert "conjunction" not in _tags(y, "Y")
    assert y.ambiguities == ()
    e = _classified('JOSE MARIA SANTOS "E"')
    assert "initial" in _tags(e, "E")
    assert "conjunction" not in _tags(e, "E")
    assert e.ambiguities == ()


def test_a_word_after_the_maiden_marker_reads_as_plain_vocabulary() -> None:
    # symmetric with the delimited-clause case: a word inside the
    # maiden clause itself is not one of the name's own words either,
    # so it never enters the fork -- 'e' after 'née' is bare vocabulary
    # membership, the same reading it had before this PR.
    out = _classified("juan garcia lopez née e")
    assert "conjunction" in _tags(out, "e")
    assert "initial" not in _tags(out, "e")
    assert out.ambiguities == ()

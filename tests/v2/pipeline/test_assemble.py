import pytest

from nameparser import (
    Parser, Reading, ReadingKind, ReadingSource, locales, parse, parser_for,
)
from nameparser._lexicon import Lexicon
from nameparser._pipeline import run
from nameparser._pipeline._assemble import assemble
from nameparser._pipeline._state import ParseState, PendingAmbiguity, WorkToken
from nameparser._policy import FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST, Policy
from nameparser._types import AmbiguityKind, ParsedName, Role, Span, Token

from ..cases import CASES, Case

_LEX = Lexicon(
    titles=frozenset({"dr"}),
    particles=frozenset({"de", "la", "van"}),
    particles_ambiguous=frozenset({"van"}),
    suffix_words=frozenset({"iii"}),
    maiden_markers=frozenset({"née"}),
)


def _parse(text: str) -> ParsedName:
    return assemble(run(ParseState(original=text, lexicon=_LEX,
                                   policy=Policy())))


def test_assemble_produces_validated_parsedname() -> None:
    pn = _parse("Dr. Juan de la Vega III")
    assert pn.title == "Dr."
    assert pn.given == "Juan"
    assert pn.family == "de la Vega"
    assert pn.family_base == "Vega"          # particle tags carried over
    assert pn.family_particles == "de la"
    assert pn.suffix == "III"
    assert pn.original == "Dr. Juan de la Vega III"
    for t in pn.tokens:
        assert t.span is not None
        assert t.text == pn.original[t.span.start:t.span.end]


def test_assemble_materializes_ambiguities_on_final_tokens() -> None:
    pn = _parse("Van Johnson")
    assert len(pn.ambiguities) == 1
    amb = pn.ambiguities[0]
    assert amb.kind is AmbiguityKind.PARTICLE_OR_GIVEN
    assert amb.tokens[0] is pn.tokens[0]


def test_assemble_drops_structural_marker_tokens() -> None:
    pn = _parse("Jane Smith née Jones")
    assert [t.text for t in pn.tokens] == ["Jane", "Smith", "Jones"]
    assert pn.maiden == "Jones"


def test_empty_parse_is_falsy() -> None:
    assert not _parse("")
    assert not _parse("   ")


def test_content_free_input_parses_to_empty() -> None:
    # An input with no alphanumeric character is not a name. v1 kept
    # it (parse('.') -> first='.'); 2.0 empties it so bool() stays an
    # honest "did I get a name?" check. isalnum is Unicode-aware, so
    # this only fires on pure punctuation/symbols. The test is over the
    # SURVIVING tokens, which since #329 is not the same as over the
    # input -- see cases.py's maiden_marker_delimited_content_free,
    # where dropping a marker is what leaves nothing behind.
    for junk in [".", ".,", "- -", ". .", "'", "∫≜⩕", "()", "-"]:
        pn = _parse(junk)
        assert not pn, f"{junk!r} should be falsy"
        assert pn.tokens == (), f"{junk!r} should have no tokens"
        assert pn.original == junk       # the raw input is still remembered


def test_a_single_letter_of_content_survives() -> None:
    # the guard keys on content, not length: one alnum char is a name
    for real in ["a.", ".a", "a", "李", "О"]:
        assert _parse(real), f"{real!r} should be truthy"


def test_a_content_free_parse_keeps_its_diagnostics() -> None:
    # Emptying the name must not take the reports with it. "Was this
    # input malformed?" is the one question still worth answering when
    # there is no parse left to infer it from, and every junk row in
    # the test above is balanced or delimiter-free, so none of them
    # would notice if the ambiguities were dropped again.
    pn = _parse("(")
    assert not pn and pn.tokens == ()
    assert [a.kind for a in pn.ambiguities] == [
        AmbiguityKind.UNBALANCED_DELIMITER]
    # points at no token, because none survived -- the load-bearing
    # assertion: a fix that materialized a phantom token would
    # otherwise pass, and ParsedName would reject it anyway
    assert pn.ambiguities[0].tokens == ()
    assert len(_parse("((").ambiguities) == 2      # one report each
    # a delimiter that IS balanced still reports nothing
    assert _parse("()").ambiguities == ()


def test_assemble_falls_back_to_given_for_unassigned_role() -> None:
    # This should never happen through the real pipeline -- assign/group
    # always set a role on every main-stream token before assemble runs.
    # This test constructs the invariant violation directly to pin the
    # documented last-resort behavior: assemble() must stay total over
    # its input and never raise just because upstream left a role unset.
    state = ParseState(
        original="Jane",
        lexicon=Lexicon.default(),
        policy=Policy(),
        tokens=(WorkToken("Jane", Span(0, 4), role=None),),
    )
    pn = assemble(state)
    assert pn.tokens[0].role is Role.GIVEN
    assert pn.given == "Jane"


def test_ambiguity_with_all_indices_dropped_is_omitted() -> None:
    # an ambiguity whose referent tokens were ALL dropped describes
    # nothing; emitting it hollow would mislead consumers. Born-empty
    # ambiguities (unbalanced delimiters) are kept -- they are
    # token-independent by design.
    from nameparser._pipeline._state import PendingAmbiguity
    from nameparser._types import AmbiguityKind as AK
    import dataclasses
    state = run(ParseState(original="Jane Smith née Jones", lexicon=_LEX,
                           policy=Policy()))
    née_idx = next(i for i, t in enumerate(state.tokens)
                   if t.text == "née")
    poisoned = dataclasses.replace(
        state, ambiguities=state.ambiguities + (
            PendingAmbiguity(AK.ORDER, "refers only to the marker",
                             (née_idx,)),
            PendingAmbiguity(AK.UNBALANCED_DELIMITER, "born empty", ()),
        ))
    pn = assemble(poisoned)
    kinds = [a.kind for a in pn.ambiguities]
    assert AK.ORDER not in kinds          # fully dangled: omitted
    assert AK.UNBALANCED_DELIMITER in kinds  # born empty: kept


def test_a_connective_or_initial_report_is_withdrawn_where_the_role_is_a_suffix(
) -> None:
    """rules/A1, the withdrawal (#397 second review).

    classify's connective-or-initial fork offers a connective and an
    initial and its detail says which it took. A generation is
    neither, so where the parse goes on to role the letter SUFFIX the
    report describes a branch nobody took -- and 'JOHN QUINCY SMITH
    I' carried it beside a `suffix-or-name` saying the same token
    reads as a generational suffix. 'i' is the first word that is
    both a marked connective and suffix vocabulary, so no parse
    before this cycle could reach the shape.

    The shipped vocabulary is what these names need, so `parse` is
    used rather than the trimmed `_LEX` above.
    """
    from nameparser import parse
    withdrawn = {
        "JOHN QUINCY SMITH I": ["suffix-or-name"],
        "john smith i": ["suffix-or-name"],
        "SMITH, JOHN I": [],
        "HENRY SMITH I": ["suffix-or-name"],
    }
    for text, kinds in withdrawn.items():
        name = parse(text)
        assert name.suffix.lower() == "i", text
        assert sorted(a.kind.value for a in name.ambiguities) \
            == sorted(kinds), text
    # the contrast that keeps the withdrawal honest: where the parse
    # roles the same letter a NAME word the fork DID resolve to one
    # of its branches, and the report stands
    # -- each with a word to the letter's right: ending its part, as
    # in 'HENRY I', the letter connects nothing and classify reports
    # nothing (rules/P8, #721)
    for text in ("JOSEP CAROD I ROVIRA", "josep carod i rovira",
                 "JOHN I SMITH", "JOSEP CAROD I ROVIRA III"):
        name = parse(text)
        assert "conjunction-or-initial" in [
            a.kind.value for a in name.ambiguities], text
    # ... and an unmarked-position letter of the same class reports
    # nothing at all, which is the third state
    assert [a.kind.value for a in parse("Josep Carod i Rovira").ambiguities] \
        == []


def test_the_withdrawal_reads_the_role_and_not_the_word() -> None:
    """The same withdrawal asked of a TITLE, the other role a fork
    between a connective and an initial cannot have resolved to.

    Nothing shipped builds this state -- a marked letter roled TITLE
    -- which is exactly why it is built here: an implementation
    keyed on the suffix role alone would pass every row above and
    fail this one (_pipeline/AGENTS.md: "Pin the decision, not the
    vocabulary").
    """
    import dataclasses
    from nameparser._pipeline._state import PendingAmbiguity
    from nameparser._types import AmbiguityKind as AK
    state = run(ParseState(original="Dr. Jane", lexicon=_LEX,
                           policy=Policy()))
    dr = next(i for i, t in enumerate(state.tokens) if t.text == "Dr.")
    assert state.tokens[dr].role is Role.TITLE
    poisoned = dataclasses.replace(
        state, ambiguities=state.ambiguities + (
            PendingAmbiguity(AK.CONJUNCTION_OR_INITIAL,
                             "read as an initial", (dr,)),))
    assert AK.CONJUNCTION_OR_INITIAL not in [
        a.kind for a in assemble(poisoned).ambiguities]


def _with_reports(original: str, tokens: tuple[WorkToken, ...],
                  *reports: PendingAmbiguity) -> ParsedName:
    return assemble(ParseState(
        original=original, lexicon=Lexicon.default(), policy=Policy(),
        tokens=tokens, ambiguities=reports))


def test_a_field_tail_report_is_worded_from_the_final_role() -> None:
    # #626: the emitter writes the sentence up to the field and the
    # rest as field_tail; assemble names the field of the FIRST
    # referent's final role, whatever the emitter saw. An empty tail is
    # a real tail (the field ends the sentence), not an absent one.
    tokens = (WorkToken("Kim", Span(0, 3), role=Role.FAMILY),
              WorkToken("Do", Span(4, 6), role=Role.FAMILY))
    pn = _with_reports(
        "Kim Do", tokens,
        PendingAmbiguity(AmbiguityKind.SUFFIX_OR_NAME, "'Do' read as ",
                         (1,), field_tail=" rather than a post-nominal"),
        PendingAmbiguity(AmbiguityKind.PARTICLE_OR_GIVEN,
                         "leading 'Kim' read as ", (0,), field_tail=""),
        PendingAmbiguity(AmbiguityKind.ORDER, "a whole sentence", (0,)))
    assert [a.detail for a in pn.ambiguities] == [
        "'Do' read as a family name rather than a post-nominal",
        "leading 'Kim' read as a family name",
        "a whole sentence"]


def test_a_field_tail_report_in_an_emptied_name_is_withdrawn() -> None:
    # A name emptied for want of content keeps its reports, but one
    # naming a field has no field left to name: it goes rather than
    # ship the sentence's first half. No emitter reaches this today.
    pn = _with_reports(
        "-", (WorkToken("-", Span(0, 1), role=Role.GIVEN),),
        PendingAmbiguity(AmbiguityKind.GIVEN_OR_FAMILY, "'-' read as ",
                         (0,), field_tail=" by convention"),
        PendingAmbiguity(AmbiguityKind.UNBALANCED_DELIMITER, "kept", (0,)))
    assert not pn
    assert [a.detail for a in pn.ambiguities] == ["kept"]


def test_a_field_tail_report_names_its_first_referent_s_field() -> None:
    # The field comes from the FIRST referent: every emitter's referents
    # share one role today, so this pins the documented choice rather
    # than a case the pipeline produces.
    tokens = (WorkToken("General", Span(0, 7), role=Role.FAMILY),
              WorkToken("Smith", Span(8, 13), role=Role.GIVEN))
    pn = _with_reports(
        "General Smith", tokens,
        PendingAmbiguity(AmbiguityKind.TITLE_OR_NAME, "read as ", (0, 1),
                         field_tail=""))
    assert [a.detail for a in pn.ambiguities] == ["read as a family name"]


# -- Token.reading (3.0, 4a): the reading the parse took --------------

#: (name, policy, word, kind, source): one row per branch assemble
#: names a reading by, so a branch that stops being reached, or starts
#: naming another reading, fails here by name.
_EXPECTED_READINGS = [
    ("Dr. Juan de la Vega III", None, "Dr.", "title", "vocabulary"),
    ("Insp. Jane Morse", None, "Insp.", "title", "shape"),
    ("Esq. Smith", None, "Esq.", "title", "shape"),
    ("Member of Parliament John Smith", None, "of", "conjunction",
     "vocabulary"),
    ("Member of Parliament John Smith", None, "Parliament", "title",
     "position"),
    ("Dr. Juan de la Vega III", None, "Juan", "name", "position"),
    ("Dr. Juan de la Vega III", None, "de", "particle", "vocabulary"),
    ("Dr. Juan de la Vega III", None, "III", "generation", "vocabulary"),
    ("John Q. Smith", None, "Q.", "initial", "shape"),
    ("Juan e Maria Smith", None, "e", "conjunction", "vocabulary"),
    # a particle with nothing to join is the name word it stands as
    ("van Gogh", None, "van", "name", "declared"),
    ("de", None, "de", "name", "position"),
    ("Abdul Aziz Tariq", None, "Abdul", "name", "vocabulary"),
    ("John Abdul Smith", None, "Abdul", "name", "vocabulary"),
    # a bound given name that is also a particle is P5's given name
    # where P5 joins it, the first word of its segment past the titles,
    # and a particle where the chain took it, in either part
    ("Abu Bakar Salim", None, "Abu", "name", "vocabulary"),
    ("Abu Bakar Smith", None, "Abu", "name", "vocabulary"),
    ("Smith, Abu Bakar", None, "Abu", "name", "vocabulary"),
    (", Abu Bakar", None, "Abu", "name", "vocabulary"),
    ("Dr. Abu Bakar Smith", None, "Abu", "name", "vocabulary"),
    ("Abu Smith", None, "Abu", "name", "vocabulary"),
    ("Salim Ali abu Bakar Hassan", Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
     "abu", "particle", "vocabulary"),
    ("John Abu Smith", None, "Abu", "particle", "vocabulary"),
    ("Smith, John Abu", None, "Abu", "particle", "vocabulary"),
    ("김민준", None, "김", "name", "vocabulary"),
    # spaced, the order places the family and the list decides nothing
    ("김 민준", None, "김", "name", "position"),
    ("김 성", None, "성", "name", "position"),
    ("Chas. Smith", None, "Chas.", "name", "declared"),
    ("Joao Filho Silva Filho", None, "Silva", "name", "position"),
    ("Pedro Alves Filho", None, "Filho", "agnomen", "vocabulary"),
    ("Alexandre Dumas fils", None, "fils", "generation", "vocabulary"),
    ("John Smith VI", None, "VI", "generation", "shape"),
    ("John Smith PhD", None, "PhD", "credential", "vocabulary"),
    ("John Smith X.Y.Z.", None, "X.Y.Z.", "credential", "shape"),
    ("Jean-Luc Picard Esq.", None, "Esq.", "post-nominal", "vocabulary"),
    ("王小明先生", None, "先生", "post-nominal", "vocabulary"),
    # a word the run takes by position, and a credential split across a
    # space, which is one credential
    ("John Smith PhD Jones", None, "Jones", "credential", "position"),
    ("John Smith III Jones", None, "Jones", "credential", "position"),
    ("John Smith Jr Jones", None, "Jones", "credential", "position"),
    ("John Smith Ph. D.", None, "D.", "credential", "vocabulary"),
    ("John Smith, Jr., Foo", None, "Foo", "credential", "position"),
    ("John Smith, PhD and MD", None, "and", "conjunction", "vocabulary"),
    ("John Smith (M.A)", None, "M.A", "credential", "vocabulary"),
    ("John (Jack) Smith", None, "Jack", "name", "position"),
    ('"Van" Smith', None, "Van", "name", "declared"),
    ('"Abu" Smith', None, "Abu", "name", "vocabulary"),
    ("Jane Smith née Jones", None, "Jones", "name", "position"),
    # the role the reading names is the final one, after every fold
    ("John Paul Smith", Policy(middle_as_family=True), "Paul", "name",
     "position"),
    ("de Mesnil Jean", Policy(name_order=FAMILY_FIRST), "de", "particle",
     "vocabulary"),
]


@pytest.mark.parametrize("text,policy,word,kind,source", _EXPECTED_READINGS,
                         ids=lambda v: v if isinstance(v, str) else None)
def test_a_token_carries_the_reading_the_parse_took(
        text: str, policy: Policy | None, word: str, kind: str,
        source: str) -> None:
    pn = (Parser(policy=policy) if policy else Parser()).parse(text)
    (tok,) = [t for t in pn.tokens if t.text == word][:1]
    assert tok.reading == Reading(kind, tok.role, source)  # type: ignore[arg-type]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_every_parsed_token_has_a_reading_of_its_own_field(case: Case) -> None:
    parser = (parser_for(locales.get(case.locale)) if case.locale is not None
              else Parser(policy=case.policy) if case.policy else Parser())
    pn = parser.parse(case.text)
    for t in pn.tokens:
        assert t.reading is not None, t
        assert t.reading.role is t.role, t
        # 4c's: no rule of the parse names a patronymic yet
        assert t.reading.kind is not ReadingKind.PATRONYMIC, t
        # no file holds a reading by shape or by position
        if t.reading.source in (ReadingSource.SHAPE, ReadingSource.POSITION):
            assert t.reading.languages == (), t
    # case repair changes case and nothing else, the readings included
    repaired = parser.capitalized(pn, force=True)
    assert ([t.reading for t in repaired.tokens]
            == [t.reading for t in pn.tokens])
    # languages is not compared, so it is checked on its own
    assert ([t.reading and t.reading.languages for t in repaired.tokens]
            == [t.reading and t.reading.languages for t in pn.tokens])


def test_a_caller_surname_reads_from_the_vocabulary_only_where_split_off(
        ) -> None:
    # spaced, a caller's own Latin surname is placed by position; the
    # list decides only a division of one written word
    lex = Lexicon.default().add(surnames={"smith"})
    pn = Parser(lexicon=lex).parse("John Smith")
    assert pn.tokens[-1].reading == Reading("name", "family", "position")  # type: ignore[arg-type]


def test_a_token_reading_names_its_own_field() -> None:
    with pytest.raises(ValueError, match="names the field 'family' but the "
                                         "token's role is 'given'"):
        Token("x", None, Role.GIVEN,
              reading=Reading("title", "family", "shape"))  # type: ignore[arg-type]


def test_a_token_replace_or_revise_builds_has_no_reading() -> None:
    pn = parse("Dr. Juan de la Vega III")
    for edited in (pn.replace(family="Smith"),
                   Parser().revise(pn, family="Smith")):
        (family,) = edited.tokens_for(Role.FAMILY)
        assert family.reading is None
        # the fields it did not touch keep theirs
        assert [t.reading for t in edited.tokens_for(Role.GIVEN)] == [
            t.reading for t in pn.tokens_for(Role.GIVEN)]


#: A listed suffix word reads as its vocabulary kind (3.0's 4b): `jr`
#: and `esq` compile into the same set with the same tags, and the
#: reading index tells them apart; a credential written as a word
#: (`博士`) is a credential, and a kind with no reading kind of its own
#: (a courtesy, an honorific) a post-nominal word.
@pytest.mark.parametrize("text,word,kind", [
    ("John Smith Jr.", "Jr.", "generation"),
    ("John Smith Sr.", "Sr.", "generation"),
    ("John Smith III", "III", "generation"),
    ("Pedro Alves Filho", "Filho", "agnomen"),
    ("John Smith Esq.", "Esq.", "post-nominal"),
    ("王小明先生", "先生", "post-nominal"),
    ("王小明 博士", "博士", "credential"),
    ("John Smith PhD", "PhD", "credential"),
])
def test_a_suffix_word_reads_as_its_vocabulary_kind(
        text: str, word: str, kind: str) -> None:
    (tok,) = [t for t in parse(text).tokens if t.text == word]
    assert tok.reading is not None
    assert tok.reading.kind.value == kind


def test_every_suffix_words_reading_alternative_and_index_kind_agree(
        ) -> None:
    # One walk over every suffix-set word, not a case per word (826 on
    # 2026-10-29): behind a name the word takes its suffix reading, a
    # lone word that reports a fork names that reading as the one not
    # taken, and both carry the kind the shipped reading index gives
    # it. One predicate (`_vocab.suffix_kind`) names the two readings
    # (rules/R8, decisions/R8)
    from nameparser._reading_index import suffix_kind_of
    lex = Lexicon.default()
    kinds = {"generation": "generation", "agnomen": "agnomen",
             "credential": "credential"}
    words = sorted(lex.suffix_words | lex.suffix_acronyms
                   | lex.suffix_words_ambiguous
                   | lex.suffix_acronyms_ambiguous)
    assert len(words) > 800
    mismatched = []
    reported = 0
    for word in words:
        want = kinds.get(suffix_kind_of(word) or "", "post-nominal")
        taken = [t.reading.kind.value if t.reading else None
                 for t in parse(f"John Smith {word}").tokens_for(Role.SUFFIX)]
        lone = parse(word).ambiguities
        not_taken = [a.alternative.kind.value for a in lone
                     if a.alternative is not None
                     and a.alternative.role is Role.SUFFIX]
        # a lone word reporting the suffix-or-name fork names the
        # suffix reading it did not take, so the walk checks that
        # reading rather than passing on an absent one
        forked = any(a.kind is AmbiguityKind.SUFFIX_OR_NAME for a in lone)
        reported += forked
        if (taken != [want] or (forked and not not_taken)
                or any(k != want for k in not_taken)):
            mismatched.append((word, want, taken, not_taken))
    assert not mismatched, mismatched[:10]
    assert reported > 0


# -- Reading.languages (3.0, 4a's follow-up): the files holding it ------

#: (name, word, languages): the files the reading index holds the
#: reading the parse took in, one row per way assemble looks a word up.
_EXPECTED_LANGUAGES = [
    # a particle, by its particle rows only ('la' is a given name in es
    # too, a reading the parse did not take)
    ("Dr. Juan de la Vega III", "de", ("es", "fr", "it", "nl", "pt")),
    ("Dr. Juan de la Vega III", "la", ("es", "fr", "it")),
    ("Dr. Juan de la Vega III", "Dr.", ("mul",)),
    ("Dr. Juan de la Vega III", "III", ("mul",)),
    ("John Smith PhD", "PhD", ("en",)),
    ("王小明先生", "先生", ("ja", "zh")),
    ("Juan e Maria Smith", "e", ("it", "pt")),
    ("Pedro Alves Filho", "Filho", ("pt",)),
    # a suffix matched by its suffix entry, whatever its finer kind (4b)
    ("John Smith Jr.", "Jr.", ("en",)),
    # a name the vocabulary declares, and a bound given name
    ("van Gogh", "van", ("nl",)),
    ("Chas. Smith", "Chas.", ("en",)),
    # a name reading names the files listing the word as a name of its
    # own field: `ma` is family in en, given in en and fil
    ("Long Ma", "Ma", ("en",)),
    ("Ma Long", "Ma", ("en", "fil")),
    ("Jane Doe (nee Smith Ma)", "Ma", ("en",)),
    # a declared name in a field no file lists it in names none: fr
    # lists `fils` only as a family name
    ("Alves, Pedro Fils", "Fils", ()),
    # a bound given name names its files in the family field too
    ("John Abdul", "Abdul", ("ar",)),
    ("Abu Bakar Smith", "Abu", ("ar",)),
    # an acronym by its periods removed, and a credential split across
    # a space, listed whole, each of its words naming the files
    ("John Smith (M.A)", "M.A", ("en",)),
    ("John Smith Ph. D.", "Ph.", ("en",)),
    ("John Smith Ph. D.", "D.", ("en",)),
    ("Smith, Ph. D. III", "D.", ("en",)),
    ("John Smith Pharm D", "Pharm", ("en",)),
    # a nickname written between a split credential's words is passed
    # over, and the run reaches its second word
    ('John Smith Ph. "Bob" D.', "Ph.", ("en",)),
    ('John Smith Ph. "Bob" D.', "D.", ("en",)),
    # a word joining listed words, by its parts; never divided at a
    # combining mark
    ("John Smith, M.D./Ph.D.", "M.D./Ph.D.", ("en",)),
    ("Lt.Gov. John Smith", "Lt.Gov.", ("en",)),
    # a word the lexicon lists whole without its periods is read whole,
    # not by its parts
    ("Lt.Gen. John Smith", "Lt.Gen.", ("en",)),
    ("प्रोफे.डॉ. अदा शर्मा", "प्रोफे.डॉ.", ("hi", "mr")),
    # a union over parts is sorted, as a word's own files are
    ("John Smith, MS-V", "MS-V", ("en", "mul")),
    # no file: position, shape, and a shipped list outside the per-word
    # files (the Korean surnames)
    ("Dr. Juan de la Vega III", "Juan", ()),
    ("John Smith X.Y.Z.", "X.Y.Z.", ()),
    ("Insp. Jane Morse", "Insp.", ()),
    ("John Q. Smith", "Q.", ()),
    ("김민준", "김", ()),
    ("John Smith Ph. D. Jones", "Jones", ()),
]


@pytest.mark.parametrize("text,word,languages", _EXPECTED_LANGUAGES,
                         ids=lambda v: v if isinstance(v, str) else None)
def test_a_reading_names_the_files_holding_it(
        text: str, word: str, languages: tuple[str, ...]) -> None:
    (tok,) = [t for t in parse(text).tokens if t.text == word][:1]
    assert tok.reading is not None
    assert tok.reading.languages == languages


@pytest.mark.parametrize("field,word,text,written", [
    ("titles", "zzq-dr", "Zzq-Dr John Smith", "Zzq-Dr"),
    ("particles", "mac-van", "John mac-van Smith", "mac-van"),
    # listed without the periods it is written with
    ("titles", "drma", "Dr.Ma Smith", "Dr.Ma"),
])
def test_a_callers_whole_word_names_no_file_of_its_parts(
        field: str, word: str, text: str, written: str) -> None:
    # the parse read it whole, so the files of `dr` or `van` are not
    # its reading's; the default's own joined words still name theirs
    # (`Lt.Gov.` in _EXPECTED_LANGUAGES, and `Dr.Ma` below)
    assert parse(text).tokens[0].reading is not None
    lex = Lexicon.default().add(**{field: {word}})
    (tok,) = [t for t in Parser(lexicon=lex).parse(text).tokens
              if t.text == written]
    assert tok.reading is not None
    assert tok.reading.source is ReadingSource.VOCABULARY
    assert tok.reading.languages == ()


def test_a_reading_from_a_callers_own_vocabulary_names_no_file() -> None:
    # a word no file holds, and one a file holds only off by default
    # (`st`, a Czech generation written `default = false`): its kind is
    # the word's, read whatever the reading's default (4b), so a pack
    # turning it on reads it alike, but no file holds it on
    lex = Lexicon.default().add(titles={"zzq"}, suffix_words={"st"})
    pn = Parser(lexicon=lex).parse("Zzq John Smith St")
    readings = {t.text: t.reading for t in pn.tokens}
    assert readings["Zzq"] == Reading("title", "title", "vocabulary")  # type: ignore[arg-type]
    assert readings["St"] == Reading("generation", "suffix", "vocabulary")  # type: ignore[arg-type]
    assert readings["Zzq"] is not None and readings["Zzq"].languages == ()
    assert readings["St"] is not None and readings["St"].languages == ()


def test_a_callers_whole_suffix_and_its_alternative_name_no_file_of_its_parts(
        ) -> None:
    # 'md' and 'ma' are in en, and the default reads 'MD-ZZ' by its
    # parts; listed whole, the token and the report's alternative name
    # none of their files
    lex = Lexicon.default().add(suffix_acronyms={"md-zz", "ma-zz"},
                                suffix_acronyms_ambiguous={"ma-zz"})
    parser = Parser(lexicon=lex)
    (md,) = [t for t in parser.parse("John Smith MD-ZZ").tokens
             if t.text == "MD-ZZ"]
    assert md.reading == Reading("credential", "suffix", "vocabulary")  # type: ignore[arg-type]
    assert md.reading is not None and md.reading.languages == ()
    (amb,) = parser.parse("JOHN SMITH MA-ZZ").ambiguities
    assert amb.alternative == Reading("name", "family", "declared")  # type: ignore[arg-type]
    assert amb.alternative is not None and amb.alternative.languages == ()


def test_the_default_reads_a_joined_word_by_its_parts() -> None:
    (tok,) = parse("Dr.Ma Smith").tokens[:1]
    assert tok.reading is not None and tok.reading.languages == ("mul",)


@pytest.mark.parametrize("text,word", [
    ("John Ma Smith", "Ma"), ("Smith, John Ma", "Ma")])
def test_a_folded_middle_names_the_files_of_the_middle_it_stands_as(
        text: str, word: str) -> None:
    # middle_as_family reports the field, and the files stay those
    # listing the word as the given name it stands as
    pn = Parser(policy=Policy(middle_as_family=True)).parse(text)
    (tok,) = [t for t in pn.tokens if t.text == word]
    assert tok.role is Role.FAMILY and tok.reading is not None
    assert tok.reading.languages == ("en", "fil")
    (amb,) = Parser(policy=Policy(middle_as_family=True)).parse(
        "Doe, John van DO").ambiguities
    assert amb.alternative is not None
    assert amb.alternative.role is Role.FAMILY
    assert amb.alternative.languages == ("en", "nl")


def test_an_alternative_names_the_files_holding_it() -> None:
    (amb,) = parse("JOHN SMITH MA").ambiguities
    assert amb.alternative is not None
    # `ma` as a family name: en lists it so, fil only as a given name
    assert amb.alternative.languages == ("en",)
    (amb,) = parse("van Gogh").ambiguities
    assert amb.alternative is not None
    assert amb.alternative.languages == ("nl",)
    # over the report's words, sorted ('van' and 'DO' as given names,
    # nl and en)
    (amb,) = parse("Doe, John van DO").ambiguities
    assert amb.alternative is not None
    assert amb.alternative.languages == ("en", "nl")

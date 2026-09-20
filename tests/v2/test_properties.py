"""Property layer. Hypothesis is a dev dependency only.

The alphabet is punctuation-heavy on purpose: plain st.text() spreads
over all of Unicode, so commas, quotes, and delimiters almost never
appear and the interesting planes go unexercised. derandomize=True
keeps runs reproducible on shared CI runners -- this layer guards
against regressions; exploratory fuzzing happened during review.
"""
import dataclasses
import hashlib
import itertools
import re
import warnings

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nameparser import (
    DEFAULT_SCRIPT_ORDERS, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST,
    GIVEN_FIRST, Lexicon, Parser, PatronymicRule, Policy, Script, parse,
)
from nameparser._lexicon import _VOCAB_FIELDS
from nameparser._pipeline import run
from nameparser._pipeline._state import ParseState
from nameparser._pipeline._vocab import effective_script
from nameparser._types import (UNJOINED_CONJUNCTION_TAG, UNJOINED_TAG,
                               AmbiguityKind, ParsedName, Role, Token)

from .conftest import differential_corpus

_ALPHABET = st.sampled_from(
    'abcdefgh ABC 12 .,،，\'"()«»‏‏\U0001f600éñßЖ-')

_FORK_CORPUS = differential_corpus()


@given(st.text(alphabet=_ALPHABET, max_size=200))
@settings(max_examples=300, deadline=None, derandomize=True)
def test_parse_never_raises_on_str(text: str) -> None:
    parse(text)


@given(st.text(alphabet=_ALPHABET, max_size=200))
@settings(max_examples=300, deadline=None, derandomize=True)
def test_provenance_for_parser_produced_names(text: str) -> None:
    pn = parse(text)
    for t in pn.tokens:
        assert t.span is not None
        assert t.text == pn.original[t.span.start:t.span.end]


@given(st.text(alphabet=_ALPHABET, max_size=100))
@settings(max_examples=200, deadline=None, derandomize=True)
def test_capitalized_idempotent(text: str) -> None:
    once = parse(text).capitalized()
    assert once.capitalized() == once


@given(st.text(alphabet=_ALPHABET, max_size=100))
@settings(max_examples=200, deadline=None, derandomize=True)
def test_render_reparse_reaches_fixpoint(text: str) -> None:
    # render/reparse legitimately takes several rounds to stabilize on
    # comma-heavy input (each round can re-segment); the invariant is
    # BOUNDED CONVERGENCE, not one-step idempotence
    s = str(parse(text))
    for _ in range(10):
        nxt = str(parse(s))
        if nxt == s:
            break
        s = nxt
    assert str(parse(s)) == s, f"no fixpoint within 10 rounds: {s!r}"


@given(st.text(alphabet=_ALPHABET, max_size=100))
@settings(max_examples=300, deadline=None, derandomize=True)
def test_every_original_char_is_accounted_for(text: str) -> None:
    # Reverse coverage (the dual of provenance): no character of the
    # input silently vanishes. Every char lies in a token span, a
    # masked delimited span, or is individually ignorable -- whitespace,
    # a structural comma, or a char the strip options remove. Checked on
    # the pre-assembly state because dropped/extracted tokens keep their
    # spans there.
    state = run(ParseState(original=text, lexicon=Lexicon.default(),
                           policy=Policy()))
    covered: set[int] = set()
    for tok in state.tokens:
        covered.update(range(tok.span.start, tok.span.end))
    for span in state.masked:
        covered.update(range(span.start, span.end))
    ignorable = {",", "،", "，", "\U0001f600", "‏"}
    for i, ch in enumerate(text):
        if i in covered or ch.isspace() or ch in ignorable:
            continue
        raise AssertionError(
            f"char {ch!r} at {i} in {text!r} is unaccounted for")


_NAME_ROLES = (Role.GIVEN, Role.MIDDLE, Role.FAMILY)


def _fork_count(state: ParseState) -> int:
    return sum(a.kind is AmbiguityKind.PARTICLE_OR_GIVEN
               for a in state.ambiguities)


def test_a_leading_ambiguous_particle_is_reported_once_and_only_once(
) -> None:
    """PARTICLE_OR_GIVEN is the one kind two stages emit: _group takes
    the particle branch when something shifts the particle off the
    name's leading piece and the chain claims something ("Freiherr von
    Richthofen"), _assign takes the given branch when it stays a lone
    leading piece ("Van Johnson", and since #367 "Dr. Van Johnson" as
    well -- a plain title is transparent, so only a leading word that
    is BOTH a title and a particle still reaches _group's emitter,
    which is what the 'Freiherr ' lead below exercises).
    Each reports the side it decides -- see the ParseState docstring --
    but they coordinate only through _group's `j > k + 1` guard, which
    mirrors _assign's reachability by hand. Nothing checked the mirror.

    The shape that separates them is the one real-name corpora have
    least reason to contain: a suffix straight after the particle, where
    the chain is a no-op and only _assign should speak. Generate it, over
    every ambiguous particle, so a vocabulary addition is covered too.

    Deliberately asserts the COUNT and not which stage spoke. Whether a
    given fork was decided by a vocabulary merge or by position is not
    recoverable from the finished parse -- 'Dr. aan Johnson Jr.' and
    'أبو بكر أحمد' end with the same roles and the same tags, and only
    one is a fork -- so any reconstruction here would have to
    re-implement _group rather than check it.
    """
    # The 'Freiherr ' lead below has to be a title AND a particle, or it
    # is transparent to the leading-particle exception (#367), every
    # shape using it leaves _group's emitter for _assign's, and this
    # sweep goes on passing with the fork count unchanged -- coverage
    # lost silently, which is the failure this sweep is least able to
    # notice about itself. Supplied rather than borrowed from the shipped
    # vocabulary, for the reason test_parser.py's _TITLE_PARTICLES block
    # gives; a no-op against today's data, and #360-proof against
    # tomorrow's.
    lex = Lexicon.default().add(titles={"freiherr"}, particles={"freiherr"})
    # bound-given prefixes are excluded, not overlooked: 'abu' is both
    # an ambiguous particle and a bound given prefix, so whether it
    # forks depends on whether the bound join fired -- a second rule,
    # covered by the case corpus rather than by this sweep
    particles = sorted(lex.particles_ambiguous - lex.bound_given_names)
    assert particles, "no ambiguous particles to exercise"
    failures = []
    for particle in particles:
        for lead in ("", "Dr. ", "Dr. Ann ", "Freiherr "):
            for body in ("", "Johnson ", "Johnson Smith "):
                for tail in ("", "Jr.", "MD", "III"):
                    text = f"{lead}{particle} {body}{tail}".strip()
                    state = run(ParseState(original=text,
                                           lexicon=lex, policy=Policy()))
                    names = [t for t in state.tokens
                             if t.role in _NAME_ROLES]
                    # Leading = no name part precedes it. With a given
                    # name in front ("Dr. Ann van Johnson") the particle
                    # sits mid-name, where nothing has to choose -- the
                    # decision-not-a-word rule, so no report. And a lone
                    # name part is the whole name, not a coin flip.
                    leads = bool(names) and "vocab:particle-ambiguous" \
                        in names[0].tags
                    want = 1 if leads and len(names) >= 2 else 0
                    got = _fork_count(state)
                    if got != want:
                        failures.append(
                            f"{text!r}: {got} report(s), expected {want} "
                            f"({len(names)} name tokens, "
                            f"leading={leads})")
    assert not failures, (
        f"{len(failures)} shape(s) disagree:\n" + "\n".join(failures[:15]))


#: The three `do` rows P6's attachment owns by design. A CLOSED list
#: with the rule that owns each one: a fourth exception fails, which is
#: the whole point of carrying them by name rather than by count.
_COMMA_AGREEMENT_EXCEPTIONS = {
    "John Doe do": "rules.md#P6 attaches the lower-case particle member",
    "John Q. Doe do": "rules.md#P6 attaches the lower-case particle member",
    "Mary Jo Doe do": "rules.md#P6 attaches the lower-case particle member",
}


def test_a_comma_form_and_its_comma_less_twin_agree_on_the_class(
) -> None:
    """#531's invariant, and the shape of the defect it closed.

    A word ending the given part of a family-comma listing and the
    same word ending the comma-less spelling of the same name must be
    put in the SAME CLASS -- credential (role SUFFIX) or name (any of
    the other six roles). CLASS, not FIELD, and the difference
    matters: 'John Doe Ma' reads family 'Ma' with middle 'Doe' while
    'Doe, John Ma' reads middle 'Ma', different fields and both
    'name', and this test must pass on that pair.

    Measured on this tree before #531: 48 of the 78 pairs disagreed,
    every one of them in the same direction -- the comma form
    declining a credential the comma-less form took. After: 3, and
    they are the allowlist above.
    """
    words = []
    for base in ("ba", "do", "ed", "jd", "ma", "x.y.z.", "q.w.e.r.t."):
        words += [base, base.upper(), base.capitalize()]
    words += ["phd", "PhD", "Jr", "xyz", "XYZ"]
    shapes = (("John Doe {w}", "Doe, John {w}"),
              ("John Q. Doe {w}", "Doe, John Q. {w}"),
              ("Mary Jo Doe {w}", "Doe, Mary Jo {w}"))
    parser = Parser()

    def side(name: object, word: str) -> str:
        for role in Role:
            value = getattr(name, role.value)
            if value == word or word in value.split():
                return "credential" if role is Role.SUFFIX else "name"
        return "absent"

    failures = []
    for word in words:
        for plain, comma in shapes:
            a = side(parser.parse(plain.format(w=word)), word)
            b = side(parser.parse(comma.format(w=word)), word)
            if a == b:
                continue
            key = plain.format(w=word)
            if key in _COMMA_AGREEMENT_EXCEPTIONS:
                continue
            failures.append(
                f"{key!r} reads {a} but {comma.format(w=word)!r} "
                f"reads {b}")
    assert not failures, (
        f"{len(failures)} pair(s) disagree:\n" + "\n".join(failures[:15]))


def test_the_comma_agreement_exceptions_are_all_still_exceptions(
) -> None:
    """The allowlist's own negative control: a row that stopped being
    an exception is an allowlist entry silently covering nothing, and
    the sweep above cannot notice that about itself."""
    parser = Parser()
    for plain in _COMMA_AGREEMENT_EXCEPTIONS:
        comma_form = "Doe, " + plain.replace("John Doe ", "John ").replace(
            "John Q. Doe ", "John Q. ").replace("Mary Jo Doe ", "Mary Jo ")
        assert parser.parse(plain).suffix, plain
        assert not parser.parse(comma_form).suffix, comma_form


#: The one-case-head exception class, and the recorded size of it.
#: Structural rather than a name list: a name whose OWN words are
#: written in one case, where the member's own writing is the only
#: contrast in the string, so the clause hides it. `own_words` stops
#: at the maiden marker (rules.md#P3), so a member inside the clause
#: cannot contribute the case contrast `one_case` is computed from --
#: which is decisions.md#S2's own "THE PREDICATE KEEPS THE JUDGED
#: TOKEN IN THE SPAN" (the 2026-09-14 #289/#516 entry) failing
#: structurally, the judged token never being in the span at this
#: slot. Accepted by Derek 2026-09-19 and recorded in
#: decisions.md#S2 as the M2 instance of #492's deferred question.
#: The class is asserted beside the count because a structural
#: allowlist cannot notice a new member of it, and a COUNT cannot
#: notice a swap -- one pair leaving and another arriving keeps the
#: number. So the SET is pinned, by digest: sha256 over the sorted
#: "<policy>|<marker>|<clause name>" lines, printed by the assertion
#: when it fails, which is how a deliberate move is re-recorded.
#: Re-measured 2026-09-19 on the widened grid below: 1,026 of 18,144
#: pairs, which is exactly 9x the 114 of 2,016 the single-marker,
#: single-policy grid held -- three markers x three policies, and the
#: class is indifferent to both, which is the finding. (Before #533
#: the same grid had 186 allowlisted and 984 failing.)
_MAIDEN_AGREEMENT_EXCEPTIONS = 1026
_MAIDEN_AGREEMENT_DIGEST = (
    "4b70727a2633fea1a9c219173d48b223cc0866a5d340b69a9eb4f14fc386ae6a")


def _one_case(text: str) -> bool | None:
    """ParseState.one_case for a whole parse -- `is_one_case` over the
    name's own words, which is exactly the span the allowlist asks
    about."""
    return run(ParseState(original=text, lexicon=Lexicon.default(),
                          policy=Policy())).one_case


def test_a_maiden_clause_does_not_change_how_a_trailing_word_reads(
) -> None:
    """#533's invariant: appending a maiden clause to a name must not
    change the CLASS a trailing word is read in.

    A member of the ambiguous credential class ending a name that
    carries a maiden clause, and the same member ending the same name
    with the clause removed, must land in the same class -- credential
    (role SUFFIX) or name (any other role). CLASS, not FIELD.

    The clause bodies are NAME WORDS ONLY on purpose: a suffix word or
    a title inside the clause is a word the count reads, so removing
    the clause changes the question rather than answering it ('J. nee
    Smith Jr MA' against 'J. MA' is not a pair).

    Measured on this tree before #533: 984 of 2016 pairs disagreed
    outside the allowlist. After: 0, and the allowlist holds exactly
    its recorded size.
    """
    members = ("ba", "do", "ed", "jd", "ma", "x.y.z.", "r.a.i.")
    heads = ("Jane Doe", "Doe, Jane", "John", "J.", "Dr.", "Jane",
             "Jane van der Berg", "JANE DOE", "jane doe", "DOE, JANE",
             "doe, jane", "Jane Q. Doe", "Doe, Dr. Jane", "Doe, J.",
             "Smith, Jane", "Jane Doe Jr.")
    bodies = ("Smith", "Yo-Yo", "van der Berg", "Jones Smith", "MA",
              "Ma")
    # three markers and the two 2.4 switches beside the default: the
    # switches change WHICH tokens are in the class, and the marker
    # spellings are what `own_words` stops at, so both are dimensions
    # the allowlist's structural argument rests on.
    markers = ("nee", "n\u00e9e", "geb.")
    policies = (("default", Policy()),
                ("caps", Policy(unlisted_caps_suffixes=True)),
                ("nodot", Policy(unlisted_dotted_suffixes=False)))

    def side(parser: Parser, text: str, word: str) -> str:
        name = parser.parse(text)
        hits = [t for t in name.tokens if t.text == word]
        if not hits:
            return "gone"
        return ("credential" if hits[-1].role is Role.SUFFIX
                else "name")

    pairs = 0
    allowed: list[str] = []
    failures = []
    for label, policy in policies:
        parser = Parser(policy=policy)
        for head in heads:
            for body in bodies:
                for base in members:
                    for word in (base.lower(), base.title(),
                                 base.upper()):
                        for marker in markers:
                            clause = f"{head} {marker} {body} {word}"
                            plain = f"{head} {word}"
                            pairs += 1
                            if side(parser, clause, word) == side(
                                    parser, plain, word):
                                continue
                            if _one_case(clause) and not _one_case(plain):
                                allowed.append(
                                    f"{label}|{marker}|{clause}")
                                continue
                            failures.append(
                                f"[{label}] {clause!r} reads "
                                f"{side(parser, clause, word)} but "
                                f"{plain!r} reads "
                                f"{side(parser, plain, word)}")
    assert not failures, (
        f"{len(failures)} of {pairs} pair(s) disagree outside the "
        f"one-case-head class:\n" + "\n".join(failures[:15]))
    digest = hashlib.sha256(
        "\n".join(sorted(allowed)).encode()).hexdigest()
    assert (len(allowed), digest) == (
        _MAIDEN_AGREEMENT_EXCEPTIONS, _MAIDEN_AGREEMENT_DIGEST), (
        f"the one-case-head class holds {len(allowed)} of {pairs} "
        f"pairs with digest {digest}, recorded as "
        f"{_MAIDEN_AGREEMENT_EXCEPTIONS} / "
        f"{_MAIDEN_AGREEMENT_DIGEST} on 2026-09-19. The SET is "
        f"pinned, not only the size: a swap keeps the count. "
        f"Re-record both deliberately, saying why. Members:\n"
        + "\n".join(sorted(allowed)[:10]))


#: The tags that make a token a member of the ambiguous credential
#: class as the reader sees it -- the listed one and the by-shape one
#: a 2.4 switch writes. Spelled here rather than imported so the
#: property is stated in the terms rules.md#M2 states it in, and so a
#: rename in the pipeline cannot quietly narrow what this checks.
_CLASS_TAGS = frozenset({"vocab:suffix-ambiguous", "shape:acronym"})

#: Two-member trailing runs: the one shape that puts a maiden-clause
#: report and an assign-peel report on the same parse, each naming a
#: different token. Written out rather than generated, because what
#: makes them work is the CONTRAST between the two members' writing.
_TAILS = ("Ma JD", "MA JD", "MA Ma")


def _maiden_clause_grid() -> list[tuple[str, Parser, str]]:
    """(name, parser, policy label) for the M2 release grid.

    Rich enough to hold every shape the #533 review found: title-led
    and post-nominal-led comma heads, particle heads, a bound-given
    head, by-shape and caps-on members, two adjacent particle members,
    mixed/ALL-CAPS/lower writing, comma and no-comma, four markers,
    and the default policy beside each 2.4 switch.
    """
    heads = ("Jane Doe", "Doe, Jane", "Doe, Prof.", "Doe, Dr.",
             "Jane Doe, Jr", "Jane Doe, PhD", "Doe, J.", "Doe, PhD",
             "Berg, Jane van der", "Jane van der Berg", "Berg, abdul",
             "abdul Berg", "J. Doe", "Doe", "Prof. Jane Doe",
             "Doe, Jane van der", "Doe, Sir")
    bodies = ("Smith", "Smith MA", "Smith Ma", "Smith ma", "Smith A.B.",
              "Smith X.Y.Z.", "Smith XYZ", "Smith ba", "Smith DO",
              "Smith Do", "Smith do", "Smith MA XYZ", "Smith DO DO",
              "Smith Ma JD", "Smith MA JD", "Smith MA Ma",
              "Smith V MA", "MA", "MA PhD", "MA ba", "Smith Jones MA",
              "Smith PhD", "Smith Jr", "Jones Smith Ma", "Smith MA PhD")
    policies = (("default", Policy()),
                ("caps", Policy(unlisted_caps_suffixes=True)),
                ("nodot", Policy(unlisted_dotted_suffixes=False)))
    parsers = [(label, Parser(policy=p)) for label, p in policies]
    texts: list[str] = []
    seen: set[str] = set()
    for head in heads:
        for body in bodies:
            markers = ("nee", "née", "geb.", "z domu") if " " not in body \
                else ("nee",)
            for marker in markers:
                base = f"{head} {marker} {body}"
                for text in (base, f"{base}, MD"):
                    for written in (text, text.upper(), text.lower()):
                        if written not in seen:
                            seen.add(written)
                            texts.append(written)
    return [(t, parser, label) for t in texts for label, parser in parsers]


def _released_but_not_suffix(text: str, parser: Parser) -> list[str]:
    """Words rules.md#M2 says must be SUFFIX-roled and are not.

    The clause's parent-style reach is everything from the marker to
    the first CERTAIN suffix word -- suffix vocabulary that is not
    initial-shaped, which is where the walk stopped before #533 and
    still stops. Inside that reach a class member is either still in
    the maiden name or was given up as a credential; any third answer
    is a word the clause released into the current name, which is the
    failure this property exists for.
    """
    marker = _MARKER_RE.search(text)
    if marker is None:
        return []
    name = parser.parse(text)
    if not name.maiden:
        return []
    out = []
    for tok in name.tokens:
        if tok.span is None or tok.span.start < marker.end():
            continue
        if "vocab:suffix" in tok.tags and "initial" not in tok.tags:
            break
        if (not _CLASS_TAGS.isdisjoint(tok.tags)
                and tok.role not in (Role.MAIDEN, Role.SUFFIX)):
            out.append(f"{tok.text!r} -> {tok.role.value}")
    return out


_MARKER_RE = re.compile(
    r"(?<![\w.])(nee|née|geb\.|z domu)(?![\w])", re.IGNORECASE)


def test_a_word_the_clause_gives_up_lands_in_suffix() -> None:
    """rules.md#M2's invariant, over the whole release grid.

    The clause may hand a word to the trailing rule that reads it as
    a credential, and it may keep the word. There is no third answer:
    a released word that ends the parse in `given`, `middle` or
    `family` has crossed from the BIRTH name into the current one,
    silently, and that is the class of failure #424 named from the
    other direction.

    The grid is the pin, and it is a grid rather than a name list so
    that it could fail. At d97d3eb7 -- the commit this review round
    started from -- it fails on 790 of its 8,466 parses, 290 distinct
    names, covering every shape the review reported: 'Doe, Prof. nee
    Smith A.B.' reading given 'A.B.' (32 parses, and 'X.Y.Z.' another
    32), 'DOE, PROF. NEE SMITH MA' reading given 'MA' (206, the
    largest class, with 'ba' at 96), 'Berg, Jane van der nee Smith
    DO' reading family 'van der DO Berg' (12) and 'Jane Doe nee Smith
    DO DO' reading family 'DO DO' (108, two words apiece). At
    2f57ff21, the parent, it passes on all 8,466 -- the invariant is
    what the conservative direction always held.
    """
    failures = []
    grid = _maiden_clause_grid()
    for text, parser, label in grid:
        for bad in _released_but_not_suffix(text, parser):
            failures.append(f"[{label}] {text!r}: {bad}")
    assert not failures, (
        f"{len(failures)} of {len(grid)} parse(s) released a word the "
        f"clause should have kept:\n" + "\n".join(failures[:20]))
    # the grid has to be able to fail: every shape above must actually
    # reach the walk, which it does only where a clause is taken
    reached = sum(bool(p.parse(t).maiden) for t, p, _ in grid)
    assert reached > len(grid) // 2, (
        f"only {reached} of {len(grid)} grid parses carry a maiden "
        f"name; the rest cannot exercise M2 at all")


def test_no_two_ambiguities_name_the_same_token_span() -> None:
    """The maiden walk and assign's trailing peel both report at this
    class, and group's particle-chain emitter stands beside them. None
    of the three may report a word another already did -- the maiden
    pieces are removed before the chain runs, and a member the reading
    TOOK is out of the clause by the time roles are assigned.

    Per TOKEN, not per whole span: a first draft compared the
    ambiguities' token tuples for equality, which sees two reports of
    the same span and misses the likelier defect -- one report naming
    `Smith MA` while another names `MA`. The check below is over the
    spans the reports claim, so an OVERLAP fails it however the two
    spans differ in length.

    Measured 2026-09-19: 0 over 27,216 parses, every particle shape
    among them ('nee van der Berg Ma', 'nee de Ma', 'nee van Ma').
    A COUNT of the parses that carry two reports rides along, because
    a comparison over one report is vacuous and nothing else would
    say so.

    The count is also what caught this test measuring the wrong
    thing. Every one of the 2,160 multi-report parses the grid held
    at the review paired the MAIDEN emitter with the particle-chain
    emitter -- the pair this test is named for, maiden against
    assign's peel, never occurred, because one trailing member is
    either kept by the clause or peeled by assign and no grid row had
    TWO. The `_TAILS` below are that shape: 'Ma JD' keeps 'Ma' and
    peels 'JD', 'MA JD' releases 'MA' and peels 'JD' behind it, and
    'MA Ma' keeps the Title-case one with the caps one in front. The
    count is re-pinned on the widened grid, and the pairing is
    asserted directly beside it so a later edit that drops the tails
    fails here rather than silently turning this back into a test of
    the particle emitter.
    """
    members = ("ba", "do", "ed", "jd", "ma", "x.y.z.", "r.a.i.")
    heads = ("Jane Doe", "Doe, Jane", "John", "J.", "Dr.", "Jane",
             "Jane van der Berg", "JANE DOE", "jane doe", "DOE, JANE",
             "doe, jane", "Jane Q. Doe", "Doe, Dr. Jane", "Doe, J.",
             "Smith, Jane", "Jane Doe Jr.", "Doe, Jane van",
             "Doe, Jane van der")
    bodies = ("Smith", "Yo-Yo", "van der Berg", "de", "van",
              "Jones Smith")
    parsers = [Parser(),
               Parser(policy=Policy(unlisted_dotted_suffixes=False)),
               Parser(policy=Policy(unlisted_caps_suffixes=True))]
    failures = []
    multi = 0
    for head in heads:
        for body in bodies:
            for base in members:
                for word in (base.lower(), base.title(), base.upper()):
                    for marker in ("nee", "née", "geb."):
                        text = f"{head} {marker} {body} {word}"
                        for parser in parsers:
                            claimed: set[object] = set()
                            overlap = False
                            spans = []
                            reports = parser.parse(text).ambiguities
                            multi += len(reports) > 1
                            for a in reports:
                                # a synthetic token has no span; fall
                                # back on its identity so it cannot
                                # collide with another report's
                                span = {t.span if t.span is not None
                                        else id(t) for t in a.tokens}
                                spans.append(sorted(map(str, span)))
                                overlap = overlap or bool(claimed & span)
                                claimed |= span
                            if overlap:
                                failures.append(f"{text!r}: {spans}")
    # the tails that put the maiden emitter and assign's peel on one
    # parse -- the pair this test is named for, which the grid above
    # cannot produce (see the docstring)
    both = 0
    for head in heads:
        for body in bodies:
            for tail in _TAILS:
                for marker in ("nee", "née", "geb."):
                    text = f"{head} {marker} {body} {tail}"
                    for parser in parsers:
                        claimed = set()
                        overlap = False
                        spans = []
                        reports = parser.parse(text).ambiguities
                        multi += len(reports) > 1
                        kinds = [a.kind for a in reports]
                        both += (kinds.count(
                            AmbiguityKind.SUFFIX_OR_NAME) > 1)
                        for a in reports:
                            span = {t.span if t.span is not None
                                    else id(t) for t in a.tokens}
                            spans.append(sorted(map(str, span)))
                            overlap = overlap or bool(claimed & span)
                            claimed |= span
                        if overlap:
                            failures.append(f"{text!r}: {spans}")
    assert not failures, (
        f"{len(failures)} parse(s) report one token twice:\n"
        + "\n".join(failures[:15]))
    assert multi == 4320, (
        f"{multi} of these parses carry more than one report, recorded "
        f"as 4320 on 2026-09-19. A parse with one report cannot fail "
        f"the check above, so this is what keeps the grid honest: move "
        f"the number deliberately, and never to 0")
    assert both == 1944, (
        f"{both} parse(s) carry TWO suffix-or-name reports, recorded "
        f"as 1944 on 2026-09-19. This is the pair the test is named "
        f"for -- the maiden emitter against assign's trailing peel -- "
        f"and it was 0 for the whole grid until the two-member tails "
        f"were added. Never re-record it as 0")


@pytest.mark.parametrize("text", _FORK_CORPUS)
def test_a_fork_is_never_reported_twice_on_a_real_name(text: str) -> None:
    state = run(ParseState(original=text, lexicon=Lexicon.default(),
                           policy=Policy()))
    assert _fork_count(state) <= 1


@given(st.text(alphabet=_ALPHABET, max_size=120))
@settings(max_examples=400, deadline=None, derandomize=True)
def test_particle_fork_is_never_double_reported(text: str) -> None:
    # The half of the invariant that needs no reconstruction: whatever
    # the two emitters decide, they must not both fire on one parse.
    state = run(ParseState(original=text, lexicon=Lexicon.default(),
                           policy=Policy()))
    assert _fork_count(state) <= 1, (
        f"{text!r} reported the same fork more than once")


# ---------------------------------------------------------------- config
# Everything above fuzzes the INPUT STRING against the default
# configuration. That leaves 2.0's largest new surface -- Lexicon and
# Policy -- covered only by hand-written cases, which is backwards: the
# vocabulary and the switches are the parts a user is invited to
# change, so they are the parts most likely to be given a combination
# nobody tried.

# Deliberately mixed: real vocabulary, one-letter words that collide
# with initials, an interior period, and non-Latin entries. Nothing
# here normalizes to empty, which Lexicon rejects outright. No
# multi-word phrase: every field below except given_name_titles is
# matched one word at a time, so a multi-word draw in a per-word field
# would be a dead entry that trips Lexicon's multi-word warning.
# The CJK tail (#271) is what lets a drawn `surnames` set activate
# script_segment at all: hangul is the script segmented by default, so
# "김"/"남궁"/"남" are what make the stage fire (see _names_using, which
# supplies the unspaced token to fire it ON -- and, since the drawn
# policy picks its own segment_scripts, only when that policy
# activates hangul too). "남" is there for the stage's multi-match
# FORK, which nothing else in this pool can reach: it is a proper
# PREFIX of "남궁", so a lexicon drawn with both makes "남궁민준" match
# twice, and longest-first then has to choose and report the reading
# it passed over. Reachable is all it is -- both entries have to land
# in the same drawn `surnames`, 0.8% of draws, so the fork fires
# roughly once in 900 examples (42 over 36000 measured) and the
# committed 250-example seed does not reach it at all; a randomized
# run is what sees it. The Han rows ride along for script_orders, and
# are not inert here either -- `_policies` draws segment_scripts
# freely, so HAN is activated in 37.7% of drawn policies (measured
# over 20000 draws), and an activated Han token STANDING EARLIER takes
# the surname site: "欧阳 김민준" does not split, where "김민준 欧阳"
# does. What these policies never draw is a locale PACK, which is the
# only way shipped configuration turns Han segmentation on.
_VOCAB = st.sampled_from([
    "van", "de", "la", "bin", "abdul", "abu", "dr", "sir", "prof",
    "md", "jr", "iii", "esq", "ma", "do", "and", "y", "née", "geb",
    "a", "b", "ph.d", "عبد", "фон", "μεγα",
    "김", "남궁", "남", "毛", "欧阳",
])

# given_name_titles is the one field matched as a space-joined run, so
# a multi-word phrase there is meaningful (not dead) and must not warn.
# Derived from _VOCAB rather than duplicated, so the two pools cannot
# drift apart.
_TITLE_VOCAB = st.one_of(_VOCAB, st.just("grand duke"))


def _fix_invariants(**fields: frozenset[str]) -> dict[str, frozenset[str]]:
    """Repair a random draw into a legal Lexicon instead of generating
    one legally.

    Drawing dependent subsets directly (particles_ambiguous from
    whatever particles happened to be drawn) makes the strategy tree
    deep and mostly rejects; intersecting after the fact keeps every
    draw usable and still reaches every shape. The five rules are
    Lexicon's own, restated here on purpose -- if one changes, this
    fails loudly rather than silently fuzzing a narrower space.
    """
    fields["particles_ambiguous"] &= fields["particles"]
    fields["suffix_acronyms_ambiguous"] &= fields["suffix_acronyms"]
    fields["suffix_words"] -= fields["suffix_acronyms_ambiguous"]
    # order matters: must run AFTER the suffix_words subtraction above,
    # or that later subtraction could re-orphan a tail this repair just
    # fixed
    fields["honorific_tails"] &= fields["suffix_words"]
    fields["bound_given_names"] -= (
        fields["particles"] - fields["particles_ambiguous"])
    return fields


# Derived, never listed: a new vocabulary field must be fuzzed the day
# it is added, and a hand-copied list would leave it silently unfuzzed
# -- the invisible gap this whole layer exists to prevent.
_SET_FIELDS = _VOCAB_FIELDS


@st.composite
def _lexicons(draw: st.DrawFn) -> Lexicon:
    fields = {name: draw(st.frozensets(
        _TITLE_VOCAB if name == "given_name_titles" else _VOCAB,
        max_size=5))
              for name in _SET_FIELDS}
    caps = draw(st.lists(st.tuples(_VOCAB, _VOCAB), max_size=3))
    return Lexicon(capitalization_exceptions=tuple(caps),
                   **_fix_invariants(**fields))


# script_orders' legal values are as restricted as name_order's (only
# the three exported orders, keyed by Script), so they are sampled
# rather than generated. The five cover the axes that matter: the
# shipped default, the full opt-out, one script alone, an order that
# disagrees with the default -- FAMILY_FIRST_GIVEN_LAST on hangul
# reads "김민준 수" differently from every other entry here, which is
# what makes a script table that is merely PRESENT distinguishable
# from one that is actually consulted -- and a table keyed on the kana
# license's carrier (#272). That last row is the only one whose key is
# reached INDIRECTLY: a mixed kanji+kana name resolves to HIRAGANA
# rather than to any script it is literally written in, and pointing
# the carrier back at GIVEN_FIRST makes a consulted table visibly
# different from the default it would otherwise agree with.
_SCRIPT_ORDER_TABLES = [
    DEFAULT_SCRIPT_ORDERS,
    (),
    ((Script.HAN, FAMILY_FIRST),),
    ((Script.HANGUL, FAMILY_FIRST_GIVEN_LAST),),
    ((Script.HIRAGANA, GIVEN_FIRST),),
]


@st.composite
def _policies(draw: st.DrawFn) -> Policy:
    pairs = st.sampled_from([("(", ")"), ('"', '"'), ("'", "'"),
                             ("[", "]"), ("«", "»")])
    nickname = draw(st.frozensets(pairs, max_size=2))
    # a pair may not sit in both buckets; Policy canonicalizes overlap
    # away, but constructing the contradiction is not what this fuzzes
    maiden = draw(st.frozensets(pairs, max_size=2)) - nickname
    return Policy(
        name_order=draw(st.sampled_from(
            [GIVEN_FIRST, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST])),
        script_orders=draw(st.sampled_from(_SCRIPT_ORDER_TABLES)),
        # no max_size: Script has four members, so the unbounded draw
        # still reaches every subset -- including the empty one, which
        # is the documented segmentation opt-out, and the full one,
        # which turns on the Han and kana activation that only
        # locales.ZH and locales.JA turn on in shipped configuration
        segment_scripts=draw(st.frozensets(st.sampled_from(list(Script)))),
        patronymic_rules=draw(st.frozensets(
            st.sampled_from(list(PatronymicRule)), max_size=2)),
        middle_as_family=draw(st.booleans()),
        nickname_delimiters=nickname,
        maiden_delimiters=maiden,
        extra_suffix_delimiters=draw(
            st.frozensets(st.sampled_from(["/", ";", "|"]), max_size=2)),
        lenient_comma_suffixes=draw(st.booleans()),
        strip_emoji=draw(st.booleans()),
        strip_bidi=draw(st.booleans()),
    )


@st.composite
def _names_using(draw: st.DrawFn, lexicon: Lexicon,
                 policy: Policy) -> str:
    """Build the input out of the lexicon's OWN words.

    Fuzzing configuration while feeding unrelated text tests almost
    nothing: a randomly generated string essentially never contains a
    randomly generated vocabulary entry, so every configured set would
    sit unused and the parse would take the same path every time.

    Takes the POLICY as well as the lexicon because one of the shapes
    below is only reachable when the two agree -- see the segmentation
    note.
    """
    vocab = sorted({w for name in _SET_FIELDS
                    for w in getattr(lexicon, name)})
    # script_segment (#271, #308) holds the two halves a space-joined
    # name can never reach, and BOTH need their token derived from the
    # draw: waiting for a drawn entry and a matching literal to
    # coincide leaves the stage unexercised. The surname half splits an
    # unspaced token whose PREFIX is a drawn surname; the peel splits a
    # listed tail off the END of one. The peel's line was added after a
    # mutation pass asked the same question of it and instrumentation
    # answered: 14 fires across this file, every one under the DEFAULT
    # lexicon and none under a drawn one, because no generated token
    # ended in a drawn tail. Deriving it moves that off zero.
    # A Latin entry is useful input in its own right: it makes a
    # mixed-script token the surname half correctly declines, and for
    # the peel it is the one shape that reaches an ASCII tail at all --
    # the stage bails on a wholly-ASCII original, so the non-Latin stem
    # is what admits '민준jr'. Every peel fire observed under a drawn
    # lexicon is of exactly that shape -- the committed run's is
    # '민준de'.
    # What the forced insertion below is worth, in the one number that
    # cannot rot: instrument _split under this test's committed
    # derandomize=True seed -- peel and surname split are told apart by
    # its tail_tag argument -- and origin/master's version of this
    # strategy counts ZERO surname splits against two peels, while this
    # one counts 23 against one. That figure is reproducible by anyone
    # in one command and moves only when these strategies do.
    # Being in the POOL is not the same as being in the NAME, and for
    # the surname half that gap was the whole story. Two things must
    # coincide before the shape is legal at all -- a HANGUL surname
    # drawn AND a policy that activates hangul, together 5.5% of draws
    # over 20000 -- and the token then has to win a place in a 1-8
    # piece name against a pool of median size 23. Merely offered, it
    # reached the name a couple of times per 250. The shortfall was
    # sampling, never the stage.
    # What that buys is COVERAGE, not detection, and the two are worth
    # separating because the first is the easier to oversell. This
    # layer asserts totality and span-exactness only, so every
    # BEHAVIORAL mutant in the stage -- the site's last-token scan,
    # shortest-first, the whole-token guard, the activation gate, the
    # post-nominal decline, the prefix cap, the segment remap -- passes
    # here with the insertion and without it, and is killed by
    # tests/v2/pipeline/test_script_segment.py instead. The one defect
    # class this layer CAN catch is span arithmetic inside _split, and
    # the peel already reached that path. Writing `base + end` as
    # `base + end + 1` and giving each tree ten randomized runs of 250:
    # origin/master finds it in 8 runs of 10, at a median 1561 shrink
    # calls and 14.6 seconds; this tree finds it in 10 of 10, at 346
    # calls and 3.6 seconds, and shrinks to '김민준 김' where master
    # shrinks to the peel's '민준van'. st.integers shrinks the
    # insertion index toward 0, which walks the token into the position
    # likeliest to fire instead of away from it.
    # Alignment is still not a guarantee: with the token forced in the
    # split fires in about four aligned examples in five (350 of 450,
    # over 24 randomized runs of 250). Every decline is the stage
    # deciding, not waste. A FAMILY_COMMA opts the stage out whole -- a
    # ',' piece is in the pool. Otherwise an EARLIER script-written
    # token takes the surname site: a bare drawn surname ('김 김민준'
    # leaves 김민준 unsplit -- the whole-token guard), a drawn hangul
    # post-nominal (the leading post-nominal decline), or a Han token
    # under a policy that activated HAN. A LATIN word never takes it --
    # 'John 김민준' still splits, zero occurrences in 1082 aligned
    # examples -- which is why the insertion index is drawn rather than
    # pinned to 0.
    # Two earlier versions of this comment overstated this half from
    # small samples -- one calling it "structurally inert, not luck" on
    # a single derandomize=True run reporting zero, one putting the
    # conversion above at 100%. So: a derandomize=True run is one
    # sample and cannot disagree with itself, and every randomized
    # figure quoted here was taken under derandomize=False instead,
    # which is how to re-measure them. The structural claim is real but
    # narrower than it was made: `w + "민준"` on a NON-hangul surname is
    # a mixed-script token whose effective_script is None, so those
    # candidates can never be a site whatever the policy says. Only a
    # drawn hangul surname makes a usable one, which is what
    # `activatable` selects.
    # Two shapes the insertion costs, both small, neither zero. It is
    # unconditional once lexicon and policy align, so the stage's
    # i-is-None early return under a LIVE configuration fell from 1.3%
    # of examples to 0.1%: it survives only where a drawn quote pair
    # carries the token off into a nickname, leaving segments[0] with
    # nothing in an activated script ("prof ' Smith 남민준 '"). And the
    # inserted token can SUPPRESS a peel, the peel site being the last
    # non-post-nominal token and this token being no post-nominal:
    # '김민준씨 김민준' leaves 씨 glued where '김민준 김민준씨' peels
    # it.
    # The peel gets no forced piece of its own -- it is saturated by
    # case rows and stage tests, so a second one was not worth the
    # distribution shift -- and its count here is a lottery either way
    # (0-7 per randomized run of 250). On net the insertion nudges it
    # UP, by a route worth knowing: a hangul token makes the original
    # non-ASCII, which lifts the stage's ASCII bail off Latin tails
    # that are otherwise unreachable -- under honorific_tails={'a'},
    # 'John la' does not peel and '김민준 la' does.
    # sorted for the same reason `vocab` above is: frozenset iteration
    # order is not stable across runs, and an unsorted pool shifts
    # every index sampled_from draws -- which would defeat
    # derandomize=True on the whole strategy, not just this slice.
    unspaced = sorted(w + "민준" for w in lexicon.surnames)
    glued = sorted("민준" + w for w in lexicon.honorific_tails)
    # plain names and structure characters are always available, so the
    # pool is never empty even for an empty lexicon
    pieces = st.sampled_from(
        vocab + unspaced + glued + ["John", "Smith", "Q.", ",", "(", "'"])
    drawn = draw(st.lists(pieces, min_size=1, max_size=8))
    # The one shape the pool does not deliver RELIABLY -- it is in
    # there, it just loses the draw. Inserted at a drawn position
    # rather than the front: the stage takes the first ACTIVATED-script
    # token, not the first token, so a leading Latin word cannot hide
    # it -- and both placements are worth covering.
    activatable = sorted(
        w + "민준" for w in lexicon.surnames
        if effective_script(w + "민준") in policy.segment_scripts)
    if activatable:
        # rebuilt rather than list.insert()d: st.lists hands back a
        # fresh list today, so mutating it is safe today, and a
        # strategy that ever memoized one would make this a bug in the
        # fuzzer rather than in the code under test
        at = draw(st.integers(0, len(drawn)))
        token = draw(st.sampled_from(activatable))
        drawn = [*drawn[:at], token, *drawn[at:]]
    return " ".join(drawn)




def _quiet_parser(**kwargs: object) -> Parser:
    """Parser construction with the segmenterless-activation warning
    ignored: a drawn segment_scripts with a drawn vocabulary that
    cannot serve it is exactly the misconfiguration the warning names,
    so drawn configs hit it legitimately and constantly. The fuzz here
    targets parse behavior, not construction diagnostics --
    tests/v2/test_parser.py pins the warning itself."""
    with warnings.catch_warnings():
        # message-scoped, not a blanket UserWarning ignore: a future
        # unrelated construction diagnostic should still fail the fuzz
        warnings.filterwarnings(
            "ignore", message=r"Policy\.segment_scripts activates")
        return Parser(**kwargs)  # type: ignore[arg-type]


@given(_lexicons(), _policies(), st.data())
@settings(max_examples=250, deadline=None, derandomize=True)
def test_any_valid_config_still_parses_totally(
        lexicon: Lexicon, policy: Policy, data: st.DataObject) -> None:
    # Building the parser is part of the contract: a Lexicon and Policy
    # that each constructed must also combine.
    parser = _quiet_parser(lexicon=lexicon, policy=policy)
    text = data.draw(_names_using(lexicon, policy))
    parsed = parser.parse(text)          # must not raise, ever
    # the anti-#100 invariant, under configuration rather than under
    # the default vocabulary: spans index the original exactly
    for token in parsed.tokens:
        assert token.span is not None
        assert token.text == parsed.original[
            token.span.start:token.span.end]
    # rendering is downstream of every config choice above
    assert isinstance(str(parsed), str)
    assert isinstance(parsed.capitalized().given, str)
    assert isinstance(parsed.initials(), str)


@given(_lexicons(), _policies())
@settings(max_examples=100, deadline=None, derandomize=True)
def test_config_values_are_hashable_and_reusable(
        lexicon: Lexicon, policy: Policy) -> None:
    # The docs promise these are frozen values: safe as dict keys, and
    # safe to build a parser from more than once.
    assert hash(lexicon) == hash(lexicon)
    assert {lexicon: 1, policy: 2}
    assert _quiet_parser(lexicon=lexicon, policy=policy) == \
        _quiet_parser(lexicon=lexicon, policy=policy)


# Values a real caller plausibly passes by mistake: the bare string that
# iterates into characters, a mapping confused for a set, bytes, None,
# and entries that normalize to nothing.
_HOSTILE = st.sampled_from([
    None, 0, 1, True, "", "dr", "  ", ".", b"dr", ["dr", None],
    {"dr": "Dr"}, {1, 2}, [("a", "b")], [[]], object(),
])

# Same rule as _SET_FIELDS; test_policy.py already reflects this way.
_POLICY_FIELDS = tuple(f.name for f in dataclasses.fields(Policy))


@given(st.sampled_from(_SET_FIELDS + ("capitalization_exceptions",)),
       _HOSTILE)
@settings(max_examples=200, deadline=None, derandomize=True)
def test_bad_lexicon_field_fails_cleanly(field: str, value: object) -> None:
    """A rejected configuration must be a DOCUMENTED rejection.

    ValueError and TypeError are the contract; anything else means the
    bad value got past validation and blew up somewhere downstream,
    where the message no longer names the field the caller typed.
    """
    try:
        lexicon = Lexicon(**{field: value})     # type: ignore[arg-type]
    except (ValueError, TypeError):
        return
    # Accepted, so it has to survive an actual parse -- construction
    # succeeding while parsing dies is the same bug one stage later.
    _quiet_parser(lexicon=lexicon).parse("Dr. John de la Vega III")


@given(st.sampled_from(_POLICY_FIELDS), _HOSTILE)
@settings(max_examples=200, deadline=None, derandomize=True)
def test_bad_policy_field_fails_cleanly(field: str, value: object) -> None:
    try:
        policy = Policy(**{field: value})       # type: ignore[arg-type]
    except (ValueError, TypeError):
        return
    _quiet_parser(policy=policy).parse("Dr. John de la Vega III")


# --- #397/#461: the connective grid, and its five invariants --------
# A GRID and not a name list, for the reason #531's agreement sweep
# was one: every invariant below is stated about a shape the parser
# can reach in many ways, and a list pins the ways somebody thought
# of. Generators include heads with NO name word, parts of one word,
# a part that is nothing but the connective, comma and no-comma,
# mixed/ALL-CAPS/lower, class members supplied by a CUSTOM lexicon
# (a second single letter that is also generational vocabulary, and a
# connective that is also particle vocabulary), and four policies.


def _connective_grid() -> list[tuple[str, Parser, str]]:
    heads: tuple[list[str], ...] = (
        [], ["Josep"], ["Josep", "Lluis"], ["Dr."], ["Dr.", "Josep"])
    mids: tuple[list[str], ...] = (
        [], ["Carod"], ["de", "Carod"], ["Carod", "Rovira"])
    conns = ("i", "y", "e", "and", "&", "of", "и")
    tails: tuple[list[str], ...] = (
        [], ["Rovira"], ["de", "Rovira"], ["Rovira", "Puig"])
    suffixes: tuple[list[str], ...] = (
        [], ["III"], ["Jr."], ["I"], ["MA"])
    lexicons = (("default", Lexicon.default()),
                ("conj+v", Lexicon.default().add(conjunctions={"v"})),
                ("part+y", Lexicon.default().add(particles={"y"})))
    policies = (("default", Policy()),
                ("family-first", Policy(name_order=FAMILY_FIRST)),
                ("given-last", Policy(name_order=FAMILY_FIRST_GIVEN_LAST)),
                ("strict-comma", Policy(lenient_comma_suffixes=False)))
    texts: list[str] = []
    seen: set[str] = set()
    for head, mid, conn, tail, suffix, comma in itertools.product(
            heads, mids, conns, tails, suffixes, (False, True)):
        if not (mid or tail):
            continue
        if comma and tail:
            base = " ".join(tail) + ", " + " ".join(head + mid + [conn])
        else:
            base = " ".join(head + mid + [conn] + tail)
        base = (base + " " + " ".join(suffix)).strip()
        for written in (base, base.upper(), base.lower()):
            if written not in seen:
                seen.add(written)
                texts.append(written)
    parsers = [(f"{ln}/{pn}", Parser(lexicon=lex, policy=pol))
               for ln, lex in lexicons for pn, pol in policies]
    return [(t, p, label) for t in texts for label, p in parsers]


_CONNECTIVE_GRID = _connective_grid()


def _readmitted(tok: Token) -> bool:
    return not {UNJOINED_TAG, UNJOINED_CONJUNCTION_TAG}.isdisjoint(tok.tags)


def _has_something_to_join(tok: Token, part: tuple[Token, ...]) -> bool:
    """rules.md#R3's question, asked of the WHOLE PART.

    Working particles are set aside -- a particle the unjoined mark
    has NOT readmitted is doing a particle's work and is no name word
    for a connective to join.
    """
    return any(other is not tok
               and "conjunction" not in other.tags
               and not ("particle" in other.tags
                        and UNJOINED_TAG not in other.tags)
               for other in part)


def _predicted_initials(part: tuple[Token, ...], role: Role) -> list[str]:
    out = []
    for tok in part:
        skip = ("conjunction" in tok.tags
                or ("particle" in tok.tags and role is not Role.GIVEN))
        if not skip or _readmitted(tok):
            out.append(tok.text[0])
    return out


def test_the_connective_grid_can_fail() -> None:
    """The reachability probe every grid in this file carries.

    A grid that reaches none of the shapes it is about passes
    vacuously, and a comparison over a population of zero is the same
    silence as a clean run. These three counts are a dated recorded
    control, measured 2026-09-20 on the shipped tree.
    """
    assert len(_CONNECTIVE_GRID) == 170100, len(_CONNECTIVE_GRID)
    assert len({t for t, _, _ in _CONNECTIVE_GRID}) == 14175
    joined = sum(1 for text, parser, _ in _CONNECTIVE_GRID[:2000]
                 if any("conjunction" in tok.tags
                        for tok in parser.parse(text).tokens))
    assert joined > 500, joined


def test_a_generational_connective_joins_only_with_both_sides() -> None:
    """INV1 (#397). For a single-letter connective that is ALSO
    generational vocabulary: if it shares its role part with any other
    word, a non-connective word stands before it AND after it.

    Mutation-checked, 2026-09-20: dropping the position test fails
    this on 1575 parses, dropping the whole both-sides condition on
    504, and dropping the rootname count arm on 816. The CLASS test
    is NOT covered here and has its own rows -- see
    tests/v2/pipeline/test_group.py.
    """
    failures = []
    for text, parser, label in _CONNECTIVE_GRID:
        letters = {w for w in parser.lexicon.conjunctions
                   if len(w) == 1 and w in parser.lexicon.suffix_words}
        name = parser.parse(text)
        for role in (Role.GIVEN, Role.MIDDLE, Role.FAMILY):
            part = name.tokens_for(role)
            if len(part) < 2:
                continue
            for i, tok in enumerate(part):
                if ("conjunction" not in tok.tags or len(tok.text) != 1
                        or tok.text.lower() not in letters):
                    continue
                left = any("conjunction" not in t.tags for t in part[:i])
                right = any("conjunction" not in t.tags for t in part[i + 1:])
                if not (left and right):
                    failures.append(
                        f"[{label}] {text!r}: {role.value} {tok.text!r}")
    assert not failures, (
        f"{len(failures)} parse(s) joined a generational connective "
        f"without a name word on each side:\n" + "\n".join(failures[:10]))


def test_the_mark_is_exactly_the_parts_with_nothing_to_join() -> None:
    """INV2 (#461). A connective carries a readmitting mark IFF its
    part holds no other word that is neither a connective nor a
    working particle.

    Stated over the PAIR of marks deliberately: keyed on the new mark
    alone it fails 366 times under `add(particles={"y"})`, where the
    part is all-particle and R2's OLD mark does the readmitting.
    Mutation-checked: dropping the new mark fails this on 14,066.
    """
    failures = []
    for text, parser, label in _CONNECTIVE_GRID:
        name = parser.parse(text)
        for role in (Role.GIVEN, Role.MIDDLE, Role.FAMILY):
            part = name.tokens_for(role)
            for tok in part:
                if "conjunction" not in tok.tags:
                    continue
                if _has_something_to_join(tok, part) == _readmitted(tok):
                    failures.append(
                        f"[{label}] {text!r}: {role.value} {tok.text!r} "
                        f"joinable={_has_something_to_join(tok, part)} "
                        f"marked={_readmitted(tok)}")
    assert not failures, (
        f"{len(failures)} connective token(s) disagree with the "
        f"criterion:\n" + "\n".join(failures[:10]))


def test_initials_take_only_base_words_and_drop_only_joiners() -> None:
    """INV3 and INV4, beside R2's existing invariant.

    INV3: every family word `initials()` contributes is a word of
    `family_base`. INV4: every `family_base` word that contributes no
    initial is tagged conjunction. Together they say the two views of
    one parse cannot come apart again, which is the defect #461 was
    filed about.

    Mutation-checked: swapping the two branches of the mark walk fails
    this on 188 parses (`Carod y` under `add(particles={"y"})`, whose
    base is empty while its `y` initials).
    """
    failures = []
    for text, parser, label in _CONNECTIVE_GRID:
        name = parser.parse(text)
        family = name.tokens_for(Role.FAMILY)
        base = name.family_base.split()
        contributing = [t for t in family
                        if t.text[0] in _predicted_initials(family,
                                                            Role.FAMILY)
                        and (not ("conjunction" in t.tags
                                  or "particle" in t.tags)
                             or _readmitted(t))]
        for tok in contributing:
            if tok.text not in base:
                failures.append(
                    f"[{label}] {text!r}: INV3 {tok.text!r} initials but "
                    f"is not in base {base!r}")
        for tok in family:
            if (tok.text in base and tok not in contributing
                    and "conjunction" not in tok.tags):
                failures.append(
                    f"[{label}] {text!r}: INV4 {tok.text!r} is a base "
                    f"word, contributes no initial, and is no connective")
    assert not failures, (
        f"{len(failures)} disagreement(s) between initials() and "
        f"family_base:\n" + "\n".join(failures[:10]))


def test_initials_emit_exactly_the_predicted_contributors() -> None:
    """INV5. Per group, `initials("{role}")` emits exactly the words
    the criterion predicts, in field order.

    The output-level statement of the same rule, and the one that
    catches a view reading the marks correctly and then rendering
    something else. Mutation-checked: restoring the given group's old
    blanket exemption fails this on 27,343 parses, and dropping the
    new mark from the readmitting set on 14,066.
    """
    failures = []
    for text, parser, label in _CONNECTIVE_GRID:
        name = parser.parse(text)
        for role in (Role.GIVEN, Role.MIDDLE, Role.FAMILY):
            predicted = _predicted_initials(name.tokens_for(role), role)
            got = name.initials(
                f"{{{role.value}}}").replace(".", "").split()
            if got != predicted:
                failures.append(
                    f"[{label}] {text!r}: {role.value} {got!r} != "
                    f"predicted {predicted!r}")
    assert not failures, (
        f"{len(failures)} group(s) emitted something other than the "
        f"criterion's contributors:\n" + "\n".join(failures[:10]))


# --- #397 review: the OFF-SWITCH grid, and its two invariants -------
# A second grid, kept apart from the one above rather than folded
# into it, and the reason is the cost: both invariants below parse
# every entry TWICE -- once as configured and once with the class
# letter out of the connective vocabulary -- so the shapes that
# earned a place here are the ones the first cut of #397 got wrong,
# not every shape the file already covers. What this one adds over
# `_connective_grid`: the trailing numeral and bare acronym assign's
# peel takes ('V', 'i', beside the 'III'/'Jr.'/'I'/'MA' both carry),
# a maiden clause, a head that is nothing but an initial or a
# particle, and the SUFFIX comma as a third comma shape.


def _off_switch_grid() -> list[tuple[str, Parser, str]]:
    heads: tuple[list[str], ...] = (
        [], ["Josep"], ["Josep", "Lluis"], ["Dr."], ["J."], ["van"],
        ["Josep", "Lluis", "Marti"])
    mids: tuple[list[str], ...] = ([], ["Carod"], ["de", "Carod"])
    conns = ("i", "y", "e", "and")
    tails: tuple[list[str], ...] = ([], ["Rovira"], ["de", "Rovira"])
    suffixes: tuple[list[str], ...] = (
        [], ["III"], ["Jr."], ["I"], ["V"], ["MA"], ["i"], ["nee", "Puig"])
    lexicons = (("default", Lexicon.default()),
                ("conj+v", Lexicon.default().add(conjunctions={"v"})))
    policies = (("default", Policy()),
                ("family-first", Policy(name_order=FAMILY_FIRST)),
                ("given-last", Policy(name_order=FAMILY_FIRST_GIVEN_LAST)),
                ("strict-comma", Policy(lenient_comma_suffixes=False)))
    texts: list[str] = []
    seen: set[str] = set()
    for head, mid, conn, tail, suffix, comma in itertools.product(
            heads, mids, conns, tails, suffixes, (0, 1, 2)):
        if not (mid or tail):
            continue
        if comma == 1 and not tail:
            continue
        if comma == 2 and not suffix:
            continue
        front = head + mid + [conn]
        if comma == 1:
            base = " ".join(tail) + ", " + " ".join(front + suffix)
        elif comma == 2:
            base = " ".join(front + tail) + ", " + " ".join(suffix)
        else:
            base = " ".join(front + tail + suffix)
        for written in (base, base.upper(), base.lower()):
            if written not in seen:
                seen.add(written)
                texts.append(written)
    parsers = [(f"{ln}/{pn}", Parser(lexicon=lex, policy=pol))
               for ln, lex in lexicons for pn, pol in policies]
    return [(t, p, label) for t in texts for label, p in parsers]


_OFF_SWITCH_GRID = _off_switch_grid()
_NAME_ROLES = (Role.GIVEN, Role.MIDDLE, Role.FAMILY)
_OFF_PARSERS: dict[tuple[int, frozenset[str]], Parser] = {}


def _class_letters(lexicon: Lexicon) -> frozenset[str]:
    """The class rules.md#P3's both-sides condition is about: a
    one-letter connective that is ALSO generational vocabulary."""
    return frozenset(w for w in lexicon.conjunctions
                     if len(w) == 1 and w in lexicon.suffix_words)


def _off_switch(parser: Parser, letters: frozenset[str]) -> Parser:
    """The same parser with those letters out of the connectives --
    the parent-equivalent reading, where nothing can have joined.

    Keyed by `id`, which is safe here and nowhere else: the grid above
    holds every parser for the module's lifetime, so no id is reused.
    A `Parser` is not hashable (its `Lexicon` carries a mappingproxy).
    """
    key = (id(parser), letters)
    if key not in _OFF_PARSERS:
        _OFF_PARSERS[key] = Parser(
            lexicon=parser.lexicon.remove(conjunctions=set(letters)),
            policy=parser.policy)
    return _OFF_PARSERS[key]


def _present(text: str, letters: frozenset[str]) -> frozenset[str]:
    words = {w.strip(".,").lower() for w in text.split()}
    return frozenset(letters & words)


_Placed = tuple[Token, tuple[int, int]]


def _placed(name: ParsedName) -> list[_Placed]:
    """The parse's tokens with their spans, spliced ones dropped."""
    return [(tok, tok.span) for tok in name.tokens if tok.span is not None]


def _off_roles(off: ParsedName) -> dict[tuple[int, int], Role]:
    return {span: tok.role for tok, span in _placed(off)}


def _name_word_beside(toks: list[_Placed], i: int, step: int,
                      off_role: dict[tuple[int, int], Role],
                      original: str) -> bool:
    """Whether a name word stands on the `step` side of toks[i],
    judged by the OFF-SWITCH parse's roles -- which is what makes
    this a PRE-JOIN reading: in that parse the class letter is no
    connective, so no join has moved anything. A comma between ends
    the walk (it is another segment), and connectives are stepped
    over because a run of them joins as one."""
    j = i
    while True:
        k = j + step
        if not 0 <= k < len(toks):
            return False
        left, right = (j, k) if step > 0 else (k, j)
        if "," in original[toks[left][1][1]:toks[right][1][0]]:
            return False
        j = k
        if "conjunction" in toks[j][0].tags:
            continue
        return off_role.get(toks[j][1]) in _NAME_ROLES


def _initial_spans(name: ParsedName,
                   letters: frozenset[str]) -> set[tuple[int, int]]:
    return {span for tok, span in _placed(name)
            if "initial" in tok.tags and tok.text.lower() in letters}


def _initial_reading_moved(on: ParsedName, off: ParsedName,
                           letters: frozenset[str]) -> bool:
    """Whether the two parses disagree about a class letter being an
    INITIAL -- rules.md#P3's marked-subset clause rather than its
    both-sides one, and the one thing an off-switch comparison cannot
    hold fixed: taking the word out of the connectives decides that
    question too, in either direction. A marked letter in a one-case
    name reads as an initial only while it IS connective vocabulary;
    a bare capital the caller's own connectives claim stops reading
    as one."""
    return _initial_spans(on, letters) != _initial_spans(off, letters)


def _link_joins_between_name_words(on: ParsedName, off: ParsedName,
                                   letters: frozenset[str]) -> bool:
    off_role = _off_roles(off)
    toks = _placed(on)
    for i, (tok, _span) in enumerate(toks):
        if ("conjunction" not in tok.tags
                or tok.text.lower() not in letters):
            continue
        if (_name_word_beside(toks, i, -1, off_role, on.original)
                and _name_word_beside(toks, i, 1, off_role, on.original)):
            return True
    return False


def test_the_off_switch_grid_can_fail() -> None:
    """The reachability probe, the shape every grid in this file
    carries. Dated recorded control, measured 2026-09-20."""
    assert len(_OFF_SWITCH_GRID) == 103040, len(_OFF_SWITCH_GRID)
    assert len({t for t, _, _ in _OFF_SWITCH_GRID}) == 12880
    reached = sum(1 for text, parser, _ in _OFF_SWITCH_GRID[:4000]
                  if _present(text, _class_letters(parser.lexicon)))
    assert reached > 1000, reached


def test_a_link_that_joins_nothing_changes_no_field() -> None:
    """INV6 (#397 review), and the strongest thing this rule can be
    asked: turning the class letter OFF is the parent's reading, so
    a letter that joins nothing must leave every field where the
    parent left it.

    Two exemptions, both narrow and both P3's own OTHER clauses. A
    letter that JOINED between name words is the rule working, judged
    on the off-switch parse's classes so an absorbed suffix cannot
    pass itself off as the name word on the right. And a letter the
    two parses disagree about being an INITIAL is the marked-subset
    clause, which the switch decides along with the join and so
    cannot hold fixed.

    Mutation-checked, 2026-09-20: this fails on 2,360 parses at
    c8550b64, the commit the review was written against.
    """
    failures = []
    for text, parser, label in _OFF_SWITCH_GRID:
        letters = _present(text, _class_letters(parser.lexicon))
        if not letters:
            continue
        on = parser.parse(text)
        off = _off_switch(parser, letters).parse(text)
        # the SEVEN FIELDS, and not comparison_key: a parse carries
        # more than its fields, and what the off-switch legitimately
        # moves besides them is the conjunction-or-initial report
        if on.as_dict() == off.as_dict():
            continue
        if _link_joins_between_name_words(on, off, letters):
            continue
        if _initial_reading_moved(on, off, letters):
            continue
        failures.append(f"[{label}] {text!r}: {on.as_dict()} != "
                        f"off-switch {off.as_dict()}")
    assert not failures, (
        f"{len(failures)} parse(s) moved a field with no link joining "
        f"anything:\n" + "\n".join(failures[:10]))


def test_a_trailing_credential_never_joins_into_a_name_part() -> None:
    """INV1 strengthened (#397 review). INV1 above inspects the part
    a join PRODUCED, where an absorbed credential is itself the name
    word standing on the right, so it is satisfied by the very defect
    it is about -- `Josep Lluis Carod i III` passes it. This asks the
    off-switch parse instead: a word THAT reading puts in the suffix
    never lands inside a joined name part.

    It carries INV6's second exemption and not its first: a letter
    the two parses disagree about being an INITIAL moved for the
    marked-subset clause's reasons, not this one. The JOIN exemption
    is deliberately absent -- a link joining elsewhere in the name
    never licenses a credential joining here.

    Mutation-checked, 2026-09-20: this fails on 960 parses at
    c8550b64, where INV1 fails on none of them.
    """
    failures = []
    for text, parser, label in _OFF_SWITCH_GRID:
        letters = _present(text, _class_letters(parser.lexicon))
        if not letters:
            continue
        on = parser.parse(text)
        off = _off_switch(parser, letters).parse(text)
        if _initial_reading_moved(on, off, letters):
            continue
        off_role = _off_roles(off)
        for role in _NAME_ROLES:
            part = on.tokens_for(role)
            if len(part) < 2:
                continue
            for tok in part:
                # not the LINK itself: it is generational vocabulary
                # by definition of the class, so the off-switch parse
                # reads it as the suffix in every name it ends. This
                # rule is about the OTHER word -- the credential a
                # link must not take with it.
                # `span is None` is a typing guard and nothing else:
                # every token of a PARSER-produced name carries one,
                # and this grid holds no spliced parse.
                if "conjunction" in tok.tags or tok.span is None:
                    continue
                if off_role.get(tok.span) is Role.SUFFIX:
                    failures.append(
                        f"[{label}] {text!r}: {tok.text!r} reads as the "
                        f"suffix and joined into {role.value}")
    assert not failures, (
        f"{len(failures)} credential(s) joined into a name part:\n"
        + "\n".join(failures[:10]))

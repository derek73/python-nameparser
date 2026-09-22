"""Property layer. Hypothesis is a dev dependency only.

The alphabet is punctuation-heavy on purpose: plain st.text() spreads
over all of Unicode, so commas, quotes, and delimiters almost never
appear and the interesting planes go unexercised. derandomize=True
keeps runs reproducible on shared CI runners -- this layer guards
against regressions; exploratory fuzzing happened during review.
"""
import dataclasses
import functools
import hashlib
import itertools
import re
import warnings

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nameparser import (
    DEFAULT_SCRIPT_ORDERS, FAMILY_FIRST, FAMILY_FIRST_GIVEN_LAST,
    GIVEN_FIRST, HumanName, Lexicon, Parser, PatronymicRule, Policy,
    Script, parse,
)
from nameparser.config import Constants
from nameparser._lexicon import _VOCAB_FIELDS
from nameparser._pipeline import run
from nameparser._pipeline._state import (AMBIGUOUS_ACRONYM_TAG,
                                         ParseState)
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
#
# ONE PARSE, MANY CHECKS (2026-09-20). The four invariants below ask
# four questions of the SAME parse, so the grid is walked ONCE, in
# `_connective_findings`, and each test reads its own answers out of
# that walk. Four tests each walking the grid for themselves is what
# took this module from 11s to 115s and CI's build jobs from about 5
# minutes to 17-25 (every parse costs several times more under
# coverage tracing, which is what CI runs). A new invariant over this
# grid joins the walk rather than opening a fifth.


#: A grid's configuration variants: (label, value, the features of a
#: text that reach it). See `_rows`.
_Variants = tuple[tuple[str, Lexicon, frozenset[str]], ...]

#: The policies both grids below run, each with the feature a text
#: must hold for the policy to be distinguishable at all -- see
#: `_rows`.
_GRID_POLICIES: tuple[tuple[str, Policy, frozenset[str]], ...] = (
    ("default", Policy(), frozenset()),
    ("family-first", Policy(name_order=FAMILY_FIRST), frozenset()),
    ("given-last", Policy(name_order=FAMILY_FIRST_GIVEN_LAST),
     frozenset()),
    # lenient_comma_suffixes decides what a COMMA hands to the suffix
    # run, and a name without one has no such hand-off to decide
    ("strict-comma", Policy(lenient_comma_suffixes=False),
     frozenset({","})),
)


def _reaching(text: str) -> frozenset[str]:
    """What of a text a configuration variant could read at all: its
    words, folded the way the vocabulary matches them, plus ',' when
    it carries one."""
    out = {w.strip(".,").lower() for w in text.split()}
    if "," in text:
        out.add(",")
    return frozenset(out)


def _rows(texts: list[str],
          lexicons: _Variants) -> list[tuple[str, Parser, str]]:
    """Every text against the parsers that can read it DIFFERENTLY.

    A variant that ADDS vocabulary changes no parse of a name not
    containing the added word, and `lenient_comma_suffixes` decides
    nothing in a name with no comma, so most of a full cross product
    is one configuration re-deriving another's answer. Each variant
    declares the words that reach it and is paired with the texts
    holding them.

    A SHAPE trim and not a sample -- the TEXTS are untouched, and so
    is every shape class among them; what goes is duplicate pairings.
    Measured 2026-09-20 over the full cross product of both grids:
    177,980 collapsed rows, 0 of them differing from the row they
    collapse onto in fields, token tags and spans, `initials()` on
    every group, the four derived views, `capitalized()` plain and
    forced, or the reports. Reproduce with the signature comparison
    in the commit that introduced this (`test(#397/#461): the
    invariant tests share one parsed grid`).

    Self-maintaining, which a hand-picked subset would not be: give a
    generator below a 'v' word and the conj+v rows come back on their
    own. That is the one to know about -- no text of the connective
    grid holds a standalone 'v', so `conj+v` earns no row there and
    earns them in the off-switch grid, whose suffixes include 'V'.
    """
    parsers = [(f"{ln}/{pn}", Parser(lexicon=lex, policy=pol),
                lex_need | pol_need)
               for ln, lex, lex_need in lexicons
               for pn, pol, pol_need in _GRID_POLICIES]
    out: list[tuple[str, Parser, str]] = []
    for text in texts:
        reach = _reaching(text)
        out += [(text, parser, label)
                for label, parser, need in parsers if need <= reach]
    return out


def _signature(parser: Parser, text: str) -> tuple[object, ...]:
    """Everything the four grids' invariants can read of one parse.

    Used only by the trim's own guard below, which is why it is
    exhaustive rather than cheap: it has to be able to see a
    difference no invariant in this file happens to ask about.
    """
    name = parser.parse(text)
    return (
        tuple(sorted(name.as_dict().items())),
        tuple((t.text, t.role.value, tuple(sorted(t.tags)), t.span)
              for t in name.tokens),
        name.initials(),
        tuple(name.initials(f"{{{r.value}}}") for r in _NAME_ROLES),
        name.family_base, name.family_particles,
        str(parser.capitalized(name)),
        str(parser.capitalized(name, force=True)),
        tuple(sorted((a.kind.value, a.detail,
                      tuple(t.text for t in a.tokens))
                     for a in name.ambiguities)),
    )


#: Every (text, lexicon, policy) the trim drops is checked against
#: the row it collapses onto, one in `_TRIM_STRIDE` of them.
_TRIM_STRIDE = 61


def _dropped_rows(texts: list[str], lexicons: _Variants) -> list[
        tuple[str, tuple[str, Lexicon], tuple[str, Policy],
              tuple[str, Lexicon], tuple[str, Policy]]]:
    """The pairings `_rows` declines, each with the pairing it
    collapses onto: the same text under the variant it could not read
    differently, replaced by the baseline of whichever dimension
    declined.

    Deterministically sampled by stride rather than at random -- a
    random slice makes a failure unreproducible, and the shapes here
    are generated in a fixed order.
    """
    base_lex = lexicons[0]
    base_pol = _GRID_POLICIES[0]
    out = []
    for i, text in enumerate(texts):
        if i % _TRIM_STRIDE:
            continue
        reach = _reaching(text)
        for ln, lex, lex_need in lexicons:
            for pn, pol, pol_need in _GRID_POLICIES:
                if (lex_need | pol_need) <= reach:
                    continue
                twin_lex = (ln, lex) if lex_need <= reach else base_lex[:2]
                twin_pol = (pn, pol) if pol_need <= reach else base_pol[:2]
                out.append((text, (ln, lex), (pn, pol),
                            twin_lex, twin_pol))
    return out


@functools.cache
def _class_letters(lexicon: Lexicon) -> frozenset[str]:
    """The class rules.md#P3's both-sides condition is about: a
    connective that is ALSO generational vocabulary.

    NO LENGTH TEST, matching the rule's own scope and the stage's
    (#397 second review, where a `len(w) == 1` came out of both).
    Measured no-op over every lexicon these grids build: `i` is the
    only member in the default vocabulary and in every locale pack,
    and the two variant lexicons add a one-letter connective and a
    particle.

    Cached on the lexicon -- a frozen, hashable value -- because both
    grids ask this of every row and there are five lexicons between
    them.
    """
    return frozenset(w for w in lexicon.conjunctions
                     if w in lexicon.suffix_words)


#: The two grids' lexicon variants, module-level so
#: `test_every_declared_variant_earns_a_row` can name them. See
#: `_rows` for what the third element of each declares.
_CONNECTIVE_LEXICONS: _Variants = (
    ("default", Lexicon.default(), frozenset()),
    ("conj+v", Lexicon.default().add(conjunctions={"v"}),
     frozenset({"v"})),
    ("part+y", Lexicon.default().add(particles={"y"}),
     frozenset({"y"})))
_OFF_SWITCH_LEXICONS: _Variants = (
    ("default", Lexicon.default(), frozenset()),
    ("conj+v", Lexicon.default().add(conjunctions={"v"}),
     frozenset({"v"})))


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
    return _rows(texts, _CONNECTIVE_LEXICONS)


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


#: The two kinds whose details assert DIFFERENT readings of the same
#: word: one says the letter is read as an initial, the other that it
#: is read as a generational suffix. A token cannot be both, so a
#: token named by both carries a report that contradicts the reading
#: beside it (#397 second review).
_CONTRADICTORY_KINDS = (AmbiguityKind.CONJUNCTION_OR_INITIAL,
                        AmbiguityKind.SUFFIX_OR_NAME)


def _record_contradicting_reports(name: ParsedName, label: str, text: str,
                                  out: list[str]) -> None:
    """INV10 (#397 second review). Two statements of one rule, the
    second wider than the first and both about the same defect.

    rules.md#A1's own sentence, that a report names the reading the
    parse took. The
    connective-or-initial fork offers a connective and an initial and
    says which it took, so a token the parse roles SUFFIX or TITLE
    resolved that fork to NEITHER branch and the report is false on
    its face. And no token may be named by two reports whose details
    assert different readings of it, which is the same defect stated
    without naming a role: 'JOHN QUINCY SMITH I' carried
    connective-or-initial beside suffix-or-name, one saying the
    letter reads as an initial and the other that it reads as the
    generation.

    'i' is the first word that is both a marked connective and suffix
    vocabulary, so this could not arise before this cycle -- which is
    why the invariant is worth writing down now rather than having
    been written down before.
    """
    by_span: dict[tuple[int, int] | None, set[AmbiguityKind]] = {}
    for amb in name.ambiguities:
        for tok in amb.tokens:
            span = None if tok.span is None else (tok.span.start,
                                                  tok.span.end)
            by_span.setdefault(span, set()).add(amb.kind)
            if (amb.kind is AmbiguityKind.CONJUNCTION_OR_INITIAL
                    and tok.role in (Role.SUFFIX, Role.TITLE)):
                out.append(
                    f"[{label}] {text!r}: {tok.text!r} is roled "
                    f"{tok.role.value} and reports "
                    f"{amb.kind.value}")
    for span, kinds in by_span.items():
        if set(_CONTRADICTORY_KINDS) <= kinds:
            out.append(
                f"[{label}] {text!r}: the token at {span} carries both "
                f"{_CONTRADICTORY_KINDS[0].value} and "
                f"{_CONTRADICTORY_KINDS[1].value}")


@functools.cache
def _connective_findings() -> dict[str, list[str]]:
    """One walk of the connective grid; FIVE invariants' answers.

    Each key below is one test's failure list, built with the parse
    in hand and in grid order, so a test reads exactly what it would
    have found walking the grid itself -- same rows, same order, same
    message. What the walk does NOT do is decide anything: every
    predicate stays where it was, spelled in the terms its own rule
    is stated in, and this function only asks them all at once.
    """
    out: dict[str, list[str]] = {k: [] for k in
                                 ("INV1", "INV2", "INV3/4", "INV5",
                                  "INV10")}
    for text, parser, label in _CONNECTIVE_GRID:
        letters = _class_letters(parser.lexicon)
        name = parser.parse(text)
        _record_contradicting_reports(name, label, text, out["INV10"])
        for role in _NAME_ROLES:
            part = name.tokens_for(role)
            # hoisted out of the INV3/INV4 comprehensions below, where
            # it used to be recomputed once per token of the part
            predicted = _predicted_initials(part, role)
            if len(part) >= 2:
                for i, tok in enumerate(part):
                    if ("conjunction" not in tok.tags
                            or len(tok.text) != 1
                            or tok.text.lower() not in letters):
                        continue
                    left = any("conjunction" not in t.tags
                               for t in part[:i])
                    right = any("conjunction" not in t.tags
                                for t in part[i + 1:])
                    if not (left and right):
                        out["INV1"].append(
                            f"[{label}] {text!r}: {role.value} "
                            f"{tok.text!r}")
            for tok in part:
                if "conjunction" not in tok.tags:
                    continue
                joinable = _has_something_to_join(tok, part)
                if joinable == _readmitted(tok):
                    out["INV2"].append(
                        f"[{label}] {text!r}: {role.value} {tok.text!r} "
                        f"joinable={joinable} "
                        f"marked={_readmitted(tok)}")
            got = name.initials(
                f"{{{role.value}}}").replace(".", "").split()
            if got != predicted:
                out["INV5"].append(
                    f"[{label}] {text!r}: {role.value} {got!r} != "
                    f"predicted {predicted!r}")
            if role is not Role.FAMILY:
                continue
            base = name.family_base.split()
            contributing = [t for t in part
                            if t.text[0] in predicted
                            and (not ("conjunction" in t.tags
                                      or "particle" in t.tags)
                                 or _readmitted(t))]
            for tok in contributing:
                if tok.text not in base:
                    out["INV3/4"].append(
                        f"[{label}] {text!r}: INV3 {tok.text!r} initials "
                        f"but is not in base {base!r}")
            for tok in part:
                if (tok.text in base and tok not in contributing
                        and "conjunction" not in tok.tags):
                    out["INV3/4"].append(
                        f"[{label}] {text!r}: INV4 {tok.text!r} is a base "
                        f"word, contributes no initial, and is no "
                        f"connective")
    return out


@pytest.mark.parametrize("grid_name", ("connective", "off-switch"))
def test_the_reach_trim_drops_only_rows_a_kept_row_repeats(
        grid_name: str) -> None:
    """The TRIM ITSELF, as a mechanism rather than as a measurement.

    `_rows` pairs a text only with the configurations that can read
    it differently, and each variant declares its reach as a set of
    WORDS that `_reaching` folds a text into. Sound for the variants
    that stand here today -- verified row by row when the trim
    landed -- and silently wrong for a variant nobody has written
    yet: `_reaching` splits on whitespace and strips edge periods, so
    a variant declaring a MULTI-WORD entry ("van der") or a
    hyphenated one would be matched by no text at all and would
    contribute ZERO rows, leaving a green suite testing one
    configuration fewer than it names.

    Two checks, and the second is the one that catches that: every
    dropped pairing parses identically to the pairing it collapses
    onto, and every declared variant earns at least one row. A
    variant that reaches nothing passes the first vacuously.

    Sampled by stride (`_TRIM_STRIDE`), which keeps this at about a
    second while covering every shape class: the generators emit
    shapes in a fixed order, so a stride walks all of them.
    """
    grid, lexicons = ((_CONNECTIVE_GRID, _CONNECTIVE_LEXICONS)
                      if grid_name == "connective"
                      else (_OFF_SWITCH_GRID, _OFF_SWITCH_LEXICONS))
    texts: list[str] = []
    seen: set[str] = set()
    for text, _parser, _label in grid:
        if text not in seen:
            seen.add(text)
            texts.append(text)
    cache: dict[tuple[str, str, str], tuple[object, ...]] = {}

    def sig(text: str, lex: tuple[str, Lexicon],
            pol: tuple[str, Policy]) -> tuple[object, ...]:
        key = (text, lex[0], pol[0])
        if key not in cache:
            cache[key] = _signature(
                Parser(lexicon=lex[1], policy=pol[1]), text)
        return cache[key]

    dropped = _dropped_rows(texts, lexicons)
    assert dropped, "the trim dropped nothing; it has stopped trimming"
    problems = [
        f"{text!r} [{lex[0]}/{pol[0]}] differs from its kept twin "
        f"[{twin_lex[0]}/{twin_pol[0]}]"
        for text, lex, pol, twin_lex, twin_pol in dropped
        if sig(text, lex, pol) != sig(text, twin_lex, twin_pol)]
    assert not problems, (
        f"{len(problems)} of {len(dropped)} dropped row(s) are not "
        f"repeats:\n" + "\n".join(problems[:10]))


def test_every_declared_variant_earns_a_row_somewhere() -> None:
    """The other half of the trim's guard: a variant whose declared
    reach no text can satisfy contributes ZERO rows and the suite
    goes on testing one configuration fewer than it names, in
    silence. `_reaching` splits a text on whitespace and strips edge
    periods, so a multi-word or hyphenated entry is the shape that
    would do it.

    Asked of the two grids TOGETHER, because a variant earning rows
    in one of them alone is the state today and is recorded rather
    than a defect: no text of the connective grid holds a standalone
    'v', so `conj+v` earns its rows in the off-switch grid, whose
    suffixes include 'V'. `_rows` says so and calls it
    self-maintaining -- give a connective generator a 'v' word and
    the rows come back. What no generator can repair is a reach
    nothing folds to, and that is what this refuses.
    """
    labels = ({label for _t, _p, label in _CONNECTIVE_GRID}
              | {label for _t, _p, label in _OFF_SWITCH_GRID}
              | {label for _t, _p, label in _MAIDEN_LINK_GRID})
    declared = {f"{ln}/{pn}"
                for lexicons in (_CONNECTIVE_LEXICONS,
                                 _OFF_SWITCH_LEXICONS)
                for ln, _lex, _ln_need in lexicons
                for pn, _pol, _pn_need in _GRID_POLICIES}
    missing = sorted(declared - labels)
    assert not missing, (
        f"declared variant(s) earning no row in any grid: {missing}")


def test_the_connective_grid_can_fail() -> None:
    """The reachability probe every grid in this file carries.

    A grid that reaches none of the shapes it is about passes
    vacuously, and a comparison over a population of zero is the same
    silence as a clean run. These three counts are a dated recorded
    control, measured 2026-09-20 on the shipped tree.

    The row count fell from 170,100 to 55,800 when `_rows` stopped
    pairing a text with configurations that cannot read it; the TEXT
    count did not move, and that is the number to watch here, because
    it is the one that says a shape was dropped. 1,580 of the first
    2,000 rows join, against 1,280 of the old grid's first 2,000 --
    the same texts, reached sooner, the old slice having held twelve
    rows per text where this one holds three or four.
    """
    assert len(_CONNECTIVE_GRID) == 55800, len(_CONNECTIVE_GRID)
    assert len({t for t, _, _ in _CONNECTIVE_GRID}) == 14175
    joined = sum(1 for text, parser, _ in _CONNECTIVE_GRID[:2000]
                 if any("conjunction" in tok.tags
                        for tok in parser.parse(text).tokens))
    assert joined > 1000, joined


def test_a_generational_connective_joins_only_with_both_sides() -> None:
    """INV1 (#397). For a single-letter connective that is ALSO
    generational vocabulary: if it shares its role part with any other
    word, a non-connective word stands before it AND after it.

    Mutation-checked, 2026-09-20, re-measured on the trimmed grid:
    dropping the whole both-sides condition fails this on 162 parses,
    where the full cross product gave 504. The gate's other two
    failure modes stay invisible here and are INV6's and INV1-
    strengthened's to catch -- testing POSITION instead of class, and
    dropping the count's frozen exclusion, each leave this invariant
    green on every row, which is why those two exist. The CLASS test
    is NOT covered here and has its own rows -- see
    tests/v2/pipeline/test_group.py.
    """
    failures = _connective_findings()["INV1"]
    assert not failures, (
        f"{len(failures)} parse(s) joined a generational connective "
        f"without a name word on each side:\n" + "\n".join(failures[:10]))


def test_the_mark_is_exactly_the_parts_with_nothing_to_join() -> None:
    """INV2 (#461). A connective carries a readmitting mark IFF its
    part holds no other word that is neither a connective nor a
    working particle.

    Stated over the PAIR of marks deliberately: keyed on the new mark
    alone it fails 272 times, every one of them under
    `add(particles={"y"})`, where the part is all-particle and R2's
    OLD mark does the readmitting. Mutation-checked, re-measured
    2026-09-20 on the trimmed grid: neutering the walk's
    lone-connective arm, so the new mark is never written, fails this
    on 4,639 rows -- 14,078 of the full cross product, which is what
    the trim costs a count and not what it costs detection.
    """
    failures = _connective_findings()["INV2"]
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

    Mutation-checked, re-measured 2026-09-20 on the trimmed grid:
    swapping the two branches of the mark walk fails this on 94
    parses (188 over the full cross product) -- `Carod y` under
    `add(particles={"y"})`, whose base is empty while its `y`
    initials.
    """
    failures = _connective_findings()["INV3/4"]
    assert not failures, (
        f"{len(failures)} disagreement(s) between initials() and "
        f"family_base:\n" + "\n".join(failures[:10]))


def test_initials_emit_exactly_the_predicted_contributors() -> None:
    """INV5. Per group, `initials("{role}")` emits exactly the words
    the criterion predicts, in field order.

    The output-level statement of the same rule, and the one that
    catches a view reading the marks correctly and then rendering
    something else. Mutation-checked, re-measured 2026-09-20 on the
    trimmed grid: restoring the given group's old blanket exemption
    (`_SKIP_TAGS_GIVEN` back to the empty set) fails this on 9,308
    parses, and dropping the new mark from the readmitting set on
    4,639 -- 27,103 and 14,078 over the full cross product.
    """
    failures = _connective_findings()["INV5"]
    assert not failures, (
        f"{len(failures)} group(s) emitted something other than the "
        f"criterion's contributors:\n" + "\n".join(failures[:10]))


def test_no_report_contradicts_the_reading_beside_it() -> None:
    """INV10 (#397 second review). Two forms of one rule, both over
    the connective grid's 55,800 rows: no token carries
    connective-or-initial while the parse roles it SUFFIX or TITLE,
    and no token is named by two reports whose details assert
    different readings of it.

    The fork classify takes offers a connective and an initial. A
    generation is neither, so where the parse reads one the report
    describes a branch nobody took -- which is the narrow half. The
    wide half needs no role at all: two reports on one token, one
    saying it reads as an initial and the other that it reads as a
    generational suffix, cannot both be true whatever the roles say.

    Mutation-checked, 2026-09-20: it fails on 8,204 rows at
    dc3bdf9c -- 5,078 the narrow half and 3,126 the wide one -- and
    on the same 8,204 at e540d4c5 and c8550b64, the report having
    been wrong since the letter joined the marked subset. 0 here,
    and deleting the withdrawal in `_pipeline/_assemble.py` restores
    all 8,204.
    """
    failures = _connective_findings()["INV10"]
    assert not failures, (
        f"{len(failures)} report(s) contradict the reading beside "
        f"them:\n" + "\n".join(failures[:10]))


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
#
# The same ONE PARSE, MANY CHECKS rule as the grid above, and here it
# buys twice as much: the three invariants share BOTH parses of every
# row -- six parses became two -- in `_off_switch_findings`.


def _off_switch_grid() -> list[tuple[str, Parser, str]]:
    heads: tuple[list[str], ...] = (
        [], ["Josep"], ["Josep", "Lluis"], ["Dr."], ["J."], ["van"],
        ["Josep", "Lluis", "Marti"])
    mids: tuple[list[str], ...] = ([], ["Carod"], ["de", "Carod"])
    conns = ("i", "y", "e", "and")
    tails: tuple[list[str], ...] = ([], ["Rovira"], ["de", "Rovira"])
    # The last two are the #397 SECOND review's addition: a trailing
    # TITLE, alone and standing behind a credential. Where the peel
    # is read over the pieces as WRITTEN a following title hides the
    # suffix run from it, so the bound the join checks its right
    # neighbour against said "name word" of a credential and the join
    # swallowed it -- 'John Quincy Adams i MA Prof.' read family
    # 'Adams i MA' where 'John Quincy Adams i MA' reads family
    # 'Adams'. The lower-case spelling of the title comes free with
    # the casing loop below, and the leading-title-only head is
    # `["Dr."]` above.
    suffixes: tuple[list[str], ...] = (
        [], ["III"], ["Jr."], ["I"], ["V"], ["MA"], ["i"], ["nee", "Puig"],
        ["MA", "Prof."], ["Prof."])
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
    return _rows(texts, _OFF_SWITCH_LEXICONS)


_OFF_SWITCH_GRID = _off_switch_grid()
_OFF_PARSERS: dict[tuple[int, frozenset[str]], Parser] = {}


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


def _name_word_on_the_side(toks: list[_Placed], i: int, step: int,
                           off_role: dict[tuple[int, int], Role],
                           original: str) -> bool:
    """Whether a name word stands on the `step` side of toks[i],
    judged by the OFF-SWITCH parse's roles -- which is what makes
    this a PRE-JOIN reading: in that parse the class letter is no
    connective, so no join has moved anything. A comma between ends
    the walk (it is another segment), and connectives are stepped
    over because a run of them joins as one.

    DELIBERATELY A SECOND IMPLEMENTATION, and named so that the
    mirror cannot be mistaken for the glass: it asks ONE side per
    call over spans and off-switch roles, where the parser's
    `_group._between_name_words` asks both at once over pieces and
    tags. The name it used to carry was the implementation's own,
    which read as a call into the thing under test rather than as a
    model of it."""
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


def _without_the_link(text: str, letters: frozenset[str]) -> str:
    """The same name with every class letter deleted -- the LINK-FREE
    CONTROL.

    What it is for: a credential can land inside a name part for a
    reason that has nothing to do with the link, and one such reason
    is older than #397 and untouched by it. The particle chain reads
    where the trailing suffix run begins over the pieces as WRITTEN,
    so a trailing title hides that run from it and the chain runs to
    the end of the segment -- 'Josep de Carod y Rovira MA Prof.'
    reads family 'de Carod y Rovira MA Prof.' at the parent 46651750
    and at 1.4.0, with no link of the generational class in it at
    all. Deleting the link answers whether the link is what put the
    credential there: where the control puts it in a name part too,
    it did not.

    A trailing comma rides back onto the word before, so the comma
    SHAPE survives the deletion ('Josep Carod i, MA' -> 'Josep
    Carod, MA') -- the one structure whose loss would make the
    control a different name rather than the same one shorter.
    """
    out: list[str] = []
    for word in text.split():
        core = word.rstrip(",")
        if core.lower() in letters:
            if word.endswith(",") and out:
                out[-1] += ","
            continue
        out.append(word)
    return " ".join(out)


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
        if (_name_word_on_the_side(toks, i, -1, off_role, on.original)
                and _name_word_on_the_side(toks, i, 1, off_role,
                                           on.original)):
            return True
    return False


@functools.cache
def _off_switch_findings() -> dict[str, list[str]]:
    """One walk of the off-switch grid; FOUR invariants' answers.

    Both parses of a row -- as configured, and with the class letters
    out of the connectives -- are taken once here and handed to all
    four predicates, which is the whole of what this walk does. The
    exemptions stay each test's own: INV6 takes the join and the
    initial reading, INV1-strengthened the initial reading and the
    link-free control, INV7 the join and the initial reading plus
    R4's placed-connective sentence, exactly as their docstrings say.

    INV6b costs NO parse at all, which is why it joins this walk
    rather than opening a grid of its own: the grid already writes
    every text in three casings, so the ALL-CAPS twin of a lower-case
    row is another row of this same walk and the comparison is a
    lookup over what the walk already read. The link-free controls
    INV1-strengthened wants are the only parses added here, and only
    on a row that would otherwise be recorded as a failure.
    """
    out: dict[str, list[str]] = {k: [] for k in
                                 ("INV6", "INV1-strengthened", "INV7",
                                  "INV6b")}
    v1_off: dict[frozenset[str], Constants] = {}
    #: (label, text) -> the roles the configured parse gave, in token
    #: order, for INV6b's casing comparison below.
    roles_by: dict[tuple[str, str],
                   tuple[tuple[str, str, bool], ...]] = {}
    for text, parser, label in _OFF_SWITCH_GRID:
        letters = _present(text, _class_letters(parser.lexicon))
        if not letters:
            continue
        on = parser.parse(text)
        # INV6b's rows, and its scope: the MARKED subset. Its claim
        # is decisions.md#P3's own -- a one-case name reads the
        # marked letter as an initial and so reads as its ALL-CAPS
        # twin already did -- and a class letter the caller's lexicon
        # leaves UNMARKED is the shape P3's Accepted block records
        # instead, where a bare Latin capital and its lowercase
        # spelling genuinely part. The `conj+v` variant is exactly
        # that caller: it adds 'v' to the connectives and not to the
        # marked subset, so 'carod y rovira, v' and its ALL-CAPS twin
        # disagree, identically at the parent 46651750 (20 rows,
        # measured 2026-09-20, every one of them strict-comma).
        if letters <= parser.lexicon.conjunctions_ambiguous:
            roles_by[(label, text)] = tuple(
                (tok.text.lower(), tok.role.value,
                 AMBIGUOUS_ACRONYM_TAG in tok.tags) for tok in on.tokens)
        off_parser = _off_switch(parser, letters)
        off = off_parser.parse(text)
        # the SEVEN FIELDS, and not comparison_key: a parse carries
        # more than its fields, and what the off-switch legitimately
        # moves besides them is the conjunction-or-initial report
        same_fields = on.as_dict() == off.as_dict()
        moved = _initial_reading_moved(on, off, letters)
        if not (same_fields
                or _link_joins_between_name_words(on, off, letters)
                or moved):
            out["INV6"].append(f"[{label}] {text!r}: {on.as_dict()} != "
                               f"off-switch {off.as_dict()}")
        if not moved:
            off_role = _off_roles(off)
            for role in _NAME_ROLES:
                part = on.tokens_for(role)
                if len(part) < 2:
                    continue
                for tok in part:
                    # not the LINK itself: it is generational
                    # vocabulary by definition of the class, so the
                    # off-switch parse reads it as the suffix in every
                    # name it ends. This rule is about the OTHER word
                    # -- the credential a link must not take with it.
                    # `span is None` is a typing guard and nothing
                    # else: every token of a PARSER-produced name
                    # carries one, and this grid holds no spliced
                    # parse.
                    if "conjunction" in tok.tags or tok.span is None:
                        continue
                    if off_role.get(tok.span) is not Role.SUFFIX:
                        continue
                    # THE LINK-FREE CONTROL, and the reason it is
                    # asked here rather than folded into the oracle:
                    # the particle chain puts a credential into the
                    # family on its own where a trailing title hides
                    # the suffix run from it, link or no link, at
                    # this commit and at the parent and at 1.4.0
                    # alike ('Josep de Carod y Rovira MA Prof.').
                    # Turning the class letter off ALSO stops that
                    # chain -- the letter becomes suffix vocabulary
                    # again and the chain halts at it -- so the
                    # off-switch parse reads the credential as a
                    # suffix for a reason this rule is not about.
                    # Deleting the link asks the question directly.
                    # Recorded boundary, not a silence: the shape is
                    # pinned by test_a_trailing_title_still_hides_the
                    # _suffix_run_from_the_particle_chain below and
                    # is the #535 family.
                    #
                    # Taken only on a row already read as a failure,
                    # so the green state pays 15 parses over the
                    # whole grid (measured 2026-09-20).
                    control = parser.parse(
                        _without_the_link(text, letters))
                    if any(c.text == tok.text and c.role is role
                           for c in control.tokens_for(role)):
                        continue
                    out["INV1-strengthened"].append(
                        f"[{label}] {text!r}: {tok.text!r} reads as "
                        f"the suffix and joined into {role.value}")
        if not (same_fields and not moved
                and not _placed_as_a_connective(on, letters)):
            continue
        for force in (False, True):
            here = str(parser.capitalized(on, force=force))
            there = str(off_parser.capitalized(off, force=force))
            if here != there:
                out["INV7"].append(
                    f"[{label}] {text!r} force={force}: {here!r} != "
                    f"off-switch {there!r}")
            if label != "default/default":
                continue
            if letters not in v1_off:
                v1_off[letters] = _v1_off_switch(letters)
            v1_here = _v1_capitalized(text, None, force)
            v1_there = _v1_capitalized(text, v1_off[letters], force)
            if v1_here != v1_there:
                out["INV7"].append(
                    f"[v1] {text!r} force={force}: {v1_here!r} != "
                    f"off-switch {v1_there!r}")
    # INV6b, over what the walk above already read. A text that is
    # its own lower-casing and is not its own upper-casing is the
    # all-lower spelling of a one-case name, and the grid wrote its
    # ALL-CAPS twin too, under the same labels.
    for (label, text), roles in roles_by.items():
        if text != text.lower() or text == text.upper():
            continue
        twin = roles_by.get((label, text.upper()))
        if twin is None or twin == roles:
            continue
        if _a_case_reading_the_docs_already_own(roles, twin):
            continue
        out["INV6b"].append(
            f"[{label}] {text!r}: {list(roles)} != ALL-CAPS twin "
            f"{list(twin)}")
    return out


def _a_case_reading_the_docs_already_own(
        lower: tuple[tuple[str, str, bool], ...],
        upper: tuple[tuple[str, str, bool], ...]) -> bool:
    """INV6b's TWO exemptions, both of them case readings this
    library decided long before #397 and neither of them the marked
    subset's.

    ONE: a single-letter suffix word the lower spelling reads as the
    suffix and the ALL-CAPS spelling does not. That is the
    `suffix_not_acronyms` vs `is_an_initial` tension, Latin-only:
    `_vocab.is_initial` matches an ASCII CAPITAL, so the peel's veto
    fires on 'I' and 'V' and never on 'i' and 'v'. Measured
    2026-09-20 at the parent 46651750 on letters this branch does not
    touch at all -- 'carod y i' reads suffix 'i' where 'CAROD Y I'
    reads family 'I', and 'carod y v' against 'CAROD Y V' and 'carod
    e i' against 'CAROD E I' are the same pair.

    TWO: a member of the AMBIGUOUS credential class reading
    differently in the two spellings. That is decisions.md#S2's own
    lean -- an ALL-CAPS bare member of the class reads as the
    credential and a lower-case one as a name word -- and it decides
    the COMMA STRUCTURE, so its effect reaches every token of the
    name: 'i rovira, ma' reads given 'ma' and 'I ROVIRA, MA' suffix
    'MA', and the rest of the row moves with it. Identical at the
    parent on all 24 rows it exempts, measured 2026-09-20, and 21 of
    those carry no letter of #397's class at all.

    Neither exemption reaches what the branch DID close, which is
    what makes INV6b worth running: 'rovira, i', 'john smith i jr'
    and 'josep de carod i rovira' each disagreed with its ALL-CAPS
    twin at the parent and agrees with it here.

    Compared by token INDEX, the two spellings having the same tokens
    in the same order by construction.
    """
    return any(
        (a[1] == Role.SUFFIX.value and b[1] != Role.SUFFIX.value
         and len(a[0]) == 1)
        or ((a[2] or b[2]) and a[1] != b[1])
        for a, b in zip(lower, upper))


def test_the_off_switch_grid_can_fail() -> None:
    """The reachability probe, the shape every grid in this file
    carries. Dated recorded control, measured 2026-09-20.

    The row count fell from 103,040 to 53,312 with `_rows` (see the
    connective probe above); the TEXT count is unmoved by the trim,
    and 2,011 of the first 4,000 rows carried a class letter against
    1,800 of the pre-trim grid's first 4,000.

    RE-MEASURED 2026-09-20 for the #397 second review, which added
    the two trailing-title suffix runs: 66,752 rows over 16,576
    texts, 2,109 of the first 4,000 rows carrying a class letter and
    28,448 over the whole grid -- those being the rows parsed twice.
    The module's own runtime is the budget these numbers spend, and
    it is stated where the walk is built."""
    assert len(_OFF_SWITCH_GRID) == 66752, len(_OFF_SWITCH_GRID)
    assert len({t for t, _, _ in _OFF_SWITCH_GRID}) == 16576
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

    Mutation-checked, re-measured 2026-09-20 over the grid as it
    now stands (the second review added the two trailing-title
    suffix runs, so every count here moved with it): this fails on
    1,480 parses at c8550b64, the commit the first review was
    written against, on 764 where the both-sides gate tests POSITION
    rather than class -- the c8550b64 defect isolated, which is the
    one INV1 above cannot see -- and on 154 at dc3bdf9c, where the
    join's right-hand bound was read over the pieces as WRITTEN and
    a trailing title hid the suffix run from it. 0 here.
    """
    failures = _off_switch_findings()["INV6"]
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

    THE LINK-FREE CONTROL is its third exemption, added by the
    second review and documented at the walk: a credential can land
    in a name part for a reason older than #397 and untouched by it,
    and deleting the link is how this asks whether the link is what
    put it there.

    Mutation-checked, re-measured 2026-09-20 over the grid as it now
    stands: this fails on 639 parses at c8550b64, where INV1 fails
    on none of them, on the same 639 where the both-sides gate tests
    POSITION rather than class, and on 105 at dc3bdf9c -- the
    trailing-title bound, the defect the two new suffix runs were
    added to see. 0 here.
    """
    failures = _off_switch_findings()["INV1-strengthened"]
    assert not failures, (
        f"{len(failures)} credential(s) joined into a name part:\n"
        + "\n".join(failures[:10]))


def _placed_as_a_connective(on: ParsedName,
                            letters: frozenset[str]) -> bool:
    """Whether the parse put a class letter among the NAME words as a
    connective -- rules.md#R4's own reading, and the one thing an
    off-switch comparison of case repair cannot hold fixed: a
    connective keeps its lowercase there and the off-switch parse,
    where the letter is no connective at all, capitalizes it. Asked
    of the token's WORDS rather than of its whole text, because a
    merged piece renders word by word and repair asks per word."""
    for tok in on.tokens:
        if tok.role is Role.SUFFIX or "conjunction" not in tok.tags:
            continue
        if letters & {w.strip(".,").lower() for w in tok.text.split()}:
            return True
    return False


def _v1_off_switch(letters: frozenset[str]) -> Constants:
    constants = Constants()
    for letter in letters:
        constants.conjunctions.remove(letter)
    return constants


def _v1_capitalized(text: str, constants: Constants | None,
                    force: bool) -> str:
    name = HumanName(text) if constants is None else HumanName(text,
                                                               constants)
    name.capitalize(force=force)
    return str(name)


def test_a_letter_that_did_not_join_repairs_as_the_off_switch_does() -> None:
    """INV7 (#397 review). Case repair is the third view, and the one
    the differential cannot see at all, so it gets the same treatment
    INV6 gives the fields: turning the class letter OFF is the
    parent's reading, so a letter that became no connective of this
    name must leave every repair where the parent left it, plain and
    forced, on both surfaces.

    Three exemptions. The first two are INV6's -- a name whose FIELDS
    moved is a name the join changed, and a letter the two parses
    disagree about being an INITIAL is the marked-subset clause. The
    third is rules.md#R4's own sentence: a connective the parse
    placed among the name words keeps its lowercase there, which the
    off-switch parse cannot agree with, since for it the letter is
    not a connective at all. What is left is the generation, and the
    rule for it is that it repairs as the generation it was read as.

    Mutation-checked, re-measured 2026-09-20 over the grid as it
    now stands: this fails on 7,860 repairs at e540d4c5, where the
    suffix-roled letter still took the connective conjunct, on 8,054
    with the generation conjunct removed outright, and on 0 here and
    at dc3bdf9c -- dc3bdf9c PASSES it, which is the point of INV7b
    below: the guard there was the suffix ROLE alone, which is too
    wide, and too wide in a direction this invariant's subject
    cannot reach. The v1 arm runs on the default-lexicon,
    default-policy rows, the only ones a `Constants` can express,
    and 1,017 of the e540d4c5 failures are its.
    """
    failures = _off_switch_findings()["INV7"]
    assert not failures, (
        f"{len(failures)} repair(s) moved for a letter that joined "
        f"nothing:\n" + "\n".join(failures[:10]))


def test_a_one_case_name_reads_the_same_in_either_case() -> None:
    """INV6b (#397 second review). decisions.md#P3 states in prose
    that a name written wholly in lower case now reads as its
    ALL-CAPS twin already did, and INV6 cannot hold it: the
    `_initial_reading_moved` exemption there swallows the one-case
    population, 9,296 of the 28,448 rows that carry a class letter,
    which is exactly where the marked subset's riskiest movement
    lives.

    Every all-lower row's roles, token for token, against the roles
    of the same text ALL-CAPS under the same parser. Costs no parse:
    the grid writes both spellings, so the twin is another row of the
    walk that just ran.

    Scope and exemptions in `_a_case_reading_the_docs_already_own`
    and at the `roles_by` write -- the marked subset, less two case
    readings the library decided long before this rule.

    Mutation-checked, 2026-09-20: marking the letter for ALL-CAPS
    names only -- `and token.text.isupper()` on classify's fork --
    fails this on 944 rows. Five unit tests in
    tests/v2/pipeline/test_classify.py fall with it, so this is not
    the only guard on that line and is not claimed to be; what it
    adds is the SHAPE of the claim. Those five each assert one
    spelling's reading against a stored expectation; this asserts
    that the two spellings AGREE, over the 6,496 all-lower rows this
    invariant's scope keeps -- where INV6 is exempt and where, until
    the four rows this round added, no row of tests/v2/cases.py
    stood. What it holds is
    real: 'rovira, i', 'john smith i jr' and 'josep de carod i
    rovira' each disagreed with its ALL-CAPS twin at the parent
    46651750 and agrees with it here.
    """
    failures = _off_switch_findings()["INV6b"]
    assert not failures, (
        f"{len(failures)} one-case name(s) read differently from "
        f"their ALL-CAPS twin:\n" + "\n".join(failures[:10]))


# --- #397 second review: the SUFFIX-FIELD CONNECTIVE grid -----------
# A fourth grid, and a tiny one -- 60 rows against the three above in
# the tens of thousands -- because the shape it is about is one none
# of them can generate. Every grid above puts its connective among
# the name's own words or inside a clause; this one puts a connective
# in the SUFFIX FIELD without its being generational vocabulary, and
# there are exactly two ways to do that: a third comma part, whose
# words assign reads as the suffix run whatever they are, and a field
# spliced in after the parse.
#
# The oracle cannot be the off switch, and that is the reason for the
# separate grid rather than a second reason for it: no `i` stands in
# any of these names, so removing `i` from the connectives changes
# nothing and the comparison would be vacuous -- the silence a
# reachability probe exists to catch. The oracle is the RULE instead,
# the RULE instead, rules.md#R4 read in its own words: a suffix-roled
# connective that the suffix vocabulary does NOT hold was read as no
# generation and keeps its lowercase.
# The literal strings the released wheels give are pinned separately,
# as unit tests in tests/v2/test_render.py.

_SUFFIX_FIELD_CONNECTIVES = ("and", "y", "e", "und", "of", "&", "и")


def _suffix_field_rows() -> list[tuple[str, str]]:
    """(description, the connective word) for every way this grid
    puts a connective into the suffix field."""
    rows: list[tuple[str, str]] = []
    for word in _SUFFIX_FIELD_CONNECTIVES:
        rows += [(f"Smith, John, {word}", word),
                 (f"Doe, Jane, {word} Jr.", word),
                 (f"Smith, John, {word} III", word)]
    return rows


def test_a_connective_the_suffix_field_holds_keeps_its_lowercase() -> None:
    """INV7b (#397 second review). R4's clause turns on the
    GENERATION and not on the field: a connective the suffix field
    merely holds, which the suffix vocabulary does not know, was read
    as no generation, so case repair leaves it lowercase -- plain and
    forced, on both surfaces.

    INV7 cannot see this. Its oracle is the off switch and its
    subject is the class letter, and no name here carries one: `and`,
    `y`, `e`, `und`, `of`, `&` and `и` are connectives and nothing
    else, which is the whole point -- they are what a role test alone
    could not tell apart from the generation.

    Mutation-checked, 2026-09-20: this fails on 36 of its 42 rows
    at dc3bdf9c, where `role is not Role.SUFFIX` gated both
    conjunction arms, and on 0 here; the six that pass there are the
    Cyrillic 'и', which repairs to itself either way. 'Smith, John,
    and' repaired forced to 'John Smith And' there, against 'John
    Smith and' at 1.4.0, at 2.0.0 through 2.3.0 and at the parent
    46651750. INV7 above cannot see any of this -- it passes at
    dc3bdf9c.
    """
    parser = Parser()
    failures = []
    for text, word in _suffix_field_rows():
        name = parser.parse(text)
        if word not in {t.text for t in name.tokens_for(Role.SUFFIX)}:
            failures.append(f"{text!r}: {word!r} is not in the suffix")
            continue
        for force in (False, True):
            repaired = str(parser.capitalized(name, force=force))
            v1 = _v1_capitalized(text, None, force)
            for label, got in (("core", repaired), ("v1", v1)):
                if word not in got.split():
                    failures.append(
                        f"[{label}] {text!r} force={force}: {got!r} does "
                        f"not keep {word!r} lowercase")
    assert not failures, (
        f"{len(failures)} repair(s) capitalized a connective the "
        f"suffix field merely holds:\n" + "\n".join(failures[:10]))


def test_the_suffix_field_connective_grid_can_fail() -> None:
    """The reachability probe, the shape every grid in this file
    carries. Dated recorded control, measured 2026-09-20.

    The one that matters here is the SECOND: a row whose connective
    the parse did not actually put in the suffix field would pass
    INV7b for the wrong reason, and the invariant records that as a
    failure rather than skipping it, so this counts the rows that
    reach the repair at all.
    """
    rows = _suffix_field_rows()
    assert len(rows) == 21, len(rows)
    parser = Parser()
    reached = sum(
        1 for text, word in rows
        if word in {t.text for t in parser.parse(text).tokens_for(
            Role.SUFFIX)})
    assert reached == 21, reached
    assert not _class_letters(Lexicon.default()) & {
        w for _t, w in rows}, "a class letter would make INV7 the oracle"


# --- #397 review: the MAIDEN-CLAUSE LINK grid, and its two ----------
# invariants
# A third grid, kept apart from the two above for the reason the
# off-switch one is: every row here is parsed TWICE, once as written
# and once with the link spelled `y`, and the texts that earn the
# second parse are the clause shapes -- which neither grid above
# generates, both putting their connective among the name's own
# words. What this one adds: a link INSIDE a maiden clause, in every
# position a clause can hold one, under every marker the library
# ships and behind every trailing run the walk stops at.
#
# The `y` spelling is the ORACLE and not a second subject. It is the
# same sentence with the ambiguity removed: `y` is connective
# vocabulary and no generation, so nothing in the walk can read it as
# the end of the clause, and whatever it does is what the `i`
# spelling has to do wherever P3 says the letter is joining.

#: The clause bodies, `@` standing where the link goes: a link
#: between two words, with a word run on either side of it, doubled,
#: and the two shapes where it joins NOTHING -- nothing on its right,
#: nothing on its left but the marker. The last two are the
#: controls the guard below must refuse, and
#: `test_the_maiden_link_grid_can_fail` counts them out.
_LINK_BODIES: tuple[tuple[str, ...], ...] = (
    ("Puig", "@", "Soler"),
    ("Puig", "@", "Soler", "Roig"),
    ("Puig", "Soler", "@", "Roig"),
    ("Puig", "@", "Soler", "@", "Roig"),
    ("Puig", "@"),
    ("@", "Soler"),
)
#: Nothing, the two generations and the two credential classes -- the
#: four trailing runs M2's walk stops at, plus the empty one.
_LINK_TAILS: tuple[tuple[str, ...], ...] = (
    (), ("III",), ("Jr.",), ("MA",), ("PhD",))
#: One to three words, and the last carries a link of its OWN, which
#: stays spelled `i` in both parses: the head's reading is not what
#: this grid is about, and holding it fixed is what makes a moved
#: field the clause's doing.
_LINK_HEADS: tuple[tuple[str, ...], ...] = (
    ("Jane",), ("Doe", "Jane"), ("Jane", "Doe"),
    ("Jane", "M.", "Doe"), ("Carod", "i", "Rovira"))

_LINK_RE = re.compile(r"(?<!\S)y(?!\S)")


def _link_texts() -> dict[str, str]:
    """Every clause shape, mapped to its `y`-spelled twin.

    The two spellings differ in one CHARACTER per link, so their
    token spans line up exactly -- which is what lets the second
    invariant below delimit the clause with the twin's own maiden
    tokens and then read the first parse at those offsets.
    """
    out: dict[str, str] = {}
    markers = sorted(Lexicon.default().maiden_markers)
    for head, marker, body, tail, comma in itertools.product(
            _LINK_HEADS, markers, _LINK_BODIES, _LINK_TAILS,
            (False, True)):
        if comma and len(head) < 2:
            continue
        pair = []
        for link in ("i", "y"):
            words = [link if w == "@" else w for w in body]
            rest = list(head[1:] if comma else head) + [marker] \
                + words + list(tail)
            pair.append(f"{head[0]}, " + " ".join(rest) if comma
                        else " ".join(rest))
        out.setdefault(pair[0], pair[1])
    return out


_LINK_TWIN = _link_texts()
_MAIDEN_LINK_GRID = _rows(
    list(_LINK_TWIN),
    (("default", Lexicon.default(), frozenset()),))


def _link_joins_inside_the_clause(maiden: str) -> bool:
    """Whether the ORACLE parse put a link inside the birth name with
    a birth-name word on each side of it -- rules.md#P3's both-sides
    condition, read off the `y` spelling's own maiden field.

    The guard, and it is narrower than "the twin keeps the link" for
    a measured reason: 'Jane Doe nee Puig y' keeps its `y` in maiden
    'Puig y', and 'Jane Doe nee Puig i' reads maiden 'Puig' with
    suffix 'i' -- deliberately, the link there joining nothing and
    being the generation it also spells (rules.md#M2). So a guard
    asking only whether the twin kept the letter would demand the two
    agree where the rules say they must not. `Puig y III` and `y
    Soler` are the same shape from the other two sides.
    """
    words = maiden.split()
    at = [k for k, w in enumerate(words) if w == "y"]
    return bool(at) and all(
        any(w != "y" for w in words[:k])
        and any(w != "y" for w in words[k + 1:]) for k in at)


@functools.cache
def _maiden_link_findings() -> dict[str, list[str]]:
    """One walk of the maiden-link grid; two invariants' answers.

    Both parses of a row are taken once here and handed to both
    predicates, which is all this walk does -- the ONE PARSE, MANY
    CHECKS rule the two grids above follow.
    """
    out: dict[str, list[str]] = {k: [] for k in ("INV8", "INV9")}
    for text, parser, label in _MAIDEN_LINK_GRID:
        twin = parser.parse(_LINK_TWIN[text])
        if not _link_joins_inside_the_clause(twin.maiden):
            continue
        on = parser.parse(text)
        want = {k: _LINK_RE.sub("i", v) for k, v in twin.as_dict().items()}
        if on.as_dict() != want:
            out["INV8"].append(f"[{label}] {text!r}: {on.as_dict()} != "
                               f"y-twin {want}")
        spans = [tok.span for tok in twin.tokens
                 if tok.role is Role.MAIDEN and tok.span is not None]
        lo = min(s.start for s in spans)
        hi = max(s.end for s in spans)
        for tok in on.tokens:
            if (tok.span is not None and lo <= tok.span.start
                    and tok.span.end <= hi and tok.role in _NAME_ROLES):
                out["INV9"].append(
                    f"[{label}] {text!r}: {tok.text!r} of the birth "
                    f"name reads as {tok.role.value}")
    return out


def test_the_maiden_link_grid_can_fail() -> None:
    """The reachability probe, the shape every grid in this file
    carries. Dated recorded control, measured 2026-09-20.

    The third count is the one to watch: the guard above refuses the
    two joining-nothing bodies outright, so a grid whose every row
    were one of those would pass both invariants in silence. 1,350 of
    the first 2,000 rows are guarded in, and 10,540 of all 15,810 --
    two thirds, which is the four admitted bodies of six.
    """
    assert len(_MAIDEN_LINK_GRID) == 15810, len(_MAIDEN_LINK_GRID)
    assert len(_LINK_TWIN) == 4590, len(_LINK_TWIN)
    guarded = sum(
        1 for text, parser, _ in _MAIDEN_LINK_GRID[:2000]
        if _link_joins_inside_the_clause(parser.parse(_LINK_TWIN[text]).maiden))
    assert guarded > 800, guarded


def test_a_clause_link_reads_as_its_y_twin_does() -> None:
    """INV8 (#397 review). THE y TWIN. Where the `y` spelling puts a
    link inside the birth name with a birth-name word on each side,
    the `i` spelling gives the same seven fields, letter for letter
    apart from the link itself.

    `y` is connective vocabulary and nothing else, so its reading is
    the one the maiden walk was never able to get wrong; `i` is that
    same connective AND the roman numeral, and the walk used to end
    the birth name at it. The pair is the whole statement of
    rules.md#M2's link clause, and it needs no expected values of its
    own.

    Mutation-checked, 2026-09-20: it fails on all 10,540 guarded rows
    at 0fbcaa0b -- this branch's tip before the fix -- and on the same
    10,540 at the parent 46651750, the walk having truncated the
    birth name at the link since long before #397 reached it. That it
    is EVERY guarded row and not a subset is the finding: no clause
    shape holding a joining link read as its twin did.
    """
    failures = _maiden_link_findings()["INV8"]
    assert not failures, (
        f"{len(failures)} parse(s) read a clause link differently "
        f"from its y twin:\n" + "\n".join(failures[:10]))


def test_no_birth_name_word_reads_as_a_word_of_the_current_name() -> None:
    """INV9 (#397 review). The failure class #424 and #533 exist to
    prevent, stated for the link: no token standing inside the birth
    name -- as the `y` twin's own maiden tokens delimit it -- is
    roled GIVEN, MIDDLE or FAMILY.

    Weaker than INV8 and kept beside it because it is the one that
    names the HARM. A truncation moves fields too, and this stays
    green for it; what it refuses is a word of one person's birth
    name being handed to the surname they carry now.

    Mutation-checked, 2026-09-20: it fails on 28,985 tokens at
    0fbcaa0b and on 22,185 at the parent 46651750, over the same
    10,540 guarded rows. The GAP between those two is what this
    branch added: at the parent the released words are a truncation
    that left them in `middle` and `family`, and with the link
    joining they became words of the current surname itself.
    """
    failures = _maiden_link_findings()["INV9"]
    assert not failures, (
        f"{len(failures)} birth-name word(s) read as a word of the "
        f"current name:\n" + "\n".join(failures[:10]))

"""Not a stage: converts the final ParseState into a public ParsedName.

Consumes: tokens (all roles set, and their tags, which name each
token's reading), dropped, order (for ParsedName.order, and for the
field a report's alternative names under rules/P1's family-first fold)
and structure (for ParsedName.order, and for rules/T7's family comma,
which names a family where C15 reads none),
ambiguities (by index;
one carrying ``field_tail`` is worded from its word's final role,
#626), segments, for the part a withdrawn connective report's
letter ends (rules/P8, #721), and comma_offsets, for the comma part
rules/R9's Turkic arm keeps a marker and its father's name in.
Produces: a validated ParsedName, a given name written as a run of
initials parted into them (rules/T7), each token carrying the reading the
parse took (`Token.reading`), a word of the family's second unit
marked `Reading.second_surname` where O6's or W5's tag says so
(rules/R10) and `Reading.first_surname` where a first-surname tag
does (rules/R11) --
the constructor re-checks every
invariant (span order/bounds, ambiguity subset), so a pipeline bug
that would produce an invalid result dies HERE, not in a renderer
three layers away.
Reads: Policy.middle_as_family, folding a report's other field as the
policy folds a middle, and with Policy.two_given_names keeping a given
name written as a run of initials whole (rules/T7); Policy.name_order, for ParsedName.order where
no positional read happened; Policy.patronymic_rules, for the words
an ending rule reads as a patronymic (rules/R9); and Lexicon.surnames, suffix_acronyms,
suffix_acronyms_ambiguous and given_name_abbreviations (the last
through _vocab.is_title_shaped), for the source of a token's reading
where no tag gives it; and the Lexicon's readings by word (Lexicon._files),
for Reading.languages, the files whose reading is on in it, with
every vocabulary field (`_lexicon._VOCAB_FIELDS`, `_listed_whole`)
for whether the lexicon lists a word whole rather than by its parts;
and every vocabulary field and Lexicon.capitalization_exceptions
(`_listed_run`) for a run of initials listed whole (rules/T7).

Structural tokens (dropped maiden markers) are omitted, like delimiter
characters. A main-stream token that somehow reaches here with no role
takes Role.GIVEN -- parse must never raise on the *content* of a name,
so the fallback is deliberately boring rather than an exception. This
should never fire in practice (assign/group must set a role on every
main-stream token); it exists as a last-resort safety net against a
pipeline bug, not as sanctioned behavior for real input -- see
test_assemble_falls_back_to_given_for_unassigned_role in
tests/v2/pipeline/test_assemble.py.
"""
from __future__ import annotations

import functools
import unicodedata
from collections.abc import Sequence
from types import MappingProxyType

from nameparser._lexicon import (
    _VOCAB_FIELDS, Lexicon, _normalize, _ReadingFiles,
)
from nameparser._pipeline._state import (
    AGNOMEN_TAG, AMBIGUOUS_ACRONYM_TAG, AMBIGUOUS_WORD_TAG, ATTACHED_TAG,
    CREDENTIAL_WORD_TAG, FIELD_READING, GENERATION_WORD_TAG, HONORIFIC_WORD_TAG,
    NAME_ROLES, PATRONYMIC_TAG, SECOND_SURNAME_TAG, SHAPE_ACRONYM_TAG,
    SHARED_NAME_TAG, PARTICLE_GIVEN_TAG, BOUND_PHRASE_TAG,
    FIRST_SURNAME_TAG, SURNAME_PAIR_TAG,
    SPLIT_CREDENTIAL_TAG, SPLIT_MEMBER_TAG, PAST_REACH_TAG,
    DOTTED_TITLE_TAG, JOINED_TITLE_TAG, TITLE_AMBIGUOUS_TAG, TRAILING_TITLE_TAG, Beside, Deferred, ParseState, PendingAmbiguity,
    Structure, WorkToken, comma_bucket, reported_suffix_fork,
)
from nameparser._pipeline._vocab import (
    _LETTER_RUN, _RUN_LETTER,
    has_patronymic_ending, is_patronymic_marker, is_title_shaped,
    name_source, suffix_kind,
)
from nameparser._policy import PatronymicRule
from nameparser._reading_index import CATEGORY
from nameparser._types import (
    FOLDED_TAG, GIVEN_FIRST, UNJOINED_CONJUNCTION_TAG, UNJOINED_TAG,
    Ambiguity, AmbiguityKind, ParsedName, Reading, ReadingKind,
    ReadingSource, Role, Span, Token,
)

#: Every Reading a token can take, built once: a `Reading` is three
#: enum members, so the parse hands out shared instances rather than
#: constructing one per token, which would cost two frames a word
#: (decisions/parse-cost).
_READINGS = MappingProxyType({
    (kind, role, source): Reading(kind, role, source)
    for kind in ReadingKind for role in Role for source in ReadingSource})

def _kinds_of(*categories: str) -> frozenset[str]:
    return frozenset(k for k, c in CATEGORY.items() if c in categories)


#: The vocabulary kinds (_reading_index.CATEGORY's keys) whose rows
#: hold a reading of each kind. A suffix reading takes the word's
#: suffix rows whatever their finer kind, since a word has one suffix
#: kind (the build's check 4), which `_vocab.suffix_kind` has already
#: read the reading's kind by (4b).
#: A name reading's rows depend on its field (`_NAME_KINDS`). A
#: patronymic's are the patronymic particle's (rules/R9); the words its
#: run takes, and a patronymic an ending rule reads, are read by
#: position or shape, as an initial is, never from a file.
_SUFFIX_KINDS = _kinds_of("suffix")
_KINDS: MappingProxyType[ReadingKind, frozenset[str]] = MappingProxyType({
    ReadingKind.TITLE: _kinds_of("title"),
    ReadingKind.PARTICLE: _kinds_of("particle"),
    ReadingKind.CONJUNCTION: _kinds_of("conjunction"),
    ReadingKind.PATRONYMIC: frozenset({"patronymic"}),
    ReadingKind.CREDENTIAL: _SUFFIX_KINDS,
    ReadingKind.GENERATION: _SUFFIX_KINDS,
    ReadingKind.AGNOMEN: _SUFFIX_KINDS,
    ReadingKind.POST_NOMINAL: _SUFFIX_KINDS,
    ReadingKind.HONORIFIC: _SUFFIX_KINDS,
})

#: A name reading's rows by the field it lands in: a family word the
#: files listing it as a family name, a given or middle word those
#: listing it as a given name ('Ma' as a family name names `en`, not
#: `fil`, which lists it only as given), and a bound given name
#: (rules/P5) in any field, its rows being the reason it was read so;
#: a name in another field (a nickname) any name rows.
_GIVEN_KINDS = frozenset({"given", "bound_given"})
_FAMILY_KINDS = frozenset({"family", "bound_given"})
_NAME_KINDS: MappingProxyType[Role, frozenset[str]] = MappingProxyType({
    Role.GIVEN: _GIVEN_KINDS, Role.MIDDLE: _GIVEN_KINDS,
    Role.FAMILY: _FAMILY_KINDS, Role.MAIDEN: _FAMILY_KINDS,
})
_ANY_NAME_KINDS = _kinds_of("name", "bound_given")

#: The sources a file can hold: a listed word, and a name the
#: vocabulary declares beside another reading.
_LISTED = frozenset({ReadingSource.VOCABULARY, ReadingSource.DECLARED})


def _kinds(kind: ReadingKind, role: Role) -> frozenset[str]:
    # an initial or a patronymic matches no row
    return (_NAME_KINDS.get(role, _ANY_NAME_KINDS)
            if kind is ReadingKind.NAME else _KINDS.get(kind, frozenset()))


# The lookup is a memo, C-level on a hit, so a word read before costs
# no frame (decisions/vocabulary-model, 2026-10-29; 2026-11-05 #1085,
# which made the lookup one memo): a pure function of
# the word and the lexicon's readings, which `files` stands for, one
# object per base, log and choice hashed by identity
# (decisions/vocabulary-model, 2026-11-02 #754, sub-phase 4i-d), and
# bounded (maxsize) because the caller's text keys it; so is `_reading`,
# of the readings that name files.
@functools.lru_cache(maxsize=4096)
def _languages_of(text: str, kind: ReadingKind, role: Role,
                  files: _ReadingFiles) -> tuple[tuple[str, ...], bool]:
    """Reading.languages for the `kind` reading of `text` in `role`:
    the files holding the word whole (`_languages`), else those holding
    its parts (`_part_languages`); and whether they are its parts',
    which the caller drops where the parse's own lexicon lists the word
    whole (`_listed_whole`): that reads the lexicon's `surnames` and
    `given_names` lists too, which `files` does not stand for, so the
    memo cannot answer it."""
    found = _languages(text, kind, role, files)
    if found:
        return found, False
    found = _part_languages(text, kind, role, files)
    return found, bool(found)


#: `_languages_of`'s answer for a reading by position or shape
#: (`source not in _LISTED`), which names no file.
_UNLISTED: tuple[tuple[str, ...], bool] = ((), False)


def _languages(text: str, kind: ReadingKind, role: Role,
               files: _ReadingFiles) -> tuple[str, ...]:
    """The files holding the `kind` reading of `text` as written, in
    `role`, on in the parse's lexicon (`files`, its `_files`),
    Reading.languages: by the vocabulary's own form of the
    word, and then with every period removed, the form a credential is
    matched by ('M.A' in 'John Smith (M.A)') and a word listed whole
    without them ('Lt.Gen.' as 'ltgen')."""
    kinds = _kinds(kind, role)
    n = _normalize(text)
    found = files.languages(n, kinds)
    if not found and "." in n:
        found = files.languages(n.replace(".", ""), kinds)
    return found


def _part_languages(text: str, kind: ReadingKind, role: Role,
                    files: _ReadingFiles) -> tuple[str, ...]:
    """The files of the listed words `text` joins with punctuation
    ('Lt.Gov.', 'MD/PhD', 'MD;'), sorted: a suffix's parts divided by
    any mark but the period first, each an acronym ('M.D./Ph.D.'),
    then any word's by every mark. Asked only where `_languages` finds
    nothing (`_languages_of`); its answer is dropped where the parse's
    own lexicon lists the word whole (`_listed_whole`)."""
    kinds = _kinds(kind, role)
    n = _normalize(text)
    found = (_by_parts(n, kinds, ".", files) if kinds is _SUFFIX_KINDS
             else ())
    return found or _by_parts(n, kinds, "", files)


def _by_parts(n: str, kinds: frozenset[str], keep: str,
              files: _ReadingFiles) -> tuple[str, ...]:
    """The files of the parts of `n`, sorted: divided by punctuation,
    symbols and spaces, but for the marks in `keep`, which are removed
    from each part instead; never by a combining mark, which a `[^\\w]`
    would count ('डॉ' in 'प्रोफे.डॉ.')."""
    parts = "".join(" " if c not in keep
                    and unicodedata.category(c)[0] in "PSZ" else c
                    for c in n).split()
    return tuple(sorted({
        tag for part in parts
        for tag in files.languages(
            part.replace(keep, "") if keep else part, kinds)}))


@functools.lru_cache(maxsize=4096)
def _forms(text: str) -> tuple[str, str]:
    """`text` as the vocabulary stores it, and without its periods."""
    n = _normalize(text)
    return n, n.replace(".", "")


def _listed_whole(text: str, lexicon: Lexicon) -> bool:
    """Whether the parse's own lexicon lists `text` whole, in either
    form, so that the parse read it whole and not by its parts: a
    caller's 'zzq-dr' title names none of the files of 'dr'. Asked
    only of a word whose whole form no file holds and whose parts some
    file does (`_part_languages`), so other words pay no frame."""
    n, bare = _forms(text)
    sets = lexicon._sets
    for name in _VOCAB_FIELDS:
        field = getattr(sets, name)
        if n in field or bare in field:
            return True
    return False


def _next_word(tokens: Sequence[WorkToken], dropped: set[int], i: int,
               step: int) -> int:
    """The index of the nearest token past `i` in direction `step` (1
    or -1) that is neither dropped nor a nickname: -1 or len(tokens)
    where none is. Asked only on the rare shapes its callers name."""
    j = i + step
    while 0 <= j < len(tokens) and (j in dropped
                                    or tokens[j].role is Role.NICKNAME):
        j += step
    return j


def _split_partner(tokens: tuple[WorkToken, ...], dropped: set[int],
                   i: int) -> str:
    """The text of the second word of the credential split across a
    space that token `i` opens: the next word past a nickname written
    between them ('Ph. "Bob" D.'), or nothing where that word is not
    the joined suffix word that completes it. Asked only of a split
    credential's first word, so other names pay nothing."""
    # classify tags a split's words only as a pair, so its second word
    # always follows; the bound test keeps parse total without a
    # branch no input reaches
    j = _next_word(tokens, dropped, i, 1)
    return (tokens[j].text if j < len(tokens) and tokens[j].role is Role.SUFFIX
            and "joined" in tokens[j].tags else "")


_reading = functools.lru_cache(maxsize=1024)(Reading)


#: Tags that serve the stages and reach no published token: classify's
#: kind tags for a listed suffix word (rules/R8) and a patronymic
#: particle, and P6's attachment mark (rules/R9), whose kind
#: `Token.reading` carries out; and the written-short mark rules/H5's
#: chain reads (#999), for which the published token keeps
#: TITLE_AMBIGUOUS_TAG; and the shared-name and particle-given marks
#: rules/O6 and O7 read (#704), the bound-phrase mark rules/P12
#: reads (#694), the past-reach mark on a particle chain past rules/P1's
#: fold (#828), and the joined-title mark rules/H5's chain reads
#: (#1104).
_KIND_TAGS = frozenset({GENERATION_WORD_TAG, CREDENTIAL_WORD_TAG, HONORIFIC_WORD_TAG,
                        PATRONYMIC_TAG, ATTACHED_TAG, TRAILING_TITLE_TAG,
                        SHARED_NAME_TAG, PARTICLE_GIVEN_TAG, PAST_REACH_TAG,
                        BOUND_PHRASE_TAG, JOINED_TITLE_TAG,
                        SURNAME_PAIR_TAG})

#: The second-surname mark O6 or W5 writes (rules/R10) and the
#: first-unit mark O6, W5 or O3 writes (rules/R11), which no published
#: token carries either:
#: `Reading.second_surname` and `Reading.first_surname` name them.
_SURNAME_UNITS = frozenset({SECOND_SURNAME_TAG, FIRST_SURNAME_TAG})

#: The tags that say a list or a shape made a word a suffix: without
#: one, a suffix word stands there by position, unless the vocabulary
#: lists it (a bracketed member, which classify leaves untagged).
_SUFFIX_EVIDENCE = frozenset({
    "vocab:suffix", "vocab:suffix-word", AMBIGUOUS_ACRONYM_TAG,
    AMBIGUOUS_WORD_TAG, AGNOMEN_TAG, SHAPE_ACRONYM_TAG,
    SPLIT_CREDENTIAL_TAG, SPLIT_MEMBER_TAG})

#: The tags that say the vocabulary lists a word as a title, in any of
#: the title sets, a dotted run's spelling without its stops included
#: (rules/H10).
_TITLE_TAGS = frozenset({
    "vocab:title", TITLE_AMBIGUOUS_TAG, "vocab:given-title",
    "vocab:after-given-title", DOTTED_TITLE_TAG})


def _alternative(pending: PendingAmbiguity, materialized: tuple[Token, ...],
                 final: dict[int, Token],
                 state: ParseState) -> Reading | None:
    """The public Reading of a report's PendingReading, its field named
    from the final roles where the emitter deferred it (O5's other
    primary field) and folded as `Policy.middle_as_family` folds every middle
    (rules/O6's neighbour, the policy's own fold), and its languages
    the files holding it for any word the report names."""
    alt = pending.alternative
    if alt is None or not materialized:
        return None
    role = alt.role
    if role is Deferred.OTHER_PRIMARY:
        role = (Role.FAMILY if materialized[0].role is Role.GIVEN
                else Role.GIVEN)
    elif isinstance(role, Beside) and role.index in final:
        beside = role
        front = final[beside.index]
        role = (beside.unfolded
                if FOLDED_TAG in front.tags and beside.unfolded is not None
                else front.role)
        # a chain whose last word stayed the family when its head left
        # it (rules/P10's middle name, which O7 may then take) lands the
        # word there; any other split names the head's field, and so
        # does a last word P6 attached to the family (FOLDED_TAG) (#704)
        if (role is not Role.FAMILY and beside.last is not None
                and beside.last != beside.index and beside.last in final
                and final[beside.last].role is Role.FAMILY
                and FOLDED_TAG not in final[beside.last].tags):
            role = Role.FAMILY
        # a chain opening a family-first name holding a name word of its
        # own: rules/P1's fold takes its particles and that ONE unit
        # (#828), so the word, joining it last, is laid out by the order
        # behind the family -- the other primary where it would be the
        # one word left, else the order's last name position -- unless
        # another word past the fold's reach was read against the whole
        # chain, which the fold then leaves whole (the one predicate the
        # fold asks)
        elif (role is Role.FAMILY and state.order is not None
                and state.order[0] is Role.FAMILY and beside.last is not None
                and beside.last in final
                and "particle" in front.tags
                and "particle" not in final[beside.last].tags
                and not reported_suffix_fork(
                    state.ambiguities,
                    [i for i in range(beside.index, pending.indices[0])
                     if PAST_REACH_TAG in state.tokens[i].tags],
                    skip=pending)):
            alone = (final[beside.last].role is Role.FAMILY
                     and not any(beside.last < i < pending.indices[0]
                                 for i in final))
            role = Role.GIVEN if alone else state.order[2]
    elif isinstance(role, (Deferred, Beside)):
        # assign found no name position to name it from
        return None
    # the files holding the reading for any of its words, as a token's
    # own reading names them, by the field before the policy's fold of
    # the middle (a middle word names the files listing it as given)
    found: set[str] = set()
    if alt.source in _LISTED:
        # a loop, not a generator, which would resume a frame per word
        for t in materialized:
            langs, by_parts = _languages_of(t.text, alt.kind, role,
                                            state.lexicon._files)
            if not (by_parts and _listed_whole(t.text, state.lexicon)):
                found.update(langs)
    if state.policy.middle_as_family and role is Role.MIDDLE:
        role = Role.FAMILY
    return Reading(alt.kind, role, alt.source, tuple(sorted(found)))


def _opens_its_segment(state: ParseState, i: int) -> bool:
    """Whether token `i` is the first word of its segment that is not a
    title: where rules/P5 joins a bound given name. Asked only of a
    word that is both a bound given name and a particle, read into the
    given part, so other names pay nothing."""
    dropped = state.dropped
    # every given-part token stands in a segment; the empty default
    # keeps parse total all the same
    seg = next((s for s in state.segments if i in s), ())
    return next((j for j in seg if j not in dropped
                 and state.tokens[j].role is not Role.TITLE), None) == i


#: The fields a Turkic marker and its father's name may stand in: the
#: name's own and the maiden name, a name of the same shape.
_PATRONYMIC_FIELDS = frozenset({*NAME_ROLES, Role.MAIDEN})


# rules/R9: "a standalone patronymic marker, O2's, with the name word
# before it in its comma part" -- the Turkic arm (decisions/R9, #754)
def _turkic_patronymics(state: ParseState,
                        dropped: set[int]) -> dict[int, int]:
    """The markers rules/R9's Turkic arm may read as a patronymic, each
    with the father's name before it: a marker standing in a name field
    or the maiden name, with the word before it, a nickname aside,
    standing in one too, the maiden name's own where the marker stands
    there, and in the marker's own comma part. The father is read once
    its marker reads as a name word. Asked only where the policy turns
    the rule on."""
    markers: dict[int, int] = {}
    tokens = state.tokens
    commas = state.comma_offsets
    for i, t in enumerate(tokens):
        if (i in dropped or t.role not in _PATRONYMIC_FIELDS
                or not is_patronymic_marker(t.text)):
            continue
        j = _next_word(tokens, dropped, i, -1)
        if (j >= 0 and tokens[j].role in _PATRONYMIC_FIELDS
                and (tokens[j].role is Role.MAIDEN) is (t.role is Role.MAIDEN)
                and comma_bucket(tokens[j].span.start, commas)
                == comma_bucket(t.span.start, commas)):
            markers[i] = j
    return markers


def _patronymic_opening(state: ParseState, dropped: set[int], i: int,
                        field: Role, folds_middle: bool) -> tuple[bool, bool]:
    """Whether the patronymic particle at `i`, read as a particle, names
    a parent (rules/R9), and whether it names it as P6's attachment: a
    particle P6 attached to the family written before it ('Mohamad,
    Mahathir bin', 'Bakar, Ali bin Abu') names that family, the words
    attached after it with it, where the family holds a word not
    folded; any other names the words after it in
    its field, a nickname aside, and one ending its field names nobody,
    a family word spelled as one ('Bar' in 'Fritz von Bar'). Asked only
    of a patronymic particle, so other names pay nothing."""
    tokens = state.tokens
    if ATTACHED_TAG in tokens[i].tags:
        # the family it attaches to must hold a word of its own: behind
        # an empty head P6 attaches it as the whole family (', Siti
        # Aminah binti'), which O3's fold can give a base, and a
        # particle with no family to name names nobody
        # (a loop, not a generator, which would resume a frame per word)
        for k, other in enumerate(tokens):
            if (other.role is Role.FAMILY and FOLDED_TAG not in other.tags
                    and k not in dropped):
                return True, True
        return False, False
    j = _next_word(tokens, dropped, i, 1)
    return (j < len(tokens)
            and _field_of(tokens[j], folds_middle) is field), False


def _field_of(token: WorkToken, folds_middle: bool) -> Role:
    """The field a token stands as: its role, save a middle word the
    policy folded into the family, which stands as the middle; a word
    P6 attached carries the folded mark too and stands as the family."""
    role = token.role if token.role is not None else Role.GIVEN
    return (Role.MIDDLE if role is Role.FAMILY and folds_middle
            and FOLDED_TAG in token.tags and ATTACHED_TAG not in token.tags
            else role)


def _listed_suffix(text: str, lexicon: Lexicon) -> bool:
    """Whether the suffix vocabulary lists, its periods removed, an
    acronym no tag marks: a bracketed member written with an interior
    period ('M.A' in 'John Smith (M.A)'), which rules/S13 settles by its
    writing and classify leaves untagged. A listed suffix WORD is
    always tagged, bracketed or not. Asked only of a suffix word with
    no suffix tag, so other names pay nothing."""
    n = _normalize(text).replace(".", "")
    return n in lexicon._sets.suffix_acronyms or n in lexicon._sets.suffix_acronyms_ambiguous


# rules/A2: "a name with no name content parses to the empty
# name — every field empty, false as a boolean — while ambiguities
# born from its punctuation survive on the empty result"
# (history: decisions/A2)
def assemble(state: ParseState) -> ParsedName:
    dropped = set(state.dropped)
    final: dict[int, Token] = {}
    surnames = state.lexicon._sets.surnames
    files = state.lexicon._files
    folds_middle = state.policy.middle_as_family
    tokens = state.tokens
    last = len(tokens)
    # the suffix reading of the token before, and whether it opens a
    # credential split across a space, whose second word takes it
    before: Reading | None = None
    prev_split = False
    # the field of the patronymic a patronymic particle opened, whose
    # run takes the words after it there; and the ending rules' words,
    # where a policy turns one on
    run_field: Role | None = None
    # a patronymic particle rules/P6 attached to the family written
    # before it, whose run is that family's own words
    attached = False
    rules = state.policy.patronymic_rules
    slavic = PatronymicRule.EAST_SLAVIC in rules
    markers = (_turkic_patronymics(state, dropped)
               if PatronymicRule.TURKIC in rules else {})
    # each marker's father, held unbuilt until its marker is read: the
    # word before it reads `patronymic` only where the marker reads as
    # a name word, and building its Token twice costs frames
    held: dict[int, tuple[str, Span | None, Role, frozenset[str], Reading]] = {}
    fathers = frozenset(markers.values())
    for i, t in enumerate(state.tokens):
        if i in dropped:
            continue
        role = t.role if t.role is not None else Role.GIVEN
        tags = t.tags
        # rules/R10: "the family's second name unit, the one written
        # second, makes the second-surname view" -- O6's mark, on family
        # words only; the word is read below as it reads without it,
        # and its reading then carries the mark (decisions/R10, #754)
        second = SECOND_SURNAME_TAG in tags
        # rules/R11: "the family's first name unit, the one written
        # first, makes the first-surname view" -- the first-unit mark O6
        # or O3 writes, read and carried out the same way (decisions/R11,
        # #1022)
        first = FIRST_SURNAME_TAG in tags
        if second or first:
            tags = tags - _SURNAME_UNITS
        # The reading the parse took (Token.reading): the final role
        # says which decision placed the word, and the tags the
        # deciding stages left (classify's, the `joined` and unjoined
        # marks) say which reading of it that decision weighed. Read
        # here, where roles are final, so a rule that moves a word
        # later (P1's fold, P6's attachment, the policy folds) needs
        # no reading of its own to keep in step. Per token, measured
        # 2026-10-29: no frame for an untagged non-suffix word, the
        # commonest; one for a listed or shaped suffix (`suffix_kind`,
        # reading the kind classify tagged) and for a tagged name word that reaches `name_source` or a
        # family word glued to the next (`_normalize`); three for a
        # suffix word nothing tags or lists (`suffix_kind`, then
        # `_listed_suffix` and its `_normalize`). `_vocab`'s two predicates
        # also name the sources of the reading NOT taken
        # (Ambiguity.alternative).
        # Reading.languages, the files holding the reading taken, on in
        # the parse's lexicon, is read below for a listed or declared
        # reading, through `_languages_of`, whose hit costs no frame,
        # save `_listed_whole` for a word read by its parts
        # (decisions/vocabulary-model, 2026-10-29; 2026-11-02, 4i-d;
        # 2026-11-05 #1085).
        reading: Reading | None = None
        if role is Role.SUFFIX:
            # a suffix ends a particle's run: the family can resume
            # behind it ('Hasan' in 'bin Ahmad Jr. Hasan, Ali')
            run_field = None
            kind, source = suffix_kind(t.text, tags)
            if (source is ReadingSource.VOCABULARY
                    and tags.isdisjoint(_SUFFIX_EVIDENCE)):
                if "conjunction" in tags:
                    # a connective joining two entries ('and' in 'John
                    # Smith, PhD and MD'), as in a title or name part
                    kind = ReadingKind.CONJUNCTION
                elif not _listed_suffix(t.text, state.lexicon):
                    # nothing lists or shapes it: a word read into the
                    # suffix by where it stands
                    source = ReadingSource.POSITION
                    if ("joined" in tags and before is not None
                            and prev_split):
                        # the second word of a credential split across
                        # a space, which is one credential ('Ph.' 'D.');
                        # any other word a run took stays a credential
                        # by position ('Jones' in 'John Smith III Jones'),
                        # files and all
                        reading = before
            prev_split = (SPLIT_CREDENTIAL_TAG in tags
                          or SPLIT_MEMBER_TAG in tags)
            if reading is None:
                # a credential split across a space is listed whole
                # ('Ph.' 'D.' as 'phd'): its first word reads the files
                # of the two words, which the second then takes
                written = (t.text + _split_partner(tokens, dropped, i)
                           if prev_split else t.text)
                langs, by_parts = (_languages_of(written, kind, role, files)
                                   if source in _LISTED else _UNLISTED)
                if by_parts and _listed_whole(written, state.lexicon):
                    langs = ()
                reading = (_reading(kind, role, source, langs) if langs
                           else _READINGS[kind, role, source])
            before = reading
        else:
            if role is not Role.NICKNAME:
                # a nickname written inside a split credential ('Ph.
                # "Bob" D.') leaves the run to its second word
                before = None
            if role is Role.TITLE:
                if "conjunction" in tags:
                    kind, source = (ReadingKind.CONJUNCTION,
                                    ReadingSource.VOCABULARY)
                elif not tags.isdisjoint(_TITLE_TAGS):
                    kind, source = ReadingKind.TITLE, ReadingSource.VOCABULARY
                elif is_title_shaped(t.text, state.lexicon):
                    # rules/H2: "an abbreviation the vocabulary reads as
                    # a given name written short", "word in one of the
                    # ten Brahmic scripts from Devanagari to Sinhala" and
                    # "has no period abbreviations either" -- H2's shape,
                    # asked through its own predicate; a word it refuses
                    # is a title only by where it stands (decisions/A1,
                    # 2026-11-09)
                    kind, source = ReadingKind.TITLE, ReadingSource.SHAPE
                else:
                    # a title phrase's connective object ('of
                    # Parliament'), a title by where it stands
                    kind, source = ReadingKind.TITLE, ReadingSource.POSITION
            elif not tags:
                kind, source = ReadingKind.NAME, ReadingSource.POSITION
                # a surname the segmentation split off an unspaced
                # name by the surname list ('김' in '김민준'): a family
                # word touching the next with nothing written between
                # (C-level). Spaced, the order placed the family and the
                # list decided nothing ('김' in '김 민준')
                if (role is Role.FAMILY and i + 1 < last
                        and tokens[i + 1].span.start == t.span.end
                        and _normalize(t.text) in surnames):
                    source = ReadingSource.VOCABULARY
            elif "initial" in tags:
                kind, source = ReadingKind.INITIAL, ReadingSource.SHAPE
            elif ("conjunction" in tags
                    and UNJOINED_CONJUNCTION_TAG not in tags):
                kind, source = (ReadingKind.CONJUNCTION,
                                ReadingSource.VOCABULARY)
            elif ("particle" in tags and UNJOINED_TAG not in tags
                    # a nickname has no family for a particle to join,
                    # and the unjoined marks are written in the name
                    # parts only ('"Van" Smith' reads a name)
                    and role is not Role.NICKNAME
                    and not ("vocab:bound-given" in tags
                             and role is Role.GIVEN
                             and _opens_its_segment(state, i))):
                kind, source = ReadingKind.PARTICLE, ReadingSource.VOCABULARY
            elif "vocab:bound-given" in tags:
                # rules/P5's bound given name, joined ('Abdul Aziz', and
                # 'Abu Bakar' in 'Abu Bakar Smith') or not ('Abdul' as a
                # middle name in 'John Abdul Smith'), a word the
                # vocabulary lists as a given name. One that is also a
                # particle ('abu') is P5's only in the given part and
                # only where P5 joins, the first word of its segment
                # past the titles; elsewhere the particle chain took it
                # (the family in 'John Abu Smith', the given part in
                # 'Salim Ali abu Bakar Hassan' under
                # FAMILY_FIRST_GIVEN_LAST) and it read the arm above
                kind, source = ReadingKind.NAME, ReadingSource.VOCABULARY
            else:
                # a particle or connective with nothing to join reads
                # as the name word it stands as ('van' in 'van Gogh')
                kind, source = ReadingKind.NAME, name_source(tags)
            # a name's files by its field, a middle word the policy
            # folded into the family by the middle it stands as
            # (inline, not `_field_of`: a frame per token, measured
            # 2026-10-29 at 7 on the reference row)
            field = (Role.MIDDLE if role is Role.FAMILY and folds_middle
                     and FOLDED_TAG in tags and ATTACHED_TAG not in tags
                     else role)
            # rules/R9: "a particle the lexicon holds as a patronymic",
            # read as a particle, opens a patronymic that
            # takes the words after it in its field; an ending rule a
            # policy turns on reads its own words (decisions/R9, #754)
            opens = attaches = False
            if kind is ReadingKind.PARTICLE and PATRONYMIC_TAG in tags:
                opens, attaches = _patronymic_opening(state, dropped, i,
                                                      field, folds_middle)
            if opens:
                kind = ReadingKind.PATRONYMIC
                run_field = field
                attached = attached or attaches
            elif field is run_field:
                kind, source = ReadingKind.PATRONYMIC, ReadingSource.POSITION
            else:
                if role is not Role.NICKNAME:
                    run_field = None
                # a marker or an ending read as a name word: one a
                # caller's Lexicon lists as a connective keeps that
                # reading, and its father with it
                if kind is ReadingKind.NAME and (
                        i in markers or slavic and field is Role.MIDDLE
                        and has_patronymic_ending(t.text)):
                    kind, source = ReadingKind.PATRONYMIC, ReadingSource.SHAPE
            if i in markers:
                text, span, frole, ftags, freading = held.pop(markers[i])
                if (kind is ReadingKind.PATRONYMIC
                        and freading.kind is not ReadingKind.PATRONYMIC):
                    # a father in the second surname keeps the mark
                    freading = _reading(ReadingKind.PATRONYMIC, frole,
                                        ReadingSource.POSITION, (),
                                        freading.second_surname,
                                        freading.first_surname)
                final[markers[i]] = Token(text, span, frole, ftags, freading)
            langs, by_parts = (_languages_of(t.text, kind, field, files)
                               if source in _LISTED else _UNLISTED)
            if by_parts and _listed_whole(t.text, state.lexicon):
                langs = ()
            reading = (_reading(kind, role, source, langs, second, first)
                       if langs or second or first
                       else _READINGS[kind, role, source])
        if not tags.isdisjoint(_KIND_TAGS):
            # the kind tags serve the stages and this one, whatever the
            # word's field (a lone 'Jr' is a given name), the reading
            # carrying the kind out; the written-short mark serves the
            # stages alone; and a published tag would make a name
            # unequal to its own 2.x pickle (Token compares tags)
            tags = tags - _KIND_TAGS
        if i in fathers:
            held[i] = (t.text, t.span, role, tags, reading)
        else:
            final[i] = Token(t.text, t.span, role, tags, reading)
    if markers:
        # a father built at its marker went in after the words between
        # them (a nickname); `final` is read in token order
        final = dict(sorted(final.items()))
    if attached:
        # rules/R9: "A trailing patronymic particle P6 attaches to the
        # family written before it takes that family's words as the
        # parent's name" (decisions/R9, #754)
        for j, tok in final.items():
            if (tok.role is Role.FAMILY and FOLDED_TAG not in tok.tags
                    and tok.reading is not None
                    and tok.reading.kind is not ReadingKind.PATRONYMIC):
                # a word of the second surname keeps the mark
                final[j] = Token(tok.text, tok.span, tok.role, tok.tags,
                                 _reading(ReadingKind.PATRONYMIC,
                                          Role.FAMILY,
                                          ReadingSource.POSITION, (),
                                          tok.reading.second_surname,
                                          tok.reading.first_surname))
    # No alphanumeric character among the SURVIVING tokens means no
    # name: a bare '.' or '- -' is not a person. v1 kept such input
    # (parse('.') -> first '.'); 2.0 empties it so bool() stays an
    # honest "did I get a name?" check. isalnum() is Unicode-aware, so
    # every real name in any script has content and only pure
    # punctuation/symbols empty out. (Embedded junk in a name with
    # content -- 'John . Smith' -- is left alone: that parse is truthy,
    # so bool() is not misled.)
    #
    # This read "anywhere" until #329, and the two said the same thing
    # for as long as nothing could take a content-bearing token away.
    # Dropping a maiden marker inside a delimited clause can, and
    # "(née —)" under Policy(maiden_delimiters=...) is the input where
    # the readings part: the marker is the clause's only alnum token,
    # so once it goes structural the em dash is all that survives and
    # the whole parse empties -- where 1.4.0 and pre-#329 both gave
    # maiden 'née —'. Deliberate, not fallout: a dropped marker is
    # structural like a delimiter character, and brackets plus a marker
    # plus a dash name no one, exactly as "(-)" already named no one.
    # A guard keyed on what ELSE is in the clause would be a different
    # rule, and would leave maiden holding marker-plus-punctuation.
    # Pinned by cases.py's maiden_marker_delimited_content_free and,
    # for the other side of it -- the same clause inside a name, where
    # the em dash survives as the maiden value because Jane Smith
    # carries the content -- ..._content_free_in_a_name beside it.
    #
    # The TOKENS go, not the diagnostics: this drops the name, and
    # "was the input malformed?" is the one question still worth
    # answering about it -- most of all here, where there is no parse
    # left to infer it from. parse('(') keeps its unbalanced-delimiter
    # report, pointing at no token because no token survived.
    contentless = not any(
        c.isalnum() for t in final.values() for c in t.text)
    if contentless:
        final = {}
    ambiguities = []
    segment_of: dict[int, tuple[int, ...]] | None = None
    for pending in state.ambiguities:
        materialized = tuple(final[i] for i in pending.indices
                             if i in final)
        if pending.indices and not materialized and not contentless:
            # every referent was dropped: the ambiguity describes
            # nothing that survives assembly. Born-empty ambiguities
            # (unbalanced delimiters) are token-independent and kept.
            # Not so when the whole name was emptied just above -- the
            # referents did not lose a contest, they were discarded
            # wholesale, and the report still describes the input.
            continue
        # rules/A1: "a report names the reading the parse took, so
        # a report whose fork the rest of the parse then resolved to
        # NEITHER branch is withdrawn rather than carried beside a
        # reading it contradicts". classify's connective-or-initial
        # fork offers exactly two readings and its detail says which
        # it took ("it is read as an initial"); a generation and an
        # honorific are neither. So where the parse goes on to role
        # that letter SUFFIX or TITLE the report is false on its
        # face, and 'JOHN QUINCY SMITH I' carried it beside a
        # suffix-or-name saying the same token reads as a
        # generational suffix (#397 second review). 'i' is the first
        # word that is both a marked connective and suffix
        # vocabulary, so no parse before this cycle could reach the
        # shape.
        #
        # WITHDRAWN HERE and not emitted later, which is the narrow
        # reading of mechanisms.md#AMBIGUITY-AT-THE-DECISION-SITE
        # rather than an exception to it: "Emit at the site that
        # takes the branch, not where an ambiguous tag sits" governs
        # the EMISSION, classify still owns the fork, and what this
        # drops is a report whose subject the parse went on to read
        # as something else. Here is the one place that knows --
        # roles are final and nothing downstream moves them -- and
        # the loop already withdraws a report whose referents did not
        # survive, just above.
        if (pending.kind is AmbiguityKind.CONJUNCTION_OR_INITIAL
                and any(t.role in (Role.SUFFIX, Role.TITLE)
                        for t in materialized)):
            continue
        # rules/P8: "unless no name word of its part stands to its
        # right" -- nothing after the letter in its segment, or only
        # suffixes, titles, a maiden clause or a nickname: it connects
        # nothing, so the report goes (#721). Asked here for the reason
        # above: the roles are final. Where the letter is also a
        # numeral the fork read, its own report (rules/S10) is the one
        # left, so one token never carries both. Built only for a
        # connective report, so other names pay nothing.
        if pending.kind is AmbiguityKind.CONJUNCTION_OR_INITIAL:
            if segment_of is None:
                segment_of = {j: seg for seg in state.segments
                              for j in seg}
            i = pending.indices[0]
            if not any(j > i and j in final
                       and final[j].role in NAME_ROLES
                       for j in segment_of.get(i, ())):
                continue
        detail = pending.detail
        if pending.field_tail is not None:
            # A report naming a field, in a name emptied above (no
            # emitter of one reaches that today: every referent is a
            # name word): no field is left to name, so it goes rather
            # than ship the sentence's first half.
            if not materialized:
                continue
            detail = (f"{detail}{FIELD_READING[materialized[0].role]}"
                      f"{pending.field_tail}")
        ambiguities.append(Ambiguity(
            pending.kind, detail, materialized,
            _alternative(pending, materialized, final, state)))
    # rules/R6: "the name is laid out in the order it was read in" --
    # ParsedName.order records that order for the rendering to read:
    # the order assign read the name in, given-first after a family
    # comma (which fixes the family without consulting an order), and
    # the declared name_order where no positional read happened; inline,
    # since every parse would pay a frame for a helper (decisions/R6,
    # #754)
    order = (state.order if state.order is not None
             else GIVEN_FIRST if state.structure is Structure.FAMILY_COMMA
             else state.policy.name_order)
    # rules/T7: "the given name is a run of single letters joined by
    # full stops" -- found inline (a helper would cost every parse a
    # frame, decisions/parse-cost): the one given word, a stop in it,
    # and a family beside it, a family comma marking one where it
    # names none (rules/C15) -- decisions/T7 (#1296)
    run_at = None
    has_family = state.structure is Structure.FAMILY_COMMA
    capitals = False
    for j, tok in final.items():
        if tok.role is Role.GIVEN:
            run_at = (-1 if run_at is not None or "." not in tok.text
                      else j)
        elif tok.role is Role.FAMILY:
            has_family = True
        if tok.role in NAME_ROLES and not tok.text.islower():
            capitals = True
    out = tuple(final.values())
    if (run_at is not None and run_at >= 0 and has_family
            and not state.policy.middle_as_family
            and not state.policy.two_given_names
            and final[run_at].span is not None
            and _LETTER_RUN.fullmatch(final[run_at].text)
            # written in capitals, or among given, middle and family
            # names written wholly in lower case, which read as their
            # capitals do (a title is not asked): a run in lower case
            # among capitals may be an abbreviation of its own ('Dr.
            # h.c. Hans Meier', honoris causa)
            and (final[run_at].text.isupper() or not capitals)
            # a run the vocabulary lists or masks whole is that word
            and not _listed_run(final[run_at].text, state.lexicon)):
        out, ambiguities = _part_letter_run(final[run_at], out,
                                            ambiguities, order)
    return ParsedName(original=state.original,
                      tokens=out,
                      ambiguities=tuple(ambiguities),
                      order=order)


# rules/T7: "it reads as its letters written with a space between
# them would: the letter in the given name's place in the order is the
# given name, and the others are middle names" -- decisions/T7 (#1296)
def _part_letter_run(whole: Token, tokens: tuple[Token, ...],
                     ambiguities: list[Ambiguity],
                     order: tuple[Role, Role, Role],
                     ) -> tuple[tuple[Token, ...], list[Ambiguity]]:
    """`tokens` with `whole`, a given name written as a run of single
    letters, parted into one initial per letter, and every report
    naming it naming its letters instead ('Smith, J.R.', a credential's
    shape after a comma), worded for them: the field it named is now
    the name's initials. The given name is the first letter, or the
    last where the order lays the given name out after the middle
    names."""
    assert whole.span is not None
    letters = _RUN_LETTER.findall(whole.text)
    given = (len(letters) - 1
             if order.index(Role.GIVEN) > order.index(Role.MIDDLE) else 0)
    start = whole.span.start
    parts: list[Token] = []
    for n, text in enumerate(letters):
        role = Role.GIVEN if n == given else Role.MIDDLE
        parts.append(Token(text, Span(start, start + len(text)), role,
                           _INITIAL_TAGS,
                           _READINGS[(ReadingKind.INITIAL, role,
                                      ReadingSource.SHAPE)]))
        start += len(text)
    at = tokens.index(whole)
    reported = [a if whole not in a.tokens else Ambiguity(
        a.kind, a.detail.replace(FIELD_READING[Role.GIVEN],
                                 "the name's initials"),
        tuple(p for t in a.tokens for p in (parts if t == whole else (t,))),
        a.alternative) for a in ambiguities]
    return tokens[:at] + tuple(parts) + tokens[at + 1:], reported


_INITIAL_TAGS = frozenset({"initial"})


def _listed_run(text: str, lexicon: Lexicon) -> bool:
    """Whether the lexicon lists `text`, a run of single letters, as a
    word of its own, written as it is, with its full stops: in a
    vocabulary set, or under a case mask keyed with them or writing one
    (a caller's honoris causa, 'h.c' or 'hc' masked 'h.c'). The spelling
    without stops is how initials spell a word, so a vocabulary word or
    a mask spelled without them says nothing about the run: 'J.R.' is
    no 'jr', and 'K.T.' and 'B.T.' part though 'Kt' and 'Bt' are
    credentials masked in mixed case."""
    n = _normalize(text)
    cap_map = lexicon._cap_map
    mask = cap_map.get(n)
    if mask is not None and not mask.isupper():
        return True
    bare = cap_map.get(n.replace(".", ""))
    if bare is not None and "." in bare:
        return True
    sets = lexicon._sets
    return any(n in getattr(sets, name) for name in _VOCAB_FIELDS)

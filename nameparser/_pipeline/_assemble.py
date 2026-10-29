"""Not a stage: converts the final ParseState into a public ParsedName.

Consumes: tokens (all roles set, and their tags, which name each
token's reading), dropped, order and structure (for ParsedName.order),
ambiguities (by index;
one carrying ``field_tail`` is worded from its word's final role,
#626), and segments, for the part a withdrawn connective report's
letter ends (rules/P8, #721).
Produces: a validated ParsedName, each token carrying the reading the
parse took (`Token.reading`) -- the constructor re-checks every
invariant (span order/bounds, ambiguity subset), so a pipeline bug
that would produce an invalid result dies HERE, not in a renderer
three layers away.
Reads: Policy.middle_as_family, folding a report's other field as the
policy folds a middle; Policy.name_order, for ParsedName.order where
no positional read happened; and Lexicon.surnames, suffix_acronyms and
suffix_acronyms_ambiguous, for the source of a token's reading where
no tag gives it. Not a Lexicon: the shipped reading index
(_reading_index.languages_of), for Reading.languages, which names the
files and so is the same under every Lexicon.

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
from types import MappingProxyType

from nameparser._lexicon import _VOCAB_FIELDS, Lexicon, _normalize
from nameparser._pipeline._state import (
    AGNOMEN_TAG, AMBIGUOUS_ACRONYM_TAG, AMBIGUOUS_WORD_TAG, FIELD_READING,
    NAME_ROLES, SHAPE_ACRONYM_TAG, SPLIT_CREDENTIAL_TAG, SPLIT_MEMBER_TAG,
    TITLE_AMBIGUOUS_TAG, Beside, Deferred, ParseState, PendingAmbiguity,
    Structure, WorkToken,
)
from nameparser._pipeline._vocab import (
    _PERIOD_ABBREV, name_source, suffix_kind,
)
from nameparser._reading_index import CATEGORY, languages_of
from nameparser._types import (
    FOLDED_TAG, GIVEN_FIRST, UNJOINED_CONJUNCTION_TAG, UNJOINED_TAG,
    Ambiguity, AmbiguityKind, ParsedName, Reading, ReadingKind,
    ReadingSource, Role, Token,
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
#: kind (the build's check 4) and the parse does not yet read it (4b).
#: A name reading's rows depend on its field (`_NAME_KINDS`). An
#: initial and a patronymic are read by shape or rule, never from a
#: file.
_SUFFIX_KINDS = _kinds_of("suffix")
_KINDS: MappingProxyType[ReadingKind, frozenset[str]] = MappingProxyType({
    ReadingKind.TITLE: _kinds_of("title"),
    ReadingKind.PARTICLE: _kinds_of("particle"),
    ReadingKind.CONJUNCTION: _kinds_of("conjunction"),
    ReadingKind.CREDENTIAL: _SUFFIX_KINDS,
    ReadingKind.GENERATION: _SUFFIX_KINDS,
    ReadingKind.AGNOMEN: _SUFFIX_KINDS,
    ReadingKind.POST_NOMINAL: _SUFFIX_KINDS,
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


# Both lookups are memos, C-level on a hit, so a word read before costs
# no frame (decisions/parse-cost), and both are pure functions of the
# shipped files, bounded since what keys them comes from the caller's
# text; so is `_reading`, of the readings that name files.
@functools.lru_cache(maxsize=4096)
def _languages(text: str, kind: ReadingKind, role: Role) -> tuple[str, ...]:
    """The files holding the `kind` reading of `text` as written, in
    `role`, Reading.languages: by the vocabulary's own form of the
    word, and then with every period removed, the form a credential is
    matched by ('M.A' in 'John Smith (M.A)') and a word listed whole
    without them ('Lt.Gen.' as 'ltgen')."""
    kinds = _kinds(kind, role)
    n = _normalize(text)
    found = languages_of(n, kinds)
    if not found and "." in n:
        found = languages_of(n.replace(".", ""), kinds)
    return found


@functools.lru_cache(maxsize=4096)
def _part_languages(text: str, kind: ReadingKind,
                    role: Role) -> tuple[str, ...]:
    """The files of the listed words `text` joins with punctuation
    ('Lt.Gov.', 'MD/PhD', 'MD;'), sorted: a suffix's parts divided by
    any mark but the period first, each an acronym ('M.D./Ph.D.'),
    then any word's by every mark. Read only for a word the parse's
    own lexicon does not list whole (`_listed_whole`)."""
    kinds = _kinds(kind, role)
    n = _normalize(text)
    found = _by_parts(n, kinds, ".") if kinds is _SUFFIX_KINDS else ()
    return found or _by_parts(n, kinds, "")


def _by_parts(n: str, kinds: frozenset[str], keep: str) -> tuple[str, ...]:
    """The files of the parts of `n`, sorted: divided by punctuation,
    symbols and spaces, but for the marks in `keep`, which are removed
    from each part instead; never by a combining mark, which a `[^\\w]`
    would count ('डॉ' in 'प्रोफे.डॉ.')."""
    parts = "".join(" " if c not in keep
                    and unicodedata.category(c)[0] in "PSZ" else c
                    for c in n).split()
    return tuple(sorted({
        tag for part in parts
        for tag in languages_of(part.replace(keep, "") if keep else part,
                                kinds)}))


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
    for name in _VOCAB_FIELDS:
        field = getattr(lexicon, name)
        if n in field or bare in field:
            return True
    return False


def _split_partner(tokens: tuple[WorkToken, ...], dropped: set[int],
                   i: int) -> str:
    """The text of the second word of the credential split across a
    space that token `i` opens: the next word past a nickname written
    between them ('Ph. "Bob" D.'), or nothing where that word is not
    the joined suffix word that completes it. Asked only of a split
    credential's first word, so other names pay nothing."""
    # classify tags a split's words only as a pair, so its second word
    # always follows; an empty default keeps parse total without a
    # branch no input reaches
    nxt = next((tokens[j] for j in range(i + 1, len(tokens))
                if j not in dropped and tokens[j].role is not Role.NICKNAME),
               None)
    return (nxt.text if nxt is not None and nxt.role is Role.SUFFIX
            and "joined" in nxt.tags else "")


_reading = functools.lru_cache(maxsize=1024)(Reading)


#: The tags that say a list or a shape made a word a suffix: without
#: one, a suffix word stands there by position, unless the vocabulary
#: lists it (a bracketed member, which classify leaves untagged).
_SUFFIX_EVIDENCE = frozenset({
    "vocab:suffix", "vocab:suffix-word", AMBIGUOUS_ACRONYM_TAG,
    AMBIGUOUS_WORD_TAG, AGNOMEN_TAG, SHAPE_ACRONYM_TAG,
    SPLIT_CREDENTIAL_TAG, SPLIT_MEMBER_TAG})

#: The tags that say the vocabulary lists a word as a title, in any of
#: the title sets.
_TITLE_TAGS = frozenset({
    "vocab:title", TITLE_AMBIGUOUS_TAG, "vocab:given-title",
    "vocab:after-given-title"})


def _alternative(pending: PendingAmbiguity, materialized: tuple[Token, ...],
                 final: dict[int, Token], middle_as_family: bool,
                 lexicon: Lexicon) -> Reading | None:
    """The public Reading of a report's PendingReading, its field named
    from the final roles where the emitter deferred it (O5's other
    primary field) and folded as `middle_as_family` folds every middle
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
        front = final[role.index]
        role = (role.unfolded
                if FOLDED_TAG in front.tags and role.unfolded is not None
                else front.role)
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
            langs = _languages(t.text, alt.kind, role)
            if (not langs
                    and (langs := _part_languages(t.text, alt.kind, role))
                    and _listed_whole(t.text, lexicon)):
                langs = ()
            found.update(langs)
    if middle_as_family and role is Role.MIDDLE:
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


def _listed_suffix(text: str, lexicon: Lexicon) -> bool:
    """Whether the suffix vocabulary lists, its periods removed, an
    acronym no tag marks: a bracketed member written with an interior
    period ('M.A' in 'John Smith (M.A)'), which rules/S13 settles by its
    writing and classify leaves untagged. A listed suffix WORD is
    always tagged, bracketed or not. Asked only of a suffix word with
    no suffix tag, so other names pay nothing."""
    n = _normalize(text).replace(".", "")
    return n in lexicon.suffix_acronyms or n in lexicon.suffix_acronyms_ambiguous


# rules/A2: "a name with no name content parses to the empty
# name — every field empty, false as a boolean — while ambiguities
# born from its punctuation survive on the empty result"
# (history: decisions/A2)
def assemble(state: ParseState) -> ParsedName:
    dropped = set(state.dropped)
    final: dict[int, Token] = {}
    surnames = state.lexicon.surnames
    folds_middle = state.policy.middle_as_family
    tokens = state.tokens
    last = len(tokens)
    # the suffix reading of the token before, and whether it opens a
    # credential split across a space, whose second word takes it
    before: Reading | None = None
    prev_split = False
    for i, t in enumerate(state.tokens):
        if i in dropped:
            continue
        role = t.role if t.role is not None else Role.GIVEN
        tags = t.tags
        # The reading the parse took (Token.reading): the final role
        # says which decision placed the word, and the tags the
        # deciding stages left (classify's, the `joined` and unjoined
        # marks) say which reading of it that decision weighed. Read
        # here, where roles are final, so a rule that moves a word
        # later (P1's fold, P6's attachment, the policy folds) needs
        # no reading of its own to keep in step. Per token, measured
        # 2026-10-29: no frame for an untagged non-suffix word, the
        # commonest; one for a listed or shaped suffix (`suffix_kind`)
        # and for a tagged name word that reaches `name_source` or a
        # family word glued to the next (`_normalize`); three for a
        # suffix word nothing tags or lists (`suffix_kind`, then
        # `_listed_suffix` and its `_normalize`). `_vocab`'s two predicates
        # also name the sources of the reading NOT taken
        # (Ambiguity.alternative).
        # Reading.languages, the files holding the reading taken, is
        # read below from phase 3's reading index for a listed or
        # declared reading, through `_languages`, whose hit costs no
        # frame (decisions/vocabulary-model, 2026-10-29).
        reading: Reading | None = None
        if role is Role.SUFFIX:
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
                langs = _languages(written, kind, role) if source in _LISTED else ()
                if (not langs and source in _LISTED
                        and (langs := _part_languages(written, kind, role))
                        and _listed_whole(written, state.lexicon)):
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
                elif _PERIOD_ABBREV.match(t.text):
                    # rules/H2's shape: an unlisted abbreviation
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
            field = (Role.MIDDLE if role is Role.FAMILY and folds_middle
                     and FOLDED_TAG in tags else role)
            langs = _languages(t.text, kind, field) if source in _LISTED else ()
            if (not langs and source in _LISTED
                    and (langs := _part_languages(t.text, kind, field))
                    and _listed_whole(t.text, state.lexicon)):
                langs = ()
            reading = (_reading(kind, role, source, langs) if langs
                       else _READINGS[kind, role, source])
        final[i] = Token(t.text, t.span, role, tags, reading)
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
            _alternative(pending, materialized, final,
                         state.policy.middle_as_family, state.lexicon)))
    return ParsedName(original=state.original,
                      tokens=tuple(final.values()),
                      ambiguities=tuple(ambiguities),
                      order=_read_order(state))


def _read_order(state: ParseState) -> tuple[Role, Role, Role]:
    """ParsedName.order: the order assign read the name in, given-first
    after a family comma (which fixes the family without consulting
    an order), and the declared name_order where no positional read
    happened."""
    # rules/R6: "the name is laid out in the order it was read in" --
    # this records that order for the rendering to read (decisions/R6,
    # #754)
    if state.order is not None:
        return state.order
    if state.structure is Structure.FAMILY_COMMA:
        return GIVEN_FIRST
    return state.policy.name_order

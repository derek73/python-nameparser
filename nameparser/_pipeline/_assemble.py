"""Not a stage: converts the final ParseState into a public ParsedName.

Consumes: tokens (all roles set, and their tags, which name each
token's reading), dropped, ambiguities (by index;
one carrying ``field_tail`` is worded from its word's final role,
#626), and segments, for the part a withdrawn connective report's
letter ends (rules/P8, #721).
Produces: a validated ParsedName, each token carrying the reading the
parse took (`Token.reading`) -- the constructor re-checks every
invariant (span order/bounds, ambiguity subset), so a pipeline bug
that would produce an invalid result dies HERE, not in a renderer
three layers away.
Reads: Policy.middle_as_family, folding a report's other field as the
policy folds a middle; and Lexicon.surnames, suffix_acronyms and
suffix_acronyms_ambiguous, for the source of a token's reading where
no tag gives it.

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

from types import MappingProxyType

from nameparser._lexicon import Lexicon, _normalize
from nameparser._pipeline._state import (
    AGNOMEN_TAG, AMBIGUOUS_ACRONYM_TAG, AMBIGUOUS_WORD_TAG, FIELD_READING,
    NAME_ROLES, SHAPE_ACRONYM_TAG, SPLIT_CREDENTIAL_TAG, SPLIT_MEMBER_TAG,
    TITLE_AMBIGUOUS_TAG, Beside, Deferred, ParseState, PendingAmbiguity,
)
from nameparser._pipeline._vocab import (
    _PERIOD_ABBREV, name_source, suffix_kind,
)
from nameparser._types import (
    FOLDED_TAG, UNJOINED_CONJUNCTION_TAG, UNJOINED_TAG, Ambiguity,
    AmbiguityKind, ParsedName, Reading, ReadingKind, ReadingSource, Role,
    Token,
)

#: Every Reading a token can take, built once: a `Reading` is three
#: enum members, so the parse hands out shared instances rather than
#: constructing one per token, which would cost two frames a word
#: (decisions/parse-cost).
_READINGS = MappingProxyType({
    (kind, role, source): Reading(kind, role, source)
    for kind in ReadingKind for role in Role for source in ReadingSource})

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
                 final: dict[int, Token],
                 middle_as_family: bool) -> Reading | None:
    """The public Reading of a report's PendingReading, its field named
    from the final roles where the emitter deferred it (O5's other
    primary field) and folded as `middle_as_family` folds every middle
    (rules/O6's neighbour, the policy's own fold)."""
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
    if middle_as_family and role is Role.MIDDLE:
        role = Role.FAMILY
    return Reading(alt.kind, role, alt.source)


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
        # family word glued to the next (`_normalize`); four for a
        # suffix word nothing tags or lists (`_listed_suffix` and its
        # `_normalize` beside it). `_vocab`'s two predicates
        # also name the sources of the reading NOT taken
        # (Ambiguity.alternative).
        # Reading.languages joins here, in 4a's follow-up: phase 3's
        # reading index (`_reading_index.readings_of`, 3a) answers
        # which files hold a reading.
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
                        # by position ('Jones' in 'John Smith III Jones')
                        kind, source = before.kind, before.source
            reading = _READINGS[kind, role, source]
            before = reading
            prev_split = (SPLIT_CREDENTIAL_TAG in tags
                          or SPLIT_MEMBER_TAG in tags)
        else:
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
            elif "particle" in tags and UNJOINED_TAG not in tags:
                kind, source = ReadingKind.PARTICLE, ReadingSource.VOCABULARY
            elif "vocab:bound-given" in tags:
                # rules/P5's bound given name, joined ('Abdul Aziz') or
                # not ('Abdul' as a middle name in 'John Abdul Smith'),
                # a word the vocabulary lists as a given name. One that
                # is also a particle ('abu') read the particle arm above
                # wherever it joins: no tag tells P5's join from the
                # chain's, which under FAMILY_FIRST_GIVEN_LAST can leave
                # it in the given part too ('Salim Ali abu Bakar Hassan')
                kind, source = ReadingKind.NAME, ReadingSource.VOCABULARY
            else:
                # a particle or connective with nothing to join reads
                # as the name word it stands as ('van' in 'van Gogh')
                kind, source = ReadingKind.NAME, name_source(tags)
            reading = _READINGS[kind, role, source]
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
                         state.policy.middle_as_family)))
    return ParsedName(original=state.original,
                      tokens=tuple(final.values()),
                      ambiguities=tuple(ambiguities))

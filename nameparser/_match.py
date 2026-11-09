"""Name matching: the settings object, the result types and the check.

Not a stage: nothing here runs inside a parse. `Matching` carries a
`Parser`, the set of outcomes the caller accepts and the switch for
other readings, and its `check` compares two parsed names role by
role.
Produces: `Outcome`, `Side`, `RoleMatch`, `CrossRoleMatch`, `MatchResult`,
`DEFAULT_ACCEPT` and `Matching`.
Reads: the `Parser`'s `Lexicon`, for the listed spellings (`same_as`)
through `Lexicon._headwords`, each role in the group of its kind
(`_GROUP`), for the familiar forms (`short_for`) through
`Lexicon._familiar_forms`, and for `Lexicon.particles`, a hyphen half
that is a listed particle being set aside, and its `revise`, for a
name's other readings (`Matching.other_readings`); no `Policy` field.

Consistent means nothing in the two names contradicts it, under the
outcomes the caller accepts. The module imports `_types`, `_policy`
(for the scripts that write no initials) and `_lexicon` (for
`_normalize`, which folds a hyphen half before it is looked up among
the particles), and `Lexicon` and `Parser` for typing alone.
"""
from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from nameparser._lexicon import FULL_STOPS, _normalize
from nameparser._policy import _NO_INITIALS, _script_matcher
from nameparser._types import (
    UNJOINED_TAG,
    Ambiguity,
    ParsedName,
    Role,
    _coerce_enum,
    _guarded_getstate,
    _guarded_setstate,
)

if TYPE_CHECKING:
    from nameparser._lexicon import Lexicon
    from nameparser._parser import Parser


class Outcome(StrEnum):
    """How one role of one name compares with the same role of another,
    listed in the order `check` ranks them, strongest first. `strength`
    is that rank as a number, larger for a stronger outcome and lowest
    for `conflict`; rank outcomes by it, since `<` on an Outcome
    compares the names as strings (`folded` sorts before `same`).
    `conflict` is the one outcome that is never accepted. The search
    for each side's other readings is not an outcome but a switch,
    `Matching.other_readings`, and the reading used is named in
    `MatchResult.left_alternative` and `right_alternative`."""

    SAME = "same"
    FOLDED = "folded"
    LISTED_SPELLING = "listed-spelling"
    PARTICLES_ASIDE = "particles-aside"
    PART_OF_OTHER = "part-of-other"
    INITIAL = "initial"
    INITIALS_AGREE = "initials-agree"
    ONE_SIDE = "one-side"
    GENERATION_ONE_SIDE = "generation-one-side"
    NOTED = "noted"
    FAMILIAR_FORM = "familiar-form"
    FAMILY_INITIAL = "family-initial"
    GIVEN_ONE_SIDE = "given-one-side"
    HYPHENATED_PART = "hyphenated-part"
    ACROSS_ROLES = "across-roles"
    CONFLICT = "conflict"

    @property
    def strength(self) -> int:
        """The outcome's rank as a number: `conflict` is 0, and each
        outcome declared before another is stronger than it, `same`
        the strongest."""
        return _STRENGTH[self]


#: Each outcome's strength, from its declaration order.
_STRENGTH: Mapping[Outcome, int] = {
    o: len(Outcome) - 1 - i for i, o in enumerate(Outcome)}


class Side(StrEnum):
    """Which side of a comparison carried more of the role's text."""

    LEFT = "left"
    RIGHT = "right"
    NEITHER = "neither"


_MIRROR = {Side.LEFT: Side.RIGHT, Side.RIGHT: Side.LEFT, Side.NEITHER: Side.NEITHER}


@dataclass(frozen=True, slots=True)
class RoleMatch:
    """One role's comparison: the outcome, both sides' text, and which
    side carried more. On a row read `across-roles`, the side carrying
    more is the one whose name held both the role and the cross role
    the match used (`J. Edgar Hoover` / `Edgar Hoover`: left)."""

    role: Role
    outcome: Outcome
    left: str
    right: str
    more: Side

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def mirrored(self) -> RoleMatch:
        """The same comparison with the two names swapped."""
        return RoleMatch(self.role, self.outcome, self.right, self.left,
                         _MIRROR[self.more])


@dataclass(frozen=True, slots=True)
class CrossRoleMatch:
    """A role of one name matched against a different role of the
    other (`across-roles`): the left name's role and text, the right
    name's role and text, and the outcome of comparing the two texts."""

    left_role: Role
    right_role: Role
    outcome: Outcome
    left: str
    right: str

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def mirrored(self) -> CrossRoleMatch:
        """The same match with the two names swapped."""
        return CrossRoleMatch(self.right_role, self.left_role, self.outcome,
                              self.right, self.left)


@dataclass(frozen=True, slots=True)
class MatchResult:
    """The result of comparing two names: whether nothing in them
    contradicts the match under the accepted outcomes, one `RoleMatch`
    per `Role`, in `Role` order, the `CrossRoleMatch` behind each
    role reading `across-roles`, in `Role` order of the role it
    resolved (empty unless `across-roles` is accepted), and on each
    side the `Ambiguity` whose other reading the table used, or `None`
    where that side is read as parsed (always `None` unless
    `other_readings` is on). A side uses one other reading at a
    time; each row keeps its own outcome under it.

    A row is read by its role, a `Role` member or its name
    (`result["suffix"]`), and `weakest` is the weakest row's outcome."""

    consistent: bool
    roles: tuple[RoleMatch, ...]
    across: tuple[CrossRoleMatch, ...] = ()
    left_alternative: Ambiguity | None = None
    right_alternative: Ambiguity | None = None

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        order = ", ".join(r.value for r in Role)
        if not isinstance(self.roles, tuple):
            raise TypeError(
                f"roles must be a tuple of RoleMatch, one per Role, got "
                f"{type(self.roles).__name__}; pass tuple(rows)")
        for row in self.roles:
            if not isinstance(row, RoleMatch):
                raise TypeError(
                    f"roles must hold RoleMatch rows, got "
                    f"{type(row).__name__} {row!r}; build each row as "
                    f"RoleMatch(role, outcome, left, right, more)")
        held = [row.role for row in self.roles]
        if held != list(Role):
            raise ValueError(
                f"roles must hold one RoleMatch per Role, in Role order "
                f"({order}), got {', '.join(str(r) for r in held) or 'none'}; "
                f"pass a row for every role, in that order")

    def __getitem__(self, role: Role | str) -> RoleMatch:
        """The row of one role: a `Role` member or its name; anything
        else raises ValueError naming the valid roles."""
        return self.roles[_RANK_ROLE[_coerce_enum(role, Role, "Role", "roles")]]

    @property
    def weakest(self) -> Outcome:
        """The weakest row's outcome, by `Outcome.strength`."""
        return _weakest(r.outcome for r in self.roles)

    def mirrored(self) -> MatchResult:
        """The same result with the two names swapped: each role's left
        and right text exchanged and its `more` side flipped, each
        cross-role match's roles and texts exchanged, and the two sides'
        alternatives exchanged."""
        return MatchResult(self.consistent,
                           tuple(m.mirrored() for m in self.roles),
                           tuple(c.mirrored() for c in self.across),
                           self.right_alternative, self.left_alternative)


#: The outcomes accepted when a caller states none.
DEFAULT_ACCEPT: frozenset[Outcome] = frozenset({
    Outcome.SAME, Outcome.FOLDED, Outcome.LISTED_SPELLING,
    Outcome.PARTICLES_ASIDE, Outcome.PART_OF_OTHER, Outcome.INITIAL,
    Outcome.INITIALS_AGREE, Outcome.ONE_SIDE, Outcome.GENERATION_ONE_SIDE,
    Outcome.NOTED,
})

_VALID = ", ".join(o.value for o in Outcome if o is not Outcome.CONFLICT)
#: The code a refused `accept` is offered: it extends the default set,
#: which a bare `accept=` would replace, and type-checks.
_ACCEPT_HINT = ('pass e.g. parser.matching(accept=parser.matching().accept'
                ' | {"family-initial"})')
#: The spelling of the other-reading search before it became a switch,
#: refused with the call that replaces it.
_OTHER_READING = "other-reading"
#: The code a refused `other-reading` member is offered; it type-checks.
_OTHER_READINGS_HINT = "parser.matching(other_readings=True)"


def _outcome(value: object) -> Outcome:
    # not _coerce_enum: its message would list `conflict` among the
    # valid values, which accept refuses
    if isinstance(value, Outcome):
        return value
    if isinstance(value, str):
        if value == _OTHER_READING:
            raise ValueError(
                f"{_OTHER_READING!r} is not an outcome: the search for each "
                f"side's other readings is a switch; drop it from accept, "
                f"keep the rest, and pass other_readings=True beside it, "
                f"e.g. {_OTHER_READINGS_HINT}")
        try:
            return Outcome(value)
        except ValueError:
            raise ValueError(
                f"unknown outcome {value!r}; valid outcomes: {_VALID}"
            ) from None
    raise TypeError(
        f"accept must be an iterable of outcome names or Outcome members, "
        f"got a member {value!r} of type {type(value).__name__}; "
        f"{_ACCEPT_HINT}")


@dataclass(frozen=True, slots=True)
class Matching:
    """The settings of a name match: the parser that reads the names and
    the outcomes accepted as consistent, and whether each side's other
    readings are searched.

    `accept` takes any iterable of `Outcome` members or their names and is
    stored as a frozenset with `same` always present. Passing it replaces
    the default set rather than extending it, so extend the default
    matcher's set: `parser.matching(accept=parser.matching().accept |
    {"family-initial"})`. `conflict` cannot be accepted.

    `other_readings`, a bool, off by default, switches on the search
    for each side's other readings where the names as parsed are not
    consistent (see `check`), and the keys of each reading searched
    (see `keys`). It is not an outcome: no row reads it, and each row
    keeps its own outcome under the reading used.
    """

    parser: Parser
    accept: frozenset[Outcome] = DEFAULT_ACCEPT
    other_readings: bool = False

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if not callable(getattr(self.parser, "parse", None)):
            raise TypeError(
                f"parser must be a Parser, got {type(self.parser).__name__}; "
                f"pass Parser() or use Parser.matching()")
        accept = self.accept
        if isinstance(accept, (str, bytes, Mapping)) or not isinstance(accept, Iterable):
            raise TypeError(
                f"accept must be an iterable of outcome names, got "
                f"{type(accept).__name__} {accept!r}; {_ACCEPT_HINT}")
        outcomes = frozenset(_outcome(v) for v in accept)
        if Outcome.CONFLICT in outcomes:
            raise ValueError(
                f"'conflict' cannot be accepted: it is the outcome of a "
                f"contradiction; drop it from accept (valid outcomes: "
                f"{_VALID})")
        object.__setattr__(self, "accept", outcomes | {Outcome.SAME})
        if not isinstance(self.other_readings, bool):
            raise TypeError(
                f"other_readings must be a bool, got "
                f"{type(self.other_readings).__name__} "
                f"{self.other_readings!r}; pass other_readings=True or "
                f"other_readings=False")

    def __repr__(self) -> str:
        added = sorted(o.value for o in self.accept - DEFAULT_ACCEPT)
        removed = sorted(o.value for o in DEFAULT_ACCEPT - self.accept)
        if self.other_readings:
            # a switch, not an outcome, so it follows the outcomes added
            added.append("other-readings")
        parts = ["default"]
        if added:
            parts.append("+ " + ", ".join(added))
        if removed:
            parts.append("- " + ", ".join(removed))
        return f"Matching({' '.join(parts)})"

    def check(self, a: str | ParsedName, b: str | ParsedName) -> MatchResult:
        """Compare two names role by role. A string is parsed with this
        settings object's parser. The result is consistent when every
        role's outcome is among the accepted ones; `conflict` never is,
        and an empty family role on either side is a conflict. The
        check is symmetric: swapping the names gives the mirrored
        result. It is not transitive: `J. Smith` is consistent with
        `John Smith` and with `Jane Smith`, which are not consistent
        with each other.

        Where `other_readings` is on and the names as parsed are
        not consistent, each side's other readings are tried too: one
        per `Ambiguity` with an `alternative`, its words moved to the
        alternative's role, one ambiguity at a time and never two
        together, save an alternative into the title or suffix, which
        is not tried: a title never conflicts and a suffix only on its
        generation, so the move could only empty a role that does.
        The table reported is the one with the strongest outcomes, each
        row keeping its own outcome, and the result names in
        `left_alternative` and `right_alternative` the ambiguity whose
        other reading each side used.

        Where `across-roles` is accepted, a given or family role whose
        outcome is not accepted is compared with a different role of
        the other name: a given name with each word of the other's
        middle name and with its nickname, a family name with the
        other's maiden name. Only a full name on both sides counts, at
        `same`, `folded` or `listed-spelling`, never an initial. The
        strongest match resolves the role, which then reads
        `across-roles`, and is recorded in the result's `across`; a
        middle word it used is taken out of the middle comparison, the
        words left compared role to role. No cross-role match is tried
        where `across-roles` is not accepted. The family role must still
        agree, here directly or through the maiden name."""
        left, right = self._parsed(a), self._parsed(b)
        best = self._result(left, right)
        if best.consistent or not self.other_readings:
            return best
        # each side's first reading is the name as parsed, so the pair
        # of those is `best`, already built
        candidates = [best, *(
            self._result(ra, rb, alt_a, alt_b)
            for ra, alt_a in self._readings(left)
            for rb, alt_b in self._readings(right)
            if alt_a is not None or alt_b is not None)]
        return min(candidates, key=_strength)

    def keys(self, name: str | ParsedName) -> frozenset[str]:
        """Grouping keys: for each word of the folded family base, and
        each half of a hyphenated one beside its joined and its whole
        form, a half that is a listed particle left out (`Al-Saud` keys
        `saud`, `alsaud` and `al-saud`, never `al`), one key `word;g`
        where `g` is the first letter of the given name (empty where
        there is none). A word is keyed by every word in its spelling
        set among surnames (itself and the words it is listed as a
        spelling of, read as written and folded, each folded), and a
        given name by the first letter of every word in its set among
        given names, where a word that is a name of its own as well
        (`jo`) contributes only itself unless written with its trailing
        period, the one spelling set the check reads (`_spellings`),
        and where `familiar-form` is accepted also by the first letter
        of every name a word of that set is paired with directly as a
        familiar form, in either direction (`Bill` keys `w` for William
        beside `b`, and `William` keys `b`).
        The guarantee rests on this: two words the check
        reads as listed spellings have sets that meet, so they share a
        member and with it a key; every family-base word the default
        check compares is keyed, so two names it finds consistent share
        a key and grouping by key loses no match. A name with no family
        has no key.

        Each accepted opt-in adds the keys its outcome needs:
        `family-initial` a key `f;g` for the first letter `f` of the
        family's first word, `given-one-side` a bare key for every
        family part keyed and `across-roles` the maiden name's
        words without particles as family words, and as given letters
        the first letter of each middle word and of the nickname's
        first word, save a middle word or a nickname written in
        initials alone, which the check never matches across roles.
        Where `other_readings` is on, each other reading `check` tries
        adds its own keys."""
        parsed = self._parsed(name)
        readings = (self._readings(parsed) if self.other_readings
                    else [(parsed, None)])
        return frozenset().union(
            *(self._keys(reading) for reading, _ in readings))

    def _result(self, left: ParsedName, right: ParsedName,
                left_alternative: Ambiguity | None = None,
                right_alternative: Ambiguity | None = None) -> MatchResult:
        """The table of two readings, each side's alternative the
        ambiguity whose other reading it is, `None` for a name as
        parsed."""
        lexicon = self.parser.lexicon
        roles = [_compare_role(role, left, right, lexicon) for role in Role]
        across: list[CrossRoleMatch] = []
        if Outcome.ACROSS_ROLES in self.accept:
            middles = [left.middle.split(), right.middle.split()]
            for i, r in enumerate(roles):
                if r.outcome in self.accept or r.role not in _ACROSS:
                    continue
                found = self._across(r.role, left, right)
                if found is None:
                    continue
                cross, index = found
                # the side carrying more is the one whose name held both
                # the role and the cross role the match used
                holder = Side.RIGHT if cross.left_role is r.role else Side.LEFT
                held = r.left if holder is Side.LEFT else r.right
                roles[i] = dataclasses.replace(
                    r, outcome=Outcome.ACROSS_ROLES,
                    more=holder if held else Side.NEITHER)
                across.append(cross)
                if index is not None:
                    # the middle word matched as the given name is
                    # consumed, and the words left compare role to role,
                    # the row keeping both sides' text as parsed
                    del middles[0 if cross.left_role is Role.MIDDLE
                                else 1][index]
                    la, lb = (" ".join(words) for words in middles)
                    outcome = _middle_outcome(la, lb, lexicon)
                    roles[_MIDDLE] = dataclasses.replace(
                        roles[_MIDDLE], outcome=outcome,
                        more=(Side.NEITHER if outcome is Outcome.CONFLICT
                              else _more(la, lb)))
        return MatchResult(all(r.outcome in self.accept for r in roles),
                           tuple(roles), tuple(across),
                           left_alternative, right_alternative)

    def _across(self, role: Role, left: ParsedName, right: ParsedName,
                ) -> tuple[CrossRoleMatch, int | None] | None:
        """The strongest match of `role` on one side against one of its
        cross roles (`_ACROSS`) on the other, or `None`, with the index
        of the middle word it used (`None` for a role other than the
        middle; the match's middle role names the side): a middle name
        word by word, the other roles whole. Only a full name on both
        sides counts (`_full_outcome`), never an initial. The pick is by
        outcome, then by texts and roles named without a side, so it is
        the same with the names swapped."""
        lexicon = self.parser.lexicon
        group = _GROUP[role]
        found: list[tuple[tuple[object, ...],
                          tuple[CrossRoleMatch, int | None]]] = []
        for other in _ACROSS[role]:
            for lrole, rrole in ((other, role), (role, other)):
                rights = [(t, _fold(t)) for t in _cross_texts(right, rrole)]
                for li, la in enumerate(_cross_texts(left, lrole)):
                    fla = _fold(la)
                    for ri, (ra, fra) in enumerate(rights):
                        outcome = _full_outcome(la, ra, fla, fra, lexicon, group)
                        if (outcome is None or outcome not in self.accept
                                or _initials_only(fla) or _initials_only(fra)):
                            continue
                        theirs, mine = (la, ra) if lrole is other else (ra, la)
                        index = (None if other is not Role.MIDDLE
                                 else li if lrole is other else ri)
                        found.append((
                            (-_STRENGTH[outcome], _RANK_ROLE[other], theirs, mine),
                            (CrossRoleMatch(lrole, rrole, outcome, la, ra),
                             index)))
        return min(found, key=lambda f: f[0])[1] if found else None

    def _readings(self, name: ParsedName
                  ) -> list[tuple[ParsedName, Ambiguity | None]]:
        """The name as parsed, with no ambiguity, then one other
        reading per ambiguity whose `alternative` moves a word into a
        role other than the title or suffix (`_NOT_TRIED_INTO`): that
        ambiguity's words moved to the alternative's role by
        `Parser.revise`, with the ambiguity."""
        readings: list[tuple[ParsedName, Ambiguity | None]] = [(name, None)]
        for ambiguity in name.ambiguities:
            if ambiguity.alternative is None:
                continue
            target = ambiguity.alternative.role
            if target in _NOT_TRIED_INTO:
                continue
            words = [t for t in ambiguity.tokens if t.role is not target]
            if not words:
                continue
            moved = frozenset({target, *(t.role for t in words)})
            # the moved name's texts, read off its own views so a word
            # a division cut keeps its halves joined
            laid_out = ParsedName(name.original, tuple(
                dataclasses.replace(t, role=target, reading=None)
                if t in words else t for t in name.tokens))
            readings.append((self.parser.revise(
                name, **{r.value: getattr(laid_out, r) for r in moved}),
                ambiguity))
        return readings

    def _keys(self, parsed: ParsedName) -> frozenset[str]:
        lexicon = self.parser.lexicon
        across = Outcome.ACROSS_ROLES in self.accept
        bases = [parsed.family_base]
        if across:
            bases.append(_maiden_base(parsed))
        forms: list[str] = []
        for base in bases:
            forms += _family_words(base, lexicon)
            # a hyphenated word joined and whole too: either may itself
            # be the full form another word is listed as a spelling of
            forms += [form for raw in base.split() if "-" in raw
                      for form in (raw.replace("-", ""), raw)]
        words = set().union(*(_spelling_keys(form, "family", lexicon)
                              for form in forms if form))
        family = parsed.family.split()
        if family and words and Outcome.FAMILY_INITIAL in self.accept:
            words |= {f[:1] for f in _spelling_keys(
                family[0], "family", lexicon)} - {""}
        given = parsed.given.split()
        initials = ({g[:1] for g in _spelling_keys(given[0], "given", lexicon)}
                    if given else {""})
        if given and Outcome.FAMILIAR_FORM in self.accept:
            # every name the check pairs with it as a familiar form,
            # either way (`_familiar`), so `Bill` and `William` share
            # each other's keys
            initials |= {g[:1] for g in _paired_forms(
                _spellings(given[0], "given", lexicon), lexicon)} - {""}
        if across:
            # the texts the check matches against a given name, each
            # refused as it refuses them: a cross-role match is never
            # made by initials alone (`_initials_only`, so `J.-P.` is
            # not keyed); a text is keyed by its first word's letter
            for other in _ACROSS[Role.GIVEN]:
                for text in _cross_texts(parsed, other):
                    if not _initials_only(_fold(text)):
                        initials |= {g[:1] for g in _spelling_keys(
                            text.split()[0], "given", lexicon)}
        keys = {f"{w};{g}" for w in words for g in initials}
        if Outcome.GIVEN_ONE_SIDE in self.accept:
            keys |= words
        return frozenset(keys)

    def _parsed(self, name: object) -> ParsedName:
        if isinstance(name, ParsedName):
            return name
        if isinstance(name, str):
            return self.parser.parse(name)
        raise TypeError(
            f"check takes a name string or a ParsedName, got "
            f"{type(name).__name__} {name!r}; pass the text, or "
            f"parser.parse(text)")


# -- the check -------------------------------------------------------------

#: Full stops and apostrophes: the typed one, the typographic U+2019
#: and the modifier letter U+02BC, so `O’Brien` folds to `obrien`.
_DROPPED = str.maketrans("", "", ".'\u2019\u02bc")
#: The scripts whose combining marks `_fold` drops as accents.
_ACCENTED_SCRIPTS = ("LATIN ", "GREEK ", "CYRILLIC ")
_WORDS = re.compile(r"[\s-]+")
#: rules/R7's scripts that write no initials (_policy._NO_INITIALS): a
#: single character in one of them is a whole word, never an initial.
_initialless = _script_matcher(*_NO_INITIALS, whole=True)
#: The roles an alternative reading is not tried into: a title never
#: conflicts and a suffix only on its generation, so a word moved there
#: could only empty a role that does.
_NOT_TRIED_INTO = frozenset({Role.TITLE, Role.SUFFIX})
#: The roles a cross-role match may resolve, each with the roles of the
#: other name it is tried against (`across-roles`).
_ACROSS: Mapping[Role, tuple[Role, ...]] = {
    Role.GIVEN: (Role.MIDDLE, Role.NICKNAME),
    Role.FAMILY: (Role.MAIDEN,),
}
_RANK_ROLE = {r: i for i, r in enumerate(Role)}
#: `FULL_STOPS` as the tuple `str.endswith` takes, one test for the
#: period `_spellings` reads off a word as written.
_FULL_STOPS = tuple(FULL_STOPS)
_MIDDLE = _RANK_ROLE[Role.MIDDLE]
#: The `same_as` group each role reads its listed spellings in: the
#: readings of the kind that stands there (`Lexicon._headwords`), so a
#: given name's spelling never matches a surname (`Ma.` / `María` agree
#: as given names; the surname Ma never matches María).
_GROUP: Mapping[Role, str] = {
    Role.TITLE: "title",
    Role.GIVEN: "given",
    Role.MIDDLE: "given",
    Role.FAMILY: "family",
    Role.SUFFIX: "suffix",
    Role.NICKNAME: "given",
    Role.MAIDEN: "family",
}


def _maiden_base(name: ParsedName) -> str:
    """The maiden name without its particles, as `family_base` writes
    the family's."""
    return name._text_for(Role.MAIDEN, without_tag="particle",
                          unless_tag=UNJOINED_TAG)


def _cross_texts(name: ParsedName, role: Role) -> list[str]:
    """The texts of `role` a cross-role match compares: a middle name's
    words one by one, any other role whole."""
    if role is Role.MIDDLE:
        return name.middle.split()
    text: str = getattr(name, role)
    return [text] if text else []



def _fold(text: str) -> str:
    """The text with case, accents, full stops and apostrophes folded
    away: NFC, `.` and the apostrophes `'`, U+2019 and U+02BC removed,
    NFD, casefolded, then NFC again, so the folded text, and every key
    cut from it, is precomposed (a Hangul syllable, never a conjoining
    jamo). Hyphens and spaces are kept. A combining mark (Mn) is dropped
    only where the letter it attaches to is Latin, Greek or Cyrillic,
    where it is an accent; in another script (a Devanagari virama,
    anusvara or vowel sign) it is spelling and is kept. A letter counts
    as in those scripts where it or its casefolded form is, so a letter
    that casefolds into one (the micro sign U+00B5 into Greek mu, U+2183
    into Latin) loses its mark on the first fold, which keeps the fold
    idempotent; so does removing the full stops and apostrophes before
    the marks are read, a mark after one then attaching to the letter
    before it, and again after casefolding, which can write one (U+0149
    `ŉ` casefolds to `ʼn`). The iota subscript U+0345 is a mark like any
    other, so `ᾳ` folds to `α`."""
    if text.isascii():
        # no accent, no composition, and no apostrophe but the typed one
        return text.casefold().translate(_DROPPED)
    decomposed = unicodedata.normalize(
        "NFD", unicodedata.normalize("NFC", text).translate(_DROPPED))
    kept = []
    accented = False
    for c in decomposed:
        if unicodedata.category(c) == "Mn":
            if accented:
                continue
        else:
            accented = (unicodedata.name(c, "").startswith(_ACCENTED_SCRIPTS)
                        or unicodedata.name(c.casefold()[:1] or c, "")
                        .startswith(_ACCENTED_SCRIPTS))
        kept.append(c)
    # again after casefolding, which can write an apostrophe (U+0149)
    return unicodedata.normalize(
        "NFC", "".join(kept).casefold().translate(_DROPPED))


def _strength(result: MatchResult) -> tuple[object, ...]:
    """The order `check` picks a table by, best first: consistent, then
    the weakest outcome strongest (then the next weakest, and so on),
    then fewer sides read another way, then each role's text pair, each
    cross-role match's and the two alternatives, each pair taken
    without its sides, which keeps the pick the same with the names
    swapped."""
    alternatives = (result.left_alternative, result.right_alternative)
    ranks = sorted((-_STRENGTH[r.outcome] for r in result.roles),
                   reverse=True)
    sides = sum(a is not None for a in alternatives)
    texts = tuple(tuple(sorted((r.left, r.right))) for r in result.roles)
    across = tuple(sorted(((c.left, c.left_role), (c.right, c.right_role)))
                   for c in result.across)
    return (not result.consistent, ranks, sides, texts, across,
            sorted(_ambiguity_key(a) for a in alternatives))


def _ambiguity_key(ambiguity: Ambiguity | None) -> tuple[str, ...]:
    """An ambiguity as sortable text, `()` for none."""
    if ambiguity is None:
        return ()
    alternative = ambiguity.alternative
    return (ambiguity.kind.value, ambiguity.detail,
            repr([(t.text, t.span) for t in ambiguity.tokens]),
            alternative.role.value if alternative is not None else "")


def _weakest(outcomes: Iterable[Outcome]) -> Outcome:
    return min(outcomes, key=_STRENGTH.__getitem__)


def _letters(text: str) -> int:
    return sum(c.isalnum() for c in _fold(text))


def _more(left: str, right: str) -> Side:
    if left == right:
        return Side.NEITHER
    a, b = _letters(left), _letters(right)
    return Side.LEFT if a > b else Side.RIGHT if b > a else Side.NEITHER


def _is_initial(folded: str) -> bool:
    return len(folded) == 1 and folded.isalpha() and not _initialless(folded)


def _spellings(word: str, group: str, lexicon: Lexicon) -> frozenset[str]:
    """The words `word` is a listed spelling of in `group`, the word
    itself included, read from the word as written and from it folded,
    each member beside its folded form: `Jose` among given names reaches
    `jo`'s full form `josé` folded, so `Jo.` and `Jose` meet. A word that
    is a name of its own as well reaches its links only written with
    its trailing period, any full stop the vocabulary strips
    (`FULL_STOPS`, `Jo．` too), read here off the word as written since
    both the normalizing and the fold drop it: `Jo` is the given name Jo
    alone (decisions/name-matching, 2026-11-08 #1006 follow-up)."""
    period = word.endswith(_FULL_STOPS)
    heads = (lexicon._headwords(word, group, period=period)
             | lexicon._headwords(_fold(word), group, period=period))
    return heads | {_fold(h) for h in heads}


def _spelling_keys(word: str, group: str, lexicon: Lexicon) -> set[str]:
    """The folded members of `word`'s spelling set in `group`, which
    `keys` cuts its keys from: every spelling set holds each member's
    folded form, so two sets that meet share a folded member. `_fold` is
    idempotent (test_match.py holds it over every assigned code point,
    alone and beside letters, hyphens and combining marks), so the
    folded members are the folds of `_spellings`' own."""
    return {_fold(h) for h in _spellings(word, group, lexicon)}


def _listed(a: str, b: str, group: str, lexicon: Lexicon) -> bool:
    """Two words are listed spellings of one word in `group`: their
    spelling sets meet."""
    return not _spellings(a, group, lexicon).isdisjoint(
        _spellings(b, group, lexicon))


def _part_agrees(a: str, b: str, lexicon: Lexicon,
                 group: str) -> Outcome | None:
    """One word against one word: `same` where they are equal once
    folded or listed as one spelling in `group`, `initial` where one is
    an initial of the other's first letter, else `None`. A hyphenated
    word is compared part by part against the other's hyphen-split
    parts (`J.-P.` / `Jean-Pierre`)."""
    fa, fb = _fold(a), _fold(b)
    if fa == fb or _listed(a, b, group, lexicon):
        return Outcome.SAME
    if (_is_initial(fa) and fb[:1] == fa) or (_is_initial(fb) and fa[:1] == fb):
        return Outcome.INITIAL
    pa, pb = a.split("-"), b.split("-")
    if len(pa) > 1 and len(pa) == len(pb):
        parts = [_part_agrees(x, y, lexicon, group) for x, y in zip(pa, pb)]
        if None not in parts:
            return _weakest(p for p in parts if p is not None)
    return None


def _paired_forms(spellings: frozenset[str], lexicon: Lexicon) -> set[str]:
    """The given names any member of a spelling set is paired with
    directly as a familiar form, in either direction, each folded and
    as normalized."""
    paired = {name for word in spellings
              for name in lexicon._familiar_forms(word)}
    return paired | {_fold(name) for name in paired}


def _familiar(a: str, b: str, lexicon: Lexicon) -> bool:
    """One given-name word and the other are a listed familiar-form
    pair (`Bill` / `William`, `Masha` / `Maria`): a name one word's
    spelling set is paired with directly meets the other's spelling
    set. Read whichever way the source wrote the pair, since nam_dict
    does not always write the shorter name first, and never chained, so
    two longer names paired with one short name (`Maximilian` /
    `Maxim`) are no pair. Asked from both sides, since the pairs are
    keyed as written (`mária`) and a spelling set reaches a word's fold
    but not its accented form (`Maria` / `Mari`, Mária's familiar
    form); symmetric in its two arguments."""
    sa, sb = _spellings(a, "given", lexicon), _spellings(b, "given", lexicon)
    return (not _paired_forms(sa, lexicon).isdisjoint(sb)
            or not _paired_forms(sb, lexicon).isdisjoint(sa))


def _familiar_outcome(wa: list[str], wb: list[str],
                      lexicon: Lexicon) -> Outcome | None:
    """Two given texts' words, pair by pair, each the same once folded,
    a listed spelling or a familiar form, and at least one a familiar
    form: `familiar-form`, else `None`."""
    if len(wa) != len(wb):
        return None
    found = False
    for x, y in zip(wa, wb):
        if _fold(x) == _fold(y) or _listed(x, y, "given", lexicon):
            continue
        if not _familiar(x, y, lexicon):
            return None
        found = True
    return Outcome.FAMILIAR_FORM if found else None


def _initials_only(folded: str) -> bool:
    """A folded text is initials alone."""
    return all(_is_initial(w) for w in _WORDS.split(folded) if w)


def _full_outcome(a: str, b: str, fa: str, fb: str, lexicon: Lexicon,
                  group: str) -> Outcome | None:
    """Two non-empty texts, `fa` and `fb` their folded forms, as full
    names: same, folded, or listed spelling (word by word, in the role's
    `same_as` `group`), else `None`."""
    if a == b:
        return Outcome.SAME
    if fa == fb:
        return Outcome.FOLDED
    wa, wb = a.split(), b.split()
    if len(wa) == len(wb) and all(
            _listed(x, y, group, lexicon) for x, y in zip(wa, wb)):
        return Outcome.LISTED_SPELLING
    return None


def _text_outcome(a: str, b: str, lexicon: Lexicon, group: str,
                  bases: tuple[str, str] | None = None) -> Outcome:
    """Two non-empty texts of one role, by the strongest outcome that
    holds: a full-name outcome (`_full_outcome`), then for a family,
    given its two `bases`, particles set aside and part of the other,
    then initial against name (family initial in the family role), then
    initials agree, then in the `given` group a familiar form, then
    a hyphenated part, else conflict."""
    if a == b:
        return Outcome.SAME
    fa, fb = _fold(a), _fold(b)
    outcome = _full_outcome(a, b, fa, fb, lexicon, group)
    if outcome is not None:
        return outcome
    family = bases is not None
    wa, wb = a.split(), b.split()
    if bases is not None:
        if bases[0] and _fold(bases[0]) == _fold(bases[1]):
            return Outcome.PARTICLES_ASIDE
        sa, sb = _base_words(bases[0], lexicon), _base_words(bases[1], lexicon)
        if sa and sb and (sa <= sb or sb <= sa):
            return Outcome.PART_OF_OTHER
    if len(wa) == len(wb):
        parts = [_part_agrees(x, y, lexicon, group) for x, y in zip(wa, wb)]
        if None not in parts and Outcome.INITIAL in parts:
            return Outcome.FAMILY_INITIAL if family else Outcome.INITIAL
    if _initials_only(fa) and _initials_only(fb) and (
            _WORDS.split(fa) == _WORDS.split(fb)):
        return Outcome.INITIALS_AGREE
    if not family and group == "given" and (
            familiar := _familiar_outcome(wa, wb, lexicon)) is not None:
        return familiar
    if not family and len(wa) == len(wb) == 1 and (
            _first_half(fa, fb) or _first_half(fb, fa)):
        return Outcome.HYPHENATED_PART
    return Outcome.CONFLICT


def _particle_half(folded: str, lexicon: Lexicon) -> bool:
    """A folded half of a hyphenated family word that is a listed
    particle (`al` in `Al-Saud`): set aside like a spaced particle, so it
    is neither a family-base word for `part-of-other` nor a key."""
    # _normalize is the lexicon's own key normalizer, so the half is
    # looked up as the particle set's keys are written
    return _normalize(folded) in lexicon._sets.particles


def _family_words(base: str, lexicon: Lexicon) -> list[str]:
    """A family base's comparable words, as written: each word, and a
    hyphenated one as its halves less any listed particle, an empty half
    dropped. Read by `part-of-other` (`_base_words`) and by `keys`, so
    the two set aside the same halves. Raw and folded agree half for
    half: `_fold` never adds or removes a hyphen or a space (test_match.py
    holds it over every assigned code point in context), so a word's
    halves fold to its folded halves, save that a word or half of full
    stops folds to empty."""
    words: list[str] = []
    for word in base.split():
        halves = word.split("-")
        if len(halves) > 1:
            words += [h for h in halves
                      if h and not _particle_half(_fold(h), lexicon)]
        else:
            words.append(word)
    return words


def _base_words(base: str, lexicon: Lexicon) -> set[str]:
    """The folded family-base words `part-of-other` compares, a word
    that folds to empty left out."""
    return {_fold(w) for w in _family_words(base, lexicon)} - {""}


def _first_half(w: str, hyphenated: str) -> bool:
    """The folded word `w` is the first half of the folded `hyphenated`
    (`hong` / `hong-yi`): the first half only, which shares the given
    initial a key is cut on."""
    parts = hyphenated.split("-")
    return len(parts) > 1 and "-" not in w and bool(w) and parts[0] == w


def _middle_outcome(a: str, b: str, lexicon: Lexicon) -> Outcome:
    """The middle role word by word, in order: each aligned pair by
    `_text_outcome`, each word past the shorter side one-sided, the role
    taking the weakest; `same` where both are empty."""
    wa, wb = a.split(), b.split()
    if not wa and not wb:
        return Outcome.SAME
    outcomes = [_text_outcome(x, y, lexicon, "given") for x, y in zip(wa, wb)]
    if len(wa) != len(wb):
        outcomes.append(Outcome.ONE_SIDE)
    return _weakest(outcomes)


def _noted(a: str, b: str, lexicon: Lexicon, group: str) -> Outcome:
    """A role that never conflicts: equal by any spelling, else noted."""
    if not a and not b:
        return Outcome.SAME
    if a and b:
        return (_full_outcome(a, b, _fold(a), _fold(b), lexicon, group)
                or Outcome.NOTED)
    return Outcome.NOTED


def _suffix_outcome(left: ParsedName, right: ParsedName,
                    lexicon: Lexicon) -> Outcome:
    """A different generation conflicts and one on one side only is its
    own outcome, whatever credentials either side carries; where the
    generations agree, the rest of the suffix (credentials, honorifics)
    is noted."""
    if left.suffix == right.suffix:
        return Outcome.SAME
    ga, gb = left.generation, right.generation
    if ga and gb:
        full = _full_outcome(ga, gb, _fold(ga), _fold(gb), lexicon, "suffix")
        if full is None:
            return Outcome.CONFLICT
        generation = full
    elif ga or gb:
        return Outcome.GENERATION_ONE_SIDE
    else:
        generation = Outcome.SAME
    rest = _noted(" ".join(filter(None, (left.credentials, left.honorifics))),
                  " ".join(filter(None, (right.credentials, right.honorifics))),
                  lexicon, "suffix")
    return _weakest((generation, rest))


def _compare_role(role: Role, left: ParsedName, right: ParsedName,
                  lexicon: Lexicon) -> RoleMatch:
    a, b = getattr(left, role), getattr(right, role)
    if role is Role.SUFFIX:
        outcome = _suffix_outcome(left, right, lexicon)
    elif role is Role.TITLE:
        outcome = _noted(a, b, lexicon, "title")
    elif role is Role.FAMILY and not (a and b):
        outcome = Outcome.CONFLICT
    elif not a and not b:
        outcome = Outcome.SAME
    elif role is Role.MIDDLE:
        outcome = _middle_outcome(a, b, lexicon)
    elif not (a and b):
        outcome = Outcome.GIVEN_ONE_SIDE if role is Role.GIVEN else Outcome.ONE_SIDE
    else:
        outcome = _text_outcome(
            a, b, lexicon, _GROUP[role],
            (left.family_base, right.family_base)
            if role is Role.FAMILY else None)
    more = Side.NEITHER if outcome is Outcome.CONFLICT else _more(a, b)
    return RoleMatch(role, outcome, a, b, more)

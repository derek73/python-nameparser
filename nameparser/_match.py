"""Name matching: the settings object, the result types and the check.

Not a stage: nothing here runs inside a parse. `Matching` carries a
`Parser`, the set of outcomes the caller accepts and the switch for
other readings, and its `check` compares two parsed names role by
role.
Produces: `Outcome`, `Side`, `RoleMatch`, `CrossRoleMatch`, `MatchResult`,
`DEFAULT_ACCEPT` and `Matching`.
Reads: the `Parser`'s `Lexicon`, for the listed spellings (`same_as`)
through `Lexicon._headwords`, each role in the group of its kind
(its `_RULES` row), for the familiar forms (`short_for`) through
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
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from nameparser._lexicon import FULL_STOPS, _fold, _normalize
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
    is that rank as an ordinal, larger for a stronger outcome and 0 for
    `conflict`; compare outcomes by it, since `<` on an Outcome
    compares the names as strings (`folded` sorts before `same`), but
    never store one: the values change when an outcome is added.
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
        """The outcome's rank as an ordinal to compare outcomes by:
        `conflict` is 0, and each outcome declared before another is
        stronger than it, `same` the strongest. The values change when
        an outcome is added, so compare them, never store one."""
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
        familiar form, in either direction (`Bill` and `William` each
        key both `b` and `w`).
        The guarantee rests on this: two words the check
        reads as listed spellings have sets that meet, so they share a
        member and with it a key; every family-base word the default
        check compares is keyed, so two names it finds consistent share
        a key and grouping by key loses no match. A name with no family
        has no key.

        Each accepted opt-in adds the keys its outcome needs:
        `familiar-form` the given letters of the paired names (above),
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
        roles = [_compare_role(role, left, right, lexicon, self.accept)
                 for role in Role]
        across: list[CrossRoleMatch] = []
        if Outcome.ACROSS_ROLES in self.accept:
            middles = [left.middle.split(), right.middle.split()]
            for i, r in enumerate(roles):
                if r.outcome in self.accept or not _RULES[r.role].across:
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
                    outcome = _middle_outcome(la, lb, lexicon, self.accept,
                                              _RULES[Role.MIDDLE].group)
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
        cross roles (its `_RULES` row's `across`) on the other, or `None`, with the index
        of the middle word it used (`None` for a role other than the
        middle; the match's middle role names the side): a middle name
        word by word, the other roles whole. Only a full name on both
        sides counts (`_full_outcome`), never an initial. The pick is by
        outcome, then by texts and roles named without a side, so it is
        the same with the names swapped."""
        lexicon = self.parser.lexicon
        rule = _RULES[role]
        found: list[tuple[tuple[object, ...],
                          tuple[CrossRoleMatch, int | None]]] = []
        for other in rule.across:
            for lrole, rrole in ((other, role), (role, other)):
                rights = [(t, _fold(t)) for t in _cross_texts(right, rrole)]
                for li, la in enumerate(_cross_texts(left, lrole)):
                    fla = _fold(la)
                    for ri, (ra, fra) in enumerate(rights):
                        outcome = _full_outcome(la, ra, fla, fra, lexicon,
                                                rule.group)
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
        role its `_RULES` row lets one be tried into (not the title or
        suffix): that
        ambiguity's words moved to the alternative's role by
        `Parser.revise`, with the ambiguity."""
        readings: list[tuple[ParsedName, Ambiguity | None]] = [(name, None)]
        for ambiguity in name.ambiguities:
            if ambiguity.alternative is None:
                continue
            target = ambiguity.alternative.role
            if not _RULES[target].tried_into:
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
        family_rule, given_rule = _RULES[Role.FAMILY], _RULES[Role.GIVEN]
        assert family_rule.base is not None
        bases = [family_rule.base(parsed)]
        if across:
            bases.append(_maiden_base(parsed))
        forms: list[str] = []
        for base in bases:
            forms += _family_words(base, lexicon)
            # a hyphenated word joined and whole too: either may itself
            # be the full form another word is listed as a spelling of
            forms += [form for raw in base.split() if "-" in raw
                      for form in (raw.replace("-", ""), raw)]
        words = set().union(*(_spelling_keys(form, family_rule.group, lexicon)
                              for form in forms if form))
        family = parsed.family.split()
        if family and words and Outcome.FAMILY_INITIAL in self.accept:
            words |= {f[:1] for f in _spelling_keys(
                family[0], family_rule.group, lexicon)} - {""}
        given = parsed.given.split()
        initials = ({g[:1] for g in _spelling_keys(
            given[0], given_rule.group, lexicon)} if given else {""})
        if given and Outcome.FAMILIAR_FORM in self.accept:
            # every name the check pairs with it as a familiar form,
            # either way (`_familiar`), so `Bill` and `William` share
            # each other's keys
            initials |= {g[:1] for g in _paired_forms(
                _spellings(given[0], given_rule.group, lexicon), lexicon)} - {""}
        if across:
            # the texts the check matches against a given name, each
            # refused as it refuses them: a cross-role match is never
            # made by initials alone (`_initials_only`, so `J.-P.` is
            # not keyed); a text is keyed by its first word's letter
            for other in given_rule.across:
                for text in _cross_texts(parsed, other):
                    if not _initials_only(_fold(text)):
                        initials |= {g[:1] for g in _spelling_keys(
                            text.split()[0], given_rule.group, lexicon)}
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

_WORDS = re.compile(r"[\s-]+")
#: rules/R7's scripts that write no initials (_policy._NO_INITIALS): a
#: single character in one of them is a whole word, never an initial.
_initialless = _script_matcher(*_NO_INITIALS, whole=True)
_RANK_ROLE = {r: i for i, r in enumerate(Role)}
#: `FULL_STOPS` as the tuple `str.endswith` takes, one test for the
#: period `_spellings` reads off a word as written.
_FULL_STOPS = tuple(FULL_STOPS)
_MIDDLE = _RANK_ROLE[Role.MIDDLE]


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
    set. Read whichever way the source wrote the pair, since the
    sources do not always write the shorter name first, and never
    chained, so two longer names paired with one short name
    (`Maximilian` / `Maxim`) are no pair. Symmetric in its two arguments by
    construction: the lexicon pairs each name both ways and under its
    fold as well (`Lexicon._familiar_forms`), and a spelling set holds
    each member's fold, so asking from the second side finds nothing the
    first does not (measured over every pair of the 1,034 familiar
    names nam_dict shipped and their folds, 2026-11-08)."""
    sa, sb = _spellings(a, "given", lexicon), _spellings(b, "given", lexicon)
    return not _paired_forms(sa, lexicon).isdisjoint(sb)


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


def _text_outcomes(a: str, b: str, lexicon: Lexicon, group: str,
                   bases: tuple[str, str] | None = None) -> Iterator[Outcome]:
    """The outcomes that hold for two non-empty texts of one role,
    strongest first, lazily, and last conflict, which always holds. An
    outcome holds only where the leniency it names was needed: none is
    yielded where a stronger one that implies it holds, nor in the
    family role after the first of its chain (decisions/name-matching,
    2026-11-08 FAMILIAR FORMS, the review's ruling 1).

    - A full-name outcome (`_full_outcome`: same, folded, listed
      spelling) implies every weaker one, two texts equal once folded
      or listed as one needing no other leniency, so it is the only
      outcome yielded.
    - In the family role (given its two `bases`) the outcomes are
      treated as one chain, particles set aside, part of the other,
      family initial, initials agree, and the first that holds is the
      only one yielded. They are not all implied by the one before:
      part of the other and family initial are independent leniencies
      (`John S.` / `John S.-Jones` holds both), so a pair holding an
      unaccepted part of the other is refused even where family
      initial holds and is accepted.
    - In any other role, initial against name and initials agree are
      one leniency, the first that holds of the two yielded; a familiar
      form (in the `given` group) and a hyphenated part are each
      orthogonal to it and to each other, so each is yielded where it
      holds (`Jean` / `Jean-Paul`, a caller's familiar pair and a
      hyphenated part both)."""
    fa, fb = _fold(a), _fold(b)
    full = _full_outcome(a, b, fa, fb, lexicon, group)
    wa, wb = a.split(), b.split()
    if full is not None:
        yield full
    elif bases is not None:
        chain = _family_outcome(wa, wb, fa, fb, bases, lexicon, group)
        if chain is not None:
            yield chain
    else:
        initials = _initial_outcome(wa, wb, fa, fb, lexicon, group)
        if initials is not None:
            yield initials
        if group == "given" and (
                familiar := _familiar_outcome(wa, wb, lexicon)) is not None:
            yield familiar
        if len(wa) == len(wb) == 1 and (
                _first_half(fa, fb) or _first_half(fb, fa)):
            yield Outcome.HYPHENATED_PART
    yield Outcome.CONFLICT


def _initial_outcome(wa: list[str], wb: list[str], fa: str, fb: str,
                     lexicon: Lexicon, group: str) -> Outcome | None:
    """Two texts' words, as `wa` and `wb`, folded whole as `fa` and
    `fb`: `initial` where every pair agrees and one is an initial of
    its name, else `initials-agree` where both are initials alone and
    the same ones, else `None`."""
    if len(wa) == len(wb):
        parts = [_part_agrees(x, y, lexicon, group) for x, y in zip(wa, wb)]
        if None not in parts and Outcome.INITIAL in parts:
            return Outcome.INITIAL
    if _initials_only(fa) and _initials_only(fb) and (
            _WORDS.split(fa) == _WORDS.split(fb)):
        return Outcome.INITIALS_AGREE
    return None


def _family_outcome(wa: list[str], wb: list[str], fa: str, fb: str,
                    bases: tuple[str, str], lexicon: Lexicon,
                    group: str) -> Outcome | None:
    """The family role's leniencies, treated as one chain, the first
    that holds: the bases equal once folded (particles set aside), one
    base's words among the other's (part of the other), an initial
    against the family name (family initial), initials alone agreeing.
    A later one is not always implied by an earlier (`John S.` /
    `John S.-Jones` holds part of the other and family initial both),
    and only the first is returned (`_text_outcomes`)."""
    if bases[0] and _fold(bases[0]) == _fold(bases[1]):
        return Outcome.PARTICLES_ASIDE
    sa, sb = _base_words(bases[0], lexicon), _base_words(bases[1], lexicon)
    if sa and sb and (sa <= sb or sb <= sa):
        return Outcome.PART_OF_OTHER
    initials = _initial_outcome(wa, wb, fa, fb, lexicon, group)
    return (Outcome.FAMILY_INITIAL if initials is Outcome.INITIAL
            else initials)


def _pick(outcomes: Iterable[Outcome], accept: frozenset[Outcome]) -> Outcome:
    """The outcome a row reports: the strongest that holds and is
    accepted, else, where none of those holding is accepted, the
    strongest that holds, so an unaccepted outcome still says what the
    pair needed (`Jack` / `John` reads `familiar-form` under the
    default) and an accepted weaker one is never hidden behind it
    (decisions/name-matching, 2026-11-08 FAMILIAR FORMS). `outcomes`
    run strongest first and end in `conflict`, never accepted."""
    holding = iter(outcomes)
    strongest = next(holding)
    if strongest in accept:
        return strongest
    return next((o for o in holding if o in accept), strongest)


def _text_outcome(a: str, b: str, lexicon: Lexicon, group: str,
                  accept: frozenset[Outcome],
                  bases: tuple[str, str] | None = None) -> Outcome:
    """Two non-empty texts of one role, by `_pick` over the outcomes
    that hold (`_text_outcomes`)."""
    return _pick(_text_outcomes(a, b, lexicon, group, bases), accept)


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


def _middle_outcome(a: str, b: str, lexicon: Lexicon,
                    accept: frozenset[Outcome], group: str) -> Outcome:
    """The middle role word by word, in order: each aligned pair by
    `_text_outcome` in `group`, each word past the shorter side
    one-sided, the role taking the weakest; `same` where both are
    empty."""
    wa, wb = a.split(), b.split()
    if not wa and not wb:
        return Outcome.SAME
    outcomes = [_text_outcome(x, y, lexicon, group, accept)
                for x, y in zip(wa, wb)]
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
                    lexicon: Lexicon, group: str) -> Outcome:
    """A different generation conflicts and one on one side only is its
    own outcome, whatever credentials either side carries; where the
    generations agree, the rest of the suffix (credentials, honorifics)
    is noted."""
    if left.suffix == right.suffix:
        return Outcome.SAME
    ga, gb = left.generation, right.generation
    if ga and gb:
        full = _full_outcome(ga, gb, _fold(ga), _fold(gb), lexicon, group)
        if full is None:
            return Outcome.CONFLICT
        generation = full
    elif ga or gb:
        return Outcome.GENERATION_ONE_SIDE
    else:
        generation = Outcome.SAME
    rest = _noted(" ".join(filter(None, (left.credentials, left.honorifics))),
                  " ".join(filter(None, (right.credentials, right.honorifics))),
                  lexicon, group)
    return _weakest((generation, rest))


#: A role's comparator: its two texts, the two names they come from, the
#: lexicon, the accepted outcomes and the role's own rule.
_Compare = Callable[
    [str, str, ParsedName, ParsedName, "Lexicon", frozenset[Outcome], "_RoleRule"],
    Outcome]


@dataclass(frozen=True, slots=True)
class _RoleRule:
    """How one role compares: every role-specific decision of the check
    and the keys in one row (#1260).

    - `group`: the `same_as` group its listed spellings are read in, the
      readings of the kind that stands there (`Lexicon._headwords`), so
      a given name's spelling never matches a surname (`Ma.` / `María`
      agree as given names; the surname Ma never matches María).
    - `both_empty` and `one_side`: the outcome where neither side holds
      the role, and where one side alone does; the family role's are
      both `conflict`, a family name being the minimum evidence.
    - `compare`: the comparator where both sides hold it.
    - `whole`: the comparator reads the two names whole, empty sides
      included (the suffix, which compares generations), so its
      `both_empty` and `one_side` are never read.
    - `base`: the text the family leniencies compare beside the role's
      own (`particles-aside`, `part-of-other`), `None` where the role
      has none.
    - `across`: the roles of the other name a cross-role match tries it
      against (`across-roles`), empty where it is never tried.
    - `tried_into`: whether another reading may move words into it; a
      title never conflicts and a suffix only on its generation, so a
      word moved there could only empty a role that does."""

    group: str
    both_empty: Outcome
    one_side: Outcome
    compare: _Compare
    whole: bool = False
    base: Callable[[ParsedName], str] | None = None
    across: tuple[Role, ...] = ()
    tried_into: bool = True

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate


def _compare_text(a: str, b: str, left: ParsedName, right: ParsedName,
                  lexicon: Lexicon, accept: frozenset[Outcome],
                  rule: _RoleRule) -> Outcome:
    """Two non-empty texts by `_text_outcome`, with the role's bases
    where it has them."""
    bases = (None if rule.base is None
             else (rule.base(left), rule.base(right)))
    return _text_outcome(a, b, lexicon, rule.group, accept, bases)


def _compare_middle(a: str, b: str, left: ParsedName, right: ParsedName,
                    lexicon: Lexicon, accept: frozenset[Outcome],
                    rule: _RoleRule) -> Outcome:
    return _middle_outcome(a, b, lexicon, accept, rule.group)


def _compare_noted(a: str, b: str, left: ParsedName, right: ParsedName,
                   lexicon: Lexicon, accept: frozenset[Outcome],
                   rule: _RoleRule) -> Outcome:
    return _noted(a, b, lexicon, rule.group)


def _compare_suffix(a: str, b: str, left: ParsedName, right: ParsedName,
                    lexicon: Lexicon, accept: frozenset[Outcome],
                    rule: _RoleRule) -> Outcome:
    return _suffix_outcome(left, right, lexicon, rule.group)


def _family_base(name: ParsedName) -> str:
    return name.family_base


#: Each role's rule (`_RoleRule`), one row per `Role`.
_RULES: Mapping[Role, _RoleRule] = {
    Role.TITLE: _RoleRule("title", Outcome.SAME, Outcome.NOTED,
                          _compare_noted, tried_into=False),
    Role.GIVEN: _RoleRule("given", Outcome.SAME, Outcome.GIVEN_ONE_SIDE,
                          _compare_text, across=(Role.MIDDLE, Role.NICKNAME)),
    Role.MIDDLE: _RoleRule("given", Outcome.SAME, Outcome.ONE_SIDE,
                           _compare_middle),
    Role.FAMILY: _RoleRule("family", Outcome.CONFLICT, Outcome.CONFLICT,
                           _compare_text, base=_family_base,
                           across=(Role.MAIDEN,)),
    Role.SUFFIX: _RoleRule("suffix", Outcome.SAME, Outcome.SAME,
                           _compare_suffix, whole=True, tried_into=False),
    Role.NICKNAME: _RoleRule("given", Outcome.SAME, Outcome.ONE_SIDE,
                             _compare_text),
    Role.MAIDEN: _RoleRule("family", Outcome.SAME, Outcome.ONE_SIDE,
                           _compare_text),
}


def _compare_role(role: Role, left: ParsedName, right: ParsedName,
                  lexicon: Lexicon, accept: frozenset[Outcome]) -> RoleMatch:
    """One role's row, by its `_RULES` row."""
    rule = _RULES[role]
    a, b = getattr(left, role), getattr(right, role)
    if rule.whole or (a and b):
        outcome = rule.compare(a, b, left, right, lexicon, accept, rule)
    elif a or b:
        outcome = rule.one_side
    else:
        outcome = rule.both_empty
    more = Side.NEITHER if outcome is Outcome.CONFLICT else _more(a, b)
    return RoleMatch(role, outcome, a, b, more)

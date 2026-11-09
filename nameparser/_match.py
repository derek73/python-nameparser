"""Name matching: the settings object, the result types and the check.

Not a stage: nothing here runs inside a parse. `Matching` carries a
`Parser` and the set of outcomes the caller accepts, and its `check`
compares two parsed names role by role.
Produces: `Outcome`, `Side`, `RoleMatch`, `CrossRoleMatch`, `MatchResult`,
`DEFAULT_ACCEPT` and `Matching`.
Reads: the `Parser`'s `Lexicon`, for the listed spellings (`same_as`)
through `Lexicon._headword`, and its `revise`, for a name's other
readings (`other-reading`); no `Policy` field.

Consistent means nothing in the two names contradicts it, under the
outcomes the caller accepts. The module imports `_types` and `_policy`
(for the scripts that write no initials), `Lexicon` and `Parser` for
typing alone.
"""
from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from nameparser._lexicon import _normalize
from nameparser._policy import _NO_INITIALS, _script_matcher
from nameparser._types import (
    UNJOINED_TAG,
    ParsedName,
    Role,
    _guarded_getstate,
    _guarded_setstate,
)

if TYPE_CHECKING:
    from nameparser._lexicon import Lexicon
    from nameparser._parser import Parser


class Outcome(StrEnum):
    """How one role of one name compares with the same role of another,
    strongest first. `conflict` is the one outcome that is never accepted."""

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
    FAMILY_INITIAL = "family-initial"
    GIVEN_ONE_SIDE = "given-one-side"
    HYPHENATED_PART = "hyphenated-part"
    OTHER_READING = "other-reading"
    ACROSS_ROLES = "across-roles"
    CONFLICT = "conflict"


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
    per `Role`, in `Role` order, and the `CrossRoleMatch` behind each
    role reading `across-roles`, in `Role` order of the role it
    resolved (empty unless `across-roles` is accepted)."""

    consistent: bool
    roles: tuple[RoleMatch, ...]
    across: tuple[CrossRoleMatch, ...] = ()

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def mirrored(self) -> MatchResult:
        """The same result with the two names swapped: each role's left
        and right text exchanged and its `more` side flipped, and each
        cross-role match's roles and texts exchanged."""
        return MatchResult(self.consistent,
                           tuple(m.mirrored() for m in self.roles),
                           tuple(c.mirrored() for c in self.across))


#: The outcomes accepted when a caller states none.
DEFAULT_ACCEPT: frozenset[Outcome] = frozenset({
    Outcome.SAME, Outcome.FOLDED, Outcome.LISTED_SPELLING,
    Outcome.PARTICLES_ASIDE, Outcome.PART_OF_OTHER, Outcome.INITIAL,
    Outcome.INITIALS_AGREE, Outcome.ONE_SIDE, Outcome.GENERATION_ONE_SIDE,
    Outcome.NOTED,
})

_VALID = ", ".join(o.value for o in Outcome if o is not Outcome.CONFLICT)


def _outcome(value: object) -> Outcome:
    if isinstance(value, Outcome):
        return value
    if isinstance(value, str):
        try:
            return Outcome(value)
        except ValueError:
            raise ValueError(
                f"unknown outcome {value!r}; valid outcomes: {_VALID}"
            ) from None
    raise TypeError(
        f"accept must be an iterable of outcome names or Outcome members, "
        f"got a member {value!r} of type {type(value).__name__}; pass "
        f"e.g. accept={{'initial', 'family-initial'}}")


@dataclass(frozen=True, slots=True)
class Matching:
    """The settings of a name match: the parser that reads the names and
    the outcomes accepted as consistent.

    `accept` takes any iterable of `Outcome` members or their names and is
    stored as a frozenset with `same` always present. Passing it replaces
    the default set rather than extending it, so extend the default
    matcher's set: `parser.matching(accept=parser.matching().accept |
    {"family-initial"})`. `conflict` cannot be accepted.
    """

    parser: Parser
    accept: frozenset[Outcome] = DEFAULT_ACCEPT

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
                f"{type(accept).__name__} {accept!r}; pass e.g. "
                f"accept={{'initial', 'family-initial'}}")
        outcomes = frozenset(_outcome(v) for v in accept)
        if Outcome.CONFLICT in outcomes:
            raise ValueError(
                f"'conflict' cannot be accepted: it is the outcome of a "
                f"contradiction; drop it from accept (valid outcomes: "
                f"{_VALID})")
        object.__setattr__(self, "accept", outcomes | {Outcome.SAME})

    def __repr__(self) -> str:
        added = sorted(o.value for o in self.accept - DEFAULT_ACCEPT)
        removed = sorted(o.value for o in DEFAULT_ACCEPT - self.accept)
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

        Where `other-reading` is accepted and the names as parsed are
        not consistent, each side's other readings are tried too: one
        per `Ambiguity` with an `alternative`, its words moved to the
        alternative's role, one ambiguity at a time and never two
        together, save an alternative into the title or suffix, roles
        that never conflict, which could only empty a role that does. The table reported
        is the one with the strongest outcomes, every role the
        alternative moved a word into or out of that would otherwise be
        accepted reading `other-reading`, so the pair is consistent
        through it only where `other-reading` is accepted.

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
        best = self._result(left, right, frozenset())
        if best.consistent or Outcome.OTHER_READING not in self.accept:
            return best
        readings_a, readings_b = self._readings(left), self._readings(right)
        if len(readings_a) == len(readings_b) == 1:
            return best
        candidates = [
            (self._result(ra, rb, ta | tb), int(bool(ta)) + int(bool(tb)))
            for ra, ta in readings_a for rb, tb in readings_b
        ]
        return min(candidates, key=_strength)[0]

    def keys(self, name: str | ParsedName) -> frozenset[str]:
        """Grouping keys: for each word of the folded family base, and
        each half of a hyphenated one beside its joined form, a half that
        is a listed particle left out (`Al-Saud` keys `saud` and
        `alsaud`, never `al`), one key
        `word;g` where `g` is the first letter of the given name (empty
        where there is none). A word is keyed by its headword, so two
        listed spellings of one surname share a key, each word under its
        headword folded and its folded form's headword, and a given name
        by the first letter of its text and of its headword. The
        guarantee rests on this: every family-base word the default check
        compares is keyed, under both headword orders, so two names it
        finds consistent share a key and grouping by key loses no match.
        A name with no family has no key.

        Each accepted opt-in adds the keys its outcome needs:
        `family-initial` a key `f;g` for the first letter `f` of the
        family's first word, `given-one-side` a bare key for every
        family part keyed, `other-reading` the keys of each other
        reading `check` tries, and `across-roles` the maiden name's
        words without particles as family words, and the first letter
        of each middle word and of the nickname's first word, save one
        written as an initial, as given letters."""
        parsed = self._parsed(name)
        if Outcome.OTHER_READING not in self.accept:
            return self._keys(parsed)
        return frozenset().union(
            *(self._keys(reading) for reading, _ in self._readings(parsed)))

    def _result(self, left: ParsedName, right: ParsedName,
                moved: frozenset[Role]) -> MatchResult:
        """The table of two readings; each role in `moved`, which an
        alternative reading moved a word into or out of, reads
        `other-reading` where its own outcome is accepted."""
        lexicon = self.parser.lexicon
        roles = [_compare_role(role, left, right, lexicon) for role in Role]
        roles = [
            dataclasses.replace(r, outcome=Outcome.OTHER_READING)
            if r.role in moved and r.outcome in self.accept else r
            for r in roles]
        across: list[CrossRoleMatch] = []
        if Outcome.ACROSS_ROLES in self.accept:
            middles = [left.middle.split(), right.middle.split()]
            for i, r in enumerate(roles):
                if r.outcome in self.accept or r.role not in _ACROSS:
                    continue
                found = self._across(r.role, left, right)
                if found is None:
                    continue
                cross, side, index = found
                # the side carrying more is the one whose name held both
                # the role and the cross role the match used
                holder = Side.RIGHT if cross.left_role is r.role else Side.LEFT
                held = r.left if holder is Side.LEFT else r.right
                roles[i] = dataclasses.replace(
                    r, outcome=Outcome.ACROSS_ROLES,
                    more=holder if held else Side.NEITHER)
                across.append(cross)
                if side is not None:
                    # the middle word matched as the given name is
                    # consumed, and the words left compare role to role
                    del middles[side][index]
                    at = list(Role).index(Role.MIDDLE)
                    roles[at] = self._middle_left_over(
                        roles[at], middles[0], middles[1], Role.MIDDLE in moved)
        return MatchResult(all(r.outcome in self.accept for r in roles),
                           tuple(roles), tuple(across))

    def _middle_left_over(self, row: RoleMatch, a: list[str], b: list[str],
                          moved: bool) -> RoleMatch:
        """The middle row once a middle word matched across roles is
        taken out: the words left compared role to role, the row
        keeping both sides' text as parsed."""
        la, lb = " ".join(a), " ".join(b)
        outcome = (_middle_outcome(la, lb, self.parser.lexicon)
                   if la or lb else Outcome.SAME)
        if moved and outcome in self.accept:
            outcome = Outcome.OTHER_READING
        more = Side.NEITHER if outcome is Outcome.CONFLICT else _more(la, lb)
        return dataclasses.replace(row, outcome=outcome, more=more)

    def _across(self, role: Role, left: ParsedName, right: ParsedName,
                ) -> tuple[CrossRoleMatch, int | None, int] | None:
        """The strongest match of `role` on one side against one of its
        cross roles (`_ACROSS`) on the other, or `None`, with the side
        (0 left, 1 right; `None` for a role other than the middle) and
        the index of the middle word it used: a middle name word by
        word, the other roles whole. Only a full name on both sides
        counts, at `_ACROSS_OUTCOMES`, never an initial. The pick is by
        outcome, then by texts and roles named without a side, so it is
        the same with the names swapped."""
        lexicon = self.parser.lexicon
        found: list[tuple[tuple[object, ...],
                          tuple[CrossRoleMatch, int | None, int]]] = []
        for other in _ACROSS[role]:
            for lrole, rrole in ((other, role), (role, other)):
                for li, la in enumerate(_cross_texts(left, lrole)):
                    for ri, ra in enumerate(_cross_texts(right, rrole)):
                        outcome = _text_outcome(la, ra, lexicon)
                        if (outcome not in _ACROSS_OUTCOMES
                                or outcome not in self.accept
                                or _initials_only(la) or _initials_only(ra)):
                            continue
                        theirs, mine = (la, ra) if lrole is other else (ra, la)
                        side = (None if other is not Role.MIDDLE
                                else 0 if lrole is other else 1)
                        found.append((
                            (_RANK[outcome], _RANK_ROLE[other], theirs, mine),
                            (CrossRoleMatch(lrole, rrole, outcome, la, ra),
                             side, li if side == 0 else ri)))
        return min(found, key=lambda f: f[0])[1] if found else None

    def _readings(self, name: ParsedName
                  ) -> list[tuple[ParsedName, frozenset[Role]]]:
        """The name as parsed, with no role moved, then one other
        reading per ambiguity whose `alternative` moves a word into a
        role that can conflict (not the title or suffix): that
        ambiguity's words moved to the alternative's role by
        `Parser.revise`, with the roles it changed."""
        readings: list[tuple[ParsedName, frozenset[Role]]] = [(name, frozenset())]
        for ambiguity in name.ambiguities:
            if ambiguity.alternative is None:
                continue
            target = ambiguity.alternative.role
            if target in _NEVER_CONFLICT:
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
                name, **{r.value: getattr(laid_out, r) for r in moved}), moved))
        return readings

    def _keys(self, parsed: ParsedName) -> frozenset[str]:
        lexicon = self.parser.lexicon

        def heads(word: str) -> set[str]:
            return {lexicon._headword(_fold(word)), _fold(lexicon._headword(word))}

        across = Outcome.ACROSS_ROLES in self.accept
        bases = parsed.family_base.split()
        if across:
            bases += _maiden_base(parsed).split()
        words: set[str] = set()
        for raw in bases:
            folded = _fold(raw)
            # the halves the check's part-of-other drops, by position, so
            # the raw and the folded word drop the same ones
            drop = {i for i, h in enumerate(folded.split("-"))
                    if "-" in folded and _particle_half(h, lexicon)}
            for word in (raw, folded):
                halves = [h for i, h in enumerate(word.split("-"))
                          if i not in drop]
                for form in (*halves, word.replace("-", "")):
                    if form:
                        words |= heads(form)
        family = parsed.family.split()
        if family and words and Outcome.FAMILY_INITIAL in self.accept:
            words |= {f[:1] for f in heads(family[0]) | {_fold(family[0])}} - {""}

        def initials_of(word: str) -> set[str]:
            return {g[:1] for g in heads(word) | {_fold(word)}}

        given = parsed.given.split()
        initials = initials_of(given[0]) if given else {""}
        if across:
            # a cross-role match is never made by an initial
            for word in (*parsed.middle.split(), *parsed.nickname.split()[:1]):
                if not _is_initial(_fold(word)):
                    initials |= initials_of(word)
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

_DROPPED = str.maketrans("", "", ".'")
_WORDS = re.compile(r"[\s-]+")
#: rules/R7's scripts that write no initials (_policy._NO_INITIALS): a
#: single character in one of them is a whole word, never an initial.
_initialless = _script_matcher(*_NO_INITIALS, whole=True)
_RANK = {o: i for i, o in enumerate(Outcome)}
#: The roles whose outcome is never a conflict; an alternative reading
#: moving a word into one of them is not tried.
_NEVER_CONFLICT = frozenset({Role.TITLE, Role.SUFFIX})
#: The roles a cross-role match may resolve, each with the roles of the
#: other name it is tried against (`across-roles`).
_ACROSS: Mapping[Role, tuple[Role, ...]] = {
    Role.GIVEN: (Role.MIDDLE, Role.NICKNAME),
    Role.FAMILY: (Role.MAIDEN,),
}
_RANK_ROLE = {r: i for i, r in enumerate(Role)}
#: The outcomes a cross-role match counts at: a full name on both sides,
#: never an initial or an opt-in outcome.
_ACROSS_OUTCOMES = frozenset({Outcome.SAME, Outcome.FOLDED,
                              Outcome.LISTED_SPELLING})


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


_ACCENTED_SCRIPTS = ("LATIN ", "GREEK ", "CYRILLIC ")


def _fold(text: str) -> str:
    """The text with case, accents, full stops and apostrophes folded
    away: NFC then NFD, casefolded, `.` and `'` removed. Hyphens and
    spaces are kept. A combining mark (Mn) is dropped only where the
    letter it attaches to is Latin, Greek or Cyrillic, where it is an
    accent; in another script (a Devanagari virama, anusvara or vowel
    sign) it is spelling and is kept."""
    decomposed = unicodedata.normalize(
        "NFD", unicodedata.normalize("NFC", text))
    kept = []
    accented = False
    for c in decomposed:
        if unicodedata.category(c) == "Mn":
            if accented:
                continue
        else:
            accented = unicodedata.name(c, "").startswith(_ACCENTED_SCRIPTS)
        kept.append(c)
    return "".join(kept).casefold().translate(_DROPPED)


def _strength(candidate: tuple[MatchResult, int]) -> tuple[object, ...]:
    """The order `check` picks a table by, best first: consistent, then
    the weakest outcome strongest (then the next weakest, and so on),
    then fewer sides read another way, then each role's text pair and
    each cross-role match's, which keeps the pick the same with the
    names swapped."""
    result, sides = candidate
    ranks = sorted((_RANK[r.outcome] for r in result.roles), reverse=True)
    texts = tuple(tuple(sorted((r.left, r.right))) for r in result.roles)
    across = tuple(sorted(((c.left, c.left_role), (c.right, c.right_role)))
                   for c in result.across)
    return (not result.consistent, ranks, sides, texts, across)


def _weakest(outcomes: Iterable[Outcome]) -> Outcome:
    return max(outcomes, key=_RANK.__getitem__)


def _letters(text: str) -> int:
    return sum(c.isalnum() for c in _fold(text))


def _more(left: str, right: str) -> Side:
    a, b = _letters(left), _letters(right)
    return Side.LEFT if a > b else Side.RIGHT if b > a else Side.NEITHER


def _is_initial(folded: str) -> bool:
    return len(folded) == 1 and folded.isalpha() and not _initialless(folded)


def _part_agrees(a: str, b: str, lexicon: Lexicon) -> Outcome | None:
    """One word against one word: `same` where they are equal once
    folded or listed as one spelling, `initial` where one is an initial
    of the other's first letter, else `None`. A hyphenated word is compared part by part against the
    other's hyphen-split parts (`J.-P.` / `Jean-Pierre`)."""
    fa, fb = _fold(a), _fold(b)
    if fa == fb or lexicon._headword(a) == lexicon._headword(b):
        return Outcome.SAME
    if (_is_initial(fa) and fb[:1] == fa) or (_is_initial(fb) and fa[:1] == fb):
        return Outcome.INITIAL
    pa, pb = a.split("-"), b.split("-")
    if len(pa) > 1 and len(pa) == len(pb):
        parts = [_part_agrees(x, y, lexicon) for x, y in zip(pa, pb)]
        if None not in parts:
            return _weakest(p for p in parts if p is not None)
    return None


def _initials_only(text: str) -> bool:
    return all(_is_initial(w) for w in _WORDS.split(_fold(text)) if w)


def _text_outcome(a: str, b: str, lexicon: Lexicon, *, family: bool = False,
                  bases: tuple[str, str] = ("", "")) -> Outcome:
    """Two non-empty texts of one role, by the strongest outcome that
    holds: same, folded, listed spelling, then for a family particles
    set aside and part of the other, then initial against name (family
    initial in the family role), then initials agree, else conflict."""
    if a == b:
        return Outcome.SAME
    if _fold(a) == _fold(b):
        return Outcome.FOLDED
    wa, wb = a.split(), b.split()
    if len(wa) == len(wb) and all(
            lexicon._headword(x) == lexicon._headword(y) for x, y in zip(wa, wb)):
        return Outcome.LISTED_SPELLING
    if family:
        if bases[0] and _fold(bases[0]) == _fold(bases[1]):
            return Outcome.PARTICLES_ASIDE
        sa, sb = _base_words(bases[0], lexicon), _base_words(bases[1], lexicon)
        if sa and sb and (sa <= sb or sb <= sa):
            return Outcome.PART_OF_OTHER
    if len(wa) == len(wb):
        parts = [_part_agrees(x, y, lexicon) for x, y in zip(wa, wb)]
        if None not in parts and Outcome.INITIAL in parts:
            return Outcome.FAMILY_INITIAL if family else Outcome.INITIAL
    if _initials_only(a) and _initials_only(b) and (
            _WORDS.split(_fold(a)) == _WORDS.split(_fold(b))):
        return Outcome.INITIALS_AGREE
    if not family and len(wa) == len(wb) == 1 and (
            _first_half(a, b) or _first_half(b, a)):
        return Outcome.HYPHENATED_PART
    return Outcome.CONFLICT


def _particle_half(folded: str, lexicon: Lexicon) -> bool:
    """A folded half of a hyphenated family word that is a listed
    particle (`al` in `Al-Saud`): set aside like a spaced particle, so it
    is neither a family-base word for `part-of-other` nor a key."""
    return _normalize(folded) in lexicon._sets.particles


def _base_words(base: str, lexicon: Lexicon) -> set[str]:
    """The folded family-base words `part-of-other` compares: each
    word, and a hyphenated one as its halves less any listed particle."""
    words: set[str] = set()
    for word in _fold(base).split():
        halves = word.split("-")
        if len(halves) > 1:
            words.update(h for h in halves if not _particle_half(h, lexicon))
        else:
            words.add(word)
    return words - {""}


def _first_half(word: str, hyphenated: str) -> bool:
    """`word` is the first half of `hyphenated` once folded (`Hong` /
    `Hong-Yi`): the first half only, which shares the given initial a
    key is cut on."""
    w, parts = _fold(word), _fold(hyphenated).split("-")
    return len(parts) > 1 and "-" not in w and bool(w) and parts[0] == w


def _middle_outcome(a: str, b: str, lexicon: Lexicon) -> Outcome:
    """The middle role word by word, in order: each aligned pair by
    `_text_outcome`, each word past the shorter side one-sided, the role
    taking the weakest."""
    wa, wb = a.split(), b.split()
    outcomes = [_text_outcome(x, y, lexicon) for x, y in zip(wa, wb)]
    if len(wa) != len(wb):
        outcomes.append(Outcome.ONE_SIDE)
    return _weakest(outcomes)


def _noted(a: str, b: str, lexicon: Lexicon) -> Outcome:
    """A role that never conflicts: equal by any spelling, else noted."""
    if not a and not b:
        return Outcome.SAME
    if a and b:
        outcome = _text_outcome(a, b, lexicon)
        if outcome in (Outcome.SAME, Outcome.FOLDED, Outcome.LISTED_SPELLING):
            return outcome
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
        generation = _noted(ga, gb, lexicon)
        if generation is Outcome.NOTED:
            return Outcome.CONFLICT
    elif ga or gb:
        return Outcome.GENERATION_ONE_SIDE
    else:
        generation = Outcome.SAME
    rest = _noted(" ".join(filter(None, (left.credentials, left.honorifics))),
                  " ".join(filter(None, (right.credentials, right.honorifics))),
                  lexicon)
    return _weakest((generation, rest))


def _compare_role(role: Role, left: ParsedName, right: ParsedName,
                  lexicon: Lexicon) -> RoleMatch:
    a, b = getattr(left, role), getattr(right, role)
    if role is Role.SUFFIX:
        outcome = _suffix_outcome(left, right, lexicon)
    elif role is Role.TITLE:
        outcome = _noted(a, b, lexicon)
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
            a, b, lexicon, family=role is Role.FAMILY,
            bases=(left.family_base, right.family_base))
    more = Side.NEITHER if outcome is Outcome.CONFLICT else _more(a, b)
    return RoleMatch(role, outcome, a, b, more)

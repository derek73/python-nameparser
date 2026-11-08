"""Name matching: the settings object, the result types and the check.

Not a stage: nothing here runs inside a parse. `Matching` carries a
`Parser` and the set of outcomes the caller accepts, and its `check`
compares two parsed names role by role.
Produces: `Outcome`, `Side`, `RoleMatch`, `MatchResult`, `DEFAULT_ACCEPT`
and `Matching`.
Reads: the `Parser`'s `Lexicon`, for the listed spellings (`same_as`)
through `Lexicon._headword`; no `Policy` field.

Consistent means nothing in the two names contradicts it, under the
outcomes the caller accepts. The module imports `_types` and `_policy`
(for the scripts that write no initials), `Lexicon` and `Parser` for
typing alone.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from nameparser._policy import _NO_INITIALS, _script_matcher
from nameparser._types import (
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
    side carried more."""

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
class MatchResult:
    """The result of comparing two names: whether nothing in them
    contradicts the match under the accepted outcomes, and one
    `RoleMatch` per `Role`, in `Role` order."""

    consistent: bool
    roles: tuple[RoleMatch, ...]

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def mirrored(self) -> MatchResult:
        """The same result with the two names swapped: each role's left
        and right text exchanged and its `more` side flipped."""
        return MatchResult(self.consistent,
                           tuple(m.mirrored() for m in self.roles))


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
    the default set rather than extending it, so extend with
    `DEFAULT_ACCEPT | {"family-initial"}`. `conflict` cannot be accepted.
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
        with each other."""
        left, right = self._parsed(a), self._parsed(b)
        lexicon = self.parser.lexicon
        roles = tuple(_compare_role(role, left, right, lexicon) for role in Role)
        return MatchResult(all(r.outcome in self.accept for r in roles), roles)

    def keys(self, name: str | ParsedName) -> frozenset[str]:
        """Grouping keys: for each word of the folded family base, and
        each half of a hyphenated one beside its joined form, one key
        `word;g` where `g` is the first letter of the given name (empty
        where there is none). A word is keyed by its headword, so two
        listed spellings of one surname share a key, and a given name by
        the first letter of its text and of its headword. Under the
        default settings two names `check` finds consistent always share
        a key, so grouping by key and checking within each group loses no
        match. A name with no family has no key."""
        parsed = self._parsed(name)
        lexicon = self.parser.lexicon
        words: set[str] = set()
        for word in _fold(parsed.family_base).split():
            for form in (*word.split("-"), word.replace("-", "")):
                if form:
                    words.add(lexicon._headword(form))
        given = _fold(parsed.given).split()
        initials = {""}
        if given:
            initials = {given[0][:1], lexicon._headword(given[0])[:1]}
        return frozenset(f"{w};{g}" for w in words for g in initials)

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
        sa = set(_WORDS.split(_fold(a))) - {""}
        sb = set(_WORDS.split(_fold(b))) - {""}
        if sa <= sb or sb <= sa:
            return Outcome.PART_OF_OTHER
    if len(wa) == len(wb):
        parts = [_part_agrees(x, y, lexicon) for x, y in zip(wa, wb)]
        if None not in parts and Outcome.INITIAL in parts:
            return Outcome.FAMILY_INITIAL if family else Outcome.INITIAL
    if _initials_only(a) and _initials_only(b) and (
            _WORDS.split(_fold(a)) == _WORDS.split(_fold(b))):
        return Outcome.INITIALS_AGREE
    return Outcome.CONFLICT


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
    own outcome; the rest of the suffix (credentials, honorifics) is
    noted."""
    if left.suffix == right.suffix:
        return Outcome.SAME
    ga, gb = left.generation, right.generation
    if ga and gb:
        generation = _noted(ga, gb, lexicon)
        if generation is Outcome.NOTED:
            return Outcome.CONFLICT
    elif ga or gb:
        generation = Outcome.GENERATION_ONE_SIDE
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

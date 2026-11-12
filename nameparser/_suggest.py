"""The group suggester: given names a caller declares to be one group,
it suggests ``Policy`` settings, chiefly the name order (``Parser.suggest``).

Contracts are stated in prose here, with no doctest blocks. This module
holds the shared spelling fold so the name tables
(``config/_order_names.py``, written by ``tools/vocab/order_names.py``)
and the reader that looks words up in them fold alike, and the per-name
signals: ``name_votes`` reads one name and returns the votes it casts,
a dict from ``Signal`` to either an order (``GIVEN_FIRST`` or
``FAMILY_FIRST``) or, for ``Signal.PATRONYMIC``, the ``PatronymicRule``
its shape matches. A name is read past its titles at the head and its
post-nominals at the end, by the base lexicon, with quotes and brackets
around a word read past too; a name with a comma is read before the
comma where only post-nominals follow it, and casts nothing otherwise.
A signal that does not apply casts no vote, so the dict is empty for a
name of fewer than two words once those are read past. The signals read
cased evidence in any script: a word with no cased letter never counts
as capitals (Cyrillic capitals vote, as Latin ones do), a one-letter
word is never looked up in the name tables, a capitals word of two or
three letters ending a name that holds a lowercase letter (joined
initials, `Armitage JO`, or a short surname, `Jason NG`) casts no
capitals vote and is not looked up as a surname, and a script the
tables do not hold (Hangul, Han) simply matches nothing. A patronymic
votes, Latin or Cyrillic, only where the pipeline's rule reads one
(rules/O1's three name words, rules/O2's four), through the pipeline's
own predicates, never a copy of them. No signal raises on any string.

``suggest`` tallies the group's votes and decides two settings
together, ``patronymic_rules`` first and ``name_order`` second: a
decided East Slavic rule reorders each name itself and stands down
under a family-first order, so it decides the order as given-first,
unless the names' own votes decide family-first, which it never
overrides (decisions/group-suggestion). Before either it decides
``initials_as_family`` (rules/O8) from the runs of letters ending the
group's names, a group property with no per-name vote, and a group
decided so casts no trailing-initial vote on its order. A setting is
decided only on the evidence the thresholds below admit; any other
setting keeps the base's value, so an empty group, or one with no
votes, gives back a parser that reads exactly as the base does. The
result is a ``Suggestion``: the ``PolicyPatch`` holding only the
settings the group changed, a ``SettingEvidence`` per setting
considered, and a ``NameEvidence`` per input name, in input order.
"""
from __future__ import annotations

import dataclasses
import re
import reprlib
import unicodedata
import warnings
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from ._lexicon import Lexicon, _normalize
from ._pipeline._state import COMMA_CHARS
from ._pipeline._vocab import (
    ROMAN, east_slavic_rotates, has_patronymic_ending, is_initial,
    is_one_case, is_patronymic_marker, is_suffix_lenient, is_title_shaped,
    reads_as_generation, suffix_as_written,
)
from ._policy import (
    UNSET, PatronymicRule, Policy, PolicyPatch, _order_repr, apply_patch,
    initials_as_family_may_move,
)
from ._types import (
    FAMILY_FIRST, GIVEN_FIRST, Role, _guarded_getstate, _guarded_setstate,
)
from .config._order_names import COMMON_GIVEN_NAMES, ROMANIZED_SURNAMES

if TYPE_CHECKING:
    from ._parser import Parser

# the letters NFKD leaves whole, spelled as an ASCII keyboard writes
# them
_KEYBOARD = str.maketrans({
    "ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "ı": "i", "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE", "ß": "ss", "ẞ": "SS", "đ": "d", "Đ": "D"})
# a letter u with a diaeresis, decomposed: the pinyin vowel written v on
# a keyboard (lü -> lv)
_U_DIAERESIS = {"u\u0308": "v", "U\u0308": "V"}


def fold(word: str) -> str:
    """The spelling a word is looked up under in the name tables: lower
    case, every diacritic dropped, the letters NFKD leaves whole written
    as an ASCII keyboard writes them (``ł`` as ``l``, ``ø`` as ``o``,
    ``ı`` as ``i``, ``æ`` as ``ae``, ``œ`` as ``oe``, ``ß`` as ``ss``,
    ``đ`` as ``d``) and ``ü`` as ``v``.

    ``Nguyễn`` folds to ``nguyen``, ``Đặng`` to ``dang``, ``Łukasz`` to
    ``lukasz``, ``Barış`` to ``baris`` and ``Lǚ`` to ``lv``. The tables
    hold only folded spellings, written with this function, so a reader
    folds the word first.
    """
    text = unicodedata.normalize("NFKD", word).translate(_KEYBOARD)
    for mark, letter in _U_DIAERESIS.items():
        text = text.replace(mark, letter)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


class Signal(StrEnum):
    """The evidence a single name offers about its writer's name order."""

    CAPITALS = "capitals"
    TRAILING_INITIAL = "trailing-initial"
    PARTICLE = "particle"
    SURNAME = "surname"
    GIVEN_NAME = "given-name"
    PATRONYMIC = "patronymic"


_INITIAL_JOINS = re.compile(r"[.-]+")


def _is_initialed(word: str) -> bool:
    """An initial: one letter with an optional period, or single letters
    joined by periods or hyphens (`J.P.`, `J.-P.`, `J-P`)."""
    if is_initial(word):
        return True
    if "." not in word and "-" not in word:
        return False
    chunks = _INITIAL_JOINS.split(word.rstrip("."))
    return all(chunk and is_initial(chunk + ".") for chunk in chunks)


def _is_caps_word(word: str) -> bool:
    """Two or more letters, all of them capitals, and no initial."""
    letters = [c for c in word if c.isalpha()]
    # single letters joined by stops or hyphens ('J.-P.', 'J-P') are
    # initials, however many letters they hold
    chunks = [c for c in word.replace(".", "-").split("-") if c]
    paired_initials = len(chunks) > 1 and all(len(c) == 1 for c in chunks)
    return (len(letters) >= 2 and word.isupper()
            and not paired_initials and not _is_initialed(word))


def _has_lower(words: list[str]) -> bool:
    return any(c.islower() for w in words for c in w)


def _ends_in_short_capitals(words: list[str]) -> bool:
    """Whether a name holding a lowercase letter ends in a capitals word
    of two or three letters: joined initials (`Armitage JO`, `Smith JP`)
    or a short surname (`Jason NG`), which the word alone cannot tell
    apart. Such a word casts no capitals vote and is not looked up as a
    surname; a leading one (`NG Jason`) still votes."""
    last = words[-1]
    letters = sum(c.isalpha() for c in last)
    return (2 <= letters <= 3 and _is_caps_word(last)
            and _has_lower(words))


def _capitals(words: list[str]) -> tuple[Role, Role, Role] | None:
    """A run of capitals words at one end of a name that also holds a
    lowercase letter reads as the family name, which writers set in
    capitals."""
    if not _has_lower(words) or _ends_in_short_capitals(words):
        return None
    # a name holding a lowercase letter holds a word that is not all
    # capitals, so the two ends never both vote by being every word
    caps = [_is_caps_word(w) for w in words]
    if caps[0] and not caps[-1]:
        return FAMILY_FIRST
    if caps[-1] and not caps[0]:
        return GIVEN_FIRST
    return None


def _particle(words: list[str], lexicon: Lexicon) -> tuple[Role, Role, Role] | None:
    if len(words) < 3:
        return None
    particles = lexicon._sets.particles

    def is_particle(word: str) -> bool:
        return word == word.lower() and _normalize(word) in particles

    first = is_particle(words[0])
    before_last = is_particle(words[-2])
    if first == before_last:
        return None
    return FAMILY_FIRST if first else GIVEN_FIRST


def _listed(word: str, table: frozenset[str]) -> bool:
    spelling = fold(word.strip("."))
    return len(spelling) >= 2 and spelling in table


def _at_one_end(words: list[str], table: frozenset[str],
                skip_last: bool = False) -> tuple[bool, bool]:
    return _listed(words[0], table), not skip_last and _listed(words[-1], table)


def _a_listed_name(word: str) -> bool:
    """A word the name tables list: name evidence, which is never read
    past as a title or a post-nominal (`Law`, a Cantonese surname and a
    listed title; `Cem`, a Turkish given name and a listed credential)."""
    return (_listed(word, ROMANIZED_SURNAMES)
            or _listed(word, COMMON_GIVEN_NAMES))


def _is_leading_title(word: str, lexicon: Lexicon) -> bool:
    """A word the lexicon lists as a title, or one rules/H2's shape
    reads as a title at the head of a name (`Prof.`, `Insp.`)."""
    return not _a_listed_name(word) and (
        _normalize(word) in lexicon._sets.titles
        or is_title_shaped(word, lexicon))


def _is_post_nominal(word: str, lexicon: Lexicon) -> bool:
    """A word after a comma that is a suffix the lexicon lists, or a
    numeral of two letters or more: is_suffix_lenient, the reading
    after a comma, which takes a listed one-letter numeral too."""
    stem = word.rstrip(".")
    return not _a_listed_name(word) and (
        is_suffix_lenient(word, lexicon)
        or (len(stem) > 1 and ROMAN.match(stem) is not None))


def _ends_in_post_nominal(words: list[str], lexicon: Lexicon,
                          one_case: bool) -> bool:
    """Whether the last of `words` is a suffix the lexicon lists or a
    numeral the trailing fork reads as the generation. A one-letter
    numeral, and a listed acronym written as initials (`J.P.`), need two
    name words in front of them, as the trailing fork's words-to-spare
    count asks (rules/S10, rules/S3): `Armitage V` and `Smith J.P.` end
    in initials."""
    word = words[-1]
    if len(words) < 2 or _a_listed_name(word):
        return False
    stem = word.rstrip(".")
    if len(words) < 3 and (len(stem) == 1 or _is_initialed(word)):
        return False
    listed = suffix_as_written(_normalize(word), word, lexicon)
    if stem and ROMAN.match(stem) is not None:
        return reads_as_generation(
            word, frozenset({"vocab:suffix"}) if listed else frozenset(),
            words[-2], one_case)
    return listed


#: The marks a word is written inside (quotes, brackets), stripped from
#: its ends before any test.
_EDGES = "\"'\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u00ab\u00bb\u2039\u203a()[]{}"
_COMMAS = re.compile("[" + re.escape("".join(sorted(COMMA_CHARS))) + r"\s]+")


def _name_words(text: str, lexicon: Lexicon) -> tuple[list[str], bool]:
    """The words the signals read, and whether a comma left the name
    out. A comma followed by post-nominals alone (`Zhang Wei, PhD`)
    leaves the part before it; any other comma name is left out, its
    comma stating its order. Quotes and brackets are stripped from each
    word, which is composed (NFC), then the titles at the head and the
    post-nominals at the end (a listed suffix, a numeral read as the
    generation)."""
    cut = next((i for i, c in enumerate(text) if c in COMMA_CHARS), None)
    if cut is not None:
        tail = [w.strip(_EDGES) for w in _COMMAS.split(text[cut + 1:])]
        if not all(_is_post_nominal(w, lexicon) for w in tail if w):
            return [], True
        text = text[:cut]
    # composed, so a letter written as base and mark (`oğlu` decomposed)
    # meets the patterns written composed
    words = [unicodedata.normalize("NFC", w)
             for w in (w.strip(_EDGES) for w in text.split()) if w]
    if not words:
        return words, False
    one_case = is_one_case(words)
    while words and _is_leading_title(words[0], lexicon):
        del words[0]
    while _ends_in_post_nominal(words, lexicon, one_case):
        del words[-1]
    return words, False


def _patronymic(words: list[str]) -> PatronymicRule | None:
    """The rule a name's patronymic votes for, where the pipeline's rule
    can read it there. rules/O2's four name words, the marker last
    (family-first) or third (given-first, which the Turkic rule reads
    too), never first or second; rules/O1's three name words, the
    ending on the middle word (given-first) or on the last
    (`east_slavic_rotates`, the family-first shape the rule restores),
    whatever the first word ends in (a surname may end like a
    patronymic: `Abramovich Roman Arkadyevich`), and no initial first or in the middle (O1's
    precedence). A final full stop is read past."""
    bare = [w.rstrip(".") or w for w in words]
    if (len(bare) == 4 and not any(map(is_patronymic_marker, bare[:2]))
            and (is_patronymic_marker(bare[2])
                 or is_patronymic_marker(bare[3]))):
        return PatronymicRule.TURKIC
    if (len(bare) == 3
            and not (_is_initialed(words[0]) or _is_initialed(words[1]))
            and (has_patronymic_ending(bare[1])
                 or east_slavic_rotates(bare[1], bare[2]))):
        return PatronymicRule.EAST_SLAVIC
    return None


def _letter_run(text: str, readers: tuple[Parser, Parser]) -> str | None:
    """The letters ending `text` that are evidence of the convention
    rules/O8 reads, folded and run together (`Lakshmi R. S.` gives
    ``rs``), or None. A spaced run counts where the rule reads it, asked
    of the parse itself with the switch on and off (the base's lexicon,
    the given-first order the rule reads under), so it counts exactly
    where the rule moves a name. A run written joined with full stops
    (`B.K.`, `K.C.`) ending the name's words after a name word counts
    too, though the rule never moves it: the parse makes it the family
    already (rules/T7), so it is the same convention, and the setting it
    suggests moves only the spaced runs beside it. Two or three bare
    capitals (`BK`) do not count: they are written as a short surname is
    (`Zhi LI`)."""
    # the cheap text test first: a name it refuses holds no run at all
    if not initials_as_family_may_move(text):
        return None
    on, off = readers
    family = on.parse(text).family
    if family != off.parse(text).family:
        return "".join(_normalize(word).replace(".", "")
                       for word in family.split())
    # a comma name gives no words (_name_words), so it holds no run
    words = _name_words(text, readers[0].lexicon)[0]
    if len(words) < 2 or _is_initialed(words[0]):
        return None
    last = words[-1]
    # joined with full stops alone: a hyphen joins the halves of one
    # given name (`J.-P.`, `J-H`), which is no family
    if not ("." in last.rstrip(".") and "-" not in last
            and _is_initialed(last)):
        return None
    letters = [ch for ch in last if ch.isalpha()]
    # only where the parse makes the word the whole family: an unlisted
    # dotted credential (`John Smith X.Y.Z.`, rules/S3) is a suffix
    if len(letters) < 2 or _normalize(
            readers[1].parse(text).family) != _normalize(last):
        return None
    return "".join(letters).lower()


def _read(text: str, lexicon: Lexicon
          ) -> tuple[dict[Signal, tuple[Role, Role, Role] | PatronymicRule], bool]:
    """The votes one name casts, and whether a comma left it out."""
    words, comma = _name_words(text, lexicon)
    if len(words) < 2:
        return {}, comma
    votes: dict[Signal, tuple[Role, Role, Role] | PatronymicRule] = {}

    capitals = _capitals(words)
    if capitals is not None:
        votes[Signal.CAPITALS] = capitals

    if _is_initialed(words[-1]) and not _is_initialed(words[0]):
        votes[Signal.TRAILING_INITIAL] = FAMILY_FIRST

    particle = _particle(words, lexicon)
    if particle is not None:
        votes[Signal.PARTICLE] = particle

    short_capitals = _ends_in_short_capitals(words)
    for signal, table, first_order, last_order, skip_last in (
            (Signal.SURNAME, ROMANIZED_SURNAMES, FAMILY_FIRST, GIVEN_FIRST,
             short_capitals),
            (Signal.GIVEN_NAME, COMMON_GIVEN_NAMES, GIVEN_FIRST, FAMILY_FIRST,
             False)):
        at_first, at_last = _at_one_end(words, table, skip_last)
        if at_first != at_last:
            votes[signal] = first_order if at_first else last_order

    patronymic = _patronymic(words)
    if patronymic is not None:
        votes[Signal.PATRONYMIC] = patronymic
    return votes, False


def name_votes(text: str, lexicon: Lexicon
               ) -> dict[Signal, tuple[Role, Role, Role] | PatronymicRule]:
    """The votes one name casts; empty for a name of fewer than two
    words once its titles and post-nominals are read past, and for a
    comma name, save one whose comma is followed by post-nominals
    alone."""
    return _read(text, lexicon)[0]


# -- the group ----------------------------------------------------------

#: A vote one signal casts: an order, or the patronymic rule a shape
#: matches.
Vote = tuple[Role, Role, Role] | PatronymicRule
#: A setting's value as SettingEvidence holds it: an order, a set of
#: patronymic rules, or a switch (initials_as_family).
SettingValue = tuple[Role, Role, Role] | frozenset[PatronymicRule] | bool

# The thresholds, chosen with tools/differential/suggest_measure.py
# so that a group written in its base's own order stays right in at
# least 95% of draws at every size; the measurements behind each are in
# decisions/group-suggestion, 2026-11-10 THRESHOLDS.

#: The fewest names voting for a value that can decide it.
_MIN_VOTES = 2
#: The share of the names casting an order vote that one end must hold
#: STRICTLY MORE THAN to decide the order: more than two thirds, so a
#: tie, or two names against one, decides nothing.
_MIN_SHARE = 2 / 3
#: The share of the names casting any vote that one patronymic rule
#: (East Slavic or Turkic) must hold strictly more than to decide it,
#: higher than _MIN_SHARE because a decided East Slavic rule brings a
#: given-first order with it.
_MIN_PATRONYMIC_SHARE = 0.8
#: The fewest names carrying one patronymic rule that can decide it,
#: besides the share, for the same reason.
_MIN_PATRONYMIC_VOTES = 5
#: The fewest names ending in one run of letters (rules/O8) that can
#: decide initials_as_family, and the share of the names ending in any
#: run that one run must hold at least: a list written in that
#: convention repeats its letters (Nepal's `B K` and `K C`), where a
#: list of middle and family initials or of bylines rarely does
#: (decisions/group-suggestion, 2026-11-11 LETTER RUNS).
_MIN_RUN_NAMES = 2
_MIN_RUN_SHARE = 0.5

_NAME_ORDER = "name_order"
_PATRONYMIC_RULES = "patronymic_rules"
_INITIALS_AS_FAMILY = "initials_as_family"
_SIGNAL_RANK = {signal: rank for rank, signal in enumerate(Signal)}


def _end(order: tuple[Role, ...]) -> tuple[Role, Role, Role]:
    """The end an order writes the family name at, spelled as a vote:
    ``FAMILY_FIRST`` for either family-first order."""
    return FAMILY_FIRST if order[0] is Role.FAMILY else GIVEN_FIRST


def _order_ends(pairs: Iterable[tuple[Signal, Vote]]
                ) -> frozenset[tuple[Role, Role, Role]]:
    """The ends a name's order signals voted for: none, one (the name's
    order vote) or both (the name is contested and casts no order
    vote)."""
    return frozenset(vote for signal, vote in pairs  # type: ignore[misc]
                     if signal is not Signal.PATRONYMIC)


def _checked_vote(signal: object, vote: object,
                  owner: str = "NameEvidence") -> tuple[Signal, Vote]:
    """One (signal, vote) pair, validated: an order signal votes
    ``GIVEN_FIRST`` or ``FAMILY_FIRST``, the patronymic signal a
    ``PatronymicRule``. ``owner`` names the type in the message."""
    signal = Signal(signal)  # type: ignore[arg-type]  # ValueError names it
    if signal is Signal.PATRONYMIC:
        if not isinstance(vote, PatronymicRule):
            raise TypeError(
                f"{owner} vote for {signal.value!r} must be a "
                f"PatronymicRule, got {vote!r}; pass e.g. "
                f"{{Signal.PATRONYMIC: PatronymicRule.EAST_SLAVIC}}")
        return signal, vote
    if not isinstance(vote, (tuple, list)):
        raise TypeError(
            f"{owner} vote for {signal.value!r} must be an order, "
            f"got {vote!r}; pass GIVEN_FIRST or FAMILY_FIRST")
    order = tuple(vote)
    for end in (GIVEN_FIRST, FAMILY_FIRST):
        if order == end:
            # the shared constant, so a vote compares by identity too
            return signal, end
    raise ValueError(
        f"{owner} vote for {signal.value!r} must name an end, "
        f"GIVEN_FIRST or FAMILY_FIRST, got {vote!r}; a vote never "
        f"spells FAMILY_FIRST_GIVEN_LAST, which is FAMILY_FIRST's end")


def _iterable(value: object, owner: str, form: str, example: str
              ) -> tuple[object, ...]:
    """``value`` as a tuple, refusing a bare str, bytes, a mapping or a
    non-iterable, each of which would iterate into the wrong items."""
    if (isinstance(value, (str, bytes, bytearray, Mapping))
            or not isinstance(value, Iterable)):
        raise TypeError(
            f"{owner} must be {form}, got {type(value).__name__} "
            f"{reprlib.repr(value)}; pass e.g. {example}")
    return tuple(value)


def _checked_row(row: object, setting: str) -> tuple[Signal, Vote, int]:
    """One ``by_signal`` row, validated: ``(signal, vote, count)``, its
    signal one that votes on ``setting``."""
    if isinstance(row, (str, bytes)) or not isinstance(row, (tuple, list)) \
            or len(row) != 3:
        raise TypeError(
            f"SettingEvidence by_signal rows must be (signal, vote, count) "
            f"triples, got {reprlib.repr(row)}; pass e.g. "
            f"(Signal.SURNAME, FAMILY_FIRST, 2)")
    signal, vote, count = row
    pair = _checked_vote(signal, vote, "SettingEvidence by_signal")
    if _setting_of(pair[0]) != setting:
        raise ValueError(
            f"SettingEvidence by_signal row {reprlib.repr(row)} is a "
            f"{pair[0].value!r} vote, which votes on {_setting_of(pair[0])}, "
            f"not on {setting}; put it in that setting's evidence")
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError(
            f"SettingEvidence by_signal count must be an int count of "
            f"votes, got {count!r}; pass e.g. 2")
    if count < 0:
        raise ValueError(
            f"SettingEvidence by_signal count must not be negative, got "
            f"{count!r}; a count of votes is 0 or more")
    return (*pair, count)


#: The settings a SettingEvidence may be about: the PolicyPatch fields,
#: which the report reads off the patch by name.
_SETTINGS = frozenset(f.name for f in dataclasses.fields(PolicyPatch))


def _label(value: object) -> str:
    """A vote or a setting's value, as the report and reprs write it."""
    if isinstance(value, PatronymicRule):
        return value.value
    if isinstance(value, frozenset):
        return ", ".join(sorted(_label(v) for v in value)) or "none"
    if isinstance(value, tuple):
        return _order_repr(value)
    return repr(value)


_NAME_EVIDENCE_EXAMPLE = (
    "NameEvidence('Kim Minjun', {Signal.SURNAME: FAMILY_FIRST})")


@dataclass(frozen=True, slots=True, init=False)
class NameEvidence:
    """One input name and the votes it cast, read with the base
    parser's lexicon. A name with a comma, no words or one word casts
    none, and a name that casts none never disagrees with the group.
    Order votes are one per NAME: the end the name's order signals
    agree on. A name whose order signals point at both ends is
    contested, casts no order vote and never disagrees on order.
    ``votes`` keeps every signal's vote all the same, save a
    trailing-initial vote in a group whose runs of letters decided
    ``initials_as_family``, whose letters are its family.
    ``dataclasses.replace`` keeps the votes unless it is passed
    ``votes=`` too."""

    #: The name exactly as the caller passed it.
    text: str
    # the votes as (Signal, vote) pairs in Signal's order: a tuple, so
    # the type stays frozen, hashable and picklable; read it through
    # the `votes` property
    _votes: tuple[tuple[Signal, Vote], ...]

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __init__(self, text: str,
                 votes: Mapping[Signal, Vote] | None = None, *,
                 _votes: Iterable[tuple[Signal, Vote]] | None = None
                 ) -> None:
        # `_votes` is the stored field's name, which dataclasses.replace
        # passes back; `votes`, where given, wins, so
        # replace(evidence, votes=...) replaces them
        if votes is None and _votes is not None:
            votes = dict(_votes)
        if not isinstance(text, str):
            raise TypeError(
                f"NameEvidence text must be a str, got "
                f"{type(text).__name__} {reprlib.repr(text)}; pass e.g. "
                f"{_NAME_EVIDENCE_EXAMPLE}")
        if not isinstance(votes, Mapping):
            raise TypeError(
                f"NameEvidence votes must be a mapping of Signal to vote, "
                f"got {type(votes).__name__} {reprlib.repr(votes)}; pass "
                f"e.g. {_NAME_EVIDENCE_EXAMPLE}")
        pairs = tuple(sorted(
            (_checked_vote(signal, vote) for signal, vote in votes.items()),
            key=lambda pair: _SIGNAL_RANK[pair[0]]))
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "_votes", pairs)

    def __repr__(self) -> str:
        votes = "".join(f", {signal.value}={_label(vote)}"
                        for signal, vote in self._votes)
        return f"NameEvidence({self.text!r}{votes})"

    @property
    def votes(self) -> Mapping[Signal, Vote]:
        """The votes this name cast, keyed by signal; read-only."""
        return MappingProxyType(dict(self._votes))


@dataclass(frozen=True, slots=True)
class SettingEvidence:
    """What the group said about one ``Policy`` setting.

    ``value`` is the setting's value under the suggested parser: the
    decided value where ``decided`` is true, else the base's. A decided
    value equal to the base's is not in the patch, which holds only
    changes, but is still ``decided``. The four counts are of NAMES and
    add up to the group's size: ``votes_for`` the names whose vote is
    for ``value``, ``votes_against`` the names whose vote is for
    another value, ``contested`` the names whose signals point both
    ways on this setting (and so cast no vote), and ``no_evidence`` the
    names with no signal on it. ``by_signal`` breaks the signals' own
    votes down as ``(signal, vote, count)`` rows, so a name two signals
    read appears in two of them. ``note``, where it is not empty, says
    why the setting was decided or left undecided as it was."""

    #: The ``Policy`` field this evidence is about.
    setting: str
    #: The field's value under the suggested parser.
    value: SettingValue
    #: Whether the group's votes decided the value.
    decided: bool
    votes_for: int
    votes_against: int
    contested: int
    no_evidence: int
    by_signal: tuple[tuple[Signal, Vote, int], ...]
    note: str = ""

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if not isinstance(self.setting, str):
            raise TypeError(
                f"SettingEvidence setting must be a Policy field name "
                f"(str), got {self.setting!r}; pass e.g. 'name_order'")
        if self.setting not in _SETTINGS:
            raise ValueError(
                f"SettingEvidence setting must name a Policy field, got "
                f"{self.setting!r}; pass one of "
                f"{', '.join(sorted(_SETTINGS))}")
        if not isinstance(self.decided, bool):
            raise TypeError(
                f"SettingEvidence decided must be a bool, got "
                f"{self.decided!r}; pass True or False")
        for name in ("votes_for", "votes_against", "contested",
                     "no_evidence"):
            count = getattr(self, name)
            if isinstance(count, bool) or not isinstance(count, int):
                raise TypeError(
                    f"SettingEvidence {name} must be an int count of "
                    f"names, got {count!r}; pass e.g. 0")
            if count < 0:
                raise ValueError(
                    f"SettingEvidence {name} must not be negative, got "
                    f"{count!r}; a count of names is 0 or more")
        if not isinstance(self.note, str):
            raise TypeError(
                f"SettingEvidence note must be a str, got {self.note!r}; "
                f"pass '' for no note")
        rows = _iterable(self.by_signal, "SettingEvidence by_signal",
                         "an iterable of (signal, vote, count) rows",
                         "((Signal.SURNAME, FAMILY_FIRST, 2),) or ()")
        object.__setattr__(
            self, "by_signal",
            tuple(_checked_row(row, self.setting) for row in rows))

    def __repr__(self) -> str:
        state = "decided" if self.decided else "undecided"
        return (f"SettingEvidence({self.setting}={_label(self.value)}, "
                f"{state}, {self.votes_for} for, {self.votes_against} "
                f"against, {self.contested} contested, {self.no_evidence} "
                f"no evidence)")


@dataclass(frozen=True, slots=True)
class Suggestion:
    """The settings a group of names suggests: build it with
    :meth:`Parser.suggest`. ``patch`` holds only the settings the group
    decided and that differ from the base's; ``parser`` is the base
    with the patch applied; ``evidence`` holds one
    :class:`SettingEvidence` per setting considered, and ``names`` one
    :class:`NameEvidence` per input name, in input order, blanks and
    duplicates included. ``str()`` is a readable report."""

    #: The parser ``suggest`` was called on.
    base: Parser
    #: The settings the group decided that differ from the base's.
    patch: PolicyPatch
    evidence: tuple[SettingEvidence, ...]
    names: tuple[NameEvidence, ...]

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        # Parser at call time: _parser imports this module at call time
        # too, in Parser.suggest
        from ._parser import Parser
        if not isinstance(self.base, Parser):
            raise TypeError(
                f"Suggestion base must be a Parser, got "
                f"{type(self.base).__name__} {reprlib.repr(self.base)}; "
                f"build a Suggestion with parser.suggest(names)")
        if not isinstance(self.patch, PolicyPatch):
            raise TypeError(
                f"Suggestion patch must be a PolicyPatch, got "
                f"{reprlib.repr(self.patch)}; pass e.g. PolicyPatch() or "
                f"PolicyPatch(name_order=FAMILY_FIRST)")
        for name, cls in (("evidence", SettingEvidence),
                          ("names", NameEvidence)):
            items = _iterable(
                getattr(self, name), f"Suggestion {name}",
                f"a tuple of {cls.__name__}", f"() or a tuple of "
                f"{cls.__name__} items")
            for item in items:
                if not isinstance(item, cls):
                    raise TypeError(
                        f"Suggestion {name} must hold {cls.__name__} "
                        f"items, got {type(item).__name__} "
                        f"{reprlib.repr(item)}; pass a tuple of "
                        f"{cls.__name__}, or build a Suggestion with "
                        f"parser.suggest(names)")
            object.__setattr__(self, name, items)
        self._check_against_the_patch()

    def __repr__(self) -> str:
        # bounded: the patch and counts, never a name
        return (f"Suggestion({self.patch!r}, names={len(self.names)}, "
                f"disagreeing={len(self.disagreeing())})")

    def __str__(self) -> str:
        noun = "name" if len(self.names) == 1 else "names"
        lines = [f"Suggested for {len(self.names)} {noun} "
                 f"(base: {self.base!r}):"]
        for e in self.evidence:
            if e.decided:
                changed = getattr(self.patch, e.setting) is not UNSET
                state = _label(e.value) + ("" if changed else " (as the base)")
            else:
                state = f"unchanged ({_label(e.value)})"
            if e.votes_for or e.votes_against or e.contested:
                contested = (f"{e.contested} contested, "
                             if e.contested else "")
                counts = (f"{e.votes_for} for, {e.votes_against} against, "
                          f"{contested}{e.no_evidence} no evidence")
            else:
                counts = "no evidence"
            lines.append(f"  {e.setting}  {state}  {counts}")
            for signal, vote, count in e.by_signal:
                lines.append(f"      {signal.value} {_label(vote)}  {count}")
            if e.note:
                lines.append(f"      {e.note}")
        against = self.disagreeing()
        if against:
            shown = ", ".join(n.text for n in against[:5])
            more = f", and {len(against) - 5} more" if len(against) > 5 else ""
            lines.append(f"  disagreeing ({len(against)}): {shown}{more}")
        return "\n".join(lines)

    @property
    def parser(self) -> Parser:
        """The base parser with :attr:`patch` applied: the same lexicon
        and segmenter, and the base's policy for every setting the
        group did not change. It is built afresh on each access, so
        bind it once (``p = s.parser``) before parsing in a loop."""
        # A new construction site for Parser (AGENTS.md's validation
        # bullet): a warning Parser.__post_init__ gives here is passed
        # on from the caller's frame only where the base, built the
        # same way, does not give it too -- the base's own warnings
        # reached its caller when it was built.
        def built(policy: Policy
                  ) -> tuple[Parser, list[warnings.WarningMessage]]:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                parser = dataclasses.replace(self.base, policy=policy)
            return parser, caught

        _, before = built(self.base.policy)
        parser, after = built(apply_patch(self.base.policy, self.patch))
        seen = {(w.category, str(w.message)) for w in before}
        for w in after:
            if (w.category, str(w.message)) not in seen:
                warnings.warn(w.message, w.category, stacklevel=2)
        return parser

    def disagreeing(self) -> tuple[NameEvidence, ...]:
        """The names whose vote is against a decided setting's value,
        in input order. A setting left undecided has no answer to
        disagree with; a name that cast no vote, or whose order signals
        are contested, never disagrees on order; and a name carrying an
        East Slavic patronymic never disagrees on order where the East
        Slavic rule is decided, since the rule reorders it."""
        decided = {e.setting: e.value for e in self.evidence if e.decided}
        if not decided:
            return ()
        return tuple(n for n in self.names if _disagrees(n, decided))

    def _check_against_the_patch(self) -> None:
        """The evidence, the patch and the names agree: one evidence
        per setting, a decided value the suggested parser's own, an
        undecided setting out of the patch, every patch field a decided
        change from the base, and every setting's counts adding up to
        the names."""
        settings = Counter(e.setting for e in self.evidence)
        for setting, count in settings.items():
            if count > 1:
                raise ValueError(
                    f"Suggestion evidence holds {setting!r} more than "
                    f"once ({count} times); pass one SettingEvidence per "
                    f"setting")
        policy = apply_patch(self.base.policy, self.patch)
        decided = set()
        size = len(self.names)
        for e in self.evidence:
            total = (e.votes_for + e.votes_against + e.contested
                     + e.no_evidence)
            if total != size:
                raise ValueError(
                    f"Suggestion evidence for {e.setting} counts names "
                    f"that add up to {total}, not the {size} names in "
                    f"names; each name is for, against, contested or of "
                    f"no evidence on every setting")
            if e.decided:
                decided.add(e.setting)
                if e.value != getattr(policy, e.setting):
                    raise ValueError(
                        f"Suggestion's decided {e.setting} value "
                        f"{_label(e.value)} is not the suggested parser's "
                        f"{_label(getattr(policy, e.setting))}; set the "
                        f"patch to the decided value, or leave it out "
                        f"where the value is the base's")
            elif getattr(self.patch, e.setting) is not UNSET:
                raise ValueError(
                    f"Suggestion patch sets {e.setting}, which its "
                    f"evidence leaves undecided; mark the evidence "
                    f"decided, or leave {e.setting} out of the patch")
        for f in dataclasses.fields(PolicyPatch):
            if getattr(self.patch, f.name) is UNSET:
                continue
            if f.name not in decided:
                raise ValueError(
                    f"Suggestion patch sets {f.name}, which no decided "
                    f"SettingEvidence holds; add that evidence, or leave "
                    f"{f.name} out of the patch")
            if getattr(policy, f.name) == getattr(self.base.policy, f.name):
                raise ValueError(
                    f"Suggestion patch sets {f.name} to the base's own "
                    f"value {_label(getattr(policy, f.name))}; a patch "
                    f"holds only changes, so leave it out and keep the "
                    f"evidence decided")



def _setting_of(signal: Signal) -> str:
    return _PATRONYMIC_RULES if signal is Signal.PATRONYMIC else _NAME_ORDER


def _disagrees(name: NameEvidence, decided: Mapping[str, object]) -> bool:
    """Whether one name's votes contradict a decided setting."""
    patronymic = dict(name._votes).get(Signal.PATRONYMIC)
    rules = decided.get(_PATRONYMIC_RULES)
    if rules is not None and patronymic is not None:
        if patronymic not in rules:  # type: ignore[operator]
            return True
    order = decided.get(_NAME_ORDER)
    if order is None:
        return False
    if (rules is not None and patronymic is PatronymicRule.EAST_SLAVIC
            and patronymic in rules  # type: ignore[operator]
            and _end(order) == GIVEN_FIRST):  # type: ignore[arg-type]
        return False
    ends = _order_ends(name._votes)
    return len(ends) == 1 and next(iter(ends)) != _end(order)  # type: ignore[arg-type]


class _Tally:
    """The group's votes on one setting, one per name, gathered in one
    pass. A plain class rather than a dataclass: it is never pickled or
    returned."""

    __slots__ = ("names", "contested", "by_name", "by_signal")

    def __init__(self) -> None:
        self.names = 0
        self.contested = 0
        #: names per value voted for
        self.by_name: Counter[Vote] = Counter()
        #: signal votes per (signal, value)
        self.by_signal: Counter[tuple[Signal, Vote]] = Counter()

    def add(self, pairs: list[tuple[Signal, Vote]]) -> None:
        """One name's votes on this setting: its signals' votes, and
        one name vote where they agree."""
        self.names += 1
        for pair in pairs:
            self.by_signal[pair] += 1
        values = {vote for _, vote in pairs}
        if len(values) == 1:
            self.by_name[values.pop()] += 1
        elif values:
            self.contested += 1

    def winner(self) -> Vote | None:
        """The value whose names are at least _MIN_VOTES and strictly
        more than _MIN_SHARE of the names that cast a vote, if one
        is."""
        counts = self.by_name
        total = sum(counts.values())
        if not counts:
            return None
        vote, count = max(counts.items(), key=lambda item: item[1])
        if count < _MIN_VOTES or count <= _MIN_SHARE * total:
            return None
        return vote

    def evidence(self, setting: str, value: SettingValue, decided: bool,
                 is_for: Callable[[Vote], bool], note: str = ""
                 ) -> SettingEvidence:
        """Evidence for ``value``; ``is_for`` says which name votes are
        for it."""
        counts = self.by_name
        votes_for = sum(c for v, c in counts.items() if is_for(v))
        rows = tuple(sorted(
            ((signal, vote, count)
             for (signal, vote), count in self.by_signal.items()),
            key=lambda row: (_SIGNAL_RANK[row[0]], _label(row[1]))))
        voters = sum(counts.values())
        return SettingEvidence(
            setting, value, decided, votes_for, voters - votes_for,
            self.contested, self.names - voters - self.contested, rows,
            note)


def _patronymic_winner(tally: _Tally, any_voters: int
                       ) -> PatronymicRule | None:
    """The rule whose names are strictly more than _MIN_PATRONYMIC_SHARE
    of the names that cast any vote, and at least _MIN_PATRONYMIC_VOTES
    of them. A
    name whose order signals are contested still counts among the names
    that cast a vote: it carries evidence, and leaving it out moved no
    measured group by more than a point. A name casts at most one
    patronymic vote, so its votes count names: a share of the group,
    not of the patronymic votes alone, so one patronymic among many
    given-first names decides nothing."""
    counts = tally.by_name
    if not counts:
        return None
    rule, count = max(counts.items(), key=lambda item: item[1])
    if (count < _MIN_PATRONYMIC_VOTES
            or count <= _MIN_PATRONYMIC_SHARE * any_voters):
        return None
    return rule  # type: ignore[return-value]


def _decide_patronymic(tally: _Tally, base_rules: frozenset[PatronymicRule],
                       any_voters: int
                       ) -> tuple[SettingEvidence, dict[str, object], bool]:
    """Decide ``patronymic_rules``: the evidence, the patch fields, and
    whether the decided rule needs a given-first order."""
    rule = _patronymic_winner(tally, any_voters)
    if rule is PatronymicRule.EAST_SLAVIC:
        # the rule reorders a family-first East Slavic name itself, and
        # stands down under a declared family-first order, so the group
        # gets the rule with a given-first order (what locales.RU ships)
        value = base_rules | {rule}
        fields: dict[str, object] = (
            {} if rule in base_rules else {_PATRONYMIC_RULES: frozenset({rule})})
        return (tally.evidence(_PATRONYMIC_RULES, value, True,
                               lambda v: v in value), fields, True)
    if rule is PatronymicRule.TURKIC:
        return _decide_turkic(tally, base_rules)
    return (tally.evidence(_PATRONYMIC_RULES, base_rules, False,
                           lambda v: v in base_rules), {}, False)


def _decide_turkic(tally: _Tally, base_rules: frozenset[PatronymicRule]
                   ) -> tuple[SettingEvidence, dict[str, object], bool]:
    """A group whose patronymics are Turkic gets the rule alone. Unlike
    the East Slavic rule it reads a name written either way round
    (``Mamedov Ali Huseyn oglu`` and ``Ali Huseyn oglu Mamedov`` both
    read family Mamedov), so it forces no order: the order is decided
    from the names' own votes (decisions/group-suggestion, 2026-11-10
    TURKIC)."""
    rule = PatronymicRule.TURKIC
    value = base_rules | {rule}
    fields: dict[str, object] = (
        {} if rule in base_rules else {_PATRONYMIC_RULES: frozenset({rule})})
    return (tally.evidence(_PATRONYMIC_RULES, value, True,
                           lambda v: v in value), fields, False)


def _comma_note(left_out: int) -> str:
    if not left_out:
        return ""
    noun = "name with a comma was" if left_out == 1 else "names with a comma were"
    return (f"{left_out} {noun} left out: a comma states its own order, "
            f"so only a comma followed by post-nominals alone is read past")


def _decide_order(tally: _Tally, base_order: tuple[Role, Role, Role],
                  rule_needs_given_first: bool, comma_left_out: int,
                  extra_note: str = ""
                  ) -> tuple[SettingEvidence, dict[str, object]]:
    """Decide ``name_order`` in either direction. A family-first answer
    keeps the base's family-first spelling where the base has one. A
    decided East Slavic rule decides the order as given-first, since
    the rule reorders each name and stands down under a family-first
    order, unless the names' own votes decide family-first: a decided
    order is never overridden, and the rule then stands down."""
    notes = [_comma_note(comma_left_out), extra_note]
    end = tally.winner()
    if rule_needs_given_first and end != FAMILY_FIRST:
        fields: dict[str, object] = (
            {} if base_order == GIVEN_FIRST else {_NAME_ORDER: GIVEN_FIRST})
        notes.insert(0, "the East Slavic rule reorders each name; it needs "
                        "a given-first order")
        return (tally.evidence(
            _NAME_ORDER, GIVEN_FIRST, True, lambda v: v == GIVEN_FIRST,
            note="; ".join(n for n in notes if n)), fields)
    if rule_needs_given_first:
        notes.insert(0, "the East Slavic rule is decided too, but the names' "
                        "order votes decide a family-first order, under "
                        "which the rule stands down")
    note = "; ".join(n for n in notes if n)
    if end is None:
        return (tally.evidence(_NAME_ORDER, base_order, False,
                               lambda v: v == _end(base_order), note), {})
    # the order tally holds orders alone
    order = base_order if _end(base_order) == end else cast(
        "tuple[Role, Role, Role]", end)
    fields = (
        {} if order == base_order else {_NAME_ORDER: order})
    return (tally.evidence(_NAME_ORDER, order, True,
                           lambda v: v == end, note), fields)


def _texts(names: Iterable[str]) -> Iterator[str]:
    """The names, checked as they are consumed: one pass, so a
    generator is read once."""
    example = 'parser.suggest(["Priem Jason", "Kim Minjun"])'
    if isinstance(names, str):
        raise TypeError(
            f"suggest() takes an iterable of names, not a bare string: "
            f"{names!r}. Wrap one name in a list: "
            f"parser.suggest([{names!r}])")
    if isinstance(names, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"suggest() takes an iterable of str, not "
            f"{type(names).__name__} -- decode first, e.g. "
            f"raw.decode('utf-8')")
    if isinstance(names, Mapping):
        raise TypeError(
            f"suggest() takes an iterable of names, not a mapping "
            f"({type(names).__name__}). A mapping yields only its keys; "
            f"pass the names themselves, e.g. list(mapping) or "
            f"list(mapping.values()): {example}")
    try:
        iterator = iter(names)
    except TypeError:
        raise TypeError(
            f"suggest() takes an iterable of names, got {names!r}: "
            f"{example}") from None
    for index, text in enumerate(iterator):
        if not isinstance(text, str):
            raise TypeError(
                f"suggest() takes an iterable of str; item {index} is "
                f"{text!r} ({type(text).__name__}). Pass each name as a "
                f"string: {example}")
        yield text


def _letter_readers(parser: Parser) -> tuple[Parser, Parser]:
    """The base with the switch on and off, every other setting the
    base's own save the fold of every middle into the family (rules/O3),
    which takes the letters there too and so would hide the run the
    switch reads. Asked only of a base reading names given first, where
    the rule acts."""
    policy = dataclasses.replace(parser.policy, middle_as_family=False)
    with warnings.catch_warnings():
        # the base's own construction warnings reached its caller
        warnings.simplefilter("ignore")
        return (dataclasses.replace(parser, policy=dataclasses.replace(
                    policy, initials_as_family=True)),
                dataclasses.replace(parser, policy=dataclasses.replace(
                    policy, initials_as_family=False)))


def _decide_letters(runs: list[str | None], base_value: bool,
                    family_first: bool
                    ) -> tuple[SettingEvidence, dict[str, object]]:
    """Decide ``initials_as_family``: true where at least _MIN_RUN_NAMES
    names end in one run of letters and it is at least _MIN_RUN_SHARE of
    the names ending in any run. A group never decides it false: no
    name is evidence that letters are NOT a family. Nor does it decide
    anything under a base reading names family first (`family_first`),
    where rules/O8 stands down, so the switch would change no name and
    no name was read for a run."""
    counts = Counter(run for run in runs if run)
    carrying = sum(counts.values())
    if family_first:
        return (SettingEvidence(
            _INITIALS_AS_FAMILY, base_value, False, 0, 0, 0, len(runs), (),
            "not read: the base reads names family first, where letters "
            "ending a name are never taken as its family"), {})
    if not counts:
        return (SettingEvidence(_INITIALS_AS_FAMILY, base_value, False,
                                0, 0, 0, len(runs), ()), {})
    run, top = counts.most_common(1)[0]
    decided = top >= _MIN_RUN_NAMES and top >= _MIN_RUN_SHARE * carrying
    value = True if decided else base_value
    # a name ending in a run is evidence FOR the switch, whatever the
    # group decided; the others carry none
    votes_for, votes_against = (carrying, 0) if value else (0, carrying)
    if top >= _MIN_RUN_NAMES:
        note = (f"{top} of the {carrying} names ending in a run of "
                f"letters end in {' '.join(run.upper())}")
    else:
        verb = "ends" if carrying == 1 else "end"
        note = (f"{carrying} of {len(runs)} names {verb} in a run of "
                f"letters, none repeated")
    fields: dict[str, object] = (
        {_INITIALS_AS_FAMILY: True} if decided and not base_value else {})
    return (SettingEvidence(_INITIALS_AS_FAMILY, value, decided, votes_for,
                            votes_against, 0, len(runs) - carrying, (),
                            note), fields)


def suggest(parser: Parser, names: Iterable[str]) -> Suggestion:
    """The settings a group of names suggests, with ``parser`` as the
    base: see :meth:`Parser.suggest`."""
    tallies = {_NAME_ORDER: _Tally(), _PATRONYMIC_RULES: _Tally()}
    evidence: list[NameEvidence] = []
    any_voters = comma_left_out = 0
    texts = list(_texts(names))
    family_first = parser.policy.name_order != GIVEN_FIRST
    if family_first:
        runs: list[str | None] = [None] * len(texts)
    else:
        readers = _letter_readers(parser)
        runs = [_letter_run(text, readers) for text in texts]
    letters, letter_fields = _decide_letters(
        runs, parser.policy.initials_as_family, family_first)
    letters_are_family = letters.decided and letters.value is True
    for text in texts:
        votes, comma = _read(text, parser.lexicon)
        # counted before the vote below leaves it: the name carries
        # evidence all the same, the patronymic share's denominator
        any_voters += bool(votes)
        if letters_are_family:
            # the group's letters are its family (rules/O8), so a name
            # ending in letters is no evidence of a family-first order
            votes.pop(Signal.TRAILING_INITIAL, None)
        evidence.append(NameEvidence(text, votes))
        comma_left_out += comma
        per_setting: dict[str, list[tuple[Signal, Vote]]] = {
            setting: [] for setting in tallies}
        for signal, vote in votes.items():
            per_setting[_setting_of(signal)].append((signal, vote))
        for setting, tally in tallies.items():
            tally.add(per_setting[setting])
    policy = parser.policy
    patronymic, patronymic_fields, settled = _decide_patronymic(
        tallies[_PATRONYMIC_RULES], policy.patronymic_rules, any_voters)
    order, order_fields = _decide_order(
        tallies[_NAME_ORDER], policy.name_order, settled, comma_left_out,
        "the trailing-initial signal casts no vote: the group's letters "
        "are its family (initials_as_family)" if letters_are_family else "")
    fields = {**order_fields, **patronymic_fields, **letter_fields}
    patch = PolicyPatch(**fields)  # type: ignore[arg-type]
    return Suggestion(parser, patch, (order, patronymic, letters),
                      tuple(evidence))

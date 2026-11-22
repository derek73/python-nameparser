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
capitals vote and no surname vote of its own, being looked up only to
veto (a name ending in one that is a listed surname, `Zhou NG`, casts
no surname vote, #1397), one opening such a name with no capitals word
after it (`AM Hoy`, `NG Emily`) casts no capitals vote either, and the
name no surname vote (#1355), and a script the tables do not hold
(Hangul, Han) simply matches nothing. A patronymic
votes, Latin or Cyrillic, only where the pipeline's rule reads one
(rules/O1's three name words, rules/O2's four), through the pipeline's
own predicates, never a copy of them, and an East Slavic one casts a
second vote, on the order, by where it stands as rules/O1 reads it
(``Signal.PATRONYMIC_POSITION``: last family-first, in the middle
given-first). No signal raises on any string.

``suggest`` tallies the group's votes and decides two settings
together, ``patronymic_rules`` first and ``name_order`` second: a
decided East Slavic rule reorders each name itself, and reorders none
under a family-first order, so it decides the order as given-first,
unless the names' own votes decide family-first, as a list of
patronymics written last does, which it never overrides (a ``FAMILY_FIRST_GIVEN_LAST`` base
then gets ``FAMILY_FIRST``),
or the base reads ``FAMILY_FIRST`` and the patronymics are
mostly written last, whose order it keeps (decisions/group-suggestion).
Before either it decides
``initials_as_family`` (rules/O8) from the runs of letters ending the
group's names, a group property with no per-name vote, and a group
decided so casts no trailing-initial vote on its order. Beside them it
decides ``capitals_as_family`` (rules/O9) from the names whose family
the rule, asked of the parse itself with the switch on, reads as a
word in capitals of four letters or more that the lexicon lists as no
credential or numeral and the base reads as no title, against the names
the switch would give a family the base reads as a title and the names
in mixed case with no word in capitals; it is no vote on the order,
which the capitals signal casts as before. Last it weighs
``two_family_names`` (rules/O6), where the rest reads given-first with
the East Slavic rule off, asking the parse itself under that parser
with the switch off and on: a name the switch would change votes for it
where the word it would take into the family is a common surname of
the ORCID table (`Signal.FIRST_SURNAME`), casts no vote where that word
is a common given name, and votes against it where it is a father's
name. A setting is
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
from ._pipeline._post_rules import _listed_suffix
from ._pipeline._vocab import (
    ROMAN, east_slavic_rotates, has_patronymic_ending, is_capitals_word,
    is_initial, is_one_case, is_patronymic_marker, is_suffix_lenient,
    is_title_shaped, reads_as_generation, suffix_as_written,
)
from ._policy import (
    UNSET, CapsSuffixes, PatronymicRule, Policy, PolicyPatch, _order_repr,
    apply_patch, initials_as_family_may_move,
)
from ._types import (
    ADDED_IN, FAMILY_FIRST, GIVEN_FIRST, ReadingSource, Role,
    _guarded_getstate, _guarded_setstate,
)
from .config._order_names import COMMON_GIVEN_NAMES, COMMON_SURNAMES, SURNAMES

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
    """The evidence a single name offers about how its writer writes
    names; each signal votes on one ``Policy`` setting: the order, the
    patronymic rule or ``two_family_names``."""

    #: A family name written in capitals at one end of a name in mixed
    #: case (``Mary SMITH``); votes on the order.
    CAPITALS = "capitals"
    #: Initials ending the name (``Smith J.``), counted only where enough
    #: of the group's names end in them, as a bibliography's do; votes on
    #: the order.
    TRAILING_INITIAL = "trailing-initial"
    #: A lowercase particle first or before the last word; votes on the
    #: order.
    PARTICLE = "particle"
    #: A common surname as the first or last word: a romanized Chinese,
    #: Korean or Vietnamese one, or one researchers rarely write as a
    #: given name (``García``, ``Quispe``); votes on the order.
    SURNAME = "surname"
    #: A common given name that is rarely a surname (``Emily``, not
    #: ``Taylor``) as the first or last word; votes on the order.
    GIVEN_NAME = "given-name"
    #: A patronymic a rule reads (Russian ``Petrovich``, Azerbaijani
    #: ``Huseyn oglu``); votes on ``patronymic_rules``.
    PATRONYMIC = "patronymic"
    #: Where a Russian-style patronymic stands in a name of three words:
    #: last (``Sidorov Ivan Petrovich``), the family name is written
    #: first; in the middle (``Ivan Petrovich Sidorov``), last. Cast only
    #: beside a Russian-style ``PATRONYMIC`` vote; votes on the order.
    PATRONYMIC_POSITION = "patronymic-position"
    #: The word ``two_family_names`` would take into a name's family,
    #: voting the switch's value: True where it is a surname researchers
    #: rarely write as a given name, the second of the tables ``SURNAME``
    #: names (``García`` in ``Gabriel García Márquez``, a first surname where
    #: a second given name would stand), False where it is a father's
    #: name the switch would read as a first surname (``Ivan Petrovich
    #: Sidorov``). A listed given name there casts no vote.
    FIRST_SURNAME = "first-surname"


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


def _is_short_capitals(word: str) -> bool:
    """A capitals word of two or three letters: joined initials (`JO`,
    `AM`) or a short surname (`NG`, `LI`), which the word alone cannot
    tell apart."""
    return 2 <= sum(c.isalpha() for c in word) <= 3 and _is_caps_word(word)


def _ends_in_short_capitals(words: list[str]) -> bool:
    """Whether a name holding a lowercase letter ends in a capitals word
    of two or three letters (`Armitage JO`, `Smith JP`, `Jason NG`).
    Such a word casts no capitals vote, and no surname vote of its
    own: `_read` looks it up only to veto the word in front's (#1397)."""
    return _is_short_capitals(words[-1]) and _has_lower(words)


def _opens_in_short_capitals(words: list[str]) -> bool:
    """Whether a name holding a lowercase letter opens in one capitals
    word of two or three letters (`AM Hoy`, a byline written initials
    first; `NG Emily`). Such a word casts no capitals vote, and the name
    no surname vote: with the word in front not looked up, the word at
    the other end would vote alone (`WU Zhi`, `Zhi` a listed surname
    too). A run of capitals words in front is the family as before,
    whatever its first word (`DE SOUZA Maria`, `LI WANG Zhi`)
    (decisions/group-suggestion, 2026-11-14 #1355)."""
    return (_is_short_capitals(words[0]) and not _is_caps_word(words[1])
            and _has_lower(words))


def _capitals(words: list[str]) -> tuple[Role, Role, Role] | None:
    """A run of capitals words at one end of a name that also holds a
    lowercase letter reads as the family name, which writers set in
    capitals; two or three capitals ending the name, or opening it
    with no capitals word after them, are joined initials as often, and
    cast no vote."""
    if (not _has_lower(words) or _ends_in_short_capitals(words)
            or _opens_in_short_capitals(words)):
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


def _a_listed_name(word: str) -> bool:
    """A word the name tables list: name evidence, which is never read
    past as a title or a post-nominal (`Law`, a Cantonese surname and a
    listed title). The given-name and ORCID surname tables hold no
    listed suffix or title (their builder refuses them), and the
    romanized surname table's suffixes (`ma`, `meng`) are acronyms that
    may be a name, which are not read past bare with or without this
    test, so the post-nominal half acts on no shipped word; it holds for
    a table built otherwise."""
    return _listed(word, SURNAMES) or _listed(word, COMMON_GIVEN_NAMES)


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
    # the length first: the titles read past at the head can leave no
    # word at all (`Dr.`, `Jr.`, which H2's shape reads as a title there)
    if len(words) < 2 or _a_listed_name(words[-1]):
        return False
    word = words[-1]
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
    too), never first or second, and its three, the marker last
    whatever the words before it (#1187); rules/O1's three name words, the
    ending on the middle word (given-first) or on the last
    (`east_slavic_rotates`, the family-first shape the rule restores),
    whatever the first word ends in (a surname may end like a
    patronymic: `Abramovich Roman Arkadyevich`), and no initial first or in the middle (O1's
    precedence). A final full stop is read past.

    Both Turkic shapes count the words `_name_words` keeps, not the
    rule's name words, so they vote where the rule reads nothing: a
    nickname counted as a word (a bracketed marker among them), a given
    name P5 binds from two words, a name before a suffix comma, and a
    marker with a final full stop. The rule the vote turns on leaves
    each such name as it was (decisions/group-suggestion, 2026-11-12
    #1187)."""
    bare = [w.rstrip(".") or w for w in words]
    if (len(bare) == 4 and not any(map(is_patronymic_marker, bare[:2]))
            and (is_patronymic_marker(bare[2])
                 or is_patronymic_marker(bare[3]))):
        return PatronymicRule.TURKIC
    if len(bare) != 3:
        return None
    if is_patronymic_marker(bare[2]):
        return PatronymicRule.TURKIC
    if (not (_is_initialed(words[0]) or _is_initialed(words[1]))
            and (has_patronymic_ending(bare[1])
                 or east_slavic_rotates(bare[1], bare[2]))):
        return PatronymicRule.EAST_SLAVIC
    return None


def _patronymic_end(words: list[str]) -> tuple[Role, Role, Role]:
    """The end a name casting the East Slavic vote writes its family at,
    read where rules/O1 reads it: the ending on the middle word is the
    given-first shape (given, patronymic, family), whatever the last
    word ends in, and otherwise the patronymic stands last, the
    family-first shape the rule restores (family, given, patronymic).
    Asked only of a name `_patronymic` votes East Slavic for, three
    words long, where the ending stands on the middle word or rules/O1's
    `east_slavic_rotates` holds."""
    middle, last = (w.rstrip(".") or w for w in words[1:])
    return FAMILY_FIRST if east_slavic_rotates(middle, last) else GIVEN_FIRST


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
    base_family = off.parse(text).family
    if family != base_family:
        return "".join(_normalize(word).replace(".", "")
                       for word in family.split())
    # a comma name gives no words (_name_words), so it holds no run
    words = _name_words(text, on.lexicon)[0]
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
    if len(letters) < 2 or _normalize(base_family) != _normalize(last):
        return None
    return "".join(letters).lower()


def _read(text: str, lexicon: Lexicon
          ) -> tuple[dict[Signal, Vote], bool, list[str]]:
    """The votes one name casts, whether a comma left it out, and the
    words the signals read."""
    words, comma = _name_words(text, lexicon)
    if len(words) < 2:
        return {}, comma, words
    votes: dict[Signal, Vote] = {}

    capitals = _capitals(words)
    if capitals is not None:
        votes[Signal.CAPITALS] = capitals

    if _is_initialed(words[-1]) and not _is_initialed(words[0]):
        votes[Signal.TRAILING_INITIAL] = FAMILY_FIRST

    particle = _particle(words, lexicon)
    if particle is not None:
        votes[Signal.PARTICLE] = particle

    # a name opening in two or three capitals casts no surname vote
    # (#1355), nor does one ending in them where they spell a listed
    # surname: the ending word is looked up only to veto, so it never
    # votes alone, and the word in front votes where it does not veto
    # (#1397)
    silent = _opens_in_short_capitals(words) or (
        _ends_in_short_capitals(words)
        and _listed(words[-1], SURNAMES))
    tables = () if silent else (
        (Signal.SURNAME, SURNAMES, FAMILY_FIRST, GIVEN_FIRST),)
    for signal, table, first_order, last_order in (
            *tables,
            (Signal.GIVEN_NAME, COMMON_GIVEN_NAMES, GIVEN_FIRST, FAMILY_FIRST)):
        at_first = _listed(words[0], table)
        at_last = _listed(words[-1], table)
        if at_first != at_last:
            votes[signal] = first_order if at_first else last_order

    patronymic = _patronymic(words)
    if patronymic is not None:
        votes[Signal.PATRONYMIC] = patronymic
        if patronymic is PatronymicRule.EAST_SLAVIC:
            votes[Signal.PATRONYMIC_POSITION] = _patronymic_end(words)
    return votes, False, words


def name_votes(text: str, lexicon: Lexicon
               ) -> dict[Signal, tuple[Role, Role, Role] | PatronymicRule]:
    """The votes one name casts; empty for a name of fewer than two
    words once its titles and post-nominals are read past, and for a
    comma name, save one whose comma is followed by post-nominals
    alone. It holds no ``two_family_names`` vote, which reads the parse
    the rest of a suggestion gives."""
    # _read casts orders and rules alone: the switch's votes are cast in
    # suggest
    return cast("dict[Signal, tuple[Role, Role, Role] | PatronymicRule]",
                _read(text, lexicon)[0])


# -- the group ----------------------------------------------------------

#: A vote one signal casts: an order, the patronymic rule a shape
#: matches, or a switch's value (``two_family_names``).
Vote = tuple[Role, Role, Role] | PatronymicRule | bool
#: A setting's value as SettingEvidence holds it: an order, a set of
#: patronymic rules, or a switch (initials_as_family, capitals_as_family,
#: two_family_names).
SettingValue = tuple[Role, Role, Role] | frozenset[PatronymicRule] | bool

# The thresholds, chosen with tools/differential/suggest_measure.py
# so that a group written in its base's own order stays right in at
# least 95% of draws at every size; the measurements behind each are in
# decisions/group-suggestion, 2026-11-10 THRESHOLDS and 2026-11-11
# TRAILING INITIAL.

#: The fewest names voting for a value that can decide it.
_MIN_VOTES = 2
#: The share of the names casting an order vote that one end must hold
#: STRICTLY MORE THAN to decide the order: more than two thirds, so a
#: tie, or two names against one, decides nothing.
_MIN_SHARE = 2 / 3
#: The share of ALL the group's names, voting or not, save those a
#: comma left out (which state their own order, and which the order
#: decided reads none of), that the names voting for one end must be at
#: least to decide the order: in a long list where few names vote, two
#: stray votes are more than two thirds of the voters and would decide
#: it. At 200 names or fewer it asks no more than _MIN_VOTES does
#: (decisions/group-suggestion, 2026-11-16 ORDER FLOOR, #1442).
_MIN_ORDER_GROUP_SHARE = 0.01
#: The share of the names casting any vote that one patronymic rule
#: (East Slavic or Turkic) must hold strictly more than to decide it,
#: higher than _MIN_SHARE because a decided East Slavic rule brought a
#: given-first order with it on any base when the share was chosen;
#: since #1356 a FAMILY_FIRST base keeps its order where the
#: patronymics are mostly written last.
_MIN_PATRONYMIC_SHARE = 0.8
#: The fewest names carrying one patronymic rule that can decide it,
#: besides the share, chosen for the same reason (decisions/
#: group-suggestion, 2026-11-15 #1356, which measured what it decides
#: now).
_MIN_PATRONYMIC_VOTES = 5
#: The fewest names ending in one run of letters (rules/O8) that can
#: decide initials_as_family, and the share of the names ending in any
#: run that one run must hold at least: a list written in that
#: convention repeats its letters (Nepal's `B K` and `K C`), where a
#: list of middle and family initials or of bylines rarely does
#: (decisions/group-suggestion, 2026-11-11 LETTER RUNS).
_MIN_RUN_NAMES = 2
_MIN_RUN_SHARE = 0.5
#: A word rules/O9 reads as the family is evidence that the group writes
#: its families in capitals only where it holds at least this many
#: letters: two or three capitals are joined initials as often as a short
#: surname (`AM Hoy`, `Zhi LI`), and stay out of the evidence (#659,
#: decisions/group-suggestion, 2026-11-12 CAPITALS). The names for the
#: switch must be at least _MIN_VOTES and more than _MIN_SHARE of the
#: names with evidence either way, as for an order.
_MIN_CAPITALS_LETTERS = 4
#: The trailing-initial signal casts its votes only where the names it
#: reads are at least this many and at least _MIN_TRAILING_SHARE of the
#: group's names: a byline list ends nearly every name in initials,
#: while a South Asian or Brazilian list ends a minority that way, and
#: there the letters are the family or a middle and a family initial
#: (decisions/group-suggestion, 2026-11-11 TRAILING INITIAL, #1254).
_MIN_TRAILING_NAMES = 3
_MIN_TRAILING_SHARE = 0.6
#: two_family_names is decided where at least this many names vote for
#: it, they are more than _MIN_TWO_FAMILY_SHARE of the names the switch
#: would change, and more than the names voting against it: a list of
#: two family names writes many first surnames the table does not hold,
#: so the share is lower than an order's (decisions/group-suggestion,
#: 2026-11-19 #1452, which holds the measurement).
_MIN_TWO_FAMILY_VOTES = 3
_MIN_TWO_FAMILY_SHARE = 0.3

_NAME_ORDER = "name_order"
_PATRONYMIC_RULES = "patronymic_rules"
_INITIALS_AS_FAMILY = "initials_as_family"
_CAPITALS_AS_FAMILY = "capitals_as_family"
_TWO_FAMILY_NAMES = "two_family_names"
_SIGNAL_RANK = {signal: rank for rank, signal in enumerate(Signal)}
#: The setting each signal votes on: one setting a signal, one signal a
#: kind of vote, read by every site that tells the kinds apart
#: (decisions/group-suggestion, 2026-11-19 #1447 and #1452).
_SETTING_OF: Mapping[Signal, str] = MappingProxyType({
    Signal.CAPITALS: _NAME_ORDER, Signal.TRAILING_INITIAL: _NAME_ORDER,
    Signal.PARTICLE: _NAME_ORDER, Signal.SURNAME: _NAME_ORDER,
    Signal.GIVEN_NAME: _NAME_ORDER, Signal.PATRONYMIC: _PATRONYMIC_RULES,
    Signal.PATRONYMIC_POSITION: _NAME_ORDER,
    Signal.FIRST_SURNAME: _TWO_FAMILY_NAMES,
})


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
                     if _SETTING_OF[signal] == _NAME_ORDER)


def _offered(owner: str, signal: Signal, vote_code: str) -> str:
    """The code a refused vote's message offers, in its owner's shape: a
    NameEvidence vote is a mapping entry, a SettingEvidence row a
    triple."""
    return (f"{{Signal.{signal.name}: {vote_code}}}"
            if owner == "NameEvidence"
            else f"(Signal.{signal.name}, {vote_code}, 2)")


def _checked_vote(signal: object, vote: object,
                  owner: str = "NameEvidence") -> tuple[Signal, Vote]:
    """One (signal, vote) pair, validated: an order signal votes
    ``GIVEN_FIRST`` or ``FAMILY_FIRST``, the patronymic signal a
    ``PatronymicRule``, a ``two_family_names`` signal the switch's
    value, True or False. ``owner`` names the type in the message."""
    signal = Signal(signal)  # type: ignore[arg-type]  # ValueError names it
    setting = _SETTING_OF[signal]
    if setting == _TWO_FAMILY_NAMES:
        if not isinstance(vote, bool):
            raise TypeError(
                f"{owner} vote for {signal.value!r} must be True or False, "
                f"got {vote!r}; pass e.g. {_offered(owner, signal, 'True')}")
        return signal, vote
    if setting == _PATRONYMIC_RULES:
        if not isinstance(vote, PatronymicRule):
            raise TypeError(
                f"{owner} vote for {signal.value!r} must be a "
                f"PatronymicRule, got {vote!r}; pass e.g. "
                f"{_offered(owner, signal, 'PatronymicRule.EAST_SLAVIC')}")
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


#: A ``by_signal`` row each setting takes, which a refused row's message
#: offers: one whose signal votes on that setting
_ROW_EXAMPLE: Mapping[str, str] = MappingProxyType({
    _NAME_ORDER: "(Signal.SURNAME, FAMILY_FIRST, 2)",
    _PATRONYMIC_RULES: "(Signal.PATRONYMIC, PatronymicRule.EAST_SLAVIC, 2)",
    _TWO_FAMILY_NAMES: "(Signal.FIRST_SURNAME, True, 2)",
})


def _checked_row(row: object, setting: str) -> tuple[Signal, Vote, int]:
    """One ``by_signal`` row, validated: ``(signal, vote, count)``, its
    signal one that votes on ``setting``."""
    if isinstance(row, (str, bytes)) or not isinstance(row, (tuple, list)) \
            or len(row) != 3:
        raise TypeError(
            f"SettingEvidence by_signal rows must be (signal, vote, count) "
            f"triples, got {reprlib.repr(row)}; "
            + (f"pass e.g. {_ROW_EXAMPLE[setting]}" if setting in _ROW_EXAMPLE
               else f"no signal votes on {setting}, so pass by_signal=()"))
    signal, vote, count = row
    pair = _checked_vote(signal, vote, "SettingEvidence by_signal")
    if _SETTING_OF[pair[0]] != setting:
        raise ValueError(
            f"SettingEvidence by_signal row {reprlib.repr(row)} is a "
            f"{pair[0].value!r} vote, which votes on {_SETTING_OF[pair[0]]}, "
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
    parser's lexicon. A name with a comma, save one whose comma only
    post-nominals follow (``Kim Minjun, PhD``), and a name of no words
    or one word cast none, and a name that casts none never disagrees
    with the group.
    Order votes are one per NAME: the end the name's order signals
    agree on. A name whose order signals point at both ends is
    contested, casts no order vote and never disagrees on order.
    ``votes`` holds the votes keyed by signal: an order vote is the
    order it votes for (``GIVEN_FIRST`` or ``FAMILY_FIRST``), a
    patronymic vote the ``PatronymicRule``, and a first-surname vote
    ``True`` or ``False``, cast only where ``two_family_names`` is
    weighed (not where the base has it on or an East Slavic rule is
    decided). It keeps every signal's vote all the same, save a
    trailing-initial vote the group did not cast: too few of its names
    ending in initials (``Parser.suggest``), or its runs of letters
    decided ``initials_as_family``, whose letters are its family.
    ``family_in_capitals`` is the name's evidence on
    ``capitals_as_family`` (rules/O9), which is no per-signal vote:
    True where it writes its family in capitals, False where it is in
    mixed case with no word in capitals, None where it carries none.
    ``dataclasses.replace`` keeps the votes unless it is passed
    ``votes=`` too."""

    #: The name exactly as the caller passed it.
    text: str
    # the votes as (Signal, vote) pairs in Signal's order: a tuple, so
    # the type stays frozen, hashable and picklable; read it through
    # the `votes` property
    _votes: tuple[tuple[Signal, Vote], ...]
    #: The name's evidence on ``capitals_as_family``: True, False or None.
    family_in_capitals: bool | None = dataclasses.field(
        default=None, metadata={ADDED_IN: "3.1.0"})

    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __init__(self, text: str,
                 votes: Mapping[Signal, Vote] | None = None, *,
                 family_in_capitals: bool | None = None,
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
        if family_in_capitals is not None and not isinstance(
                family_in_capitals, bool):
            raise TypeError(
                f"NameEvidence family_in_capitals must be True, False or "
                f"None, got {family_in_capitals!r}; pass e.g. "
                f"NameEvidence('Jean DUPONT', {{}}, family_in_capitals=True)")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "_votes", pairs)
        object.__setattr__(self, "family_in_capitals", family_in_capitals)

    def __repr__(self) -> str:
        votes = "".join(f", {signal.value}={_label(vote)}"
                        for signal, vote in self._votes)
        capitals = ("" if self.family_in_capitals is None else
                    f", family_in_capitals={self.family_in_capitals}")
        return f"NameEvidence({self.text!r}{votes}{capitals})"

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
    #: The names whose vote is for ``value``.
    votes_for: int
    #: The names whose vote is for another value.
    votes_against: int
    #: The names whose signals point both ways on this setting, and so
    #: cast no vote.
    contested: int
    #: The names with no signal on this setting.
    no_evidence: int
    #: The signals' own votes as ``(signal, vote, count)`` rows; a name
    #: two signals read is in two of them.
    by_signal: tuple[tuple[Signal, Vote, int], ...]
    #: Why the setting was decided or left undecided as it was, where
    #: not empty.
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
                         (f"({_ROW_EXAMPLE[self.setting]},) or ()"
                          if self.setting in _ROW_EXAMPLE else "()"))
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
    duplicates included. ``str()`` is a readable report.

    A suggestion is one release's reading of the group: the tables and
    thresholds behind it change between releases, so keep the ``patch``
    applied (or the ``parser``'s ``Policy``) with the data rather than
    calling ``suggest`` again and expecting the same one."""

    #: The parser ``suggest`` was called on.
    base: Parser
    #: The settings the group decided that differ from the base's.
    patch: PolicyPatch
    #: One :class:`SettingEvidence` per setting considered.
    evidence: tuple[SettingEvidence, ...]
    #: One :class:`NameEvidence` per input name, in input order, blanks and
    #: duplicates included.
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
        are contested, never disagrees on order; a name in mixed case
        with no word in capitals disagrees with a decided
        ``capitals_as_family``; a name whose father's name the switch
        would take disagrees with a decided ``two_family_names``; and a
        name carrying an
        East Slavic patronymic never disagrees on order where the East
        Slavic rule is decided with a given-first order, since the rule
        reorders it there."""
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


def _disagrees(name: NameEvidence, decided: Mapping[str, object]) -> bool:
    """Whether one name's votes contradict a decided setting."""
    if (decided.get(_CAPITALS_AS_FAMILY) is True
            and name.family_in_capitals is False):
        return True
    votes = dict(name._votes)
    if (decided.get(_TWO_FAMILY_NAMES) is True
            and votes.get(Signal.FIRST_SURNAME) is False):
        return True
    patronymic = votes.get(Signal.PATRONYMIC)
    rules = decided.get(_PATRONYMIC_RULES)
    if (rules is not None and patronymic is not None
            and patronymic not in rules):  # type: ignore[operator]
        return True
    order = decided.get(_NAME_ORDER)
    if order is None:
        return False
    # a decided rule holds the name's patronymic by now
    if (rules is not None and patronymic is PatronymicRule.EAST_SLAVIC
            and _end(order) == GIVEN_FIRST):  # type: ignore[arg-type]
        return False
    ends = _order_ends(name._votes)
    return len(ends) == 1 and next(iter(ends)) != _end(order)  # type: ignore[arg-type]


class _Tally:
    """The group's votes on one setting, one per name, gathered in one
    pass. A plain class rather than a dataclass: it is never pickled or
    returned."""

    __slots__ = ("names", "left_out", "contested", "by_name", "by_signal")

    def __init__(self) -> None:
        self.names = 0
        #: names a comma left out (`_comma_note`), which cast no vote
        self.left_out = 0
        self.contested = 0
        #: names per value voted for
        self.by_name: Counter[Vote] = Counter()
        #: signal votes per (signal, value)
        self.by_signal: Counter[tuple[Signal, Vote]] = Counter()

    def add(self, pairs: list[tuple[Signal, Vote]], left_out: bool = False
            ) -> None:
        """One name's votes on this setting: its signals' votes, and
        one name vote where they agree. ``left_out`` is a name a comma
        left out."""
        self.names += 1
        self.left_out += left_out
        for pair in pairs:
            self.by_signal[pair] += 1
        values = {vote for _, vote in pairs}
        if len(values) == 1:
            self.by_name[values.pop()] += 1
        elif values:
            self.contested += 1

    def winner(self) -> Vote | None:
        """The value whose names are at least _MIN_VOTES, strictly
        more than _MIN_SHARE of the names that cast a vote and at least
        _MIN_ORDER_GROUP_SHARE of the group's names a comma did not
        leave out, if one is."""
        end = self.top(_MIN_VOTES, _MIN_SHARE, sum(self.by_name.values()))
        return None if end is None or self._short_of_group(end) else end

    def held_back(self) -> Vote | None:
        """The value the votes would decide but for
        _MIN_ORDER_GROUP_SHARE, if one is."""
        end = self.top(_MIN_VOTES, _MIN_SHARE, sum(self.by_name.values()))
        return end if end is not None and self._short_of_group(end) else None

    def _short_of_group(self, end: Vote) -> bool:
        # a name a comma left out states its own order, and the order
        # decided reads none of them, so it is no name of the floor's
        return (self.by_name[end]
                < _MIN_ORDER_GROUP_SHARE * (self.names - self.left_out))

    def top(self, min_votes: int, min_share: float, total: int
            ) -> Vote | None:
        """The value most names voted for, where they are at least
        ``min_votes`` and strictly more than ``min_share`` of
        ``total``."""
        if not self.by_name:
            return None
        vote, count = max(self.by_name.items(), key=lambda item: item[1])
        if count < min_votes or count <= min_share * total:
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
    return tally.top(  # type: ignore[return-value]
        _MIN_PATRONYMIC_VOTES, _MIN_PATRONYMIC_SHARE, any_voters)


def _decide_patronymic(tally: _Tally, base_rules: frozenset[PatronymicRule],
                       any_voters: int,
                       written_last: tuple[int, int] | None = None
                       ) -> tuple[SettingEvidence, dict[str, object], bool]:
    """Decide ``patronymic_rules``: the evidence, the patch fields, and
    whether the decided rule needs a given-first order. ``written_last``
    is given where a decided East Slavic rule keeps the base's
    ``FAMILY_FIRST`` order (`_keeps_family_first`): how many of its
    voters write the patronymic last and how many in the middle."""
    rule = _patronymic_winner(tally, any_voters)
    if rule is PatronymicRule.EAST_SLAVIC and written_last is not None:
        return (*_rule_decided(tally, base_rules, rule,
                               _kept_order_note(*written_last)), False)
    if rule is PatronymicRule.EAST_SLAVIC:
        # the rule reorders a family-first East Slavic name itself, and
        # its reordering stands down under a declared family-first
        # order, so the group gets the rule with a given-first order
        # (what locales.RU ships)
        return (*_rule_decided(tally, base_rules, rule), True)
    if rule is PatronymicRule.TURKIC:
        # unlike the East Slavic rule it reads a name written either way
        # round (``Mamedov Ali Huseyn oglu`` and ``Ali Huseyn oglu
        # Mamedov`` both read family Mamedov), so it forces no order:
        # the order is decided from the names' own votes
        # (decisions/group-suggestion, 2026-11-10 TURKIC)
        return (*_rule_decided(tally, base_rules, rule), False)
    return (tally.evidence(_PATRONYMIC_RULES, base_rules, False,
                           lambda v: v in base_rules), {}, False)


def _rule_decided(tally: _Tally, base_rules: frozenset[PatronymicRule],
                  rule: PatronymicRule, note: str = ""
                  ) -> tuple[SettingEvidence, dict[str, object]]:
    """The evidence and patch fields for a decided ``rule``: the value
    the base's rules with it, the patch the rule alone where the base
    lacks it (``patronymic_rules`` composes by union)."""
    value = base_rules | {rule}
    fields: dict[str, object] = (
        {} if rule in base_rules else {_PATRONYMIC_RULES: frozenset({rule})})
    return (tally.evidence(_PATRONYMIC_RULES, value, True,
                           lambda v: v in value, note), fields)


def _kept_order_note(last: int, middle: int) -> str:
    """The note on an East Slavic rule decided under a ``FAMILY_FIRST``
    base the names' own votes do not move (`_keeps_family_first`): the
    group gets the rule and no order. That order reads a name written
    family, given, patronymic already, and under it the rule reorders
    no name and fills the ``patronymic`` view (`Sidorov Ivan
    Petrovich`); a given-first order would read the list's names
    without a patronymic family-last (`Aliyev Farrukh`). The names that
    write the patronymic in the middle get no given-first order, and
    the note says how many (decisions/group-suggestion, 2026-11-15
    #1356)."""
    note = (f"the base's family-first order is kept: {last} of the "
            f"{last + middle} names carrying the patronymic write it "
            f"last, as a list written family first does, and the rule "
            f"reorders none of them")
    if middle:
        # true whatever else the patch turns on: capitals_as_family,
        # suggested beside it, may read these names all the same
        verb, gets = ("writes", "gets") if middle == 1 else ("write", "get")
        note += (f"; the {middle} that {verb} it in the middle {gets} "
                 f"no given-first order from this suggestion")
    return note


def _keeps_family_first(
        policy: Policy, order_end: Vote | None,
        with_words: list[tuple[str, dict[Signal, Vote], bool, list[str]]]
        ) -> tuple[int, int] | None:
    """Whether a decided East Slavic rule would keep this base's order,
    and if so how many of its voters write the patronymic last and how
    many in the middle; None where the rule decides the order as
    given-first, as it does on every other base.

    The order is kept only under ``FAMILY_FIRST``, only where the names'
    own votes do not decide a given-first order, and only where MORE of
    the names casting the East Slavic vote write the patronymic last
    (family, given, patronymic: rules/O1's family-first shape) than in
    the middle (given, patronymic, family); a tie is not kept. A name
    with the ending on both its middle and its last word counts as
    middle, as rules/O1 reads it. ``FAMILY_FIRST_GIVEN_LAST`` is never
    kept: that order takes the patronymic of such a list for the given
    name; the names' position votes give it ``FAMILY_FIRST``
    (`_decide_order`), and where they decide no order the given-first
    order with the rule reads it. The names are counted by their
    ``PATRONYMIC_POSITION`` votes, cast beside every East Slavic one."""
    if policy.name_order != FAMILY_FIRST or order_end == GIVEN_FIRST:
        return None
    ends = Counter(votes.get(Signal.PATRONYMIC_POSITION)
                   for _, votes, _, _ in with_words)
    last, middle = ends[FAMILY_FIRST], ends[GIVEN_FIRST]
    return (last, middle) if last > middle else None


def _comma_note(left_out: int) -> str:
    if not left_out:
        return ""
    noun = "name with a comma was" if left_out == 1 else "names with a comma were"
    return (f"{left_out} {noun} left out: a comma states its own order, "
            f"so only a comma followed by post-nominals alone is read past")


def _floor_note(tally: _Tally, rule_decides: bool) -> str:
    """The note on votes _MIN_ORDER_GROUP_SHARE held back: where they
    alone leave the order undecided, and where a decided East Slavic
    rule sets the given-first order they voted against. None where the
    rule sets the order they voted for, which they did not decide."""
    end = tally.held_back()
    if end is None or (rule_decides and end == GIVEN_FIRST):
        return ""
    counted = tally.names - tally.left_out
    whose = (f"of the group's {counted} names" if not tally.left_out else
             f"of the {counted} names no comma left out")
    floor = (f"an order is decided where the names voting for one end are "
             f"at least {_MIN_ORDER_GROUP_SHARE:.0%} of those names")
    if rule_decides:
        return (f"{tally.by_name[end]} {whose} vote {_label(end)}, too few "
                f"to decide that order against the rule: {floor}")
    return (f"{tally.by_name[end]} {whose} vote {_label(end)}, too few to "
            f"decide the order: {floor}")


def _decide_order(tally: _Tally, base_order: tuple[Role, Role, Role],
                  rule_needs_given_first: bool, comma_left_out: int,
                  trailing_note: str = ""
                  ) -> tuple[SettingEvidence, dict[str, object]]:
    """Decide ``name_order`` in either direction. A family-first answer
    keeps the base's family-first spelling where the base has one,
    unless an East Slavic rule is decided (below). A
    decided East Slavic rule decides the order as given-first, since
    the rule reorders each name and reorders none under a family-first
    order, unless the names' own votes decide family-first: a decided
    order is never overridden, and the rule then reorders no name. There
    a ``FAMILY_FIRST_GIVEN_LAST`` base gets ``FAMILY_FIRST``, whose
    reading the rule leaves as written (`Popov Ivan Ivanovich`, given
    `Ivan`); its own spelling would read the patronymic as the given name
    (decisions/group-suggestion, 2026-11-19 #1364). A
    rule that keeps a ``FAMILY_FIRST`` base's order
    (`_keeps_family_first`) is not passed here: the order is then the
    votes' or the base's."""
    end = tally.winner()
    notes = [_comma_note(comma_left_out),
             _floor_note(tally, rule_needs_given_first and end is None),
             trailing_note]
    if rule_needs_given_first and end != FAMILY_FIRST:
        end = GIVEN_FIRST
        notes.insert(0, "the East Slavic rule reorders each name; it needs "
                        "a given-first order")
    elif rule_needs_given_first:
        notes.insert(0, "the East Slavic rule is decided too, but the names' "
                        "order votes decide a family-first order, under "
                        "which the rule reorders no name")
    note = "; ".join(n for n in notes if n)
    if end is None:
        return (tally.evidence(_NAME_ORDER, base_order, False,
                               lambda v: v == _end(base_order), note), {})
    # the order tally holds orders alone; a decided East Slavic rule
    # takes the end's own spelling, the base's spelling of it otherwise
    order = (cast("tuple[Role, Role, Role]", end)
             if rule_needs_given_first or _end(base_order) != end
             else base_order)
    fields: dict[str, object] = (
        {} if order == base_order else {_NAME_ORDER: order})
    return (tally.evidence(_NAME_ORDER, order, True,
                           lambda v: v == end, note), fields)


def _texts(names: Iterable[str]) -> Iterator[str]:
    """The names, checked as they are consumed: one pass, so a
    generator is read once."""
    example = 'parser.suggest(["Smith Mary", "Kim Minjun"])'
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


def _quiet(parser: Parser, policy: Policy) -> Parser:
    """``parser`` reading under ``policy``, its construction warnings
    silenced: they read only ``segment_scripts``, the lexicon and the
    segmenter, which these policies never change from the base's, so
    they are the base's own, which reached its caller when it was
    built."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return dataclasses.replace(parser, policy=policy)


def _letter_readers(parser: Parser) -> tuple[Parser, Parser]:
    """The base with the switch on and off, every other setting the
    base's own save the fold of every middle into the family (rules/O3),
    which takes the letters there too and so would hide the run the
    switch reads. Asked only of a base reading names given first, where
    the rule acts."""
    policy = dataclasses.replace(parser.policy, middle_as_family=False)
    return (_quiet(parser, dataclasses.replace(policy, initials_as_family=True)),
            _quiet(parser, dataclasses.replace(policy, initials_as_family=False)))


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


def _capitals_reader(parser: Parser) -> Parser:
    """The base with rules/O9's switch on, every other setting the
    base's own. Never asked of a base reading an unlisted capitals word
    as a credential everywhere, beside which the switch cannot be set."""
    return _quiet(parser, dataclasses.replace(parser.policy,
                                              capitals_as_family=True))


def _capitals_family(text: str, words: list[str], base: Parser,
                     reader: Callable[[], Parser]) -> bool | None:
    """One name's evidence on ``capitals_as_family``.

    True where rules/O9, asked of the parse itself with the switch on,
    reads as the family a word of at least _MIN_CAPITALS_LETTERS letters
    that the lexicon lists as no credential or numeral, and that the
    base, parsing the name itself, does not read as a title. False
    where the switch would move the family onto any word the base reads
    as a title (`MISS Ann Berg`, `DR DUPONT Jean`), and where the words the signals read (`words`) are two or
    more, hold an uppercase and a lowercase letter and none is in
    capitals: a title or a credential they are read past leaves such a
    name (`DR Ann Berg`, `Prof. Ann Berg`, `John Smith FRCS`). None
    otherwise: a name in one case, a run of two or three capitals (`Zhi
    LI`), a credential the name is not read past (`Mary Jones MBA`, a
    name too), a family comma, a name of one word.

    A word is a title by the base's own reading of the name, so a
    surname the vocabulary also lists as a title counts as the family
    the base reads it as (`Mary BISHOP`); the base parse is asked only
    where a word of the family the switch reads is a listed title. A
    word in capitals ending in a full stop is no capitals word to the
    rule, so a name holding one carries none (`Ann Berg DUPONT.`). Only a name
    holding a word in capitals is parsed, its words cut at commas and
    read past quotes and brackets as `_name_words` reads them. The loops
    are plain and their per-character tests C-level, so a name with no
    word holding two capitals costs this one call: the group suggester
    parses no name of a list with none."""
    # a capitals word holds two capitals at least
    if any(sum(map(str.isupper, word)) >= 2
           and is_capitals_word(word.strip(_EDGES).rstrip("."))
           for word in _COMMAS.split(text)):
        lexicon = base.lexicon
        sets = lexicon._sets
        family = []
        counted = False
        listed = False
        for token in reader().parse(text).tokens:
            if token.role is not Role.FAMILY:
                continue
            family.append(token)
            # rules/O9's family: a family word read by its shape is a
            # word of the run in capitals (a particle the run took reads
            # by vocabulary, a family comma's by position)
            counted = counted or (
                token.reading is not None
                and token.reading.source is ReadingSource.SHAPE
                and sum(map(str.isalpha, token.text))
                >= _MIN_CAPITALS_LETTERS
                and not _listed_suffix(token.text, lexicon))
            # a title of any kind the vocabulary lists (a modifier and a
            # style compile into the titles, a word that is also a given
            # name into the ambiguous titles instead): only such a word
            # may be the base's title, so only it costs the base parse
            word = _normalize(token.text)
            listed = listed or (
                word in sets.titles or word in sets.titles_ambiguous)
        if counted:
            if listed:
                titles = {token.span for token in base.parse(text).tokens
                          if token.role is Role.TITLE}
                # the switch would move the family onto a word the base
                # reads as a title (`DR DUPONT Jean`, `MISS Ann Berg`)
                return not any(token.span in titles for token in family)
            return True
        for word in words:
            # a word in capitals the rule reads as no family, a final
            # full stop read past (`Ann Berg DUPONT.`)
            if is_capitals_word(word.rstrip(".")):
                return None
    if len(words) < 2:
        return None
    if not (_has_lower(words) and any(c.isupper() for w in words for c in w)):
        return None
    return False


def _decide_capitals(marks: list[bool | None], base: Policy
                     ) -> tuple[SettingEvidence, dict[str, object]]:
    """Decide ``capitals_as_family`` (rules/O9): true where at least
    _MIN_VOTES names write the family in capitals and more than
    _MIN_SHARE of the names with evidence either way do. A group never
    decides it false: a name with no capitals is no evidence that a
    list does not write them, the rule reading only a name that holds
    some. Nor does anything decide it under a base reading an unlisted
    capitals word as a credential everywhere, beside which the switch
    cannot be set."""
    base_value = base.capitals_as_family
    if base.unlisted_caps_suffixes is CapsSuffixes.EVERYWHERE:
        return (SettingEvidence(
            _CAPITALS_AS_FAMILY, base_value, False, 0, 0, 0, len(marks), (),
            "not read: the base reads an unlisted word in capitals as a "
            "credential everywhere (unlisted_caps_suffixes=EVERYWHERE), "
            "beside which capitals_as_family cannot be set"), {})
    written = marks.count(True)
    plain = marks.count(False)
    if not written and not plain:
        return (SettingEvidence(_CAPITALS_AS_FAMILY, base_value, False,
                                0, 0, 0, len(marks), ()), {})
    decided = (written >= _MIN_VOTES
               and written > _MIN_SHARE * (written + plain))
    value = True if decided else base_value
    votes_for, votes_against = (written, plain) if value else (plain, written)
    # said where a name writes it: a list with none is the common case,
    # and its counts say what it showed
    noun = "name" if written + plain == 1 else "names"
    verb = "writes" if written == 1 else "write"
    note = (f"{written} of the {written + plain} {noun} with evidence "
            f"{verb} the family in capitals of {_MIN_CAPITALS_LETTERS} "
            f"letters or more, {plain} in mixed case with no capitals"
            if written else "")
    fields: dict[str, object] = (
        {_CAPITALS_AS_FAMILY: True} if decided and not base_value else {})
    return (SettingEvidence(_CAPITALS_AS_FAMILY, value, decided, votes_for,
                            votes_against, 0,
                            len(marks) - written - plain, (), note), fields)


def _counts_as_initialed(votes: Mapping[Signal, Vote]) -> bool:
    """Whether a name counts toward the trailing-initial share: its
    trailing initial is its only order evidence or agrees with the rest
    of it, so a name whose listed given name contradicts it (`Anna R S`)
    does not count."""
    return (Signal.TRAILING_INITIAL in votes
            and len(_order_ends(votes.items())) == 1)


def _trailing_initials_vote(
        with_words: list[tuple[str, dict[Signal, Vote], bool, list[str]]]
        ) -> tuple[bool, str]:
    """Whether the group's trailing-initial votes are cast, and the note
    saying so where they are not. One rule at every count: where any
    name casts one, they are cast only where at least _MIN_TRAILING_NAMES
    names, and _MIN_TRAILING_SHARE of the group's names, count as
    initialed (_counts_as_initialed). The group is the names that hold
    a word with a letter or a digit once their titles and post-nominals
    are read past, as _name_words reads them: a blank, a mark, a
    zero-width character alone (`\u200b`), a name of nothing but titles
    and a name a comma left out (which _name_words gives no word) are
    no names of the group."""
    if not any(Signal.TRAILING_INITIAL in votes
               for _, votes, _, _ in with_words):
        return True, ""
    group = initialed = 0
    for _, votes, _, words in with_words:
        if not any(c.isalnum() for word in words for c in word):
            continue
        group += 1
        initialed += _counts_as_initialed(votes)
    if (initialed >= _MIN_TRAILING_NAMES
            and initialed >= _MIN_TRAILING_SHARE * group):
        return True, ""
    verb = "ends" if initialed == 1 else "end"
    return False, (
        f"{initialed} of the group's {group} names {verb} in initials no "
        f"other signal contradicts, too few for the trailing-initial "
        f"signal to vote: it votes where at least {_MIN_TRAILING_NAMES} "
        f"names and {_MIN_TRAILING_SHARE:.0%} of the group do")


def _two_family_note(base: Policy, rest: Policy) -> str:
    """Why ``two_family_names`` is not weighed under ``rest``, the policy
    the other settings suggest on ``base``, or "" where it is: it is
    weighed only where the base's switch is off and the rest reads
    given-first with the East Slavic rule off (decisions/group-suggestion,
    2026-11-19 #1452)."""
    if base.two_family_names:
        return "not read: the base reads two family names already"
    if PatronymicRule.EAST_SLAVIC in rest.patronymic_rules:
        return ("not read: the East Slavic rule is on, and the switch "
                "would read a patronymic as a first surname")
    if rest.name_order != GIVEN_FIRST:
        return ("not read: the order is family-first, and two family "
                "names are weighed under a given-first order alone")
    return ""


def _two_family_votes(
        with_words: list[tuple[str, dict[Signal, Vote], bool, list[str]]],
        reader: Parser) -> tuple[list[dict[Signal, Vote]], int, int]:
    """Each name's votes on ``two_family_names``, read where rules/O6
    reads it: the parse itself is asked, under ``reader`` (the parser the
    rest of the suggestion gives) with the switch off and on, and a name
    the switch moves is one whose family it changes, every name of the
    group with a middle name asked. Where such a name has no comma and
    three name words or more, the last word the switch takes into its family votes
    (`Signal.FIRST_SURNAME`): for the switch where it is a common
    surname of the ORCID table, against it where it is a patronymic or
    its marker, a father's name the switch would read as a first
    surname, and not at all where it is a common given name, the second
    given name the switch would take (`COMMON_GIVEN_NAMES`). Returns the
    votes, the names the switch moves and the names whose taken word is
    a listed given name."""
    on = _quiet(reader, dataclasses.replace(reader.policy,
                                            two_family_names=True))
    out: list[dict[Signal, Vote]] = []
    moved = vetoed = 0
    for text, _, comma, words in with_words:
        votes: dict[Signal, Vote] = {}
        out.append(votes)
        # every name the switch changes counts in the share, a comma name
        # and one whose words the signals do not split included; only a
        # name they read casts a vote
        off = reader.parse(text)
        if not off.middle:
            # the switch takes the word before the family from the
            # middle, so a name with none is one it leaves as it is
            continue
        off_family, on_family = off.family, on.parse(text).family
        if on_family == off_family:
            continue
        moved += 1
        if (comma or len(words) < 3
                or not on_family.endswith(" " + off_family)):
            continue
        word = on_family.removesuffix(off_family).split()[-1]
        bare = word.rstrip(".") or word
        if is_patronymic_marker(bare) or has_patronymic_ending(bare):
            # a father's name or its marker, never a first surname
            votes[Signal.FIRST_SURNAME] = False
        elif _listed(word, COMMON_GIVEN_NAMES):
            vetoed += 1
        elif _listed(word, COMMON_SURNAMES):
            votes[Signal.FIRST_SURNAME] = True
    return out, moved, vetoed


def _decide_two_family_names(
        votes: list[dict[Signal, Vote]], moved: int, vetoed: int,
        base_value: bool, note: str
        ) -> tuple[SettingEvidence, dict[str, object]]:
    """Decide ``two_family_names`` (rules/O6): true where at least
    _MIN_TWO_FAMILY_VOTES names vote for it and they are more than
    _MIN_TWO_FAMILY_SHARE of the names the switch would move, and more
    than the names it would read a father's name in as a first surname.
    A group never decides it false. ``note`` says why it was not
    weighed, and is empty where it was, a group no name of which the
    switch moves included."""
    # a name casts one vote at most, so the tally counts names
    tally = _Tally()
    for v in votes:
        tally.add(list(v.items()))
    if note or not moved:
        return (tally.evidence(_TWO_FAMILY_NAMES, base_value, False,
                               lambda v: v == base_value, note), {})
    voters, fathers = tally.by_name[True], tally.by_name[False]
    decided = (voters >= _MIN_TWO_FAMILY_VOTES
               and voters > _MIN_TWO_FAMILY_SHARE * moved
               and voters > fathers)
    value = True if decided else base_value
    noun = "name" if moved == 1 else "names"
    text = (f"{voters} of the {moved} {noun} two_family_names would "
            f"change carry a common surname where it would take a first "
            f"surname")
    if vetoed:
        text += (f"; {vetoed} of them a common given name there, which "
                 f"casts no vote")
    if fathers:
        text += (f"; {fathers} a father's name there, which it would read "
                 f"as a first surname")
    fields: dict[str, object] = (
        {_TWO_FAMILY_NAMES: True} if decided and not base_value else {})
    # counted for and against the value kept, as the other switches are
    return (tally.evidence(_TWO_FAMILY_NAMES, value, decided,
                           lambda v: v == value, text), fields)


def suggest(parser: Parser, names: Iterable[str]) -> Suggestion:
    """The settings a group of names suggests, with ``parser`` as the
    base: see :meth:`Parser.suggest`."""
    tallies = {_NAME_ORDER: _Tally(), _PATRONYMIC_RULES: _Tally()}
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
    with_words = [(text, *_read(text, parser.lexicon)) for text in texts]
    capitals_parser: list[Parser] = []

    def capitals_reader() -> Parser:
        # built once, and only for a group holding a word in capitals
        if not capitals_parser:
            capitals_parser.append(_capitals_reader(parser))
        return capitals_parser[0]

    if parser.policy.unlisted_caps_suffixes is CapsSuffixes.EVERYWHERE:
        # the switch cannot be set beside it: no name is read for it
        marks: list[bool | None] = [None] * len(texts)
    else:
        marks = [_capitals_family(text, words, parser, capitals_reader)
                 for text, _, _, words in with_words]
    capitals, capitals_fields = _decide_capitals(marks, parser.policy)
    if letters_are_family:
        # the group's letters are its family (rules/O8), so a name
        # ending in letters is no evidence of a family-first order
        trailing_votes, trailing_note = False, (
            "the trailing-initial signal casts no vote: the group's "
            "letters are its family (initials_as_family)")
    else:
        trailing_votes, trailing_note = _trailing_initials_vote(with_words)
    set_aside = 0
    for (text, votes, comma, _), mark in zip(with_words, marks):
        # counted before a set-aside vote leaves it: a name ending in
        # initials carries evidence all the same, and leaving it out of
        # the patronymic share's denominator lets one rule win a group
        # of family-first names written with a patronymic initial
        # (`Popov Ivan I.`, PatentsView's Russian inventors)
        any_voters += bool(votes)
        if not trailing_votes and Signal.TRAILING_INITIAL in votes:
            del votes[Signal.TRAILING_INITIAL]
            set_aside += not votes
        comma_left_out += comma
        per_setting: dict[str, list[tuple[Signal, Vote]]] = {
            setting: [] for setting in tallies}
        for signal, vote in votes.items():
            per_setting[_SETTING_OF[signal]].append((signal, vote))
        for setting, tally in tallies.items():
            tally.add(per_setting[setting], comma)
    policy = parser.policy
    # a FAMILY_FIRST base keeps its order where the group's East Slavic
    # patronymics are mostly written last (#1356)
    patronymic, patronymic_fields, settled = _decide_patronymic(
        tallies[_PATRONYMIC_RULES], policy.patronymic_rules, any_voters,
        _keeps_family_first(policy, tallies[_NAME_ORDER].winner(),
                            with_words))
    if set_aside and any(Signal.PATRONYMIC in votes
                         for _, votes, _, _ in with_words):
        # the evidence says what its share was taken of: the names a
        # set-aside vote left with none still count among those casting
        # one, and show as no evidence
        counted = ("1 name whose only vote was a set-aside trailing "
                   "initial counts" if set_aside == 1 else
                   f"{set_aside} names whose only vote was a set-aside "
                   f"trailing initial count")
        patronymic = dataclasses.replace(patronymic, note="; ".join(
            n for n in (patronymic.note,
                        f"{counted} among the names casting a vote, the "
                        f"share's denominator") if n))
    order, order_fields = _decide_order(
        tallies[_NAME_ORDER], policy.name_order, settled, comma_left_out,
        trailing_note)
    fields = {**order_fields, **patronymic_fields, **letter_fields,
              **capitals_fields}
    # the policy the other settings suggest, which the switch's votes
    # are read under
    rest = apply_patch(policy, PolicyPatch(**fields))  # type: ignore[arg-type]
    two_note = _two_family_note(policy, rest)
    if two_note:
        family_votes: list[dict[Signal, Vote]] = [{} for _ in texts]
        moved = vetoed = 0
    else:
        family_votes, moved, vetoed = _two_family_votes(
            with_words, _quiet(parser, rest))
    two_family, two_fields = _decide_two_family_names(
        family_votes, moved, vetoed, policy.two_family_names, two_note)
    fields.update(two_fields)
    evidence = [NameEvidence(text, {**votes, **extra},
                             family_in_capitals=mark)
                for (text, votes, _, _), mark, extra
                in zip(with_words, marks, family_votes)]
    patch = PolicyPatch(**fields)  # type: ignore[arg-type]
    return Suggestion(parser, patch,
                      (order, patronymic, letters, capitals, two_family),
                      tuple(evidence))

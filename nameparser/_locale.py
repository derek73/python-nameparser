"""The Locale type: a named delta over (Lexicon, Policy), with a
choice of languages.

A Locale dissolves at parser construction (parser_for): the packs'
languages are unioned into one choice, which selects among the default
vocabulary's readings by the file each sits in, the lexicon fragments
union onto the result, and the PolicyPatch folds via apply_patch. Packs
are pure data; they have no privileged capabilities
(mechanisms.md#LOCALE-PACKS-PURE-DATA).

Layering: imports _types, _lexicon and _policy only, and the compiled
[rules] tables, nameparser/config/_rules.py, at call time (enforced by
tests/v2/test_layering.py).
"""
from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from nameparser._lexicon import Lexicon
from nameparser._policy import (
    _ORDER_CONSTANT_NAMES, UNSET, PatronymicRule, PolicyPatch,
    _reject_str_and_mapping,
)
from nameparser._types import ADDED_IN, _guarded_getstate, _guarded_setstate

# a BCP 47 tag's shape: a language subtag and any number of subtags
# after it; whether a vocabulary file holds it is parser_for's question,
# asked of the reading index when the choice is applied
_TAG = re.compile(r"[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*")


@dataclass(frozen=True, slots=True)
class Locale:
    """A named, shareable bundle of vocabulary and behavior for a
    naming tradition: a lexicon fragment plus a policy patch, applied
    together by :func:`nameparser.parser_for`. The packs shipped with
    nameparser live in :mod:`nameparser.locales`; building your own
    needs no registration -- construct one and pass it to
    ``parser_for``. See the :doc:`locale packs guide </locales>` for
    using, creating, and contributing packs."""

    #: Identifier, lowercase ``[a-z0-9_]+`` (e.g. "ru", "tr_az").
    code: str
    #: Vocabulary ADDED to the base parser's lexicon (unioned after the
    #: choice in ``languages``; the fragment never removes base
    #: vocabulary, where a choice selects among the default's readings).
    lexicon: Lexicon
    #: Behavior changes folded onto the base policy (set-valued fields
    #: union; scalars override, later pack wins).
    policy: PolicyPatch = PolicyPatch()
    #: The languages chosen, as BCP 47 tags (``{"pt"}``, ``{"pt-BR"}``):
    #: ``parser_for`` unions the packs' languages into one choice, which
    #: turns on the chosen languages' readings the default leaves off
    #: and, on a word a chosen language holds a vocabulary reading of,
    #: drops other languages' vocabulary readings. A tag selects its own
    #: vocabulary file and its ancestors' (``pt-BR`` selects ``pt``
    #: too), never its descendants'. Empty, the default, chooses
    #: nothing, and the default vocabulary stands as it is.
    languages: frozenset[str] = field(
        default=frozenset(), metadata={ADDED_IN: "3.0.0"})

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            raise TypeError(
                f"Locale.code must be a str, got {self.code!r}"
            )
        if not self.code.strip():
            raise ValueError(
                f"Locale.code must be a non-empty string, got {self.code!r}"
            )
        if self.code != self.code.lower():
            raise ValueError(
                f"Locale.code must be lowercase, got {self.code!r}"
            )
        # Codes are registry keys (parser_for, third-party packs): every
        # accepted character is supported forever, so pin the charset
        # while relaxing later is still compatible. One separator only --
        # allowing '-' too would make tr-az and tr_az distinct keys.
        if not re.fullmatch(r"[a-z0-9_]+", self.code):
            raise ValueError(
                f"Locale.code must match [a-z0-9_]+, got {self.code!r}"
            )
        if not isinstance(self.lexicon, Lexicon):
            raise TypeError(
                f"Locale.lexicon must be a Lexicon, got {self.lexicon!r}"
            )
        if not isinstance(self.policy, PolicyPatch):
            raise TypeError(
                f"Locale.policy must be a PolicyPatch, got {self.policy!r}"
            )
        object.__setattr__(self, "languages", _tags(self.languages))

    def __repr__(self) -> str:
        # Bounded: shows the code and which Policy fields the patch sets,
        # never the Lexicon contents or the patched values themselves
        # (design rule, see nameparser._types module docstring).
        patched = [f.name for f in dataclasses.fields(self.policy)
                   if getattr(self.policy, f.name) is not UNSET]
        # a choice is shown by its tags while it is short, as one is
        # (a pack chooses one or two), and by its size past that
        if len(self.languages) > _REPR_TAGS:
            patched.insert(0, f"languages: {len(self.languages)}")
        elif self.languages:
            patched.insert(0, "languages " + "+".join(sorted(self.languages)))
        suffix = f": {', '.join(patched)}" if patched else ""
        return f"Locale({self.code!r}{suffix})"


#: The most tags Locale's repr lists; a longer choice is shown by its
#: size, so the repr stays bounded however many languages are chosen.
_REPR_TAGS = 3


def _canonical(tag: str) -> str:
    """`tag` in BCP 47's canonical case: the language subtag lowercase,
    a four-letter script subtag title case, a two-letter region
    uppercase, every other subtag lowercase (RFC 5646, 2.1.1). Equal
    choices then compare and hash equal, whatever case they were
    written in."""
    first, *rest = tag.split("-")
    out = [first.lower()]
    for sub in rest:
        if len(sub) == 4 and sub.isalpha():
            out.append(sub.title())
        elif len(sub) == 2 and sub.isalpha():
            out.append(sub.upper())
        else:
            out.append(sub.lower())
    return "-".join(out)


def _tags(value: object) -> frozenset[str]:
    """`value` as Locale.languages stores it, each tag in canonical case,
    or the TypeError or ValueError naming what is wrong with it."""
    if isinstance(value, Mapping):
        # not _reject_str_and_mapping's message: its {open: close} hint
        # is about delimiter pairs, which a choice of languages never is
        raise TypeError(
            f"Locale.languages must be a set of BCP 47 tags, not a "
            f"mapping: {value!r}. Write frozenset({{'pt'}}), or "
            f"frozenset(mapping) to choose its keys")
    _reject_str_and_mapping(value, "Locale.languages")
    if not isinstance(value, Iterable):
        raise TypeError(
            f"Locale.languages must be an iterable of BCP 47 tags, e.g. "
            f"frozenset({{'pt'}}), got {value!r}")
    tags = frozenset(value)
    for tag in sorted(tags, key=repr):
        if not isinstance(tag, str):
            raise TypeError(
                f"Locale.languages entries must be str BCP 47 tags, got "
                f"{tag!r}")
        if not _TAG.fullmatch(tag):
            raise ValueError(
                f"Locale.languages entries must be BCP 47 tags such as 'pt' "
                f"or 'pt-BR', got {tag!r}")
    return frozenset(_canonical(tag) for tag in tags)


#: How a compiled [rules] value becomes its PolicyPatch field's value,
#: by key: an order by its constant's name written in the file's case
#: ("family-first" is FAMILY_FIRST), a rule set by PatronymicRule's
#: values. tools/vocab/build.py's RULE_KEYS checks the names at build
#: time, and tests/v2/test_vocab.py holds the two tables to each other.
_ORDERS = {name.lower().replace("_", "-"): order
           for order, name in _ORDER_CONSTANT_NAMES.items()}
_RULE_VALUES: dict[str, Callable[[Any], object]] = {
    "name_order": lambda v: _ORDERS[v],
    "patronymic_rules": lambda v: frozenset(PatronymicRule(r) for r in v),
    "two_family_names": bool,
    "two_given_names": bool,
}


def rules_patch(tag: str) -> PolicyPatch:
    """The policy patch compiled from the [rules] table of the
    vocabulary file `tag` (``"ru"`` for ru.toml), which a shipped pack
    carries as its ``policy`` (#754, 4f): each key is the Policy field
    of the same name, so a rule a pack turns on is a Policy field and a
    Locale holds no rules of its own. Raises KeyError naming the files
    that hold a table when `tag`'s holds none."""
    from nameparser.config._rules import RULES

    tables = dict(RULES)
    if tag not in tables:
        raise KeyError(
            f"no vocabulary file {tag!r} holds a [rules] table; the files "
            f"that do: {', '.join(sorted(tables))}")
    values = {key: _RULE_VALUES[key](value) for key, value in tables[tag]}
    # Known mypy limitation with **dict-unpacked construction; see the
    # full explanation at Lexicon._edit in _lexicon.py.
    return PolicyPatch(**values)  # type: ignore[arg-type]


def deviates_by_two_family_names(name: str) -> bool:
    """The DEVIATES declaration of a pack whose patch turns on
    ``Policy.two_family_names`` (rules/O6), and of a given-name list
    beside it, which acts only where O6 does (the es, cs and sk packs):
    O6 acts only on a name of three or more name words, so a name of
    three or more words, commas read as spaces, or of three or more runs
    of letters declares. Titles, suffixes and a family comma count here
    though O6 reads none of them, which over-declares, the safe
    direction."""
    pieces = name.replace(",", " ").split()
    return len(pieces) >= 3 or _letter_runs(name) >= 3


def _letter_runs(text: str) -> int:
    """The runs of letters in `text`, whatever separates one from the
    next: a hyphen, a zero-width space or an interpunct, which the
    tokenizer may read as separators (rules/T1, T2, T3). A run of Han,
    hangul or kana counts twice, since segmentation may divide it into a
    family and a given name (rules/W1). A letter written with a combining
    mark splits a run, which over-declares."""
    runs, inside = 0, False
    for ch in text:
        letter = ch.isalpha()
        if letter and not inside:
            runs += 2 if unicodedata.name(ch, "").startswith(_CJK) else 1
        inside = letter
    return runs


_CJK = ("CJK", "HANGUL", "HIRAGANA", "KATAKANA")

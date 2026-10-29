"""The Locale type: a named delta over (Lexicon, Policy), with a
choice of languages.

A Locale dissolves at parser construction (parser_for): the packs'
languages are unioned into one choice, which selects among the default
vocabulary's readings by the file each sits in, the lexicon fragments
union onto the result, and the PolicyPatch folds via apply_patch. Packs
are pure data; they have no privileged capabilities
(mechanisms.md#LOCALE-PACKS-PURE-DATA).

Layering: imports _types, _lexicon and _policy only (enforced by
tests/v2/test_layering.py).
"""
from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from nameparser._lexicon import Lexicon
from nameparser._policy import UNSET, PolicyPatch, _reject_str_and_mapping
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
        if self.languages:
            patched.insert(0, "languages " + "+".join(sorted(self.languages)))
        suffix = f": {', '.join(patched)}" if patched else ""
        return f"Locale({self.code!r}{suffix})"


def _tags(value: object) -> frozenset[str]:
    """`value` as Locale.languages stores it, or the TypeError or
    ValueError naming what is wrong with it."""
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
    return tags

"""The Locale type: a named delta over (Lexicon, Policy).

A Locale dissolves at parser construction (parser_for, a later plan):
lexicon fragments union onto the base, the PolicyPatch folds via
apply_patch. Packs are pure data; they have no privileged capabilities.

Layering: imports _lexicon and _policy only (enforced by
tests/v2/test_layering.py).
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass

from nameparser._lexicon import Lexicon
from nameparser._policy import UNSET, PolicyPatch
from nameparser._types import _guarded_getstate, _guarded_setstate


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
    #: Vocabulary ADDED to the base parser's lexicon (unioned; a pack
    #: never removes base vocabulary).
    lexicon: Lexicon
    #: Behavior changes folded onto the base policy (set-valued fields
    #: union; scalars override, later pack wins).
    policy: PolicyPatch = PolicyPatch()

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

    def __repr__(self) -> str:
        # Bounded: shows the code and which Policy fields the patch sets,
        # never the Lexicon contents or the patched values themselves
        # (design rule, see nameparser._types module docstring).
        patched = [f.name for f in dataclasses.fields(self.policy)
                   if getattr(self.policy, f.name) is not UNSET]
        suffix = f": {', '.join(patched)}" if patched else ""
        return f"Locale({self.code!r}{suffix})"

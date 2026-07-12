"""The Locale type: a named delta over (Lexicon, Policy).

A Locale dissolves at parser construction (parser_for, a later plan):
lexicon fragments union onto the base, the PolicyPatch folds via
apply_patch. Packs are pure data; they have no privileged capabilities.

Layering: imports _lexicon and _policy only (tests/v2/test_layering.py,
added in a later task, enforces this).
"""
from __future__ import annotations

from dataclasses import dataclass

from nameparser._lexicon import Lexicon
from nameparser._policy import PolicyPatch


@dataclass(frozen=True, slots=True)
class Locale:
    code: str
    lexicon: Lexicon
    policy: PolicyPatch = PolicyPatch()

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError(
                f"Locale.code must be a non-empty string, got {self.code!r}"
            )
        if self.code != self.code.lower():
            raise ValueError(
                f"Locale.code must be lowercase, got {self.code!r}"
            )
        if any(c.isspace() for c in self.code):
            raise ValueError(
                f"Locale.code must not contain whitespace, got {self.code!r}"
            )
        if not isinstance(self.lexicon, Lexicon):
            raise ValueError(
                f"Locale.lexicon must be a Lexicon, got {self.lexicon!r}"
            )
        if not isinstance(self.policy, PolicyPatch):
            raise ValueError(
                f"Locale.policy must be a PolicyPatch, got {self.policy!r}"
            )

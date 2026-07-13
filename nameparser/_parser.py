"""Parser and the module-level parse() for the 2.0 API.

Layering: sits on _types/_lexicon/_policy/_locale/_pipeline; never
imports _render or the v1 facade (enforced by tests/v2/test_layering.py).

_default_parser is THE one sanctioned module-level global (conventions
§8): a functools.cache'd frozen Parser over default config.
"""
from __future__ import annotations

import dataclasses
import functools
import warnings
from dataclasses import dataclass

from nameparser._lexicon import Lexicon
from nameparser._locale import Locale
from nameparser._pipeline import run
from nameparser._pipeline._assemble import assemble
from nameparser._pipeline._state import ParseState
from nameparser._policy import UNSET, Policy, PolicyPatch, apply_patch
from nameparser._types import ParsedName, _guarded_getstate, _guarded_setstate


@dataclass(frozen=True, slots=True)
class Parser:
    """Immutable, thread-safe, picklable by construction (spec §4): all
    validity checking happens at construction; a Parser that constructs
    successfully cannot fail at parse time on any str content."""

    lexicon: Lexicon = None  # type: ignore[assignment]  # None -> default()
    policy: Policy = None  # type: ignore[assignment]    # None -> Policy()

    # in the class body so @dataclass(slots=True) keeps them
    __getstate__ = _guarded_getstate
    __setstate__ = _guarded_setstate

    def __post_init__(self) -> None:
        if self.lexicon is None:
            object.__setattr__(self, "lexicon", Lexicon.default())
        elif not isinstance(self.lexicon, Lexicon):
            raise TypeError(
                f"lexicon must be a Lexicon or None, got {self.lexicon!r}")
        if self.policy is None:
            object.__setattr__(self, "policy", Policy())
        elif not isinstance(self.policy, Policy):
            raise TypeError(
                f"policy must be a Policy or None, got {self.policy!r}")

    def __repr__(self) -> str:
        # composes the two bounded component reprs (spec §2 reprs)
        return f"Parser({self.lexicon!r}, {self.policy!r})"

    def parse(self, text: str) -> ParsedName:
        """Total over str (spec §5a): content never raises; non-str
        raises TypeError eagerly, with a decode hint for bytes (#245:
        bytes support ended with 1.x)."""
        if isinstance(text, bytes):
            raise TypeError(
                "parse() takes str, not bytes -- decode first, e.g. "
                "raw.decode('utf-8')")
        if not isinstance(text, str):
            raise TypeError(f"parse() takes str, got {text!r}")
        state = ParseState(original=text, lexicon=self.lexicon,
                           policy=self.policy)
        return assemble(run(state))


@functools.cache
def _default_parser() -> Parser:
    return Parser()


def parse(text: str) -> ParsedName:
    """Module-level convenience over a lazily created default Parser."""
    return _default_parser().parse(text)


def parser_for(*locales: Locale, base: Parser | None = None) -> Parser:
    """Lexicon fragments unioned left-to-right onto base's; policy
    patches applied left-to-right (later wins; set-valued fields union
    per the patch metadata). Validation errors raised while applying a
    pack are wrapped with that pack's identity (spec §4 amendment) --
    PolicyPatch validates lazily, so with stacked packs the raw error
    would otherwise point at nothing. Two packs setting the same SCALAR
    field is a declared conflict: UserWarning, later wins."""
    if base is not None and not isinstance(base, Parser):
        raise TypeError(f"base must be a Parser or None, got {base!r}")
    for loc in locales:
        if not isinstance(loc, Locale):
            raise TypeError(f"parser_for() takes Locale packs, got {loc!r}")
    lexicon = base.lexicon if base is not None else Lexicon.default()
    policy = base.policy if base is not None else Policy()
    scalar_setters: dict[str, str] = {}
    for loc in locales:
        for f in dataclasses.fields(PolicyPatch):
            if f.metadata.get("compose") == "union":
                continue
            if getattr(loc.policy, f.name) is UNSET:
                continue
            if f.name in scalar_setters and scalar_setters[f.name] != loc.code:
                warnings.warn(
                    f"locale {loc.code!r} overrides scalar policy field "
                    f"{f.name!r} already set by locale "
                    f"{scalar_setters[f.name]!r}; later wins",
                    UserWarning, stacklevel=2)
            scalar_setters[f.name] = loc.code
        try:
            lexicon = lexicon | loc.lexicon
            policy = apply_patch(policy, loc.policy)
        except (TypeError, ValueError) as exc:
            # safe: every raise in the apply path (Policy.__post_init__,
            # Lexicon.__or__, apply_patch) is a PLAIN TypeError/ValueError --
            # a subclass with extra mandatory args would break this rewrap
            raise type(exc)(
                f"while applying locale {loc.code!r}: {exc}") from exc
    return Parser(lexicon=lexicon, policy=policy)

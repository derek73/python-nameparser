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
from nameparser._types import (
    FOLDED_TAG, ParsedName, Token, _guarded_getstate, _guarded_setstate,
    _validated_field_strings,
)


@dataclass(frozen=True, slots=True)
class Parser:
    """A configured name parser: a :class:`Lexicon` (vocabulary) plus
    a :class:`Policy` (behavior), both defaulted when omitted. Build
    one when you need non-default configuration, build it once, and
    call :meth:`parse` many times -- it is immutable, thread-safe, and
    picklable by construction: all validity checking happens at
    construction, so a Parser that constructs successfully cannot fail
    at parse time on any str content.

    (The None field defaults resolve in __post_init__; after
    construction both fields are always non-None -- the annotations
    state the steady-state truth, hence the assignment ignores on the
    defaults.)"""

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
        """Parse one name string into a :class:`ParsedName`. Never
        raises on string content (unparseable input yields empty
        fields plus ambiguities); non-str raises TypeError eagerly,
        with a decode hint for bytes (bytes support ended with 1.x)."""
        if isinstance(text, bytes):
            raise TypeError(
                "parse() takes str, not bytes -- decode first, e.g. "
                "raw.decode('utf-8')")
        if not isinstance(text, str):
            raise TypeError(f"parse() takes str, got {text!r}")
        state = ParseState(original=text, lexicon=self.lexicon,
                           policy=self.policy)
        return assemble(run(state))

    def matches(self, a: str | ParsedName, b: str | ParsedName) -> bool:
        """Component-wise case-insensitive comparison of two names,
        parsing str arguments with THIS parser.
        :meth:`ParsedName.matches` parses its str argument with the
        DEFAULT parser instead -- for names parsed with a custom
        Parser, use this method."""
        if isinstance(a, str):
            a = self.parse(a)
        elif not isinstance(a, ParsedName):
            raise TypeError(f"matches() takes str or ParsedName, got {a!r}")
        if isinstance(b, str):
            b = self.parse(b)
        elif not isinstance(b, ParsedName):
            raise TypeError(f"matches() takes str or ParsedName, got {b!r}")
        return a.comparison_key() == b.comparison_key()

    def capitalized(self, name: ParsedName, *,
                    force: bool = False) -> ParsedName:
        """:meth:`ParsedName.capitalized` under THIS parser's lexicon.
        The no-argument form of that method uses the DEFAULT lexicon --
        for names parsed with a custom Parser, use this method."""
        if not isinstance(name, ParsedName):
            raise TypeError(f"capitalized() takes a ParsedName, got {name!r}")
        return name.capitalized(self.lexicon, force=force)

    def revise(self, name: ParsedName, **fields: str) -> ParsedName:
        """:meth:`ParsedName.replace` with this parser's vocabulary:
        each value is tokenized and classified by a full sub-parse, so
        the stable tags survive and the tag-driven views
        (family_particles, initials(), the suffix join) behave as if
        the text had been parsed. The value is classified ON ITS OWN,
        though -- a word whose reading depends on surrounding context
        may classify differently than it would in place (a standalone
        "B. S." reads as initials, not a suffix run). The sub-parse's
        role choices and ambiguities are discarded -- every harvested
        token takes the named field's role -- and its structural
        behavior applies: delimiter characters do not become tokens,
        and a mid-value maiden marker is consumed as in parsing.
        Tokens are synthetic (span=None); original is unchanged; a
        value with no name content (empty, whitespace, or punctuation
        only) clears the field; ambiguities referencing replaced
        tokens are dropped."""
        if not isinstance(name, ParsedName):
            raise TypeError(f"revise() takes a ParsedName, got {name!r}")
        replaced = _validated_field_strings(fields)
        harvested = {
            role: tuple(
                Token(t.text, None, role, t.tags - {FOLDED_TAG})
                for t in self.parse(value).tokens)
            for role, value in replaced.items()
        }
        return name._with_field_tokens(harvested)


@functools.cache
def _default_parser() -> Parser:
    return Parser()


def parse(text: str) -> ParsedName:
    """Parse a name with the default configuration and return a
    :class:`ParsedName`. Equivalent to ``Parser().parse(text)``; build
    your own :class:`Parser` (or use :func:`parser_for`) for custom
    vocabulary or behavior. Never raises on string content."""
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

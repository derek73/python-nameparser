"""v1 ``Constants`` compatibility shim over Lexicon/Policy (migration
spec §3). ``nameparser.config`` re-exports these names from the swap
commit onward; the whole module is deleted in 3.0 with the facade.

Layering: facade layer -- may import anything public; here that's
``nameparser.util`` for ``lc()``, ``nameparser.config.regexes`` for
the read-only regexes proxy's underlying compiled patterns, and
``nameparser._lexicon``/``_policy``/``_parser`` for the ``_snapshot()``
translation and the shared parser cache.

All ``nameparser.config.<data module>`` imports below are deferred
(function-local), never module-level: ``nameparser/config/__init__.py``
itself imports ``CONSTANTS``/``Constants``/etc. from this module, so a
module-level ``from nameparser.config.regexes import REGEXES`` here
would need the ``nameparser.config`` package's ``__init__.py`` to run
to completion first -- which needs this module to already be fully
initialized. Importing the data submodules lazily, on first use, breaks
that cycle.
"""
from __future__ import annotations

import functools
import warnings
from collections.abc import (
    Callable, ItemsView, Iterable, Iterator, KeysView, Mapping, Set,
    ValuesView,
)
from typing import NamedTuple, Self

from nameparser._lexicon import Lexicon, _normalize
from nameparser._parser import Parser
from nameparser._policy import PatronymicRule, Policy
from nameparser.util import lc


def _reject_bare_str_or_bytes(value: object, expected: str) -> None:
    # A bare string is an iterable of its characters, so e.g. SetManager('dr')
    # would silently shred it into {'d', 'r'} instead of raising -- shared by
    # SetManager's constructor/operands (#238/#241) and TupleManager's
    # constructor (#242). Ported from v1's `_reject_bare_str_or_bytes`.
    if isinstance(value, bytes):
        raise TypeError(
            f"expected {expected}, got a single bytes; decode it first: "
            f"{value!r}.decode()"
        )
    if isinstance(value, str):
        raise TypeError(
            f"expected {expected}, got a single str; wrap it in a list: "
            f"[{value!r}]"
        )


def _lc_validated(s: object) -> str:
    # Validates and lc()-normalizes a single element -- shared by bulk
    # iterable normalization (constructor/operands) and add()'s per-string
    # loop, so every path raises the same #238/#245-shaped TypeError instead
    # of lc() crashing cryptically (bytes) or silently transmuting (None).
    if isinstance(s, bytes):
        raise TypeError(
            f"expected a str, got bytes; decode it first: {s!r}.decode()"
        )
    if not isinstance(s, str):
        raise TypeError(f"expected a str, got {type(s).__name__}: {s!r}")
    return lc(s)


def _normalize_iterable_of_strings(
        elements: object, expected: str = "an iterable of strings") -> set[str]:
    # a SetManager's elements were already validated/normalized when it was
    # built, so copy them instead of re-validating (v1's fast path)
    if isinstance(elements, SetManager):
        return set(elements._elements)
    _reject_bare_str_or_bytes(elements, expected)
    return {_lc_validated(s) for s in elements}  # type: ignore[attr-defined]


class SetManager:
    """v1 ``SetManager`` surface over a plain set of ``lc()``-normalized
    strings. Mutations call ``_on_change`` (the owning Constants'
    generation bump, wired by a later task). ``__call__`` and the
    missing-member-tolerant ``remove()`` are gone per the #243 schedule
    (warned 1.3.0, removed 2.0): ``remove()`` of a missing member raises
    ``KeyError``, matching ``set.remove``.
    """

    _elements: set[str]
    _on_change: Callable[[], None] | None

    def __init__(self, elements: Iterable[str] = (),
                 _on_change: Callable[[], None] | None = None,
                 _field: str | None = None) -> None:
        # _field carries a Constants field name (e.g. "titles") through to
        # the bare-str/bytes guard's message, when this SetManager is being
        # built on behalf of a named Constants field (constructor kwarg or
        # __setattr__ auto-wrap); a direct SetManager(...) call gets the
        # generic v1 message instead.
        expected = f"{_field} to be an iterable of strings" if _field \
            else "an iterable of strings"
        self._elements = _normalize_iterable_of_strings(elements, expected)
        self._on_change = _on_change

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def add(self, *strings: str) -> SetManager:
        """Add the normalized string arguments to the set. Returns
        ``self`` for chaining."""
        # notify only on real change (v1 parity): a no-op add must not
        # bump the owner's generation
        changed = False
        try:
            for s in strings:
                normalized = _lc_validated(s)  # TypeError on bytes (#245)
                if normalized not in self._elements:
                    self._elements.add(normalized)
                    changed = True
        finally:
            # a TypeError mid-list still leaves earlier additions
            # applied, so the owner must hear about them or its cache
            # goes stale (same rule as remove() below)
            if changed:
                self._changed()
        return self

    def remove(self, *strings: str) -> SetManager:
        """Remove the normalized string arguments from the set.
        Raises ``KeyError`` if any argument is not a member. Returns
        ``self`` for chaining."""
        changed = False
        try:
            for s in strings:
                # _lc_validated: bytes get the same decode-hint TypeError
                # as add() (#245)
                normalized = _lc_validated(s)
                self._elements.remove(normalized)  # KeyError on missing (#243)
                changed = True
        finally:
            # a KeyError mid-list still leaves earlier removals applied,
            # so the owner must hear about them or its cache goes stale
            if changed:
                self._changed()
        return self

    def discard(self, *strings: str) -> SetManager:
        """Remove the normalized string arguments from the set if
        present; missing members are ignored, like ``set.discard``.
        Returns ``self`` for chaining."""
        changed = False
        for s in strings:
            normalized = _lc_validated(s)  # bytes decode hint (#245)
            if normalized in self._elements:
                self._elements.discard(normalized)
                changed = True
        if changed:
            self._changed()
        return self

    def clear(self) -> SetManager:
        """Remove all entries from the set. Returns ``self`` for
        chaining."""
        if self._elements:
            self._elements.clear()
            self._changed()
        return self

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and lc(item) in self._elements

    def __iter__(self) -> Iterator[str]:
        return iter(self._elements)

    def __len__(self) -> int:
        return len(self._elements)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SetManager):
            return self._elements == other._elements
        if isinstance(other, (set, frozenset)):
            return self._elements == other
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]  # mutable; v1 parity

    # -- set operators: accept ANY iterable (v1.3 normalize-everywhere) -----
    # A bare str/bytes operand raises TypeError via _normalize_iterable_of_
    # strings rather than iterating its characters (#238/#241); everything
    # else (list, generator, set, another SetManager, ...) is normalized
    # through lc() before the plain set op runs.

    def __or__(self, other: object) -> set[str]:
        return self._elements | _normalize_iterable_of_strings(other)

    __ror__ = __or__

    def __and__(self, other: object) -> set[str]:
        return self._elements & _normalize_iterable_of_strings(other)

    __rand__ = __and__

    def __sub__(self, other: object) -> set[str]:
        return self._elements - _normalize_iterable_of_strings(other)

    def __rsub__(self, other: object) -> set[str]:
        return _normalize_iterable_of_strings(other) - self._elements

    def __xor__(self, other: object) -> set[str]:
        return self._elements ^ _normalize_iterable_of_strings(other)

    __rxor__ = __xor__  # symmetric difference is commutative, like v1

    # -- comparisons: v1 subclassed collections.abc.Set, whose __le__/__lt__/
    # __ge__/__gt__ mixins only accept another Set-registered operand (set,
    # frozenset, or another Set subclass) -- NOT an arbitrary iterable like
    # list, unlike the operators above. Mirrored here since this SetManager
    # doesn't itself subclass the ABC.

    def __le__(self, other: object) -> bool:
        if not isinstance(other, (SetManager, Set)):
            return NotImplemented
        if len(self) > len(other):
            return False
        return all(elem in other for elem in self)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, (SetManager, Set)):
            return NotImplemented
        return len(self) < len(other) and self.__le__(other)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, (SetManager, Set)):
            return NotImplemented
        if len(self) < len(other):
            return False
        return all(elem in self for elem in other)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, (SetManager, Set)):
            return NotImplemented
        return len(self) > len(other) and self.__ge__(other)

    def __repr__(self) -> str:
        # Sorted so repr is stable across runs -- set() iteration order
        # depends on per-process string hash randomization.
        elements = ", ".join(repr(e) for e in sorted(self._elements))
        return f"SetManager({{{elements}}})" if self._elements else "SetManager(set())"

    # -- pickle interop with v1 blobs ---------------------------------------

    def __getstate__(self) -> dict[str, object]:
        return {"_elements": set(self._elements)}

    def __setstate__(self, state: dict[str, object]) -> None:
        # v1 SetManager stored its set under `elements` (plain __dict__
        # pickling); the shim stores `_elements`. Accept both, so a
        # v1.3/1.4 Constants blob's embedded managers unpickle straight
        # into shim instances. Re-normalize: nothing guarantees an
        # incoming blob's elements passed through lc().
        elements: Iterable[str] = state.get(  # type: ignore[assignment]
            "_elements", state.get("elements", ()))
        self._elements = {lc(e) for e in elements}
        self._on_change = None  # rewired by the owning Constants


def _validated_mapping_args(args: tuple[object, ...]) -> tuple[object, ...]:
    """The #242 constructor guard, shared by TupleManager and
    _DelimiterManager: a bare str/bytes silently shreds into a garbage
    mapping (dict's own error), and an iterable of short strings
    silently splits each one into a (key, value) pair -- ported from
    v1's TupleManager.__init__ guard."""
    if not args:
        return args
    arg = args[0]
    _reject_bare_str_or_bytes(
        arg, "a mapping or iterable of (key, value) pairs")
    if not isinstance(arg, Mapping):
        checked = []
        for item in arg:  # type: ignore[attr-defined]
            if isinstance(item, (str, bytes)):
                kind = "bytes" if isinstance(item, bytes) else "str"
                raise TypeError(
                    f"expected (key, value) pairs, got a {kind} "
                    f"element {item!r}; a 2-character string "
                    "silently splits into a key and a value"
                )
            checked.append(item)
        args = (checked, *args[1:])
    return args


class TupleManager(dict[str, object]):
    """v1 ``TupleManager``: a dict with dot-notation access. Backs
    ``capitalization_exceptions``. Unknown-key attribute access raises
    ``AttributeError`` naming the key (#256, warned 1.4, enforced 2.0 --
    the v1 ``DeprecationWarning`` is gone, this shim only speaks 2.0).
    Mutations call ``_on_change`` (the owning Constants' generation
    bump, wired by a later task).
    """

    _on_change: Callable[[], None] | None

    def __init__(self, *args: object,
                 _on_change: Callable[[], None] | None = None,
                 **kwargs: object) -> None:
        args = _validated_mapping_args(args)
        super().__init__(*args, **kwargs)
        self._on_change = _on_change

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def __getattr__(self, name: str) -> object:
        # Only reached for a missing attribute -- real instance attrs
        # (_on_change) and dict methods (keys, get, ...) resolve first
        # without ever hitting this. Dunder/underscore probes (pickling,
        # copy.deepcopy, IPython's _repr_html_) are never config keys.
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            # #256: name the known keys, like v1's 1.4 deprecation warning
            # did -- this shim only speaks 2.0, so what was a warning there
            # is a hard AttributeError here.
            raise AttributeError(
                f"{name!r} is not a known key "
                f"({', '.join(sorted(self))}); use .get() for intentional "
                "soft access."
            ) from None

    def __setattr__(self, name: str, value: object) -> None:
        # v1 parity: dunder probes (typing's __orig_class__, etc.) and this
        # shim's own _on_change hook get real object-attribute storage;
        # every other name -- including single-underscore ones, per v1 --
        # routes to the dict so `t.mcdonald = 'x'` and `t['mcdonald'] = 'x'`
        # are the same operation.
        if name == "_on_change" or (name.startswith("__") and name.endswith("__")):
            object.__setattr__(self, name, value)
        else:
            self[name] = value

    def __delattr__(self, name: str) -> None:
        if name == "_on_change" or (name.startswith("__") and name.endswith("__")):
            object.__delattr__(self, name)
        else:
            del self[name]

    def __setitem__(self, key: str, value: object) -> None:
        super().__setitem__(key, value)
        self._changed()

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self._changed()

    def pop(self, *args: object) -> object:
        # bump only on a real removal -- pop(key, default) on a missing
        # key is a no-op read, not a mutation, same rule as SetManager's
        # no-op add()
        present = bool(args) and args[0] in self
        result = super().pop(*args)  # type: ignore[call-overload]
        if present:
            self._changed()
        return result

    def popitem(self) -> tuple[str, object]:
        result = super().popitem()  # KeyError when empty: no bump
        self._changed()
        return result

    def clear(self) -> None:
        had_items = bool(self)
        super().clear()
        if had_items:  # clearing an empty dict is a no-op, not a change
            self._changed()

    def update(self, *args: object, **kwargs: object) -> None:
        # dict.update's C path skips a subclass __setitem__; route every
        # item through it so subclass validation (_DelimiterManager's
        # sentinel rule) and the owner notification hold here too
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key: str, default: object = None) -> object:
        if key in self:
            return self[key]  # existing key: a read, not a mutation
        self[key] = default   # validated + notifying path
        return default

    # in-place |= must validate/notify like update; dict's C path would
    # skip both. mypy flags any non-overloaded __ior__ as inconsistent
    # with dict.__or__'s overloads -- the runtime behavior is the plain
    # dict |= contract, so the ignore is about typeshed shape only.
    def __ior__(self, other: object) -> Self:  # type: ignore[override, misc]
        self.update(other)
        return self

    # -- pickle interop -------------------------------------------------

    def __reduce__(self) -> tuple[type[TupleManager], tuple[()], dict[str, object]]:
        return (type(self), (), dict(self))

    def __setstate__(self, state: dict[str, object]) -> None:
        # routes through __setitem__ (validated for _DelimiterManager);
        # _on_change is still None here, so no spurious bumps
        self.update(state)
        self._on_change = None  # rewired by the owning Constants


#: The named delimiter buckets, translated to the ``Policy``
#: (open, close) pairs they stand for (spec §3). The first three are
#: v1's; the rest are the #273 typographic conventions, named so the
#: v1 keyed idioms (pop/move/del) work on them like the originals.
#: Keep in sync with DEFAULT_NICKNAME_DELIMITERS in _policy.py (pinned
#: by the default-Constants equality test).
_SENTINEL_PAIRS = {
    "quoted_word": ("'", "'"),
    "double_quotes": ('"', '"'),
    "parenthesis": ("(", ")"),
    "smart_double_quotes": ("“", "”"),
    "low_high_quotes": ("„", "“"),
    "right_double_quotes": ("”", "”"),
    "guillemets": ("«", "»"),
    "reversed_guillemets": ("»", "«"),
    "corner_brackets": ("「", "」"),
    "white_corner_brackets": ("『", "』"),
    "fullwidth_parenthesis": ("（", "）"),
}

#: derived, so the manager's accepted keys and _snapshot()'s
#: translation table can never drift apart
_DELIMITER_SENTINELS = tuple(_SENTINEL_PAIRS)


class RegexTupleManager(TupleManager):  # pickle-compat: do NOT delete
    """Pickle-compat alias only: v1.4's ``Constants.regexes`` field was a
    ``nameparser.config.RegexTupleManager`` instance (a ``TupleManager``
    subclass whose ``__getattr__`` fell back to ``EMPTY_REGEX`` for an
    unknown key). Unpickling a v1.4 blob resolves and constructs this
    class -- via ``TupleManager.__reduce__``'s ``(type(self), (), state)``
    -- before ``Constants.__setstate__`` runs, so the name must exist
    here even though the shim's ``Constants._snapshot()`` never reads it:
    ``regexes`` is a read-only ``_RegexesProxy`` in 2.0 (see above), and
    ``Constants.__setstate__`` below deliberately ignores an incoming
    ``regexes`` key rather than restoring it from this reconstructed
    (and otherwise unused) instance.
    """


class _DelimiterManager(TupleManager):
    """v1 ``nickname_delimiters``/``maiden_delimiters`` bucket. In 2.0
    only the named sentinels in ``_DELIMITER_SENTINELS`` exist (spec
    §3; the v1 trio plus the #273 typographic pairs) -- assigning any
    other key raises so a caller reaches for a custom-delimiter Policy
    kwarg instead of a dict entry that silently does nothing. ``pop()``/
    ``__setitem__``/``__delitem__`` stay open (inherited) for the
    documented bucket-move idiom, e.g.
    ``maiden_delimiters['parenthesis'] = nickname_delimiters.pop('parenthesis')``.
    """

    def __init__(self, *args: object,
                 _on_change: Callable[[], None] | None = None,
                 **kwargs: object) -> None:
        # dict's C-level __init__ never calls a subclass __setitem__, so
        # collect and validate the initial items here -- BEFORE any item
        # lands -- or the sentinel rule silently misses the constructor.
        # The parent's #242 guard runs first: bare str/bytes gets the
        # friendly TypeError, not dict's cryptic one.
        args = _validated_mapping_args(args)
        items: dict[str, object] = dict(*args, **kwargs)
        for key in items:
            self._reject_non_sentinel(key)
        super().__init__(items, _on_change=_on_change)

    @staticmethod
    def _reject_non_sentinel(key: str) -> None:
        if key not in _DELIMITER_SENTINELS:
            raise TypeError(
                f"2.0 delimiter managers accept only the named sentinels "
                f"{_DELIMITER_SENTINELS}; for custom delimiter pairs use "
                f"Policy(nickname_delimiters=...) / maiden_delimiters"
            )

    def __setitem__(self, key: str, value: object) -> None:
        self._reject_non_sentinel(key)
        super().__setitem__(key, value)
    # update/setdefault/|= inherit TupleManager's routing through
    # __setitem__, so they validate (and notify) for free


class _RegexesProxy:
    """Read-only view over the v1 compiled patterns
    (``nameparser.config.regexes.REGEXES``). Reads keep working --
    ``CONSTANTS.regexes.word`` stays informational -- but 2.0 configures
    parsing behavior through named ``Policy`` flags, not by mutating a
    regex, so any attribute *or* item assignment raises ``TypeError``
    (spec §3's uniform read-only rule).
    """

    @staticmethod
    def _regexes() -> Mapping[str, object]:
        # deferred import: see the module docstring's note on why every
        # nameparser.config.<data module> import in this file is lazy
        from nameparser.config.regexes import REGEXES
        return REGEXES

    #: dict methods this read-only proxy deliberately does not carry.
    #: Without this, __getattr__ reports them as missing regexes and
    #: sends the reader hunting for a vocabulary entry.
    _DICT_ONLY = frozenset({
        "pop", "popitem", "setdefault", "update", "clear", "fromkeys",
    })

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in _RegexesProxy._DICT_ONLY:
            raise AttributeError(
                f"{name!r} is not supported on CONSTANTS.regexes: it is a "
                f"read-only view in 2.0, and parsing behavior is configured "
                f"through named Policy flags"
            )
        try:
            return self._regexes()[name]
        except KeyError:
            raise AttributeError(f"no regex named {name!r}") from None

    def __getitem__(self, name: str) -> object:
        return self._regexes()[name]

    def __contains__(self, name: object) -> bool:
        return name in self._regexes()

    def __iter__(self) -> Iterator[str]:
        return iter(self._regexes())

    def keys(self) -> KeysView[str]:
        return self._regexes().keys()

    # Defined explicitly because __getattr__ would otherwise claim each
    # of these names as a regex lookup and raise "no regex named
    # 'items'". The sibling managers inherit the whole surface from
    # dict; this proxy has to spell out the read half it supports.
    # #256's deprecation text promised .get() on both managers.

    def get(self, name: str, default: object = None) -> object:
        return self._regexes().get(name, default)

    def items(self) -> ItemsView[str, object]:
        return self._regexes().items()

    def values(self) -> ValuesView[object]:
        return self._regexes().values()

    def __len__(self) -> int:
        return len(self._regexes())

    def copy(self) -> dict[str, object]:
        # v1's regexes was a dict subclass, so copy() returned a plain
        # mutable dict. Mutating the copy never affected parsing there
        # either, so this is a faithful read-only carry-over.
        return dict(self._regexes())

    def __setattr__(self, name: str, value: object) -> None:
        self._raise_readonly(name)

    def __setitem__(self, name: str, value: object) -> None:
        self._raise_readonly(name)

    @staticmethod
    def _raise_readonly(name: str) -> None:
        # bidi/emoji are the two regexes v1 code toggled directly
        # (`CONSTANTS.regexes.bidi = False`) to opt out of stripping;
        # point those two at their named Policy replacement, everything
        # else gets the generic pointer.
        hints = {
            "bidi": "use Policy(strip_bidi=False) to keep bidi marks",
            "emoji": "use Policy(strip_emoji=False) to keep emoji",
        }
        hint = hints.get(
            name, "parsing behavior is configured through named Policy "
                  "flags in 2.0; if none fits, open an issue")
        raise TypeError(
            f"assigning CONSTANTS.regexes.{name} is not supported in "
            f"2.0: {hint}"
        )


_SET_FIELDS = (
    "prefixes", "suffix_acronyms", "suffix_not_acronyms",
    "suffix_acronyms_ambiguous", "titles", "first_name_titles",
    "conjunctions", "bound_first_names", "non_first_name_prefixes",
)
_MANAGER_FIELDS = _SET_FIELDS + (
    "capitalization_exceptions", "nickname_delimiters", "maiden_delimiters",
)

#: v1's Constants.__repr__ field order (#221) -- kept as its own tuple
#: rather than reusing _SET_FIELDS, whose order differs (v1 lists
#: suffix_acronyms_ambiguous last, not fourth).
_REPR_COLLECTION_ATTRS = (
    "prefixes", "suffix_acronyms", "suffix_not_acronyms", "titles",
    "first_name_titles", "conjunctions", "bound_first_names",
    "non_first_name_prefixes", "suffix_acronyms_ambiguous",
)
#: v1's repr scalar order, minus empty_attribute_default -- removed in 2.0
#: (#255), so there's no such attribute on this shim's Constants to show.
_REPR_SCALAR_ATTRS = (
    "string_format", "initials_format", "initials_delimiter",
    "initials_separator", "suffix_delimiter",
    "capitalize_name", "force_mixed_case_capitalization",
    "patronymic_name_order", "middle_name_as_last",
)

_SCALAR_DEFAULTS: dict[str, object] = {
    "patronymic_name_order": False,
    "middle_name_as_last": False,
    "capitalize_name": False,
    "force_mixed_case_capitalization": False,
    "string_format": "{title} {first} {middle} {last} {suffix} ({nickname})",
    "initials_format": "{first} {middle} {last}",
    "initials_delimiter": ".",
    "initials_separator": " ",
    "suffix_delimiter": None,
}

# distinguishes "attribute not set yet" from any real scalar value
# (None is a legitimate value for string_format/suffix_delimiter)
_UNSET = object()

# distinguishes "kwarg not passed to Constants()" (use library defaults)
# from any real value a caller might pass, including a falsy one like ""
_UNSET_KWARG = object()


_SHARED_MUTATION_MESSAGE = (
    "mutating the shared CONSTANTS singleton is deprecated and will be "
    "removed in 3.0; build a Lexicon/Policy (or a private Constants "
    "passed as HumanName(constants=...)) instead. See the migration "
    "guide."
)


def _default_vocab() -> dict[str, set[str]]:
    # v1 data modules stay the single vocabulary source through 2.x
    # (same rule as Lexicon.default()).
    from nameparser.config.bound_first_names import BOUND_FIRST_NAMES
    from nameparser.config.conjunctions import CONJUNCTIONS
    from nameparser.config.prefixes import (
        NON_FIRST_NAME_PREFIXES, PREFIXES,
    )
    from nameparser.config.suffixes import (
        SUFFIX_ACRONYMS, SUFFIX_ACRONYMS_AMBIGUOUS, SUFFIX_NOT_ACRONYMS,
    )
    from nameparser.config.titles import FIRST_NAME_TITLES, TITLES
    return {
        "prefixes": PREFIXES,
        "suffix_acronyms": SUFFIX_ACRONYMS,
        "suffix_not_acronyms": SUFFIX_NOT_ACRONYMS,
        "suffix_acronyms_ambiguous": SUFFIX_ACRONYMS_AMBIGUOUS,
        "titles": TITLES,
        "first_name_titles": FIRST_NAME_TITLES,
        "conjunctions": CONJUNCTIONS,
        "bound_first_names": BOUND_FIRST_NAMES,
        "non_first_name_prefixes": NON_FIRST_NAME_PREFIXES,
    }


class _RenderDefaults(NamedTuple):
    """v1 scalar rendering knobs that have no home on ``Policy``
    (spec §3): ``__str__``/initials formatting and capitalization stay
    per-Constants defaults, layered onto a shared ``Parser`` by the
    facade (a later task) rather than folded into the cache key."""

    string_format: str | None
    initials_format: str
    initials_delimiter: str
    initials_separator: str
    suffix_delimiter: str | None
    capitalize_name: bool
    force_mixed_case_capitalization: bool


@functools.lru_cache(maxsize=64)
def _cached_parser(lexicon: Lexicon, policy: Policy) -> Parser:
    # keyed on hashable value objects: shared across every facade whose
    # Constants resolve to the same snapshot (spec §3)
    return Parser(lexicon=lexicon, policy=policy)


class Constants:
    """v1 ``Constants`` shim: a mutable container whose state resolves to
    a frozen ``(Lexicon, Policy, _RenderDefaults)`` snapshot via
    ``_snapshot()``. ``_generation`` increments on every mutation;
    facades compare it against a cached value to decide whether their
    snapshot is stale (dirty-tracking, spec §3 -- the facade itself is
    a later task).

    The module-level ``CONSTANTS`` singleton (below) has ``_shared``
    flipped to ``True``: any mutation reached through it emits
    ``DeprecationWarning`` pointing at ``Lexicon``/``Policy`` and
    ``HumanName(constants=...)``. A private ``Constants()`` never
    warns -- only the shared instance is on the 3.0 removal path.
    """

    _shared = False  # the CONSTANTS singleton flips this to True
    _generation: int

    prefixes: SetManager
    suffix_acronyms: SetManager
    suffix_not_acronyms: SetManager
    suffix_acronyms_ambiguous: SetManager
    titles: SetManager
    first_name_titles: SetManager
    conjunctions: SetManager
    bound_first_names: SetManager
    non_first_name_prefixes: SetManager
    capitalization_exceptions: TupleManager
    nickname_delimiters: _DelimiterManager
    maiden_delimiters: _DelimiterManager
    regexes: _RegexesProxy

    patronymic_name_order: bool
    middle_name_as_last: bool
    capitalize_name: bool
    force_mixed_case_capitalization: bool
    string_format: str | None
    initials_format: str
    initials_delimiter: str
    initials_separator: str
    suffix_delimiter: str | None

    def __init__(
        self,
        *,
        prefixes: Iterable[str] | object = _UNSET_KWARG,
        suffix_acronyms: Iterable[str] | object = _UNSET_KWARG,
        suffix_not_acronyms: Iterable[str] | object = _UNSET_KWARG,
        suffix_acronyms_ambiguous: Iterable[str] | object = _UNSET_KWARG,
        titles: Iterable[str] | object = _UNSET_KWARG,
        first_name_titles: Iterable[str] | object = _UNSET_KWARG,
        conjunctions: Iterable[str] | object = _UNSET_KWARG,
        bound_first_names: Iterable[str] | object = _UNSET_KWARG,
        non_first_name_prefixes: Iterable[str] | object = _UNSET_KWARG,
        capitalization_exceptions:
            Mapping[str, str] | Iterable[tuple[str, str]] | object
            = _UNSET_KWARG,
        regexes: object = _UNSET_KWARG,
        patronymic_name_order: bool = False,
        middle_name_as_last: bool = False,
    ) -> None:
        # v1.4 parity constructor kwargs (#238/#242/#244 hardening); the
        # signature is spelled out rather than **kwargs so an unknown
        # keyword raises Python's own TypeError with no help from here.
        # `regexes` is the one deliberate 2.0 divergence: v1.4 accepted it
        # (RegexTupleManager(regexes)), but constructor injection is
        # assignment by another door, and __setattr__ above already
        # forbids `c.regexes = ...` post-construction -- the uniform 2.0
        # rule is that parsing behavior is configured through Policy, not
        # by handing Constants a compiled-pattern mapping either way.
        if regexes is not _UNSET_KWARG:
            raise TypeError(
                "Constants(regexes=...) is not supported in 2.0; parsing "
                "behavior is configured through named Policy flags, not "
                "by constructing Constants with a regex mapping. See the "
                "migration guide."
            )
        overrides = {
            "prefixes": prefixes,
            "suffix_acronyms": suffix_acronyms,
            "suffix_not_acronyms": suffix_not_acronyms,
            "suffix_acronyms_ambiguous": suffix_acronyms_ambiguous,
            "titles": titles,
            "first_name_titles": first_name_titles,
            "conjunctions": conjunctions,
            "bound_first_names": bound_first_names,
            "non_first_name_prefixes": non_first_name_prefixes,
        }
        vocab = _default_vocab()
        object.__setattr__(self, "_generation", 0)
        for name in _SET_FIELDS:
            value = overrides[name]
            if value is _UNSET_KWARG:
                value = vocab[name]
            # a caller-supplied value REPLACES that field's default
            # vocabulary wholesale (v1 parity); SetManager itself validates/
            # normalizes and rejects a bare str/bytes (#238/#241), naming
            # this field in the message via _field=
            object.__setattr__(
                self, name,
                SetManager(value, _on_change=self._bump, _field=name))  # type: ignore[arg-type]
        if capitalization_exceptions is _UNSET_KWARG:
            from nameparser.config.capitalization import (
                CAPITALIZATION_EXCEPTIONS,
            )
            capitalization_exceptions = CAPITALIZATION_EXCEPTIONS
        object.__setattr__(self, "capitalization_exceptions", TupleManager(
            capitalization_exceptions,  # type: ignore[arg-type]
            _on_change=self._bump))
        object.__setattr__(self, "nickname_delimiters", _DelimiterManager(
            {name: name for name in _DELIMITER_SENTINELS},
            _on_change=self._bump))
        object.__setattr__(self, "maiden_delimiters", _DelimiterManager(
            _on_change=self._bump))
        object.__setattr__(self, "regexes", _RegexesProxy())
        for name, value in _SCALAR_DEFAULTS.items():
            object.__setattr__(self, name, value)
        # the two behavior bools were v1.4 constructor kwargs too
        # (docs/customize.rst doctests use them); truthiness matches v1,
        # storage goes through the plain scalar slot
        if patronymic_name_order:
            object.__setattr__(self, "patronymic_name_order", True)
        if middle_name_as_last:
            object.__setattr__(self, "middle_name_as_last", True)

    def _invalidate_pst(self) -> None:
        """Pickle-compat alias only, never called at runtime: v1's four
        cached-union ``SetManager`` fields (``prefixes``,
        ``suffix_acronyms``, ``suffix_not_acronyms``, ``titles``) stored
        their ``_on_change`` as the bound method
        ``Constants._invalidate_pst``. A pickled bound method serializes
        as a back-reference to its ``__self__`` (this same ``Constants``
        instance, mid-unpickle) plus the method NAME -- reconstructed via
        ``getattr(constants_obj, '_invalidate_pst')`` before
        ``Constants.__setstate__`` ever runs (same two-phase-unpickling
        story as ``RegexTupleManager`` above). Without this name, loading
        a v1.4 blob raises ``AttributeError`` looking up the method.
        ``SetManager.__setstate__`` (shim) never restores ``_on_change``
        from pickled state regardless -- it always resets to ``None`` and
        is rewired by ``Constants.__setstate__`` below -- so this bound
        method value is reconstructed only to satisfy the pickle format;
        it is discarded immediately and never invoked.
        """

    def _bump(self) -> None:
        # stacklevel=3 is exact for the direct scalar-assignment path
        # (user code -> Constants.__setattr__ -> here) and lands one
        # frame short -- inside the manager's own add()/remove()/
        # __setitem__ -- for the indirect manager-mutation path (user
        # code -> manager method -> _changed() -> here), since a
        # single warn() call can't be exact for both call depths at
        # once. Either way the warning still fires from this module,
        # not the manager's true caller, which is enough: only the
        # DeprecationWarning's presence/category/message are load-
        # bearing (see the specified test), not the reported line.
        if self._shared:
            warnings.warn(_SHARED_MUTATION_MESSAGE, DeprecationWarning,
                          stacklevel=3)
        object.__setattr__(self, "_generation", self._generation + 1)

    def __setattr__(self, name: str, value: object) -> None:
        if name == "_shared":
            # the flag the whole shared-mutation DeprecationWarning
            # mechanism hinges on: only the module-level singleton flip
            # (object.__setattr__ below) may set it
            raise AttributeError(
                "Constants._shared is read-only; it marks the module "
                "singleton and is set once at import"
            )
        if name == "empty_attribute_default":
            raise AttributeError(
                "empty_attribute_default was removed in 2.0 (#255): "
                "empty attributes are always ''"
            )
        if name == "regexes":
            raise TypeError(
                "replacing CONSTANTS.regexes is not supported in 2.0; "
                "parsing behavior is configured through named Policy "
                "flags"
            )
        if name in _SET_FIELDS:
            # v1 allowed wholesale reassignment (c.titles = {...}); same
            # bare-str/bytes guard as the constructor kwarg path (#238/#241)
            value = SetManager(
                value, _on_change=self._bump, _field=name)  # type: ignore[arg-type]
        elif name == "capitalization_exceptions":
            value = TupleManager(value, _on_change=self._bump)  # type: ignore[arg-type]
        elif name in ("nickname_delimiters", "maiden_delimiters"):
            value = _DelimiterManager(value, _on_change=self._bump)  # type: ignore[arg-type]
        elif name in _SCALAR_DEFAULTS and \
                getattr(self, name, _UNSET) == value:
            # no-op scalar assignment: managers already suppress no-op
            # mutations, so re-assigning the current scalar value must
            # not bump the generation (or warn on the shared singleton)
            # either. __init__ writes via object.__setattr__, so this
            # only runs on real user assignments -- _UNSET never
            # actually matches, it just keeps a not-yet-set attribute
            # from raising here. Manager-field reassignment above stays
            # an unconditional bump: comparing manager contents isn't
            # worth it.
            object.__setattr__(self, name, value)
            return
        object.__setattr__(self, name, value)
        if name in _MANAGER_FIELDS or name in _SCALAR_DEFAULTS:
            self._bump()

    def copy(self) -> Constants:
        """Independent copy (#260), subclass-preserving. Divergence from
        v1 (which deepcopied __dict__): attributes OUTSIDE the known
        field surface -- e.g. ad-hoc names stashed on the instance --
        are not carried by copy() or pickling; only the enumerated
        fields survive."""                          # #260
        # An independent instance with its own generation counter and
        # its own manager callbacks -- not a shared-state alias like a
        # naive attribute-for-attribute copy would produce. v1's copy()
        # was `copy.deepcopy(self)`, which builds the new object via
        # `type(self).__new__(type(self))` -- NOT by calling `type(self)()`
        # -- so a Constants subclass copies as itself without its __init__
        # running (and without needing to satisfy whatever signature that
        # __init__ might require). Mirrored here with an explicit __new__
        # bypass rather than type(self)().
        new = object.__new__(type(self))
        object.__setattr__(new, "_generation", 0)
        for name in _SET_FIELDS:
            object.__setattr__(
                new, name,
                SetManager(getattr(self, name), _on_change=new._bump))
        object.__setattr__(new, "capitalization_exceptions", TupleManager(
            dict(self.capitalization_exceptions), _on_change=new._bump))
        for bucket in ("nickname_delimiters", "maiden_delimiters"):
            object.__setattr__(new, bucket, _DelimiterManager(
                dict(getattr(self, bucket)), _on_change=new._bump))
        object.__setattr__(new, "regexes", _RegexesProxy())
        for name in _SCALAR_DEFAULTS:
            object.__setattr__(new, name, getattr(self, name))
        return new

    def __repr__(self) -> str:                            # #221
        # Collections (some with hundreds of entries, e.g. titles/prefixes)
        # are summarized as counts rather than dumped in full, like v1.
        # Scalars are only shown when they differ from the library default
        # -- _SCALAR_DEFAULTS stands in for v1's `getattr(type(self), name)`
        # class-level default, since this shim's scalar defaults are
        # instance attributes set in __init__, not class attributes.
        lines = [f"    {name}: {len(getattr(self, name))}"
                 for name in _REPR_COLLECTION_ATTRS]
        lines += [
            f"    {name}: {value!r}" for name in _REPR_SCALAR_ATTRS
            if (value := getattr(self, name)) != _SCALAR_DEFAULTS[name]
        ]
        return "<Constants : [\n" + "\n".join(lines) + "\n]>"

    # -- snapshot -----------------------------------------------------------

    def _snapshot(self) -> tuple[Lexicon, Policy, _RenderDefaults]:
        # generation-keyed cache: rebuilding the Lexicon re-normalizes
        # ~1400 vocabulary entries (~185us) -- the same dirty-tracking
        # the facade uses, applied one level up. A pure read either way
        # (no bump, no warning).
        cached = getattr(self, "_snapshot_cache", None)
        if cached is not None and cached[0] == self._generation:
            return cached[1]  # type: ignore[no-any-return]
        snapshot = self._build_snapshot()
        object.__setattr__(
            self, "_snapshot_cache", (self._generation, snapshot))
        return snapshot

    def _build_snapshot(self) -> tuple[Lexicon, Policy, _RenderDefaults]:
        """Resolve this v1-shaped, mutable Constants into the frozen
        2.0 value objects it corresponds to (spec §3). A pure read: no
        generation bump, no deprecation warning even on the shared
        singleton -- only direct attribute mutation is on the 3.0
        removal path.
        """
        from nameparser.config.maiden_markers import MAIDEN_MARKERS
        acronyms = frozenset(self.suffix_acronyms)
        titles = frozenset(self.titles)
        particles = frozenset(self.prefixes)
        bound = frozenset(self.bound_first_names)
        ambiguous_acronyms = frozenset(self.suffix_acronyms_ambiguous) & acronyms
        # keep in sync with _lexicon._default_lexicon() (pinned by
        # tests/v2/test_config_shim.py::test_snapshot_field_translation)
        lexicon = Lexicon(
            titles=titles,
            # TRANSLATE, do not filter. The two versions build the same
            # lookup key differently: v1 joins the raw title run and
            # then applies lc(), which strips only the whole string's
            # edge periods, so an interior word keeps its own ("lt.
            # col"). v2 normalizes each token and then joins ("lt col").
            # Re-folding per word converts a v1 entry into the v2
            # spelling; filtering instead dropped every multi-word
            # honorific containing an abbreviation or a conjunction and
            # silently swapped given and family.
            # Only entries v1 could actually match: its key is the
            # joined title run, so always single-spaced and never
            # empty. An entry holding a whitespace run was inert there
            # (translating it would start matching), and one that folds
            # away entirely would trip _normset's empty-entry check on
            # a config v1 simply ignored.
            given_name_titles=frozenset(
                t for t in (
                    " ".join(_normalize(w) for w in e.split())
                    for e in self.first_name_titles
                    if e == " ".join(e.split())
                ) if t),
            suffix_acronyms=acronyms,
            # Drop any ambiguous acronym from the word set rather than
            # the other way round. Lexicon forbids the overlap because
            # the word branch bypasses the period gate, and adding an
            # ambiguous acronym to suffix_not_acronyms is INERT in v1
            # anyway: is_suffix already accepts it via the acronym
            # branch, and reserve_last keeps it as the surname. So
            # ignoring the addition reproduces v1 ("Jack Ma" keeps
            # last='Ma'), where dropping it from the AMBIGUOUS set
            # instead ungated the word and lost the family name --
            # a silent misparse worse than the raise it avoided.
            suffix_words=frozenset(
                self.suffix_not_acronyms) - ambiguous_acronyms,
            # Intersect with acronyms: Lexicon enforces ambiguous <=
            # acronyms; v1 behaves the same when an acronym is deleted
            # but its ambiguous entry lingers (the entry stops
            # mattering).
            suffix_acronyms_ambiguous=ambiguous_acronyms,
            particles=particles,
            # complement translation: v1 marks the never-given subset;
            # v2 marks the may-be-given subset. The trailing union keeps
            # a config v1 accepted: prefixes.py asserts its own data has
            # no word in both non_first_name_prefixes and
            # bound_first_names, but nothing stops a caller adding one at
            # runtime, and v1 then lets the bound rule win (leading "dos
            # Santos Silva" parses first="dos Santos"). Treating such a
            # word as may-be-given reproduces that rather than raising.
            #
            # KNOWN DEVIATION, pinned by
            # test_bound_never_given_prefix_deviates_on_two_pieces: v1's
            # join has a reserve_last guard, so with only two pieces it
            # does NOT fire and the word stays never-given ("dos Santos"
            # -> last="dos Santos"). Promotion here is unconditional, so
            # that case reads given="dos", family="Santos". v1's rule is
            # piece-count dependent and a static vocabulary set cannot
            # express it; the alternative is raising on a config v1
            # accepted, which is worse. Only reachable via a runtime
            # config the shipped data forbids.
            particles_ambiguous=(
                particles - frozenset(self.non_first_name_prefixes))
            | (bound & particles),
            conjunctions=frozenset(self.conjunctions),
            bound_given_names=bound,
            # v1 Constants has no manager for these (#274 is 2.0
            # behavior); the data module is the only source
            maiden_markers=frozenset(MAIDEN_MARKERS),
            # TupleManager is dict[str, object] (v1 parity: values were
            # never statically str-typed); every real entry is a str,
            # same assumption _DelimiterManager's sentinel lookup makes
            capitalization_exceptions=tuple(
                sorted(self.capitalization_exceptions.items())),  # type: ignore[arg-type]
        )
        rules = frozenset({PatronymicRule.EAST_SLAVIC, PatronymicRule.TURKIC}) \
            if self.patronymic_name_order else frozenset()
        policy = Policy(
            patronymic_rules=rules,
            middle_as_family=self.middle_name_as_last,
            nickname_delimiters=frozenset(
                _SENTINEL_PAIRS[k] for k in self.nickname_delimiters),
            # v1 precedence: a pair in BOTH v1 buckets parses as nickname.
            # Policy itself resolves overlap the other way (maiden wins),
            # so pre-subtract here to keep the facade at v1 behavior.
            maiden_delimiters=frozenset(
                _SENTINEL_PAIRS[k] for k in self.maiden_delimiters
                if k not in self.nickname_delimiters),
            # suffix_delimiter is a _RenderDefaults-only field here; the
            # facade layers it onto extra_suffix_delimiters per instance
            # (a later task) -- _snapshot() itself stays pure translation
        )
        defaults = _RenderDefaults(
            self.string_format, self.initials_format, self.initials_delimiter,
            self.initials_separator, self.suffix_delimiter,
            self.capitalize_name, self.force_mixed_case_capitalization)
        return lexicon, policy, defaults

    # -- pickle -----------------------------------------------------------

    def __getstate__(self) -> dict[str, object]:
        state: dict[str, object] = {}
        for name in _SET_FIELDS:
            state[name] = set(getattr(self, name))
        state["capitalization_exceptions"] = dict(
            self.capitalization_exceptions)
        state["nickname_delimiters"] = dict(self.nickname_delimiters)
        state["maiden_delimiters"] = dict(self.maiden_delimiters)
        for name in _SCALAR_DEFAULTS:
            state[name] = getattr(self, name)
        return state

    def __setstate__(self, state: dict[str, object]) -> None:
        if "suffixes_prefixes_titles" in state:
            # pre-1.3.0 blob: its dir()-sweep __getstate__ captured this
            # computed property. The 1.4 DeprecationWarning promised
            # ValueError in 2.0 (#279).
            raise ValueError(
                "this pickle was written by nameparser <= 1.2.x (#279); "
                "re-pickle under 1.3/1.4 to migrate, or re-create the "
                "configuration. See "
                "https://github.com/derek73/python-nameparser/issues/279"
            )
        # Accepts BOTH shapes with a single overlay: the shim's own
        # state and v1.3/1.4 state (public field names -> manager/
        # scalar values) share every key that matters, so no shape
        # marker is needed. empty_attribute_default is accepted and
        # DROPPED (#255: empty is always '' in 2.0).
        state = {k: v for k, v in state.items()
                 if k != "empty_attribute_default"}
        self.__init__()  # type: ignore[misc]  # defaults, then overlay
        # (managers re-wrapped below so _on_change points at THIS
        # instance, not whatever produced the incoming state)
        for name in _SET_FIELDS:
            if name in state:
                object.__setattr__(self, name, SetManager(
                    state[name], _on_change=self._bump))  # type: ignore[arg-type]
        if "capitalization_exceptions" in state:
            object.__setattr__(
                self, "capitalization_exceptions", TupleManager(
                    state["capitalization_exceptions"],  # type: ignore[arg-type]
                    _on_change=self._bump))
        for bucket in ("nickname_delimiters", "maiden_delimiters"):
            if bucket in state:
                object.__setattr__(self, bucket, _DelimiterManager(
                    state[bucket], _on_change=self._bump))  # type: ignore[arg-type]
        for name in _SCALAR_DEFAULTS:
            if name in state:
                object.__setattr__(self, name, state[name])


CONSTANTS = Constants()
object.__setattr__(CONSTANTS, "_shared", True)

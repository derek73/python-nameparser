"""v1 ``Constants`` compatibility shim over Lexicon/Policy (migration
spec §3). ``nameparser.config`` re-exports these names from the swap
commit onward; the whole module is deleted in 3.0 with the facade.

Layering: facade layer -- may import anything public; here that's
``nameparser.util`` for ``lc()`` and ``nameparser.config.regexes`` for
the read-only regexes proxy's underlying compiled patterns.
"""
from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable, Iterator, KeysView
from typing import Self

from nameparser.config.regexes import REGEXES
from nameparser.util import lc


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
                 _on_change: Callable[[], None] | None = None) -> None:
        self._elements = {lc(e) for e in elements}
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
        for s in strings:
            normalized = lc(s)
            if normalized not in self._elements:
                self._elements.add(normalized)
                changed = True
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
                self._elements.remove(lc(s))  # KeyError on missing (#243)
                changed = True
        finally:
            # a KeyError mid-list still leaves earlier removals applied,
            # so the owner must hear about them or its cache goes stale
            if changed:
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

    def _as_operand(self, other: object) -> set[str]:
        if isinstance(other, SetManager):
            return other._elements
        if isinstance(other, (set, frozenset)):
            return {lc(e) if isinstance(e, str) else e for e in other}
        raise TypeError(f"unsupported operand type for SetManager: {other!r}")

    def __or__(self, other: object) -> set[str]:
        return self._elements | self._as_operand(other)

    __ror__ = __or__

    def __and__(self, other: object) -> set[str]:
        return self._elements & self._as_operand(other)

    __rand__ = __and__

    def __sub__(self, other: object) -> set[str]:
        return self._elements - self._as_operand(other)

    def __rsub__(self, other: object) -> set[str]:
        return self._as_operand(other) - self._elements

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
            raise AttributeError(f"no key {name!r} in this manager") from None

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


_DELIMITER_SENTINELS = ("quoted_word", "double_quotes", "parenthesis")


class _DelimiterManager(TupleManager):
    """v1 ``nickname_delimiters``/``maiden_delimiters`` bucket. In 2.0
    only the three named sentinels exist (spec §3) -- each maps to the
    name of a ``_RegexesProxy`` entry it stays linked to; assigning any
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
        # lands -- or the sentinel rule silently misses the constructor
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

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return REGEXES[name]
        except KeyError:
            raise AttributeError(f"no regex named {name!r}") from None

    def __getitem__(self, name: str) -> object:
        return REGEXES[name]

    def __contains__(self, name: object) -> bool:
        return name in REGEXES

    def __iter__(self) -> Iterator[str]:
        return iter(REGEXES)

    def keys(self) -> KeysView[str]:
        return REGEXES.keys()

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


class Constants:
    """v1 ``Constants`` shim: a mutable container whose state resolves to
    a frozen ``(Lexicon, Policy, _RenderDefaults)`` snapshot on demand
    (added in a later task). ``_generation`` increments on every
    mutation; facades compare it against a cached value to decide
    whether their snapshot is stale (dirty-tracking, spec §3).

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

    def __init__(self) -> None:
        vocab = _default_vocab()
        object.__setattr__(self, "_generation", 0)
        for name in _SET_FIELDS:
            object.__setattr__(
                self, name, SetManager(vocab[name], _on_change=self._bump))
        from nameparser.config.capitalization import (
            CAPITALIZATION_EXCEPTIONS,
        )
        object.__setattr__(self, "capitalization_exceptions", TupleManager(
            CAPITALIZATION_EXCEPTIONS, _on_change=self._bump))
        object.__setattr__(self, "nickname_delimiters", _DelimiterManager(
            {name: name for name in _DELIMITER_SENTINELS},
            _on_change=self._bump))
        object.__setattr__(self, "maiden_delimiters", _DelimiterManager(
            _on_change=self._bump))
        object.__setattr__(self, "regexes", _RegexesProxy())
        for name, value in _SCALAR_DEFAULTS.items():
            object.__setattr__(self, name, value)

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
            # v1 allowed wholesale reassignment (c.titles = {...})
            value = SetManager(value, _on_change=self._bump)  # type: ignore[arg-type]
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

    def copy(self) -> Constants:                          # #260
        # An independent instance with its own generation counter and
        # its own manager callbacks -- not a shared-state alias like a
        # naive attribute-for-attribute copy would produce.
        new = Constants()
        for name in _SET_FIELDS:
            object.__setattr__(
                new, name,
                SetManager(getattr(self, name), _on_change=new._bump))
        object.__setattr__(new, "capitalization_exceptions", TupleManager(
            dict(self.capitalization_exceptions), _on_change=new._bump))
        for bucket in ("nickname_delimiters", "maiden_delimiters"):
            object.__setattr__(new, bucket, _DelimiterManager(
                dict(getattr(self, bucket)), _on_change=new._bump))
        for name in _SCALAR_DEFAULTS:
            object.__setattr__(new, name, getattr(self, name))
        return new

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
CONSTANTS._shared = True  # type: ignore[attr-defined]

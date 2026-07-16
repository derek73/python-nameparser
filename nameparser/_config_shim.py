"""v1 ``Constants`` compatibility shim over Lexicon/Policy (migration
spec §3). ``nameparser.config`` re-exports these names from the swap
commit onward; the whole module is deleted in 3.0 with the facade.

Layering: facade layer -- may import anything public; here that's
``nameparser.util`` for ``lc()`` and ``nameparser.config.regexes`` for
the read-only regexes proxy's underlying compiled patterns.
"""
from __future__ import annotations

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

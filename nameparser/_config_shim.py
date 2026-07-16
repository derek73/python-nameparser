"""v1 ``Constants`` compatibility shim over Lexicon/Policy (migration
spec §3). ``nameparser.config`` re-exports these names from the swap
commit onward; the whole module is deleted in 3.0 with the facade.

Layering: facade layer -- may import anything public; here that's just
``nameparser.util`` for ``lc()``.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

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

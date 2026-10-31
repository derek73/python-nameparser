"""tools/differential/shapes.py's ARRANGEMENTS, the shape inventory
per order (#469, 3.0's sub-phase 4h), read under each row's order.

Every row is pinned to what the tree reads today. A misread row
carries the open issue that decides it and is pinned AS read rather
than marked xfail: an xfail needs the reading the row should give,
which that issue has not decided, and a non-strict one stops watching
the row, so a change that moved it would pass. Pinned, any move fails
here, and the fix that settles the issue edits the row's reading and
drops its `misread` in the same diff.

Negative control, 2026-10-30: with every row parsed under the default
order, 31 of the 40 family-first rows fail; the 9 that still pass are
the rows with a family comma, which lays the part after it out
given-first under every order.
"""
from __future__ import annotations

from typing import Protocol

import pytest

import nameparser
from nameparser import Parser, Policy, Role

from ._differential_fixtures import load_tool

shapes = load_tool("shapes")
ARRANGEMENTS = shapes.ARRANGEMENTS

class _Row(Protocol):
    """shapes.Arrangement as this module reads it: tools/ is loaded by
    path, so its type is not importable here."""
    shape: int
    text: str
    reads: dict[str, str]
    misread: int | None


_ORDERS = (None, "FAMILY_FIRST", "FAMILY_FIRST_GIVEN_LAST")


def _order(arrangement: _Row) -> str | None:
    return shapes.SHAPES[arrangement.shape].order  # type: ignore[no-any-return]


def _parser(order: str | None) -> Parser:
    return Parser() if order is None else Parser(
        policy=Policy(name_order=getattr(nameparser, order)))


_PARSERS = {order: _parser(order) for order in _ORDERS}


@pytest.mark.parametrize(
    "arrangement", ARRANGEMENTS,
    ids=[f"{a.shape}:{a.text}" for a in ARRANGEMENTS])
def test_an_arrangement_reads_as_the_inventory_records(arrangement: _Row) -> None:
    name = _PARSERS[_order(arrangement)].parse(arrangement.text)
    read = {str(r): getattr(name, str(r)) for r in Role
            if getattr(name, str(r))}
    gap = (f" (misread today, #{arrangement.misread}: update the row and "
           f"drop its misread once the issue is decided)"
           if arrangement.misread else "")
    assert read == arrangement.reads, (
        f"{arrangement.text!r} under {_order(arrangement) or 'the default order'}"
        f" reads {read}, the inventory records {arrangement.reads}{gap}")


def test_every_order_covers_every_position() -> None:
    """The inventory is the order sweep's grid, so a position an order
    has a slot for and no row instantiates is a hole in it. The table
    is asserted non-empty first: an empty parametrize is a skip."""
    assert len(ARRANGEMENTS) > 0
    assert set(shapes.NOT_A_SLOT) == set(_ORDERS)
    for order in _ORDERS:
        rows = [a for a in ARRANGEMENTS if _order(a) == order]
        covered = {p for a in rows for p in a.positions}
        missing = (set(shapes.POSITIONS) - shapes.NOT_A_SLOT[order]) - covered
        assert not missing, (order, sorted(missing))
        assert not covered & shapes.NOT_A_SLOT[order], order


def test_an_arrangement_names_known_positions_shapes_and_roles() -> None:
    roles = {str(r) for r in Role}
    for a in ARRANGEMENTS:
        assert a.shape in shapes.SHAPES and a.shape not in (6, 7), a
        assert a.positions and set(a.positions) <= set(shapes.POSITIONS), a
        assert a.reads and set(a.reads) <= roles, a
        assert all(a.reads.values()), a
    texts = [(a.shape, a.text) for a in ARRANGEMENTS]
    assert len(texts) == len(set(texts))


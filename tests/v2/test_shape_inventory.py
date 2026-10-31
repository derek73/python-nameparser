"""tools/differential/shapes.py's ARRANGEMENTS, the shape inventory
per order (#469, 3.0's sub-phase 4h), read under each row's order.

Every row is pinned to what the tree reads today: its roles and the
kinds it reports. A row whose reading a person would not give carries
a mark saying why it stands -- `accepted`, the document that decided
it, or `misread`, the open issue holding it -- and is pinned AS read
rather than marked xfail: an xfail needs the reading the row should
give, and a non-strict one stops watching the row, so a change that
moved it would pass. Pinned, any move fails here, and the change that
moves it edits the row and its mark in the same diff.

Negative control, 2026-10-30: with every row parsed under the default
order, 31 of the 40 family-first rows of the first inventory failed;
the 9 that still passed were the rows with a family comma, which lays
the part after it out given-first under every order.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Protocol

import pytest

import nameparser
from nameparser import Parser, Policy, Role

from ._differential_fixtures import load_tool

shapes = load_tool("shapes")
ARRANGEMENTS = shapes.ARRANGEMENTS

_ROOT = Path(__file__).resolve().parents[2]
_DECISIONS = _ROOT / "docs" / "design" / "decisions"


class _Row(Protocol):
    """shapes.Arrangement as this module reads it: tools/ is loaded by
    path, so its type is not importable here."""
    shape: int
    text: str
    positions: tuple[str, ...]
    reads: dict[str, str]
    kinds: tuple[str, ...]
    accepted: str
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
    kinds = tuple(a.kind.value for a in name.ambiguities)
    mark = (f" (accepted by {arrangement.accepted}: a move changes what "
            f"that document decided, so amend it too)"
            if arrangement.accepted else
            f" (misread, #{arrangement.misread}: update the row and its "
            f"mark with the issue's decision)"
            if arrangement.misread else "")
    assert (read, kinds) == (arrangement.reads, arrangement.kinds), (
        f"{arrangement.text!r} under {_order(arrangement) or 'the default order'}"
        f" reads {read} reporting {kinds}, the inventory records "
        f"{arrangement.reads} reporting {arrangement.kinds}{mark}")


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


_DOTTED = re.compile(r"[^\W\d_]\.[^\W\d_]\.")

#: What a position needs to see in the row's text. A row's positions
#: are its own claim; these hold the ones the text can show.
_TEXT_SHOWS = {
    "comma-full-head": lambda t: "," in t and not t.startswith(","),
    "comma-one-word-head": lambda t: "," in t and not t.startswith(","),
    "comma-empty-head": lambda t: t.startswith(","),
    "title-after-empty-head": lambda t: t.startswith(","),
    "nickname-only-head": lambda t: t[:1] in "(\"" and "," in t,
    "suffix-before-comma": lambda t: "," in t,
    "suffix-after-comma": lambda t: "," in t,
    "title-after-comma": lambda t: "," in t,
    "connective-before-comma": lambda t: "," in t,
    "particle-before-comma": lambda t: "," in t,
    "nickname": lambda t: '"' in t or "(" in t,
    "dotted-suffix": lambda t: bool(_DOTTED.search(t)),
    "nfd": lambda t: unicodedata.normalize("NFC", t) != t,
    "suffix-no-comma": lambda t: True,
}


def test_an_arrangement_names_known_positions_shapes_and_roles() -> None:
    roles = {str(r) for r in Role}
    for a in ARRANGEMENTS:
        assert a.shape in shapes.SHAPES and a.shape not in (6, 7), a
        assert a.positions and set(a.positions) <= set(shapes.POSITIONS), a
        for position in a.positions:
            shows = _TEXT_SHOWS.get(position)
            assert shows is None or shows(a.text), (position, a.text)
        assert a.reads and set(a.reads) <= roles, a
        assert all(a.reads.values()), a
    texts = [(a.shape, a.text) for a in ARRANGEMENTS]
    assert len(texts) == len(set(texts))


def test_a_marked_arrangement_cites_something_that_exists() -> None:
    """`accepted` names a decisions/ key (its file must exist) or a
    repository path; `misread` an issue number; never both."""
    marked = [a for a in ARRANGEMENTS if a.accepted or a.misread]
    assert marked
    for a in marked:
        assert not (a.accepted and a.misread), a
        if a.misread is not None:
            assert isinstance(a.misread, int) and a.misread > 0, a
            continue
        if re.fullmatch(r"[A-Z]\d+", a.accepted):
            assert list(_DECISIONS.glob(f"{a.accepted}-*.md")), a
        else:
            assert (_ROOT / a.accepted).is_file(), a

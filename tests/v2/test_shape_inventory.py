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

Negative control, 2026-10-30, every row parsed under the default
order instead of its own. The final grid (104 rows, after the last
commit adding rows): 49 of its 68 family-first rows fail; of the 19
that pass, 15 hold a family comma, an empty head included, and 4 lay
out no name word by order (`(Bob), PhD`, `Freiherr St van Berg MA`). The first
grid (64 rows, f879633d): 31 of its 40 family-first rows failed, the 9
that passed being the rows with a family comma, which lays the part
after it out given-first under every order.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

import nameparser
from nameparser import Lexicon, Parser, Policy, Role

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


_LEX = Lexicon.default()
_SUFFIXES = _LEX.suffix_words | _LEX.suffix_acronyms
_DOTTED = re.compile(r"[^\W\d_]\.[^\W\d_]\.")
_ABBREVIATION = re.compile(r"[^\W\d_]{2,}\.")
_ROMAN = re.compile(r"(?=[IVXLCDM]+$)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})")


def _fold(word: str) -> str:
    return word.strip(".,()\"").lower()


def _is_title(word: str) -> bool:
    return _fold(word) in _LEX.titles or bool(_ABBREVIATION.fullmatch(word))


def _head(t: str) -> list[str]:
    return t.split(",")[0].split()


def _name_words(words: list[str]) -> int:
    """The name words of a part, counted as rules/C3 counts them for
    the shapes here: a title, a suffix and a particle (which joins the
    word after it) count as none, a connective as its word."""
    return sum(1 for w in words
               if not _is_title(w) and _fold(w) not in _SUFFIXES
               and _fold(w) not in _LEX.particles)


def _after_comma(t: str) -> list[str]:
    return t.split(",", 1)[1].split() if "," in t else []


#: What each position needs to see in the row's text. A row's
#: positions are its own claim; every one is held to the text by a
#: predicate here, cheap and vocabulary-read, so a mislabelled row
#: (`numeral` on `Dr. John Smith`) fails rather than counting as cover.
_TEXT_SHOWS: dict[str, Callable[[str], bool]] = {
    "title-front": lambda t: _is_title(t.split()[0]) or (
        bool(_after_comma(t)) and _is_title(_after_comma(t)[0])),
    "title-between": lambda t: len(t.split()) > 2
        and not _is_title(t.split()[0]) and _is_title(t.split()[1]),
    "title-end": lambda t: _fold(t.split()[-1]) in _LEX.titles,
    "title-after-comma": lambda t: bool(_head(t))
        and _is_title(t.split(",")[-1].split()[0]),
    "title-after-empty-head": lambda t: t.startswith(",")
        and _fold(t.split()[-1]) in _LEX.titles,
    "title-particle-head": lambda t: all(
        _fold(w) in _LEX.titles and _fold(w) in _LEX.particles
        for w in t.split()[:2]),
    "dual-in-title-run": lambda t: _is_title(t.split()[0])
        and _fold(t.split()[1]) in _LEX.titles
        and _fold(t.split()[1]) in _SUFFIXES,
    "shape-title": lambda t: any(
        _ABBREVIATION.fullmatch(w) and _fold(w) not in _LEX.titles
        for w in t.split()[:2]),
    "suffix-no-comma": lambda t: _fold(t.split()[-1]) in _SUFFIXES
        and "," not in t.rsplit(" ", 1)[0][-1:],
    "suffix-before-comma": lambda t: "," in t
        and _fold(_head(t)[-1]) in _SUFFIXES,
    "suffix-after-comma": lambda t: any(
        _fold(w) in _SUFFIXES for w in _after_comma(t)),
    "numeral": lambda t: any(_ROMAN.fullmatch(w) for w in t.split()),
    "dotted-suffix": lambda t: bool(_DOTTED.search(t.split()[-1])),
    "undotted-suffix": lambda t: "." not in t.split()[-1]
        and _fold(t.split()[-1]) in _LEX.suffix_words,
    "comma-full-head": lambda t: _name_words(_head(t)) >= 2 and "," in t,
    "comma-one-word-head": lambda t: _name_words(_head(t)) == 1
        and "," in t,
    "comma-empty-head": lambda t: t.startswith(","),
    "nickname-only-head": lambda t: "," in t
        and _head(t)[0][:1] in "(\"" and len(_head(t)) == 1,
    "connective-before-comma": lambda t: "," in t
        and any(_fold(w) in _LEX.conjunctions for w in _head(t)),
    "particle-before-comma": lambda t: "," in t
        and any(_fold(w) in _LEX.particles for w in _head(t)),
    "middle": lambda t: _name_words(t.split(",")[0].split()) >= 3,
    "particle": lambda t: any(_fold(w) in _LEX.particles
                              for w in t.split()),
    "nickname": lambda t: '"' in t or "(" in t,
    "nfd": lambda t: unicodedata.normalize("NFC", t) != t,
}


def test_an_arrangement_names_known_positions_shapes_and_roles() -> None:
    assert set(_TEXT_SHOWS) == set(shapes.POSITIONS)
    roles = {str(r) for r in Role}
    for a in ARRANGEMENTS:
        assert a.shape in shapes.SHAPES and a.shape not in (6, 7), a
        assert a.positions and set(a.positions) <= set(shapes.POSITIONS), a
        for position in a.positions:
            assert _TEXT_SHOWS[position](a.text), (position, a.text)
        assert a.reads and set(a.reads) <= roles, a
        assert all(a.reads.values()), a
    texts = [(a.shape, a.text) for a in ARRANGEMENTS]
    assert len(texts) == len(set(texts))


def test_a_marked_arrangement_cites_something_that_exists() -> None:
    """`accepted` names a decisions/ key, whose file must exist;
    `misread` an issue number; never both."""
    marked = [a for a in ARRANGEMENTS if a.accepted or a.misread]
    assert marked
    for a in marked:
        assert not (a.accepted and a.misread), a
        if a.misread is not None:
            assert isinstance(a.misread, int) and a.misread > 0, a
            continue
        assert re.fullmatch(r"[A-Z]\d+", a.accepted), a
        assert list(_DECISIONS.glob(f"{a.accepted}-*.md")), a

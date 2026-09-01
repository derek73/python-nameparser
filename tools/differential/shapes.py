"""The input-shape inventory (#469): each shape's notation, the
name_order it is an input shape FOR, and the oldest baseline whose
worker can honor that order.

Shapes 1-3 are docs/usage.rst's three given-first arrangements.
Shapes 4-5 are the family-first arrangements: their names are only
supported UNDER their order, so the differential compares them under
it and simply not at all below min_baseline -- "we don't care what
they do in other orders" is structural, not a ledger exception
(name_order and both constants shipped in 2.0.0).

The notations are canonical SKELETONS, not exhaustive grammars: which
bucket a written word lands in (a lone post-comma credential reading
as Suffix, a trailing particle joining the Family) is the parser's
vocabulary question, not this table's. Tagging a case row with a
shape asserts that the row instantiates the shape's ARRANGEMENT under
its declared order -- not that every word-level reading the notation
could admit is pinned here.

The CJK arrangement is deliberately absent: whether it is a third
family-first shape is #469's open question, and corpus_cjk.jsonl
covers that ground meanwhile.

`order` is the PUBLIC constant name on the nameparser package, as a
string, because the consumer that matters is the generated baseline
worker: it imports a released wheel and resolves the name with
getattr, so a misspelling fails loudly there and this module needs no
nameparser import at all.
"""
from typing import NamedTuple


class Shape(NamedTuple):
    order: str | None   # public constant name on nameparser, None = default
    notation: str
    min_baseline: str   # oldest baseline that supports the order


SHAPES: dict[int, Shape] = {
    1: Shape(None,
             'Title Given "Nickname" Middle Middle Family Suffix',
             "1.4.0"),
    2: Shape(None,
             "Family [Suffix], Title Given (Nickname) Middle Middle[,] "
             "Suffix [, Suffix]",
             "1.4.0"),
    3: Shape(None,
             "Title Given Middle Family [Suffix], Suffix [, Suffix]",
             "1.4.0"),
    4: Shape("FAMILY_FIRST",
             "Title Family Given Middle Middle [Particle] [, Suffix]",
             "2.0.0"),
    5: Shape("FAMILY_FIRST_GIVEN_LAST",
             "Title Family Middle Middle Given [, Suffix]",
             "2.0.0"),
}

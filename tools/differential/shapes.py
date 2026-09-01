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

Shapes 6-7 are the CJK arrangements (#469's third-shape question,
settled 2026-09-01): shape 6 is family-first CJK, shape 7 is a
source-order transcription listing. Both carry `order=None` -- not
because they are order-less, but because the family-first (resp.
source-order) reading is SCRIPT-carried rather than declared: a pure
shape 6/7 string parses correctly under the DEFAULT policy already
(rules.md#W4, T2/T3), the same way DEFAULT_SCRIPT_ORDERS routes Han/
Hangul/Hiragana to family-first without a Policy saying so. A shape
whose reading depends on the string's own script has nothing for
`order` to name.

Their `min_baseline` (2.1.0, when East Asian support shipped) is
DOCUMENTARY rather than a skip trigger, and that is a real asymmetry
with shapes 4/5: those two skip below their baseline because Policy
itself (and the order it carries) did not exist yet -- an order-
bearing shape sent to a pre-Policy worker has nothing to apply.
Shapes 6/7 need no such protection: `order` is None here, so at
1.4.0/2.0.0 these strings are compared as opaque tokens rather than
skipped -- the old baselines DO parse them, just without the script
rules, and the resulting diffs are already the classified East Asian
arc (fix(cjk-*) et al.), not an unhandled gap. compare.py's
min-baseline skip (main(), the `dropped`/`kept` split) is gated on
`shapes_by_id[shape].order is not None` precisely so this holds: it
drops an order-bearing entry below its shape's minimum, and leaves an
order-None entry -- shapes 1-3 as much as 6/7 -- to compare at every
baseline regardless of min_baseline. (Verified 2026-09-01: before
that gate existed the skip was keyed on `shape is not None` alone,
which happened to be harmless only because shapes 1-3 all carry
min_baseline "1.4.0", the earliest baseline the gate ever runs, so no
order-None shape had ever actually triggered it. Shapes 6/7, the
first order-None shapes with a later minimum, would have -- silently
dropping the "already classified" comparison this paragraph
describes. The `order is not None` gate closes that.)

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
    # For an order-bearing shape: the oldest baseline that can honor
    # the order (compare.py skips an earlier one). For an order-None
    # shape: documentary only, recording when the reading shipped --
    # see the module docstring's shapes-6/7 paragraph for why that is
    # not a skip trigger.
    min_baseline: str


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
    6: Shape(None,
             "Family Given [Honorific]",
             "2.1.0"),
    7: Shape(None,
             "Given[·Given]·Family / katakana transcription (source order)",
             "2.1.0"),
}

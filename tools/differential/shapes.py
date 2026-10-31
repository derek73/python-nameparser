"""The input-shape inventory (#469): each shape's notation, the
name_order it is an input shape FOR, and the oldest baseline whose
worker can honor that order.

Shapes 1-3 are docs/usage.rst's three given-first arrangements.
Shapes 4-5 are the family-first arrangements: their names are only
supported UNDER their order, so the snapshot reads them under it, and
compare.py does not compare them at all below min_baseline -- "we
don't care what they do in other orders" is structural (name_order
and both constants shipped in 2.0.0).

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
(rules/W4, T2/T3), the same way DEFAULT_SCRIPT_ORDERS routes Han/
Hangul/Hiragana to family-first without a Policy saying so. A shape
whose reading depends on the string's own script has nothing for
`order` to name.

Their `min_baseline` (2.1.0, when East Asian support shipped) is
DOCUMENTARY: compare.py skips only an ORDER-bearing entry below its
shape's minimum, since an order sent to a pre-Policy worker has
nothing to apply. An order-None string is compared at every baseline;
the old baselines parse it, just without the script rules.

ARRANGEMENTS (#469, 3.0's sub-phase 4h) lists, per order, the written
arrangements each shape's order is read in: where a title (front,
between the family and the given name, end), a suffix (a generation
or a credential, before or after a comma), a particle and a nickname
sit, and the four comma shapes (none, a full head, a one-word head,
an empty head). A SHAPE stays the corpus tag that carries the order
and the min_baseline: one skeleton per comma family under the default
order (2 a family comma, 3 a suffix comma, 1 none), and ONE per
family-first order, whose rows with a family comma are tagged 4 or 5
though those notations write none, the comma laying the part after it
out given-first under every order (decisions/O7). An arrangement's tag
therefore names its order, which is what the corpus reads it by, and
its own `notation` names the arrangement. An arrangement names the
shape it is written under and inherits both, so `build_conventions_corpus._shape_for`'s one shape
per order and compare.py's skip are untouched. Each row records what
the tree reads today: every role that is not empty, and the kind of
every ambiguity reported. A row whose reading a person would not give
says why it stands: `accepted`, the document that decided it (a
decisions/ key such as "H5", or a repository path), or `misread`, the
open issue that holds the question, its reading pinned AS read until
that issue decides. tests/v2/test_shape_inventory.py reads every row
under its order, so a change that moves one fails there and edits the
row, and its mark, in the same diff.

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
             "Suffix [, Suffix or Title]",
             "1.4.0"),
    3: Shape(None,
             "Title Given Middle Family [Suffix], Suffix or Title "
             "[, Suffix or Title]",
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


#: The positions an order's arrangements must cover between them,
#: each row naming the ones it instantiates. "title-between" is the
#: title between the family and the given name, a slot only a
#: family-first order has (#938, declined: decisions/H5). The second
#: line onward are nameparser/AGENTS.md's sweep items: a nickname-only
#: head, a connective or particle surname before a comma, two
#: title-particles at the head, a dual (title and suffix) second in a
#: title run, a trailing title after an empty head, a title after a
#: full head's comma, and the spelling sweep's shape paths (a roman
#: numeral, an unlisted dotted suffix, an undotted suffix word, a
#: title inferred by its period shape) and the encoding's (a letter
#: written decomposed, NFD).
POSITIONS = ("title-front", "title-between", "title-end",
             "suffix-no-comma", "suffix-before-comma",
             "suffix-after-comma", "comma-full-head",
             "comma-one-word-head", "comma-empty-head", "middle",
             "particle", "nickname",
             "nickname-only-head", "connective-before-comma",
             "particle-before-comma", "title-particle-head",
             "dual-in-title-run", "title-after-empty-head",
             "title-after-comma", "numeral", "dotted-suffix",
             "undotted-suffix", "shape-title", "nfd")

#: The positions an order has no slot for, by order (None = default).
NOT_A_SLOT: dict[str | None, frozenset[str]] = {
    None: frozenset({"title-between"}),
    "FAMILY_FIRST": frozenset(),
    "FAMILY_FIRST_GIVEN_LAST": frozenset(),
}


class Arrangement(NamedTuple):
    shape: int                    # SHAPES id; its order reads the text
    notation: str                 # the arrangement, in SHAPES' notation
    text: str
    positions: tuple[str, ...]    # of POSITIONS
    reads: dict[str, str]         # every role not empty, as read today
    kinds: tuple[str, ...] = ()   # each ambiguity's kind, in report order
    # Where a person would not read the row so: the document deciding
    # the reading (a decisions/ key, or a repository path), or the open
    # issue holding it. At most one; neither where the reading is plain.
    accepted: str = ""
    misread: int | None = None
    note: str = ""


ARRANGEMENTS: tuple[Arrangement, ...] = (
    # GIVEN_FIRST (the default): shapes 1, 2 (a family comma) and 3
    # (a suffix comma).
    Arrangement(1, "Title Given Family", "Dr. John Smith",
                ("title-front",),
                {"title": "Dr.", "given": "John", "family": "Smith"}),
    Arrangement(1, "Given Middle Family", "John Quincy Adams",
                ("middle",),
                {"given": "John", "middle": "Quincy", "family": "Adams"}),
    Arrangement(1, "Given Family Title.", "John Smith Prof.",
                ("title-end",),
                {"title": "Prof.", "given": "John", "family": "Smith"},
                note="period-marked, rules/H5"),
    Arrangement(1, "Given Family Title", "John Smith Prof",
                ("title-end",),
                {"given": "John", "middle": "Smith", "family": "Prof"},
                accepted="H5",
                note="a bare trailing title is a name word, rules/H5"),
    Arrangement(1, "Given Family Credential Title", "John Smith PhD Prof",
                ("title-end",),
                {"title": "Prof", "given": "John", "family": "Smith",
                 "suffix": "PhD"},
                note="a credential starts the trailing run, rules/H5"),
    Arrangement(1, "Given Family Suffix", "John Smith Jr.",
                ("suffix-no-comma",),
                {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Arrangement(1, "Given Family Credential", "John Smith PhD",
                ("suffix-no-comma",),
                {"given": "John", "family": "Smith", "suffix": "PhD"}),
    Arrangement(1, "Given Particle Family", "Juan de la Vega",
                ("particle",),
                {"given": "Juan", "family": "de la Vega"}),
    Arrangement(1, 'Given "Nickname" Family', 'John "Jack" Smith',
                ("nickname",),
                {"given": "John", "family": "Smith", "nickname": "Jack"}),
    Arrangement(3, "Given Family, Suffix", "John Smith, Jr.",
                ("suffix-after-comma", "comma-full-head"),
                {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Arrangement(3, "Given Family, Credential", "John Smith, PhD",
                ("suffix-after-comma", "comma-full-head"),
                {"given": "John", "family": "Smith", "suffix": "PhD"}),
    Arrangement(3, "Given Family, Suffix, Credential",
                "John Smith, Jr., PhD",
                ("suffix-after-comma", "comma-full-head"),
                {"given": "John", "family": "Smith", "suffix": "Jr., PhD"}),
    Arrangement(2, "Family, Given", "Smith, John",
                ("comma-one-word-head",),
                {"given": "John", "family": "Smith"}),
    Arrangement(2, "Family, Title Given", "Smith, Dr. John",
                ("title-front", "comma-one-word-head"),
                {"title": "Dr.", "given": "John", "family": "Smith"}),
    Arrangement(2, "Title Family, Given", "Dr. Smith, John",
                ("title-front", "comma-one-word-head"),
                {"title": "Dr.", "given": "John", "family": "Smith"},
                note="rules/H6"),
    Arrangement(2, "Family, Given Title.", "Smith, John Prof.",
                ("title-end", "comma-one-word-head"),
                {"title": "Prof.", "given": "John", "family": "Smith"}),
    Arrangement(2, "Family, Given Salutation", "Doe, Jane Mrs",
                ("title-end", "comma-one-word-head"),
                {"title": "Mrs", "given": "Jane", "family": "Doe"},
                note="rules/H8"),
    Arrangement(2, "Family, Given Suffix", "Smith, John Jr.",
                ("suffix-no-comma", "comma-one-word-head"),
                {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Arrangement(2, "Family Suffix, Given", "Smith Jr., John",
                ("suffix-before-comma", "comma-one-word-head"),
                {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Arrangement(2, "Family, Given, Suffix", "Smith, John, Jr.",
                ("suffix-after-comma", "comma-one-word-head"),
                {"given": "John", "family": "Smith", "suffix": "Jr."}),
    Arrangement(2, "Particle Family, Given", "de la Vega, Juan",
                ("particle", "particle-before-comma", "comma-one-word-head"),
                {"given": "Juan", "family": "de la Vega"}),
    Arrangement(2, "Family, Given (Nickname)", "Smith, John (Jack)",
                ("nickname", "comma-one-word-head"),
                {"given": "John", "family": "Smith", "nickname": "Jack"}),
    Arrangement(2, ", Given", ", John",
                ("comma-empty-head",),
                {"given": "John"},
                note="an empty family, rules/C15"),
    Arrangement(2, ", Credential", ", PhD",
                ("comma-empty-head",),
                {"suffix": "PhD"}),
    # The sweep items (nameparser/AGENTS.md).
    Arrangement(2,
                '(Nickname), Credential',
                '(Bob), PhD',
                ('nickname-only-head',),
                {'suffix': 'PhD', 'nickname': 'Bob'}),
    Arrangement(2,
                'Family y Family, Given',
                'Vega y Lopez, Juan',
                ('connective-before-comma', 'comma-one-word-head'),
                {'given': 'Juan', 'family': 'Vega y Lopez'}),
    Arrangement(2,
                'Family y Family Suffix, Credential Name',
                'Vega y Lopez Jr., PhD Jones',
                ('connective-before-comma', 'suffix-before-comma'),
                {'given': 'Vega', 'middle': 'y', 'family': 'Lopez', 'suffix': 'Jr., PhD Jones'},
                ('suffix-or-name',),
                accepted='nameparser/AGENTS.md',
                note="the connective is not joined behind a suffix before the comma (#613), nameparser/AGENTS.md's one-word-path paragraph"),
    Arrangement(1,
                'Title Title Particle Family Credential',
                'Freiherr St van Berg MA',
                ('title-particle-head',),
                {'title': 'Freiherr St', 'family': 'van Berg', 'suffix': 'MA'},
                ('particle-or-given',)),
    Arrangement(2,
                'Title Dual Family, Given',
                'Rev. Sr. Smith, Mary',
                ('dual-in-title-run', 'comma-one-word-head'),
                {'title': 'Rev. Sr.', 'given': 'Mary', 'family': 'Smith'}),
    Arrangement(2,
                ', Given Title.',
                ', Ma Dr.',
                ('title-after-empty-head', 'comma-empty-head'),
                {'title': 'Dr.', 'family': 'Ma'},
                ('suffix-or-name',),
                accepted='C15',
                note="rules/H1's title and one name word, the exception rules/C15 names"),
    Arrangement(3,
                'Given Family, Title.',
                'John Smith, Dr.',
                ('title-after-comma', 'comma-full-head'),
                {'title': 'Dr.', 'given': 'John', 'family': 'Smith'}),
    Arrangement(1,
                'Given Family Numeral',
                'John Smith III',
                ('numeral',),
                {'given': 'John', 'family': 'Smith', 'suffix': 'III'}),
    Arrangement(1,
                'Given Family X.Y.Z.',
                'John Smith X.Y.Z.',
                ('dotted-suffix',),
                {'given': 'John', 'family': 'Smith', 'suffix': 'X.Y.Z.'},
                ('suffix-or-name',),
                note='rules/S3'),
    Arrangement(1,
                'Given Family Suffix (undotted)',
                'John Smith Jr',
                ('undotted-suffix',),
                {'given': 'John', 'family': 'Smith', 'suffix': 'Jr'}),
    Arrangement(1,
                'Abbrev. Given Family',
                'Insp. John Smith',
                ('shape-title',),
                {'title': 'Insp.', 'given': 'John', 'family': 'Smith'},
                note='rules/H2'),
    Arrangement(1,
                'Given Particle Family (NFD)',
                'Christophe du Me\u0301nil',
                ('nfd', 'particle'),
                {'given': 'Christophe', 'family': 'du Me\u0301nil'}),

    # FAMILY_FIRST: shape 4.
    Arrangement(4, "Title Family Given", "Dr. Wang Xiaoming",
                ("title-front",),
                {"title": "Dr.", "given": "Xiaoming", "family": "Wang"}),
    Arrangement(4, "Title Family Given", "Senator Wang Xiaoming",
                ("title-front",),
                {"title": "Senator", "given": "Xiaoming", "family": "Wang"}),
    Arrangement(4, "Family Title. Given", "Wang Dr. Xiaoming",
                ("title-between",),
                {"given": "Dr.", "middle": "Xiaoming", "family": "Wang"},
                accepted="H5"),
    Arrangement(4, "Family Title Given", "Wang Dr Xiaoming",
                ("title-between",),
                {"given": "Dr", "middle": "Xiaoming", "family": "Wang"},
                accepted="H5"),
    Arrangement(4, "Family Title. Title. Given Middle",
                "Brühl Prof. Dr. Ada Cornelia",
                ("title-between", "middle"),
                {"given": "Prof.", "middle": "Dr. Ada Cornelia",
                 "family": "Brühl"},
                accepted="H5", note="the RFC's example"),
    Arrangement(4, "Family Given Title.", "Wang Xiaoming Dr.",
                ("title-end",),
                {"title": "Dr.", "given": "Xiaoming", "family": "Wang"},
                note="period-marked, rules/H5"),
    Arrangement(4, "Family Given Title", "Wang Xiaoming Senator",
                ("title-end",),
                {"given": "Xiaoming", "middle": "Senator", "family": "Wang"},
                accepted="H5"),
    Arrangement(4, "Family Given Credential Title", "Wang Xiaoming PhD Prof",
                ("title-end",),
                {"title": "Prof", "given": "Xiaoming", "family": "Wang",
                 "suffix": "PhD"}),
    Arrangement(4, "Family Given Middle", "Kovács János Péter",
                ("middle",),
                {"given": "János", "middle": "Péter", "family": "Kovács"}),
    Arrangement(4, "Family Given Suffix", "Wang Xiaoming Jr.",
                ("suffix-no-comma",),
                {"given": "Xiaoming", "family": "Wang", "suffix": "Jr."}),
    Arrangement(4, "Family Given Credential", "Wang Xiaoming PhD",
                ("suffix-no-comma",),
                {"given": "Xiaoming", "family": "Wang", "suffix": "PhD"}),
    Arrangement(4, "Family Given, Suffix", "Wang Xiaoming, Jr.",
                ("suffix-after-comma", "comma-full-head"),
                {"given": "Xiaoming", "family": "Wang", "suffix": "Jr."}),
    Arrangement(4, "Family Given, Credential", "Wang Xiaoming, PhD",
                ("suffix-after-comma", "comma-full-head"),
                {"given": "Xiaoming", "family": "Wang", "suffix": "PhD"}),
    Arrangement(4, "Family Given, Suffix, Credential",
                "Wang Xiaoming, Jr., PhD",
                ("suffix-after-comma", "comma-full-head"),
                {"given": "Xiaoming", "family": "Wang",
                 "suffix": "Jr., PhD"}),
    Arrangement(4, "Family Suffix, Given", "Wang Jr., Xiaoming",
                ("suffix-before-comma", "comma-one-word-head"),
                {"given": "Xiaoming", "family": "Wang", "suffix": "Jr."}),
    Arrangement(4, "Family, Given", "Wang, Xiaoming",
                ("comma-one-word-head",),
                {"given": "Xiaoming", "family": "Wang"}),
    Arrangement(4, "Family, Title Given", "Wang, Dr. Xiaoming",
                ("title-front", "comma-one-word-head"),
                {"title": "Dr.", "given": "Xiaoming", "family": "Wang"}),
    Arrangement(4, "Title Family, Given", "Dr. Wang, Xiaoming",
                ("title-front", "comma-one-word-head"),
                {"title": "Dr.", "given": "Xiaoming", "family": "Wang"}),
    Arrangement(4, ", Given", ", Xiaoming",
                ("comma-empty-head",),
                {"given": "Xiaoming"}),
    Arrangement(4, "Particle Family Given", "de Mesnil Jean",
                ("particle",),
                {"given": "Jean", "family": "de Mesnil"},
                note="a never-given particle folds, rules/P1"),
    Arrangement(4, "Particle Family Given", "van Gogh Vincent",
                ("particle",),
                {"given": "Gogh", "middle": "Vincent", "family": "van"},
                ("particle-or-given",), accepted="AGENTS.md",
                note="an ambiguous particle opening the name is left to "
                     "position and reported, root AGENTS.md's particles "
                     "paragraph"),
    Arrangement(4, "Family Given Particle", "Ménil Christophe du",
                ("particle",),
                {"given": "Christophe", "family": "du Ménil"},
                ("particle-or-given",), note="rules/P6"),
    Arrangement(4, 'Family "Nickname" Given', 'Wang "Tony" Xiaoming',
                ("nickname",),
                {"given": "Xiaoming", "family": "Wang", "nickname": "Tony"}),
    Arrangement(4, "Family Given (Nickname)", "Wang Xiaoming (Tony)",
                ("nickname",),
                {"given": "Xiaoming", "family": "Wang", "nickname": "Tony"}),
    # The sweep items.
    Arrangement(4,
                '(Nickname), Credential',
                '(Bob), PhD',
                ('nickname-only-head',),
                {'suffix': 'PhD', 'nickname': 'Bob'}),
    Arrangement(4,
                'Family y Family, Given',
                'Vega y Lopez, Juan',
                ('connective-before-comma', 'comma-one-word-head'),
                {'given': 'Juan', 'family': 'Vega y Lopez'}),
    Arrangement(4,
                'Family y Family Suffix, Credential Name',
                'Vega y Lopez Jr., PhD Jones',
                ('connective-before-comma', 'suffix-before-comma'),
                {'given': 'y', 'middle': 'Lopez', 'family': 'Vega', 'suffix': 'Jr., PhD Jones'},
                ('suffix-or-name',),
                note="the default order's division of the words "
                     "(nameparser/AGENTS.md, #613) laid out by the order; "
                     "no document states it under a family-first order"),
    Arrangement(4,
                'Particle Family, Given',
                'de la Vega, Juan',
                ('particle-before-comma', 'comma-one-word-head'),
                {'given': 'Juan', 'family': 'de la Vega'}),
    Arrangement(4,
                'Title Title Particle Family Credential',
                'Freiherr St van Berg MA',
                ('title-particle-head',),
                {'title': 'Freiherr St', 'family': 'van Berg', 'suffix': 'MA'},
                ('particle-or-given',)),
    Arrangement(4,
                'Title Dual Family Given',
                'Rev. Sr. Wang Xiaoming',
                ('dual-in-title-run',),
                {'title': 'Rev. Sr.', 'given': 'Xiaoming', 'family': 'Wang'}),
    Arrangement(4,
                ', Given Title.',
                ', Xiaoming Dr.',
                ('title-after-empty-head', 'comma-empty-head'),
                {'title': 'Dr.', 'family': 'Xiaoming'},
                accepted='C15',
                note="rules/H1's title and one name word, the exception rules/C15 names"),
    Arrangement(4,
                'Family Given, Title.',
                'Wang Xiaoming, Dr.',
                ('title-after-comma', 'comma-full-head'),
                {'title': 'Dr.', 'given': 'Xiaoming', 'family': 'Wang'}),
    Arrangement(4,
                'Family Given Numeral',
                'Wang Xiaoming III',
                ('numeral',),
                {'given': 'Xiaoming', 'family': 'Wang', 'suffix': 'III'}),
    Arrangement(4,
                'Family Given X.Y.Z.',
                'Wang Xiaoming X.Y.Z.',
                ('dotted-suffix',),
                {'given': 'Xiaoming', 'family': 'Wang', 'suffix': 'X.Y.Z.'},
                ('suffix-or-name',),
                note='rules/S3'),
    Arrangement(4,
                'Family Given Suffix (undotted)',
                'Wang Xiaoming Jr',
                ('undotted-suffix',),
                {'given': 'Xiaoming', 'family': 'Wang', 'suffix': 'Jr'}),
    Arrangement(4,
                'Abbrev. Family Given',
                'Insp. Wang Xiaoming',
                ('shape-title',),
                {'title': 'Insp.', 'given': 'Xiaoming', 'family': 'Wang'},
                note='rules/H2'),
    Arrangement(4,
                'Family Abbrev. Given',
                'Wang Insp. Xiaoming',
                ('title-between', 'shape-title'),
                {'given': 'Insp.', 'middle': 'Xiaoming', 'family': 'Wang'},
                accepted='H5'),
    Arrangement(4,
                'Family Given Particle (NFD)',
                'Me\u0301nil Christophe du',
                ('nfd', 'particle'),
                {'given': 'Christophe', 'family': 'du Me\u0301nil'},
                ('particle-or-given',),
                note='rules/P6'),

    # FAMILY_FIRST_GIVEN_LAST: shape 5. A family comma lays the part
    # after it out given-first under every order (decisions/O7).
    Arrangement(5, "Title Family Middle Given", "Dr. Nguyen Thi Mai",
                ("title-front", "middle"),
                {"title": "Dr.", "given": "Mai", "middle": "Thi",
                 "family": "Nguyen"}),
    Arrangement(5, "Family Title. Middle Given", "Nguyen Dr. Thi Mai",
                ("title-between",),
                {"given": "Mai", "middle": "Dr. Thi", "family": "Nguyen"},
                accepted="H5"),
    Arrangement(5, "Family Middle Given Title.", "Nguyen Thi Mai Dr.",
                ("title-end",),
                {"title": "Dr.", "given": "Mai", "middle": "Thi",
                 "family": "Nguyen"},
                note="period-marked, rules/H5"),
    Arrangement(5, "Family Middle Given Title", "Nguyen Thi Mai Senator",
                ("title-end",),
                {"given": "Senator", "middle": "Thi Mai",
                 "family": "Nguyen"},
                accepted="H5"),
    Arrangement(5, "Family Middle Given Suffix", "Nguyen Thi Mai Jr.",
                ("suffix-no-comma",),
                {"given": "Mai", "middle": "Thi", "family": "Nguyen",
                 "suffix": "Jr."}),
    Arrangement(5, "Family Middle Given Credential", "Nguyen Thi Mai PhD",
                ("suffix-no-comma",),
                {"given": "Mai", "middle": "Thi", "family": "Nguyen",
                 "suffix": "PhD"}),
    Arrangement(5, "Family Middle Given, Suffix", "Nguyen Thi Mai, Jr.",
                ("suffix-after-comma", "comma-full-head"),
                {"given": "Mai", "middle": "Thi", "family": "Nguyen",
                 "suffix": "Jr."}),
    Arrangement(5, "Family Middle Given, Credential", "Nguyen Thi Mai, PhD",
                ("suffix-after-comma", "comma-full-head"),
                {"given": "Mai", "middle": "Thi", "family": "Nguyen",
                 "suffix": "PhD"}),
    Arrangement(5, "Family Suffix, Given Middle", "Nguyen Jr., Thi Mai",
                ("suffix-before-comma", "comma-one-word-head"),
                {"given": "Thi", "middle": "Mai", "family": "Nguyen",
                 "suffix": "Jr."}),
    Arrangement(5, "Family, Given Middle", "Nguyen, Thi Mai",
                ("comma-one-word-head",),
                {"given": "Thi", "middle": "Mai", "family": "Nguyen"}),
    Arrangement(5, "Family, Title Given Middle", "Nguyen, Dr. Thi Mai",
                ("title-front", "comma-one-word-head"),
                {"title": "Dr.", "given": "Thi", "middle": "Mai",
                 "family": "Nguyen"}),
    Arrangement(5, ", Given Middle", ", Thi Mai",
                ("comma-empty-head",),
                {"given": "Thi", "middle": "Mai"}),
    Arrangement(5, "Particle Family Middle Given", "de Mesnil Thi Mai",
                ("particle",),
                {"given": "Mai", "middle": "Thi", "family": "de Mesnil"},
                note="rules/P1"),
    Arrangement(5, "Family Middle Particle", "Mesnil Jean de",
                ("particle",),
                {"given": "de", "middle": "Jean", "family": "Mesnil"},
                accepted="P1",
                note="the given slot is the caller's declaration, "
                     "rules/P1"),
    Arrangement(5, 'Family "Nickname" Middle Given', 'Nguyen "Tony" Thi Mai',
                ("nickname",),
                {"given": "Mai", "middle": "Thi", "family": "Nguyen",
                 "nickname": "Tony"}),
    Arrangement(5, "Family Middle Given (Nickname)", "Nguyen Thi Mai (Tony)",
                ("nickname",),
                {"given": "Mai", "middle": "Thi", "family": "Nguyen",
                 "nickname": "Tony"}),
    # The sweep items.
    Arrangement(5,
                '(Nickname), Credential',
                '(Bob), PhD',
                ('nickname-only-head',),
                {'suffix': 'PhD', 'nickname': 'Bob'}),
    Arrangement(5,
                'Family y Family, Given',
                'Vega y Lopez, Juan',
                ('connective-before-comma', 'comma-one-word-head'),
                {'given': 'Juan', 'family': 'Vega y Lopez'}),
    Arrangement(5,
                'Family y Family Suffix, Credential Name',
                'Vega y Lopez Jr., PhD Jones',
                ('connective-before-comma', 'suffix-before-comma'),
                {'given': 'Lopez', 'middle': 'y', 'family': 'Vega', 'suffix': 'Jr., PhD Jones'},
                ('suffix-or-name',),
                note="the default order's division of the words "
                     "(nameparser/AGENTS.md, #613) laid out by the order; "
                     "no document states it under a family-first order"),
    Arrangement(5,
                'Particle Family, Given Middle',
                'de la Vega, Thi Mai',
                ('particle-before-comma', 'comma-one-word-head'),
                {'given': 'Thi', 'middle': 'Mai', 'family': 'de la Vega'}),
    Arrangement(5,
                'Title Title Particle Family Credential',
                'Freiherr St van Berg MA',
                ('title-particle-head',),
                {'title': 'Freiherr St', 'family': 'van Berg', 'suffix': 'MA'},
                ('particle-or-given',)),
    Arrangement(5,
                'Title Dual Family Middle Given',
                'Rev. Sr. Nguyen Thi Mai',
                ('dual-in-title-run',),
                {'title': 'Rev. Sr.', 'given': 'Mai', 'middle': 'Thi', 'family': 'Nguyen'}),
    Arrangement(5,
                ', Given Middle Title.',
                ', Thi Mai Dr.',
                ('title-after-empty-head', 'comma-empty-head'),
                {'title': 'Dr.', 'given': 'Thi', 'middle': 'Mai'}),
    Arrangement(5,
                'Family Middle Given, Title.',
                'Nguyen Thi Mai, Dr.',
                ('title-after-comma', 'comma-full-head'),
                {'title': 'Dr.', 'given': 'Mai', 'middle': 'Thi', 'family': 'Nguyen'}),
    Arrangement(5,
                'Family Middle Given Numeral',
                'Nguyen Thi Mai III',
                ('numeral',),
                {'given': 'Mai', 'middle': 'Thi', 'family': 'Nguyen', 'suffix': 'III'}),
    Arrangement(5,
                'Family Middle Given X.Y.Z.',
                'Nguyen Thi Mai X.Y.Z.',
                ('dotted-suffix',),
                {'given': 'Mai', 'middle': 'Thi', 'family': 'Nguyen', 'suffix': 'X.Y.Z.'},
                ('suffix-or-name',),
                note='rules/S3'),
    Arrangement(5,
                'Family Middle Given Suffix (undotted)',
                'Nguyen Thi Mai Jr',
                ('undotted-suffix',),
                {'given': 'Mai', 'middle': 'Thi', 'family': 'Nguyen', 'suffix': 'Jr'}),
    Arrangement(5,
                'Abbrev. Family Middle Given',
                'Insp. Nguyen Thi Mai',
                ('shape-title',),
                {'title': 'Insp.', 'given': 'Mai', 'middle': 'Thi', 'family': 'Nguyen'},
                note='rules/H2'),
    Arrangement(5,
                'Family Abbrev. Middle Given',
                'Nguyen Insp. Thi Mai',
                ('title-between', 'shape-title'),
                {'given': 'Mai', 'middle': 'Insp. Thi', 'family': 'Nguyen'},
                accepted='H5'),
    Arrangement(5,
                'Particle Family Middle Given (NFD)',
                'du Me\u0301nil Thi Mai',
                ('nfd', 'particle'),
                {'given': 'Mai', 'middle': 'Me\u0301nil Thi', 'family': 'du'},
                ('particle-or-given',),
                accepted='AGENTS.md',
                note="an ambiguous particle opening the name is left to position and reported, root AGENTS.md's particles paragraph"),
)

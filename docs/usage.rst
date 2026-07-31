Using the parser
================

Requires Python 3.11+.  ``pip install nameparser``

Parse a name
------------

.. doctest::

    >>> from nameparser import parse
    >>> name = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> name.given, name.family
    ('Juan', 'de la Vega')
    >>> name.title, name.middle, name.suffix
    ('Dr.', 'Q. Xavier', 'III')

A parsed name has seven fields: ``title``, ``given``, ``middle``,
``family``, ``suffix``, ``nickname``, and ``maiden``. Parsing never
raises; unparseable input yields a :class:`~nameparser.ParsedName` with
empty fields plus any ``ambiguities`` the parser noticed along the way
(see `When the parser had to guess`_ below, and :doc:`concepts` for why
they exist). A name with no fields set is falsy, which is how you tell
"nothing parsed" from "parsed to something":

.. doctest::

    >>> bool(parse("")), bool(parse("   ")), bool(parse("John"))
    (False, False, True)

Input shapes
-------------

Three arrangements are understood, and every piece of each is optional:

1. ``Title Given "Nickname" Middle Middle Family Suffix``
2. ``Family [Suffix], Title Given (Nickname) Middle Middle[,] Suffix [, Suffix]``
3. ``Title Given Middle Family [Suffix], Suffix [, Suffix]``

The last two differ in what the comma is doing. In form 2 it separates
the family name from the rest, so the family name comes first; in form
3 it only sets off suffixes, and the name before it is still
given-then-family:

.. doctest::

    >>> parse("de la Vega, Juan Q. Xavier III").family   # form 2
    'de la Vega'
    >>> parse("Doe Jr., John").suffix                    # form 2, suffix before the comma
    'Jr.'
    >>> parse("John Doe, Jr.").family                    # form 3
    'Doe'

For family-first input *without* a comma — common outside Europe — set
``name_order``; see :doc:`customize`. Names written in Han or Hangul,
and Japanese names written in kanji and kana, are the exception that
needs no setting at all: see `East Asian names`_ below.

Words that attach to their neighbors
--------------------------------------

Input shapes tell you where the fields sit. This tells you which words
merge into one field instead of standing alone — between them, that is
most of what decides a parse.

Most words stand alone. A few pull in a neighbor, and each kind pulls
into one particular field — so this table is also a map of which fields
get built by attachment rather than by position. Titles and suffixes
attach only to *adjacent words of their own kind* (a run of titles
chains into one, but a title never swallows a plain name); the rest
reach forward to pull in the next word, whatever it is. Follow a row's
name to its full vocabulary set:

.. list-table::
   :header-rows: 1
   :widths: 22 26 12 40

   * - Words
     - Attach to
     - Field
     - Example
   * - :mod:`Titles <nameparser.config.titles>`
     - adjacent titles
     - ``title``
     - ``Asst. Vice Chancellor John`` → ``Asst. Vice Chancellor``
   * - :mod:`Suffixes <nameparser.config.suffixes>`
     - adjacent suffixes
     - ``suffix``
     - ``John Smith PhD MD`` → ``PhD, MD``
   * - :mod:`Bound given names <nameparser.config.bound_first_names>`
     - the following word
     - ``given``
     - ``abdul salam ahmed`` → ``abdul salam``
   * - :mod:`Particles <nameparser.config.prefixes>`
     - the following surname
     - ``family``
     - ``Juan de la Vega`` → ``de la Vega``
   * - :mod:`Maiden markers <nameparser.config.maiden_markers>`
     - the following name
     - ``maiden``
     - ``Jane Smith née Jones`` → ``Jones``
   * - :mod:`Conjunctions <nameparser.config.conjunctions>`
     - the words on both sides
     - any
     - ``John and Jane Smith`` → ``John and Jane``

Conjunctions are the exception the last row names: they take the field
of whatever sits on both sides, so the same ``and`` pulls two given
names together as easily as two surnames:

.. doctest::

    >>> parse("John and Jane Smith").given
    'John and Jane'
    >>> parse("Juan de la Vega y Rodriguez").family
    'de la Vega y Rodriguez'

Position matters in exactly one place: the start of a name. A particle
there has no surname to attach to yet, so it either becomes the given
name or turns the whole name into a surname, depending on whether it is
one that can double as a given name:

.. doctest::

    >>> parse("van Gogh").given          # 'van' can be a given name
    'van'
    >>> parse("de Mesnil").given         # 'de' cannot
    ''
    >>> parse("de Mesnil").family
    'de Mesnil'

:doc:`customize` covers how to change which words are in each of these
sets, including which particles may double as given names. One shipped
vocabulary works the other way round and so is not in the table above:
:mod:`surnames <nameparser.config.surnames>` *splits* a word instead of
merging two, and is covered next.

.. _east-asian-names:

East Asian names
-----------------

A Chinese, Japanese, or Korean name written in its own script
puts the family name first: 毛泽东 is MAO Zedong, 山田太郎 is YAMADA
Taro, 김민준 is KIM Minjun. The family name is short — one Han
character or one hangul syllable, occasionally two — and comes from a
small closed set, while given names are open-ended. And in native
writing the parts are usually not separated at all: the whole name is
one unbroken run of characters. A parser therefore has two distinct
jobs here: assign family and given to the right fields, and, when the
name arrives as a single token, find the boundary inside it.

Field assignment is automatic. A name written wholly in Han characters
or hangul is assigned family-first, because every language written in
those scripts orders names that way — Chinese and Japanese share
little else, but they agree on this — so the assignment requires no
knowledge of which language the name is in:

.. doctest::

    >>> parse("毛 泽东").family
    '毛'
    >>> parse("山田 太郎").family
    '山田'

Splitting an unspaced name is also automatic, but only for Korean.
Hangul is written by exactly one language, and Korean family names are
limited to a small closed set: the census surname list is part of the
default vocabulary, and the longest listed surname at the start of an
unspaced hangul token becomes the family name:

.. doctest::

    >>> minjun = parse("김민준")
    >>> minjun.family, minjun.given
    ('김', '민준')

The same split is not automatic for Han text, because there the script
does not identify the language: 高橋一郎 is a Japanese name whose
family name is 高橋, but 高 alone is a common Chinese surname, so a
Chinese surname list would split it in the wrong place. Declaring the
language is up to you. When you know the data is Chinese, apply the
``zh`` locale pack, which carries the surname list the split needs:

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> parser_for(locales.ZH).parse("毛泽东").family
    '毛'

Chinese also has a transcription convention, and it is written in the
punctuation: a foreign name transcribed into Han characters keeps its
source order and divides its parts with the 间隔号, the interpunct
``·`` (U+00B7) — 威廉·莎士比亚 is William Shakespeare, given name
first. The dot itself is the marker, so nameparser reads U+00B7 as a
token separator when it sits between classified-script characters
(each side judged on its own — a hangul character beside a Han one
qualifies), and a dot anywhere in the name reads the whole name as a
transcription listing: it keeps the order it was written in and is
never segmented — the role pure katakana plays for Japanese
transcriptions, played here by the divider instead of the script.
Because only classified characters on both sides make it a divider,
the same codepoint interior to a Latin-script name — the Catalan punt
volat in ``Gal·la`` — is untouched, and a dot with a classified
character on just one side (``王·Smith``) stays part of the word
undivided. The Japanese middle dot ・ (covered next) is a different
mark carrying a different convention, and keeps its own reading.

Japanese
~~~~~~~~~

Japanese writes a name in three scripts at once. Family names and most
given names are kanji — the same characters Chinese uses — but a given
name is often written in one of the two kana syllabaries instead:
hiragana (高橋みなみ) or katakana (山田エミ). The two syllabaries carry
different information about whose name it is. Hiragana never
transcribes a foreign name, so a name that mixes kanji and kana is a
Japanese person's name, written in Japanese order. Katakana is
ambiguous: native given names use it, but katakana is also how
Japanese text writes a *foreign* name — マイケル・ジャクソン is Michael
Jackson — and a transcription keeps the source language's order, given
name first, its parts divided by the middle dot ・ (the nakaguro,
U+30FB) rather than by a space.

Two behaviors follow from that without any configuration. A name whose
characters stay within kanji and kana and carry at least one kana is
assigned family-first, like any other native-script East Asian name: it
cannot be Chinese, and it is not a transcription, because a
transcription would have been kana alone.

.. doctest::

    >>> minami = parse("高橋 みなみ")
    >>> minami.family, minami.given
    ('高橋', 'みなみ')
    >>> parse("山田 エミ").family
    '山田'

And the middle dot separates tokens the way a space does, so a
transcribed foreign name divides into its parts — which, being wholly
katakana, keep the order they were written in:

.. doctest::

    >>> michael = parse("マイケル・ジャクソン")
    >>> michael.given, michael.family
    ('マイケル', 'ジャクソン')

Dividing an *unspaced* Japanese name is a separate matter, and one no
surname list can settle: family and given names draw on the same
kanji, both sides run one to four characters, and the reading rather
than the spelling decides most divisions. nameparser therefore takes a
**segmenter** — a callable from token text to a division — and ships a
factory wrapping `namedivider-python
<https://pypi.org/project/namedivider-python/>`_, an optional
dependency installed with the ``ja`` extra:

.. code-block:: console

    $ pip install "nameparser[ja]"

.. code-block:: python

    from nameparser import locales, parser_for

    parser = parser_for(locales.JA, segmenter=locales.ja_segmenter())
    parser.parse("山田太郎").family        # '山田'

Both halves are required, and they do different jobs: the ``ja`` pack
activates division for Japanese text, and the segmenter performs it.
``ja_segmenter()`` wraps namedivider's ``BasicNameDivider``, which
reads data bundled in the installed package;
``ja_segmenter(gbdt=True)`` selects its gradient-boosted divider
instead, which is more accurate and downloads its model and surname
files from the network on first use — worth knowing before deploying
it somewhere sandboxed or air-gapped.

Boundaries
~~~~~~~~~~~

Several boundaries apply to all of the above. Romanized names ("Kim
Min-jun", "Yamada Taro") are Latin script and follow the ordinary
positional rules — order genuinely varies in romanized data, so
nothing script-based applies. A name written wholly in katakana stays
positional for the reason given above, pack or no pack: it is
predominantly a transcription, and a transcription is already in the
order it should be read in. A Han transcription written with a space
instead of the 间隔号 (威廉 莎士比亚) carries nothing to distinguish it
from a native two-token name and keeps the family-first reading — the
dot is the marker, and without it there is no signal. The same holds
for a transcription typed with the Japanese middle dot (威廉・莎士比亚):
each dot carries its own script's convention, the nakaguro's is
Japanese roster formatting rather than transcription, so only the
Chinese dot rescues the source order. And a comma disables the script
behaviors entirely, on the reasoning ``name_order`` already follows: whoever
wrote the comma has already said where the family name ends.

Honorifics and degrees follow a CJK name, and both the spaced and the
glued forms are recognized as suffixes: ``王小明 先生`` reads family
王小明 with 先生 in ``suffix``, and so do glued ``田中さん``,
``山田太郎様`` and ``김민준씨``. The honorific is split off the end of
the last name token before the name is split or ordered, so those
rules see the name without it — which is why ``김민준씨`` still divides
into family 김 and given 민준, and why a configured Japanese segmenter
is handed 山田太郎 rather than 山田太郎様. The comma rule above comes
first, though, and covers this too: in ``田中さん, 太郎`` the writer
has already said where the family name ends, so nothing is peeled and
the family name is the whole ``田中さん``. A 间隔号-divided
transcription opts out for its own reason, the same way.

Where a segmenter divides the name, the two spellings part company. A
spaced honorific is a token boundary the writer typed, and the
segmenter is asked only where an undivided name divides — so anything
standing beside the name calls it off, honorific or not: under the
Japanese pack ``佐藤 氏`` keeps family 佐藤, where bare ``佐藤`` would
have been divided 佐 + 藤. That is a conservative reading rather than
a principled one; a spaced honorific cannot be told apart from a
spaced given name by position, and treating it as one keeps four real
surnames whole (``佐藤 氏``, ``田中 様``, ``鈴木 先生``, ``中村 教授``)
at the price of one division it declines to make (``山田太郎 様``). A
glued honorific carries no boundary at all — its writer drew none
anywhere — so ``田中さん`` divides the way bare ``田中`` does, into
family 田 and given 中, with さん in ``suffix``. Writing the honorific
spaced is therefore also how you ask for a family name to be kept
whole, short of declining the pack.

The glued reading is deliberately narrower than the spaced one. A
spaced honorific sits behind a boundary its writer drew; a glued one
has only itself to go on, so a word peels off the end of a name only
if it could never BE the end of a name. 씨, 님, 박사, 박사님, 선생님,
교수님, さん, さま, くん, ちゃん, 様, 先生, 教授, 女士 and 小姐
qualify; 양, 군, 氏, 博士 and 殿 do not, because 김지양 is a given
name, 田中博士 is Tanaka Hiroshi as readily as Doctor Tanaka, and some
ninety Japanese surnames end in 殿 (鵜殿, 真殿). Those stay recognized
in their spaced form, where position settles what the glued form
leaves ambiguous. 君 is recognized in neither form, since 王君 is a
complete Chinese name — though its kana spelling くん peels. Exactly
one honorific peels off a token, and the entries are whole
honorifics rather than parts: ``김민준박사님`` gives up 박사님 entire,
not 님 with 박사 left behind.

A division the parser had to choose is reported rather than hidden.
When an unspaced name has more than one vocabulary-supported split —
``남궁민수`` is 남궁 + 민수 by the two-syllable surname but 남 + 궁민수
by the single-syllable one — the longest surname wins and the parse
records the decision as an ``AmbiguityKind.SEGMENTATION``, described
under `When the parser had to guess`_; a name with only one possible
split reports nothing. A segmenter's answer is reported on the same
kind whenever its confidence falls below the stage's floor, naming the
division and the score in the report's ``detail``::

    "'山田太郎' splits as '山田' + '太郎' on a segmenter answer scoring 0.44, under the 0.9 confidence floor"

With namedivider that line separates its two kinds of answer. A
division it states as a rule — the kanji-to-kana boundary in 高橋みなみ
— scores 1.0 and reports nothing; a division read off kanji statistics
scores far below the floor and always reports. Read the report as a
statement about the *kind* of answer, not as a measure of how likely
this particular one is to be wrong.

A lone two-character kanji name divides one character to each side, on
namedivider's rule for that length. A name that short carries no
evidence of where its own boundary falls, and one character each way is
the presumption Japanese practice makes; that is an accepted
presumption, not a measurement, so a two-character token is the shape
to check first if a division looks wrong.

A segmenter that answers outside the token it was given — a cut at or
past the end of the text — has violated the protocol, and the parse
says so rather than hiding it: it raises ``ValueError`` naming the
offending offset and the token's length, the way an answer of the
wrong type raises ``TypeError``. Declining silently would leave an
off-by-one segmenter invisible; every answer it gave would vanish and
the name would merely look undivided. The shipped ``ja_segmenter()``
does decline — returns ``None``, token left whole — for the cases that
are *not* protocol violations: text outside the Japanese repertoire,
text too short to divide, an answer that fails to reconstruct its
input, and a score outside [0, 1]. Exceptions are the one thing that
does *not* stay inside the parse: a segmenter is your code, so its
errors propagate rather than being absorbed as content errors.

The command line takes the pack but not the segmenter: ``python -m
nameparser --locale ja`` has no way to attach one, so it activates
nothing by itself. :doc:`customize` covers turning any of these
behaviors off.

Aggregate views
----------------

.. doctest::

    >>> name.given_names          # given + middle
    'Juan Q. Xavier'
    >>> name.family_base, name.family_particles   # family, split apart
    ('Vega', 'de la')

``surnames`` (``middle`` + ``family``) is the mirror-image aggregate.
The plural is the tell: ``given`` and ``family`` are single fields,
while ``given_names`` and ``surnames`` roll several fields together —
the same sense in which a passport form asks for your "given names" as
one blank that can hold more than one word.

``family_base`` is the one to sort on. Dutch and Belgian directories
file a name under the base surname and ignore the *tussenvoegsel* — the
``van``, ``de`` or ``van der`` in front of it — and the same convention
applies wherever particles are common:

.. doctest::

    >>> names = [parse(s) for s in
    ...          ["Vincent van Gogh", "Juan de la Vega", "John Smith"]]
    >>> [n.family_base for n in sorted(names, key=lambda n: n.family_base.lower())]
    ['Gogh', 'Smith', 'Vega']

Sorting on ``family`` instead files those under "d", "S" and "v", which
is the problem the split exists to solve:

.. doctest::

    >>> [n.family for n in sorted(names, key=lambda n: n.family.lower())]
    ['de la Vega', 'Smith', 'van Gogh']

Dicts and strings
------------------

.. doctest::

    >>> name.as_dict(include_empty=False)
    {'title': 'Dr.', 'given': 'Juan', 'middle': 'Q. Xavier', 'family': 'de la Vega', 'suffix': 'III'}
    >>> str(name)
    'Dr. Juan Q. Xavier de la Vega III'
    >>> name.render("{family}, {given}")
    'de la Vega, Juan'
    >>> name.initials()
    'J. Q. X. V.'

Fixing case
-----------

.. doctest::

    >>> str(parse("juan de la vega").capitalized())
    'Juan de la Vega'

The no-argument form above uses the DEFAULT lexicon; for a name parsed
with a custom :class:`~nameparser.Parser`, call
:meth:`Parser.capitalized() <nameparser.Parser.capitalized>` so the
parser's own vocabulary decides the exceptions.

Nicknames and maiden names
----------------------------

.. doctest::

    >>> parse("Jonathan 'Jack' Kennedy").nickname
    'Jack'
    >>> parse("Jane Smith née Jones").maiden
    'Jones'

Both fields appear in the default ``str()`` rendering — the nickname
quoted after the given name, the maiden name parenthesized after the
family name:

.. doctest::

    >>> str(parse("Jane (Janie) Smith née Jones"))
    'Jane "Janie" Smith (Jones)'

.. _maiden-roundtrip:

That default is built for display, and the two fields differ in what
survives it. The quoted nickname reparses as a nickname; the
parenthesized maiden name reparses as a *nickname* too, so a
parse-render-reparse round trip silently loses it:

.. doctest::

    >>> parse('Jane "Janie" Smith (Jones)').maiden
    ''
    >>> parse('Jane "Janie" Smith (Jones)').nickname
    'Janie Jones'

If the rendered string has to survive a reparse — storing names as text
and reading them back, for instance — render the marker explicitly
instead of relying on the default:

.. doctest::

    >>> name = parse("Jane Smith née Jones")
    >>> text = name.render("{given} {family} née {maiden}")
    >>> text
    'Jane Smith née Jones'
    >>> parse(text).maiden
    'Jones'

Delimited content is not always a nickname. If what's inside is a known
suffix, or simply ends in a period, it is read as a suffix instead —
parenthesized credentials and retired ranks are far more common than
parenthesized nicknames that happen to be credentials:

.. doctest::

    >>> parse("Andrew Perkins (MBA)").suffix
    'MBA'
    >>> parse("Andrew Perkins (Ret.)").suffix
    'Ret.'

The exception to that exception is an *ambiguous* acronym — one that is
also a plausible name or set of initials. Standing alone inside
delimiters, it keeps the nickname reading:

.. doctest::

    >>> parse("JEFFREY (JD) BRICKEN").nickname
    'JD'

``JD`` is in ``suffix_acronyms_ambiguous``; see :doc:`customize` for
what that field marks and how to add to it.

.. _abbreviated-titles:

Titles you didn't configure
-----------------------------

A leading word that ends in a period is read as a title even when it is
in no vocabulary list, which is what lets unfamiliar ranks, honorifics
and abbreviations work without configuring anything:

.. doctest::

    >>> parse("Major. Dona Smith").title
    'Major.'
    >>> parse("Foo. Xyz. John Smith").title      # chains
    'Foo. Xyz.'

The rule is bounded in three ways, so it doesn't swallow ordinary
names. Single initials are left alone, so are abbreviations with
interior periods, and the rule only applies to the leading run — the
same word after the given name is a middle name:

.. doctest::

    >>> parse("J. Smith").given
    'J.'
    >>> parse("E.T. Jones").given
    'E.T.'
    >>> parse("John Major. Smith").middle
    'Major.'

Because this is structural rather than vocabulary-driven, emptying
``titles`` does not switch it off; see :doc:`customize`.

Comparing names
----------------

``==`` is strict value equality — two :class:`~nameparser.ParsedName`
instances are equal only if every field matches exactly. For "is this
the same name, allowing for order and case?" use ``matches()`` or
``comparison_key()`` instead. ``matches()`` parses a str argument with
the DEFAULT parser; to compare against a string using a custom
:class:`~nameparser.Parser`'s vocabulary, call
:meth:`Parser.matches() <nameparser.Parser.matches>`.

.. doctest::

    >>> parse("de la Vega, Juan").matches("Juan de la Vega")
    True
    >>> parse("JUAN DE LA VEGA").comparison_key() == parse("Juan de la Vega").comparison_key()
    True

When the parser had to guess
-----------------------------

Some names have no single correct reading. A leading ``Van`` could be
a given name — it really is for the actor Van Johnson — or the start
of a family name, as it is for President Van Buren. Both are the same
shape, so no rule can tell them apart. 2.0 takes the more likely
reading and *records* the choice on ``ambiguities`` rather than
deciding silently:

.. doctest::

    >>> name = parse("Van Buren")
    >>> name.given, name.family
    ('Van', 'Buren')
    >>> for a in name.ambiguities:
    ...     print(a.kind.value, "-", a.detail)
    particle-or-given - leading 'Van' may be a family-name particle; read as a given name

:class:`~nameparser.AmbiguityKind` members are their own string values,
so branching on a kind needs no import:

.. doctest::

    >>> name.ambiguities[0].kind == "particle-or-given"
    True
    >>> [t.text for t in name.ambiguities[0].tokens]
    ['Van']

The post-nominals that double as ordinary surnames report the same way.
``MA`` after a full name is read as a credential, but after a single
given name it stays the surname — either way the choice is recorded:

.. doctest::

    >>> parse("John Smith MA").suffix
    'MA'
    >>> [a.kind.value for a in parse("John Smith MA").ambiguities]
    ['suffix-or-name']
    >>> parse("Jack MA").family
    'MA'

A reading the vocabulary settles on its own is not a guess and reports
nothing — periods make ``M.A.`` unambiguously a credential:

.. doctest::

    >>> parse("John Smith M.A.").ambiguities
    ()

Most names report none. A non-empty ``ambiguities`` is a useful signal
for routing a record to human review instead of trusting it silently.

Tokens and spans
------------------

The seven fields are the convenient view. Underneath, each one is
backed by tokens carrying their exact offsets into the original string,
so you can always get back to the text a field came from:

.. doctest::

    >>> name = parse("Juan de la Vega")
    >>> for tok in name.tokens:
    ...     print(f"{tok.text!r:8} {tok.role.value:8} {tuple(tok.span)}")
    'Juan'   given    (0, 4)
    'de'     family   (5, 7)
    'la'     family   (8, 10)
    'Vega'   family   (11, 15)
    >>> tok = name.tokens[1]
    >>> name.original[tok.span.start:tok.span.end]
    'de'

``tokens_for()`` narrows that to a single role:

.. doctest::

    >>> from nameparser import Role
    >>> [t.text for t in name.tokens_for(Role.FAMILY)]
    ['de', 'la', 'Vega']

A role's string name works too: ``name.tokens_for("family")``.

Correcting a parse
--------------------

:class:`~nameparser.ParsedName` is immutable, so a correction is a new
value: ``replace()`` returns a copy with the given fields changed.
Untouched fields keep their tokens (and ``original`` is preserved),
with one deliberate exception: an ambiguity that pointed into a
replaced field is dropped — correcting the field that was flagged
clears the flag, while correcting an unrelated field keeps it.

.. doctest::

    >>> name = parse("Juan de la Vega")
    >>> corrected = name.replace(title="Dr.")
    >>> str(corrected)
    'Dr. Juan de la Vega'
    >>> name.title
    ''
    >>> flagged = parse("Van Buren")
    >>> flagged.replace(given="Martin").ambiguities
    ()
    >>> [a.kind.value for a in flagged.replace(family="Harrison").ambiguities]
    ['particle-or-given']

``replace()`` splits values on whitespace into plain, untagged
tokens — the vocabulary knowledge a parse would have about the new
text is not there. The views that depend on tags degrade: the parser
no longer knows ``de la`` are particles, so ``family_particles``
empties and the particles start contributing initials.

.. doctest::

    >>> name.family_particles
    'de la'
    >>> replaced = name.replace(family="de la Vega Smith")
    >>> replaced.family_particles
    ''
    >>> replaced.initials()
    'J. d. l. V. S.'

:meth:`Parser.revise() <nameparser.Parser.revise>` is the same
operation with each value classified by the parser's vocabulary, so
the correction behaves like a fresh parse of the corrected name
(which also means delimiters and marker words in the value are
consumed as they would be in a parse):

.. doctest::

    >>> from nameparser import Parser
    >>> parser = Parser()
    >>> revised = parser.revise(name, family="de la Vega Smith")
    >>> revised.family_particles
    'de la'
    >>> revised.initials()
    'J. V. S.'

``revise()`` has two siblings on :class:`~nameparser.Parser`:
:meth:`Parser.matches() <nameparser.Parser.matches>` and
:meth:`Parser.capitalized() <nameparser.Parser.capitalized>`. Those
two matter when you have built a custom parser — the
:class:`~nameparser.ParsedName` methods of the same names fall back
to the *default* configuration for str or omitted arguments.

Command line
------------

``python -m nameparser`` parses one name and prints what it found. It
is the quickest way to see how a particular string comes out — worth
reaching for when a name parsed unexpectedly and you want to check a
variation of it, or when trying a locale pack before wiring one into
code:

::

    $ python -m nameparser "dr. juan de la vega iii"
    Parsed:
    <ParsedName: [
        title: 'dr.'
        given: 'juan'
        family: 'de la vega'
        suffix: 'iii'
    ]>
    Capitalized:
    <ParsedName: [
        title: 'Dr.'
        given: 'Juan'
        family: 'de la Vega'
        suffix: 'III'
    ]>
    Initials: j. v.

``--json`` prints the fields as a single line instead, which is the
form to pipe somewhere:

::

    $ python -m nameparser --json "Doe, John"
    {"title": "", "given": "John", "middle": "", "family": "Doe", "suffix": "", "nickname": "", "maiden": ""}

Add ``--locale`` to parse with a locale pack (for example ``--locale
ru``); see :doc:`locales`.

Where next
----------

* :doc:`concepts` — how the parser works
* :doc:`customize` — your own vocabulary and behavior
* :doc:`locales` — locale packs
* :doc:`migrate` — coming from 1.x ``HumanName``

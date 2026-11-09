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

Three arrangements are understood by default, two more when you
declare a family-first order, and two more by how they are written.

Understood by default
~~~~~~~~~~~~~~~~~~~~~

Every piece of each is optional:

1. ``Title Given "Nickname" Middle Middle Family Suffix``
2. ``[Title] Family [Suffix], Title Given (Nickname) Middle Middle[,] Suffix [, Suffix or Title]``
3. ``Title Given Middle Family [Suffix], Suffix or Title [, Suffix or Title]``

A title written with a period (``Prof.``) is also read at the end of a
name in forms 1 and 3 and at the end of the given name in form 2;
written bare there (``Prof``), it is a name word, because many title
words are also surnames — unless a credential stands before it, which
starts a run of post-nominals and titles (``John Smith PhD Prof`` reads
title ``Prof``; see :ref:`trailing-titles`), or, at the end of the
given name in form 2, it is a listed salutation such as ``Mrs``
(``Doe, Jane Mrs`` reads title ``Mrs`` since 2.6;
``Lexicon.default().words(kind="salutation", after_given=True)`` lists
them).

The last two differ in what the comma is doing. In form 2 it separates
the family name from the rest, so the family name comes first; in form
3 it only sets off suffixes and titles, and the name before it is still
given-then-family:

.. doctest::

    >>> parse("de la Vega, Juan Q. Xavier III").family   # form 2
    'de la Vega'
    >>> parse("Doe Jr., John").suffix                    # form 2, suffix before the comma
    'Jr.'
    >>> parse("John Doe, Jr.").family                    # form 3
    'Doe'

A suffix ending a name of two or more words (a title counts) before the comma reads as
form 3 even when what follows is a credential the vocabulary does not
know, since a generation is written there in natural order. A word
after the comma written as a name, or an initial, keeps form 2 (since
2.5):

.. doctest::

    >>> parse("John Smith II, AD").suffix
    'II, AD'
    >>> parse("Garcia Lopez Jr., Juan").given
    'Juan'

A part after the comma in form 3, or after a further comma in either
form, holds suffixes and titles, a word there that is a title rather
than a suffix being read as the title (after a further comma, since
2.4):

.. doctest::

    >>> parse("Eric H. Holder, Attorney General").title
    'Attorney General'
    >>> parse("Eric H. Holder, Jr., Attorney General").title
    'Attorney General'

Family-first forms you declare
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two more arrangements apply only when ``name_order`` declares
family-first input — common outside Europe; see :ref:`name-order`:

4. ``Title Family Given Middle Middle [Particle] [, Suffix]``  (``FAMILY_FIRST``)
5. ``Title Family Middle Middle Given [, Suffix]``  (``FAMILY_FIRST_GIVEN_LAST``)

A trailing particle earns a slot in form 4 alone because it is
displaced from the family name it belongs to; form 5's trailing word
is the given name by the caller's declaration, so there is nothing
there to reinterpret.

A title is read at the front of forms 4 and 5, which is where
family-first names written with a title put it. At the end of the name
it is read as in form 1: with a period it is the title, and bare it is a
name word unless a credential stands before it. Written between the
family and the given name, it is a name word, read by its position:

.. doctest::

    >>> from nameparser import FAMILY_FIRST, Parser, Policy
    >>> ff = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> ff.parse("Dr. Wang Xiaoming").title, ff.parse("Wang Xiaoming Dr.").title
    ('Dr.', 'Dr.')
    >>> ff.parse("Wang Dr. Xiaoming").given
    'Dr.'

Forms the script carries
~~~~~~~~~~~~~~~~~~~~~~~~

Two more arrangements are native East Asian forms. The first needs
no ``name_order`` at all — the script itself carries the reading —
and the second is read the way the default order reads it, its own
written order:

6. ``Family Given [Honorific]``
7. ``Given[·Given]·Family / katakana transcription (source order)``

Form 6 is the native family-first arrangement written in Han or
Hangul — spaced or unspaced, with the honorific spaced or glued and
landing in ``suffix``. It has no title slot and no comma, because
native CJK writing has neither convention. Form 7 is a transcription
listing — Han divided by the 间隔号, or katakana joined by the
nakaguro — never segmented, and kept in the order it was written as
long as ``name_order`` is the default: the script settles no order for
a transcription, so a declared ``FAMILY_FIRST`` reverses it as it
reverses a Latin name.

A comma or a Latin wrapper around a CJK name — a listing comma, a
Latin honorific or credential set beside it — is tolerated input:
parsed best-effort, its handling changeable without notice.

Forms 6 and 7, and how a Latin wrapper around either is handled, are
covered in full under `East Asian names`_ below.

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
reach forward to pull in the next word, whatever it is. Each row's
reading kind is what :meth:`Lexicon.words(kind=...)
<nameparser.Lexicon.words>` takes to list its words:

.. list-table::
   :header-rows: 1
   :widths: 22 26 12 40

   * - Words
     - Attach to
     - Field
     - Example
   * - Titles (``title``)
     - adjacent titles; a title that is also a given name, only inside
       a title phrase (:ref:`titles-also-given-names`)
     - ``title``
     - ``Asst. Vice Chancellor John`` → ``Asst. Vice Chancellor``
   * - Suffixes (``suffix``)
     - adjacent suffixes
     - ``suffix``
     - ``John Smith PhD MD`` → ``PhD MD``
   * - Bound given names (``bound_given``)
     - the following word
     - ``given``
     - ``abdul salam ahmed`` → ``abdul salam``
   * - Particles (``particle``)
     - the following surname, save a given name's second half
       (``del Carmen``), which is ``middle``
     - ``family``
     - ``Juan de la Vega`` → ``de la Vega``
   * - Ranks (``rank``)
     - the following surname, inside the name; opening it, most are
       titles (below)
     - ``family``
     - ``Jan Freiherr von Berg`` → ``Freiherr von Berg``
   * - Maiden markers (``birth_marker``)
     - the following name
     - ``maiden``
     - ``Jane Smith née Jones`` → ``Jones``
   * - Conjunctions (``conjunction``)
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

Most ranks (``Freiherr``, ``Graf``, ``Prinz``) are titles as well as
particles, and read by where they stand: opening the name each is a
title, and inside it the surname takes it in. ``Freiherrin`` holds no
title reading, so opening a name it is a name word. ``St`` reads the same
way, a title and a ``saint`` particle; the other ``saint`` words
(``San``, ``Sta``, ...) hold no title reading, so opening a name none
of them is a title:

.. doctest::

    >>> parse("Freiherr Hans von Berg").title
    'Freiherr'
    >>> parse("Jan Freiherr von Berg").family
    'Freiherr von Berg'
    >>> parse("St John Smith").title, parse("John St Clair").family
    ('St', 'St Clair')

Two shipped vocabularies work the other way round and so are not in
the table above: they *split* a word instead of merging two. The
Korean surnames (``Lexicon.default().surnames``) divide an unspaced
hangul name, and the glued honorifics, the ``honorific`` readings
carrying ``attached`` (``Lexicon.default().words(kind="honorific",
attached="after")`` lists them), split off the end of a Chinese,
Japanese or Korean name. Both are covered under `East Asian names`_.
:doc:`customize` covers how to add and remove the readings behind each
of these rows.

Inspecting the vocabulary
~~~~~~~~~~~~~~~~~~~~~~~~~

Two questions explain why a word read as it did, and each has its own
call. What a word *may* be read as is the lexicon's answer,
:meth:`Lexicon.readings_of <nameparser.Lexicon.readings_of>`, each
reading naming the language files that hold it. What the parse *did*
read it as is the token's, :attr:`Token.reading
<nameparser.Token.reading>` (see :ref:`reading-taken`):

.. doctest::

    >>> from nameparser import Lexicon
    >>> [(r.kind, r.languages) for r in Lexicon.default().readings_of("van")]
    [('preposition', ('nl',)), ('given', ('nl',))]
    >>> parse("Ludwig van Beethoven").tokens[1].reading
    Reading('particle' as 'family', 'vocabulary', in nl)

A lexicon answers for the readings it has on. A reading its file holds
off until a caller chooses the language (:ref:`choosing-languages`) is not among
the default lexicon's: ``Lady`` is a given name only under a Spanish
choice, and only that parser's lexicon lists the reading:

.. doctest::

    >>> from nameparser import locales, parser_for
    >>> [r.kind for r in Lexicon.default().readings_of("lady")]
    ['nobility']
    >>> [r.kind for r in parser_for(locales.ES).lexicon.readings_of("lady")]
    ['nobility', 'given']

A particle at the start of a name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Position matters in exactly one place: a particle standing on its own
at the start of a name. It has no surname to attach to yet, so what
decides the reading is whether it is one that can double as a given
name: the particle either becomes the given name or turns the whole
name into a surname. Only the first of those is ``name_order``'s
question — see :ref:`order-vocabulary-first`, and read the given name
below as the default given-first order's — since a particle that can
never be a given name is the surname whatever order you declare:

.. doctest::

    >>> parse("van Gogh").given          # 'van' can be a given name
    'van'
    >>> parse("de Mesnil").given         # 'de' cannot
    ''
    >>> parse("de Mesnil").family
    'de Mesnil'

A comma gets there first. It names the surname outright, so a particle
opening that surname has nothing left to decide and the part after the
comma is the given name:

.. doctest::

    >>> parse("de Mesnil, Juan").given
    'Juan'

:ref:`ambiguous-words` covers changing which particles may double as
given names.

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

Which name comes first
~~~~~~~~~~~~~~~~~~~~~~

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

Splitting an unspaced name
~~~~~~~~~~~~~~~~~~~~~~~~~~

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

A Chinese name can carry two surnames. In Taiwan a married woman
wrote her husband's surname before her own (冠夫姓) — the Civil Code's
default until 1998, and still a choice — and a mainland child may carry
both parents' surnames the same way. A Han given name is usually one
or two characters, so under ``zh`` a four-character name whose first
two characters are each a single surname on the list, and not a listed
compound such as 歐陽, reads them as the family, the two of them its
two units (``surname1`` and ``surname2``, below); written with a space
after the pair, before a two-character given name (王李 小明), it reads
the same way:

.. doctest::

    >>> wangli = parser_for(locales.ZH).parse("王李小明")
    >>> wangli.family, wangli.given, wangli.surname2
    ('王李', '小明', '李')

Transcribed foreign names
~~~~~~~~~~~~~~~~~~~~~~~~~

Chinese also has a transcription convention, and it is written in the
punctuation: a foreign name transcribed into Han characters keeps its
source order and divides its parts with the 间隔号, the interpunct
``·`` (U+00B7) — 威廉·莎士比亚 is William Shakespeare, given name
first. The dot itself is the marker, so nameparser reads U+00B7 as a
token separator when it sits between classified-script characters
(each side judged on its own — a hangul character beside a Han one
qualifies), and a dot anywhere in the name reads the whole name as a
transcription listing: it keeps the declared order — the order it
was written in, under the default — and is never segmented — the role pure katakana plays for Japanese
transcriptions, played here by the divider instead of the script:

.. doctest::

    >>> shakespeare = parse("威廉·莎士比亚")
    >>> shakespeare.given, shakespeare.family
    ('威廉', '莎士比亚')

Because only classified characters on both sides make it a divider,
the same codepoint interior to a Latin-script name — the Catalan punt
volat in ``Gal·la`` — is untouched, and a dot with a classified
character on just one side (``王·Smith``) stays part of the word
undivided:

.. doctest::

    >>> parse("Gal·la Puig").given
    'Gal·la'
    >>> parse("王·Smith").given
    '王·Smith'

The Japanese middle dot ・ (covered next) is a different mark carrying
a different convention, and keeps its own reading.

Japanese
~~~~~~~~~

Japanese writes a name in three scripts at once. Family names and most
given names are kanji — the same characters Chinese uses — but a given
name is often written in one of the two kana syllabaries instead:
hiragana (高橋みなみ) or katakana (山田エミ). The two syllabaries carry
different information about whose name it is. Hiragana never
transcribes a foreign name, so a name that holds hiragana, alone or
beside kanji or katakana, is a Japanese person's name, written in
Japanese order. Katakana is
ambiguous: native given names use it, but katakana is also how
Japanese text writes a *foreign* name — マイケル・ジャクソン is Michael
Jackson — and a transcription keeps the source language's order, given
name first, its parts divided by the middle dot ・ (the nakaguro,
U+30FB) rather than by a space. Katakana also has a halfwidth form
(ﾀﾛｳ for タロウ), which older systems that could not store kanji used
for every name, Japanese or foreign; bank, payroll and CSV exports
still carry it. nameparser reads halfwidth katakana exactly as it reads
the full-width form.

What happens automatically
^^^^^^^^^^^^^^^^^^^^^^^^^^

Two behaviors follow from that without any configuration. A name whose
characters stay within kanji and kana, carry at least one kana, and are
not katakana alone is assigned family-first, like any other
native-script East Asian name: it cannot be Chinese, and it is not a
transcription, because a transcription is written in katakana alone.

.. doctest::

    >>> minami = parse("高橋 みなみ")
    >>> minami.family, minami.given
    ('高橋', 'みなみ')
    >>> parse("山田 エミ").family
    '山田'
    >>> parse("山田 ﾀﾛｳ").family
    '山田'

And the middle dot separates tokens the way a space does, so a
transcribed foreign name divides into its parts — which, being wholly
katakana, keep the order they were written in:

.. doctest::

    >>> michael = parse("マイケル・ジャクソン")
    >>> michael.given, michael.family
    ('マイケル', 'ジャクソン')

Dividing an unspaced name: the segmenter
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Dividing an *unspaced* Japanese name is a separate matter, and one no
surname list can settle: family and given names draw on the same
kanji, both sides run one to four characters, and the reading rather
than the spelling decides most divisions. nameparser therefore takes a
**segmenter** — a callable from token text to a division — and ships a
factory wrapping `namedivider-python
<https://github.com/rskmoi/namedivider-python>`_, an optional
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
files from the network on first use, worth knowing before deploying it
somewhere sandboxed or air-gapped.

Forgetting the segmenter is loud: building the parser emits a
``UserWarning`` naming the scripts that could never divide and the
call to pass, because the misconfigured parser would otherwise behave
exactly like a working one minus the feature. The same check guards
any configuration whose activated scripts nothing can serve. A
from-scratch lexicon with no hangul surnames warns under the default
policy, and ``Policy(segment_scripts=frozenset())`` is the deactivation the
message offers.

Decomposed text
^^^^^^^^^^^^^^^

Korean and Japanese text is sometimes stored decomposed, with a
syllable held as its separate jamo rather than as one codepoint. macOS
filenames are the common source. Everything above works on decomposed
input: script classification normalizes to NFC before deciding, so a
decomposed name gets the same order rule as its composed twin.
Vocabulary lookup does the same before matching a word against
titles, honorifics and the rest, so a decomposed ``Señor`` or ``née``
— macOS-origin data again — is recognized as readily as its composed
spelling. Case repair reads a decomposed accent as part of its letter,
so ``capitalized()`` gives a decomposed ``josé garcía`` the same
``José García`` as the composed spelling, still decomposed.

Splitting is the exception. An unspaced decomposed hangul name is
ordered correctly but not split, because surname matching runs against
the text as given and a decomposed name matches no entry in the census
list. That is the deliberate choice: being unsplit is recoverable,
whereas splitting in the wrong place is not.

One consequence is worth stating outright, because it looks like a
bug. Parse output preserves the encoding it was given, so a field from
a decomposed name is decomposed too, and comparing it against a
composed literal fails even where the parse was correct::

    decomposed = unicodedata.normalize("NFD", "김 민준")
    parse(decomposed).family == "김"                          # False
    unicodedata.normalize("NFC", parse(decomposed).family)    # '김'

Normalize both sides before comparing across encodings.

Boundaries
~~~~~~~~~~~

Several boundaries apply to all of the above.

When the script rules don't apply
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Romanized names ("Kim Min-jun", "Yamada Taro") are Latin script and
follow the ordinary positional rules. Order genuinely varies in
romanized data, so nothing script-based applies. A name written wholly
in katakana stays positional for the reason given above, pack or no
pack: it may be a transcription, already in the order it should be
read in, or a Japanese name's reading written family-first — a
furigana field, or legacy halfwidth data — and the script cannot tell
the two apart. If you know your katakana names are Japanese, map
katakana to family-first yourself:

.. doctest::

    >>> from nameparser import (DEFAULT_SCRIPT_ORDERS, FAMILY_FIRST, Parser,
    ...                         Policy, Script)
    >>> parse("ﾔﾏﾀﾞ ﾀﾛｳ").family
    'ﾀﾛｳ'
    >>> kana_family_first = Parser(policy=Policy(script_orders=(
    ...     *DEFAULT_SCRIPT_ORDERS, (Script.KATAKANA, FAMILY_FIRST))))
    >>> kana_family_first.parse("ﾔﾏﾀﾞ ﾀﾛｳ").family
    'ﾔﾏﾀﾞ'

This reaches full-width katakana too, transcriptions included
(マイケル・ジャクソン would read family マイケル), which is why it is
yours to choose rather than a default. ``name_order=FAMILY_FIRST``
would also work, but it reverses every name, Latin ones included.

A Han transcription written with a space instead of the 间隔号
(威廉 莎士比亚) carries nothing to distinguish it from a native
two-token name, and keeps the family-first reading. The dot is the
marker, and without it there is no signal. The same holds for a
transcription typed with the Japanese middle dot (威廉・莎士比亚): each
dot carries its own script's convention, the nakaguro's is Japanese
roster formatting rather than transcription, so only the Chinese dot
stands the family-first reading down.

Honorifics come off first
^^^^^^^^^^^^^^^^^^^^^^^^^

Honorifics and degrees follow a CJK name, and both the spaced and the
glued forms are recognized as suffixes:

.. doctest::

    >>> parse("王小明 先生").suffix
    '先生'
    >>> glued = parse("김민준씨")
    >>> glued.family, glued.given, glued.suffix
    ('김', '민준', '씨')

The honorific is split off the end of the last token of the name
before the name is split or ordered, so those rules see the name
without it. That is why ``김민준씨`` still divides into family 김 and
given 민준, and why a configured Japanese segmenter is handed 山田太郎
rather than 山田太郎様.

The stop can be any width: the fullwidth ``．`` a Japanese or
Chinese input method produces by default, the ideographic ``。`` and
the halfwidth ``｡`` all reach the honorific vocabulary as an ASCII
period does, so ``김민준 씨．`` gives suffix ``씨．``, family 김, given
민준. A period glued to an ordinary name word, not an honorific, is
likewise left where it was written rather than breaking the
segmentation that follows it:

.. doctest::

    >>> parse("양. 지훈").family, parse("양. 지훈").given
    ('양.', '지훈')

Commas and Latin wrappers around a CJK name
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A comma or a Latin credential set wrapped around a CJK name is
tolerated input rather than contract: no native CJK writing uses
either convention, so nameparser reads it best-effort and the
handling can change without notice. Today:

- **A comma names the family and stops the split.** ``남궁민수, 지훈``
  reads family ``남궁민수`` whole, where the bare ``남궁민수`` alone
  would split into family ``남궁`` and given ``민수``.
- **A glued honorific peels off before the comma** when what follows
  it is nothing but suffix words, as in ``田中さん, PhD`` (suffix
  ``さん, PhD``).
- **It stays glued** when the comma is followed by a title or another
  name word, as in ``田中さん, Dr.`` (family ``田中さん``).
- **Credentials after the comma** land in ``given`` or ``suffix`` by
  spelling, and ``田中さん, V.`` and ``田中さん, Ph. D.`` give up さん
  exactly as ``田中さん, PhD`` does. ``Policy(lenient_comma_suffixes=False)``
  reads ``V.`` as name text instead, and さん then stays glued (family
  ``田中さん``, given ``V.``).

Spacing, and where the name divides
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Where a segmenter divides the name, the two spellings part company. A
spaced honorific is a token boundary the writer typed, and the
segmenter is asked only where an undivided name divides, so anything
standing beside the name calls it off, honorific or not. Under the
Japanese pack ``佐藤 氏`` keeps family 佐藤, where bare ``佐藤`` would
have been divided 佐 + 藤.

That is a conservative reading rather than a principled one. A spaced
honorific cannot be told apart from a spaced given name by position,
and treating it as one keeps four real surnames whole (``佐藤 氏``,
``田中 様``, ``鈴木 先生``, ``中村 教授``) at the price of one division
it declines to make (``山田太郎 様``). A glued honorific carries no
boundary at all, its writer having drawn none anywhere, so ``田中さん``
divides the way bare ``田中`` does, into family 田 and given 中, with
さん in ``suffix``. Writing the honorific spaced is therefore also how
you ask for a family name to be kept whole on this path, short of
declining the pack.

Where the VOCABULARY divides the name the two spellings never part
company, because the peel hands the same remainder to the same surname
match either way:

.. doctest::

    >>> parse("김민준 씨").family, parse("김민준씨").family
    ('김', '김')

Under the Chinese pack ``王小明 先生`` and ``王小明先生`` both give
family 王, given 小明 and suffix 先生 for the same reason. Spacing the
honorific is no lever there, and for Korean data there is no pack to
decline either, hangul segmentation being on by default.

Which honorifics peel when glued
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The glued reading is deliberately narrower than the spaced one. A
spaced honorific sits behind a boundary its writer drew; a glued one
has only itself to go on, so a word peels off the end of a name only
if it could never BE the end of a name.

씨, 님, 박사, 박사님, 선생님, 교수님, さん, さま, くん, ちゃん, 様,
先生, 教授, 女士 and 小姐 qualify. 양, 군, 氏, 博士 and 殿 do not,
because 김지양 is a given name, 田中博士 is Tanaka Hiroshi as readily
as Doctor Tanaka, and some ninety Japanese surnames end in 殿 (鵜殿,
真殿). Those stay recognized in their spaced form, where position
settles what the glued form leaves ambiguous. 君 is recognized in
neither form, since 王君 is a complete Chinese name, though its kana
spelling くん peels.

Exactly one honorific peels off a token, and the entries are whole
honorifics rather than parts: ``김민준박사님`` gives up 박사님 entire,
not 님 with 박사 left behind.

Credential and office words (議員 legislator, 医学博士 doctor of
medicine, 社長 company president, 二世 the second) peel when glued as
well: they are not known to end a name. A longer office word that
ends in one of them is split at it, so 田中 副社長 (vice-president)
gives the given name 副 and the suffix 社長. 部長 (department head) is
the exception and is not peeled when glued, because 長 alone is a
given name, so 阿部長 can be the surname 阿部 and the given name 長:

.. doctest::

    >>> shacho = parse("田中社長")
    >>> shacho.family, shacho.suffix
    ('田中', '社長')
    >>> parse("田中部長").family
    '田中部長'

When a division was a judgment call
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A division the parser had to choose is reported rather than hidden.
When an unspaced name has more than one vocabulary-supported split,
the longest surname wins and the parse records the decision as an
``AmbiguityKind.SEGMENTATION``, described under `When the parser had
to guess`_. ``남궁민수`` is 남궁 + 민수 by the two-syllable surname but
남 + 궁민수 by the single-syllable one:

.. doctest::

    >>> parse("남궁민수").ambiguities
    (Ambiguity('segmentation': '남궁'/'민수'),)

A name with only one possible split reports nothing.

A segmenter's answer is reported on the same kind whenever its
confidence falls below the stage's floor, naming the division and the
score in the report's ``detail``::

    "'山田太郎' splits as '山田' + '太郎' on a segmenter answer scoring 0.44, under the 0.9 confidence floor"

With namedivider that line separates its two kinds of answer. A
division it states as a rule, such as the kanji-to-kana boundary in
高橋みなみ, scores 1.0 and reports nothing; a division read off kanji
statistics scores far below the floor and always reports. Read the
report as a statement about the *kind* of answer, not as a measure of
how likely this particular one is to be wrong.

A lone two-character kanji name divides one character to each side, on
namedivider's rule for that length. A name that short carries no
evidence of where its own boundary falls, and one character each way
is the presumption Japanese practice makes. That is an accepted
presumption rather than a measurement, so a two-character token is the
shape to check first if a division looks wrong.

When a segmenter misbehaves
^^^^^^^^^^^^^^^^^^^^^^^^^^^

A segmenter that answers outside the token it was given, with a cut at
or past the end of the text, has violated the protocol, and the parse
says so rather than hiding it. It raises ``ValueError`` naming the
offending offset and the token's length, the way an answer of the
wrong type raises ``TypeError``. Declining silently would leave an
off-by-one segmenter invisible: every answer it gave would vanish and
the name would merely look undivided.

The shipped ``ja_segmenter()`` does decline, returning ``None`` and
leaving the token whole, for the cases that are *not* protocol
violations: text outside the Japanese repertoire, text too short to
divide, an answer that fails to reconstruct its input, and a score
outside [0, 1].

Exceptions are the one thing that does *not* stay inside the parse: a
segmenter is your code, so its errors propagate rather than being
absorbed as content errors.

The command line attaches the segmenter for you: ``python -m
nameparser --locale ja`` uses :func:`~nameparser.locales.ja_segmenter`
when ``nameparser[ja]`` is installed, and without it divides nothing
and prints a note naming the install. :func:`~nameparser.parser_for` never
does this on its own, so the same code parses alike wherever it runs.
:doc:`customize` covers turning any of these behaviors off.

.. _aggregate-views:

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

``generation`` and ``credentials`` split the suffix the way a name
form's "Jr., III" and "PhD, MD" boxes do: a generation numbers the
bearer among relatives of the same name, and every other word after
the name, a courtesy such as ``Esq.`` included, is a credential, save
a form of address written after the name (``さん``, ``씨``, ``先生``),
which is in ``honorifics``. Each joins its words as ``suffix`` does,
and ``suffix`` itself is unchanged:

.. doctest::

    >>> suffixed = parse("Smith, John, Jr., MD, Esq.")
    >>> suffixed.generation, suffixed.credentials, suffixed.suffix
    ('Jr.', 'MD, Esq.', 'Jr., MD, Esq.')
    >>> suffixed.render("{given} {family} {generation}")
    'John Smith Jr.'
    >>> addressed = parse("田中さん, PhD")
    >>> addressed.credentials, addressed.honorifics, addressed.suffix
    ('PhD', 'さん', 'さん, PhD')

``patronymic`` names the words that say whose child the bearer is, a
particle such as ``bin`` with the parent's name after it, in whatever
field the parse put them, which keeps them. It reads no position, so a
name written without the particle has none:

.. doctest::

    >>> nasab = parse("Mahathir bin Mohamad")
    >>> nasab.patronymic, nasab.family
    ('bin Mohamad', 'bin Mohamad')
    >>> parse("Anwar Ibrahim").patronymic
    ''

``surname2`` is the family's second name, where the parse read the
family as two: with ``two_family_names`` on
(:ref:`two-family-names`), as the ``es``, ``es_ar``, ``cs`` and ``sk``
packs turn it on (:doc:`locales`), or for a Chinese name opening with
two surnames under ``zh`` (:ref:`east-asian-names`), and ``family``
keeps both. Every other name has none, a family comma's and a
hyphenated one included:

.. doctest::

    >>> from nameparser import Parser, Policy
    >>> marquez = Parser(policy=Policy(two_family_names=True)).parse(
    ...     "Gabriel García Márquez")
    >>> marquez.family, marquez.surname2
    ('García Márquez', 'Márquez')
    >>> parse("Gabriel García Márquez").surname2
    ''

``surname1`` is the other one, the first of the two family names, with
``surname1_particles`` and ``surname1_base`` splitting it as
``family_particles`` and ``family_base`` split the whole family. Where
the family is read as one, they are the family's own views, but for any
middle names ``middle_as_family`` folds into it:

.. doctest::

    >>> vega = Parser(policy=Policy(two_family_names=True)).parse(
    ...     "Juan de la Vega del Valle")
    >>> vega.surname1, vega.surname1_particles, vega.surname1_base
    ('de la Vega', 'de la', 'Vega')
    >>> vega.family_base, vega.surname2
    ('Vega Valle', 'del Valle')
    >>> parse("Juan de la Vega").surname1_base
    'Vega'

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

``str()``, like ``render()`` with no spec, lays the name out in the
order it was read in (:attr:`ParsedName.order
<nameparser.ParsedName.order>`) and keeps the separator written between
two words that stay side by side, normalized: nothing stays nothing,
any run of whitespace becomes one space, and a comma before a suffix
stays. A spec you pass renders exactly as written, in its own order:

.. doctest::

    >>> str(parse("김민준")), str(parse("John Smith, Jr."))
    ('김민준', 'John Smith, Jr.')
    >>> parse("김민준").render("{given} {family}")
    '민준 김'

Fixing case
-----------

.. doctest::

    >>> str(parse("juan de la vega").capitalized())
    'Juan de la Vega'

The no-argument form above uses the DEFAULT lexicon; for a name parsed
with a custom :class:`~nameparser.Parser`, call
:meth:`Parser.capitalized() <nameparser.Parser.capitalized>` so the
parser's own vocabulary decides the exceptions.

.. _nicknames-and-maiden-names:

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

Surviving a reparse
~~~~~~~~~~~~~~~~~~~

The default ``str()`` rendering is built for display, and the two
fields differ in what
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

What bracketed content reads as
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Delimited content is not always a nickname. If it opens with a marker
word and has a word after it, the clause is a maiden name inside any
configured delimiter pair, with nothing else configured — the clause
has said which convention it means, so you do not have to:

.. doctest::

    >>> parse("Jane Smith (née Jones)").maiden
    'Jones'
    >>> parse('Jane Smith "née Jones"').maiden
    'Jones'
    >>> parse("Jane (née Jones) Smith").family
    'Smith'

A marker with no name after it is just a word in brackets, and a clause
with no marker at all stays a nickname — the parenthesized birth surname
is a real convention, but nothing in the clause says so, and only you
can declare that with ``maiden_delimiters`` (see :ref:`brackets`):

.. doctest::

    >>> parse("Jane Smith (née)").nickname
    'née'
    >>> parse("Cherice J. (Johnson) Williams").nickname
    'Johnson'

If every word inside is a known
credential, generation or title, the clause is set apart from the name
instead, each word read as the suffix or the title it is — that reading
is taken before the maiden one, and parenthesized credentials, titles
and retired ranks are far more common than parenthesized nicknames that
happen to be credentials. Initials inside a name stay the nickname
(``Justin (JP) Stearns``), and other content ending in a period is read
as if written without its brackets:

.. doctest::

    >>> parse("Andrew Perkins (PhD)").suffix
    'PhD'
    >>> parse("Andrew Perkins (Ret.)").suffix
    'Ret.'
    >>> parse("John Smith (Dr)").title
    'Dr'

The exception to that exception is an *ambiguous* acronym — one that is
also a plausible name or set of initials. Standing alone inside
delimiters, it keeps the nickname reading unless the way it is written
settles it after the name: in capitals in a name written in mixed case,
or with a period inside it. A name written all in capitals says
nothing about the word, and inside the name the delimiters are read as
a nickname however it is written:

.. doctest::

    >>> parse("Andrew Perkins (JD)").suffix
    'JD'
    >>> parse("Andrew Perkins (Jd)").nickname
    'Jd'
    >>> parse("JEFFREY (JD) BRICKEN").nickname
    'JD'

``JD`` holds a ``given`` reading beside its credential one
(``Lexicon.default().readings_of("jd")``); see :ref:`ambiguous-words`
for what that second reading marks and how to add one.
:ref:`brackets` covers the full order these readings are tried in, and
how to configure the delimiter pairs.

.. _abbreviated-titles:

Titles you didn't configure
-----------------------------

A trailing period marks an abbreviation, and the parts of a name that
get abbreviated are mostly the ones standing outside it — titles and
post-nominals; the exception, a given name written short, is below. So a word ending in a period, in no vocabulary list at
all, is read as a title when it stands where a title stands: at the
front of the part that carries the given name. That is what lets
unfamiliar ranks, honorifics and abbreviations work without configuring
anything:

.. doctest::

    >>> parse("Insp. Jane Morse").title
    'Insp.'
    >>> parse("Det. Insp. Jane Morse").title     # chains
    'Det. Insp.'

Neither ``det`` nor ``insp`` is in the shipped vocabulary; the periods
are doing all the work.

The part that carries the given name is not always the front of the
string. After a family comma it is the part *after* the comma, and the
rule applies there in exactly the same way:

.. doctest::

    >>> parse("Morse, Det. Insp. Jane").title
    'Det. Insp.'

Where the inference stops
~~~~~~~~~~~~~~~~~~~~~~~~~

The rule is bounded so it doesn't swallow ordinary names:

- **Single initials** are left alone (``J.``).
- **Abbreviations with interior periods** are left alone (``E.T.``).
- **Only the leading run** is read this way: the same word after the
  given name is a middle name.
- **A word carrying a Han, kana or hangul character** is a name word
  even with a period,
  since those scripts write no abbreviation with one (``"田中. 太郎"``
  has family ``田中.``).
- **Before a family comma** the inference does not run, since that
  slot holds a surname too: ``Xyz. Smith, John`` keeps family
  ``Xyz. Smith``. A listed title is still read there, so
  ``Dr. Smith, John`` gives title ``Dr.``.
- **A given name written short** is that given name (since 2.7): the
  traditional English abbreviations such as ``Chas.``, ``Geo.`` and
  ``Wm.``, and the Filipino ``Ma.`` (María) and ``Jo.`` (José).
  Each is a ``given`` reading carrying ``same_as``, the full name
  (``Lexicon.default().readings_of("chas")``); written bare, or
  anywhere else in the name, each word reads as it would unlisted.

.. doctest::

    >>> parse("Chas. Smith").given
    'Chas.'
    >>> parse("Mrs Ma. Liza Cruz").given
    'Ma.'
    >>> parse("J. Smith").given
    'J.'
    >>> parse("E.T. Jones").given
    'E.T.'
    >>> parse("Jane Insp. Morse").middle
    'Insp.'
    >>> parse("Xyz. Smith, John").family
    'Xyz. Smith'

Because this is structural rather than vocabulary-driven, taking out
every title reading does not switch it off; see :ref:`title-detection-off`.

.. _trailing-titles:

At the end of a name
~~~~~~~~~~~~~~~~~~~~

Only the leading slot INFERS. At the back of a name a word ending in a
single period is read by vocabulary alone: a word the parser already
knows as a post-nominal or as a title reads as one, and an unfamiliar
abbreviation stays a name word. A word of two or more period-separated
chunks is the exception, read as a credential by its shape (see
:ref:`dotted-credentials`).

.. doctest::

    >>> parse("John Smith Prof.").title
    'Prof.'
    >>> parse("John Smith Xyz.").family
    'Xyz.'
    >>> parse("Jane Smith N.C.C.").suffix
    'N.C.C.'

That asymmetry is deliberate. The title vocabulary holds hundreds of
words that are ordinary surnames — ``pope``, ``judge``, ``bishop`` —
so inferring a trailing title from the shape alone would cost real
names their family field. The period is what separates the two: a
trailing title word written *without* one is a name word, so
``parse("Mary Jane Pope").family`` is ``'Pope'``.

A credential in front changes that. It starts a run of post-nominals
and titles that lasts to the end of the name, so a bare title word
behind it is a title:

.. doctest::

    >>> john_prof = parse("John Smith PhD Prof")
    >>> (john_prof.title, john_prof.suffix)
    ('Prof', 'PhD')

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

.. _matching-names:

Matching names across sources
-----------------------------

``matches()`` asks whether two writings are the same name. Joining
records from several sources asks something looser: could these two
names belong to the same person? One source writes ``John A. Smith``,
another ``J. Smith``, a third ``JOHN SMITH JR.``. A name matcher
answers that question role by role, using the parse to know which
words are the family name, which are particles and which are initials,
and says *why* for every pair. It never scores a pair: combine its
answer with your own evidence (coauthors, institutions, identifiers)
and set your own thresholds.

The workflow is four steps:

#. Parse each source with its own :class:`~nameparser.Policy`, so two
   sources that write names in different orders each read correctly.
#. Build one :class:`~nameparser.Matching` from a parser with
   :meth:`Parser.matching() <nameparser.Parser.matching>`, and use it
   for both of the steps below.
#. Group the names by ``keys()``.
#. Within each group, ``check()`` each pair.

Grouping by key
~~~~~~~~~~~~~~~

``keys()`` gives each name a set of short strings, the family name's
words without their particles beside the given name's first letter.
Two names ``check()`` calls consistent always share a key, so grouping
by key loses no match, and a pair that shares no key need never be
checked:

.. doctest::

    >>> from collections import defaultdict
    >>> from nameparser import Parser
    >>> matcher = Parser().matching()
    >>> sorted(matcher.keys("Jane A. de la Vega"))
    ['vega;j']
    >>> groups = defaultdict(list)
    >>> for written in ["John A. Smith", "J. Smith", "Juan de la Vega", "Juan Vega"]:
    ...     for key in matcher.keys(written):
    ...         groups[key].append(written)
    >>> dict(groups)
    {'smith;j': ['John A. Smith', 'J. Smith'], 'vega;j': ['Juan de la Vega', 'Juan Vega']}

A family name of several words gets a key for each, because a source
may cut a surname list short, and a hyphenated one a key for each half,
for the two joined and for the whole word, save a half that is a
particle (``Al-Saud`` keys ``saud``, ``alsaud`` and ``al-saud``, never
``al``):

.. doctest::

    >>> sorted(matcher.keys("Mary Smith-Jones"))
    ['jones;m', 'smith-jones;m', 'smith;m', 'smithjones;m']

A key only gathers candidates: ``Jane Smith`` shares ``smith;j`` with
``John Smith``, and ``check()`` is what tells them apart. A name with
no family name, such as a lone ``Suharto`` (read as a given name, see
:ref:`lone-name-word`), gets no key and is consistent with nothing by
default, since the family name must be present on both sides and
agree; the search for other readings (below) reaches it through its
family reading.

Checking a pair
~~~~~~~~~~~~~~~

``check()`` takes two strings, parsed with the matcher's parser, or
two :class:`~nameparser.ParsedName` objects, compared as they were
parsed. It returns a :class:`~nameparser.MatchResult`: ``consistent``,
and in ``roles`` one :class:`~nameparser.RoleMatch` per field in field
order, each with its :class:`~nameparser.Outcome`, the text on each
side, and which :class:`~nameparser.Side` carried more of it. A row is
read by its field's name or :class:`~nameparser.Role`
(``result["family"]``), and ``weakest`` is the weakest row's outcome:

.. doctest::

    >>> smiths = matcher.check("John A. Smith", "J. Smith")
    >>> smiths.consistent
    True
    >>> for row in smiths.roles:
    ...     print(row.role.value, row.outcome.value, repr(row.left), repr(row.right), row.more.value)
    title same '' '' neither
    given initial 'John' 'J.' left
    middle one-side 'A.' '' left
    family same 'Smith' 'Smith' neither
    suffix same '' '' neither
    nickname same '' '' neither
    maiden same '' '' neither
    >>> smiths["given"].outcome.value, smiths.weakest.value
    ('initial', 'one-side')

**Consistent means nothing in the two names contradicts the match**,
under the outcomes accepted. It does not mean the two are the same
person: ``J. Smith`` is consistent with half the Smiths in a phone
book. The table is what lets you tell ``John A. Smith`` / ``John
Smith`` (only a middle initial missing) from ``J. Smith`` / ``John A.
Smith`` (most of the given name missing too), though both are
consistent. A pair is inconsistent when a role's outcome is
``conflict``, or one you have not accepted:

.. doctest::

    >>> johns = matcher.check("John Smith Jr.", "John Smith Sr.")
    >>> johns.consistent, johns["suffix"].outcome.value
    (False, 'conflict')

The check is symmetric: swapping the two names gives the same verdict
and the same table with ``left`` and ``right`` exchanged
(``MatchResult.mirrored()``). Each source keeps its own order, so
names parsed under different policies compare correctly:

.. doctest::

    >>> from nameparser import FAMILY_FIRST, Policy
    >>> family_first_source = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> matcher.check(family_first_source.parse("Smith John"), "John A. Smith").consistent
    True

What the default accepts
~~~~~~~~~~~~~~~~~~~~~~~~

The outcomes, in the order ``check()`` ranks them, strongest first.
``Outcome.strength`` gives that rank as a number, larger for a stronger
outcome; rank outcomes by it, since ``<`` on an
:class:`~nameparser.Outcome` compares the names as strings (``folded``
sorts before ``same``). The default accepts the writing
variants a hand-built comparison usually forgives; the rest count as a
conflict until you accept them. ``familiar-form``, ``family-initial``,
``given-one-side`` and ``hyphenated-part`` are reported in the table
either way, so an unaccepted one shows what the pair needed. ``across-roles`` is
searched only where accepted, and each side's other readings only where
the search is switched on (below): otherwise the table shows the names
as parsed, and ``Suharto`` / ``Suharto`` reads family ``conflict``.

.. list-table::
   :header-rows: 1
   :widths: 22 38 12

   * - Outcome
     - Example (left / right)
     - Default
   * - ``same``
     - ``Smith`` / ``Smith``
     - yes
   * - ``folded``: equal once case, accents, full stops and apostrophes (typed or typographic) are folded away
     - ``María García`` / ``MARIA GARCIA``
     - yes
   * - ``listed-spelling``: spellings the vocabulary lists as one, in the role's own kind of word, a short form that is a name of its own too only written with its period
     - ``Wm. Smith`` / ``William Smith``
     - yes
   * - ``particles-aside``: the family names agree without their particles
     - ``Juan de la Vega`` / ``Juan Vega``
     - yes
   * - ``part-of-other``: one family name's words are among the other's
     - ``Ana de Melo Schmitt`` / ``Ana de Melo Schmitt e Braga``
     - yes
   * - ``initial``: an initial against a name, outside the family name
     - ``J. Smith`` / ``John Smith``
     - yes
   * - ``initials-agree``: one role written in initials alone on both sides, the same initials once spaces and hyphens are set aside
     - ``Jane Doe (née J.-P.)`` / ``Jane Doe (née J. P.)``
     - yes
   * - ``one-side``: a middle name, nickname or maiden name on one side only
     - ``John A. Smith`` / ``John Smith``
     - yes
   * - ``generation-one-side``: a generation on one side only
     - ``John Smith`` / ``John Smith Jr.``
     - yes
   * - ``noted``: titles and credentials, which never conflict
     - ``Dr. John Smith`` / ``John Smith, PhD``
     - yes
   * - ``familiar-form``: a short given name the vocabulary lists as standing for the other, one way
     - ``Bill Smith`` / ``William Smith``
     - no
   * - ``family-initial``: the family name written as an initial
     - ``John S.`` / ``John Stallbaum``
     - no
   * - ``given-one-side``: a given name on one side only
     - ``Mr. Smith`` / ``John Smith``
     - no
   * - ``hyphenated-part``: a given name against the first half of a hyphenated one
     - ``Hong Guo`` / ``Hong-Yi Guo``
     - no
   * - ``across-roles``: a name in a different role on each side
     - ``J. Edgar Hoover`` / ``Edgar Hoover``
     - no
   * - ``conflict``
     - ``John Smith`` / ``Jane Smith``
     - never

A listed spelling is read in the role's own kind of word: given names
for the given name, middle name and nickname, surnames and particles
for the family and maiden names, titles and suffixes for theirs. So
``Ma.`` (María written short) agrees with ``María`` as a given name,
while the surname Ma is another word, ``Ma, Jack`` / ``María, Jack``.
A short form that is also a name of its own, as ``Ma``, ``Jo`` (José)
and ``Jas`` (James) are, is read as its long form only written with
its period: ``Jo. Garcia`` / ``José Garcia`` agree, and ``Jo Garcia``
/ ``José Garcia`` conflict, the bare ``Jo`` being the name Jo, while
``Wm Smith`` and ``WM SMITH`` agree with ``William Smith``, ``Wm``
being no name of its own. It is read with accents folded too, so
``Jo. Garcia`` / ``Jose Garcia`` agree as ``Jo.`` / ``José`` do. A
middle name is compared word by word, in order, and takes the weakest
of its words' outcomes. A different generation conflicts
(``Jr.`` / ``Sr.``), and a generation on one side only reads
``generation-one-side`` whatever credentials either side carries
(``John Smith Jr.`` / ``John Smith, PhD``); a credential or title
never conflicts, so a career from ``Mr.`` to ``Dr.`` does not separate
a person's records. The fold drops accents only from Latin, Greek and
Cyrillic letters; a mark on another script's letter, such as a
Devanagari vowel sign, is spelling and stays. Initials written joined
read as one word, so ``J.P. Smith`` / ``J.-P. Smith`` is a conflict.
Typos (``Slvatore`` / ``Salvatore``) and transliterations are
conflicts, and so is a familiar form until you accept it (below): the
table names the conflicting role, so you can run your own fuzzy
comparison on that role alone.

Accepting more
~~~~~~~~~~~~~~

``accept`` takes outcome names or :class:`~nameparser.Outcome`
members, and *replaces* the default set rather than adding to it, so
extend the default with the ``accept`` of a default matcher. The keys
follow what is accepted and the ``other_readings`` switch, so one
matcher's ``keys()`` and ``check()`` always agree; never group with one
matcher and check with another:

.. doctest::

    >>> with_family_initial = Parser().matching(accept=matcher.accept | {"family-initial"})
    >>> with_family_initial
    Matching(default + family-initial)
    >>> matcher.check("John S.", "John Stallbaum").consistent
    False
    >>> with_family_initial.check("John S.", "John Stallbaum").consistent
    True
    >>> sorted(with_family_initial.keys("John Stallbaum"))
    ['s;j', 'stallbaum;j']

A family initial is outside the default because its key, one letter of
the family name, gathers very large groups. An unknown outcome name
raises ``ValueError`` listing the valid ones, and ``conflict`` cannot
be accepted.

``other_readings=True``, a switch beside ``accept`` rather than an
outcome, tries each side's other reading where the names as parsed are
not consistent: one :ref:`ambiguity <parser-guesses>` at a time, its
words moved to the role its ``alternative`` names. Each row keeps its
own outcome under the other reading, so whatever else the pair needed
still shows, and ``left_alternative`` and ``right_alternative`` hold
the ambiguity whose other reading each side used, ``None`` for a side
read as parsed. A lone ``Suharto``, read as a given name, has the
family reading as its alternative:

.. doctest::

    >>> with_other_reading = Parser().matching(other_readings=True)
    >>> with_other_reading
    Matching(default + other-readings)
    >>> lone = with_other_reading.check("Suharto", "Suharto")
    >>> lone.consistent, lone["family"].outcome.value
    (True, 'same')
    >>> lone.left_alternative.kind.value, lone.left_alternative.alternative.role.value
    ('given-or-family', 'family')
    >>> sorted(with_other_reading.keys("Suharto"))
    ['suharto;']

An alternative that would move words into the title or the suffix is
not tried, so a given name cannot vanish into one of them to agree
with another.

``familiar-form`` reads a short given name as standing for the longer
ones the vocabulary lists it under: ``Max`` for Maximilian, Maxim and
Maksim, ``Bill`` for William, ``Sepp`` for Josef. It is read in the
given name, middle name and nickname, never the family name, and it
runs one way, so two longer names one short name stands for do not
agree with each other. The keys follow: a familiar form is keyed by
its longer names' first letters too, so ``Bill Smith`` meets
``William Smith`` in a group:

.. doctest::

    >>> with_familiar = Parser().matching(accept=matcher.accept | {"familiar-form"})
    >>> bill = with_familiar.check("Bill Smith", "William Smith")
    >>> bill.consistent, bill["given"].outcome.value
    (True, 'familiar-form')
    >>> matcher.check("Bill Smith", "William Smith")["given"].outcome.value
    'familiar-form'
    >>> with_familiar.check("Maximilian Smith", "Maxim Smith").consistent
    False
    >>> sorted(with_familiar.keys("Bill Smith"))
    ['smith;b', 'smith;w']

The shipped familiar forms are the 736 pairs of Jörg Michael's
nam_dict (2008, GNU Free Documentation License 1.2), each in the
vocabulary file of the languages whose countries it lists them for,
so a choice of languages reads its own. It is a selection and has
gaps (``Peggy`` / ``Margaret``, ``Pepe`` / ``José``, ``Will`` /
``William`` are not in it); add your own with a ``familiar`` reading,
which replaces the word's listed longer names, so name them all:

.. doctest::

    >>> maxwell = Lexicon.default().add(
    ...     "max", kind="familiar", short_for=["maximilian", "maxim", "maksim", "maxwell"])
    >>> mine = Parser(lexicon=maxwell).matching(accept=matcher.accept | {"familiar-form"})
    >>> mine.check("Max Smith", "Maxwell Smith").consistent
    True

A familiar form is outside the default because it is many-valued and
often a name of its own: ``Max`` is a given name in its own right, as
``Bill`` and ``Sepp`` are.

``across-roles`` compares a given name with each word of the other
name's middle name and with its nickname, and a family name with the
other's maiden name. It counts only a full name on both sides, never
an initial, and records each match it made in ``across``:

.. doctest::

    >>> with_across = Parser().matching(accept=matcher.accept | {"across-roles"})
    >>> hoover = with_across.check("J. Edgar Hoover", "Edgar Hoover")
    >>> hoover.consistent, hoover["given"].outcome.value
    (True, 'across-roles')
    >>> hoover.across[0].left_role.value, hoover.across[0].right_role.value, hoover.across[0].left
    ('middle', 'given', 'Edgar')
    >>> with_across.check("Jane Doe (née Smith)", "Jane Smith").consistent
    True

The middle word a match uses is taken out of the middle comparison,
and the middle words left are compared role to role.

Consistency is not transitive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``J. Smith`` is consistent with ``John Smith`` and with ``Jane
Smith``, which are not consistent with each other:

.. doctest::

    >>> matcher.check("J. Smith", "John Smith").consistent
    True
    >>> matcher.check("J. Smith", "Jane Smith").consistent
    True
    >>> matcher.check("John Smith", "Jane Smith").consistent
    False

So do not merge records by chaining consistent pairs: a less specific
name joins people a more specific one keeps apart. ``RoleMatch.more``
tells you which side carried more of each role, so of a consistent
pair, one name is a less specific writing of the other when no role
has it carrying more:

.. doctest::

    >>> def less_specific(result):
    ...     return all(row.more.value != "left" for row in result.roles)
    >>> less_specific(matcher.check("J. Smith", "John A. Smith"))
    True
    >>> less_specific(matcher.check("John A. Smith", "J. Smith"))
    False

A role read ``across-roles`` has the side carrying more that held both
the role and the role it was matched against, so ``J. Edgar Hoover``,
which holds a given initial beside the middle name the other uses as
its given name, is the more specific of the two:

.. doctest::

    >>> less_specific(with_across.check("Edgar Hoover", "J. Edgar Hoover"))
    True
    >>> less_specific(with_across.check("J. Edgar Hoover", "Edgar Hoover"))
    False

Link each record to its most specific consistent name rather than to
every name it is consistent with.

.. _parser-guesses:

When the parser had to guess
-----------------------------

Some names have no single correct reading. A leading ``Van`` could be
a given name — it really is for the actor Van Johnson — or the start
of a family name, as it is for President Van Buren. Both are the same
shape, so no rule can tell them apart. The parser takes the more
likely reading and *records* the choice on ``ambiguities`` rather than
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

Most names report none. A non-empty ``ambiguities`` is a useful signal
for routing a record to human review instead of trusting it silently.

.. _credentials-also-surnames:

Credentials that are also surnames
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The post-nominals that double as ordinary surnames report an ambiguity
the same way.
Which reading a bare one gets depends on what the writing says:

- **Capitals** in a name written in more than one case lean to the
  credential, even with no words to spare (``Jack MA``). They settle it,
  as periods do, so nothing is reported.
- **Any other cased spelling** that is not wholly lowercase leans to
  the surname, even with words to spare (``Jack Ma``, ``John Smith Ma``).
- **No signal** — all lowercase, or a name written wholly in one
  case — leaves it to the count: the credential with two or more words
  before it, not counting a title or a nickname, the surname otherwise.

Where the writing leaves the choice to the parser, the choice is
recorded:

.. doctest::

    >>> parse("JOHN SMITH MA").suffix
    'MA'
    >>> [a.kind.value for a in parse("JOHN SMITH MA").ambiguities]
    ['suffix-or-name']
    >>> parse("John Smith MA").ambiguities
    ()
    >>> parse("Jack MA").suffix
    'MA'
    >>> parse("Jack Ma").family
    'Ma'
    >>> parse("John Smith Ma").family
    'Ma'

:ref:`ambiguous-words` has the full rules, including how a comma
changes them.

Two ``Policy`` switches extend the same class to words the vocabulary
does not hold. ``unlisted_dotted_suffixes`` (on by default) reads a
token of two or more period-separated chunks the same way —
``parse("John Smith X.Y.Z.").suffix`` is ``'X.Y.Z.'`` — and
``unlisted_caps_suffixes`` does the same for an unlisted all-caps word,
by default only after a comma behind a full name, where an all-caps
surname is never written — ``parse("John Smith, XYZ").suffix`` is
``'XYZ'`` — and at the end of a name only on request, since an
all-caps surname is written there. See :ref:`unlisted-credentials`
for both.

A reading the vocabulary settles on its own is not a guess and reports
nothing — periods make ``M.A.`` unambiguously a credential:

.. doctest::

    >>> parse("John Smith M.A.").ambiguities
    ()

Titles that are also given names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A title that is also borne as a given name, such as ``Dean``, ``King``
or ``Major``, is a title only inside a title phrase (since 2.7), and
otherwise a name word. Where it opens the name and a phrase could have
held it, the choice is recorded as ``title-or-name``:

.. doctest::

    >>> parse("Dean of Students Jane Smith").title
    'Dean of Students'
    >>> dean_smith = parse("Dean Smith")
    >>> dean_smith.given, [a.kind.value for a in dean_smith.ambiguities]
    ('Dean', ['title-or-name'])

:ref:`titles-also-given-names` covers the phrases and how to read such
a word as a title everywhere.

.. _reading-not-taken:

The reading it did not take
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since 2.7 a report of a fork also says what the other reading was.
``Ambiguity.alternative`` is a :class:`~nameparser.Reading` with three
parts, and since 3.0 a fourth, its ``languages`` (see
:ref:`reading-taken`):

- **kind** — what the word would have been read as: a ``name``, an
  ``initial``, a ``credential``, a ``generation``, a ``particle``, a
  ``title`` and so on (:class:`~nameparser.ReadingKind`).
- **role** — the field the word would have landed in, with every other
  word of the name read as the parse read it.
- **source** — why that reading was there at all
  (:class:`~nameparser.ReadingSource`): ``vocabulary`` for a listed word,
  ``declared`` for a word the vocabulary also lists as a name, ``shape``
  for a roman numeral, dotted letters or a one-letter initial, and
  ``position`` for an ordinary
  word nothing lists, which is a name only by where it stands.

The source is what tells two reports of the same kind apart. ``MA`` is
listed as a surname as well as a credential, so its name reading is
declared; ``Jones`` behind a credential is taken into the credential run
by position alone:

.. doctest::

    >>> for text in ("JOHN SMITH MA", "John Smith PhD Jones", "Van Buren"):
    ...     alt = parse(text).ambiguities[0].alternative
    ...     print(f"{text}: {alt.kind.value} as {alt.role.value} ({alt.source.value})")
    JOHN SMITH MA: name as family (declared)
    John Smith PhD Jones: name as family (position)
    Van Buren: particle as family (vocabulary)

A report of a shape rather than a fork — ``comma-structure``,
``unbalanced-delimiter``, ``segmentation`` — carries no alternative,
and neither does one whose other reading no field could hold: a
connective letter opening the name (``E SMITH JONES``) has no word
before it to join. Check for ``None`` before reading one.
The alternative is not compared: two names that differ only in it are
equal, as before 2.7, and a ``ParsedName`` pickled by an earlier
release loads with no alternative on its reports.

.. _reading-taken:

The reading each word took
~~~~~~~~~~~~~~~~~~~~~~~~~~

Since 3.0 every token also says how the parse read it, whether or not
a fork was reported. ``Token.reading`` is a :class:`~nameparser.Reading`
with the same parts, its role the token's own field, and two flags
besides, ``first_surname`` and ``second_surname``, marking the words
``surname1`` and ``surname2`` hold where the family was read as two,
or had middle names folded into it (``middle_as_family``):

.. doctest::

    >>> for tok in parse("Dr. Juan de la Vega III").tokens:
    ...     print(f"{tok.text}: {tok.reading.kind.value} ({tok.reading.source.value})")
    Dr.: title (vocabulary)
    Juan: name (position)
    de: particle (vocabulary)
    la: particle (vocabulary)
    Vega: name (position)
    III: generation (vocabulary)

Where a fork was reported, the token's reading and the report's
alternative are the two readings the parse weighed. ``Jones`` behind a
credential was taken into the suffix by position, where it would
otherwise have been the family name:

.. doctest::

    >>> jones_run = parse("John Smith PhD Jones")
    >>> jones_run.tokens[-1].reading
    Reading('credential' as 'suffix', 'position')
    >>> jones_run.ambiguities[0].alternative
    Reading('name' as 'family', 'position')

A reading from the vocabulary also names the language files that list
the word that way, as BCP 47 tags in ``languages``: the files whose
reading is on in the parser's own ``Lexicon``, so a choice of languages
(:doc:`locales`) names the files it reads. A reading by shape or
position names none, and neither does a reading you add to your own
``Lexicon`` of a kind no file holds for that word; adding a kind a
file does hold turns that file's reading on, and names it:

.. doctest::

    >>> for tok in parse("Dr. Juan de la Vega III").tokens:
    ...     print(f"{tok.text}: {tok.reading.languages}")
    Dr.: ('mul',)
    Juan: ()
    de: ('ca', 'es', 'fil', 'fr', 'it', 'nl', 'pt', 'si')
    la: ('ca', 'es', 'fil', 'fr', 'it')
    Vega: ()
    III: ('mul',)

``mul`` is the file of words shared across languages on purpose. The
first parse in a process that meets a listed word loads the index of
those files once: about a millisecond, or about 20 ms where Python
writes no bytecode cache (``PYTHONDONTWRITEBYTECODE``).

A token the parse did not read has no reading: one that
:meth:`~nameparser.ParsedName.replace` or
:meth:`~nameparser.Parser.revise` builds, and one loaded from a pickle
written before 3.0. Like the alternative, the reading is not compared,
so it never makes two names unequal.

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
value. There are two ways to make one: ``replace()`` splices the new
text in as written, and :meth:`Parser.revise()
<nameparser.Parser.revise>` reads it the way a parse would.

Splicing a value in with ``replace()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``replace()`` returns a copy with the given fields changed. Untouched
fields keep their tokens (and ``original`` is preserved), with one
deliberate exception: an ambiguity that pointed into a replaced field
is dropped — correcting the field that was flagged clears the flag,
while correcting an unrelated field keeps it.

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

What a spliced value loses
~~~~~~~~~~~~~~~~~~~~~~~~~~

``replace()`` splits values on whitespace into plain, untagged
tokens — the vocabulary knowledge a parse would have about the new
text is not there. A token the parse never saw carries no decision to
honor, so each view falls back on what it can answer without one:

- :meth:`~nameparser.ParsedName.capitalized` is handed a vocabulary,
  so it asks that whether a word is a conjunction or an initial, which
  a word answers on its own. Its other special cases never needed a
  reading: an exceptions-map mask applies wherever its word stands,
  and a listed credential acronym or a roman numeral is written in
  capitals wherever the field is the suffix, so ``replace(suffix="mba")``
  repairs to ``MBA`` and ``suffix="vi"`` to ``VI``. A credential
  recognised only by its dotted shape is the exception, since the shape
  is something the parse records. Particles are a second exception:
  whether a particle is acting as one is a fact about the whole part,
  and no word of a spliced field carries a reading to derive it from,
  so a family set to ``de la`` stays lowercase where the same words
  parsed are repaired to ``De La``.
- :meth:`~nameparser.ParsedName.initials` takes no vocabulary at all,
  so every word of a spliced field contributes an initial.
- ``family_particles`` and ``family_base`` are properties on the
  parsed name, which holds no vocabulary of its own either:
  ``family_particles`` empties and ``family_base`` takes the whole
  field.

Of the parsed name's own views, ``capitalized()`` is the only one
handed a vocabulary.

.. doctest::

    >>> name.family_particles
    'de la'
    >>> replaced = name.replace(family="de la Vega Smith")
    >>> replaced.family_particles
    ''
    >>> replaced.family_base
    'de la Vega Smith'
    >>> replaced.initials()
    'J. d. l. V. S.'
    >>> name.replace(family="de la").capitalized(force=True).family
    'de la'

Reading a value with ``Parser.revise()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
ru``); see :doc:`locales`. A code no pack has that is a language whose
vocabulary file holds readings (``--locale ko``) chooses that language
alone; one whose file holds none yet (``zu``) needs ``--strict``, and
a pack's language with a region or script subtag (``zh-CN``,
``zh-Hant``) exits naming the pack to use.
``--strict`` reads only that language's words and the shared ones (see
:ref:`strict-choice`), and needs ``--locale``:

::

    $ python -m nameparser --locale ko --strict --json "Kim Do Hyun"
    {"title": "", "given": "Kim", "middle": "Do", "family": "Hyun", "suffix": "", "nickname": "", "maiden": ""}

``--order`` reads the name in another order
— ``given-first`` (the default), ``family-first`` or
``family-first-given-last``, the three ``Policy.name_order`` values —
and replaces any order a pack sets. A name written wholly in Han,
Hangul or kana keeps the order its script gives it, and a family comma
fixes the order whatever the flag:

::

    $ python -m nameparser --order family-first --json "Kovács János Péter"
    {"title": "", "given": "János", "middle": "Péter", "family": "Kovács", "suffix": "", "nickname": "", "maiden": ""}

``--lone-name-word`` takes ``given`` (the default) or ``family``, the
field a name of one name word reads as under every order
(:ref:`lone-name-word`):

::

    $ python -m nameparser --lone-name-word family --json "Anh"
    {"title": "", "given": "", "middle": "", "family": "Anh", "suffix": "", "nickname": "", "maiden": ""}

The ``Policy`` switches that turn a reading on or off have a flag each,
spelled as the field: ``--two-given-names``, ``--two-family-names``,
``--middle-as-family``, ``--lenient-comma-suffixes`` and
``--unlisted-dotted-suffixes``, each with a ``--no-`` form, and
``--unlisted-caps-suffixes`` taking ``off``, ``after-comma`` or
``everywhere``. Like ``--order``, each replaces the setting of a pack
given with ``--locale``, keeping the pack's vocabulary, and one left
out keeps the pack's setting. ``es`` reads ``Maestra`` as a title,
which the default reads as a given name, and two family names, and the
flag turns only the second off:

::

    $ python -m nameparser --two-given-names --json "Juan Carlos García"
    {"title": "", "given": "Juan Carlos", "middle": "", "family": "García", "suffix": "", "nickname": "", "maiden": ""}
    $ python -m nameparser --locale es --no-two-family-names --json "Maestra Ana García López"
    {"title": "Maestra", "given": "Ana", "middle": "García", "family": "López", "suffix": "", "nickname": "", "maiden": ""}

Where next
----------

* :doc:`concepts` — how the parser works
* :doc:`customize` — your own vocabulary and behavior
* :doc:`locales` — locale packs
* :doc:`migrate` — coming from 1.x or 2.x ``HumanName``, which 3.0 removes

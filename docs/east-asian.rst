.. _east-asian-names:

East Asian names
=================

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
----------------------

Field assignment is automatic. A name written wholly in Han characters
or hangul is assigned family-first, because every language written in
those scripts orders names that way — Chinese and Japanese share
little else, but they agree on this — so the assignment requires no
knowledge of which language the name is in:

.. doctest::

    >>> from nameparser import Lexicon, parse
    >>> parse("毛 泽东").family
    '毛'
    >>> parse("山田 太郎").family
    '山田'

Splitting an unspaced name
--------------------------

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
-------------------------

Chinese also has a transcription convention, and it is written in the
punctuation: a foreign name transcribed into Han characters keeps its
source order and divides its parts with the 间隔号, the interpunct
``·`` (U+00B7) — 威廉·莎士比亚 is William Shakespeare, given name
first; Taiwan's writers sometimes type the fullwidth full stop ``．``
(U+FF0E) there, which reads the same. The dot itself is the marker, so
nameparser reads U+00B7 as a
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
---------

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
~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~

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
-----------

Several boundaries apply to all of the above.

When the script rules don't apply
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
neither form by default, since 王君 is a complete Chinese name, though
its kana spelling くん peels. ``parser_for(locales.JA)`` turns 君 on, glued
and spaced, as the Diet writes it (``逢沢　一郎君`` gives suffix ``君``).

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A division the parser had to choose is reported rather than hidden.
When an unspaced name has more than one vocabulary-supported split,
the longest surname wins and the parse records the decision as an
``AmbiguityKind.SEGMENTATION``, described under :ref:`When the parser had
to guess <parser-guesses>`. ``남궁민수`` is 남궁 + 민수 by the two-syllable surname but
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
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A segmenter that answers outside the token it was given, with a cut at
or past the end of the text, has violated the protocol, and the parse
says so rather than hiding it. It raises ``ValueError`` naming the
offending offset and the token's length, the way an answer of the
wrong type raises ``TypeError``. Declining silently would leave an
off-by-one segmenter invisible: every answer it gave would vanish and
the name would merely look undivided.

The shipped ``ja_segmenter()`` does decline, returning ``None`` and
leaving the token whole, for the cases that are *not* protocol
violations: text outside the Japanese repertoire, text with no kanji
(namedivider divides by kanji statistics, so ``あいさわいちろう`` stays
whole rather than splitting after its first character), text too short
to divide, an answer that fails to reconstruct its input, and a score
outside [0, 1].

Exceptions are the one thing that does *not* stay inside the parse: a
segmenter is your code, so its errors propagate rather than being
absorbed as content errors.

The command line attaches the segmenter for you: ``python -m
nameparser --locale ja`` uses :func:`~nameparser.locales.ja_segmenter`
when ``nameparser[ja]`` is installed, and without it divides nothing
and prints a note naming the install. :func:`~nameparser.parser_for` never
does this on its own, so the same code parses alike wherever it runs.
:ref:`east-asian-defaults` covers turning any of these behaviors off.

.. _east-asian-defaults:

East Asian defaults, and turning them off
-----------------------------------------

Two defaults key on the *script* a name is written in rather than on
anything you set: a name written wholly in Han or Hangul — or in kanji
and kana, unless it is katakana alone — is assigned family-first
(``script_orders``),
and an unspaced hangul name is split into surname and given name
against the shipped Korean census list (``segment_scripts``).
:ref:`east-asian-names` explains the naming conventions both rest on;
this section is how to switch them off. Two further behaviors are not
policy fields at all, and are covered last.

Switching off order and splitting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The two defaults switch off separately:

.. doctest::

    >>> parse("김민준").family                    # both defaults on
    '김'
    >>> positional = Parser(policy=Policy(script_orders=()))
    >>> positional.parse("김민준").family         # still split
    '민준'
    >>> unsplit = Parser(policy=Policy(segment_scripts=frozenset()))
    >>> unsplit.parse("김민준").family            # one token, not split
    '김민준'

The two switches interact, and clearing only ``script_orders``
produces a third behavior rather than the old one: the split still
runs, so ``김민준`` still becomes two tokens, and the positional
default then assigns them given-first — the surname lands in
``given``. To restore nameparser 2.0's reading exactly, clear both
fields.

.. note::

   Every field here is annotated with its canonical *storage* type
   rather than with everything the constructor accepts — the same as
   ``capitalization_exceptions``, and for the same reason: the
   annotation is what you get back when you READ the attribute, which
   is the commoner operation.

   The constructor is deliberately wider. It takes any mapping for
   ``script_orders``, any iterable of ``Script`` for
   ``segment_scripts``, and plain strings wherever a ``Role`` is
   wanted (``Role`` is a ``StrEnum`` precisely so that works). A
   dataclass cannot express those two types separately, so the
   examples in this guide use the spellings that check clean under
   mypy — ``()`` and ``frozenset(...)`` rather than ``{}`` and a bare
   set literal. The wider spellings parse identically; they just need
   a ``# type: ignore[arg-type]`` if you run a type checker.

Teaching the splitter a surname
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To teach the splitter a surname it doesn't ship with, join a lexicon
holding it to the ``surnames`` list, a list rather than readings since
it divides a name instead of gating a word:

.. doctest::

    >>> lex = Lexicon.default() | Lexicon(surnames={"김민"})
    >>> Parser(lexicon=lex).parse("김민준").family
    '김민'

Chinese surnames are deliberately absent from that default set,
because splitting Han text requires knowing Chinese from Japanese;
:doc:`locales` covers the opt-in ``zh`` pack that supplies them.

Japanese names
~~~~~~~~~~~~~~

The Japanese behaviors ride these same two fields, so they need no
switches of their own. ``script_orders=()`` clears the kana-licensed
entry along with the Han and Hangul ones, so a name in kanji and kana
reads given-first again:

.. doctest::

    >>> parse("山田 エミ").family
    '山田'
    >>> positional.parse("山田 エミ").given
    '山田'

``segment_scripts=frozenset()`` deactivates every script at once, which
also stops a parser consulting whatever segmenter it was given. The
segmenter has an off-switch of its own as well:
``Parser(segmenter=None)``, which is the default. See
:ref:`segmenter-contract` for what a segmenter is expected to do with
text it does not handle.

Behaviors no policy field controls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two behaviors apply however both fields are set:

- **The katakana middle dot** ``・`` separates tokens the way a space
  does, decided in tokenization.
- **A glued honorific**, a listed CJK honorific at the end of a name
  token, is split off it. The honorific vocabulary carries its own
  license rather than borrowing a script's: every entry is a word that
  can never end a name, so there is no per-script question for
  ``segment_scripts`` to answer.

.. doctest::

    >>> both_off = Parser(
    ...     policy=Policy(script_orders=(), segment_scripts=frozenset()))
    >>> both_off.parse("マイケル・ジャクソン").family
    'ジャクソン'
    >>> both_off.parse("田中さん").suffix
    'さん'

The honorific vocabulary is the peel's off-switch. Taking the
``attached`` property off an honorific's reading leaves that honorific
glued, while the spaced form still reads it as a suffix:

.. doctest::

    >>> no_san = Parser(lexicon=Lexicon.default().add(
    ...     "さん", kind="honorific", attached=None))
    >>> no_san.parse("田中さん").family
    '田中さん'
    >>> no_san.parse("田中 さん").suffix
    'さん'

The suffix reading stays, so the word is still a suffix written apart.
Taking ``attached`` off every honorific is also how to opt out of what
the peel *costs* a non-ASCII parse: with none attached the peel stops
at its first check, whereas ``segment_scripts`` never gated it and so
cannot turn it off.

.. _segmenter-contract:

Segmenters
-----------

``ja``'s policy half is inert in a second sense: it turns division on for
Japanese text without supplying anything to divide with. That job goes
to a **segmenter**, which is passed to
:func:`~nameparser.parser_for` rather than carried by the pack — a
:class:`~nameparser.Locale` is pure data, and a third-party callable is
neither pure nor data. :func:`~nameparser.locales.ja_segmenter` is the
shipped one; writing your own is worth it for any script whose
divisions you know better than a surname list does.

A :data:`~nameparser.Segmenter` is any callable taking a token's text
and returning a :class:`~nameparser.Segmentation` — the interior
offsets to cut at, plus how confident you are — or ``None`` to decline,
leaving the token whole. Declining is the load-bearing half of the
contract, because ``segment_scripts`` unions across packs: your
segmenter may be offered a token of any activated script, not only the
ones its own pack turned on. It is asked only where the surname list
could not divide an unspaced token, and not where the name is already
divided — by a second word in an East Asian script (the nakaguro ・
counts as a space), a family comma or a 间隔号. A word in any other
script beside the token — Latin (``"Dr. 高橋一郎"``), Cyrillic — divides
nothing, so the segmenter is still asked. Halfwidth katakana counts as
katakana, so ``"高橋一郎 ﾀﾛｳ"`` is already divided. Recognize the text
you can actually read and return ``None`` for the rest, rather than
answering for a script you never meant to handle. A segmenter is your
code, so its failures do not stay inside the parse: its own exceptions
propagate out of ``parse()``, and an answer of the wrong type or a cut
outside the token raises ``TypeError`` or ``ValueError``.

The pack half of that arrangement carries no words at all, which makes
it the shortest kind of pack there is:

.. doctest::

    >>> from nameparser import Lexicon, Locale, PolicyPatch, Script
    >>> script_pack = Locale(code="myscript", lexicon=Lexicon.empty(),
    ...               policy=PolicyPatch(
    ...                   segment_scripts=frozenset({Script.HAN})))

``nameparser/locales/ja.py`` is the shipped example of exactly that
shape: activation is the pack's entire contribution. Applied without a
segmenter it divides nothing, and building the parser emits a
``UserWarning`` naming the scripts that can never divide and the
argument to pass.

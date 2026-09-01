Customizing the parser
=======================

Every piece of nameparser configuration sorts into one of three places
by asking what it varies with: vocabulary varies by **language**
(:class:`~nameparser.Lexicon`), behavior varies by **data source or
application** (:class:`~nameparser.Policy`), and presentation varies by
**output destination** (a rendering argument). See :doc:`concepts` for
why the split is drawn there.

Vocabulary: Lexicon
--------------------

Adding and removing words
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. doctest::

    >>> from nameparser import Lexicon, Parser
    >>> lex = Lexicon.default().add(titles={"dean"})
    >>> Parser(lexicon=lex).parse("Dean Robert Johns").title
    'Dean'

:meth:`~nameparser.Lexicon.add` and :meth:`~nameparser.Lexicon.remove`
both return a new :class:`~nameparser.Lexicon` — the one you started
from (here, ``Lexicon.default()``) is never mutated. Every field
accepts a plain set of lowercase words, keyword by field name (``titles``
above; ``particles``, ``suffix_words``, and the rest work the same
way) — see :doc:`modules` for the full field list.

The default word lists themselves — ``TITLES``, ``PARTICLES`` and the
other frozensets in ``nameparser.config`` — are frozen, so a runtime
addition belongs on a :class:`~nameparser.Lexicon` as above, or on a
private ``Constants`` if you are still parsing through ``HumanName``.
``REGEXES`` and ``CAPITALIZATION_EXCEPTIONS`` are the two members the
freeze does not cover — they are still plain dicts. Editing one at
runtime is not a supported override, and it is not a clean no-op
either: the edit reaches a freshly built ``Constants``, while the
shared ``CONSTANTS`` (copied at import) and the cached
:meth:`~nameparser.Lexicon.default` never see it. That is the same
inconsistent reach the freeze removed for the word lists, so these
overrides belong on a config object too.

Five of these lists were renamed in 2.2 to match the field names used
here: ``PREFIXES``, ``NON_FIRST_NAME_PREFIXES``, ``BOUND_FIRST_NAMES``,
``FIRST_NAME_TITLES`` and ``SUFFIX_NOT_ACRONYMS`` became ``PARTICLES``,
``NON_GIVEN_NAME_PARTICLES``, ``BOUND_GIVEN_NAMES``,
``GIVEN_NAME_TITLES`` and ``SUFFIX_WORDS``, and two modules moved with
them. Names outside that list, ``TITLES`` among them, are unchanged.
Every 1.x name still imports, with a ``DeprecationWarning``, until 3.0
— see :doc:`migrate` for the full mapping.

Vocabulary entries are matched one word at a time, with two
exceptions, so a multi-word entry like ``titles={"grand moff"}`` can
never match; the constructor warns when it sees one
(``capitalization_exceptions`` keys included — they are looked up per
word too). The exceptions are ``given_name_titles``, looked up as the
space-joined run of words already read as titles, and
``maiden_markers``, matched by lookahead over the words as written:
``maiden_markers={"z domu"}`` matches the pair and neither word alone,
which is how the shipped Polish entry works. The words have to stand
together — a bracketed clause or a comma between them ends the run, and
the first word is then an ordinary name word. Where a phrase entry and a
word entry starting with it are both configured, the phrase wins where
it matches and the word matches everywhere else. No warning is raised
for a multi-word entry in either of these two fields, since there it is
not a mistake.

The limit is on *storage*, not on the shape a name can have. Adjacent
suffix words are reassembled after they match, so a multi-word
credential is reachable as its component words even though the phrase
itself cannot be stored:

.. doctest::

    >>> from nameparser import parse
    >>> parse("John Smith, MD PhD").suffix
    'MD PhD'

That has held since 1.4.0. A credential whose words are not in the
default vocabulary is reached by adding those words, not the phrase:

.. doctest::

    >>> lex = Lexicon.default().add(suffix_acronyms={"leed", "ap"})
    >>> Parser(lexicon=lex).parse("John Smith, LEED AP").suffix
    'LEED AP'

Removing works the same way, and drops the word from recognition:

.. doctest::

    >>> lean = Lexicon.default().remove(titles={"professor"})
    >>> Parser(lexicon=lean).parse("Professor Robert Johns").title
    ''

A few fields mark a subset of another — ``given_name_titles`` over
``titles``, ``particles_ambiguous`` over ``particles``,
``suffix_acronyms_ambiguous`` over ``suffix_acronyms``, and
``honorific_tails`` over ``suffix_words``. Entries belong in the base
field too, so add to both and remove from the marker first. The last
three enforce that: anything else raises ``ValueError`` naming the
orphans rather than leaving a marker entry that no rule will ever
consult. ``given_name_titles`` is deliberately unchecked — a title run
is matched as one space-joined string, so a legitimate entry like
``"sir and dame"`` is no single word in ``titles`` — and an orphan
there is inert rather than harmful.

Turning title detection off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The subset rule matters most when clearing a field wholesale. Emptying
``titles`` alone orphans every ``given_name_titles`` entry, so the two
go together:

.. doctest::

    >>> d = Lexicon.default()
    >>> lean = d.remove(titles=set(d.titles),
    ...                 given_name_titles=set(d.given_name_titles))
    >>> Parser(lexicon=lean).parse("Hon Solo").given
    'Hon'

Emptying the vocabulary does not switch titles off entirely, though. A
word ending in a period, standing at the front of the part that carries
the given name, is read as a title structurally, without consulting
``titles`` at all — that is what lets unfamiliar ranks and
abbreviations work (see :ref:`abbreviated-titles`):

.. doctest::

    >>> bare = Parser(lexicon=Lexicon.empty())
    >>> bare.parse("Professor John Smith").title      # vocabulary gone
    ''
    >>> bare.parse("Dr. John Smith").title            # structural, stays
    'Dr.'

Combining two lexicons
~~~~~~~~~~~~~~~~~~~~~~~

Whole lexicons compose with ``|``, which unions field by field — handy
for keeping a shared house vocabulary separate from a per-source one
and combining them at parser construction:

.. doctest::

    >>> house = Lexicon.empty().add(titles={"dean"})
    >>> per_source = Lexicon.empty().add(titles={"provost"})
    >>> sorted((house | per_source).titles)
    ['dean', 'provost']

Fixing the case of a particular word
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``capitalization_exceptions`` is the one pair-valued field — each entry
maps a lowercase key to its exact-cased replacement (``"phd"`` →
``"PhD"``), so it isn't a fit for ``add()``/``remove()``. Change it with
``dataclasses.replace()`` instead, and pass the result to
``capitalized()``:

.. doctest::

    >>> import dataclasses
    >>> from nameparser import parse
    >>> str(parse("jane smith dds").capitalized())
    'Jane Smith Dds'
    >>> default = Lexicon.default()
    >>> lex = dataclasses.replace(
    ...     default,
    ...     capitalization_exceptions=tuple(default.capitalization_exceptions)
    ...     + (("dds", "DDS"),))
    >>> str(parse("jane smith dds").capitalized(lex))
    'Jane Smith DDS'

Note the ``tuple(...) + ...``: assigning a bare ``(("dds", "DDS"),)``
would *replace* the default exceptions rather than extend them, so
``"phd"`` and the rest would stop being fixed.

The key is matched against the token with punctuation normalized away,
not against the raw text, so one ``"phd"`` entry covers ``"phd"``,
``"Phd"``, and ``"Ph.D."`` alike — you don't need a separate key for
each way a source might punctuate it.

Words that are also ordinary names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two fields — ``suffix_acronyms_ambiguous`` and ``particles_ambiguous``
— mark entries from ``suffix_acronyms`` and ``particles`` that are also
plausible as ordinary name words on their own (an acronym suffix that
doubles as a nickname, a particle that doubles as a given name). They
don't add new vocabulary by themselves; they narrow how an existing
entry is read when it appears alone. If you're not sure whether a word
you're adding is one of these ambiguous cases, leave it out — an
unrecognized word usually still parses reasonably, while a wrongly
disambiguated one silently picks the less likely reading. (That
conservatism is why ``dean`` above isn't in the default vocabulary in
the first place: "Dean" is also a common given name, and a default
that swallowed it as a title would misparse "Dean Martin" for
everyone.)

``ma`` is a shipped example. It is both a credential and a common
surname, so it is listed in ``suffix_acronyms_ambiguous`` and counts as
a suffix only when written with periods:

.. doctest::

    >>> parse("Jack Ma").family
    'Ma'
    >>> parse("Jack M.A.").suffix
    'M.A.'

``particles_ambiguous`` is the same idea for surname particles. A
particle listed there may also be a given name, which is what makes a
leading one a decision to take; a particle *not* listed there never
is, so there is nothing to decide. That shows up in what a particle
standing *alone* at the front of a name does: a listed one is a name
part in its own right, while an unlisted one pulls the rest of the
name into the surname and leaves no given name at all. Which field a
*listed* particle lands in is ``name_order``'s question, covered
below; an unlisted one opening the name is the surname under every
order, because a word that can never be a given name leaves the order
nothing to decide.

.. doctest::

    >>> parse("van Gogh").given          # 'van' may be a given name
    'van'
    >>> parse("de Mesnil").given         # 'de' may not
    ''
    >>> parse("de Mesnil").family
    'de Mesnil'

A comma forestalls the question rather than answering it. Writing the
surname before the comma has already said which words are the surname,
so a particle at the front of them decides nothing, and whatever
follows the comma is the given name as usual:

.. doctest::

    >>> parse("de Mesnil, Juan").given   # the comma named the surname
    'Juan'

If your data never uses ``Van`` as a given name, take it out of the
ambiguous set: a leading ``van`` is then no decision at all, so no
ambiguity is recorded and it becomes part of the surname — under any
``name_order``, since that is what taking the word out asserted:

.. doctest::

    >>> lex = Lexicon.default().remove(particles_ambiguous={"van"})
    >>> Parser(lexicon=lex).parse("van Gogh").family
    'van Gogh'

Bound given names
~~~~~~~~~~~~~~~~~~

``bound_given_names`` holds given-name prefixes that attach to the
following word to form one given name — ``abdul``, ``abu``, ``umm`` and
their Arabic-script spellings (``عبد``, ``أبو``, ``أم``) among them:

.. doctest::

    >>> parse("abdul salam ahmed salem").given
    'abdul salam'

Add your own, or empty the set to switch the behavior off entirely:

.. doctest::

    >>> lex = Lexicon.default().add(bound_given_names={"mohamad"})
    >>> Parser(lexicon=lex).parse("mohamad salam ahmed salem").given
    'mohamad salam'
    >>> d = Lexicon.default()
    >>> off = d.remove(bound_given_names=set(d.bound_given_names))
    >>> Parser(lexicon=off).parse("abdul salam ahmed salem").given
    'abdul'

Behavior: Policy
-----------------

When your data source or application needs different parsing behavior
— a different name order, stricter suffix rules, extra delimiters —
set it on :class:`~nameparser.Policy`, a small, closed set of fields,
listed below.

.. list-table::
   :header-rows: 1
   :widths: 22 28 50

   * - Field
     - Type
     - Effect
   * - ``name_order``
     - one of the three exported order constants
     - Assigns positional (no-comma) input to given/middle/family in
       this order. Use the exported ``GIVEN_FIRST`` (default),
       ``FAMILY_FIRST``, or ``FAMILY_FIRST_GIVEN_LAST`` constants.
       Ignored when a comma separates family from given ("Thomas,
       John" puts the family name first); a comma that only sets off
       suffixes ("John Smith, Jr.") leaves it governing the name part.
   * - ``patronymic_rules``
     - ``frozenset[PatronymicRule]``
     - Reorders patronymic-shaped names via opt-in detectors — East
       Slavic formal order (``EAST_SLAVIC``) or Turkic reversed order
       (``TURKIC``). Defaults to empty.
   * - ``middle_as_family``
     - ``bool``
     - Folds ``middle`` into ``family`` instead of splitting them —
       for naming systems with no middle-name concept. Defaults to
       ``False``.
   * - ``nickname_delimiters``
     - ``frozenset[tuple[str, str]]``
     - Routes content enclosed by these delimiter pairs to
       ``nickname``. Defaults to
       :data:`~nameparser.DEFAULT_NICKNAME_DELIMITERS` — straight
       quotes and parentheses plus the typographic conventions (smart
       quotes, guillemets, CJK brackets, ...).
   * - ``maiden_delimiters``
     - ``frozenset[tuple[str, str]]``
     - Routes content enclosed by these delimiter pairs to ``maiden``
       instead, and drops them from the effective nickname set. Set
       this for a clause that says nothing about itself, which is two
       kinds of clause and not one: content with no marker word in it
       (``"Cherice J. (Johnson) Williams"``, the parenthesized birth
       surname written bare) AND a lone marker word
       (``"Jane Smith (Nee)"``, which reads nickname ``Nee`` by default
       and maiden ``Nee`` only with the pair listed here). What needs
       no configuration since 2.2 is a clause that opens with a marker
       word AND has a word after it: ``"Jane Smith (née Jones)"`` reads
       maiden ``Jones`` whatever pair encloses it, unless the content is
       suffix-shaped, which is taken ahead of both: the brackets are
       dropped and the content parses as if written bare, so
       ``"Jane Smith (née Jr.)"`` gives family ``née``, suffix ``Jr.``
       rather than a suffix of the whole clause. A marker word opening
       the enclosed content is dropped from the value either way, but
       only where that content holds more than one *token* — the same
       reason a lone ``"(Nee)"`` listed here keeps ``Nee`` as the
       maiden value rather than reading it as a marker. Tokens, not words: a marker written
       against the name it marks is one token with them, so
       ``"山田花子（旧姓佐藤）"`` keeps its ``旧姓``. Defaults to empty —
       see the routing example below.
   * - ``extra_suffix_delimiters``
     - ``frozenset[str]``
     - Adds separators that split suffix groups, e.g. ``" - "`` for
       ``"Jane Smith, RN - CRNA"``. Additions only — the comma always
       splits suffix groups and cannot be replaced.
   * - ``lenient_comma_suffixes``
     - ``bool``
     - Reads an initial-shaped suffix word after a comma as a suffix:
       ``"John Smith, V"`` is John Smith the fifth when ``True``
       (default); ``False`` reads ``V`` as a given-name initial
       instead. Multi-letter suffixes (``III``, ``MD``) are
       unaffected. The same test is also one of the two the
       glued-honorific peel asks before crossing a family comma
       (#319), so the setting reaches CJK names too: ``"田中さん,
       V."`` gives family ``田中``, suffix ``さん`` when ``True``, and
       family ``田中さん``, given ``V.`` when ``False``.
   * - ``strip_emoji``
     - ``bool``
     - Excludes emoji from tokenization — they appear in no field or
       rendered view, though ``original`` keeps them. Defaults to
       ``True``.
   * - ``strip_bidi``
     - ``bool``
     - Excludes bidirectional control characters the same way.
       Defaults to ``True``.

To apply a :class:`PolicyPatch <nameparser.PolicyPatch>` directly --
without going through a locale pack -- call :meth:`Policy.patched()
<nameparser.Policy.patched>`:

.. doctest::

    >>> from nameparser import Policy, PolicyPatch
    >>> Policy().patched(PolicyPatch(middle_as_family=True))
    Policy(middle_as_family=True)

Family-first name order
~~~~~~~~~~~~~~~~~~~~~~~~

``name_order`` is the one most likely to matter for data that is not
in Western order. Positional input is assigned in the order you
declare — with the two vocabulary exceptions noted at the end of this
section — so a name written family-first — Hungarian, here — parses as
written instead of needing to be rearranged afterwards:

.. doctest::

    >>> from nameparser import Parser, Policy, FAMILY_FIRST, parse
    >>> parse("Nagy Laszlo Peter").family            # default GIVEN_FIRST
    'Peter'
    >>> family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> name = family_first.parse("Nagy Laszlo Peter")
    >>> name.family, name.given, name.middle
    ('Nagy', 'Laszlo', 'Peter')

An explicit comma still wins, on the reasoning that someone who wrote
one meant it — so the same parser reads ``"Thomas, John"`` as
family-then-given regardless of the configured order:

.. doctest::

    >>> family_first.parse("Thomas, John").family
    'Thomas'

A Vietnamese full name needs a third order. It is written family, then
middle, then given — the name a person is actually called by is the
*last* word, not the second. Family-first order gets the family name
right and then reverses the remaining two, so
``FAMILY_FIRST_GIVEN_LAST`` exists for the names that read this way:

.. doctest::

    >>> from nameparser import FAMILY_FIRST_GIVEN_LAST
    >>> family_first.parse("Tran Quoc Toan").given       # FAMILY_FIRST
    'Quoc'
    >>> given_last = Parser(policy=Policy(name_order=FAMILY_FIRST_GIVEN_LAST))
    >>> viet = given_last.parse("Tran Quoc Toan")
    >>> viet.family, viet.middle, viet.given
    ('Tran', 'Quoc', 'Toan')

Nothing keys this order to a script the way the East Asian defaults
below do — Vietnamese is written in the Latin alphabet, which carries
no order of its own — so it applies only where you set it, and there
is no ``vn`` locale pack yet (issue `#146
<https://github.com/derek73/python-nameparser/issues/146>`_).

Declaring the order settles where a surname ends
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A surname particle joins forward, onto the word after it. Where a
particle *ends* the name there is nothing ahead of it to join, and what
it belongs to is decided by what the writing says rather than by the
word. Two things say it, and both amount to someone stating that the
family name came first — a family comma, and a declared family-first
order — so a Dutch listing reads the same either way:

.. doctest::

    >>> parse("Jong, Anke de").family                  # the comma says so
    'de Jong'
    >>> family_first.parse("Jong Anke de").family      # the order says so
    'de Jong'

``FAMILY_FIRST`` is the only order this arises under, because it is the
only one that puts a trailing piece in the *middle*, where a particle
means nothing. ``FAMILY_FIRST_GIVEN_LAST`` puts it in the given slot,
where your own declaration says it is the given name, so it stays one:

.. doctest::

    >>> given_last.parse("Nguyen Thi Van").given
    'Van'

The declaration also bounds how far a *leading* particle run reaches.
With no order declared, nothing marks where the surname ends and a
particle followed by several words really can be all surname, so the
whole name is read as one. Declaring family-first asserts that what
follows the family is not more surname, which settles it:

.. doctest::

    >>> parse("de Mesnil Juan").family                 # nothing says where it ends
    'de Mesnil Juan'
    >>> family_first.parse("de Mesnil Juan").family    # the order does
    'de Mesnil'
    >>> family_first.parse("de Mesnil Juan").given
    'Juan'

In the default order, write the comma for that reading. The run stops
after one name *word* rather than one token, so it cannot cut inside a
conjunction-joined run or a bound given-name pair —
``"de la Vega y Santos Juan"`` keeps family ``de la Vega y Santos``.
Where two or more words are left over, the two family-first orders
differ from each other:

.. doctest::

    >>> family_first.parse("de la Cruz Juan Carlos").middle
    'Carlos'
    >>> given_last.parse("de la Cruz Juan Carlos").middle
    'Juan'

Two cautions, both places where the vocabulary layer answers before
``name_order`` is consulted at all.

The first is why the example above is not the more obvious
``"Nguyen Van Minh"``: a middle word that is also a shipped particle
is claimed by the vocabulary layer. ``Van`` is the Dutch particle
``van``, so that name reads family ``Nguyen`` with ``Van Minh`` given
under *both* family-first orders, and the choice between them makes no
difference.

The second is at the *front* of a name, and there the vocabulary
overrides the declared order outright: where a particle that can never
be a given name stands alone as the opening piece, the whole name is
the surname, in every ``name_order``. ``"de Mesnil"`` is family ``de
Mesnil`` under both family-first orders exactly as it is by default,
not family ``de`` with ``Mesnil`` given — a word that can never be a
given name leaves the order nothing to decide. Only the never-given
set does this: ``"van Gogh"`` reads family ``van``, given ``Gogh``
under a family-first order, because ``van`` *can* be a given name and
so leaves a real question to answer.

`Words that are also ordinary names`_ covers dropping a word from a
vocabulary, or moving one between those two sets.

East Asian defaults, and turning them off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two defaults key on the *script* a name is written in rather than on
anything you set: a name written wholly in Han or Hangul — or one
mixing kanji with kana — is assigned family-first (``script_orders``),
and an unspaced hangul name is split into surname and given name
against the shipped Korean census list (``segment_scripts``).
:ref:`east-asian-names` explains the naming conventions both rest on —
this section is how to switch them off, which you can do separately:

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

To teach the splitter a surname it doesn't ship with, add it to the
``surnames`` vocabulary like any other word:

.. doctest::

    >>> lex = Lexicon.default().add(surnames={"김민"})
    >>> Parser(lexicon=lex).parse("김민준").family
    '김민'

Chinese surnames are deliberately absent from that default set,
because splitting Han text requires knowing Chinese from Japanese;
:doc:`locales` covers the opt-in ``zh`` pack that supplies them.

The Japanese behaviors ride these same two fields, so they need no
switches of their own: ``script_orders=()`` clears the kana-licensed
entry along with the Han and Hangul ones, and
``segment_scripts=frozenset()``
deactivates every script at once, which also stops a parser consulting
whatever segmenter it was given. The segmenter has an off-switch as
well — ``Parser(segmenter=None)``, which is the default; see
:ref:`segmenter-contract` for what one is expected to do with text it
does not handle. Two behaviors are not policy fields at all, and apply
however these two fields are set. The katakana middle dot ・ separates
tokens the way a space does, decided in tokenization. And a listed CJK
honorific glued to the end of a name token is split off it — ``田中さん``
reads family ``田中`` with ``さん`` in ``suffix`` — because the tail
vocabulary carries its own license rather than borrowing a script's:
every entry is a word that can never end a name, so there is no
per-script trust question for ``segment_scripts`` to answer. That
vocabulary is also the peel's off-switch —
``Lexicon.default().remove(honorific_tails={"さん"})`` leaves
``田中さん`` unsplit while the spaced ``田中 さん`` still reads ``さん``
as a suffix. Dropping a word from a marker field alone orphans
nothing, so that one needs no matching ``suffix_words`` edit. Emptying
the field is also the way to opt out of what the peel *costs* a
non-ASCII parse — an empty ``honorific_tails`` stops it at its first
guard, whereas ``segment_scripts`` never gated it and so cannot turn it
off.

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

Nicknames, maiden names, and brackets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A delimiter pair carries no meaning of its own, so what a clause reads
as is settled in steps. Suffix-shaped content is taken first: the
brackets are dropped and what was inside parses as if it had been
written bare, which is not the same as the clause becoming the suffix
(``"Jane Smith (née Jr.)"`` gives family ``née``, suffix ``Jr.``).
Then the content is asked whether it announces itself: a
clause opening with a recognized maiden marker and carrying a word
after it is a maiden name whatever encloses it, and needs nothing
configured. Only for what is left — markerless content, and a lone
marker word — does the PAIR decide, and that is what this knob is for.
Listing a pair here drops it from the effective
``nickname_delimiters`` set automatically, and the one-liner is the
whole recipe:

.. doctest::

    >>> policy = Policy(maiden_delimiters=frozenset({("(", ")")}))
    >>> Parser(policy=policy).parse("Jane (Jones) Smith").maiden
    'Jones'

To *add* a delimiter pair rather than reroute one, build on the
exported default — assigning a bare set replaces the built-in pairs
instead of extending them, the same trap as ``capitalization_exceptions``:

.. doctest::

    >>> from nameparser import DEFAULT_NICKNAME_DELIMITERS
    >>> parse("Benjamin {Ben} Franklin").middle        # not a pair by default
    '{Ben}'
    >>> policy = Policy(
    ...     nickname_delimiters=DEFAULT_NICKNAME_DELIMITERS | {("{", "}")})
    >>> Parser(policy=policy).parse("Benjamin {Ben} Franklin").nickname
    'Ben'

Suffixes not separated by commas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``extra_suffix_delimiters`` handles sources that separate post-nominals
with something other than a comma. The default reading of such a name
is bad enough to be the reason you'd go looking:

.. doctest::

    >>> name = parse("Jane Smith, RN - CRNA")
    >>> name.given, name.family, name.suffix
    ('RN', 'Jane Smith', 'CRNA')
    >>> policy = Policy(extra_suffix_delimiters={" - "})
    >>> name = Parser(policy=policy).parse("Jane Smith, RN - CRNA")
    >>> name.given, name.family, name.suffix
    ('Jane', 'Smith', 'RN, CRNA')

Keeping emoji and control characters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The strip flags keep characters the parser removes by default. Note
what happens to an emoji you keep — it becomes a token like any other,
and lands in the middle name:

.. doctest::

    >>> str(parse("Sam 😊 Smith"))                      # stripped by default
    'Sam Smith'
    >>> kept = Parser(policy=Policy(strip_emoji=False)).parse("Sam 😊 Smith")
    >>> str(kept), kept.middle
    ('Sam 😊 Smith', '😊')

``strip_bidi=False`` does the same for invisible bidirectional control
characters, which is occasionally what you want when round-tripping
right-to-left text verbatim.

.. _rendering-arguments:

Presentation: rendering arguments
----------------------------------

Once a name is parsed, how it's displayed is a separate decision made
at the point of output, not baked into the parse. Three methods on
:class:`~nameparser.ParsedName` cover it — see :doc:`modules` for full
signatures:

* :meth:`~nameparser.ParsedName.render` fills a format spec from the
  seven role fields.
* :meth:`~nameparser.ParsedName.initials` is the same idea narrowed to
  first letters, with its own ``delimiter``/``separator`` arguments.
* :meth:`~nameparser.ParsedName.capitalized` returns a new, case-fixed
  :class:`~nameparser.ParsedName` instead of a string. It only touches
  input that's already single-case (all lower, all upper) unless you
  pass ``force=True`` — mixed case is left alone by default on the
  assumption that someone already capitalized it on purpose.

.. doctest::

    >>> from nameparser import parse
    >>> name = parse("Dr. Juan Q. Xavier de la Vega III")
    >>> name.render("{family}, {given} {middle}")
    'de la Vega, Juan Q. Xavier'
    >>> name.initials(spec="{given}{middle}{family}", delimiter="", separator="")
    'JQXV'
    >>> str(parse("DR. JUAN DE LA VEGA").capitalized())
    'Dr. Juan de la Vega'
    >>> str(parse("JuAn DE LA vEGA").capitalized())
    'JuAn DE LA vEGA'
    >>> str(parse("JuAn DE LA vEGA").capitalized(force=True))
    'Juan de la Vega'

Looking for v1's ``string_format``? It's the ``render(spec)`` argument
now — pass your own format string per call instead of setting it once
on a shared config object.

A spec chooses what the output is *for*. The default is written for
display and does not survive a reparse — it parenthesizes the maiden
name, which reads back as a nickname. When the rendered string will be
parsed again, spell the marker out (``née {maiden}``) so the field
round-trips; see :ref:`the round-trip note in the tour <maiden-roundtrip>`.

Sharing a configured parser
----------------------------

A :class:`~nameparser.Parser` is a frozen value, so the way to share
one configuration across a codebase is the same way you'd share any
other constant: build it once at module level and import it wherever
you parse.

.. code-block:: python

    # myapp/names.py
    from nameparser import Lexicon, Parser, Policy

    lex = Lexicon.default().add(titles={"dean"})
    policy = Policy(strip_emoji=False)
    parser = Parser(lexicon=lex, policy=policy)

    # elsewhere
    from myapp.names import parser
    name = parser.parse(raw_name)

Because :class:`~nameparser.Parser` and its ``lexicon``/``policy`` are
immutable and hashable, ``parser`` is safe to import and call from
multiple threads with no locking — there is no shared mutable state to
protect, unlike v1's module-level ``CONSTANTS``.

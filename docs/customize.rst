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

Vocabulary entries are matched one word at a time (``given_name_titles``
excepted), so a multi-word entry like ``titles={"grand moff"}`` can
never match; the constructor warns when it sees one
(``capitalization_exceptions`` keys included — they are looked up per
word too).

Removing works the same way, and drops the word from recognition:

.. doctest::

    >>> lean = Lexicon.default().remove(titles={"professor"})
    >>> Parser(lexicon=lean).parse("Professor Robert Johns").title
    ''

A few fields mark a subset of another — ``given_name_titles`` over
``titles``, ``particles_ambiguous`` over ``particles``,
``suffix_acronyms_ambiguous`` over ``suffix_acronyms``. Entries must
appear in the base field too, so add to both and remove from the marker
first; anything else raises ``ValueError`` naming the orphans rather
than leaving a marker entry that no rule will ever consult.

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
leading word that ends in a period is read as a title structurally,
without consulting ``titles`` at all — that is what lets unfamiliar
ranks and abbreviations work (see :ref:`abbreviated-titles`):

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
particle listed there may also be a given name, so a name that starts
with one keeps its given name; a particle *not* listed there is never a
given name, so a name starting with it has no given name at all — the
whole thing is the surname:

.. doctest::

    >>> parse("van Gogh").given          # 'van' may be a given name
    'van'
    >>> parse("de Mesnil").given         # 'de' may not
    ''
    >>> parse("de Mesnil").family
    'de Mesnil'

If your data never uses ``Van`` as a given name, take it out of the
ambiguous set and leading ``van`` becomes part of the surname:

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
       instead, and drops them from the effective nickname set.
       Defaults to empty — see the routing example below.
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
       unaffected.
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

``name_order`` is the one most likely to matter for non-Western data.
Positional input is assigned in the order you declare, so a
family-first name parses as written instead of needing to be
rearranged afterwards:

.. doctest::

    >>> from nameparser import Parser, Policy, FAMILY_FIRST, parse
    >>> parse("Nguyen Van Minh").family              # default GIVEN_FIRST
    'Van Minh'
    >>> family_first = Parser(policy=Policy(name_order=FAMILY_FIRST))
    >>> name = family_first.parse("Nguyen Van Minh")
    >>> name.family, name.given
    ('Nguyen', 'Van Minh')

An explicit comma still wins, on the reasoning that someone who wrote
one meant it — so the same parser reads ``"Thomas, John"`` as
family-then-given regardless of the configured order:

.. doctest::

    >>> family_first.parse("Thomas, John").family
    'Thomas'

East Asian defaults, and turning them off
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two defaults key on the *script* a name is written in rather than on
anything you set: a name written wholly in Han or Hangul is assigned
family-first (``script_orders``), and an unspaced hangul name is split
into surname and given name against the shipped Korean census list
(``segment_scripts``). :ref:`east-asian-names` explains the naming
conventions both rest on — this section is how to switch them off,
which you can do separately:

.. doctest::

    >>> parse("김민준").family                    # both defaults on
    '김'
    >>> positional = Parser(policy=Policy(script_orders={}))
    >>> positional.parse("김민준").family         # still split
    '민준'
    >>> unsplit = Parser(policy=Policy(segment_scripts=()))
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

.. note::

   Both fields are annotated with their canonical *storage* type
   rather than with everything the constructor accepts — the same as
   ``capitalization_exceptions``. Under mypy the readable spellings
   above (``script_orders={...}``, ``segment_scripts=(...)``) need a
   ``# type: ignore[arg-type]``; ``script_orders=()`` and
   ``segment_scripts=frozenset(...)`` check clean and mean the same
   thing.

Nicknames, maiden names, and brackets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A delimiter pair routes to exactly one field, and ``maiden_delimiters``
states the more specific intent — so listing a pair there drops it from
the effective ``nickname_delimiters`` set automatically, and the
one-liner is the whole recipe:

.. doctest::

    >>> policy = Policy(maiden_delimiters={("(", ")")})
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

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

``capitalization_exceptions`` is the one pair-valued field — each entry
maps a lowercase key to its exact-cased replacement (``"phd"`` →
``"PhD"``), so it isn't a fit for ``add()``/``remove()``. Change it with
``dataclasses.replace()`` instead: ``dataclasses.replace(lex,
capitalization_exceptions=(("phd", "PhD"),))``.

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
       Ignored for comma-format input — the comma itself states the
       order ("Thomas, John" puts the family name first).
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
       :data:`~nameparser.DEFAULT_NICKNAME_DELIMITERS` — quotes and
       parentheses.
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

.. doctest::

    >>> from nameparser import Parser, Policy
    >>> policy = Policy(maiden_delimiters=frozenset({("(", ")")}))
    >>> Parser(policy=policy).parse("Jane (Jones) Smith").maiden
    'Jones'

A pair routes to exactly one field, and ``maiden_delimiters`` states
the specific intent — so listing a pair there automatically drops it
from the effective ``nickname_delimiters`` set, and the one-liner
above is the whole recipe. To *add* delimiters instead of rerouting
them, build on the named default:
``nickname_delimiters=DEFAULT_NICKNAME_DELIMITERS | {("«", "»")}``.

.. _rendering-arguments:

Presentation: rendering arguments
----------------------------------

Once a name is parsed, how it's displayed is a separate decision made
at the point of output, not baked into the parse:

.. code-block:: python

    def render(self, spec: str = "{title} {given} {middle} {family} {suffix}") -> str: ...
    def initials(self, spec: str = "{given} {middle} {family}",
                 delimiter: str = ".", separator: str = " ") -> str: ...
    def capitalized(self, lexicon: Lexicon | None = None, *, force: bool = False) -> ParsedName: ...

Looking for v1's ``string_format``? It's the ``render(spec)`` argument
now — pass your own format string per call instead of setting it once
on a shared config object. See :doc:`usage` for worked examples of all
three.

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
